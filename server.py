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
    TRANSLATE_TO_EN_PROMPT,
    TRANSLATION_HTML_RENDER_PROMPT,
)
from classifier.agent import classify_files_in_folder
from pypdf import PdfReader, PdfWriter
from core.state import GraphState
import database as db


load_dotenv()

app = Flask(__name__, static_folder="frontend", static_url_path="")


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
        f"Bạn đang OCR trang {page_idx}/{total_pages}. Chỉ trả ra text của trang này."
    )
    msg = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": _img_bytes_to_data_url(image_bytes)}},
        ]
    )
    try:
        result = llm.invoke([SystemMessage(content="Bạn là OCR engine chính xác."), msg])
    except QuotaExhaustedError:
        raise
    except Exception as exc:
        _check_and_raise_quota(exc)
        raise
    return (result.content or "").strip()


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
                        page_img = page.to_image(resolution=150).original  # 150 DPI — good balance of speed vs quality
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


# ==================== PROJECT ENDPOINTS ====================

@app.post("/api/projects")
def create_project():
    payload = request.get_json(force=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Project name is required"}), 400
    project = db.create_project(name)
    return jsonify(project)


@app.get("/api/projects")
def list_projects():
    projects = db.list_projects()
    return jsonify({"projects": projects})


@app.get("/api/projects/<int:project_id>")
def get_project(project_id):
    project = db.get_project(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    return jsonify(project)


@app.put("/api/projects/<int:project_id>")
def update_project(project_id):
    payload = request.get_json(force=True) or {}
    name = payload.get("name")
    updates = {}
    if name:
        updates["name"] = name.strip()
    project = db.update_project(project_id, **updates)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    return jsonify(project)


@app.delete("/api/projects/<int:project_id>")
def delete_project(project_id):
    ok = db.delete_project(project_id)
    if not ok:
        return jsonify({"error": "Project not found"}), 404
    return jsonify({"status": "deleted"})


@app.post("/api/projects/<int:project_id>/clear")
def clear_project(project_id: int):
    """Xóa toàn bộ dữ liệu của hồ sơ (DB + file tách AI) để làm người mới. Giữ lại project."""
    project = db.get_project(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    db.clear_project_data(project_id)
    # Xóa file trong splitter_uploads có prefix p{id}__
    base_dir = os.path.dirname(os.path.abspath(__file__))
    upload_dir = os.path.join(base_dir, "splitter_uploads")
    prefix = f"p{project_id}__"
    deleted_uploads = 0
    if os.path.isdir(upload_dir):
        for fname in os.listdir(upload_dir):
            if fname.startswith(prefix) and fname.lower().endswith(".pdf"):
                try:
                    os.remove(os.path.join(upload_dir, fname))
                    deleted_uploads += 1
                except OSError:
                    pass
    # Xóa thư mục trong splitter_outputs có _source.json với project_id trùng
    output_dir = os.path.join(base_dir, "splitter_outputs")
    deleted_output_dirs = 0
    if os.path.isdir(output_dir):
        for folder_name in os.listdir(output_dir):
            folder_path = os.path.join(output_dir, folder_name)
            if not os.path.isdir(folder_path):
                continue
            meta_path = os.path.join(folder_path, "_source.json")
            if os.path.isfile(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as mf:
                        meta = json.load(mf)
                    if meta.get("project_id") == project_id:
                        shutil.rmtree(folder_path, ignore_errors=True)
                        deleted_output_dirs += 1
                        zip_path = os.path.join(output_dir, f"{folder_name}.zip")
                        if os.path.isfile(zip_path):
                            try:
                                os.remove(zip_path)
                            except OSError:
                                pass
                except Exception:
                    pass
    return jsonify({
        "status": "cleared",
        "deleted_uploads": deleted_uploads,
        "deleted_output_dirs": deleted_output_dirs,
    })


@app.get("/api/files")
def list_files():
    input_dir = request.args.get("input_dir", "input")
    files = _list_input_files(input_dir)
    return jsonify({"input_dir": input_dir, "files": files})


# ==================== PRE-CHECK ENDPOINTS ====================

def _vision_detect_pdf_documents(llm, pdf_path: str, filename: str, total_pages: int):
    """Vision check: does this scanned PDF contain multiple documents?
    Detects both different document types AND same-type docs for different people.
    Samples up to 8 pages at 100 DPI for reliable name/type recognition."""
    import fitz  # PyMuPDF
    import base64
    
    doc = fitz.open(pdf_path)
    actual_pages = len(doc)
    
    # Smart sampling: ALL pages for short PDFs, evenly-spaced for longer ones
    if actual_pages <= 6:
        sample_indices = list(range(actual_pages))
    else:
        # Sample up to 8 pages evenly distributed (first, last, + 6 middle)
        max_samples = min(8, actual_pages)
        step = (actual_pages - 1) / (max_samples - 1)
        sample_indices = sorted(set(int(round(i * step)) for i in range(max_samples)))
    
    # Render sampled pages as images
    content_parts = [
        {"type": "text", "text": f"""Analyze these {len(sample_indices)} sampled pages from "{filename}" ({actual_pages} pages total).

TASK: Determine if this PDF contains MULTIPLE TRULY SEPARATE documents that were scanned together into one file. 

A PDF needs splitting ONLY when it contains GENUINELY DIFFERENT, STANDALONE documents. Examples of documents that NEED splitting:
- Marriage certificate + birth certificate (completely different docs)
- Two birth certificates for DIFFERENT children (same type but different people)
- Bank statement + identity card (unrelated docs)
- Multiple standalone government certificates mixed together

⚠️ DO NOT SPLIT these — they are ONE document/package:
- PASSPORT booklet with visa stamps/stickers = 1 PASSPORT (visa pages are part of the passport)
- Rental/Lease AGREEMENT + inventory list/appendix/attachment = 1 RENTAL AGREEMENT (appendices belong to the contract)
- Any CONTRACT + its appendix/supplement/addendum = 1 CONTRACT
- Land use RIGHT CERTIFICATE + supplementary pages = 1 LAND CERTIFICATE
- Any document with its cover page + content pages = 1 document
- Bank statement spanning multiple pages = 1 BANK STATEMENT
- Front + back of same ID card = 1 IDENTITY CARD

⚠️ CRITICAL — PASSPORT EXPIRY CHECK:
The current year is 2026. For ANY passport document, you MUST read the "Date of expiry" / "Ngày hết hạn" field on the passport image.
- If the expiry year < 2026 → doc_type_en = "OLD PASSPORT [expiry year]" (e.g. "OLD PASSPORT 2011")
- If the expiry year >= 2026 → doc_type_en = "PASSPORT"
You MUST include the actual expiry year you read from the document.

For EACH truly separate document found, provide:
- doc_type_en: type in ENGLISH, UPPERCASE (see passport rule above)
- person_name: owner name in UPPERCASE, no diacritics. If unclear → "UNKNOWN"
- start_page and end_page: approximate page range

Return JSON ONLY:
{{"documents": [
  {{"doc_type_en": "OLD PASSPORT 2011", "person_name": "NGUYEN VAN A", "start_page": 1, "end_page": 2}},
  {{"doc_type_en": "BIRTH CERTIFICATE", "person_name": "NGUYEN VAN B", "start_page": 3, "end_page": 4}}
]}}

If this is ONE single document or package: {{"documents": [{{"doc_type_en": "RENTAL AGREEMENT", "person_name": "NGUYEN VAN A", "start_page": 1, "end_page": {actual_pages}}}]}}"""}
    ]
    
    for idx in sample_indices:
        page = doc[idx]
        pix = page.get_pixmap(dpi=100)  # 100 DPI: enough to read names on scanned docs
        img_bytes = pix.tobytes("png")
        b64 = base64.b64encode(img_bytes).decode()
        content_parts.append({"type": "text", "text": f"Page {idx + 1}/{actual_pages}:"})
        content_parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
    
    doc.close()
    
    from langchain_core.messages import HumanMessage, SystemMessage
    try:
        result = llm.invoke([
            SystemMessage(content="You are an expert document classifier for visa application files. You can read Vietnamese documents. Answer only with JSON."),
            HumanMessage(content=content_parts),
        ])
    except Exception as exc:
        _check_and_raise_quota(exc)
        raise
    
    # Parse response
    import re
    text = (result.content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    
    try:
        parsed = json.loads(text)
    except Exception:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                parsed = json.loads(match.group())
            except Exception:
                return []
        else:
            return []
    
    # Extract documents list
    docs = parsed.get("documents", [])
    if not isinstance(docs, list) or len(docs) == 0:
        # Fallback: try old format (mixed/doc_count)
        is_mixed = parsed.get("mixed", False)
        doc_count = int(parsed.get("doc_count", 1))
        doc_types = parsed.get("doc_types", ["UNKNOWN"])
        if is_mixed and doc_count > 1:
            return [{"doc_type_en": dt, "person_name": "UNKNOWN", "start_page": 0, "end_page": 0}
                    for dt in doc_types]
        return [{"doc_type_en": doc_types[0] if doc_types else "UNKNOWN",
                 "person_name": "UNKNOWN", "start_page": 1, "end_page": actual_pages}]
    
    # Process documents list
    output = []
    for item in docs:
        if not isinstance(item, dict):
            continue
        output.append({
            "doc_type_en": (item.get("doc_type_en") or "UNKNOWN").upper().strip(),
            "person_name": (item.get("person_name") or "UNKNOWN").upper().strip(),
            "start_page": int(item.get("start_page", 0)),
            "end_page": int(item.get("end_page", 0)),
        })
    
    return output if output else [{"doc_type_en": "UNKNOWN", "person_name": "UNKNOWN",
                                    "start_page": 1, "end_page": actual_pages}]


# ── Progress tracking for precheck scan ──
_precheck_progress = {"total": 0, "done": 0, "current_file": "", "running": False}

@app.get("/api/precheck/progress")
def precheck_progress():
    """Poll endpoint for scan progress."""
    return jsonify(_precheck_progress)

@app.post("/api/precheck/scan")
def precheck_scan():
    """Scan all files in input/ subfolders: classify doc type + detect multi-doc + suggest rename."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    model = payload.get("model") or get_vision_model()

    if not os.path.isdir(input_dir):
        return jsonify({"error": "folder_not_found", "input_dir": input_dir}), 404

    from langchain_openai import ChatOpenAI
    from classifier.agent import classify_doc_type_only, normalize_vietnamese_name
    from concurrent.futures import ThreadPoolExecutor, as_completed

    llm = ChatOpenAI(model=model, temperature=0)

    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}

    # Collect files grouped by person subfolder (RECURSIVE with os.walk)
    folders_data = {}
    for item in sorted(os.listdir(input_dir)):
        folder_path = os.path.join(input_dir, item)
        if not os.path.isdir(folder_path):
            continue
        if item.startswith('.') or item.startswith('_'):
            continue
        person_normalized = normalize_vietnamese_name(item)
        files_in_folder = []
        # Walk recursively into all subfolders
        for root, _dirs, filenames in os.walk(folder_path):
            for fname in sorted(filenames):
                fpath = os.path.join(root, fname)
                if not os.path.isfile(fpath):
                    continue
                rel_path = os.path.relpath(fpath, input_dir).replace("\\", "/")
                sub_path = os.path.relpath(fpath, folder_path).replace("\\", "/")
                ext = os.path.splitext(fname)[1].lower()
                files_in_folder.append({
                    "filename": fname,
                    "path": fpath,
                    "rel_path": rel_path,
                    "sub_path": sub_path,  # path relative to person folder
                    "ext": ext,
                })
        if files_in_folder:
            folders_data[item] = {
                "folder_name": item,
                "person_name": person_normalized,
                "files": files_in_folder,
            }

    # Also collect files in root (not in any subfolder)
    root_files = []
    for fname in sorted(os.listdir(input_dir)):
        fpath = os.path.join(input_dir, fname)
        if os.path.isfile(fpath):
            ext = os.path.splitext(fname)[1].lower()
            root_files.append({
                "filename": fname,
                "path": fpath,
                "rel_path": fname,
                "sub_path": fname,
                "ext": ext,
            })
    if root_files:
        folders_data["__ROOT__"] = {
            "folder_name": "(Root)",
            "person_name": "UNKNOWN",
            "files": root_files,
        }

    # Classify all files in parallel
    # Known bank name keywords for post-processing
    _BANK_NAMES = {
        'BIDV': 'BIDV', 'VCB': 'VCB', 'VIETCOMBANK': 'VCB',
        'TCB': 'TCB', 'TECHCOMBANK': 'TCB', 'ACB': 'ACB',
        'MBB': 'MB', 'MBBANK': 'MB', 'MB': 'MB',
        'VPB': 'VPB', 'VPBANK': 'VPB', 'SACOMBANK': 'SACOMBANK',
        'STB': 'SACOMBANK', 'AGRIBANK': 'AGRIBANK', 'TPBANK': 'TPBANK',
        'TPB': 'TPBANK', 'HDBank': 'HDBANK', 'SHB': 'SHB',
        'VIETINBANK': 'VIETINBANK', 'CTG': 'VIETINBANK',
        'EXIMBANK': 'EXIMBANK', 'SCB': 'SCB', 'OCB': 'OCB',
    }

    def _enrich_doc_type(doc_type: str, filename: str, sub_path: str) -> str:
        """Post-process: add bank name and time period to doc_type if AI missed them."""
        upper_type = doc_type.upper().strip()
        # Full context for bank name detection
        context_upper = (filename + " " + sub_path).upper()
        # ONLY filename for period extraction (avoid folder path duplicates)
        fname_only = os.path.splitext(filename)[0].upper()

        # Only enrich financial docs (BANK STATEMENT, SAVINGS BOOK, BALANCE, etc.)
        financial_keywords = ['BANK STATEMENT', 'SAVINGS', 'BALANCE', 'ACCOUNT STATEMENT',
                              'DEPOSIT', 'SỔ PHỤ', 'SAO KÊ']
        is_financial = any(kw in upper_type for kw in ['BANK', 'STATEMENT', 'SAVINGS', 'BALANCE', 'DEPOSIT', 'ACCOUNT'])
        if not is_financial:
            # Also check if filename suggests financial but AI returned generic DOCUMENT
            is_financial = any(kw in context_upper for kw in ['SỔ PHỤ', 'SAO KÊ', 'BANK', 'SỔ TIẾT KIỆM'])
            if is_financial and upper_type in ['DOCUMENT', 'UNKNOWN DOCUMENT']:
                upper_type = 'BANK STATEMENT'

        if is_financial:
            # Check if bank name already in doc_type
            has_bank = any(bk in upper_type for bk in _BANK_NAMES.values())
            if not has_bank:
                # Try to find bank name in full path context
                for keyword, bank_std in _BANK_NAMES.items():
                    if keyword.upper() in context_upper:
                        upper_type = f"{upper_type} {bank_std}"
                        break

            # Check if time period already in doc_type (T01, T06, 2025, 2026, etc.)
            has_period = bool(re.search(r'T\d{1,2}|20\d{2}', upper_type))
            if not has_period:
                # Extract periods from FILENAME ONLY (not folder path!) to avoid duplicates
                periods = re.findall(r'T(\d{1,2})', fname_only)
                years = re.findall(r'(20\d{2})', fname_only)
                period_parts = []
                if periods:
                    period_parts.extend([f"T{p.zfill(2)}" for p in periods])
                if years:
                    period_parts.extend(years)
                # Deduplicate while preserving order
                period_parts = list(dict.fromkeys(period_parts))
                if period_parts:
                    upper_type = f"{upper_type} {' '.join(period_parts)}"

        # ==== VIETNAMESE KEYWORD FALLBACK ====
        # When AI returns generic DOCUMENT/PHOTO, try to match Vietnamese keywords in filename
        if upper_type in ['DOCUMENT', 'UNKNOWN DOCUMENT', 'UNKNOWN', 'OTHER', 'PHOTO']:
            _VN_KEYWORDS = {
                # Land & Property
                'SỔ ĐỎ': 'LAND USE RIGHT CERTIFICATE',
                'SỔ HỒNG': 'LAND USE RIGHT CERTIFICATE',
                'QUYỀN SỬ DỤNG ĐẤT': 'LAND USE RIGHT CERTIFICATE',
                'GIẤY CHỨNG NHẬN QSDĐ': 'LAND USE RIGHT CERTIFICATE',
                # Vehicle
                'Ô TÔ': 'VEHICLE REGISTRATION',
                'XE MÁY': 'VEHICLE REGISTRATION',
                'ĐĂNG KÝ XE': 'VEHICLE REGISTRATION',
                'ĐĂNG KIỂM': 'VEHICLE INSPECTION',
                'CAVET': 'VEHICLE REGISTRATION',
                # Bank & Finance
                'TÀI KHOẢN': 'BANK ACCOUNT STATEMENT',
                'SỔ TIẾT KIỆM': 'SAVINGS BOOK',
                'XÁC NHẬN SỐ DƯ': 'BALANCE CONFIRMATION',
                # Insurance
                'BẢO HIỂM XÃ HỘI': 'SOCIAL INSURANCE',
                'BHXH': 'SOCIAL INSURANCE',
                'BẢO HIỂM Y TẾ': 'HEALTH INSURANCE',
                'BHYT': 'HEALTH INSURANCE',
                'BẢO HIỂM': 'INSURANCE',
                # Identity
                'HỘ CHIẾU': 'PASSPORT',
                'CCCD': 'CITIZEN IDENTITY CARD',
                'CMND': 'CITIZEN IDENTITY CARD',
                'GIẤY KHAI SINH': 'BIRTH CERTIFICATE',
                'KHAI SINH': 'BIRTH CERTIFICATE',
                'GIẤY ĐĂNG KÝ KẾT HÔN': 'MARRIAGE CERTIFICATE',
                'KẾT HÔN': 'MARRIAGE CERTIFICATE',
                'HỘ KHẨU': 'HOUSEHOLD REGISTRATION',
                # Employment & Tax
                'HỢP ĐỒNG LAO ĐỘNG': 'LABOR CONTRACT',
                'HỢP ĐỒNG': 'CONTRACT',
                'LƯƠNG': 'SALARY CERTIFICATE',
                'XÁC NHẬN LƯƠNG': 'SALARY CERTIFICATE',
                'THUẾ': 'TAX CERTIFICATE',
                'THUẾ TNCN': 'PERSONAL INCOME TAX',
                'TNCN': 'PERSONAL INCOME TAX',
                'THÔNG BÁO THUẾ': 'TAX NOTICE',
                'MST': 'TAX REGISTRATION',
                # Education
                'THẺ HỌC SINH': 'STUDENT ID CARD',
                'HỌC BẠ': 'ACADEMIC TRANSCRIPT',
                'BẰNG': 'DIPLOMA',
                'BẰNG TỐT NGHIỆP': 'GRADUATION DIPLOMA',
                'CHỨNG CHỈ': 'CERTIFICATE',
                # Travel
                'LỊCH TRÌNH': 'ITINERARY',
                'VÉ MÁY BAY': 'FLIGHT TICKET',
                'BOOKING': 'BOOKING CONFIRMATION',
                'KHÁCH SẠN': 'HOTEL BOOKING',
                # Business
                'GIẤY PHÉP KINH DOANH': 'BUSINESS LICENSE',
                'ĐĂNG KÝ KINH DOANH': 'BUSINESS REGISTRATION',
                'GPKD': 'BUSINESS LICENSE',
                'GIẤY ỦY QUYỀN': 'POWER OF ATTORNEY',
                'ỦY QUYỀN': 'POWER OF ATTORNEY',
                # Application
                'FORM': 'APPLICATION FORM',
                'ĐƠN XIN': 'APPLICATION FORM',
                # Other common
                'ORIGIN': 'ORIGIN STATEMENT',
                'GRANTED': 'GRANT LETTER',
                'GIẤY XÁC NHẬN': 'CONFIRMATION LETTER',
            }
            # Search in both filename and folder path (Vietnamese chars!)
            fn_upper = filename.upper()
            sub_upper = sub_path.upper() if sub_path else ""
            search_text = fn_upper + " " + sub_upper
            for vn_kw, en_type in _VN_KEYWORDS.items():
                if vn_kw.upper() in search_text:
                    upper_type = en_type
                    break

        return upper_type.strip()

    def _is_same_person(name_a: str, name_b: str) -> bool:
        """Check if two Vietnamese names refer to the same person.
        Handles: LE THI NHAT PHUONG vs NGUYEN THI NHAT PHUONG (same person, different family name).
        Also handles folder prefix like UC_NGUYEN_THI_NHAT_PHUONG_VINH."""
        if not name_a or not name_b:
            return False
        a = name_a.replace("_", " ").strip().upper()
        b = name_b.replace("_", " ").strip().upper()
        # Exact match
        if a == b:
            return True
        # Substring containment
        if a in b or b in a:
            return True
        parts_a = a.split()
        parts_b = b.split()
        # Same given name (last 2+ words match at end)
        if len(parts_a) >= 2 and len(parts_b) >= 2:
            if parts_a[-2:] == parts_b[-2:]:
                return True
            if len(parts_a) >= 3 and len(parts_b) >= 3:
                if parts_a[-3:] == parts_b[-3:]:
                    return True
        # Handle folder names with prefix (UC) or suffix (city like VINH):
        # Check if shorter name's last 2 given-name parts appear as consecutive
        # words anywhere in the longer name. e.g. "NHAT PHUONG" from
        # "LE THI NHAT PHUONG" appears in "UC NGUYEN THI NHAT PHUONG VINH"
        shorter, longer = (parts_a, parts_b) if len(parts_a) <= len(parts_b) else (parts_b, parts_a)
        if len(shorter) >= 2:
            tail2 = shorter[-2:]
            for i in range(len(longer) - 1):
                if longer[i:i+2] == tail2:
                    return True
        if len(shorter) >= 3:
            tail3 = shorter[-3:]
            for i in range(len(longer) - 2):
                if longer[i:i+3] == tail3:
                    return True
        return False

    def _fix_doc_owner(doc_owner: str, person_name: str, filename: str, doc_type: str) -> str:
        """Post-process: fix doc_owner to avoid duplicates and detect missing owners."""
        from classifier.agent import normalize_vietnamese_name
        owner = (doc_owner or "").strip()

        # Treat UNKNOWN PERSON / UNKNOWN as "no owner found"
        if owner.upper() in ('UNKNOWN PERSON', 'UNKNOWN', 'UNKNOWN_PERSON'):
            owner = ""

        # Property/land docs → always use folder name, skip doc_owner
        _SKIP_OWNER_DOCS = [
            'LAND USE', 'LAND CERTIFICATE', 'PROPERTY', 'SỔ ĐỎ',
            'RENTAL AGREEMENT', 'LEASE', 'CONTRACT',
        ]
        upper_dt = doc_type.upper()
        if any(kw in upper_dt for kw in _SKIP_OWNER_DOCS):
            return ""

        # If doc_owner is same as folder person → set empty (it's the main applicant)
        if owner:
            owner_norm = normalize_vietnamese_name(owner)
            if _is_same_person(owner_norm, person_name):
                return ""

        # Vietnamese relational clues in filename that indicate different person
        _VN_RELATION_CLUES = [
            'con trai', 'con gái', 'con', 'mẹ', 'vợ', 'bố', 'cha',
            'chồng', 'anh', 'chị', 'em', 'bà', 'ông',
        ]
        fn_lower = filename.lower()
        has_relation_clue = any(clue in fn_lower for clue in _VN_RELATION_CLUES)

        # If no doc_owner but filename has initials/name different from person
        if not owner:
            upper_type = doc_type.upper()
            # Only for identity/personal docs where owner matters
            identity_docs = ['PASSPORT', 'OLD PASSPORT', 'CITIZEN IDENTITY', 'CCCD',
                             'BIRTH CERTIFICATE', 'STUDENT ID', 'STUDENT CARD',
                             'HEALTH INSURANCE', 'SCHOOL']
            is_identity = any(kw in upper_type for kw in identity_docs)

            if is_identity or has_relation_clue:
                stem = os.path.splitext(filename)[0]
                # Look for initials (2-6 uppercase letters at end of filename)
                match = re.search(r'[A-Z]{2,6}(?:\s*\.?\s*$)', stem)
                if match:
                    initials = match.group().strip('. ')
                    if initials not in person_name:
                        return initials

        return owner

    import threading
    _quota_stop = threading.Event()

    # Quick filename-based doc type lookup (skips LLM call for obvious files)
    _QUICK_CLASSIFY_MAP = {
        'hộ chiếu': 'PASSPORT', 'ho chieu': 'PASSPORT', 'passport': 'PASSPORT',
        'cccd': 'CITIZEN IDENTITY CARD', 'cmnd': 'CITIZEN IDENTITY CARD',
        'khai sinh': 'BIRTH CERTIFICATE', 'birth': 'BIRTH CERTIFICATE',
        'kết hôn': 'MARRIAGE CERTIFICATE', 'ket hon': 'MARRIAGE CERTIFICATE',
        'sổ đất': 'LAND USE RIGHT CERTIFICATE', 'so dat': 'LAND USE RIGHT CERTIFICATE',
        'sổ đỏ': 'LAND USE RIGHT CERTIFICATE', 'so do': 'LAND USE RIGHT CERTIFICATE',
        'quyền sử dụng đất': 'LAND USE RIGHT CERTIFICATE',
        'thẻ học sinh': 'STUDENT ID CARD', 'the hoc sinh': 'STUDENT ID CARD',
        'bank': 'BANK STATEMENT', 'ngân hàng': 'BANK STATEMENT',
        'hợp đồng thuê': 'RENTAL AGREEMENT', 'hd thue': 'RENTAL AGREEMENT',
        'hd cho thue': 'RENTAL AGREEMENT', 'thuê nhà': 'RENTAL AGREEMENT',
        'xác nhận công việc': 'WORK CERTIFICATE', 'xncv': 'WORK CERTIFICATE',
        'xác nhận số dư': 'BALANCE CONFIRMATION', 'xnsd': 'BALANCE CONFIRMATION',
        'nghỉ phép': 'LEAVE REQUEST', 'don xin nghi': 'LEAVE REQUEST',
        'sổ tiết kiệm': 'SAVINGS BOOK', 'tiet kiem': 'SAVINGS BOOK',
        'bảo hiểm': 'INSURANCE', 'bhxh': 'SOCIAL INSURANCE',
        'thuế': 'TAX CERTIFICATE', 'thue': 'TAX CERTIFICATE',
        'hộ khẩu': 'HOUSEHOLD REGISTRATION', 'ho khau': 'HOUSEHOLD REGISTRATION',
    }

    def _quick_classify_from_filename(fname: str) -> str:
        """Try to classify doc type from filename alone. Returns '' if unclear."""
        fn_lower = os.path.splitext(fname)[0].lower()
        # Remove common prefixes like numbers, parentheses
        for kw, doc_type in _QUICK_CLASSIFY_MAP.items():
            if kw in fn_lower:
                return doc_type
        return ""

    def _classify_one(file_info, person_name):
        fname = file_info["filename"]
        fpath = file_info["path"]
        ext = file_info["ext"]
        sub_path = file_info.get("sub_path", fname)

        # Early exit if quota already exhausted (don't waste API calls)
        if _quota_stop.is_set():
            return {
                **file_info,
                "person_name": person_name,
                "doc_type_en": "QUOTA ERROR",
                "doc_owner": "",
                "suggested_name": fname,
                "needs_split": False,
                "doc_count": 1,
                "doc_types": ["ERROR"],
                "error": "Skipped: API quota exhausted",
                "quota_error": True,
            }

        try:
            # FAST PATH: if filename clearly tells us the doc type, skip LLM call
            # This saves both time AND tokens for obvious files
            quick_type = _quick_classify_from_filename(fname)
            if quick_type:
                # Still need to check page count for multi-doc detection
                page_count = 1
                if ext == '.pdf':
                    try:
                        from pypdf import PdfReader as _PdfR
                        page_count = len(_PdfR(fpath).pages)
                    except Exception:
                        pass
                # Single page or known single-doc type → skip LLM
                if page_count <= 2:
                    doc_type = quick_type
                    doc_owner = ""
                    ai_person = ""
                    needs_split = False
                    doc_count = 1
                    doc_types = [doc_type]
                    # Jump directly to post-processing (skip LLM + vision)
                    doc_type = _enrich_doc_type(doc_type, fname, sub_path)
                    doc_owner = _fix_doc_owner(doc_owner, person_name, fname, doc_type)
                    doc_type_clean = doc_type.upper().strip()
                    doc_type_clean = re.sub(r'[^A-Z0-9]+', '_', doc_type_clean).strip('_')
                    out_ext = '.pdf' if ext in IMAGE_EXTS else ext
                    suggested_name = f"{person_name}_{doc_type_clean}{out_ext}"
                    return {
                        **file_info,
                        "person_name": person_name,
                        "doc_type_en": doc_type,
                        "doc_owner": doc_owner,
                        "suggested_name": suggested_name,
                        "needs_split": needs_split,
                        "doc_count": doc_count,
                        "doc_types": doc_types,
                        "fast_classified": True,
                    }

            result = classify_doc_type_only(llm, fname, fpath, folder_person=person_name)
            doc_type = result.get("doc_type_en", "DOCUMENT")
            doc_owner = result.get("doc_owner", "")
            ai_person = result.get("person_name", "")  # Actual owner from document content
            needs_split = result.get("needs_split", False)
            doc_count = result.get("doc_count", 1)
            doc_types = result.get("doc_types", [doc_type])

            # VISION MULTI-DOC DETECTION for PDFs (2+ pages, not already flagged)
            # Only skip vision if ALL pages have extractable text (text-based is reliable)
            # If ANY pages are scanned (empty), vision is needed as backup
            if ext == '.pdf' and not needs_split:
                try:
                    from pypdf import PdfReader as _PdfR
                    _reader = _PdfR(fpath)
                    total_pages = len(_reader.pages)
                    # Check if pages lack text (scanned/image pages)
                    page_texts_len = [len((p.extract_text() or "").strip()) for p in _reader.pages]
                    has_scanned_pages = any(tl < 30 for tl in page_texts_len)
                    all_scanned = all(tl < 30 for tl in page_texts_len)
                except Exception:
                    total_pages = 1
                    has_scanned_pages = True
                    all_scanned = True
                # Run vision for scanned PDFs to get person name + multi-doc detection
                # Cost optimization: only run for 2+ pages (multi-doc) OR when filename
                # has relational clues (con, vợ, mẹ...) suggesting different person
                _VN_CLUES_FOR_VISION = [
                    'con trai', 'con gái', 'con', 'mẹ', 'vợ', 'bố', 'cha',
                    'chồng', 'anh', 'chị', 'em', 'bà', 'ông',
                ]
                fn_lower_check = fname.lower()
                needs_vision_for_name = any(c in fn_lower_check for c in _VN_CLUES_FOR_VISION)
                should_run_vision = has_scanned_pages and (total_pages >= 2 or needs_vision_for_name or all_scanned)
                if should_run_vision:
                    try:
                        vision_results = _vision_detect_pdf_documents(llm, fpath, fname, total_pages)
                        if vision_results:
                            if len(vision_results) > 1:
                                # Check if all results are passport-related (PASSPORT + VISA)
                                # for the same person → treat as ONE passport, don't split
                                _PASSPORT_FAMILY = {'PASSPORT', 'VISA', 'OLD PASSPORT'}
                                vr_types = set()
                                vr_persons = set()
                                for vr in vision_results:
                                    vt = vr.get("doc_type_en", "").upper()
                                    # Normalize: "OLD PASSPORT 2011" → "OLD PASSPORT"
                                    for pf in _PASSPORT_FAMILY:
                                        if vt.startswith(pf):
                                            vr_types.add(pf)
                                            break
                                    else:
                                        vr_types.add(vt)
                                    vr_persons.add(vr.get("person_name", "UNKNOWN").upper())
                                # All passport-family docs for same person → single doc
                                is_passport_bundle = vr_types.issubset(_PASSPORT_FAMILY) and len(vr_persons) <= 1
                                if not is_passport_bundle:
                                    needs_split = True
                                    doc_count = len(vision_results)
                                doc_types = []
                                for r in vision_results:
                                    dt = r.get("doc_type_en", "UNKNOWN")
                                    pn = r.get("person_name", "")
                                    if pn and pn != "UNKNOWN":
                                        doc_types.append(f"{dt} ({pn})")
                                    else:
                                        doc_types.append(dt)
                                doc_type = vision_results[0].get("doc_type_en", doc_type)
                            # ALWAYS use vision person_name for ai_person (even single-doc)
                            # This is how we find the child's name from a scanned passport
                            vision_person = vision_results[0].get("person_name", "")
                            if vision_person and vision_person not in ("UNKNOWN", "UNKNOWN PERSON"):
                                ai_person = vision_person
                            # Use vision doc_type if better than text-based
                            # For scanned PDFs, text-based only guesses from filename → vision is MORE reliable
                            vision_doc_type = vision_results[0].get("doc_type_en", "")
                            if vision_doc_type:
                                # Always prefer vision for fully-scanned PDFs (text-based just guesses)
                                if all_scanned:
                                    doc_type = vision_doc_type
                                # For partial-scan PDFs, only override if text-based gave generic result
                                elif doc_type in ("DOCUMENT", "UNKNOWN DOCUMENT", "UNKNOWN"):
                                    doc_type = vision_doc_type
                    except QuotaExhaustedError:
                        raise
                    except Exception:
                        pass  # Vision detection failed, keep original result

            # POST-PROCESSING: enrich doc_type with bank name + period from filename
            doc_type = _enrich_doc_type(doc_type, fname, sub_path)

            # POST-PROCESSING: fix doc_owner (prevent duplicate, detect missing)
            doc_owner = _fix_doc_owner(doc_owner, person_name, fname, doc_type)

            # FALLBACK: if AI returned a different person_name than folder person,
            # use it as doc_owner — BUT ONLY for personal/identity docs
            # (passport, student ID, birth cert). Other docs → folder name only.
            _PERSONAL_DOCS = ['PASSPORT', 'OLD PASSPORT', 'STUDENT ID', 'STUDENT CARD',
                              'BIRTH CERTIFICATE', 'IDENTITY CARD', 'CCCD', 'CITIZEN',
                              'HEALTH INSURANCE', 'PHOTO']
            upper_doc = doc_type.upper()
            is_personal = any(kw in upper_doc for kw in _PERSONAL_DOCS)
            if not doc_owner and ai_person and is_personal:
                ai_person_norm = normalize_vietnamese_name(ai_person)
                if (ai_person_norm and ai_person_norm != "UNKNOWN_PERSON"
                        and not _is_same_person(ai_person_norm, person_name)):
                    doc_owner = ai_person_norm

            # Build suggested name
            doc_type_clean = doc_type.upper().strip()
            doc_type_clean = re.sub(r'[^A-Z0-9]+', '_', doc_type_clean).strip('_')
            out_ext = '.pdf' if ext in IMAGE_EXTS else ext

            # If doc_owner exists (different person), use ONLY owner name
            # e.g. "Hộ chiếu con trai" → NGUYEN_DUC_TRI_PASSPORT.pdf
            if doc_owner:
                owner_clean = re.sub(r'[^A-Z0-9]+', '_', doc_owner.upper().strip()).strip('_')
                suggested_name = f"{owner_clean}_{doc_type_clean}{out_ext}"
            else:
                suggested_name = f"{person_name}_{doc_type_clean}{out_ext}"

            return {
                **file_info,
                "person_name": person_name,
                "doc_type_en": doc_type,
                "doc_owner": doc_owner,
                "suggested_name": suggested_name,
                "needs_split": needs_split,
                "doc_count": doc_count,
                "doc_types": doc_types,
            }
        except Exception as e:
            err_str = str(e).lower()
            is_quota = 'insufficient_quota' in err_str or '429' in err_str or 'rate limit' in err_str
            if is_quota:
                _quota_stop.set()  # Signal all other threads to stop
            return {
                **file_info,
                "person_name": person_name,
                "doc_type_en": "QUOTA ERROR" if is_quota else "ERROR",
                "doc_owner": "",
                "suggested_name": fname,
                "needs_split": False,
                "doc_count": 1,
                "doc_types": ["ERROR"],
                "error": str(e),
                "quota_error": is_quota,
            }

    all_results = []
    folders_output = []

    # Setup progress tracking
    total_files = sum(len(fd["files"]) for fd in folders_data.values())
    _precheck_progress.update({"total": total_files, "done": 0, "current_file": "", "running": True})

    # Build flat list of (file_info, person_name, folder_key) for sequential submit
    all_tasks = []
    for folder_key, folder_data in folders_data.items():
        for file_info in folder_data["files"]:
            all_tasks.append((file_info, folder_data["person_name"], folder_key))

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_map = {}
        for file_info, person_name, folder_key in all_tasks:
            if _quota_stop.is_set():
                # Quota exhausted — skip remaining, mark as quota error
                all_results.append({
                    **file_info,
                    "person_name": person_name,
                    "doc_type_en": "QUOTA ERROR",
                    "doc_owner": "",
                    "suggested_name": file_info["filename"],
                    "needs_split": False,
                    "doc_count": 1,
                    "doc_types": ["ERROR"],
                    "error": "Skipped: API quota exhausted",
                    "quota_error": True,
                })
                continue
            future = executor.submit(_classify_one, file_info, person_name)
            future_map[future] = (folder_key, file_info, person_name)

        for future in as_completed(future_map):
            result = future.result()
            folder_key, file_info, person_name = future_map[future]
            # Update progress for frontend polling
            _precheck_progress["done"] = _precheck_progress.get("done", 0) + 1
            _precheck_progress["current_file"] = file_info["filename"]
            all_results.append(result)
            # If quota just got exhausted, cancel remaining pending futures
            if _quota_stop.is_set():
                for pending in future_map:
                    pending.cancel()

    # Group results back by folder
    folder_results = {}
    for r in all_results:
        # Find which folder this file belongs to
        for folder_key, folder_data in folders_data.items():
            if any(f["path"] == r["path"] for f in folder_data["files"]):
                if folder_key not in folder_results:
                    folder_results[folder_key] = {
                        "folder_name": folder_data["folder_name"],
                        "person_name": folder_data["person_name"],
                        "files": [],
                    }
                folder_results[folder_key]["files"].append(r)
                break

    # Handle duplicate suggested names within each folder
    for folder_key, folder_data in folder_results.items():
        name_counts = {}
        for f in sorted(folder_data["files"], key=lambda x: x["filename"]):
            sname = f["suggested_name"]
            if sname in name_counts:
                name_counts[sname] += 1
                base, ext = os.path.splitext(sname)
                f["suggested_name"] = f"{base}_({name_counts[sname]}){ext}"
            else:
                name_counts[sname] = 0

    # Sort files within each folder
    for folder_data in folder_results.values():
        folder_data["files"].sort(key=lambda x: x["filename"])

    folders_output = sorted(folder_results.values(), key=lambda x: x["folder_name"])

    total_files = sum(len(f["files"]) for f in folders_output)
    multi_count = sum(1 for r in all_results if r.get("needs_split"))
    quota_errors = sum(1 for r in all_results if r.get("quota_error"))

    # Reset progress
    _precheck_progress.update({"total": total_files, "done": total_files, "current_file": "", "running": False})

    return jsonify({
        "status": "done",
        "input_dir": input_dir,
        "total_files": total_files,
        "multi_doc_count": multi_count,
        "clean_count": total_files - multi_count,
        "folders": folders_output,
        "quota_exhausted": quota_errors > 0,
        "quota_error_count": quota_errors,
    })


@app.post("/api/processor/apply-rename")
def processor_apply_rename():
    """Rename files in-place within input/ subfolders. Converts images to PDF."""
    payload = request.get_json(force=True) or {}
    renames = payload.get("renames", [])

    if not renames:
        return jsonify({"error": "no_renames_provided"}), 400

    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
    renamed = []
    errors = []

    for item in renames:
        old_path = item.get("path", "")
        new_name = item.get("new_name", "")

        if not old_path or not new_name:
            errors.append({"path": old_path, "error": "missing path or new_name"})
            continue

        if not os.path.isfile(old_path):
            errors.append({"path": old_path, "error": "file_not_found"})
            continue

        parent_dir = os.path.dirname(old_path)
        old_ext = os.path.splitext(old_path)[1].lower()
        new_ext = os.path.splitext(new_name)[1].lower()
        needs_convert = (old_ext in IMAGE_EXTS and new_ext == '.pdf')

        new_path = os.path.join(parent_dir, new_name)

        # Handle duplicate: add suffix
        if os.path.exists(new_path) and not os.path.samefile(old_path, new_path):
            base, ext = os.path.splitext(new_name)
            idx = 1
            while os.path.exists(new_path):
                new_path = os.path.join(parent_dir, f"{base}_({idx}){ext}")
                idx += 1

        try:
            if needs_convert:
                # Convert image → PDF using Pillow
                from PIL import Image
                img = Image.open(old_path)
                if img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')
                img.save(new_path, 'PDF', resolution=150)
                img.close()
                os.remove(old_path)  # Remove original image
            else:
                os.rename(old_path, new_path)
            renamed.append({
                "old": os.path.basename(old_path),
                "new": os.path.basename(new_path),
                "path": new_path,
                "converted": needs_convert,
            })
        except Exception as e:
            errors.append({"path": old_path, "error": str(e)})

    return jsonify({
        "status": "done",
        "renamed_count": len(renamed),
        "error_count": len(errors),
        "renamed": renamed,
        "errors": errors,
    })


@app.post("/api/processor/merge-files")
def processor_merge_files():
    """Merge multiple files (images + PDFs) into a single PDF in user-specified order."""
    payload = request.get_json(force=True) or {}
    file_paths = payload.get("files", [])  # ordered list of file paths
    output_name = payload.get("output_name", "merged.pdf")

    if len(file_paths) < 2:
        return jsonify({"error": "need_at_least_2_files"}), 400

    from pypdf import PdfWriter, PdfReader
    from PIL import Image
    import tempfile

    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
    writer = PdfWriter()
    tmp_files = []

    try:
        for fpath in file_paths:
            if not os.path.isfile(fpath):
                return jsonify({"error": f"file_not_found: {fpath}"}), 404
            ext = os.path.splitext(fpath)[1].lower()
            if ext in IMAGE_EXTS:
                # Convert image to temp PDF page
                img = Image.open(fpath)
                if img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')
                tmp_pdf = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
                img.save(tmp_pdf.name, 'PDF', resolution=150)
                img.close()
                tmp_files.append(tmp_pdf.name)
                reader = PdfReader(tmp_pdf.name)
                for page in reader.pages:
                    writer.add_page(page)
            elif ext == '.pdf':
                reader = PdfReader(fpath)
                for page in reader.pages:
                    writer.add_page(page)
            else:
                return jsonify({"error": f"unsupported_format: {ext}"}), 400

        # Output path = same folder as first file
        parent_dir = os.path.dirname(file_paths[0])
        if not output_name.lower().endswith('.pdf'):
            output_name += '.pdf'
        output_path = os.path.join(parent_dir, output_name)

        # Handle duplicate
        if os.path.exists(output_path):
            base, ext = os.path.splitext(output_name)
            idx = 1
            while os.path.exists(os.path.join(parent_dir, f"{base}_({idx}){ext}")):
                idx += 1
            output_path = os.path.join(parent_dir, f"{base}_({idx}){ext}")

        with open(output_path, 'wb') as out:
            writer.write(out)

        # Delete original source files after successful merge
        deleted_files = []
        output_abs = os.path.abspath(output_path)
        for fpath in file_paths:
            src_abs = os.path.abspath(fpath)
            if src_abs == output_abs:
                continue  # don't delete the output file itself
            try:
                os.remove(fpath)
                deleted_files.append(os.path.basename(fpath))
            except Exception as del_err:
                print(f"[merge] Warning: could not delete {fpath}: {del_err}")

        return jsonify({
            "status": "done",
            "output_path": output_path,
            "output_name": os.path.basename(output_path),
            "total_pages": len(writer.pages),
            "merged_count": len(file_paths),
            "deleted_files": deleted_files,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        for tf in tmp_files:
            try:
                os.remove(tf)
            except:
                pass


@app.post("/api/pipeline/send-to-splitter")
def pipeline_send_to_splitter():
    """Copy selected multi-doc files → splitter_uploads for AI splitting."""
    payload = request.get_json(force=True) or {}
    file_paths = payload.get("file_paths", [])
    project_id = payload.get("project_id")

    if not file_paths:
        return jsonify({"error": "no_files_selected"}), 400

    target_dir = os.path.join("splitter_uploads")
    os.makedirs(target_dir, exist_ok=True)
    copied = []

    # Normalise project_id to int if possible
    pid: Optional[int]
    if isinstance(project_id, int):
        pid = project_id
    elif isinstance(project_id, str) and project_id.isdigit():
        pid = int(project_id)
    else:
        pid = None

    for src in file_paths:
        if not os.path.isfile(src):
            continue
        original_name = os.path.basename(src)

        # Prefix filename with project id so we can filter queue per project later.
        # Old files without prefix will be treated as "global" and ignored when a project_id is provided.
        if pid is not None:
            stored_name = f"p{pid}__{original_name}"
        else:
            stored_name = original_name

        dst = os.path.join(target_dir, stored_name)
        base, ext = os.path.splitext(stored_name)
        idx = 1
        while os.path.exists(dst):
            dst = os.path.join(target_dir, f"{base} ({idx}){ext}")
            idx += 1
        shutil.copy2(src, dst)
        copied.append(stored_name)

    # Save mapping: stored_name → original_path (for save-to-source later)
    mapping_file = os.path.join(target_dir, "_source_mapping.json")
    existing_mapping = {}
    if os.path.isfile(mapping_file):
        try:
            with open(mapping_file, "r", encoding="utf-8") as mf:
                existing_mapping = json.load(mf)
        except Exception:
            pass
    for src, stored in zip(file_paths, copied):
        existing_mapping[stored] = src
    with open(mapping_file, "w", encoding="utf-8") as mf:
        json.dump(existing_mapping, mf, ensure_ascii=False, indent=2)

    return jsonify({"status": "done", "copied": copied, "count": len(copied)})


@app.post("/api/splitter/save-to-source")
def splitter_save_to_source():
    """Save split output files back to the original file's folder and delete the original."""
    payload = request.get_json(force=True) or {}
    file_id = payload.get("file_id", "")
    original_path = payload.get("original_path", "")

    if not file_id:
        return jsonify({"error": "no_file_id"}), 400
    if not original_path or not os.path.isfile(original_path):
        return jsonify({"error": "original_file_not_found", "path": original_path}), 404

    # Find split output directory
    output_dir = os.path.join(os.path.dirname(__file__), "splitter_outputs", file_id)
    if not os.path.isdir(output_dir):
        return jsonify({"error": "split_output_not_found"}), 404

    target_dir = os.path.dirname(original_path)
    saved = []
    errors = []

    # Copy each split PDF to the source folder
    for fname in os.listdir(output_dir):
        if not fname.lower().endswith(".pdf"):
            continue
        src = os.path.join(output_dir, fname)
        dst = os.path.join(target_dir, fname)
        # Handle duplicate names
        if os.path.exists(dst):
            base, ext = os.path.splitext(fname)
            idx = 1
            while os.path.exists(dst):
                dst = os.path.join(target_dir, f"{base}_({idx}){ext}")
                idx += 1
        try:
            shutil.copy2(src, dst)
            saved.append(os.path.basename(dst))
        except Exception as e:
            errors.append({"file": fname, "error": str(e)})

    # Delete the original file if at least 1 split file was saved
    deleted_original = False
    if saved:
        try:
            os.remove(original_path)
            deleted_original = True
        except Exception:
            pass

    return jsonify({
        "status": "done",
        "saved": saved,
        "saved_count": len(saved),
        "deleted_original": deleted_original,
        "original_name": os.path.basename(original_path),
        "target_dir": target_dir,
        "errors": errors,
    })



@app.get("/api/splitter/source-mapping")
def splitter_source_mapping():
    """Return the stored_name → original_path mapping for save-to-source."""
    mapping_file = os.path.join("splitter_uploads", "_source_mapping.json")
    if os.path.isfile(mapping_file):
        try:
            with open(mapping_file, "r", encoding="utf-8") as mf:
                return jsonify(json.load(mf))
        except Exception:
            pass
    return jsonify({})


@app.post("/api/pipeline/send-clean-to-classifier")
def pipeline_send_clean_to_classifier():
    """Copy clean (single-doc) files directly → classifier input folder."""
    payload = request.get_json(force=True) or {}
    file_paths = payload.get("file_paths", [])
    target_dir = payload.get("target_dir", os.path.join("phanloai", "input"))

    if not file_paths:
        return jsonify({"error": "no_files_selected"}), 400

    os.makedirs(target_dir, exist_ok=True)
    copied = []
    for src in file_paths:
        if not os.path.isfile(src):
            continue
        fname = os.path.basename(src)
        dst = os.path.join(target_dir, fname)
        base, ext = os.path.splitext(fname)
        idx = 1
        while os.path.exists(dst):
            dst = os.path.join(target_dir, f"{base} ({idx}){ext}")
            idx += 1
        shutil.copy2(src, dst)
        copied.append(fname)

    return jsonify({"status": "done", "copied": copied, "count": len(copied), "target_dir": target_dir})


@app.get("/api/classifier/files")
def list_classifier_files():
    input_dir = request.args.get("input_dir", os.path.join("phanloai", "input"))
    if not os.path.isdir(input_dir):
        return jsonify({"input_dir": input_dir, "files": [], "exists": False})
    items = _list_input_files(input_dir)
    return jsonify(
        {
            "input_dir": input_dir,
            "exists": True,
            "files": items,
        }
    )


@app.post("/api/classifier/delete")
def classifier_delete_file():
    """Delete a single file from classifier input folder."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", os.path.join("phanloai", "input"))
    filename = payload.get("filename", "")
    if not filename:
        return jsonify({"error": "no_filename"}), 400
    file_path = os.path.join(input_dir, filename)
    if not os.path.isfile(file_path):
        return jsonify({"error": "file_not_found"}), 404
    os.remove(file_path)
    return jsonify({"deleted": filename})


@app.post("/api/classifier/delete-all")
def classifier_delete_all():
    """Delete all files from classifier input folder."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", os.path.join("phanloai", "input"))
    count = 0
    if os.path.isdir(input_dir):
        for fname in os.listdir(input_dir):
            fpath = os.path.join(input_dir, fname)
            if os.path.isfile(fpath):
                os.remove(fpath)
                count += 1
    return jsonify({"deleted_count": count})


@app.post("/api/classifier/run")
def run_classifier():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", os.path.join("phanloai", "input"))
    output_dir = payload.get("output_dir", os.path.join("phanloai", "output"))
    save_output = payload.get("save_output", False)  # Don't auto-save by default
    model = payload.get("model") or get_vision_model()  # classifier reads images

    if not os.path.isdir(input_dir):
        return jsonify({"error": "folder_not_found", "input_dir": input_dir}), 404

    # If save_output is False, use a temp dir so classifier doesn't write to real output
    actual_output = output_dir if save_output else os.path.join("phanloai", "_temp_output")
    result = classify_files_in_folder(input_dir=input_dir, output_dir=actual_output, model=model)
    # Store the temp dir in result so save-output can use it
    result["_temp_output"] = actual_output
    result["_final_output"] = output_dir
    return jsonify({"status": "done", **result})

@app.get("/api/classifier/last-result")
def classifier_last_result():
    """Scan _temp_output to reconstruct last classification result."""
    temp_output = os.path.join("phanloai", "_temp_output")
    if not os.path.isdir(temp_output):
        return jsonify({"exists": False})

    copied = []
    person_counts = {}
    for person_dir in sorted(os.listdir(temp_output)):
        person_path = os.path.join(temp_output, person_dir)
        if not os.path.isdir(person_path):
            continue
        count = 0
        for fname in sorted(os.listdir(person_path)):
            fpath = os.path.join(person_path, fname)
            if not os.path.isfile(fpath):
                continue
            count += 1
            # Try to extract doc_type from filename: DOMAIN_PERSON_DOCTYPE.ext
            stem = os.path.splitext(fname)[0]
            parts = stem.split("_", 2)  # DOMAIN_PERSON_DOCTYPE or just name
            doc_type = parts[-1] if len(parts) >= 3 else stem
            # Remove trailing (1), (2) etc
            import re
            doc_type = re.sub(r'\s*\(\d+\)$', '', doc_type).strip()

            rel_path = os.path.join(person_dir, fname).replace("\\", "/")
            copied.append({
                "source": fname,
                "person_name": person_dir,
                "doc_type_en": doc_type,
                "to": rel_path,
            })
        if count > 0:
            person_counts[person_dir] = count

    if not copied:
        return jsonify({"exists": False})

    return jsonify({
        "exists": True,
        "status": "done",
        "copied": copied,
        "copied_count": len(copied),
        "skipped_count": 0,
        "person_counts": person_counts,
        "_temp_output": temp_output,
        "_final_output": os.path.join("phanloai", "output"),
    })


@app.post("/api/classifier/save-output")
def classifier_save_output():
    """Copy classified results from temp to final output folder."""
    payload = request.get_json(force=True) or {}
    temp_output = payload.get("temp_output", os.path.join("phanloai", "_temp_output"))
    final_output = payload.get("output_dir", os.path.join("phanloai", "output"))

    if not os.path.isdir(temp_output):
        return jsonify({"error": "no_results_to_save"}), 404

    os.makedirs(final_output, exist_ok=True)
    count = 0
    for root, dirs, files in os.walk(temp_output):
        rel = os.path.relpath(root, temp_output)
        dest_dir = os.path.join(final_output, rel) if rel != "." else final_output
        os.makedirs(dest_dir, exist_ok=True)
        for fname in files:
            src = os.path.join(root, fname)
            dst = os.path.join(dest_dir, fname)
            shutil.copy2(src, dst)
            count += 1

    # Auto-cleanup: delete temp output to save disk space
    try:
        shutil.rmtree(temp_output)
    except Exception:
        pass

    # Optional: clean input files too
    clean_input = payload.get("clean_input", False)
    input_dir = payload.get("input_dir", os.path.join("phanloai", "input"))
    if clean_input and os.path.isdir(input_dir):
        try:
            shutil.rmtree(input_dir)
            os.makedirs(input_dir, exist_ok=True)
        except Exception:
            pass

    return jsonify({"status": "saved", "output_dir": final_output, "file_count": count})


@app.post("/api/classifier/rename-file")
def classifier_rename_file():
    """Rename/move a classified output file to a different person or doc_type."""
    payload = request.get_json(force=True) or {}
    old_path = payload.get("old_path", "")  # relative path like "UNKNOWN PERSON/FINANCIAL_BANK STATEMENT.pdf"
    new_person = payload.get("new_person", "").strip()
    new_doc_type = payload.get("new_doc_type", "").strip()
    temp_output = payload.get("temp_output", os.path.join("phanloai", "_temp_output"))

    if not old_path or not new_person:
        return jsonify({"error": "old_path and new_person are required"}), 400

    full_old = os.path.join(temp_output, old_path)
    if not os.path.isfile(full_old):
        return jsonify({"error": f"File not found: {old_path}"}), 404

    ext = os.path.splitext(full_old)[1] or ".pdf"

    # Import domain resolver from classifier
    from classifier.agent import _resolve_domain_prefix, _sanitize_name

    doc_type = _sanitize_name(new_doc_type, "DOCUMENT") if new_doc_type else "DOCUMENT"
    person_clean = _sanitize_name(new_person, "UNKNOWN PERSON")
    domain = _resolve_domain_prefix(doc_type)
    pname = person_clean.replace(" ", "_")
    stem = f"{domain}_{pname}_{doc_type}"

    # Create new person directory
    new_person_dir = os.path.join(temp_output, person_clean)
    os.makedirs(new_person_dir, exist_ok=True)
    
    # Pick a unique destination name, but don't increment if the "collision" is just the source file itself
    new_path = os.path.join(new_person_dir, f"{stem}{ext}")
    idx = 1
    while os.path.exists(new_path):
        try:
            if os.path.samefile(full_old, new_path):
                break  # The file already has this name, no collision
        except OSError:
            pass
        new_path = os.path.join(new_person_dir, f"{stem} ({idx}){ext}")
        idx += 1

    # Only move if the path actually changed
    if not (os.path.exists(new_path) and os.path.exists(full_old) and os.path.samefile(full_old, new_path)):
        try:
            shutil.move(full_old, new_path)
        except getattr(__builtins__, "FileNotFoundError", OSError):
            return jsonify({"error": f"File already moved or not found: {old_path}"}), 404

    # Clean up empty old directory
    old_dir = os.path.dirname(full_old)
    if os.path.isdir(old_dir) and not os.listdir(old_dir):
        os.rmdir(old_dir)

    new_rel = os.path.relpath(new_path, temp_output).replace("\\", "/")
    return jsonify({
        "status": "renamed",
        "old_path": old_path,
        "new_path": new_rel,
        "person_name": person_clean,
        "doc_type_en": doc_type,
    })


# ==================== PIPELINE CONNECTION ENDPOINTS ====================

@app.post("/api/pipeline/send-to-classifier")
def pipeline_send_to_classifier():
    """Copy ALL splitter output files (AI + manual) → classifier input folder.
    Walks splitter_outputs/ recursively, skipping .zip files."""
    payload = request.get_json(force=True) or {}
    file_id = payload.get("file_id", "")
    target_dir = payload.get("target_dir", os.path.join("phanloai", "input"))

    # Find source: specific file_id or all outputs
    source_dir = os.path.join("splitter_outputs", file_id) if file_id else ""
    if not source_dir or not os.path.isdir(source_dir):
        source_dir = "splitter_outputs"
        if not os.path.isdir(source_dir):
            return jsonify({"error": "no_splitter_output"}), 404

    os.makedirs(target_dir, exist_ok=True)
    copied = []
    for root, _, files in os.walk(source_dir):
        for fname in files:
            if fname.endswith(".zip"):
                continue
            if not fname.lower().endswith(".pdf"):
                continue
            src = os.path.join(root, fname)
            dst = os.path.join(target_dir, fname)
            # Avoid overwriting: add suffix if exists
            base, ext = os.path.splitext(fname)
            idx = 1
            while os.path.exists(dst):
                dst = os.path.join(target_dir, f"{base} ({idx}){ext}")
                idx += 1
            shutil.copy2(src, dst)
            copied.append(fname)

    return jsonify({"status": "done", "copied": copied, "count": len(copied), "target_dir": target_dir})


# ═══════════════════════════════════════════════════════════════════
# SCAN SPLITTER — Split scanned PDFs by Translation Certification Page
# Detects "PASSPORT LOUNGE" / "undertake to translate" certification pages
# and splits PDF at these boundaries.
# ═══════════════════════════════════════════════════════════════════

_scan_splitter_llm = None

def _get_or_create_llm():
    """Get or create a cached ChatOpenAI instance for vision tasks."""
    global _scan_splitter_llm
    if _scan_splitter_llm is None:
        _scan_splitter_llm = ChatOpenAI(model=get_vision_model(), temperature=0)
    return _scan_splitter_llm


_scan_split_progress = {"total": 0, "done": 0, "current_page": "", "running": False, "results": [], "error": ""}

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
    # Must match at least 2 keywords to avoid false positives
    matches = sum(1 for kw in _CERT_KEYWORDS if kw in text_lower)
    return matches >= 2


def _batch_detect_cert_pages_vision(llm, page_images_b64: list, page_numbers: list) -> list:
    """Batch vision: check multiple pages at once for translation certification.
    Sends bottom 40% crop of each page to save tokens.
    Returns list of page numbers that ARE certification pages."""
    from langchain_core.messages import HumanMessage, SystemMessage

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
        import json as _json
        text = result.content if hasattr(result, 'content') else str(result)
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        parsed = _json.loads(text)
        return parsed.get("cert_pages", [])
    except Exception as e:
        print(f"[SCAN-SPLITTER] ❌ Vision batch error: {e}")
        return []


@app.post("/api/scan-splitter/split")
def scan_splitter_split():
    """Upload a scanned PDF, detect translation certification pages, and split."""
    import fitz
    import base64
    global _scan_split_progress

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported"}), 400

    # Save uploaded file to temp
    scan_output_dir = "scan_splitter_outputs"
    os.makedirs(scan_output_dir, exist_ok=True)

    original_name = file.filename
    stem = os.path.splitext(original_name)[0]
    temp_pdf = os.path.join(scan_output_dir, f"_src_{original_name}")
    file.save(temp_pdf)

    # Reset progress
    _scan_split_progress = {"total": 0, "done": 0, "current_page": "", "running": True, "results": [], "error": ""}

    def _do_scan_split():
        global _scan_split_progress
        try:
            doc = fitz.open(temp_pdf)
            total_pages = len(doc)
            _scan_split_progress["total"] = total_pages

            # Phase 1: Detect certification pages
            # Step 1a: Quick text-based pass (free, instant)
            cert_pages = set()  # 0-indexed
            needs_vision = []   # pages that need vision check
            for i in range(total_pages):
                page = doc[i]
                page_text = page.get_text() or ""
                if _is_certification_page_by_text(page_text):
                    cert_pages.add(i)
                else:
                    needs_vision.append(i)

            print(f"[SCAN-SPLITTER] Text scan done: {len(cert_pages)} cert pages found by text, {len(needs_vision)} pages need vision check")
            _scan_split_progress["current_page"] = f"Text scan xong. {len(cert_pages)} trang xác nhận tìm thấy. Đang quét ảnh {len(needs_vision)} trang còn lại..."
            _scan_split_progress["done"] = len(cert_pages)

            # Step 1b: Batch vision for remaining pages (8 pages per API call, ALL PARALLEL)
            if needs_vision:
                from concurrent.futures import ThreadPoolExecutor, as_completed
                llm = _get_or_create_llm()
                BATCH_SIZE = 8

                # Phase A: Pre-render ALL page images (CPU work, fast)
                _scan_split_progress["current_page"] = "📸 Đang render ảnh tất cả trang..."
                all_images = {}  # idx -> (b64, page_num_1indexed)
                for idx in needs_vision:
                    try:
                        page = doc[idx]
                        rect = page.rect
                        clip = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y0 + rect.height / 2)
                        pix = page.get_pixmap(dpi=100, clip=clip)
                        img_bytes = pix.tobytes("png")
                        b64 = base64.b64encode(img_bytes).decode()
                        all_images[idx] = (b64, idx + 1)
                    except Exception as e:
                        print(f"[SCAN-SPLITTER] ❌ Error rendering page {idx}: {e}")

                # Phase B: Build batches and send ALL to vision API concurrently
                batches = []
                for batch_start in range(0, len(needs_vision), BATCH_SIZE):
                    batch_indices = needs_vision[batch_start:batch_start + BATCH_SIZE]
                    batch_images = []
                    batch_page_nums = []
                    for idx in batch_indices:
                        if idx in all_images:
                            b64, pnum = all_images[idx]
                            batch_images.append(b64)
                            batch_page_nums.append(pnum)
                    if batch_images:
                        batches.append((batch_images, batch_page_nums))

                total_batches = len(batches)
                _scan_split_progress["current_page"] = f"🔍 Đang gửi {total_batches} batch song song đến AI..."
                print(f"[SCAN-SPLITTER] 🚀 Sending {total_batches} batches in PARALLEL ({len(all_images)} pages total)")

                def _process_batch(batch_idx, images, page_nums):
                    """Worker: send one batch to vision API."""
                    found = _batch_detect_cert_pages_vision(llm, images, page_nums)
                    print(f"[SCAN-SPLITTER] ✅ Batch {batch_idx+1}/{total_batches} done: cert_pages={found}")
                    return found

                # Fire all batches concurrently (max 4 parallel to avoid rate limits)
                with ThreadPoolExecutor(max_workers=min(4, total_batches)) as executor:
                    futures = {
                        executor.submit(_process_batch, i, imgs, pnums): i
                        for i, (imgs, pnums) in enumerate(batches)
                    }
                    done_count = 0
                    for future in as_completed(futures):
                        done_count += 1
                        _scan_split_progress["current_page"] = f"🔍 Hoàn tất {done_count}/{total_batches} batch..."
                        _scan_split_progress["done"] = len(cert_pages) + done_count * BATCH_SIZE
                        try:
                            found_pages = future.result()
                            for pnum in found_pages:
                                cert_pages.add(pnum - 1)  # Convert back to 0-indexed
                        except Exception as e:
                            print(f"[SCAN-SPLITTER] ❌ Batch error: {e}")

            cert_pages = sorted(cert_pages)

            # Phase 2: Split PDF at certification boundaries
            # Each certification page = last page of a document group
            # Pages after last cert until next cert = one document
            _scan_split_progress["current_page"] = "Đang tách file..."

            if not cert_pages:
                _scan_split_progress["error"] = "Không tìm thấy trang xác nhận dịch nào trong file này."
                _scan_split_progress["running"] = False
                doc.close()
                return

            # Clean old output files (except source)
            for f in os.listdir(scan_output_dir):
                fp = os.path.join(scan_output_dir, f)
                if os.path.isfile(fp) and not f.startswith("_src_"):
                    os.remove(fp)

            results = []
            doc_start = 0
            for doc_idx, cert_page_idx in enumerate(cert_pages):
                doc_end = cert_page_idx  # inclusive
                page_range = f"{doc_start + 1}-{doc_end + 1}"
                out_name = f"{stem}_part{doc_idx + 1}_p{doc_start + 1}-{doc_end + 1}.pdf"
                out_path = os.path.join(scan_output_dir, out_name)

                # Create new PDF with these pages
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=doc_start, to_page=doc_end)
                new_doc.save(out_path)
                new_doc.close()

                results.append({
                    "filename": out_name,
                    "pages": page_range,
                    "page_count": doc_end - doc_start + 1,
                    "start_page": doc_start + 1,
                    "end_page": doc_end + 1,
                })
                doc_start = cert_page_idx + 1

            # Handle remaining pages after last certification (if any)
            if doc_start < total_pages:
                page_range = f"{doc_start + 1}-{total_pages}"
                out_name = f"{stem}_part{len(cert_pages) + 1}_p{doc_start + 1}-{total_pages}.pdf"
                out_path = os.path.join(scan_output_dir, out_name)

                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=doc_start, to_page=total_pages - 1)
                new_doc.save(out_path)
                new_doc.close()

                results.append({
                    "filename": out_name,
                    "pages": page_range,
                    "page_count": total_pages - doc_start,
                    "start_page": doc_start + 1,
                    "end_page": total_pages,
                    "no_cert": True,  # Flag: these pages had no certification
                })

            doc.close()
            _scan_split_progress["results"] = results
            _scan_split_progress["done"] = total_pages
            _scan_split_progress["current_page"] = f"Hoàn tất! Tách thành {len(results)} file."
            _scan_split_progress["running"] = False

        except Exception as e:
            _scan_split_progress["error"] = str(e)
            _scan_split_progress["running"] = False

    # Run in background thread
    import threading
    t = threading.Thread(target=_do_scan_split, daemon=True)
    t.start()

    return jsonify({"status": "started", "filename": original_name})


@app.get("/api/scan-splitter/progress")
def scan_splitter_progress():
    """Polling endpoint for scan split progress."""
    return jsonify(_scan_split_progress)


@app.get("/api/scan-splitter/download/<path:filename>")
def scan_splitter_download(filename):
    """Download a single split file."""
    scan_output_dir = "scan_splitter_outputs"
    fpath = os.path.join(scan_output_dir, filename)
    if not os.path.isfile(fpath):
        return jsonify({"error": "File not found"}), 404
    return send_file(fpath, as_attachment=True, download_name=filename)


@app.get("/api/scan-splitter/view/<path:filename>")
def scan_splitter_view(filename):
    """View a single split file inline in browser."""
    scan_output_dir = "scan_splitter_outputs"
    fpath = os.path.join(scan_output_dir, filename)
    if not os.path.isfile(fpath):
        return jsonify({"error": "File not found"}), 404
    return send_file(fpath, as_attachment=False, mimetype="application/pdf")


@app.get("/api/scan-splitter/download-zip")
def scan_splitter_download_zip():
    """Download all split files as ZIP."""
    import zipfile
    import io
    scan_output_dir = "scan_splitter_outputs"
    if not os.path.isdir(scan_output_dir):
        return jsonify({"error": "No output files"}), 404

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(os.listdir(scan_output_dir)):
            if f.startswith("_src_"):
                continue
            fp = os.path.join(scan_output_dir, f)
            if os.path.isfile(fp) and f.endswith(".pdf"):
                zf.write(fp, f)
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name="scan_split_results.zip")


