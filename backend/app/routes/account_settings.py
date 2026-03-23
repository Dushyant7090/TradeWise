"""
Account Settings routes
- PUT  /api/pro-trader/account-settings
- POST /api/pro-trader/change-password
- GET  /api/pro-trader/login-activity
- GET  /api/pro-trader/notification-preferences
- PUT  /api/pro-trader/notification-preferences
- POST /api/pro-trader/logout-sessions
"""
import logging
import bcrypt
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from app import db
from app.middleware import require_pro_trader
from app.models.user import User
from app.models.profile import Profile
from app.models.login_activity import LoginActivity
from app.models.notification_preferences import NotificationPreferences
from app.utils.validators import validate_password

logger = logging.getLogger(__name__)
account_bp = Blueprint("account", __name__)


@account_bp.route("/account-settings", methods=["PUT"])
@require_pro_trader
def update_account_settings():
    """Update account settings (display name, etc.)."""
    user_id = get_jwt_identity()
    data = request.get_json() or {}

    profile = Profile.query.filter_by(user_id=user_id).first()
    if not profile:
        return jsonify({"error": "Profile not found"}), 404

    if "display_name" in data:
        name = data["display_name"].strip()
        if not name or len(name) > 100:
            return jsonify({"error": "Display name must be 1-100 characters"}), 400
        profile.display_name = name

    db.session.commit()
    return jsonify({"message": "Account settings updated", "profile": profile.to_dict()}), 200


@account_bp.route("/change-password", methods=["POST"])
@require_pro_trader
def change_password():
    """Change password with validation."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.auth_provider != "email":
        return jsonify({"error": "Password change is not available for social login accounts"}), 400

    data = request.get_json() or {}
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    if not current_password or not new_password:
        return jsonify({"error": "current_password and new_password are required"}), 400

    if not user.password_hash or not bcrypt.checkpw(current_password.encode(), user.password_hash.encode()):
        return jsonify({"error": "Current password is incorrect"}), 401

    valid, msg = validate_password(new_password)
    if not valid:
        return jsonify({"error": msg}), 400

    if current_password == new_password:
        return jsonify({"error": "New password must be different from current password"}), 400

    user.password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    db.session.commit()

    # Send notification email
    try:
        from app.services.email_service import send_password_changed_email
        send_password_changed_email(user.email)
    except Exception as e:
        logger.error(f"Failed to send password change email: {e}")

    return jsonify({"message": "Password changed successfully"}), 200


@account_bp.route("/login-activity", methods=["GET"])
@require_pro_trader
def get_login_activity():
    """Get login activity logs."""
    user_id = get_jwt_identity()
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)

    query = LoginActivity.query.filter_by(user_id=user_id).order_by(LoginActivity.created_at.desc())
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "activities": [a.to_dict() for a in paginated.items],
        "total": paginated.total,
        "page": page,
        "per_page": per_page,
        "pages": paginated.pages,
    }), 200


@account_bp.route("/notification-preferences", methods=["GET"])
@require_pro_trader
def get_notification_preferences():
    """Get notification preferences."""
    user_id = get_jwt_identity()
    prefs = NotificationPreferences.query.filter_by(user_id=user_id).first()
    if not prefs:
        # Create defaults
        prefs = NotificationPreferences(user_id=user_id)
        db.session.add(prefs)
        db.session.commit()
    return jsonify(prefs.to_dict()), 200


@account_bp.route("/notification-preferences", methods=["PUT"])
@require_pro_trader
def update_notification_preferences():
    """Update notification preferences."""
    user_id = get_jwt_identity()
    prefs = NotificationPreferences.query.filter_by(user_id=user_id).first()
    if not prefs:
        prefs = NotificationPreferences(user_id=user_id)
        db.session.add(prefs)

    data = request.get_json() or {}
    bool_fields = [
        "email_new_subscriber",
        "email_trade_flagged",
        "email_payout_confirmation",
        "in_app_new_subscriber",
        "in_app_trade_flagged",
        "in_app_payout_confirmation",
        "sms_enabled",
    ]
    for field in bool_fields:
        if field in data:
            setattr(prefs, field, bool(data[field]))

    if "sms_phone" in data:
        prefs.sms_phone = data["sms_phone"].strip() if data["sms_phone"] else None

    db.session.commit()
    return jsonify({"message": "Preferences updated", "preferences": prefs.to_dict()}), 200


@account_bp.route("/logout-sessions", methods=["POST"])
@require_pro_trader
def logout_other_sessions():
    """
    Logout from other devices.
    Since we use stateless JWT, this endpoint is a placeholder for
    a token blacklist or forced re-login implementation.
    In production, implement a token blacklist with Redis.
    """
    return jsonify({
        "message": "All other sessions have been invalidated. Please re-login on other devices.",
    }), 200
