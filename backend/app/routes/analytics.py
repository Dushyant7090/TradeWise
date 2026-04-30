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
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import case, func, extract

from app import db
from app.middleware import require_pro_trader
from app.models.trade import Trade
from app.models.pro_trader_profile import ProTraderProfile
from app.utils.response_cache import cache_response

logger = logging.getLogger(__name__)
analytics_bp = Blueprint("analytics", __name__)


def _month_floor(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _add_months(dt: datetime, months: int) -> datetime:
    month_idx = (dt.month - 1) + months
    year = dt.year + (month_idx // 12)
    month = (month_idx % 12) + 1
    return dt.replace(year=year, month=month, day=1)


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
        "leaderboard_rank": pt_profile.leaderboard_rank,
    }), 200


@analytics_bp.route("/analytics/performance-chart", methods=["GET"])
@require_pro_trader
@cache_response(ttl_seconds=12, key_prefix="pro_analytics_performance")
def get_performance_chart():
    """Get 12-month accuracy trend data."""
    user_id = get_jwt_identity()
    now = datetime.now(timezone.utc)

    month_zero = _month_floor(now)
    first_month = _add_months(month_zero, -11)
    end_month = _add_months(month_zero, 1)

    rows = (
        db.session.query(
            extract("year", Trade.closed_at).label("year"),
            extract("month", Trade.closed_at).label("month"),
            func.count(Trade.id).label("total"),
            func.coalesce(func.sum(case((Trade.status == "target_hit", 1), else_=0)), 0).label("wins"),
        )
        .filter(
            Trade.trader_id == user_id,
            Trade.status.in_(["target_hit", "sl_hit"]),
            Trade.closed_at >= first_month,
            Trade.closed_at < end_month,
        )
        .group_by(extract("year", Trade.closed_at), extract("month", Trade.closed_at))
        .all()
    )
    stats_map = {
        (int(row.year), int(row.month)): {
            "total": int(row.total or 0),
            "wins": int(row.wins or 0),
        }
        for row in rows
    }

    monthly_data = []
    for i in range(11, -1, -1):
        month_start = _add_months(month_zero, -i)
        stats = stats_map.get((month_start.year, month_start.month), {"total": 0, "wins": 0})
        total = stats["total"]
        wins = stats["wins"]
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
@cache_response(ttl_seconds=12, key_prefix="pro_analytics_win_loss")
def get_win_loss():
    """Get win/loss counts."""
    user_id = get_jwt_identity()

    wins, losses, active, cancelled = (
        db.session.query(
            func.coalesce(func.sum(case((Trade.status == "target_hit", 1), else_=0)), 0),
            func.coalesce(func.sum(case((Trade.status == "sl_hit", 1), else_=0)), 0),
            func.coalesce(func.sum(case((Trade.status == "active", 1), else_=0)), 0),
            func.coalesce(func.sum(case((Trade.status == "cancelled", 1), else_=0)), 0),
        )
        .filter(Trade.trader_id == user_id)
        .first()
    )

    wins = int(wins or 0)
    losses = int(losses or 0)
    active = int(active or 0)
    cancelled = int(cancelled or 0)

    return jsonify({
        "wins": wins,
        "losses": losses,
        "active": active,
        "cancelled": cancelled,
        "total_trades": wins + losses,
        "total_closed": wins + losses,
    }), 200


@analytics_bp.route("/analytics/rrr", methods=["GET"])
@require_pro_trader
@cache_response(ttl_seconds=12, key_prefix="pro_analytics_rrr")
def get_rrr():
    """Get average Risk-Reward Ratio across all trades."""
    user_id = get_jwt_identity()

    rows = db.session.query(Trade.rrr).filter(
        Trade.trader_id == user_id,
        Trade.status.in_(["target_hit", "sl_hit", "active"]),
        Trade.rrr.isnot(None),
    ).all()

    rrr_values = [float(row[0]) for row in rows if row[0] is not None]
    if not rrr_values:
        return jsonify({
            "average_rrr": 0.0,
            "best_rrr": 0.0,
            "worst_rrr": 0.0,
            "distribution": {
                "labels": ["<1", "1-1.5", "1.5-2", "2-3", ">3"],
                "values": [0, 0, 0, 0, 0],
            },
        }), 200

    avg_rrr = round(sum(rrr_values) / len(rrr_values), 4)
    best_rrr = round(max(rrr_values), 4)
    worst_rrr = round(min(rrr_values), 4)

    distribution = [0, 0, 0, 0, 0]
    for value in rrr_values:
        if value < 1:
            distribution[0] += 1
        elif value < 1.5:
            distribution[1] += 1
        elif value < 2:
            distribution[2] += 1
        elif value < 3:
            distribution[3] += 1
        else:
            distribution[4] += 1

    return jsonify({
        "average_rrr": avg_rrr,
        "best_rrr": best_rrr,
        "worst_rrr": worst_rrr,
        "distribution": {
            "labels": ["<1", "1-1.5", "1.5-2", "2-3", ">3"],
            "values": distribution,
        },
    }), 200


