"""
PDF tools routes: merge, rename, extract objects, edit.
"""
from __future__ import annotations

import io
import logging
import os
import re
from typing import List

from flask import Blueprint, jsonify, request, send_file

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from pypdf import PdfReader, PdfWriter

from core.helpers import get_text_model
from config import Config
import database as db

from routes.pipeline_helpers import (
    _safe_join,
    _is_quota_error,
    _pdf_merge_sanitize_name,
    _pdf_merge_pick_unique,
)

# Base directory (project root, one level up from routes/)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


pipeline_pdf_bp = Blueprint("pipeline_pdf", __name__)

@pipeline_pdf_bp.route("/api/pdf/merge-upload", methods=["POST"])
def merge_pdf_upload():
    """Merge PDFs uploaded from user's computer. Order of form fields = page order."""
    output_dir = Config.PDF_OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    output_name = (request.form.get("output_name") or "").strip()
    if not output_name:
        return jsonify({"error": "missing_output_name"}), 400

    files = request.files.getlist("file")
    if not files:
        return jsonify({"error": "missing_files"}), 400

    writer = PdfWriter()
    total_pages = 0
    used_names: List[str] = []

    for f in files:
        if not f or not getattr(f, "filename", None):
            continue
        if not str(f.filename).lower().endswith(".pdf"):
            continue
        try:
            reader = PdfReader(f.stream)
        except Exception as e:
            logging.exception("[Safe Log] Unhandled exception in pipeline_pdf.py: %s", e)
            logging.debug("Skipped: %s", e)
            continue
        for page in reader.pages:
            writer.add_page(page)
            total_pages += 1
        used_names.append(f.filename)

    if not used_names:
        return jsonify({"error": "no_valid_pdfs"}), 400

    safe_name = _pdf_merge_sanitize_name(output_name, "MERGED")
    out_path = _pdf_merge_pick_unique(output_dir, safe_name, ".pdf")
    try:
        with open(out_path, "wb") as fp:
            writer.write(fp)
    except Exception as exc:
        logging.exception("[Safe Log] Unhandled exception in pipeline_pdf.py: %s", exc)
        return jsonify({"error": "write_failed", "detail": str(exc)}), 500

    # Save to database
    file_size = os.path.getsize(out_path)
    final_filename = os.path.basename(out_path)
    record = db.save_merged_pdf(
        filename=final_filename,
        file_path=os.path.abspath(out_path),
        source_files=used_names,
        total_pages=total_pages,
        file_size=file_size,
    )

    return jsonify(
        {
            "status": "done",
            "id": record["id"],
            "output_dir": output_dir,
            "files": used_names,
            "file_count": len(used_names),
            "total_pages": total_pages,
            "file_size": file_size,
            "output_file": final_filename,
        }
    )


@pipeline_pdf_bp.route("/api/pdf/merged", methods=["GET"])
def list_merged_pdfs():
    """List all merged PDF records."""
    records = db.list_merged_pdfs()
    return jsonify({"merged_pdfs": records})


@pipeline_pdf_bp.route("/api/pdf/merged/<int:record_id>/view", methods=["GET"])
def view_merged_pdf(record_id):
    """View a merged PDF inline in browser (new tab)."""
    record = db.get_merged_pdf(record_id)
    if not record:
        return jsonify({"error": "not_found"}), 404
    fpath = record["file_path"]
    if not os.path.isfile(fpath):
        return jsonify({"error": "file_missing"}), 404
    return send_file(fpath, as_attachment=False, mimetype="application/pdf")


@pipeline_pdf_bp.route("/api/pdf/merged/<int:record_id>/download", methods=["GET"])
def download_merged_pdf(record_id):
    """Download a merged PDF file."""
    record = db.get_merged_pdf(record_id)
    if not record:
        return jsonify({"error": "not_found"}), 404
    fpath = record["file_path"]
    if not os.path.isfile(fpath):
        return jsonify({"error": "file_missing"}), 404
    return send_file(fpath, as_attachment=True, download_name=record["filename"])


@pipeline_pdf_bp.route("/api/pdf/merged/<int:record_id>", methods=["DELETE"])
def delete_merged_pdf(record_id):
    """Delete a single merged PDF (DB + disk)."""
    ok = db.delete_merged_pdf(record_id)
    if not ok:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"status": "deleted"})


