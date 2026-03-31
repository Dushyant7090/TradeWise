"""
Auth Middleware - JWT token verification and role-based access
"""
import logging
from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from app.models.user import User
from app.models.profile import Profile

logger = logging.getLogger(__name__)


def require_auth(f):
    """Decorator: require valid JWT token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception as e:
            logger.debug("JWT verification failed: %s", e)
            return jsonify({"error": "Unauthorized", "message": "Invalid or missing token"}), 401
        return f(*args, **kwargs)
    return decorated


def require_pro_trader(f):
    """Decorator: require valid JWT + pro_trader role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception as e:
            logger.debug("JWT verification failed: %s", e)
            return jsonify({"error": "Unauthorized", "message": "Invalid or missing token"}), 401

        user_id = get_jwt_identity()
        profile = Profile.query.filter_by(user_id=user_id).first()
        if not profile or profile.role != "pro_trader":
            return jsonify({"error": "Forbidden", "message": "Pro trader access required"}), 403

        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """Decorator: require valid JWT + admin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception as e:
            logger.debug("JWT verification failed: %s", e)
            return jsonify({"error": "Unauthorized", "message": "Invalid or missing token"}), 401

        user_id = get_jwt_identity()
        profile = Profile.query.filter_by(user_id=user_id).first()
        if not profile or profile.role != "admin":
            return jsonify({"error": "Forbidden", "message": "Admin access required"}), 403

        return f(*args, **kwargs)
    return decorated


def get_current_user():
    """Get the current authenticated user from JWT."""
    user_id = get_jwt_identity()
    return User.query.get(user_id)


def get_current_pro_trader_profile():
    """Get the current authenticated user's pro trader profile."""
    from app.models.pro_trader_profile import ProTraderProfile
    user_id = get_jwt_identity()
    return ProTraderProfile.query.filter_by(user_id=user_id).first()
