"""
Email notification service using Flask-Mail
"""
import logging
from flask import current_app, render_template_string
from flask_mail import Message
from app import mail

logger = logging.getLogger(__name__)

# Email templates

NEW_SUBSCRIBER_TEMPLATE = """
<h2>New Subscriber Alert 🎉</h2>
<p>Hello {{ trader_name }},</p>
<p>You have a new subscriber: <strong>{{ subscriber_name }}</strong> has subscribed to your pro trader feed.</p>
<p>Keep up the great work!</p>
<p>— TradeWise Team</p>
"""

TRADE_FLAGGED_TEMPLATE = """
<h2>Trade Flagged ⚠️</h2>
<p>Hello {{ trader_name }},</p>
<p>Your trade on <strong>{{ symbol }}</strong> has been flagged by a user.</p>
<p>Reason: {{ reason }}</p>
<p>Please review and ensure your trade signal complies with platform guidelines.</p>
<p>— TradeWise Team</p>
"""

PAYOUT_CONFIRMATION_TEMPLATE = """
<h2>Payout Confirmation ✅</h2>
<p>Hello {{ trader_name }},</p>
<p>Your withdrawal of <strong>₹{{ amount }}</strong> has been successfully processed.</p>
<p>Transfer ID: {{ transfer_id }}</p>
<p>It will reflect in your bank account within 1-3 business days.</p>
<p>— TradeWise Team</p>
"""

PAYOUT_FAILED_TEMPLATE = """
<h2>Payout Failed ❌</h2>
<p>Hello {{ trader_name }},</p>
<p>Your withdrawal of <strong>₹{{ amount }}</strong> could not be processed.</p>
<p>Reason: {{ reason }}</p>
<p>Please check your bank details and try again.</p>
<p>— TradeWise Team</p>
"""

KYC_VERIFIED_TEMPLATE = """
<h2>KYC Verified ✅</h2>
<p>Hello {{ trader_name }},</p>
<p>Your KYC verification has been approved. You can now initiate payouts from your wallet.</p>
<p>— TradeWise Team</p>
"""

KYC_REJECTED_TEMPLATE = """
<h2>KYC Rejected ❌</h2>
<p>Hello {{ trader_name }},</p>
<p>Your KYC verification was rejected. Reason: {{ reason }}</p>
<p>Please re-submit your documents with the necessary corrections.</p>
<p>— TradeWise Team</p>
"""

PASSWORD_CHANGED_TEMPLATE = """
<h2>Password Changed 🔐</h2>
<p>Hello,</p>
<p>Your TradeWise account password has been changed successfully.</p>
<p>If you did not make this change, please contact support immediately.</p>
<p>— TradeWise Team</p>
"""


def send_email(to: str, subject: str, html_body: str):
    """Send an email using Flask-Mail."""
    try:
        msg = Message(
            subject=subject,
            recipients=[to],
            html=html_body,
            sender=current_app.config.get("MAIL_DEFAULT_SENDER", "noreply@tradewise.com"),
        )
        mail.send(msg)
        logger.info(f"Email sent to {to}: {subject}")
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")


def _render(template: str, **kwargs) -> str:
    return render_template_string(template, **kwargs)


def send_new_subscriber_email(trader_email: str, trader_name: str, subscriber_name: str):
    html = _render(NEW_SUBSCRIBER_TEMPLATE, trader_name=trader_name, subscriber_name=subscriber_name)
    send_email(trader_email, "New Subscriber on TradeWise 🎉", html)


def send_trade_flagged_email(trader_email: str, trader_name: str, symbol: str, reason: str):
    html = _render(TRADE_FLAGGED_TEMPLATE, trader_name=trader_name, symbol=symbol, reason=reason)
    send_email(trader_email, f"Trade Flagged: {symbol} ⚠️", html)


def send_payout_confirmation_email(trader_email: str, trader_name: str, amount: float, transfer_id: str):
    html = _render(PAYOUT_CONFIRMATION_TEMPLATE, trader_name=trader_name, amount=amount, transfer_id=transfer_id)
    send_email(trader_email, "Payout Successful ✅", html)


def send_payout_failed_email(trader_email: str, trader_name: str, amount: float, reason: str):
    html = _render(PAYOUT_FAILED_TEMPLATE, trader_name=trader_name, amount=amount, reason=reason)
    send_email(trader_email, "Payout Failed ❌", html)


def send_kyc_verified_email(trader_email: str, trader_name: str):
    html = _render(KYC_VERIFIED_TEMPLATE, trader_name=trader_name)
    send_email(trader_email, "KYC Verification Approved ✅", html)


def send_kyc_rejected_email(trader_email: str, trader_name: str, reason: str):
    html = _render(KYC_REJECTED_TEMPLATE, trader_name=trader_name, reason=reason)
    send_email(trader_email, "KYC Verification Rejected ❌", html)


def send_password_changed_email(user_email: str):
    html = _render(PASSWORD_CHANGED_TEMPLATE)
    send_email(user_email, "Password Changed 🔐", html)
