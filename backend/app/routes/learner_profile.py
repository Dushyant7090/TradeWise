"""
Learner Profile routes
- GET  /api/learner/profile
- PUT  /api/learner/profile
- PUT  /api/learner/profile/picture
- GET  /api/learner/dashboard
"""
import logging
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from app import db
from app.middleware import require_auth
from app.models.learner_profile import LearnerProfile
from app.models.profile import Profile
from app.models.subscription import Subscription
from app.models.learner_unlocked_trade import LearnerUnlockedTrade
from app.models.learner_credits_log import LearnerCreditsLog
from app.models.trade import Trade
from app.models.pro_trader_profile import ProTraderProfile
from app.services.supabase_storage import supabase_storage

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
        learner.learning_goal = data["learning_goal"]

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

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    allowed = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed:
        return jsonify({"error": "Only JPEG, PNG, and WebP images are allowed"}), 400

    try:
        file_data = file.read()
        ext = file.content_type.split("/")[-1]
        path = f"learner-avatars/{user_id}.{ext}"
        url = supabase_storage.upload_file("avatars", path, file_data, file.content_type)
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
def get_dashboard():
    """Get learner dashboard summary."""
    user_id = get_jwt_identity()
    learner, err, code = _get_learner_profile_or_404(user_id)
    if err:
        return err, code

    # Recent unlocked trades (last 5)
    from datetime import datetime, timezone
    recent_unlocks = (
        LearnerUnlockedTrade.query.filter_by(learner_id=user_id)
        .order_by(LearnerUnlockedTrade.unlocked_at.desc())
        .limit(5)
        .all()
    )
    recent_trades = []
    for unlock in recent_unlocks:
        trade = Trade.query.get(unlock.trade_id)
        if trade:
            t = {
                "trade_id": trade.id,
                "symbol": trade.symbol,
                "status": trade.status,
                "outcome": trade.outcome,
                "unlocked_at": unlock.unlocked_at.isoformat(),
            }
            recent_trades.append(t)

    # Active subscriptions count
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    active_subs = Subscription.query.filter(
        Subscription.subscriber_id == user_id,
        Subscription.status == "active",
        Subscription.ends_at > now,
    ).count()

    # Featured pro traders (top 5 by accuracy)
    top_traders = (
        ProTraderProfile.query.filter_by(is_active=True)
        .order_by(ProTraderProfile.accuracy_score.desc())
        .limit(5)
        .all()
    )
    featured_traders = []
    for pt in top_traders:
        prof = Profile.query.filter_by(user_id=pt.user_id).first()
        featured_traders.append({
            "trader_id": pt.user_id,
            "display_name": prof.display_name if prof else "Unknown",
            "accuracy_score": float(pt.accuracy_score or 0),
            "total_subscribers": pt.total_subscribers,
            "monthly_subscription_price": float(pt.monthly_subscription_price or 0),
            "profile_picture_url": pt.profile_picture_url,
        })

    return jsonify({
        "credits": learner.credits,
        "total_unlocked_trades": learner.total_unlocked_trades,
        "total_spent": float(learner.total_spent or 0),
        "active_subscriptions": active_subs,
        "recent_trades": recent_trades,
        "featured_traders": featured_traders,
    }), 200