@app.post("/api/ai-splitter/save-to-input")
def splitter_save_to_input():
    """Copy split output files back to the ORIGINAL source file's folder.
    Uses source_path from _source.json to determine correct subfolder.
    Deletes the original source file that was split.
    """
    payload = request.get_json(force=True) or {}
    target_dir = payload.get("target_dir", "input")  # fallback base
    delete_originals = payload.get("delete_originals", True)

    output_base = "splitter_outputs"
    if not os.path.isdir(output_base):
        return jsonify({"error": "no_splitter_output"}), 404

    # Also load the source mapping as fallback
    source_mapping = {}
    mapping_file = os.path.join("splitter_uploads", "_source_mapping.json")
    if os.path.isfile(mapping_file):
        try:
            with open(mapping_file, "r", encoding="utf-8") as mf:
                source_mapping = json.load(mf)
        except Exception:
            pass

    copied = []
    originals_deleted = []

    for folder_name in sorted(os.listdir(output_base)):
        folder_path = os.path.join(output_base, folder_name)
        if not os.path.isdir(folder_path):
            continue

        # Read source metadata
        source_path = ""
        source_filename = ""
        source_meta_path = os.path.join(folder_path, "_source.json")
        if os.path.isfile(source_meta_path):
            try:
                with open(source_meta_path, "r", encoding="utf-8") as mf:
                    meta = json.load(mf)
                source_path = meta.get("source_path", "")
                source_filename = meta.get("source_filename", "")
            except Exception:
                pass

        # If no source_path in _source.json, try the mapping
        if not source_path and source_filename and source_filename in source_mapping:
            source_path = source_mapping[source_filename]

        # Determine destination folder from the original file's location
        if source_path and os.path.isfile(source_path):
            dest_folder = os.path.dirname(source_path)
        elif source_path:
            # source_path set but file already deleted — use its directory
            dest_folder = os.path.dirname(source_path)
        else:
            # Last resort: search for source file in target_dir tree
            dest_folder = target_dir
            # Strip pN__ prefix to get original filename for searching
            search_name = source_filename
            if "__" in search_name:
                search_name = search_name.split("__", 1)[1]
            if search_name:
                for root, _, files in os.walk(target_dir):
                    if search_name in files:
                        dest_folder = root
                        break

        os.makedirs(dest_folder, exist_ok=True)

        # Copy all PDFs to the correct folder
        for fname in sorted(os.listdir(folder_path)):
            fpath = os.path.join(folder_path, fname)
            if not os.path.isfile(fpath) or not fname.lower().endswith(".pdf"):
                continue
            dst = os.path.join(dest_folder, fname)
            base, ext = os.path.splitext(fname)
            idx = 1
            while os.path.exists(dst):
                dst = os.path.join(dest_folder, f"{base} ({idx}){ext}")
                idx += 1
            shutil.copy2(fpath, dst)
            copied.append(fname)

        # Delete original source file
        if delete_originals and source_path and os.path.isfile(source_path):
            try:
                os.remove(source_path)
                originals_deleted.append(os.path.basename(source_path))
            except Exception:
                pass

    return jsonify({
        "status": "done",
        "copied": copied,
        "count": len(copied),
        "originals_deleted": originals_deleted,
        "target_dir": target_dir,
    })

