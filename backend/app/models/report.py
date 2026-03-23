"""
Report model
"""
import uuid
from datetime import datetime, timezone
from app import db


class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trade_id = db.Column(
        db.String(36), db.ForeignKey("trades.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reporter_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)
    admin_verdict = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships
    trade = db.relationship("Trade", back_populates="reports")
    reporter = db.relationship("User", foreign_keys=[reporter_id])

    VALID_STATUSES = ["pending", "investigating", "resolved"]

    def to_dict(self):
        return {
            "id": self.id,
            "trade_id": self.trade_id,
            "reporter_id": self.reporter_id,
            "reason": self.reason,
            "status": self.status,
            "admin_verdict": self.admin_verdict,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }
