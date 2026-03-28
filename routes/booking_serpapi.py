"""
SerpAPI-based booking routes: flights search, hotels search, ticket generation.
"""
from __future__ import annotations

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
    # Room logic: use user-provided value if > 0, else auto-calculate
    user_num_rooms = payload.get("num_rooms", 0) or 0
    num_rooms = int(user_num_rooms) if int(user_num_rooms) > 0 else (1 if total_guests <= 3 else 2)

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

    def _format_price_with_currency_code(price_str):
        """Convert price with currency symbol to Agoda-style format.

        Examples:
            '$2,056'   → '2,056 USD'
            'A$1,500'  → '1,500 AUD'
            'C$800'    → '800 CAD'
            '€1,200'   → '1,200 EUR'
            '£900'     → '900 GBP'
            '2056 USD' → '2,056 USD' (already has code — keep as-is)
        """
        if not price_str or price_str == "N/A":
            return price_str

        price_str = price_str.strip()

        # Map of currency symbols/prefixes → ISO codes
        symbol_to_code = {
            "A$": "AUD", "C$": "CAD", "NZ$": "NZD", "S$": "SGD",
            "HK$": "HKD", "NT$": "TWD", "R$": "BRL", "MX$": "MXN",
            "$": "USD",
            "€": "EUR", "£": "GBP", "¥": "JPY", "₩": "KRW",
            "₫": "VND", "₹": "INR", "₱": "PHP", "฿": "THB",
            "kr": "SEK", "zł": "PLN", "Kč": "CZK",
        }

        # Check if price already ends with a currency code (e.g. "2,056 USD")
        if re.search(r'\s+[A-Z]{3}$', price_str):
            return price_str

        # Try matching symbol prefixes (longer prefixes first)
        for symbol in sorted(symbol_to_code.keys(), key=len, reverse=True):
            if price_str.startswith(symbol):
                amount = price_str[len(symbol):].strip()
                code = symbol_to_code[symbol]
                return f"{code} {amount}"

        # No known symbol found — return as-is
        return price_str

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
            api_key = get_serpapi_key()

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
            json_match = re.search(r'\[.*\]', ai_text, re.DOTALL)
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
        import random as _rand
        booking_id = str(_rand.randint(1000000000, 9999999999))
        booking_ref = str(_rand.randint(1000000000, 9999999999))
        member_id = str(_rand.randint(100000000, 999999999))

        check_in = hs.get("check_in", "")
        check_out = hs.get("check_out", "")
        hotel_name = hs.get("hotel_name", "Hotel")
        hotel_address = hs.get("hotel_address", "") or hs.get("city", "")
        total_price_raw = hs.get("total_price", "") or hs.get("price_per_night", "N/A")
        total_price = _format_price_with_currency_code(str(total_price_raw))
        room_type = hs.get("room_type", "") or "Deluxe Room"
        phone = hs.get("phone", "") or f"+{_rand.randint(1, 99)}{_rand.randint(100000000, 999999999)}"

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
        html = html.replace("{{TOTAL_PRICE}}", total_price)
        html = html.replace("{{GUEST_LIST}}", guest_list)

        # ── Font fix: override embedded PDF subset fonts with system font ──
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
            except Exception as e:
                all_htmls.append(first_html if i == 0 else "")

    # Save to DB so itinerary "from_db" mode can find the SerpAPI hotel bookings
    if project_id:
        try:
            existing = db.get_latest_booking(int(project_id)) or {}
            db.save_booking(
                int(project_id),
                booking_data=existing.get("booking_data", {}),
                hotel_htmls=all_htmls,
                flight_html=existing.get("flight_html", ""),
                reasoning=existing.get("reasoning", ""),
            )
            print(f"[HOTEL-BOOKING] 💾 Saved {len(all_htmls)} hotel booking(s) to DB for project {project_id}")
        except Exception as e:
            print(f"[HOTEL-BOOKING] ⚠️ Could not save to DB: {e}")

    return jsonify({
        "hotel_html": first_html,
        "hotel_htmls": all_htmls,  # Array of HTML content strings for tabs
        "saved_files": [os.path.basename(f) for f in saved_files],
        "file_count": len(saved_files),
    })


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
        return "", hm


def _serp_minutes_to_duration(minutes: Any) -> str:
    try:
        total = int(minutes or 0)
    except Exception as e:
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
