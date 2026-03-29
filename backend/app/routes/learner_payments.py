"""
Learner Payments routes (Cashfree integration)
- POST /api/payments/create-order
- GET  /api/payments/verify/{order_id}
- POST /api/payments/webhook
- GET  /api/payments/history
"""
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import get_jwt_identity

from app import db
from app.middleware import require_auth
from app.models.payment import Payment
from app.models.subscription import Subscription
from app.models.pro_trader_profile import ProTraderProfile
from app.models.profile import Profile
from app.models.learner_profile import LearnerProfile
from app.models.learner_notification import LearnerNotification
from app.services.cashfree import cashfree_service

logger = logging.getLogger(__name__)
learner_payments_bp = Blueprint("learner_payments", __name__)


@learner_payments_bp.route("/create-order", methods=["POST"])
@require_auth
def create_payment_order():
    """Create a Cashfree payment order for a subscription."""
    user_id = get_jwt_identity()

    data = request.get_json() or {}
    trader_id = data.get("trader_id", "")
    if not trader_id:
        return jsonify({"error": "trader_id is required"}), 400

    pt_profile = ProTraderProfile.query.filter_by(user_id=trader_id).first()
    if not pt_profile:
        return jsonify({"error": "Pro trader not found"}), 404

    amount = float(pt_profile.monthly_subscription_price or 0)
    if amount <= 0:
        return jsonify({"error": "This trader has not set a subscription price"}), 400

    # Get learner info
    profile = Profile.query.filter_by(user_id=user_id).first()
    from app.models.user import User
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    cf_order_id = f"TW-{uuid.uuid4().hex[:12].upper()}"

    # Create pending payment record
    payment = Payment(
        subscriber_id=user_id,
        trader_id=trader_id,
        amount=amount,
        cashfree_order_id=cf_order_id,
        status="pending",
    )
    db.session.add(payment)
    db.session.commit()

    try:
        frontend_url = current_app.config.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
        return_url = f"{frontend_url}/frontend/learner/pages/payment-callback.html?order_id={cf_order_id}"
        cf_response = cashfree_service.create_order(
            order_id=cf_order_id,
            amount=amount,
            customer_id=user_id,
            customer_email=user.email,
            customer_phone=data.get("phone", "9999999999"),
            return_url=return_url,
        )
        return jsonify({
            "order_id": cf_order_id,
            "payment_session_id": cf_response.get("payment_session_id"),
            "amount": amount,
            "currency": "INR",
            "trader_id": trader_id,
            "payment_id": payment.id,
        }), 201
    except Exception as e:
        logger.error(f"Cashfree create_order failed: {e}")
        payment.status = "failed"
        db.session.commit()
        return jsonify({"error": "Failed to create payment order"}), 500


@learner_payments_bp.route("/verify/<order_id>", methods=["GET"])
@require_auth
def verify_payment(order_id):
    """Verify payment completion by order ID."""
    user_id = get_jwt_identity()

    payment = Payment.query.filter_by(cashfree_order_id=order_id, subscriber_id=user_id).first()
    if not payment:
        return jsonify({"error": "Payment not found"}), 404

    try:
        cf_order = cashfree_service.get_order(order_id)
        cf_status = cf_order.get("order_status", "")

        if cf_status == "PAID" and payment.status != "success":
            payment.status = "success"
            payment.completed_at = datetime.now(timezone.utc)
            db.session.commit()

        return jsonify({
            "payment_id": payment.id,
            "order_id": order_id,
            "status": payment.status,
            "cashfree_status": cf_status,
            "amount": float(payment.amount),
        }), 200
    except Exception as e:
        logger.error(f"Cashfree verify payment error: {e}")
        return jsonify({"error": "Failed to verify payment"}), 500


