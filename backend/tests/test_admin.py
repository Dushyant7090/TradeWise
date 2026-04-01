"""
Tests for admin routes — focusing on permission and self-protection guards.
"""
import json
import pytest
from tests.conftest import create_test_user


def _login(client, email, password="TestPass1"):
    """Login and return the JWT access token."""
    resp = client.post(
        "/api/auth/login",
        data=json.dumps({"email": email, "password": password}),
        content_type="application/json",
    )
    data = resp.get_json()
    assert "access_token" in data, f"Login failed for {email}: {data}"
    return data["access_token"]


def _admin_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


class TestAdminAuth:
    """Admin endpoints must reject non-admin callers."""

    def test_stats_requires_auth(self, client, db):
        resp = client.get("/api/admin/stats")
        assert resp.status_code == 401

    def test_stats_forbidden_for_pro_trader(self, client, db):
        create_test_user(db, email="pt_stats@example.com", role="pro_trader")
        token = _login(client, "pt_stats@example.com")
        resp = client.get("/api/admin/stats", headers=_admin_headers(token))
        assert resp.status_code == 403

    def test_stats_accessible_by_admin(self, client, db):
        create_test_user(db, email="admin_stats@example.com", role="admin")
        token = _login(client, "admin_stats@example.com")
        resp = client.get("/api/admin/stats", headers=_admin_headers(token))
        assert resp.status_code == 200


class TestAdminSelfProtection:
    """Admin cannot suspend, reactivate, or ban their own account."""

    def _get_user_id(self, client, token, email):
        """Find a user's ID from the admin users list."""
        resp = client.get("/api/admin/users", headers=_admin_headers(token))
        users = resp.get_json().get("users", [])
        for u in users:
            if u.get("email") == email:
                return u["id"]
        return None

    def test_admin_cannot_suspend_self(self, client, db):
        create_test_user(db, email="self_suspend@example.com", role="admin")
        token = _login(client, "self_suspend@example.com")
        admin_id = self._get_user_id(client, token, "self_suspend@example.com")
        assert admin_id is not None

        resp = client.post(
            f"/api/admin/users/{admin_id}/suspend",
            headers=_admin_headers(token),
        )
        assert resp.status_code == 403
        assert "cannot suspend" in resp.get_json().get("error", "").lower()

    def test_admin_cannot_ban_self(self, client, db):
        create_test_user(db, email="self_ban@example.com", role="admin")
        token = _login(client, "self_ban@example.com")
        admin_id = self._get_user_id(client, token, "self_ban@example.com")
        assert admin_id is not None

        resp = client.post(
            f"/api/admin/users/{admin_id}/ban",
            headers=_admin_headers(token),
        )
        assert resp.status_code == 403
        assert "cannot ban" in resp.get_json().get("error", "").lower()

    def test_admin_cannot_reactivate_self(self, client, db):
        create_test_user(db, email="self_react@example.com", role="admin")
        token = _login(client, "self_react@example.com")
        admin_id = self._get_user_id(client, token, "self_react@example.com")
        assert admin_id is not None

        resp = client.post(
            f"/api/admin/users/{admin_id}/reactivate",
            headers=_admin_headers(token),
        )
        assert resp.status_code == 403

    def test_admin_cannot_suspend_another_admin(self, client, db):
        create_test_user(db, email="admin1@example.com", role="admin")
        create_test_user(db, email="admin2@example.com", role="admin")
        admin1_token = _login(client, "admin1@example.com")
        admin2_id = self._get_user_id(client, admin1_token, "admin2@example.com")
        assert admin2_id is not None

        resp = client.post(
            f"/api/admin/users/{admin2_id}/suspend",
            headers=_admin_headers(admin1_token),
        )
        assert resp.status_code == 403
        assert "admin accounts cannot be suspended" in resp.get_json().get("error", "").lower()

    def test_admin_cannot_ban_another_admin(self, client, db):
        create_test_user(db, email="admin3@example.com", role="admin")
        create_test_user(db, email="admin4@example.com", role="admin")
        admin3_token = _login(client, "admin3@example.com")
        admin4_id = self._get_user_id(client, admin3_token, "admin4@example.com")
        assert admin4_id is not None

        resp = client.post(
            f"/api/admin/users/{admin4_id}/ban",
            headers=_admin_headers(admin3_token),
        )
        assert resp.status_code == 403
        assert "admin accounts cannot be banned" in resp.get_json().get("error", "").lower()


class TestAdminUserActions:
    """Admin can successfully suspend/reactivate/ban non-admin users."""

    def _get_user_id(self, client, token, email):
        resp = client.get("/api/admin/users", headers=_admin_headers(token))
        users = resp.get_json().get("users", [])
        for u in users:
            if u.get("email") == email:
                return u["id"]
        return None

    def test_suspend_and_reactivate_pro_trader(self, client, db):
        create_test_user(db, email="admin_act@example.com", role="admin")
        create_test_user(db, email="trader_act@example.com", role="pro_trader")
        admin_token = _login(client, "admin_act@example.com")
        trader_id = self._get_user_id(client, admin_token, "trader_act@example.com")
        assert trader_id is not None

        resp = client.post(
            f"/api/admin/users/{trader_id}/suspend",
            headers=_admin_headers(admin_token),
        )
        assert resp.status_code == 200

        resp = client.post(
            f"/api/admin/users/{trader_id}/reactivate",
            headers=_admin_headers(admin_token),
        )
        assert resp.status_code == 200

    def test_ban_pro_trader(self, client, db):
        create_test_user(db, email="admin_ban@example.com", role="admin")
        create_test_user(db, email="trader_ban@example.com", role="pro_trader")
        admin_token = _login(client, "admin_ban@example.com")
        trader_id = self._get_user_id(client, admin_token, "trader_ban@example.com")
        assert trader_id is not None

        resp = client.post(
            f"/api/admin/users/{trader_id}/ban",
            headers=_admin_headers(admin_token),
        )
        assert resp.status_code == 200
        assert "banned" in resp.get_json().get("message", "").lower()
