"""
Document translation routes: bilingual check, OCR+translate, HTML generation.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import tempfile
import uuid
from pathlib import Path as SplitterPath
from typing import Any, Dict, List, Optional

from flask import Blueprint, Response, jsonify, request

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from core.errors import QuotaExhaustedError, is_quota_error
from config import Config
import database as db

splitter_translate_bp = Blueprint("splitter_translate", __name__)

# Base directory (project root, one level up from routes/)
_BASE_DIR = SplitterPath(__file__).parent.parent

# Translation directories
TRANSLATE_TEMPLATE_DIR = os.path.join(str(_BASE_DIR), Config.TRANSLATION_TEMPLATE_DIR)
TRANSLATE_DEFAULT_TEMPLATE = Config.TRANSLATION_DEFAULT_TEMPLATE
TRANSLATE_OUTPUT_DIR = os.path.join(str(_BASE_DIR), Config.TRANSLATION_OUTPUT_DIR)
TRANSLATE_HTML_SAVE_DIR = os.path.join(str(_BASE_DIR), Config.TRANSLATION_HTML_SAVE_DIR)

# In-memory cache for uploaded translation files
translation_upload_cache: Dict[str, Dict] = {}

# Persistent storage for original uploaded files (survives F5 + server restart)
TRANSLATION_ORIGINALS_DIR = os.path.join(str(_BASE_DIR), "uploads", "translation_originals")
os.makedirs(TRANSLATION_ORIGINALS_DIR, exist_ok=True)

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
        # Try in-memory cache first (fast path)
        meta = translation_upload_cache.get(token)
        if meta and os.path.isfile(meta.get("temp_path", "")):
            return meta["temp_path"]
        # Fallback: scan persistent directory for file with this token in name
        # (handles server restart where in-memory cache is lost)
        for fname in os.listdir(TRANSLATION_ORIGINALS_DIR):
            if token in fname:
                disk_path = os.path.join(TRANSLATION_ORIGINALS_DIR, fname)
                if os.path.isfile(disk_path):
                    # Re-populate in-memory cache for future calls
                    translation_upload_cache[token] = {"temp_path": disk_path, "filename": fname}
                    return disk_path
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
                    import logging, sys; logging.exception("[Safe Log] Unhandled exception in splitter_translate.py: %s", sys.exc_info()[1])
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
        logging.exception("[Safe Log] Unhandled exception in splitter_translate.py: %s", e)
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



@splitter_translate_bp.post("/api/translate/check_bilingual")
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
                logging.exception("[Safe Log] Unhandled exception in splitter_translate.py: %s", e)
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


@splitter_translate_bp.get("/api/translate/templates")
def list_translate_templates():
    _ensure_translate_template_dir()
    templates: List[Dict[str, str]] = []
    for name in sorted(os.listdir(TRANSLATE_TEMPLATE_DIR)):
        path = os.path.join(TRANSLATE_TEMPLATE_DIR, name)
        if os.path.isfile(path) and name.lower().endswith(".html"):
            templates.append({"name": name})
    return jsonify({"templates": templates, "default": TRANSLATE_DEFAULT_TEMPLATE})


@splitter_translate_bp.post("/api/translate/upload")
def translate_upload_file():
    """Upload a file for translation flow — persisted to uploads/translation_originals/."""
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
    # Save to persistent directory (survives F5 + server restart)
    out_path = os.path.join(TRANSLATION_ORIGINALS_DIR, out_name)

    try:
        f.save(out_path)
    except Exception as e:
        logging.exception("[Safe Log] Unhandled exception in splitter_translate.py: %s", e)
        return jsonify({"error": "save_failed", "detail": str(e)}), 500

    # Keep in-memory cache for backwards compat with existing code paths
    translation_upload_cache[token] = {"temp_path": out_path, "filename": safe_name}
    file_ref = f"upload_token:{token}"
    return jsonify(
        {
            "status": "success",
            "file_ref": file_ref,
            "filename": safe_name,
            "persistent_path": out_path,
        }
    )



@splitter_translate_bp.post("/api/translate/original_pages")
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
        logging.exception("[Safe Log] Unhandled exception in splitter_translate.py: %s", e)
        return jsonify({"error": "save_failed", "detail": str(e)}), 500

    pages = []
    try:
        # User requested: Automatically convert input images to A4 PDF
        # so that the original page renders with correct A4 aspect ratio 
        # for printing (preventing horizontal squashing).
        if ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"):
            tmp_path = _convert_image_to_a4_pdf(tmp_path)
            ext = ".pdf"
            
        if ext == ".pdf":
            import fitz  # PyMuPDF
            doc = fitz.open(tmp_path)
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                b64 = base64.b64encode(img_bytes).decode("ascii")
                pages.append({"index": i, "data_url": f"data:image/png;base64,{b64}"})
            doc.close()
        else:
            return jsonify({"error": "unsupported_format", "detail": f"Cannot render {ext} as images"}), 400
    except Exception as e:
        logging.exception("[Safe Log] Unhandled exception in splitter_translate.py: %s", e)
        return jsonify({"error": "render_failed", "detail": str(e)}), 500
    finally:
        # Cleanup temp file
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    return jsonify({"pages": pages})


@splitter_translate_bp.post("/api/translate/original_pages_by_ref")
def translate_original_pages_by_ref():
    """Render original file pages as base64 PNG images using file_ref (for restored flows)."""
    payload = request.get_json(force=True, silent=True) or {}
    file_ref = (payload.get("file_ref") or "").strip()
    if not file_ref:
        return jsonify({"error": "missing_file_ref"}), 400

    input_dir = current_app.config.get("UPLOAD_FOLDER", "uploads")
    source_path = _resolve_translate_source_path(input_dir, file_ref)
    if not source_path:
        return jsonify({"error": "file_not_found", "detail": f"Cannot resolve: {file_ref}"}), 404

    ext = os.path.splitext(source_path)[1].lower()
    pages = []
    tmp_path = None
    try:
        if ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"):
            tmp_path = _convert_image_to_a4_pdf(source_path)
            render_path = tmp_path
        elif ext == ".pdf":
            render_path = source_path
        else:
            return jsonify({"error": "unsupported_format", "detail": f"Cannot render {ext}"}), 400

        import fitz
        doc = fitz.open(render_path)
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            b64 = base64.b64encode(img_bytes).decode("ascii")
            pages.append({"index": i, "data_url": f"data:image/png;base64,{b64}"})
        doc.close()
    except Exception as e:
        logging.exception("[Safe Log] original_pages_by_ref error: %s", e)
        return jsonify({"error": "render_failed", "detail": str(e)}), 500
    finally:
        if tmp_path and tmp_path != source_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    return jsonify({"pages": pages})


@splitter_translate_bp.get("/api/translate/certification_template")
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

def _convert_image_to_a4_pdf(image_path: str) -> str:
    """Converts an image to an A4-sized PDF, centering the image to maintain aspect ratio."""
    import fitz
    import tempfile
    
    A4_WIDTH = 595.0
    A4_HEIGHT = 842.0
    
    doc = fitz.open()
    page = doc.new_page(width=A4_WIDTH, height=A4_HEIGHT)
    
    img_doc = fitz.open(image_path)
    rect = img_doc[0].rect
    img_w, img_h = rect.width, rect.height
    img_doc.close()
    
    margin = 20
    scale = min((A4_WIDTH - 2*margin) / img_w, (A4_HEIGHT - 2*margin) / img_h)
    new_w, new_h = img_w * scale, img_h * scale
    
    x0, y0 = (A4_WIDTH - new_w) / 2, (A4_HEIGHT - new_h) / 2
    target_rect = fitz.Rect(x0, y0, x0 + new_w, y0 + new_h)
    
    page.insert_image(target_rect, filename=image_path)
    
    fd, temp_pdf_path = tempfile.mkstemp(suffix=".pdf", prefix="img_to_a4_")
    os.close(fd)
    doc.save(temp_pdf_path)
    doc.close()
    return temp_pdf_path


@splitter_translate_bp.post("/api/translate/run_stream")
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
        
    # User requested: Automatically convert input images to A4 PDF
    # so that the AI layout and HTML mapper don't overflow the page bounds.
    ext = os.path.splitext(source_path)[1].lower()
    if ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"):
        try:
            source_path = _convert_image_to_a4_pdf(source_path)
        except Exception as e:
            logging.exception("Failed to convert image to A4 PDF: %s", e)
            # Proceeding with original image if it fails

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
                    logging.exception("[Safe Log] Unhandled exception in splitter_translate.py: %s", e)
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
            logging.exception("[Safe Log] Unhandled exception in splitter_translate.py: %s", e)
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
                        logging.exception("[Safe Log] Unhandled exception in splitter_translate.py: %s", e)
                        logging.debug("Ignored: %s", e)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@splitter_translate_bp.post("/api/translate/save_html")
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
        logging.exception("[Safe Log] Unhandled exception in splitter_translate.py: %s", e)
        return jsonify({"error": "save_failed", "detail": str(e)}), 500

    return jsonify(
        {
            "status": "success",
            "saved_path": out_path.replace("\\", "/"),
            "saved_name": os.path.basename(out_path),
        }
    )


@splitter_translate_bp.post("/api/translate/rebuild_html")
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
        logging.exception("[Safe Log] Unhandled exception in splitter_translate.py: %s", e)
        if _is_quota_error(e):
            return jsonify({"error": "quota_exceeded", "detail": "⚠️ Đã hết quota OpenAI API! Vui lòng kiểm tra billing."}), 429
        return jsonify({"error": str(e)}), 500




# ─── Serve output files (so previews persist after F5) ───

_OUTPUT_DIR = os.path.join(str(_BASE_DIR), "output")

@splitter_translate_bp.route("/api/output/<path:filename>", methods=["GET"])
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


@splitter_translate_bp.route("/api/output-files", methods=["GET"])
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


# ==================== TRANSLATION FLOW PERSISTENCE ====================

@splitter_translate_bp.get("/api/translate/flows")
def list_translate_flows():
    """List all saved translation flows."""
    flows = db.list_translation_flows()
    return jsonify({"flows": flows})


@splitter_translate_bp.post("/api/translate/flows")
def create_translate_flow():
    """Create (save) a new translation flow."""
    data = request.get_json(force=True, silent=True) or {}
    flow = db.save_translation_flow(
        filename=data.get("filename", ""),
        file_ref=data.get("file_ref", ""),
        template_name=data.get("template_name", "auto"),
        source_lang=data.get("source_lang", "vi"),
        ocr_text=data.get("ocr_text", ""),
        translated_text=data.get("translated_text", ""),
        html_content=data.get("html_content", ""),
        save_name=data.get("save_name", ""),
        status=data.get("status", "done"),
    )
    return jsonify(flow), 201


@splitter_translate_bp.put("/api/translate/flows/<int:flow_id>")
def update_translate_flow(flow_id):
    """Update an existing translation flow (e.g. after editing HTML)."""
    data = request.get_json(force=True, silent=True) or {}
    # Only allow updating specific fields
    allowed = {"filename", "file_ref", "template_name", "source_lang",
               "ocr_text", "translated_text", "html_content", "save_name", "status"}
    updates = {k: v for k, v in data.items() if k in allowed}
    result = db.update_translation_flow(flow_id, **updates)
    if result is None:
        return jsonify({"error": "not_found"}), 404
    return jsonify(result)


@splitter_translate_bp.delete("/api/translate/flows/<int:flow_id>")
def delete_translate_flow(flow_id):
    """Delete a single translation flow + clean up original file on disk."""
    # Get flow data before deletion to find the file_ref
    flow_data = db.get_translation_flow(flow_id)
    if flow_data:
        _cleanup_original_file(flow_data.get("file_ref", ""))
    ok = db.delete_translation_flow(flow_id)
    if not ok:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"deleted": True, "id": flow_id})


@splitter_translate_bp.delete("/api/translate/flows")
def delete_all_translate_flows():
    """Delete all translation flows + clean up ALL original files on disk."""
    # Get all flows to clean up their files
    all_flows = db.list_translation_flows()
    for f in all_flows:
        _cleanup_original_file(f.get("file_ref", ""))
    count = db.delete_all_translation_flows()
    return jsonify({"deleted": True, "count": count})


def _cleanup_original_file(file_ref: str):
    """Remove the original uploaded file from disk given a file_ref."""
    if not file_ref:
        return
    if file_ref.startswith("upload_token:"):
        token = file_ref.split(":", 1)[1].strip()
        # Remove from in-memory cache
        meta = translation_upload_cache.pop(token, None)
        if meta:
            path = meta.get("temp_path", "")
            if path and os.path.isfile(path):
                try:
                    os.remove(path)
                    logging.info("[Cleanup] Removed original file: %s", path)
                except OSError as e:
                    logging.warning("[Cleanup] Failed to remove %s: %s", path, e)
                return
        # Fallback: scan persistent directory
        for fname in os.listdir(TRANSLATION_ORIGINALS_DIR):
            if token in fname:
                disk_path = os.path.join(TRANSLATION_ORIGINALS_DIR, fname)
                try:
                    os.remove(disk_path)
                    logging.info("[Cleanup] Removed original file: %s", disk_path)
                except OSError as e:
                    logging.warning("[Cleanup] Failed to remove %s: %s", disk_path, e)
                break

