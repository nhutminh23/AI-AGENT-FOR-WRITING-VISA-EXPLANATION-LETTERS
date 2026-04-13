"""
Shared state, constants, and helper functions for translation routes.

This module defines the Blueprint, directory constants, in-memory cache,
and all helper/utility functions used across translation sub-modules.
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

# ─── Blueprint ────────────────────────────────────────────────────────
splitter_translate_bp = Blueprint("splitter_translate", __name__)

# ─── Directory Constants ─────────────────────────────────────────────
_BASE_DIR = SplitterPath(__file__).parent.parent

TRANSLATE_TEMPLATE_DIR = os.path.join(str(_BASE_DIR), Config.TRANSLATION_TEMPLATE_DIR)
TRANSLATE_DEFAULT_TEMPLATE = Config.TRANSLATION_DEFAULT_TEMPLATE
TRANSLATE_OUTPUT_DIR = os.path.join(str(_BASE_DIR), Config.TRANSLATION_OUTPUT_DIR)
TRANSLATE_HTML_SAVE_DIR = os.path.join(str(_BASE_DIR), Config.TRANSLATION_HTML_SAVE_DIR)

# ─── In-memory Cache ─────────────────────────────────────────────────
translation_upload_cache: Dict[str, Dict] = {}

# Persistent storage for original uploaded files (survives F5 + server restart)
TRANSLATION_ORIGINALS_DIR = os.path.join(str(_BASE_DIR), "uploads", "translation_originals")
os.makedirs(TRANSLATION_ORIGINALS_DIR, exist_ok=True)

_is_quota_error = is_quota_error

# ─── Document types that should NOT be translated ────────────────────
_SKIP_TRANSLATION_KEYWORDS = [
    "passport", "photo", "citizen_identity", "cccd",
    "residence_permit", "visa_application", "visa_form",
]

# ─── Scannable file extensions ───────────────────────────────────────
SCAN_EXTS = {".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}


# =====================================================================
# Helper Functions
# =====================================================================

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
                    html = re.sub(
                        r'<img\s+class="emblem-placeholder"[^>]*>',
                        f'<img src="data:image/png;base64,{emblem_b64}" alt="National Emblem" '
                        f'style="width:60px;height:auto;display:block;margin:0 auto 8px;">',
                        html,
                    )
                except Exception:
                    logging.exception("[Safe Log] Failed to embed emblem")
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
            "skip": True,
            "reason": skip_reason,
            "languages": [],
        }

    # --- OCR page 1 ---
    ext = os.path.splitext(filename)[1].lower()
    b64 = ""

    try:
        if ext == ".pdf":
            import fitz
            doc = fitz.open(filepath)
            if len(doc) == 0:
                doc.close()
                return {
                    "filename": filename,
                    "is_bilingual": False,
                    "needs_translation": True,
                    "reason": "PDF rỗng (0 trang)",
                    "languages": [],
                }
            pix = doc[0].get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            b64 = _resize_image_b64(img_bytes)
            doc.close()
        elif ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"):
            with open(filepath, "rb") as f:
                img_bytes = f.read()
            b64 = _resize_image_b64(img_bytes)
        else:
            # Can't OCR this type — assume it needs translation
            return {
                "filename": filename,
                "is_bilingual": False,
                "needs_translation": True,
                "reason": f"Không hỗ trợ OCR cho {ext}",
                "languages": [],
            }
    except Exception as e:
        logging.warning("Failed to read %s: %s", filename, e)
        return {
            "filename": filename,
            "is_bilingual": False,
            "needs_translation": True,
            "reason": f"Lỗi đọc file: {str(e)[:50]}",
            "languages": [],
        }

    if not b64:
        return {
            "filename": filename,
            "is_bilingual": False,
            "needs_translation": True,
            "reason": "Không thể OCR",
            "languages": [],
        }

    # --- Ask LLM to check languages ---
    try:
        result = llm.invoke([
            SystemMessage(content=(
                "You are a language detection expert. Analyze the document image and identify ALL languages present. "
                "Respond in this EXACT JSON format only:\n"
                '{"languages": ["lang1", "lang2"], "is_bilingual": true/false, "needs_translation": true/false, "reason": "brief explanation"}\n\n'
                "Rules:\n"
                "- is_bilingual=true if BOTH Vietnamese AND English text are present\n"
                "- needs_translation=true if the document is ONLY in Vietnamese (no English)\n"
                "- needs_translation=false if already bilingual or already in English\n"
                "- Output ONLY the JSON, nothing else"
            )),
            HumanMessage(content=[
                {"type": "text", "text": f"Analyze this document image. Filename: {filename}"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ]),
        ])

        raw = (result.content or "").strip()
        # Parse JSON from response
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        
        data = json.loads(raw)
        data["filename"] = filename
        return data
    except Exception as e:
        logging.warning("Language detection failed for %s: %s", filename, e)
        return {
            "filename": filename,
            "is_bilingual": False,
            "needs_translation": True,
            "reason": f"Lỗi phát hiện ngôn ngữ: {str(e)[:50]}",
            "languages": [],
        }


def _html_to_pdf(html_path: str, output_pdf_path: str):
    """Convert an HTML file to PDF using pdfkit (wkhtmltopdf) or browser fallback."""
    import subprocess

    try:
        import pdfkit
        pdfkit.from_file(html_path, output_pdf_path, options={
            "page-size": "A4",
            "margin-top": "15mm",
            "margin-bottom": "15mm",
            "margin-left": "18mm",
            "margin-right": "18mm",
            "encoding": "UTF-8",
            "enable-local-file-access": "",
        })
    except Exception as pdfkit_err:
        logging.warning("pdfkit failed, trying browser: %s", pdfkit_err)
        edge_paths = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        ]
        browser_path = None
        for p in edge_paths:
            if os.path.isfile(p):
                browser_path = p
                break

        if browser_path:
            subprocess.run([
                browser_path,
                "--headless",
                "--disable-gpu",
                f"--print-to-pdf={output_pdf_path}",
                "--no-pdf-header-footer",
                f"file:///{html_path.replace(os.sep, '/')}",
            ], capture_output=True, timeout=30, check=True)
        else:
            raise RuntimeError("No PDF converter found (install wkhtmltopdf or Chrome/Edge)")


def _convert_pdf_to_grayscale(input_path: str, output_path: str):
    """Convert all pages of a PDF to grayscale (black & white).

    Re-renders each page as a grayscale image at 200 DPI and rebuilds
    the PDF. This ensures no color appears in the final document.
    """
    import fitz

    src = fitz.open(input_path)
    dst = fitz.open()

    for page in src:
        # Render page as grayscale pixmap
        pix = page.get_pixmap(dpi=200, colorspace=fitz.csGRAY)
        # Convert grayscale pixmap back to RGB for PDF compatibility
        pix_rgb = fitz.Pixmap(fitz.csRGB, pix)

        # Create new page with same dimensions
        new_page = dst.new_page(width=page.rect.width, height=page.rect.height)
        new_page.insert_image(new_page.rect, pixmap=pix_rgb)

    total_pages = len(dst)
    dst.save(output_path, garbage=4, deflate=True)
    dst.close()
    src.close()
    logging.info("  🖤 Converted to grayscale: %s (%d pages)", output_path, total_pages)


def _convert_image_to_a4_pdf(image_path: str) -> str:
    """Converts an image to an A4-sized PDF, centering the image to maintain aspect ratio."""
    import fitz
    
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
