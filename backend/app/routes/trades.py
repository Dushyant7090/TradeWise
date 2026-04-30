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
from urllib.parse import unquote, urlparse

import requests
from flask import Blueprint, Response, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity
from sqlalchemy.exc import IntegrityError

from app import db
from app.middleware import require_pro_trader, require_verified_trader
from app.models.trade import Trade
from app.services.supabase_storage import supabase_storage
from app.utils.accuracy import recalculate_accuracy, calculate_rrr
from app.utils.validators import validate_rationale

logger = logging.getLogger(__name__)
trades_bp = Blueprint("trades", __name__)


def _normalize_chart_url(url: str) -> str:
    """Normalize stored chart URLs by removing accidental trailing query delimiters."""
    if not url:
        return ""
    clean = str(url).strip()
    while clean.endswith("?"):
        clean = clean[:-1]
    return clean


def _extract_supabase_storage_target(url: str):
    """Extract bucket/path from Supabase storage public or signed URLs."""
    if not url:
        return None, None

    path = urlparse(url).path or ""
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
            if signed.startswith(("http://", "https://")):
                signed_url = signed
            else:
                base_url = current_app.config.get("SUPABASE_URL", "").rstrip("/")
                signed_url = f"{base_url}{signed}" if signed.startswith("/") else f"{base_url}/{signed}"
            if signed_url and signed_url not in candidates:
                candidates.append(signed_url)
    except Exception as exc:
        logger.warning("Could not generate signed chart URL for %s/%s: %s", bucket, object_path, exc)

    return candidates


def _trade_payload(trade: Trade):
    payload = trade.to_dict()
    chart_url = _normalize_chart_url(payload.get("chart_image_url"))
    payload["chart_image_url"] = chart_url
    payload["chart_proxy_url"] = f"/api/pro-trader/trades/{trade.id}/chart-image" if chart_url else None
    return payload


def _parse_price(value):
    """Parse numeric price values, accepting comma-formatted strings like '4,650.25'."""
    if value is None:
        raise ValueError("missing")
    if isinstance(value, str):
        normalized = value.replace(",", "").strip()
        if normalized == "":
            raise ValueError("missing")
        return float(normalized)
    return float(value)


def _upload_chart_file_for_user(user_id: str):
    file = request.files.get("file") or request.files.get("chart_image") or request.files.get("image")
    if file is None:
        return None, (jsonify({"error": "No chart image file provided"}), 400)

    if not file.filename:
        return None, (jsonify({"error": "Empty file"}), 400)

    allowed_types = {"image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"}
    content_type = (file.content_type or "").lower().strip()
    if content_type not in allowed_types:
        return None, (jsonify({"error": "Invalid file type. Use JPEG, PNG, GIF, or WebP"}), 400)

    file_data = file.read()
    if len(file_data) > 5 * 1024 * 1024:
        return None, (jsonify({"error": "File too large. Max 5MB"}), 400)

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "png"
    file_id = str(uuid.uuid4())
    path = f"trade-charts/{user_id}/{file_id}.{ext}"
    bucket = current_app.config.get("TRADE_CHARTS_BUCKET", "chart-images")

    try:
        url = supabase_storage.upload_file(
            bucket=bucket,
            path=path,
            file_data=file_data,
            content_type=content_type,
        )
    except Exception as exc:
        logger.error("Trade chart upload failed for user %s: %s", user_id, exc)
        message = str(exc)
        if "Bucket not found" in message:
            return jsonify({
                "error": f"Storage bucket '{bucket}' not found. Configure TRADE_CHARTS_BUCKET to an existing Supabase bucket (for example: chart-images)."
            }), 500
        if isinstance(exc, ModuleNotFoundError):
            return None, (jsonify({
                "error": f"Storage upload dependency is missing: {exc.name}. Reinstall backend requirements and try again."
            }), 500)
        return None, (jsonify({"error": "Failed to upload chart image"}), 500)

    return {
        "message": "Chart image uploaded successfully",
        "url": url,
        "image_url": url,
        "storage_path": path,
        "bucket": bucket,
    }, None


@trades_bp.route("/uploads/chart", methods=["POST"])
@require_pro_trader
def upload_trade_chart():
    """Upload a trade chart image and return a persistent URL."""
    user_id = get_jwt_identity()
    payload, error = _upload_chart_file_for_user(user_id)
    if error:
        return error
    return jsonify(payload), 201


@trades_bp.route("/trades/<trade_id>/chart-image", methods=["PUT"])
@require_pro_trader
def update_trade_chart_image(trade_id):
    """Upload or replace the chart image for an existing trade."""
    user_id = get_jwt_identity()
    trade = Trade.query.filter_by(id=trade_id, trader_id=user_id).first()
    if not trade:
        return jsonify({"error": "Trade not found"}), 404

    payload, error = _upload_chart_file_for_user(user_id)
    if error:
        return error

    trade.chart_image_url = payload["url"]
    db.session.commit()
    payload["trade"] = _trade_payload(trade)
    return jsonify(payload), 200


@trades_bp.route("/trades", methods=["POST"])
@require_verified_trader
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
        entry = _parse_price(data.get("entry_price"))
        sl = _parse_price(data.get("stop_loss_price"))
        target = _parse_price(data.get("target_price"))
    except (TypeError, ValueError):
        return jsonify({"error": "Prices must be numeric"}), 400

    if entry <= 0 or sl <= 0 or target <= 0:
        return jsonify({"error": "All prices must be positive"}), 400

    # Price sanity checks
    if direction == "buy":
        if sl > entry:
            return jsonify({"error": "For BUY: stop_loss must be equal to or below entry_price"}), 400
        if target <= entry:
            return jsonify({"error": "For BUY: target_price must be above entry_price"}), 400
    else:
        if sl < entry:
            return jsonify({"error": "For SELL: stop_loss must be equal to or above entry_price"}), 400
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
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        logger.warning("Trade create failed integrity check: %s", exc)
        return jsonify({"error": "Trade validation failed. Please verify entry, stop-loss, and target values."}), 400

    return jsonify({"message": "Trade created successfully", "trade": _trade_payload(trade)}), 201


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
        "trades": [_trade_payload(t) for t in paginated.items],
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
    return jsonify(_trade_payload(trade)), 200


@trades_bp.route("/trades/<trade_id>/chart-image", methods=["GET"])
@require_pro_trader
def get_trade_chart_image(trade_id):
    """Proxy a trader's chart image through the backend."""
    user_id = get_jwt_identity()
    trade = Trade.query.filter_by(id=trade_id, trader_id=user_id).first()
    if not trade:
        return jsonify({"error": "Trade not found"}), 404

    chart_url = _normalize_chart_url(trade.chart_image_url)
    if not chart_url:
        return jsonify({"error": "Chart image not available"}), 404

    last_error = None
    for candidate in _build_fetch_candidates(chart_url):
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

    return jsonify({"message": f"Trade closed as {status}", "trade": _trade_payload(trade)}), 200


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
