"""
Shared helper functions used across multiple route blueprints.
Consolidates duplicated code from server.py, routes/pipeline.py,
routes/precheck.py, routes/booking.py.
"""
from __future__ import annotations

import os
from typing import Dict, List

from core.agents import detect_domain


# ── Model helpers ──

def get_text_model() -> str:
    """Model for text reasoning/writing tasks (gpt-5-mini default)."""
    return os.getenv("TEXT_MODEL",
                     os.getenv("OPENAI_MODEL", "gpt-5-mini"))


def get_vision_model() -> str:
    """Model for image/OCR tasks (gpt-4o-mini default — cheaper, good at vision)."""
    return os.getenv("VISION_MODEL",
                     os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini"))


# ── File helpers ──

def list_input_files(input_dir: str) -> List[Dict[str, str]]:
    """Walk input_dir and return a list of file dicts with name, rel_path, path, domain."""
    items: List[Dict[str, str]] = []
    for root, _, filenames in os.walk(input_dir):
        for fname in filenames:
            path = os.path.join(root, fname)
            rel_path = os.path.relpath(path, input_dir).replace("\\", "/")
            items.append(
                {
                    "name": fname,
                    "rel_path": rel_path,
                    "path": path,
                    "domain": detect_domain(fname),
                }
            )
    return items


def cache_dir(output_path: str) -> str:
    """Return the cache directory sibling to output_path."""
    return os.path.join(os.path.dirname(output_path), "cache")
