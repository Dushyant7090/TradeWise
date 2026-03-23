"""
Test configuration and fixtures
"""
import pytest
from app import create_app, db as _db
from app.models.user import User
from app.models.profile import Profile
from app.models.pro_trader_profile import ProTraderProfile
from app.models.notification_preferences import NotificationPreferences


@pytest.fixture(scope="session")
def app():
    """Create test Flask app."""
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture(scope="function")
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture(scope="function")
def db(app):
    """Provide clean DB for each test."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()
        _db.create_all()


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
