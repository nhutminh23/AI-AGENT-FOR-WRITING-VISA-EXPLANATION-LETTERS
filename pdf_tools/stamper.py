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


def _apply_edge_seal(
    doc: fitz.Document,
    seal_path: Path,
    seal_height_pt: float,
    margin_right_pt: float,
) -> None:
    """
    Slice the seal image into N vertical strips (one per page) and overlay
    each strip on the right edge of its corresponding page.

    The seal_height_pt controls the visual height (diameter) of the seal circle
    on each page. The strip width is auto-calculated so the seal appears as a
    continuous circle when pages are stacked.
    """
    from PIL import Image
    import io

    seal_img = Image.open(str(seal_path)).convert("RGBA")
    seal_w, seal_h = seal_img.size
    page_count = len(doc)

    # Use float division for perfectly even distribution
    strip_w_float = seal_w / page_count

    # Generate random offsets for natural look (seeded per document for consistency)
    import random
    rng = random.Random(page_count * 7 + seal_w)  # deterministic per doc structure

    for i, page in enumerate(doc):
        # Slice: left to right, one strip per page (float → int rounding for even splits)
        left = round(i * strip_w_float)
        right = round((i + 1) * strip_w_float)
        right = min(right, seal_w)

        strip = seal_img.crop((left, 0, right, seal_h))

        # Random rotation: ±6 degrees for natural hand-stamp look
        rotation_deg = rng.uniform(-6.0, 6.0)
        strip = strip.rotate(rotation_deg, expand=True, resample=Image.BICUBIC)

        # Convert strip to bytes
        buf = io.BytesIO()
        strip.save(buf, format="PNG")
        strip_bytes = buf.getvalue()

        # Calculate display size on page (use original strip dimensions for aspect ratio)
        strip_pixel_w = right - left
        strip_pixel_h = seal_h
        strip_aspect_wh = strip_pixel_w / max(strip_pixel_h, 1)  # width/height ratio
        strip_display_h = seal_height_pt
        strip_display_w = seal_height_pt * strip_aspect_wh

        # Random Y offset: ±15 points for natural variation
        y_offset = rng.uniform(-15.0, 15.0)

        # Position: right edge, vertically centered + random offset
        page_rect = page.rect
        x1 = page_rect.width - margin_right_pt
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

    logger.info("  📍 Edge seal applied to %d pages (height=%.0f pt, randomized)", page_count, seal_height_pt)


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
