"""
Learner Profile routes
- GET  /api/learner/profile
- PUT  /api/learner/profile
- PUT  /api/learner/profile/picture
- GET  /api/learner/dashboard
"""
import logging
import mimetypes
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import case, func

from app import db
from app.middleware import require_auth
from app.models.learner_profile import LearnerProfile
from app.models.profile import Profile
from app.models.subscription import Subscription
from app.models.learner_trade_unlock import LearnerUnlockedTrade
from app.models.learner_credit_transaction import LearnerCreditsLog
from app.models.learner_notification import LearnerNotification
from app.models.trade import Trade
from app.models.pro_trader_profile import ProTraderProfile
from app.services.supabase_storage import supabase_storage
from app.utils.response_cache import cache_response
from flask import current_app

logger = logging.getLogger(__name__)
learner_profile_bp = Blueprint("learner_profile", __name__)


def _get_learner_profile_or_404(user_id):
    learner = LearnerProfile.query.filter_by(user_id=user_id).first()
    if not learner:
        return None, jsonify({"error": "Learner profile not found"}), 404
    return learner, None, None


@learner_profile_bp.route("/profile", methods=["GET"])
@require_auth
def get_learner_profile():
    """Get the authenticated learner's profile."""
    user_id = get_jwt_identity()
    learner, err, code = _get_learner_profile_or_404(user_id)
    if err:
        return err, code

    profile = Profile.query.filter_by(user_id=user_id).first()
    result = learner.to_dict()
    if profile:
        result["display_name"] = profile.display_name
        result["avatar_url"] = profile.avatar_url

    return jsonify(result), 200


@learner_profile_bp.route("/profile", methods=["PUT"])
@require_auth
def update_learner_profile():
    """Update learner profile fields."""
    user_id = get_jwt_identity()
    learner, err, code = _get_learner_profile_or_404(user_id)
    if err:
        return err, code

    data = request.get_json() or {}

    if "interests" in data:
        interests = data["interests"]
        if not isinstance(interests, list):
            return jsonify({"error": "interests must be a list"}), 400
        learner.interests = interests

    if "experience_level" in data:
        level = data["experience_level"]
        if level not in LearnerProfile.VALID_EXPERIENCE_LEVELS:
            return jsonify({"error": f"experience_level must be one of {LearnerProfile.VALID_EXPERIENCE_LEVELS}"}), 400
        learner.experience_level = level

    if "learning_goal" in data:
        goal = data["learning_goal"]
        if goal not in LearnerProfile.VALID_LEARNING_GOALS:
            return jsonify({"error": f"learning_goal must be one of {LearnerProfile.VALID_LEARNING_GOALS}"}), 400
        learner.learning_goal = goal

    if "favorite_traders" in data:
        traders = data["favorite_traders"]
        if not isinstance(traders, list):
            return jsonify({"error": "favorite_traders must be a list"}), 400
        learner.favorite_traders = traders

    # Update base profile fields too
    profile = Profile.query.filter_by(user_id=user_id).first()
    if profile:
        if "display_name" in data:
            profile.display_name = data["display_name"]

    db.session.commit()

    result = learner.to_dict()
    if profile:
        result["display_name"] = profile.display_name
        result["avatar_url"] = profile.avatar_url

    return jsonify({"message": "Profile updated", "profile": result}), 200


@learner_profile_bp.route("/profile/picture", methods=["PUT"])
@require_auth
def upload_profile_picture():
    """Upload a profile picture to Supabase Storage."""
    user_id = get_jwt_identity()
    learner, err, code = _get_learner_profile_or_404(user_id)
    if err:
        return err, code

    # Accept both keys for backward compatibility across frontend bundles.
    file = request.files.get("file") or request.files.get("picture")
    if not file and request.files:
        file = next(iter(request.files.values()))
    if not file:
        return jsonify({
            "error": "No file uploaded. Use multipart/form-data with field 'file'."
        }), 400

    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    allowed = {"image/jpeg", "image/png", "image/webp"}
    file_content_type = (file.content_type or "").lower().strip()
    guessed_type, _ = mimetypes.guess_type(file.filename)
    guessed_type = (guessed_type or "").lower().strip()
    if file_content_type == "image/jpg":
        file_content_type = "image/jpeg"
    if guessed_type == "image/jpg":
        guessed_type = "image/jpeg"
    effective_content_type = file_content_type or guessed_type

    if effective_content_type not in allowed:
        return jsonify({
            "error": "Only JPEG, PNG, and WebP images are allowed",
            "received_content_type": file_content_type or None,
            "filename": file.filename,
        }), 400

    try:
        file_data = file.read()
        ext = (effective_content_type.split("/")[-1] if effective_content_type else "jpeg")
        path = f"learner-avatars/{user_id}.{ext}"
        bucket = current_app.config.get("PROFILE_PICTURES_BUCKET", "profile-pictures")
        url = supabase_storage.upload_file(bucket, path, file_data, effective_content_type)
        profile = Profile.query.filter_by(user_id=user_id).first()
        if profile:
            profile.avatar_url = url
            db.session.commit()
        return jsonify({"message": "Profile picture updated", "avatar_url": url}), 200
    except Exception as e:
        logger.error(f"Profile picture upload error: {e}")
        return jsonify({"error": "Upload failed"}), 500


