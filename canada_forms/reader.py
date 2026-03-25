"""
Read input files (PDF, DOCX, images) for the Canada forms module.

Extracts text content from various file types to feed into the AI agent.
Optimised for speed + accuracy + token savings:
  - Single-pass scanned-PDF detection (no double-read)
  - Lower DPI (150) with max-dimension cap → fewer tokens, still accurate
  - Skips blank / near-blank pages
  - Parallel file reading via ThreadPoolExecutor
"""
from __future__ import annotations

import base64
import io
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

logger = logging.getLogger(__name__)

# Supported file extensions
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}

# Image conversion settings — tune for speed vs accuracy
PDF_IMAGE_DPI = 150          # 150 DPI is enough for OCR, ~44% smaller than 200 DPI
MAX_IMAGE_DIM = 1568         # Cap longest side → fewer vision tokens
BLANK_PAGE_THRESHOLD = 30    # Skip pages with < 30 chars of text (likely blank)
MAX_WORKERS = 4              # Parallel file readers


def read_pdf_text(file_path: str | Path) -> str:
    """Extract text from a PDF using pypdf."""
    import pypdf

    reader = pypdf.PdfReader(str(file_path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            logger.warning("Cannot decrypt PDF: %s", file_path)
            return ""

    pages_text = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages_text.append(f"--- Page {i+1} ---\n{text}")

    return "\n\n".join(pages_text)


def read_docx_text(file_path: str | Path) -> str:
    """Extract text from a DOCX file."""
    try:
        import docx
        doc = docx.Document(str(file_path))
        return "\n".join(para.text for para in doc.paragraphs if para.text.strip())
    except ImportError:
        logger.warning("python-docx not installed, cannot read DOCX files")
        return ""
    except Exception as exc:
        logger.warning("Error reading DOCX %s: %s", file_path, exc)
        return ""


def _resize_image_bytes(img_bytes: bytes, max_dim: int = MAX_IMAGE_DIM) -> bytes:
    """Resize image if any dimension exceeds max_dim. Returns PNG bytes."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(img_bytes))
        w, h = img.size
        if max(w, h) <= max_dim:
            return img_bytes  # Already small enough
        ratio = max_dim / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        img = img.resize(new_size, Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    except ImportError:
        return img_bytes  # No Pillow, return as-is
    except Exception:
        return img_bytes


def read_image_as_base64(file_path: str | Path) -> str:
    """Read an image file, resize if too large, return base64-encoded string."""
    with open(file_path, "rb") as f:
        raw = f.read()
    resized = _resize_image_bytes(raw)
    return base64.b64encode(resized).decode("utf-8")


def get_mime_type(file_path: str | Path) -> str:
    """Get MIME type from file extension."""
    ext = Path(file_path).suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
        ".pdf": "application/pdf",
    }
    return mime_map.get(ext, "application/octet-stream")


def is_image_file(file_path: str | Path) -> bool:
    """Check if the file is an image."""
    return Path(file_path).suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}


def is_pdf_file(file_path: str | Path) -> bool:
    """Check if the file is a PDF."""
    return Path(file_path).suffix.lower() == ".pdf"


def _read_pdf_smart(file_path: Path) -> dict:
    """
    Single-pass PDF reader: extract text, detect scan, convert to images if needed.
    Avoids reading the PDF twice (old is_scanned_pdf did a double-read).
    """
    import pypdf

    reader = pypdf.PdfReader(str(file_path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            logger.warning("Cannot decrypt PDF: %s", file_path)

    num_pages = len(reader.pages)

    # Single pass: extract text
    pages_text = []
    total_chars = 0
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        stripped = text.strip()
        total_chars += len(stripped)
        if stripped:
            pages_text.append(f"--- Page {i+1} ---\n{text}")

    full_text = "\n\n".join(pages_text)

    # Heuristic: < 50 chars per page = scanned PDF
    is_scanned = total_chars < (num_pages * 50)

    if not is_scanned:
        # Text-based PDF — just return text (cheap, fast)
        return {
            "filename": file_path.name,
            "type": "text",
            "content": full_text,
            "images": None,
        }

    # Scanned PDF — convert to images
    logger.info("Scanned PDF detected: %s (%d pages, %d chars)", file_path.name, num_pages, total_chars)
    images = _pdf_to_images_optimized(file_path, num_pages)

    return {
        "filename": file_path.name,
        "type": "scanned_pdf",
        "content": full_text if full_text else None,  # Include any OCR text too
        "images": images,
    }


def _pdf_to_images_optimized(file_path: Path, num_pages: int) -> list[dict]:
    """
    Convert PDF pages to base64 images with optimisations:
    - Lower DPI (150 vs 200) → ~44% smaller files
    - Skip blank pages
    - Resize if too large → fewer vision API tokens
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.warning("PyMuPDF not installed, cannot convert PDF to images")
        return []

    doc = fitz.open(str(file_path))
    images = []
    for i, page in enumerate(doc):
        # Quick blank-page check: if page has very little content, skip
        text = page.get_text().strip()
        if len(text) < BLANK_PAGE_THRESHOLD and not page.get_images():
            logger.debug("Skipping blank page %d in %s", i + 1, file_path.name)
            continue

        mat = fitz.Matrix(PDF_IMAGE_DPI / 72, PDF_IMAGE_DPI / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")

        # Resize if too large (saves tokens)
        img_bytes = _resize_image_bytes(img_bytes)

        images.append({
            "base64": base64.b64encode(img_bytes).decode("utf-8"),
            "mime_type": "image/png",
            "page": i + 1,
        })
    doc.close()

    logger.info("Converted %s: %d/%d pages → images", file_path.name, len(images), num_pages)
    return images


def _read_single_file(fp: Path) -> dict | None:
    """Read a single file and return structured content. Used by ThreadPoolExecutor."""
    if not fp.exists():
        logger.warning("File not found: %s", fp)
        return None

    if fp.suffix.lower() not in SUPPORTED_EXTENSIONS:
        logger.warning("Unsupported file type: %s", fp)
        return None

    try:
        if is_image_file(fp):
            return {
                "filename": fp.name,
                "type": "image",
                "content": None,
                "images": [{
                    "base64": read_image_as_base64(fp),
                    "mime_type": get_mime_type(fp),
                }],
            }

        elif is_pdf_file(fp):
            return _read_pdf_smart(fp)

        elif fp.suffix.lower() in (".docx", ".doc"):
            return {
                "filename": fp.name,
                "type": "text",
                "content": read_docx_text(fp),
                "images": None,
            }
    except Exception as exc:
        logger.error("Error reading %s: %s", fp.name, exc)
        return None

    return None


def read_all_files(file_paths: list[str | Path]) -> list[dict]:
    """
    Read all input files and return structured content list.
    Uses parallel processing for speed.

    Returns
    -------
    list[dict]
        Each dict has:
        - filename: str
        - type: "text" | "image" | "scanned_pdf"
        - content: str (text content) or None
        - images: list[dict] (base64 images for vision) or None
    """
    paths = [Path(fp) for fp in file_paths]

    # Parallel file reading — 4 workers for I/O bound tasks
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_path = {executor.submit(_read_single_file, fp): fp for fp in paths}
        for future in as_completed(future_to_path):
            result = future.result()
            if result:
                results.append(result)

    # Sort by original order (as_completed doesn't preserve order)
    path_order = {p.name: i for i, p in enumerate(paths)}
    results.sort(key=lambda r: path_order.get(r["filename"], 999))

    total_images = sum(len(r.get("images") or []) for r in results)
    logger.info(
        "Read %d files: %d text, %d with images (%d total images)",
        len(results),
        sum(1 for r in results if r["type"] == "text"),
        sum(1 for r in results if r.get("images")),
        total_images,
    )

    return results
