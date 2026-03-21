"""
Booking routes: generate bookings, AI booking, SerpAPI flights/hotels.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from flask import Blueprint, Response, jsonify, request, send_file

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from core.helpers import cache_dir as get_cache_dir

import database as db
from booking.generator import (
    generate_all_bookings,
    fill_hotel_template,
    fill_flight_template,
    fill_vivavivu_template,
    generate_bookings_from_ai,
)
from booking.ai_agent import (
    DEFAULT_TRIP_INFO,
    extract_trip_info,
    ai_select_bookings,
    generate_ai_booking,
)

booking_bp = Blueprint("booking", __name__)

# Base directory (project root, one level up from routes/)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OUTPUT_DIR = os.path.join(_BASE_DIR, "output")


# _cache_dir → imported as cache_dir from core.helpers


# Import model helpers from server (they will stay in server.py for now)
def _get_text_model():
    return os.getenv("TEXT_MODEL", "gpt-5-mini")

def _get_vision_model():
    return os.getenv("VISION_MODEL", "gpt-4o-mini")


def _get_serpapi_key():
    return os.getenv("SERPAPI_KEY", "")

@booking_bp.get("/api/booking/latest_html")
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






@booking_bp.post("/api/booking/generate")
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
        _BASE_DIR, 
        "templates", 
        "hotel_booking.html"
    )
    
    # Flight template path
    flight_template_path = os.path.join(
        _BASE_DIR,
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


@booking_bp.get("/api/booking/latest")
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


@booking_bp.get("/api/booking/destinations")
def get_destinations():
    """Get available destinations from the hotels database."""
    from booking.generator import load_hotels_database
    
    hotels_db = load_hotels_database()
    destinations = [key for key in hotels_db.keys() if key != "flights"]
    
    return jsonify({"destinations": destinations})




@booking_bp.get("/api/booking/filtered-files")
def booking_filtered_files():
    """List files in input dir, categorized by trip-info prefix."""
    input_dir = request.args.get("input_dir", "input")
    project_id = request.args.get("project_id", type=int)
    guest_names_param = request.args.get("guest_names", "")

    if not os.path.isdir(input_dir):
        return jsonify({"files": [], "matched": [], "other": []})

    # Get guest names for filtering (from param or DB)
    guest_names = [n.strip() for n in guest_names_param.split(",") if n.strip()] if guest_names_param else []
    if not guest_names and project_id:
        saved_ti = db.get_latest_trip_info(project_id)
        if saved_ti and saved_ti.get("data", {}).get("guest_names"):
            guest_names = saved_ti["data"]["guest_names"]

    def _filename_matches_guests(fname, names):
        if not names:
            return True  # No filter = show all
        normalized_fname = re.sub(r'[\s\-_]+', ' ', os.path.splitext(fname)[0].upper()).strip()
        for name in names:
            normalized_name = re.sub(r'[\s\-_]+', ' ', name.upper()).strip()
            if not normalized_name:
                continue
            name_parts = [p for p in normalized_name.split() if len(p) > 1]
            if len(name_parts) >= 2 and all(part in normalized_fname for part in name_parts):
                return True
        return False

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
            # Filter by guest names if available
            if guest_names and not _filename_matches_guests(fname, guest_names):
                continue

            stem = os.path.splitext(fname)[0]
            normalized = re.sub(r"[\s\-_]+", " ", stem.upper()).strip()
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


@booking_bp.post("/api/booking/extract_trip")
def extract_trip():
    """Extract trip information from input files."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    model = payload.get("model") or _get_vision_model()  # reads input files (may contain images)
    project_id = payload.get("project_id")
    # Get saved guest names to filter input files by project
    saved_guest_names = payload.get("guest_names") or []
    if not saved_guest_names and project_id:
        saved_ti = db.get_latest_trip_info(int(project_id))
        if saved_ti and saved_ti.get("data", {}).get("guest_names"):
            saved_guest_names = saved_ti["data"]["guest_names"]

    llm = ChatOpenAI(model=model, temperature=0)

    try:
        trip_info = extract_trip_info(llm, input_dir, guest_names=saved_guest_names)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if not isinstance(trip_info, dict):
        trip_info = dict(DEFAULT_TRIP_INFO)

    # Cache trip info to file
    cache_dir = get_cache_dir(os.path.join("output", "letter.txt"))
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


