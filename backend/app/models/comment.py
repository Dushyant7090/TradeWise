"""
Comment model
"""
import uuid
from datetime import datetime, timezone
from app import db


class Comment(db.Model):
    __tablename__ = "comments_threads"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trade_id = db.Column(
        db.String(36), db.ForeignKey("trades.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content = db.Column(db.Text, nullable=False)
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
    trade = db.relationship("Trade", back_populates="comments")
    user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "trade_id": self.trade_id,
            "user_id": self.user_id,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
