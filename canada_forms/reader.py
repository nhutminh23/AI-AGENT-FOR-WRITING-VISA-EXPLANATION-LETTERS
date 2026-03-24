"""
Read input files (PDF, DOCX, images) for the Canada forms module.

Extracts text content from various file types to feed into the AI agent.
Reuses existing OCR patterns from the main project.
"""
from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Supported file extensions
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}


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


def read_image_as_base64(file_path: str | Path) -> str:
    """Read an image file and return base64-encoded string."""
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


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


def is_scanned_pdf(file_path: str | Path) -> bool:
    """
    Heuristic: check if a PDF is scanned (image-based) by looking at text content.
    If the extracted text is very short relative to page count, it's likely scanned.
    """
    text = read_pdf_text(file_path)
    import pypdf
    reader = pypdf.PdfReader(str(file_path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            return True
    num_pages = len(reader.pages)
    # Less than 50 chars per page = likely scanned
    return len(text.strip()) < (num_pages * 50)


def pdf_pages_to_images(file_path: str | Path, dpi: int = 200) -> list[str]:
    """
    Convert PDF pages to base64 images for OCR via vision model.
    Returns list of base64-encoded PNG strings.
    """
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(file_path))
        images = []
        for page in doc:
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            images.append(base64.b64encode(img_bytes).decode("utf-8"))
        doc.close()
        return images
    except Exception as exc:
        logger.warning("Error converting PDF to images: %s", exc)
        return []


def read_all_files(file_paths: list[str | Path]) -> list[dict]:
    """
    Read all input files and return structured content list.

    Returns
    -------
    list[dict]
        Each dict has:
        - filename: str
        - type: "text" | "image" | "scanned_pdf"
        - content: str (text content) or None
        - images: list[dict] (base64 images for vision) or None
    """
    results = []

    for fp in file_paths:
        fp = Path(fp)
        if not fp.exists():
            logger.warning("File not found: %s", fp)
            continue

        if fp.suffix.lower() not in SUPPORTED_EXTENSIONS:
            logger.warning("Unsupported file type: %s", fp)
            continue

        entry = {
            "filename": fp.name,
            "type": "text",
            "content": None,
            "images": None,
        }

        if is_image_file(fp):
            entry["type"] = "image"
            entry["images"] = [{
                "base64": read_image_as_base64(fp),
                "mime_type": get_mime_type(fp),
            }]

        elif is_pdf_file(fp):
            if is_scanned_pdf(fp):
                entry["type"] = "scanned_pdf"
                b64_pages = pdf_pages_to_images(fp)
                entry["images"] = [
                    {"base64": b64, "mime_type": "image/png"}
                    for b64 in b64_pages
                ]
            else:
                entry["type"] = "text"
                entry["content"] = read_pdf_text(fp)

        elif fp.suffix.lower() in (".docx", ".doc"):
            entry["type"] = "text"
            entry["content"] = read_docx_text(fp)

        results.append(entry)

    return results
