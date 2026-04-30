"""
Learner Feed & Discovery routes
- GET /api/learner/feed
- GET /api/learner/feed/filter
- GET /api/learner/trades/{id}
"""
import logging
import requests
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse
from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import get_jwt_identity
from sqlalchemy.orm import joinedload

from app import db
from app.middleware import require_auth
from app.models.trade import Trade
from app.models.subscription import Subscription
from app.models.learner_trade_unlock import LearnerUnlockedTrade
from app.models.pro_trader_profile import ProTraderProfile
from app.models.profile import Profile
from app.models.user import User
from app.services.supabase_storage import supabase_storage
from app.utils.response_cache import cache_response

logger = logging.getLogger(__name__)
learner_feed_bp = Blueprint("learner_feed", __name__)


_trader_stats_cache = {}


def _compute_live_trader_public_stats(trader_id: str) -> dict:
    """Compute live public stats for a pro trader (single aggregate query)."""
    # Simple per-request cache keyed by trader_id (cleared on new request)
    from flask import g
    cache = getattr(g, '_trader_stats_cache', None)
    if cache is None:
        cache = {}
        g._trader_stats_cache = cache
    if trader_id in cache:
        return cache[trader_id]

    from sqlalchemy import case, func
    now = datetime.now(timezone.utc)

    # Single aggregate query replacing 4 separate COUNT queries
    row = db.session.query(
        func.count(Trade.id).label("total_trades"),
        func.coalesce(
            func.sum(case((Trade.status == "target_hit", 1), else_=0)), 0
        ).label("winning_trades"),
        func.coalesce(
            func.sum(case((Trade.status.in_(["target_hit", "sl_hit"]), 1), else_=0)), 0
        ).label("closed_trades"),
    ).filter(Trade.trader_id == trader_id).first()

    total_trades = int(row.total_trades or 0)
    winning_trades = int(row.winning_trades or 0)
    closed_trades = int(row.closed_trades or 0)
    win_rate = round((winning_trades / closed_trades) * 100, 2) if closed_trades > 0 else 0.0

    subscribers_count = Subscription.query.filter(
        Subscription.trader_id == trader_id,
        Subscription.status == "active",
        Subscription.ends_at > now,
    ).count()

    result = {
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "closed_trades": closed_trades,
        "win_rate": win_rate,
        "subscribers_count": subscribers_count,
    }
    cache[trader_id] = result
    return result


def _normalize_chart_url(url: str) -> str:
    """Normalize stored chart URLs by removing accidental trailing query delimiters."""
    if not url:
        return ""
    clean = str(url).strip()
    # Some records may accidentally end with '?', which can create brittle fetch behavior.
    while clean.endswith("?"):
        clean = clean[:-1]
    return clean


def _extract_supabase_storage_target(url: str):
    """Extract bucket/path from Supabase storage public or signed URLs."""
    if not url:
        return None, None

    parsed = urlparse(url)
    path = parsed.path or ""

    marker_public = "/storage/v1/object/public/"
    marker_sign = "/storage/v1/object/sign/"

    tail = ""
    if marker_public in path:
        tail = path.split(marker_public, 1)[1]
    elif marker_sign in path:
        tail = path.split(marker_sign, 1)[1]

    if not tail or "/" not in tail:
        return None, None

    bucket, object_path = tail.split("/", 1)
    return bucket, unquote(object_path)


def _build_fetch_candidates(chart_url: str):
    """Build chart URL candidates, including signed URL fallback for Supabase storage."""
    candidates = []
    if chart_url:
        candidates.append(chart_url)

    bucket, object_path = _extract_supabase_storage_target(chart_url)
    if not bucket or not object_path:
        return candidates

    try:
        signed = supabase_storage.get_signed_url(bucket, object_path, expires_in=3600)
        if signed:
            if signed.startswith("http://") or signed.startswith("https://"):
                signed_url = signed
            else:
                from flask import current_app
                base_url = current_app.config.get("SUPABASE_URL", "").rstrip("/")
                if not base_url:
                    signed_url = ""
                elif signed.startswith("/"):
                    signed_url = f"{base_url}{signed}"
                else:
                    signed_url = f"{base_url}/{signed}"
            if signed_url and signed_url not in candidates:
                candidates.append(signed_url)
    except Exception as exc:
        logger.warning("Could not generate signed URL fallback for %s/%s: %s", bucket, object_path, exc)

    return candidates


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


