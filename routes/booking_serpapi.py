"""
SerpAPI-based booking routes: flights search, hotels search, ticket generation.
"""
from __future__ import annotations
import logging

import json
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict

from flask import Blueprint, jsonify, request

from langchain_openai import ChatOpenAI

import database as db
from booking.generator import (
    fill_flight_template,
    fill_vivavivu_template,
)
from routes.booking_helpers import _BASE_DIR, get_serpapi_key

booking_serpapi_bp = Blueprint("booking_serpapi", __name__)


# ---------------------------------------------------------------------------
# SerpAPI: Flight search
# ---------------------------------------------------------------------------

@booking_serpapi_bp.post("/api/flights/search")
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

    if flight_type != "3":
        if not departure_id or not outbound_date:
            return jsonify({"error": "departure_id and outbound_date are required"}), 400
        if not arrival_id:
            return jsonify({"error": "arrival_id is required"}), 400

    params = {
        "engine": "google_flights",
        "hl": payload.get("hl", "en"),
        "gl": payload.get("gl", "vn"),
        "type": flight_type,
        "adults": int(payload.get("adults", 1)),
        "currency": payload.get("currency", "VND"),
        "api_key": get_serpapi_key(),
    }

    # Multi-city uses only multi_city_json; standard uses departure_id/arrival_id/outbound_date
    if flight_type == "3":
        if payload.get("multi_city_json"):
            params["multi_city_json"] = payload["multi_city_json"]
        else:
            return jsonify({"error": "multi_city_json is required for multi-city searches"}), 400
    else:
        params["departure_id"] = departure_id
        params["arrival_id"] = arrival_id
        params["outbound_date"] = outbound_date
        if payload.get("return_date"):
            params["return_date"] = payload["return_date"]

    if payload.get("children"):
        params["children"] = int(payload["children"])
    if payload.get("departure_token"):
        params["departure_token"] = payload["departure_token"]

    # Debug log
    debug_params = {k: v for k, v in params.items() if k != "api_key"}
    print(f"[FLIGHTS] SerpAPI params: {debug_params}")

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
    except Exception as e:
        logging.exception("[Safe Log] Unhandled exception in booking_serpapi.py: %s", e)
        return jsonify({"error": f"SerpAPI error: {str(e)}"}), 500

    best = results.get("best_flights", [])
    other = results.get("other_flights", [])
    print(f"[FLIGHTS] Results: {len(best)} best, {len(other)} other flights")
    if not best and not other:
        print(f"[FLIGHTS] SerpAPI raw keys: {list(results.keys())}")
        if "error" in results:
            print(f"[FLIGHTS] SerpAPI error: {results['error']}")

    return jsonify({
        "best_flights": best,
        "other_flights": other,
        "search_parameters": results.get("search_parameters", {}),
    })


# ---------------------------------------------------------------------------
# SerpAPI: Hotel search (itinerary-based multi-city)
# ---------------------------------------------------------------------------

@booking_serpapi_bp.post("/api/hotels/search-itinerary")
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

    api_key = get_serpapi_key()

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
            logging.exception("[Safe Log] Unhandled exception in booking_serpapi.py: %s", e)
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


# ---------------------------------------------------------------------------
# Generate hotel booking HTML from SerpAPI results
# ---------------------------------------------------------------------------

@booking_serpapi_bp.post("/api/hotels/generate-booking")
def generate_hotel_booking_from_serp():
    """Generate hotel booking HTML from selected SerpAPI hotel results using Agoda template."""
    payload = request.get_json(force=True) or {}
    
    from routes.booking_html_builder import build_hotel_booking_htmls_from_serp
    
    try:
        api_key = get_serpapi_key()
    except Exception:
        api_key = None
        
    try:
        result = build_hotel_booking_htmls_from_serp(payload, _BASE_DIR, api_key)
        return jsonify(result)
    except Exception as e:
        logging.exception("[Safe Log] Unhandled exception in booking_serpapi.py: %s", e)
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Helper: SerpAPI flight data → VNA template mapping
# ---------------------------------------------------------------------------

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
    except Exception as e:
        logging.exception("[Safe Log] Unhandled exception in booking_serpapi.py: %s", e)
        return "", hm


def _serp_minutes_to_duration(minutes: Any) -> str:
    try:
        total = int(minutes or 0)
    except Exception as e:
        logging.exception("[Safe Log] Unhandled exception in booking_serpapi.py: %s", e)
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


# ---------------------------------------------------------------------------
# Generate flight booking HTML from SerpAPI results
# ---------------------------------------------------------------------------

@booking_serpapi_bp.post("/api/flights/generate_from_serp")
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
