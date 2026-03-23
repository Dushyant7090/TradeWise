"""
Earnings & Payouts routes
- GET  /api/pro-trader/earnings
- GET  /api/pro-trader/subscription-price
- PUT  /api/pro-trader/subscription-price
- GET  /api/pro-trader/balance
- GET  /api/pro-trader/payouts
- POST /api/pro-trader/payouts/initiate
- GET  /api/pro-trader/payouts/{id}/status
"""
import logging
import uuid
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import func

from app import db
from app.middleware import require_pro_trader
from app.models.pro_trader_profile import ProTraderProfile
from app.models.payout import Payout
from app.models.revenue_split import RevenueSplit
from app.models.payment import Payment
from app.utils.encryption import decrypt_value

logger = logging.getLogger(__name__)
earnings_bp = Blueprint("earnings", __name__)


@earnings_bp.route("/earnings", methods=["GET"])
@require_pro_trader
def get_earnings():
    """Get total and monthly earnings."""
    user_id = get_jwt_identity()
    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt_profile:
        return jsonify({"error": "Profile not found"}), 404

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    monthly = db.session.query(func.sum(RevenueSplit.pro_trader_amount)).join(
        Payment, RevenueSplit.payment_id == Payment.id
    ).filter(
        RevenueSplit.trader_id == user_id,
        Payment.completed_at >= month_start,
        Payment.status == "success",
    ).scalar()

    return jsonify({
        "total_earnings": float(pt_profile.total_earnings or 0),
        "available_balance": float(pt_profile.available_balance or 0),
        "monthly_earnings": float(monthly) if monthly else 0.0,
    }), 200


@earnings_bp.route("/subscription-price", methods=["GET"])
@require_pro_trader
def get_subscription_price():
    """Get current subscription price."""
    user_id = get_jwt_identity()
    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt_profile:
        return jsonify({"error": "Profile not found"}), 404
    return jsonify({
        "monthly_subscription_price": float(pt_profile.monthly_subscription_price or 0)
    }), 200


@earnings_bp.route("/subscription-price", methods=["PUT"])
@require_pro_trader
def set_subscription_price():
    """Set subscription price."""
    user_id = get_jwt_identity()
    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt_profile:
        return jsonify({"error": "Profile not found"}), 404

    data = request.get_json() or {}
    try:
        price = float(data.get("monthly_subscription_price", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid price"}), 400

    if price < 0:
        return jsonify({"error": "Price cannot be negative"}), 400

    pt_profile.monthly_subscription_price = price
    db.session.commit()

    return jsonify({
        "message": "Subscription price updated",
        "monthly_subscription_price": price,
    }), 200


@earnings_bp.route("/balance", methods=["GET"])
@require_pro_trader
def get_balance():
    """Get available balance for withdrawal."""
    user_id = get_jwt_identity()
    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt_profile:
        return jsonify({"error": "Profile not found"}), 404
    return jsonify({
        "available_balance": float(pt_profile.available_balance or 0),
        "total_earnings": float(pt_profile.total_earnings or 0),
    }), 200


@earnings_bp.route("/payouts", methods=["GET"])
@require_pro_trader
def get_payouts():
    """Get payout history."""
    user_id = get_jwt_identity()
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)

    query = Payout.query.filter_by(trader_id=user_id).order_by(Payout.initiated_at.desc())
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "payouts": [p.to_dict() for p in paginated.items],
        "total": paginated.total,
        "page": page,
        "per_page": per_page,
        "pages": paginated.pages,
    }), 200


