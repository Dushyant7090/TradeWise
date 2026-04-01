"""
Admin routes — all endpoints require admin JWT role.

Endpoints:
  GET  /api/admin/stats                      — Dashboard summary stats
  GET  /api/admin/users                      — List all users (paginated, searchable)
  GET  /api/admin/users/<user_id>            — User detail
  POST /api/admin/users/<user_id>/suspend    — Suspend a user
  POST /api/admin/users/<user_id>/reactivate — Reactivate a suspended user
  POST /api/admin/users/<user_id>/ban        — Permanently ban a user
  GET  /api/admin/trades                     — List all trades (paginated, filterable)
  GET  /api/admin/trades/<trade_id>          — Trade detail
  POST /api/admin/trades/<trade_id>/flag     — Flag a trade
  POST /api/admin/trades/<trade_id>/unflag   — Unflag a trade
  GET  /api/admin/reports                    — List all reports/flags
  POST /api/admin/reports/<report_id>/resolve — Resolve a report
  POST /api/admin/reports/<report_id>/dismiss — Dismiss a report
  GET  /api/admin/payouts                    — List all payouts
  POST /api/admin/payouts/<payout_id>/mark-paid   — Mark payout as paid
  POST /api/admin/payouts/<payout_id>/mark-unpaid — Mark payout as unpaid
  GET  /api/admin/comments                   — List all comments
  POST /api/admin/comments/<comment_id>/reply — Admin reply to comment
  DELETE /api/admin/comments/<comment_id>   — Delete a comment
  GET  /api/admin/kyc                        — List pending KYC requests
  POST /api/admin/kyc/<user_id>/approve      — Approve KYC
  POST /api/admin/kyc/<user_id>/reject       — Reject KYC
  GET  /api/admin/analytics/revenue          — Monthly revenue chart data
  GET  /api/admin/analytics/users            — User growth chart data
  GET  /api/admin/analytics/flags            — Flags/reports trend data
  GET  /api/admin/analytics/payouts          — Payouts history chart data
  GET  /api/admin/export/users               — CSV export — users
  GET  /api/admin/export/trades              — CSV export — trades
  GET  /api/admin/export/payouts             — CSV export — payouts
  GET  /api/admin/export/reports             — CSV export — reports/flags
"""
import csv
import io
import logging
from datetime import datetime, timezone, timedelta

from flask import Blueprint, jsonify, request, Response
from flask_jwt_extended import get_jwt_identity

from app import db
from app.middleware import require_admin
from app.models.user import User
from app.models.profile import Profile
from app.models.pro_trader_profile import ProTraderProfile
from app.models.learner_profile import LearnerProfile
from app.models.trade import Trade
from app.models.report import Report
from app.models.comment import Comment
from app.models.payout import Payout
from app.models.payment import Payment
from app.models.learner_flag import LearnerFlag

logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _paginate(query, page, per_page=20):
    """Return paginated result dict."""
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return items, total


