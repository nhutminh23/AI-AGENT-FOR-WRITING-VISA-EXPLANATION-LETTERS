"""Tests for config.py — verify all constants exist and have correct types."""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config


class TestConfigServer:
    """Test server configuration constants."""

    def test_host_is_string(self):
        assert isinstance(Config.HOST, str)
        assert Config.HOST == "127.0.0.1"

    def test_port_is_int(self):
        assert isinstance(Config.PORT, int)
        assert Config.PORT == 8000

    def test_debug_is_bool(self):
        assert isinstance(Config.DEBUG, bool)


class TestConfigAIModels:
    """Test AI model configuration."""

    def test_text_model_exists(self):
        assert isinstance(Config.TEXT_MODEL, str)
        assert len(Config.TEXT_MODEL) > 0

    def test_vision_model_exists(self):
        assert isinstance(Config.VISION_MODEL, str)
        assert len(Config.VISION_MODEL) > 0


class TestConfigAPIKeys:
    """Test API key configuration loads from env."""

    def test_openai_key_is_string(self):
        assert isinstance(Config.OPENAI_API_KEY, str)

    def test_serpapi_key_is_string(self):
        assert isinstance(Config.SERPAPI_KEY, str)


class TestConfigDirectories:
    """Test all 13 directory constants exist and are strings."""

    def test_input_dir(self):
        assert isinstance(Config.INPUT_DIR, str)
        assert "input" in Config.INPUT_DIR

    def test_output_dir(self):
        assert isinstance(Config.OUTPUT_DIR, str)

    def test_pdf_output_dir(self):
        assert isinstance(Config.PDF_OUTPUT_DIR, str)
        assert "output" in Config.PDF_OUTPUT_DIR

    def test_booking_input_dir(self):
        assert isinstance(Config.BOOKING_INPUT_DIR, str)
        assert "booking" in Config.BOOKING_INPUT_DIR

    def test_splitter_uploads_dir(self):
        assert isinstance(Config.SPLITTER_UPLOADS_DIR, str)

    def test_splitter_outputs_dir(self):
        assert isinstance(Config.SPLITTER_OUTPUTS_DIR, str)

    def test_scan_splitter_outputs_dir(self):
        assert isinstance(Config.SCAN_SPLITTER_OUTPUTS_DIR, str)

    def test_classifier_input_dir(self):
        assert isinstance(Config.CLASSIFIER_INPUT_DIR, str)

    def test_classifier_output_dir(self):
        assert isinstance(Config.CLASSIFIER_OUTPUT_DIR, str)

    def test_classifier_temp_output_dir(self):
        assert isinstance(Config.CLASSIFIER_TEMP_OUTPUT_DIR, str)

    def test_translation_template_dir(self):
        assert isinstance(Config.TRANSLATION_TEMPLATE_DIR, str)

    def test_translation_default_template(self):
        assert isinstance(Config.TRANSLATION_DEFAULT_TEMPLATE, str)
        assert Config.TRANSLATION_DEFAULT_TEMPLATE == "a4.html"

    def test_translation_output_dir(self):
        assert isinstance(Config.TRANSLATION_OUTPUT_DIR, str)

    def test_translation_html_save_dir(self):
        assert isinstance(Config.TRANSLATION_HTML_SAVE_DIR, str)

    def test_all_13_dir_constants_exist(self):
        """Verify exactly 13 directory constants are defined."""
        dir_attrs = [
            "INPUT_DIR", "OUTPUT_DIR", "PDF_OUTPUT_DIR", "BOOKING_INPUT_DIR",
            "SPLITTER_UPLOADS_DIR", "SPLITTER_OUTPUTS_DIR", "SCAN_SPLITTER_OUTPUTS_DIR",
            "CLASSIFIER_INPUT_DIR", "CLASSIFIER_OUTPUT_DIR", "CLASSIFIER_TEMP_OUTPUT_DIR",
            "TRANSLATION_TEMPLATE_DIR", "TRANSLATION_DEFAULT_TEMPLATE",
            "TRANSLATION_OUTPUT_DIR", "TRANSLATION_HTML_SAVE_DIR",
        ]
        for attr in dir_attrs:
            assert hasattr(Config, attr), f"Missing Config.{attr}"


class TestConfigOCR:
    """Test OCR configuration."""

    def test_ocr_dpi(self):
        assert isinstance(Config.OCR_DPI, int)
        assert Config.OCR_DPI > 0

    def test_ocr_max_workers(self):
        assert isinstance(Config.OCR_MAX_WORKERS, int)
        assert Config.OCR_MAX_WORKERS > 0
