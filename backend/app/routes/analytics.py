"""
Analytics routes
- GET /api/pro-trader/analytics/accuracy
- GET /api/pro-trader/analytics/performance-chart
- GET /api/pro-trader/analytics/win-loss
- GET /api/pro-trader/analytics/rrr
- GET /api/pro-trader/analytics/monthly-stats
- GET /api/pro-trader/analytics/trade-history
"""
import logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import func, extract

from app import db
from app.middleware import require_pro_trader
from app.models.trade import Trade
from app.models.pro_trader_profile import ProTraderProfile

logger = logging.getLogger(__name__)
analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/analytics/accuracy", methods=["GET"])
@require_pro_trader
def get_accuracy():
    """Get current accuracy score."""
    user_id = get_jwt_identity()
    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt_profile:
        return jsonify({"error": "Profile not found"}), 404

    return jsonify({
        "accuracy_score": float(pt_profile.accuracy_score or 0),
        "total_trades": pt_profile.total_trades,
        "winning_trades": pt_profile.winning_trades,
        "losing_trades": pt_profile.total_trades - pt_profile.winning_trades,
    }), 200


@analytics_bp.route("/analytics/performance-chart", methods=["GET"])
@require_pro_trader
def get_performance_chart():
    """Get 12-month accuracy trend data."""
    user_id = get_jwt_identity()
    now = datetime.now(timezone.utc)

    monthly_data = []
    for i in range(11, -1, -1):
        month_start = (now.replace(day=1) - timedelta(days=i * 30)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1)

        trades_in_month = Trade.query.filter(
            Trade.trader_id == user_id,
            Trade.status.in_(["target_hit", "sl_hit"]),
            Trade.closed_at >= month_start,
            Trade.closed_at < month_end,
        ).all()

        total = len(trades_in_month)
        wins = sum(1 for t in trades_in_month if t.status == "target_hit")
        accuracy = round((wins / total) * 100, 2) if total > 0 else 0.0

        monthly_data.append({
            "month": month_start.strftime("%b %Y"),
            "year": month_start.year,
            "month_num": month_start.month,
            "total_trades": total,
            "wins": wins,
            "losses": total - wins,
            "accuracy": accuracy,
        })

    return jsonify({"chart_data": monthly_data}), 200


@analytics_bp.route("/analytics/win-loss", methods=["GET"])
@require_pro_trader
def get_win_loss():
    """Get win/loss counts."""
    user_id = get_jwt_identity()

    wins = Trade.query.filter_by(trader_id=user_id, status="target_hit").count()
    losses = Trade.query.filter_by(trader_id=user_id, status="sl_hit").count()
    active = Trade.query.filter_by(trader_id=user_id, status="active").count()
    cancelled = Trade.query.filter_by(trader_id=user_id, status="cancelled").count()

    return jsonify({
        "wins": wins,
        "losses": losses,
        "active": active,
        "cancelled": cancelled,
        "total_closed": wins + losses,
    }), 200


@analytics_bp.route("/analytics/rrr", methods=["GET"])
@require_pro_trader
def get_rrr():
    """Get average Risk-Reward Ratio across all trades."""
    user_id = get_jwt_identity()

    result = db.session.query(func.avg(Trade.rrr)).filter(
        Trade.trader_id == user_id,
        Trade.status.in_(["target_hit", "sl_hit", "active"])
    ).scalar()

    avg_rrr = float(result) if result else 0.0
    return jsonify({"average_rrr": round(avg_rrr, 4)}), 200


@analytics_bp.route("/analytics/monthly-stats", methods=["GET"])
@require_pro_trader
def get_monthly_stats():
    """Get monthly performance stats."""
    user_id = get_jwt_identity()
    now = datetime.now(timezone.utc)

    # Current month
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    trades_this_month = Trade.query.filter(
        Trade.trader_id == user_id,
        Trade.created_at >= month_start,
    ).all()

    total = len(trades_this_month)
    wins = sum(1 for t in trades_this_month if t.status == "target_hit")
    losses = sum(1 for t in trades_this_month if t.status == "sl_hit")
    active = sum(1 for t in trades_this_month if t.status == "active")
    accuracy = round((wins / (wins + losses)) * 100, 2) if (wins + losses) > 0 else 0.0

    # Earnings this month (from revenue splits)
    from app.models.revenue_split import RevenueSplit
    from app.models.payment import Payment
    monthly_earnings_result = db.session.query(func.sum(RevenueSplit.pro_trader_amount)).join(
        Payment, RevenueSplit.payment_id == Payment.id
    ).filter(
        RevenueSplit.trader_id == user_id,
        Payment.completed_at >= month_start,
        Payment.status == "success",
    ).scalar()
    monthly_earnings = float(monthly_earnings_result) if monthly_earnings_result else 0.0

    return jsonify({
        "month": now.strftime("%B %Y"),
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "active": active,
        "accuracy": accuracy,
        "monthly_earnings": monthly_earnings,
    }), 200


@analytics_bp.route("/analytics/trade-history", methods=["GET"])
@require_pro_trader
def get_trade_history():
    """Get closed trades list with pagination."""
    user_id = get_jwt_identity()
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)

    query = Trade.query.filter(
        Trade.trader_id == user_id,
        Trade.status.in_(["target_hit", "sl_hit", "cancelled"])
    ).order_by(Trade.closed_at.desc())

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "trades": [t.to_dict() for t in paginated.items],
        "total": paginated.total,
        "page": page,
        "per_page": per_page,
        "pages": paginated.pages,
    }), 200
