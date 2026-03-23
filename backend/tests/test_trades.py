"""
Tests for Pro Trader Profile and Trades endpoints
"""
import pytest
import json


def _register_and_login(client, email="trader@example.com"):
    """Helper: register and return access token."""
    client.post(
        "/api/auth/register",
        data=json.dumps({"email": email, "password": "TestPass1", "role": "pro_trader"}),
        content_type="application/json",
    )
    resp = client.post(
        "/api/auth/login",
        data=json.dumps({"email": email, "password": "TestPass1"}),
        content_type="application/json",
    )
    return resp.get_json()["access_token"]


class TestProfile:
    def test_get_profile_requires_auth(self, client, db):
        resp = client.get("/api/pro-trader/profile")
        assert resp.status_code == 401

    def test_get_profile_success(self, client, db):
        token = _register_and_login(client, "proftest@example.com")
        resp = client.get(
            "/api/pro-trader/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "accuracy_score" in data

    def test_update_profile(self, client, db):
        token = _register_and_login(client, "profupdate@example.com")
        bio = "A" * 110  # 110 chars, > 100 required
        resp = client.put(
            "/api/pro-trader/profile",
            data=json.dumps({
                "bio": bio,
                "specializations": ["stocks", "crypto"],
                "years_of_experience": 5,
                "trading_style": "swing",
            }),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["profile"]["bio"] == bio

    def test_update_profile_short_bio(self, client, db):
        token = _register_and_login(client, "shortbio@example.com")
        resp = client.put(
            "/api/pro-trader/profile",
            data=json.dumps({"bio": "Too short"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    def test_get_dashboard(self, client, db):
        token = _register_and_login(client, "dashboard@example.com")
        resp = client.get(
            "/api/pro-trader/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "accuracy_score" in data
        assert "total_subscribers" in data


class TestTrades:
    def _get_token(self, client):
        return _register_and_login(client, "tradestest@example.com")

    def test_create_trade_success(self, client, db):
        token = self._get_token(client)
        rationale = "A " * 55  # > 50 words
        resp = client.post(
            "/api/pro-trader/trades",
            data=json.dumps({
                "symbol": "RELIANCE",
                "direction": "buy",
                "entry_price": 2500.0,
                "stop_loss_price": 2400.0,
                "target_price": 2700.0,
                "technical_rationale": rationale,
            }),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["trade"]["symbol"] == "RELIANCE"
        assert float(data["trade"]["rrr"]) > 0

    def test_create_trade_invalid_direction(self, client, db):
        token = self._get_token(client)
        resp = client.post(
            "/api/pro-trader/trades",
            data=json.dumps({
                "symbol": "RELIANCE",
                "direction": "hold",  # invalid
                "entry_price": 2500.0,
                "stop_loss_price": 2400.0,
                "target_price": 2700.0,
                "technical_rationale": "A " * 55,
            }),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    def test_create_trade_short_rationale(self, client, db):
        token = self._get_token(client)
        resp = client.post(
            "/api/pro-trader/trades",
            data=json.dumps({
                "symbol": "RELIANCE",
                "direction": "buy",
                "entry_price": 2500.0,
                "stop_loss_price": 2400.0,
                "target_price": 2700.0,
                "technical_rationale": "Short rationale",  # < 50 words
            }),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    def test_create_trade_invalid_sl_for_buy(self, client, db):
        token = self._get_token(client)
        resp = client.post(
            "/api/pro-trader/trades",
            data=json.dumps({
                "symbol": "RELIANCE",
                "direction": "buy",
                "entry_price": 2500.0,
                "stop_loss_price": 2600.0,  # SL above entry for BUY - invalid
                "target_price": 2700.0,
                "technical_rationale": "A " * 55,
            }),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    def test_get_trades(self, client, db):
        token = self._get_token(client)
        resp = client.get(
            "/api/pro-trader/trades",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "trades" in resp.get_json()

    def test_close_trade(self, client, db):
        token = self._get_token(client)
        # Create trade
        create_resp = client.post(
            "/api/pro-trader/trades",
            data=json.dumps({
                "symbol": "INFY",
                "direction": "buy",
                "entry_price": 1500.0,
                "stop_loss_price": 1450.0,
                "target_price": 1600.0,
                "technical_rationale": "A " * 55,
            }),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        trade_id = create_resp.get_json()["trade"]["id"]

        # Close it
        close_resp = client.put(
            f"/api/pro-trader/trades/{trade_id}/close",
            data=json.dumps({"outcome": "win"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert close_resp.status_code == 200
        assert close_resp.get_json()["trade"]["status"] == "target_hit"

    def test_cancel_trade(self, client, db):
        token = self._get_token(client)
        create_resp = client.post(
            "/api/pro-trader/trades",
            data=json.dumps({
                "symbol": "TCS",
                "direction": "sell",
                "entry_price": 3500.0,
                "stop_loss_price": 3600.0,
                "target_price": 3400.0,
                "technical_rationale": "A " * 55,
            }),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        trade_id = create_resp.get_json()["trade"]["id"]

        cancel_resp = client.delete(
            f"/api/pro-trader/trades/{trade_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert cancel_resp.status_code == 200