@booking_bp.get("/api/booking/trip/latest")
def get_booking_trip_latest():
    """Load cached trip info for editing in frontend."""
    project_id = request.args.get("project_id", type=int)
    if project_id:
        ti = db.get_latest_trip_info(project_id)
        data = ti["data"] if ti else dict(DEFAULT_TRIP_INFO)
        return jsonify({"trip_info": data})
    cache_dir = get_cache_dir(os.path.join("output", "letter.txt"))
    trip_path = os.path.join(cache_dir, "booking_trip_info.json")
    if not os.path.exists(trip_path):
        return jsonify({"trip_info": dict(DEFAULT_TRIP_INFO)})
    with open(trip_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    merged = dict(DEFAULT_TRIP_INFO)
    if isinstance(data, dict):
        merged.update(data)
    return jsonify({"trip_info": merged})


@booking_bp.post("/api/itinerary/extract_from_html")
def extract_trip_from_html():
    """Extract trip info (guests, dates, purpose) from uploaded HTML content."""
    payload = request.get_json(force=True) or {}
    flight_html = payload.get("flight_html", "")
    hotel_htmls = payload.get("hotel_htmls", [])

    import re as _re

    def _strip_tags(html_str):
        text = _re.sub(r'<style[^>]*>.*?</style>', '', html_str, flags=_re.DOTALL)
        text = _re.sub(r'<script[^>]*>.*?</script>', '', text, flags=_re.DOTALL)
        text = _re.sub(r'<[^>]+>', ' ', text)
        text = _re.sub(r'\s+', ' ', text).strip()
        return text

    all_text = _strip_tags(flight_html)
    for h in hotel_htmls:
        all_text += "\n" + _strip_tags(h)

    # Extract dates (YYYY-MM-DD or DD/MM/YYYY patterns)
    dates = []
    for m in _re.finditer(r'(\d{4}-\d{2}-\d{2})', all_text):
        dates.append(m.group(1))
    for m in _re.finditer(r'(\d{2}/\d{2}/\d{4})', all_text):
        parts = m.group(1).split("/")
        dates.append(f"{parts[2]}-{parts[1]}-{parts[0]}")

    travel_start = min(dates) if dates else ""
    travel_end = max(dates) if dates else ""

    # Extract passenger/guest names from common patterns
    names = set()
    # Pattern: "Passenger: NAME" or "Guest: NAME" or "Name: NAME"
    for m in _re.finditer(r'(?:Passenger|Guest|Họ tên|Name|Tên)\s*[:\-]\s*([A-ZÀ-Ỹ][A-ZÀ-Ỹa-zà-ỹ\s]{2,40})', all_text):
        name = m.group(1).strip()
        if len(name) > 2 and not any(w in name.lower() for w in ['hotel', 'airline', 'booking', 'check', 'room']):
            names.add(name)
    # Pattern: "Mr/Mrs/Ms NAME" 
    for m in _re.finditer(r'(?:Mr|Mrs|Ms|MR|MRS|MS)\.?\s+([A-ZÀ-Ỹ][A-ZÀ-Ỹa-zà-ỹ\s]{2,40})', all_text):
        name = m.group(1).strip()
        if len(name) > 2:
            names.add(name)
    # Pattern: ALL CAPS names (common in booking) — look for 2+ word uppercase sequences
    for m in _re.finditer(r'\b([A-ZÀ-Ỹ]{2,}\s+[A-ZÀ-Ỹ]{2,}(?:\s+[A-ZÀ-Ỹ]{2,})*)\b', all_text):
        candidate = m.group(1).strip()
        skip_words = {'CHECK IN', 'CHECK OUT', 'HOTEL NAME', 'ROOM TYPE', 'BOOKING ID',
                       'MEMBER ID', 'CONFIRMATION', 'TOTAL PRICE', 'FLIGHT NUMBER',
                       'DEPARTURE TIME', 'ARRIVAL TIME', 'BOOKING CONFIRMATION',
                       'ECONOMY CLASS', 'BUSINESS CLASS', 'FIRST CLASS', 'ONE WAY',
                       'ROUND TRIP', 'GUEST NAME', 'HOTEL BOOKING', 'FLIGHT BOOKING',
                       'IATA CODE', 'MEMBER NUMBER', 'BOOKING REFERENCE'}
        if candidate not in skip_words and 4 < len(candidate) < 40:
            names.add(candidate)

    guest_names = sorted(list(names))

    return jsonify({
        "trip_info": {
            "guest_names": guest_names,
            "travel_start_date": travel_start,
            "travel_end_date": travel_end,
            "travel_purpose": "Tourism",
        }
    })

@booking_bp.post("/api/booking/trip/save")
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
    cache_dir = get_cache_dir(os.path.join("output", "letter.txt"))
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


@booking_bp.post("/api/booking/ai_generate")
def ai_generate_booking():
    """Generate bookings using AI. Uses cached booking data if available to save tokens."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_dir = payload.get("output_dir", "output")
    model = payload.get("model") or _get_text_model()  # booking uses text reasoning
    force_new = payload.get("force_new", False)
    target = (payload.get("target") or "both").strip().lower()
    if target not in ["both", "hotel", "flight"]:
        target = "both"
    trip_info_override = payload.get("trip_info")
    project_id = payload.get("project_id")

    cache_dir = get_cache_dir(os.path.join("output", "letter.txt"))
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
        _BASE_DIR,
        "templates",
        "hotel_booking.html"
    )
    flight_template_path = os.path.join(
        _BASE_DIR,
        "templates",
        "flight_booking.html"
    )

    try:
        selected_booking_data = dict(booking_data or {})
        if target == "hotel":
            selected_booking_data["flight"] = {}
        elif target == "flight":
            selected_booking_data["hotels"] = []

        # Generate HTML files from AI decisions
        result = generate_bookings_from_ai(
            ai_booking_data=selected_booking_data,
            hotel_template_path=hotel_template_path,
            flight_template_path=flight_template_path,
            output_dir=output_dir,
        )

        # Save to DB
        if project_id:
            existing = db.get_latest_booking(int(project_id)) or {}
            final_hotel_htmls = result["hotel_htmls"] if target in ["both", "hotel"] else existing.get("hotel_htmls", [])
            final_flight_html = result["flight_html"] if target in ["both", "flight"] else existing.get("flight_html", "")
            db.save_booking(
                int(project_id),
                booking_data=booking_data,
                hotel_htmls=final_hotel_htmls,
                flight_html=final_flight_html,
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


@booking_bp.post("/api/booking/ai_generate_stream")
def ai_generate_booking_stream():
    """Generate bookings using AI with SSE progress streaming."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_dir = payload.get("output_dir", "output")
    model = payload.get("model") or _get_text_model()
    force_new = payload.get("force_new", False)
    target = (payload.get("target") or "both").strip().lower()
    if target not in ["both", "hotel", "flight"]:
        target = "both"
    trip_info_override = payload.get("trip_info")
    project_id = payload.get("project_id")

    cache_dir = get_cache_dir(os.path.join("output", "letter.txt"))
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
                    # Get saved guest names to filter input files by project
                    saved_guest_names = []
                    if project_id:
                        saved_ti = db.get_latest_trip_info(int(project_id))
                        if saved_ti and saved_ti.get("data", {}).get("guest_names"):
                            saved_guest_names = saved_ti["data"]["guest_names"]
                    trip_info = extract_trip_info(llm, input_dir, guest_names=saved_guest_names)
                    yield from send_event(1, "✅ Trích xuất thông tin chuyến đi hoàn tất")
                else:
                    yield from send_event(1, "✅ Đã có thông tin chuyến đi")

                if not trip_info or not trip_info.get("destination_country"):
                    yield from send_event(-1, "❌ Không thể trích xuất thông tin chuyến đi")
                    return

                # Step 2: AI select bookings (use mini model for cost savings)
                if target == "hotel":
                    yield from send_event(2, "⏳ AI đang chọn khách sạn...")
                elif target == "flight":
                    yield from send_event(2, "⏳ AI đang chọn chuyến bay...")
                else:
                    yield from send_event(2, "⏳ AI đang chọn khách sạn & chuyến bay...")
                booking_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
                booking_data = ai_select_bookings(booking_llm, trip_info)
                if target == "hotel":
                    yield from send_event(2, "✅ AI đã chọn xong khách sạn")
                elif target == "flight":
                    yield from send_event(2, "✅ AI đã chọn xong chuyến bay")
                else:
                    yield from send_event(2, "✅ AI đã chọn xong khách sạn & chuyến bay")

                if not booking_data:
                    yield from send_event(-1, "❌ AI không thể tạo booking")
                    return
                if target in ["both", "hotel"] and not booking_data.get("hotels"):
                    yield from send_event(-1, "❌ AI không thể tạo booking khách sạn")
                    return
                if target in ["both", "flight"] and not booking_data.get("flight"):
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
        if target == "hotel":
            yield from send_event(3, "⏳ Đang tạo file HTML khách sạn...")
        elif target == "flight":
            yield from send_event(3, "⏳ Đang tạo file HTML máy bay...")
        else:
            yield from send_event(3, "⏳ Đang tạo file HTML booking...")

        hotel_template_path = os.path.join(_BASE_DIR, "templates", "hotel_booking.html")
        flight_template_path = os.path.join(_BASE_DIR, "templates", "flight_booking.html")

        try:
            selected_booking_data = dict(booking_data or {})
            if target == "hotel":
                selected_booking_data["flight"] = {}
            elif target == "flight":
                selected_booking_data["hotels"] = []

            result = generate_bookings_from_ai(
                ai_booking_data=selected_booking_data,
                hotel_template_path=hotel_template_path,
                flight_template_path=flight_template_path,
                output_dir=output_dir,
            )

            if project_id:
                existing = db.get_latest_booking(int(project_id)) or {}
                final_hotel_htmls = result["hotel_htmls"] if target in ["both", "hotel"] else existing.get("hotel_htmls", [])
                final_flight_html = result["flight_html"] if target in ["both", "flight"] else existing.get("flight_html", "")
                db.save_booking(
                    int(project_id),
                    booking_data=booking_data,
                    hotel_htmls=final_hotel_htmls,
                    flight_html=final_flight_html,
                    reasoning=booking_data.get("reasoning", ""),
                )

            if target == "hotel":
                yield from send_event(3, "✅ Tạo HTML khách sạn hoàn tất")
            elif target == "flight":
                yield from send_event(3, "✅ Tạo HTML máy bay hoàn tất")
            else:
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




@booking_bp.post("/api/flights/search")
def search_flights():
    """Search flights using SerpAPI Google Flights engine."""
    try:
        from serpapi import GoogleSearch
    except ImportError:
        return jsonify({"error": "google-search-results package not installed. Run: pip install google-search-results"}), 500

    payload = request.get_json(force=True) or {}
    flight_type = str(payload.get("type", 2))
    departure_id = payload.get("departure_id", "")
    arrival_id = payload.get("arrival_id", "")
    outbound_date = payload.get("outbound_date", "")

    if not departure_id or not outbound_date:
        return jsonify({"error": "departure_id and outbound_date are required"}), 400
    if flight_type != "3" and not arrival_id:
        return jsonify({"error": "arrival_id is required for non-multi-city searches"}), 400

    params = {
        "engine": "google_flights",
        "hl": payload.get("hl", "en"),
        "gl": payload.get("gl", "vn"),
        "type": flight_type,
        "departure_id": departure_id,
        "arrival_id": arrival_id,
        "outbound_date": outbound_date,
        "adults": int(payload.get("adults", 1)),
        "currency": payload.get("currency", "VND"),
        "api_key": _get_serpapi_key(),
    }

    if payload.get("return_date"):
        params["return_date"] = payload["return_date"]
    if payload.get("children"):
        params["children"] = int(payload["children"])
    if payload.get("departure_token"):
        params["departure_token"] = payload["departure_token"]
    if payload.get("multi_city_json"):
        params["multi_city_json"] = payload["multi_city_json"]

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
    except Exception as e:
        return jsonify({"error": f"SerpAPI error: {str(e)}"}), 500

    return jsonify({
        "best_flights": results.get("best_flights", []),
        "other_flights": results.get("other_flights", []),
        "search_parameters": results.get("search_parameters", {}),
    })




@booking_bp.post("/api/hotels/search-itinerary")
def search_hotels_itinerary():
    """Search hotels for an entire itinerary using SerpAPI Google Hotels engine."""
    try:
        from serpapi import GoogleSearch
    except ImportError:
        return jsonify({"error": "google-search-results package not installed. Run: pip install google-search-results"}), 500

    payload = request.get_json(force=True) or {}
    start_date = payload.get("start_date", "")
    stops = payload.get("stops", [])
    adults = int(payload.get("adults", 2))
    children = int(payload.get("children", 0))
    currency = payload.get("currency", "USD")

    if not start_date or not stops:
        return jsonify({"error": "start_date and stops are required"}), 400

    # Calculate check-in/check-out for each stop
    try:
        current_date = datetime.strptime(start_date, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": f"Invalid start_date format: {start_date}. Use YYYY-MM-DD"}), 400

    enriched_stops = []
    for stop in stops:
        city = stop.get("city", "").strip()
        nights = int(stop.get("nights", 1))
        hotel_hint = stop.get("hotel_hint", "").strip()
        if not city:
            continue
        check_in = current_date.strftime("%Y-%m-%d")
        current_date += timedelta(days=nights)
        check_out = current_date.strftime("%Y-%m-%d")
        enriched_stops.append({
            "city": city,
            "nights": nights,
            "hotel_hint": hotel_hint,
            "check_in": check_in,
            "check_out": check_out,
        })

    if not enriched_stops:
        return jsonify({"error": "No valid stops found"}), 400

    api_key = _get_serpapi_key()

    def _search_one_stop(stop_info):
        """Search hotels for a single city stop."""
        q = stop_info["hotel_hint"] if stop_info["hotel_hint"] else f"Hotels in {stop_info['city']}"
        params = {
            "engine": "google_hotels",
            "q": q,
            "check_in_date": stop_info["check_in"],
            "check_out_date": stop_info["check_out"],
            "adults": adults,
            "currency": currency,
            "hl": "en",
            "gl": "us",
            "api_key": api_key,
        }
        if children > 0:
            params["children"] = children

        try:
            print(f"[HOTEL-SEARCH] 🔍 Searching: {q} ({stop_info['check_in']} → {stop_info['check_out']})")
            search = GoogleSearch(params)
            results = search.get_dict()
            properties = results.get("properties", [])
            print(f"[HOTEL-SEARCH] ✅ {stop_info['city']}: {len(properties)} hotels found")
            return {
                "city": stop_info["city"],
                "nights": stop_info["nights"],
                "hotel_hint": stop_info["hotel_hint"],
                "check_in": stop_info["check_in"],
                "check_out": stop_info["check_out"],
                "properties": properties[:10],  # Top 10 results per city
            }
        except Exception as e:
            print(f"[HOTEL-SEARCH] ❌ {stop_info['city']}: {e}")
            return {
                "city": stop_info["city"],
                "nights": stop_info["nights"],
                "hotel_hint": stop_info["hotel_hint"],
                "check_in": stop_info["check_in"],
                "check_out": stop_info["check_out"],
                "properties": [],
                "error": str(e),
            }

    # Search all stops in parallel (max 4 concurrent)
    from concurrent.futures import ThreadPoolExecutor, as_completed
    print(f"[HOTEL-SEARCH] 🚀 Searching {len(enriched_stops)} cities in parallel")
    results_list = []
    with ThreadPoolExecutor(max_workers=min(4, len(enriched_stops))) as executor:
        future_map = {executor.submit(_search_one_stop, s): i for i, s in enumerate(enriched_stops)}
        for future in as_completed(future_map):
            results_list.append((future_map[future], future.result()))

    # Sort by original order
    results_list.sort(key=lambda x: x[0])
    ordered_results = [r[1] for r in results_list]

    return jsonify({"stops": ordered_results})


@booking_bp.post("/api/hotels/generate-booking")
def generate_hotel_booking_from_serp():
    """Generate hotel booking HTML from selected SerpAPI hotel results using Agoda template."""
    import random
    
    payload = request.get_json(force=True) or {}
    hotel_stops = payload.get("hotel_stops", [])
    guests_all = payload.get("guests", [])        # list of names (adults)
    children = payload.get("children", [])         # list of child names
    output_dir = str(payload.get("output_dir", "output") or "output")
    project_id = str(payload.get("project_id", "") or "")

    if not hotel_stops:
        return jsonify({"error": "hotel_stops is required"}), 400

    # --- Read Agoda template ---
    _project_root = _BASE_DIR
    template_path = os.path.join(_project_root, "templates", "hotel_booking.html")
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template_html = f.read()
    except FileNotFoundError:
        return jsonify({"error": f"Template not found: {template_path}"}), 500

    # --- Guest info ---
    adult_names = guests_all if guests_all else ["Guest"]
    child_names = children if children else []
    num_adults = len(adult_names)
    num_children = len(child_names)
    total_guests = num_adults + num_children
    # Room logic: default 1, if total > 3 then +1
    num_rooms = 1 if total_guests <= 3 else 2

    client_name = ", ".join([n.upper() for n in adult_names])
    guest_list = ", ".join([n.upper() for n in adult_names + child_names])

    # Helper: format date string to "Month Day, Year" e.g. "March 16, 2026"
    def _fmt_date(date_str):
        """Try to parse YYYY-MM-DD or various formats and return 'Month Day, Year'."""
        if not date_str:
            return "N/A"
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime("%B %d, %Y")
            except ValueError:
                continue
        return date_str  # fallback: return as-is

    def _day_of_week(date_str):
        """Return day name like 'Monday'."""
        if not date_str:
            return ""
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime("%A")
            except ValueError:
                continue
        return ""

    def _cancel_date(date_str):
        """Return 1 day before check-in, formatted."""
        if not date_str:
            return "N/A"
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                cancel = dt - timedelta(days=1)
                return cancel.strftime("%B %d, %Y")
            except ValueError:
                continue
        return date_str

    def _split_address(addr):
        """Split long address into max 3 lines."""
        if not addr:
            return ("", "", "")
        parts = [p.strip() for p in addr.split(",")]
        if len(parts) <= 1:
            return (addr, "", "")
        elif len(parts) == 2:
            return (parts[0] + ",", parts[1], "")
        else:
            # Group into 3 lines
            mid = len(parts) // 2
            line1 = ", ".join(parts[:mid]) + ","
            line2 = ", ".join(parts[mid:-1]) + ","
            line3 = parts[-1]
            return (line1, line2, line3)

    # --- Generate one file per hotel ---
    saved_files = []
    first_html = ""

    base = os.path.join(_project_root, output_dir)
    os.makedirs(base, exist_ok=True)

    # --- Fill missing fields: Database first → AI second → Defaults last ---
    # SerpAPI hotel listing doesn't always return address, phone, or room type.
    # Priority: 1) Check hotels_database.json  2) AI generate  3) Static defaults

    # Step 1: Load hotels database and build a lookup by normalized name
    _db_hotels_flat = {}  # { normalized_name: hotel_dict }
    try:
        _db_path = os.path.join(_project_root, "booking", "hotels_database.json")
        with open(_db_path, "r", encoding="utf-8") as f:
            _hotels_db = json.load(f)
        # Flatten: country -> city -> [hotels] into a single dict keyed by normalized name
        for country, cities in _hotels_db.items():
            if country == "flights":
                continue
            if isinstance(cities, dict):
                for city, hotels_list in cities.items():
                    if isinstance(hotels_list, list):
                        for h in hotels_list:
                            name_key = h.get("hotel_name", "").strip().lower()
                            if name_key:
                                _db_hotels_flat[name_key] = h
        print(f"[HOTEL-BOOKING] 📚 Loaded {len(_db_hotels_flat)} hotels from database")
    except Exception as e:
        print(f"[HOTEL-BOOKING] ⚠️ Could not load hotels database: {e}")

    def _find_in_database(hotel_name):
        """Fuzzy match hotel name against database. Returns dict or None."""
        if not hotel_name or not _db_hotels_flat:
            return None
        name_lower = hotel_name.strip().lower()
        # Exact match
        if name_lower in _db_hotels_flat:
            return _db_hotels_flat[name_lower]
        # Partial match: check if DB name is contained in SerpAPI name or vice versa
        for db_name, db_hotel in _db_hotels_flat.items():
            if db_name in name_lower or name_lower in db_name:
                return db_hotel
        # Word-based match: at least 2 key words match
        name_words = set(name_lower.split())
        skip_words = {"hotel", "the", "a", "an", "resort", "&", "spa", "and"}
        name_key_words = name_words - skip_words
        if len(name_key_words) >= 2:
            for db_name, db_hotel in _db_hotels_flat.items():
                db_words = set(db_name.split()) - skip_words
                common = name_key_words & db_words
                if len(common) >= 2:
                    return db_hotel
        return None

    # Step 2: Try database lookup for each hotel with missing fields
    hotels_still_needing_ai = []
    for idx, hs in enumerate(hotel_stops):
        missing_address = not hs.get("hotel_address", "").strip()
        missing_phone = not hs.get("phone", "").strip()
        missing_room = not hs.get("room_type", "").strip()

        if not (missing_address or missing_phone or missing_room):
            continue  # All fields present from SerpAPI

        # Try database lookup
        db_match = _find_in_database(hs.get("hotel_name", ""))
        if db_match:
            if missing_address and db_match.get("hotel_address"):
                hs["hotel_address"] = db_match["hotel_address"]
                missing_address = False
            if missing_phone and db_match.get("hotel_phone"):
                hs["phone"] = db_match["hotel_phone"]
                missing_phone = False
            if missing_room and db_match.get("room_types"):
                hs["room_type"] = random.choice(db_match["room_types"])
                missing_room = False
            print(f"[HOTEL-BOOKING] 📚 DB match for '{hs.get('hotel_name')}' → filled from database")

        # If still missing after DB lookup → try SerpAPI Property Details
        if missing_address or missing_phone or missing_room:
            hotels_still_needing_ai.append((idx, hs))

    # Step 2.5: SerpAPI Property Details API for hotels with property_token
    # This gets real address, phone, and room info directly from Google
    hotels_with_token = [(idx, hs) for idx, hs in hotels_still_needing_ai if hs.get("property_token", "").strip()]
    if hotels_with_token:
        try:
            from serpapi import GoogleSearch
            api_key = _get_serpapi_key()

            def _fetch_property_details(token_info):
                idx, hs = token_info
                try:
                    params = {
                        "engine": "google_hotels",
                        "property_token": hs["property_token"],
                        "q": hs.get("hotel_name", "Hotel"),
                        "check_in_date": hs.get("check_in", ""),
                        "check_out_date": hs.get("check_out", ""),
                        "adults": len(guests_all) if guests_all else 2,
                        "currency": "USD",
                        "hl": "en",
                        "gl": "us",
                        "api_key": api_key,
                    }
                    search = GoogleSearch(params)
                    result = search.get_dict()

                    # Property details are in different possible locations
                    prop = result
                    filled = []
                    if not hs.get("hotel_address", "").strip():
                        addr = prop.get("address", "") or prop.get("location", "")
                        if addr:
                            hs["hotel_address"] = addr
                            filled.append("address")
                    if not hs.get("phone", "").strip():
                        phone = prop.get("phone", "")
                        if phone:
                            hs["phone"] = phone
                            filled.append("phone")
                    if not hs.get("room_type", "").strip():
                        # Try to get room type from prices/rooms info
                        prices = prop.get("prices", [])
                        if prices and isinstance(prices, list) and len(prices) > 0:
                            first_price = prices[0]
                            room_name = first_price.get("name", "") or first_price.get("room_name", "")
                            if room_name:
                                hs["room_type"] = room_name
                                filled.append("room_type")
                    if filled:
                        print(f"[HOTEL-BOOKING] 🔍 SerpAPI Details for '{hs.get('hotel_name')}' → filled: {', '.join(filled)}")
                    return True
                except Exception as e:
                    print(f"[HOTEL-BOOKING] ⚠️ SerpAPI Details failed for '{hs.get('hotel_name')}': {e}")
                    return False

            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(3, len(hotels_with_token))) as executor:
                list(executor.map(_fetch_property_details, hotels_with_token))

        except ImportError:
            print("[HOTEL-BOOKING] ⚠️ serpapi not installed, skipping Property Details")
        except Exception as e:
            print(f"[HOTEL-BOOKING] ⚠️ SerpAPI Property Details error: {e}")

    # Rebuild list of hotels still missing fields after SerpAPI Details
    hotels_still_needing_ai = []
    for idx, hs in enumerate(hotel_stops):
        still_missing = (
            not hs.get("hotel_address", "").strip()
            or not hs.get("phone", "").strip()
            or not hs.get("room_type", "").strip()
        )
        if still_missing:
            hotels_still_needing_ai.append((idx, hs))

    # Step 3: AI generate for hotels NOT found in database
    if hotels_still_needing_ai:
        try:
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7, max_tokens=1000)
            hotel_descriptions = []
            for idx, hs in hotels_still_needing_ai:
                missing_fields = []
                if not hs.get("hotel_address", "").strip():
                    missing_fields.append("address")
                if not hs.get("phone", "").strip():
                    missing_fields.append("phone")
                if not hs.get("room_type", "").strip():
                    missing_fields.append("room_type")
                hotel_descriptions.append(
                    f"Hotel {idx + 1}: \"{hs.get('hotel_name', 'Unknown')}\" in {hs.get('city', 'Unknown City')} (needs: {', '.join(missing_fields)})"
                )
            prompt = (
                "For each hotel below, generate REALISTIC details in JSON format. "
                "Only generate the fields marked as needed.\n"
                "- address: full street address with city, state/province, postal code, country\n"
                "- phone: international format with country code, e.g. +33145678901\n"
                "- room_type: realistic room type like 'Deluxe King', 'Superior Twin', 'Premier Suite'\n\n"
                + "\n".join(hotel_descriptions) + "\n\n"
                "Return a JSON array with objects having keys: hotel_index, address, phone, room_type.\n"
                "ONLY return the JSON array, no other text."
            )
            from langchain_core.messages import HumanMessage
            ai_response = llm.invoke([HumanMessage(content=prompt)])
            ai_text = ai_response.content.strip()
            import re as _re
            json_match = _re.search(r'\[.*\]', ai_text, _re.DOTALL)
            if json_match:
                ai_data = json.loads(json_match.group())
                for item in ai_data:
                    hi = item.get("hotel_index", 0)
                    # Try 0-based first, then 1-based
                    if isinstance(hi, int) and 0 <= hi < len(hotel_stops):
                        hs = hotel_stops[hi]
                    elif isinstance(hi, int) and hi > 0 and (hi - 1) < len(hotel_stops):
                        hs = hotel_stops[hi - 1]
                    else:
                        continue
                    if not hs.get("hotel_address", "").strip() and item.get("address"):
                        hs["hotel_address"] = item["address"]
                    if not hs.get("phone", "").strip() and item.get("phone"):
                        hs["phone"] = item["phone"]
                    if not hs.get("room_type", "").strip() and item.get("room_type"):
                        hs["room_type"] = item["room_type"]
                print(f"[HOTEL-BOOKING] 🤖 AI generated missing fields for {len(ai_data)} hotels")
        except Exception as e:
            print(f"[HOTEL-BOOKING] ⚠️ AI generation failed, using defaults: {e}")

    for i, hs in enumerate(hotel_stops):
        booking_id = str(random.randint(1000000000, 9999999999))
        booking_ref = str(random.randint(1000000000, 9999999999))
        member_id = str(random.randint(100000000, 999999999))

        check_in = hs.get("check_in", "")
        check_out = hs.get("check_out", "")
        hotel_name = hs.get("hotel_name", "Hotel")
        hotel_address = hs.get("hotel_address", "") or hs.get("city", "")
        total_price = hs.get("total_price", "") or hs.get("price_per_night", "N/A")
        room_type = hs.get("room_type", "") or "Deluxe Room"
        phone = hs.get("phone", "") or f"+{random.randint(1, 99)}{random.randint(100000000, 999999999)}"

        addr1, addr2, addr3 = _split_address(hotel_address)

        html = template_html
        html = html.replace("{{BOOKING_ID}}", booking_id)
        html = html.replace("{{BOOKING_REF}}", booking_ref)
        html = html.replace("{{NUM_ROOMS}}", str(num_rooms))
        html = html.replace("{{NUM_EXTRA_BEDS}}", "0")
        html = html.replace("{{NUM_ADULTS}}", str(num_adults))
        html = html.replace("{{NUM_CHILDREN}}", str(num_children))
        html = html.replace("{{CLIENT_NAME}}", client_name)
        html = html.replace("{{MEMBER_ID}}", member_id)
        html = html.replace("{{COUNTRY_OF_RESIDENCE}}", "Vietnam / Vietnam")
        html = html.replace("{{HOTEL_NAME}}", hotel_name)
        html = html.replace("{{ROOM_TYPE}}", room_type)
        html = html.replace("{{ADDRESS_LINE1}}", addr1)
        html = html.replace("{{ADDRESS_LINE2}}", addr2)
        html = html.replace("{{ADDRESS_LINE3}}", addr3)
        html = html.replace("{{PHONE}}", phone)
        html = html.replace("{{CANCEL_FREE_DATE}}", _cancel_date(check_in))
        html = html.replace("{{ARRIVAL_DATE}}", _fmt_date(check_in))
        html = html.replace("{{DEPARTURE_DATE}}", _fmt_date(check_out))
        html = html.replace("{{CHECKIN_DAY}}", _day_of_week(check_in))
        html = html.replace("{{TOTAL_PRICE}}", str(total_price))
        html = html.replace("{{GUEST_LIST}}", guest_list)

        # ── Font fix: override embedded PDF subset fonts with system font ──
        # The PDF-to-HTML template embeds Liberation Sans as base64 subsets with
        # only original glyphs. New characters (Vietnamese, different hotel names)
        # fall back to a different font, causing visual inconsistency.
        font_override_css = """<style>
.pdf24_07, .pdf24_10, .pdf24_14, .pdf24_16, .pdf24_23 {
    font-family: Arial, Helvetica, sans-serif !important;
    font-weight: bold !important;
}
.pdf24_11, .pdf24_24 {
    font-family: Arial, Helvetica, sans-serif !important;
    font-weight: normal !important;
}
</style>"""
        html = html.replace("</head>", font_override_css + "\n</head>")

        # Save file
        fname = f"booking_hotel_{i + 1}.html"
        fpath = os.path.join(base, fname)
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(html)
            saved_files.append(fpath)
            print(f"[HOTEL-BOOKING] ✅ Saved {fpath}")
        except Exception as e:
            print(f"[HOTEL-BOOKING] ⚠️ Could not save {fname}: {e}")

        if i == 0:
            first_html = html

    # Collect all HTML content for frontend tabs
    all_htmls = []
    for i, hs in enumerate(hotel_stops):
        # Re-read from saved files to get the actual HTML content
        fname = f"booking_hotel_{i + 1}.html"
        fpath = os.path.join(base, fname)
        if fpath in saved_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    all_htmls.append(f.read())
            except Exception:
                all_htmls.append(first_html if i == 0 else "")

    return jsonify({
        "hotel_html": first_html,
        "hotel_htmls": all_htmls,  # Array of HTML content strings for tabs
        "saved_files": [os.path.basename(f) for f in saved_files],
        "file_count": len(saved_files),
    })


