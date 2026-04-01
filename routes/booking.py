"""
Booking routes: generate bookings, AI booking, trip info extraction.
"""
from __future__ import annotations

import json
import os
import re
import traceback
from datetime import datetime, timedelta
from typing import Any, Dict

from flask import Blueprint, Response, jsonify, request

from langchain_openai import ChatOpenAI

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
from routes.booking_helpers import _BASE_DIR, _OUTPUT_DIR, get_text_model, get_vision_model

booking_bp = Blueprint("booking", __name__)


# Use shared helpers
_get_text_model = get_text_model
_get_vision_model = get_vision_model


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
        import logging; logging.exception("[Safe Log] Unhandled exception in booking.py: %s", e)
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

    from routes.booking_itinerary_parser import parse_trip_from_html
    trip_info = parse_trip_from_html(flight_html, hotel_htmls)
    
    return jsonify({
        "trip_info": trip_info
    })


@booking_bp.post("/api/itinerary/extract_from_text")
def extract_trip_from_text():
    """Extract trip info (guests, dates, purpose) from plain text (e.g. PDF-extracted text)."""
    payload = request.get_json(force=True) or {}
    all_text = payload.get("text", "")

    from routes.booking_itinerary_parser import parse_trip_from_text
    trip_info = parse_trip_from_text(all_text)

    return jsonify({
        "trip_info": trip_info
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
            import logging; logging.exception("[Safe Log] Unhandled exception in booking.py: %s", e)
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
        import logging; logging.exception("[Safe Log] Unhandled exception in booking.py: %s", e)
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
                import logging; logging.exception("[Safe Log] Unhandled exception in booking.py: %s", e)
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
            import logging; logging.exception("[Safe Log] Unhandled exception in booking.py: %s", e)
            yield from send_event(-1, f"❌ Lỗi tạo HTML: {str(e)}")

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })

