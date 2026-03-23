"""
Services package
"""
from app.services.cashfree import cashfree_service, cashfree_payout_service
from app.services.supabase_storage import supabase_storage
from app.services.email_service import (
    send_new_subscriber_email,
    send_trade_flagged_email,
    send_payout_confirmation_email,
    send_payout_failed_email,
    send_kyc_verified_email,
    send_kyc_rejected_email,
    send_password_changed_email,
)
from app.services.notification_service import (
    create_notification,
    notify_new_subscriber,
    notify_trade_flagged,
    notify_payout_result,
)

__all__ = [
    "cashfree_service",
    "cashfree_payout_service",
    "supabase_storage",
    "send_new_subscriber_email",
    "send_trade_flagged_email",
    "send_payout_confirmation_email",
    "send_payout_failed_email",
    "send_kyc_verified_email",
    "send_kyc_rejected_email",
    "send_password_changed_email",
    "create_notification",
    "notify_new_subscriber",
    "notify_trade_flagged",
    "notify_payout_result",
]
