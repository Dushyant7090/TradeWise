"""
Subscription model
"""
import uuid
from datetime import datetime, timezone
from app import db


class Subscription(db.Model):
    __tablename__ = "subscriptions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subscriber_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trader_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    ends_at = db.Column(db.DateTime(timezone=True), nullable=False)
    status = db.Column(db.String(20), default="active", nullable=False, index=True)
    auto_renew = db.Column(db.Boolean, default=False, nullable=False)
    payment_id = db.Column(
        db.String(36), db.ForeignKey("payments.id", ondelete="SET NULL"), nullable=True
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    subscriber = db.relationship("User", foreign_keys=[subscriber_id])
    trader = db.relationship("User", foreign_keys=[trader_id])
    payment = db.relationship("Payment", back_populates="subscription")

    VALID_STATUSES = ["active", "expired", "cancelled"]

    def to_dict(self):
        return {
            "id": self.id,
            "subscriber_id": self.subscriber_id,
            "trader_id": self.trader_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ends_at": self.ends_at.isoformat() if self.ends_at else None,
            "status": self.status,
            "auto_renew": self.auto_renew,
            "payment_id": self.payment_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
