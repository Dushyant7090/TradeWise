"""
Cashfree Payments and Payouts Service (TEST MODE)
"""
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
import requests
from flask import current_app

logger = logging.getLogger(__name__)


class CashfreeService:
    """Cashfree Payments API integration (sandbox/test mode)."""

    def _get_headers(self):
        return {
            "x-api-version": "2023-08-01",
            "x-client-id": current_app.config["CASHFREE_APP_ID"],
            "x-client-secret": current_app.config["CASHFREE_SECRET_KEY"],
            "Content-Type": "application/json",
        }

    def create_order(self, order_id: str, amount: float, customer_id: str, customer_email: str, customer_phone: str, return_url: str = "") -> dict:
        """Create a Cashfree payment order."""
        url = f"{current_app.config['CASHFREE_BASE_URL']}/orders"
        payload = {
            "order_id": order_id,
            "order_amount": amount,
            "order_currency": "INR",
            "customer_details": {
                "customer_id": customer_id,
                "customer_email": customer_email,
                "customer_phone": customer_phone,
            },
            "order_meta": {
                "return_url": return_url or f"{current_app.config.get('FRONTEND_URL', '')}/payment/callback",
                "notify_url": f"{current_app.config.get('FRONTEND_URL', '')}/api/webhooks/cashfree/payment",
            },
        }
        try:
            resp = requests.post(url, json=payload, headers=self._get_headers(), timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Cashfree create_order error: {e}")
            raise

    def get_order(self, order_id: str) -> dict:
        """Get Cashfree order details."""
        url = f"{current_app.config['CASHFREE_BASE_URL']}/orders/{order_id}"
        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Cashfree get_order error: {e}")
            raise

    def verify_webhook_signature(self, raw_body: bytes, signature: str, timestamp: str) -> bool:
        """Verify Cashfree webhook signature."""
        secret = current_app.config.get("CASHFREE_WEBHOOK_SECRET", "")
        if not secret:
            return True  # Skip verification if no secret configured
        message = timestamp + raw_body.decode("utf-8")
        computed = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(computed, signature)


class CashfreePayoutService:
    """Cashfree Payouts API integration (sandbox/test mode)."""

    _auth_token: str | None = None
    _token_expiry: datetime | None = None

    def _get_auth_token(self) -> str:
        """Authenticate and get bearer token for payouts API."""
        if self._auth_token and self._token_expiry and datetime.now(timezone.utc) < self._token_expiry:
            return self._auth_token

        url = f"{current_app.config['CASHFREE_PAYOUT_BASE_URL']}/payout/v1/authorize"
        headers = {
            "X-Client-Id": current_app.config["CASHFREE_APP_ID"],
            "X-Client-Secret": current_app.config["CASHFREE_SECRET_KEY"],
        }
        try:
            resp = requests.post(url, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            self._auth_token = data["data"]["token"]
            self._token_expiry = datetime.now(timezone.utc).replace(
                second=datetime.now(timezone.utc).second + data["data"].get("expiry", 3600)
            )
            return self._auth_token
        except requests.RequestException as e:
            logger.error(f"Cashfree payout auth error: {e}")
            raise

    def _get_headers(self) -> dict:
        token = self._get_auth_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def initiate_transfer(
        self,
        transfer_id: str,
        amount: float,
        account_number: str,
        ifsc_code: str,
        account_holder_name: str,
        remarks: str = "TradeWise payout",
    ) -> dict:
        """Initiate a bank transfer via Cashfree Payouts."""
        url = f"{current_app.config['CASHFREE_PAYOUT_BASE_URL']}/payout/v1/requestTransfer"
        payload = {
            "beneDetails": {
                "beneId": transfer_id,
                "name": account_holder_name,
                "email": "payout@tradewise.com",
                "phone": "9999999999",
                "bankAccount": account_number,
                "ifsc": ifsc_code,
                "address1": "India",
            },
            "amount": str(amount),
            "transferId": transfer_id,
            "transferMode": "NEFT",
            "remarks": remarks,
        }
        try:
            resp = requests.post(url, json=payload, headers=self._get_headers(), timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Cashfree initiate_transfer error: {e}")
            raise

    def get_transfer_status(self, transfer_id: str) -> dict:
        """Check payout transfer status."""
        url = f"{current_app.config['CASHFREE_PAYOUT_BASE_URL']}/payout/v1/getTransferStatus"
        params = {"transferId": transfer_id}
        try:
            resp = requests.get(url, params=params, headers=self._get_headers(), timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Cashfree get_transfer_status error: {e}")
            raise


cashfree_service = CashfreeService()
cashfree_payout_service = CashfreePayoutService()
