"""
Application configuration.
Centralizes all config values and environment variables.
"""
from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv(override=True)


class Config:
    """Flask application configuration."""

    # --- Server ---
    HOST = "127.0.0.1"
    PORT = 8000
    DEBUG = True

    # --- AI Models ---
    TEXT_MODEL = os.getenv("OPENAI_MODEL") or os.getenv("TEXT_MODEL", "gpt-5-mini")
    VISION_MODEL = os.getenv("OPENAI_VISION_MODEL") or os.getenv("VISION_MODEL", "gpt-4o-mini")

    # --- API Keys ---
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")

    # --- Directories ---
    INPUT_DIR = os.path.join("pdf", "input")
    OUTPUT_DIR = "output"
    PDF_OUTPUT_DIR = os.path.join("pdf", "output")
    BOOKING_INPUT_DIR = os.path.join("booking", "input")
    SPLITTER_UPLOADS_DIR = "splitter_uploads"
    SPLITTER_OUTPUTS_DIR = "splitter_outputs"
    SCAN_SPLITTER_OUTPUTS_DIR = "scan_splitter_outputs"
    CLASSIFIER_INPUT_DIR = os.path.join("phanloai", "input")
    CLASSIFIER_OUTPUT_DIR = os.path.join("phanloai", "output")
    CLASSIFIER_TEMP_OUTPUT_DIR = os.path.join("phanloai", "_temp_output")
    TRANSLATION_TEMPLATE_DIR = os.path.join("dich", "HTML template")
    TRANSLATION_DEFAULT_TEMPLATE = "a4.html"
    TRANSLATION_OUTPUT_DIR = os.path.join("dich", "output")
    TRANSLATION_HTML_SAVE_DIR = os.path.join("dich", "html")

    # --- Canada Forms ---
    CANADA_FORMS_INPUT_DIR = os.path.join("canada_forms", "input")
    CANADA_FORMS_OUTPUT_DIR = os.path.join("canada_forms", "output")
    CANADA_FORMS_TEMPLATE_DIR = os.path.join("canada_forms", "templates")

    # --- Australia Forms ---
    AUSTRALIA_FORMS_OUTPUT_DIR = os.path.join("australia_forms", "output")
    AUSTRALIA_FORMS_TEMPLATE_DIR = os.path.join("australia_forms", "templates")


    # --- Gemini (fallback AI) ---
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    # --- OCR ---
    OCR_DPI = 250
    OCR_MAX_WORKERS = 4

    # --- Google Drive Sync (Traffic Light) ---
    GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    DRIVE_ROOT_FOLDER = os.getenv("DRIVE_ROOT_FOLDER", "HỒ SƠ VISA 2026")
    DRIVE_TRANSLATION_FOLDER = os.getenv("DRIVE_TRANSLATION_FOLDER", "Dịch Thuật")
    DRIVE_TRANSLATION_FOLDER_ID = os.getenv("DRIVE_TRANSLATION_FOLDER_ID", "")
    DRIVE_TRANSLATION_DONE_PREFIX = os.getenv("DRIVE_TRANSLATION_DONE_PREFIX", "DONE")
    DRIVE_POLL_INTERVAL = int(os.getenv("DRIVE_POLL_INTERVAL", "10"))
    DRIVE_LOCAL_INPUT = os.path.join(os.path.dirname(__file__), "input")

    # --- Translation Workspace (Auto-downloaded from Drive) ---
    TRANSLATION_WORKSPACE_DIR = os.path.join(os.path.dirname(__file__), "translation_workspace")