@learner_payments_bp.route("/webhook", methods=["POST"])
def payment_webhook():
    """Handle Cashfree payment webhook for learner subscriptions."""
    raw_body = request.get_data()
    signature = request.headers.get("x-webhook-signature", "")
    timestamp = request.headers.get("x-webhook-timestamp", "")

    # Verify signature
    secret = current_app.config.get("CASHFREE_WEBHOOK_SECRET", "")
    if secret:
        message = timestamp + raw_body.decode("utf-8")
        computed = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(computed, signature):
            return jsonify({"error": "Invalid signature"}), 401

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON"}), 400

    payment_data = data.get("data", {}).get("payment", {})
    order_data = data.get("data", {}).get("order", {})
    cf_order_id = order_data.get("order_id", "")
    cf_payment_id = str(payment_data.get("cf_payment_id", ""))
    payment_status = payment_data.get("payment_status", "")

    if not cf_order_id:
        return jsonify({"error": "Missing order_id"}), 400

    payment = Payment.query.filter_by(cashfree_order_id=cf_order_id).first()
    if not payment:
        return jsonify({"status": "ignored"}), 200

    now = datetime.now(timezone.utc)

    if payment_status == "SUCCESS":
        payment.status = "success"
        payment.cashfree_payment_id = cf_payment_id
        payment.payment_method = payment_data.get("payment_method", {}).get("type", "")
        payment.completed_at = now
        db.session.flush()

        # Create subscription
        existing_sub = Subscription.query.filter_by(payment_id=payment.id).first()
        if not existing_sub:
            subscription = Subscription(
                subscriber_id=payment.subscriber_id,
                trader_id=payment.trader_id,
                started_at=now,
                ends_at=now + timedelta(days=30),
                status="active",
                payment_id=payment.id,
            )
            db.session.add(subscription)

            # Update learner total_spent
            learner = LearnerProfile.query.filter_by(user_id=payment.subscriber_id).first()
            if learner:
                learner.total_spent = float(learner.total_spent or 0) + float(payment.amount)

            # Update trader subscriber count
            pt_profile = ProTraderProfile.query.filter_by(user_id=payment.trader_id).first()
            if pt_profile:
                pt_profile.total_subscribers = (pt_profile.total_subscribers or 0) + 1
                pt_profile.total_earnings = float(pt_profile.total_earnings or 0) + float(payment.amount) * 0.9
                pt_profile.available_balance = float(pt_profile.available_balance or 0) + float(payment.amount) * 0.9

            # Send notification to learner
            trader_profile = Profile.query.filter_by(user_id=payment.trader_id).first()
            trader_name = trader_profile.display_name if trader_profile else "the trader"
            notif = LearnerNotification(
                learner_id=payment.subscriber_id,
                type="subscriber_alert",
                title="Subscription Activated",
                message=f"Your subscription to {trader_name} has been activated.",
                related_trader_id=payment.trader_id,
            )
            db.session.add(notif)

        db.session.commit()
        logger.info(f"Payment {payment.id} succeeded (order: {cf_order_id})")

    elif payment_status in ("FAILED", "USER_DROPPED", "CANCELLED"):
        payment.status = "failed"
        db.session.flush()

        # Notify learner
        notif = LearnerNotification(
            learner_id=payment.subscriber_id,
            type="subscriber_alert",
            title="Payment Failed",
            message="Your payment could not be processed. Please try again.",
        )
        db.session.add(notif)
        db.session.commit()
        logger.info(f"Payment {payment.id} failed (order: {cf_order_id})")

    return jsonify({"status": "ok"}), 200


@learner_payments_bp.route("/history", methods=["GET"])
@require_auth
def payment_history():
    """Get learner's payment history."""
    user_id = get_jwt_identity()
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)

    query = Payment.query.filter_by(subscriber_id=user_id).order_by(
        Payment.created_at.desc()
    )
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    payments = []
    for p in paginated.items:
        entry = p.to_dict()
        trader_profile = Profile.query.filter_by(user_id=p.trader_id).first()
        entry["trader_name"] = trader_profile.display_name if trader_profile else "Unknown"
        payments.append(entry)

    return jsonify({
        "payments": payments,
        "total": paginated.total,
        "page": page,
        "per_page": per_page,
        "pages": paginated.pages,
    }), 200
