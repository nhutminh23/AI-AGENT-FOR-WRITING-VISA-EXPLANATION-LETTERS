"""
PDF Stamper – Digital stamp and edge-seal overlay engine.

Applies two types of stamps to translated PDF documents:
1. **Company stamp + signature** (``moc_chu_ky.png``) → centered on the LAST page
   (positioned over the "Signature of translator" area of the certification page).
2. **Edge seal / Giáp lai** (``moc_giap_lai.png``) → sliced vertically and overlaid
   on the right edge of EVERY page to prove continuity.

Uses PyMuPDF (``fitz``) for fast, high-quality PDF manipulation.
"""
from __future__ import annotations

import logging
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger("pdf_tools.stamper")

# Default asset paths (relative to this file)
_ASSETS_DIR = Path(__file__).parent / "assets"
_DEFAULT_STAMP_PATH = _ASSETS_DIR / "moc_chu_ky.png"
_DEFAULT_SEAL_PATH = _ASSETS_DIR / "moc_giap_lai.png"


def stamp_pdf(
    input_path: str | Path,
    output_path: str | Path | None = None,
    stamp_path: str | Path | None = None,
    seal_path: str | Path | None = None,
    stamp_width_pt: float = 180,
    seal_height_pt: float = 110,
    seal_margin_right_pt: float = 0,
    stamp_center_x_pt: float | None = None,
    stamp_center_y_pt: float = 370,
) -> Path:
    """
    Apply company stamp + edge seal to a PDF.

    Parameters
    ----------
    input_path : str | Path
        Path to the input PDF file.
    output_path : str | Path, optional
        Where to write the stamped PDF. If None, overwrites input.
    stamp_path : str | Path, optional
        Path to the stamp+signature PNG (RGBA). Defaults to built-in asset.
    seal_path : str | Path, optional
        Path to the seal-only PNG (RGBA) for giáp lai. Defaults to built-in asset.
    stamp_width_pt : float
        Width of the stamp image on the last page (in PDF points, 1 pt = 1/72 inch).
        Height is auto-calculated to preserve aspect ratio.
    seal_height_pt : float
        Display height of the seal circle on EACH page (in PDF points).
        Strip width is auto-calculated based on page count and aspect ratio.
    seal_margin_right_pt : float
        Margin from right edge of page to the seal strip (0 = flush to edge).
    stamp_center_x_pt : float, optional
        X center of the stamp on the last page. If None, uses page center.
    stamp_center_y_pt : float
        Y center of the stamp on the last page (from top). Default 330pt
        matches the "Signature of translator" area of the certification template.

    Returns
    -------
    Path
        Absolute path to the stamped output PDF.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input PDF not found: {input_path}")

    stamp_path = Path(stamp_path) if stamp_path else _DEFAULT_STAMP_PATH
    seal_path = Path(seal_path) if seal_path else _DEFAULT_SEAL_PATH

    if not stamp_path.exists():
        raise FileNotFoundError(f"Stamp image not found: {stamp_path}")
    if not seal_path.exists():
        raise FileNotFoundError(f"Seal image not found: {seal_path}")

    if output_path is None:
        output_path = input_path
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Open PDF
    doc = fitz.open(str(input_path))
    page_count = len(doc)

    if page_count == 0:
        logger.warning("PDF has 0 pages, nothing to stamp: %s", input_path)
        doc.close()
        return output_path

    logger.info(
        "Stamping PDF: %s (%d pages) -> %s",
        input_path.name, page_count, output_path.name,
    )

    # --- Normalize all pages to A4 (so seal looks consistent) ---
    _normalize_pages_to_a4(doc)
    page_count = len(doc)  # refresh in case pages changed

    # --- Edge Seal (Giáp lai) on ALL pages ---
    _apply_edge_seal(doc, seal_path, seal_height_pt, seal_margin_right_pt)

    # --- Company Stamp + Signature on LAST page ---
    _apply_company_stamp(
        doc, stamp_path, stamp_width_pt,
        stamp_center_x_pt, stamp_center_y_pt,
    )

    # Save
    doc.save(str(output_path), garbage=4, deflate=True)
    doc.close()

    logger.info("Stamped PDF saved: %s", output_path)
    return output_path


# A4 dimensions in points (72 dpi)
A4_WIDTH_PT = 595.28
A4_HEIGHT_PT = 841.89
# Tolerance: pages within 0.1% of A4 are considered A4 already
_A4_TOLERANCE = 0.001


def _normalize_pages_to_a4(doc: fitz.Document) -> None:
    """
    Normalize all pages to A4 size. Oversized pages are scaled down to fit A4
    while maintaining aspect ratio. Pages already at A4 (within tolerance) are
    left unchanged.
    """
    def _a4_target_size_for_page(width: float, height: float) -> tuple[float, float]:
        # Preserve page orientation: landscape pages become A4 landscape,
        # portrait pages become A4 portrait.
        if width > height:
            return A4_HEIGHT_PT, A4_WIDTH_PT
        return A4_WIDTH_PT, A4_HEIGHT_PT

    # Find pages that need resizing
    pages_to_resize = []
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        pw, ph = page.rect.width, page.rect.height
        target_w, target_h = _a4_target_size_for_page(pw, ph)
        w_ratio = pw / target_w
        h_ratio = ph / target_h
        if abs(w_ratio - 1.0) > _A4_TOLERANCE or abs(h_ratio - 1.0) > _A4_TOLERANCE:
            pages_to_resize.append(page_idx)

    if not pages_to_resize:
        logger.info("  All pages already A4, no normalization needed")
        return

    # Open a SEPARATE copy of the document as source (PyMuPDF requires src != target)
    src_doc = fitz.open()
    src_doc.insert_pdf(doc)

    # Process in REVERSE order so indices don't shift when deleting/inserting
    for page_idx in reversed(pages_to_resize):
        src_page = src_doc[page_idx]
        pw, ph = src_page.rect.width, src_page.rect.height

        target_w, target_h = _a4_target_size_for_page(pw, ph)
        scale = min(target_w / pw, target_h / ph)
        new_w = pw * scale
        new_h = ph * scale
        x_offset = (target_w - new_w) / 2
        y_offset = (target_h - new_h) / 2
        target_rect = fitz.Rect(x_offset, y_offset, x_offset + new_w, y_offset + new_h)

        # Delete original page
        doc.delete_page(page_idx)

        # Insert new blank A4 page at same position
        doc.insert_page(page_idx, width=target_w, height=target_h)
        new_page = doc[page_idx]

        # Render source page content onto new A4 page
        new_page.show_pdf_page(target_rect, src_doc, page_idx)

        logger.debug(
            "  Page %d: %.0fx%.0f -> A4 (scale=%.2f)",
            page_idx + 1, pw, ph, scale,
        )

    src_doc.close()
    logger.info("  Normalized %d oversized pages to A4", len(pages_to_resize))


def _apply_edge_seal(
    doc: fitz.Document,
    seal_path: Path,
    seal_height_pt: float,
    margin_right_pt: float,
) -> None:
    """
    Slice ONE seal image across ALL pages of the document.

    The seal is divided into equal-width vertical strips — one per page.
    Each strip is placed on the right edge of its page, vertically centered.
    The display size is FIXED regardless of page orientation (portrait vs landscape)
    so the seal looks consistent across mixed-orientation documents.

    Performance: pre-crops all strips into PNG bytes first, then inserts in bulk.
    """
    from PIL import Image
    import io
    import time as _time

    t0 = _time.perf_counter()

    seal_img = Image.open(str(seal_path)).convert("RGBA")
    # Trim transparent padding so first/last strips are not mostly empty.
    alpha_bbox = seal_img.split()[-1].getbbox()
    if alpha_bbox:
        seal_img = seal_img.crop(alpha_bbox)
    seal_w, seal_h = seal_img.size

    page_count = len(doc)
    if page_count == 0:
        return

    # --- Divide the seal image into equal-width strips, one per page ---
    base_strip_w = seal_w // page_count
    extra_pixels = seal_w % page_count
    strip_boundaries = [0]
    running_x = 0
    for j in range(page_count):
        running_x += base_strip_w + (1 if j < extra_pixels else 0)
        strip_boundaries.append(running_x)

    # --- Fixed display width per strip ---
    # Total seal display width ≈ 100pt, spread across all pages.
    # Clamp individual strip width between 10pt and 50pt for readability.
    TOTAL_SEAL_DISPLAY_W = 100.0
    MIN_STRIP_DISPLAY_W = 10.0
    MAX_STRIP_DISPLAY_W = 50.0
    strip_display_w = TOTAL_SEAL_DISPLAY_W / max(page_count, 1)
    strip_display_w = max(MIN_STRIP_DISPLAY_W, min(MAX_STRIP_DISPLAY_W, strip_display_w))

    # --- Fixed display height (same as portrait A4 — never scaled by orientation) ---
    strip_display_h = seal_height_pt

    # --- Phase 1: Pre-crop ALL strips into PNG bytes (batch) ---
    strip_bytes_list = []
    for page_idx in range(page_count):
        left = strip_boundaries[page_idx]
        right = strip_boundaries[page_idx + 1]
        right = min(right, seal_w)
        if right <= left:
            right = min(left + 1, seal_w)
        if right <= left:
            strip_bytes_list.append(None)
            continue

        strip = seal_img.crop((left, 0, right, seal_h))
        buf = io.BytesIO()
        strip.save(buf, format="PNG")
        strip_bytes_list.append(buf.getvalue())

    # Release PIL image immediately — no longer needed
    del seal_img

    # --- Phase 2: Insert pre-cropped strips into pages ---
    for page_idx in range(page_count):
        strip_bytes = strip_bytes_list[page_idx]
        if strip_bytes is None:
            continue

        page = doc[page_idx]
        page_rect = page.rect
        x1 = page_rect.width - margin_right_pt
        x0 = x1 - strip_display_w
        y_center = page_rect.height / 2
        y0 = y_center - strip_display_h / 2
        y1 = y_center + strip_display_h / 2

        stamp_rect = fitz.Rect(x0, y0, x1, y1)

        page.insert_image(
            stamp_rect,
            stream=strip_bytes,
            overlay=True,
        )

    elapsed = (_time.perf_counter() - t0) * 1000
    logger.info(
        "  Edge seal: %d pages, strip_w=%.1fpt, h=%.1fpt in %.0fms",
        page_count, strip_display_w, strip_display_h, elapsed,
    )


def _apply_company_stamp(
    doc: fitz.Document,
    stamp_path: Path,
    stamp_width_pt: float,
    center_x_pt: float | None,
    center_y_pt: float,
) -> None:
    """
    Place the company stamp + signature centered on the last page.

    The stamp is positioned at (center_x_pt, center_y_pt). If center_x_pt is None,
    the stamp is horizontally centered on the page. center_y_pt defaults to 330pt
    which matches the "Signature of translator" area.
    """
    # Read raw PNG bytes — no PIL needed, fitz handles PNG directly
    stamp_bytes = stamp_path.read_bytes()

    # Get dimensions via fitz.Pixmap (avoids PIL import)
    pix = fitz.Pixmap(stamp_bytes)
    aspect = pix.height / pix.width
    stamp_h_pt = stamp_width_pt * aspect
    del pix  # free immediately

    # Last page
    last_page = doc[-1]
    page_rect = last_page.rect

    # Center position
    cx = center_x_pt if center_x_pt is not None else (page_rect.width / 2)
    cy = center_y_pt

    x0 = cx - stamp_width_pt / 2
    x1 = cx + stamp_width_pt / 2
    y0 = cy - stamp_h_pt / 2
    y1 = cy + stamp_h_pt / 2

    stamp_rect = fitz.Rect(x0, y0, x1, y1)

    last_page.insert_image(
        stamp_rect,
        stream=stamp_bytes,
        overlay=True,
    )

    logger.info(
        "  Company stamp on last page (page %d) center=(%.0f, %.0f), size=%.0fx%.0f pt",
        len(doc), cx, cy, stamp_width_pt, stamp_h_pt,
    )
