"""
Itinerary routes: latest, context, run, stream.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from flask import Blueprint, Response, jsonify, request

from langchain_openai import ChatOpenAI

import database as db
from core.agents import itinerary_writer, extract_text_with_openai
from core.helpers import get_text_model
from config import Config

from routes.pipeline_helpers import _resolve_input_file_path, _cache_dir



STEP_ORDER = ["ingest", "summary", "writer"]

pipeline_itinerary_bp = Blueprint("pipeline_itinerary", __name__)

@pipeline_itinerary_bp.get("/api/itinerary/latest")
def get_itinerary_latest():
    project_id = request.args.get("project_id", type=int)
    if project_id:
        it = db.get_latest_itinerary(project_id)
        return jsonify({"itinerary": it["html_content"] if it else ""})
    output_path = request.args.get("output", os.path.join("output", "itinerary.html"))
    # Priority: output file (user-editable) → cache file (AI-generated)
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            return jsonify({"itinerary": f.read()})
    cache_dir = _cache_dir(output_path)
    path = os.path.join(cache_dir, "itinerary.html")
    if not os.path.exists(path):
        return jsonify({"itinerary": ""})
    with open(path, "r", encoding="utf-8") as f:
        return jsonify({"itinerary": f.read()})


@pipeline_itinerary_bp.get("/api/itinerary/context/latest")
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
    additional_info = (form_data.get("additional_info") or "").strip()
    travel_purpose = (form_data.get("travel_purpose") or "").strip()
    start_date = (form_data.get("travel_start_date") or "").strip()
    end_date = (form_data.get("travel_end_date") or "").strip()
    has_any_value = any(
        [
            participants,
            additional_info,
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
    if additional_info:
        lines.append(f"- Additional information: {additional_info}")
    if start_date and end_date:
        lines.append(f"- Travel period: From {start_date} to {end_date}")
    elif start_date:
        lines.append(f"- travel_start_date: {start_date}")
    elif end_date:
        lines.append(f"- travel_end_date: {end_date}")
    if travel_purpose:
        lines.append(f"- Purpose of travel: {travel_purpose}")

    return "\n".join(lines).strip()


@pipeline_itinerary_bp.route("/api/itinerary/context/save", methods=["POST"])
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




@pipeline_itinerary_bp.post("/api/itinerary/run")
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
    # Only fall back to DB trip info when explicitly using DB mode
    if not summary_profile and from_db and project_id:
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
        # New: accept HTML content directly from browser file upload
        uploaded_flight_html = payload.get("flight_html")
        uploaded_hotel_htmls = payload.get("hotel_htmls")  # list of HTML strings
        if uploaded_flight_html and uploaded_hotel_htmls:
            flight_text = _html_to_text(uploaded_flight_html)
            hotel_text = "\n\n---\n\n".join(_html_to_text(h) for h in uploaded_hotel_htmls)
        elif flight_file and hotel_file:
            flight_path = _resolve_input_file_path(input_dir, str(flight_file))
            hotel_path = _resolve_input_file_path(input_dir, str(hotel_file))
            if not flight_path or not hotel_path:
                return jsonify({"error": "missing_files"}), 400
            flight_text = extract_text_with_openai(llm, flight_path)
            hotel_text = extract_text_with_openai(llm, hotel_path)
        else:
            return jsonify({"error": "missing_files"}), 400

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


@pipeline_itinerary_bp.post("/api/itinerary/run_stream")
def run_itinerary_stream():
    """Generate itinerary with SSE progress streaming."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_path = payload.get("output", os.path.join("output", "itinerary.html"))
    flight_file = payload.get("flight_file")
    hotel_file = payload.get("hotel_file")
    # New: accept HTML content directly from browser file upload
    uploaded_flight_html = payload.get("flight_html")
    uploaded_hotel_htmls = payload.get("hotel_htmls")  # list of HTML strings
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
        # Only fall back to DB trip info when explicitly using DB mode
        if not summary_profile and from_db and project_id:
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
                # Option A: HTML content uploaded directly from browser
                if uploaded_flight_html and uploaded_hotel_htmls:
                    yield from send_event(1, "✅ Đã nhận file từ trình duyệt")
                    yield from send_event(2, "⏳ Đang trích xuất nội dung booking...")
                    flight_text = _html_to_text(uploaded_flight_html)
                    hotel_text = "\n\n---\n\n".join(_html_to_text(h) for h in uploaded_hotel_htmls)
                    yield from send_event(2, "✅ Trích xuất nội dung hoàn tất")
                # Option B: Legacy file path approach (backward compatible)
                elif flight_file and hotel_file:
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
                else:
                    yield from send_event(-1, "❌ Vui lòng chọn đủ file vé máy bay và khách sạn")
                    return

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
