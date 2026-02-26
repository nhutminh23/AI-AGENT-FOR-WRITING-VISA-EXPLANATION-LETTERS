from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory
from langchain_openai import ChatOpenAI

from agents import (
    classify_files,
    detect_domain,
    domain_agent,
    extract_text_with_openai,
    ingest_files,
    itinerary_writer,
    letter_writer,
    risk_explanation_finder,
    _build_summary_profile,
)
from state import GraphState


load_dotenv()

app = Flask(__name__, static_folder="frontend", static_url_path="")


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
    "extract",
    "summary",
    "risk",
    "writer",
]


def _cache_dir(output_path: str) -> str:
    return os.path.join(os.path.dirname(output_path), "cache")


def _state_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, "state.json")


def _step_marker_path(cache_dir: str, step: str) -> str:
    return os.path.join(cache_dir, f"step_{step}.json")


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
        "extracted": state.get("extracted", {}),
        "risk_points": state.get("risk_points", []),
        "risk_report": state.get("risk_report", ""),
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
    elif step == "extract":
        with open(os.path.join(cache_dir, "extracted.json"), "w", encoding="utf-8") as f:
            json.dump(state.get("extracted", {}), f, ensure_ascii=False, indent=2)
    elif step == "summary":
        with open(
            os.path.join(cache_dir, "summary_profile.txt"), "w", encoding="utf-8"
        ) as f:
            f.write(state.get("summary_profile", ""))
    elif step == "risk":
        with open(
            os.path.join(cache_dir, "risk_points.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(
                {"risk_points": state.get("risk_points", [])},
                f,
                ensure_ascii=False,
                indent=2,
            )
    elif step == "writer":
        output_path = state.get("output_path") or os.path.join("output", "letter.txt")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(state.get("letter_full", ""))
        risk_report = state.get("risk_report", "")
        if risk_report:
            risk_path = os.path.join(os.path.dirname(output_path), "risk_report.txt")
            with open(risk_path, "w", encoding="utf-8") as f:
                f.write(risk_report)
            with open(os.path.join(cache_dir, "risk_report.txt"), "w", encoding="utf-8") as f:
                f.write(risk_report)

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
    if step == "extract":
        state = classify_files(state)
        state = domain_agent("personal")(state)
        state = domain_agent("travel_history")(state)
        state = domain_agent("employment")(state)
        state = domain_agent("financial")(state)
        state = domain_agent("purpose")(state)
        return state
    if step == "summary":
        summary = _build_summary_profile(state.get("extracted", {}))
        state["summary_profile"] = summary
        return state
    if step == "risk":
        return risk_explanation_finder(state)
    if step == "writer":
        return letter_writer(state)
    return state


@app.get("/")
def index():
    return send_from_directory("frontend", "index.html")


@app.get("/api/files")
def list_files():
    input_dir = request.args.get("input_dir", "input")
    files = _list_input_files(input_dir)
    return jsonify({"input_dir": input_dir, "files": files})


@app.get("/api/steps")
def list_steps():
    output_path = request.args.get("output", os.path.join("output", "letter.txt"))
    cache_dir = _cache_dir(output_path)
    steps = [
        {"name": step, "done": _is_step_done(cache_dir, step)} for step in STEP_ORDER
    ]
    return jsonify({"steps": steps})


@app.get("/api/summary")
def get_summary():
    output_path = request.args.get("output", os.path.join("output", "letter.txt"))
    cache_dir = _cache_dir(output_path)
    state_cache = _load_state(cache_dir)
    extracted = state_cache.get("extracted", {})
    summary = _build_summary_profile(extracted)
    return jsonify({"summary_profile": summary})


@app.get("/api/risk_report")
def get_risk_report():
    output_path = request.args.get("output", os.path.join("output", "letter.txt"))
    cache_dir = _cache_dir(output_path)
    report_path = os.path.join(cache_dir, "risk_report.txt")
    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            return jsonify({"risk_report": f.read()})

    state_cache = _load_state(cache_dir)
    risk_report = state_cache.get("risk_report", "")
    if risk_report:
        return jsonify({"risk_report": risk_report})

    risk_points_path = os.path.join(cache_dir, "risk_points.json")
    if os.path.exists(risk_points_path):
        with open(risk_points_path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        return jsonify(
            {
                "risk_report": json.dumps(
                    data.get("risk_points", []), ensure_ascii=False, indent=2
                )
            }
        )

    return jsonify({"risk_report": ""})


@app.get("/api/writer_context")
def get_writer_context():
    output_path = request.args.get("output", os.path.join("output", "letter.txt"))
    cache_dir = _cache_dir(output_path)
    state_cache = _load_state(cache_dir)
    return jsonify({"writer_context": state_cache.get("writer_context", "")})


@app.get("/api/ingest_stream")
def ingest_stream():
    input_dir = request.args.get("input_dir", "input")
    output_path = request.args.get("output", os.path.join("output", "letter.txt"))
    model = request.args.get("model") or os.getenv("OPENAI_MODEL", "gpt-5-mini")

    llm = ChatOpenAI(model=model, temperature=0)
    cache_dir = _cache_dir(output_path)
    files: List[Dict[str, str]] = []

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
        yield sse({"type": "done"})

    return Response(generate(), mimetype="text/event-stream")


@app.get("/api/itinerary/latest")
def get_itinerary_latest():
    output_path = request.args.get("output", os.path.join("output", "itinerary.html"))
    cache_dir = _cache_dir(output_path)
    path = os.path.join(cache_dir, "itinerary.html")
    if not os.path.exists(path):
        return jsonify({"itinerary": ""})
    with open(path, "r", encoding="utf-8") as f:
        return jsonify({"itinerary": f.read()})


@app.get("/api/itinerary/context/latest")
def get_itinerary_context_latest():
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

    if not isinstance(form_data, dict):
        return jsonify({"error": "invalid_form_data"}), 400

    summary_profile = _build_itinerary_summary_from_form(form_data)
    if not summary_profile:
        return jsonify({"error": "missing_context"}), 400

    cache_dir = _cache_dir(output_path)
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "itinerary_summary.txt"), "w", encoding="utf-8") as f:
        f.write(summary_profile)
    with open(os.path.join(cache_dir, "itinerary_summary_meta.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "form_data": form_data,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

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
    model = payload.get("model") or os.getenv("OPENAI_MODEL", "gpt-5-mini")
    force = bool(payload.get("force", False))
    writer_context = (payload.get("writer_context") or "").strip()

    if step not in STEP_ORDER:
        return jsonify({"error": "invalid_step"}), 400

    cache_dir = _cache_dir(output_path)
    missing = _missing_prereq_step(cache_dir, step)
    if missing and not force:
        return jsonify({"error": "missing_prerequisite", "missing": missing}), 400

    if _is_step_done(cache_dir, step) and not force:
        return jsonify({"status": "cached", "step": step})

    state_cache = _load_state(cache_dir)
    llm = ChatOpenAI(model=model, temperature=0)
    state: GraphState = {
        "input_dir": input_dir,
        "output_path": output_path,
        "model": model,
        "llm": llm,
        "files": state_cache.get("files", []),
        "grouped": state_cache.get("grouped", {}),
        "extracted": state_cache.get("extracted", {}),
        "risk_points": state_cache.get("risk_points", []),
        "risk_report": state_cache.get("risk_report", ""),
        "summary_profile": state_cache.get("summary_profile", ""),
        "writer_context": writer_context or state_cache.get("writer_context", ""),
        "letter_full": state_cache.get("letter_full", ""),
    }

    state = _run_single_step(step, state)
    _save_state(cache_dir, state)
    _save_step_output(cache_dir, step, state)

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
    model = payload.get("model") or os.getenv("OPENAI_MODEL", "gpt-5-mini")
    force = bool(payload.get("force", False))
    writer_context = (payload.get("writer_context") or "").strip()

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
        "extracted": state_cache.get("extracted", {}),
        "risk_points": state_cache.get("risk_points", []),
        "risk_report": state_cache.get("risk_report", ""),
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

    return jsonify({"letter": state.get("letter_full", ""), "output_path": output_path})


@app.post("/api/run_add_file")
def run_add_file():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_path = payload.get("output", os.path.join("output", "letter.txt"))
    file_ref = payload.get("file")
    model = payload.get("model") or os.getenv("OPENAI_MODEL", "gpt-5-mini")
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
        "extracted": state_cache.get("extracted", {}),
        "risk_points": state_cache.get("risk_points", []),
        "risk_report": state_cache.get("risk_report", ""),
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

    for step in ["extract", "summary", "risk", "writer"]:
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
    model = payload.get("model") or os.getenv("OPENAI_MODEL", "gpt-5-mini")

    if not flight_file or not hotel_file:
        return jsonify({"error": "missing_files"}), 400

    cache_dir = _cache_dir(output_path)
    summary_profile = (payload.get("summary_profile") or "").strip()
    if not summary_profile:
        summary_path = os.path.join(cache_dir, "itinerary_summary.txt")
        if os.path.exists(summary_path):
            with open(summary_path, "r", encoding="utf-8") as f:
                summary_profile = f.read().strip()
    if not summary_profile:
        return jsonify({"error": "missing_itinerary_summary"}), 400

    llm = ChatOpenAI(model=model, temperature=0)
    flight_path = _resolve_input_file_path(input_dir, str(flight_file))
    hotel_path = _resolve_input_file_path(input_dir, str(hotel_file))
    if not flight_path or not hotel_path:
        return jsonify({"error": "missing_files"}), 400

    flight_text = extract_text_with_openai(llm, flight_path)
    hotel_text = extract_text_with_openai(llm, hotel_path)

    itinerary = itinerary_writer(llm, flight_text, hotel_text, summary_profile)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(itinerary)
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "itinerary.html"), "w", encoding="utf-8") as f:
        f.write(itinerary)

    return jsonify({"itinerary": itinerary, "output_path": output_path})


