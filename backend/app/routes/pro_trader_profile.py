"""
Pro-Trader Profile routes
- GET /api/pro-trader/profile
- PUT /api/pro-trader/profile
- PUT /api/pro-trader/profile/picture
- GET /api/pro-trader/dashboard
- GET /api/pro-trader/onboarding-state
- PUT /api/pro-trader/onboarding/step1
- PUT /api/pro-trader/onboarding/step2
- PUT /api/pro-trader/onboarding/step3
- POST /api/pro-trader/onboarding/skip
"""
import logging
import os
import uuid
import json
from datetime import datetime, timezone
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import func

from app import db
from app.middleware import require_pro_trader
from app.models.profile import Profile
from app.models.pro_trader_profile import ProTraderProfile
from app.models.payment import Payment
from app.models.revenue_split import RevenueSplit
from app.models.trade import Trade
from app.models.subscription import Subscription
from app.models.subscription_plan import SubscriptionPlan
from app.utils.validators import validate_bio
from app.utils.pro_trader_state import get_pro_trader_state, check_pending_eligibility, get_state_response
from app.utils.response_cache import cache_response

logger = logging.getLogger(__name__)
profile_bp = Blueprint("profile", __name__)


def _normalize_specializations(value):
    """Return a clean list of specialization strings from list/json/comma formats."""
    if value is None:
        return []

    parsed = value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            maybe_json = json.loads(raw)
            parsed = maybe_json
        except (ValueError, TypeError):
            parsed = [item.strip() for item in raw.split(",") if item and item.strip()]

    if not isinstance(parsed, list):
        parsed = [parsed]

    cleaned_specs = []
    seen = set()
    for item in parsed:
        if item is None:
            continue
        spec = str(item).strip().lower()
        if not spec or spec in seen:
            continue
        seen.add(spec)
        cleaned_specs.append(spec)

    return cleaned_specs


@profile_bp.route("/profile", methods=["GET"])
@require_pro_trader
def get_profile():
    """Get pro trader profile."""
    user_id = get_jwt_identity()
    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt_profile:
        return jsonify({"error": "Pro trader profile not found"}), 404

    profile = Profile.query.filter_by(user_id=user_id).first()
    data = pt_profile.to_dict()
    data["specializations"] = _normalize_specializations(pt_profile.specializations)
    if profile:
        data["display_name"] = profile.display_name
        data["avatar_url"] = profile.avatar_url
        data["is_verified"] = profile.is_verified

    return jsonify(data), 200


@profile_bp.route("/profile", methods=["PUT"])
@require_pro_trader
def update_profile():
    """Update pro trader profile (bio, specializations, experience, trading_style, etc.)."""
    user_id = get_jwt_identity()
    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt_profile:
        return jsonify({"error": "Pro trader profile not found"}), 404

    data = request.get_json() or {}

    # Bio validation
    if "bio" in data:
        bio = data["bio"].strip()
        valid, msg = validate_bio(bio)
        if not valid:
            return jsonify({"error": msg}), 400
        pt_profile.bio = bio

    if "specializations" in data:
        specs = data["specializations"]
        normalized_specs = _normalize_specializations(specs)
        pt_profile.specializations = normalized_specs

    if "external_portfolio_url" in data:
        pt_profile.external_portfolio_url = data["external_portfolio_url"]

    if "years_of_experience" in data:
        try:
            years_value = data["years_of_experience"]
            if years_value is None or str(years_value).strip() == "":
                pt_profile.years_of_experience = 0
            else:
                years_int = int(years_value)
                if years_int < 0:
                    return jsonify({"error": "years_of_experience must be 0 or greater"}), 400
                pt_profile.years_of_experience = years_int
        except (ValueError, TypeError):
            return jsonify({"error": "years_of_experience must be an integer"}), 400

    if "trading_style" in data:
        style = data["trading_style"]
        style_aliases = {
            "day_trading": "intraday",
            "swing_trading": "swing",
            "position_trading": "positional",
            "longterm": "long_term",
        }
        if isinstance(style, str):
            style = style_aliases.get(style.strip().lower(), style.strip().lower())
        if style is None or str(style).strip() == "":
            pt_profile.trading_style = None
        elif style not in ProTraderProfile.VALID_TRADING_STYLES:
            return jsonify({
                "error": f"Invalid trading_style. Must be one of: {ProTraderProfile.VALID_TRADING_STYLES}"
            }), 400
        else:
            pt_profile.trading_style = style

    # Update display name in profile table too
    profile = Profile.query.filter_by(user_id=user_id).first()
    if profile and "display_name" in data:
        profile.display_name = data["display_name"].strip()

    db.session.commit()

    response_profile = pt_profile.to_dict()
    if profile:
        response_profile["display_name"] = profile.display_name
        response_profile["avatar_url"] = profile.avatar_url
        response_profile["is_verified"] = profile.is_verified

    return jsonify({"message": "Profile updated successfully", "profile": response_profile}), 200


