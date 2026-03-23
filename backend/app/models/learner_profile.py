"""
Learner Profile model
"""
import uuid
from datetime import datetime, timezone
from app import db


class LearnerProfile(db.Model):
    __tablename__ = "learner_profiles"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    interests = db.Column(db.JSON, nullable=True, default=list)
    experience_level = db.Column(db.String(20), default="beginner", nullable=False)
    credits = db.Column(db.Integer, default=7, nullable=False)
    total_unlocked_trades = db.Column(db.Integer, default=0, nullable=False)
    total_spent = db.Column(db.Numeric(12, 2), default=0.0, nullable=False)
    favorite_traders = db.Column(db.JSON, nullable=True, default=list)
    learning_goal = db.Column(db.Text, nullable=True)
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

    # Relationships
    user = db.relationship("User", foreign_keys=[user_id])

    VALID_EXPERIENCE_LEVELS = ["beginner", "intermediate", "advanced"]

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "interests": self.interests or [],
            "experience_level": self.experience_level,
            "credits": self.credits,
            "total_unlocked_trades": self.total_unlocked_trades,
            "total_spent": float(self.total_spent or 0),
            "favorite_traders": self.favorite_traders or [],
            "learning_goal": self.learning_goal,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
