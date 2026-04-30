"""
Pro-Trader Public Info routes (learner-facing)
- GET /api/pro-traders
- GET /api/pro-traders/{id}/profile
- GET /api/pro-traders/{id}/trades
"""
import logging
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import case, func

from app import db
from app.middleware import require_auth
from app.models.pro_trader_profile import ProTraderProfile
from app.models.profile import Profile
from app.models.trade import Trade
from app.models.subscription import Subscription
from app.models.learner_trade_unlock import LearnerUnlockedTrade
from app.utils.response_cache import cache_response

logger = logging.getLogger(__name__)
pro_traders_bp = Blueprint("pro_traders_public", __name__)


def _compute_live_trader_stats(trader_id: str):
    """Compute live public stats directly from trades/subscriptions."""
    now = datetime.now(timezone.utc)

    total_trades, winning_trades, closed_trades = (
        db.session.query(
            func.count(Trade.id),
            func.coalesce(func.sum(case((Trade.status == "target_hit", 1), else_=0)), 0),
            func.coalesce(func.sum(case((Trade.status.in_(["target_hit", "sl_hit"]), 1), else_=0)), 0),
        )
        .filter(Trade.trader_id == trader_id)
        .first()
    )

    total_trades = int(total_trades or 0)
    winning_trades = int(winning_trades or 0)
    closed_trades = int(closed_trades or 0)

    win_rate = round((winning_trades / closed_trades) * 100, 2) if closed_trades > 0 else 0.0

    total_subscribers = Subscription.query.filter(
        Subscription.trader_id == trader_id,
        Subscription.status == "active",
        Subscription.ends_at > now,
    ).count()

    return {
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "closed_trades": closed_trades,
        "win_rate": win_rate,
        "accuracy_score": win_rate,
        "total_subscribers": total_subscribers,
    }


@pro_traders_bp.route("", methods=["GET"])
@require_auth
@cache_response(ttl_seconds=20, key_prefix="pro_traders_public")
def list_pro_traders():
    """Get list of all pro-traders with public info."""
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)
    sort_by = request.args.get("sort_by", "accuracy_score")

    now = datetime.now(timezone.utc)
    trade_stats_subq = (
        db.session.query(
            Trade.trader_id.label("trader_id"),
            func.count(Trade.id).label("total_trades"),
            func.coalesce(func.sum(case((Trade.status == "target_hit", 1), else_=0)), 0).label("winning_trades"),
            func.coalesce(func.sum(case((Trade.status.in_(["target_hit", "sl_hit"]), 1), else_=0)), 0).label("closed_trades"),
        )
        .group_by(Trade.trader_id)
        .subquery()
    )
    subscriber_stats_subq = (
        db.session.query(
            Subscription.trader_id.label("trader_id"),
            func.count(Subscription.id).label("total_subscribers"),
        )
        .filter(
            Subscription.status == "active",
            Subscription.ends_at > now,
        )
        .group_by(Subscription.trader_id)
        .subquery()
    )

    query = (
        db.session.query(
            ProTraderProfile,
            Profile,
            trade_stats_subq.c.total_trades,
            trade_stats_subq.c.winning_trades,
            trade_stats_subq.c.closed_trades,
            subscriber_stats_subq.c.total_subscribers,
        )
        .join(Profile, Profile.user_id == ProTraderProfile.user_id)
        .outerjoin(trade_stats_subq, trade_stats_subq.c.trader_id == ProTraderProfile.user_id)
        .outerjoin(subscriber_stats_subq, subscriber_stats_subq.c.trader_id == ProTraderProfile.user_id)
        .filter(ProTraderProfile.is_active == True)
    )

    if sort_by == "subscribers":
        query = query.order_by(func.coalesce(subscriber_stats_subq.c.total_subscribers, 0).desc())
    else:
        query = query.order_by(ProTraderProfile.accuracy_score.desc())

    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    pages = (total + per_page - 1) // per_page if per_page else 0

    traders = []
    for pt, prof, total_trades, winning_trades, closed_trades, total_subscribers in items:
        total_trades = int(total_trades or 0)
        winning_trades = int(winning_trades or 0)
        closed_trades = int(closed_trades or 0)
        total_subscribers = int(total_subscribers or 0)
        win_rate = round((winning_trades / closed_trades) * 100, 2) if closed_trades > 0 else float(pt.accuracy_score or 0)
        traders.append({
            "trader_id": pt.user_id,
            "display_name": prof.display_name if prof else "Unknown",
            "avatar_url": prof.avatar_url if prof else None,
            "bio": pt.bio,
            "accuracy_score": float(win_rate),
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "closed_trades": closed_trades,
            "win_rate": float(win_rate),
            "total_subscribers": total_subscribers,
            "subscribers_count": total_subscribers,
            "monthly_subscription_price": float(pt.monthly_subscription_price or 0),
            "specializations": pt.specializations or [],
            "trading_style": pt.trading_style,
            "profile_picture_url": pt.profile_picture_url,
        })

    return jsonify({
        "traders": traders,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }), 200


