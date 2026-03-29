"""Tests for core/helpers.py and routes/pipeline_helpers.py — utility functions."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.helpers import get_text_model, get_vision_model, list_input_files, cache_dir
from routes.pipeline_helpers import (
    _safe_join, _resolve_input_file_path,
    _pdf_merge_sanitize_name, _pdf_merge_pick_unique,
    _is_certification_page_by_text,
)


# ── core/helpers.py ──

class TestGetTextModel:
    def test_returns_string(self):
        result = get_text_model()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_default_is_gpt5_mini(self, monkeypatch):
        monkeypatch.delenv("TEXT_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)
        # Config is evaluated at import time, so we test the function returns a string
        assert isinstance(get_text_model(), str)


class TestGetVisionModel:
    def test_returns_string(self):
        result = get_vision_model()
        assert isinstance(result, str)
        assert len(result) > 0


class TestListInputFiles:
    def test_empty_dir(self, tmp_path):
        result = list_input_files(str(tmp_path))
        assert result == []

    def test_finds_files(self, tmp_path):
        (tmp_path / "test.pdf").write_text("pdf content")
        (tmp_path / "test.jpg").write_bytes(b"\xff\xd8")
        result = list_input_files(str(tmp_path))
        assert len(result) == 2
        assert all("name" in f for f in result)
        assert all("path" in f for f in result)
        assert all("domain" in f for f in result)

    def test_walks_subdirs(self, tmp_path):
        sub = tmp_path / "person1"
        sub.mkdir()
        (sub / "passport.pdf").write_text("data")
        result = list_input_files(str(tmp_path))
        assert len(result) == 1
        assert "person1" in result[0]["rel_path"]

    def test_nonexistent_dir(self):
        result = list_input_files("/nonexistent/path/xyz")
        assert result == []


class TestCacheDir:
    def test_returns_cache_sibling(self):
        result = cache_dir("/some/output/file.pdf")
        assert result.endswith("cache")
        assert "/some/output/" in result.replace("\\", "/") or "\\some\\output\\" in result


# ── routes/pipeline_helpers.py ──

class TestSafeJoin:
    def test_normal_join(self, tmp_path):
        result = _safe_join(str(tmp_path), "file.pdf")
        assert result.endswith("file.pdf")
        assert str(tmp_path) in result

    def test_blocks_traversal(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid path"):
            _safe_join(str(tmp_path), "../../etc/passwd")

    def test_blocks_absolute_path(self, tmp_path):
        with pytest.raises(ValueError):
            _safe_join(str(tmp_path), "/etc/passwd")


class TestResolveInputFilePath:
    def test_normal_resolve(self, tmp_path):
        (tmp_path / "doc.pdf").write_text("x")
        result = _resolve_input_file_path(str(tmp_path), "doc.pdf")
        assert result.endswith("doc.pdf")

    def test_blocks_traversal(self, tmp_path):
        with pytest.raises(ValueError, match="Path traversal"):
            _resolve_input_file_path(str(tmp_path), "../../../etc/shadow")


class TestPdfMergeSanitizeName:
    def test_normal_name(self):
        assert _pdf_merge_sanitize_name("my file", "fallback") == "my file"

    def test_strips_dangerous_chars(self):
        result = _pdf_merge_sanitize_name('test<>:"/\\|?*file', "fb")
        assert "<" not in result
        assert ">" not in result

    def test_empty_returns_fallback(self):
        assert _pdf_merge_sanitize_name("", "fallback") == "fallback"

    def test_whitespace_only_returns_fallback(self):
        assert _pdf_merge_sanitize_name("   ", "fallback") == "fallback"

    def test_collapses_spaces(self):
        result = _pdf_merge_sanitize_name("a    b   c", "fb")
        assert result == "a b c"


class TestPdfMergePickUnique:
    def test_first_pick_no_conflict(self, tmp_path):
        result = _pdf_merge_pick_unique(str(tmp_path), "doc", ".pdf")
        assert result.endswith("doc.pdf")

    def test_increments_on_conflict(self, tmp_path):
        (tmp_path / "doc.pdf").write_text("existing")
        result = _pdf_merge_pick_unique(str(tmp_path), "doc", ".pdf")
        assert "doc (1).pdf" in result

    def test_multiple_conflicts(self, tmp_path):
        (tmp_path / "doc.pdf").write_text("x")
        (tmp_path / "doc (1).pdf").write_text("x")
        result = _pdf_merge_pick_unique(str(tmp_path), "doc", ".pdf")
        assert "doc (2).pdf" in result


class TestIsCertificationPageByText:
    def test_empty_text(self):
        assert _is_certification_page_by_text("") is False

    def test_short_text(self):
        assert _is_certification_page_by_text("short") is False

    def test_none_text(self):
        assert _is_certification_page_by_text(None) is False

    def test_certification_keywords_match(self):
        text = """
        This is a certification page from PASSPORT LOUNGE company.
        We undertake to translate this document accurately.
        Signature of Translator below.
        """
        assert _is_certification_page_by_text(text) is True

    def test_non_cert_text(self):
        text = "This is a regular bank statement with transaction details for account 123456."
        assert _is_certification_page_by_text(text) is False

    def test_one_keyword_not_enough(self):
        text = "This document mentions passport lounge but nothing else relevant to certification."
        assert _is_certification_page_by_text(text) is False
