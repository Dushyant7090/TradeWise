"""
Tests for pro-trader subscriber endpoints.
"""
import json
from datetime import datetime, timedelta, timezone

from app.models.payment import Payment
from app.models.subscription import Subscription


def _register_learner(client, email="learner@example.com", password="TestPass1", display_name="Test Learner"):
    resp = client.post(
        "/api/auth/register",
        data=json.dumps({
            "email": email,
            "password": password,
            "role": "public_trader",
            "display_name": display_name,
        }),
        content_type="application/json",
    )
    return resp.get_json()


def _register_pro_trader(client, email="trader@example.com", password="TestPass1"):
    resp = client.post(
        "/api/auth/register",
        data=json.dumps({
            "email": email,
            "password": password,
            "role": "pro_trader",
            "display_name": "Pro Trader",
        }),
        content_type="application/json",
    )
    return resp.get_json()


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


class TestProTraderSubscribers:
    def test_get_subscribers_includes_payment_amount(self, client, db):
        trader_data = _register_pro_trader(client, email="paid_sub_trader@example.com")
        trader_id = trader_data["user"]["id"]
        trader_token = trader_data["access_token"]

        learner_data = _register_learner(
            client,
            email="joe_paid_subscriber@example.com",
            display_name="JOE",
        )
        learner_id = learner_data["user"]["id"]

        now = datetime.now(timezone.utc)
        payment = Payment(
            subscriber_id=learner_id,
            trader_id=trader_id,
            amount=1000,
            currency="INR",
            status="success",
            completed_at=now,
        )
        db.session.add(payment)
        db.session.flush()

        subscription = Subscription(
            subscriber_id=learner_id,
            trader_id=trader_id,
            started_at=now,
            ends_at=now + timedelta(days=30),
            status="active",
            payment_id=payment.id,
        )
        db.session.add(subscription)
        db.session.commit()

        resp = client.get("/api/pro-trader/subscribers", headers=_auth_header(trader_token))

        assert resp.status_code == 200
        subscribers = resp.get_json()["subscribers"]
        assert len(subscribers) == 1
        assert subscribers[0]["subscriber_name"] == "JOE"
        assert subscribers[0]["amount_paid"] == 1000.0
        assert subscribers[0]["amount"] == 1000.0
        assert subscribers[0]["currency"] == "INR"
        assert subscribers[0]["payment_status"] == "success"
