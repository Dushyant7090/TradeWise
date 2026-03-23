"""
Learner Notification model
"""
import uuid
from datetime import datetime, timezone
from app import db


class LearnerNotification(db.Model):
    __tablename__ = "learner_notifications"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    learner_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    related_trade_id = db.Column(
        db.String(36), db.ForeignKey("trades.id", ondelete="SET NULL"), nullable=True
    )
    related_trader_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    VALID_TYPES = [
        "trade_closed",
        "new_trade",
        "subscriber_alert",
        "flag_update",
        "subscription_expiring",
    ]

    def to_dict(self):
        return {
            "id": self.id,
            "learner_id": self.learner_id,
            "type": self.type,
            "title": self.title,
            "message": self.message,
            "related_trade_id": self.related_trade_id,
            "related_trader_id": self.related_trader_id,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
