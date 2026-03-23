"""
Learner Unlocked Trade model
"""
import uuid
from datetime import datetime, timezone
from app import db


class LearnerUnlockedTrade(db.Model):
    __tablename__ = "learner_unlocked_trades"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    learner_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trade_id = db.Column(
        db.String(36), db.ForeignKey("trades.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unlocked_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    via_credit = db.Column(db.Boolean, default=True, nullable=False)
    viewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    rating = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # Relationships
    learner = db.relationship("User", foreign_keys=[learner_id])
    trade = db.relationship("Trade", foreign_keys=[trade_id])

    __table_args__ = (
        db.UniqueConstraint("learner_id", "trade_id", name="uq_learner_unlocked_trade"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "learner_id": self.learner_id,
            "trade_id": self.trade_id,
            "unlocked_at": self.unlocked_at.isoformat() if self.unlocked_at else None,
            "via_credit": self.via_credit,
            "viewed_at": self.viewed_at.isoformat() if self.viewed_at else None,
            "rating": self.rating,
            "notes": self.notes,
        }
