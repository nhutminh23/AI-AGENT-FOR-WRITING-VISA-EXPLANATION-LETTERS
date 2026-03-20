"""Extract pipeline routes from server.py into routes/pipeline.py"""
import os, re

lines = open('server.py', 'r', encoding='utf-8').readlines()

# Find boundaries: first route after precheck marker, to the booking/splitter markers
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if start_idx is None and line.strip().startswith('@app.post("/api/pipeline/send-to-splitter")'):
        start_idx = i
    if line.strip().startswith("if __name__"):
        end_idx = i
        break

# But we also want to exclude all the redirect comments at end
# Actually find the last real code before the "BOOKING" or "if __name__" markers
for i in range(end_idx - 1, start_idx, -1):
    s = lines[i].strip()
    if s and not s.startswith('#'):
        end_idx = i + 1  # Include this line
        break

print(f"Extracting lines {start_idx+1} to {end_idx} ({end_idx - start_idx} lines)")

chunk = lines[start_idx:end_idx]

header = (
    '"""\n'
    'Pipeline routes: classifier, scan-splitter, pdf-tools, itinerary, run.\n'
    '"""\n'
    'from __future__ import annotations\n'
    '\n'
    'import asyncio\n'
    'import base64\n'
    'import io\n'
    'import json\n'
    'import os\n'
    'import re\n'
    'import shutil\n'
    'import tempfile\n'
    'import traceback\n'
    'import uuid\n'
    'import zipfile\n'
    'from pathlib import Path as SplitterPath\n'
    'from typing import Any, Dict, List, Optional, Tuple\n'
    '\n'
    'from flask import Blueprint, Response, jsonify, request, send_file, send_from_directory\n'
    '\n'
    'from langchain_openai import ChatOpenAI\n'
    'from langchain_core.messages import HumanMessage, SystemMessage\n'
    'from pypdf import PdfReader, PdfWriter\n'
    '\n'
    'import database as db\n'
    'from core.agents import detect_domain\n'
    'from core.errors import QuotaExhaustedError, is_quota_error\n'
    '\n'
    'pipeline_bp = Blueprint("pipeline", __name__)\n'
    '\n'
    '# Base directory (project root, one level up from routes/)\n'
    '_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n'
    '_OUTPUT_DIR = os.path.join(_BASE_DIR, "output")\n'
    '\n'
    '\n'
    'def get_text_model() -> str:\n'
    '    return os.getenv("TEXT_MODEL", "gpt-5-mini")\n'
    '\n'
    '\n'
    'def get_vision_model() -> str:\n'
    '    return os.getenv("VISION_MODEL", "gpt-4o-mini")\n'
    '\n'
    '\n'
    'def _list_input_files(input_dir: str) -> List[Dict[str, str]]:\n'
    '    items: List[Dict[str, str]] = []\n'
    '    for root, _, filenames in os.walk(input_dir):\n'
    '        for fname in filenames:\n'
    '            path = os.path.join(root, fname)\n'
    '            rel_path = os.path.relpath(path, input_dir).replace("\\\\", "/")\n'
    '            items.append(\n'
    '                {\n'
    '                    "name": fname,\n'
    '                    "rel_path": rel_path,\n'
    '                    "path": path,\n'
    '                    "domain": detect_domain(fname),\n'
    '                }\n'
    '            )\n'
    '    return items\n'
    '\n'
    '\n'
    'STEP_ORDER = ["ingest", "summary", "writer"]\n'
    '\n'
    '\n'
    'def _cache_dir(output_path: str) -> str:\n'
    '    return os.path.join(os.path.dirname(output_path), "cache")\n'
    '\n'
    '\n'
    'def _state_path(cache_dir: str) -> str:\n'
    '    return os.path.join(cache_dir, "state.json")\n'
    '\n'
    '\n'
    'def _step_marker_path(cache_dir: str, step: str) -> str:\n'
    '    return os.path.join(cache_dir, f"step_{step}.json")\n'
    '\n'
    '\n'
    'def _reset_downstream_steps(cache_dir: str, step: str) -> None:\n'
    '    if step not in STEP_ORDER:\n'
    '        return\n'
    '    idx = STEP_ORDER.index(step)\n'
    '    downstream = STEP_ORDER[idx + 1:]\n'
    '    for ds in downstream:\n'
    '        marker = _step_marker_path(cache_dir, ds)\n'
    '        if os.path.exists(marker):\n'
    '            os.remove(marker)\n'
    '\n'
    '\n'
    'def _check_and_raise_quota(response):\n'
    '    """Check response for quota errors and raise if found."""\n'
    '    if hasattr(response, "response_metadata"):\n'
    '        meta = response.response_metadata or {}\n'
    '        finish = meta.get("finish_reason", "")\n'
    '        if finish == "error":\n'
    '            raise QuotaExhaustedError("API quota exceeded")\n'
    '\n'
)

content = ''.join(chunk)

# Replace @app. with @pipeline_bp.
content = content.replace('@app.get(', '@pipeline_bp.get(')
content = content.replace('@app.post(', '@pipeline_bp.post(')
content = content.replace('@app.put(', '@pipeline_bp.put(')
content = content.replace('@app.delete(', '@pipeline_bp.delete(')
content = content.replace('@app.route(', '@pipeline_bp.route(')

# Fix __file__ references
content = content.replace('os.path.dirname(os.path.abspath(__file__))', '_BASE_DIR')
content = content.replace('os.path.dirname(__file__)', '_BASE_DIR')
content = content.replace("SplitterPath(__file__).parent", "SplitterPath(_BASE_DIR)")

# Remove section comments
for s in [
    '# ==================== PIPELINE CONNECTION ENDPOINTS ====================',
    '# ==================== BOOKING ENDPOINTS -> routes/booking.py ====================',
    '# ==================== SPLITTER ENDPOINTS -> routes/splitter.py ====================',
]:
    content = content.replace(s, '')

with open('routes/pipeline.py', 'w', encoding='utf-8') as f:
    f.write(header + content)

with open('routes/pipeline.py', 'r', encoding='utf-8') as f:
    n = sum(1 for _ in f)
print(f'Created routes/pipeline.py with {n} lines')