def _ensure_subscription_history_entry(learner_id: str, trade_id: str) -> LearnerUnlockedTrade:
    """Record subscribed trade views in learner history without charging credits."""
    now = datetime.now(timezone.utc)
    unlock = LearnerUnlockedTrade.query.filter_by(
        learner_id=learner_id,
        trade_id=trade_id,
    ).first()
    if unlock:
        if not unlock.viewed_at:
            unlock.viewed_at = now
        return unlock

    unlock = LearnerUnlockedTrade(
        learner_id=learner_id,
        trade_id=trade_id,
        unlocked_at=now,
        viewed_at=now,
        via_credit=False,
    )
    db.session.add(unlock)
    return unlock


def _serialize_trade_public(
    trade: Trade,
    trader_profile: Profile,
    is_unlocked: bool,
    has_sub: bool,
    pt_profile: ProTraderProfile = None,
) -> dict:
    """Serialize a trade. Hide sensitive fields if not unlocked and no subscription."""
    pt_profile = pt_profile or ProTraderProfile.query.filter_by(user_id=trade.trader_id).first()
    trader_name = trader_profile.display_name if trader_profile else "Unknown"
    trader_avatar_url = trader_profile.avatar_url if trader_profile else None
    trader_profile_picture_url = pt_profile.profile_picture_url if pt_profile else None
    trader_accuracy = float(pt_profile.accuracy_score or 0) if pt_profile else 0.0

    base = {
        "id": trade.id,
        "trader_id": trade.trader_id,
        "trader_name": trader_name,
        "trader_avatar_url": trader_avatar_url,
        "trader_profile_picture_url": trader_profile_picture_url,
        "monthly_subscription_price": float(pt_profile.monthly_subscription_price or 499) if pt_profile else 499.0,
        "symbol": trade.symbol,
        "rrr": float(trade.rrr),
        "status": trade.status,
        "view_count": trade.view_count,
        "unlock_count": trade.unlock_count,
        "created_at": trade.created_at.isoformat() if trade.created_at else None,
        "is_unlocked": is_unlocked,
        "has_subscription": has_sub,
        "pro_trader": {
            "id": trade.trader_id,
            "display_name": trader_name,
            "avatar_url": trader_avatar_url,
            "profile_picture_url": trader_profile_picture_url,
            "accuracy_score": trader_accuracy,
            "subscription_price": float(pt_profile.monthly_subscription_price or 499) if pt_profile else 499.0,
        },
    }
    base["accuracy_score"] = trader_accuracy

    if is_unlocked or has_sub:
        chart_url = _normalize_chart_url(trade.chart_image_url)
        base.update({
            "direction": trade.direction,
            "entry_price": float(trade.entry_price),
            "stop_loss_price": float(trade.stop_loss_price),
            "target_price": float(trade.target_price),
            "technical_rationale": trade.technical_rationale,
            "chart_image_url": chart_url,
            "chart_proxy_url": f"/api/learner/trades/{trade.id}/chart-image" if chart_url else None,
            "outcome": trade.outcome,
            "closed_at": trade.closed_at.isoformat() if trade.closed_at else None,
        })
    return base


