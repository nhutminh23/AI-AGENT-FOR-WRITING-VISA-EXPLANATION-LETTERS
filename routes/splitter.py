"""
AI PDF Splitter routes: upload, split, classify, download.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import shutil
import tempfile
import uuid
import zipfile
import threading
from pathlib import Path as SplitterPath
from typing import Any, Dict, List, Optional

from pypdf import PdfReader, PdfWriter

from flask import Blueprint, Response, jsonify, request, send_from_directory

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from core.errors import QuotaExhaustedError, is_quota_error

from pdf_tools.pdf_service import pdf_to_images, get_page_count, create_output_files
from pdf_tools.ai_service import classify_all_pages
from config import Config

splitter_bp = Blueprint("splitter", __name__)

# Base directory (project root, one level up from routes/)
_BASE_DIR = SplitterPath(__file__).parent.parent

# Directories for AI splitter
SPLITTER_UPLOAD_DIR = _BASE_DIR / Config.SPLITTER_UPLOADS_DIR
SPLITTER_OUTPUT_DIR = _BASE_DIR / Config.SPLITTER_OUTPUTS_DIR
SPLITTER_UPLOAD_DIR.mkdir(exist_ok=True)
SPLITTER_OUTPUT_DIR.mkdir(exist_ok=True)

# In-memory job tracking for AI splitter
splitter_jobs: Dict[str, Dict] = {}

# Output dir constant
_OUTPUT_DIR = os.path.join(str(_BASE_DIR), "output")

# Translation directories (aliases from Config for splitter routes)
TRANSLATE_TEMPLATE_DIR = os.path.join(str(_BASE_DIR), Config.TRANSLATION_TEMPLATE_DIR)
TRANSLATE_DEFAULT_TEMPLATE = Config.TRANSLATION_DEFAULT_TEMPLATE
TRANSLATE_OUTPUT_DIR = os.path.join(str(_BASE_DIR), Config.TRANSLATION_OUTPUT_DIR)
TRANSLATE_HTML_SAVE_DIR = os.path.join(str(_BASE_DIR), Config.TRANSLATION_HTML_SAVE_DIR)


# In-memory cache for uploaded translation files
translation_upload_cache: Dict[str, Dict] = {}

# Alias for backward compatibility
_is_quota_error = is_quota_error


def _safe_name(name: str) -> str:
    """Sanitize a filename: remove path separators, control chars, collapse spaces."""
    name = os.path.basename(name)
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def _resolve_translate_source_path(input_dir: str, file_ref: str) -> Optional[str]:
    """Resolve a file reference to an absolute path for translation.
    
    Handles:
    - upload_token:<token> → temp file from translation_upload_cache
    - relative path → joined with input_dir
    - absolute path → used directly
    """
    if file_ref.startswith("upload_token:"):
        token = file_ref.split(":", 1)[1].strip()
        meta = translation_upload_cache.get(token)
        if meta and os.path.isfile(meta.get("temp_path", "")):
            return meta["temp_path"]
        return None
    
    # Try as relative path under input_dir
    candidate = os.path.join(input_dir, file_ref)
    if os.path.isfile(candidate):
        return os.path.abspath(candidate)
    
    # Try as absolute path
    if os.path.isfile(file_ref):
        return os.path.abspath(file_ref)
    
    return None


def _resize_image_b64(img_bytes: bytes, max_width: int = 1024, quality: int = 80) -> str:
    """Resize image to max_width and compress as JPEG. Returns base64 string.
    
    This reduces API token cost by ~60-70% compared to full-resolution PNG.
    OpenAI charges per 512x512 tile — smaller images = fewer tiles = fewer tokens.
    """
    from io import BytesIO
    try:
        from PIL import Image
        img = Image.open(BytesIO(img_bytes))
        # Resize if wider than max_width
        if img.width > max_width:
            ratio = max_width / img.width
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        # Convert to RGB (JPEG doesn't support alpha)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        # Save as JPEG with compression
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except ImportError:
        # Pillow not installed — return original as base64
        logging.warning("Pillow not installed, sending full-resolution image")
        return base64.b64encode(img_bytes).decode("ascii")


def _ocr_and_translate_document(
    llm,
    source_path: str,
    source_lang: str = "tiếng Việt",
    page_callback=None,
) -> tuple:
    """OCR + translate a document (PDF or image) in one pass per page.
    
    For PDF: converts each page to image, resizes to max 1024px, sends to vision model.
    For images: resizes and sends directly.
    Returns tuple of (translated_text, layout_descriptions, page_images_small).
    - layout_descriptions: list of text descriptions of each page's layout
    - page_images_small: small resized base64 images (for fallback only)
    """
    ext = os.path.splitext(source_path)[1].lower()
    pages_text = []
    layout_descriptions = []
    page_images = []  # Small resized images (for fallback)
    
    if ext == ".pdf":
        import fitz
        doc = fitz.open(source_path)
        total = len(doc)
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=150)  # Reduced from 200 to 150 dpi
            img_bytes = pix.tobytes("png")
            # Resize to max 1024px width + JPEG compression → saves ~60-70% tokens
            b64 = _resize_image_b64(img_bytes)
            page_images.append(b64)
            
            if page_callback:
                page_callback(i + 1, total)
            
            prompt = (
                f"This is page {i+1}/{total} of a document originally in {source_lang}. "
                "Do TWO things:\n\n"
                "1. OCR all text and translate it fully to English. Keep the original structure "
                "(headings, paragraphs, lists, tables). Output the English translation.\n\n"
                "2. After the translation, on a NEW LINE write [LAYOUT] followed by a brief description "
                "of the page layout structure. Include:\n"
                "- Header elements (emblem/logo, organization name, title)\n"
                "- Body structure (sections, tables with column count, indented blocks)\n"
                "- Footer elements (signature blocks, dates, stamps, notes)\n"
                "- Any borders, decorative elements, or special formatting\n\n"
                "Format:\n"
                "[TRANSLATED TEXT HERE]\n\n"
                "[LAYOUT] Header: ... | Body: ... | Footer: ..."
            )
            try:
                result = llm.invoke([
                    SystemMessage(content="You are a professional document translator and layout analyst. OCR, translate to English, and describe the layout."),
                    HumanMessage(content=[
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    ]),
                ])
                raw = (result.content or "").strip()
                # Split text and layout description
                if "[LAYOUT]" in raw:
                    parts = raw.split("[LAYOUT]", 1)
                    pages_text.append(parts[0].strip())
                    layout_descriptions.append(parts[1].strip())
                else:
                    pages_text.append(raw)
                    layout_descriptions.append("")
            except Exception as e:
                logging.warning("OCR page %d failed: %s", i + 1, e)
                pages_text.append(f"[Page {i+1}: OCR failed]")
                layout_descriptions.append("")
        doc.close()
    elif ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"):
        with open(source_path, "rb") as f:
            img_bytes = f.read()
        # Resize to max 1024px + JPEG compression
        b64 = _resize_image_b64(img_bytes)
        page_images.append(b64)
        
        if page_callback:
            page_callback(1, 1)
        
        try:
            result = llm.invoke([
                SystemMessage(content="You are a professional document translator and layout analyst. OCR, translate to English, and describe the layout."),
                HumanMessage(content=[
                    {"type": "text", "text": (
                        f"OCR all text from this {source_lang} document image and translate fully to English. "
                        "Keep structure intact.\n\n"
                        "After the translation, on a NEW LINE write [LAYOUT] followed by a brief description "
                        "of the page layout (header, body structure, tables, footer, signature blocks, etc).\n\n"
                        "Format:\n[TRANSLATED TEXT]\n\n[LAYOUT] description..."
                    )},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ]),
            ])
            raw = (result.content or "").strip()
            if "[LAYOUT]" in raw:
                parts = raw.split("[LAYOUT]", 1)
                pages_text.append(parts[0].strip())
                layout_descriptions.append(parts[1].strip())
            else:
                pages_text.append(raw)
                layout_descriptions.append("")
        except Exception as e:
            logging.warning("OCR image failed: %s", e)
    else:
        # Text file — just read and translate
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                raw_text = f.read()
            result = llm.invoke([
                SystemMessage(content="You are a professional translator."),
                HumanMessage(content=f"Translate this {source_lang} text to English. Keep formatting:\n\n{raw_text}"),
            ])
            pages_text.append((result.content or "").strip())
            layout_descriptions.append("")
        except Exception as e:
            logging.warning("Text translate failed: %s", e)
    
    return "\n\n".join(pages_text), layout_descriptions, page_images


def _build_translation_html(
    llm,
    translated_text: str,
    template_html: str,
    original_text: str = "",
) -> str:
    """Use LLM to build a formatted HTML document from translated text + template."""
    prompt = (
        "You are a document formatter. Given a translated English text and an HTML template, "
        "create a complete HTML document by filling the template with the translated content.\n\n"
        "RULES:\n"
        "- Keep the template's CSS and structure intact\n"
        "- Replace placeholder content with the translated text\n"
        "- Format paragraphs, headings, and lists properly\n"
        "- PRINT-SAFE: Content MUST fit within each page when printed. NO overflow, NO clipping.\n"
        "- If translated text is longer than original, REDUCE font-size slightly to fit the page\n"
        "- Keep all @media print and @page CSS rules from the template\n"
        "- DO NOT add <h1>Translated Document</h1> or any generic titles not in the template\n"
        "- Output ONLY the complete HTML (no markdown, no explanation)\n\n"
        f"=== TEMPLATE HTML ===\n{template_html}\n\n"
        f"=== TRANSLATED TEXT ===\n{translated_text}"
    )
    try:
        result = llm.invoke([
            SystemMessage(content="You are an expert HTML document formatter. Output only valid HTML."),
            HumanMessage(content=prompt),
        ])
        html = (result.content or "").strip()
        # Strip markdown code fences if present
        if html.startswith("```"):
            html = html.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return html
    except Exception as e:
        logging.error("Build HTML failed: %s", e)
        raise


def _build_html_vision_clone(
    llm,
    translated_text: str,
    page_images: list,
    layout_descriptions: list = None,
) -> str:
    """Build HTML by cloning the original document layout using resized images.

    Sends RESIZED page images (1024px JPEG from OCR step) + translated text.
    The model sees the layout and recreates it in HTML with English content.
    Images are already resized by _resize_image_b64, saving ~60% tokens vs full-res.
    """
    if not page_images:
        # No images — fall back to simple HTML
        return (
            '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<style>'
            '@page{size:A4;margin:0;}'
            'body{margin:0;background:#f3f4f6;font-family:"Times New Roman",serif;'
            'display:flex;flex-direction:column;align-items:center;gap:20px;padding:20px;}'
            '.a4-page{width:210mm;min-height:297mm;margin:0 auto;background:#fff;'
            'padding:18mm;box-sizing:border-box;page-break-after:always;overflow:hidden;}'
            '.a4-page:last-child{page-break-after:auto;}'
            '@media print{body{background:#fff;padding:0;margin:0;gap:0;}'
            '.a4-page{box-shadow:none;margin:0;width:100%;border:none;}}'
            '</style></head><body>'
            f'<div class="a4-page"><pre style="white-space:pre-wrap;">{translated_text}</pre></div>'
            '</body></html>'
        )

    # Emblem handling: DO NOT send base64 in prompt (biases AI to always include it).
    # Instead, tell AI to use a placeholder IF it sees an emblem in the original.
    # Post-processing will replace placeholders with actual emblem.
    emblem_instruction = (
        "\n\nEMBLEM/COAT OF ARMS RULE (CRITICAL — READ CAREFULLY):\n"
        "- Look at the ORIGINAL page images carefully.\n"
        "- ONLY government-issued documents have national emblems (e.g. birth certificates, "
        "marriage certificates, court decisions, civil judgments).\n"
        "- Tax reports, bank statements, employment contracts, salary slips, insurance documents, "
        "company letters, school transcripts do NOT have national emblems.\n"
        "- If and ONLY if you see a national emblem/coat of arms (quốc huy) in the ORIGINAL images, "
        'add this placeholder: <img class="emblem-placeholder" alt="National Emblem" '
        'style="width:60px;height:auto;display:block;margin:0 auto 8px;">\n'
        "- If the original does NOT have an emblem, absolutely DO NOT add any emblem placeholder.\n"
        "- When in doubt, DO NOT add an emblem. It is better to miss it than to add a false one.\n"
    )

    # Build vision prompt with resized page images
    num_pages = len(page_images)
    content_parts = [
        {
            "type": "text",
            "text": (
                "You are an expert HTML document formatter specializing in PRINT-READY documents.\n\n"
                f"I'm showing you {num_pages} page(s) of an ORIGINAL document. Your job is to create an HTML document that:\n"
                "1. CLONES THE EXACT LAYOUT of the original (headers, tables, columns, borders, spacing, alignment)\n"
                "2. Uses the TRANSLATED ENGLISH TEXT below instead of the original Vietnamese text\n"
                f"3. The output MUST have EXACTLY {num_pages} page(s), matching the original\n"
                "4. Each page goes in a separate <div class=\"a4-page\">\n"
                "5. DO NOT include <h1>Translated Document</h1> or any generic titles\n"
                "6. Replicate borders, tables, grid layouts, headers, footers EXACTLY as in the original\n\n"
                "CRITICAL PRINT-SAFE RULES:\n"
                "- Content MUST FIT within each .a4-page when printed — NO OVERFLOW, NO CLIPPING\n"
                "- If English text is longer than Vietnamese, REDUCE font-size slightly (e.g. 11pt→10pt) to fit\n"
                "- Use 'position: relative' for page elements, avoid 'position: absolute' for main content\n"
                "- Only use 'position: absolute' for signature blocks/footers that are fixed on the page\n"
                "- Tables and content blocks must stay within the page height (297mm - 36mm padding = 261mm usable)\n"
                f"- Total pages: {num_pages}. Each page = one .a4-page div\n\n"
                "REQUIRED CSS (include exactly this):\n"
                "@page { size: A4; margin: 0; }\n"
                "body { margin:0; padding:20px; background:#f3f4f6; font-family:'Times New Roman',serif; "
                "display:flex; flex-direction:column; align-items:center; gap:20px; }\n"
                ".a4-page { width:210mm; min-height:297mm; margin:0 auto; background:#fff; "
                "padding:18mm; box-sizing:border-box; box-shadow:0 0 8px rgba(0,0,0,0.1); "
                "position:relative; page-break-after:always; break-after:page; overflow:hidden; }\n"
                ".a4-page:last-child { page-break-after:auto; break-after:auto; }\n"
                "@media print { body{background:#fff;padding:0;margin:0;gap:0;} "
                ".a4-page{box-shadow:none;margin:0;width:100%;border:none;} }\n"
                f"{emblem_instruction}\n"
                f"=== TRANSLATED ENGLISH TEXT ===\n{translated_text}\n\n"
                "Output ONLY complete HTML. No markdown, no explanation."
            ),
        },
    ]

    # Add resized page images (already 1024px JPEG from OCR step)
    for i, b64 in enumerate(page_images):
        content_parts.append({
            "type": "text",
            "text": f"\n--- Original Page {i + 1} ---",
        })
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })

    try:
        result = llm.invoke([
            SystemMessage(content=(
                "You are an expert HTML/CSS developer. You clone document layouts pixel-perfectly. "
                "Output ONLY valid, complete HTML documents."
            )),
            HumanMessage(content=content_parts),
        ])
        html = (result.content or "").strip()
        # Strip markdown code fences if present
        if html.startswith("```"):
            html = html.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        # Post-process: replace emblem placeholders with actual emblem image
        if 'emblem-placeholder' in html:
            emblem_path = os.path.join(str(_BASE_DIR), "dich", "HTML template", "Emblem_of_Vietnam.png")
            if os.path.isfile(emblem_path):
                try:
                    with open(emblem_path, "rb") as f:
                        emblem_b64 = base64.b64encode(f.read()).decode("ascii")
                    # Replace placeholder img with actual emblem
                    import re as _re
                    html = _re.sub(
                        r'<img\s+class="emblem-placeholder"[^>]*>',
                        f'<img src="data:image/png;base64,{emblem_b64}" alt="National Emblem" '
                        f'style="width:60px;height:auto;display:block;margin:0 auto 8px;">',
                        html,
                    )
                except Exception:
                    pass  # If emblem file can't be read, leave placeholder as-is

        return html
    except Exception as e:
        logging.error("Vision Layout Clone failed: %s", e)
        raise


def _embed_template_images(html: str) -> str:
    """Replace local image references (e.g. Emblem_of_Vietnam.png) with base64 data URIs.

    This makes the HTML self-contained so images display correctly in web preview
    and when saved as PDF, without needing the original image files.
    """
    import re
    import base64

    template_dir = os.path.join(str(_BASE_DIR), "dich", "HTML template")

    # Map of known image filenames in the template directory
    MIME_MAP = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
        '.webp': 'image/webp',
    }

    def replace_img_src(match):
        full_match = match.group(0)
        src = match.group(1)
        # Skip already-embedded data URIs and external URLs
        if src.startswith(('data:', 'http://', 'https://')):
            return full_match
        # Try to find the image file in the template directory
        img_path = os.path.join(template_dir, src)
        if not os.path.isfile(img_path):
            # Also try just the basename
            img_path = os.path.join(template_dir, os.path.basename(src))
        if os.path.isfile(img_path):
            ext = os.path.splitext(img_path)[1].lower()
            mime = MIME_MAP.get(ext, 'image/png')
            try:
                with open(img_path, 'rb') as f:
                    b64 = base64.b64encode(f.read()).decode('ascii')
                return full_match.replace(src, f'data:{mime};base64,{b64}')
            except Exception as e:
                logging.warning("Failed to embed image %s: %s", src, e)
        return full_match

    # Match src="..." in <img> tags
    return re.sub(r'<img\s[^>]*src=["\']([^"\']+)["\']', replace_img_src, html, flags=re.IGNORECASE)


def _auto_detect_template(translated_text: str) -> str:
    """Auto-detect the best translation template based on content."""
    text_lower = translated_text.lower()
    
    templates_dir = TRANSLATE_TEMPLATE_DIR
    if not os.path.isdir(templates_dir):
        return TRANSLATE_DEFAULT_TEMPLATE
    
    available = [f for f in os.listdir(templates_dir) if f.lower().endswith(".html")]
    if not available:
        return TRANSLATE_DEFAULT_TEMPLATE
    
    # Simple keyword matching
    for template in available:
        stem = os.path.splitext(template)[0].lower()
        keywords = stem.replace("_", " ").replace("-", " ").split()
        if any(kw in text_lower for kw in keywords if len(kw) > 3):
            return template
    
    return TRANSLATE_DEFAULT_TEMPLATE


def _ensure_translate_template_dir():
    """Create the translation template directory if it doesn't exist."""
    os.makedirs(TRANSLATE_TEMPLATE_DIR, exist_ok=True)






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
            except Exception as e:
                logging.debug("Ignored: %s", e)
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


