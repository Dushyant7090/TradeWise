"""
Input validators
"""
import re


def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_password(password: str) -> tuple[bool, str]:
    """
    Validate password strength.
    Returns (is_valid, error_message).
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit"
    return True, ""


def validate_ifsc_code(ifsc: str) -> bool:
    """Validate Indian IFSC code format (e.g., SBIN0001234)."""
    pattern = r"^[A-Z]{4}0[A-Z0-9]{6}$"
    return bool(re.match(pattern, ifsc.upper()))


def count_words(text: str) -> int:
    """Count words in a text string."""
    return len(text.split())


def validate_rationale(text: str, min_words: int = 50) -> tuple[bool, str]:
    """Validate trade technical rationale has minimum word count."""
    word_count = count_words(text)
    if word_count < min_words:
        return False, f"Technical rationale must be at least {min_words} words (got {word_count})"
    return True, ""


def validate_bio(bio: str, min_chars: int = 100) -> tuple[bool, str]:
    """Validate bio has minimum character count."""
    if len(bio) < min_chars:
        return False, f"Bio must be at least {min_chars} characters (got {len(bio)})"
    return True, ""


def sanitize_string(value: str, max_length: int = 255) -> str:
    """Sanitize and truncate a string value."""
    if not value:
        return ""
    return str(value).strip()[:max_length]
