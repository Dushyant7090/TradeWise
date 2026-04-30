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
import re
from datetime import datetime, timezone, timedelta

from flask import Blueprint, current_app, jsonify, request, Response
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import func, case
from sqlalchemy.orm import joinedload

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
from app.models.revenue_split import RevenueSplit
from app.models.learner_flag import LearnerFlag
from app.utils.response_cache import cache_response

logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__)
ADMIN_REPLY_PATTERN = re.compile(r"^\[Admin reply:(?P<comment_id>[0-9a-fA-F-]{36})\]\s*(?P<content>[\s\S]*)$")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _paginate(query, page, per_page=20):
    """Return paginated result dict."""
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return items, total


def _storage_signed_url(bucket: str, path: str, expires_in: int = 3600) -> str:
    """Create a temporary Supabase Storage URL without requiring the SDK."""
    supabase_url = current_app.config.get("SUPABASE_URL", "").rstrip("/")
    service_key = current_app.config.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not supabase_url or not service_key or not path:
        return ""

    try:
        import requests
        response = requests.post(
            f"{supabase_url}/storage/v1/object/sign/{bucket}/{path}",
            headers={
                "Authorization": f"Bearer {service_key}",
                "apikey": service_key,
                "Content-Type": "application/json",
            },
            json={"expiresIn": expires_in},
            timeout=10,
        )
        response.raise_for_status()
        signed_path = (response.json() or {}).get("signedURL", "")
        if not signed_path:
            return ""
        if signed_path.startswith("http"):
            return signed_path
        return f"{supabase_url}/storage/v1{signed_path}"
    except Exception as exc:
        logger.warning("Failed to create signed Storage URL for %s/%s: %s", bucket, path, exc)
        return ""


def _admin_kyc_documents(pt: ProTraderProfile) -> list:
    """Return KYC documents with admin-only view URLs."""
    docs = pt.kyc_documents or {}
    if not isinstance(docs, dict):
        return []

    bucket = current_app.config.get("KYC_DOCUMENTS_BUCKET", "kyc-documents")
    normalized = []
    for doc_id, doc in docs.items():
        if not isinstance(doc, dict):
            continue

        item = {
            "id": doc.get("id") or doc_id,
            "type": doc.get("type") or "document",
            "filename": doc.get("filename") or "Uploaded document",
            "content_type": doc.get("content_type") or "application/octet-stream",
            "uploaded_at": doc.get("uploaded_at"),
            "storage_path": doc.get("storage_path"),
            "url": doc.get("url"),
            "view_url": doc.get("url"),
        }

        storage_path = doc.get("storage_path")
        if storage_path:
            signed_url = _storage_signed_url(bucket=bucket, path=storage_path, expires_in=3600)
            if signed_url:
                item["view_url"] = signed_url

        normalized.append(item)

    normalized.sort(key=lambda d: d.get("uploaded_at") or "", reverse=True)
    return normalized


def _user_summary(user: User, learner_profiles_map: dict = None) -> dict:
    """Build a summary dict for a user."""
    profile = user.profile
    pt = user.pro_trader_profile
    lp = (learner_profiles_map or {}).get(user.id)
    if lp is None and learner_profiles_map is None:
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


