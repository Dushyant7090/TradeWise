"""
TradeWise Backend - Configuration
"""
import os
from typing import Optional
from datetime import timedelta


def _resolve_postgres_database_url(primary_env: str, fallback_env: Optional[str] = None) -> str:
    """Resolve and validate a PostgreSQL-only database URL."""
    database_url = os.getenv(primary_env, "").strip()
    if not database_url and fallback_env:
        database_url = os.getenv(fallback_env, "").strip()

    if not database_url:
        required = primary_env if not fallback_env else f"{primary_env} or {fallback_env}"
        raise RuntimeError(
            f"{required} must be set to a Supabase/PostgreSQL connection string."
        )

    normalized = database_url.lower()
    if not normalized.startswith(("postgresql://", "postgresql+psycopg2://")):
        raise RuntimeError(
            "DATABASE_URL must use PostgreSQL. SQLite and other database engines are not supported."
        )

    return database_url


def _resolve_testing_database_url() -> str:
    """Resolve test database URL and enforce hard safety checks."""
    test_database_url = _resolve_postgres_database_url("TEST_DATABASE_URL")
    primary_database_url = os.getenv("DATABASE_URL", "").strip()

    if primary_database_url and primary_database_url == test_database_url:
        raise RuntimeError(
            "TEST_DATABASE_URL must be different from DATABASE_URL. "
            "Refusing to run tests against the non-isolated primary database."
        )

    return test_database_url


def _resolve_testing_schema() -> str:
    """Require an isolated schema name for each test run/worker."""
    schema_name = os.getenv("TEST_DATABASE_SCHEMA", "").strip()
    if not schema_name:
        raise RuntimeError(
            "TEST_DATABASE_SCHEMA must be set for testing config. "
            "Use an isolated temporary schema (for example: pytest_gw0_ab12cd)."
        )
    return schema_name


class BaseConfig:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "change-me-in-production")
    DEBUG = False
    TESTING = False

    # Database
    SQLALCHEMY_DATABASE_URI = _resolve_postgres_database_url("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # JWT
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-secret-change-in-production")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        seconds=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", 3600))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        seconds=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRES", 2592000))
    )
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer"

    # Flask-Mail
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "noreply@tradewise.com")

    # Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    PROFILE_PICTURES_BUCKET = os.getenv("PROFILE_PICTURES_BUCKET", "profile-pictures")
    TRADE_CHARTS_BUCKET = os.getenv("TRADE_CHARTS_BUCKET", "chart-images")
    KYC_DOCUMENTS_BUCKET = os.getenv("KYC_DOCUMENTS_BUCKET", "kyc-documents")

    # Cashfree
    CASHFREE_APP_ID = os.getenv("CASHFREE_APP_ID", "")
    CASHFREE_SECRET_KEY = os.getenv("CASHFREE_SECRET_KEY", "")
    CASHFREE_BASE_URL = os.getenv("CASHFREE_BASE_URL", "https://sandbox.cashfree.com/pg")
    CASHFREE_PAYOUT_BASE_URL = os.getenv(
        "CASHFREE_PAYOUT_BASE_URL", "https://payout-gamma.cashfree.com"
    )
    CASHFREE_WEBHOOK_SECRET = os.getenv("CASHFREE_WEBHOOK_SECRET", "")

    # Encryption
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")

    # Platform
    PLATFORM_FEE_PERCENT = int(os.getenv("PLATFORM_FEE_PERCENT", 10))
    PRO_TRADER_REVENUE_PERCENT = int(os.getenv("PRO_TRADER_REVENUE_PERCENT", 90))
    MIN_WITHDRAWAL_AMOUNT = float(os.getenv("MIN_WITHDRAWAL_AMOUNT", 500))
    MAX_FLAG_PENALTY_THRESHOLD = int(os.getenv("MAX_FLAG_PENALTY_THRESHOLD", 10))
    FLAG_ACCURACY_PENALTY = float(os.getenv("FLAG_ACCURACY_PENALTY", 5.0))

    # Frontend
    FRONTEND_URL = os.getenv(
        "FRONTEND_URL",
        "http://localhost:5500,http://127.0.0.1:5500,http://localhost:3000,http://127.0.0.1:3000",
    )

    # Redis/Celery
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Max upload size (10 MB)
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = True
    # Values are resolved lazily via apply_testing_config_overrides to avoid
    # forcing test-only env vars during normal app startup.
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", os.getenv("DATABASE_URL", ""))
    TEST_DATABASE_SCHEMA = os.getenv("TEST_DATABASE_SCHEMA", "")
    SQLALCHEMY_ENGINE_OPTIONS = {
        **BaseConfig.SQLALCHEMY_ENGINE_OPTIONS,
    }
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=60)


def apply_testing_config_overrides(target_config: dict) -> None:
    """Apply strict testing DB/schema constraints only for testing mode."""
    test_database_url = _resolve_testing_database_url()
    test_database_schema = _resolve_testing_schema()

    target_config["SQLALCHEMY_DATABASE_URI"] = test_database_url
    target_config["TEST_DATABASE_SCHEMA"] = test_database_schema

    engine_options = dict(BaseConfig.SQLALCHEMY_ENGINE_OPTIONS)
    connect_args = dict(engine_options.get("connect_args") or {})
    connect_args["options"] = f"-csearch_path={test_database_schema},public"
    engine_options["connect_args"] = connect_args
    target_config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_options


class ProductionConfig(BaseConfig):
    DEBUG = False


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
