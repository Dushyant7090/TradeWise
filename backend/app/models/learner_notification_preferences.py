"""
Learner Notification Preferences model
"""
import uuid
from datetime import datetime, timezone
from app import db


class LearnerNotificationPreferences(db.Model):
    __tablename__ = "learner_notification_preferences"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    email_new_trade = db.Column(db.Boolean, default=True, nullable=False)
    email_trade_closed = db.Column(db.Boolean, default=True, nullable=False)
    email_subscription_expiring = db.Column(db.Boolean, default=True, nullable=False)
    email_flag_update = db.Column(db.Boolean, default=True, nullable=False)
    email_announcements = db.Column(db.Boolean, default=False, nullable=False)
    in_app_new_trade = db.Column(db.Boolean, default=True, nullable=False)
    in_app_trade_closed = db.Column(db.Boolean, default=True, nullable=False)
    in_app_subscription_expiring = db.Column(db.Boolean, default=True, nullable=False)
    in_app_flag_update = db.Column(db.Boolean, default=True, nullable=False)
    sms_enabled = db.Column(db.Boolean, default=False, nullable=False)
    sms_phone = db.Column(db.String(20), nullable=True)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user = db.relationship("User", foreign_keys=[user_id])

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "email_new_trade": self.email_new_trade,
            "email_trade_closed": self.email_trade_closed,
            "email_subscription_expiring": self.email_subscription_expiring,
            "email_flag_update": self.email_flag_update,
            "email_announcements": self.email_announcements,
            "in_app_new_trade": self.in_app_new_trade,
            "in_app_trade_closed": self.in_app_trade_closed,
            "in_app_subscription_expiring": self.in_app_subscription_expiring,
            "in_app_flag_update": self.in_app_flag_update,
            "sms_enabled": self.sms_enabled,
            "sms_phone": self.sms_phone,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
