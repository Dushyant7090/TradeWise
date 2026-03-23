"""
Pro-Trader Profile routes
- GET /api/pro-trader/profile
- PUT /api/pro-trader/profile
- PUT /api/pro-trader/profile/picture
- GET /api/pro-trader/dashboard
"""
import logging
import os
import uuid
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from app import db
from app.middleware import require_pro_trader
from app.models.profile import Profile
from app.models.pro_trader_profile import ProTraderProfile
from app.models.trade import Trade
from app.models.subscription import Subscription
from app.utils.validators import validate_bio

logger = logging.getLogger(__name__)
profile_bp = Blueprint("profile", __name__)


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
        if not isinstance(specs, list):
            return jsonify({"error": "specializations must be a list"}), 400
        pt_profile.specializations = specs

    if "external_portfolio_url" in data:
        pt_profile.external_portfolio_url = data["external_portfolio_url"]

    if "years_of_experience" in data:
        try:
            pt_profile.years_of_experience = int(data["years_of_experience"])
        except (ValueError, TypeError):
            return jsonify({"error": "years_of_experience must be an integer"}), 400

    if "trading_style" in data:
        style = data["trading_style"]
        if style not in ProTraderProfile.VALID_TRADING_STYLES:
            return jsonify({
                "error": f"Invalid trading_style. Must be one of: {ProTraderProfile.VALID_TRADING_STYLES}"
            }), 400
        pt_profile.trading_style = style

    # Update display name in profile table too
    profile = Profile.query.filter_by(user_id=user_id).first()
    if profile and "display_name" in data:
        profile.display_name = data["display_name"].strip()

    db.session.commit()
    return jsonify({"message": "Profile updated successfully", "profile": pt_profile.to_dict()}), 200


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
        public_url = supabase_storage.upload_file(
            bucket="profile-pictures",
            path=filename,
            file_data=file_data,
            content_type=file.content_type,
        )
        pt_profile.profile_picture_url = public_url
        # Also update profile avatar
        profile = Profile.query.filter_by(user_id=user_id).first()
        if profile:
            profile.avatar_url = public_url
        db.session.commit()
        return jsonify({"message": "Profile picture updated", "url": public_url}), 200
    except Exception as e:
        logger.error(f"Profile picture upload error: {e}")
        return jsonify({"error": "Failed to upload profile picture"}), 500


@profile_bp.route("/dashboard", methods=["GET"])
@require_pro_trader
def get_dashboard():
    """Get dashboard stats: accuracy, earnings, subscribers, trade counts."""
    user_id = get_jwt_identity()
    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt_profile:
        return jsonify({"error": "Pro trader profile not found"}), 404

    # Active subscribers
    active_subs = Subscription.query.filter_by(trader_id=user_id, status="active").count()

    # Trade counts
    active_trades = Trade.query.filter_by(trader_id=user_id, status="active").count()
    total_trades = Trade.query.filter(
        Trade.trader_id == user_id,
        Trade.status.in_(["target_hit", "sl_hit"])
    ).count()

    return jsonify({
        "accuracy_score": float(pt_profile.accuracy_score or 0),
        "total_earnings": float(pt_profile.total_earnings or 0),
        "available_balance": float(pt_profile.available_balance or 0),
        "total_subscribers": active_subs,
        "active_trades": active_trades,
        "total_closed_trades": total_trades,
        "winning_trades": pt_profile.winning_trades,
        "leaderboard_rank": pt_profile.leaderboard_rank,
        "kyc_status": pt_profile.kyc_status,
        "monthly_subscription_price": float(pt_profile.monthly_subscription_price or 0),
    }), 200