@pipeline_pdf_bp.route("/api/pdf/merged", methods=["DELETE"])
def delete_all_merged_pdfs():
    """Delete all merged PDFs (DB + disk)."""
    count = db.delete_all_merged_pdfs()
    return jsonify({"status": "deleted", "deleted_count": count})


@pipeline_pdf_bp.route("/api/pdf/merged/download-zip", methods=["GET"])
def download_all_merged_zip():
    """Download all merged PDFs as a single ZIP file."""
    import zipfile
    records = db.list_merged_pdfs()
    if not records:
        return jsonify({"error": "no_files"}), 404

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in records:
            fpath = r["file_path"]
            if os.path.isfile(fpath):
                zf.write(fpath, r["filename"])
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="merged_pdfs.zip",
                     mimetype="application/zip")


@pipeline_pdf_bp.route("/api/pdf/merge", methods=["POST"])
def merge_pdf():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", Config.INPUT_DIR)
    output_dir = payload.get("output_dir", Config.PDF_OUTPUT_DIR)
    files = payload.get("files") or []
    output_name = (payload.get("output_name") or "").strip()

    if not os.path.isdir(input_dir):
        return jsonify({"error": "folder_not_found", "input_dir": input_dir}), 404
    os.makedirs(output_dir, exist_ok=True)

    if not isinstance(files, list) or not files:
        return jsonify({"error": "missing_files"}), 400
    if not output_name:
        return jsonify({"error": "missing_output_name"}), 400

    writer = PdfWriter()
    total_pages = 0
    used_files: list[str] = []

    for rel in files:
        try:
            src_path = _safe_join(input_dir, rel)
        except ValueError:
            continue
        if not os.path.exists(src_path):
            continue
        if os.path.splitext(src_path)[1].lower() != ".pdf":
            continue
        try:
            reader = PdfReader(src_path)
        except Exception as e:
            logging.exception("[Safe Log] Unhandled exception in pipeline_pdf.py: %s", e)
            logging.debug("Skipped: %s", e)
            continue
        for page in reader.pages:
            writer.add_page(page)
            total_pages += 1
        used_files.append(os.path.relpath(src_path, input_dir).replace("\\", "/"))

    if not used_files:
        return jsonify({"error": "no_valid_pdfs"}), 400

    safe_name = _pdf_merge_sanitize_name(output_name, "MERGED")
    out_path = _pdf_merge_pick_unique(output_dir, safe_name, ".pdf")
    try:
        with open(out_path, "wb") as f:
            writer.write(f)
    except Exception as exc:
        logging.exception("[Safe Log] Unhandled exception in pipeline_pdf.py: %s", exc)
        return jsonify({"error": "write_failed", "detail": str(exc)}), 500

    return jsonify(
        {
            "status": "done",
            "input_dir": input_dir,
            "output_dir": output_dir,
            "files": used_files,
            "file_count": len(used_files),
            "total_pages": total_pages,
            "output_file": os.path.relpath(out_path, output_dir).replace("\\", "/"),
        }
    )