# ==================== BOOKING GENERATOR ENDPOINTS ====================

from datetime import datetime, timedelta
from booking_generator import (
    generate_all_bookings,
    fill_hotel_template,
    fill_flight_template,
    generate_bookings_from_ai,
)
from ai_booking_agent import (
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
        cache_dir = _cache_dir(os.path.join("output", "letter.txt"))
        state_cache = _load_state(cache_dir)
        extracted = state_cache.get("extracted", {})
        
        # Try to extract name from personal info
        personal = extracted.get("personal", {})
        if personal:
            # Get first file's data
            for _, data in personal.items():
                if isinstance(data, dict):
                    guest_name = data.get("ho_ten", data.get("name", "NGUYEN VAN A"))
                    break
                elif isinstance(data, str):
                    # Try to parse name from text
                    guest_name = "NGUYEN VAN A"
        
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
        "Booking", 
        "Confirmation_for_Booking_ID_#_1696039455.html"
    )
    
    # Flight template path
    flight_template_path = os.path.join(
        os.path.dirname(__file__),
        "Booking",
        "flight.html"
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
    output_dir = request.args.get("output_dir", "output")
    
    result = {
        "hotel_htmls": [],
        "flight_html": ""
    }
    
    # Find hotel booking files
    i = 1
    while True:
        hotel_path = os.path.join(output_dir, f"booking_hotel_{i}.html")
        if os.path.exists(hotel_path):
            with open(hotel_path, "r", encoding="utf-8") as f:
                result["hotel_htmls"].append(f.read())
            i += 1
        else:
            break
    
    # Get flight booking
    flight_path = os.path.join(output_dir, "booking_flight.html")
    if os.path.exists(flight_path):
        with open(flight_path, "r", encoding="utf-8") as f:
            result["flight_html"] = f.read()
    
    return jsonify(result)


@app.get("/api/booking/destinations")
def get_destinations():
    """Get available destinations from the hotels database."""
    from booking_generator import load_hotels_database
    
    db = load_hotels_database()
    destinations = [key for key in db.keys() if key != "flights"]
    
    return jsonify({"destinations": destinations})


# ==================== AI BOOKING ENDPOINTS ====================

@app.post("/api/booking/extract_trip")
def extract_trip():
    """Extract trip information from input files - independent from Letter tab."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    model = payload.get("model") or os.getenv("OPENAI_MODEL", "gpt-5-mini")

    llm = ChatOpenAI(model=model, temperature=0)

    try:
        trip_info = extract_trip_info(llm, input_dir)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if not trip_info:
        return jsonify(
            {
                "error": (
                    "Không trích xuất được thông tin chuyến đi. "
                    "Vui lòng thêm file có tiền tố 'THONG TIN CHUYEN DI'."
                )
            }
        ), 400

    # Cache trip info + clear old booking cache (force fresh AI gen next time)
    cache_dir = _cache_dir(os.path.join("output", "letter.txt"))
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "booking_trip_info.json"), "w", encoding="utf-8") as f:
        json.dump(trip_info, f, ensure_ascii=False, indent=2)
    # Clear booking cache so AI will regenerate
    booking_cache = os.path.join(cache_dir, "ai_booking_data.json")
    if os.path.exists(booking_cache):
        os.remove(booking_cache)

    return jsonify({"status": "success", "trip_info": trip_info})


@app.post("/api/booking/ai_generate")
def ai_generate_booking():
    """Generate bookings using AI. Uses cached booking data if available to save tokens."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_dir = payload.get("output_dir", "output")
    model = payload.get("model") or os.getenv("OPENAI_MODEL", "gpt-5-mini")
    force_new = payload.get("force_new", False)

    cache_dir = _cache_dir(os.path.join("output", "letter.txt"))
    booking_cache_path = os.path.join(cache_dir, "ai_booking_data.json")
    trip_cache_path = os.path.join(cache_dir, "booking_trip_info.json")

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
        "Booking",
        "Confirmation_for_Booking_ID_#_1696039455.html"
    )
    flight_template_path = os.path.join(
        os.path.dirname(__file__),
        "Booking",
        "flight.html"
    )

    try:
        # Generate HTML files from AI decisions
        result = generate_bookings_from_ai(
            ai_booking_data=booking_data,
            hotel_template_path=hotel_template_path,
            flight_template_path=flight_template_path,
            output_dir=output_dir,
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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)

