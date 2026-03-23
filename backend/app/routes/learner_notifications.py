"""
Learner Notifications routes
- GET    /api/learner/notifications
- PUT    /api/learner/notifications/{id}/read
- DELETE /api/learner/notifications/{id}
- POST   /api/learner/notifications/clear-all
- GET    /api/learner/notification-preferences
- PUT    /api/learner/notification-preferences
"""
import logging
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from app import db
from app.middleware import require_auth
from app.models.learner_notification import LearnerNotification
from app.models.learner_notification_preferences import LearnerNotificationPreferences

logger = logging.getLogger(__name__)
learner_notifications_bp = Blueprint("learner_notifications", __name__)


@learner_notifications_bp.route("/notifications", methods=["GET"])
@require_auth
def get_notifications():
    """Get all notifications for the learner."""
    user_id = get_jwt_identity()
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)
    unread_only = request.args.get("unread_only", "false").lower() == "true"

    query = LearnerNotification.query.filter_by(learner_id=user_id)
    if unread_only:
        query = query.filter_by(is_read=False)
    query = query.order_by(LearnerNotification.created_at.desc())
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    unread_count = LearnerNotification.query.filter_by(
        learner_id=user_id, is_read=False
    ).count()

    return jsonify({
        "notifications": [n.to_dict() for n in paginated.items],
        "unread_count": unread_count,
        "total": paginated.total,
        "page": page,
        "per_page": per_page,
        "pages": paginated.pages,
    }), 200


@learner_notifications_bp.route("/notifications/<notification_id>/read", methods=["PUT"])
@require_auth
def mark_notification_read(notification_id):
    """Mark a notification as read."""
    user_id = get_jwt_identity()

    notif = LearnerNotification.query.filter_by(
        id=notification_id, learner_id=user_id
    ).first()
    if not notif:
        return jsonify({"error": "Notification not found"}), 404

    notif.is_read = True
    db.session.commit()

    return jsonify({"message": "Notification marked as read"}), 200


@learner_notifications_bp.route("/notifications/<notification_id>", methods=["DELETE"])
@require_auth
def delete_notification(notification_id):
    """Delete a notification."""
    user_id = get_jwt_identity()

    notif = LearnerNotification.query.filter_by(
        id=notification_id, learner_id=user_id
    ).first()
    if not notif:
        return jsonify({"error": "Notification not found"}), 404

    db.session.delete(notif)
    db.session.commit()

    return jsonify({"message": "Notification deleted"}), 200


@learner_notifications_bp.route("/notifications/clear-all", methods=["POST"])
@require_auth
def clear_all_notifications():
    """Delete all notifications for the learner."""
    user_id = get_jwt_identity()

    deleted = LearnerNotification.query.filter_by(learner_id=user_id).delete()
    db.session.commit()

    return jsonify({"message": f"Cleared {deleted} notifications"}), 200


@learner_notifications_bp.route("/notification-preferences", methods=["GET"])
@require_auth
def get_notification_preferences():
    """Get learner notification preferences."""
    user_id = get_jwt_identity()

    prefs = LearnerNotificationPreferences.query.filter_by(user_id=user_id).first()
    if not prefs:
        return jsonify({"error": "Notification preferences not found"}), 404

    return jsonify(prefs.to_dict()), 200


@learner_notifications_bp.route("/notification-preferences", methods=["PUT"])
@require_auth
def update_notification_preferences():
    """Update learner notification preferences."""
    user_id = get_jwt_identity()

    prefs = LearnerNotificationPreferences.query.filter_by(user_id=user_id).first()
    if not prefs:
        return jsonify({"error": "Notification preferences not found"}), 404

    data = request.get_json() or {}
    bool_fields = [
        "email_new_trade", "email_trade_closed", "email_subscription_expiring",
        "email_flag_update", "email_announcements",
        "in_app_new_trade", "in_app_trade_closed", "in_app_subscription_expiring",
        "in_app_flag_update", "sms_enabled",
    ]

    for field in bool_fields:
        if field in data:
            setattr(prefs, field, bool(data[field]))

    if "sms_phone" in data:
        prefs.sms_phone = data["sms_phone"] or None

    db.session.commit()

    return jsonify({
        "message": "Notification preferences updated",
        "preferences": prefs.to_dict(),
    }), 200
