"""
Manual compression tool routes.

Use-case:
- User picks a local root folder.
- System scans recursively and finds files inside any "Final" subfolder.
- If file size exceeds max threshold (default 5MB), user can compress one or all.
- On successful compression under target, original file is replaced automatically.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF
from PIL import Image, ImageOps
from flask import Blueprint, jsonify, request

compress_tools_bp = Blueprint("compress_tools", __name__)
logger = logging.getLogger(__name__)

_DEFAULT_MAX_MB = 5.0
_MIN_MAX_MB = 0.1
_MAX_MAX_MB = 100.0

_SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
_SUPPORTED_COMPRESS_EXTS = {".pdf", *_SUPPORTED_IMAGE_EXTS}


def _safe_unlink(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


def _to_abs_existing_dir(path_text: str) -> Path:
    root = Path((path_text or "").strip().strip('"')).expanduser()
    try:
        root = root.resolve()
    except Exception:
        root = root.absolute()
    return root


def _parse_target_bytes(payload: Dict) -> Tuple[float, int]:
    raw = payload.get("max_mb", _DEFAULT_MAX_MB)
    try:
        max_mb = float(raw)
    except Exception as exc:
        raise ValueError("invalid_max_mb") from exc

    if not (_MIN_MAX_MB <= max_mb <= _MAX_MAX_MB):
        raise ValueError("invalid_max_mb")

    target_bytes = int(max_mb * 1024 * 1024)
    return max_mb, target_bytes


def _is_in_final_subtree(file_path: Path, root_path: Path) -> bool:
    try:
        rel = file_path.relative_to(root_path)
    except ValueError:
        return False

    # Any parent segment named Final counts.
    parent_parts = [part.lower() for part in rel.parts[:-1]]
    return "final" in parent_parts


def _is_supported_for_compression(file_path: Path) -> bool:
    return file_path.suffix.lower() in _SUPPORTED_COMPRESS_EXTS


def _serialize_file(file_path: Path, root_path: Path, target_bytes: int) -> Dict:
    size_bytes = file_path.stat().st_size
    rel_path = file_path.relative_to(root_path).as_posix()
    ext = file_path.suffix.lower()

    return {
        "name": file_path.name,
        "abs_path": str(file_path),
        "rel_path": rel_path,
        "ext": ext,
        "size_bytes": size_bytes,
        "size_mb": round(size_bytes / (1024 * 1024), 3),
        "over_limit": size_bytes > target_bytes,
        "compress_supported": ext in _SUPPORTED_COMPRESS_EXTS,
        "in_final_subtree": _is_in_final_subtree(file_path, root_path),
    }


def _scan_over_limit_files(root_path: Path, target_bytes: int) -> Dict:
    scanned_total = 0
    scanned_in_final = 0
    over_limit: List[Dict] = []

    for path in root_path.rglob("*"):
        if not path.is_file():
            continue

        scanned_total += 1

        try:
            in_final = _is_in_final_subtree(path, root_path)
            if not in_final:
                continue

            scanned_in_final += 1
            item = _serialize_file(path, root_path, target_bytes)
            if item["over_limit"]:
                over_limit.append(item)
        except Exception as exc:
            logger.warning("Skip file during scan (%s): %s", path, exc)

    over_limit.sort(key=lambda x: x.get("size_bytes", 0), reverse=True)

    return {
        "scanned_total": scanned_total,
        "scanned_in_final": scanned_in_final,
        "over_limit_count": len(over_limit),
        "over_limit_files": over_limit,
    }


def _temp_path_in_same_dir(original: Path, suffix: str) -> Path:
    fd, tmp = tempfile.mkstemp(prefix=f"{original.stem}_cmp_", suffix=suffix, dir=str(original.parent))
    os.close(fd)
    return Path(tmp)


def _pick_available_target_path(original: Path, new_ext: str) -> Path:
    new_ext = new_ext if new_ext.startswith(".") else f".{new_ext}"
    candidate = original.with_suffix(new_ext)
    if not candidate.exists() or candidate == original:
        return candidate

    for idx in range(1, 1000):
        alt = candidate.with_name(f"{candidate.stem}_compressed{idx}{new_ext}")
        if not alt.exists():
            return alt

    raise RuntimeError("Cannot allocate replacement filename")


def _replace_original_with_candidate(original: Path, candidate: Path, new_ext: str) -> Path:
    target = _pick_available_target_path(original, new_ext)
    backup = original.with_name(f"{original.name}.bak")

    _safe_unlink(backup)
    os.replace(original, backup)

    try:
        os.replace(candidate, target)
        _safe_unlink(backup)
        return target
    except Exception:
        if backup.exists():
            os.replace(backup, original)
        _safe_unlink(candidate)
        raise


def _consider_best_candidate(
    candidate_path: Path,
    candidate_ext: str,
    method: str,
    best: Optional[Dict],
) -> Optional[Dict]:
    try:
        size = candidate_path.stat().st_size
    except Exception:
        _safe_unlink(candidate_path)
        return best

    if best is None or size < best["size_bytes"]:
        if best and best.get("path"):
            _safe_unlink(best["path"])
        return {
            "path": candidate_path,
            "ext": candidate_ext,
            "size_bytes": size,
            "method": method,
        }

    _safe_unlink(candidate_path)
    return best


def _rebuild_pdf_as_images(src_pdf: Path, dst_pdf: Path, dpi: int, quality: int) -> None:
    src = fitz.open(src_pdf)
    out = fitz.open()

    try:
        for page in src:
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            img_bytes = buf.getvalue()

            new_page = out.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, stream=img_bytes)

        out.save(str(dst_pdf), garbage=4, deflate=True)
    finally:
        out.close()
        src.close()


def _compress_pdf_to_target(src_path: Path, target_bytes: int) -> Optional[Dict]:
    original_size = src_path.stat().st_size
    best: Optional[Dict] = None

    # Pass 1: lossless-style optimization
    lossless_candidate = _temp_path_in_same_dir(src_path, ".pdf")
    try:
        doc = fitz.open(src_path)
        doc.save(str(lossless_candidate), garbage=4, deflate=True, clean=True)
        doc.close()
        best = _consider_best_candidate(lossless_candidate, ".pdf", "pdf-lossless", best)
        if best and best["size_bytes"] <= target_bytes:
            return best
    except Exception as exc:
        _safe_unlink(lossless_candidate)
        logger.warning("PDF lossless optimization failed for %s: %s", src_path, exc)

    # Pass 2: rasterized compression for heavy PDFs
    presets = [
        (150, 80),
        (130, 72),
        (110, 66),
        (96, 60),
        (84, 54),
        (72, 50),
    ]

    for dpi, quality in presets:
        candidate = _temp_path_in_same_dir(src_path, ".pdf")
        try:
            _rebuild_pdf_as_images(src_path, candidate, dpi=dpi, quality=quality)
            best = _consider_best_candidate(candidate, ".pdf", f"pdf-raster-{dpi}dpi-q{quality}", best)
            if best and best["size_bytes"] <= target_bytes:
                break
        except Exception as exc:
            _safe_unlink(candidate)
            logger.warning("PDF raster compression failed for %s (%sdpi q%s): %s", src_path, dpi, quality, exc)

    if best and best["size_bytes"] < original_size:
        return best

    if best and best.get("path"):
        _safe_unlink(best["path"])
    return None


def _resize_for_scale(image: Image.Image, scale: float) -> Image.Image:
    if abs(scale - 1.0) < 1e-6:
        return image.copy()

    w, h = image.size
    nw = max(1, int(w * scale))
    nh = max(1, int(h * scale))
    return image.resize((nw, nh), Image.Resampling.LANCZOS)


def _compress_image_to_target(src_path: Path, target_bytes: int) -> Optional[Dict]:
    ext = src_path.suffix.lower()
    original_size = src_path.stat().st_size

    with Image.open(src_path) as raw:
        base = ImageOps.exif_transpose(raw).copy()

    has_alpha = base.mode in ("RGBA", "LA") or ("transparency" in base.info)
    scales = [1.0, 0.92, 0.84, 0.76, 0.68, 0.60]
    best: Optional[Dict] = None

    def consider_and_break(candidate: Path, candidate_ext: str, method: str) -> bool:
        nonlocal best
        best = _consider_best_candidate(candidate, candidate_ext, method, best)
        return bool(best and best["size_bytes"] <= target_bytes)

    # JPEG / WEBP path
    if ext in {".jpg", ".jpeg", ".webp"}:
        quality_steps = [85, 75, 68, 60, 52, 45, 38]
        fmt = "WEBP" if ext == ".webp" else "JPEG"

        for scale in scales:
            scaled = _resize_for_scale(base, scale)
            if fmt == "JPEG" and scaled.mode not in ("RGB", "L"):
                scaled = scaled.convert("RGB")
            for q in quality_steps:
                suffix = ext if ext != ".jpeg" else ".jpg"
                candidate = _temp_path_in_same_dir(src_path, suffix)
                try:
                    if fmt == "WEBP":
                        scaled.save(candidate, format=fmt, quality=q, method=6)
                    else:
                        scaled.save(candidate, format=fmt, quality=q, optimize=True, progressive=True)
                    if consider_and_break(candidate, suffix, f"img-{fmt.lower()}-scale{scale:.2f}-q{q}"):
                        return best
                except Exception:
                    _safe_unlink(candidate)

    # PNG path: first keep PNG via quantization, then fallback to JPEG if no alpha
    elif ext == ".png":
        color_steps = [256, 128, 64, 32]
        for scale in scales:
            scaled = _resize_for_scale(base, scale)
            for colors in color_steps:
                candidate = _temp_path_in_same_dir(src_path, ".png")
                try:
                    quantized = scaled.convert("P", palette=Image.Palette.ADAPTIVE, colors=colors)
                    quantized.save(candidate, format="PNG", optimize=True, compress_level=9)
                    if consider_and_break(candidate, ".png", f"img-png-scale{scale:.2f}-colors{colors}"):
                        return best
                except Exception:
                    _safe_unlink(candidate)

        if not has_alpha:
            quality_steps = [82, 72, 64, 56, 48, 40]
            for scale in scales:
                scaled = _resize_for_scale(base, scale).convert("RGB")
                for q in quality_steps:
                    candidate = _temp_path_in_same_dir(src_path, ".jpg")
                    try:
                        scaled.save(candidate, format="JPEG", quality=q, optimize=True, progressive=True)
                        if consider_and_break(candidate, ".jpg", f"img-png2jpg-scale{scale:.2f}-q{q}"):
                            return best
                    except Exception:
                        _safe_unlink(candidate)

    # Other bitmap types -> JPEG
    else:
        quality_steps = [82, 72, 64, 56, 48, 40]
        rgb = base.convert("RGB")
        for scale in scales:
            scaled = _resize_for_scale(rgb, scale)
            for q in quality_steps:
                candidate = _temp_path_in_same_dir(src_path, ".jpg")
                try:
                    scaled.save(candidate, format="JPEG", quality=q, optimize=True, progressive=True)
                    if consider_and_break(candidate, ".jpg", f"img-tojpg-scale{scale:.2f}-q{q}"):
                        return best
                except Exception:
                    _safe_unlink(candidate)

    if best and best["size_bytes"] < original_size:
        return best

    if best and best.get("path"):
        _safe_unlink(best["path"])
    return None


def _compress_single_file(file_path: Path, root_path: Optional[Path], target_bytes: int) -> Dict:
    if not file_path.exists() or not file_path.is_file():
        return {
            "status": "failed",
            "detail": "file_not_found",
            "file_path": str(file_path),
        }

    ext = file_path.suffix.lower()
    old_size = file_path.stat().st_size

    rel_path = None
    if root_path:
        try:
            rel_path = file_path.relative_to(root_path).as_posix()
        except ValueError:
            rel_path = None

    if old_size <= target_bytes:
        return {
            "status": "skipped",
            "detail": "already_under_limit",
            "file_path": str(file_path),
            "rel_path": rel_path,
            "old_size_bytes": old_size,
            "new_size_bytes": old_size,
            "method": "none",
        }

    if ext not in _SUPPORTED_COMPRESS_EXTS:
        return {
            "status": "failed",
            "detail": f"unsupported_type:{ext}",
            "file_path": str(file_path),
            "rel_path": rel_path,
            "old_size_bytes": old_size,
            "new_size_bytes": old_size,
            "method": "unsupported",
        }

    best = None
    if ext == ".pdf":
        best = _compress_pdf_to_target(file_path, target_bytes)
    else:
        best = _compress_image_to_target(file_path, target_bytes)

    if not best:
        return {
            "status": "failed",
            "detail": "unable_to_reduce_size",
            "file_path": str(file_path),
            "rel_path": rel_path,
            "old_size_bytes": old_size,
            "new_size_bytes": old_size,
            "method": "none",
        }

    if best["size_bytes"] > target_bytes:
        _safe_unlink(best["path"])
        return {
            "status": "failed",
            "detail": "cannot_reach_target_size",
            "file_path": str(file_path),
            "rel_path": rel_path,
            "old_size_bytes": old_size,
            "new_size_bytes": old_size,
            "method": best.get("method", "none"),
        }

    try:
        replaced_path = _replace_original_with_candidate(file_path, best["path"], best["ext"])
        new_size = replaced_path.stat().st_size
        final_rel_path = rel_path
        if root_path:
            try:
                final_rel_path = replaced_path.relative_to(root_path).as_posix()
            except ValueError:
                pass

        return {
            "status": "done",
            "detail": "compressed_and_replaced",
            "file_path": str(file_path),
            "replaced_path": str(replaced_path),
            "rel_path": final_rel_path,
            "old_size_bytes": old_size,
            "new_size_bytes": new_size,
            "method": best.get("method", "unknown"),
        }
    except Exception as exc:
        logger.exception("Failed replacing compressed file %s: %s", file_path, exc)
        return {
            "status": "failed",
            "detail": f"replace_failed:{exc}",
            "file_path": str(file_path),
            "rel_path": rel_path,
            "old_size_bytes": old_size,
            "new_size_bytes": old_size,
            "method": best.get("method", "unknown"),
        }


@compress_tools_bp.post("/api/compress/pick-folder")
def pick_folder_dialog():
    """Open a native folder picker and return selected path."""
    # Script with explicit UTF-8 stdout to handle Vietnamese folder names on Windows
    script = """
