from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from core.agents import (
    build_summary_profile,
    detect_domain,
    extract_text_with_openai,
    ingest_files,
    itinerary_writer,
    letter_writer,
)
from classifier.agent import classify_files_in_folder
from pypdf import PdfReader, PdfWriter
from core.state import GraphState
import database as db


load_dotenv()

app = Flask(__name__, static_folder="frontend", static_url_path="")

# ── Per-project directory helpers ──
PROJECTS_ROOT = os.path.join(os.path.dirname(__file__), "projects")


def _project_base_dir(project_id):
    """Return the base directory for a project: projects/{project_id}/"""
    if not project_id:
        return None
    base = os.path.join(PROJECTS_ROOT, str(project_id))
    os.makedirs(base, exist_ok=True)
    return base


def _get_project_dirs(project_id):
    """Return dict of project-scoped directory paths. Creates them if needed."""
    base = _project_base_dir(project_id)
    if not base:
        return {
            "input": "input",
            "output": "output",
            "splitter_uploads": "splitter_uploads",
            "splitter_outputs": "splitter_outputs",
        }
    dirs = {
        "input": os.path.join(base, "input"),
        "output": os.path.join(base, "output"),
        "splitter_uploads": os.path.join(base, "splitter_uploads"),
        "splitter_outputs": os.path.join(base, "splitter_outputs"),
    }
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)
    return dirs


def get_text_model() -> str:
    """Model for text reasoning/writing tasks (gpt-5-mini default)."""
    return os.getenv("OPENAI_MODEL", "gpt-5-mini")


def get_vision_model() -> str:
    """Model for image/OCR tasks (gpt-4o-mini default — cheaper, good at vision)."""
    return os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")


def _list_input_files(input_dir: str) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    for root, _, filenames in os.walk(input_dir):
        for fname in filenames:
            path = os.path.join(root, fname)
            rel_path = os.path.relpath(path, input_dir).replace("\\", "/")
            items.append(
                {
                    "name": fname,
                    "rel_path": rel_path,
                    "path": path,
                    "domain": detect_domain(fname),
                }
            )
    return items


STEP_ORDER = [
    "ingest",
    "summary",
    "writer",
]


def _cache_dir(output_path: str) -> str:
    return os.path.join(os.path.dirname(output_path), "cache")


def _state_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, "state.json")


def _step_marker_path(cache_dir: str, step: str) -> str:
    return os.path.join(cache_dir, f"step_{step}.json")


def _reset_downstream_steps(cache_dir: str, step: str) -> None:
    if step not in STEP_ORDER:
        return
    idx = STEP_ORDER.index(step)
    downstream = STEP_ORDER[idx + 1 :]
    for s in downstream:
        marker = _step_marker_path(cache_dir, s)
        if os.path.exists(marker):
            os.remove(marker)

    # Clear derived caches so downstream status/data stay consistent.
    if "summary" in downstream:
        path = os.path.join(cache_dir, "summary_profile.txt")
        if os.path.exists(path):
            os.remove(path)