@splitter_bp.get("/api/ai-splitter/list")
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


@splitter_bp.post("/api/ai-splitter/delete")
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


@splitter_bp.post("/api/ai-splitter/delete-all")
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


@splitter_bp.post("/api/ai-splitter/process-local")
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


@splitter_bp.post("/api/ai-splitter/upload")
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


@splitter_bp.post("/api/ai-splitter/process/<file_id>")
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


@splitter_bp.get("/api/ai-splitter/status/<file_id>")
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


@splitter_bp.get("/api/ai-splitter/download/<file_id>/<filename>")
def splitter_download_single(file_id: str, filename: str):
    # Check both splitter_jobs (AI) and filesystem (manual splits)
    file_path = SPLITTER_OUTPUT_DIR / file_id / filename
    if not file_path.exists():
        return jsonify({"error": "file_not_found"}), 404
    return send_from_directory(str(SPLITTER_OUTPUT_DIR / file_id), filename,
                                as_attachment=True, mimetype="application/pdf")


@splitter_bp.get("/api/ai-splitter/view/<file_id>/<filename>")
def splitter_view_single(file_id: str, filename: str):
    """Serve PDF for in-browser viewing (as_attachment=False)."""
    file_path = SPLITTER_OUTPUT_DIR / file_id / filename
    if not file_path.exists():
        return jsonify({"error": "file_not_found"}), 404
    return send_from_directory(str(SPLITTER_OUTPUT_DIR / file_id), filename,
                                as_attachment=False, mimetype="application/pdf")