import sys
import os

# Force UTF-8 output on Windows (critical for Vietnamese paths)
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

import tkinter as tk
from tkinter import filedialog

root = tk.Tk()
root.withdraw()

# Force the dialog to appear on top of all windows
root.attributes("-topmost", True)
root.lift()
root.focus_force()
root.update()

path = filedialog.askdirectory(
    title="Chọn thư mục",
    parent=root,
)

if path:
    # Normalize path separators for consistency
    path = os.path.normpath(path)
    print(path, flush=True)
else:
    print("", flush=True)

root.destroy()
"""

    # Build env with forced UTF-8
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    # Windows-specific: suppress console window flash
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW

    try:
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            check=False,
            env=env,
            creationflags=creationflags,
        )
    except Exception as exc:
        logger.error("Folder picker subprocess failed: %s", exc)
        return jsonify({"error": "folder_picker_failed", "detail": str(exc)}), 500

    # Log stderr for debugging if any
    if proc.stderr and proc.stderr.strip():
        logger.warning("Folder picker stderr: %s", proc.stderr.strip())

    picked = (proc.stdout or "").strip()
    if not picked:
        # Check if the process actually failed vs user cancelled
        if proc.returncode != 0:
            detail = (proc.stderr or "").strip() or f"Process exited with code {proc.returncode}"
            logger.error("Folder picker process error: %s", detail)
            return jsonify({"error": "folder_picker_error", "detail": detail}), 500
        return jsonify({"status": "cancelled", "folder_path": ""})

    # Verify the path exists
    resolved = Path(picked)
    if not resolved.is_dir():
        logger.warning("Picked path does not exist: %s", picked)
        return jsonify({"status": "ok", "folder_path": picked, "warning": "path_not_found"})

    return jsonify({"status": "ok", "folder_path": str(resolved)})


@compress_tools_bp.post("/api/compress/scan")
def scan_folder_for_compression():
    payload = request.get_json(force=True) or {}

    try:
        max_mb, target_bytes = _parse_target_bytes(payload)
    except ValueError:
        return jsonify({"error": "invalid_max_mb", "detail": "max_mb must be between 0.1 and 100"}), 400

    root_path = _to_abs_existing_dir(payload.get("root_path", ""))
    if not root_path.is_dir():
        return jsonify({"error": "folder_not_found", "detail": str(root_path)}), 404

    result = _scan_over_limit_files(root_path, target_bytes)
    return jsonify(
        {
            "status": "ok",
            "root_path": str(root_path),
            "max_mb": max_mb,
            "max_bytes": target_bytes,
            **result,
        }
    )


@compress_tools_bp.post("/api/compress/file")
def compress_one_file():
    payload = request.get_json(force=True) or {}

    file_text = (payload.get("file_path") or "").strip()
    if not file_text:
        return jsonify({"error": "missing_file_path"}), 400

    try:
        max_mb, target_bytes = _parse_target_bytes(payload)
    except ValueError:
        return jsonify({"error": "invalid_max_mb", "detail": "max_mb must be between 0.1 and 100"}), 400

    file_path = Path(file_text).expanduser()
    if not file_path.exists() or not file_path.is_file():
        return jsonify({"status": "failed", "detail": "file_not_found", "file_path": str(file_path)}), 404

    root_hint = payload.get("root_path")
    root_path = _to_abs_existing_dir(root_hint) if root_hint else None
    if root_path and not root_path.exists():
        root_path = None

    result = _compress_single_file(file_path, root_path, target_bytes)
    result["target_bytes"] = target_bytes
    result["max_mb"] = max_mb

    code = 200 if result["status"] != "failed" else 400
    return jsonify(result), code


@compress_tools_bp.post("/api/compress/all")
def compress_all_files_in_final():
    payload = request.get_json(force=True) or {}

    try:
        max_mb, target_bytes = _parse_target_bytes(payload)
    except ValueError:
        return jsonify({"error": "invalid_max_mb", "detail": "max_mb must be between 0.1 and 100"}), 400

    root_path = _to_abs_existing_dir(payload.get("root_path", ""))
    if not root_path.is_dir():
        return jsonify({"error": "folder_not_found", "detail": str(root_path)}), 404

    scan_result = _scan_over_limit_files(root_path, target_bytes)
    over_files = scan_result["over_limit_files"]

    results = []
    success_count = 0
    failed_count = 0
    skipped_count = 0

    for item in over_files:
        abs_path = Path(item.get("abs_path", ""))
        one = _compress_single_file(abs_path, root_path, target_bytes)
        results.append(one)

        if one["status"] == "done":
            success_count += 1
        elif one["status"] == "skipped":
            skipped_count += 1
        else:
            failed_count += 1

    return jsonify(
        {
            "status": "done",
            "root_path": str(root_path),
            "max_mb": max_mb,
            "target_bytes": target_bytes,
            "total": len(over_files),
            "success_count": success_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "results": results,
        }
    )
