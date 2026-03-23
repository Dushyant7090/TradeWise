"""
Encryption utilities for sensitive data (bank account numbers, etc.)
"""
import os
import base64
from cryptography.fernet import Fernet
from flask import current_app


def _get_fernet():
    key = current_app.config.get("ENCRYPTION_KEY", "")
    if not key:
        # Generate a key for development if not set
        key = base64.urlsafe_b64encode(os.urandom(32)).decode()
    # Ensure the key is properly formatted for Fernet
    try:
        fernet_key = key.encode() if isinstance(key, str) else key
        # Fernet requires a 32-byte URL-safe base64 key
        if len(base64.urlsafe_b64decode(fernet_key + b"==")) < 32:
            fernet_key = base64.urlsafe_b64encode(fernet_key.ljust(32)[:32])
        return Fernet(fernet_key)
    except Exception:
        # Fallback: generate a valid key
        return Fernet(Fernet.generate_key())


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value."""
    if not plaintext:
        return ""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt an encrypted string value."""
    if not ciphertext:
        return ""
    f = _get_fernet()
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except Exception:
        return ""


def mask_account_number(account_number: str) -> str:
    """Return only last 4 digits of account number."""
    if not account_number or len(account_number) < 4:
        return "****"
    return "X" * (len(account_number) - 4) + account_number[-4:]
