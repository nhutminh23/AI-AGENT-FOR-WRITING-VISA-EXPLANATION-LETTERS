from __future__ import annotations

import json
import os
import re
import shutil
import base64
import tempfile
import uuid
from io import BytesIO
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_file, send_from_directory
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from core.agents import (
    build_summary_profile,
    detect_domain,
    extract_text_with_openai,
    ingest_files,
    itinerary_writer,
    letter_writer,
)
from core.prompts import (
    OCR_VIETNAMESE_ADMIN_PROMPT,
    OCR_AND_TRANSLATE_PROMPT,
    TRANSLATE_TO_EN_PROMPT,
    TRANSLATION_HTML_RENDER_PROMPT,
)
from classifier.agent import classify_files_in_folder
from pypdf import PdfReader, PdfWriter
from core.state import GraphState
import database as db


load_dotenv()

app = Flask(__name__, static_folder="frontend", static_url_path="")

# Register extracted route blueprints
from routes import register_blueprints
register_blueprints(app)

def get_text_model() -> str:
    """Model for text reasoning/writing tasks (gpt-5-mini default)."""
    return os.getenv("OPENAI_MODEL", "gpt-5-mini")


def get_vision_model() -> str:
    """Model for image/OCR tasks (gpt-4o-mini default — cheaper, good at vision)."""
    return os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")


TRANSLATE_TEMPLATE_DIR = os.path.join("dich", "HTML template")
TRANSLATE_OUTPUT_DIR = os.path.join("output", "translation")
TRANSLATE_HTML_SAVE_DIR = os.path.join("dich", "html")
TRANSLATE_DEFAULT_TEMPLATE = "a4.html"
translation_upload_cache: Dict[str, Dict[str, str]] = {}

