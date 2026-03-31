"""
Learner Subscription model
"""
import uuid
from datetime import datetime, timezone
from app import db


class LearnerSubscription(db.Model):
    __tablename__ = "learner_subscriptions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    learner_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pro_trader_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status = db.Column(
        db.String(20),
        nullable=False,
        default="active",
    )  # active / cancelled / expired
    started_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        db.UniqueConstraint("learner_id", "pro_trader_id", name="uq_learner_subscription"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "learner_id": self.learner_id,
            "pro_trader_id": self.pro_trader_id,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
