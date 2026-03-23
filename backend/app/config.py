"""
TradeWise Backend - Configuration
"""
import os
from datetime import timedelta


class BaseConfig:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "change-me-in-production")
    DEBUG = False
    TESTING = False

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///tradewise.db")
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
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

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
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=60)


class ProductionConfig(BaseConfig):
    DEBUG = False


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