@app.post("/api/pipeline/send-to-input")
def pipeline_send_to_input():
    """Copy classifier output files → letter/booking input folder."""
    payload = request.get_json(force=True) or {}
    source_dir = payload.get("source_dir", os.path.join("phanloai", "output"))
    target_dir = payload.get("target_dir", "input")

    if not os.path.isdir(source_dir):
        return jsonify({"error": "no_classifier_output"}), 404

    os.makedirs(target_dir, exist_ok=True)
    copied = []
    for root, _, files in os.walk(source_dir):
        for fname in files:
            src = os.path.join(root, fname)
            dst = os.path.join(target_dir, fname)
            base, ext = os.path.splitext(fname)
            idx = 1
            while os.path.exists(dst):
                dst = os.path.join(target_dir, f"{base} ({idx}){ext}")
                idx += 1
            shutil.copy2(src, dst)
            copied.append(fname)

    return jsonify({"status": "done", "copied": copied, "count": len(copied), "target_dir": target_dir})

def _safe_join(base: str, rel_path: str) -> str:
    base_abs = os.path.abspath(base)
    candidate = os.path.abspath(os.path.join(base, rel_path))
    if not candidate.startswith(base_abs):
        raise ValueError("Invalid path")
    return candidate


@app.post("/api/classifier/split_manual")
def split_manual():
    """Manual PDF splitting. Outputs go to splitter_outputs/manual_<uuid>/.
    If source_file_id + source_filename are provided (from AI results),
    the original AI file is removed from splitter_outputs so it won't be
    transferred to classifier (only the manually split files will be)."""
    payload = request.get_json(force=True) or {}
    # Source can be from AI results or from uploaded file
    source_file_id = (payload.get("source_file_id") or "").strip()
    source_filename = (payload.get("source_filename") or "").strip()
    # Legacy support: direct source path
    input_dir = payload.get("input_dir", os.path.join("phanloai", "input"))
    source = (payload.get("source") or "").strip()
    project_id = payload.get("project_id")
    segments = payload.get("segments") or []

    if not isinstance(segments, list) or not segments:
        return jsonify({"error": "missing_segments"}), 400

    # Determine source PDF path
    src_path = None
    if source_file_id and source_filename:
        # Source from AI splitter output
        candidate = SPLITTER_OUTPUT_DIR / source_file_id / source_filename
        if candidate.is_file():
            src_path = str(candidate)
    if not src_path and source:
        # Legacy: from input_dir
        try:
            src_path = _safe_join(input_dir, source)
        except ValueError:
            return jsonify({"error": "invalid_source"}), 400

    if not src_path or not os.path.exists(src_path):
        return jsonify({"error": "source_not_found"}), 404
    if os.path.splitext(src_path)[1].lower() != ".pdf":
        return jsonify({"error": "source_not_pdf"}), 400

    try:
        reader = PdfReader(src_path)
    except Exception as exc:
        return jsonify({"error": "read_pdf_failed", "detail": str(exc)}), 500

    total_pages = len(reader.pages)

    # Output goes to splitter_outputs/manual_<uuid>/
    manual_id = f"manual_{uuid.uuid4().hex[:8]}"
    output_dir = str(SPLITTER_OUTPUT_DIR / manual_id)
    os.makedirs(output_dir, exist_ok=True)

    created: list[dict[str, Any]] = []

    def _sanitize_name(value: str, fallback: str) -> str:
        text = (value or "").strip()
        text = re.sub(r"[\\/:*?\"<>|]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text or fallback

    def _pick_unique(dest_dir: str, stem: str, ext: str) -> str:
        candidate = os.path.join(dest_dir, f"{stem}{ext}")
        idx = 1
        while os.path.exists(candidate):
            candidate = os.path.join(dest_dir, f"{stem} ({idx}){ext}")
            idx += 1
        return candidate

    for seg in segments:
        if not isinstance(seg, dict):
            continue
        name = _sanitize_name(seg.get("output_name") or "", "DOCUMENT")
        try:
            s = int(seg.get("start_page"))
            e = int(seg.get("end_page"))
        except Exception:
            continue
        if s < 1 or e < 1 or s > total_pages or e > total_pages:
            continue
        if s > e:
            s, e = e, s
        writer = PdfWriter()
        for i in range(s - 1, e):
            writer.add_page(reader.pages[i])
        out_path = _pick_unique(output_dir, name, ".pdf")
        try:
            with open(out_path, "wb") as f:
                writer.write(f)
        except Exception:
            continue
        created.append(
            {
                "output_name": name,
                "start_page": s,
                "end_page": e,
                "to": os.path.relpath(out_path, output_dir).replace("\\", "/"),
            }
        )

    # If splitting from AI result, remove the original AI file so it won't be
    # transferred to classifier (only the new manual splits will be transferred).
    removed_original = None
    if source_file_id and source_filename and created:
        original_path = SPLITTER_OUTPUT_DIR / source_file_id / source_filename
        if original_path.is_file():
            os.remove(str(original_path))
            removed_original = source_filename

    # Save source metadata for persistent display
    if created:
        src_display = source_filename or source or "unknown"
        source_meta = {"source_filename": src_display, "source_type": "manual"}

        # Normalise project_id to int if possible
        if isinstance(project_id, int):
            pid = project_id
        elif isinstance(project_id, str) and project_id.isdigit():
            pid = int(project_id)
        else:
            pid = None
        if pid is not None:
            source_meta["project_id"] = pid

        with open(os.path.join(output_dir, "_source.json"), "w", encoding="utf-8") as mf:
            json.dump(source_meta, mf, ensure_ascii=False)

    return jsonify(
        {
            "status": "done",
            "manual_id": manual_id,
            "output_dir": output_dir,
            "source": source or source_filename,
            "total_pages": total_pages,
            "segments": created,
            "removed_original": removed_original,
        }
    )


def _pdf_merge_sanitize_name(value: str, fallback: str) -> str:
    text = (value or "").strip()
    text = re.sub(r"[\\/:*?\"<>|]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or fallback


def _pdf_merge_pick_unique(dest_dir: str, stem: str, ext: str) -> str:
    candidate = os.path.join(dest_dir, f"{stem}{ext}")
    idx = 1
    while os.path.exists(candidate):
        candidate = os.path.join(dest_dir, f"{stem} ({idx}){ext}")
        idx += 1
    return candidate


@app.route("/api/pdf/merge-upload", methods=["POST"])
def merge_pdf_upload():
    """Merge PDFs uploaded from user's computer. Order of form fields = page order."""
    output_dir = os.path.join("pdf", "output")
    os.makedirs(output_dir, exist_ok=True)
    output_name = (request.form.get("output_name") or "").strip()
    if not output_name:
        return jsonify({"error": "missing_output_name"}), 400

    files = request.files.getlist("file")
    if not files:
        return jsonify({"error": "missing_files"}), 400

    writer = PdfWriter()
    total_pages = 0
    used_names: List[str] = []

    for f in files:
        if not f or not getattr(f, "filename", None):
            continue
        if not str(f.filename).lower().endswith(".pdf"):
            continue
        try:
            reader = PdfReader(f.stream)
        except Exception:
            continue
        for page in reader.pages:
            writer.add_page(page)
            total_pages += 1
        used_names.append(f.filename)

    if not used_names:
        return jsonify({"error": "no_valid_pdfs"}), 400

    safe_name = _pdf_merge_sanitize_name(output_name, "MERGED")
    out_path = _pdf_merge_pick_unique(output_dir, safe_name, ".pdf")
    try:
        with open(out_path, "wb") as fp:
            writer.write(fp)
    except Exception as exc:
        return jsonify({"error": "write_failed", "detail": str(exc)}), 500

    return jsonify(
        {
            "status": "done",
            "output_dir": output_dir,
            "files": used_names,
            "file_count": len(used_names),
            "total_pages": total_pages,
            "output_file": os.path.relpath(out_path, output_dir).replace("\\", "/"),
        }
    )


@app.route("/api/pdf/merge", methods=["POST"])
def merge_pdf():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", os.path.join("pdf", "input"))
    output_dir = payload.get("output_dir", os.path.join("pdf", "output"))
    files = payload.get("files") or []
    output_name = (payload.get("output_name") or "").strip()

    if not os.path.isdir(input_dir):
        return jsonify({"error": "folder_not_found", "input_dir": input_dir}), 404
    os.makedirs(output_dir, exist_ok=True)

    if not isinstance(files, list) or not files:
        return jsonify({"error": "missing_files"}), 400
    if not output_name:
        return jsonify({"error": "missing_output_name"}), 400

    writer = PdfWriter()
    total_pages = 0
    used_files: list[str] = []

    for rel in files:
        try:
            src_path = _safe_join(input_dir, rel)
        except ValueError:
            continue
        if not os.path.exists(src_path):
            continue
        if os.path.splitext(src_path)[1].lower() != ".pdf":
            continue
        try:
            reader = PdfReader(src_path)
        except Exception:
            continue
        for page in reader.pages:
            writer.add_page(page)
            total_pages += 1
        used_files.append(os.path.relpath(src_path, input_dir).replace("\\", "/"))

    if not used_files:
        return jsonify({"error": "no_valid_pdfs"}), 400

    safe_name = _pdf_merge_sanitize_name(output_name, "MERGED")
    out_path = _pdf_merge_pick_unique(output_dir, safe_name, ".pdf")
    try:
        with open(out_path, "wb") as f:
            writer.write(f)
    except Exception as exc:
        return jsonify({"error": "write_failed", "detail": str(exc)}), 500

    return jsonify(
        {
            "status": "done",
            "input_dir": input_dir,
            "output_dir": output_dir,
            "files": used_files,
            "file_count": len(used_files),
            "total_pages": total_pages,
            "output_file": os.path.relpath(out_path, output_dir).replace("\\", "/"),
        }
    )


@app.route("/api/pdf/rename", methods=["POST"])
def rename_pdf():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", os.path.join("pdf", "input"))
    source = (payload.get("source") or "").strip()
    prefix = (payload.get("prefix") or "").strip()
    doc_type = (payload.get("doc_type") or "").strip()

    if not os.path.isdir(input_dir):
        return jsonify({"error": "folder_not_found", "input_dir": input_dir}), 404
    if not source:
        return jsonify({"error": "missing_source"}), 400
    if not prefix or not doc_type:
        return jsonify({"error": "missing_name_parts"}), 400

    try:
        src_path = _safe_join(input_dir, source)
    except ValueError:
        return jsonify({"error": "invalid_source"}), 400

    if not os.path.exists(src_path):
        return jsonify({"error": "source_not_found"}), 404
    if os.path.splitext(src_path)[1].lower() != ".pdf":
        return jsonify({"error": "source_not_pdf"}), 400

    def _sanitize_part(value: str) -> str:
        text = (value or "").strip()
        text = re.sub(r"[\\/:*?\"<>|]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _pick_unique_name(dest_dir: str, stem: str, ext: str) -> str:
        candidate = os.path.join(dest_dir, f"{stem}{ext}")
        idx = 1
        while os.path.exists(candidate):
            candidate = os.path.join(dest_dir, f"{stem} ({idx}){ext}")
            idx += 1
        return candidate

    prefix_clean = _sanitize_part(prefix)
    doc_type_clean = _sanitize_part(doc_type)
    if not prefix_clean or not doc_type_clean:
        return jsonify({"error": "invalid_name"}), 400

    stem = f"{prefix_clean} - {doc_type_clean}"
    dest_dir = os.path.dirname(src_path)
    dest_path = _pick_unique_name(dest_dir, stem, ".pdf")

    try:
        os.rename(src_path, dest_path)
    except Exception as exc:
        return jsonify({"error": "rename_failed", "detail": str(exc)}), 500

    return jsonify(
        {
            "status": "done",
            "input_dir": input_dir,
            "source": os.path.relpath(src_path, input_dir).replace("\\", "/"),
            "new_name": os.path.basename(dest_path),
            "new_rel_path": os.path.relpath(dest_path, input_dir).replace("\\", "/"),
        }
    )


@app.route("/api/pdf/rename_suggest_name", methods=["POST"])
def pdf_rename_suggest_name():
    payload = request.get_json(force=True) or {}
    input_text = (payload.get("input_text") or "").strip()
    model = payload.get("model") or get_text_model()  # text analysis

    if not input_text:
        return jsonify({"error": "missing_input_text"}), 400

    llm = ChatOpenAI(model=model, temperature=0)

    system = SystemMessage(
        content=(
            "Bạn là trợ lý đặt tên tài liệu cho hồ sơ visa. "
            "Nhiệm vụ: chuyển mô tả tiếng Việt về loại giấy tờ sang 1 cụm tiếng Anh rất ngắn gọn "
            "(tối đa khoảng 3–4 từ), ALL CAPS, phù hợp đặt tên file. "
            "Ví dụ: 'giấy khai sinh' -> 'BIRTH CERT'; 'giấy kết hôn' -> 'MARRIAGE CERT'. "
            "Chỉ trả về đúng cụm tiếng Anh, không giải thích thêm."
        )
    )
    human = HumanMessage(
        content=f"Người dùng nhập: \"{input_text}\".\nHãy trả về cụm tiếng Anh ngắn gọn để đặt tên file."
    )

    try:
        result = llm.invoke([system, human])
    except Exception as exc:
        if _is_quota_error(exc):
            return jsonify({"error": "quota_exceeded", "detail": "⚠️ Đã hết quota OpenAI API! Vui lòng kiểm tra billing."}), 429
        return jsonify({"error": "llm_error", "detail": str(exc)}), 500

    suggested = (getattr(result, "content", "") or "").strip().upper()
    suggested = re.sub(r"[^A-Z0-9\s]", " ", suggested)
    suggested = re.sub(r"\s+", " ", suggested).strip()

    if not suggested:
        return jsonify({"error": "empty_suggestion"}), 500

    return jsonify({"suggested_name": suggested})


@app.route("/api/pdf/extract-objects", methods=["POST"])
def extract_pdf_objects():
    """Extract text blocks from PDF with bbox, font, size, color info."""
    import fitz
    import io

    if "file" not in request.files:
        return jsonify({"error": "missing_file"}), 400
    f = request.files["file"]
    if not f.filename.lower().endswith(".pdf"):
        return jsonify({"error": "not_a_pdf"}), 400

    try:
        pdf_bytes = f.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        for page_idx, page in enumerate(doc):
            rect = page.rect
            page_info = {
                "pageIndex": page_idx,
                "width": rect.width,
                "height": rect.height,
                "blocks": [],
            }
            text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:  # text block only
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text:
                            continue
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        c = span.get("color", 0)
                        if isinstance(c, int):
                            color_hex = "#{:06x}".format(c)
                        else:
                            color_hex = "#000000"
                        flags = span.get("flags", 0)
                        page_info["blocks"].append({
                            "text": text,
                            "bbox": list(bbox),
                            "font": span.get("font", ""),
                            "fontSize": round(span.get("size", 12), 1),
                            "color": color_hex,
                            "bold": bool(flags & 16),
                            "italic": bool(flags & 2),
                        })
            pages.append(page_info)
        doc.close()
        return jsonify({"pages": pages})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# Mapping common PDF font names to PyMuPDF built-in fonts
_FONT_MAP = {
    "helv": "helv", "helvetica": "helv", "arial": "helv",
    "arialmt": "helv", "arial-boldmt": "hebo",
    "tiro": "tiro", "times": "tiro", "timesnewroman": "tiro",
    "timesnewromanpsmt": "tiro", "timesnewromanps-boldmt": "tibo",
    "cour": "cour", "courier": "cour", "couriernew": "cour",
    "couriernewpsmt": "cour",
    "symbol": "symb", "zapfdingbats": "zadb",
}

def _resolve_font(pdf_font_name, is_bold=False, is_italic=False):
    """Map a PDF font name to a PyMuPDF built-in font name, preserving bold/italic."""
    if not pdf_font_name:
        pdf_font_name = "helv"
    key = pdf_font_name.lower().replace(" ", "").replace("-", "")

    # Detect bold/italic from font name itself
    name_bold = "bold" in key or is_bold
    name_italic = ("italic" in key or "oblique" in key) or is_italic

    # Find base font family
    base = "helv"  # default
    if key in _FONT_MAP:
        base = _FONT_MAP[key]
    else:
        for k, v in _FONT_MAP.items():
            if k in key:
                base = v
                break

    # Pick bold/italic variant based on base font family
    # Helvetica family: helv, hebo, heit, hebi
    # Times family: tiro, tibo, tiit, tibi
    # Courier family: cour, cobo, coit, cobi
    family_variants = {
        "helv": {"b": "hebo", "i": "heit", "bi": "hebi"},
        "hebo": {"b": "hebo", "i": "hebi", "bi": "hebi"},
        "heit": {"b": "hebi", "i": "heit", "bi": "hebi"},
        "hebi": {"b": "hebi", "i": "hebi", "bi": "hebi"},
        "tiro": {"b": "tibo", "i": "tiit", "bi": "tibi"},
        "tibo": {"b": "tibo", "i": "tibi", "bi": "tibi"},
        "tiit": {"b": "tibi", "i": "tiit", "bi": "tibi"},
        "tibi": {"b": "tibi", "i": "tibi", "bi": "tibi"},
        "cour": {"b": "cobo", "i": "coit", "bi": "cobi"},
        "cobo": {"b": "cobo", "i": "cobi", "bi": "cobi"},
        "coit": {"b": "cobi", "i": "coit", "bi": "cobi"},
        "cobi": {"b": "cobi", "i": "cobi", "bi": "cobi"},
    }

    if name_bold and name_italic:
        return family_variants.get(base, {}).get("bi", base)
    if name_bold:
        return family_variants.get(base, {}).get("b", base)
    if name_italic:
        return family_variants.get(base, {}).get("i", base)
    return base


@app.route("/api/pdf/edit", methods=["POST"])
def edit_pdf():
    """Find & replace text in an uploaded PDF using PyMuPDF."""
    import fitz
    import json as _json
    import io

    if "file" not in request.files:
        return jsonify({"error": "missing_file"}), 400
    f = request.files["file"]
    if not f.filename.lower().endswith(".pdf"):
        return jsonify({"error": "not_a_pdf"}), 400

    raw_replacements = request.form.get("replacements", "[]")
    try:
        replacements = _json.loads(raw_replacements)
    except Exception:
        return jsonify({"error": "invalid_replacements_json"}), 400

    if not replacements or not isinstance(replacements, list):
        return jsonify({"error": "empty_replacements"}), 400

    try:
        pdf_bytes = f.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        for pair in replacements:
            find_text = pair.get("find", "")
            replace_text = pair.get("replace", "")
            if not find_text:
                continue

            # Use fontname from request if provided, else detect from PDF
            req_font = pair.get("fontname", "")

            for page in doc:
                hits = page.search_for(find_text)
                if not hits:
                    continue

                # Detect font info from the first hit's span
                span_font = req_font or "helv"
                span_color = (0, 0, 0)
                span_size = 0
                span_bold = False
                span_italic = False
                try:
                    text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
                    for block in text_dict.get("blocks", []):
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                if find_text in span.get("text", ""):
                                    if not req_font:
                                        span_font = span.get("font", "helv")
                                    span_size = span.get("size", 0)
                                    sflags = span.get("flags", 0)
                                    span_bold = bool(sflags & 16)
                                    span_italic = bool(sflags & 2)
                                    c = span.get("color", 0)
                                    if isinstance(c, int):
                                        span_color = (
                                            ((c >> 16) & 0xFF) / 255.0,
                                            ((c >> 8) & 0xFF) / 255.0,
                                            (c & 0xFF) / 255.0,
                                        )
                                    raise StopIteration
                except StopIteration:
                    pass

                # Try to extract & register the actual embedded font from the PDF
                use_fontname = None
                use_fontfile = None
                print(f"[PDF-EDIT] Detected font='{span_font}', size={span_size}, color={span_color}")
                try:
                    page_fonts = page.get_fonts(full=True)
                    print(f"[PDF-EDIT] Page fonts: {[(name, basefont) for xref, ext, ftype, basefont, name, enc in page_fonts]}")
                    for xref, ext, ftype, basefont, name, enc in page_fonts:
                        if name == span_font or basefont == span_font:
                            font_data = doc.extract_font(xref)
                            # font_data = (basename, ext, subtype, buffer)
                            if font_data and len(font_data) >= 4 and font_data[3]:
                                buf = font_data[3]
                                print(f"[PDF-EDIT] ✅ Extracted font '{name}' ({len(buf)} bytes), re-registering...")
                                # Register extracted font on the page
                                registered = page.insert_font(
                                    fontname=name or basefont,
                                    fontbuffer=buf,
                                )
                                use_fontname = registered
                                print(f"[PDF-EDIT] ✅ Registered as '{use_fontname}'")
                            else:
                                print(f"[PDF-EDIT] ⚠️ Font '{name}' found but no buffer data")
                            break
                except Exception as font_err:
                    print(f"[PDF-EDIT] ❌ Font extraction failed: {font_err}")

                # Fallback to built-in font mapping
                if not use_fontname:
                    use_fontname = _resolve_font(span_font, is_bold=span_bold, is_italic=span_italic)
                    print(f"[PDF-EDIT] ⚠️ Fallback to built-in font: '{span_font}' (bold={span_bold}, italic={span_italic}) → '{use_fontname}'")

                # Collect rects for redaction + text insertion
                insert_jobs = []
                for rect in hits:
                    fontsize = span_size if span_size > 4 else rect.height * 0.75
                    if fontsize < 4:
                        fontsize = 10
                    # Add redaction annotation WITHOUT fill (preserves background)
                    page.add_redact_annot(rect, fill=False)
                    insert_jobs.append((rect, fontsize))

                # Apply all redactions (removes text, keeps background)
                page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

                # Insert new text at original positions
                for rect, fontsize in insert_jobs:
                    page.insert_text(
                        fitz.Point(rect.x0, rect.y0 + rect.height * 0.8),
                        replace_text,
                        fontname=use_fontname,
                        fontsize=fontsize,
                        color=span_color,
                    )

        out_buf = io.BytesIO()
        doc.save(out_buf, garbage=4, deflate=True)
        doc.close()
        out_buf.seek(0)

        from flask import send_file
        return send_file(
            out_buf,
            mimetype="application/pdf",
            as_attachment=False,
            download_name=f.filename.replace(".pdf", "_edited.pdf"),
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.get("/api/steps")
def list_steps():
    project_id = request.args.get("project_id", type=int)
    if project_id:
        state = db.get_latest_letter_state(project_id)
        if state:
            steps = [
                {"name": "ingest", "done": state["step_ingest"]},
                {"name": "summary", "done": state["step_summary"]},
                {"name": "writer", "done": state["step_writer"]},
            ]
        else:
            steps = [{"name": s, "done": False} for s in STEP_ORDER]
        return jsonify({"steps": steps})
    # Fallback to file-based
    output_path = request.args.get("output", os.path.join("output", "letter.txt"))
    cache_dir = _cache_dir(output_path)
    steps = [
        {"name": step, "done": _is_step_done(cache_dir, step)} for step in STEP_ORDER
    ]
    return jsonify({"steps": steps})


@app.get("/api/summary")
def get_summary():
    project_id = request.args.get("project_id", type=int)
    if project_id:
        state = db.get_latest_letter_state(project_id)
        summary = state["summary_profile"] if state else ""
        return jsonify({"summary_profile": summary})
    output_path = request.args.get("output", os.path.join("output", "letter.txt"))
    cache_dir = _cache_dir(output_path)
    state_cache = _load_state(cache_dir)
    summary = state_cache.get("summary_profile", "")
    if not summary:
        path = os.path.join(cache_dir, "summary_profile.txt")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                summary = f.read()
    return jsonify({"summary_profile": summary})


@app.get("/api/writer_context")
def get_writer_context():
    project_id = request.args.get("project_id", type=int)
    if project_id:
        state = db.get_latest_letter_state(project_id)
        return jsonify({"writer_context": state["writer_context"] if state else ""})
    output_path = request.args.get("output", os.path.join("output", "letter.txt"))
    cache_dir = _cache_dir(output_path)
    state_cache = _load_state(cache_dir)
    return jsonify({"writer_context": state_cache.get("writer_context", "")})


@app.get("/api/ingest_stream")
def ingest_stream():
    input_dir = request.args.get("input_dir", "input")
    output_path = request.args.get("output", os.path.join("output", "letter.txt"))
    model = request.args.get("model") or get_vision_model()  # ingest reads images
    force = request.args.get("force", "0") == "1"
    project_id = request.args.get("project_id", type=int)

    llm = ChatOpenAI(model=model, temperature=0)
    cache_dir = _cache_dir(output_path)
    files: List[Dict[str, str]] = []

    if force:
        _reset_downstream_steps(cache_dir, "ingest")

    def sse(data: Dict) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    def generate():
        for root, _, filenames in os.walk(input_dir):
            for fname in filenames:
                path = os.path.join(root, fname)
                yield sse({"type": "progress", "message": f"Đang trích xuất: {fname}"})
                text = extract_text_with_openai(llm, path)
                files.append(
                    {
                        "path": path,
                        "name": fname,
                        "text": text,
                        "domain": detect_domain(fname),
                    }
                )
        state: GraphState = {
            "input_dir": input_dir,
            "output_path": output_path,
            "model": model,
            "llm": llm,
            "files": files,
        }
        _save_state(cache_dir, state)
        _save_step_output(cache_dir, "ingest", state)

        # Save to DB if project_id provided
        if project_id:
            db.save_letter_state(
                project_id,
                files_data=files,
                step_ingest=True,
            )

        yield sse({"type": "done"})

    return Response(generate(), mimetype="text/event-stream")


@app.get("/api/itinerary/latest")
def get_itinerary_latest():
    project_id = request.args.get("project_id", type=int)
    if project_id:
        it = db.get_latest_itinerary(project_id)
        return jsonify({"itinerary": it["html_content"] if it else ""})
    output_path = request.args.get("output", os.path.join("output", "itinerary.html"))
    cache_dir = _cache_dir(output_path)
    path = os.path.join(cache_dir, "itinerary.html")
    if not os.path.exists(path):
        return jsonify({"itinerary": ""})
    with open(path, "r", encoding="utf-8") as f:
        return jsonify({"itinerary": f.read()})


@app.get("/api/itinerary/context/latest")
def get_itinerary_context_latest():
    project_id = request.args.get("project_id", type=int)
    if project_id:
        ctx = db.get_latest_itinerary_context(project_id)
        if ctx:
            summary = _build_itinerary_summary_from_form(ctx.get("form_data", {}))
            return jsonify({"summary_profile": summary, "form_data": ctx.get("form_data", {})})
        return jsonify({"summary_profile": "", "form_data": {}})
    output_path = request.args.get("output", os.path.join("output", "itinerary.html"))
    cache_dir = _cache_dir(output_path)
    summary_path = os.path.join(cache_dir, "itinerary_summary.txt")
    meta_path = os.path.join(cache_dir, "itinerary_summary_meta.json")

    summary = ""
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            summary = f.read()

    meta: Dict[str, Any] = {"form_data": {}}
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

    return jsonify(
        {
            "summary_profile": summary,
            "form_data": meta.get("form_data", {}),
        }
    )


def _build_itinerary_summary_from_form(form_data: Dict[str, Any]) -> str:
    participants = (form_data.get("participants") or "").strip()
    additional_info = (form_data.get("additional_info") or "").strip()
    travel_purpose = (form_data.get("travel_purpose") or "").strip()
    start_date = (form_data.get("travel_start_date") or "").strip()
    end_date = (form_data.get("travel_end_date") or "").strip()
    has_any_value = any(
        [
            participants,
            additional_info,
            travel_purpose,
            start_date,
            end_date,
        ]
    )
    if not has_any_value:
        return ""

    lines: List[str] = ["Core itinerary inputs:"]
    if participants:
        lines.append(f"- Participant(s): {participants}")
    if additional_info:
        lines.append(f"- Additional information: {additional_info}")
    if start_date and end_date:
        lines.append(f"- Travel period: From {start_date} to {end_date}")
    elif start_date:
        lines.append(f"- travel_start_date: {start_date}")
    elif end_date:
        lines.append(f"- travel_end_date: {end_date}")
    if travel_purpose:
        lines.append(f"- Purpose of travel: {travel_purpose}")

    return "\n".join(lines).strip()


@app.route("/api/itinerary/context/save", methods=["POST"])
def save_itinerary_context():
    payload = request.get_json(force=True) or {}
    output_path = payload.get("output", os.path.join("output", "itinerary.html"))
    form_data = payload.get("form_data") or {}
    project_id = payload.get("project_id")

    if not isinstance(form_data, dict):
        return jsonify({"error": "invalid_form_data"}), 400

    summary_profile = _build_itinerary_summary_from_form(form_data)
    if not summary_profile:
        return jsonify({"error": "missing_context"}), 400

    # Save to file cache
    cache_dir = _cache_dir(output_path)
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "itinerary_summary.txt"), "w", encoding="utf-8") as f:
        f.write(summary_profile)
    with open(os.path.join(cache_dir, "itinerary_summary_meta.json"), "w", encoding="utf-8") as f:
        json.dump({"form_data": form_data}, f, ensure_ascii=False, indent=2)

    # Save to DB
    if project_id:
        db.save_itinerary_context(int(project_id), {"form_data": form_data})

    return jsonify(
        {
            "status": "done",
            "summary_profile": summary_profile,
            "form_data": form_data,
        }
    )


@app.post("/api/run_step")
def run_step():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_path = payload.get("output", os.path.join("output", "letter.txt"))
    step = payload.get("step")
    model = payload.get("model") or get_vision_model()  # ingest step reads images
    force = bool(payload.get("force", False))
    writer_context = (payload.get("writer_context") or "").strip()
    project_id = payload.get("project_id", type=int) if isinstance(payload.get("project_id"), int) else None

    if step not in STEP_ORDER:
        return jsonify({"error": "invalid_step"}), 400

    cache_dir = _cache_dir(output_path)
    missing = _missing_prereq_step(cache_dir, step)
    if missing and not force:
        return jsonify({"error": "missing_prerequisite", "missing": missing}), 400

    if _is_step_done(cache_dir, step) and not force:
        return jsonify({"status": "cached", "step": step})

    if force:
        _reset_downstream_steps(cache_dir, step)

    state_cache = _load_state(cache_dir)
    llm = ChatOpenAI(model=model, temperature=0)
    state: GraphState = {
        "input_dir": input_dir,
        "output_path": output_path,
        "model": model,
        "llm": llm,
        "files": state_cache.get("files", []),
        "grouped": state_cache.get("grouped", {}),
        "summary_profile": state_cache.get("summary_profile", ""),
        "writer_context": writer_context or state_cache.get("writer_context", ""),
        "letter_full": state_cache.get("letter_full", ""),
    }

    state = _run_single_step(step, state)
    _save_state(cache_dir, state)
    _save_step_output(cache_dir, step, state)

    # Save to DB if project_id provided
    if project_id:
        db_updates = {f"step_{step}": True}
        if step == "summary":
            db_updates["summary_profile"] = state.get("summary_profile", "")
        if step == "writer":
            db_updates["writer_context"] = state.get("writer_context", "")
            db_updates["letter_content"] = state.get("letter_full", "")
        db.save_letter_state(project_id, **db_updates)

    response: Dict[str, Any] = {"status": "done", "step": step}
    if step == "summary":
        response["summary_profile"] = state.get("summary_profile", "")
    if step == "writer":
        response["letter"] = state.get("letter_full", "")
        response["output_path"] = output_path

    return jsonify(response)


@app.post("/api/run_all")
def run_all():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_path = payload.get("output", os.path.join("output", "letter.txt"))
    model = payload.get("model") or get_vision_model()  # pipeline includes ingest (images)
    force = bool(payload.get("force", False))
    writer_context = (payload.get("writer_context") or "").strip()
    project_id = payload.get("project_id", type=int) if isinstance(payload.get("project_id"), int) else None

    cache_dir = _cache_dir(output_path)
    state_cache = _load_state(cache_dir)
    llm = ChatOpenAI(model=model, temperature=0)
    state: GraphState = {
        "input_dir": input_dir,
        "output_path": output_path,
        "model": model,
        "llm": llm,
        "files": state_cache.get("files", []),
        "grouped": state_cache.get("grouped", {}),
        "summary_profile": state_cache.get("summary_profile", ""),
        "writer_context": writer_context or state_cache.get("writer_context", ""),
        "letter_full": state_cache.get("letter_full", ""),
    }

    for step in STEP_ORDER:
        if _is_step_done(cache_dir, step) and not force:
            continue
        state = _run_single_step(step, state)
        _save_state(cache_dir, state)
        _save_step_output(cache_dir, step, state)

    # Save final state to DB
    if project_id:
        db.save_letter_state(
            project_id,
            files_data=state.get("files", []),
            summary_profile=state.get("summary_profile", ""),
            writer_context=state.get("writer_context", ""),
            letter_content=state.get("letter_full", ""),
            step_ingest=True,
            step_summary=True,
            step_writer=True,
        )

    return jsonify({"letter": state.get("letter_full", ""), "output_path": output_path})


@app.post("/api/run_add_file")
def run_add_file():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_path = payload.get("output", os.path.join("output", "letter.txt"))
    file_ref = payload.get("file")
    model = payload.get("model") or get_vision_model()  # reads input files (images/PDFs)
    writer_context = (payload.get("writer_context") or "").strip()

    if not file_ref:
        return jsonify({"error": "missing_file"}), 400

    resolved_path = _resolve_input_file_path(input_dir, str(file_ref))
    if not resolved_path:
        return jsonify({"error": "file_not_found"}), 404

    cache_dir = _cache_dir(output_path)
    state_cache = _load_state(cache_dir)
    llm = ChatOpenAI(model=model, temperature=0)
    state: GraphState = {
        "input_dir": input_dir,
        "output_path": output_path,
        "model": model,
        "llm": llm,
        "files": state_cache.get("files", []),
        "grouped": state_cache.get("grouped", {}),
        "summary_profile": state_cache.get("summary_profile", ""),
        "writer_context": writer_context or state_cache.get("writer_context", ""),
        "letter_full": state_cache.get("letter_full", ""),
    }

    filename = os.path.basename(resolved_path)
    text = extract_text_with_openai(llm, resolved_path)
    new_file = {
        "path": resolved_path,
        "name": filename,
        "text": text,
        "domain": detect_domain(filename),
    }
    state["files"] = _upsert_file_record(state.get("files", []), new_file)
    _save_state(cache_dir, state)
    _save_step_output(cache_dir, "ingest", state)

    for step in ["summary", "writer"]:
        state = _run_single_step(step, state)
        _save_state(cache_dir, state)
        _save_step_output(cache_dir, step, state)

    return jsonify(
        {
            "status": "done",
            "added_file": os.path.relpath(resolved_path, input_dir).replace("\\", "/"),
            "summary_profile": state.get("summary_profile", ""),
            "letter": state.get("letter_full", ""),
            "output_path": output_path,
        }
    )


@app.post("/api/itinerary/run")
def run_itinerary():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_path = payload.get("output", os.path.join("output", "itinerary.html"))
    flight_file = payload.get("flight_file")
    hotel_file = payload.get("hotel_file")
    from_db = payload.get("from_db", False)
    model = payload.get("model") or get_text_model()  # itinerary generation (text reasoning)
    project_id = payload.get("project_id")

    cache_dir = _cache_dir(output_path)
    summary_profile = (payload.get("summary_profile") or "").strip()
    if not summary_profile:
        summary_path = os.path.join(cache_dir, "itinerary_summary.txt")
        if os.path.exists(summary_path):
            with open(summary_path, "r", encoding="utf-8") as f:
                summary_profile = f.read().strip()
    # If still empty, try to build from trip info (make it optional)
    if not summary_profile and project_id:
        ti = db.get_latest_trip_info(int(project_id))
        if ti and ti.get("data"):
            d = ti["data"]
            parts = []
            if d.get("guest_names"):
                names = d["guest_names"] if isinstance(d["guest_names"], list) else [d["guest_names"]]
                parts.append("- participants: " + ", ".join(str(n) for n in names))
            if d.get("travel_start_date"):
                parts.append(f"- travel_start_date: {d['travel_start_date']}")
            if d.get("travel_end_date"):
                parts.append(f"- travel_end_date: {d['travel_end_date']}")
            if d.get("travel_purpose"):
                parts.append(f"- travel_purpose: {d['travel_purpose']}")
            if parts:
                summary_profile = "\n".join(parts)
    if not summary_profile:
        summary_profile = "Create itinerary from the provided flight and hotel booking data."

    llm = ChatOpenAI(model=model, temperature=0)

    # ── Load flight/hotel text from DB or files ──
    if from_db and project_id:
        booking = db.get_latest_booking(int(project_id))
        if not booking:
            return jsonify({"error": "no_booking_in_db", "message": "Không tìm thấy booking trong database. Hãy tạo booking AI trước."}), 400
        # Extract text from HTML (strip tags for AI processing)
        import re as _re_it
        def _html_to_text(html_str):
            text = _re_it.sub(r'<style[^>]*>.*?</style>', '', html_str, flags=_re_it.DOTALL)
            text = _re_it.sub(r'<script[^>]*>.*?</script>', '', text, flags=_re_it.DOTALL)
            text = _re_it.sub(r'<[^>]+>', ' ', text)
            text = _re_it.sub(r'\s+', ' ', text).strip()
            return text

        flight_text = _html_to_text(booking.get("flight_html", ""))
        # Combine all hotel HTMLs
        hotel_htmls = booking.get("hotel_htmls", [])
        hotel_text = "\n\n---\n\n".join(_html_to_text(h) for h in hotel_htmls)
    else:
        if not flight_file or not hotel_file:
            return jsonify({"error": "missing_files"}), 400
        flight_path = _resolve_input_file_path(input_dir, str(flight_file))
        hotel_path = _resolve_input_file_path(input_dir, str(hotel_file))
        if not flight_path or not hotel_path:
            return jsonify({"error": "missing_files"}), 400
        flight_text = extract_text_with_openai(llm, flight_path)
        hotel_text = extract_text_with_openai(llm, hotel_path)

    itinerary = itinerary_writer(llm, flight_text, hotel_text, summary_profile)

    # Save to file cache
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(itinerary)
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "itinerary.html"), "w", encoding="utf-8") as f:
        f.write(itinerary)

    # Save to DB
    if project_id:
        ctx = db.get_latest_itinerary_context(int(project_id)) or {}
        db.save_itinerary_html(int(project_id), ctx, itinerary)

    return jsonify({"itinerary": itinerary, "output_path": output_path})


