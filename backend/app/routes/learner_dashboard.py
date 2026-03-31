"""
Learner Dashboard routes
- GET /api/learner/dashboard  — summary stats for the learner's home page
"""
import logging
from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt_identity

from app import db
from app.middleware import require_auth
from app.models.profile import Profile
from app.models.learner_profile import LearnerProfile

logger = logging.getLogger(__name__)
learner_dashboard_bp = Blueprint("learner_dashboard", __name__)


@learner_dashboard_bp.route("/api/learner/dashboard", methods=["GET"])
@require_auth
def get_learner_dashboard():
    """Return aggregated dashboard stats for the authenticated learner."""
    user_id = get_jwt_identity()
    try:
        profile = Profile.query.filter_by(user_id=user_id).first()
        learner_profile = LearnerProfile.query.filter_by(user_id=user_id).first()

        data = {
            "user_id": user_id,
            "full_name": profile.full_name if profile else None,
            "credits": learner_profile.credits if learner_profile else 0,
        }
        return jsonify(data), 200
    except Exception as exc:
        logger.exception("Error fetching learner dashboard: %s", exc)
        return jsonify({"error": "Internal server error"}), 500
