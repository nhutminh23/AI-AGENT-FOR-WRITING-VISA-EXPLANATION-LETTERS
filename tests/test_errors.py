"""Tests for core/errors.py — custom exception handling."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.errors import QuotaExhaustedError, is_quota_error, check_and_raise_quota


class TestQuotaExhaustedError:
    """Test custom exception type."""

    def test_is_exception(self):
        assert issubclass(QuotaExhaustedError, Exception)

    def test_can_raise_and_catch(self):
        with pytest.raises(QuotaExhaustedError):
            raise QuotaExhaustedError("test")

    def test_preserves_message(self):
        try:
            raise QuotaExhaustedError("quota exceeded")
        except QuotaExhaustedError as e:
            assert "quota exceeded" in str(e)


class TestIsQuotaError:
    """Test quota error detection from exception messages."""

    def test_insufficient_quota(self):
        assert is_quota_error(Exception("insufficient_quota"))

    def test_rate_limit(self):
        assert is_quota_error(Exception("rate_limit_exceeded"))

    def test_429_error(self):
        assert is_quota_error(Exception("Error 429: Too Many Requests"))

    def test_billing_error(self):
        assert is_quota_error(Exception("billing limit reached"))

    def test_exceeded_error(self):
        assert is_quota_error(Exception("quota exceeded"))

    def test_ratelimiterror(self):
        assert is_quota_error(Exception("RateLimitError"))

    def test_normal_error_not_quota(self):
        assert not is_quota_error(Exception("file not found"))

    def test_empty_message(self):
        assert not is_quota_error(Exception(""))

    def test_case_insensitive(self):
        assert is_quota_error(Exception("INSUFFICIENT_QUOTA"))


class TestCheckAndRaiseQuota:
    """Test check_and_raise_quota re-raise behavior."""

    def test_raises_on_quota_error(self):
        with pytest.raises(QuotaExhaustedError):
            check_and_raise_quota(Exception("insufficient_quota"))

    def test_no_raise_on_normal_error(self):
        # Should not raise anything
        check_and_raise_quota(Exception("file not found"))

    def test_preserves_original_via_chain(self):
        original = Exception("429 rate limit")
        try:
            check_and_raise_quota(original)
        except QuotaExhaustedError as e:
            assert e.__cause__ is original
