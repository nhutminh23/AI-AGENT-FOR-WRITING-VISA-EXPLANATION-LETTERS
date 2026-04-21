"""
Shared constants and helper functions for booking routes.
"""
from __future__ import annotations

import os

from core.helpers import get_text_model, get_vision_model  # noqa: F401  — re-export
from config import Config


# Base directory (project root, one level up from routes/)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OUTPUT_DIR = os.path.join(_BASE_DIR, "output")


def get_serpapi_key() -> str:
    return Config.SERPAPI_KEY