@app.post("/api/itinerary/run_stream")
def run_itinerary_stream():
    """Generate itinerary with SSE progress streaming."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_path = payload.get("output", os.path.join("output", "itinerary.html"))
    flight_file = payload.get("flight_file")
    hotel_file = payload.get("hotel_file")
    from_db = payload.get("from_db", False)
    model = payload.get("model") or get_text_model()
    project_id = payload.get("project_id")

    def generate():
        def send_event(step, msg, data=None):
            evt = {"step": step, "msg": msg}
            if data is not None:
                evt["data"] = data
            yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

        # Build summary profile
        cache_dir = _cache_dir(output_path)
        summary_profile = (payload.get("summary_profile") or "").strip()
        if not summary_profile:
            summary_path = os.path.join(cache_dir, "itinerary_summary.txt")
            if os.path.exists(summary_path):
                with open(summary_path, "r", encoding="utf-8") as f:
                    summary_profile = f.read().strip()
        if not summary_profile and project_id:
            ti = db.get_latest_trip_info(int(project_id))
            if ti and ti.get("data"):
                d = ti["data"]
                parts = []
                if d.get("guest_names"):
                    names = d["guest_names"] if isinstance(d["guest_names"], list) else [d["guest_names"]]
                    parts.append("- participants: " + ", ".join(str(n) for n in names))
                if d.get("travel_start_date"):
                    parts.append(f"- travel_start_date: {d['travel_start_date']}")
                if d.get("travel_end_date"):
                    parts.append(f"- travel_end_date: {d['travel_end_date']}")
                if d.get("travel_purpose"):
                    parts.append(f"- travel_purpose: {d['travel_purpose']}")
                if parts:
                    summary_profile = "\n".join(parts)
        if not summary_profile:
            summary_profile = "Create itinerary from the provided flight and hotel booking data."

        llm = ChatOpenAI(model=model, temperature=0)

        try:
            # Step 1: Load booking data
            yield from send_event(1, "⏳ Đang tải dữ liệu booking...")

            import re as _re_it
            def _html_to_text(html_str):
                text = _re_it.sub(r'<style[^>]*>.*?</style>', '', html_str, flags=_re_it.DOTALL)
                text = _re_it.sub(r'<script[^>]*>.*?</script>', '', text, flags=_re_it.DOTALL)
                text = _re_it.sub(r'<[^>]+>', ' ', text)
                text = _re_it.sub(r'\s+', ' ', text).strip()
                return text

            if from_db and project_id:
                booking = db.get_latest_booking(int(project_id))
                if not booking:
                    yield from send_event(-1, "❌ Không tìm thấy booking trong database")
                    return
                yield from send_event(1, "✅ Đã tải booking từ database")

                # Step 2: Extract text
                yield from send_event(2, "⏳ Đang trích xuất nội dung booking...")
                flight_text = _html_to_text(booking.get("flight_html", ""))
                hotel_htmls = booking.get("hotel_htmls", [])
                hotel_text = "\n\n---\n\n".join(_html_to_text(h) for h in hotel_htmls)
                yield from send_event(2, "✅ Trích xuất nội dung hoàn tất")
            else:
                if not flight_file or not hotel_file:
                    yield from send_event(-1, "❌ Vui lòng chọn đủ file vé máy bay và khách sạn")
                    return
                flight_path = _resolve_input_file_path(input_dir, str(flight_file))
                hotel_path = _resolve_input_file_path(input_dir, str(hotel_file))
                if not flight_path or not hotel_path:
                    yield from send_event(-1, "❌ Không tìm thấy file đã chọn")
                    return
                yield from send_event(1, "✅ Đã tìm thấy file")

                yield from send_event(2, "⏳ AI đang đọc vé máy bay & khách sạn...")
                flight_text = extract_text_with_openai(llm, flight_path)
                hotel_text = extract_text_with_openai(llm, hotel_path)
                yield from send_event(2, "✅ Đọc nội dung file hoàn tất")

            # Step 3: Generate itinerary
            yield from send_event(3, "⏳ AI đang viết lịch trình chi tiết...")
            itinerary = itinerary_writer(llm, flight_text, hotel_text, summary_profile)
            yield from send_event(3, "✅ Viết lịch trình hoàn tất")

            # Step 4: Save
            yield from send_event(4, "⏳ Đang lưu kết quả...")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(itinerary)
            os.makedirs(cache_dir, exist_ok=True)
            with open(os.path.join(cache_dir, "itinerary.html"), "w", encoding="utf-8") as f:
                f.write(itinerary)
            if project_id:
                ctx = db.get_latest_itinerary_context(int(project_id)) or {}
                db.save_itinerary_html(int(project_id), ctx, itinerary)
            yield from send_event(4, "✅ Đã lưu")

            # Final result
            yield from send_event(5, "✅ Hoàn tất!", {"itinerary": itinerary, "output_path": output_path})

        except Exception as e:
            yield from send_event(-1, f"❌ Lỗi: {str(e)}")

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@app.get("/api/booking/latest_html")
def get_latest_booking_html():
    """Return the latest booking HTML from DB for use in itinerary creation."""
    project_id = request.args.get("project_id")
    if not project_id:
        return jsonify({"error": "project_id required"}), 400
    booking = db.get_latest_booking(int(project_id))
    if not booking:
        return jsonify({"has_booking": False})
    return jsonify({
        "has_booking": True,
        "hotel_htmls": booking.get("hotel_htmls", []),
        "flight_html": booking.get("flight_html", ""),
        "created_at": booking.get("created_at"),
    })


# ==================== BOOKING GENERATOR ENDPOINTS ====================

from datetime import datetime, timedelta
from booking.generator import (
    generate_all_bookings,
    fill_hotel_template,
    fill_flight_template,
    fill_vivavivu_template,
    generate_bookings_from_ai,
)
from booking.ai_agent import (
    DEFAULT_TRIP_INFO,
    extract_trip_info,
    ai_select_bookings,
    generate_ai_booking,
)


@app.post("/api/booking/generate")
def generate_booking():
    """Generate hotel and flight booking confirmations."""
    payload = request.get_json(force=True) or {}
    
    destination = payload.get("destination", "Australia")
    num_days = int(payload.get("num_days", 10))
    guest_name = payload.get("guest_name", "")
    origin_airport = payload.get("origin_airport", "HAN")
    output_dir = payload.get("output_dir", "output")
    
    # Get guest name from summary if not provided
    if not guest_name:
        guest_name = "NGUYEN VAN A"
    
    # Calculate start date (3 months from now by default)
    start_date_str = payload.get("start_date")
    if start_date_str:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    else:
        start_date = datetime.now() + timedelta(days=90)
    
    # Generate bookings
    hotel_bookings, flight_booking = generate_all_bookings(
        destination=destination,
        num_days=num_days,
        guest_name=guest_name,
        origin_airport=origin_airport,
        start_date=start_date
    )
    
    # Fill templates and save
    os.makedirs(output_dir, exist_ok=True)
    
    # Hotel template path
    hotel_template_path = os.path.join(
        os.path.dirname(__file__), 
        "templates", 
        "hotel_booking.html"
    )
    
    # Flight template path
    flight_template_path = os.path.join(
        os.path.dirname(__file__),
        "templates",
        "flight_booking.html"
    )
    
    # Generate hotel HTMLs
    hotel_htmls = []
    for i, booking in enumerate(hotel_bookings, 1):
        if os.path.exists(hotel_template_path):
            html = fill_hotel_template(hotel_template_path, booking)
        else:
            # Fallback: return JSON as HTML
            html = f"<pre>{json.dumps(booking, indent=2, ensure_ascii=False)}</pre>"
        
        output_path = os.path.join(output_dir, f"booking_hotel_{i}.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        hotel_htmls.append({"path": output_path, "html": html, "data": booking})
    
    # Generate flight HTML
    if os.path.exists(flight_template_path):
        flight_html = fill_flight_template(flight_template_path, flight_booking)
    else:
        flight_html = f"<pre>{json.dumps(flight_booking, indent=2, ensure_ascii=False)}</pre>"
    
    flight_output_path = os.path.join(output_dir, "booking_flight.html")
    with open(flight_output_path, "w", encoding="utf-8") as f:
        f.write(flight_html)
    
    return jsonify({
        "status": "success",
        "hotel_bookings": [h["data"] for h in hotel_htmls],
        "hotel_htmls": [h["html"] for h in hotel_htmls],
        "hotel_paths": [h["path"] for h in hotel_htmls],
        "flight_booking": flight_booking,
        "flight_html": flight_html,
        "flight_path": flight_output_path,
        "guest_name": guest_name,
        "destination": destination,
        "num_days": num_days,
        "start_date": start_date.strftime("%Y-%m-%d")
    })


@app.get("/api/booking/latest")
def get_booking_latest():
    """Get the latest generated booking files."""
    project_id = request.args.get("project_id", type=int)
    if project_id:
        bk = db.get_latest_booking(project_id)
        if bk:
            return jsonify({"hotel_htmls": bk["hotel_htmls"], "flight_html": bk["flight_html"]})
        return jsonify({"hotel_htmls": [], "flight_html": ""})
    output_dir = request.args.get("output_dir", "output")
    result = {"hotel_htmls": [], "flight_html": ""}
    i = 1
    while True:
        hotel_path = os.path.join(output_dir, f"booking_hotel_{i}.html")
        if os.path.exists(hotel_path):
            with open(hotel_path, "r", encoding="utf-8") as f:
                result["hotel_htmls"].append(f.read())
            i += 1
        else:
            break
    flight_path = os.path.join(output_dir, "booking_flight.html")
    if os.path.exists(flight_path):
        with open(flight_path, "r", encoding="utf-8") as f:
            result["flight_html"] = f.read()
    return jsonify(result)


@app.get("/api/booking/destinations")
def get_destinations():
    """Get available destinations from the hotels database."""
    from booking.generator import load_hotels_database
    
    hotels_db = load_hotels_database()
    destinations = [key for key in hotels_db.keys() if key != "flights"]
    
    return jsonify({"destinations": destinations})


# ==================== AI BOOKING ENDPOINTS ====================

@app.get("/api/booking/filtered-files")
def booking_filtered_files():
    """List files in input dir, categorized by trip-info prefix."""
    input_dir = request.args.get("input_dir", "input")
    project_id = request.args.get("project_id", type=int)
    guest_names_param = request.args.get("guest_names", "")

    if not os.path.isdir(input_dir):
        return jsonify({"files": [], "matched": [], "other": []})

    # Get guest names for filtering (from param or DB)
    guest_names = [n.strip() for n in guest_names_param.split(",") if n.strip()] if guest_names_param else []
    if not guest_names and project_id:
        saved_ti = db.get_latest_trip_info(project_id)
        if saved_ti and saved_ti.get("data", {}).get("guest_names"):
            guest_names = saved_ti["data"]["guest_names"]

    def _filename_matches_guests(fname, names):
        if not names:
            return True  # No filter = show all
        normalized_fname = re.sub(r'[\s\-_]+', ' ', os.path.splitext(fname)[0].upper()).strip()
        for name in names:
            normalized_name = re.sub(r'[\s\-_]+', ' ', name.upper()).strip()
            if not normalized_name:
                continue
            name_parts = [p for p in normalized_name.split() if len(p) > 1]
            if len(name_parts) >= 2 and all(part in normalized_fname for part in name_parts):
                return True
        return False

    PREFIXES = {
        "OVERVIEW": "🌍 Tổng quan",
        "TONG QUAN": "🌍 Tổng quan",
        "PERSONAL": "👤 Hồ sơ cá nhân",
        "HO SO CA NHAN": "👤 Hồ sơ cá nhân",
        "PURPOSE": "🎯 Mục đích",
        "MUC DICH CHUYEN DI": "🎯 Mục đích",
    }
    matched = []
    other = []
    for root, _, filenames in os.walk(input_dir):
        for fname in sorted(filenames):
            # Filter by guest names if available
            if guest_names and not _filename_matches_guests(fname, guest_names):
                continue

            stem = os.path.splitext(fname)[0]
            normalized = re.sub(r"[\s\-_]+", " ", stem.upper()).strip()
            rel = os.path.relpath(os.path.join(root, fname), input_dir).replace("\\", "/")
            found_prefix = None
            found_label = None
            for prefix, label in PREFIXES.items():
                if normalized.startswith(prefix):
                    found_prefix = prefix
                    found_label = label
                    break
            if found_prefix:
                matched.append({"filename": fname, "path": rel, "prefix": found_prefix, "label": found_label})
            else:
                other.append({"filename": fname, "path": rel})

    return jsonify({"matched": matched, "other": other, "total": len(matched) + len(other)})


@app.post("/api/booking/extract_trip")
def extract_trip():
    """Extract trip information from input files."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    model = payload.get("model") or get_vision_model()  # reads input files (may contain images)
    project_id = payload.get("project_id")
    # Get saved guest names to filter input files by project
    saved_guest_names = payload.get("guest_names") or []
    if not saved_guest_names and project_id:
        saved_ti = db.get_latest_trip_info(int(project_id))
        if saved_ti and saved_ti.get("data", {}).get("guest_names"):
            saved_guest_names = saved_ti["data"]["guest_names"]

    llm = ChatOpenAI(model=model, temperature=0)

    try:
        trip_info = extract_trip_info(llm, input_dir, guest_names=saved_guest_names)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if not isinstance(trip_info, dict):
        trip_info = dict(DEFAULT_TRIP_INFO)

    # Cache trip info to file
    cache_dir = _cache_dir(os.path.join("output", "letter.txt"))
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "booking_trip_info.json"), "w", encoding="utf-8") as f:
        json.dump(trip_info, f, ensure_ascii=False, indent=2)
    booking_cache = os.path.join(cache_dir, "ai_booking_data.json")
    if os.path.exists(booking_cache):
        os.remove(booking_cache)

    # Save to DB
    if project_id:
        db.save_trip_info(int(project_id), trip_info)
        # Update input hash
        input_hash = db.compute_input_hash(input_dir)
        db.update_project(int(project_id), input_hash=input_hash)

    return jsonify({"status": "success", "trip_info": trip_info})


