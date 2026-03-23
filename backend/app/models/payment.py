"""
Payment model
"""
import uuid
from datetime import datetime, timezone
from app import db


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subscriber_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trader_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(5), default="INR", nullable=False)
    cashfree_order_id = db.Column(db.String(100), nullable=True, unique=True)
    cashfree_payment_id = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)
    payment_method = db.Column(db.String(30), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships
    subscriber = db.relationship("User", foreign_keys=[subscriber_id])
    trader = db.relationship("User", foreign_keys=[trader_id])
    subscription = db.relationship("Subscription", back_populates="payment", uselist=False)
    revenue_split = db.relationship("RevenueSplit", back_populates="payment", uselist=False, cascade="all, delete-orphan")

    VALID_STATUSES = ["pending", "success", "failed", "refunded"]

    def to_dict(self):
        return {
            "id": self.id,
            "subscriber_id": self.subscriber_id,
            "trader_id": self.trader_id,
            "amount": float(self.amount),
            "currency": self.currency,
            "cashfree_order_id": self.cashfree_order_id,
            "cashfree_payment_id": self.cashfree_payment_id,
            "status": self.status,
            "payment_method": self.payment_method,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
