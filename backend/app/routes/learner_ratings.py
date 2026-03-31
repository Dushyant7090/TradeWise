"""
Learner Trade Ratings routes
- POST /api/learner/trades/{id}/rate
- PUT  /api/learner/trades/{id}/rate
"""
import logging
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from app import db
from app.middleware import require_auth
from app.models.learner_trade_rating import LearnerTradeRating
from app.models.learner_trade_unlock import LearnerUnlockedTrade
from app.models.trade import Trade

logger = logging.getLogger(__name__)
learner_ratings_bp = Blueprint("learner_ratings", __name__)


def _validate_rating(rating):
    if not isinstance(rating, int) or rating < 1 or rating > 5:
        return False, "Rating must be an integer between 1 and 5"
    return True, ""


@learner_ratings_bp.route("/trades/<trade_id>/rate", methods=["POST"])
@require_auth
def rate_trade(trade_id):
    """Submit a rating for a trade (must be unlocked first)."""
    user_id = get_jwt_identity()

    trade = Trade.query.get(trade_id)
    if not trade:
        return jsonify({"error": "Trade not found"}), 404

    # Must have unlocked the trade
    unlock = LearnerUnlockedTrade.query.filter_by(
        learner_id=user_id, trade_id=trade_id
    ).first()
    if not unlock:
        return jsonify({"error": "You must unlock this trade before rating it"}), 403

    # Check for existing rating
    existing = LearnerTradeRating.query.filter_by(
        learner_id=user_id, trade_id=trade_id
    ).first()
    if existing:
        return jsonify({"error": "You have already rated this trade. Use PUT to update."}), 409

    data = request.get_json() or {}
    rating = data.get("rating")
    if rating is None:
        return jsonify({"error": "rating is required"}), 400

    valid, msg = _validate_rating(rating)
    if not valid:
        return jsonify({"error": msg}), 400

    trade_rating = LearnerTradeRating(
        learner_id=user_id,
        trade_id=trade_id,
        rating=rating,
        review=data.get("review", "").strip() or None,
    )
    db.session.add(trade_rating)
    db.session.commit()

    return jsonify({
        "message": "Trade rated successfully",
        "rating": trade_rating.to_dict(),
    }), 201


@learner_ratings_bp.route("/trades/<trade_id>/rate", methods=["PUT"])
@require_auth
def update_trade_rating(trade_id):
    """Update an existing trade rating."""
    user_id = get_jwt_identity()

    rating_obj = LearnerTradeRating.query.filter_by(
        learner_id=user_id, trade_id=trade_id
    ).first()
    if not rating_obj:
        return jsonify({"error": "No existing rating found. Use POST to create."}), 404

    data = request.get_json() or {}
    rating = data.get("rating")
    if rating is None:
        return jsonify({"error": "rating is required"}), 400

    valid, msg = _validate_rating(rating)
    if not valid:
        return jsonify({"error": msg}), 400

    rating_obj.rating = rating
    if "review" in data:
        rating_obj.review = data["review"].strip() or None
    db.session.commit()

    return jsonify({
        "message": "Rating updated",
        "rating": rating_obj.to_dict(),
    }), 200
