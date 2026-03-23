"""
Tests for authentication endpoints
"""
import pytest
import json


class TestRegister:
    def test_register_success(self, client, db):
        resp = client.post(
            "/api/auth/register",
            data=json.dumps({
                "email": "newuser@example.com",
                "password": "TestPass1",
                "role": "pro_trader",
                "display_name": "Test Trader",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "newuser@example.com"

    def test_register_duplicate_email(self, client, db):
        payload = {
            "email": "dup@example.com",
            "password": "TestPass1",
            "role": "pro_trader",
        }
        client.post("/api/auth/register", data=json.dumps(payload), content_type="application/json")
        resp = client.post("/api/auth/register", data=json.dumps(payload), content_type="application/json")
        assert resp.status_code == 409

    def test_register_invalid_email(self, client, db):
        resp = client.post(
            "/api/auth/register",
            data=json.dumps({"email": "notanemail", "password": "TestPass1", "role": "pro_trader"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_register_weak_password(self, client, db):
        resp = client.post(
            "/api/auth/register",
            data=json.dumps({"email": "user@example.com", "password": "weak", "role": "pro_trader"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_register_invalid_role(self, client, db):
        resp = client.post(
            "/api/auth/register",
            data=json.dumps({"email": "user@example.com", "password": "TestPass1", "role": "superadmin"}),
            content_type="application/json",
        )
        assert resp.status_code == 400


class TestLogin:
    def test_login_success(self, client, db):
        # Register first
        client.post(
            "/api/auth/register",
            data=json.dumps({"email": "login@example.com", "password": "TestPass1", "role": "pro_trader"}),
            content_type="application/json",
        )
        resp = client.post(
            "/api/auth/login",
            data=json.dumps({"email": "login@example.com", "password": "TestPass1"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data

    def test_login_wrong_password(self, client, db):
        client.post(
            "/api/auth/register",
            data=json.dumps({"email": "wrongpw@example.com", "password": "TestPass1", "role": "pro_trader"}),
            content_type="application/json",
        )
        resp = client.post(
            "/api/auth/login",
            data=json.dumps({"email": "wrongpw@example.com", "password": "WrongPass1"}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client, db):
        resp = client.post(
            "/api/auth/login",
            data=json.dumps({"email": "nobody@example.com", "password": "TestPass1"}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_login_missing_fields(self, client, db):
        resp = client.post(
            "/api/auth/login",
            data=json.dumps({"email": "only@example.com"}),
            content_type="application/json",
        )
        assert resp.status_code == 400


class TestRefreshToken:
    def test_refresh_token(self, client, db):
        # Register and login
        client.post(
            "/api/auth/register",
            data=json.dumps({"email": "refresh@example.com", "password": "TestPass1", "role": "pro_trader"}),
            content_type="application/json",
        )
        login_resp = client.post(
            "/api/auth/login",
            data=json.dumps({"email": "refresh@example.com", "password": "TestPass1"}),
            content_type="application/json",
        )
        refresh_token = login_resp.get_json()["refresh_token"]

        resp = client.post(
            "/api/auth/refresh-token",
            headers={"Authorization": f"Bearer {refresh_token}"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.get_json()


class TestLogout:
    def test_logout_requires_auth(self, client, db):
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 401

    def test_logout_success(self, client, db):
        client.post(
            "/api/auth/register",
            data=json.dumps({"email": "logout@example.com", "password": "TestPass1", "role": "pro_trader"}),
            content_type="application/json",
        )
        login_resp = client.post(
            "/api/auth/login",
            data=json.dumps({"email": "logout@example.com", "password": "TestPass1"}),
            content_type="application/json",
        )
        token = login_resp.get_json()["access_token"]

        resp = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
