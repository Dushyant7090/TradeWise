"""
User model
"""
import uuid
from datetime import datetime, timezone
from app import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    auth_provider = db.Column(
        db.String(20),
        nullable=False,
        default="email",
    )
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    totp_secret = db.Column(db.String(64), nullable=True)
    totp_enabled = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    profile = db.relationship("Profile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    pro_trader_profile = db.relationship(
        "ProTraderProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    trades = db.relationship("Trade", back_populates="trader", cascade="all, delete-orphan")
    notifications = db.relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    notification_preferences = db.relationship(
        "NotificationPreferences", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    login_activities = db.relationship("LoginActivity", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "auth_provider": self.auth_provider,
            "is_active": self.is_active,
            "totp_enabled": self.totp_enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