def _default_translate_template_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Translated Document</title>
  <style>
    body { margin:0; padding:20px; background:#f3f4f6; font-family:"Times New Roman", serif; }
    .a4-page { width:210mm; min-height:297mm; margin:0 auto; background:#fff; padding:18mm; box-sizing:border-box; box-shadow:0 0 8px rgba(0,0,0,.1); }
    h1 { font-size:20px; margin:0 0 14px; text-align:center; text-transform:uppercase; }
    .doc-content { white-space:pre-wrap; font-size:14px; line-height:1.45; }
    @media print { body { background:#fff; padding:0; } .a4-page { box-shadow:none; margin:0; width:100%; min-height:unset; } }
  </style>
</head>
<body>
  <div class="a4-page">
    <h1>TRANSLATED DOCUMENT</h1>
    <div class="doc-content">{{CONTENT}}</div>
  </div>
</body>
</html>"""


def _ensure_translate_template_dir() -> None:
    os.makedirs(TRANSLATE_TEMPLATE_DIR, exist_ok=True)
    default_path = os.path.join(TRANSLATE_TEMPLATE_DIR, TRANSLATE_DEFAULT_TEMPLATE)
    if not os.path.exists(default_path):
        with open(default_path, "w", encoding="utf-8") as f:
            f.write(_default_translate_template_html())


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", " ", (name or "")).strip()
    return re.sub(r"\s+", " ", cleaned)


def _resolve_translate_source_path(input_dir: str, file_ref: str) -> Optional[str]:
    """Resolve file path for translation sources.

    Supports:
    - files inside input_dir (same as other modules)
    - uploaded files in temp cache using prefix: "upload_token:<token>"
    """
    if not file_ref:
        return None
    file_ref = file_ref.strip().replace("\\", "/")
    if file_ref.startswith("upload_token:"):
        token = file_ref.split(":", 1)[1].strip()
        meta = translation_upload_cache.get(token) or {}
        candidate = meta.get("temp_path", "")
        if candidate and os.path.exists(candidate):
            return candidate
        return None
    return _resolve_input_file_path(input_dir, file_ref)


def _img_bytes_to_data_url(image_bytes: bytes) -> str:
    return f"data:image/png;base64,{base64.b64encode(image_bytes).decode('utf-8')}"


class QuotaExhaustedError(Exception):
    """Raised when OpenAI API returns a quota/rate-limit error."""
    pass


def _is_quota_error(exc: Exception) -> bool:
    """Check if an exception is an OpenAI quota/rate-limit/billing error."""
    msg = str(exc).lower()
    quota_keywords = [
        "quota", "rate_limit", "rate limit", "insufficient_quota",
        "billing", "exceeded", "limit reached", "too many requests",
        "429", "billing_hard_limit", "exceeded your current quota",
        "you exceeded", "plan limit",
    ]
    return any(kw in msg for kw in quota_keywords)


def _check_and_raise_quota(exc: Exception) -> None:
    """If exc is a quota error, raise QuotaExhaustedError with user-friendly message."""
    if _is_quota_error(exc):
        raise QuotaExhaustedError(
            "⚠️ Đã hết quota OpenAI API! Vui lòng kiểm tra billing tại https://platform.openai.com/account/billing hoặc chờ reset quota."
        ) from exc


def _ocr_image_bytes(llm: Any, image_bytes: bytes, page_idx: int, total_pages: int) -> str:
    prompt = (
        f"{OCR_VIETNAMESE_ADMIN_PROMPT}\n\n"
        f"=== TRANG {page_idx}/{total_pages} ===\n"
        f"ĐỌC TOÀN BỘ text trên trang này. KHÔNG ĐƯỢC BỎ SÓT BẤT KỲ NỘI DUNG NÀO.\n"
        f"Bao gồm: tiêu đề, nội dung chính, bảng biểu, chú thích, footer, số trang, watermark, con dấu.\n"
        f"Nếu có bảng (table): đọc theo hàng từ TRÁI sang PHẢI, mỗi ô cách nhau bằng | .\n"
        f"Chỉ trả ra text OCR của trang này."
    )
    msg = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": _img_bytes_to_data_url(image_bytes)}},
        ]
    )
    try:
        result = llm.invoke([SystemMessage(content="Bạn là OCR engine chuyên nghiệp, chính xác tuyệt đối. Đọc TOÀN BỘ nội dung, KHÔNG bỏ sót."), msg])
    except QuotaExhaustedError:
        raise
    except Exception as exc:
        _check_and_raise_quota(exc)
        raise
    return (result.content or "").strip()


def _ocr_and_translate_image_bytes(llm: Any, image_bytes: bytes, page_idx: int, total_pages: int, source_lang: str = "tiếng Việt") -> str:
    """OCR + Translate in a single vision call. Returns translated English text."""
    prompt = (
        f"{OCR_AND_TRANSLATE_PROMPT}\n\n"
        f"=== TRANG {page_idx}/{total_pages} ===\n"
        f"Ngôn ngữ gốc: {source_lang}\n"
        f"ĐỌc TOÀN BỘ text trên trang này và DỊCH SANG TIẾNG ANH. Trả về BẢN DỊCH TIẾNG ANH."
    )
    msg = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": _img_bytes_to_data_url(image_bytes)}},
        ]
    )
    try:
        result = llm.invoke([SystemMessage(content="You are a professional OCR + legal translator. Read ALL text and translate to English. Output ONLY the English translation."), msg])
    except QuotaExhaustedError:
        raise
    except Exception as exc:
        _check_and_raise_quota(exc)
        raise
    return (result.content or "").strip()


def _ocr_and_translate_document(llm: Any, file_path: str, source_lang: str = "tiếng Việt", page_callback: Any = None) -> str:
    """OCR + Translate a document in one step. Returns translated English text."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        try:
            import pdfplumber
            from PIL import Image
            from concurrent.futures import ThreadPoolExecutor, as_completed

            page_images: List[tuple] = []
            with pdfplumber.open(file_path) as pdf:
                total = len(pdf.pages)
                for idx, page in enumerate(pdf.pages, start=1):
                    try:
                        page_img = page.to_image(resolution=250).original
                        if isinstance(page_img, Image.Image):
                            buff = BytesIO()
                            page_img.save(buff, format="PNG")
                            page_images.append((idx, buff.getvalue()))
                    except Exception:
                        continue

            if not page_images:
                return ""

            total = len(page_images)

            def _ocr_translate_one(args):
                idx, img_bytes = args
                return idx, _ocr_and_translate_image_bytes(llm, img_bytes, idx, total, source_lang)

            results: dict = {}
            max_workers = min(4, total)
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {pool.submit(_ocr_translate_one, item): item[0] for item in page_images}
                for future in as_completed(futures):
                    idx = futures[future]
                    try:
                        page_idx, text = future.result()
                        results[page_idx] = text
                        if page_callback:
                            page_callback(page_idx, total)
                    except QuotaExhaustedError:
                        for f in futures:
                            f.cancel()
                        raise
                    except Exception:
                        continue

            page_texts = [results[i] for i in sorted(results.keys()) if results.get(i)]
            return "\n\n".join(t for t in page_texts if t).strip()
        except QuotaExhaustedError:
            raise
        except Exception as exc:
            _check_and_raise_quota(exc)
            return ""

    if ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"]:
        if page_callback:
            page_callback(1, 1)
        try:
            from PIL import Image
            img = Image.open(file_path)
            buff = BytesIO()
            img.save(buff, format="PNG")
            return _ocr_and_translate_image_bytes(llm, buff.getvalue(), 1, 1, source_lang)
        except QuotaExhaustedError:
            raise
        except Exception as exc:
            _check_and_raise_quota(exc)
            return ""

    return ""


def _ocr_document_for_translation(llm: Any, file_path: str, page_callback: Any = None) -> str:
    """OCR a document. page_callback(page_idx, total_pages) is called per page for progress."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        try:
            import pdfplumber
            from PIL import Image
            from concurrent.futures import ThreadPoolExecutor, as_completed

            # Render all page images first (fast, CPU-bound)
            page_images: List[tuple] = []  # [(idx, image_bytes)]
            with pdfplumber.open(file_path) as pdf:
                total = len(pdf.pages)
                for idx, page in enumerate(pdf.pages, start=1):
                    try:
                        page_img = page.to_image(resolution=250).original  # 250 DPI — higher quality for OCR accuracy
                        if isinstance(page_img, Image.Image):
                            buff = BytesIO()
                            page_img.save(buff, format="PNG")
                            page_images.append((idx, buff.getvalue()))
                    except Exception:
                        continue

            if not page_images:
                return extract_text_with_openai(llm, file_path)

            total = len(page_images)

            # OCR pages in parallel (IO-bound LLM calls)
            def _ocr_one(args):
                idx, img_bytes = args
                return idx, _ocr_image_bytes(llm, img_bytes, idx, total)

            results: dict = {}
            max_workers = min(4, total)  # Cap at 4 concurrent LLM calls
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {pool.submit(_ocr_one, item): item[0] for item in page_images}
                for future in as_completed(futures):
                    idx = futures[future]
                    try:
                        page_idx, text = future.result()
                        results[page_idx] = text
                        if page_callback:
                            page_callback(page_idx, total)
                    except QuotaExhaustedError:
                        # Cancel remaining and propagate
                        for f in futures:
                            f.cancel()
                        raise
                    except Exception:
                        continue

            # Reassemble in page order
            page_texts = [results[i] for i in sorted(results.keys()) if results.get(i)]
            return "\n\n".join(t for t in page_texts if t).strip()
        except QuotaExhaustedError:
            raise
        except Exception as exc:
            _check_and_raise_quota(exc)
            # Fallback: use existing extractor if image-render OCR fails
            return extract_text_with_openai(llm, file_path)

    if ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"]:
        if page_callback:
            page_callback(1, 1)
        try:
            from PIL import Image
            img = Image.open(file_path)
            buff = BytesIO()
            img.save(buff, format="PNG")
            return _ocr_image_bytes(llm, buff.getvalue(), 1, 1)
        except QuotaExhaustedError:
            raise
        except Exception as exc:
            _check_and_raise_quota(exc)
            return extract_text_with_openai(llm, file_path)

    # Non-image docs fallback
    if page_callback:
        page_callback(1, 1)
    return extract_text_with_openai(llm, file_path)


def _translate_ocr_text(llm: Any, ocr_text: str, source_lang: str = "tiếng Việt") -> str:
    prompt = TRANSLATE_TO_EN_PROMPT.format(ocr_text=ocr_text, source_lang=source_lang)
    try:
        result = llm.invoke([SystemMessage(content="You are a strict legal translator."), HumanMessage(content=prompt)])
    except QuotaExhaustedError:
        raise
    except Exception as exc:
        _check_and_raise_quota(exc)
        raise
    return (result.content or "").strip()


def _auto_detect_template(ocr_text: str) -> str:
    """Auto-detect document type from OCR text and return matching template filename.
    Uses keyword matching (no LLM call needed — fast & free).
    """
    text_lower = ocr_text.lower()
    # Keyword → template mapping (order matters: more specific first)
    patterns = [
        (["khai sinh", "giấy khai sinh", "trích lục khai sinh", "birth certificate"], "giấy khai sinh.html"),
        (["kết hôn", "giấy chứng nhận kết hôn", "đăng ký kết hôn", "marriage"], "giấy kết hôn.html"),
        (["hộ khẩu", "sổ hộ khẩu", "đăng ký thường trú", "household"], "hộ khẩu.html"),
        (["hợp đồng lao động", "người lao động", "người sử dụng lao động", "labor contract", "employment contract"], "hợp đồng lao động.html"),
        (["sổ đỏ", "quyền sử dụng đất", "giấy chứng nhận quyền sử dụng", "land use right"], "sổ đỏ.html"),
    ]
    for keywords, template_name in patterns:
        for kw in keywords:
            if kw in text_lower:
                # Verify template file exists
                tpl_path = os.path.join(TRANSLATE_TEMPLATE_DIR, template_name)
                if os.path.exists(tpl_path):
                    return template_name
    return TRANSLATE_DEFAULT_TEMPLATE  # fallback: a4.html



def _build_translation_html(
    llm: Any,
    translated_text: str,
    template_html: str,
    source_pdf_text: str,
) -> str:
    prompt = TRANSLATION_HTML_RENDER_PROMPT.format(
        source_pdf_text=source_pdf_text or "",
        template_html=template_html,
        translated_text=translated_text,
    )
    try:
        result = llm.invoke([SystemMessage(content="You output valid HTML only."), HumanMessage(content=prompt)])
    except QuotaExhaustedError:
        raise
    except Exception as exc:
        _check_and_raise_quota(exc)
        raise
    html_text = (result.content or "").strip()
    if not html_text:
        html_text = template_html.replace("{{CONTENT}}", translated_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return html_text


def _list_input_files(input_dir: str) -> List[Dict[str, str]]:
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


STEP_ORDER = [
    "ingest",
    "summary",
    "writer",
]


def _cache_dir(output_path: str) -> str:
    return os.path.join(os.path.dirname(output_path), "cache")


def _state_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, "state.json")


def _step_marker_path(cache_dir: str, step: str) -> str:
    return os.path.join(cache_dir, f"step_{step}.json")


def _reset_downstream_steps(cache_dir: str, step: str) -> None:
    if step not in STEP_ORDER:
        return
    idx = STEP_ORDER.index(step)
    downstream = STEP_ORDER[idx + 1 :]
    for s in downstream:
        marker = _step_marker_path(cache_dir, s)
        if os.path.exists(marker):
            os.remove(marker)

    # Clear derived caches so downstream status/data stay consistent.
    if "summary" in downstream:
        path = os.path.join(cache_dir, "summary_profile.txt")
        if os.path.exists(path):
            os.remove(path)


def _load_state(cache_dir: str) -> Dict[str, Any]:
    path = _state_path(cache_dir)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_state(cache_dir: str, state: GraphState) -> None:
    os.makedirs(cache_dir, exist_ok=True)
    serializable = {
        "input_dir": state.get("input_dir"),
        "output_path": state.get("output_path"),
        "model": state.get("model"),
        "files": state.get("files", []),
        "grouped": state.get("grouped", {}),
        "summary_profile": state.get("summary_profile", ""),
        "writer_context": state.get("writer_context", ""),
        "letter_full": state.get("letter_full", ""),
    }
    with open(_state_path(cache_dir), "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)


def _save_step_output(cache_dir: str, step: str, state: GraphState) -> None:
    os.makedirs(cache_dir, exist_ok=True)
    if step == "ingest":
        with open(os.path.join(cache_dir, "ingest.json"), "w", encoding="utf-8") as f:
            json.dump(state.get("files", []), f, ensure_ascii=False, indent=2)
    elif step == "summary":
        with open(
            os.path.join(cache_dir, "summary_profile.txt"), "w", encoding="utf-8"
        ) as f:
            f.write(state.get("summary_profile", ""))
    elif step == "writer":
        output_path = state.get("output_path") or os.path.join("output", "letter.txt")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(state.get("letter_full", ""))

    with open(_step_marker_path(cache_dir, step), "w", encoding="utf-8") as f:
        json.dump({"done": True}, f)


def _is_step_done(cache_dir: str, step: str) -> bool:
    return os.path.exists(_step_marker_path(cache_dir, step))


def _resolve_input_file_path(input_dir: str, file_ref: str) -> Optional[str]:
    if not file_ref:
        return None

    input_root = os.path.abspath(input_dir)
    candidate = os.path.abspath(os.path.normpath(os.path.join(input_dir, file_ref)))
    if candidate.startswith(input_root) and os.path.exists(candidate):
        return candidate

    for root, _, filenames in os.walk(input_dir):
        for fname in filenames:
            if fname == file_ref:
                return os.path.join(root, fname)
    return None


def _upsert_file_record(files: List[Dict[str, Any]], new_file: Dict[str, Any]) -> List[Dict[str, Any]]:
    updated: List[Dict[str, Any]] = []
    replaced = False
    for item in files:
        if item.get("path") == new_file.get("path"):
            updated.append(new_file)
            replaced = True
        else:
            updated.append(item)
    if not replaced:
        updated.append(new_file)
    return updated


def _missing_prereq_step(cache_dir: str, step: str) -> Optional[str]:
    if step not in STEP_ORDER:
        return None
    idx = STEP_ORDER.index(step)
    for prev in STEP_ORDER[:idx]:
        if not _is_step_done(cache_dir, prev):
            return prev
    return None


def _run_single_step(step: str, state: GraphState) -> GraphState:
    if step == "ingest":
        return ingest_files(state)
    if step == "summary":
        return build_summary_profile(state)
    if step == "writer":
        return letter_writer(state)
    return state


@app.get("/")
def index():
    return send_from_directory("frontend", "index.html")


# ==================== PROJECT ENDPOINTS → routes/projects.py ====================

# ==================== PRECHECK ENDPOINTS -> routes/precheck.py ====================



# ==================== ALL ROUTE ENDPOINTS -> routes/ ====================

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)


