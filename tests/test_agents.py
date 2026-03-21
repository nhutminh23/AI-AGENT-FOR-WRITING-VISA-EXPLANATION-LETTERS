"""Tests for core/agents.py — pure functions only (no AI calls)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.agents import detect_domain, _safe_json_loads, _trim_text_for_summary


class TestDetectDomain:
    """Test file domain detection from filename prefixes."""

    # English prefixes
    def test_personal(self):
        assert detect_domain("PERSONAL - passport.pdf") == "personal"

    def test_travel_history(self):
        assert detect_domain("TRAVEL_HISTORY - stamps.pdf") == "travel_history"

    def test_employment(self):
        assert detect_domain("EMPLOYMENT - contract.pdf") == "employment"

    def test_financial(self):
        assert detect_domain("FINANCIAL - bank_statement.pdf") == "financial"

    def test_purpose(self):
        assert detect_domain("PURPOSE - invitation_letter.pdf") == "purpose"

    def test_overview(self):
        assert detect_domain("OVERVIEW - form.pdf") == "overview"

    # Vietnamese prefixes (backward compatible)
    def test_ho_so_ca_nhan(self):
        assert detect_domain("HO SO CA NHAN - cccd.pdf") == "personal"

    def test_lich_su_du_lich(self):
        assert detect_domain("LICH SU DU LICH - old_passport.pdf") == "travel_history"

    def test_cong_viec(self):
        assert detect_domain("CONG VIEC - hop_dong.docx") == "employment"

    def test_tai_chinh(self):
        assert detect_domain("TAI CHINH - sao_ke.pdf") == "financial"

    def test_muc_dich(self):
        assert detect_domain("MUC DICH CHUYEN DI - plan.pdf") == "purpose"

    def test_tong_quan(self):
        assert detect_domain("TONG QUAN - summary.pdf") == "overview"

    # Edge cases
    def test_unknown_prefix(self):
        assert detect_domain("random_file.pdf") == "unknown"

    def test_empty_filename(self):
        assert detect_domain("") == "unknown"

    def test_lowercase_still_matches(self):
        """Prefixes should match case-insensitively."""
        assert detect_domain("personal - doc.pdf") == "personal"

    def test_partial_prefix_no_match(self):
        assert detect_domain("PERSON_doc.pdf") == "unknown"


class TestSafeJsonLoads:
    """Test JSON parsing with fallback."""

    def test_valid_json(self):
        result = _safe_json_loads('{"name": "test"}')
        assert result == {"name": "test"}

    def test_valid_json_array(self):
        result = _safe_json_loads('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_invalid_json_returns_raw(self):
        result = _safe_json_loads("not json at all")
        assert result == {"raw_output": "not json at all"}

    def test_empty_string(self):
        result = _safe_json_loads("")
        assert "raw_output" in result

    def test_nested_json(self):
        result = _safe_json_loads('{"a": {"b": [1, 2]}}')
        assert result["a"]["b"] == [1, 2]


class TestTrimTextForSummary:
    """Test text trimming for summary generation."""

    def test_short_text_unchanged(self):
        text = "Short text"
        assert _trim_text_for_summary(text) == text

    def test_empty_text(self):
        assert _trim_text_for_summary("") == ""

    def test_none_returns_empty(self):
        assert _trim_text_for_summary(None) == ""

    def test_long_text_trimmed(self):
        text = "x" * 20000
        result = _trim_text_for_summary(text)
        assert len(result) < len(text)
        assert "TRUNCATED" in result

    def test_exactly_max_chars_unchanged(self):
        text = "x" * 12000
        assert _trim_text_for_summary(text) == text

    def test_custom_max_chars(self):
        text = "x" * 100
        result = _trim_text_for_summary(text, max_chars=50)
        assert "TRUNCATED" in result
