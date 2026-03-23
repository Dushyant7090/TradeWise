"""
Trade model
"""
import uuid
from datetime import datetime, timezone
from app import db


class Trade(db.Model):
    __tablename__ = "trades"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trader_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol = db.Column(db.String(30), nullable=False)
    direction = db.Column(db.String(4), nullable=False)  # buy / sell
    entry_price = db.Column(db.Numeric(16, 4), nullable=False)
    stop_loss_price = db.Column(db.Numeric(16, 4), nullable=False)
    target_price = db.Column(db.Numeric(16, 4), nullable=False)
    rrr = db.Column(db.Numeric(8, 4), nullable=False)
    technical_rationale = db.Column(db.Text, nullable=False)
    chart_image_url = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(20), default="active", nullable=False, index=True)
    outcome = db.Column(db.String(10), nullable=True)  # win / loss / null

    view_count = db.Column(db.Integer, default=0)
    unlock_count = db.Column(db.Integer, default=0)
    flag_count = db.Column(db.Integer, default=0)

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    closed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    closed_by_trader_at = db.Column(db.DateTime(timezone=True), nullable=True)
    close_reason = db.Column(db.Text, nullable=True)

    # Relationships
    trader = db.relationship("User", back_populates="trades")
    comments = db.relationship("Comment", back_populates="trade", cascade="all, delete-orphan")
    reports = db.relationship("Report", back_populates="trade", cascade="all, delete-orphan")

    VALID_DIRECTIONS = ["buy", "sell"]
    VALID_STATUSES = ["active", "target_hit", "sl_hit", "cancelled"]
    VALID_OUTCOMES = ["win", "loss"]

    def to_dict(self):
        return {
            "id": self.id,
            "trader_id": self.trader_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": float(self.entry_price),
            "stop_loss_price": float(self.stop_loss_price),
            "target_price": float(self.target_price),
            "rrr": float(self.rrr),
            "technical_rationale": self.technical_rationale,
            "chart_image_url": self.chart_image_url,
            "status": self.status,
            "outcome": self.outcome,
            "view_count": self.view_count,
            "unlock_count": self.unlock_count,
            "flag_count": self.flag_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "closed_by_trader_at": self.closed_by_trader_at.isoformat() if self.closed_by_trader_at else None,
            "close_reason": self.close_reason,
        }