@app.get("/api/booking/trip/latest")
def get_booking_trip_latest():
    """Load cached trip info for editing in frontend."""
    project_id = request.args.get("project_id", type=int)
    if project_id:
        ti = db.get_latest_trip_info(project_id)
        data = ti["data"] if ti else dict(DEFAULT_TRIP_INFO)
        return jsonify({"trip_info": data})
    cache_dir = _cache_dir(os.path.join("output", "letter.txt"))
    trip_path = os.path.join(cache_dir, "booking_trip_info.json")
    if not os.path.exists(trip_path):
        return jsonify({"trip_info": dict(DEFAULT_TRIP_INFO)})
    with open(trip_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    merged = dict(DEFAULT_TRIP_INFO)
    if isinstance(data, dict):
        merged.update(data)
    return jsonify({"trip_info": merged})


@app.post("/api/booking/trip/save")
def save_booking_trip():
    """Save edited trip info from frontend."""
    payload = request.get_json(force=True) or {}
    trip_info = payload.get("trip_info") or {}
    project_id = payload.get("project_id")
    if not isinstance(trip_info, dict):
        return jsonify({"error": "invalid_trip_info"}), 400

    merged = dict(DEFAULT_TRIP_INFO)
    merged.update(trip_info)

    # Save to file cache
    cache_dir = _cache_dir(os.path.join("output", "letter.txt"))
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "booking_trip_info.json"), "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    booking_cache = os.path.join(cache_dir, "ai_booking_data.json")
    if os.path.exists(booking_cache):
        os.remove(booking_cache)

    # Save to DB
    if project_id:
        db.save_trip_info(int(project_id), merged)

    return jsonify({"status": "success", "trip_info": merged})


