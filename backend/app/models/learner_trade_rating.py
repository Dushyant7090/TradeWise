"""
Learner Trade Rating model
"""
import uuid
from datetime import datetime, timezone
from app import db


class LearnerTradeRating(db.Model):
    __tablename__ = "learner_trade_ratings"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    learner_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trade_id = db.Column(
        db.String(36), db.ForeignKey("trades.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating = db.Column(db.Integer, nullable=False)
    review = db.Column(db.Text, nullable=True)
    helpful_count = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        db.UniqueConstraint("learner_id", "trade_id", name="uq_learner_trade_rating"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "learner_id": self.learner_id,
            "trade_id": self.trade_id,
            "rating": self.rating,
            "review": self.review,
            "helpful_count": self.helpful_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
