"""
Tests for Learner Dashboard backend endpoints
"""
import json
import pytest


def _register_learner(client, email="learner@example.com", password="TestPass1"):
    resp = client.post(
        "/api/auth/register",
        data=json.dumps({"email": email, "password": password, "role": "public_trader", "display_name": "Test Learner"}),
        content_type="application/json",
    )
    return resp.get_json()


def _register_pro_trader(client, email="trader@example.com", password="TestPass1"):
    resp = client.post(
        "/api/auth/register",
        data=json.dumps({"email": email, "password": password, "role": "pro_trader", "display_name": "Pro Trader"}),
        content_type="application/json",
    )
    return resp.get_json()


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


class TestLearnerRegistration:
    def test_register_public_trader_creates_learner_profile(self, client, db):
        data = _register_learner(client)
        assert "access_token" in data
        token = data["access_token"]

        resp = client.get("/api/learner/profile", headers=_auth_header(token))
        assert resp.status_code == 200
        profile = resp.get_json()
        assert profile["credits"] == 7
        assert profile["experience_level"] == "beginner"

    def test_register_public_trader_creates_notification_prefs(self, client, db):
        data = _register_learner(client, email="notif_pref@example.com")
        token = data["access_token"]

        resp = client.get("/api/learner/notification-preferences", headers=_auth_header(token))
        assert resp.status_code == 200
        prefs = resp.get_json()
        assert prefs["email_new_trade"] is True
        assert prefs["sms_enabled"] is False