@profile_bp.route("/profile/picture", methods=["PUT"])
@require_pro_trader
def upload_profile_picture():
    """Upload/update profile picture to Supabase Storage."""
    user_id = get_jwt_identity()
    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt_profile:
        return jsonify({"error": "Pro trader profile not found"}), 404

    if "picture" not in request.files:
        return jsonify({"error": "No picture file provided"}), 400

    file = request.files["picture"]
    if not file.filename:
        return jsonify({"error": "Empty file"}), 400

    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        return jsonify({"error": "Invalid file type. Use JPEG, PNG, or WebP"}), 400

    file_data = file.read()
    if len(file_data) > 5 * 1024 * 1024:  # 5 MB limit
        return jsonify({"error": "File too large. Max 5MB"}), 400

    ext = file.filename.rsplit(".", 1)[-1].lower()
    filename = f"profiles/{user_id}/{uuid.uuid4()}.{ext}"

    try:
        from app.services.supabase_storage import supabase_storage
        bucket = current_app.config.get("PROFILE_PICTURES_BUCKET", "profile-pictures")
        public_url = supabase_storage.upload_file(
            bucket=bucket,
            path=filename,
            file_data=file_data,
            content_type=file.content_type,
        )
        pt_profile.profile_picture_url = public_url
        # Also update profile avatar; create profile row defensively if missing.
        profile = Profile.query.filter_by(user_id=user_id).first()
        if not profile:
            profile = Profile(user_id=user_id, role="pro_trader")
            db.session.add(profile)
        profile.avatar_url = public_url
        db.session.commit()
        return jsonify({"message": "Profile picture updated", "url": public_url}), 200
    except Exception as e:
        logger.error(f"Profile picture upload error: {e}")
        return jsonify({"error": "Failed to upload profile picture"}), 500


@profile_bp.route("/dashboard", methods=["GET"])
@require_pro_trader
@cache_response(ttl_seconds=15, key_prefix="pro_dashboard")
def get_dashboard():
    """Get dashboard stats: accuracy, earnings, subscribers, trade counts + verification state."""
    user_id = get_jwt_identity()
    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt_profile:
        return jsonify({"error": "Pro trader profile not found"}), 404

    profile = Profile.query.filter_by(user_id=user_id).first()

    # Active subscribers
    now = datetime.now(timezone.utc)
    active_subs = Subscription.query.filter(
        Subscription.trader_id == user_id,
        Subscription.status == "active",
        Subscription.ends_at > now,
    ).count()

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_earnings = db.session.query(func.coalesce(func.sum(RevenueSplit.pro_trader_amount), 0)).join(
        Payment, RevenueSplit.payment_id == Payment.id
    ).filter(
        RevenueSplit.trader_id == user_id,
        Payment.status == "success",
        Payment.completed_at >= month_start,
    ).scalar()

    # Trade counts
    active_trades = Trade.query.filter_by(trader_id=user_id, status="active").count()
    total_trades = Trade.query.filter(
        Trade.trader_id == user_id,
        Trade.status.in_(["target_hit", "sl_hit"])
    ).count()

    # Verification state
    state_info = get_state_response(profile, pt_profile)

    return jsonify({
        "accuracy_score": float(pt_profile.accuracy_score or 0),
        "total_earnings": float(pt_profile.total_earnings or 0),
        "monthly_earnings": float(monthly_earnings or 0),
        "available_balance": float(pt_profile.available_balance or 0),
        "total_subscribers": active_subs,
        "active_trades": active_trades,
        "total_closed_trades": total_trades,
        "winning_trades": pt_profile.winning_trades,
        "leaderboard_rank": pt_profile.leaderboard_rank,
        "kyc_status": pt_profile.kyc_status,
        "monthly_subscription_price": float(pt_profile.monthly_subscription_price or 0),
        # Verification state fields
        **state_info,
    }), 200


# ---------------------------------------------------------------------------
# Onboarding Endpoints
# ---------------------------------------------------------------------------

