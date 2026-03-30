"""
Scan splitter routes: split scanned PDFs, rename, download, view.
"""
from __future__ import annotations

import logging
import os
import re

from flask import Blueprint, jsonify, request, send_file
import threading

from config import Config

from routes.pipeline_helpers import (
    _get_or_create_llm,
    _scan_split_progress,
    _is_certification_page_by_text,
    _batch_detect_cert_pages_vision,
    _is_quota_error,
)


pipeline_scan_bp = Blueprint("pipeline_scan", __name__)

@pipeline_scan_bp.post("/api/scan-splitter/split")
def scan_splitter_split():
    """Upload a scanned PDF, detect translation certification pages, and split."""
    import fitz
    import base64
    global _scan_split_progress

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported"}), 400

    # Save uploaded file to temp
    scan_output_dir = Config.SCAN_SPLITTER_OUTPUTS_DIR
    os.makedirs(scan_output_dir, exist_ok=True)

    original_name = file.filename
    stem = os.path.splitext(original_name)[0]
    temp_pdf = os.path.join(scan_output_dir, f"_src_{original_name}")
    file.save(temp_pdf)

    # Reset progress
    _scan_split_progress = {"total": 0, "done": 0, "current_page": "", "running": True, "results": [], "error": ""}

    def _do_scan_split():
        global _scan_split_progress
        try:
            doc = fitz.open(temp_pdf)
            total_pages = len(doc)
            _scan_split_progress["total"] = total_pages

            # Phase 1: Detect certification pages
            # Step 1a: Quick text-based pass (free, instant)
            cert_pages = set()  # 0-indexed
            needs_vision = []   # pages that need vision check
            for i in range(total_pages):
                page = doc[i]
                page_text = page.get_text() or ""
                if _is_certification_page_by_text(page_text):
                    cert_pages.add(i)
                else:
                    needs_vision.append(i)

            print(f"[SCAN-SPLITTER] Text scan done: {len(cert_pages)} cert pages found by text, {len(needs_vision)} pages need vision check")
            _scan_split_progress["current_page"] = f"Text scan xong. {len(cert_pages)} trang xác nhận tìm thấy. Đang quét ảnh {len(needs_vision)} trang còn lại..."
            _scan_split_progress["done"] = len(cert_pages)

            # Step 1b: Batch vision for remaining pages (8 pages per API call, ALL PARALLEL)
            if needs_vision:
                from concurrent.futures import ThreadPoolExecutor, as_completed
                llm = _get_or_create_llm()
                BATCH_SIZE = 8

                # Phase A: Pre-render ALL page images (CPU work, fast)
                _scan_split_progress["current_page"] = "📸 Đang render ảnh tất cả trang..."
                all_images = {}  # idx -> (b64, page_num_1indexed)
                for idx in needs_vision:
                    try:
                        page = doc[idx]
                        rect = page.rect
                        clip = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y0 + rect.height / 2)
                        pix = page.get_pixmap(dpi=100, clip=clip)
                        img_bytes = pix.tobytes("png")
                        b64 = base64.b64encode(img_bytes).decode()
                        all_images[idx] = (b64, idx + 1)
                    except Exception as e:
                        print(f"[SCAN-SPLITTER] ❌ Error rendering page {idx}: {e}")

                # Phase B: Build batches and send ALL to vision API concurrently
                batches = []
                for batch_start in range(0, len(needs_vision), BATCH_SIZE):
                    batch_indices = needs_vision[batch_start:batch_start + BATCH_SIZE]
                    batch_images = []
                    batch_page_nums = []
                    for idx in batch_indices:
                        if idx in all_images:
                            b64, pnum = all_images[idx]
                            batch_images.append(b64)
                            batch_page_nums.append(pnum)
                    if batch_images:
                        batches.append((batch_images, batch_page_nums))

                total_batches = len(batches)
                _scan_split_progress["current_page"] = f"🔍 Đang gửi {total_batches} batch song song đến AI..."
                print(f"[SCAN-SPLITTER] 🚀 Sending {total_batches} batches in PARALLEL ({len(all_images)} pages total)")

                def _process_batch(batch_idx, images, page_nums):
                    """Worker: send one batch to vision API."""
                    found = _batch_detect_cert_pages_vision(llm, images, page_nums)
                    print(f"[SCAN-SPLITTER] ✅ Batch {batch_idx+1}/{total_batches} done: cert_pages={found}")
                    return found

                # Fire all batches concurrently (max 4 parallel to avoid rate limits)
                with ThreadPoolExecutor(max_workers=min(4, total_batches)) as executor:
                    futures = {
                        executor.submit(_process_batch, i, imgs, pnums): i
                        for i, (imgs, pnums) in enumerate(batches)
                    }
                    done_count = 0
                    for future in as_completed(futures):
                        done_count += 1
                        _scan_split_progress["current_page"] = f"🔍 Hoàn tất {done_count}/{total_batches} batch..."
                        _scan_split_progress["done"] = len(cert_pages) + done_count * BATCH_SIZE
                        try:
                            found_pages = future.result()
                            for pnum in found_pages:
                                cert_pages.add(pnum - 1)  # Convert back to 0-indexed
                        except Exception as e:
                            print(f"[SCAN-SPLITTER] ❌ Batch error: {e}")

            cert_pages = sorted(cert_pages)

            # Phase 2: Split PDF at certification boundaries
            # Each certification page = last page of a document group
            # Pages after last cert until next cert = one document
            _scan_split_progress["current_page"] = "Đang tách file..."

            if not cert_pages:
                _scan_split_progress["error"] = "Không tìm thấy trang xác nhận dịch nào trong file này."
                _scan_split_progress["running"] = False
                doc.close()
                return

            # Clean old output files (except source)
            for f in os.listdir(scan_output_dir):
                fp = os.path.join(scan_output_dir, f)
                if os.path.isfile(fp) and not f.startswith("_src_"):
                    os.remove(fp)

            results = []
            doc_start = 0
            for doc_idx, cert_page_idx in enumerate(cert_pages):
                doc_end = cert_page_idx  # inclusive
                page_range = f"{doc_start + 1}-{doc_end + 1}"
                out_name = f"{stem}_part{doc_idx + 1}_p{doc_start + 1}-{doc_end + 1}.pdf"
                out_path = os.path.join(scan_output_dir, out_name)

                # Create new PDF with these pages
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=doc_start, to_page=doc_end)
                new_doc.save(out_path)
                new_doc.close()

                results.append({
                    "filename": out_name,
                    "pages": page_range,
                    "page_count": doc_end - doc_start + 1,
                    "start_page": doc_start + 1,
                    "end_page": doc_end + 1,
                })
                doc_start = cert_page_idx + 1

            # Handle remaining pages after last certification (if any)
            if doc_start < total_pages:
                page_range = f"{doc_start + 1}-{total_pages}"
                out_name = f"{stem}_part{len(cert_pages) + 1}_p{doc_start + 1}-{total_pages}.pdf"
                out_path = os.path.join(scan_output_dir, out_name)

                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=doc_start, to_page=total_pages - 1)
                new_doc.save(out_path)
                new_doc.close()

                results.append({
                    "filename": out_name,
                    "pages": page_range,
                    "page_count": total_pages - doc_start,
                    "start_page": doc_start + 1,
                    "end_page": total_pages,
                    "no_cert": True,  # Flag: these pages had no certification
                })

            doc.close()
            _scan_split_progress["results"] = results
            _scan_split_progress["done"] = total_pages
            _scan_split_progress["current_page"] = f"Hoàn tất! Tách thành {len(results)} file."
            _scan_split_progress["running"] = False

        except Exception as e:
            _scan_split_progress["error"] = str(e)
            _scan_split_progress["running"] = False

    # Run in background thread
    import threading
    t = threading.Thread(target=_do_scan_split, daemon=True)
    t.start()

    return jsonify({"status": "started", "filename": original_name})