@splitter_bp.get("/api/ai-splitter/download-zip/<file_id>")
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


@splitter_bp.get("/api/ai-splitter/list-outputs")
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
                except Exception as e:
                    logging.debug("Ignored: %s", e)
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


@splitter_bp.post("/api/manual-split/upload-and-split")
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
    except Exception as e:
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
        except Exception as e:
            logging.debug("Skipped: %s", e)
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
        except Exception as e:
            logging.debug("Skipped: %s", e)
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


@splitter_bp.post("/api/manual-split/send-to-classifier")
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


@splitter_bp.post("/api/manual-split/get-page-count")
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


@splitter_bp.post("/api/manual-split/upload-get-page-count")
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



@splitter_bp.post("/api/ai-splitter/merge-outputs")
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
        except Exception as e:
            logging.debug("Ignored: %s", e)

    return jsonify({
        "status": "done",
        "merged_file": out_filename,
        "file_id": files[0]["file_id"],
        "total_pages": len(writer.pages),
        "deleted": deleted,
    })


@splitter_bp.post("/api/ai-splitter/clear-outputs")
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


# ---------------------------------------------------------------------------
# Bulk bilingual check — OCR page 1 only, parallel
# ---------------------------------------------------------------------------

# Document types that should NOT be translated (keep original for embassy check)
_SKIP_TRANSLATION_KEYWORDS = [
    "passport", "photo", "citizen_identity", "cccd",
    "residence_permit", "visa_application", "visa_form",
]

