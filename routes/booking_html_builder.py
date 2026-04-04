import os
import json
import re
import random
import logging
from datetime import datetime, timedelta
import database as db

# Helper functions for string formatting
def _fmt_date(date_str):
    if not date_str:
        return "N/A"
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime("%B %d, %Y")
        except ValueError:
            continue
    return date_str

def _day_of_week(date_str):
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
    if not addr:
        return ("", "", "")
    parts = [p.strip() for p in addr.split(",")]
    if len(parts) <= 1:
        return (addr, "", "")
    elif len(parts) == 2:
        return (parts[0] + ",", parts[1], "")
    else:
        mid = len(parts) // 2
        line1 = ", ".join(parts[:mid]) + ","
        line2 = ", ".join(parts[mid:-1]) + ","
        line3 = parts[-1]
        return (line1, line2, line3)

def _format_price_with_currency_code(price_str):
    if not price_str or price_str == "N/A":
        return price_str
    price_str = price_str.strip()
    symbol_to_code = {
        "A$": "AUD", "C$": "CAD", "NZ$": "NZD", "S$": "SGD",
        "HK$": "HKD", "NT$": "TWD", "R$": "BRL", "MX$": "MXN",
        "$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY", "₩": "KRW",
        "₫": "VND", "₹": "INR", "₱": "PHP", "฿": "THB",
        "kr": "SEK", "zł": "PLN", "Kč": "CZK",
    }
    if re.search(r'\s+[A-Z]{3}$', price_str):
        return price_str
    for symbol in sorted(symbol_to_code.keys(), key=len, reverse=True):
        if price_str.startswith(symbol):
            amount = price_str[len(symbol):].strip()
            code = symbol_to_code[symbol]
            return f"{code} {amount}"
    return price_str