def _resolve_trade_access(user_id: str, trade_items):
    """Bulk resolve unlocked trade IDs and active subscription trader IDs for the page."""
    trade_ids = [trade.id for trade in trade_items]
    trader_ids = {trade.trader_id for trade in trade_items}

    if not trade_ids:
        return set(), set()

    now = datetime.now(timezone.utc)
    unlocked_ids = {
        row.trade_id
        for row in LearnerUnlockedTrade.query.filter(
            LearnerUnlockedTrade.learner_id == user_id,
            LearnerUnlockedTrade.trade_id.in_(trade_ids),
        ).all()
    }

    subscribed_trader_ids = set()
    if trader_ids:
        subscribed_trader_ids = {
            row.trader_id
            for row in Subscription.query.filter(
                Subscription.subscriber_id == user_id,
                Subscription.trader_id.in_(trader_ids),
                Subscription.status == "active",
                Subscription.ends_at > now,
            ).all()
        }

    return unlocked_ids, subscribed_trader_ids


@learner_feed_bp.route("/feed", methods=["GET"])
@require_auth
@cache_response(ttl_seconds=12, key_prefix="learner_feed")
def get_feed():
    """Get paginated active trades from all pro traders."""
    user_id = get_jwt_identity()
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)
    sort_by = request.args.get("sort_by", "created_at")

    query = Trade.query.options(
        joinedload(Trade.trader).joinedload(User.profile),
        joinedload(Trade.trader).joinedload(User.pro_trader_profile),
    ).filter(Trade.status == "active")

    if sort_by == "accuracy_score":
        query = query.join(ProTraderProfile, Trade.trader_id == ProTraderProfile.user_id).order_by(
            ProTraderProfile.accuracy_score.desc()
        )
    elif sort_by == "view_count":
        query = query.order_by(Trade.view_count.desc())
    else:
        query = query.order_by(Trade.created_at.desc())

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    unlocked_ids, subscribed_trader_ids = _resolve_trade_access(user_id, paginated.items)

    trades = []
    for trade in paginated.items:
        trader = trade.trader
        trader_profile = trader.profile if trader else None
        pt_profile = trader.pro_trader_profile if trader else None
        is_unlocked = trade.id in unlocked_ids
        has_sub = trade.trader_id in subscribed_trader_ids
        trades.append(_serialize_trade_public(trade, trader_profile, is_unlocked, has_sub, pt_profile))

    return jsonify({
        "trades": trades,
        "total": paginated.total,
        "page": page,
        "per_page": per_page,
        "pages": paginated.pages,
    }), 200


