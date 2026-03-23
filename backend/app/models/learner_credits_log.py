"""
Learner Credits Log model
"""
import uuid
from datetime import datetime, timezone
from app import db


class LearnerCreditsLog(db.Model):
    __tablename__ = "learner_credits_log"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    learner_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trade_id = db.Column(
        db.String(36), db.ForeignKey("trades.id", ondelete="SET NULL"), nullable=True
    )
    action = db.Column(db.String(20), nullable=False)  # used / refunded / bonus
    amount = db.Column(db.Integer, nullable=False)
    credits_remaining = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    VALID_ACTIONS = ["used", "refunded", "bonus"]

    def to_dict(self):
        return {
            "id": self.id,
            "learner_id": self.learner_id,
            "trade_id": self.trade_id,
            "action": self.action,
            "amount": self.amount,
            "credits_remaining": self.credits_remaining,
            "reason": self.reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
