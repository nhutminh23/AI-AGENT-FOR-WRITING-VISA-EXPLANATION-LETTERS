"""
File-operation routes for precheck: rename files, merge files.
"""
from __future__ import annotations

import logging
import os
import tempfile

from flask import Blueprint, jsonify, request

precheck_processor_bp = Blueprint("precheck_processor", __name__)

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}


@precheck_processor_bp.post("/api/processor/apply-rename")
def processor_apply_rename():
    """Rename files in-place within input/ subfolders. Converts images to PDF."""
    payload = request.get_json(force=True) or {}
    renames = payload.get("renames", [])

    if not renames:
        return jsonify({"error": "no_renames_provided"}), 400

    renamed = []
    errors = []

    for item in renames:
        old_path = item.get("path", "")
        new_name = item.get("new_name", "")

        if not old_path or not new_name:
            errors.append({"path": old_path, "error": "missing path or new_name"})
            continue

        if not os.path.isfile(old_path):
            errors.append({"path": old_path, "error": "file_not_found"})
            continue

        parent_dir = os.path.dirname(old_path)
        old_ext = os.path.splitext(old_path)[1].lower()
        new_ext = os.path.splitext(new_name)[1].lower()
        needs_convert = (old_ext in IMAGE_EXTS and new_ext == '.pdf')

        new_path = os.path.join(parent_dir, new_name)

        # Handle duplicate: add suffix
        if os.path.exists(new_path) and not os.path.samefile(old_path, new_path):
            base, ext = os.path.splitext(new_name)
            idx = 1
            while os.path.exists(new_path):
                new_path = os.path.join(parent_dir, f"{base}_({idx}){ext}")
                idx += 1

        try:
            if needs_convert:
                # Convert image → PDF using Pillow
                from PIL import Image
                img = Image.open(old_path)
                if img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')
                img.save(new_path, 'PDF', resolution=150)
                img.close()
                os.remove(old_path)  # Remove original image
            else:
                os.rename(old_path, new_path)
            renamed.append({
                "old": os.path.basename(old_path),
                "new": os.path.basename(new_path),
                "path": new_path,
                "converted": needs_convert,
            })
        except Exception as e:
            import logging; logging.exception("[Safe Log] Unhandled exception in precheck_processor.py: %s", e)
            errors.append({"path": old_path, "error": str(e)})

    return jsonify({
        "status": "done",
        "renamed_count": len(renamed),
        "error_count": len(errors),
        "renamed": renamed,
        "errors": errors,
    })


@precheck_processor_bp.post("/api/processor/merge-files")
def processor_merge_files():
    """Merge multiple files (images + PDFs) into a single PDF in user-specified order."""
    payload = request.get_json(force=True) or {}
    file_paths = payload.get("files", [])  # ordered list of file paths
    output_name = payload.get("output_name", "merged.pdf")

    if len(file_paths) < 2:
        return jsonify({"error": "need_at_least_2_files"}), 400

    from pypdf import PdfWriter, PdfReader
    from PIL import Image

    writer = PdfWriter()
    tmp_files = []

    try:
        for fpath in file_paths:
            if not os.path.isfile(fpath):
                return jsonify({"error": f"file_not_found: {fpath}"}), 404
            ext = os.path.splitext(fpath)[1].lower()
            if ext in IMAGE_EXTS:
                # Convert image to temp PDF page
                img = Image.open(fpath)
                if img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')
                tmp_pdf = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
                img.save(tmp_pdf.name, 'PDF', resolution=150)
                img.close()
                tmp_files.append(tmp_pdf.name)
                reader = PdfReader(tmp_pdf.name)
                for page in reader.pages:
                    writer.add_page(page)
            elif ext == '.pdf':
                reader = PdfReader(fpath)
                for page in reader.pages:
                    writer.add_page(page)
            else:
                return jsonify({"error": f"unsupported_format: {ext}"}), 400

        # Output path = same folder as first file
        parent_dir = os.path.dirname(file_paths[0])
        if not output_name.lower().endswith('.pdf'):
            output_name += '.pdf'
        output_path = os.path.join(parent_dir, output_name)

        # Handle duplicate
        if os.path.exists(output_path):
            base, ext = os.path.splitext(output_name)
            idx = 1
            while os.path.exists(os.path.join(parent_dir, f"{base}_({idx}){ext}")):
                idx += 1
            output_path = os.path.join(parent_dir, f"{base}_({idx}){ext}")

        with open(output_path, 'wb') as out:
            writer.write(out)

        # Delete original source files after successful merge
        deleted_files = []
        output_abs = os.path.abspath(output_path)
        for fpath in file_paths:
            src_abs = os.path.abspath(fpath)
            if src_abs == output_abs:
                continue  # don't delete the output file itself
            try:
                os.remove(fpath)
                deleted_files.append(os.path.basename(fpath))
            except Exception as del_err:
                logging.warning(f"[merge] Warning: could not delete {fpath}: {del_err}")

        return jsonify({
            "status": "done",
            "output_path": output_path,
            "output_name": os.path.basename(output_path),
            "total_pages": len(writer.pages),
            "merged_count": len(file_paths),
            "deleted_files": deleted_files,
        })
    except Exception as e:
        import logging; logging.exception("[Safe Log] Unhandled exception in precheck_processor.py: %s", e)
        return jsonify({"error": str(e)}), 500
    finally:
        for tf in tmp_files:
            try:
                os.remove(tf)
            except Exception as e:
                import logging; logging.exception("[Safe Log] Unhandled exception in precheck_processor.py: %s", e)
                logging.debug("Ignored error: %s", e)
