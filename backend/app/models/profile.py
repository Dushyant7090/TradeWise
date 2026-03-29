"""
Profile model
"""
import uuid
from datetime import datetime, timezone
from app import db


class Profile(db.Model):
    __tablename__ = "profiles"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    role = db.Column(db.String(20), nullable=False, default="public_trader")
    display_name = db.Column(db.String(100), nullable=True)
    avatar_url = db.Column(db.Text, nullable=True)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_banned = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user = db.relationship("User", back_populates="profile")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "role": self.role,
            "display_name": self.display_name,
            "avatar_url": self.avatar_url,
            "is_verified": self.is_verified,
            "is_banned": self.is_banned,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