@pipeline_pdf_bp.route("/api/pdf/rename", methods=["POST"])
def rename_pdf():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", Config.INPUT_DIR)
    source = (payload.get("source") or "").strip()
    prefix = (payload.get("prefix") or "").strip()
    doc_type = (payload.get("doc_type") or "").strip()

    if not os.path.isdir(input_dir):
        return jsonify({"error": "folder_not_found", "input_dir": input_dir}), 404
    if not source:
        return jsonify({"error": "missing_source"}), 400
    if not prefix or not doc_type:
        return jsonify({"error": "missing_name_parts"}), 400

    try:
        src_path = _safe_join(input_dir, source)
    except ValueError:
        return jsonify({"error": "invalid_source"}), 400

    if not os.path.exists(src_path):
        return jsonify({"error": "source_not_found"}), 404
    if os.path.splitext(src_path)[1].lower() != ".pdf":
        return jsonify({"error": "source_not_pdf"}), 400

    def _sanitize_part(value: str) -> str:
        text = (value or "").strip()
        text = re.sub(r"[\\/:*?\"<>|]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _pick_unique_name(dest_dir: str, stem: str, ext: str) -> str:
        candidate = os.path.join(dest_dir, f"{stem}{ext}")
        idx = 1
        while os.path.exists(candidate):
            candidate = os.path.join(dest_dir, f"{stem} ({idx}){ext}")
            idx += 1
        return candidate

    prefix_clean = _sanitize_part(prefix)
    doc_type_clean = _sanitize_part(doc_type)
    if not prefix_clean or not doc_type_clean:
        return jsonify({"error": "invalid_name"}), 400

    stem = f"{prefix_clean} - {doc_type_clean}"
    dest_dir = os.path.dirname(src_path)
    dest_path = _pick_unique_name(dest_dir, stem, ".pdf")

    try:
        os.rename(src_path, dest_path)
    except Exception as exc:
        logging.exception("[Safe Log] Unhandled exception in pipeline_pdf.py: %s", exc)
        return jsonify({"error": "rename_failed", "detail": str(exc)}), 500

    return jsonify(
        {
            "status": "done",
            "input_dir": input_dir,
            "source": os.path.relpath(src_path, input_dir).replace("\\", "/"),
            "new_name": os.path.basename(dest_path),
            "new_rel_path": os.path.relpath(dest_path, input_dir).replace("\\", "/"),
        }
    )


@pipeline_pdf_bp.route("/api/pdf/rename_suggest_name", methods=["POST"])
def pdf_rename_suggest_name():
    payload = request.get_json(force=True) or {}
    input_text = (payload.get("input_text") or "").strip()
    model = payload.get("model") or get_text_model()  # text analysis

    if not input_text:
        return jsonify({"error": "missing_input_text"}), 400

    llm = ChatOpenAI(model=model, temperature=0)

    system = SystemMessage(
        content=(
            "Bạn là trợ lý đặt tên tài liệu cho hồ sơ visa. "
            "Nhiệm vụ: chuyển mô tả tiếng Việt về loại giấy tờ sang 1 cụm tiếng Anh rất ngắn gọn "
            "(tối đa khoảng 3–4 từ), ALL CAPS, phù hợp đặt tên file. "
            "Ví dụ: 'giấy khai sinh' -> 'BIRTH CERT'; 'giấy kết hôn' -> 'MARRIAGE CERT'. "
            "Chỉ trả về đúng cụm tiếng Anh, không giải thích thêm."
        )
    )
    human = HumanMessage(
        content=f"Người dùng nhập: \"{input_text}\".\nHãy trả về cụm tiếng Anh ngắn gọn để đặt tên file."
    )

    try:
        result = llm.invoke([system, human])
    except Exception as exc:
        logging.exception("[Safe Log] Unhandled exception in pipeline_pdf.py: %s", exc)
        if _is_quota_error(exc):
            return jsonify({"error": "quota_exceeded", "detail": "⚠️ Đã hết quota OpenAI API! Vui lòng kiểm tra billing."}), 429
        return jsonify({"error": "llm_error", "detail": str(exc)}), 500

    suggested = (getattr(result, "content", "") or "").strip().upper()
    suggested = re.sub(r"[^A-Z0-9\s]", " ", suggested)
    suggested = re.sub(r"\s+", " ", suggested).strip()

    if not suggested:
        return jsonify({"error": "empty_suggestion"}), 500

    return jsonify({"suggested_name": suggested})


@pipeline_pdf_bp.route("/api/pdf/extract-objects", methods=["POST"])
def extract_pdf_objects():
    """Extract text blocks from PDF with bbox, font, size, color info."""
    import fitz

    if "file" not in request.files:
        return jsonify({"error": "missing_file"}), 400
    f = request.files["file"]
    if not f.filename.lower().endswith(".pdf"):
        return jsonify({"error": "not_a_pdf"}), 400

    try:
        pdf_bytes = f.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        for page_idx, page in enumerate(doc):
            rect = page.rect
            page_info = {
                "pageIndex": page_idx,
                "width": rect.width,
                "height": rect.height,
                "blocks": [],
            }
            text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:  # text block only
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text:
                            continue
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        c = span.get("color", 0)
                        if isinstance(c, int):
                            color_hex = "#{:06x}".format(c)
                        else:
                            color_hex = "#000000"
                        flags = span.get("flags", 0)
                        page_info["blocks"].append({
                            "text": text,
                            "bbox": list(bbox),
                            "font": span.get("font", ""),
                            "fontSize": round(span.get("size", 12), 1),
                            "color": color_hex,
                            "bold": bool(flags & 16),
                            "italic": bool(flags & 2),
                        })
            pages.append(page_info)
        doc.close()
        return jsonify({"pages": pages})
    except Exception as exc:
        logging.exception("[Safe Log] Unhandled exception in pipeline_pdf.py: %s", exc)
        return jsonify({"error": str(exc)}), 500


# Mapping common PDF font names to PyMuPDF built-in fonts
_FONT_MAP = {
    "helv": "helv", "helvetica": "helv", "arial": "helv",
    "arialmt": "helv", "arial-boldmt": "hebo",
    "tiro": "tiro", "times": "tiro", "timesnewroman": "tiro",
    "timesnewromanpsmt": "tiro", "timesnewromanps-boldmt": "tibo",
    "cour": "cour", "courier": "cour", "couriernew": "cour",
    "couriernewpsmt": "cour",
    "symbol": "symb", "zapfdingbats": "zadb",
}

def _resolve_font(pdf_font_name, is_bold=False, is_italic=False):
    """Map a PDF font name to a PyMuPDF built-in font name, preserving bold/italic."""
    if not pdf_font_name:
        pdf_font_name = "helv"
    key = pdf_font_name.lower().replace(" ", "").replace("-", "")

    # Detect bold/italic from font name itself
    name_bold = "bold" in key or is_bold
    name_italic = ("italic" in key or "oblique" in key) or is_italic

    # Find base font family
    base = "helv"  # default
    if key in _FONT_MAP:
        base = _FONT_MAP[key]
    else:
        for k, v in _FONT_MAP.items():
            if k in key:
                base = v
                break

    # Pick bold/italic variant based on base font family
    # Helvetica family: helv, hebo, heit, hebi
    # Times family: tiro, tibo, tiit, tibi
    # Courier family: cour, cobo, coit, cobi
    family_variants = {
        "helv": {"b": "hebo", "i": "heit", "bi": "hebi"},
        "hebo": {"b": "hebo", "i": "hebi", "bi": "hebi"},
        "heit": {"b": "hebi", "i": "heit", "bi": "hebi"},
        "hebi": {"b": "hebi", "i": "hebi", "bi": "hebi"},
        "tiro": {"b": "tibo", "i": "tiit", "bi": "tibi"},
        "tibo": {"b": "tibo", "i": "tibi", "bi": "tibi"},
        "tiit": {"b": "tibi", "i": "tiit", "bi": "tibi"},
        "tibi": {"b": "tibi", "i": "tibi", "bi": "tibi"},
        "cour": {"b": "cobo", "i": "coit", "bi": "cobi"},
        "cobo": {"b": "cobo", "i": "cobi", "bi": "cobi"},
        "coit": {"b": "cobi", "i": "coit", "bi": "cobi"},
        "cobi": {"b": "cobi", "i": "cobi", "bi": "cobi"},
    }

    if name_bold and name_italic:
        return family_variants.get(base, {}).get("bi", base)
    if name_bold:
        return family_variants.get(base, {}).get("b", base)
    if name_italic:
        return family_variants.get(base, {}).get("i", base)
    return base


@pipeline_pdf_bp.route("/api/pdf/edit", methods=["POST"])
def edit_pdf():
    """Find & replace text in an uploaded PDF using PyMuPDF."""
    import fitz
    import json as _json
    import io

    if "file" not in request.files:
        return jsonify({"error": "missing_file"}), 400
    f = request.files["file"]
    if not f.filename.lower().endswith(".pdf"):
        return jsonify({"error": "not_a_pdf"}), 400

    raw_replacements = request.form.get("replacements", "[]")
    try:
        replacements = _json.loads(raw_replacements)
    except Exception as e:
        logging.exception("[Safe Log] Unhandled exception in pipeline_pdf.py: %s", e)
        return jsonify({"error": "invalid_replacements_json"}), 400

    if not replacements or not isinstance(replacements, list):
        return jsonify({"error": "empty_replacements"}), 400

    try:
        pdf_bytes = f.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        for pair in replacements:
            find_text = pair.get("find", "")
            replace_text = pair.get("replace", "")
            if not find_text:
                continue

            # Use fontname from request if provided, else detect from PDF
            req_font = pair.get("fontname", "")

            for page in doc:
                hits = page.search_for(find_text)
                if not hits:
                    continue

                # Detect font info from the first hit's span
                span_font = req_font or "helv"
                span_color = (0, 0, 0)
                span_size = 0
                span_bold = False
                span_italic = False
                try:
                    text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
                    for block in text_dict.get("blocks", []):
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                if find_text in span.get("text", ""):
                                    if not req_font:
                                        span_font = span.get("font", "helv")
                                    span_size = span.get("size", 0)
                                    sflags = span.get("flags", 0)
                                    span_bold = bool(sflags & 16)
                                    span_italic = bool(sflags & 2)
                                    c = span.get("color", 0)
                                    if isinstance(c, int):
                                        span_color = (
                                            ((c >> 16) & 0xFF) / 255.0,
                                            ((c >> 8) & 0xFF) / 255.0,
                                            (c & 0xFF) / 255.0,
                                        )
                                    raise StopIteration
                except StopIteration:
                    pass

                # Try to extract & register the actual embedded font from the PDF
                use_fontname = None
                use_fontfile = None
                logging.info(f"[PDF-EDIT] Detected font='{span_font}', size={span_size}, color={span_color}")
                try:
                    page_fonts = page.get_fonts(full=True)
                    logging.info(f"[PDF-EDIT] Page fonts: {[(name, basefont) for xref, ext, ftype, basefont, name, enc in page_fonts]}")
                    for xref, ext, ftype, basefont, name, enc in page_fonts:
                        if name == span_font or basefont == span_font:
                            font_data = doc.extract_font(xref)
                            # font_data = (basename, ext, subtype, buffer)
                            if font_data and len(font_data) >= 4 and font_data[3]:
                                buf = font_data[3]
                                logging.info(f"[PDF-EDIT] ✅ Extracted font '{name}' ({len(buf)} bytes), re-registering...")
                                # Register extracted font on the page
                                registered = page.insert_font(
                                    fontname=name or basefont,
                                    fontbuffer=buf,
                                )
                                use_fontname = registered
                                logging.info(f"[PDF-EDIT] OK: Registered as '{use_fontname}'")
                            else:
                                logging.warning(f"[PDF-EDIT] WARN: Font '{name}' found but no buffer data")
                            break
                except Exception as font_err:
                    logging.error(f"[PDF-EDIT] ERROR: Font extraction failed: {font_err}")

                # Fallback to built-in font mapping
                if not use_fontname:
                    use_fontname = _resolve_font(span_font, is_bold=span_bold, is_italic=span_italic)
                    logging.warning(f"[PDF-EDIT] WARN: Fallback to built-in font: '{span_font}' (bold={span_bold}, italic={span_italic}) -> '{use_fontname}'")

                # Collect rects for redaction + text insertion
                insert_jobs = []
                for rect in hits:
                    fontsize = span_size if span_size > 4 else rect.height * 0.75
                    if fontsize < 4:
                        fontsize = 10
                    # Add redaction annotation WITHOUT fill (preserves background)
                    page.add_redact_annot(rect, fill=False)
                    insert_jobs.append((rect, fontsize))

                # Apply all redactions (removes text, keeps background)
                page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

                # Insert new text at original positions
                for rect, fontsize in insert_jobs:
                    page.insert_text(
                        fitz.Point(rect.x0, rect.y0 + rect.height * 0.8),
                        replace_text,
                        fontname=use_fontname,
                        fontsize=fontsize,
                        color=span_color,
                    )

        out_buf = io.BytesIO()
        doc.save(out_buf, garbage=4, deflate=True)
        doc.close()
        out_buf.seek(0)

        from flask import send_file
        return send_file(
            out_buf,
            mimetype="application/pdf",
            as_attachment=False,
            download_name=f.filename.replace(".pdf", "_edited.pdf"),
        )
    except Exception as exc:
        logging.exception("[Safe Log] Unhandled exception in pipeline_pdf.py: %s", exc)
        return jsonify({"error": str(exc)}), 500