@pipeline_scan_bp.get("/api/scan-splitter/progress")
def scan_splitter_progress():
    """Polling endpoint for scan split progress."""
    return jsonify(_scan_split_progress)


@pipeline_scan_bp.post("/api/scan-splitter/rename")
def scan_splitter_rename():
    """Rename a split output file."""
    payload = request.get_json(force=True) or {}
    old_name = payload.get("old_filename", "").strip()
    new_name = payload.get("new_filename", "").strip()
    
    if not old_name or not new_name:
        return jsonify({"error": "old_filename and new_filename are required"}), 400
    
    scan_output_dir = Config.SCAN_SPLITTER_OUTPUTS_DIR
    old_path = os.path.join(scan_output_dir, old_name)
    
    if not os.path.isfile(old_path):
        return jsonify({"error": f"File not found: {old_name}"}), 404
    
    # Sanitize new name
    new_name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', ' ', new_name).strip()
    if not new_name:
        return jsonify({"error": "Invalid new filename"}), 400
    
    # Ensure .pdf extension
    if not new_name.lower().endswith(".pdf"):
        new_name += ".pdf"
    
    new_path = os.path.join(scan_output_dir, new_name)
    
    # Handle duplicate names
    if os.path.exists(new_path) and not os.path.samefile(old_path, new_path):
        base, ext = os.path.splitext(new_name)
        idx = 1
        while os.path.exists(new_path):
            new_path = os.path.join(scan_output_dir, f"{base} ({idx}){ext}")
            idx += 1
        new_name = os.path.basename(new_path)
    
    if old_path != new_path:
        os.rename(old_path, new_path)
    
    return jsonify({"status": "renamed", "old_filename": old_name, "new_filename": new_name})