def _month_floor(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _add_months(dt: datetime, months: int) -> datetime:
    month_index = (dt.month - 1) + months
    year = dt.year + month_index // 12
    month = (month_index % 12) + 1
    return dt.replace(year=year, month=month, day=1)


def _parse_admin_reply(content: str) -> tuple[str | None, str]:
    match = ADMIN_REPLY_PATTERN.match(content or "")
    if not match:
        return None, content or ""
    return match.group("comment_id"), match.group("content").strip()


def _admin_reply_content(comment_id: str, content: str) -> str:
    return f"[Admin reply:{comment_id}] {content.strip()}"


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@admin_bp.route("/stats", methods=["GET"])
@require_admin
@cache_response(ttl_seconds=45, key_prefix="admin_stats")
def get_stats():
    """Return dashboard summary statistics (optimized: 3 queries instead of 9)."""
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    platform_fee_percent = float(current_app.config.get("PLATFORM_FEE_PERCENT", 10) or 10)

    # Query 1: Profile counts using conditional aggregation

    profile_stats = db.session.query(
        func.coalesce(func.sum(case((Profile.role == "pro_trader", 1), else_=0)), 0).label("total_pro_traders"),
        func.coalesce(func.sum(case((Profile.role == "public_trader", 1), else_=0)), 0).label("total_learners"),
    ).first()

    active_users = User.query.filter(
        User.created_at >= thirty_days_ago,
        User.is_active == True
    ).count()

    # Query 2: Revenue + payout aggregates (combines 4 old queries)
    money_stats = db.session.query(
        func.coalesce(
            db.session.query(
                func.sum(
                    func.coalesce(
                        RevenueSplit.admin_amount,
                        Payment.amount * platform_fee_percent / 100.0,
                    )
                )
            )
            .select_from(Payment)
            .outerjoin(RevenueSplit, RevenueSplit.payment_id == Payment.id)
            .filter(Payment.status == "success", Payment.created_at >= start_of_month)
            .correlate(None).scalar_subquery(), 0
        ).label("monthly_revenue"),
        func.coalesce(
            db.session.query(func.sum(Payout.amount))
            .filter(Payout.status.in_(["initiated", "processing"]))
            .correlate(None).scalar_subquery(), 0
        ).label("pending_payouts_amount"),
        func.coalesce(
            db.session.query(func.count(Payout.id))
            .filter(Payout.status.in_(["initiated", "processing"]))
            .correlate(None).scalar_subquery(), 0
        ).label("pending_payouts_count"),
        func.coalesce(
            db.session.query(func.sum(Payout.amount))
            .filter(Payout.status == "success", Payout.initiated_at >= start_of_month)
            .correlate(None).scalar_subquery(), 0
        ).label("paid_payouts_amount"),
    ).first()

    # Query 3: Counts for flags, KYC, reports
    flagged_trades_month = Trade.query.filter(
        Trade.flag_count > 0, Trade.created_at >= start_of_month
    ).count()
    pending_kyc = ProTraderProfile.query.filter_by(kyc_status="pending").count()
    open_reports = Report.query.filter_by(status="pending").count()

    return jsonify({
        "total_pro_traders": int(profile_stats.total_pro_traders),
        "total_learners": int(profile_stats.total_learners),
        "active_users_30d": active_users,
        "monthly_revenue": float(money_stats.monthly_revenue),
        "pending_payouts_amount": float(money_stats.pending_payouts_amount),
        "pending_payouts_count": int(money_stats.pending_payouts_count),
        "paid_payouts_month": float(money_stats.paid_payouts_amount),
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
        .options(
            joinedload(User.profile),
            joinedload(User.pro_trader_profile),
        )
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
    user_ids = [user.id for user in users]
    learner_profiles_map = {
        lp.user_id: lp
        for lp in LearnerProfile.query.filter(LearnerProfile.user_id.in_(user_ids)).all()
    } if user_ids else {}

    return jsonify({
        "users": [_user_summary(u, learner_profiles_map) for u in users],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }), 200


@admin_bp.route("/users/<user_id>", methods=["GET"])
@require_admin
def get_user(user_id):
    """Get detailed info for a single user."""
    user = (
        db.session.query(User)
        .options(
            joinedload(User.profile),
            joinedload(User.pro_trader_profile),
        )
        .filter(User.id == user_id)
        .first()
    )
    if not user:
        return jsonify({"error": "User not found"}), 404
    learner_profile = LearnerProfile.query.filter_by(user_id=user.id).first()
    return jsonify({"user": _user_summary(user, {user.id: learner_profile} if learner_profile else {})}), 200


@admin_bp.route("/users/<user_id>/suspend", methods=["POST"])
@require_admin
def suspend_user(user_id):
    """Suspend a user (reversible)."""
    requesting_admin_id = get_jwt_identity()
    if user_id == requesting_admin_id:
        return jsonify({"error": "Admins cannot suspend their own account"}), 403

    user = db.session.get(User, user_id)
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

    user = db.session.get(User, user_id)
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

    user = db.session.get(User, user_id)
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

    query = (
        db.session.query(Trade, Profile.display_name.label("trader_name"))
        .outerjoin(Profile, Profile.user_id == Trade.trader_id)
        .order_by(Trade.created_at.desc())
    )
    if status:
        query = query.filter(Trade.status == status)
    if flagged_only:
        query = query.filter(Trade.flag_count > 0)
    if search:
        query = query.filter(Trade.symbol.ilike(f"%{search}%"))

    trades, total = _paginate(query, page, per_page)

    result = []
    for t, trader_name in trades:
        d = t.to_dict()
        d["trader_name"] = trader_name
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
    row = (
        db.session.query(Trade, Profile.display_name.label("trader_name"))
        .outerjoin(Profile, Profile.user_id == Trade.trader_id)
        .filter(Trade.id == trade_id)
        .first()
    )
    if not row:
        return jsonify({"error": "Trade not found"}), 404
    trade, trader_name = row
    d = trade.to_dict()
    d["trader_name"] = trader_name
    return jsonify({"trade": d}), 200


@admin_bp.route("/trades/<trade_id>/flag", methods=["POST"])
@require_admin
def admin_flag_trade(trade_id):
    """Admin-flag a trade (increment flag_count)."""
    trade = db.session.get(Trade, trade_id)
    if not trade:
        return jsonify({"error": "Trade not found"}), 404
    trade.flag_count = (trade.flag_count or 0) + 1
    db.session.commit()
    return jsonify({"message": "Trade flagged", "flag_count": trade.flag_count}), 200


@admin_bp.route("/trades/<trade_id>/unflag", methods=["POST"])
@require_admin
def admin_unflag_trade(trade_id):
    """Clear all admin flags on a trade."""
    trade = db.session.get(Trade, trade_id)
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
@cache_response(ttl_seconds=10, key_prefix="admin_reports")
def list_reports():
    """List all reports with optional status filter."""
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)
    status = request.args.get("status", "").strip()

    query = Report.query.order_by(Report.created_at.desc())
    if status:
        query = query.filter(Report.status == status)

    reports, total = _paginate(query, page, per_page)

    trade_ids = [r.trade_id for r in reports if r.trade_id]
    reporter_ids = [r.reporter_id for r in reports if r.reporter_id]
    trade_symbol_map = {
        trade.id: trade.symbol
        for trade in Trade.query.filter(Trade.id.in_(trade_ids)).all()
    } if trade_ids else {}
    reporter_name_map = {
        profile.user_id: profile.display_name
        for profile in Profile.query.filter(Profile.user_id.in_(reporter_ids)).all()
    } if reporter_ids else {}

    result = []
    for r in reports:
        d = r.to_dict()
        d["trade_symbol"] = trade_symbol_map.get(r.trade_id)
        d["reporter_name"] = reporter_name_map.get(r.reporter_id)
        result.append(d)

    # Also include learner flags
    lf_query = LearnerFlag.query.order_by(LearnerFlag.created_at.desc())
    if status:
        lf_query = lf_query.filter(LearnerFlag.status == status)
    learner_flags = lf_query.limit(50).all()

    learner_flag_trade_ids = [lf.trade_id for lf in learner_flags if lf.trade_id]
    learner_flag_reporter_ids = [lf.learner_id for lf in learner_flags if lf.learner_id]
    learner_trade_symbol_map = {
        trade.id: trade.symbol
        for trade in Trade.query.filter(Trade.id.in_(learner_flag_trade_ids)).all()
    } if learner_flag_trade_ids else {}
    learner_reporter_name_map = {
        profile.user_id: profile.display_name
        for profile in Profile.query.filter(Profile.user_id.in_(learner_flag_reporter_ids)).all()
    } if learner_flag_reporter_ids else {}

    learner_flag_list = []
    for lf in learner_flags:
        d = lf.to_dict()
        d["type"] = "learner_flag"
        d["trade_symbol"] = learner_trade_symbol_map.get(lf.trade_id)
        d["reporter_name"] = learner_reporter_name_map.get(lf.learner_id)
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
    report = db.session.get(Report, report_id)
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
    report = db.session.get(Report, report_id)
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
@cache_response(ttl_seconds=10, key_prefix="admin_payouts")
def list_payouts():
    """List all payouts with optional status filter."""
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)
    status = request.args.get("status", "").strip()
    search = request.args.get("search", "").strip()

    query = (
        db.session.query(
            Payout,
            Profile.display_name.label("trader_name"),
            User.email.label("trader_email"),
        )
        .join(Profile, Profile.user_id == Payout.trader_id, isouter=True)
        .join(User, User.id == Payout.trader_id, isouter=True)
        .order_by(Payout.initiated_at.desc())
    )
    if status:
        query = query.filter(Payout.status == status)
    if search:
        query = query.filter(Profile.display_name.ilike(f"%{search}%"))

    payouts, total = _paginate(query, page, per_page)

    result = []
    for p, trader_name, trader_email in payouts:
        d = p.to_dict()
        d["trader_name"] = trader_name
        d["trader_email"] = trader_email
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
    payout = db.session.get(Payout, payout_id)
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
    payout = db.session.get(Payout, payout_id)
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
@cache_response(ttl_seconds=10, key_prefix="admin_comments")
def list_comments():
    """List all comments with optional trade/user filter."""
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)
    trade_id = request.args.get("trade_id", "").strip()
    user_id = request.args.get("user_id", "").strip()

    query = Comment.query.filter(~Comment.content.like("[Admin reply:%")).order_by(Comment.created_at.desc())
    if trade_id:
        query = query.filter(Comment.trade_id == trade_id)
    if user_id:
        query = query.filter(Comment.user_id == user_id)

    comments, total = _paginate(query, page, per_page)

    user_ids = [c.user_id for c in comments if c.user_id]
    trade_ids = [c.trade_id for c in comments if c.trade_id]
    comment_ids = [c.id for c in comments]
    profile_name_map = {
        p.user_id: p.display_name
        for p in Profile.query.filter(Profile.user_id.in_(user_ids)).all()
    } if user_ids else {}
    trade_symbol_map = {
        t.id: t.symbol
        for t in Trade.query.filter(Trade.id.in_(trade_ids)).all()
    } if trade_ids else {}
    admin_replies = {}
    if comment_ids and trade_ids:
        reply_rows = (
            Comment.query
            .filter(Comment.trade_id.in_(trade_ids), Comment.content.like("[Admin reply:%"))
            .order_by(Comment.created_at.desc())
            .all()
        )
        reply_user_ids = [reply.user_id for reply in reply_rows if reply.user_id]
        reply_author_map = {
            p.user_id: p.display_name
            for p in Profile.query.filter(Profile.user_id.in_(reply_user_ids)).all()
        } if reply_user_ids else {}
        for reply in reply_rows:
            parent_id, reply_text = _parse_admin_reply(reply.content)
            if parent_id not in comment_ids or parent_id in admin_replies:
                continue
            admin_replies[parent_id] = {
                "id": reply.id,
                "content": reply_text,
                "author_name": reply_author_map.get(reply.user_id) or "Admin",
                "created_at": reply.created_at.isoformat() if reply.created_at else None,
                "updated_at": reply.updated_at.isoformat() if reply.updated_at else None,
            }

    result = []
    for c in comments:
        d = c.to_dict()
        d["author_name"] = profile_name_map.get(c.user_id)
        d["trade_symbol"] = trade_symbol_map.get(c.trade_id)
        d["admin_reply"] = admin_replies.get(c.id)
        d["has_admin_reply"] = c.id in admin_replies
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
    """Post or update an admin reply to a comment thread."""
    parent = db.session.get(Comment, comment_id)
    if not parent:
        return jsonify({"error": "Comment not found"}), 404
    reply_target_id, _ = _parse_admin_reply(parent.content)
    if reply_target_id:
        return jsonify({"error": "Cannot reply to an admin reply"}), 400

    data = request.get_json() or {}
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "Reply content is required"}), 400
    if len(content) > 2000:
        return jsonify({"error": "Reply too long (max 2000 chars)"}), 400

    admin_id = get_jwt_identity()
    existing_reply = (
        Comment.query
        .filter(Comment.trade_id == parent.trade_id, Comment.content.like(f"[Admin reply:{parent.id}]%"))
        .order_by(Comment.created_at.desc())
        .first()
    )
    if existing_reply:
        existing_reply.user_id = admin_id
        existing_reply.content = _admin_reply_content(parent.id, content)
        existing_reply.updated_at = datetime.now(timezone.utc)
        reply = existing_reply
    else:
        reply = Comment(
            trade_id=parent.trade_id,
            user_id=admin_id,
            content=_admin_reply_content(parent.id, content),
        )
        db.session.add(reply)
    db.session.commit()
    reply_dict = reply.to_dict()
    reply_dict["content"] = content
    return jsonify({"message": "Reply saved", "comment": reply_dict}), 200 if existing_reply else 201