class TestLearnerProfile:
    def test_get_profile(self, client, db):
        data = _register_learner(client, email="profile_get@example.com")
        token = data["access_token"]

        resp = client.get("/api/learner/profile", headers=_auth_header(token))
        assert resp.status_code == 200
        profile = resp.get_json()
        assert profile["credits"] == 7

    def test_update_profile(self, client, db):
        data = _register_learner(client, email="profile_update@example.com")
        token = data["access_token"]

        resp = client.put(
            "/api/learner/profile",
            data=json.dumps({
                "interests": ["stocks", "crypto"],
                "experience_level": "intermediate",
                "learning_goal": "Learn to trade profitably",
            }),
            content_type="application/json",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        profile = resp.get_json()["profile"]
        assert profile["interests"] == ["stocks", "crypto"]
        assert profile["experience_level"] == "intermediate"
        assert profile["learning_goal"] == "Learn to trade profitably"

    def test_update_profile_invalid_experience_level(self, client, db):
        data = _register_learner(client, email="profile_invalid@example.com")
        token = data["access_token"]

        resp = client.put(
            "/api/learner/profile",
            data=json.dumps({"experience_level": "expert"}),
            content_type="application/json",
            headers=_auth_header(token),
        )
        assert resp.status_code == 400

    def test_profile_requires_auth(self, client, db):
        resp = client.get("/api/learner/profile")
        assert resp.status_code == 401


class TestLearnerDashboard:
    def test_dashboard(self, client, db):
        data = _register_learner(client, email="dashboard@example.com")
        token = data["access_token"]

        resp = client.get("/api/learner/dashboard", headers=_auth_header(token))
        assert resp.status_code == 200
        dashboard = resp.get_json()
        assert "credits" in dashboard
        assert dashboard["credits"] == 7
        assert "recent_trades" in dashboard
        assert "featured_traders" in dashboard
        assert "active_subscriptions" in dashboard


class TestLearnerCredits:
    def test_get_credits(self, client, db):
        data = _register_learner(client, email="credits@example.com")
        token = data["access_token"]

        resp = client.get("/api/learner/credits", headers=_auth_header(token))
        assert resp.status_code == 200
        credits = resp.get_json()
        assert credits["credits"] == 7

    def test_credits_log_empty(self, client, db):
        data = _register_learner(client, email="credits_log@example.com")
        token = data["access_token"]

        resp = client.get("/api/learner/credits-log", headers=_auth_header(token))
        assert resp.status_code == 200
        assert resp.get_json()["credits_log"] == []

    def test_history_empty(self, client, db):
        data = _register_learner(client, email="history@example.com")
        token = data["access_token"]

        resp = client.get("/api/learner/history", headers=_auth_header(token))
        assert resp.status_code == 200
        assert resp.get_json()["history"] == []


class TestTradeUnlock:
    def _create_trade(self, client, db, trader_token):
        resp = client.post(
            "/api/pro-trader/trades",
            data=json.dumps({
                "symbol": "NIFTY",
                "direction": "buy",
                "entry_price": 100.0,
                "stop_loss_price": 95.0,
                "target_price": 115.0,
                "technical_rationale": "The price is consolidating near a key support zone showing clear signs of institutional accumulation with RSI indicating oversold conditions and a bullish divergence forming on the daily chart suggesting a high probability reversal to the upside targeting the next resistance level with a very favorable risk to reward setup for entry",
            }),
            content_type="application/json",
            headers=_auth_header(trader_token),
        )
        return resp.get_json()["trade"]["id"]

    def test_unlock_trade_with_credits(self, client, db):
        # Create pro trader and trade
        trader_data = _register_pro_trader(client, email="unlock_trader@example.com")
        trader_token = trader_data["access_token"]
        trade_id = self._create_trade(client, db, trader_token)

        # Create learner
        learner_data = _register_learner(client, email="unlock_learner@example.com")
        learner_token = learner_data["access_token"]

        # Unlock the trade
        resp = client.post(
            f"/api/learner/trades/{trade_id}/unlock",
            headers=_auth_header(learner_token),
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["via_credit"] is True
        assert result["credits_remaining"] == 6

        # Verify credits were deducted
        credits_resp = client.get("/api/learner/credits", headers=_auth_header(learner_token))
        assert credits_resp.get_json()["credits"] == 6

    def test_unlock_same_trade_twice(self, client, db):
        trader_data = _register_pro_trader(client, email="dup_trader@example.com")
        trader_token = trader_data["access_token"]
        trade_id = self._create_trade(client, db, trader_token)

        learner_data = _register_learner(client, email="dup_learner@example.com")
        learner_token = learner_data["access_token"]

        client.post(f"/api/learner/trades/{trade_id}/unlock", headers=_auth_header(learner_token))
        # Second unlock should return 200 with "already unlocked"
        resp = client.post(f"/api/learner/trades/{trade_id}/unlock", headers=_auth_header(learner_token))
        assert resp.status_code == 200
        assert "already unlocked" in resp.get_json()["message"].lower()

        # Credits should still be 6 (only deducted once)
        credits_resp = client.get("/api/learner/credits", headers=_auth_header(learner_token))
        assert credits_resp.get_json()["credits"] == 6

    def test_unlock_nonexistent_trade(self, client, db):
        learner_data = _register_learner(client, email="noexist_learner@example.com")
        learner_token = learner_data["access_token"]

        resp = client.post(
            "/api/learner/trades/nonexistent-trade-id/unlock",
            headers=_auth_header(learner_token),
        )
        assert resp.status_code == 404

    def test_trade_detail_limited_when_not_unlocked(self, client, db):
        trader_data = _register_pro_trader(client, email="detail_trader@example.com")
        trader_token = trader_data["access_token"]
        trade_id = self._create_trade(client, db, trader_token)

        learner_data = _register_learner(client, email="detail_learner@example.com")
        learner_token = learner_data["access_token"]

        resp = client.get(f"/api/learner/trades/{trade_id}", headers=_auth_header(learner_token))
        assert resp.status_code == 200
        trade_data = resp.get_json()
        assert "symbol" in trade_data
        assert "rrr" in trade_data
        # Sensitive fields should NOT be present when not unlocked
        assert "direction" not in trade_data
        assert "entry_price" not in trade_data

    def test_trade_detail_full_when_unlocked(self, client, db):
        trader_data = _register_pro_trader(client, email="full_trader@example.com")
        trader_token = trader_data["access_token"]
        trade_id = self._create_trade(client, db, trader_token)

        learner_data = _register_learner(client, email="full_learner@example.com")
        learner_token = learner_data["access_token"]

        # Unlock the trade
        client.post(f"/api/learner/trades/{trade_id}/unlock", headers=_auth_header(learner_token))

        resp = client.get(f"/api/learner/trades/{trade_id}", headers=_auth_header(learner_token))
        assert resp.status_code == 200
        trade_data = resp.get_json()
        assert "direction" in trade_data
        assert "entry_price" in trade_data
        assert "stop_loss_price" in trade_data
        assert "target_price" in trade_data


class TestLearnerFeed:
    def test_get_feed(self, client, db):
        learner_data = _register_learner(client, email="feed@example.com")
        token = learner_data["access_token"]

        resp = client.get("/api/learner/feed", headers=_auth_header(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert "trades" in data
        assert "total" in data

    def test_filter_feed(self, client, db):
        learner_data = _register_learner(client, email="filter_feed@example.com")
        token = learner_data["access_token"]

        resp = client.get(
            "/api/learner/feed/filter?market=NIFTY&sort_by=created_at",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        assert "trades" in resp.get_json()


class TestLearnerSubscriptions:
    def test_get_subscriptions_empty(self, client, db):
        learner_data = _register_learner(client, email="subs@example.com")
        token = learner_data["access_token"]

        resp = client.get("/api/learner/subscriptions", headers=_auth_header(token))
        assert resp.status_code == 200
        assert resp.get_json()["subscriptions"] == []

    def test_subscribe_and_unsubscribe(self, client, db):
        trader_data = _register_pro_trader(client, email="sub_trader@example.com")
        trader_user_id = trader_data["user"]["id"]

        learner_data = _register_learner(client, email="sub_learner@example.com")
        learner_token = learner_data["access_token"]

        # Subscribe
        resp = client.post(
            f"/api/learner/subscriptions/{trader_user_id}/subscribe",
            data=json.dumps({}),
            content_type="application/json",
            headers=_auth_header(learner_token),
        )
        assert resp.status_code == 201
        sub = resp.get_json()["subscription"]
        assert sub["status"] == "active"

        # Check subscription status
        status_resp = client.get(
            f"/api/learner/subscriptions/{trader_user_id}",
            headers=_auth_header(learner_token),
        )
        assert status_resp.get_json()["subscribed"] is True

        # Unsubscribe
        unsub_resp = client.delete(
            f"/api/learner/subscriptions/{trader_user_id}",
            headers=_auth_header(learner_token),
        )
        assert unsub_resp.status_code == 200

    def test_duplicate_subscription(self, client, db):
        trader_data = _register_pro_trader(client, email="dup_sub_trader@example.com")
        trader_user_id = trader_data["user"]["id"]

        learner_data = _register_learner(client, email="dup_sub_learner@example.com")
        learner_token = learner_data["access_token"]

        client.post(
            f"/api/learner/subscriptions/{trader_user_id}/subscribe",
            data=json.dumps({}),
            content_type="application/json",
            headers=_auth_header(learner_token),
        )
        resp = client.post(
            f"/api/learner/subscriptions/{trader_user_id}/subscribe",
            data=json.dumps({}),
            content_type="application/json",
            headers=_auth_header(learner_token),
        )
        assert resp.status_code == 409

    def test_toggle_auto_renew(self, client, db):
        trader_data = _register_pro_trader(client, email="renew_trader@example.com")
        trader_user_id = trader_data["user"]["id"]

        learner_data = _register_learner(client, email="renew_learner@example.com")
        learner_token = learner_data["access_token"]

        sub_resp = client.post(
            f"/api/learner/subscriptions/{trader_user_id}/subscribe",
            data=json.dumps({}),
            content_type="application/json",
            headers=_auth_header(learner_token),
        )
        sub_id = sub_resp.get_json()["subscription"]["id"]

        resp = client.put(
            f"/api/learner/subscriptions/{sub_id}/auto-renew",
            data=json.dumps({"auto_renew": True}),
            content_type="application/json",
            headers=_auth_header(learner_token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["subscription"]["auto_renew"] is True


class TestLearnerFlags:
    def _create_trade_for_test(self, client, trader_token):
        resp = client.post(
            "/api/pro-trader/trades",
            data=json.dumps({
                "symbol": "BTC",
                "direction": "buy",
                "entry_price": 50000.0,
                "stop_loss_price": 48000.0,
                "target_price": 55000.0,
                "technical_rationale": "The price is consolidating near a key support zone showing clear signs of institutional accumulation with RSI indicating oversold conditions and a bullish divergence forming on the daily chart suggesting a high probability reversal to the upside targeting the next resistance level with a very favorable risk to reward setup for entry",
            }),
            content_type="application/json",
            headers=_auth_header(trader_token),
        )
        return resp.get_json()["trade"]["id"]

    def test_flag_trade(self, client, db):
        trader_data = _register_pro_trader(client, email="flag_trader@example.com")
        trader_token = trader_data["access_token"]
        trade_id = self._create_trade_for_test(client, trader_token)

        learner_data = _register_learner(client, email="flag_learner@example.com")
        learner_token = learner_data["access_token"]

        resp = client.post(
            f"/api/learner/trades/{trade_id}/flag",
            data=json.dumps({"reason": "This trade looks fraudulent"}),
            content_type="application/json",
            headers=_auth_header(learner_token),
        )
        assert resp.status_code == 201
        flag = resp.get_json()["flag"]
        assert flag["status"] == "pending"

    def test_flag_same_trade_twice(self, client, db):
        trader_data = _register_pro_trader(client, email="flag2_trader@example.com")
        trader_token = trader_data["access_token"]
        trade_id = self._create_trade_for_test(client, trader_token)

        learner_data = _register_learner(client, email="flag2_learner@example.com")
        learner_token = learner_data["access_token"]

        client.post(
            f"/api/learner/trades/{trade_id}/flag",
            data=json.dumps({"reason": "First flag"}),
            content_type="application/json",
            headers=_auth_header(learner_token),
        )
        resp = client.post(
            f"/api/learner/trades/{trade_id}/flag",
            data=json.dumps({"reason": "Second flag"}),
            content_type="application/json",
            headers=_auth_header(learner_token),
        )
        assert resp.status_code == 409

    def test_get_flags(self, client, db):
        learner_data = _register_learner(client, email="get_flags@example.com")
        token = learner_data["access_token"]

        resp = client.get("/api/learner/flags", headers=_auth_header(token))
        assert resp.status_code == 200
        assert "flags" in resp.get_json()


class TestLearnerRatings:
    def _create_trade_and_unlock(self, client, db, trader_email, learner_email):
        trader_data = _register_pro_trader(client, email=trader_email)
        trader_token = trader_data["access_token"]
        resp = client.post(
            "/api/pro-trader/trades",
            data=json.dumps({
                "symbol": "ETH",
                "direction": "sell",
                "entry_price": 2000.0,
                "stop_loss_price": 2100.0,
                "target_price": 1800.0,
                "technical_rationale": "The price is consolidating near a key support zone showing clear signs of institutional accumulation with RSI indicating oversold conditions and a bullish divergence forming on the daily chart suggesting a high probability reversal to the upside targeting the next resistance level with a very favorable risk to reward setup for entry",
            }),
            content_type="application/json",
            headers=_auth_header(trader_token),
        )
        trade_id = resp.get_json()["trade"]["id"]

        learner_data = _register_learner(client, email=learner_email)
        learner_token = learner_data["access_token"]
        client.post(f"/api/learner/trades/{trade_id}/unlock", headers=_auth_header(learner_token))
        return trade_id, learner_token

    def test_rate_trade(self, client, db):
        trade_id, learner_token = self._create_trade_and_unlock(
            client, db, "rate_trader@example.com", "rate_learner@example.com"
        )

        resp = client.post(
            f"/api/learner/trades/{trade_id}/rate",
            data=json.dumps({"rating": 5, "review": "Excellent trade!"}),
            content_type="application/json",
            headers=_auth_header(learner_token),
        )
        assert resp.status_code == 201
        assert resp.get_json()["rating"]["rating"] == 5

    def test_update_rating(self, client, db):
        trade_id, learner_token = self._create_trade_and_unlock(
            client, db, "update_rate_trader@example.com", "update_rate_learner@example.com"
        )

        client.post(
            f"/api/learner/trades/{trade_id}/rate",
            data=json.dumps({"rating": 3}),
            content_type="application/json",
            headers=_auth_header(learner_token),
        )

        resp = client.put(
            f"/api/learner/trades/{trade_id}/rate",
            data=json.dumps({"rating": 4}),
            content_type="application/json",
            headers=_auth_header(learner_token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["rating"]["rating"] == 4

    def test_rate_without_unlock(self, client, db):
        trader_data = _register_pro_trader(client, email="rate_no_unlock_trader@example.com")
        trader_token = trader_data["access_token"]
        resp = client.post(
            "/api/pro-trader/trades",
            data=json.dumps({
                "symbol": "USDT",
                "direction": "buy",
                "entry_price": 1.0,
                "stop_loss_price": 0.98,
                "target_price": 1.05,
                "technical_rationale": "The price is consolidating near a key support zone showing clear signs of institutional accumulation with RSI indicating oversold conditions and a bullish divergence forming on the daily chart suggesting a high probability reversal to the upside targeting the next resistance level with a very favorable risk to reward setup for entry",
            }),
            content_type="application/json",
            headers=_auth_header(trader_token),
        )
        trade_id = resp.get_json()["trade"]["id"]

        learner_data = _register_learner(client, email="rate_no_unlock_learner@example.com")
        learner_token = learner_data["access_token"]

        resp = client.post(
            f"/api/learner/trades/{trade_id}/rate",
            data=json.dumps({"rating": 5}),
            content_type="application/json",
            headers=_auth_header(learner_token),
        )
        assert resp.status_code == 403

    def test_invalid_rating_value(self, client, db):
        trade_id, learner_token = self._create_trade_and_unlock(
            client, db, "invalid_rate_trader@example.com", "invalid_rate_learner@example.com"
        )

        resp = client.post(
            f"/api/learner/trades/{trade_id}/rate",
            data=json.dumps({"rating": 6}),
            content_type="application/json",
            headers=_auth_header(learner_token),
        )
        assert resp.status_code == 400


class TestLearnerNotifications:
    def test_get_notifications_empty(self, client, db):
        data = _register_learner(client, email="notif@example.com")
        token = data["access_token"]

        resp = client.get("/api/learner/notifications", headers=_auth_header(token))
        assert resp.status_code == 200
        r = resp.get_json()
        assert r["notifications"] == []
        assert r["unread_count"] == 0

    def test_notification_preferences(self, client, db):
        data = _register_learner(client, email="notifpref@example.com")
        token = data["access_token"]

        # Get preferences
        resp = client.get("/api/learner/notification-preferences", headers=_auth_header(token))
        assert resp.status_code == 200
        prefs = resp.get_json()
        assert "email_new_trade" in prefs

        # Update preferences
        update_resp = client.put(
            "/api/learner/notification-preferences",
            data=json.dumps({"email_new_trade": False, "sms_enabled": True, "sms_phone": "+919876543210"}),
            content_type="application/json",
            headers=_auth_header(token),
        )
        assert update_resp.status_code == 200
        updated = update_resp.get_json()["preferences"]
        assert updated["email_new_trade"] is False
        assert updated["sms_enabled"] is True
        assert updated["sms_phone"] == "+919876543210"


class TestProTradersPublic:
    def test_list_pro_traders(self, client, db):
        _register_pro_trader(client, email="pub_trader1@example.com")
        learner_data = _register_learner(client, email="pub_learner1@example.com")
        token = learner_data["access_token"]

        resp = client.get("/api/pro-traders", headers=_auth_header(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert "traders" in data

    def test_get_pro_trader_profile(self, client, db):
        trader_data = _register_pro_trader(client, email="pub_profile_trader@example.com")
        trader_id = trader_data["user"]["id"]

        learner_data = _register_learner(client, email="pub_profile_learner@example.com")
        learner_token = learner_data["access_token"]

        resp = client.get(f"/api/pro-traders/{trader_id}/profile", headers=_auth_header(learner_token))
        assert resp.status_code == 200
        profile = resp.get_json()
        assert "accuracy_score" in profile
        assert "total_subscribers" in profile

    def test_get_pro_trader_trades(self, client, db):
        trader_data = _register_pro_trader(client, email="pub_trades_trader@example.com")
        trader_id = trader_data["user"]["id"]
        trader_token = trader_data["access_token"]

        # Create a trade for the trader
        client.post(
            "/api/pro-trader/trades",
            data=json.dumps({
                "symbol": "BNB",
                "direction": "buy",
                "entry_price": 300.0,
                "stop_loss_price": 280.0,
                "target_price": 350.0,
                "technical_rationale": "The price is consolidating near a key support zone showing clear signs of institutional accumulation with RSI indicating oversold conditions and a bullish divergence forming on the daily chart suggesting a high probability reversal to the upside targeting the next resistance level with a very favorable risk to reward setup for entry",
            }),
            content_type="application/json",
            headers=_auth_header(trader_token),
        )

        learner_data = _register_learner(client, email="pub_trades_learner@example.com")
        learner_token = learner_data["access_token"]

        resp = client.get(
            f"/api/pro-traders/{trader_id}/trades",
            headers=_auth_header(learner_token),
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "trades" in data
        assert len(data["trades"]) >= 1


class TestLearnerComments:
    def _setup_unlocked_trade(self, client, db, trader_email, learner_email):
        trader_data = _register_pro_trader(client, email=trader_email)
        trader_token = trader_data["access_token"]
        resp = client.post(
            "/api/pro-trader/trades",
            data=json.dumps({
                "symbol": "SOL",
                "direction": "buy",
                "entry_price": 100.0,
                "stop_loss_price": 90.0,
                "target_price": 120.0,
                "technical_rationale": "The price is consolidating near a key support zone showing clear signs of institutional accumulation with RSI indicating oversold conditions and a bullish divergence forming on the daily chart suggesting a high probability reversal to the upside targeting the next resistance level with a very favorable risk to reward setup for entry",
            }),
            content_type="application/json",
            headers=_auth_header(trader_token),
        )
        trade_id = resp.get_json()["trade"]["id"]

        learner_data = _register_learner(client, email=learner_email)
        learner_token = learner_data["access_token"]
        client.post(f"/api/learner/trades/{trade_id}/unlock", headers=_auth_header(learner_token))
        return trade_id, learner_token

    def test_post_and_get_comment(self, client, db):
        trade_id, learner_token = self._setup_unlocked_trade(
            client, db, "comm_trader@example.com", "comm_learner@example.com"
        )

        resp = client.post(
            f"/api/learner/trades/{trade_id}/comments",
            data=json.dumps({"content": "Great trade signal!"}),
            content_type="application/json",
            headers=_auth_header(learner_token),
        )
        assert resp.status_code == 201

        get_resp = client.get(
            f"/api/learner/trades/{trade_id}/comments",
            headers=_auth_header(learner_token),
        )
        assert get_resp.status_code == 200
        assert len(get_resp.get_json()["comments"]) >= 1

    def test_comment_without_unlock(self, client, db):
        trader_data = _register_pro_trader(client, email="nounlock_trader@example.com")
        trader_token = trader_data["access_token"]
        resp = client.post(
            "/api/pro-trader/trades",
            data=json.dumps({
                "symbol": "ADA",
                "direction": "buy",
                "entry_price": 0.5,
                "stop_loss_price": 0.45,
                "target_price": 0.6,
                "technical_rationale": "The price is consolidating near a key support zone showing clear signs of institutional accumulation with RSI indicating oversold conditions and a bullish divergence forming on the daily chart suggesting a high probability reversal to the upside targeting the next resistance level with a very favorable risk to reward setup for entry",
            }),
            content_type="application/json",
            headers=_auth_header(trader_token),
        )
        trade_id = resp.get_json()["trade"]["id"]

        learner_data = _register_learner(client, email="nounlock_learner@example.com")
        learner_token = learner_data["access_token"]

        resp = client.post(
            f"/api/learner/trades/{trade_id}/comments",
            data=json.dumps({"content": "Should not be allowed"}),
            content_type="application/json",
            headers=_auth_header(learner_token),
        )
        assert resp.status_code == 403


class TestChangePassword:
    def test_change_password_success(self, client, db):
        client.post(
            "/api/auth/register",
            data=json.dumps({"email": "changepw@example.com", "password": "TestPass1", "role": "public_trader"}),
            content_type="application/json",
        )
        login_resp = client.post(
            "/api/auth/login",
            data=json.dumps({"email": "changepw@example.com", "password": "TestPass1"}),
            content_type="application/json",
        )
        token = login_resp.get_json()["access_token"]

        resp = client.post(
            "/api/auth/change-password",
            data=json.dumps({"current_password": "TestPass1", "new_password": "NewPass2"}),
            content_type="application/json",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200

        # Verify new password works
        login2_resp = client.post(
            "/api/auth/login",
            data=json.dumps({"email": "changepw@example.com", "password": "NewPass2"}),
            content_type="application/json",
        )
        assert login2_resp.status_code == 200

    def test_change_password_wrong_current(self, client, db):
        client.post(
            "/api/auth/register",
            data=json.dumps({"email": "wrongpw@example.com", "password": "TestPass1", "role": "public_trader"}),
            content_type="application/json",
        )
        login_resp = client.post(
            "/api/auth/login",
            data=json.dumps({"email": "wrongpw@example.com", "password": "TestPass1"}),
            content_type="application/json",
        )
        token = login_resp.get_json()["access_token"]

        resp = client.post(
            "/api/auth/change-password",
            data=json.dumps({"current_password": "WrongPass1", "new_password": "NewPass2"}),
            content_type="application/json",
            headers=_auth_header(token),
        )
        assert resp.status_code == 401

    def test_change_password_weak_new(self, client, db):
        client.post(
            "/api/auth/register",
            data=json.dumps({"email": "weakpw@example.com", "password": "TestPass1", "role": "public_trader"}),
            content_type="application/json",
        )
        login_resp = client.post(
            "/api/auth/login",
            data=json.dumps({"email": "weakpw@example.com", "password": "TestPass1"}),
            content_type="application/json",
        )
        token = login_resp.get_json()["access_token"]

        resp = client.post(
            "/api/auth/change-password",
            data=json.dumps({"current_password": "TestPass1", "new_password": "weak"}),
            content_type="application/json",
            headers=_auth_header(token),
        )
        assert resp.status_code == 400