def _serp_dt_parts(dt_str: str) -> tuple[str, str]:
    if not dt_str:
        return "", ""
    parts = dt_str.strip().split(" ")
    if len(parts) < 2:
        return "", ""
    ymd = parts[0]
    hm = parts[1]
    try:
        yyyy, mm, dd = ymd.split("-")
        return f"{dd}/{mm}/{yyyy}", hm
    except Exception:
        return "", hm


def _serp_minutes_to_duration(minutes: Any) -> str:
    try:
        total = int(minutes or 0)
    except Exception:
        total = 0
    h = total // 60
    m = total % 60
    if h and m:
        return f"{h}h {m}m"
    if h:
        return f"{h}h"
    return f"{m}m"


def _map_serp_option_to_vna_segment(option: Dict[str, Any]) -> Dict[str, Any]:
    flights = option.get("flights", []) if isinstance(option, dict) else []
    first = flights[0] if flights else {}
    last = flights[-1] if flights else {}

    dep_air = first.get("departure_airport", {}) if isinstance(first, dict) else {}
    arr_air = last.get("arrival_airport", {}) if isinstance(last, dict) else {}
    dep_date, dep_time = _serp_dt_parts(dep_air.get("time", ""))
    arr_date, arr_time = _serp_dt_parts(arr_air.get("time", ""))

    all_numbers = [
        (f.get("flight_number") or "").strip()
        for f in flights
        if isinstance(f, dict) and (f.get("flight_number") or "").strip()
    ]
    flight_number = " / ".join(all_numbers)

    baggage = ""
    for ext in option.get("extensions", []) or []:
        if isinstance(ext, str) and "baggage" in ext.lower():
            baggage = ext
            break

    return {
        "flight_number": flight_number,
        "airline": first.get("airline", ""),
        "departure_date": dep_date,
        "departure_time": dep_time,
        "departure_airport": dep_air.get("id", ""),
        "departure_city": dep_air.get("name", ""),
        "departure_terminal": "",
        "arrival_date": arr_date,
        "arrival_time": arr_time,
        "arrival_airport": arr_air.get("id", ""),
        "arrival_city": arr_air.get("name", ""),
        "arrival_terminal": "",
        "duration": _serp_minutes_to_duration(option.get("total_duration")),
        "baggage": baggage,
    }


