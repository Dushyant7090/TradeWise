"""
Learner Flags & Reports routes
- POST /api/learner/trades/{id}/flag
- GET  /api/learner/flags
"""
import logging
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from app import db
from app.middleware import require_auth
from app.models.learner_flag import LearnerFlag
from app.models.learner_unlocked_trade import LearnerUnlockedTrade
from app.models.trade import Trade

logger = logging.getLogger(__name__)
learner_flags_bp = Blueprint("learner_flags", __name__)


@learner_flags_bp.route("/trades/<trade_id>/flag", methods=["POST"])
@require_auth
def flag_trade(trade_id):
    """Flag/report a trade as fraudulent."""
    user_id = get_jwt_identity()

    trade = Trade.query.get(trade_id)
    if not trade:
        return jsonify({"error": "Trade not found"}), 404

    data = request.get_json() or {}
    reason = data.get("reason", "").strip()
    if not reason:
        return jsonify({"error": "Reason is required"}), 400

    # Check for duplicate flag
    existing = LearnerFlag.query.filter_by(
        learner_id=user_id, trade_id=trade_id
    ).first()
    if existing:
        return jsonify({"error": "You have already flagged this trade"}), 409

    flag = LearnerFlag(
        learner_id=user_id,
        trade_id=trade_id,
        reason=reason,
        status="pending",
    )
    db.session.add(flag)

    # Increment trade flag count
    trade.flag_count = (trade.flag_count or 0) + 1

    db.session.commit()

    return jsonify({"message": "Trade flagged successfully", "flag": flag.to_dict()}), 201


@learner_flags_bp.route("/flags", methods=["GET"])
@require_auth
def get_flags():
    """Get all flag reports submitted by the learner."""
    user_id = get_jwt_identity()
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)

    query = LearnerFlag.query.filter_by(learner_id=user_id).order_by(
        LearnerFlag.created_at.desc()
    )
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    flags = []
    for flag in paginated.items:
        entry = flag.to_dict()
        trade = Trade.query.get(flag.trade_id)
        if trade:
            entry["trade_symbol"] = trade.symbol
            entry["trade_status"] = trade.status
        flags.append(entry)

    return jsonify({
        "flags": flags,
        "total": paginated.total,
        "page": page,
        "per_page": per_page,
        "pages": paginated.pages,
    }), 200
