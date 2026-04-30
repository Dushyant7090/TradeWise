"""
Test configuration and fixtures
"""
import os
import re
import uuid

import pytest


def _sanitize_schema_name(value: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", value)
    return sanitized.lower()


def _build_isolated_test_schema() -> str:
    worker = os.getenv("PYTEST_XDIST_WORKER", "gw0")
    run_id = os.getenv("PYTEST_RUN_ID", "").strip()
    if not run_id:
        run_id = uuid.uuid4().hex[:10]
        os.environ["PYTEST_RUN_ID"] = run_id

    return _sanitize_schema_name(f"pytest_{worker}_{run_id}")


os.environ["TEST_DATABASE_SCHEMA"] = _build_isolated_test_schema()

from app import create_app, db as _db
from app.models.user import User
from app.models.profile import Profile
from app.models.pro_trader_profile import ProTraderProfile
from app.models.notification_preferences import NotificationPreferences
from sqlalchemy import text


def _quote_identifier(identifier: str) -> str:
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'


def _create_schema(engine, schema_name: str):
    quoted = _quote_identifier(schema_name)
    statement = text(f"CREATE SCHEMA IF NOT EXISTS {quoted}")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(statement)


def _drop_schema(engine, schema_name: str):
    quoted = _quote_identifier(schema_name)
    statement = text(f"DROP SCHEMA IF EXISTS {quoted} CASCADE")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(statement)


def _truncate_schema_tables(engine, schema_name: str):
    def _list_tables(conn, target_schema: str):
        list_tables = text(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = :schema_name
            ORDER BY tablename
            """
        )
        return [row[0] for row in conn.execute(list_tables, {"schema_name": target_schema}).fetchall()]

    with engine.begin() as conn:
        candidate_schemas = [schema_name]
        if schema_name != "public":
            candidate_schemas.append("public")

        for active_schema in candidate_schemas:
            table_names = _list_tables(conn, active_schema)
            if not table_names:
                continue

            qualified = ", ".join(
                f"{_quote_identifier(active_schema)}.{_quote_identifier(table_name)}"
                for table_name in table_names
            )
            conn.execute(text(f"TRUNCATE TABLE {qualified} RESTART IDENTITY CASCADE"))


@pytest.fixture(scope="session")
def app():
    """Create test Flask app."""
    app = create_app("testing")
    schema_name = app.config["TEST_DATABASE_SCHEMA"]

    with app.app_context():
        _create_schema(_db.engine, schema_name)
        _db.create_all()
        yield app
        _db.session.remove()
        _drop_schema(_db.engine, schema_name)


@pytest.fixture(scope="function")
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture(scope="function")
def db(app):
    """Provide clean DB for each test."""
    schema_name = app.config["TEST_DATABASE_SCHEMA"]

    with app.app_context():
        _truncate_schema_tables(_db.engine, schema_name)
        yield _db
        _db.session.remove()
        _truncate_schema_tables(_db.engine, schema_name)


def create_test_user(db_session, email="test@example.com", role="pro_trader", password="TestPass1"):
    """Helper to create a test user with profile."""
    import bcrypt
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user = User(email=email, password_hash=password_hash, auth_provider="email")
    db_session.session.add(user)
    db_session.session.flush()

    profile = Profile(user_id=user.id, role=role, display_name="Test Trader")
    db_session.session.add(profile)

    prefs = NotificationPreferences(user_id=user.id)
    db_session.session.add(prefs)

    if role == "pro_trader":
        pt_profile = ProTraderProfile(user_id=user.id)
        db_session.session.add(pt_profile)

    db_session.session.commit()
    return user