@booking_bp.post("/api/flights/generate_from_serp")
def generate_flight_from_serp():
    """Generate flight booking HTML from selected SerpAPI options."""
    payload = request.get_json(force=True) or {}
    template_type = (payload.get("template_type") or "vivavivu").strip().lower()

    selected_outbound = payload.get("selected_outbound") or {}
    selected_return = payload.get("selected_return") or {}
    trip_type = payload.get("trip_type", "One way")
    passengers = payload.get("passengers") or []

    if not selected_outbound:
        return jsonify({"error": "selected_outbound is required"}), 400

    output_dir = payload.get("output_dir", "output")
    os.makedirs(output_dir, exist_ok=True)

    if template_type == "vietnam_airlines":
        template_path = os.path.join(_BASE_DIR, "templates", "flight_booking.html")
        if not os.path.exists(template_path):
            return jsonify({"error": "Vietnam Airlines template not found"}), 500

        mapped_outbound = _map_serp_option_to_vna_segment(selected_outbound)
        mapped_return = _map_serp_option_to_vna_segment(selected_return or selected_outbound)

        flight_data = {
            "trip_type": trip_type,
            "booking_reference": "",
            "passengers": [
                {"name": (p.get("name") or "").strip(), "type": "Adult"}
                for p in passengers
                if isinstance(p, dict) and (p.get("name") or "").strip()
            ],
            "outbound_flight": mapped_outbound,
            "return_flight": mapped_return,
        }
        html = fill_flight_template(template_path, flight_data)
    else:
        template_path = os.path.join(_BASE_DIR, "templates", "flight_vivavivu.html")
        if not os.path.exists(template_path):
            return jsonify({"error": "Vivavivu template not found"}), 500

        flight_data = {
            "booking_code": payload.get("booking_code"),
            "trip_type": trip_type,
            "contact": payload.get("contact", {}),
            "passengers": passengers,
            "total_price": payload.get("total_price", "0"),
            "discount": payload.get("discount", "0"),
            "currency": payload.get("currency", "VND"),
            "directions": payload.get("directions", []),
        }
        html = fill_vivavivu_template(template_path, flight_data)

    output_path = os.path.join(output_dir, "booking_flight.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    project_id = payload.get("project_id")
    if project_id:
        existing = db.get_latest_booking(int(project_id)) or {}
        db.save_booking(
            int(project_id),
            booking_data=existing.get("booking_data", {}),
            hotel_htmls=existing.get("hotel_htmls", []),
            flight_html=html,
            reasoning=existing.get("reasoning", ""),
        )

    return jsonify({
        "status": "success",
        "flight_html": html,
        "flight_path": output_path,
    })


