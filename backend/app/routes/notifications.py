"""
Notifications routes
- GET    /api/pro-trader/notifications
- PUT    /api/pro-trader/notifications/{id}/read
- DELETE /api/pro-trader/notifications/{id}
- POST   /api/pro-trader/notifications/clear-all
"""
import logging
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from app import db
from app.middleware import require_auth
from app.models.notification import Notification

logger = logging.getLogger(__name__)
notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/notifications", methods=["GET"])
@require_auth
def get_notifications():
    """Get all notifications (paginated)."""
    user_id = get_jwt_identity()
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)
    unread_only = request.args.get("unread_only", "false").lower() == "true"

    query = Notification.query.filter_by(user_id=user_id)
    if unread_only:
        query = query.filter_by(is_read=False)
    query = query.order_by(Notification.created_at.desc())

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    unread_count = Notification.query.filter_by(user_id=user_id, is_read=False).count()

    return jsonify({
        "notifications": [n.to_dict() for n in paginated.items],
        "total": paginated.total,
        "unread_count": unread_count,
        "page": page,
        "per_page": per_page,
        "pages": paginated.pages,
    }), 200


@notifications_bp.route("/notifications/<notif_id>/read", methods=["PUT"])
@require_auth
def mark_as_read(notif_id):
    """Mark a notification as read."""
    user_id = get_jwt_identity()
    notif = Notification.query.filter_by(id=notif_id, user_id=user_id).first()
    if not notif:
        return jsonify({"error": "Notification not found"}), 404

    notif.is_read = True
    db.session.commit()
    return jsonify({"message": "Marked as read", "notification": notif.to_dict()}), 200


@notifications_bp.route("/notifications/<notif_id>", methods=["DELETE"])
@require_auth
def delete_notification(notif_id):
    """Delete a notification."""
    user_id = get_jwt_identity()
    notif = Notification.query.filter_by(id=notif_id, user_id=user_id).first()
    if not notif:
        return jsonify({"error": "Notification not found"}), 404

    db.session.delete(notif)
    db.session.commit()
    return jsonify({"message": "Notification deleted"}), 200


@notifications_bp.route("/notifications/clear-all", methods=["POST"])
@require_auth
def clear_all_notifications():
    """Clear all notifications for the current user."""
    user_id = get_jwt_identity()
    deleted = Notification.query.filter_by(user_id=user_id).delete()
    db.session.commit()
    return jsonify({"message": f"Cleared {deleted} notification(s)"}), 200
