"""
Learner Subscriptions routes
- GET    /api/learner/subscriptions
- GET    /api/learner/subscriptions/{trader_id}
- POST   /api/learner/subscriptions/{trader_id}/subscribe
- DELETE /api/learner/subscriptions/{trader_id}
- PUT    /api/learner/subscriptions/{subscription_id}/auto-renew
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from app import db
from app.middleware import require_auth
from app.models.subscription import Subscription
from app.models.payment import Payment
from app.models.pro_trader_profile import ProTraderProfile
from app.models.profile import Profile

logger = logging.getLogger(__name__)
learner_subscriptions_bp = Blueprint("learner_subscriptions", __name__)


def _utc(dt):
    """Return dt as a UTC-aware datetime; treats naive datetimes as UTC."""
    if dt is None:
        return dt
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@learner_subscriptions_bp.route("/subscriptions", methods=["GET"])
@require_auth
def get_subscriptions():
    """Get all subscriptions for the authenticated learner."""
    user_id = get_jwt_identity()
    now = datetime.now(timezone.utc)

    subscriptions = Subscription.query.filter_by(subscriber_id=user_id).order_by(
        Subscription.created_at.desc()
    ).all()

    result = []
    for sub in subscriptions:
        # Auto-expire if past ends_at
        if sub.status == "active" and _utc(sub.ends_at) < now:
            if sub.auto_renew:
                sub.ends_at = sub.ends_at + timedelta(days=30)
            else:
                sub.status = "expired"

        trader_profile = Profile.query.filter_by(user_id=sub.trader_id).first()
        pt_profile = ProTraderProfile.query.filter_by(user_id=sub.trader_id).first()

        entry = sub.to_dict()
        entry["trader_name"] = trader_profile.display_name if trader_profile else "Unknown"
        entry["trader_accuracy"] = float(pt_profile.accuracy_score or 0) if pt_profile else 0.0
        entry["trader_picture_url"] = pt_profile.profile_picture_url if pt_profile else None
        result.append(entry)

    db.session.commit()

    return jsonify({"subscriptions": result}), 200


@learner_subscriptions_bp.route("/subscriptions/<trader_id>", methods=["GET"])
@require_auth
def get_subscription_status(trader_id):
    """Get subscription status for a specific trader."""
    user_id = get_jwt_identity()
    now = datetime.now(timezone.utc)

    sub = Subscription.query.filter_by(
        subscriber_id=user_id,
        trader_id=trader_id,
    ).order_by(Subscription.created_at.desc()).first()

    if not sub:
        return jsonify({"subscribed": False, "subscription": None}), 200

    is_active = sub.status == "active" and _utc(sub.ends_at) > now
    return jsonify({
        "subscribed": is_active,
        "subscription": sub.to_dict(),
    }), 200


@learner_subscriptions_bp.route("/subscriptions/<trader_id>/subscribe", methods=["POST"])
@require_auth
def subscribe_to_trader(trader_id):
    """Create subscription after payment. Expects payment_id in body."""
    user_id = get_jwt_identity()
    now = datetime.now(timezone.utc)

    # Check if already has active subscription
    existing = Subscription.query.filter(
        Subscription.subscriber_id == user_id,
        Subscription.trader_id == trader_id,
        Subscription.status == "active",
        Subscription.ends_at > now,
    ).first()
    if existing:
        return jsonify({"error": "Already subscribed to this trader"}), 409

    pt_profile = ProTraderProfile.query.filter_by(user_id=trader_id).first()
    if not pt_profile:
        return jsonify({"error": "Pro trader not found"}), 404

    data = request.get_json() or {}
    payment_id = data.get("payment_id")
    auto_renew = data.get("auto_renew", False)

    # Validate payment if provided
    if payment_id:
        payment = Payment.query.filter_by(id=payment_id, status="success").first()
        if not payment:
            return jsonify({"error": "Valid completed payment not found"}), 400

    subscription = Subscription(
        subscriber_id=user_id,
        trader_id=trader_id,
        started_at=now,
        ends_at=now + timedelta(days=30),
        status="active",
        auto_renew=auto_renew,
        payment_id=payment_id,
    )
    db.session.add(subscription)

    # Update trader's subscriber count
    pt_profile.total_subscribers = (pt_profile.total_subscribers or 0) + 1

    db.session.commit()

    return jsonify({
        "message": "Subscription created successfully",
        "subscription": subscription.to_dict(),
    }), 201


@learner_subscriptions_bp.route("/subscriptions/<trader_id>", methods=["DELETE"])
@require_auth
def unsubscribe(trader_id):
    """Cancel active subscription to a pro trader."""
    user_id = get_jwt_identity()
    now = datetime.now(timezone.utc)

    sub = Subscription.query.filter(
        Subscription.subscriber_id == user_id,
        Subscription.trader_id == trader_id,
        Subscription.status == "active",
    ).first()

    if not sub:
        return jsonify({"error": "No active subscription found for this trader"}), 404

    sub.status = "cancelled"

    # Decrement trader subscriber count
    pt_profile = ProTraderProfile.query.filter_by(user_id=trader_id).first()
    if pt_profile and pt_profile.total_subscribers > 0:
        pt_profile.total_subscribers -= 1

    db.session.commit()
    return jsonify({"message": "Unsubscribed successfully"}), 200


@learner_subscriptions_bp.route("/subscriptions/<subscription_id>/auto-renew", methods=["PUT"])
@require_auth
def toggle_auto_renew(subscription_id):
    """Toggle auto-renewal for a subscription."""
    user_id = get_jwt_identity()

    sub = Subscription.query.filter_by(id=subscription_id, subscriber_id=user_id).first()
    if not sub:
        return jsonify({"error": "Subscription not found"}), 404

    data = request.get_json() or {}
    auto_renew = data.get("auto_renew")
    if auto_renew is None:
        return jsonify({"error": "auto_renew field is required"}), 400

    sub.auto_renew = bool(auto_renew)
    db.session.commit()

    return jsonify({
        "message": f"Auto-renew {'enabled' if sub.auto_renew else 'disabled'}",
        "subscription": sub.to_dict(),
    }), 200
