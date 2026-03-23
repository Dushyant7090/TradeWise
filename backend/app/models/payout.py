"""
Payout model
"""
import uuid
from datetime import datetime, timezone
from app import db


class Payout(db.Model):
    __tablename__ = "payouts"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trader_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    cashfree_payout_id = db.Column(db.String(100), nullable=True)
    cashfree_transfer_id = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default="initiated", nullable=False, index=True)
    bank_account_last_4 = db.Column(db.String(4), nullable=True)
    initiated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    failure_reason = db.Column(db.Text, nullable=True)

    # Relationships
    trader = db.relationship("User", foreign_keys=[trader_id], overlaps="payouts")

    VALID_STATUSES = ["initiated", "processing", "success", "failed"]

    def to_dict(self):
        return {
            "id": self.id,
            "trader_id": self.trader_id,
            "amount": float(self.amount),
            "cashfree_payout_id": self.cashfree_payout_id,
            "cashfree_transfer_id": self.cashfree_transfer_id,
            "status": self.status,
            "bank_account_last_4": self.bank_account_last_4,
            "initiated_at": self.initiated_at.isoformat() if self.initiated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "failure_reason": self.failure_reason,
        }
