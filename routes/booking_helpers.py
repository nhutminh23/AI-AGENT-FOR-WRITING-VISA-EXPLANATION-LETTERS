"""
Shared constants and helper functions for booking routes.
"""
from __future__ import annotations

import os


# Base directory (project root, one level up from routes/)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OUTPUT_DIR = os.path.join(_BASE_DIR, "output")


def get_text_model() -> str:
    return os.getenv("TEXT_MODEL", "gpt-5-mini")


def get_vision_model() -> str:
    return os.getenv("VISION_MODEL", "gpt-4o-mini")


def get_serpapi_key() -> str:
    return os.getenv("SERPAPI_KEY", "")
