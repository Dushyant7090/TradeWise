"""
Authentication routes
- POST /api/auth/register
- POST /api/auth/login
- POST /api/auth/logout
- POST /api/auth/refresh-token
- POST /api/auth/google-auth
- POST /api/auth/2fa-setup
- POST /api/auth/2fa-verify
- POST /api/auth/2fa-disable
- PUT  /api/auth/role
"""
import logging
from datetime import datetime, timezone

import bcrypt
import pyotp
import qrcode
import io
import base64
from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)

from app import db
from app.models.user import User
from app.models.profile import Profile
from app.models.notification_preferences import NotificationPreferences
from app.models.login_activity import LoginActivity
from app.utils.validators import validate_email, validate_password

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)

# Starting credits awarded to every new Public Trader account
DEFAULT_LEARNER_CREDITS = 7

def _log_login(user_id: str, request_obj, status: str = "success"):
    """Record login activity."""
    try:
        activity = LoginActivity(
            user_id=user_id,
            ip_address=request_obj.remote_addr,
            user_agent=request_obj.headers.get("User-Agent", ""),
            status=status,
        )
        db.session.add(activity)
        db.session.commit()
    except Exception as e:
        logger.error(f"Failed to log login activity: {e}")


@auth_bp.route("/register", methods=["POST"])
def register():
    """Register a new user."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    display_name = data.get("display_name", "").strip()
    role = data.get("role", "public_trader")

    # Validate
    if not email or not validate_email(email):
        return jsonify({"error": "Valid email is required"}), 400

    valid_pw, pw_msg = validate_password(password)
    if not valid_pw:
        return jsonify({"error": pw_msg}), 400

    if role not in ("public_trader", "pro_trader"):
        return jsonify({"error": "Invalid role"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    # Create user
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user = User(email=email, password_hash=password_hash, auth_provider="email")
    db.session.add(user)
    db.session.flush()

    # Create profile
    profile = Profile(user_id=user.id, role=role, display_name=display_name or email.split("@")[0])
    db.session.add(profile)

    # Create default notification preferences
    prefs = NotificationPreferences(user_id=user.id)
    db.session.add(prefs)

    # If pro_trader, create pro trader profile
    if role == "pro_trader":
        from app.models.pro_trader_profile import ProTraderProfile
        pt_profile = ProTraderProfile(user_id=user.id)
        db.session.add(pt_profile)

    # If public_trader, create learner profile with starting credits
    if role == "public_trader":
        from app.models.learner_profile import LearnerProfile
        from app.models.learner_notification_preferences import LearnerNotificationPreferences
        learner_profile = LearnerProfile(user_id=user.id, credits=DEFAULT_LEARNER_CREDITS)
        db.session.add(learner_profile)
        learner_prefs = LearnerNotificationPreferences(user_id=user.id)
        db.session.add(learner_prefs)

    db.session.commit()

    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)

    _log_login(user.id, request)

    return jsonify({
        "message": "Registration successful",
        "user": user.to_dict(),
        "profile": profile.to_dict(),
        "access_token": access_token,
        "refresh_token": refresh_token,
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate a user and return JWT tokens."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    totp_code = data.get("totp_code", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = User.query.filter_by(email=email, auth_provider="email").first()
    if not user or not user.password_hash:
        _log_login(email, request, "failed")
        return jsonify({"error": "Invalid credentials"}), 401

    if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        _log_login(user.id, request, "failed")
        return jsonify({"error": "Invalid credentials"}), 401

    if not user.is_active:
        return jsonify({"error": "Account is disabled"}), 403

    # 2FA check
    if user.totp_enabled:
        if not totp_code:
            return jsonify({"error": "2FA code required", "requires_2fa": True}), 200
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(totp_code):
            _log_login(user.id, request, "failed_2fa")
            return jsonify({"error": "Invalid 2FA code"}), 401

    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)

    _log_login(user.id, request)

    profile = Profile.query.filter_by(user_id=user.id).first()
    return jsonify({
        "message": "Login successful",
        "user": user.to_dict(),
        "profile": profile.to_dict() if profile else None,
        "access_token": access_token,
        "refresh_token": refresh_token,
    }), 200


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    """Logout endpoint (client should discard tokens)."""
    return jsonify({"message": "Logged out successfully"}), 200


@auth_bp.route("/refresh-token", methods=["POST"])
@jwt_required(refresh=True)
def refresh_token():
    """Issue a new access token using a refresh token."""
    user_id = get_jwt_identity()
    access_token = create_access_token(identity=user_id)
    return jsonify({"access_token": access_token}), 200


@auth_bp.route("/google-auth", methods=["POST"])
def google_auth():
    """Authenticate with Google OAuth token."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    google_token = data.get("token", "")
    role = data.get("role", "public_trader")

    if not google_token:
        return jsonify({"error": "Google token is required"}), 400

    # Verify Google token
    try:
        import requests as req
        resp = req.get(
            f"https://www.googleapis.com/oauth2/v3/tokeninfo?id_token={google_token}",
            timeout=10,
        )
        if resp.status_code != 200:
            return jsonify({"error": "Invalid Google token"}), 401
        google_data = resp.json()
        email = google_data.get("email", "").lower()
        name = google_data.get("name", "")
        if not email:
            return jsonify({"error": "Could not retrieve email from Google token"}), 400
    except Exception as e:
        logger.error(f"Google token verification error: {e}")
        return jsonify({"error": "Google authentication failed"}), 500

    # Find or create user
    user = User.query.filter_by(email=email).first()
    created = False
    if not user:
        user = User(email=email, auth_provider="google")
        db.session.add(user)
        db.session.flush()

        profile = Profile(user_id=user.id, role=role, display_name=name or email.split("@")[0])
        db.session.add(profile)
        prefs = NotificationPreferences(user_id=user.id)
        db.session.add(prefs)

        if role == "pro_trader":
            from app.models.pro_trader_profile import ProTraderProfile
            pt_profile = ProTraderProfile(user_id=user.id)
            db.session.add(pt_profile)

        db.session.commit()
        created = True

    access_token = create_access_token(identity=user.id)
    refresh_token_val = create_refresh_token(identity=user.id)
    _log_login(user.id, request)

    profile = Profile.query.filter_by(user_id=user.id).first()
    return jsonify({
        "message": "Google authentication successful",
        "user": user.to_dict(),
        "profile": profile.to_dict() if profile else None,
        "access_token": access_token,
        "refresh_token": refresh_token_val,
        "is_new_user": created,
    }), 201 if created else 200