@profile_bp.route("/onboarding-state", methods=["GET"])
@require_pro_trader
def get_onboarding_state():
    """Get current onboarding state and eligibility for the authenticated pro-trader."""
    user_id = get_jwt_identity()
    profile = Profile.query.filter_by(user_id=user_id).first()
    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()

    if not pt_profile:
        return jsonify({"error": "Pro trader profile not found"}), 404

    state_info = get_state_response(profile, pt_profile)

    # Also include subscription plans count
    plans_count = SubscriptionPlan.query.filter_by(trader_id=user_id, is_active=True).count()
    state_info["has_subscription_plans"] = plans_count > 0
    state_info["subscription_plans_count"] = plans_count

    return jsonify(state_info), 200


@profile_bp.route("/onboarding/step1", methods=["PUT"])
@require_pro_trader
def onboarding_step1():
    """
    Step 1: Profile basics — bio, specializations, trading style.
    On success: sets onboarding_step = 1 (EXPLORER state).
    Idempotent — safe to call multiple times.
    """
    user_id = get_jwt_identity()
    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt_profile:
        return jsonify({"error": "Pro trader profile not found"}), 404

    data = request.get_json() or {}

    # Bio (required for step 1)
    bio = (data.get("bio") or "").strip()
    if not bio:
        return jsonify({"error": "Bio is required for Step 1"}), 400
    valid, msg = validate_bio(bio)
    if not valid:
        return jsonify({"error": msg}), 400
    pt_profile.bio = bio

    # Specializations (optional but encouraged)
    if "specializations" in data:
        pt_profile.specializations = _normalize_specializations(data["specializations"])

    # Trading style (optional)
    if "trading_style" in data:
        style = data["trading_style"]
        style_aliases = {
            "day_trading": "intraday",
            "swing_trading": "swing",
            "position_trading": "positional",
            "longterm": "long_term",
        }
        if isinstance(style, str):
            style = style_aliases.get(style.strip().lower(), style.strip().lower())
        if style and style in ProTraderProfile.VALID_TRADING_STYLES:
            pt_profile.trading_style = style

    # Years of experience (optional)
    if "years_of_experience" in data:
        try:
            years = int(data["years_of_experience"])
            if years >= 0:
                pt_profile.years_of_experience = years
        except (ValueError, TypeError):
            pass

    # Display name
    if "display_name" in data:
        profile = Profile.query.filter_by(user_id=user_id).first()
        if profile:
            profile.display_name = data["display_name"].strip()

    # Set onboarding step to at least 1
    if pt_profile.onboarding_step < 1:
        pt_profile.onboarding_step = 1

    db.session.commit()

    profile = Profile.query.filter_by(user_id=user_id).first()
    state_info = get_state_response(profile, pt_profile)

    return jsonify({
        "message": "Step 1 complete — Welcome to Explorer mode!",
        "onboarding_step": pt_profile.onboarding_step,
        **state_info,
    }), 200


@profile_bp.route("/onboarding/step2", methods=["PUT"])
@require_pro_trader
def onboarding_step2():
    """
    Step 2: Financial setup — mock Cashfree vendor creation.
    Idempotent: if cf_seller_id already set, returns existing ID.
    On success: sets onboarding_step = 2.
    """
    user_id = get_jwt_identity()
    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt_profile:
        return jsonify({"error": "Pro trader profile not found"}), 404

    # Must have completed step 1
    if pt_profile.onboarding_step < 1:
        return jsonify({"error": "Please complete Step 1 (profile setup) first"}), 400

    # Idempotent: if already linked, return existing
    if pt_profile.cf_seller_id:
        profile = Profile.query.filter_by(user_id=user_id).first()
        state_info = get_state_response(profile, pt_profile)
        return jsonify({
            "message": "Financial setup already complete",
            "cf_seller_id": pt_profile.cf_seller_id,
            "onboarding_step": pt_profile.onboarding_step,
            **state_info,
        }), 200

    # Generate mock Cashfree vendor ID (sandbox/test mode)
    mock_seller_id = f"cf_vendor_{uuid.uuid4().hex[:16]}"
    pt_profile.cf_seller_id = mock_seller_id

    # Set onboarding step to at least 2
    if pt_profile.onboarding_step < 2:
        pt_profile.onboarding_step = 2

    db.session.commit()

    profile = Profile.query.filter_by(user_id=user_id).first()
    state_info = get_state_response(profile, pt_profile)

    return jsonify({
        "message": "Financial setup complete — Cashfree vendor linked!",
        "cf_seller_id": mock_seller_id,
        "onboarding_step": pt_profile.onboarding_step,
        **state_info,
    }), 200