def build_hotel_booking_htmls_from_serp(payload, base_dir, serpapi_key=None):
    """
    Core function that builds hotel HTML bookings from SerpAPI data.
    """
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage

    hotel_stops = payload.get("hotel_stops", [])
    guests_all = payload.get("guests", [])
    children = payload.get("children", [])
    output_dir = str(payload.get("output_dir", "output") or "output")
    project_id = str(payload.get("project_id", "") or "")

    if not hotel_stops:
        raise ValueError("hotel_stops is required")

    template_path = os.path.join(base_dir, "templates", "hotel_booking.html")
    with open(template_path, "r", encoding="utf-8") as f:
        template_html = f.read()

    adult_names = guests_all if guests_all else ["Guest"]
    child_names = children if children else []
    num_adults = len(adult_names)
    num_children = len(child_names)
    total_guests = num_adults + num_children
    user_num_rooms = payload.get("num_rooms", 0) or 0
    num_rooms = int(user_num_rooms) if int(user_num_rooms) > 0 else (1 if total_guests <= 3 else 2)

    client_name = ", ".join([n.upper() for n in adult_names])
    guest_list = ", ".join([n.upper() for n in adult_names + child_names])

    saved_files = []
    first_html = ""
    base = os.path.join(base_dir, output_dir)
    os.makedirs(base, exist_ok=True)

    # Database load mapping
    _db_hotels_flat = {}
    try:
        _db_path = os.path.join(base_dir, "booking", "hotels_database.json")
        with open(_db_path, "r", encoding="utf-8") as f:
            _hotels_db = json.load(f)
        for country, cities in _hotels_db.items():
            if country == "flights": continue
            if isinstance(cities, dict):
                for city, hotels_list in cities.items():
                    if isinstance(hotels_list, list):
                        for h in hotels_list:
                            name_key = h.get("hotel_name", "").strip().lower()
                            if name_key:
                                _db_hotels_flat[name_key] = h
    except Exception as e:
        logging.exception("[Safe Log] Could not load hotels database: %s", e)

    def _find_in_database(hotel_name):
        if not hotel_name or not _db_hotels_flat: return None
        name_lower = hotel_name.strip().lower()
        if name_lower in _db_hotels_flat: return _db_hotels_flat[name_lower]
        for db_name, db_hotel in _db_hotels_flat.items():
            if db_name in name_lower or name_lower in db_name: return db_hotel
        name_words = set(name_lower.split())
        skip_words = {"hotel", "the", "a", "an", "resort", "&", "spa", "and"}
        name_key_words = name_words - skip_words
        if len(name_key_words) >= 2:
            for db_name, db_hotel in _db_hotels_flat.items():
                db_words = set(db_name.split()) - skip_words
                common = name_key_words & db_words
                if len(common) >= 2: return db_hotel
        return None

    hotels_still_needing_ai = []
    for idx, hs in enumerate(hotel_stops):
        missing_address = not hs.get("hotel_address", "").strip()
        missing_phone = not hs.get("phone", "").strip()
        missing_room = not hs.get("room_type", "").strip()
        if not (missing_address or missing_phone or missing_room):
            continue
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
        if missing_address or missing_phone or missing_room:
            hotels_still_needing_ai.append((idx, hs))

    hotels_with_token = [(idx, hs) for idx, hs in hotels_still_needing_ai if hs.get("property_token", "").strip()]
    if hotels_with_token and serpapi_key:
        try:
            from serpapi import GoogleSearch
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
                        "api_key": serpapi_key,
                    }
                    search = GoogleSearch(params)
                    prop = search.get_dict()
                    if not hs.get("hotel_address", "").strip():
                        addr = prop.get("address", "") or prop.get("location", "")
                        if addr: hs["hotel_address"] = addr
                    if not hs.get("phone", "").strip():
                        phone = prop.get("phone", "")
                        if phone: hs["phone"] = phone
                    if not hs.get("room_type", "").strip():
                        prices = prop.get("prices", [])
                        if prices and isinstance(prices, list) and len(prices) > 0:
                            room_name = prices[0].get("name", "") or prices[0].get("room_name", "")
                            if room_name: hs["room_type"] = room_name
                    return True
                except Exception as e:
                    logging.exception("[Safe Log] SerpAPI Details failed: %s", e)
                    return False
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(3, len(hotels_with_token))) as executor:
                list(executor.map(_fetch_property_details, hotels_with_token))
        except Exception as e:
            logging.exception("[Safe Log] SerpAPI Property Details setup error: %s", e)

    hotels_still_needing_ai = []
    for idx, hs in enumerate(hotel_stops):
        if not hs.get("hotel_address", "").strip() or not hs.get("phone", "").strip() or not hs.get("room_type", "").strip():
            hotels_still_needing_ai.append((idx, hs))

    if hotels_still_needing_ai:
        try:
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7, max_tokens=1000)
            hotel_descriptions = []
            for idx, hs in hotels_still_needing_ai:
                missing_fields = []
                if not hs.get("hotel_address", "").strip(): missing_fields.append("address")
                if not hs.get("phone", "").strip(): missing_fields.append("phone")
                if not hs.get("room_type", "").strip(): missing_fields.append("room_type")
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
            ai_response = llm.invoke([HumanMessage(content=prompt)])
            ai_text = ai_response.content.strip()
            json_match = re.search(r'\[.*\]', ai_text, re.DOTALL)
            if json_match:
                ai_data = json.loads(json_match.group())
                for item in ai_data:
                    hi = item.get("hotel_index", 0)
                    if isinstance(hi, int) and 0 <= hi < len(hotel_stops):
                        hs = hotel_stops[hi]
                    elif isinstance(hi, int) and hi > 0 and (hi - 1) < len(hotel_stops):
                        hs = hotel_stops[hi - 1]
                    else: continue
                    if not hs.get("hotel_address", "").strip() and item.get("address"): hs["hotel_address"] = item["address"]
                    if not hs.get("phone", "").strip() and item.get("phone"): hs["phone"] = item["phone"]
                    if not hs.get("room_type", "").strip() and item.get("room_type"): hs["room_type"] = item["room_type"]
        except Exception as e:
            logging.exception("[Safe Log] AI generation failed, using defaults: %s", e)

    # Generate one member ID for the entire batch to ensure consistency for the same user
    session_member_id = str(random.randint(100000000, 999999999))

    for i, hs in enumerate(hotel_stops):
        booking_id = str(random.randint(1000000000, 9999999999))
        booking_ref = str(random.randint(1000000000, 9999999999))
        member_id = session_member_id

        check_in = hs.get("check_in", "")
        check_out = hs.get("check_out", "")
        hotel_name = hs.get("hotel_name", "Hotel")
        hotel_address = hs.get("hotel_address", "") or hs.get("city", "")
        total_price_raw = hs.get("total_price", "") or hs.get("price_per_night", "N/A")
        total_price = _format_price_with_currency_code(str(total_price_raw))
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
        html = html.replace("{{TOTAL_PRICE}}", total_price)
        html = html.replace("{{GUEST_LIST}}", guest_list)

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

        fname = f"booking_hotel_{i + 1}.html"
        fpath = os.path.join(base, fname)
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(html)
            saved_files.append(fpath)
        except Exception as e:
            logging.exception("[Safe Log] Could not save %s: %s", fname, e)

        if i == 0:
            first_html = html

    all_htmls = []
    for i, hs in enumerate(hotel_stops):
        fname = f"booking_hotel_{i + 1}.html"
        fpath = os.path.join(base, fname)
        if fpath in saved_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    all_htmls.append(f.read())
            except Exception as e:
                logging.exception("[Safe Log] Error reading HTML: %s", e)
                all_htmls.append(first_html if i == 0 else "")

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
        except Exception as e:
            logging.exception("[Safe Log] Could not save to DB: %s", e)

    return {
        "hotel_html": first_html,
        "hotel_htmls": all_htmls,
        "saved_files": [os.path.basename(f) for f in saved_files],
        "file_count": len(saved_files),
    }