@earnings_bp.route("/payouts/initiate", methods=["POST"])
@require_pro_trader
def initiate_payout():
    """Initiate a withdrawal via Cashfree Payouts."""
    user_id = get_jwt_identity()
    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt_profile:
        return jsonify({"error": "Profile not found"}), 404

    # KYC check
    if pt_profile.kyc_status != "verified":
        return jsonify({"error": "KYC verification required before payout"}), 403

    # Bank details check
    if not pt_profile.bank_account_number_encrypted or not pt_profile.ifsc_code:
        return jsonify({"error": "Bank details are required before payout"}), 400

    data = request.get_json() or {}
    try:
        amount = float(data.get("amount", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid amount"}), 400

    min_amount = current_app.config.get("MIN_WITHDRAWAL_AMOUNT", 500)
    if amount < min_amount:
        return jsonify({"error": f"Minimum withdrawal amount is ₹{min_amount}"}), 400

    if amount > float(pt_profile.available_balance or 0):
        return jsonify({"error": "Insufficient balance"}), 400

    # Decrypt bank account
    account_number = decrypt_value(pt_profile.bank_account_number_encrypted)
    if not account_number:
        return jsonify({"error": "Invalid bank account details"}), 400

    transfer_id = f"TW_PAYOUT_{uuid.uuid4().hex[:16].upper()}"

    # Create payout record
    payout = Payout(
        trader_id=user_id,
        amount=amount,
        status="initiated",
        bank_account_last_4=pt_profile.bank_account_last_4,
        cashfree_transfer_id=transfer_id,
    )
    db.session.add(payout)

    # Deduct from available balance
    pt_profile.available_balance = float(pt_profile.available_balance or 0) - amount
    db.session.commit()

    # Initiate Cashfree payout
    try:
        from app.services.cashfree import cashfree_payout_service
        result = cashfree_payout_service.initiate_transfer(
            transfer_id=transfer_id,
            amount=amount,
            account_number=account_number,
            ifsc_code=pt_profile.ifsc_code,
            account_holder_name=pt_profile.account_holder_name or "Trader",
        )
        payout.cashfree_payout_id = result.get("data", {}).get("referenceId", "")
        payout.status = "processing"
        db.session.commit()
    except Exception as e:
        logger.error(f"Cashfree payout initiation error: {e}")
        # Refund balance on failure
        payout.status = "failed"
        payout.failure_reason = str(e)
        pt_profile.available_balance = float(pt_profile.available_balance or 0) + amount
        db.session.commit()

        from app.services.notification_service import notify_payout_result
        notify_payout_result(user_id, amount, success=False, reason=str(e))
        return jsonify({"error": "Failed to initiate payout. Balance refunded."}), 500

    from app.services.notification_service import notify_payout_result
    notify_payout_result(user_id, amount, success=True, transfer_id=transfer_id)

    return jsonify({
        "message": "Payout initiated successfully",
        "payout": payout.to_dict(),
    }), 201


@earnings_bp.route("/payouts/<payout_id>/status", methods=["GET"])
@require_pro_trader
def get_payout_status(payout_id):
    """Check payout status."""
    user_id = get_jwt_identity()
    payout = Payout.query.filter_by(id=payout_id, trader_id=user_id).first()
    if not payout:
        return jsonify({"error": "Payout not found"}), 404

    # If still processing, check with Cashfree
    if payout.status == "processing" and payout.cashfree_transfer_id:
        try:
            from app.services.cashfree import cashfree_payout_service
            result = cashfree_payout_service.get_transfer_status(payout.cashfree_transfer_id)
            cf_status = result.get("data", {}).get("status", "")
            if cf_status in ("SUCCESS", "COMPLETED"):
                payout.status = "success"
                payout.completed_at = datetime.now(timezone.utc)
            elif cf_status in ("FAILED", "REJECTED"):
                payout.status = "failed"
                payout.failure_reason = result.get("data", {}).get("reason", "Transfer failed")
                # Refund
                pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
                if pt_profile:
                    pt_profile.available_balance = float(pt_profile.available_balance or 0) + float(payout.amount)
            db.session.commit()
        except Exception as e:
            logger.error(f"Error checking payout status: {e}")

    return jsonify({"payout": payout.to_dict()}), 200