@profile_bp.route("/onboarding/step3", methods=["PUT"])
@require_pro_trader
def onboarding_step3():
    """
    Step 3: Subscription pricing + submit for review.
    Stores pricing in paise (integer). Validates PENDING eligibility
    before setting is_review_pending = true.
    """
    user_id = get_jwt_identity()
    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt_profile:
        return jsonify({"error": "Pro trader profile not found"}), 404

    # Must have completed step 1
    if pt_profile.onboarding_step < 1:
        return jsonify({"error": "Please complete Step 1 (profile setup) first"}), 400

    data = request.get_json() or {}

    # Handle subscription plan pricing
    plans_data = data.get("plans", [])
    if plans_data:
        for plan_info in plans_data:
            plan_name = plan_info.get("plan_name", "1 Month").strip()
            duration = int(plan_info.get("duration_months", 1))
            price_inr = plan_info.get("price_inr")
            price_paise = plan_info.get("price_paise")

            # Accept price in INR and convert, or accept paise directly
            if price_paise is not None:
                paise = int(price_paise)
            elif price_inr is not None:
                paise = int(float(price_inr) * 100)
            else:
                return jsonify({"error": "Each plan requires price_inr or price_paise"}), 400

            if paise < 0:
                return jsonify({"error": "Price cannot be negative"}), 400

            # Upsert: update existing plan or create new
            existing = SubscriptionPlan.query.filter_by(
                trader_id=user_id,
                duration_months=duration,
                is_active=True,
            ).first()

            if existing:
                existing.plan_name = plan_name
                existing.price_paise = paise
            else:
                new_plan = SubscriptionPlan(
                    trader_id=user_id,
                    plan_name=plan_name,
                    duration_months=duration,
                    price_paise=paise,
                )
                db.session.add(new_plan)

    # Also update the legacy monthly_subscription_price field for compatibility
    if "monthly_subscription_price" in data:
        try:
            price = float(data["monthly_subscription_price"])
            if price >= 0:
                pt_profile.monthly_subscription_price = price
        except (TypeError, ValueError):
            pass

    # Set onboarding step to 3
    if pt_profile.onboarding_step < 3:
        pt_profile.onboarding_step = 3

    # Check PENDING eligibility before marking for review
    eligible, missing = check_pending_eligibility(pt_profile)
    if eligible:
        pt_profile.is_review_pending = True
        db.session.commit()
        profile = Profile.query.filter_by(user_id=user_id).first()
        state_info = get_state_response(profile, pt_profile)
        return jsonify({
            "message": "Submission complete — your profile is under admin review!",
            "onboarding_step": pt_profile.onboarding_step,
            "is_review_pending": True,
            **state_info,
        }), 200
    else:
        # Save partial progress but don't mark for review
        db.session.commit()
        profile = Profile.query.filter_by(user_id=user_id).first()
        state_info = get_state_response(profile, pt_profile)
        return jsonify({
            "message": "Pricing saved, but some requirements are still incomplete.",
            "onboarding_step": pt_profile.onboarding_step,
            "is_review_pending": False,
            "pending_missing": missing,
            **state_info,
        }), 200


@profile_bp.route("/onboarding/skip", methods=["POST"])
@require_pro_trader
def onboarding_skip():
    """
    Skip remaining onboarding steps — save partial progress and redirect to dashboard.
    Does NOT wipe any previously saved data.
    Requires at least Step 1 to be complete.
    """
    user_id = get_jwt_identity()
    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt_profile:
        return jsonify({"error": "Pro trader profile not found"}), 404

    if pt_profile.onboarding_step < 1:
        return jsonify({"error": "Please complete Step 1 (profile setup) before skipping"}), 400

    # Save any partial data sent with the skip request
    data = request.get_json() or {}
    if "bio" in data and data["bio"]:
        pt_profile.bio = data["bio"].strip()
    if "specializations" in data:
        pt_profile.specializations = _normalize_specializations(data["specializations"])

    db.session.commit()

    profile = Profile.query.filter_by(user_id=user_id).first()
    state_info = get_state_response(profile, pt_profile)

    return jsonify({
        "message": "Progress saved — redirecting to dashboard. You can complete remaining steps anytime.",
        "redirect": "dashboard.html",
        "onboarding_step": pt_profile.onboarding_step,
        **state_info,
    }), 200
