"""
Pro-Trader Public Info routes (learner-facing)
- GET /api/pro-traders
- GET /api/pro-traders/{id}/profile
- GET /api/pro-traders/{id}/trades
"""
import logging
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from app import db
from app.middleware import require_auth
from app.models.pro_trader_profile import ProTraderProfile
from app.models.profile import Profile
from app.models.trade import Trade

logger = logging.getLogger(__name__)
pro_traders_bp = Blueprint("pro_traders_public", __name__)


@pro_traders_bp.route("", methods=["GET"])
@require_auth
def list_pro_traders():
    """Get list of all pro-traders with public info."""
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)
    sort_by = request.args.get("sort_by", "accuracy_score")

    query = ProTraderProfile.query.filter_by(is_active=True)

    if sort_by == "subscribers":
        query = query.order_by(ProTraderProfile.total_subscribers.desc())
    else:
        query = query.order_by(ProTraderProfile.accuracy_score.desc())

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    traders = []
    for pt in paginated.items:
        prof = Profile.query.filter_by(user_id=pt.user_id).first()
        traders.append({
            "trader_id": pt.user_id,
            "display_name": prof.display_name if prof else "Unknown",
            "avatar_url": prof.avatar_url if prof else None,
            "bio": pt.bio,
            "accuracy_score": float(pt.accuracy_score or 0),
            "total_trades": pt.total_trades,
            "winning_trades": pt.winning_trades,
            "total_subscribers": pt.total_subscribers,
            "monthly_subscription_price": float(pt.monthly_subscription_price or 0),
            "specializations": pt.specializations or [],
            "trading_style": pt.trading_style,
            "profile_picture_url": pt.profile_picture_url,
        })

    return jsonify({
        "traders": traders,
        "total": paginated.total,
        "page": page,
        "per_page": per_page,
        "pages": paginated.pages,
    }), 200


@pro_traders_bp.route("/<trader_id>/profile", methods=["GET"])
@require_auth
def get_pro_trader_profile(trader_id):
    """Get public profile details for a specific pro trader."""
    pt = ProTraderProfile.query.filter_by(user_id=trader_id, is_active=True).first()
    if not pt:
        return jsonify({"error": "Pro trader not found"}), 404

    prof = Profile.query.filter_by(user_id=trader_id).first()

    return jsonify({
        "trader_id": pt.user_id,
        "display_name": prof.display_name if prof else "Unknown",
        "avatar_url": prof.avatar_url if prof else None,
        "bio": pt.bio,
        "accuracy_score": float(pt.accuracy_score or 0),
        "total_trades": pt.total_trades,
        "winning_trades": pt.winning_trades,
        "total_subscribers": pt.total_subscribers,
        "monthly_subscription_price": float(pt.monthly_subscription_price or 0),
        "specializations": pt.specializations or [],
        "trading_style": pt.trading_style,
        "years_of_experience": pt.years_of_experience,
        "profile_picture_url": pt.profile_picture_url,
        "leaderboard_rank": pt.leaderboard_rank,
    }), 200


@pro_traders_bp.route("/<trader_id>/trades", methods=["GET"])
@require_auth
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

    from app.routes.learner_feed import _is_trade_unlocked, _has_active_subscription, _serialize_trade_public
    prof = Profile.query.filter_by(user_id=trader_id).first()
    has_sub = _has_active_subscription(user_id, trader_id)

    trades = []
    for trade in paginated.items:
        is_unlocked = _is_trade_unlocked(user_id, trade.id)
        trades.append(_serialize_trade_public(trade, prof, is_unlocked, has_sub))

    return jsonify({
        "trades": trades,
        "total": paginated.total,
        "page": page,
        "per_page": per_page,
        "pages": paginated.pages,
    }), 200