@pro_traders_bp.route("/<trader_id>/profile", methods=["GET"])
@require_auth
@cache_response(ttl_seconds=20, key_prefix="pro_trader_profile")
def get_pro_trader_profile(trader_id):
    """Get public profile details for a specific pro trader."""
    pt = ProTraderProfile.query.filter_by(user_id=trader_id, is_active=True).first()
    if not pt:
        return jsonify({"error": "Pro trader not found"}), 404

    prof = Profile.query.filter_by(user_id=trader_id).first()
    stats = _compute_live_trader_stats(trader_id)

    return jsonify({
        "trader_id": pt.user_id,
        "display_name": prof.display_name if prof else "Unknown",
        "avatar_url": prof.avatar_url if prof else None,
        "bio": pt.bio,
        "accuracy_score": float(stats["accuracy_score"]),
        "total_trades": stats["total_trades"],
        "winning_trades": stats["winning_trades"],
        "closed_trades": stats["closed_trades"],
        "win_rate": float(stats["win_rate"]),
        "total_subscribers": stats["total_subscribers"],
        "subscribers_count": stats["total_subscribers"],
        "monthly_subscription_price": float(pt.monthly_subscription_price or 0),
        "specializations": pt.specializations or [],
        "trading_style": pt.trading_style,
        "years_of_experience": pt.years_of_experience,
        "profile_picture_url": pt.profile_picture_url,
        "leaderboard_rank": pt.leaderboard_rank,
    }), 200


@pro_traders_bp.route("/<trader_id>/trades", methods=["GET"])
@require_auth
@cache_response(ttl_seconds=10, key_prefix="pro_trader_trades")
def get_pro_trader_trades(trader_id):
    """Get trades from a specific pro trader."""
    user_id = get_jwt_identity()
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)
    status_filter = request.args.get("status", "active")

    pt = ProTraderProfile.query.filter_by(user_id=trader_id, is_active=True).first()
    if not pt:
        return jsonify({"error": "Pro trader not found"}), 404

    query = Trade.query.filter_by(trader_id=trader_id)
    if status_filter in Trade.VALID_STATUSES + ["active"]:
        query = query.filter_by(status=status_filter)
    query = query.order_by(Trade.created_at.desc())
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    from app.routes.learner_feed import _has_active_subscription, _serialize_trade_public
    prof = Profile.query.filter_by(user_id=trader_id).first()
    has_sub = _has_active_subscription(user_id, trader_id)

    trade_ids = [trade.id for trade in paginated.items]
    unlocked_ids = {
        row.trade_id
        for row in LearnerUnlockedTrade.query.filter(
            LearnerUnlockedTrade.learner_id == user_id,
            LearnerUnlockedTrade.trade_id.in_(trade_ids),
        ).all()
    } if trade_ids else set()

    trades = []
    for trade in paginated.items:
        is_unlocked = trade.id in unlocked_ids
        trades.append(_serialize_trade_public(trade, prof, is_unlocked, has_sub, pt))

    return jsonify({
        "trades": trades,
        "total": paginated.total,
        "page": page,
        "per_page": per_page,
        "pages": paginated.pages,
    }), 200