@analytics_bp.route("/analytics/monthly-stats", methods=["GET"])
@require_pro_trader
@cache_response(ttl_seconds=12, key_prefix="pro_analytics_monthly")
def get_monthly_stats():
    """Get monthly performance stats."""
    user_id = get_jwt_identity()
    now = datetime.now(timezone.utc)

    month_start = _month_floor(now)

    # Earnings by month (from revenue splits)
    from app.models.revenue_split import RevenueSplit
    from app.models.payment import Payment

    first_month = _add_months(month_start, -11)
    end_month = _add_months(month_start, 1)

    trade_rows = (
        db.session.query(
            extract("year", Trade.created_at).label("year"),
            extract("month", Trade.created_at).label("month"),
            func.count(Trade.id).label("total"),
            func.coalesce(func.sum(case((Trade.status == "target_hit", 1), else_=0)), 0).label("wins"),
            func.coalesce(func.sum(case((Trade.status == "sl_hit", 1), else_=0)), 0).label("losses"),
            func.coalesce(func.sum(case((Trade.status == "active", 1), else_=0)), 0).label("active"),
        )
        .filter(
            Trade.trader_id == user_id,
            Trade.created_at >= first_month,
            Trade.created_at < end_month,
        )
        .group_by(extract("year", Trade.created_at), extract("month", Trade.created_at))
        .all()
    )
    trade_map = {
        (int(row.year), int(row.month)): {
            "total": int(row.total or 0),
            "wins": int(row.wins or 0),
            "losses": int(row.losses or 0),
            "active": int(row.active or 0),
        }
        for row in trade_rows
    }

    earnings_rows = (
        db.session.query(
            extract("year", Payment.completed_at).label("year"),
            extract("month", Payment.completed_at).label("month"),
            func.coalesce(func.sum(RevenueSplit.pro_trader_amount), 0).label("earnings"),
        )
        .join(Payment, RevenueSplit.payment_id == Payment.id)
        .filter(
            RevenueSplit.trader_id == user_id,
            Payment.status == "success",
            Payment.completed_at >= first_month,
            Payment.completed_at < end_month,
        )
        .group_by(extract("year", Payment.completed_at), extract("month", Payment.completed_at))
        .all()
    )
    earnings_map = {
        (int(row.year), int(row.month)): float(row.earnings or 0)
        for row in earnings_rows
    }

    monthly_rows = []
    for i in range(11, -1, -1):
        start = _add_months(month_start, -i)
        trade_stats = trade_map.get((start.year, start.month), {
            "total": 0,
            "wins": 0,
            "losses": 0,
            "active": 0,
        })

        total = trade_stats["total"]
        wins = trade_stats["wins"]
        losses = trade_stats["losses"]
        active = trade_stats["active"]
        closed = wins + losses
        accuracy = round((wins / closed) * 100, 2) if closed > 0 else 0.0
        earnings = earnings_map.get((start.year, start.month), 0.0)

        monthly_rows.append({
            "month": start.strftime("%b %Y"),
            "year": start.year,
            "month_num": start.month,
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "active": active,
            "accuracy": accuracy,
            "earnings": round(earnings, 2),
        })

    current = monthly_rows[-1] if monthly_rows else {
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "active": 0,
        "accuracy": 0.0,
        "earnings": 0.0,
    }

    return jsonify({
        "month": now.strftime("%B %Y"),
        "total_trades": current["total_trades"],
        "wins": current["wins"],
        "losses": current["losses"],
        "active": current["active"],
        "accuracy": current["accuracy"],
        "monthly_earnings": current["earnings"],
        "data": monthly_rows,
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