def _load_state(cache_dir: str) -> Dict[str, Any]:
    path = _state_path(cache_dir)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_state(cache_dir: str, state: GraphState) -> None:
    os.makedirs(cache_dir, exist_ok=True)
    serializable = {
        "input_dir": state.get("input_dir"),
        "output_path": state.get("output_path"),
        "model": state.get("model"),
        "files": state.get("files", []),
        "grouped": state.get("grouped", {}),
        "summary_profile": state.get("summary_profile", ""),
        "writer_context": state.get("writer_context", ""),
        "letter_full": state.get("letter_full", ""),
    }
    with open(_state_path(cache_dir), "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)


def _save_step_output(cache_dir: str, step: str, state: GraphState) -> None:
    os.makedirs(cache_dir, exist_ok=True)
    if step == "ingest":
        with open(os.path.join(cache_dir, "ingest.json"), "w", encoding="utf-8") as f:
            json.dump(state.get("files", []), f, ensure_ascii=False, indent=2)
    elif step == "summary":
        with open(
            os.path.join(cache_dir, "summary_profile.txt"), "w", encoding="utf-8"
        ) as f:
            f.write(state.get("summary_profile", ""))
    elif step == "writer":
        output_path = state.get("output_path") or os.path.join("output", "letter.txt")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(state.get("letter_full", ""))

    with open(_step_marker_path(cache_dir, step), "w", encoding="utf-8") as f:
        json.dump({"done": True}, f)


def _is_step_done(cache_dir: str, step: str) -> bool:
    return os.path.exists(_step_marker_path(cache_dir, step))


def _resolve_input_file_path(input_dir: str, file_ref: str) -> Optional[str]:
    if not file_ref:
        return None

    input_root = os.path.abspath(input_dir)
    candidate = os.path.abspath(os.path.normpath(os.path.join(input_dir, file_ref)))
    if candidate.startswith(input_root) and os.path.exists(candidate):
        return candidate

    for root, _, filenames in os.walk(input_dir):
        for fname in filenames:
            if fname == file_ref:
                return os.path.join(root, fname)
    return None


def _upsert_file_record(files: List[Dict[str, Any]], new_file: Dict[str, Any]) -> List[Dict[str, Any]]:
    updated: List[Dict[str, Any]] = []
    replaced = False
    for item in files:
        if item.get("path") == new_file.get("path"):
            updated.append(new_file)
            replaced = True
        else:
            updated.append(item)
    if not replaced:
        updated.append(new_file)
    return updated


def _missing_prereq_step(cache_dir: str, step: str) -> Optional[str]:
    if step not in STEP_ORDER:
        return None
    idx = STEP_ORDER.index(step)
    for prev in STEP_ORDER[:idx]:
        if not _is_step_done(cache_dir, prev):
            return prev
    return None


def _run_single_step(step: str, state: GraphState) -> GraphState:
    if step == "ingest":
        return ingest_files(state)
    if step == "summary":
        return build_summary_profile(state)
    if step == "writer":
        return letter_writer(state)
    return state


@app.get("/")
def index():
    return send_from_directory("frontend", "index.html")


# ==================== PROJECT ENDPOINTS ====================

@app.post("/api/projects")
def create_project():
    payload = request.get_json(force=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Project name is required"}), 400
    project = db.create_project(name)
    return jsonify(project)


@app.get("/api/projects")
def list_projects():
    projects = db.list_projects()
    return jsonify({"projects": projects})


@app.get("/api/projects/<int:project_id>")
def get_project(project_id):
    project = db.get_project(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    return jsonify(project)


@app.put("/api/projects/<int:project_id>")
def update_project(project_id):
    payload = request.get_json(force=True) or {}
    name = payload.get("name")
    updates = {}
    if name:
        updates["name"] = name.strip()
    project = db.update_project(project_id, **updates)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    return jsonify(project)


@app.delete("/api/projects/<int:project_id>")
def delete_project(project_id):
    # Clean up project directory on disk
    import shutil as _shutil
    project_dir = _project_base_dir(project_id)
    if project_dir and os.path.isdir(project_dir):
        _shutil.rmtree(project_dir, ignore_errors=True)
    ok = db.delete_project(project_id)
    if not ok:
        return jsonify({"error": "Project not found"}), 404
    return jsonify({"status": "deleted"})


@app.get("/api/project/dirs")
def get_project_dirs():
    """Return project-scoped directory paths for frontend."""
    project_id = request.args.get("project_id")
    if not project_id:
        return jsonify({"input": "input", "output": "output",
                        "splitter_uploads": "splitter_uploads",
                        "splitter_outputs": "splitter_outputs"})
    dirs = _get_project_dirs(int(project_id))
    return jsonify(dirs)


@app.get("/api/files")
def list_files():
    input_dir = request.args.get("input_dir", "input")
    files = _list_input_files(input_dir)
    return jsonify({"input_dir": input_dir, "files": files})


# ==================== PRE-CHECK ENDPOINTS ====================

def _vision_detect_pdf_documents(llm, pdf_path: str, filename: str, total_pages: int):
    """Quick vision check: does this scanned PDF contain 1 document type or multiple?
    Only samples 3 pages (first, middle, last) at low DPI for speed."""
    import fitz  # PyMuPDF
    import base64
    
    doc = fitz.open(pdf_path)
    actual_pages = len(doc)
    
    # Only sample 3 pages: first, middle, last (fast & cheap)
    if actual_pages <= 3:
        sample_indices = list(range(actual_pages))
    else:
        mid = actual_pages // 2
        sample_indices = [0, mid, actual_pages - 1]
    
    # Render sampled pages as tiny thumbnails
    content_parts = [
        {"type": "text", "text": f"""Look at these {len(sample_indices)} sampled pages from "{filename}" ({actual_pages} pages total).

Quick check: Do these pages contain MULTIPLE DIFFERENT types of documents (e.g., passport + bank statement + birth certificate mixed together)?

Answer in this JSON format ONLY:
{{"mixed": true, "doc_count": 5, "doc_types": ["PASSPORT", "BANK STATEMENT", "BIRTH CERTIFICATE", ...]}}

OR if all pages look like the SAME document type:
{{"mixed": false, "doc_count": 1, "doc_types": ["BANK STATEMENT"]}}

Return ONLY JSON, nothing else."""}
    ]
    
    for idx in sample_indices:
        page = doc[idx]
        pix = page.get_pixmap(dpi=72)  # Very low DPI, just enough to identify doc type
        img_bytes = pix.tobytes("png")
        b64 = base64.b64encode(img_bytes).decode()
        content_parts.append({"type": "text", "text": f"Page {idx + 1}/{actual_pages}:"})
        content_parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
    
    doc.close()
    
    from langchain_core.messages import HumanMessage, SystemMessage
    result = llm.invoke([
        SystemMessage(content="You are a document classifier. Answer only with JSON."),
        HumanMessage(content=content_parts),
    ])
    
    # Parse response
    import re
    text = (result.content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    
    try:
        parsed = json.loads(text)
    except Exception:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                parsed = json.loads(match.group())
            except Exception:
                return []
        else:
            return []
    
    is_mixed = parsed.get("mixed", False)
    doc_count = int(parsed.get("doc_count", 1))
    doc_types = parsed.get("doc_types", ["UNKNOWN"])
    
    if not is_mixed or doc_count <= 1:
        # Single document - return 1 item
        return [{"doc_type_en": doc_types[0] if doc_types else "UNKNOWN",
                 "person_name": "UNKNOWN", "start_page": 1, "end_page": actual_pages}]
    else:
        # Multiple documents - return dummy items just to flag as needs_split
        return [{"doc_type_en": dt, "person_name": "UNKNOWN", "start_page": 0, "end_page": 0}
                for dt in doc_types]


@app.post("/api/precheck/scan")
def precheck_scan():
    """Scan all files in a folder to detect multi-document files."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    model = payload.get("model") or get_vision_model()

    if not os.path.isdir(input_dir):
        return jsonify({"error": "folder_not_found", "input_dir": input_dir}), 404

    from langchain_openai import ChatOpenAI
    from classifier.agent import _extract_pdf_pages_text, _classify_multi_page_pdf
    from concurrent.futures import ThreadPoolExecutor, as_completed

    llm = ChatOpenAI(model=model, temperature=0)

    # Collect all files first
    all_files = []
    for root, _, filenames in os.walk(input_dir):
        for fname in sorted(filenames):
            path = os.path.join(root, fname)
            ext = os.path.splitext(fname)[1].lower()
            rel_path = os.path.relpath(path, input_dir).replace("\\", "/")
            all_files.append((fname, path, ext, rel_path))

    def _scan_one_file(fname, path, ext, rel_path):
        """Scan a single file — runs in a thread."""
        if ext != ".pdf":
            return {
                "filename": fname, "rel_path": rel_path, "path": path, "ext": ext,
                "page_count": 1, "doc_count": 1, "doc_types": ["SINGLE FILE"],
                "needs_split": False,
            }
        try:
            page_texts = _extract_pdf_pages_text(path)
            total_pages = len(page_texts)
            non_empty = sum(1 for t in page_texts if len(t.strip()) > 30)
            has_text = non_empty >= max(1, total_pages * 0.3)

            if has_text:
                docs = _classify_multi_page_pdf(llm, fname, page_texts)
            else:
                docs = _vision_detect_pdf_documents(llm, path, fname, total_pages)

            doc_count = len(docs) if docs else 1
            doc_types = [d.get("doc_type_en", "UNKNOWN") for d in docs] if docs else ["UNKNOWN"]
            return {
                "filename": fname, "rel_path": rel_path, "path": path, "ext": ext,
                "page_count": total_pages, "doc_count": doc_count, "doc_types": doc_types,
                "needs_split": doc_count >= 2, "documents": docs if docs else [],
                "scan_method": "text" if has_text else "vision",
            }
        except Exception as e:
            return {
                "filename": fname, "rel_path": rel_path, "path": path, "ext": ext,
                "page_count": 0, "doc_count": 1, "doc_types": ["ERROR"],
                "needs_split": False, "error": str(e),
            }

    # Process files in parallel (5 workers)
    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(_scan_one_file, fname, path, ext, rel_path): fname
            for fname, path, ext, rel_path in all_files
        }
        for future in as_completed(futures):
            results.append(future.result())

    # Sort by filename for consistent display
    results.sort(key=lambda r: r["filename"])

    multi_count = sum(1 for r in results if r.get("needs_split"))
    clean_count = len(results) - multi_count

    return jsonify({
        "status": "done",
        "input_dir": input_dir,
        "total_files": len(results),
        "multi_doc_count": multi_count,
        "clean_count": clean_count,
        "files": results,
    })


@app.post("/api/pipeline/send-to-splitter")
def pipeline_send_to_splitter():
    """Copy selected multi-doc files → splitter_uploads for AI splitting."""
    payload = request.get_json(force=True) or {}
    file_paths = payload.get("file_paths", [])

    if not file_paths:
        return jsonify({"error": "no_files_selected"}), 400

    target_dir = os.path.join("splitter_uploads")
    os.makedirs(target_dir, exist_ok=True)
    copied = []
    for src in file_paths:
        if not os.path.isfile(src):
            continue
        fname = os.path.basename(src)
        dst = os.path.join(target_dir, fname)
        base, ext = os.path.splitext(fname)
        idx = 1
        while os.path.exists(dst):
            dst = os.path.join(target_dir, f"{base} ({idx}){ext}")
            idx += 1
        shutil.copy2(src, dst)
        copied.append(fname)

    return jsonify({"status": "done", "copied": copied, "count": len(copied)})


@app.post("/api/pipeline/send-clean-to-classifier")
def pipeline_send_clean_to_classifier():
    """Copy clean (single-doc) files directly → classifier input folder."""
    payload = request.get_json(force=True) or {}
    file_paths = payload.get("file_paths", [])
    target_dir = payload.get("target_dir", os.path.join("phanloai", "input"))

    if not file_paths:
        return jsonify({"error": "no_files_selected"}), 400

    os.makedirs(target_dir, exist_ok=True)
    copied = []
    for src in file_paths:
        if not os.path.isfile(src):
            continue
        fname = os.path.basename(src)
        dst = os.path.join(target_dir, fname)
        base, ext = os.path.splitext(fname)
        idx = 1
        while os.path.exists(dst):
            dst = os.path.join(target_dir, f"{base} ({idx}){ext}")
            idx += 1
        shutil.copy2(src, dst)
        copied.append(fname)

    return jsonify({"status": "done", "copied": copied, "count": len(copied), "target_dir": target_dir})


@app.get("/api/classifier/files")
def list_classifier_files():
    input_dir = request.args.get("input_dir", os.path.join("phanloai", "input"))
    if not os.path.isdir(input_dir):
        return jsonify({"input_dir": input_dir, "files": [], "exists": False})
    items = _list_input_files(input_dir)
    return jsonify(
        {
            "input_dir": input_dir,
            "exists": True,
            "files": items,
        }
    )


@app.post("/api/classifier/delete")
def classifier_delete_file():
    """Delete a single file from classifier input folder."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", os.path.join("phanloai", "input"))
    filename = payload.get("filename", "")
    if not filename:
        return jsonify({"error": "no_filename"}), 400
    file_path = os.path.join(input_dir, filename)
    if not os.path.isfile(file_path):
        return jsonify({"error": "file_not_found"}), 404
    os.remove(file_path)
    return jsonify({"deleted": filename})


@app.post("/api/classifier/delete-all")
def classifier_delete_all():
    """Delete all files from classifier input folder."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", os.path.join("phanloai", "input"))
    count = 0
    if os.path.isdir(input_dir):
        for fname in os.listdir(input_dir):
            fpath = os.path.join(input_dir, fname)
            if os.path.isfile(fpath):
                os.remove(fpath)
                count += 1
    return jsonify({"deleted_count": count})


@app.post("/api/classifier/run")
def run_classifier():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", os.path.join("phanloai", "input"))
    output_dir = payload.get("output_dir", os.path.join("phanloai", "output"))
    save_output = payload.get("save_output", False)  # Don't auto-save by default
    model = payload.get("model") or get_vision_model()  # classifier reads images

    if not os.path.isdir(input_dir):
        return jsonify({"error": "folder_not_found", "input_dir": input_dir}), 404

    # If save_output is False, use a temp dir so classifier doesn't write to real output
    actual_output = output_dir if save_output else os.path.join("phanloai", "_temp_output")
    result = classify_files_in_folder(input_dir=input_dir, output_dir=actual_output, model=model)
    # Store the temp dir in result so save-output can use it
    result["_temp_output"] = actual_output
    result["_final_output"] = output_dir
    return jsonify({"status": "done", **result})

@app.get("/api/classifier/last-result")
def classifier_last_result():
    """Scan _temp_output to reconstruct last classification result."""
    temp_output = os.path.join("phanloai", "_temp_output")
    if not os.path.isdir(temp_output):
        return jsonify({"exists": False})

    copied = []
    person_counts = {}
    for person_dir in sorted(os.listdir(temp_output)):
        person_path = os.path.join(temp_output, person_dir)
        if not os.path.isdir(person_path):
            continue
        count = 0
        for fname in sorted(os.listdir(person_path)):
            fpath = os.path.join(person_path, fname)
            if not os.path.isfile(fpath):
                continue
            count += 1
            # Try to extract doc_type from filename: DOMAIN_PERSON_DOCTYPE.ext
            stem = os.path.splitext(fname)[0]
            parts = stem.split("_", 2)  # DOMAIN_PERSON_DOCTYPE or just name
            doc_type = parts[-1] if len(parts) >= 3 else stem
            # Remove trailing (1), (2) etc
            import re
            doc_type = re.sub(r'\s*\(\d+\)$', '', doc_type).strip()

            rel_path = os.path.join(person_dir, fname).replace("\\", "/")
            copied.append({
                "source": fname,
                "person_name": person_dir,
                "doc_type_en": doc_type,
                "to": rel_path,
            })
        if count > 0:
            person_counts[person_dir] = count

    if not copied:
        return jsonify({"exists": False})

    return jsonify({
        "exists": True,
        "status": "done",
        "copied": copied,
        "copied_count": len(copied),
        "skipped_count": 0,
        "person_counts": person_counts,
        "_temp_output": temp_output,
        "_final_output": os.path.join("phanloai", "output"),
    })


@app.post("/api/classifier/save-output")
def classifier_save_output():
    """Copy classified results from temp to final output folder."""
    payload = request.get_json(force=True) or {}
    temp_output = payload.get("temp_output", os.path.join("phanloai", "_temp_output"))
    final_output = payload.get("output_dir", os.path.join("phanloai", "output"))

    if not os.path.isdir(temp_output):
        return jsonify({"error": "no_results_to_save"}), 404

    os.makedirs(final_output, exist_ok=True)
    count = 0
    for root, dirs, files in os.walk(temp_output):
        rel = os.path.relpath(root, temp_output)
        dest_dir = os.path.join(final_output, rel) if rel != "." else final_output
        os.makedirs(dest_dir, exist_ok=True)
        for fname in files:
            src = os.path.join(root, fname)
            dst = os.path.join(dest_dir, fname)
            shutil.copy2(src, dst)
            count += 1

    # Auto-cleanup: delete temp output to save disk space
    try:
        shutil.rmtree(temp_output)
    except Exception:
        pass

    # Optional: clean input files too
    clean_input = payload.get("clean_input", False)
    input_dir = payload.get("input_dir", os.path.join("phanloai", "input"))
    if clean_input and os.path.isdir(input_dir):
        try:
            shutil.rmtree(input_dir)
            os.makedirs(input_dir, exist_ok=True)
        except Exception:
            pass

    return jsonify({"status": "saved", "output_dir": final_output, "file_count": count})


@app.post("/api/classifier/rename-file")
def classifier_rename_file():
    """Rename/move a classified output file to a different person or doc_type."""
    payload = request.get_json(force=True) or {}
    old_path = payload.get("old_path", "")  # relative path like "UNKNOWN PERSON/FINANCIAL_BANK STATEMENT.pdf"
    new_person = payload.get("new_person", "").strip()
    new_doc_type = payload.get("new_doc_type", "").strip()
    temp_output = payload.get("temp_output", os.path.join("phanloai", "_temp_output"))

    if not old_path or not new_person:
        return jsonify({"error": "old_path and new_person are required"}), 400

    full_old = os.path.join(temp_output, old_path)
    if not os.path.isfile(full_old):
        return jsonify({"error": f"File not found: {old_path}"}), 404

    ext = os.path.splitext(full_old)[1] or ".pdf"

    # Import domain resolver from classifier
    from classifier.agent import _resolve_domain_prefix, _sanitize_name, _pick_unique_destination

    doc_type = _sanitize_name(new_doc_type, "DOCUMENT") if new_doc_type else "DOCUMENT"
    person_clean = _sanitize_name(new_person, "UNKNOWN PERSON")
    domain = _resolve_domain_prefix(doc_type)
    pname = person_clean.replace(" ", "_")
    stem = f"{domain}_{pname}_{doc_type}"

    # Create new person directory
    new_person_dir = os.path.join(temp_output, person_clean)
    os.makedirs(new_person_dir, exist_ok=True)
    new_path = _pick_unique_destination(new_person_dir, stem, ext)

    # Move file
    shutil.move(full_old, new_path)

    # Clean up empty old directory
    old_dir = os.path.dirname(full_old)
    if os.path.isdir(old_dir) and not os.listdir(old_dir):
        os.rmdir(old_dir)

    new_rel = os.path.relpath(new_path, temp_output).replace("\\", "/")
    return jsonify({
        "status": "renamed",
        "old_path": old_path,
        "new_path": new_rel,
        "person_name": person_clean,
        "doc_type_en": doc_type,
    })


# ==================== PIPELINE CONNECTION ENDPOINTS ====================

@app.post("/api/pipeline/send-to-classifier")
def pipeline_send_to_classifier():
    """Copy ALL splitter output files (AI + manual) → classifier input folder.
    Walks splitter_outputs/ recursively, skipping .zip files."""
    payload = request.get_json(force=True) or {}
    file_id = payload.get("file_id", "")
    target_dir = payload.get("target_dir", os.path.join("phanloai", "input"))

    # Find source: specific file_id or all outputs
    source_dir = os.path.join("splitter_outputs", file_id) if file_id else ""
    if not source_dir or not os.path.isdir(source_dir):
        source_dir = "splitter_outputs"
        if not os.path.isdir(source_dir):
            return jsonify({"error": "no_splitter_output"}), 404

    os.makedirs(target_dir, exist_ok=True)
    copied = []
    for root, _, files in os.walk(source_dir):
        for fname in files:
            if fname.endswith(".zip"):
                continue
            if not fname.lower().endswith(".pdf"):
                continue
            src = os.path.join(root, fname)
            dst = os.path.join(target_dir, fname)
            # Avoid overwriting: add suffix if exists
            base, ext = os.path.splitext(fname)
            idx = 1
            while os.path.exists(dst):
                dst = os.path.join(target_dir, f"{base} ({idx}){ext}")
                idx += 1
            shutil.copy2(src, dst)
            copied.append(fname)

    return jsonify({"status": "done", "copied": copied, "count": len(copied), "target_dir": target_dir})


@app.post("/api/pipeline/send-to-input")
def pipeline_send_to_input():
    """Copy classifier output files → letter/booking input folder."""
    payload = request.get_json(force=True) or {}
    source_dir = payload.get("source_dir", os.path.join("phanloai", "output"))
    target_dir = payload.get("target_dir", "input")

    if not os.path.isdir(source_dir):
        return jsonify({"error": "no_classifier_output"}), 404

    os.makedirs(target_dir, exist_ok=True)
    copied = []
    for root, _, files in os.walk(source_dir):
        for fname in files:
            src = os.path.join(root, fname)
            dst = os.path.join(target_dir, fname)
            base, ext = os.path.splitext(fname)
            idx = 1
            while os.path.exists(dst):
                dst = os.path.join(target_dir, f"{base} ({idx}){ext}")
                idx += 1
            shutil.copy2(src, dst)
            copied.append(fname)

    return jsonify({"status": "done", "copied": copied, "count": len(copied), "target_dir": target_dir})

def _safe_join(base: str, rel_path: str) -> str:
    base_abs = os.path.abspath(base)
    candidate = os.path.abspath(os.path.join(base, rel_path))
    if not candidate.startswith(base_abs):
        raise ValueError("Invalid path")
    return candidate


@app.post("/api/classifier/split_manual")
def split_manual():
    """Manual PDF splitting. Outputs go to splitter_outputs/manual_<uuid>/.
    If source_file_id + source_filename are provided (from AI results),
    the original AI file is removed from splitter_outputs so it won't be
    transferred to classifier (only the manually split files will be)."""
    payload = request.get_json(force=True) or {}
    # Source can be from AI results or from uploaded file
    source_file_id = (payload.get("source_file_id") or "").strip()
    source_filename = (payload.get("source_filename") or "").strip()
    # Legacy support: direct source path
    input_dir = payload.get("input_dir", os.path.join("phanloai", "input"))
    source = (payload.get("source") or "").strip()
    segments = payload.get("segments") or []

    if not isinstance(segments, list) or not segments:
        return jsonify({"error": "missing_segments"}), 400

    # Determine source PDF path
    src_path = None
    if source_file_id and source_filename:
        # Source from AI splitter output
        candidate = SPLITTER_OUTPUT_DIR / source_file_id / source_filename
        if candidate.is_file():
            src_path = str(candidate)
    if not src_path and source:
        # Legacy: from input_dir
        try:
            src_path = _safe_join(input_dir, source)
        except ValueError:
            return jsonify({"error": "invalid_source"}), 400

    if not src_path or not os.path.exists(src_path):
        return jsonify({"error": "source_not_found"}), 404
    if os.path.splitext(src_path)[1].lower() != ".pdf":
        return jsonify({"error": "source_not_pdf"}), 400

    try:
        reader = PdfReader(src_path)
    except Exception as exc:
        return jsonify({"error": "read_pdf_failed", "detail": str(exc)}), 500

    total_pages = len(reader.pages)

    # Output goes to splitter_outputs/manual_<uuid>/
    manual_id = f"manual_{uuid.uuid4().hex[:8]}"
    output_dir = str(SPLITTER_OUTPUT_DIR / manual_id)
    os.makedirs(output_dir, exist_ok=True)

    created: list[dict[str, Any]] = []

    def _sanitize_name(value: str, fallback: str) -> str:
        text = (value or "").strip()
        text = re.sub(r"[\\/:*?\"<>|]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text or fallback

    def _pick_unique(dest_dir: str, stem: str, ext: str) -> str:
        candidate = os.path.join(dest_dir, f"{stem}{ext}")
        idx = 1
        while os.path.exists(candidate):
            candidate = os.path.join(dest_dir, f"{stem} ({idx}){ext}")
            idx += 1
        return candidate

    for seg in segments:
        if not isinstance(seg, dict):
            continue
        name = _sanitize_name(seg.get("output_name") or "", "DOCUMENT")
        try:
            s = int(seg.get("start_page"))
            e = int(seg.get("end_page"))
        except Exception:
            continue
        if s < 1 or e < 1 or s > total_pages or e > total_pages:
            continue
        if s > e:
            s, e = e, s
        writer = PdfWriter()
        for i in range(s - 1, e):
            writer.add_page(reader.pages[i])
        out_path = _pick_unique(output_dir, name, ".pdf")
        try:
            with open(out_path, "wb") as f:
                writer.write(f)
        except Exception:
            continue
        created.append(
            {
                "output_name": name,
                "start_page": s,
                "end_page": e,
                "to": os.path.relpath(out_path, output_dir).replace("\\", "/"),
            }
        )

    # If splitting from AI result, remove the original AI file so it won't be
    # transferred to classifier (only the new manual splits will be transferred).
    removed_original = None
    if source_file_id and source_filename and created:
        original_path = SPLITTER_OUTPUT_DIR / source_file_id / source_filename
        if original_path.is_file():
            os.remove(str(original_path))
            removed_original = source_filename

    # Save source metadata for persistent display
    if created:
        src_display = source_filename or source or "unknown"
        source_meta = {"source_filename": src_display, "source_type": "manual"}
        with open(os.path.join(output_dir, "_source.json"), "w", encoding="utf-8") as mf:
            json.dump(source_meta, mf, ensure_ascii=False)

    return jsonify(
        {
            "status": "done",
            "manual_id": manual_id,
            "output_dir": output_dir,
            "source": source or source_filename,
            "total_pages": total_pages,
            "segments": created,
            "removed_original": removed_original,
        }
    )


@app.route("/api/pdf/merge", methods=["POST"])
def merge_pdf():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", os.path.join("pdf", "input"))
    output_dir = payload.get("output_dir", os.path.join("pdf", "output"))
    files = payload.get("files") or []
    output_name = (payload.get("output_name") or "").strip()

    if not os.path.isdir(input_dir):
        return jsonify({"error": "folder_not_found", "input_dir": input_dir}), 404
    os.makedirs(output_dir, exist_ok=True)

    if not isinstance(files, list) or not files:
        return jsonify({"error": "missing_files"}), 400
    if not output_name:
        return jsonify({"error": "missing_output_name"}), 400

    # Reuse helpers
    def _sanitize_name(value: str, fallback: str) -> str:
        text = (value or "").strip()
        text = re.sub(r"[\\/:*?\"<>|]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text or fallback

    def _pick_unique(dest_dir: str, stem: str, ext: str) -> str:
        candidate = os.path.join(dest_dir, f"{stem}{ext}")
        idx = 1
        while os.path.exists(candidate):
            candidate = os.path.join(dest_dir, f"{stem} ({idx}){ext}")
            idx += 1
        return candidate

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
        except Exception:
            continue
        for page in reader.pages:
            writer.add_page(page)
            total_pages += 1
        used_files.append(os.path.relpath(src_path, input_dir).replace("\\", "/"))

    if not used_files:
        return jsonify({"error": "no_valid_pdfs"}), 400

    safe_name = _sanitize_name(output_name, "MERGED")
    out_path = _pick_unique(output_dir, safe_name, ".pdf")
    try:
        with open(out_path, "wb") as f:
            writer.write(f)
    except Exception as exc:
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


@app.route("/api/pdf/rename", methods=["POST"])
def rename_pdf():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", os.path.join("pdf", "input"))
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


@app.route("/api/pdf/rename_suggest_name", methods=["POST"])
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
        return jsonify({"error": "llm_error", "detail": str(exc)}), 500

    suggested = (getattr(result, "content", "") or "").strip().upper()
    suggested = re.sub(r"[^A-Z0-9\s]", " ", suggested)
    suggested = re.sub(r"\s+", " ", suggested).strip()

    if not suggested:
        return jsonify({"error": "empty_suggestion"}), 500

    return jsonify({"suggested_name": suggested})


@app.get("/api/steps")
def list_steps():
    project_id = request.args.get("project_id", type=int)
    if project_id:
        state = db.get_latest_letter_state(project_id)
        if state:
            steps = [
                {"name": "ingest", "done": state["step_ingest"]},
                {"name": "summary", "done": state["step_summary"]},
                {"name": "writer", "done": state["step_writer"]},
            ]
        else:
            steps = [{"name": s, "done": False} for s in STEP_ORDER]
        return jsonify({"steps": steps})
    # Fallback to file-based
    output_path = request.args.get("output", os.path.join("output", "letter.txt"))
    cache_dir = _cache_dir(output_path)
    steps = [
        {"name": step, "done": _is_step_done(cache_dir, step)} for step in STEP_ORDER
    ]
    return jsonify({"steps": steps})


@app.get("/api/summary")
def get_summary():
    project_id = request.args.get("project_id", type=int)
    if project_id:
        state = db.get_latest_letter_state(project_id)
        summary = state["summary_profile"] if state else ""
        return jsonify({"summary_profile": summary})
    output_path = request.args.get("output", os.path.join("output", "letter.txt"))
    cache_dir = _cache_dir(output_path)
    state_cache = _load_state(cache_dir)
    summary = state_cache.get("summary_profile", "")
    if not summary:
        path = os.path.join(cache_dir, "summary_profile.txt")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                summary = f.read()
    return jsonify({"summary_profile": summary})


@app.get("/api/writer_context")
def get_writer_context():
    project_id = request.args.get("project_id", type=int)
    if project_id:
        state = db.get_latest_letter_state(project_id)
        return jsonify({"writer_context": state["writer_context"] if state else ""})
    output_path = request.args.get("output", os.path.join("output", "letter.txt"))
    cache_dir = _cache_dir(output_path)
    state_cache = _load_state(cache_dir)
    return jsonify({"writer_context": state_cache.get("writer_context", "")})


@app.get("/api/ingest_stream")
def ingest_stream():
    input_dir = request.args.get("input_dir", "input")
    output_path = request.args.get("output", os.path.join("output", "letter.txt"))
    model = request.args.get("model") or get_vision_model()  # ingest reads images
    force = request.args.get("force", "0") == "1"
    project_id = request.args.get("project_id", type=int)

    llm = ChatOpenAI(model=model, temperature=0)
    cache_dir = _cache_dir(output_path)
    files: List[Dict[str, str]] = []

    if force:
        _reset_downstream_steps(cache_dir, "ingest")

    def sse(data: Dict) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    def generate():
        for root, _, filenames in os.walk(input_dir):
            for fname in filenames:
                path = os.path.join(root, fname)
                yield sse({"type": "progress", "message": f"Đang trích xuất: {fname}"})
                text = extract_text_with_openai(llm, path)
                files.append(
                    {
                        "path": path,
                        "name": fname,
                        "text": text,
                        "domain": detect_domain(fname),
                    }
                )
        state: GraphState = {
            "input_dir": input_dir,
            "output_path": output_path,
            "model": model,
            "llm": llm,
            "files": files,
        }
        _save_state(cache_dir, state)
        _save_step_output(cache_dir, "ingest", state)

        # Save to DB if project_id provided
        if project_id:
            db.save_letter_state(
                project_id,
                files_data=files,
                step_ingest=True,
            )

        yield sse({"type": "done"})

    return Response(generate(), mimetype="text/event-stream")


@app.get("/api/itinerary/latest")
def get_itinerary_latest():
    project_id = request.args.get("project_id", type=int)
    if project_id:
        it = db.get_latest_itinerary(project_id)
        return jsonify({"itinerary": it["html_content"] if it else ""})
    output_path = request.args.get("output", os.path.join("output", "itinerary.html"))
    cache_dir = _cache_dir(output_path)
    path = os.path.join(cache_dir, "itinerary.html")
    if not os.path.exists(path):
        return jsonify({"itinerary": ""})
    with open(path, "r", encoding="utf-8") as f:
        return jsonify({"itinerary": f.read()})


@app.get("/api/itinerary/context/latest")
def get_itinerary_context_latest():
    project_id = request.args.get("project_id", type=int)
    if project_id:
        ctx = db.get_latest_itinerary_context(project_id)
        if ctx:
            summary = _build_itinerary_summary_from_form(ctx.get("form_data", {}))
            return jsonify({"summary_profile": summary, "form_data": ctx.get("form_data", {})})
        return jsonify({"summary_profile": "", "form_data": {}})
    output_path = request.args.get("output", os.path.join("output", "itinerary.html"))
    cache_dir = _cache_dir(output_path)
    summary_path = os.path.join(cache_dir, "itinerary_summary.txt")
    meta_path = os.path.join(cache_dir, "itinerary_summary_meta.json")

    summary = ""
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            summary = f.read()

    meta: Dict[str, Any] = {"form_data": {}}
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

    return jsonify(
        {
            "summary_profile": summary,
            "form_data": meta.get("form_data", {}),
        }
    )


def _build_itinerary_summary_from_form(form_data: Dict[str, Any]) -> str:
    participants = (form_data.get("participants") or "").strip()
    travel_purpose = (form_data.get("travel_purpose") or "").strip()
    start_date = (form_data.get("travel_start_date") or "").strip()
    end_date = (form_data.get("travel_end_date") or "").strip()
    has_any_value = any(
        [
            participants,
            travel_purpose,
            start_date,
            end_date,
        ]
    )
    if not has_any_value:
        return ""

    lines: List[str] = ["Core itinerary inputs:"]
    if participants:
        lines.append(f"- Participant(s): {participants}")
    if start_date and end_date:
        lines.append(f"- Travel period: From {start_date} to {end_date}")
    elif start_date:
        lines.append(f"- travel_start_date: {start_date}")
    elif end_date:
        lines.append(f"- travel_end_date: {end_date}")
    if travel_purpose:
        lines.append(f"- Purpose of travel: {travel_purpose}")

    return "\n".join(lines).strip()


@app.route("/api/itinerary/context/save", methods=["POST"])
def save_itinerary_context():
    payload = request.get_json(force=True) or {}
    output_path = payload.get("output", os.path.join("output", "itinerary.html"))
    form_data = payload.get("form_data") or {}
    project_id = payload.get("project_id")

    if not isinstance(form_data, dict):
        return jsonify({"error": "invalid_form_data"}), 400

    summary_profile = _build_itinerary_summary_from_form(form_data)
    if not summary_profile:
        return jsonify({"error": "missing_context"}), 400

    # Save to file cache
    cache_dir = _cache_dir(output_path)
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "itinerary_summary.txt"), "w", encoding="utf-8") as f:
        f.write(summary_profile)
    with open(os.path.join(cache_dir, "itinerary_summary_meta.json"), "w", encoding="utf-8") as f:
        json.dump({"form_data": form_data}, f, ensure_ascii=False, indent=2)

    # Save to DB
    if project_id:
        db.save_itinerary_context(int(project_id), {"form_data": form_data})

    return jsonify(
        {
            "status": "done",
            "summary_profile": summary_profile,
            "form_data": form_data,
        }
    )


@app.post("/api/run_step")
def run_step():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_path = payload.get("output", os.path.join("output", "letter.txt"))
    step = payload.get("step")
    model = payload.get("model") or get_vision_model()  # ingest step reads images
    force = bool(payload.get("force", False))
    writer_context = (payload.get("writer_context") or "").strip()
    project_id = payload.get("project_id", type=int) if isinstance(payload.get("project_id"), int) else None

    if step not in STEP_ORDER:
        return jsonify({"error": "invalid_step"}), 400

    cache_dir = _cache_dir(output_path)
    missing = _missing_prereq_step(cache_dir, step)
    if missing and not force:
        return jsonify({"error": "missing_prerequisite", "missing": missing}), 400

    if _is_step_done(cache_dir, step) and not force:
        return jsonify({"status": "cached", "step": step})

    if force:
        _reset_downstream_steps(cache_dir, step)

    state_cache = _load_state(cache_dir)
    llm = ChatOpenAI(model=model, temperature=0)
    state: GraphState = {
        "input_dir": input_dir,
        "output_path": output_path,
        "model": model,
        "llm": llm,
        "files": state_cache.get("files", []),
        "grouped": state_cache.get("grouped", {}),
        "summary_profile": state_cache.get("summary_profile", ""),
        "writer_context": writer_context or state_cache.get("writer_context", ""),
        "letter_full": state_cache.get("letter_full", ""),
    }

    state = _run_single_step(step, state)
    _save_state(cache_dir, state)
    _save_step_output(cache_dir, step, state)

    # Save to DB if project_id provided
    if project_id:
        db_updates = {f"step_{step}": True}
        if step == "summary":
            db_updates["summary_profile"] = state.get("summary_profile", "")
        if step == "writer":
            db_updates["writer_context"] = state.get("writer_context", "")
            db_updates["letter_content"] = state.get("letter_full", "")
        db.save_letter_state(project_id, **db_updates)

    response: Dict[str, Any] = {"status": "done", "step": step}
    if step == "summary":
        response["summary_profile"] = state.get("summary_profile", "")
    if step == "writer":
        response["letter"] = state.get("letter_full", "")
        response["output_path"] = output_path

    return jsonify(response)


@app.post("/api/run_all")
def run_all():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_path = payload.get("output", os.path.join("output", "letter.txt"))
    model = payload.get("model") or get_vision_model()  # pipeline includes ingest (images)
    force = bool(payload.get("force", False))
    writer_context = (payload.get("writer_context") or "").strip()
    project_id = payload.get("project_id", type=int) if isinstance(payload.get("project_id"), int) else None

    cache_dir = _cache_dir(output_path)
    state_cache = _load_state(cache_dir)
    llm = ChatOpenAI(model=model, temperature=0)
    state: GraphState = {
        "input_dir": input_dir,
        "output_path": output_path,
        "model": model,
        "llm": llm,
        "files": state_cache.get("files", []),
        "grouped": state_cache.get("grouped", {}),
        "summary_profile": state_cache.get("summary_profile", ""),
        "writer_context": writer_context or state_cache.get("writer_context", ""),
        "letter_full": state_cache.get("letter_full", ""),
    }

    for step in STEP_ORDER:
        if _is_step_done(cache_dir, step) and not force:
            continue
        state = _run_single_step(step, state)
        _save_state(cache_dir, state)
        _save_step_output(cache_dir, step, state)

    # Save final state to DB
    if project_id:
        db.save_letter_state(
            project_id,
            files_data=state.get("files", []),
            summary_profile=state.get("summary_profile", ""),
            writer_context=state.get("writer_context", ""),
            letter_content=state.get("letter_full", ""),
            step_ingest=True,
            step_summary=True,
            step_writer=True,
        )

    return jsonify({"letter": state.get("letter_full", ""), "output_path": output_path})


@app.post("/api/run_add_file")
def run_add_file():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_path = payload.get("output", os.path.join("output", "letter.txt"))
    file_ref = payload.get("file")
    model = payload.get("model") or get_vision_model()  # reads input files (images/PDFs)
    writer_context = (payload.get("writer_context") or "").strip()

    if not file_ref:
        return jsonify({"error": "missing_file"}), 400

    resolved_path = _resolve_input_file_path(input_dir, str(file_ref))
    if not resolved_path:
        return jsonify({"error": "file_not_found"}), 404

    cache_dir = _cache_dir(output_path)
    state_cache = _load_state(cache_dir)
    llm = ChatOpenAI(model=model, temperature=0)
    state: GraphState = {
        "input_dir": input_dir,
        "output_path": output_path,
        "model": model,
        "llm": llm,
        "files": state_cache.get("files", []),
        "grouped": state_cache.get("grouped", {}),
        "summary_profile": state_cache.get("summary_profile", ""),
        "writer_context": writer_context or state_cache.get("writer_context", ""),
        "letter_full": state_cache.get("letter_full", ""),
    }

    filename = os.path.basename(resolved_path)
    text = extract_text_with_openai(llm, resolved_path)
    new_file = {
        "path": resolved_path,
        "name": filename,
        "text": text,
        "domain": detect_domain(filename),
    }
    state["files"] = _upsert_file_record(state.get("files", []), new_file)
    _save_state(cache_dir, state)
    _save_step_output(cache_dir, "ingest", state)

    for step in ["summary", "writer"]:
        state = _run_single_step(step, state)
        _save_state(cache_dir, state)
        _save_step_output(cache_dir, step, state)

    return jsonify(
        {
            "status": "done",
            "added_file": os.path.relpath(resolved_path, input_dir).replace("\\", "/"),
            "summary_profile": state.get("summary_profile", ""),
            "letter": state.get("letter_full", ""),
            "output_path": output_path,
        }
    )


@app.post("/api/itinerary/run")
def run_itinerary():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_path = payload.get("output", os.path.join("output", "itinerary.html"))
    flight_file = payload.get("flight_file")
    hotel_file = payload.get("hotel_file")
    from_db = payload.get("from_db", False)
    model = payload.get("model") or get_text_model()  # itinerary generation (text reasoning)
    project_id = payload.get("project_id")

    cache_dir = _cache_dir(output_path)
    summary_profile = (payload.get("summary_profile") or "").strip()
    if not summary_profile:
        summary_path = os.path.join(cache_dir, "itinerary_summary.txt")
        if os.path.exists(summary_path):
            with open(summary_path, "r", encoding="utf-8") as f:
                summary_profile = f.read().strip()
    # If still empty, try to build from trip info (make it optional)
    if not summary_profile and project_id:
        ti = db.get_latest_trip_info(int(project_id))
        if ti and ti.get("data"):
            d = ti["data"]
            parts = []
            if d.get("guest_names"):
                names = d["guest_names"] if isinstance(d["guest_names"], list) else [d["guest_names"]]
                parts.append("- participants: " + ", ".join(str(n) for n in names))
            if d.get("travel_start_date"):
                parts.append(f"- travel_start_date: {d['travel_start_date']}")
            if d.get("travel_end_date"):
                parts.append(f"- travel_end_date: {d['travel_end_date']}")
            if d.get("travel_purpose"):
                parts.append(f"- travel_purpose: {d['travel_purpose']}")
            if parts:
                summary_profile = "\n".join(parts)
    if not summary_profile:
        summary_profile = "Create itinerary from the provided flight and hotel booking data."

    llm = ChatOpenAI(model=model, temperature=0)

    # ── Load flight/hotel text from DB or files ──
    if from_db and project_id:
        booking = db.get_latest_booking(int(project_id))
        if not booking:
            return jsonify({"error": "no_booking_in_db", "message": "Không tìm thấy booking trong database. Hãy tạo booking AI trước."}), 400
        # Extract text from HTML (strip tags for AI processing)
        import re as _re_it
        def _html_to_text(html_str):
            text = _re_it.sub(r'<style[^>]*>.*?</style>', '', html_str, flags=_re_it.DOTALL)
            text = _re_it.sub(r'<script[^>]*>.*?</script>', '', text, flags=_re_it.DOTALL)
            text = _re_it.sub(r'<[^>]+>', ' ', text)
            text = _re_it.sub(r'\s+', ' ', text).strip()
            return text

        flight_text = _html_to_text(booking.get("flight_html", ""))
        # Combine all hotel HTMLs
        hotel_htmls = booking.get("hotel_htmls", [])
        hotel_text = "\n\n---\n\n".join(_html_to_text(h) for h in hotel_htmls)
    else:
        if not flight_file or not hotel_file:
            return jsonify({"error": "missing_files"}), 400
        flight_path = _resolve_input_file_path(input_dir, str(flight_file))
        hotel_path = _resolve_input_file_path(input_dir, str(hotel_file))
        if not flight_path or not hotel_path:
            return jsonify({"error": "missing_files"}), 400
        flight_text = extract_text_with_openai(llm, flight_path)
        hotel_text = extract_text_with_openai(llm, hotel_path)

    itinerary = itinerary_writer(llm, flight_text, hotel_text, summary_profile)

    # Save to file cache
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(itinerary)
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "itinerary.html"), "w", encoding="utf-8") as f:
        f.write(itinerary)

    # Save to DB
    if project_id:
        ctx = db.get_latest_itinerary_context(int(project_id)) or {}
        db.save_itinerary_html(int(project_id), ctx, itinerary)

    return jsonify({"itinerary": itinerary, "output_path": output_path})


@app.post("/api/itinerary/run_stream")
def run_itinerary_stream():
    """Generate itinerary with SSE progress streaming."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_path = payload.get("output", os.path.join("output", "itinerary.html"))
    flight_file = payload.get("flight_file")
    hotel_file = payload.get("hotel_file")
    from_db = payload.get("from_db", False)
    model = payload.get("model") or get_text_model()
    project_id = payload.get("project_id")

    def generate():
        def send_event(step, msg, data=None):
            evt = {"step": step, "msg": msg}
            if data is not None:
                evt["data"] = data
            yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

        # Build summary profile
        cache_dir = _cache_dir(output_path)
        summary_profile = (payload.get("summary_profile") or "").strip()
        if not summary_profile:
            summary_path = os.path.join(cache_dir, "itinerary_summary.txt")
            if os.path.exists(summary_path):
                with open(summary_path, "r", encoding="utf-8") as f:
                    summary_profile = f.read().strip()
        if not summary_profile and project_id:
            ti = db.get_latest_trip_info(int(project_id))
            if ti and ti.get("data"):
                d = ti["data"]
                parts = []
                if d.get("guest_names"):
                    names = d["guest_names"] if isinstance(d["guest_names"], list) else [d["guest_names"]]
                    parts.append("- participants: " + ", ".join(str(n) for n in names))
                if d.get("travel_start_date"):
                    parts.append(f"- travel_start_date: {d['travel_start_date']}")
                if d.get("travel_end_date"):
                    parts.append(f"- travel_end_date: {d['travel_end_date']}")
                if d.get("travel_purpose"):
                    parts.append(f"- travel_purpose: {d['travel_purpose']}")
                if parts:
                    summary_profile = "\n".join(parts)
        if not summary_profile:
            summary_profile = "Create itinerary from the provided flight and hotel booking data."

        llm = ChatOpenAI(model=model, temperature=0)

        try:
            # Step 1: Load booking data
            yield from send_event(1, "⏳ Đang tải dữ liệu booking...")

            import re as _re_it
            def _html_to_text(html_str):
                text = _re_it.sub(r'<style[^>]*>.*?</style>', '', html_str, flags=_re_it.DOTALL)
                text = _re_it.sub(r'<script[^>]*>.*?</script>', '', text, flags=_re_it.DOTALL)
                text = _re_it.sub(r'<[^>]+>', ' ', text)
                text = _re_it.sub(r'\s+', ' ', text).strip()
                return text

            if from_db and project_id:
                booking = db.get_latest_booking(int(project_id))
                if not booking:
                    yield from send_event(-1, "❌ Không tìm thấy booking trong database")
                    return
                yield from send_event(1, "✅ Đã tải booking từ database")

                # Step 2: Extract text
                yield from send_event(2, "⏳ Đang trích xuất nội dung booking...")
                flight_text = _html_to_text(booking.get("flight_html", ""))
                hotel_htmls = booking.get("hotel_htmls", [])
                hotel_text = "\n\n---\n\n".join(_html_to_text(h) for h in hotel_htmls)
                yield from send_event(2, "✅ Trích xuất nội dung hoàn tất")
            else:
                if not flight_file or not hotel_file:
                    yield from send_event(-1, "❌ Vui lòng chọn đủ file vé máy bay và khách sạn")
                    return
                flight_path = _resolve_input_file_path(input_dir, str(flight_file))
                hotel_path = _resolve_input_file_path(input_dir, str(hotel_file))
                if not flight_path or not hotel_path:
                    yield from send_event(-1, "❌ Không tìm thấy file đã chọn")
                    return
                yield from send_event(1, "✅ Đã tìm thấy file")

                yield from send_event(2, "⏳ AI đang đọc vé máy bay & khách sạn...")
                flight_text = extract_text_with_openai(llm, flight_path)
                hotel_text = extract_text_with_openai(llm, hotel_path)
                yield from send_event(2, "✅ Đọc nội dung file hoàn tất")

            # Step 3: Generate itinerary
            yield from send_event(3, "⏳ AI đang viết lịch trình chi tiết...")
            itinerary = itinerary_writer(llm, flight_text, hotel_text, summary_profile)
            yield from send_event(3, "✅ Viết lịch trình hoàn tất")

            # Step 4: Save
            yield from send_event(4, "⏳ Đang lưu kết quả...")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(itinerary)
            os.makedirs(cache_dir, exist_ok=True)
            with open(os.path.join(cache_dir, "itinerary.html"), "w", encoding="utf-8") as f:
                f.write(itinerary)
            if project_id:
                ctx = db.get_latest_itinerary_context(int(project_id)) or {}
                db.save_itinerary_html(int(project_id), ctx, itinerary)
            yield from send_event(4, "✅ Đã lưu")

            # Final result
            yield from send_event(5, "✅ Hoàn tất!", {"itinerary": itinerary, "output_path": output_path})

        except Exception as e:
            yield from send_event(-1, f"❌ Lỗi: {str(e)}")

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@app.get("/api/booking/latest_html")
def get_latest_booking_html():
    """Return the latest booking HTML from DB for use in itinerary creation."""
    project_id = request.args.get("project_id")
    if not project_id:
        return jsonify({"error": "project_id required"}), 400
    booking = db.get_latest_booking(int(project_id))
    if not booking:
        return jsonify({"has_booking": False})
    return jsonify({
        "has_booking": True,
        "hotel_htmls": booking.get("hotel_htmls", []),
        "flight_html": booking.get("flight_html", ""),
        "created_at": booking.get("created_at"),
    })


# ==================== BOOKING GENERATOR ENDPOINTS ====================

from datetime import datetime, timedelta
from booking.generator import (
    generate_all_bookings,
    fill_hotel_template,
    fill_flight_template,
    generate_bookings_from_ai,
)
from booking.ai_agent import (
    DEFAULT_TRIP_INFO,
    extract_trip_info,
    ai_select_bookings,
    generate_ai_booking,
)


@app.post("/api/booking/generate")
def generate_booking():
    """Generate hotel and flight booking confirmations."""
    payload = request.get_json(force=True) or {}
    
    destination = payload.get("destination", "Australia")
    num_days = int(payload.get("num_days", 10))
    guest_name = payload.get("guest_name", "")
    origin_airport = payload.get("origin_airport", "HAN")
    output_dir = payload.get("output_dir", "output")
    
    # Get guest name from summary if not provided
    if not guest_name:
        guest_name = "NGUYEN VAN A"
    
    # Calculate start date (3 months from now by default)
    start_date_str = payload.get("start_date")
    if start_date_str:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    else:
        start_date = datetime.now() + timedelta(days=90)
    
    # Generate bookings
    hotel_bookings, flight_booking = generate_all_bookings(
        destination=destination,
        num_days=num_days,
        guest_name=guest_name,
        origin_airport=origin_airport,
        start_date=start_date
    )
    
    # Fill templates and save
    os.makedirs(output_dir, exist_ok=True)
    
    # Hotel template path
    hotel_template_path = os.path.join(
        os.path.dirname(__file__), 
        "templates", 
        "hotel_booking.html"
    )
    
    # Flight template path
    flight_template_path = os.path.join(
        os.path.dirname(__file__),
        "templates",
        "flight_booking.html"
    )
    
    # Generate hotel HTMLs
    hotel_htmls = []
    for i, booking in enumerate(hotel_bookings, 1):
        if os.path.exists(hotel_template_path):
            html = fill_hotel_template(hotel_template_path, booking)
        else:
            # Fallback: return JSON as HTML
            html = f"<pre>{json.dumps(booking, indent=2, ensure_ascii=False)}</pre>"
        
        output_path = os.path.join(output_dir, f"booking_hotel_{i}.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        hotel_htmls.append({"path": output_path, "html": html, "data": booking})
    
    # Generate flight HTML
    if os.path.exists(flight_template_path):
        flight_html = fill_flight_template(flight_template_path, flight_booking)
    else:
        flight_html = f"<pre>{json.dumps(flight_booking, indent=2, ensure_ascii=False)}</pre>"
    
    flight_output_path = os.path.join(output_dir, "booking_flight.html")
    with open(flight_output_path, "w", encoding="utf-8") as f:
        f.write(flight_html)
    
    return jsonify({
        "status": "success",
        "hotel_bookings": [h["data"] for h in hotel_htmls],
        "hotel_htmls": [h["html"] for h in hotel_htmls],
        "hotel_paths": [h["path"] for h in hotel_htmls],
        "flight_booking": flight_booking,
        "flight_html": flight_html,
        "flight_path": flight_output_path,
        "guest_name": guest_name,
        "destination": destination,
        "num_days": num_days,
        "start_date": start_date.strftime("%Y-%m-%d")
    })


@app.get("/api/booking/latest")
def get_booking_latest():
    """Get the latest generated booking files."""
    project_id = request.args.get("project_id", type=int)
    if project_id:
        bk = db.get_latest_booking(project_id)
        if bk:
            return jsonify({"hotel_htmls": bk["hotel_htmls"], "flight_html": bk["flight_html"]})
        return jsonify({"hotel_htmls": [], "flight_html": ""})
    output_dir = request.args.get("output_dir", "output")
    result = {"hotel_htmls": [], "flight_html": ""}
    i = 1
    while True:
        hotel_path = os.path.join(output_dir, f"booking_hotel_{i}.html")
        if os.path.exists(hotel_path):
            with open(hotel_path, "r", encoding="utf-8") as f:
                result["hotel_htmls"].append(f.read())
            i += 1
        else:
            break
    flight_path = os.path.join(output_dir, "booking_flight.html")
    if os.path.exists(flight_path):
        with open(flight_path, "r", encoding="utf-8") as f:
            result["flight_html"] = f.read()
    return jsonify(result)


@app.get("/api/booking/destinations")
def get_destinations():
    """Get available destinations from the hotels database."""
    from booking.generator import load_hotels_database
    
    hotels_db = load_hotels_database()
    destinations = [key for key in hotels_db.keys() if key != "flights"]
    
    return jsonify({"destinations": destinations})


# ==================== AI BOOKING ENDPOINTS ====================

@app.get("/api/booking/filtered-files")
def booking_filtered_files():
    """List files in input dir, categorized by trip-info prefix."""
    input_dir = request.args.get("input_dir", "input")
    if not os.path.isdir(input_dir):
        return jsonify({"files": [], "matched": [], "other": []})

    PREFIXES = {
        "OVERVIEW": "🌍 Tổng quan",
        "TONG QUAN": "🌍 Tổng quan",
        "PERSONAL": "👤 Hồ sơ cá nhân",
        "HO SO CA NHAN": "👤 Hồ sơ cá nhân",
        "PURPOSE": "🎯 Mục đích",
        "MUC DICH CHUYEN DI": "🎯 Mục đích",
    }
    matched = []
    other = []
    for root, _, filenames in os.walk(input_dir):
        for fname in sorted(filenames):
            stem = os.path.splitext(fname)[0]
            normalized = __import__("re").sub(r"[\s\-_]+", " ", stem.upper()).strip()
            rel = os.path.relpath(os.path.join(root, fname), input_dir).replace("\\", "/")
            found_prefix = None
            found_label = None
            for prefix, label in PREFIXES.items():
                if normalized.startswith(prefix):
                    found_prefix = prefix
                    found_label = label
                    break
            if found_prefix:
                matched.append({"filename": fname, "path": rel, "prefix": found_prefix, "label": found_label})
            else:
                other.append({"filename": fname, "path": rel})

    return jsonify({"matched": matched, "other": other, "total": len(matched) + len(other)})


@app.post("/api/booking/extract_trip")
def extract_trip():
    """Extract trip information from input files."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    model = payload.get("model") or get_vision_model()  # reads input files (may contain images)
    project_id = payload.get("project_id")

    llm = ChatOpenAI(model=model, temperature=0)

    try:
        trip_info = extract_trip_info(llm, input_dir)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if not isinstance(trip_info, dict):
        trip_info = dict(DEFAULT_TRIP_INFO)

    # Cache trip info to file
    cache_dir = _cache_dir(os.path.join("output", "letter.txt"))
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "booking_trip_info.json"), "w", encoding="utf-8") as f:
        json.dump(trip_info, f, ensure_ascii=False, indent=2)
    booking_cache = os.path.join(cache_dir, "ai_booking_data.json")
    if os.path.exists(booking_cache):
        os.remove(booking_cache)

    # Save to DB
    if project_id:
        db.save_trip_info(int(project_id), trip_info)
        # Update input hash
        input_hash = db.compute_input_hash(input_dir)
        db.update_project(int(project_id), input_hash=input_hash)

    return jsonify({"status": "success", "trip_info": trip_info})


@app.get("/api/booking/trip/latest")
def get_booking_trip_latest():
    """Load cached trip info for editing in frontend."""
    project_id = request.args.get("project_id", type=int)
    if project_id:
        ti = db.get_latest_trip_info(project_id)
        data = ti["data"] if ti else dict(DEFAULT_TRIP_INFO)
        return jsonify({"trip_info": data})
    cache_dir = _cache_dir(os.path.join("output", "letter.txt"))
    trip_path = os.path.join(cache_dir, "booking_trip_info.json")
    if not os.path.exists(trip_path):
        return jsonify({"trip_info": dict(DEFAULT_TRIP_INFO)})
    with open(trip_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    merged = dict(DEFAULT_TRIP_INFO)
    if isinstance(data, dict):
        merged.update(data)
    return jsonify({"trip_info": merged})


@app.post("/api/booking/trip/save")
def save_booking_trip():
    """Save edited trip info from frontend."""
    payload = request.get_json(force=True) or {}
    trip_info = payload.get("trip_info") or {}
    project_id = payload.get("project_id")
    if not isinstance(trip_info, dict):
        return jsonify({"error": "invalid_trip_info"}), 400

    merged = dict(DEFAULT_TRIP_INFO)
    merged.update(trip_info)

    # Save to file cache
    cache_dir = _cache_dir(os.path.join("output", "letter.txt"))
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "booking_trip_info.json"), "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    booking_cache = os.path.join(cache_dir, "ai_booking_data.json")
    if os.path.exists(booking_cache):
        os.remove(booking_cache)

    # Save to DB
    if project_id:
        db.save_trip_info(int(project_id), merged)

    return jsonify({"status": "success", "trip_info": merged})


@app.post("/api/booking/ai_generate")
def ai_generate_booking():
    """Generate bookings using AI. Uses cached booking data if available to save tokens."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_dir = payload.get("output_dir", "output")
    model = payload.get("model") or get_text_model()  # booking uses text reasoning
    force_new = payload.get("force_new", False)
    trip_info_override = payload.get("trip_info")
    project_id = payload.get("project_id")

    cache_dir = _cache_dir(os.path.join("output", "letter.txt"))
    booking_cache_path = os.path.join(cache_dir, "ai_booking_data.json")
    trip_cache_path = os.path.join(cache_dir, "booking_trip_info.json")

    # If user edited trip info on frontend, persist and force new booking.
    if isinstance(trip_info_override, dict):
        merged_trip = dict(DEFAULT_TRIP_INFO)
        merged_trip.update(trip_info_override)
        os.makedirs(cache_dir, exist_ok=True)
        with open(trip_cache_path, "w", encoding="utf-8") as f:
            json.dump(merged_trip, f, ensure_ascii=False, indent=2)
        force_new = True
        if os.path.exists(booking_cache_path):
            os.remove(booking_cache_path)

    # --- Check for cached booking data first (skip AI to save tokens) ---
    booking_data = None
    trip_info = None
    used_cache = False

    if not force_new and os.path.exists(booking_cache_path):
        with open(booking_cache_path, "r", encoding="utf-8") as f:
            booking_data = json.load(f)
        if os.path.exists(trip_cache_path):
            with open(trip_cache_path, "r", encoding="utf-8") as f:
                trip_info = json.load(f)
        used_cache = True

    # --- If no cache, call AI ---
    if not booking_data:
        if os.path.exists(trip_cache_path):
            with open(trip_cache_path, "r", encoding="utf-8") as f:
                trip_info = json.load(f)

        llm = ChatOpenAI(model=model, temperature=0)

        try:
            trip_info, booking_data = generate_ai_booking(llm, input_dir, trip_info)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": f"Lỗi AI: {str(e)}"}), 500

        # Cache booking data for next time
        os.makedirs(cache_dir, exist_ok=True)
        with open(booking_cache_path, "w", encoding="utf-8") as f:
            json.dump(booking_data, f, ensure_ascii=False, indent=2)

    # Template paths
    hotel_template_path = os.path.join(
        os.path.dirname(__file__),
        "templates",
        "hotel_booking.html"
    )
    flight_template_path = os.path.join(
        os.path.dirname(__file__),
        "templates",
        "flight_booking.html"
    )

    try:
        # Generate HTML files from AI decisions
        result = generate_bookings_from_ai(
            ai_booking_data=booking_data,
            hotel_template_path=hotel_template_path,
            flight_template_path=flight_template_path,
            output_dir=output_dir,
        )

        # Save to DB
        if project_id:
            db.save_booking(
                int(project_id),
                booking_data=booking_data,
                hotel_htmls=result["hotel_htmls"],
                flight_html=result["flight_html"],
                reasoning=booking_data.get("reasoning", ""),
            )

        return jsonify({
            "status": "success",
            "used_cache": used_cache,
            "trip_info": trip_info,
            "booking_data": {
                "hotels": result["hotel_data"],
                "reasoning": booking_data.get("reasoning", ""),
            },
            "hotel_htmls": result["hotel_htmls"],
            "hotel_paths": result["hotel_paths"],
            "flight_html": result["flight_html"],
            "flight_path": result["flight_path"],
        })
    except Exception as e:
        import traceback
        return jsonify({"error": "Lỗi khi tạo HTML: " + str(e), "traceback": traceback.format_exc()}), 500


@app.post("/api/booking/ai_generate_stream")
def ai_generate_booking_stream():
    """Generate bookings using AI with SSE progress streaming."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_dir = payload.get("output_dir", "output")
    model = payload.get("model") or get_text_model()
    force_new = payload.get("force_new", False)
    trip_info_override = payload.get("trip_info")
    project_id = payload.get("project_id")

    cache_dir = _cache_dir(os.path.join("output", "letter.txt"))
    booking_cache_path = os.path.join(cache_dir, "ai_booking_data.json")
    trip_cache_path = os.path.join(cache_dir, "booking_trip_info.json")

    def generate():
        import time as _time

        def send_event(step, msg, data=None):
            evt = {"step": step, "msg": msg}
            if data is not None:
                evt["data"] = data
            yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

        nonlocal force_new

        # If user edited trip info on frontend, persist and force new booking.
        if isinstance(trip_info_override, dict):
            merged_trip = dict(DEFAULT_TRIP_INFO)
            merged_trip.update(trip_info_override)
            os.makedirs(cache_dir, exist_ok=True)
            with open(trip_cache_path, "w", encoding="utf-8") as f:
                json.dump(merged_trip, f, ensure_ascii=False, indent=2)
            force_new = True
            if os.path.exists(booking_cache_path):
                os.remove(booking_cache_path)

        booking_data = None
        trip_info = None
        used_cache = False

        # Check cache
        if not force_new and os.path.exists(booking_cache_path):
            yield from send_event(1, "✅ Đã tìm thấy dữ liệu cache, bỏ qua AI")
            with open(booking_cache_path, "r", encoding="utf-8") as f:
                booking_data = json.load(f)
            if os.path.exists(trip_cache_path):
                with open(trip_cache_path, "r", encoding="utf-8") as f:
                    trip_info = json.load(f)
            used_cache = True

        # If no cache, call AI with progress
        if not booking_data:
            if os.path.exists(trip_cache_path):
                with open(trip_cache_path, "r", encoding="utf-8") as f:
                    trip_info = json.load(f)

            llm = ChatOpenAI(model=model, temperature=0)

            def progress_cb(step, msg):
                pass  # Can't yield inside callback; we handle steps inline

            try:
                # Step 1: Extract or load trip info
                if not trip_info:
                    yield from send_event(1, "⏳ Đang trích xuất thông tin chuyến đi từ file...")
                    trip_info = extract_trip_info(llm, input_dir)
                    yield from send_event(1, "✅ Trích xuất thông tin chuyến đi hoàn tất")
                else:
                    yield from send_event(1, "✅ Đã có thông tin chuyến đi")

                if not trip_info or not trip_info.get("destination_country"):
                    yield from send_event(-1, "❌ Không thể trích xuất thông tin chuyến đi")
                    return

                # Step 2: AI select bookings (use mini model for cost savings)
                yield from send_event(2, "⏳ AI đang chọn khách sạn & chuyến bay...")
                booking_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
                booking_data = ai_select_bookings(booking_llm, trip_info)
                yield from send_event(2, "✅ AI đã chọn xong khách sạn & chuyến bay")

                if not booking_data or not booking_data.get("hotels"):
                    yield from send_event(-1, "❌ AI không thể tạo booking")
                    return

                # Cache
                os.makedirs(cache_dir, exist_ok=True)
                with open(booking_cache_path, "w", encoding="utf-8") as f:
                    json.dump(booking_data, f, ensure_ascii=False, indent=2)

            except Exception as e:
                yield from send_event(-1, f"❌ Lỗi AI: {str(e)}")
                return

        # Step 3: Generate HTML
        yield from send_event(3, "⏳ Đang tạo file HTML booking...")

        hotel_template_path = os.path.join(os.path.dirname(__file__), "templates", "hotel_booking.html")
        flight_template_path = os.path.join(os.path.dirname(__file__), "templates", "flight_booking.html")

        try:
            result = generate_bookings_from_ai(
                ai_booking_data=booking_data,
                hotel_template_path=hotel_template_path,
                flight_template_path=flight_template_path,
                output_dir=output_dir,
            )

            if project_id:
                db.save_booking(
                    int(project_id),
                    booking_data=booking_data,
                    hotel_htmls=result["hotel_htmls"],
                    flight_html=result["flight_html"],
                    reasoning=booking_data.get("reasoning", ""),
                )

            yield from send_event(3, "✅ Tạo HTML booking hoàn tất")

            # Final result
            final = {
                "status": "success",
                "used_cache": used_cache,
                "trip_info": trip_info,
                "booking_data": {
                    "hotels": result["hotel_data"],
                    "reasoning": booking_data.get("reasoning", ""),
                },
                "hotel_htmls": result["hotel_htmls"],
                "hotel_paths": result["hotel_paths"],
                "flight_html": result["flight_html"],
                "flight_path": result["flight_path"],
            }
            yield from send_event(4, "✅ Hoàn tất!", final)

        except Exception as e:
            import traceback
            yield from send_event(-1, f"❌ Lỗi tạo HTML: {str(e)}")

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })

# ==================== AI PDF SPLITTER ENDPOINTS ====================

import uuid
import shutil
import zipfile
import threading
from pathlib import Path as SplitterPath

from pdf_tools.pdf_service import pdf_to_images, get_page_count, create_output_files
from pdf_tools.ai_service import classify_all_pages

# Directories for AI splitter (defaults, used as fallback)
SPLITTER_UPLOAD_DIR = SplitterPath(__file__).parent / "splitter_uploads"
SPLITTER_OUTPUT_DIR = SplitterPath(__file__).parent / "splitter_outputs"
SPLITTER_UPLOAD_DIR.mkdir(exist_ok=True)
SPLITTER_OUTPUT_DIR.mkdir(exist_ok=True)


def _splitter_upload_dir(project_id=None):
    """Return project-scoped or global splitter upload directory."""
    if project_id:
        dirs = _get_project_dirs(project_id)
        d = SplitterPath(dirs["splitter_uploads"])
        d.mkdir(parents=True, exist_ok=True)
        return d
    return SPLITTER_UPLOAD_DIR


def _splitter_output_dir(project_id=None):
    """Return project-scoped or global splitter output directory."""
    if project_id:
        dirs = _get_project_dirs(project_id)
        d = SplitterPath(dirs["splitter_outputs"])
        d.mkdir(parents=True, exist_ok=True)
        return d
    return SPLITTER_OUTPUT_DIR


# In-memory job tracking for AI splitter
splitter_jobs: Dict[str, Dict] = {}


def _run_splitter_job(file_id: str):
    """Run AI PDF splitting in a background thread with its own event loop."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_process_splitter_job(file_id))
    finally:
        loop.close()


async def _process_splitter_job(file_id: str):
    """Process a PDF file: convert → classify → split."""
    job = splitter_jobs[file_id]
    try:
        # Step 1: Convert PDF pages to images
        job["status"] = "converting"
        images = pdf_to_images(job["file_path"])

        # Step 2: Classify each page with AI
        job["status"] = "classifying"

        async def progress_callback(page_num, total, result):
            job["current_page"] = page_num
            job["classifications"].append({
                "page": page_num,
                "document_type_en": result.get("document_type_en", ""),
                "person_name_en": result.get("person_name_en", ""),
                "is_continuation": result.get("is_continuation", False),
            })

        classifications = await classify_all_pages(
            images, progress_callback=progress_callback
        )

        # Update with post-processed data
        job["classifications"] = []
        for idx, cls in enumerate(classifications):
            job["classifications"].append({
                "page": idx + 1,
                "document_type_en": cls.get("document_type_en", ""),
                "person_name_en": cls.get("person_name_en", ""),
                "is_continuation": cls.get("is_continuation", False),
            })

        # Step 3: Create output files
        job["status"] = "splitting"
        _out_base = SplitterPath(job.get("output_dir") or str(SPLITTER_OUTPUT_DIR))
        _out_base.mkdir(parents=True, exist_ok=True)
        job_output_dir = str(_out_base / file_id)
        output_files = create_output_files(
            job["file_path"], classifications, job_output_dir
        )
        job["output_files"] = output_files

        # Save source metadata for persistent display
        source_meta = {"source_filename": job["filename"], "source_type": "ai"}
        with open(os.path.join(job_output_dir, "_source.json"), "w", encoding="utf-8") as mf:
            json.dump(source_meta, mf, ensure_ascii=False)

        # Step 4: Create ZIP
        zip_path = str(_out_base / f"{file_id}.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in output_files:
                zf.write(f["path"], f["filename"])
        job["zip_path"] = zip_path
        job["status"] = "completed"

    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        print(f"[AI Splitter] Error processing {file_id}: {e}")


@app.get("/api/ai-splitter/list")
def splitter_list_files():
    """List PDF files already in splitter_uploads folder."""
    pid = request.args.get("project_id")
    upload_dir = str(_splitter_upload_dir(int(pid) if pid else None))
    if not os.path.isdir(upload_dir):
        return jsonify({"files": []})
    files = []
    for fname in sorted(os.listdir(upload_dir)):
        path = os.path.join(upload_dir, fname)
        if os.path.isfile(path) and fname.lower().endswith(".pdf"):
            files.append({"filename": fname, "size": os.path.getsize(path)})
    return jsonify({"files": files})


@app.post("/api/ai-splitter/delete")
def splitter_delete_file():
    """Delete a single file from splitter_uploads."""
    payload = request.get_json(force=True) or {}
    filename = payload.get("filename", "")
    pid = payload.get("project_id")
    if not filename:
        return jsonify({"error": "no_filename"}), 400
    upload_dir = _splitter_upload_dir(int(pid) if pid else None)
    file_path = upload_dir / filename
    if not file_path.is_file():
        return jsonify({"error": "file_not_found"}), 404
    os.remove(str(file_path))
    return jsonify({"deleted": filename})


@app.post("/api/ai-splitter/delete-all")
def splitter_delete_all():
    """Delete all PDF files from splitter_uploads."""
    payload = request.get_json(force=True) or {}
    pid = payload.get("project_id")
    upload_dir = str(_splitter_upload_dir(int(pid) if pid else None))
    count = 0
    if os.path.isdir(upload_dir):
        for fname in os.listdir(upload_dir):
            fpath = os.path.join(upload_dir, fname)
            if os.path.isfile(fpath) and fname.lower().endswith(".pdf"):
                os.remove(fpath)
                count += 1
    return jsonify({"deleted_count": count})


@app.post("/api/ai-splitter/process-local")
def splitter_process_local():
    """Process a PDF already in splitter_uploads (no upload needed)."""
    payload = request.get_json(force=True) or {}
    filename = payload.get("filename", "")
    pid = payload.get("project_id")
    if not filename:
        return jsonify({"error": "no_filename"}), 400

    upload_dir = _splitter_upload_dir(int(pid) if pid else None)
    src_path = upload_dir / filename
    if not src_path.is_file():
        return jsonify({"error": "file_not_found"}), 404

    import threading

    file_id = uuid.uuid4().hex[:8]
    # Copy to sub-folder (same structure as upload flow)
    job_dir = upload_dir / file_id
    job_dir.mkdir(exist_ok=True)
    file_path = job_dir / filename
    shutil.copy2(str(src_path), str(file_path))

    page_count = get_page_count(str(file_path))

    # Store project_id in job so output goes to the right place
    output_dir = _splitter_output_dir(int(pid) if pid else None)
    splitter_jobs[file_id] = {
        "status": "uploaded",
        "filename": filename,
        "file_path": str(file_path),
        "page_count": page_count,
        "current_page": 0,
        "classifications": [],
        "output_files": [],
        "error": None,
        "zip_path": None,
        "output_dir": str(output_dir),
    }

    # Run in background thread (same as upload flow)
    thread = threading.Thread(target=_run_splitter_job, args=(file_id,), daemon=True)
    thread.start()

    return jsonify({"file_id": file_id, "filename": filename, "page_count": page_count})


@app.post("/api/ai-splitter/upload")
def splitter_upload():
    if "file" not in request.files:
        return jsonify({"error": "no_file"}), 400
    file = request.files["file"]
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "not_pdf"}), 400

    pid = request.form.get("project_id")
    upload_dir = _splitter_upload_dir(int(pid) if pid else None)
    output_dir = _splitter_output_dir(int(pid) if pid else None)

    file_id = uuid.uuid4().hex[:8]
    job_dir = upload_dir / file_id
    job_dir.mkdir(exist_ok=True)
    file_path = job_dir / file.filename
    file.save(str(file_path))

    page_count = get_page_count(str(file_path))

    splitter_jobs[file_id] = {
        "status": "uploaded",
        "filename": file.filename,
        "file_path": str(file_path),
        "output_dir": str(output_dir),
        "page_count": page_count,
        "current_page": 0,
        "classifications": [],
        "output_files": [],
        "error": None,
        "zip_path": None,
    }

    return jsonify({
        "file_id": file_id,
        "filename": file.filename,
        "page_count": page_count,
    })


@app.post("/api/ai-splitter/process/<file_id>")
def splitter_process(file_id: str):
    if file_id not in splitter_jobs:
        return jsonify({"error": "not_found"}), 404
    job = splitter_jobs[file_id]
    if job["status"] in ("processing", "classifying", "converting", "splitting"):
        return jsonify({"message": "already_processing"})
    if job["status"] == "completed":
        return jsonify({"message": "already_completed"})

    job["status"] = "processing"
    job["current_page"] = 0
    job["classifications"] = []
    job["output_files"] = []
    job["error"] = None

    # Run in background thread (separate event loop for async code)
    t = threading.Thread(target=_run_splitter_job, args=(file_id,), daemon=True)
    t.start()

    return jsonify({"message": "processing_started", "file_id": file_id})


@app.get("/api/ai-splitter/status/<file_id>")
def splitter_status(file_id: str):
    if file_id not in splitter_jobs:
        return jsonify({"error": "not_found"}), 404
    job = splitter_jobs[file_id]
    resp = {
        "file_id": file_id,
        "filename": job["filename"],
        "status": job["status"],
        "page_count": job["page_count"],
        "current_page": job["current_page"],
        "error": job["error"],
        "classifications": job.get("classifications", []),
    }
    if job["status"] == "completed":
        resp["output_files"] = [
            {
                "filename": f["filename"],
                "document_type": f["document_type"],
                "person_name": f["person_name"],
                "pages": f["pages"],
            }
            for f in job["output_files"]
        ]
    return jsonify(resp)


@app.get("/api/ai-splitter/download/<file_id>/<filename>")
def splitter_download_single(file_id: str, filename: str):
    # Check job's output_dir first (project-scoped), then fall back to global
    out_dir = None
    if file_id in splitter_jobs:
        out_dir = SplitterPath(splitter_jobs[file_id].get("output_dir", str(SPLITTER_OUTPUT_DIR)))
    else:
        # Try project-scoped dir from query param
        pid = request.args.get("project_id")
        out_dir = _splitter_output_dir(int(pid) if pid else None)
    file_path = out_dir / file_id / filename
    if not file_path.exists():
        # Fallback: try global
        file_path = SPLITTER_OUTPUT_DIR / file_id / filename
        out_dir = SPLITTER_OUTPUT_DIR
    if not file_path.exists():
        return jsonify({"error": "file_not_found"}), 404
    return send_from_directory(str(out_dir / file_id), filename,
                                as_attachment=True, mimetype="application/pdf")


@app.get("/api/ai-splitter/view/<file_id>/<filename>")
def splitter_view_single(file_id: str, filename: str):
    """Serve PDF for in-browser viewing (as_attachment=False)."""
    out_dir = None
    if file_id in splitter_jobs:
        out_dir = SplitterPath(splitter_jobs[file_id].get("output_dir", str(SPLITTER_OUTPUT_DIR)))
    else:
        pid = request.args.get("project_id")
        out_dir = _splitter_output_dir(int(pid) if pid else None)
    file_path = out_dir / file_id / filename
    if not file_path.exists():
        file_path = SPLITTER_OUTPUT_DIR / file_id / filename
        out_dir = SPLITTER_OUTPUT_DIR
    if not file_path.exists():
        return jsonify({"error": "file_not_found"}), 404
    return send_from_directory(str(out_dir / file_id), filename,
                                as_attachment=False, mimetype="application/pdf")


@app.get("/api/ai-splitter/download-zip/<file_id>")
def splitter_download_zip(file_id: str):
    if file_id not in splitter_jobs:
        return jsonify({"error": "not_found"}), 404
    job = splitter_jobs[file_id]
    if job["status"] != "completed" or not job.get("zip_path"):
        return jsonify({"error": "not_ready"}), 400
    zip_path = SplitterPath(job["zip_path"])
    return send_from_directory(str(zip_path.parent), zip_path.name,
                                as_attachment=True, mimetype="application/zip")


@app.get("/api/ai-splitter/list-outputs")
def splitter_list_outputs():
    """List ALL split output files across all splitter job folders (AI + manual).
    Used by Tab ② to pick a file to re-split manually."""
    pid = request.args.get("project_id")
    output_dir = str(_splitter_output_dir(int(pid) if pid else None))
    if not os.path.isdir(output_dir):
        return jsonify({"groups": []})

    groups = []
    for folder_name in sorted(os.listdir(output_dir)):
        folder_path = os.path.join(output_dir, folder_name)
        if not os.path.isdir(folder_path):
            continue
        files = []
        for fname in sorted(os.listdir(folder_path)):
            fpath = os.path.join(folder_path, fname)
            if os.path.isfile(fpath) and fname.lower().endswith(".pdf"):
                files.append({
                    "filename": fname,
                    "size": os.path.getsize(fpath),
                    "file_id": folder_name,
                })
        if files:
            is_manual = folder_name.startswith("manual_")
            # Read persistent source metadata
            source_name = ""
            source_meta_path = os.path.join(folder_path, "_source.json")
            if os.path.isfile(source_meta_path):
                try:
                    with open(source_meta_path, "r", encoding="utf-8") as mf:
                        meta = json.load(mf)
                    source_name = meta.get("source_filename", "")
                except Exception:
                    pass
            # Fallback to in-memory splitter_jobs
            if not source_name and not is_manual and folder_name in splitter_jobs:
                source_name = splitter_jobs[folder_name].get("filename", "")
            groups.append({
                "folder_id": folder_name,
                "source_type": "manual" if is_manual else "ai",
                "source_filename": source_name,
                "files": files,
            })
    return jsonify({"groups": groups})


@app.post("/api/manual-split/upload-and-split")
def manual_split_upload_and_split():
    """Upload a PDF from computer and split it manually.
    The uploaded file is stored temporarily, split into segments,
    and results go to splitter_outputs/manual_<uuid>/."""
    if "file" not in request.files:
        return jsonify({"error": "no_file"}), 400
    file = request.files["file"]
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "not_pdf"}), 400

    segments_json = request.form.get("segments", "[]")
    try:
        segments = json.loads(segments_json)
    except Exception:
        return jsonify({"error": "invalid_segments"}), 400
    if not isinstance(segments, list) or not segments:
        return jsonify({"error": "missing_segments"}), 400

    # Save uploaded file to temp location
    manual_id = f"manual_{uuid.uuid4().hex[:8]}"
    output_dir = str(SPLITTER_OUTPUT_DIR / manual_id)
    os.makedirs(output_dir, exist_ok=True)

    import tempfile
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, file.filename)
    file.save(tmp_path)

    try:
        reader = PdfReader(tmp_path)
    except Exception as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify({"error": "read_pdf_failed", "detail": str(exc)}), 500

    total_pages = len(reader.pages)
    created: list[dict[str, Any]] = []

    def _sanitize_name(value: str, fallback: str) -> str:
        text = (value or "").strip()
        text = re.sub(r"[\\/:*?\"<>|]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text or fallback

    def _pick_unique(dest_dir: str, stem: str, ext: str) -> str:
        candidate = os.path.join(dest_dir, f"{stem}{ext}")
        idx = 1
        while os.path.exists(candidate):
            candidate = os.path.join(dest_dir, f"{stem} ({idx}){ext}")
            idx += 1
        return candidate

    for seg in segments:
        if not isinstance(seg, dict):
            continue
        name = _sanitize_name(seg.get("output_name") or "", "DOCUMENT")
        try:
            s = int(seg.get("start_page"))
            e = int(seg.get("end_page"))
        except Exception:
            continue
        if s < 1 or e < 1 or s > total_pages or e > total_pages:
            continue
        if s > e:
            s, e = e, s
        writer = PdfWriter()
        for i in range(s - 1, e):
            writer.add_page(reader.pages[i])
        out_path = _pick_unique(output_dir, name, ".pdf")
        try:
            with open(out_path, "wb") as f:
                writer.write(f)
        except Exception:
            continue
        created.append(
            {
                "output_name": name,
                "start_page": s,
                "end_page": e,
                "to": os.path.relpath(out_path, output_dir).replace("\\", "/"),
                "file_id": manual_id,
            }
        )

    # Clean up temp
    shutil.rmtree(tmp_dir, ignore_errors=True)

    # Save source metadata for persistent display
    if created:
        source_meta = {"source_filename": file.filename, "source_type": "manual"}
        with open(os.path.join(output_dir, "_source.json"), "w", encoding="utf-8") as mf:
            json.dump(source_meta, mf, ensure_ascii=False)

    return jsonify(
        {
            "status": "done",
            "manual_id": manual_id,
            "output_dir": output_dir,
            "source": file.filename,
            "total_pages": total_pages,
            "segments": created,
        }
    )


@app.post("/api/manual-split/send-to-classifier")
def manual_split_send_to_classifier():
    """Send specific manual split results directly to classifier input.
    Use this when user uploads a file from computer and wants to send
    directly to classifier without going through the full pipeline."""
    payload = request.get_json(force=True) or {}
    manual_id = payload.get("manual_id", "")
    target_dir = payload.get("target_dir", os.path.join("phanloai", "input"))

    if not manual_id:
        return jsonify({"error": "missing_manual_id"}), 400

    source_dir = str(SPLITTER_OUTPUT_DIR / manual_id)
    if not os.path.isdir(source_dir):
        return jsonify({"error": "not_found"}), 404

    os.makedirs(target_dir, exist_ok=True)
    copied = []
    for fname in os.listdir(source_dir):
        fpath = os.path.join(source_dir, fname)
        if not os.path.isfile(fpath) or not fname.lower().endswith(".pdf"):
            continue
        dst = os.path.join(target_dir, fname)
        base, ext = os.path.splitext(fname)
        idx = 1
        while os.path.exists(dst):
            dst = os.path.join(target_dir, f"{base} ({idx}){ext}")
            idx += 1
        shutil.copy2(fpath, dst)
        copied.append(fname)

    return jsonify({"status": "done", "copied": copied, "count": len(copied), "target_dir": target_dir})


@app.post("/api/manual-split/get-page-count")
def manual_split_get_page_count():
    """Get page count of a file in splitter_outputs (for re-splitting from AI results)."""
    payload = request.get_json(force=True) or {}
    file_id = payload.get("file_id", "")
    filename = payload.get("filename", "")
    if not file_id or not filename:
        return jsonify({"error": "missing_params"}), 400
    file_path = SPLITTER_OUTPUT_DIR / file_id / filename
    if not file_path.is_file():
        return jsonify({"error": "file_not_found"}), 404
    try:
        count = get_page_count(str(file_path))
    except Exception as exc:
        return jsonify({"error": "read_failed", "detail": str(exc)}), 500
    return jsonify({"page_count": count, "filename": filename, "file_id": file_id})


@app.post("/api/manual-split/upload-get-page-count")
def manual_split_upload_get_page_count():
    """Upload a PDF and return its page count (for building split form)."""
    if "file" not in request.files:
        return jsonify({"error": "no_file"}), 400
    file = request.files["file"]
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "not_pdf"}), 400

    # Save to a temp location under splitter_uploads
    temp_id = f"temp_{uuid.uuid4().hex[:8]}"
    temp_dir = SPLITTER_UPLOAD_DIR / temp_id
    temp_dir.mkdir(exist_ok=True)
    file_path = temp_dir / file.filename
    file.save(str(file_path))

    try:
        count = get_page_count(str(file_path))
    except Exception as exc:
        shutil.rmtree(str(temp_dir), ignore_errors=True)
        return jsonify({"error": "read_failed", "detail": str(exc)}), 500

    return jsonify({
        "page_count": count,
        "filename": file.filename,
        "temp_id": temp_id,
        "temp_path": str(file_path),
    })