@app.post("/api/booking/ai_generate")
def ai_generate_booking():
    """Generate bookings using AI. Uses cached booking data if available to save tokens."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_dir = payload.get("output_dir", "output")
    model = payload.get("model") or get_text_model()  # booking uses text reasoning
    force_new = payload.get("force_new", False)
    target = (payload.get("target") or "both").strip().lower()
    if target not in ["both", "hotel", "flight"]:
        target = "both"
    trip_info_override = payload.get("trip_info")
    project_id = payload.get("project_id")

    cache_dir = _cache_dir(os.path.join("output", "letter.txt"))
    booking_cache_path = os.path.join(cache_dir, "ai_booking_data.json")
    trip_cache_path = os.path.join(cache_dir, "booking_trip_info.json")

    # If user edited trip info on frontend, persist and force new booking.
    if isinstance(trip_info_override, dict):
        merged_trip = dict(DEFAULT_TRIP_INFO)
        merged_trip.update(trip_info_override)
        os.makedirs(cache_dir, exist_ok=True)
        with open(trip_cache_path, "w", encoding="utf-8") as f:
            json.dump(merged_trip, f, ensure_ascii=False, indent=2)
        force_new = True
        if os.path.exists(booking_cache_path):
            os.remove(booking_cache_path)

    # --- Check for cached booking data first (skip AI to save tokens) ---
    booking_data = None
    trip_info = None
    used_cache = False

    if not force_new and os.path.exists(booking_cache_path):
        with open(booking_cache_path, "r", encoding="utf-8") as f:
            booking_data = json.load(f)
        if os.path.exists(trip_cache_path):
            with open(trip_cache_path, "r", encoding="utf-8") as f:
                trip_info = json.load(f)
        used_cache = True

    # --- If no cache, call AI ---
    if not booking_data:
        if os.path.exists(trip_cache_path):
            with open(trip_cache_path, "r", encoding="utf-8") as f:
                trip_info = json.load(f)

        llm = ChatOpenAI(model=model, temperature=0)

        try:
            trip_info, booking_data = generate_ai_booking(llm, input_dir, trip_info)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": f"Lỗi AI: {str(e)}"}), 500

        # Cache booking data for next time
        os.makedirs(cache_dir, exist_ok=True)
        with open(booking_cache_path, "w", encoding="utf-8") as f:
            json.dump(booking_data, f, ensure_ascii=False, indent=2)

    # Template paths
    hotel_template_path = os.path.join(
        os.path.dirname(__file__),
        "templates",
        "hotel_booking.html"
    )
    flight_template_path = os.path.join(
        os.path.dirname(__file__),
        "templates",
        "flight_booking.html"
    )

    try:
        selected_booking_data = dict(booking_data or {})
        if target == "hotel":
            selected_booking_data["flight"] = {}
        elif target == "flight":
            selected_booking_data["hotels"] = []

        # Generate HTML files from AI decisions
        result = generate_bookings_from_ai(
            ai_booking_data=selected_booking_data,
            hotel_template_path=hotel_template_path,
            flight_template_path=flight_template_path,
            output_dir=output_dir,
        )

        # Save to DB
        if project_id:
            existing = db.get_latest_booking(int(project_id)) or {}
            final_hotel_htmls = result["hotel_htmls"] if target in ["both", "hotel"] else existing.get("hotel_htmls", [])
            final_flight_html = result["flight_html"] if target in ["both", "flight"] else existing.get("flight_html", "")
            db.save_booking(
                int(project_id),
                booking_data=booking_data,
                hotel_htmls=final_hotel_htmls,
                flight_html=final_flight_html,
                reasoning=booking_data.get("reasoning", ""),
            )

        return jsonify({
            "status": "success",
            "used_cache": used_cache,
            "trip_info": trip_info,
            "booking_data": {
                "hotels": result["hotel_data"],
                "reasoning": booking_data.get("reasoning", ""),
            },
            "hotel_htmls": result["hotel_htmls"],
            "hotel_paths": result["hotel_paths"],
            "flight_html": result["flight_html"],
            "flight_path": result["flight_path"],
        })
    except Exception as e:
        import traceback
        return jsonify({"error": "Lỗi khi tạo HTML: " + str(e), "traceback": traceback.format_exc()}), 500


@app.post("/api/booking/ai_generate_stream")
def ai_generate_booking_stream():
    """Generate bookings using AI with SSE progress streaming."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_dir = payload.get("output_dir", "output")
    model = payload.get("model") or get_text_model()
    force_new = payload.get("force_new", False)
    target = (payload.get("target") or "both").strip().lower()
    if target not in ["both", "hotel", "flight"]:
        target = "both"
    trip_info_override = payload.get("trip_info")
    project_id = payload.get("project_id")

    cache_dir = _cache_dir(os.path.join("output", "letter.txt"))
    booking_cache_path = os.path.join(cache_dir, "ai_booking_data.json")
    trip_cache_path = os.path.join(cache_dir, "booking_trip_info.json")

    def generate():
        import time as _time

        def send_event(step, msg, data=None):
            evt = {"step": step, "msg": msg}
            if data is not None:
                evt["data"] = data
            yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

        nonlocal force_new

        # If user edited trip info on frontend, persist and force new booking.
        if isinstance(trip_info_override, dict):
            merged_trip = dict(DEFAULT_TRIP_INFO)
            merged_trip.update(trip_info_override)
            os.makedirs(cache_dir, exist_ok=True)
            with open(trip_cache_path, "w", encoding="utf-8") as f:
                json.dump(merged_trip, f, ensure_ascii=False, indent=2)
            force_new = True
            if os.path.exists(booking_cache_path):
                os.remove(booking_cache_path)

        booking_data = None
        trip_info = None
        used_cache = False

        # Check cache
        if not force_new and os.path.exists(booking_cache_path):
            yield from send_event(1, "✅ Đã tìm thấy dữ liệu cache, bỏ qua AI")
            with open(booking_cache_path, "r", encoding="utf-8") as f:
                booking_data = json.load(f)
            if os.path.exists(trip_cache_path):
                with open(trip_cache_path, "r", encoding="utf-8") as f:
                    trip_info = json.load(f)
            used_cache = True

        # If no cache, call AI with progress
        if not booking_data:
            if os.path.exists(trip_cache_path):
                with open(trip_cache_path, "r", encoding="utf-8") as f:
                    trip_info = json.load(f)

            llm = ChatOpenAI(model=model, temperature=0)

            def progress_cb(step, msg):
                pass  # Can't yield inside callback; we handle steps inline

            try:
                # Step 1: Extract or load trip info
                if not trip_info:
                    yield from send_event(1, "⏳ Đang trích xuất thông tin chuyến đi từ file...")
                    # Get saved guest names to filter input files by project
                    saved_guest_names = []
                    if project_id:
                        saved_ti = db.get_latest_trip_info(int(project_id))
                        if saved_ti and saved_ti.get("data", {}).get("guest_names"):
                            saved_guest_names = saved_ti["data"]["guest_names"]
                    trip_info = extract_trip_info(llm, input_dir, guest_names=saved_guest_names)
                    yield from send_event(1, "✅ Trích xuất thông tin chuyến đi hoàn tất")
                else:
                    yield from send_event(1, "✅ Đã có thông tin chuyến đi")

                if not trip_info or not trip_info.get("destination_country"):
                    yield from send_event(-1, "❌ Không thể trích xuất thông tin chuyến đi")
                    return

                # Step 2: AI select bookings (use mini model for cost savings)
                if target == "hotel":
                    yield from send_event(2, "⏳ AI đang chọn khách sạn...")
                elif target == "flight":
                    yield from send_event(2, "⏳ AI đang chọn chuyến bay...")
                else:
                    yield from send_event(2, "⏳ AI đang chọn khách sạn & chuyến bay...")
                booking_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
                booking_data = ai_select_bookings(booking_llm, trip_info)
                if target == "hotel":
                    yield from send_event(2, "✅ AI đã chọn xong khách sạn")
                elif target == "flight":
                    yield from send_event(2, "✅ AI đã chọn xong chuyến bay")
                else:
                    yield from send_event(2, "✅ AI đã chọn xong khách sạn & chuyến bay")

                if not booking_data:
                    yield from send_event(-1, "❌ AI không thể tạo booking")
                    return
                if target in ["both", "hotel"] and not booking_data.get("hotels"):
                    yield from send_event(-1, "❌ AI không thể tạo booking khách sạn")
                    return
                if target in ["both", "flight"] and not booking_data.get("flight"):
                    yield from send_event(-1, "❌ AI không thể tạo booking")
                    return

                # Cache
                os.makedirs(cache_dir, exist_ok=True)
                with open(booking_cache_path, "w", encoding="utf-8") as f:
                    json.dump(booking_data, f, ensure_ascii=False, indent=2)

            except Exception as e:
                yield from send_event(-1, f"❌ Lỗi AI: {str(e)}")
                return

        # Step 3: Generate HTML
        if target == "hotel":
            yield from send_event(3, "⏳ Đang tạo file HTML khách sạn...")
        elif target == "flight":
            yield from send_event(3, "⏳ Đang tạo file HTML máy bay...")
        else:
            yield from send_event(3, "⏳ Đang tạo file HTML booking...")

        hotel_template_path = os.path.join(os.path.dirname(__file__), "templates", "hotel_booking.html")
        flight_template_path = os.path.join(os.path.dirname(__file__), "templates", "flight_booking.html")

        try:
            selected_booking_data = dict(booking_data or {})
            if target == "hotel":
                selected_booking_data["flight"] = {}
            elif target == "flight":
                selected_booking_data["hotels"] = []

            result = generate_bookings_from_ai(
                ai_booking_data=selected_booking_data,
                hotel_template_path=hotel_template_path,
                flight_template_path=flight_template_path,
                output_dir=output_dir,
            )

            if project_id:
                existing = db.get_latest_booking(int(project_id)) or {}
                final_hotel_htmls = result["hotel_htmls"] if target in ["both", "hotel"] else existing.get("hotel_htmls", [])
                final_flight_html = result["flight_html"] if target in ["both", "flight"] else existing.get("flight_html", "")
                db.save_booking(
                    int(project_id),
                    booking_data=booking_data,
                    hotel_htmls=final_hotel_htmls,
                    flight_html=final_flight_html,
                    reasoning=booking_data.get("reasoning", ""),
                )

            if target == "hotel":
                yield from send_event(3, "✅ Tạo HTML khách sạn hoàn tất")
            elif target == "flight":
                yield from send_event(3, "✅ Tạo HTML máy bay hoàn tất")
            else:
                yield from send_event(3, "✅ Tạo HTML booking hoàn tất")

            # Final result
            final = {
                "status": "success",
                "used_cache": used_cache,
                "trip_info": trip_info,
                "booking_data": {
                    "hotels": result["hotel_data"],
                    "reasoning": booking_data.get("reasoning", ""),
                },
                "hotel_htmls": result["hotel_htmls"],
                "hotel_paths": result["hotel_paths"],
                "flight_html": result["flight_html"],
                "flight_path": result["flight_path"],
            }
            yield from send_event(4, "✅ Hoàn tất!", final)

        except Exception as e:
            import traceback
            yield from send_event(-1, f"❌ Lỗi tạo HTML: {str(e)}")

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