def _user_summary(user: User) -> dict:
    """Build a summary dict for a user."""
    profile = user.profile
    pt = user.pro_trader_profile
    lp = LearnerProfile.query.filter_by(user_id=user.id).first()
    role = profile.role if profile else "unknown"
    return {
        "id": user.id,
        "email": user.email,
        "display_name": profile.display_name if profile else None,
        "role": role,
        "is_active": user.is_active,
        "is_banned": getattr(profile, "is_banned", False),
        "is_suspended": getattr(profile, "is_suspended", False),
        "is_verified": profile.is_verified if profile else False,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        # Pro trader stats
        "kyc_status": pt.kyc_status if pt else None,
        "total_trades": pt.total_trades if pt else 0,
        "total_subscribers": pt.total_subscribers if pt else 0,
        "accuracy_score": pt.accuracy_score if pt else None,
        # Learner stats
        "total_unlocked_trades": lp.total_unlocked_trades if lp else 0,
        "credits": lp.credits if lp else 0,
    }


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@admin_bp.route("/stats", methods=["GET"])
@require_admin
def get_stats():
    """Return dashboard summary statistics."""
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_pro_traders = Profile.query.filter_by(role="pro_trader").count()
    total_learners = Profile.query.filter_by(role="public_trader").count()

    # Active users in last 30 days — approximated by recently created users
    active_users = User.query.filter(
        User.created_at >= thirty_days_ago,
        User.is_active == True
    ).count()

    # Revenue this month (successful payments)
    monthly_revenue = (
        db.session.query(db.func.sum(Payment.amount))
        .filter(Payment.status == "success", Payment.created_at >= start_of_month)
        .scalar() or 0
    )

    # Pending payouts
    pending_payouts_amount = (
        db.session.query(db.func.sum(Payout.amount))
        .filter(Payout.status.in_(["initiated", "processing"]))
        .scalar() or 0
    )
    pending_payouts_count = Payout.query.filter(
        Payout.status.in_(["initiated", "processing"])
    ).count()

    # Paid payouts this month
    paid_payouts_amount = (
        db.session.query(db.func.sum(Payout.amount))
        .filter(Payout.status == "success", Payout.initiated_at >= start_of_month)
        .scalar() or 0
    )

    # Flagged trades this month
    flagged_trades_month = Trade.query.filter(
        Trade.flag_count > 0, Trade.created_at >= start_of_month
    ).count()

    # Pending KYC
    pending_kyc = ProTraderProfile.query.filter_by(kyc_status="pending").count()

    # Open reports
    open_reports = Report.query.filter_by(status="pending").count()

    return jsonify({
        "total_pro_traders": total_pro_traders,
        "total_learners": total_learners,
        "active_users_30d": active_users,
        "monthly_revenue": float(monthly_revenue),
        "pending_payouts_amount": float(pending_payouts_amount),
        "pending_payouts_count": pending_payouts_count,
        "paid_payouts_month": float(paid_payouts_amount),
        "flagged_trades_month": flagged_trades_month,
        "pending_kyc": pending_kyc,
        "open_reports": open_reports,
    }), 200


# ---------------------------------------------------------------------------
# User Management
# ---------------------------------------------------------------------------

@admin_bp.route("/users", methods=["GET"])
@require_admin
def list_users():
    """List all users with optional search and role filter."""
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)
    search = request.args.get("search", "").strip()
    role = request.args.get("role", "").strip()

    query = (
        db.session.query(User)
        .join(Profile, Profile.user_id == User.id)
        .order_by(User.created_at.desc())
    )

    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(User.email.ilike(like), Profile.display_name.ilike(like))
        )
    if role:
        query = query.filter(Profile.role == role)

    users, total = _paginate(query, page, per_page)
    return jsonify({
        "users": [_user_summary(u) for u in users],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }), 200