@admin_bp.route("/comments/<comment_id>", methods=["DELETE"])
@require_admin
def delete_comment(comment_id):
    """Delete a comment."""
    comment = db.session.get(Comment, comment_id)
    if not comment:
        return jsonify({"error": "Comment not found"}), 404
    Comment.query.filter(Comment.content.like(f"[Admin reply:{comment.id}]%")).delete(synchronize_session=False)
    db.session.delete(comment)
    db.session.commit()
    return jsonify({"message": "Comment deleted"}), 200


# ---------------------------------------------------------------------------
# KYC Management
# ---------------------------------------------------------------------------

@admin_bp.route("/kyc", methods=["GET"])
@require_admin
@cache_response(ttl_seconds=10, key_prefix="admin_kyc")
def list_kyc():
    """List KYC submissions, filterable by status."""
    status = request.args.get("status", "pending").strip()
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)

    query = (
        db.session.query(
            ProTraderProfile,
            User.email.label("email"),
            Profile.display_name.label("display_name"),
        )
        .outerjoin(User, User.id == ProTraderProfile.user_id)
        .outerjoin(Profile, Profile.user_id == ProTraderProfile.user_id)
    )
    if status:
        query = query.filter(ProTraderProfile.kyc_status == status)
    query = query.order_by(ProTraderProfile.created_at.desc())

    profiles, total = _paginate(query, page, per_page)

    result = []
    for pt, email, display_name in profiles:
        d = pt.to_dict()
        documents = _admin_kyc_documents(pt)
        d["email"] = email
        d["display_name"] = display_name
        d["documents"] = documents
        d["document_count"] = len(documents)
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
    """Approve KYC for a pro trader — transitions to VERIFIED state."""
    pt = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt:
        return jsonify({"error": "Pro trader profile not found"}), 404
    pt.kyc_status = "verified"
    pt.is_review_pending = False
    # Ensure onboarding is at least step 3 (admin verification implies full onboarding)
    if pt.onboarding_step < 3:
        pt.onboarding_step = 3
    profile = Profile.query.filter_by(user_id=user_id).first()
    if profile:
        profile.is_verified = True
    db.session.commit()
    return jsonify({"message": "KYC approved — trader is now VERIFIED", "kyc_status": "verified"}), 200