# ==================== SERPAPI FLIGHT SEARCH ENDPOINTS ====================

def _get_serpapi_key() -> str:
    return os.getenv("SERPAPI_KEY", "5ce801b1ff2274fc0f430d0fb53c26570893c0edbfede9ffe68a342ca05bf557")


@app.post("/api/flights/search")
def search_flights():
    """Search flights using SerpAPI Google Flights engine."""
    try:
        from serpapi import GoogleSearch
    except ImportError:
        return jsonify({"error": "google-search-results package not installed. Run: pip install google-search-results"}), 500

    payload = request.get_json(force=True) or {}
    flight_type = str(payload.get("type", 2))
    departure_id = payload.get("departure_id", "")
    arrival_id = payload.get("arrival_id", "")
    outbound_date = payload.get("outbound_date", "")

    if not departure_id or not outbound_date:
        return jsonify({"error": "departure_id and outbound_date are required"}), 400
    if flight_type != "3" and not arrival_id:
        return jsonify({"error": "arrival_id is required for non-multi-city searches"}), 400

    params = {
        "engine": "google_flights",
        "hl": payload.get("hl", "en"),
        "gl": payload.get("gl", "vn"),
        "type": flight_type,
        "departure_id": departure_id,
        "arrival_id": arrival_id,
        "outbound_date": outbound_date,
        "adults": int(payload.get("adults", 1)),
        "currency": payload.get("currency", "VND"),
        "api_key": _get_serpapi_key(),
    }

    if payload.get("return_date"):
        params["return_date"] = payload["return_date"]
    if payload.get("children"):
        params["children"] = int(payload["children"])
    if payload.get("departure_token"):
        params["departure_token"] = payload["departure_token"]
    if payload.get("multi_city_json"):
        params["multi_city_json"] = payload["multi_city_json"]

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
    except Exception as e:
        return jsonify({"error": f"SerpAPI error: {str(e)}"}), 500

    return jsonify({
        "best_flights": results.get("best_flights", []),
        "other_flights": results.get("other_flights", []),
        "search_parameters": results.get("search_parameters", {}),
    })


def _serp_dt_parts(dt_str: str) -> tuple[str, str]:
    if not dt_str:
        return "", ""
    parts = dt_str.strip().split(" ")
    if len(parts) < 2:
        return "", ""
    ymd = parts[0]
    hm = parts[1]
    try:
        yyyy, mm, dd = ymd.split("-")
        return f"{dd}/{mm}/{yyyy}", hm
    except Exception:
        return "", hm


def _serp_minutes_to_duration(minutes: Any) -> str:
    try:
        total = int(minutes or 0)
    except Exception:
        total = 0
    h = total // 60
    m = total % 60
    if h and m:
        return f"{h}h {m}m"
    if h:
        return f"{h}h"
    return f"{m}m"


def _map_serp_option_to_vna_segment(option: Dict[str, Any]) -> Dict[str, Any]:
    flights = option.get("flights", []) if isinstance(option, dict) else []
    first = flights[0] if flights else {}
    last = flights[-1] if flights else {}

    dep_air = first.get("departure_airport", {}) if isinstance(first, dict) else {}
    arr_air = last.get("arrival_airport", {}) if isinstance(last, dict) else {}
    dep_date, dep_time = _serp_dt_parts(dep_air.get("time", ""))
    arr_date, arr_time = _serp_dt_parts(arr_air.get("time", ""))

    all_numbers = [
        (f.get("flight_number") or "").strip()
        for f in flights
        if isinstance(f, dict) and (f.get("flight_number") or "").strip()
    ]
    flight_number = " / ".join(all_numbers)

    baggage = ""
    for ext in option.get("extensions", []) or []:
        if isinstance(ext, str) and "baggage" in ext.lower():
            baggage = ext
            break

    return {
        "flight_number": flight_number,
        "airline": first.get("airline", ""),
        "departure_date": dep_date,
        "departure_time": dep_time,
        "departure_airport": dep_air.get("id", ""),
        "departure_city": dep_air.get("name", ""),
        "departure_terminal": "",
        "arrival_date": arr_date,
        "arrival_time": arr_time,
        "arrival_airport": arr_air.get("id", ""),
        "arrival_city": arr_air.get("name", ""),
        "arrival_terminal": "",
        "duration": _serp_minutes_to_duration(option.get("total_duration")),
        "baggage": baggage,
    }