@admin_bp.route("/users/<user_id>", methods=["GET"])
@require_admin
def get_user(user_id):
    """Get detailed info for a single user."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"user": _user_summary(user)}), 200


@admin_bp.route("/users/<user_id>/suspend", methods=["POST"])
@require_admin
def suspend_user(user_id):
    """Suspend a user (reversible)."""
    requesting_admin_id = get_jwt_identity()
    if user_id == requesting_admin_id:
        return jsonify({"error": "Admins cannot suspend their own account"}), 403

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    profile = user.profile
    if not profile:
        return jsonify({"error": "Profile not found"}), 404

    if profile.role == "admin":
        return jsonify({"error": "Admin accounts cannot be suspended via this interface"}), 403

    if getattr(profile, "is_banned", False):
        return jsonify({"error": "User is permanently banned and cannot be suspended"}), 400

    user.is_active = False
    db.session.commit()
    return jsonify({"message": "User suspended successfully"}), 200


@admin_bp.route("/users/<user_id>/reactivate", methods=["POST"])
@require_admin
def reactivate_user(user_id):
    """Reactivate a suspended user."""
    requesting_admin_id = get_jwt_identity()
    if user_id == requesting_admin_id:
        return jsonify({"error": "Admins cannot reactivate their own account via this interface"}), 403

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    profile = user.profile
    if profile and getattr(profile, "is_banned", False):
        return jsonify({"error": "Banned users cannot be reactivated"}), 400

    user.is_active = True
    db.session.commit()
    return jsonify({"message": "User reactivated successfully"}), 200


@admin_bp.route("/users/<user_id>/ban", methods=["POST"])
@require_admin
def ban_user(user_id):
    """Permanently ban a user (irreversible)."""
    requesting_admin_id = get_jwt_identity()
    if user_id == requesting_admin_id:
        return jsonify({"error": "Admins cannot ban their own account"}), 403

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    profile = user.profile
    if not profile:
        return jsonify({"error": "Profile not found"}), 404

    if profile.role == "admin":
        return jsonify({"error": "Admin accounts cannot be banned via this interface"}), 403

    # Mark as permanently banned by deactivating and storing ban flag in profile
    user.is_active = False
    profile.is_banned = True
    db.session.commit()
    return jsonify({"message": "User permanently banned"}), 200


# ---------------------------------------------------------------------------
# Trade Monitoring
# ---------------------------------------------------------------------------

@admin_bp.route("/trades", methods=["GET"])
@require_admin
def list_trades():
    """List all trades with optional filters."""
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)
    status = request.args.get("status", "").strip()
    search = request.args.get("search", "").strip()
    flagged_only = request.args.get("flagged_only", "false").lower() == "true"

    query = Trade.query.order_by(Trade.created_at.desc())
    if status:
        query = query.filter(Trade.status == status)
    if flagged_only:
        query = query.filter(Trade.flag_count > 0)
    if search:
        query = query.filter(Trade.symbol.ilike(f"%{search}%"))

    trades, total = _paginate(query, page, per_page)

    result = []
    for t in trades:
        d = t.to_dict()
        # Attach trader display name
        profile = Profile.query.filter_by(user_id=t.trader_id).first()
        d["trader_name"] = profile.display_name if profile else None
        result.append(d)

    return jsonify({
        "trades": result,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }), 200


@admin_bp.route("/trades/<trade_id>", methods=["GET"])
@require_admin
def get_trade(trade_id):
    """Get a single trade detail."""
    trade = Trade.query.get(trade_id)
    if not trade:
        return jsonify({"error": "Trade not found"}), 404
    d = trade.to_dict()
    profile = Profile.query.filter_by(user_id=trade.trader_id).first()
    d["trader_name"] = profile.display_name if profile else None
    return jsonify({"trade": d}), 200


@admin_bp.route("/trades/<trade_id>/flag", methods=["POST"])
@require_admin
def admin_flag_trade(trade_id):
    """Admin-flag a trade (increment flag_count)."""
    trade = Trade.query.get(trade_id)
    if not trade:
        return jsonify({"error": "Trade not found"}), 404
    trade.flag_count = (trade.flag_count or 0) + 1
    db.session.commit()
    return jsonify({"message": "Trade flagged", "flag_count": trade.flag_count}), 200


@admin_bp.route("/trades/<trade_id>/unflag", methods=["POST"])
@require_admin
def admin_unflag_trade(trade_id):
    """Clear all admin flags on a trade."""
    trade = Trade.query.get(trade_id)
    if not trade:
        return jsonify({"error": "Trade not found"}), 404
    trade.flag_count = 0
    db.session.commit()
    return jsonify({"message": "Trade flags cleared", "flag_count": 0}), 200


# ---------------------------------------------------------------------------
# Reports / Flags
# ---------------------------------------------------------------------------

@admin_bp.route("/reports", methods=["GET"])
@require_admin
def list_reports():
    """List all reports with optional status filter."""
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)
    status = request.args.get("status", "").strip()

    query = Report.query.order_by(Report.created_at.desc())
    if status:
        query = query.filter(Report.status == status)

    reports, total = _paginate(query, page, per_page)

    result = []
    for r in reports:
        d = r.to_dict()
        trade = Trade.query.get(r.trade_id)
        d["trade_symbol"] = trade.symbol if trade else None
        reporter_profile = Profile.query.filter_by(user_id=r.reporter_id).first()
        d["reporter_name"] = reporter_profile.display_name if reporter_profile else None
        result.append(d)

    # Also include learner flags
    lf_query = LearnerFlag.query.order_by(LearnerFlag.created_at.desc())
    if status:
        lf_query = lf_query.filter(LearnerFlag.status == status)
    learner_flags = lf_query.limit(50).all()
    learner_flag_list = []
    for lf in learner_flags:
        d = lf.to_dict()
        d["type"] = "learner_flag"
        trade = Trade.query.get(lf.trade_id)
        d["trade_symbol"] = trade.symbol if trade else None
        reporter_profile = Profile.query.filter_by(user_id=lf.learner_id).first()
        d["reporter_name"] = reporter_profile.display_name if reporter_profile else None
        learner_flag_list.append(d)

    return jsonify({
        "reports": result,
        "learner_flags": learner_flag_list,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }), 200


@admin_bp.route("/reports/<report_id>/resolve", methods=["POST"])
@require_admin
def resolve_report(report_id):
    """Resolve a report with an admin verdict."""
    report = Report.query.get(report_id)
    if not report:
        return jsonify({"error": "Report not found"}), 404
    data = request.get_json() or {}
    verdict = data.get("verdict", "").strip()
    report.status = "resolved"
    report.admin_verdict = verdict or "Resolved by admin"
    report.resolved_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"message": "Report resolved", "report": report.to_dict()}), 200


@admin_bp.route("/reports/<report_id>/dismiss", methods=["POST"])
@require_admin
def dismiss_report(report_id):
    """Dismiss a report."""
    report = Report.query.get(report_id)
    if not report:
        return jsonify({"error": "Report not found"}), 404
    data = request.get_json() or {}
    note = data.get("note", "").strip()
    report.status = "resolved"
    report.admin_verdict = note or "Dismissed by admin"
    report.resolved_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"message": "Report dismissed", "report": report.to_dict()}), 200


# ---------------------------------------------------------------------------
# Payout Management
# ---------------------------------------------------------------------------

@admin_bp.route("/payouts", methods=["GET"])
@require_admin
def list_payouts():
    """List all payouts with optional status filter."""
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)
    status = request.args.get("status", "").strip()
    search = request.args.get("search", "").strip()

    query = (
        db.session.query(Payout)
        .join(Profile, Profile.user_id == Payout.trader_id, isouter=True)
        .order_by(Payout.initiated_at.desc())
    )
    if status:
        query = query.filter(Payout.status == status)
    if search:
        query = query.filter(Profile.display_name.ilike(f"%{search}%"))

    payouts, total = _paginate(query, page, per_page)

    result = []
    for p in payouts:
        d = p.to_dict()
        profile = Profile.query.filter_by(user_id=p.trader_id).first()
        d["trader_name"] = profile.display_name if profile else None
        user = User.query.get(p.trader_id)
        d["trader_email"] = user.email if user else None
        result.append(d)

    return jsonify({
        "payouts": result,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }), 200


@admin_bp.route("/payouts/<payout_id>/mark-paid", methods=["POST"])
@require_admin
def mark_payout_paid(payout_id):
    """Mark a payout as successfully paid."""
    payout = Payout.query.get(payout_id)
    if not payout:
        return jsonify({"error": "Payout not found"}), 404
    payout.status = "success"
    payout.completed_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"message": "Payout marked as paid", "payout": payout.to_dict()}), 200


@admin_bp.route("/payouts/<payout_id>/mark-unpaid", methods=["POST"])
@require_admin
def mark_payout_unpaid(payout_id):
    """Revert a payout back to initiated (pending) status."""
    payout = Payout.query.get(payout_id)
    if not payout:
        return jsonify({"error": "Payout not found"}), 404
    payout.status = "initiated"
    payout.completed_at = None
    db.session.commit()
    return jsonify({"message": "Payout marked as unpaid", "payout": payout.to_dict()}), 200


# ---------------------------------------------------------------------------
# Comment Moderation
# ---------------------------------------------------------------------------

@admin_bp.route("/comments", methods=["GET"])
@require_admin
def list_comments():
    """List all comments with optional trade/user filter."""
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)
    trade_id = request.args.get("trade_id", "").strip()
    user_id = request.args.get("user_id", "").strip()

    query = Comment.query.order_by(Comment.created_at.desc())
    if trade_id:
        query = query.filter(Comment.trade_id == trade_id)
    if user_id:
        query = query.filter(Comment.user_id == user_id)

    comments, total = _paginate(query, page, per_page)

    result = []
    for c in comments:
        d = c.to_dict()
        profile = Profile.query.filter_by(user_id=c.user_id).first()
        d["author_name"] = profile.display_name if profile else None
        trade = Trade.query.get(c.trade_id)
        d["trade_symbol"] = trade.symbol if trade else None
        result.append(d)

    return jsonify({
        "comments": result,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }), 200


@admin_bp.route("/comments/<comment_id>/reply", methods=["POST"])
@require_admin
def admin_reply_comment(comment_id):
    """Post an admin reply to a comment thread."""
    parent = Comment.query.get(comment_id)
    if not parent:
        return jsonify({"error": "Comment not found"}), 404

    data = request.get_json() or {}
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "Reply content is required"}), 400

    admin_id = get_jwt_identity()
    reply = Comment(
        trade_id=parent.trade_id,
        user_id=admin_id,
        content=f"[Admin] {content}",
    )
    db.session.add(reply)
    db.session.commit()
    return jsonify({"message": "Reply posted", "comment": reply.to_dict()}), 201


@admin_bp.route("/comments/<comment_id>", methods=["DELETE"])
@require_admin
def delete_comment(comment_id):
    """Delete a comment."""
    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({"error": "Comment not found"}), 404
    db.session.delete(comment)
    db.session.commit()
    return jsonify({"message": "Comment deleted"}), 200


# ---------------------------------------------------------------------------
# KYC Management
# ---------------------------------------------------------------------------

@admin_bp.route("/kyc", methods=["GET"])
@require_admin
def list_kyc():
    """List KYC submissions, filterable by status."""
    status = request.args.get("status", "pending").strip()
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)

    query = ProTraderProfile.query
    if status:
        query = query.filter(ProTraderProfile.kyc_status == status)
    query = query.order_by(ProTraderProfile.created_at.desc())

    profiles, total = _paginate(query, page, per_page)

    result = []
    for pt in profiles:
        d = pt.to_dict()
        user = User.query.get(pt.user_id)
        profile = Profile.query.filter_by(user_id=pt.user_id).first()
        d["email"] = user.email if user else None
        d["display_name"] = profile.display_name if profile else None
        d["document_count"] = len(pt.kyc_documents or {})
        result.append(d)

    return jsonify({
        "kyc_requests": result,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }), 200


@admin_bp.route("/kyc/<user_id>/approve", methods=["POST"])
@require_admin
def approve_kyc(user_id):
    """Approve KYC for a pro trader."""
    pt = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt:
        return jsonify({"error": "Pro trader profile not found"}), 404
    pt.kyc_status = "verified"
    profile = Profile.query.filter_by(user_id=user_id).first()
    if profile:
        profile.is_verified = True
    db.session.commit()
    return jsonify({"message": "KYC approved", "kyc_status": "verified"}), 200


@admin_bp.route("/kyc/<user_id>/reject", methods=["POST"])
@require_admin
def reject_kyc(user_id):
    """Reject KYC for a pro trader."""
    pt = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt:
        return jsonify({"error": "Pro trader profile not found"}), 404
    data = request.get_json() or {}
    pt.kyc_status = "rejected"
    db.session.commit()
    return jsonify({"message": "KYC rejected", "kyc_status": "rejected"}), 200


# ---------------------------------------------------------------------------
# Analytics chart data
# ---------------------------------------------------------------------------

@admin_bp.route("/analytics/revenue", methods=["GET"])
@require_admin
def analytics_revenue():
    """Monthly revenue for the last 12 months."""
    now = datetime.now(timezone.utc)
    months = []
    for i in range(11, -1, -1):
        # Calculate month offset properly using calendar arithmetic
        target_month = now.month - i
        target_year = now.year + (target_month - 1) // 12
        target_month = ((target_month - 1) % 12) + 1
        month_start = datetime(target_year, target_month, 1, tzinfo=timezone.utc)
        # Next month start
        if target_month == 12:
            month_end = datetime(target_year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            month_end = datetime(target_year, target_month + 1, 1, tzinfo=timezone.utc)
        total = (
            db.session.query(db.func.sum(Payment.amount))
            .filter(
                Payment.status == "success",
                Payment.created_at >= month_start,
                Payment.created_at < month_end,
            )
            .scalar() or 0
        )
        months.append({
            "month": month_start.strftime("%b %Y"),
            "revenue": float(total),
        })
    return jsonify({"data": months}), 200


@admin_bp.route("/analytics/users", methods=["GET"])
@require_admin
def analytics_users():
    """Weekly user registrations for the last 12 weeks."""
    now = datetime.now(timezone.utc)
    weeks = []
    for i in range(11, -1, -1):
        week_start = now - timedelta(weeks=i + 1)
        week_end = now - timedelta(weeks=i)
        count = User.query.filter(
            User.created_at >= week_start, User.created_at < week_end
        ).count()
        weeks.append({
            "week": week_start.strftime("%d %b"),
            "users": count,
        })
    return jsonify({"data": weeks}), 200


@admin_bp.route("/analytics/flags", methods=["GET"])
@require_admin
def analytics_flags():
    """Weekly flag/report counts for the last 12 weeks."""
    now = datetime.now(timezone.utc)
    weeks = []
    for i in range(11, -1, -1):
        week_start = now - timedelta(weeks=i + 1)
        week_end = now - timedelta(weeks=i)
        report_count = Report.query.filter(
            Report.created_at >= week_start, Report.created_at < week_end
        ).count()
        learner_flag_count = LearnerFlag.query.filter(
            LearnerFlag.created_at >= week_start, LearnerFlag.created_at < week_end
        ).count()
        weeks.append({
            "week": week_start.strftime("%d %b"),
            "reports": report_count,
            "learner_flags": learner_flag_count,
            "total": report_count + learner_flag_count,
        })
    return jsonify({"data": weeks}), 200


@admin_bp.route("/analytics/payouts", methods=["GET"])
@require_admin
def analytics_payouts():
    """Monthly payout totals for the last 12 months."""
    now = datetime.now(timezone.utc)
    months = []
    for i in range(11, -1, -1):
        # Calculate month offset properly using calendar arithmetic
        target_month = now.month - i
        target_year = now.year + (target_month - 1) // 12
        target_month = ((target_month - 1) % 12) + 1
        month_start = datetime(target_year, target_month, 1, tzinfo=timezone.utc)
        # Next month start
        if target_month == 12:
            month_end = datetime(target_year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            month_end = datetime(target_year, target_month + 1, 1, tzinfo=timezone.utc)
        total = (
            db.session.query(db.func.sum(Payout.amount))
            .filter(
                Payout.status == "success",
                Payout.initiated_at >= month_start,
                Payout.initiated_at < month_end,
            )
            .scalar() or 0
        )
        months.append({
            "month": month_start.strftime("%b %Y"),
            "payouts": float(total),
        })
    return jsonify({"data": months}), 200


# ---------------------------------------------------------------------------
# CSV Exports
# ---------------------------------------------------------------------------

def _csv_response(filename: str, headers: list, rows: list) -> Response:
    """Build a CSV download response."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    buf.seek(0)
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@admin_bp.route("/export/users", methods=["GET"])
@require_admin
def export_users():
    """Export all users as CSV."""
    users = (
        db.session.query(User)
        .join(Profile, Profile.user_id == User.id)
        .order_by(User.created_at.desc())
        .all()
    )
    headers = ["id", "email", "display_name", "role", "is_active", "is_verified", "created_at"]
    rows = []
    for u in users:
        p = u.profile
        rows.append([
            u.id,
            u.email,
            p.display_name if p else "",
            p.role if p else "",
            u.is_active,
            p.is_verified if p else False,
            u.created_at.isoformat() if u.created_at else "",
        ])
    return _csv_response("tradewise_users.csv", headers, rows)


