"""
Utils package
"""
from app.utils.encryption import encrypt_value, decrypt_value, mask_account_number
from app.utils.validators import (
    validate_email,
    validate_password,
    validate_ifsc_code,
    validate_rationale,
    validate_bio,
    sanitize_string,
)


def recalculate_accuracy(*args, **kwargs):
    from app.utils.accuracy import recalculate_accuracy as _recalculate_accuracy

    return _recalculate_accuracy(*args, **kwargs)


def calculate_rrr(*args, **kwargs):
    from app.utils.accuracy import calculate_rrr as _calculate_rrr

    return _calculate_rrr(*args, **kwargs)


def update_leaderboard_ranks(*args, **kwargs):
    from app.utils.accuracy import update_leaderboard_ranks as _update_leaderboard_ranks

    return _update_leaderboard_ranks(*args, **kwargs)

__all__ = [
    "encrypt_value",
    "decrypt_value",
    "mask_account_number",
    "recalculate_accuracy",
    "calculate_rrr",
    "update_leaderboard_ranks",
    "validate_email",
    "validate_password",
    "validate_ifsc_code",
    "validate_rationale",
    "validate_bio",
    "sanitize_string",
]
