"""
Application configuration.
Centralizes all config values and environment variables.
"""
from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Flask application configuration."""

    # --- Server ---
    HOST = "127.0.0.1"
    PORT = 8000
    DEBUG = True

    # --- AI Models ---
    TEXT_MODEL = os.getenv("TEXT_MODEL", "gpt-5-mini")
    VISION_MODEL = os.getenv("VISION_MODEL", "gpt-4o-mini")

    # --- API Keys ---
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")

    # --- Directories ---
    INPUT_DIR = "pdf/input"
    OUTPUT_DIR = "output"
    BOOKING_INPUT_DIR = "booking/input"
    SPLITTER_UPLOADS_DIR = "splitter_uploads"
    SPLITTER_OUTPUTS_DIR = "splitter_outputs"
    TRANSLATION_TEMPLATE_DIR = os.path.join("dich", "HTML template")
    TRANSLATION_OUTPUT_DIR = os.path.join("dich", "output")

    # --- OCR ---
    OCR_DPI = 250
    OCR_MAX_WORKERS = 4
