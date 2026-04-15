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
    seal_height_pt: float = 150,
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
        "Stamping PDF: %s (%d pages) → %s",
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

    logger.info("✅ Stamped PDF saved: %s", output_path)
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
    # Find pages that need resizing
    pages_to_resize = []
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        pw, ph = page.rect.width, page.rect.height
        w_ratio = pw / A4_WIDTH_PT
        h_ratio = ph / A4_HEIGHT_PT
        if abs(w_ratio - 1.0) > _A4_TOLERANCE or abs(h_ratio - 1.0) > _A4_TOLERANCE:
            pages_to_resize.append(page_idx)

    if not pages_to_resize:
        logger.info("  📐 All pages already A4, no normalization needed")
        return

    # Open a SEPARATE copy of the document as source (PyMuPDF requires src != target)
    src_doc = fitz.open()
    src_doc.insert_pdf(doc)

    # Process in REVERSE order so indices don't shift when deleting/inserting
    for page_idx in reversed(pages_to_resize):
        src_page = src_doc[page_idx]
        pw, ph = src_page.rect.width, src_page.rect.height

        scale = min(A4_WIDTH_PT / pw, A4_HEIGHT_PT / ph)
        new_w = pw * scale
        new_h = ph * scale
        x_offset = (A4_WIDTH_PT - new_w) / 2
        y_offset = (A4_HEIGHT_PT - new_h) / 2
        target_rect = fitz.Rect(x_offset, y_offset, x_offset + new_w, y_offset + new_h)

        # Delete original page
        doc.delete_page(page_idx)

        # Insert new blank A4 page at same position
        doc.insert_page(page_idx, width=A4_WIDTH_PT, height=A4_HEIGHT_PT)
        new_page = doc[page_idx]

        # Render source page content onto new A4 page
        new_page.show_pdf_page(target_rect, src_doc, page_idx)

        logger.debug(
            "  📐 Page %d: %.0f×%.0f → A4 (scale=%.2f)",
            page_idx + 1, pw, ph, scale,
        )

    src_doc.close()
    logger.info("  📐 Normalized %d oversized pages to A4", len(pages_to_resize))


def _apply_edge_seal(
    doc: fitz.Document,
    seal_path: Path,
    seal_height_pt: float,
    margin_right_pt: float,
    max_pages_per_seal: int = 4,
) -> None:
    """
    Slice the seal image into groups of at most `max_pages_per_seal` pages.
    Each group gets ONE FULL seal image divided among its pages.

    For example, 14 pages with max_pages_per_seal=5 → 3 groups:
      Group 1: pages 1–5  (seal ÷ 5 strips)
      Group 2: pages 6–10 (seal ÷ 5 strips)
      Group 3: pages 11–14 (seal ÷ 4 strips)
    """
    from PIL import Image
    import io
    import random

    seal_img = Image.open(str(seal_path)).convert("RGBA")
    seal_w, seal_h = seal_img.size
    page_count = len(doc)

    # Split pages into groups of max_pages_per_seal
    # Rule: last group must have >= 2 pages (avoid full seal on cert page alone)
    groups = []
    for start in range(0, page_count, max_pages_per_seal):
        end = min(start + max_pages_per_seal, page_count)
        groups.append((start, end))

    # If last group has only 1 page, merge it into the previous group
    if len(groups) >= 2:
        last_start, last_end = groups[-1]
        if last_end - last_start == 1:
            prev_start, _ = groups[-2]
            groups[-2] = (prev_start, last_end)
            groups.pop()

    logger.info(
        "  📍 Edge seal: %d pages → %d groups (max %d pages/seal)",
        page_count, len(groups), max_pages_per_seal,
    )

    for group_idx, (group_start, group_end) in enumerate(groups):
        group_size = group_end - group_start

        # U-shaped distribution: edge strips get slightly MORE pixels (circle is thin at edges)
        # Keep boost moderate to avoid center pages looking too thin
        edge_boost = 0.6
        center = (group_size - 1) / 2.0
        max_dist = center if center > 0 else 1
        weights = []
        for j in range(group_size):
            dist = abs(j - center) / max_dist  # 0=center, 1=edge
            weights.append(1.0 + edge_boost * dist)
        total_w = sum(weights)
        # Convert weights to cumulative pixel boundaries
        strip_boundaries = [0]
        for j in range(group_size):
            strip_boundaries.append(strip_boundaries[-1] + (weights[j] / total_w) * seal_w)

        # Deterministic RNG per group for consistent randomization
        rng = random.Random(page_count * 7 + seal_w + group_idx * 31)

        for local_i in range(group_size):
            page_idx = group_start + local_i
            page = doc[page_idx]

            # Slice: weighted boundaries (edge strips are wider)
            left = round(strip_boundaries[local_i])
            right = round(strip_boundaries[local_i + 1])
            right = min(right, seal_w)

            strip = seal_img.crop((left, 0, right, seal_h))

            # Random rotation: ±6 degrees for natural hand-stamp look
            rotation_deg = rng.uniform(-6.0, 6.0)
            strip = strip.rotate(rotation_deg, expand=True, resample=Image.BICUBIC)

            # Convert strip to bytes
            buf = io.BytesIO()
            strip.save(buf, format="PNG")
            strip_bytes = buf.getvalue()

            # Calculate display size on page (fixed A4 size after normalization)
            strip_pixel_w = right - left
            strip_pixel_h = seal_h
            strip_aspect_wh = strip_pixel_w / max(strip_pixel_h, 1)
            strip_display_h = seal_height_pt
            strip_display_w = seal_height_pt * strip_aspect_wh

            # Random Y offset: ±15 points for natural variation
            y_offset = rng.uniform(-15.0, 15.0)

            # Position: right edge, vertically centered + random offset
            page_rect = page.rect
            # Last page of each group → push seal to outer edge (rightmost strip)
            is_last_in_group = (local_i == group_size - 1)
            overhang = 35 if is_last_in_group else 0
            x1 = page_rect.width - margin_right_pt + overhang
            x0 = x1 - strip_display_w
            y_center = (page_rect.height / 2) + y_offset
            y0 = y_center - strip_display_h / 2
            y1 = y_center + strip_display_h / 2

            stamp_rect = fitz.Rect(x0, y0, x1, y1)

            # Insert image with transparency
            page.insert_image(
                stamp_rect,
                stream=strip_bytes,
                overlay=True,
            )

        logger.info(
            "    Group %d: pages %d–%d (%d strips)",
            group_idx + 1, group_start + 1, group_end, group_size,
        )

    logger.info("  📍 Edge seal complete: %d groups applied", len(groups))


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
    from PIL import Image
    import io

    stamp_img = Image.open(str(stamp_path)).convert("RGBA")
    stamp_w, stamp_h = stamp_img.size
    aspect = stamp_h / stamp_w
    stamp_h_pt = stamp_width_pt * aspect

    # Convert to bytes
    buf = io.BytesIO()
    stamp_img.save(buf, format="PNG")
    stamp_bytes = buf.getvalue()

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
        "  🔏 Company stamp applied to last page (page %d) at center=(%.0f, %.0f), size=%.0fx%.0f pt",
        len(doc), cx, cy, stamp_width_pt, stamp_h_pt,
    )
