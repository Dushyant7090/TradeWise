"""
Webhook routes - Cashfree payment and payout webhooks
- POST /api/webhooks/cashfree/payment   - Payment success/failure
- POST /api/webhooks/cashfree/payout    - Payout status update
"""
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request, current_app

from app import db
from app.models.payment import Payment
from app.models.subscription import Subscription
from app.models.revenue_split import RevenueSplit
from app.models.payout import Payout
from app.models.pro_trader_profile import ProTraderProfile

logger = logging.getLogger(__name__)
webhooks_bp = Blueprint("webhooks", __name__)


def _verify_cashfree_signature(raw_body: bytes, signature: str, timestamp: str) -> bool:
    """Verify Cashfree webhook HMAC signature."""
    secret = current_app.config.get("CASHFREE_WEBHOOK_SECRET", "")
    if not secret:
        return True  # Skip in test mode without secret
    message = timestamp + raw_body.decode("utf-8")
    computed = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)


@webhooks_bp.route("/cashfree/payment", methods=["POST"])
def cashfree_payment_webhook():
    """
    Handle Cashfree payment webhook.
    On payment success: create revenue split and update subscriptions.
    """
    raw_body = request.get_data()
    signature = request.headers.get("x-webhook-signature", "")
    timestamp = request.headers.get("x-webhook-timestamp", "")

    if not _verify_cashfree_signature(raw_body, signature, timestamp):
        return jsonify({"error": "Invalid signature"}), 401

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON"}), 400

    event_type = data.get("type", "")
    payment_data = data.get("data", {}).get("payment", {})
    order_data = data.get("data", {}).get("order", {})

    cf_order_id = order_data.get("order_id", "")
    cf_payment_id = payment_data.get("cf_payment_id", "")
    payment_status = payment_data.get("payment_status", "")

    if not cf_order_id:
        return jsonify({"error": "Missing order_id"}), 400

    payment = Payment.query.filter_by(cashfree_order_id=cf_order_id).first()
    if not payment:
        logger.warning(f"Payment not found for order_id: {cf_order_id}")
        return jsonify({"status": "ignored"}), 200

    if payment_status == "SUCCESS":
        payment.status = "success"
        payment.cashfree_payment_id = str(cf_payment_id)
        payment.payment_method = payment_data.get("payment_method", {}).get("type", "")
        payment.completed_at = datetime.now(timezone.utc)
        db.session.flush()

        # Revenue split
        _process_revenue_split(payment)

        # Activate subscription
        subscription = Subscription.query.filter_by(payment_id=payment.id).first()
        if subscription:
            subscription.status = "active"

        db.session.commit()
        logger.info(f"Payment {payment.id} completed successfully (order: {cf_order_id})")

    elif payment_status in ("FAILED", "USER_DROPPED", "CANCELLED"):
        payment.status = "failed"
        db.session.commit()
        logger.info(f"Payment {payment.id} failed (order: {cf_order_id})")

    return jsonify({"status": "ok"}), 200


def _process_revenue_split(payment: Payment):
    """
    Split payment revenue: 90% to trader, 10% to admin.
    Update pro trader available_balance.
    """
    from flask import current_app

    pro_pct = current_app.config.get("PRO_TRADER_REVENUE_PERCENT", 90)
    admin_pct = current_app.config.get("PLATFORM_FEE_PERCENT", 10)

    amount = float(payment.amount)
    pro_amount = round(amount * pro_pct / 100, 2)
    admin_amount = round(amount * admin_pct / 100, 2)

    # Check if split already exists
    existing = RevenueSplit.query.filter_by(payment_id=payment.id).first()
    if existing:
        return

    split = RevenueSplit(
        payment_id=payment.id,
        trader_id=payment.trader_id,
        pro_trader_amount=pro_amount,
        admin_amount=admin_amount,
        split_percentage_pro=pro_pct,
        split_percentage_admin=admin_pct,
        pro_trader_wallet_credited=True,
        admin_wallet_credited=True,
    )
    db.session.add(split)

    # Update trader's wallet
    pt_profile = ProTraderProfile.query.filter_by(user_id=payment.trader_id).first()
    if pt_profile:
        pt_profile.available_balance = float(pt_profile.available_balance or 0) + pro_amount
        pt_profile.total_earnings = float(pt_profile.total_earnings or 0) + pro_amount

    logger.info(
        f"Revenue split: payment={payment.id}, trader={pro_amount}, admin={admin_amount}"
    )


@webhooks_bp.route("/cashfree/payout", methods=["POST"])
def cashfree_payout_webhook():
    """
    Handle Cashfree payout webhook.
    Updates payout status: processing -> success/failed.
    """
    raw_body = request.get_data()
    signature = request.headers.get("x-webhook-signature", "")
    timestamp = request.headers.get("x-webhook-timestamp", "")

    if not _verify_cashfree_signature(raw_body, signature, timestamp):
        return jsonify({"error": "Invalid signature"}), 401

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON"}), 400

    transfer_id = data.get("transferId", "")
    event = data.get("event", "")

    if not transfer_id:
        return jsonify({"error": "Missing transferId"}), 400

    payout = Payout.query.filter_by(cashfree_transfer_id=transfer_id).first()
    if not payout:
        logger.warning(f"Payout not found for transferId: {transfer_id}")
        return jsonify({"status": "ignored"}), 200

    if event in ("TRANSFER_SUCCESS", "PAYOUT_SUCCESS"):
        payout.status = "success"
        payout.cashfree_payout_id = data.get("referenceId", "")
        payout.completed_at = datetime.now(timezone.utc)
        db.session.commit()

        from app.services.notification_service import notify_payout_result
        notify_payout_result(payout.trader_id, float(payout.amount), success=True, transfer_id=transfer_id)

    elif event in ("TRANSFER_FAILED", "PAYOUT_FAILED"):
        reason = data.get("reason", "Transfer failed")
        payout.status = "failed"
        payout.failure_reason = reason
        db.session.flush()

        # Refund balance
        pt_profile = ProTraderProfile.query.filter_by(user_id=payout.trader_id).first()
        if pt_profile:
            pt_profile.available_balance = float(pt_profile.available_balance or 0) + float(payout.amount)
        db.session.commit()

        from app.services.notification_service import notify_payout_result
        notify_payout_result(payout.trader_id, float(payout.amount), success=False, reason=reason)

    logger.info(f"Payout webhook: transfer_id={transfer_id}, event={event}")
    return jsonify({"status": "ok"}), 200
