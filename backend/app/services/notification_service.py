"""
In-app Notification service
"""
import logging
from datetime import datetime, timezone
from app import db
from app.models.notification import Notification
from app.models.notification_preferences import NotificationPreferences

logger = logging.getLogger(__name__)


def create_notification(
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    data: dict | None = None,
) -> Notification:
    """Create an in-app notification for a user."""
    notif = Notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        message=message,
        data=data or {},
    )
    db.session.add(notif)
    db.session.commit()
    return notif


def notify_new_subscriber(trader_id: str, subscriber_display_name: str, subscriber_id: str):
    """Notify trader of a new subscriber (in-app + email)."""
    from app.models.user import User
    from app.models.profile import Profile
    from app.services.email_service import send_new_subscriber_email

    prefs = NotificationPreferences.query.filter_by(user_id=trader_id).first()

    if not prefs or prefs.in_app_new_subscriber:
        create_notification(
            user_id=trader_id,
            notification_type="new_subscriber",
            title="New Subscriber!",
            message=f"{subscriber_display_name} has subscribed to your pro trader feed.",
            data={"subscriber_id": subscriber_id},
        )

    if not prefs or prefs.email_new_subscriber:
        trader = User.query.get(trader_id)
        trader_profile = Profile.query.filter_by(user_id=trader_id).first()
        if trader:
            try:
                send_new_subscriber_email(
                    trader_email=trader.email,
                    trader_name=trader_profile.display_name if trader_profile else "Trader",
                    subscriber_name=subscriber_display_name,
                )
            except Exception as e:
                logger.error(f"Email notification error: {e}")


def notify_trade_flagged(trader_id: str, trade_id: str, symbol: str, reason: str):
    """Notify trader their trade has been flagged."""
    from app.models.user import User
    from app.models.profile import Profile
    from app.services.email_service import send_trade_flagged_email

    prefs = NotificationPreferences.query.filter_by(user_id=trader_id).first()

    if not prefs or prefs.in_app_trade_flagged:
        create_notification(
            user_id=trader_id,
            notification_type="trade_flagged",
            title="Trade Flagged",
            message=f"Your trade on {symbol} has been flagged. Reason: {reason}",
            data={"trade_id": trade_id, "symbol": symbol},
        )

    if not prefs or prefs.email_trade_flagged:
        trader = User.query.get(trader_id)
        trader_profile = Profile.query.filter_by(user_id=trader_id).first()
        if trader:
            try:
                send_trade_flagged_email(
                    trader_email=trader.email,
                    trader_name=trader_profile.display_name if trader_profile else "Trader",
                    symbol=symbol,
                    reason=reason,
                )
            except Exception as e:
                logger.error(f"Email notification error: {e}")


def notify_payout_result(trader_id: str, amount: float, success: bool, transfer_id: str = "", reason: str = ""):
    """Notify trader of payout success or failure."""
    from app.models.user import User
    from app.models.profile import Profile
    from app.services.email_service import send_payout_confirmation_email, send_payout_failed_email

    prefs = NotificationPreferences.query.filter_by(user_id=trader_id).first()
    notif_type = "payout_confirmation" if success else "payout_failed"
    title = "Payout Successful ✅" if success else "Payout Failed ❌"
    message = (
        f"Your withdrawal of ₹{amount:.2f} has been processed successfully."
        if success
        else f"Your withdrawal of ₹{amount:.2f} failed. Reason: {reason}"
    )

    if not prefs or prefs.in_app_payout_confirmation:
        create_notification(
            user_id=trader_id,
            notification_type=notif_type,
            title=title,
            message=message,
            data={"amount": amount, "transfer_id": transfer_id},
        )

    if not prefs or prefs.email_payout_confirmation:
        trader = User.query.get(trader_id)
        trader_profile = Profile.query.filter_by(user_id=trader_id).first()
        if trader:
            try:
                if success:
                    send_payout_confirmation_email(
                        trader_email=trader.email,
                        trader_name=trader_profile.display_name if trader_profile else "Trader",
                        amount=amount,
                        transfer_id=transfer_id,
                    )
                else:
                    send_payout_failed_email(
                        trader_email=trader.email,
                        trader_name=trader_profile.display_name if trader_profile else "Trader",
                        amount=amount,
                        reason=reason,
                    )
            except Exception as e:
                logger.error(f"Email notification error: {e}")
