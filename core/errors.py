"""
Custom error types shared across the application.
"""
from __future__ import annotations


class QuotaExhaustedError(Exception):
    """Raised when an AI API quota/rate-limit is hit."""
    pass


def is_quota_error(exc: Exception) -> bool:
    """Check if an exception indicates an API quota/rate-limit error."""
    msg = str(exc).lower()
    keywords = [
        "insufficient_quota",
        "rate_limit",
        "429",
        "billing",
        "exceeded",
        "ratelimiterror",
    ]
    return any(k in msg for k in keywords)


def check_and_raise_quota(exc: Exception) -> None:
    """Re-raise as QuotaExhaustedError if it's a quota error."""
    if is_quota_error(exc):
        raise QuotaExhaustedError(str(exc)) from exc