@app.post("/api/flights/generate_from_serp")
def generate_flight_from_serp():
    """Generate flight booking HTML from selected SerpAPI options."""
    payload = request.get_json(force=True) or {}
    template_type = (payload.get("template_type") or "vivavivu").strip().lower()

    selected_outbound = payload.get("selected_outbound") or {}
    selected_return = payload.get("selected_return") or {}
    trip_type = payload.get("trip_type", "One way")
    passengers = payload.get("passengers") or []

    if not selected_outbound:
        return jsonify({"error": "selected_outbound is required"}), 400

    output_dir = payload.get("output_dir", "output")
    os.makedirs(output_dir, exist_ok=True)

    if template_type == "vietnam_airlines":
        template_path = os.path.join(os.path.dirname(__file__), "templates", "flight_booking.html")
        if not os.path.exists(template_path):
            return jsonify({"error": "Vietnam Airlines template not found"}), 500

        mapped_outbound = _map_serp_option_to_vna_segment(selected_outbound)
        mapped_return = _map_serp_option_to_vna_segment(selected_return or selected_outbound)

        flight_data = {
            "trip_type": trip_type,
            "booking_reference": "",
            "passengers": [
                {"name": (p.get("name") or "").strip(), "type": "Adult"}
                for p in passengers
                if isinstance(p, dict) and (p.get("name") or "").strip()
            ],
            "outbound_flight": mapped_outbound,
            "return_flight": mapped_return,
        }
        html = fill_flight_template(template_path, flight_data)
    else:
        template_path = os.path.join(os.path.dirname(__file__), "templates", "flight_vivavivu.html")
        if not os.path.exists(template_path):
            return jsonify({"error": "Vivavivu template not found"}), 500

        flight_data = {
            "booking_code": payload.get("booking_code"),
            "trip_type": trip_type,
            "contact": payload.get("contact", {}),
            "passengers": passengers,
            "total_price": payload.get("total_price", "0"),
            "discount": payload.get("discount", "0"),
            "currency": payload.get("currency", "VND"),
            "directions": payload.get("directions", []),
        }
        html = fill_vivavivu_template(template_path, flight_data)

    output_path = os.path.join(output_dir, "booking_flight.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    project_id = payload.get("project_id")
    if project_id:
        existing = db.get_latest_booking(int(project_id)) or {}
        db.save_booking(
            int(project_id),
            booking_data=existing.get("booking_data", {}),
            hotel_htmls=existing.get("hotel_htmls", []),
            flight_html=html,
            reasoning=existing.get("reasoning", ""),
        )

    return jsonify({
        "status": "success",
        "flight_html": html,
        "flight_path": output_path,
    })


# ==================== AI PDF SPLITTER ENDPOINTS ====================

import uuid
import shutil
import zipfile
import threading
from pathlib import Path as SplitterPath

from pdf_tools.pdf_service import pdf_to_images, get_page_count, create_output_files
from pdf_tools.ai_service import classify_all_pages

# Directories for AI splitter
SPLITTER_UPLOAD_DIR = SplitterPath(__file__).parent / "splitter_uploads"
SPLITTER_OUTPUT_DIR = SplitterPath(__file__).parent / "splitter_outputs"
SPLITTER_UPLOAD_DIR.mkdir(exist_ok=True)
SPLITTER_OUTPUT_DIR.mkdir(exist_ok=True)

# In-memory job tracking for AI splitter
splitter_jobs: Dict[str, Dict] = {}


def _run_splitter_job(file_id: str):
    """Run AI PDF splitting in a background thread with its own event loop."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_process_splitter_job(file_id))
    finally:
        loop.close()


async def _process_splitter_job(file_id: str):
    """Process a PDF file: convert → classify → split."""
    job = splitter_jobs[file_id]
    try:
        # Step 1: Convert PDF pages to images
        job["status"] = "converting"
        images = pdf_to_images(job["file_path"])

        # Step 2: Classify each page with AI
        job["status"] = "classifying"

        async def progress_callback(page_num, total, result):
            job["current_page"] = page_num
            job["classifications"].append({
                "page": page_num,
                "document_type_en": result.get("document_type_en", ""),
                "person_name_en": result.get("person_name_en", ""),
                "is_continuation": result.get("is_continuation", False),
            })

        classifications = await classify_all_pages(
            images, progress_callback=progress_callback
        )

        # Update with post-processed data
        job["classifications"] = []
        for idx, cls in enumerate(classifications):
            job["classifications"].append({
                "page": idx + 1,
                "document_type_en": cls.get("document_type_en", ""),
                "person_name_en": cls.get("person_name_en", ""),
                "is_continuation": cls.get("is_continuation", False),
            })

        # Step 3: Create output files
        job["status"] = "splitting"
        job_output_dir = str(SPLITTER_OUTPUT_DIR / file_id)
        output_files = create_output_files(
            job["file_path"], classifications, job_output_dir
        )
        job["output_files"] = output_files

        # Save source metadata for persistent display
        source_meta = {"source_filename": job["filename"], "source_type": "ai"}
        pid = job.get("project_id")
        if pid is not None:
            source_meta["project_id"] = pid
        # Also store original source path from mapping (for save-to-input)
        mapping_file = os.path.join("splitter_uploads", "_source_mapping.json")
        if os.path.isfile(mapping_file):
            try:
                with open(mapping_file, "r", encoding="utf-8") as mmf:
                    mapping = json.load(mmf)
                orig_path = mapping.get(job["filename"], "")
                if orig_path:
                    source_meta["source_path"] = orig_path
            except Exception:
                pass
        with open(os.path.join(job_output_dir, "_source.json"), "w", encoding="utf-8") as mf:
            json.dump(source_meta, mf, ensure_ascii=False)

        # Step 4: Create ZIP
        zip_path = str(SPLITTER_OUTPUT_DIR / f"{file_id}.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in output_files:
                zf.write(f["path"], f["filename"])
        job["zip_path"] = zip_path
        job["status"] = "completed"

    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        print(f"[AI Splitter] Error processing {file_id}: {e}")


@app.get("/api/ai-splitter/list")
def splitter_list_files():
    """List PDF files already in splitter_uploads folder."""
    upload_dir = str(SPLITTER_UPLOAD_DIR)
    project_id = request.args.get("project_id", type=int)
    if not os.path.isdir(upload_dir):
        return jsonify({"files": []})
    files = []
    for fname in sorted(os.listdir(upload_dir)):
        path = os.path.join(upload_dir, fname)
        if not (os.path.isfile(path) and fname.lower().endswith(".pdf")):
            continue

        display_name = fname
        file_pid: Optional[int] = None

        # New convention: filenames starting with p<id>__ belong to a specific project
        match = re.match(r"p(\d+)__(.+)", fname, re.IGNORECASE)
        if match:
            try:
                file_pid = int(match.group(1))
            except ValueError:
                file_pid = None
            display_name = match.group(2)

        if project_id is not None and file_pid != project_id:
            continue

        files.append(
            {
                "filename": fname,  # stored name used by APIs
                "display_name": display_name,  # original name for UI
                "size": os.path.getsize(path),
            }
        )
    return jsonify({"files": files})


@app.post("/api/ai-splitter/delete")
def splitter_delete_file():
    """Delete a single file from splitter_uploads."""
    payload = request.get_json(force=True) or {}
    filename = payload.get("filename", "")
    if not filename:
        return jsonify({"error": "no_filename"}), 400
    file_path = SPLITTER_UPLOAD_DIR / filename
    if not file_path.is_file():
        return jsonify({"error": "file_not_found"}), 404
    os.remove(str(file_path))
    return jsonify({"deleted": filename})


@app.post("/api/ai-splitter/delete-all")
def splitter_delete_all():
    """Delete all PDF files from splitter_uploads. If project_id is in body, only delete files with p{id}__ prefix."""
    payload = request.get_json(force=True) or {}
    project_id = payload.get("project_id")
    pid = None
    if isinstance(project_id, int):
        pid = project_id
    elif isinstance(project_id, str) and project_id.isdigit():
        pid = int(project_id)
    upload_dir = str(SPLITTER_UPLOAD_DIR)
    count = 0
    if os.path.isdir(upload_dir):
        for fname in os.listdir(upload_dir):
            fpath = os.path.join(upload_dir, fname)
            if not (os.path.isfile(fpath) and fname.lower().endswith(".pdf")):
                continue
            if pid is not None:
                match = re.match(r"p" + str(pid) + r"__(.+)", fname)
                if not match:
                    continue
            os.remove(fpath)
            count += 1
    return jsonify({"deleted_count": count})


@app.post("/api/ai-splitter/process-local")
def splitter_process_local():
    """Process a PDF already in splitter_uploads (no upload needed)."""
    payload = request.get_json(force=True) or {}
    filename = payload.get("filename", "")
    project_id = payload.get("project_id")
    if not filename:
        return jsonify({"error": "no_filename"}), 400

    src_path = SPLITTER_UPLOAD_DIR / filename
    if not src_path.is_file():
        return jsonify({"error": "file_not_found"}), 404

    import threading

    # Normalise project_id to int if possible
    if isinstance(project_id, int):
        pid: Optional[int] = project_id
    elif isinstance(project_id, str) and project_id.isdigit():
        pid = int(project_id)
    else:
        pid = None

    file_id = uuid.uuid4().hex[:8]
    # Copy to sub-folder (same structure as upload flow)
    job_dir = SPLITTER_UPLOAD_DIR / file_id
    job_dir.mkdir(exist_ok=True)
    file_path = job_dir / filename
    shutil.copy2(str(src_path), str(file_path))

    page_count = get_page_count(str(file_path))

    splitter_jobs[file_id] = {
        "status": "uploaded",
        "filename": filename,
        "project_id": pid,
        "file_path": str(file_path),
        "page_count": page_count,
        "current_page": 0,
        "classifications": [],
        "output_files": [],
        "error": None,
        "zip_path": None,
    }

    # Run in background thread (same as upload flow)
    thread = threading.Thread(target=_run_splitter_job, args=(file_id,), daemon=True)
    thread.start()

    return jsonify({"file_id": file_id, "filename": filename, "page_count": page_count})


@app.post("/api/ai-splitter/upload")
def splitter_upload():
    if "file" not in request.files:
        return jsonify({"error": "no_file"}), 400
    file = request.files["file"]
    project_id_raw = request.form.get("project_id")
    if isinstance(project_id_raw, str) and project_id_raw.isdigit():
        pid: Optional[int] = int(project_id_raw)
    else:
        pid = None
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "not_pdf"}), 400

    file_id = uuid.uuid4().hex[:8]
    job_dir = SPLITTER_UPLOAD_DIR / file_id
    job_dir.mkdir(exist_ok=True)
    file_path = job_dir / file.filename
    file.save(str(file_path))

    page_count = get_page_count(str(file_path))

    splitter_jobs[file_id] = {
        "status": "uploaded",
        "filename": file.filename,
        "project_id": pid,
        "file_path": str(file_path),
        "page_count": page_count,
        "current_page": 0,
        "classifications": [],
        "output_files": [],
        "error": None,
        "zip_path": None,
    }

    return jsonify({
        "file_id": file_id,
        "filename": file.filename,
        "page_count": page_count,
    })


@app.post("/api/ai-splitter/process/<file_id>")
def splitter_process(file_id: str):
    if file_id not in splitter_jobs:
        return jsonify({"error": "not_found"}), 404
    job = splitter_jobs[file_id]
    if job["status"] in ("processing", "classifying", "converting", "splitting"):
        return jsonify({"message": "already_processing"})
    if job["status"] == "completed":
        return jsonify({"message": "already_completed"})

    job["status"] = "processing"
    job["current_page"] = 0
    job["classifications"] = []
    job["output_files"] = []
    job["error"] = None

    # Run in background thread (separate event loop for async code)
    t = threading.Thread(target=_run_splitter_job, args=(file_id,), daemon=True)
    t.start()

    return jsonify({"message": "processing_started", "file_id": file_id})


@app.get("/api/ai-splitter/status/<file_id>")
def splitter_status(file_id: str):
    if file_id not in splitter_jobs:
        return jsonify({"error": "not_found"}), 404
    job = splitter_jobs[file_id]
    resp = {
        "file_id": file_id,
        "filename": job["filename"],
        "status": job["status"],
        "page_count": job["page_count"],
        "current_page": job["current_page"],
        "error": job["error"],
        "classifications": job.get("classifications", []),
    }
    if job["status"] == "completed":
        resp["output_files"] = [
            {
                "filename": f["filename"],
                "document_type": f["document_type"],
                "person_name": f["person_name"],
                "pages": f["pages"],
            }
            for f in job["output_files"]
        ]
    return jsonify(resp)


@app.get("/api/ai-splitter/download/<file_id>/<filename>")
def splitter_download_single(file_id: str, filename: str):
    # Check both splitter_jobs (AI) and filesystem (manual splits)
    file_path = SPLITTER_OUTPUT_DIR / file_id / filename
    if not file_path.exists():
        return jsonify({"error": "file_not_found"}), 404
    return send_from_directory(str(SPLITTER_OUTPUT_DIR / file_id), filename,
                                as_attachment=True, mimetype="application/pdf")


@app.get("/api/ai-splitter/view/<file_id>/<filename>")
def splitter_view_single(file_id: str, filename: str):
    """Serve PDF for in-browser viewing (as_attachment=False)."""
    file_path = SPLITTER_OUTPUT_DIR / file_id / filename
    if not file_path.exists():
        return jsonify({"error": "file_not_found"}), 404
    return send_from_directory(str(SPLITTER_OUTPUT_DIR / file_id), filename,
                                as_attachment=False, mimetype="application/pdf")


@app.get("/api/ai-splitter/download-zip/<file_id>")
def splitter_download_zip(file_id: str):
    # Try AI splitter pre-built zip first
    if file_id in splitter_jobs:
        job = splitter_jobs[file_id]
        if job["status"] == "completed" and job.get("zip_path"):
            zip_path = SplitterPath(job["zip_path"])
            if zip_path.exists():
                return send_from_directory(str(zip_path.parent), zip_path.name,
                                            as_attachment=True, mimetype="application/zip")

    # Fallback: create zip on-the-fly from output folder (manual splits)
    output_folder = SPLITTER_OUTPUT_DIR / file_id
    if not output_folder.exists():
        return jsonify({"error": "not_found"}), 404

    import io, zipfile as zf
    buf = io.BytesIO()
    with zf.ZipFile(buf, "w", zf.ZIP_DEFLATED) as z:
        for fname in sorted(os.listdir(str(output_folder))):
            fpath = os.path.join(str(output_folder), fname)
            if os.path.isfile(fpath) and fname.lower().endswith(".pdf"):
                z.write(fpath, fname)
    buf.seek(0)
    from flask import Response
    return Response(
        buf.read(),
        mimetype="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{file_id}.zip"'}
    )


@app.get("/api/ai-splitter/list-outputs")
def splitter_list_outputs():
    """List ALL split output files across all splitter job folders (AI + manual).
    Used by Tab ② to pick a file to re-split manually."""
    output_dir = str(SPLITTER_OUTPUT_DIR)
    project_id = request.args.get("project_id", type=int)
    if not os.path.isdir(output_dir):
        return jsonify({"groups": []})

    groups = []
    for folder_name in sorted(os.listdir(output_dir)):
        folder_path = os.path.join(output_dir, folder_name)
        if not os.path.isdir(folder_path):
            continue
        files = []
        for fname in sorted(os.listdir(folder_path)):
            fpath = os.path.join(folder_path, fname)
            if os.path.isfile(fpath) and fname.lower().endswith(".pdf"):
                files.append({
                    "filename": fname,
                    "size": os.path.getsize(fpath),
                    "file_id": folder_name,
                })
        if files:
            is_manual = folder_name.startswith("manual_")
            # Read persistent source metadata
            source_name = ""
            source_project_id = None
            source_meta_path = os.path.join(folder_path, "_source.json")
            if os.path.isfile(source_meta_path):
                try:
                    with open(source_meta_path, "r", encoding="utf-8") as mf:
                        meta = json.load(mf)
                    source_name = meta.get("source_filename", "")
                    source_project_id = meta.get("project_id")
                except Exception:
                    pass
            # Fallback to in-memory splitter_jobs
            if not source_name and not is_manual and folder_name in splitter_jobs:
                source_name = splitter_jobs[folder_name].get("filename", "")
                if source_project_id is None:
                    source_project_id = splitter_jobs[folder_name].get("project_id")

            # Filter by project if requested
            if project_id is not None and source_project_id != project_id:
                continue

            groups.append({
                "folder_id": folder_name,
                "source_type": "manual" if is_manual else "ai",
                "source_filename": source_name,
                "files": files,
            })
    return jsonify({"groups": groups})


@app.post("/api/manual-split/upload-and-split")
def manual_split_upload_and_split():
    """Upload a PDF from computer and split it manually.
    The uploaded file is stored temporarily, split into segments,
    and results go to splitter_outputs/manual_<uuid>/."""
    if "file" not in request.files:
        return jsonify({"error": "no_file"}), 400
    file = request.files["file"]
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "not_pdf"}), 400

    segments_json = request.form.get("segments", "[]")
    project_id_raw = request.form.get("project_id")
    try:
        segments = json.loads(segments_json)
    except Exception:
        return jsonify({"error": "invalid_segments"}), 400
    if not isinstance(segments, list) or not segments:
        return jsonify({"error": "missing_segments"}), 400

    # Save uploaded file to temp location
    manual_id = f"manual_{uuid.uuid4().hex[:8]}"
    output_dir = str(SPLITTER_OUTPUT_DIR / manual_id)
    os.makedirs(output_dir, exist_ok=True)

    import tempfile
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, file.filename)
    file.save(tmp_path)

    try:
        reader = PdfReader(tmp_path)
    except Exception as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify({"error": "read_pdf_failed", "detail": str(exc)}), 500

    total_pages = len(reader.pages)
    created: list[dict[str, Any]] = []

    def _sanitize_name(value: str, fallback: str) -> str:
        text = (value or "").strip()
        text = re.sub(r"[\\/:*?\"<>|]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text or fallback

    def _pick_unique(dest_dir: str, stem: str, ext: str) -> str:
        candidate = os.path.join(dest_dir, f"{stem}{ext}")
        idx = 1
        while os.path.exists(candidate):
            candidate = os.path.join(dest_dir, f"{stem} ({idx}){ext}")
            idx += 1
        return candidate

    for seg in segments:
        if not isinstance(seg, dict):
            continue
        name = _sanitize_name(seg.get("output_name") or "", "DOCUMENT")
        try:
            s = int(seg.get("start_page"))
            e = int(seg.get("end_page"))
        except Exception:
            continue
        if s < 1 or e < 1 or s > total_pages or e > total_pages:
            continue
        if s > e:
            s, e = e, s
        writer = PdfWriter()
        for i in range(s - 1, e):
            writer.add_page(reader.pages[i])
        out_path = _pick_unique(output_dir, name, ".pdf")
        try:
            with open(out_path, "wb") as f:
                writer.write(f)
        except Exception:
            continue
        created.append(
            {
                "output_name": name,
                "start_page": s,
                "end_page": e,
                "to": os.path.relpath(out_path, output_dir).replace("\\", "/"),
                "file_id": manual_id,
            }
        )

    # Clean up temp
    shutil.rmtree(tmp_dir, ignore_errors=True)

    # Save source metadata for persistent display
    if created:
        source_meta = {"source_filename": file.filename, "source_type": "manual"}
        if project_id_raw and project_id_raw.isdigit():
            source_meta["project_id"] = int(project_id_raw)
        with open(os.path.join(output_dir, "_source.json"), "w", encoding="utf-8") as mf:
            json.dump(source_meta, mf, ensure_ascii=False)

    return jsonify(
        {
            "status": "done",
            "manual_id": manual_id,
            "output_dir": output_dir,
            "source": file.filename,
            "total_pages": total_pages,
            "segments": created,
        }
    )


@app.post("/api/manual-split/send-to-classifier")
def manual_split_send_to_classifier():
    """Send specific manual split results directly to classifier input.
    Use this when user uploads a file from computer and wants to send
    directly to classifier without going through the full pipeline."""
    payload = request.get_json(force=True) or {}
    manual_id = payload.get("manual_id", "")
    target_dir = payload.get("target_dir", os.path.join("phanloai", "input"))

    if not manual_id:
        return jsonify({"error": "missing_manual_id"}), 400

    source_dir = str(SPLITTER_OUTPUT_DIR / manual_id)
    if not os.path.isdir(source_dir):
        return jsonify({"error": "not_found"}), 404

    os.makedirs(target_dir, exist_ok=True)
    copied = []
    for fname in os.listdir(source_dir):
        fpath = os.path.join(source_dir, fname)
        if not os.path.isfile(fpath) or not fname.lower().endswith(".pdf"):
            continue
        dst = os.path.join(target_dir, fname)
        base, ext = os.path.splitext(fname)
        idx = 1
        while os.path.exists(dst):
            dst = os.path.join(target_dir, f"{base} ({idx}){ext}")
            idx += 1
        shutil.copy2(fpath, dst)
        copied.append(fname)

    return jsonify({"status": "done", "copied": copied, "count": len(copied), "target_dir": target_dir})


@app.post("/api/manual-split/get-page-count")
def manual_split_get_page_count():
    """Get page count of a file in splitter_outputs (for re-splitting from AI results)."""
    payload = request.get_json(force=True) or {}
    file_id = payload.get("file_id", "")
    filename = payload.get("filename", "")
    if not file_id or not filename:
        return jsonify({"error": "missing_params"}), 400
    file_path = SPLITTER_OUTPUT_DIR / file_id / filename
    if not file_path.is_file():
        return jsonify({"error": "file_not_found"}), 404
    try:
        count = get_page_count(str(file_path))
    except Exception as exc:
        return jsonify({"error": "read_failed", "detail": str(exc)}), 500
    return jsonify({"page_count": count, "filename": filename, "file_id": file_id})


@app.post("/api/manual-split/upload-get-page-count")
def manual_split_upload_get_page_count():
    """Upload a PDF and return its page count (for building split form)."""
    if "file" not in request.files:
        return jsonify({"error": "no_file"}), 400
    file = request.files["file"]
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "not_pdf"}), 400

    # Save to a temp location under splitter_uploads
    temp_id = f"temp_{uuid.uuid4().hex[:8]}"
    temp_dir = SPLITTER_UPLOAD_DIR / temp_id
    temp_dir.mkdir(exist_ok=True)
    file_path = temp_dir / file.filename
    file.save(str(file_path))

    try:
        count = get_page_count(str(file_path))
    except Exception as exc:
        shutil.rmtree(str(temp_dir), ignore_errors=True)
        return jsonify({"error": "read_failed", "detail": str(exc)}), 500

    return jsonify({
        "page_count": count,
        "filename": file.filename,
        "temp_id": temp_id,
        "temp_path": str(file_path),
    })



@app.post("/api/ai-splitter/merge-outputs")
def splitter_merge_outputs():
    """Merge multiple output PDF files into one.
    Expects JSON: { files: [{file_id, filename}, ...], output_name: "optional" }
    Merges in order, saves into the first file's folder, deletes originals."""
    payload = request.get_json(force=True) or {}
    files = payload.get("files", [])
    output_name = (payload.get("output_name") or "").strip()

    if not isinstance(files, list) or len(files) < 2:
        return jsonify({"error": "need_at_least_2_files"}), 400

    # Validate all files exist
    paths = []
    for f in files:
        fid = f.get("file_id", "")
        fname = f.get("filename", "")
        fpath = SPLITTER_OUTPUT_DIR / fid / fname
        if not fpath.is_file():
            return jsonify({"error": f"file_not_found: {fid}/{fname}"}), 404
        paths.append((fid, fname, str(fpath)))

    # Default output name = first file's name (without .pdf)
    if not output_name:
        first_name = os.path.splitext(files[0]["filename"])[0]
        output_name = first_name

    # Sanitize
    output_name = re.sub(r'[\\/:*?"<>|]+', ' ', output_name)
    output_name = re.sub(r'\s+', ' ', output_name).strip() or "Merged"

    # Merge PDFs
    writer = PdfWriter()
    for _, _, fpath in paths:
        try:
            reader = PdfReader(fpath)
            for page in reader.pages:
                writer.add_page(page)
        except Exception as exc:
            return jsonify({"error": f"read_failed: {fpath}", "detail": str(exc)}), 500

    # Save to first file's folder
    target_dir = str(SPLITTER_OUTPUT_DIR / files[0]["file_id"])
    out_filename = f"{output_name}.pdf"
    out_path = os.path.join(target_dir, out_filename)
    # Avoid overwriting
    idx = 1
    while os.path.exists(out_path):
        out_path = os.path.join(target_dir, f"{output_name} ({idx}).pdf")
        out_filename = f"{output_name} ({idx}).pdf"
        idx += 1

    try:
        with open(out_path, "wb") as f:
            writer.write(f)
    except Exception as exc:
        return jsonify({"error": "write_failed", "detail": str(exc)}), 500

    # Delete originals
    deleted = []
    for fid, fname, fpath in paths:
        try:
            os.remove(fpath)
            deleted.append(f"{fid}/{fname}")
        except Exception:
            pass

    return jsonify({
        "status": "done",
        "merged_file": out_filename,
        "file_id": files[0]["file_id"],
        "total_pages": len(writer.pages),
        "deleted": deleted,
    })


@app.post("/api/ai-splitter/clear-outputs")
def splitter_clear_outputs():
    """Delete ALL output folders in splitter_outputs/ (AI + manual).
    Also clears in-memory splitter_jobs."""
    output_dir = str(SPLITTER_OUTPUT_DIR)
    deleted_count = 0
    if os.path.isdir(output_dir):
        for name in os.listdir(output_dir):
            path = os.path.join(output_dir, name)
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
                deleted_count += 1
            elif os.path.isfile(path):
                os.remove(path)  # remove .zip files etc.
                deleted_count += 1
    splitter_jobs.clear()
    return jsonify({"status": "done", "deleted_count": deleted_count})


@app.get("/api/translate/templates")
def list_translate_templates():
    _ensure_translate_template_dir()
    templates: List[Dict[str, str]] = []
    for name in sorted(os.listdir(TRANSLATE_TEMPLATE_DIR)):
        path = os.path.join(TRANSLATE_TEMPLATE_DIR, name)
        if os.path.isfile(path) and name.lower().endswith(".html"):
            templates.append({"name": name})
    return jsonify({"templates": templates, "default": TRANSLATE_DEFAULT_TEMPLATE})


@app.post("/api/translate/upload")
def translate_upload_file():
    """Upload a file for translation flow (temporary, auto-clean)."""
    if "file" not in request.files:
        return jsonify({"error": "missing_file"}), 400
    f = request.files["file"]
    if not f or not f.filename:
        return jsonify({"error": "missing_filename"}), 400

    orig_name = os.path.basename(f.filename)
    safe_name = _safe_name(orig_name)
    safe_name = safe_name.replace("..", ".")
    if not safe_name:
        return jsonify({"error": "invalid_filename"}), 400

    base, ext = os.path.splitext(safe_name)
    ext = ext or ".bin"
    token = uuid.uuid4().hex
    out_name = f"translate_{token}{ext}"
    out_path = os.path.join(tempfile.gettempdir(), out_name)

    try:
        f.save(out_path)
    except Exception as e:
        return jsonify({"error": "save_failed", "detail": str(e)}), 500

    translation_upload_cache[token] = {"temp_path": out_path, "filename": safe_name}
    file_ref = f"upload_token:{token}"
    return jsonify(
        {
            "status": "success",
            "file_ref": file_ref,
            "filename": safe_name,
            "temporary": True,
        }
    )


@app.post("/api/translate/run_stream")
def run_translate_stream():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    file_ref = (payload.get("file_ref") or "").strip()
    template_name = (payload.get("template_name") or TRANSLATE_DEFAULT_TEMPLATE).strip()
    flow_id = payload.get("flow_id") or 1
    source_lang = (payload.get("source_lang") or "tiếng Việt").strip()
    ocr_model = payload.get("ocr_model") or "gpt-4o-mini"
    translate_model = payload.get("translate_model") or "gpt-5-mini"

    if not file_ref:
        return jsonify({"error": "missing_file_ref"}), 400

    _ensure_translate_template_dir()
    is_auto_template = template_name.lower() in ("auto", "")
    if not is_auto_template:
        template_name = _safe_name(template_name) or TRANSLATE_DEFAULT_TEMPLATE
        template_path = os.path.abspath(os.path.join(TRANSLATE_TEMPLATE_DIR, template_name))
        template_root = os.path.abspath(TRANSLATE_TEMPLATE_DIR)
        if not template_path.startswith(template_root) or not os.path.exists(template_path):
            return jsonify({"error": "template_not_found"}), 404

    source_path = _resolve_translate_source_path(input_dir, file_ref)
    if not source_path:
        return jsonify({"error": "file_not_found"}), 404
    upload_token = ""
    if file_ref.startswith("upload_token:"):
        upload_token = file_ref.split(":", 1)[1].strip()

    def generate():
        nonlocal template_name
        def send_event(step: int, msg: str, data: Optional[Dict[str, Any]] = None):
            evt: Dict[str, Any] = {"step": step, "msg": msg}
            if data is not None:
                evt["data"] = data
            yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

        try:
            # Step 1: OCR with per-page progress
            yield from send_event(1, "⏳ Đang OCR tài liệu...")
            llm_ocr = ChatOpenAI(model=ocr_model, temperature=0)
            page_events: List[str] = []

            def on_page(page_idx: int, total: int) -> None:
                page_events.append(f"data: {json.dumps({'step': 1, 'msg': f'⏳ OCR trang {page_idx}/{total}...'}, ensure_ascii=False)}\n\n")

            ocr_text = _ocr_document_for_translation(llm_ocr, source_path, page_callback=on_page)
            # Yield page progress events
            for pe in page_events:
                yield pe
            if not ocr_text.strip():
                yield from send_event(-1, "❌ Không trích xuất được OCR từ file")
                return
            yield from send_event(1, "✅ OCR hoàn tất")

            # Auto-detect template from OCR text if needed
            if is_auto_template:
                template_name = _auto_detect_template(ocr_text)
                yield from send_event(1, f"🔍 Tự động chọn template: {template_name}")

            # Load template HTML
            tpl_path = os.path.abspath(os.path.join(TRANSLATE_TEMPLATE_DIR, template_name))
            tpl_root = os.path.abspath(TRANSLATE_TEMPLATE_DIR)
            if not tpl_path.startswith(tpl_root) or not os.path.exists(tpl_path):
                tpl_path = os.path.join(TRANSLATE_TEMPLATE_DIR, TRANSLATE_DEFAULT_TEMPLATE)
            with open(tpl_path, "r", encoding="utf-8") as f:
                template_html = f.read()

            # Step 2: Translate
            yield from send_event(2, f"⏳ Đang dịch {source_lang} sang tiếng Anh...")
            llm_translate = ChatOpenAI(model=translate_model, temperature=0)
            translated_text = _translate_ocr_text(llm_translate, ocr_text, source_lang=source_lang)
            if not translated_text.strip():
                yield from send_event(-1, "❌ Không tạo được bản dịch")
                return
            yield from send_event(2, "✅ Dịch hoàn tất")

            # Step 3: Build HTML — use truncated OCR for layout hints only (saves tokens)
            yield from send_event(3, "⏳ Đang tạo HTML theo template...")
            layout_hint = ocr_text[:1500] + ("\n..." if len(ocr_text) > 1500 else "")
            html_result = _build_translation_html(
                llm_translate,
                translated_text,
                template_html,
                layout_hint,
            )
            if not html_result.strip():
                yield from send_event(-1, "❌ Không tạo được HTML")
                return
            yield from send_event(3, "✅ Tạo HTML hoàn tất")

            file_stem = os.path.splitext(os.path.basename(source_path))[0]
            safe_stem = _safe_name(file_stem) or "translated_document"
            out_dir = os.path.join(TRANSLATE_OUTPUT_DIR, f"flow_{flow_id}")
            os.makedirs(out_dir, exist_ok=True)

            ocr_path = os.path.join(out_dir, f"{safe_stem}.ocr.txt")
            translated_path = os.path.join(out_dir, f"{safe_stem}.translated.txt")
            html_path = os.path.join(out_dir, f"{safe_stem}.translated.html")
            with open(ocr_path, "w", encoding="utf-8") as f:
                f.write(ocr_text)
            with open(translated_path, "w", encoding="utf-8") as f:
                f.write(translated_text)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_result)

            yield from send_event(
                4,
                "✅ Hoàn tất",
                {
                    "ocr_text": ocr_text,
                    "translated_text": translated_text,
                    "html": html_result,
                    "paths": {
                        "ocr_path": ocr_path,
                        "translated_path": translated_path,
                        "html_path": html_path,
                    },
                },
            )
        except QuotaExhaustedError as qe:
            yield from send_event(-1, f"⚠️ HẾT QUOTA OpenAI! {str(qe)}")
        except Exception as e:
            # Check if it's a quota error in disguise
            if _is_quota_error(e):
                yield from send_event(-1, "⚠️ HẾT QUOTA OpenAI! Vui lòng kiểm tra billing tại https://platform.openai.com/account/billing")
            else:
                yield from send_event(-1, f"❌ Lỗi: {str(e)}")
        finally:
            # Cleanup temporary uploaded file (if any)
            if upload_token:
                meta = translation_upload_cache.pop(upload_token, None) or {}
                temp_path = meta.get("temp_path", "")
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/translate/save_html")
def translate_save_html():
    payload = request.get_json(force=True) or {}
    html_content = payload.get("html_content") or ""
    file_name = _safe_name(payload.get("file_name") or "").strip()
    if not html_content.strip():
        return jsonify({"error": "missing_html_content"}), 400
    if not file_name:
        return jsonify({"error": "missing_file_name"}), 400
    if not file_name.lower().endswith(".html"):
        file_name = f"{file_name}.html"

    os.makedirs(TRANSLATE_HTML_SAVE_DIR, exist_ok=True)
    out_path = os.path.join(TRANSLATE_HTML_SAVE_DIR, file_name)

    # Avoid overwrite by suffixing
    if os.path.exists(out_path):
        stem, ext = os.path.splitext(file_name)
        idx = 1
        while os.path.exists(out_path):
            out_path = os.path.join(TRANSLATE_HTML_SAVE_DIR, f"{stem} ({idx}){ext}")
            idx += 1

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html_content)
    except Exception as e:
        return jsonify({"error": "save_failed", "detail": str(e)}), 500

    return jsonify(
        {
            "status": "success",
            "saved_path": out_path.replace("\\", "/"),
            "saved_name": os.path.basename(out_path),
        }
    )


@app.post("/api/translate/rebuild_html")
def translate_rebuild_html():
    """Rebuild HTML from edited translated text without re-OCR."""
    payload = request.get_json(force=True) or {}
    translated_text = (payload.get("translated_text") or "").strip()
    ocr_text = (payload.get("ocr_text") or "").strip()
    template_name = (payload.get("template_name") or TRANSLATE_DEFAULT_TEMPLATE).strip()

    if not translated_text:
        return jsonify({"error": "missing_translated_text"}), 400

    _ensure_translate_template_dir()
    template_name = _safe_name(template_name) or TRANSLATE_DEFAULT_TEMPLATE
    template_path = os.path.abspath(os.path.join(TRANSLATE_TEMPLATE_DIR, template_name))
    template_root = os.path.abspath(TRANSLATE_TEMPLATE_DIR)
    if not template_path.startswith(template_root) or not os.path.exists(template_path):
        return jsonify({"error": "template_not_found"}), 404

    with open(template_path, "r", encoding="utf-8") as f:
        template_html = f.read()

    try:
        llm = ChatOpenAI(model="gpt-5-mini", temperature=0)
        html_result = _build_translation_html(llm, translated_text, template_html, ocr_text or translated_text)
        return jsonify({"html": html_result})
    except QuotaExhaustedError as qe:
        return jsonify({"error": "quota_exceeded", "detail": str(qe)}), 429
    except Exception as e:
        if _is_quota_error(e):
            return jsonify({"error": "quota_exceeded", "detail": "⚠️ Đã hết quota OpenAI API! Vui lòng kiểm tra billing."}), 429
        return jsonify({"error": str(e)}), 500



if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)