@pipeline_scan_bp.get("/api/scan-splitter/download/<path:filename>")
def scan_splitter_download(filename):
    """Download a single split file."""
    scan_output_dir = Config.SCAN_SPLITTER_OUTPUTS_DIR
    fpath = os.path.join(scan_output_dir, filename)
    if not os.path.isfile(fpath):
        return jsonify({"error": "File not found"}), 404
    return send_file(fpath, as_attachment=True, download_name=filename)


@pipeline_scan_bp.get("/api/scan-splitter/view/<path:filename>")
def scan_splitter_view(filename):
    """View a single split file inline in browser."""
    scan_output_dir = Config.SCAN_SPLITTER_OUTPUTS_DIR
    fpath = os.path.join(scan_output_dir, filename)
    if not os.path.isfile(fpath):
        return jsonify({"error": "File not found"}), 404
    return send_file(fpath, as_attachment=False, mimetype="application/pdf")


@pipeline_scan_bp.get("/api/scan-splitter/download-zip")
def scan_splitter_download_zip():
    """Download all split files as ZIP."""
    import zipfile
    import io
    scan_output_dir = Config.SCAN_SPLITTER_OUTPUTS_DIR
    if not os.path.isdir(scan_output_dir):
        return jsonify({"error": "No output files"}), 404

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(os.listdir(scan_output_dir)):
            if f.startswith("_src_"):
                continue
            fp = os.path.join(scan_output_dir, f)
            if os.path.isfile(fp) and f.endswith(".pdf"):
                zf.write(fp, f)
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name="scan_split_results.zip")


@pipeline_scan_bp.post("/api/scan-splitter/rename-all")
def scan_splitter_rename_all():
    """Rename multiple split files at once."""
    payload = request.get_json(force=True) or {}
    renames = payload.get("renames", [])

    if not renames:
        return jsonify({"error": "No renames provided"}), 400

    scan_output_dir = Config.SCAN_SPLITTER_OUTPUTS_DIR
    results = []
    for item in renames:
        old_name = (item.get("old_filename") or "").strip()
        new_name = (item.get("new_filename") or "").strip()
        if not old_name or not new_name:
            results.append({"old": old_name, "new": new_name, "error": "Missing name"})
            continue
        new_name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', ' ', new_name).strip()
        if not new_name.lower().endswith(".pdf"):
            new_name += ".pdf"

        old_path = os.path.join(scan_output_dir, old_name)
        if not os.path.isfile(old_path):
            results.append({"old": old_name, "new": new_name, "error": "File not found"})
            continue

        new_path = os.path.join(scan_output_dir, new_name)
        if os.path.exists(new_path) and not os.path.samefile(old_path, new_path):
            base, ext = os.path.splitext(new_name)
            idx = 1
            while os.path.exists(new_path):
                new_path = os.path.join(scan_output_dir, f"{base} ({idx}){ext}")
                idx += 1
            new_name = os.path.basename(new_path)

        if old_path != new_path:
            os.rename(old_path, new_path)
        results.append({"old": old_name, "new": new_name, "ok": True})

    ok_count = sum(1 for r in results if r.get("ok"))
    return jsonify({"status": "done", "renamed_count": ok_count, "total": len(renames), "results": results})


