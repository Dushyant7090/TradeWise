"""
Pro Trader Profile model
"""
import uuid
from datetime import datetime, timezone
from app import db


class ProTraderProfile(db.Model):
    __tablename__ = "pro_trader_profiles"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    bio = db.Column(db.Text, nullable=True)
    specializations = db.Column(db.JSON, nullable=True, default=list)
    external_portfolio_url = db.Column(db.Text, nullable=True)
    years_of_experience = db.Column(db.Integer, default=0)
    trading_style = db.Column(
        db.String(30),
        nullable=True,
    )
    # Bank details (encrypted)
    bank_account_number_encrypted = db.Column(db.Text, nullable=True)
    ifsc_code = db.Column(db.String(20), nullable=True)
    account_holder_name = db.Column(db.String(100), nullable=True)
    bank_account_last_4 = db.Column(db.String(4), nullable=True)

    # KYC
    kyc_status = db.Column(db.String(20), default="pending", nullable=False)
    kyc_documents = db.Column(db.JSON, nullable=True, default=dict)

    # Stats
    accuracy_score = db.Column(db.Float, default=0.0)
    total_trades = db.Column(db.Integer, default=0)
    winning_trades = db.Column(db.Integer, default=0)
    leaderboard_rank = db.Column(db.Integer, nullable=True)
    total_subscribers = db.Column(db.Integer, default=0)

    # Financials
    monthly_subscription_price = db.Column(db.Numeric(12, 2), default=0.0)
    total_earnings = db.Column(db.Numeric(12, 2), default=0.0)
    available_balance = db.Column(db.Numeric(12, 2), default=0.0)

    # Media
    profile_picture_url = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

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
    user = db.relationship("User", back_populates="pro_trader_profile")
    payouts = db.relationship(
        "Payout",
        primaryjoin="ProTraderProfile.user_id == foreign(Payout.trader_id)",
        cascade="all, delete-orphan",
        viewonly=False,
        overlaps="trader",
    )

    VALID_TRADING_STYLES = ["scalping", "intraday", "swing", "positional", "long_term"]
    VALID_KYC_STATUSES = ["pending", "verified", "rejected"]

    def to_dict(self, include_bank=False):
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "bio": self.bio,
            "specializations": self.specializations or [],
            "external_portfolio_url": self.external_portfolio_url,
            "years_of_experience": self.years_of_experience,
            "trading_style": self.trading_style,
            "kyc_status": self.kyc_status,
            "kyc_documents": self.kyc_documents or {},
            "accuracy_score": float(self.accuracy_score or 0),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "leaderboard_rank": self.leaderboard_rank,
            "total_subscribers": self.total_subscribers,
            "monthly_subscription_price": float(self.monthly_subscription_price or 0),
            "total_earnings": float(self.total_earnings or 0),
            "available_balance": float(self.available_balance or 0),
            "profile_picture_url": self.profile_picture_url,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_bank:
            data["bank_account_last_4"] = self.bank_account_last_4
            data["ifsc_code"] = self.ifsc_code
            data["account_holder_name"] = self.account_holder_name
        return data