@admin_bp.route("/export/trades", methods=["GET"])
@require_admin
def export_trades():
    """Export all trades as CSV."""
    trades = Trade.query.order_by(Trade.created_at.desc()).all()
    headers = [
        "id", "trader_id", "trader_name", "symbol", "direction",
        "entry_price", "stop_loss_price", "target_price", "rrr",
        "status", "outcome", "flag_count", "unlock_count", "created_at",
    ]
    rows = []
    for t in trades:
        p = Profile.query.filter_by(user_id=t.trader_id).first()
        rows.append([
            t.id, t.trader_id, p.display_name if p else "",
            t.symbol, t.direction, t.entry_price, t.stop_loss_price,
            t.target_price, t.rrr, t.status, t.outcome or "",
            t.flag_count, t.unlock_count,
            t.created_at.isoformat() if t.created_at else "",
        ])
    return _csv_response("tradewise_trades.csv", headers, rows)


@admin_bp.route("/export/payouts", methods=["GET"])
@require_admin
def export_payouts():
    """Export all payouts as CSV."""
    payouts = Payout.query.order_by(Payout.initiated_at.desc()).all()
    headers = [
        "id", "trader_id", "trader_name", "trader_email",
        "amount", "status", "bank_account_last_4",
        "initiated_at", "completed_at",
    ]
    rows = []
    for p in payouts:
        profile = Profile.query.filter_by(user_id=p.trader_id).first()
        user = User.query.get(p.trader_id)
        rows.append([
            p.id, p.trader_id,
            profile.display_name if profile else "",
            user.email if user else "",
            float(p.amount), p.status, p.bank_account_last_4 or "",
            p.initiated_at.isoformat() if p.initiated_at else "",
            p.completed_at.isoformat() if p.completed_at else "",
        ])
    return _csv_response("tradewise_payouts.csv", headers, rows)


@admin_bp.route("/export/reports", methods=["GET"])
@require_admin
def export_reports():
    """Export all reports/flags as CSV."""
    reports = Report.query.order_by(Report.created_at.desc()).all()
    headers = [
        "id", "trade_id", "trade_symbol", "reporter_id", "reporter_name",
        "reason", "status", "admin_verdict", "created_at", "resolved_at",
    ]
    rows = []
    for r in reports:
        trade = Trade.query.get(r.trade_id)
        reporter = Profile.query.filter_by(user_id=r.reporter_id).first()
        rows.append([
            r.id, r.trade_id,
            trade.symbol if trade else "",
            r.reporter_id,
            reporter.display_name if reporter else "",
            r.reason, r.status,
            r.admin_verdict or "",
            r.created_at.isoformat() if r.created_at else "",
            r.resolved_at.isoformat() if r.resolved_at else "",
        ])
    return _csv_response("tradewise_reports.csv", headers, rows)
