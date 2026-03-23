"""
Trades routes
- POST /api/pro-trader/trades
- GET /api/pro-trader/trades
- GET /api/pro-trader/trades/{id}
- PUT /api/pro-trader/trades/{id}/close
- DELETE /api/pro-trader/trades/{id}
"""
import logging
import uuid
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from app import db
from app.middleware import require_pro_trader
from app.models.trade import Trade
from app.utils.accuracy import recalculate_accuracy, calculate_rrr
from app.utils.validators import validate_rationale

logger = logging.getLogger(__name__)
trades_bp = Blueprint("trades", __name__)


@trades_bp.route("/trades", methods=["POST"])
@require_pro_trader
def create_trade():
    """Submit a new trade signal."""
    user_id = get_jwt_identity()
    data = request.get_json() or {}

    required = ["symbol", "direction", "entry_price", "stop_loss_price", "target_price", "technical_rationale"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 400

    symbol = data["symbol"].strip().upper()
    direction = data["direction"].strip().lower()
    if direction not in Trade.VALID_DIRECTIONS:
        return jsonify({"error": f"Direction must be 'buy' or 'sell'"}), 400

    try:
        entry = float(data["entry_price"])
        sl = float(data["stop_loss_price"])
        target = float(data["target_price"])
    except (TypeError, ValueError):
        return jsonify({"error": "Prices must be numeric"}), 400

    if entry <= 0 or sl <= 0 or target <= 0:
        return jsonify({"error": "All prices must be positive"}), 400

    # Price sanity checks
    if direction == "buy":
        if sl >= entry:
            return jsonify({"error": "For BUY: stop_loss must be below entry_price"}), 400
        if target <= entry:
            return jsonify({"error": "For BUY: target_price must be above entry_price"}), 400
    else:
        if sl <= entry:
            return jsonify({"error": "For SELL: stop_loss must be above entry_price"}), 400
        if target >= entry:
            return jsonify({"error": "For SELL: target_price must be below entry_price"}), 400

    rationale = data["technical_rationale"].strip()
    valid_rat, rat_msg = validate_rationale(rationale)
    if not valid_rat:
        return jsonify({"error": rat_msg}), 400

    rrr = calculate_rrr(direction, entry, sl, target)

    trade = Trade(
        trader_id=user_id,
        symbol=symbol,
        direction=direction,
        entry_price=entry,
        stop_loss_price=sl,
        target_price=target,
        rrr=rrr,
        technical_rationale=rationale,
        chart_image_url=data.get("chart_image_url"),
        status="active",
    )
    db.session.add(trade)
    db.session.commit()

    return jsonify({"message": "Trade created successfully", "trade": trade.to_dict()}), 201


@trades_bp.route("/trades", methods=["GET"])
@require_pro_trader
def get_trades():
    """Get all trades for the current trader with pagination."""
    user_id = get_jwt_identity()

    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)
    status_filter = request.args.get("status", "")

    query = Trade.query.filter_by(trader_id=user_id)
    if status_filter and status_filter in Trade.VALID_STATUSES:
        query = query.filter_by(status=status_filter)

    query = query.order_by(Trade.created_at.desc())
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "trades": [t.to_dict() for t in paginated.items],
        "total": paginated.total,
        "page": page,
        "per_page": per_page,
        "pages": paginated.pages,
    }), 200


@trades_bp.route("/trades/<trade_id>", methods=["GET"])
@require_pro_trader
def get_trade(trade_id):
    """Get a specific trade by ID."""
    user_id = get_jwt_identity()
    trade = Trade.query.filter_by(id=trade_id, trader_id=user_id).first()
    if not trade:
        return jsonify({"error": "Trade not found"}), 404
    return jsonify(trade.to_dict()), 200


@trades_bp.route("/trades/<trade_id>/close", methods=["PUT"])
@require_pro_trader
def close_trade(trade_id):
    """Close a trade (mark as target_hit or sl_hit)."""
    user_id = get_jwt_identity()
    trade = Trade.query.filter_by(id=trade_id, trader_id=user_id).first()
    if not trade:
        return jsonify({"error": "Trade not found"}), 404

    if trade.status != "active":
        return jsonify({"error": "Only active trades can be closed"}), 400

    data = request.get_json() or {}
    outcome = data.get("outcome", "").strip().lower()
    if outcome not in ("win", "loss"):
        return jsonify({"error": "outcome must be 'win' or 'loss'"}), 400

    status = "target_hit" if outcome == "win" else "sl_hit"
    now = datetime.now(timezone.utc)

    trade.status = status
    trade.outcome = outcome
    trade.closed_at = now
    trade.closed_by_trader_at = now
    trade.close_reason = data.get("close_reason", "")
    db.session.commit()

    # Recalculate accuracy
    recalculate_accuracy(user_id)

    return jsonify({"message": f"Trade closed as {status}", "trade": trade.to_dict()}), 200


@trades_bp.route("/trades/<trade_id>", methods=["DELETE"])
@require_pro_trader
def cancel_trade(trade_id):
    """Cancel an active trade."""
    user_id = get_jwt_identity()
    trade = Trade.query.filter_by(id=trade_id, trader_id=user_id).first()
    if not trade:
        return jsonify({"error": "Trade not found"}), 404

    if trade.status != "active":
        return jsonify({"error": "Only active trades can be cancelled"}), 400

    trade.status = "cancelled"
    trade.closed_at = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify({"message": "Trade cancelled successfully"}), 200
