"""
Learner Credits routes
- GET  /api/learner/credits
- POST /api/learner/trades/{id}/unlock
- GET  /api/learner/history
- GET  /api/learner/credits-log
"""
import logging
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from app import db
from app.middleware import require_auth
from app.models.learner_profile import LearnerProfile
from app.models.learner_trade_unlock import LearnerUnlockedTrade
from app.models.learner_credit_transaction import LearnerCreditsLog
from app.models.trade import Trade
from app.models.subscription import Subscription
from app.models.profile import Profile

logger = logging.getLogger(__name__)
learner_credits_bp = Blueprint("learner_credits", __name__)


def _has_active_subscription(learner_id: str, trader_id: str) -> bool:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return Subscription.query.filter(
        Subscription.subscriber_id == learner_id,
        Subscription.trader_id == trader_id,
        Subscription.status == "active",
        Subscription.ends_at > now,
    ).first() is not None


@learner_credits_bp.route("/credits", methods=["GET"])
@require_auth
def get_credits():
    """Get current credits and usage info."""
    user_id = get_jwt_identity()
    learner = LearnerProfile.query.filter_by(user_id=user_id).first()
    if not learner:
        return jsonify({"error": "Learner profile not found"}), 404

    return jsonify({
        "credits": learner.credits,
        "total_unlocked_trades": learner.total_unlocked_trades,
        "total_spent": float(learner.total_spent or 0),
    }), 200


@learner_credits_bp.route("/trades/<trade_id>/unlock", methods=["POST"])
@require_auth
def unlock_trade(trade_id):
    """Unlock a trade analysis (deduct 1 credit or use subscription)."""
    from datetime import datetime, timezone

    user_id = get_jwt_identity()
    learner = LearnerProfile.query.filter_by(user_id=user_id).first()
    if not learner:
        return jsonify({"error": "Learner profile not found"}), 404

    trade = Trade.query.get(trade_id)
    if not trade:
        return jsonify({"error": "Trade not found"}), 404

    # Check if already unlocked
    existing = LearnerUnlockedTrade.query.filter_by(
        learner_id=user_id, trade_id=trade_id
    ).first()
    if existing:
        return jsonify({"message": "Trade already unlocked", "trade_id": trade_id}), 200

    via_credit = True
    has_sub = _has_active_subscription(user_id, trade.trader_id)

    if has_sub:
        via_credit = False
    else:
        if learner.credits <= 0:
            return jsonify({
                "error": "Insufficient credits",
                "message": "You have no credits left. Please subscribe to a pro trader.",
                "credits": 0,
            }), 402

        # Deduct credit
        learner.credits -= 1
        learner.total_unlocked_trades += 1

        log = LearnerCreditsLog(
            learner_id=user_id,
            trade_id=trade_id,
            action="used",
            amount=1,
            credits_remaining=learner.credits,
            reason=f"Unlocked trade {trade_id}",
        )
        db.session.add(log)

    # Record unlock
    unlock = LearnerUnlockedTrade(
        learner_id=user_id,
        trade_id=trade_id,
        via_credit=via_credit,
        unlocked_at=datetime.now(timezone.utc),
    )
    db.session.add(unlock)

    if not has_sub:
        pass  # already counted above
    else:
        learner.total_unlocked_trades += 1

    # Increment trade's unlock_count
    trade.unlock_count = (trade.unlock_count or 0) + 1

    db.session.commit()

    return jsonify({
        "message": "Trade unlocked successfully",
        "trade_id": trade_id,
        "via_credit": via_credit,
        "credits_remaining": learner.credits,
    }), 200


@learner_credits_bp.route("/history", methods=["GET"])
@require_auth
def get_history():
    """Get all unlocked trades history."""
    user_id = get_jwt_identity()
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)
    status_filter = request.args.get("status", "")

    query = LearnerUnlockedTrade.query.filter_by(learner_id=user_id)
    query = query.order_by(LearnerUnlockedTrade.unlocked_at.desc())
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    history = []
    for unlock in paginated.items:
        trade = Trade.query.get(unlock.trade_id)
        if trade:
            if status_filter and trade.status != status_filter:
                continue
            trader_profile = Profile.query.filter_by(user_id=trade.trader_id).first()
            entry = unlock.to_dict()
            entry["trade"] = {
                "id": trade.id,
                "symbol": trade.symbol,
                "direction": trade.direction,
                "entry_price": float(trade.entry_price),
                "stop_loss_price": float(trade.stop_loss_price),
                "target_price": float(trade.target_price),
                "rrr": float(trade.rrr),
                "status": trade.status,
                "outcome": trade.outcome,
                "created_at": trade.created_at.isoformat() if trade.created_at else None,
                "trader_name": trader_profile.display_name if trader_profile else "Unknown",
            }
            history.append(entry)

    return jsonify({
        "history": history,
        "total": paginated.total,
        "page": page,
        "per_page": per_page,
        "pages": paginated.pages,
    }), 200


@learner_credits_bp.route("/credits-log", methods=["GET"])
@require_auth
def get_credits_log():
    """Get credit usage log."""
    user_id = get_jwt_identity()
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)

    query = LearnerCreditsLog.query.filter_by(learner_id=user_id).order_by(
        LearnerCreditsLog.created_at.desc()
    )
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "credits_log": [log.to_dict() for log in paginated.items],
        "total": paginated.total,
        "page": page,
        "per_page": per_page,
        "pages": paginated.pages,
    }), 200