@app.post("/api/ai-splitter/merge-outputs")
def splitter_merge_outputs():
    """Merge multiple output PDF files into one.
    Expects JSON: { files: [{file_id, filename}, ...], output_name: "optional" }
    Merges in order, saves into the first file's folder, deletes originals."""
    payload = request.get_json(force=True) or {}
    files = payload.get("files", [])
    output_name = (payload.get("output_name") or "").strip()

    if not isinstance(files, list) or len(files) < 2:
        return jsonify({"error": "need_at_least_2_files"}), 400

    # Validate all files exist
    paths = []
    for f in files:
        fid = f.get("file_id", "")
        fname = f.get("filename", "")
        fpath = SPLITTER_OUTPUT_DIR / fid / fname
        if not fpath.is_file():
            return jsonify({"error": f"file_not_found: {fid}/{fname}"}), 404
        paths.append((fid, fname, str(fpath)))

    # Default output name = first file's name (without .pdf)
    if not output_name:
        first_name = os.path.splitext(files[0]["filename"])[0]
        output_name = first_name

    # Sanitize
    output_name = re.sub(r'[\\/:*?"<>|]+', ' ', output_name)
    output_name = re.sub(r'\s+', ' ', output_name).strip() or "Merged"

    # Merge PDFs
    writer = PdfWriter()
    for _, _, fpath in paths:
        try:
            reader = PdfReader(fpath)
            for page in reader.pages:
                writer.add_page(page)
        except Exception as exc:
            return jsonify({"error": f"read_failed: {fpath}", "detail": str(exc)}), 500

    # Save to first file's folder
    target_dir = str(SPLITTER_OUTPUT_DIR / files[0]["file_id"])
    out_filename = f"{output_name}.pdf"
    out_path = os.path.join(target_dir, out_filename)
    # Avoid overwriting
    idx = 1
    while os.path.exists(out_path):
        out_path = os.path.join(target_dir, f"{output_name} ({idx}).pdf")
        out_filename = f"{output_name} ({idx}).pdf"
        idx += 1

    try:
        with open(out_path, "wb") as f:
            writer.write(f)
    except Exception as exc:
        return jsonify({"error": "write_failed", "detail": str(exc)}), 500

    # Delete originals
    deleted = []
    for fid, fname, fpath in paths:
        try:
            os.remove(fpath)
            deleted.append(f"{fid}/{fname}")
        except Exception:
            pass

    return jsonify({
        "status": "done",
        "merged_file": out_filename,
        "file_id": files[0]["file_id"],
        "total_pages": len(writer.pages),
        "deleted": deleted,
    })


@app.post("/api/ai-splitter/clear-outputs")
def splitter_clear_outputs():
    """Delete ALL output folders in splitter_outputs/ (AI + manual).
    Also clears in-memory splitter_jobs."""
    payload = request.get_json(force=True) or {}
    pid = payload.get("project_id")
    output_dir = str(_splitter_output_dir(int(pid) if pid else None))
    deleted_count = 0
    if os.path.isdir(output_dir):
        for name in os.listdir(output_dir):
            path = os.path.join(output_dir, name)
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
                deleted_count += 1
            elif os.path.isfile(path):
                os.remove(path)  # remove .zip files etc.
                deleted_count += 1
    splitter_jobs.clear()
    return jsonify({"status": "done", "deleted_count": deleted_count})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)


