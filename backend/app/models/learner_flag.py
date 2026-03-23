"""
Learner Flag model
"""
import uuid
from datetime import datetime, timezone
from app import db


class LearnerFlag(db.Model):
    __tablename__ = "learner_flags"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    learner_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trade_id = db.Column(
        db.String(36), db.ForeignKey("trades.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)
    admin_action = db.Column(db.String(20), nullable=True)  # none / warning / penalty / suspension
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    VALID_STATUSES = ["pending", "investigating", "resolved"]
    VALID_ADMIN_ACTIONS = ["none", "warning", "penalty", "suspension"]

    def to_dict(self):
        return {
            "id": self.id,
            "learner_id": self.learner_id,
            "trade_id": self.trade_id,
            "reason": self.reason,
            "status": self.status,
            "admin_action": self.admin_action,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }
