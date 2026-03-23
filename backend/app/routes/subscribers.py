"""
Subscribers routes
- GET  /api/pro-trader/subscribers
- GET  /api/pro-trader/subscribers/stats
- POST /api/pro-trader/subscribers/notify
"""
import logging
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity
from datetime import datetime, timezone

from app import db
from app.middleware import require_pro_trader
from app.models.subscription import Subscription
from app.models.user import User
from app.models.profile import Profile
from app.services.notification_service import create_notification

logger = logging.getLogger(__name__)
subscribers_bp = Blueprint("subscribers", __name__)


@subscribers_bp.route("/subscribers", methods=["GET"])
@require_pro_trader
def get_subscribers():
    """Get active subscribers list."""
    user_id = get_jwt_identity()
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)

    now = datetime.now(timezone.utc)
    query = Subscription.query.filter_by(
        trader_id=user_id, status="active"
    ).filter(Subscription.ends_at > now).order_by(Subscription.started_at.desc())

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    subscribers = []
    for sub in paginated.items:
        sub_dict = sub.to_dict()
        prof = Profile.query.filter_by(user_id=sub.subscriber_id).first()
        if prof:
            sub_dict["subscriber_name"] = prof.display_name
            sub_dict["subscriber_avatar"] = prof.avatar_url
        subscribers.append(sub_dict)

    return jsonify({
        "subscribers": subscribers,
        "total": paginated.total,
        "page": page,
        "per_page": per_page,
        "pages": paginated.pages,
    }), 200


@subscribers_bp.route("/subscribers/stats", methods=["GET"])
@require_pro_trader
def get_subscriber_stats():
    """Get subscriber count stats."""
    user_id = get_jwt_identity()
    now = datetime.now(timezone.utc)

    active_count = Subscription.query.filter_by(
        trader_id=user_id, status="active"
    ).filter(Subscription.ends_at > now).count()

    total_ever = Subscription.query.filter_by(trader_id=user_id).count()
    expired_count = Subscription.query.filter_by(
        trader_id=user_id, status="expired"
    ).count()

    return jsonify({
        "active_subscribers": active_count,
        "total_subscribers_ever": total_ever,
        "expired_subscribers": expired_count,
    }), 200


@subscribers_bp.route("/subscribers/notify", methods=["POST"])
@require_pro_trader
def notify_subscribers():
    """Send a notification to all active subscribers."""
    user_id = get_jwt_identity()
    data = request.get_json() or {}

    title = data.get("title", "").strip()
    message = data.get("message", "").strip()

    if not title or not message:
        return jsonify({"error": "Title and message are required"}), 400
    if len(title) > 100:
        return jsonify({"error": "Title too long (max 100 chars)"}), 400
    if len(message) > 1000:
        return jsonify({"error": "Message too long (max 1000 chars)"}), 400

    now = datetime.now(timezone.utc)
    active_subs = Subscription.query.filter_by(
        trader_id=user_id, status="active"
    ).filter(Subscription.ends_at > now).all()

    sent_count = 0
    for sub in active_subs:
        try:
            create_notification(
                user_id=sub.subscriber_id,
                notification_type="platform_update",
                title=title,
                message=message,
                data={"from_trader_id": user_id},
            )
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to notify subscriber {sub.subscriber_id}: {e}")

    return jsonify({
        "message": f"Notification sent to {sent_count} subscriber(s)",
        "sent_count": sent_count,
    }), 200