@admin_bp.route("/kyc/<user_id>/reject", methods=["POST"])
@require_admin
def reject_kyc(user_id):
    """Reject KYC for a pro trader — returns to EXPLORER state."""
    pt = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt:
        return jsonify({"error": "Pro trader profile not found"}), 404
    data = request.get_json() or {}
    pt.kyc_status = "rejected"
    pt.is_review_pending = False
    # Keep is_verified = false (already the case, but be explicit)
    profile = Profile.query.filter_by(user_id=user_id).first()
    if profile:
        profile.is_verified = False
    db.session.commit()
    return jsonify({"message": "KYC rejected", "kyc_status": "rejected"}), 200


# ---------------------------------------------------------------------------
# Analytics chart data
# ---------------------------------------------------------------------------

@admin_bp.route("/analytics/revenue", methods=["GET"])
@require_admin
@cache_response(ttl_seconds=15, key_prefix="admin_analytics_revenue")
def analytics_revenue():
    """Monthly platform revenue for the last 12 months."""
    now = datetime.now(timezone.utc)
    month_zero = _month_floor(now)
    first_month = _add_months(month_zero, -11)
    end_month = _add_months(month_zero, 1)
    platform_fee_percent = float(current_app.config.get("PLATFORM_FEE_PERCENT", 10) or 10)

    rows = (
        db.session.query(
            func.extract("year", Payment.created_at).label("year"),
            func.extract("month", Payment.created_at).label("month"),
            func.coalesce(
                func.sum(
                    func.coalesce(
                        RevenueSplit.admin_amount,
                        Payment.amount * platform_fee_percent / 100.0,
                    )
                ),
                0,
            ).label("revenue"),
        )
        .select_from(Payment)
        .outerjoin(RevenueSplit, RevenueSplit.payment_id == Payment.id)
        .filter(
            Payment.status == "success",
            Payment.created_at >= first_month,
            Payment.created_at < end_month,
        )
        .group_by(func.extract("year", Payment.created_at), func.extract("month", Payment.created_at))
        .all()
    )
    revenue_map = {
        (int(row.year), int(row.month)): float(row.revenue or 0)
        for row in rows
    }

    months = []
    for i in range(11, -1, -1):
        month_start = _add_months(month_zero, -i)
        total = revenue_map.get((month_start.year, month_start.month), 0.0)
        months.append({
            "month": month_start.strftime("%b %Y"),
            "revenue": float(total),
        })
    return jsonify({"data": months}), 200