def _should_skip_by_filename(filename: str) -> tuple:
    """Check if file should skip translation based on filename patterns.
    Returns (should_skip: bool, reason: str).
    """
    name_lower = filename.lower().replace(" ", "_").replace("-", "_")
    for kw in _SKIP_TRANSLATION_KEYWORDS:
        if kw in name_lower:
            label = kw.replace("_", " ").title()
            return True, f"Loại '{label}' — giữ gốc, không cần dịch"
    return False, ""


def _check_single_file_bilingual(filepath: str, filename: str, llm) -> dict:
    """OCR page 1 of a file and check if it's bilingual or needs translation.
    
    Skips passport, CCCD, photo, visa forms, bank statements by filename.
    For remaining: OCRs page 1 via vision LLM to detect languages.
    """
    # --- Pre-filter by filename ---
    skip, skip_reason = _should_skip_by_filename(filename)
    if skip:
        return {
            "filename": filename,
            "is_bilingual": False,
            "needs_translation": False,
            "languages": [],
            "reason": skip_reason,
        }

    import fitz
    ext = os.path.splitext(filepath)[1].lower()
    
    # Get page 1 as base64 image
    b64 = None
    mime = "image/png"
    
    try:
        if ext == ".pdf":
            doc = fitz.open(filepath)
            if len(doc) == 0:
                doc.close()
                return {"filename": filename, "needs_translation": False, 
                        "reason": "Empty PDF", "is_bilingual": False}
            pix = doc[0].get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            b64 = base64.b64encode(img_bytes).decode("ascii")
            doc.close()
        elif ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"):
            with open(filepath, "rb") as f:
                img_bytes = f.read()
            mime = "image/jpeg" if ext in (".jpg", ".jpeg") else f"image/{ext.lstrip('.')}"
            b64 = base64.b64encode(img_bytes).decode("ascii")
        else:
            return {"filename": filename, "needs_translation": False, 
                    "reason": f"Unsupported format: {ext}", "is_bilingual": False}
    except Exception as e:
        return {"filename": filename, "needs_translation": False, 
                "reason": f"Cannot read file: {str(e)}", "is_bilingual": False}
    
    if not b64:
        return {"filename": filename, "needs_translation": False, 
                "reason": "Cannot extract image", "is_bilingual": False}
    
    # Ask LLM to check if the document page needs translation
    prompt = (
        "Look at this document image. Determine:\n"
        "1) What TYPE of document is this?\n"
        "2) Does it contain bilingual text (Vietnamese + English)?\n"
        "3) Does it NEED translation?\n\n"
        "Answer in this EXACT JSON format only:\n"
        '{"is_bilingual": true/false, "needs_translation": true/false, '
        '"doc_type": "type", "languages": ["list"], "reason": "brief explanation"}\n\n'
        "Rules for needs_translation:\n"
        "- Photo/portrait with no meaningful text → needs_translation: false\n"
        "- Passport → needs_translation: false (international standard)\n"
        "- ID card / CCCD / Citizen Identity Card → needs_translation: false (keep original)\n"
        "- Visa application form → needs_translation: false (already in English)\n"
        "- Residence permit → needs_translation: false (keep original)\n"
        "- Bank statements with bilingual column headers (e.g. 'Ngày GD / Trans Date', 'Số dư / Balance') → needs_translation: false\n"
        "- Bank statements where headers/labels have BOTH Vietnamese and English → needs_translation: false (already bilingual)\n"
        "- Bank statements with ONLY Vietnamese headers → needs_translation: true\n"
        "- Already bilingual (Vietnamese + English) → needs_translation: false\n"
        "- Vietnamese-only administrative document → needs_translation: true\n"
        "- Vietnamese-only certificate/license → needs_translation: true\n"
        "Output ONLY the JSON, nothing else."
    )
    
    try:
        result = llm.invoke([
            SystemMessage(content="You analyze document images for language detection. Respond only with JSON."),
            HumanMessage(content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ]),
        ])
        
        raw = (result.content or "").strip()
        # Parse JSON from response (handle markdown code blocks)
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        
        info = json.loads(raw)
        is_bilingual = info.get("is_bilingual", False)
        # Use AI's needs_translation if provided, otherwise infer from bilingual status
        needs = info.get("needs_translation", not is_bilingual)
        
        return {
            "filename": filename,
            "is_bilingual": is_bilingual,
            "needs_translation": needs,
            "doc_type": info.get("doc_type", ""),
            "languages": info.get("languages", []),
            "reason": info.get("reason", ""),
        }
    except Exception as e:
        logging.warning("Bilingual check failed for %s: %s", filename, e)
        # Default to needing translation if check fails
        return {
            "filename": filename,
            "is_bilingual": False,
            "needs_translation": True,
            "reason": f"Check failed, assuming needs translation: {str(e)}",
            "languages": [],
        }