@learner_profile_bp.route("/dashboard", methods=["GET"])
@require_auth
@cache_response(ttl_seconds=10, key_prefix="learner_dashboard")
def get_dashboard():
    """Get learner dashboard summary."""
    user_id = get_jwt_identity()
    learner, err, code = _get_learner_profile_or_404(user_id)
    if err:
        return err, code

    profile = Profile.query.filter_by(user_id=user_id).first()

    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)

    # Keep dashboard totals accurate by deriving from unlock records.
    total_unlocked = LearnerUnlockedTrade.query.filter_by(learner_id=user_id).count()
    totals_synced = False
    if (learner.total_unlocked_trades or 0) != total_unlocked:
        learner.total_unlocked_trades = total_unlocked
        totals_synced = True

    # Recent unlocked trades (last 5)
    recent_unlock_rows = (
        db.session.query(LearnerUnlockedTrade, Trade)
        .join(Trade, Trade.id == LearnerUnlockedTrade.trade_id)
        .filter(LearnerUnlockedTrade.learner_id == user_id)
        .order_by(LearnerUnlockedTrade.unlocked_at.desc())
        .limit(5)
        .all()
    )
    recent_trades = []
    for unlock, trade in recent_unlock_rows:
        recent_trades.append({
            "trade_id": trade.id,
            "symbol": trade.symbol,
            "status": trade.status,
            "outcome": trade.outcome,
            "unlocked_at": unlock.unlocked_at.isoformat(),
        })

    # Win rate observed from unlocked trades that have closed outcomes.
    wins, losses = (
        db.session.query(
            func.coalesce(func.sum(case((Trade.status == "target_hit", 1), else_=0)), 0),
            func.coalesce(func.sum(case((Trade.status == "sl_hit", 1), else_=0)), 0),
        )
        .join(LearnerUnlockedTrade, LearnerUnlockedTrade.trade_id == Trade.id)
        .filter(
            LearnerUnlockedTrade.learner_id == user_id,
            Trade.status.in_(["target_hit", "sl_hit"]),
        )
        .first()
    )
    wins = int(wins or 0)
    losses = int(losses or 0)
    total_closed = wins + losses
    win_rate = round((wins / total_closed) * 100, 2) if total_closed > 0 else None

    # Recent streak based on consecutive unlock dates ending on the latest activity day.
    unlock_date_rows = (
        db.session.query(LearnerUnlockedTrade.unlocked_at)
        .filter(LearnerUnlockedTrade.learner_id == user_id)
        .all()
    )
    unlock_dates = {
        row[0].date() for row in unlock_date_rows if row[0] is not None
    }
    streak = 0
    if unlock_dates:
        cursor = max(unlock_dates)
        while cursor in unlock_dates:
            streak += 1
            cursor = cursor - timedelta(days=1)

    # Learning progress chart (last 7 days cumulative unlocks).
    chart_start_date = now.date() - timedelta(days=6)
    chart_labels = []
    chart_values = []

    unlock_rows_in_window = (
        db.session.query(LearnerUnlockedTrade.unlocked_at)
        .filter(
            LearnerUnlockedTrade.learner_id == user_id,
            LearnerUnlockedTrade.unlocked_at >= datetime.combine(chart_start_date, datetime.min.time(), tzinfo=timezone.utc),
        )
        .all()
    )
    unlock_counts_by_day = {}
    for row in unlock_rows_in_window:
        if not row[0]:
            continue
        day = row[0].date()
        unlock_counts_by_day[day] = unlock_counts_by_day.get(day, 0) + 1

    running_total = (
        db.session.query(LearnerUnlockedTrade)
        .filter(
            LearnerUnlockedTrade.learner_id == user_id,
            LearnerUnlockedTrade.unlocked_at < datetime.combine(chart_start_date, datetime.min.time(), tzinfo=timezone.utc),
        )
        .count()
    )

    for offset in range(7):
        day = chart_start_date + timedelta(days=offset)
        running_total += unlock_counts_by_day.get(day, 0)
        chart_labels.append(day.strftime("%d %b"))
        chart_values.append(running_total)

    # Active subscriptions count
    active_subs = Subscription.query.filter(
        Subscription.subscriber_id == user_id,
        Subscription.status == "active",
        Subscription.ends_at > now,
    ).count()

    # Featured pro traders (top 5 by accuracy)
    top_trader_rows = (
        db.session.query(ProTraderProfile, Profile)
        .join(Profile, Profile.user_id == ProTraderProfile.user_id)
        .filter(ProTraderProfile.is_active == True)
        .order_by(ProTraderProfile.accuracy_score.desc())
        .limit(5)
        .all()
    )
    featured_traders = []
    for pt, prof in top_trader_rows:
        featured_traders.append({
            "trader_id": pt.user_id,
            "display_name": prof.display_name if prof else "Unknown",
            "accuracy_score": float(pt.accuracy_score or 0),
            "total_subscribers": pt.total_subscribers,
            "monthly_subscription_price": float(pt.monthly_subscription_price or 0),
            "profile_picture_url": pt.profile_picture_url,
            "avatar_url": prof.avatar_url if prof else None,
        })

    unread_notifications = LearnerNotification.query.filter_by(
        learner_id=user_id,
        is_read=False,
    ).count()

    if totals_synced:
        db.session.commit()

    return jsonify({
        "credits": learner.credits,
        "total_unlocked": total_unlocked,
        "total_unlocked_trades": total_unlocked,
        "total_spent": float(learner.total_spent or 0),
        "active_subscriptions": active_subs,
        "win_rate": win_rate,
        "wins": wins,
        "losses": losses,
        "streak": streak,
        "chart_data": {
            "labels": chart_labels,
            "values": chart_values,
        },
        "profile": {
            "display_name": profile.display_name if profile else None,
            "avatar_url": profile.avatar_url if profile else None,
        },
        "unread_notifications": unread_notifications,
        "recent_trades": recent_trades,
        "featured_traders": featured_traders,
    }), 200
