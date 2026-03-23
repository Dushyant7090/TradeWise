"""
Revenue Split model
"""
import uuid
from datetime import datetime, timezone
from app import db


class RevenueSplit(db.Model):
    __tablename__ = "revenue_splits"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_id = db.Column(
        db.String(36), db.ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    trader_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pro_trader_amount = db.Column(db.Numeric(12, 2), nullable=False)
    admin_amount = db.Column(db.Numeric(12, 2), nullable=False)
    split_percentage_pro = db.Column(db.Integer, default=90, nullable=False)
    split_percentage_admin = db.Column(db.Integer, default=10, nullable=False)
    pro_trader_wallet_credited = db.Column(db.Boolean, default=False, nullable=False)
    admin_wallet_credited = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    payment = db.relationship("Payment", back_populates="revenue_split")
    trader = db.relationship("User", foreign_keys=[trader_id])

    def to_dict(self):
        return {
            "id": self.id,
            "payment_id": self.payment_id,
            "trader_id": self.trader_id,
            "pro_trader_amount": float(self.pro_trader_amount),
            "admin_amount": float(self.admin_amount),
            "split_percentage_pro": self.split_percentage_pro,
            "split_percentage_admin": self.split_percentage_admin,
            "pro_trader_wallet_credited": self.pro_trader_wallet_credited,
            "admin_wallet_credited": self.admin_wallet_credited,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
