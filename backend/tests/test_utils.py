"""
Tests for utility functions
"""
import pytest
from app.utils.validators import (
    validate_email,
    validate_password,
    validate_ifsc_code,
    validate_rationale,
    validate_bio,
    count_words,
)
from app.utils.accuracy import calculate_rrr


class TestValidators:
    def test_valid_email(self):
        assert validate_email("user@example.com") is True
        assert validate_email("user.name+tag@domain.co.in") is True

    def test_invalid_email(self):
        assert validate_email("notanemail") is False
        assert validate_email("@domain.com") is False
        assert validate_email("user@") is False
        assert validate_email("") is False

    def test_valid_password(self):
        ok, msg = validate_password("TestPass1")
        assert ok is True
        assert msg == ""

    def test_short_password(self):
        ok, msg = validate_password("Ab1")
        assert ok is False
        assert "8 characters" in msg

    def test_password_no_uppercase(self):
        ok, msg = validate_password("testpass1")
        assert ok is False
        assert "uppercase" in msg

    def test_password_no_digit(self):
        ok, msg = validate_password("TestPassWord")
        assert ok is False
        assert "digit" in msg

    def test_valid_ifsc(self):
        assert validate_ifsc_code("SBIN0001234") is True
        assert validate_ifsc_code("HDFC0000001") is True

    def test_invalid_ifsc(self):
        assert validate_ifsc_code("SBIN001234") is False  # Wrong format
        assert validate_ifsc_code("1BIN0001234") is False  # Starts with digit

    def test_count_words(self):
        assert count_words("hello world") == 2
        assert count_words("one two three four five") == 5

    def test_validate_rationale_ok(self):
        text = " ".join(["word"] * 55)
        ok, msg = validate_rationale(text)
        assert ok is True

    def test_validate_rationale_too_short(self):
        text = " ".join(["word"] * 10)
        ok, msg = validate_rationale(text)
        assert ok is False
        assert "50 words" in msg

    def test_validate_bio_ok(self):
        bio = "A" * 110
        ok, msg = validate_bio(bio)
        assert ok is True

    def test_validate_bio_too_short(self):
        bio = "Short bio"
        ok, msg = validate_bio(bio)
        assert ok is False


class TestCalculateRRR:
    def test_buy_rrr(self):
        rrr = calculate_rrr("buy", entry=2500.0, stop_loss=2400.0, target=2700.0)
        # risk = 100, reward = 200 => RRR = 2.0
        assert rrr == 2.0

    def test_sell_rrr(self):
        rrr = calculate_rrr("sell", entry=3500.0, stop_loss=3600.0, target=3300.0)
        # risk = 100, reward = 200 => RRR = 2.0
        assert rrr == 2.0

    def test_zero_risk(self):
        # risk = 0 => should return 0
        rrr = calculate_rrr("buy", entry=2500.0, stop_loss=2500.0, target=2700.0)
        assert rrr == 0.0
