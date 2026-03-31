"""
Learner Feed & Discovery routes
- GET /api/learner/feed
- GET /api/learner/feed/filter
- GET /api/learner/trades/{id}
"""
import logging
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from app import db
from app.middleware import require_auth
from app.models.trade import Trade
from app.models.subscription import Subscription
from app.models.learner_trade_unlock import LearnerUnlockedTrade
from app.models.pro_trader_profile import ProTraderProfile
from app.models.profile import Profile

logger = logging.getLogger(__name__)
learner_feed_bp = Blueprint("learner_feed", __name__)


def _has_active_subscription(learner_id: str, trader_id: str) -> bool:
    """Check if learner has an active subscription to the given trader."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    sub = Subscription.query.filter(
        Subscription.subscriber_id == learner_id,
        Subscription.trader_id == trader_id,
        Subscription.status == "active",
        Subscription.ends_at > now,
    ).first()
    return sub is not None


def _is_trade_unlocked(learner_id: str, trade_id: str) -> bool:
    """Check if a learner has already unlocked a trade."""
    return LearnerUnlockedTrade.query.filter_by(
        learner_id=learner_id, trade_id=trade_id
    ).first() is not None


def _serialize_trade_public(trade: Trade, trader_profile: Profile, is_unlocked: bool, has_sub: bool) -> dict:
    """Serialize a trade. Hide sensitive fields if not unlocked and no subscription."""
    base = {
        "id": trade.id,
        "trader_id": trade.trader_id,
        "trader_name": trader_profile.display_name if trader_profile else "Unknown",
        "symbol": trade.symbol,
        "rrr": float(trade.rrr),
        "status": trade.status,
        "view_count": trade.view_count,
        "unlock_count": trade.unlock_count,
        "created_at": trade.created_at.isoformat() if trade.created_at else None,
        "is_unlocked": is_unlocked,
        "has_subscription": has_sub,
    }

    pt_profile = ProTraderProfile.query.filter_by(user_id=trade.trader_id).first()
    base["accuracy_score"] = float(pt_profile.accuracy_score or 0) if pt_profile else 0.0

    if is_unlocked or has_sub:
        base.update({
            "direction": trade.direction,
            "entry_price": float(trade.entry_price),
            "stop_loss_price": float(trade.stop_loss_price),
            "target_price": float(trade.target_price),
            "technical_rationale": trade.technical_rationale,
            "chart_image_url": trade.chart_image_url,
            "outcome": trade.outcome,
            "closed_at": trade.closed_at.isoformat() if trade.closed_at else None,
        })
    return base


@learner_feed_bp.route("/feed", methods=["GET"])
@require_auth
def get_feed():
    """Get paginated active trades from all pro traders."""
    user_id = get_jwt_identity()
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)
    sort_by = request.args.get("sort_by", "created_at")

    query = Trade.query.filter(Trade.status == "active")

    if sort_by == "accuracy_score":
        query = query.join(ProTraderProfile, Trade.trader_id == ProTraderProfile.user_id).order_by(
            ProTraderProfile.accuracy_score.desc()
        )
    elif sort_by == "view_count":
        query = query.order_by(Trade.view_count.desc())
    else:
        query = query.order_by(Trade.created_at.desc())

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    trades = []
    for trade in paginated.items:
        trader_profile = Profile.query.filter_by(user_id=trade.trader_id).first()
        is_unlocked = _is_trade_unlocked(user_id, trade.id)
        has_sub = _has_active_subscription(user_id, trade.trader_id)
        trades.append(_serialize_trade_public(trade, trader_profile, is_unlocked, has_sub))

    return jsonify({
        "trades": trades,
        "total": paginated.total,
        "page": page,
        "per_page": per_page,
        "pages": paginated.pages,
    }), 200


@learner_feed_bp.route("/feed/filter", methods=["GET"])
@require_auth
def filter_feed():
    """Filter trades by market, trader name, accuracy score."""
    user_id = get_jwt_identity()
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)

    market = request.args.get("market", "")
    trader_name = request.args.get("trader_name", "")
    pro_trader_id = request.args.get("pro_trader_id", "")
    min_accuracy = request.args.get("min_accuracy", type=float)
    max_accuracy = request.args.get("max_accuracy", type=float)
    sort_by = request.args.get("sort_by", "created_at")

    query = Trade.query.filter(Trade.status == "active")

    if market:
        query = query.filter(Trade.symbol.ilike(f"%{market}%"))

    if pro_trader_id:
        query = query.filter(Trade.trader_id == pro_trader_id)

    if trader_name or (min_accuracy is not None) or (max_accuracy is not None):
        query = query.join(ProTraderProfile, Trade.trader_id == ProTraderProfile.user_id)
        if min_accuracy is not None:
            query = query.filter(ProTraderProfile.accuracy_score >= min_accuracy)
        if max_accuracy is not None:
            query = query.filter(ProTraderProfile.accuracy_score <= max_accuracy)

        if trader_name:
            query = query.join(Profile, Trade.trader_id == Profile.user_id)
            query = query.filter(Profile.display_name.ilike(f"%{trader_name}%"))

    if sort_by == "accuracy_score":
        try:
            query = query.order_by(ProTraderProfile.accuracy_score.desc())
        except Exception:
            query = query.order_by(Trade.created_at.desc())
    elif sort_by == "view_count":
        query = query.order_by(Trade.view_count.desc())
    else:
        query = query.order_by(Trade.created_at.desc())

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    trades = []
    for trade in paginated.items:
        trader_profile = Profile.query.filter_by(user_id=trade.trader_id).first()
        is_unlocked = _is_trade_unlocked(user_id, trade.id)
        has_sub = _has_active_subscription(user_id, trade.trader_id)
        trades.append(_serialize_trade_public(trade, trader_profile, is_unlocked, has_sub))

    return jsonify({
        "trades": trades,
        "total": paginated.total,
        "page": page,
        "per_page": per_page,
        "pages": paginated.pages,
    }), 200


@learner_feed_bp.route("/trades/<trade_id>", methods=["GET"])
@require_auth
def get_trade_detail(trade_id):
    """Get trade detail. Shows full info only if unlocked or has subscription."""
    user_id = get_jwt_identity()
    trade = Trade.query.get(trade_id)
    if not trade:
        return jsonify({"error": "Trade not found"}), 404

    trader_profile = Profile.query.filter_by(user_id=trade.trader_id).first()
    is_unlocked = _is_trade_unlocked(user_id, trade.id)
    has_sub = _has_active_subscription(user_id, trade.trader_id)

    # Increment view count
    trade.view_count = (trade.view_count or 0) + 1
    db.session.commit()

    # Mark as viewed if unlocked
    if is_unlocked:
        from datetime import datetime, timezone
        unlock = LearnerUnlockedTrade.query.filter_by(
            learner_id=user_id, trade_id=trade_id
        ).first()
        if unlock and not unlock.viewed_at:
            unlock.viewed_at = datetime.now(timezone.utc)
            db.session.commit()

    return jsonify(_serialize_trade_public(trade, trader_profile, is_unlocked, has_sub)), 200
