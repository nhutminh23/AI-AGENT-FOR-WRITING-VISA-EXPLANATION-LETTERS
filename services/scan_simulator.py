"""
Scan Simulator — convert clean PDF to realistic "scanned" PDF.

Pipeline: PDF → Page images → Add effects (noise, tilt, grayscale, blur) → Reassemble PDF

Uses PyMuPDF (fitz) for PDF→image and image→PDF, Pillow for image effects.
"""
from __future__ import annotations

import io
import logging
import random
from typing import Optional

import fitz  # PyMuPDF
from PIL import Image, ImageFilter, ImageEnhance

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Default presets
# --------------------------------------------------------------------------
DEFAULT_DPI = 200          # render resolution (balance: quality vs speed)
DEFAULT_NOISE_LEVEL = 12   # grain intensity (0=none, 30=heavy)
DEFAULT_TILT_MAX = 0.8     # max random rotation degrees
DEFAULT_BLUR_RADIUS = 0.4  # slight blur to mimic optics
DEFAULT_JPEG_QUALITY = 82  # compression quality (lower = more artifacts)
DEFAULT_BRIGHTNESS = 0.97  # slight dimming
DEFAULT_CONTRAST = 1.05    # slight contrast boost


def simulate_scan(
    pdf_bytes: bytes,
    *,
    dpi: int = DEFAULT_DPI,
    noise_level: int = DEFAULT_NOISE_LEVEL,
    tilt_max: float = DEFAULT_TILT_MAX,
    blur_radius: float = DEFAULT_BLUR_RADIUS,
    jpeg_quality: int = DEFAULT_JPEG_QUALITY,
    grayscale: bool = True,
    preserve_signature_color: bool = False,
) -> bytes:
    """
    Convert a clean PDF to a realistic scanned PDF.

    Args:
        pdf_bytes: Raw PDF file bytes.
        dpi: Render resolution.
        noise_level: Grain intensity (0-30).
        tilt_max: Maximum random tilt in degrees.
        blur_radius: Gaussian blur radius.
        jpeg_quality: JPEG compression quality.
        grayscale: Convert to grayscale (typical for scans).
        preserve_signature_color: If True, preserve blue/red ink colors
            by keeping relevant pixels in color while rest is grayscale.

    Returns:
        Scanned PDF as bytes.
    """
    src_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    out_doc = fitz.open()

    for page_idx in range(len(src_doc)):
        page = src_doc[page_idx]

        # 1) Render page to image at specified DPI
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

        # 2) Apply scan effects
        img = _apply_scan_effects(
            img,
            noise_level=noise_level,
            tilt_max=tilt_max,
            blur_radius=blur_radius,
            jpeg_quality=jpeg_quality,
            grayscale=grayscale,
            preserve_signature_color=preserve_signature_color,
        )

        # 3) Convert processed image back to PDF page
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG", quality=jpeg_quality)
        img_bytes.seek(0)

        # Create new page with same dimensions as original
        rect = page.rect
        new_page = out_doc.new_page(width=rect.width, height=rect.height)
        new_page.insert_image(rect, stream=img_bytes.read())

    # Save output
    result = io.BytesIO()
    out_doc.save(result)
    out_doc.close()
    src_doc.close()
    result.seek(0)
    return result.read()


def _apply_scan_effects(
    img: Image.Image,
    *,
    noise_level: int,
    tilt_max: float,
    blur_radius: float,
    jpeg_quality: int,
    grayscale: bool,
    preserve_signature_color: bool,
) -> Image.Image:
    """Apply realistic scanner effects to an image."""

    # --- Grayscale conversion ---
    if grayscale:
        if preserve_signature_color:
            img = _selective_grayscale(img)
        else:
            img = img.convert("L").convert("RGB")

    # --- Brightness / Contrast ---
    img = ImageEnhance.Brightness(img).enhance(DEFAULT_BRIGHTNESS)
    img = ImageEnhance.Contrast(img).enhance(DEFAULT_CONTRAST)

    # --- Random tilt ---
    if tilt_max > 0:
        angle = random.uniform(-tilt_max, tilt_max)
        # Use white fill for the background after rotation
        img = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=(255, 255, 255))

    # --- Noise (grain) ---
    if noise_level > 0:
        img = _add_noise(img, noise_level)

    # --- Slight blur (scanner optics) ---
    if blur_radius > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    # --- Edge shadow (vignette-like darkening at margins) ---
    img = _add_edge_shadow(img)

    return img


def _add_noise(img: Image.Image, level: int) -> Image.Image:
    """Add random grain noise to simulate scanner CCD noise."""
    import numpy as np

    arr = np.array(img, dtype=np.int16)
    noise = np.random.randint(-level, level + 1, arr.shape, dtype=np.int16)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def _add_edge_shadow(img: Image.Image, shadow_width: int = 15, darkness: float = 0.85) -> Image.Image:
    """Add subtle darkening at edges to mimic scanner lid shadow."""
    import numpy as np

    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]

    # Create gradient mask
    mask = np.ones((h, w), dtype=np.float32)

    for i in range(shadow_width):
        factor = darkness + (1.0 - darkness) * (i / shadow_width)
        # Top
        mask[i, :] = min(mask[i, :].min(), factor)
        # Bottom
        mask[h - 1 - i, :] = min(mask[h - 1 - i, :].min(), factor)
        # Left
        mask[:, i] = np.minimum(mask[:, i], factor)
        # Right
        mask[:, w - 1 - i] = np.minimum(mask[:, w - 1 - i], factor)

    if len(arr.shape) == 3:
        mask = mask[:, :, np.newaxis]

    arr = np.clip(arr * mask, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def _selective_grayscale(img: Image.Image) -> Image.Image:
    """
    Convert image to grayscale BUT keep pixels that look like
    blue or red ink (signature colors) in their original color.
    """
    import numpy as np

    arr = np.array(img)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    # Detect "colored" pixels (blue or red ink signatures)
    # Blue ink: high blue, low red/green
    is_blue = (b > 100) & (b > r + 40) & (b > g + 40)
    # Red ink: high red, low green/blue
    is_red = (r > 100) & (r > g + 40) & (r > b + 40)
    # Dark blue/navy ink
    is_dark_blue = (b > 60) & (b > r + 20) & (b > g + 20) & (r < 120)

    keep_color = is_blue | is_red | is_dark_blue

    # Convert to grayscale
    gray = np.dot(arr[:, :, :3], [0.299, 0.587, 0.114]).astype(np.uint8)
    gray_rgb = np.stack([gray, gray, gray], axis=-1)

    # Merge: keep colored pixels, replace rest with grayscale
    result = np.where(keep_color[:, :, np.newaxis], arr, gray_rgb)
    return Image.fromarray(result.astype(np.uint8))