@admin_bp.route("/analytics/users", methods=["GET"])
@require_admin
@cache_response(ttl_seconds=15, key_prefix="admin_analytics_users")
def analytics_users():
    """Weekly user registrations for the last 12 weeks."""
    now = datetime.now(timezone.utc)
    week_zero = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    first_week = week_zero - timedelta(weeks=11)
    week_end = week_zero + timedelta(weeks=1)

    rows = (
        db.session.query(
            func.date_trunc("week", User.created_at).label("week_start"),
            func.count(User.id).label("users"),
        )
        .filter(User.created_at >= first_week, User.created_at < week_end)
        .group_by(func.date_trunc("week", User.created_at))
        .all()
    )
    count_map = {}
    for row in rows:
        bucket = row.week_start
        if bucket and getattr(bucket, "tzinfo", None) is None:
            bucket = bucket.replace(tzinfo=timezone.utc)
        if bucket:
            count_map[bucket.date()] = int(row.users or 0)

    weeks = []
    for i in range(11, -1, -1):
        week_start = week_zero - timedelta(weeks=i)
        count = count_map.get(week_start.date(), 0)
        weeks.append({
            "week": week_start.strftime("%d %b"),
            "users": count,
        })
    return jsonify({"data": weeks}), 200


@admin_bp.route("/analytics/flags", methods=["GET"])
@require_admin
@cache_response(ttl_seconds=15, key_prefix="admin_analytics_flags")
def analytics_flags():
    """Weekly flag/report counts for the last 12 weeks."""
    now = datetime.now(timezone.utc)
    week_zero = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    first_week = week_zero - timedelta(weeks=11)
    week_end = week_zero + timedelta(weeks=1)

    report_rows = (
        db.session.query(
            func.date_trunc("week", Report.created_at).label("week_start"),
            func.count(Report.id).label("total"),
        )
        .filter(Report.created_at >= first_week, Report.created_at < week_end)
        .group_by(func.date_trunc("week", Report.created_at))
        .all()
    )
    learner_rows = (
        db.session.query(
            func.date_trunc("week", LearnerFlag.created_at).label("week_start"),
            func.count(LearnerFlag.id).label("total"),
        )
        .filter(LearnerFlag.created_at >= first_week, LearnerFlag.created_at < week_end)
        .group_by(func.date_trunc("week", LearnerFlag.created_at))
        .all()
    )

    report_map = {}
    for row in report_rows:
        bucket = row.week_start
        if bucket and getattr(bucket, "tzinfo", None) is None:
            bucket = bucket.replace(tzinfo=timezone.utc)
        if bucket:
            report_map[bucket.date()] = int(row.total or 0)

    learner_map = {}
    for row in learner_rows:
        bucket = row.week_start
        if bucket and getattr(bucket, "tzinfo", None) is None:
            bucket = bucket.replace(tzinfo=timezone.utc)
        if bucket:
            learner_map[bucket.date()] = int(row.total or 0)

    weeks = []
    for i in range(11, -1, -1):
        week_start = week_zero - timedelta(weeks=i)
        report_count = report_map.get(week_start.date(), 0)
        learner_flag_count = learner_map.get(week_start.date(), 0)
        weeks.append({
            "week": week_start.strftime("%d %b"),
            "reports": report_count,
            "learner_flags": learner_flag_count,
            "total": report_count + learner_flag_count,
        })
    return jsonify({"data": weeks}), 200