@splitter_bp.post("/api/translate/check_bilingual")
def check_bilingual():
    """Upload multiple files and check which ones need translation.
    
    OCRs only page 1 of each file for speed. Processes in parallel.
    Returns per-file results with bilingual status and upload tokens.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "no_files", "detail": "No files uploaded"}), 400
    
    # Save all files to temp and create upload tokens
    file_entries = []
    for f in files:
        if not f or not f.filename:
            continue
        orig_name = os.path.basename(f.filename)
        safe = _safe_name(orig_name).replace("..", ".")
        if not safe:
            continue
        
        base, ext = os.path.splitext(safe)
        ext = ext or ".bin"
        token = uuid.uuid4().hex
        out_name = f"translate_{token}{ext}"
        out_path = os.path.join(tempfile.gettempdir(), out_name)
        
        try:
            f.save(out_path)
            translation_upload_cache[token] = {"temp_path": out_path, "filename": safe}
            file_entries.append({
                "token": token, 
                "path": out_path, 
                "filename": safe,
                "file_ref": f"upload_token:{token}",
            })
        except Exception as e:
            logging.warning("Failed to save %s: %s", safe, e)
    
    if not file_entries:
        return jsonify({"error": "no_valid_files"}), 400
    
    # Create LLM instance for bilingual check (use project's configured vision model)
    from core.helpers import get_vision_model
    llm = ChatOpenAI(model=get_vision_model(), temperature=0)
    
    # Check all files in parallel
    results = [None] * len(file_entries)
    
    with ThreadPoolExecutor(max_workers=min(6, len(file_entries))) as executor:
        future_to_idx = {
            executor.submit(
                _check_single_file_bilingual, 
                entry["path"], entry["filename"], llm
            ): i 
            for i, entry in enumerate(file_entries)
        }
        
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                result = future.result()
                # Add upload token/ref to result
                result["upload_token"] = file_entries[idx]["token"]
                result["file_ref"] = file_entries[idx]["file_ref"]
                results[idx] = result
            except Exception as e:
                results[idx] = {
                    "filename": file_entries[idx]["filename"],
                    "needs_translation": True,
                    "is_bilingual": False,
                    "reason": f"Error: {str(e)}",
                    "upload_token": file_entries[idx]["token"],
                    "file_ref": file_entries[idx]["file_ref"],
                }
    
    needs_count = sum(1 for r in results if r and r.get("needs_translation"))
    bilingual_count = sum(1 for r in results if r and not r.get("needs_translation") and r.get("is_bilingual"))
    skipped_count = sum(1 for r in results if r and not r.get("needs_translation") and not r.get("is_bilingual"))
    
    return jsonify({
        "status": "success",
        "total": len(results),
        "needs_translation": needs_count,
        "already_bilingual": bilingual_count,
        "skipped": skipped_count,
        "results": results,
    })


@splitter_bp.get("/api/translate/templates")
def list_translate_templates():
    _ensure_translate_template_dir()
    templates: List[Dict[str, str]] = []
    for name in sorted(os.listdir(TRANSLATE_TEMPLATE_DIR)):
        path = os.path.join(TRANSLATE_TEMPLATE_DIR, name)
        if os.path.isfile(path) and name.lower().endswith(".html"):
            templates.append({"name": name})
    return jsonify({"templates": templates, "default": TRANSLATE_DEFAULT_TEMPLATE})


@splitter_bp.post("/api/translate/upload")
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


@splitter_bp.post("/api/translate/original_pages")
def translate_original_pages():
    """Render uploaded file pages as base64 PNG images (accepts file upload directly)."""
    if "file" not in request.files:
        return jsonify({"error": "missing_file"}), 400
    f = request.files["file"]
    if not f or not f.filename:
        return jsonify({"error": "missing_filename"}), 400

    ext = os.path.splitext(f.filename)[1].lower()

    # Save to temp for processing
    tmp_path = os.path.join(tempfile.gettempdir(), f"origpages_{uuid.uuid4().hex}{ext}")
    try:
        f.save(tmp_path)
    except Exception as e:
        return jsonify({"error": "save_failed", "detail": str(e)}), 500

    pages = []
    try:
        if ext == ".pdf":
            import fitz  # PyMuPDF
            doc = fitz.open(tmp_path)
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                b64 = base64.b64encode(img_bytes).decode("ascii")
                pages.append({"index": i, "data_url": f"data:image/png;base64,{b64}"})
            doc.close()
        elif ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"):
            with open(tmp_path, "rb") as fp:
                img_bytes = fp.read()
            mime = "image/jpeg" if ext in (".jpg", ".jpeg") else f"image/{ext.lstrip('.')}"
            b64 = base64.b64encode(img_bytes).decode("ascii")
            pages.append({"index": 0, "data_url": f"data:{mime};base64,{b64}"})
        else:
            return jsonify({"error": "unsupported_format", "detail": f"Cannot render {ext} as images"}), 400
    except Exception as e:
        return jsonify({"error": "render_failed", "detail": str(e)}), 500
    finally:
        # Cleanup temp file
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    return jsonify({"pages": pages})


@splitter_bp.get("/api/translate/certification_template")
def translate_certification_template():
    """Return certification HTML template with embedded logo as base64."""
    template_path = os.path.join("dich", "HTML template", "Xác nhận dịch.html")
    logo_path = os.path.join("dich", "HTML template", "passport_lounge.jpg")

    if not os.path.isfile(template_path):
        return jsonify({"error": "template_not_found"}), 404

    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Embed logo as base64 data URL
    if os.path.isfile(logo_path):
        with open(logo_path, "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode("ascii")
        html = html.replace('src="./passport_lounge.jpg"', f'src="data:image/jpeg;base64,{logo_b64}"')

    return jsonify({"html": html})

@splitter_bp.post("/api/translate/run_stream")
def run_translate_stream():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    file_ref = (payload.get("file_ref") or "").strip()
    template_name = (payload.get("template_name") or TRANSLATE_DEFAULT_TEMPLATE).strip()
    flow_id = payload.get("flow_id") or 1
    source_lang = (payload.get("source_lang") or "tiếng Việt").strip()
    ocr_model = payload.get("ocr_model") or "gpt-5-mini"
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
            # Step 1: OCR + Translate combined (per-page parallel)
            yield from send_event(1, "⏳ Đang OCR + Dịch tài liệu...")
            llm_ocr = ChatOpenAI(model=ocr_model, temperature=0)
            page_events: List[str] = []

            def on_page(page_idx: int, total: int) -> None:
                page_events.append(f"data: {json.dumps({'step': 1, 'msg': f'⏳ OCR+Dịch trang {page_idx}/{total}...'}, ensure_ascii=False)}\n\n")

            translated_text, layout_descriptions, page_images = _ocr_and_translate_document(llm_ocr, source_path, source_lang=source_lang, page_callback=on_page)
            # Yield page progress events
            for pe in page_events:
                yield pe
            if not translated_text.strip():
                yield from send_event(-1, "❌ Không trích xuất/dịch được từ file")
                return

            # Vietnamese text validation — check for leftover Vietnamese chars
            import re as _re
            viet_chars = _re.findall(r'[àáạảãăắằặẳẵâấầậẩẫèéẹẻẽêếềệểễìíịỉĩòóọỏõôốồộổỗơớờợởỡùúụủũưứừựửữỳýỵỷỹđÀÁẠẢÃĂẮẰẶẲẴÂẤẦẬẨẪÈÉẸẺẼÊẾỀỆỂỄÌÍỊỈĨÒÓỌỎÕÔỐỒỘỔỖƠỚỜỢỞỠÙÚỤỦŨƯỨỪỰỬỮỲÝỴỶỸĐ]', translated_text)
            if len(viet_chars) > 5:  # More than 5 Vietnamese chars = needs cleanup
                yield from send_event(1, "🔄 Phát hiện tiếng Việt còn sót, đang sửa...")
                llm_fix = ChatOpenAI(model=translate_model, temperature=0)
                fix_prompt = (
                    "The following text should be 100% English but contains some Vietnamese words/phrases. "
                    "Translate ALL remaining Vietnamese text to English. Keep the structure and formatting intact. "
                    "Output ONLY the corrected English text:\n\n" + translated_text
                )
                try:
                    fix_result = llm_fix.invoke([SystemMessage(content="Fix Vietnamese text remnants. Output pure English."), HumanMessage(content=fix_prompt)])
                    fixed = (fix_result.content or "").strip()
                    if fixed:
                        translated_text = fixed
                except Exception as e:
                    logging.debug("Ignored: %s", e)  # Keep original if fix fails

            yield from send_event(1, "✅ OCR + Dịch hoàn tất")

            # Auto-detect template from translated text if needed
            use_vision_clone = False
            if is_auto_template:
                template_name = _auto_detect_template(translated_text)
                # If auto-detect falls back to default template AND we have page images,
                # use Vision Layout Clone with resized images (1024px JPEG = ~55% cheaper)
                if template_name == TRANSLATE_DEFAULT_TEMPLATE and page_images:
                    use_vision_clone = True
                    yield from send_event(1, "🎨 Không tìm thấy template phù hợp → Dùng Vision Clone layout gốc")
                else:
                    yield from send_event(1, f"🔍 Tự động chọn template: {template_name}")

            # Step 2: Build HTML
            if use_vision_clone:
                # Vision Layout Clone: send RESIZED page images + translated text
                yield from send_event(2, "🎨 Đang clone layout từ ảnh gốc (ảnh đã nén 1024px)...")
                llm_vision = ChatOpenAI(model=translate_model, temperature=0)
                html_result = _build_html_vision_clone(llm_vision, translated_text, page_images)
            else:
                # Template-based: use the matched template
                tpl_path = os.path.abspath(os.path.join(TRANSLATE_TEMPLATE_DIR, template_name))
                tpl_root = os.path.abspath(TRANSLATE_TEMPLATE_DIR)
                if not tpl_path.startswith(tpl_root) or not os.path.exists(tpl_path):
                    tpl_path = os.path.join(TRANSLATE_TEMPLATE_DIR, TRANSLATE_DEFAULT_TEMPLATE)
                if os.path.isfile(tpl_path):
                    with open(tpl_path, "r", encoding="utf-8") as f:
                        template_html = f.read()
                else:
                    logging.warning("Template not found: %s, using inline fallback", tpl_path)
                    template_html = (
                        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
                        '<title>Translated Document</title>'
                        '<style>body{font-family:"Times New Roman",serif;padding:20px;max-width:800px;margin:auto;}'
                        '.doc-content{white-space:pre-wrap;line-height:1.7;font-size:14px;}</style></head>'
                        '<body><div class="doc-content">{{CONTENT}}</div></body></html>'
                    )
                yield from send_event(2, "⏳ Đang tạo HTML theo template...")
                llm_translate = ChatOpenAI(model=translate_model, temperature=0)
                html_result = _build_translation_html(
                    llm_translate,
                    translated_text,
                    template_html,
                    translated_text,
                )

            if not html_result.strip():
                yield from send_event(-1, "❌ Không tạo được HTML")
                return
            # Embed local template images (e.g. Emblem_of_Vietnam.png) as base64
            html_result = _embed_template_images(html_result)
            yield from send_event(2, "✅ Tạo HTML hoàn tất")

            file_stem = os.path.splitext(os.path.basename(source_path))[0]
            safe_stem = _safe_name(file_stem) or "translated_document"
            out_dir = os.path.join(TRANSLATE_OUTPUT_DIR, f"flow_{flow_id}")
            os.makedirs(out_dir, exist_ok=True)

            translated_path = os.path.join(out_dir, f"{safe_stem}.translated.txt")
            html_path = os.path.join(out_dir, f"{safe_stem}.translated.html")
            with open(translated_path, "w", encoding="utf-8") as f:
                f.write(translated_text)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_result)

            yield from send_event(
                3,
                "✅ Hoàn tất",
                {
                    "translated_text": translated_text,
                    "html": html_result,
                    "paths": {
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
                    except Exception as e:
                        logging.debug("Ignored: %s", e)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@splitter_bp.post("/api/translate/save_html")
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


@splitter_bp.post("/api/translate/rebuild_html")
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
        # Embed local template images as base64
        html_result = _embed_template_images(html_result)
        return jsonify({"html": html_result})
    except QuotaExhaustedError as qe:
        return jsonify({"error": "quota_exceeded", "detail": str(qe)}), 429
    except Exception as e:
        if _is_quota_error(e):
            return jsonify({"error": "quota_exceeded", "detail": "⚠️ Đã hết quota OpenAI API! Vui lòng kiểm tra billing."}), 429
        return jsonify({"error": str(e)}), 500




# ─── Serve output files (so previews persist after F5) ───

_OUTPUT_DIR = os.path.join(str(_BASE_DIR), "output")

@splitter_bp.route("/api/output/<path:filename>", methods=["GET"])
def serve_output_file(filename):
    """Serve HTML files from the output directory."""
    safe_name = os.path.basename(filename)
    fpath = os.path.join(_OUTPUT_DIR, safe_name)
    if os.path.exists(fpath):
        with open(fpath, "r", encoding="utf-8") as f:
            return f.read(), 200, {
                "Content-Type": "text/html; charset=utf-8",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            }
    return "", 404


@splitter_bp.route("/api/output-files", methods=["GET"])
def list_output_files():
    """List available output files for auto-loading previews."""
    files = {}
    itin_path = os.path.join(_OUTPUT_DIR, "itinerary.html")
    if os.path.exists(itin_path):
        files["itinerary"] = True
    hotel_files = []
    for i in range(1, 10):
        hpath = os.path.join(_OUTPUT_DIR, f"booking_hotel_{i}.html")
        if os.path.exists(hpath):
            hotel_files.append(f"booking_hotel_{i}.html")
        else:
            break
    if hotel_files:
        files["hotel_bookings"] = hotel_files
    return jsonify(files)


