"""
Notification Preferences model
"""
import uuid
from datetime import datetime, timezone
from app import db


class NotificationPreferences(db.Model):
    __tablename__ = "notification_preferences"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    email_new_subscriber = db.Column(db.Boolean, default=True, nullable=False)
    email_trade_flagged = db.Column(db.Boolean, default=True, nullable=False)
    email_payout_confirmation = db.Column(db.Boolean, default=True, nullable=False)
    in_app_new_subscriber = db.Column(db.Boolean, default=True, nullable=False)
    in_app_trade_flagged = db.Column(db.Boolean, default=True, nullable=False)
    in_app_payout_confirmation = db.Column(db.Boolean, default=True, nullable=False)
    sms_enabled = db.Column(db.Boolean, default=False, nullable=False)
    sms_phone = db.Column(db.String(20), nullable=True)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user = db.relationship("User", back_populates="notification_preferences")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "email_new_subscriber": self.email_new_subscriber,
            "email_trade_flagged": self.email_trade_flagged,
            "email_payout_confirmation": self.email_payout_confirmation,
            "in_app_new_subscriber": self.in_app_new_subscriber,
            "in_app_trade_flagged": self.in_app_trade_flagged,
            "in_app_payout_confirmation": self.in_app_payout_confirmation,
            "sms_enabled": self.sms_enabled,
            "sms_phone": self.sms_phone,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