@admin_bp.route("/analytics/payouts", methods=["GET"])
@require_admin
@cache_response(ttl_seconds=15, key_prefix="admin_analytics_payouts")
def analytics_payouts():
    """Monthly payout totals for the last 12 months."""
    now = datetime.now(timezone.utc)
    month_zero = _month_floor(now)
    first_month = _add_months(month_zero, -11)
    end_month = _add_months(month_zero, 1)

    rows = (
        db.session.query(
            func.extract("year", Payout.initiated_at).label("year"),
            func.extract("month", Payout.initiated_at).label("month"),
            func.coalesce(func.sum(Payout.amount), 0).label("payouts"),
        )
        .filter(
            Payout.status == "success",
            Payout.initiated_at >= first_month,
            Payout.initiated_at < end_month,
        )
        .group_by(func.extract("year", Payout.initiated_at), func.extract("month", Payout.initiated_at))
        .all()
    )
    payout_map = {
        (int(row.year), int(row.month)): float(row.payouts or 0)
        for row in rows
    }

    months = []
    for i in range(11, -1, -1):
        month_start = _add_months(month_zero, -i)
        total = payout_map.get((month_start.year, month_start.month), 0.0)
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
        user = db.session.get(User, p.trader_id)
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
        trade = db.session.get(Trade, r.trade_id)
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