@auth_bp.route("/2fa-setup", methods=["POST"])
@jwt_required()
def setup_2fa():
    """Set up 2FA: generate TOTP secret and QR code."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.totp_enabled:
        return jsonify({"error": "2FA is already enabled"}), 400

    # Generate TOTP secret
    secret = pyotp.random_base32()
    user.totp_secret = secret
    db.session.commit()

    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(name=user.email, issuer_name="TradeWise")

    # Generate QR code
    img = qrcode.make(provisioning_uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return jsonify({
        "secret": secret,
        "provisioning_uri": provisioning_uri,
        "qr_code_base64": f"data:image/png;base64,{qr_b64}",
    }), 200


@auth_bp.route("/2fa-verify", methods=["POST"])
@jwt_required()
def verify_2fa():
    """Verify TOTP code and enable 2FA."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json() or {}
    code = data.get("code", "")
    if not code:
        return jsonify({"error": "TOTP code is required"}), 400

    if not user.totp_secret:
        return jsonify({"error": "2FA setup not initiated"}), 400

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(code):
        return jsonify({"error": "Invalid TOTP code"}), 400

    user.totp_enabled = True
    db.session.commit()

    return jsonify({"message": "2FA enabled successfully"}), 200


@auth_bp.route("/2fa-disable", methods=["POST"])
@jwt_required()
def disable_2fa():
    """Disable 2FA."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json() or {}
    password = data.get("password", "")
    if not password or not user.password_hash:
        return jsonify({"error": "Password is required"}), 400

    if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        return jsonify({"error": "Invalid password"}), 401

    user.totp_enabled = False
    user.totp_secret = None
    db.session.commit()

    return jsonify({"message": "2FA disabled successfully"}), 200


@auth_bp.route("/change-password", methods=["POST"])
@jwt_required()
def change_password():
    """Change the authenticated user's password."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json() or {}
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    if not current_password or not new_password:
        return jsonify({"error": "current_password and new_password are required"}), 400

    if not user.password_hash:
        return jsonify({"error": "Password change not supported for OAuth accounts"}), 400

    if not bcrypt.checkpw(current_password.encode(), user.password_hash.encode()):
        return jsonify({"error": "Current password is incorrect"}), 401

    valid_pw, pw_msg = validate_password(new_password)
    if not valid_pw:
        return jsonify({"error": pw_msg}), 400

    user.password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    db.session.commit()

    return jsonify({"message": "Password changed successfully"}), 200



@auth_bp.route("/role", methods=["PUT"])
@jwt_required()
def update_role():
    """Update the authenticated user's role (e.g. public_trader → pro_trader).

    Request body: { "role": "pro_trader" | "public_trader" }

    When switching to pro_trader a ProTraderProfile row is created (if missing).
    The existing LearnerProfile is retained so that credits are not lost.
    """
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    new_role = data.get("role", "").strip()

    if new_role not in ("public_trader", "pro_trader"):
        return jsonify({"error": "role must be 'public_trader' or 'pro_trader'"}), 400

    profile = Profile.query.filter_by(user_id=user_id).first()
    if not profile:
        return jsonify({"error": "Profile not found"}), 404

    if profile.role == new_role:
        return jsonify({"profile": profile.to_dict()}), 200

    profile.role = new_role

    if new_role == "pro_trader":
        from app.models.pro_trader_profile import ProTraderProfile
        if not ProTraderProfile.query.filter_by(user_id=user_id).first():
            db.session.add(ProTraderProfile(user_id=user_id))

    if new_role == "public_trader":
        from app.models.learner_profile import LearnerProfile
        if not LearnerProfile.query.filter_by(user_id=user_id).first():
            db.session.add(LearnerProfile(user_id=user_id, credits=DEFAULT_LEARNER_CREDITS))

    db.session.commit()
    return jsonify({"profile": profile.to_dict()}), 200
