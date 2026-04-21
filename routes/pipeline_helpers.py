"""
Shared helpers for pipeline sub-modules:
  - _safe_join: path traversal protection
  - _resolve_input_file_path: resolve filename within input_dir
  - _pdf_merge_sanitize_name / _pdf_merge_pick_unique: PDF merge naming
  - Scan splitter: _get_or_create_llm, _scan_split_progress,
    _is_certification_page_by_text, _batch_detect_cert_pages_vision
"""
from __future__ import annotations
import logging

import json
import os
import re
from typing import Dict

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from core.errors import is_quota_error
from core.helpers import get_vision_model, cache_dir


# ── Path safety ──────────────────────────────────────────────────────

def _safe_join(base: str, rel_path: str) -> str:
    base_abs = os.path.abspath(base)
    candidate = os.path.abspath(os.path.join(base, rel_path))
    if not candidate.startswith(base_abs):
        raise ValueError("Invalid path")
    return candidate


def _resolve_input_file_path(input_dir: str, filename: str) -> str:
    """Safely join input_dir + filename, preventing path traversal."""
    base = os.path.abspath(input_dir)
    full = os.path.abspath(os.path.join(input_dir, filename))
    if not full.startswith(base):
        raise ValueError(f"Path traversal detected: {filename}")
    return full


# ── PDF merge naming helpers ─────────────────────────────────────────

def _pdf_merge_sanitize_name(value: str, fallback: str) -> str:
    text = (value or "").strip()
    text = re.sub(r'[\\/:*?"<>|]+', " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or fallback


def _pdf_merge_pick_unique(dest_dir: str, stem: str, ext: str) -> str:
    candidate = os.path.join(dest_dir, f"{stem}{ext}")
    idx = 1
    while os.path.exists(candidate):
        candidate = os.path.join(dest_dir, f"{stem} ({idx}){ext}")
        idx += 1
    return candidate


# ── Canonical short aliases (used by classifier & splitter) ──────────
_sanitize_name = _pdf_merge_sanitize_name
_pick_unique = _pdf_merge_pick_unique


# ── Quota error helper ───────────────────────────────────────────────

_is_quota_error = is_quota_error
_cache_dir = cache_dir


# ── Scan splitter helpers ────────────────────────────────────────────

_scan_splitter_llm = None

def _get_or_create_llm():
    """Get or create a cached ChatOpenAI instance for vision tasks."""
    global _scan_splitter_llm
    if _scan_splitter_llm is None:
        _scan_splitter_llm = ChatOpenAI(model=get_vision_model(), temperature=0)
    return _scan_splitter_llm


_scan_split_progress: Dict = {"total": 0, "done": 0, "current_page": "", "running": False, "results": [], "error": ""}

# Keywords that identify a Passport Lounge translation certification page
_CERT_KEYWORDS = [
    "passport lounge",
    "undertake to translate",
    "cam đoan đã dịch chính xác",
    "cam doan da dich chinh xac",
    "signature of translator",
    "chữ ký của người dịch",
]


def _is_certification_page_by_text(page_text: str) -> bool:
    """Check if page text contains translation certification keywords."""
    if not page_text or len(page_text.strip()) < 20:
        return False
    text_lower = page_text.lower()
    matches = sum(1 for kw in _CERT_KEYWORDS if kw in text_lower)
    return matches >= 2


def _batch_detect_cert_pages_vision(llm, page_images_b64: list, page_numbers: list) -> list:
    """Batch vision: check multiple pages at once for translation certification.
    Sends bottom 40% crop of each page to save tokens.
    Returns list of page numbers that ARE certification pages."""
    content_parts = [
        {"type": "text", "text": f"""You are analyzing {len(page_images_b64)} scanned document pages.

For EACH page, determine if it is a TRANSLATION CERTIFICATION page.
A translation certification page has ALL of these features:
- Header from "PASSPORT LOUNGE COMPANY LIMITED" (with the Passport Lounge logo)
- A bilingual statement about translating documents accurately
- Translator signature area with company stamp/seal at the bottom

⚠️ IMPORTANT: Do NOT mark pages that have OTHER types of stamps (bank stamps, government stamps, notary stamps). 
ONLY mark pages with the specific PASSPORT LOUNGE translation certification.

Pages shown: {', '.join(str(p) for p in page_numbers)}

Return JSON ONLY: {{"cert_pages": [list of page numbers that ARE certification pages]}}
Example: {{"cert_pages": [2, 5, 8]}} or {{"cert_pages": []}} if none."""}
    ]

    for i, (b64, pnum) in enumerate(zip(page_images_b64, page_numbers)):
        content_parts.append({"type": "text", "text": f"Page {pnum}:"})
        content_parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})

    try:
        result = llm.invoke([
            SystemMessage(content="You are an expert document analyzer. Answer ONLY with JSON."),
            HumanMessage(content=content_parts),
        ])
        text = result.content if hasattr(result, 'content') else str(result)
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        parsed = json.loads(text)
        return parsed.get("cert_pages", [])
    except Exception as e:
        logging.exception("[Safe Log] Unhandled exception in pipeline_helpers.py: %s", e)
        print(f"[SCAN-SPLITTER] ❌ Vision batch error: {e}")
        return []