@learner_feed_bp.route("/feed/filter", methods=["GET"])
@require_auth
@cache_response(ttl_seconds=12, key_prefix="learner_feed_filter")
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

    query = Trade.query.options(
        joinedload(Trade.trader).joinedload(User.profile),
        joinedload(Trade.trader).joinedload(User.pro_trader_profile),
    ).filter(Trade.status == "active")

    if market:
        query = query.filter(Trade.symbol.ilike(f"%{market}%"))

    if pro_trader_id:
        query = query.filter(Trade.trader_id == pro_trader_id)

    joined_accuracy = False
    if trader_name or (min_accuracy is not None) or (max_accuracy is not None):
        query = query.join(ProTraderProfile, Trade.trader_id == ProTraderProfile.user_id)
        joined_accuracy = True
        if min_accuracy is not None:
            query = query.filter(ProTraderProfile.accuracy_score >= min_accuracy)
        if max_accuracy is not None:
            query = query.filter(ProTraderProfile.accuracy_score <= max_accuracy)

        if trader_name:
            query = query.join(Profile, Trade.trader_id == Profile.user_id)
            query = query.filter(Profile.display_name.ilike(f"%{trader_name}%"))

    if sort_by == "accuracy_score":
        if not joined_accuracy:
            query = query.join(ProTraderProfile, Trade.trader_id == ProTraderProfile.user_id)
        query = query.order_by(ProTraderProfile.accuracy_score.desc())
    elif sort_by == "view_count":
        query = query.order_by(Trade.view_count.desc())
    else:
        query = query.order_by(Trade.created_at.desc())

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    unlocked_ids, subscribed_trader_ids = _resolve_trade_access(user_id, paginated.items)

    trades = []
    for trade in paginated.items:
        trader = trade.trader
        trader_profile = trader.profile if trader else None
        pt_profile = trader.pro_trader_profile if trader else None
        is_unlocked = trade.id in unlocked_ids
        has_sub = trade.trader_id in subscribed_trader_ids
        trades.append(_serialize_trade_public(trade, trader_profile, is_unlocked, has_sub, pt_profile))

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
    trade = db.session.get(Trade, trade_id)
    if not trade:
        return jsonify({"error": "Trade not found"}), 404

    trader_profile = Profile.query.filter_by(user_id=trade.trader_id).first()
    is_unlocked = _is_trade_unlocked(user_id, trade.id)
    has_sub = _has_active_subscription(user_id, trade.trader_id)

    # Increment view count
    trade.view_count = (trade.view_count or 0) + 1
    db.session.commit()

    # Mark as viewed if unlocked, and record subscription access in history.
    if has_sub and not is_unlocked:
        _ensure_subscription_history_entry(user_id, trade.id)
        is_unlocked = True
        db.session.commit()
    elif is_unlocked:
        unlock = LearnerUnlockedTrade.query.filter_by(
            learner_id=user_id, trade_id=trade_id
        ).first()
        if unlock and not unlock.viewed_at:
            unlock.viewed_at = datetime.now(timezone.utc)
            db.session.commit()

    pt_profile = ProTraderProfile.query.filter_by(user_id=trade.trader_id).first()
    payload = _serialize_trade_public(trade, trader_profile, is_unlocked, has_sub, pt_profile)

    # Ensure detail view always has complete, live pro-trader stats.
    stats = _compute_live_trader_public_stats(trade.trader_id)
    payload["pro_trader"] = {
        **(payload.get("pro_trader") or {}),
        "total_trades": stats["total_trades"],
        "winning_trades": stats["winning_trades"],
        "closed_trades": stats["closed_trades"],
        "win_rate": stats["win_rate"],
        "subscribers_count": stats["subscribers_count"],
        "total_subscribers": stats["subscribers_count"],
    }

    return jsonify(payload), 200


@learner_feed_bp.route("/trades/<trade_id>/chart-image", methods=["GET"])
@require_auth
def get_trade_chart_image(trade_id):
    """Proxy trade chart image through backend to avoid browser-side storage connectivity issues."""
    user_id = get_jwt_identity()
    trade = db.session.get(Trade, trade_id)
    if not trade:
        return jsonify({"error": "Trade not found"}), 404

    is_unlocked = _is_trade_unlocked(user_id, trade.id)
    has_sub = _has_active_subscription(user_id, trade.trader_id)
    if not (is_unlocked or has_sub):
        return jsonify({"error": "Trade is locked"}), 403

    chart_url = _normalize_chart_url(trade.chart_image_url)
    if not chart_url:
        return jsonify({"error": "Chart image not available"}), 404

    candidates = _build_fetch_candidates(chart_url)
    last_error = None

    for candidate in candidates:
        try:
            upstream = requests.get(candidate, timeout=20)
        except requests.RequestException as exc:
            last_error = exc
            logger.warning("Chart proxy fetch error for trade %s using %s: %s", trade_id, candidate, exc)
            continue

        if upstream.status_code >= 400:
            logger.warning("Chart proxy got %s for trade %s using %s", upstream.status_code, trade_id, candidate)
            continue

        content_type = upstream.headers.get("Content-Type", "image/png")
        resp = Response(upstream.content, status=200, mimetype=content_type)
        resp.headers["Cache-Control"] = "public, max-age=300"
        return resp

    if last_error is not None:
        return jsonify({"error": "Unable to fetch chart image right now"}), 504
    return jsonify({"error": "Chart image not found"}), 404
