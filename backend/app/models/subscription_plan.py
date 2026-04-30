"""
Subscription Plan model — pricing stored in paise (integer) to avoid floating-point errors.
"""
import uuid
from datetime import datetime, timezone
from app import db


class SubscriptionPlan(db.Model):
    __tablename__ = "subscription_plans"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trader_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    plan_name = db.Column(db.String(100), nullable=False, default="1 Month")
    duration_months = db.Column(db.Integer, nullable=False, default=1)
    price_paise = db.Column(db.BigInteger, nullable=False, default=0)  # INR in paise
    is_active = db.Column(db.Boolean, default=True, nullable=False)

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

    def to_dict(self):
        return {
            "id": self.id,
            "trader_id": self.trader_id,
            "plan_name": self.plan_name,
            "duration_months": self.duration_months,
            "price_paise": self.price_paise,
            "price_inr": self.price_paise / 100.0,  # convenience field for frontend
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