@pipeline_scan_bp.post("/api/scan-splitter/auto-name")
def scan_splitter_auto_name():
    """AI reads first page of each split file and suggests a descriptive name."""
    import fitz
    import base64
    import json as _json
    from langchain_core.messages import HumanMessage, SystemMessage

    scan_output_dir = Config.SCAN_SPLITTER_OUTPUTS_DIR
    if not os.path.isdir(scan_output_dir):
        return jsonify({"error": "No split files found"}), 404

    files = sorted([
        f for f in os.listdir(scan_output_dir)
        if f.endswith(".pdf") and not f.startswith("_src_")
    ])
    if not files:
        return jsonify({"error": "No split files found"}), 404

    file_images = []
    for fname in files:
        fpath = os.path.join(scan_output_dir, fname)
        try:
            doc = fitz.open(fpath)
            page = doc[0]
            pix = page.get_pixmap(dpi=120)
            img_bytes = pix.tobytes("png")
            b64 = base64.b64encode(img_bytes).decode()
            doc.close()
            file_images.append({"filename": fname, "b64": b64})
        except Exception as e:
            file_images.append({"filename": fname, "b64": None, "error": str(e)})

    llm = _get_or_create_llm()
    prompt_text = (
        f"You are analyzing {len(file_images)} scanned Vietnamese documents (first page of each).\n\n"
        "For EACH document, identify what type of document it is and who it belongs to.\n\n"
        "Common Vietnamese documents:\n"
        "- Giay Khai Sinh = Birth_Certificate\n"
        "- Giay Chung Nhan Ket Hon = Marriage_Certificate\n"
        "- Ho Chieu = Passport\n"
        "- CMND / CCCD = National_ID_Card\n"
        "- So Ho Khau = Household_Registration\n"
        "- Giay Chung Nhan Quyen Su Dung Dat = Land_Use_Right_Certificate\n"
        "- Hop Dong Thue Nha = House_Rental_Contract\n"
        "- Giay Phep Kinh Doanh = Business_License\n"
        "- Bang Tot Nghiep = Graduation_Certificate\n"
        "- Giay Xac Nhan Cong Tac = Employment_Confirmation\n"
        "- Sao Ke Ngan Hang = Bank_Statement\n"
        "- Giay Dang Ky Xe = Vehicle_Registration\n"
        "- Quyet Dinh Bo Nhiem = Appointment_Decision\n"
        "- Hop Dong Lao Dong = Labor_Contract\n"
        "- Giay Chung Nhan QSDD = Land_Use_Right_Certificate\n\n"
        "Return ONLY a JSON array:\n"
        '[{"file": "original_filename.pdf", "suggested_name": "Document_Type_Person_Name"}]\n\n'
        "Rules for suggested_name:\n"
        "- Use ENGLISH document type name with underscores\n"
        "- Include person name if visible (Vietnamese name, replace spaces with _)\n"
        "- Keep concise but descriptive\n"
        "- Example: Birth_Certificate_Nguyen_Van_A\n"
    )

    content_parts = [{"type": "text", "text": prompt_text}]
    for i, item in enumerate(file_images):
        if item.get("b64"):
            content_parts.append({"type": "text", "text": f"Document {i+1} (file: {item['filename']}):"})
            content_parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{item['b64']}"}})

    try:
        result = llm.invoke([
            SystemMessage(content="You are an expert Vietnamese document classifier. Answer ONLY with JSON."),
            HumanMessage(content=content_parts),
        ])
        text = result.content if hasattr(result, 'content') else str(result)
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        suggestions = _json.loads(text)
        return jsonify({"suggestions": suggestions})
    except Exception as e:
        return jsonify({"error": f"AI naming failed: {str(e)}"}), 500
