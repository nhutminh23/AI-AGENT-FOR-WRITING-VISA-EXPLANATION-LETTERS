"""
Booking Generator Module for Passport Lounge
Generates realistic hotel and flight booking confirmations for visa applications.
"""

import json
import os
import random
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


# Load hotels database
def load_hotels_database() -> Dict:
    """Load the verified hotels database."""
    db_path = os.path.join(os.path.dirname(__file__), "hotels_database.json")
    with open(db_path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_booking_id() -> str:
    """Generate a realistic 10-digit booking ID."""
    return str(random.randint(1000000000, 9999999999))


def generate_booking_reference() -> str:
    """Generate a realistic 10-digit booking reference."""
    return str(random.randint(1000000000, 9999999999))


def generate_flight_reference() -> str:
    """Generate a 6-character alphanumeric PNR code."""
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(random.choice(chars) for _ in range(6))


def calculate_hotel_splits(num_days: int, destination: str, db: Dict) -> List[Dict]:
    """
    Calculate how to split hotel stays across cities.
    
    Split logic:
    - 1-4 days: 1 hotel
    - 5-7 days: 2 hotels
    - 8-10 days: 2-3 hotels
    - 11+ days: 3-4 hotels
    """
    if destination not in db:
        return []
    
    cities = list(db[destination].keys())
    if not cities:
        return []
    
    # Determine number of hotels based on trip length
    if num_days <= 4:
        num_hotels = 1
    elif num_days <= 7:
        num_hotels = 2
    elif num_days <= 10:
        num_hotels = random.choice([2, 3])
    else:
        num_hotels = random.choice([3, 4])
    
    # Limit to available cities
    num_hotels = min(num_hotels, len(cities))
    
    # Select cities
    selected_cities = random.sample(cities, num_hotels)
    
    # Distribute days evenly with some variation
    base_days = num_days // num_hotels
    extra_days = num_days % num_hotels
    
    splits = []
    for i, city in enumerate(selected_cities):
        days = base_days + (1 if i < extra_days else 0)
        splits.append({"city": city, "nights": days})
    
    return splits


def select_hotel_for_city(city: str, destination: str, db: Dict) -> Optional[Dict]:
    """Select a random hotel from the database for a given city."""
    if destination not in db or city not in db[destination]:
        return None
    
    hotels = db[destination][city]
    if not hotels:
        return None
    
    return random.choice(hotels)


def generate_hotel_bookings(
    destination: str,
    num_days: int,
    start_date: datetime,
    guest_name: str
) -> List[Dict]:
    """
    Generate hotel booking data based on destination and trip duration.
    
    Args:
        destination: Country name (e.g., "Australia")
        num_days: Total number of nights
        start_date: Check-in date
        guest_name: Guest's full name
    
    Returns:
        List of hotel booking dictionaries
    """
    db = load_hotels_database()
    splits = calculate_hotel_splits(num_days, destination, db)
    
    if not splits:
        return []
    
    bookings = []
    current_date = start_date
    
    for split in splits:
        city = split["city"]
        nights = split["nights"]
        
        hotel = select_hotel_for_city(city, destination, db)
        if not hotel:
            continue
        
        check_in = current_date
        check_out = current_date + timedelta(days=nights)
        
        # Calculate price
        price_per_night = random.randint(
            hotel["price_range"]["min"],
            hotel["price_range"]["max"]
        )
        total_price = price_per_night * nights
        
        # Select room type
        room_type = random.choice(hotel["room_types"])
        
        booking = {
            "booking_id": generate_booking_id(),
            "booking_reference": generate_booking_reference(),
            "hotel_name": hotel["hotel_name"],
            "hotel_address": hotel["hotel_address"],
            "hotel_phone": hotel["hotel_phone"],
            "city": city,
            "country": destination,
            "check_in_date": check_in.strftime("%B %d, %Y"),
            "check_out_date": check_out.strftime("%B %d, %Y"),
            "check_in_date_short": check_in.strftime("%d/%m/%Y"),
            "check_out_date_short": check_out.strftime("%d/%m/%Y"),
            "num_nights": nights,
            "room_type": room_type,
            "num_rooms": 1,
            "num_adults": 1,
            "num_children": 0,
            "price_per_night": f"{price_per_night:.2f}",
            "total_price": f"{total_price:.2f}",
            "currency": hotel["currency"],
            "guest_name": guest_name,
            "star_rating": hotel["star_rating"],
            "benefits": "Breakfast included, Free WiFi, Non-smoking room",
            "cancellation_policy": "Free cancellation before " + (check_in - timedelta(days=3)).strftime("%B %d, %Y")
        }
        
        bookings.append(booking)
        current_date = check_out
    
    return bookings


def generate_flight_booking(
    origin_airport: str,
    destination: str,
    departure_date: datetime,
    return_date: datetime,
    passengers: List[str]
) -> Dict:
    """
    Generate flight booking data.
    
    Args:
        origin_airport: Origin airport code (HAN or SGN)
        destination: Destination country
        departure_date: Departure date
        return_date: Return date  
        passengers: List of passenger names
    
    Returns:
        Flight booking dictionary
    """
    db = load_hotels_database()
    flights_data = db.get("flights", {})
    
    route_key = f"Vietnam_{destination}"
    if route_key not in flights_data:
        # Fallback to default Vietnam Airlines
        route_key = "Vietnam_Australia"
    
    airlines = flights_data.get(route_key, [])
    if not airlines:
        return {}
    
    # Prefer Vietnam Airlines
    airline = next((a for a in airlines if a["airline"] == "Vietnam Airlines"), airlines[0])
    
    # Find outbound route - match origin airport, get any destination
    outbound_route = None
    for route in airline["routes"]:
        if route["from"] == origin_airport:
            outbound_route = route
            break
    
    if not outbound_route:
        # Fallback to first route
        outbound_route = airline["routes"][0]
    
    # Get all possible destination airports for return
    destination_airports = set()
    for route in airline["routes"]:
        if route["from"] == origin_airport:
            destination_airports.add(route["to"])
    
    # Find return route (can be from different city in destination country)
    return_route = None
    for route in airline["routes"]:
        if route["from"] in destination_airports and route["to"] == origin_airport:
            return_route = route
            break
    
    if not return_route:
        # Fallback - any route going back to origin
        for route in airline["routes"]:
            if route["to"] == origin_airport:
                return_route = route
                break
    
    # Generate departure/arrival times
    dep_times = ["07:30", "09:45", "14:20", "18:30", "22:15", "23:30"]
    outbound_dep_time = random.choice(dep_times)
    
    # Calculate arrival time based on duration
    duration_match = re.match(r"(\d+)h (\d+)m", outbound_route["duration"])
    if duration_match:
        hours = int(duration_match.group(1))
        minutes = int(duration_match.group(2))
        
        dep_dt = datetime.strptime(outbound_dep_time, "%H:%M")
        arr_dt = dep_dt + timedelta(hours=hours, minutes=minutes)
        
        # Add timezone offset for Australia (+4 to +5 hours ahead)
        arr_dt = arr_dt + timedelta(hours=4)
        
        # Check if crosses midnight
        outbound_arr_date = departure_date
        if arr_dt.hour < dep_dt.hour or (arr_dt.hour == dep_dt.hour and arr_dt.minute < dep_dt.minute):
            outbound_arr_date = departure_date + timedelta(days=1)
        
        outbound_arr_time = arr_dt.strftime("%H:%M")
    else:
        outbound_arr_time = "13:15"
        outbound_arr_date = departure_date + timedelta(days=1)
    
    # Return flight times
    return_dep_times = ["00:50", "06:30", "10:15", "14:00", "18:45"]
    return_dep_time = random.choice(return_dep_times)
    
    # Calculate return arrival
    if return_route:
        duration_match = re.match(r"(\d+)h (\d+)m", return_route["duration"])
        if duration_match:
            hours = int(duration_match.group(1))
            minutes = int(duration_match.group(2))
            
            dep_dt = datetime.strptime(return_dep_time, "%H:%M")
            arr_dt = dep_dt + timedelta(hours=hours, minutes=minutes)
            
            # Subtract timezone offset (going back to Vietnam)
            arr_dt = arr_dt - timedelta(hours=4)
            
            return_arr_time = arr_dt.strftime("%H:%M")
        else:
            return_arr_time = "06:10"
    else:
        return_arr_time = "06:10"
    
    booking = {
        "booking_reference": generate_flight_reference(),
        "passengers": [
            {"name": name.upper(), "type": "Adult"} for name in passengers
        ],
        "outbound_flight": {
            "flight_number": random.choice(outbound_route["flight_numbers"]),
            "airline": airline["airline"],
            "departure_date": departure_date.strftime("%d/%m/%Y"),
            "departure_time": outbound_dep_time,
            "departure_airport": outbound_route["from"],
            "departure_terminal": outbound_route["departure_terminal"],
            "arrival_date": outbound_arr_date.strftime("%d/%m/%Y"),
            "arrival_time": outbound_arr_time,
            "arrival_airport": outbound_route["to"],
            "arrival_terminal": outbound_route["arrival_terminal"],
            "duration": outbound_route["duration"],
            "baggage": airline["baggage"]
        },
        "return_flight": {
            "flight_number": random.choice(return_route["flight_numbers"]) if return_route else "VN 784",
            "airline": airline["airline"],
            "departure_date": return_date.strftime("%d/%m/%Y"),
            "departure_time": return_dep_time,
            "departure_airport": return_route["from"] if return_route else "MEL",
            "departure_terminal": return_route["departure_terminal"] if return_route else "Terminal 2",
            "arrival_date": return_date.strftime("%d/%m/%Y"),
            "arrival_time": return_arr_time,
            "arrival_airport": origin_airport,
            "arrival_terminal": "Terminal 2",
            "duration": return_route["duration"] if return_route else "9h 10m",
            "baggage": airline["baggage"]
        }
    }
    
    return booking


def _split_address_for_template(address: str):
    """Split an address string into up to 3 lines for the hotel template.
    
    The Agoda template has 3 positioned divs for the address.
    We need to distribute the address text across these 3 lines.
    """
    if not address:
        return "", "", ""
    
    parts = [p.strip() for p in address.split(',')]
    
    if len(parts) <= 1:
        return address, "", ""
    elif len(parts) == 2:
        return parts[0] + ",", parts[1], ""
    elif len(parts) == 3:
        return parts[0] + ",", parts[1] + ",", parts[2]
    else:
        # 4+ parts: first on line 1, middle on line 2, last on line 3
        line1 = parts[0] + ","
        line3 = parts[-1]
        line2 = ", ".join(parts[1:-1]) + ","
        return line1, line2, line3


def fill_hotel_template(template_path: str, booking_data: Dict) -> str:
    """
    Fill the hotel booking HTML template with actual data.
    
    The template is a PDF-to-HTML conversion where text is stored in
    individually positioned <span> elements. The address is split across
    3 separate <div> elements, so we must replace each line individually
    using the actual text fragments found in the template.
    
    Args:
        template_path: Path to the HTML template
        booking_data: Dictionary with booking information
    
    Returns:
        Filled HTML string
    """
    import re as _re

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()
    
    # Clean price to prevent "AUD AUD" 
    total_price = str(booking_data.get('total_price', '790.00')).strip()
    currency = str(booking_data.get('currency', 'AUD')).strip()
    # Remove currency from start of price if AI included it
    if total_price.upper().startswith(currency.upper()):
        total_price = total_price[len(currency):].strip()
        
    # Room type — use plain text (no wrapping span to avoid layout issues)
    room_type = str(booking_data.get("room_type", "Superior King"))
    
    # ── Simple string replacements (fields that exist as single text runs) ──
    replacements = {
        # Booking IDs
        "1696039455": booking_data.get("booking_id", "1696039455"),
        "6422371149": booking_data.get("booking_reference", "6422371149"),
        
        # Guest name (appears multiple times in template)
        "DO THI THANH HIEN": booking_data.get("guest_name", "DO THI THANH HIEN"),
        
        # Dates
        "March 16, 2026": booking_data.get("check_in_date", "March 16, 2026"),
        "March 18, 2026": booking_data.get("check_out_date", "March 18, 2026"),
        
        # Room details — plain text, no wrapper
        "Superior King": room_type,
        
        # Price
        "AUD 790.00": f"{currency} {total_price}",
    }
    
    result = template
    for old, new in replacements.items():
        result = result.replace(old, str(new))
    
    # ── Regex-based replacements for fields split across elements ──
    # These target specific text content inside positioned <span> tags.
    # Pattern: match text content just before " &nbsp;" or "&nbsp;" inside a span.
    
    def _replace_span_text(html, old_text, new_text):
        """Replace text content inside a span element, preserving &nbsp; suffix."""
        # Escape the old text for regex
        escaped = _re.escape(old_text)
        # Match: >old_text &nbsp;< or >old_text&nbsp;<
        pattern = r'(>)' + escaped + r'(\s*&nbsp;\s*<)'
        replacement = r'\g<1>' + new_text.replace('\\', '\\\\') + r' \2'
        return _re.sub(pattern, replacement, html, count=1)
    
    # Hotel name (line 220 in template: "The Langham Melbourne")
    hotel_name = str(booking_data.get("hotel_name", "The Langham Melbourne"))
    result = _replace_span_text(result, "The Langham Melbourne", hotel_name)
    
    # Hotel phone (line 228: "++61386968888")
    phone = str(booking_data.get("hotel_phone", ""))
    if phone:
        formatted_phone = phone.replace("+", "++").replace(" ", "")
        if not formatted_phone.startswith("++"):
            formatted_phone = "++" + formatted_phone.lstrip("+")
        result = _replace_span_text(result, "++61386968888", formatted_phone)
    
    # ── Address: split across 3 div elements ──
    # Template lines:
    #   Line 223: "1 Southgate Avenue, Southbank, "
    #   Line 224: "Melbourne CBD, Melbourne, Australia, "
    #   Line 225: "3006 "
    new_address = str(booking_data.get("hotel_address", ""))
    if new_address:
        addr1, addr2, addr3 = _split_address_for_template(new_address)
        result = _replace_span_text(result, "1 Southgate Avenue, Southbank,", addr1)
        result = _replace_span_text(result, "Melbourne CBD, Melbourne, Australia,", addr2)
        result = _replace_span_text(result, "3006", addr3)
    
    # ── Cancellation policy date (1 day before check-in) ──
    # Template line 230 mentions "March 15, 2026" (1 day before check-in "March 16, 2026")
    check_in = booking_data.get("check_in_date", "")
    if check_in:
        try:
            from datetime import datetime, timedelta
            cin_dt = datetime.strptime(check_in, "%B %d, %Y")
            cancel_dt = cin_dt - timedelta(days=1)
            cancel_str = cancel_dt.strftime("%B %d, %Y")
            # Remove leading zero from day, e.g. "March 04" -> "March 4"
            cancel_str = _re.sub(r' 0(\d)', r' \1', cancel_str)
            result = result.replace("March 15, 2026", cancel_str)
        except Exception:
            pass
    
    # ── Font fix: override embedded PDF subset fonts with system font ──
    # The PDF-to-HTML template embeds fonts as base64 subsets containing only
    # the original glyphs. When we replace text with new characters, those
    # characters fall back to a different font, causing visual inconsistency.
    # Solution: inject CSS that overrides all PDF font classes with Arial
    # (which is visually equivalent to Liberation Sans).
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
    result = result.replace("</head>", font_override_css + "\n</head>")
    
    return result


def fill_flight_template(template_path: str, flight_data: Dict) -> str:
    """
    Fill the flight booking HTML template with actual data.
    Uses regex-based HTML element matching for bulletproof replacements.
    """
    import re as _re

    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    outbound = flight_data.get("outbound_flight", {})
    return_fl = flight_data.get("return_flight", {})
    passengers = flight_data.get("passengers", [])

    # --- Split HTML into Route 1, Route 2, and Passenger sections ---
    # Find the split points using section titles
    route2_start = html.find('Route 2')
    passenger_start = html.find('Passenger information')

    if route2_start == -1 or passenger_start == -1:
        # Fallback: return template as-is
        return html

    # Find the card boundaries for Route 1 and Route 2
    # Route 1 card: from first <div class="card"> to just before Route 2
    route1_section_start = html.find('<div class="card">')
    route2_section_start = html.rfind('<div class="card">', 0, passenger_start)

    section_route1 = html[route1_section_start:route2_start]
    section_route2 = html[route2_start:passenger_start]
    section_passengers = html[passenger_start:]
    section_before = html[:route1_section_start]

    # --- Helper: replace content inside HTML elements by class ---
    def _replace_by_class(section, css_class, new_value, count=1):
        """Replace content of <div class="css_class">OLD</div> with new_value."""
        pattern = _re.compile(
            r'(<(?:div|span)\s+class="' + _re.escape(css_class) + r'">)(.*?)(</(?:div|span)>)',
            _re.DOTALL
        )
        def _replacer(m):
            return m.group(1) + new_value + m.group(3)
        return pattern.sub(_replacer, section, count=count)

    def _replace_pill(section, new_value):
        """Replace content of <div class="pill">OLD</div>."""
        return _replace_by_class(section, "pill", new_value, count=1)

    # --- Route 1 (Outbound) ---
    out_dep_date = outbound.get("departure_date", "10/03/2026")
    out_dep_time = outbound.get("departure_time", "23:30")
    out_dep_airport = outbound.get("departure_airport", "HAN")
    out_dep_terminal = outbound.get("departure_terminal", "Terminal 2")
    out_arr_date = outbound.get("arrival_date", "11/03/2026")
    out_arr_time = outbound.get("arrival_time", "13:15")
    out_arr_airport = outbound.get("arrival_airport", "SYD")
    out_arr_terminal = outbound.get("arrival_terminal", "Terminal 1")
    out_duration = outbound.get("duration", "9h 45m")
    out_flight_num = outbound.get("flight_number", "VN 787")
    out_baggage = outbound.get("baggage", "Free baggage: 1 piece 23KG , 1 piece 23KG")

    # Replace Route 1 elements using regex
    # Dates (2 occurrences in Route 1: departure date, arrival date)
    date_pattern = _re.compile(r'(<div class="date">)(.*?)(</div>)', _re.DOTALL)
    date_matches = list(date_pattern.finditer(section_route1))
    if len(date_matches) >= 2:
        # Replace in reverse order to preserve positions
        section_route1 = (
            section_route1[:date_matches[0].start(2)] + out_dep_date +
            section_route1[date_matches[0].end(2):date_matches[1].start(2)] + out_arr_date +
            section_route1[date_matches[1].end(2):]
        )

    # Times
    time_pattern = _re.compile(r'(<div class="time">)(.*?)(</div>)', _re.DOTALL)
    time_matches = list(time_pattern.finditer(section_route1))
    if len(time_matches) >= 2:
        section_route1 = (
            section_route1[:time_matches[0].start(2)] + out_dep_time +
            section_route1[time_matches[0].end(2):time_matches[1].start(2)] + out_arr_time +
            section_route1[time_matches[1].end(2):]
        )

    # Airport codes
    ac_pattern = _re.compile(r'(<div class="airport-code">)(.*?)(</div>)', _re.DOTALL)
    ac_matches = list(ac_pattern.finditer(section_route1))
    if len(ac_matches) >= 2:
        section_route1 = (
            section_route1[:ac_matches[0].start(2)] + out_dep_airport +
            section_route1[ac_matches[0].end(2):ac_matches[1].start(2)] + out_arr_airport +
            section_route1[ac_matches[1].end(2):]
        )

    # Terminals
    term_pattern = _re.compile(r'(<div class="terminal">)(.*?)(</div>)', _re.DOTALL)
    term_matches = list(term_pattern.finditer(section_route1))
    if len(term_matches) >= 2:
        section_route1 = (
            section_route1[:term_matches[0].start(2)] + out_dep_terminal +
            section_route1[term_matches[0].end(2):term_matches[1].start(2)] + out_arr_terminal +
            section_route1[term_matches[1].end(2):]
        )

    # Duration pill
    section_route1 = _replace_pill(section_route1, out_duration)

    # Flight number
    section_route1 = _replace_by_class(section_route1, "flight-number", out_flight_num)

    # Baggage
    baggage_pattern = _re.compile(r'(<div class="baggage-info">.*?<span>)(.*?)(</span>)', _re.DOTALL)
    section_route1 = baggage_pattern.sub(r'\g<1>' + out_baggage + r'\3', section_route1, count=1)

    # --- Route 2 (Return) ---
    ret_dep_date = return_fl.get("departure_date", "19/03/2026")
    ret_dep_time = return_fl.get("departure_time", "00:50")
    ret_dep_airport = return_fl.get("departure_airport", "MEL")
    ret_dep_terminal = return_fl.get("departure_terminal", "Terminal 2")
    ret_arr_date = return_fl.get("arrival_date", "19/03/2026")
    ret_arr_time = return_fl.get("arrival_time", "06:10")
    ret_arr_airport = return_fl.get("arrival_airport", "HAN")
    ret_arr_terminal = return_fl.get("arrival_terminal", "Terminal 2")
    ret_duration = return_fl.get("duration", "9h 20m")
    ret_flight_num = return_fl.get("flight_number", "VN 778")

    # Replace Route 2 elements
    date_matches = list(date_pattern.finditer(section_route2))
    if len(date_matches) >= 2:
        section_route2 = (
            section_route2[:date_matches[0].start(2)] + ret_dep_date +
            section_route2[date_matches[0].end(2):date_matches[1].start(2)] + ret_arr_date +
            section_route2[date_matches[1].end(2):]
        )

    time_matches = list(time_pattern.finditer(section_route2))
    if len(time_matches) >= 2:
        section_route2 = (
            section_route2[:time_matches[0].start(2)] + ret_dep_time +
            section_route2[time_matches[0].end(2):time_matches[1].start(2)] + ret_arr_time +
            section_route2[time_matches[1].end(2):]
        )

    ac_matches = list(ac_pattern.finditer(section_route2))
    if len(ac_matches) >= 2:
        section_route2 = (
            section_route2[:ac_matches[0].start(2)] + ret_dep_airport +
            section_route2[ac_matches[0].end(2):ac_matches[1].start(2)] + ret_arr_airport +
            section_route2[ac_matches[1].end(2):]
        )

    term_matches = list(term_pattern.finditer(section_route2))
    if len(term_matches) >= 2:
        section_route2 = (
            section_route2[:term_matches[0].start(2)] + ret_dep_terminal +
            section_route2[term_matches[0].end(2):term_matches[1].start(2)] + ret_arr_terminal +
            section_route2[term_matches[1].end(2):]
        )

    section_route2 = _replace_pill(section_route2, ret_duration)
    section_route2 = _replace_by_class(section_route2, "flight-number", ret_flight_num)

    # --- Passengers ---
    p1_name = passengers[0]["name"] if passengers else "THI THANH HIEN DO"
    p2_name = passengers[1]["name"] if len(passengers) > 1 else "NGOC KHUE VU"

    # Replace passenger names using p-name class
    pname_pattern = _re.compile(r'(<span class="p-name">)(.*?)(</span>)', _re.DOTALL)
    pname_matches = list(pname_pattern.finditer(section_passengers))
    if len(pname_matches) >= 2:
        section_passengers = (
            section_passengers[:pname_matches[0].start(2)] + p1_name +
            section_passengers[pname_matches[0].end(2):pname_matches[1].start(2)] + p2_name +
            section_passengers[pname_matches[1].end(2):]
        )
    elif len(pname_matches) == 1:
        section_passengers = pname_pattern.sub(r'\g<1>' + p1_name + r'\3', section_passengers, count=1)

    # Replace route details in passenger section using city names from data
    out_dep_city = outbound.get("departure_city", "Hanoi")
    out_arr_city = outbound.get("arrival_city", "Sydney")
    ret_dep_city = return_fl.get("departure_city", "Melbourne")
    ret_arr_city = return_fl.get("arrival_city", "Hanoi")

    # Determine country from airport code
    _airport_country = {
        "HAN": "Vietnam", "SGN": "Vietnam", "DAD": "Vietnam",
        "SYD": "Australia", "MEL": "Australia", "BNE": "Australia",
        "NRT": "Japan", "HND": "Japan", "KIX": "Japan",
        "ICN": "South Korea", "SIN": "Singapore", "BKK": "Thailand",
        "CDG": "France", "LHR": "United Kingdom", "LAX": "United States",
        "YVR": "Canada", "YYZ": "Canada", "AKL": "New Zealand",
    }

    out_dep_country = _airport_country.get(out_dep_airport, "Vietnam")
    out_arr_country = _airport_country.get(out_arr_airport, "")
    ret_dep_country = _airport_country.get(ret_dep_airport, "")
    ret_arr_country = _airport_country.get(ret_arr_airport, "Vietnam")

    # Build new route descriptions
    route1_dep_desc = f"{out_dep_city} ({out_dep_airport}), {out_dep_country}"
    route1_arr_desc = f"{out_arr_city} ({out_arr_airport}), {out_arr_country}"
    route2_dep_desc = f"{ret_dep_city} ({ret_dep_airport}), {ret_dep_country}"
    route2_arr_desc = f"{ret_arr_city} ({ret_arr_airport}), {ret_arr_country}"

    # Replace in template - original has "Hanoi (HAN), Vietnam" etc. 
    section_passengers = section_passengers.replace("Hanoi (HAN), Vietnam", route1_dep_desc)
    section_passengers = section_passengers.replace("Sydney (SYD), Australia", route1_arr_desc)
    section_passengers = section_passengers.replace("Melbourne (MEL), Australia", route2_dep_desc)

    # Reassemble
    result = section_before + section_route1 + section_route2 + section_passengers

    return result




def generate_all_bookings(
    destination: str,
    num_days: int,
    guest_name: str,
    origin_airport: str = "HAN",
    start_date: Optional[datetime] = None
) -> Tuple[List[Dict], Dict]:
    """
    Generate all booking data (hotels + flight) for a trip.
    
    Args:
        destination: Destination country
        num_days: Number of days/nights
        guest_name: Guest's full name
        origin_airport: Origin airport code (HAN or SGN)
        start_date: Start date (defaults to today + 3 months)
    
    Returns:
        Tuple of (hotel_bookings, flight_booking)
    """
    if start_date is None:
        start_date = datetime.now() + timedelta(days=90)  # 3 months from now
    
    # Generate hotel bookings
    hotel_bookings = generate_hotel_bookings(
        destination=destination,
        num_days=num_days,
        start_date=start_date,
        guest_name=guest_name
    )
    
    # Calculate return date based on hotel bookings
    if hotel_bookings:
        last_checkout = datetime.strptime(
            hotel_bookings[-1]["check_out_date"], 
            "%B %d, %Y"
        )
        return_date = last_checkout
    else:
        return_date = start_date + timedelta(days=num_days)
    
    # Generate flight booking
    flight_booking = generate_flight_booking(
        origin_airport=origin_airport,
        destination=destination,
        departure_date=start_date,
        return_date=return_date,
        passengers=[guest_name]
    )
    
    return hotel_bookings, flight_booking


def generate_bookings_from_ai(
    ai_booking_data: Dict,
    hotel_template_path: str,
    flight_template_path: str,
    output_dir: str = "output",
) -> Dict:
    """
    Generate booking HTML files from AI-selected hotel/flight data.
    Uses existing HTML templates but fills with AI-chosen real data.

    Args:
        ai_booking_data: JSON from AI Booking Expert agent
        hotel_template_path: Path to hotel HTML template
        flight_template_path: Path to flight HTML template
        output_dir: Directory to save output files

    Returns:
        Dict with hotel_htmls, hotel_paths, flight_html, flight_path
    """
    os.makedirs(output_dir, exist_ok=True)

    result = {
        "hotel_htmls": [],
        "hotel_paths": [],
        "hotel_data": [],
        "flight_html": "",
        "flight_path": "",
        "flight_data": {},
    }

    # --- Generate hotel booking HTMLs ---
    hotels = ai_booking_data.get("hotels", [])
    for i, hotel in enumerate(hotels, 1):
        # Ensure booking IDs exist
        if "booking_id" not in hotel:
            hotel["booking_id"] = str(random.randint(1000000000, 9999999999))
        if "booking_reference" not in hotel:
            hotel["booking_reference"] = str(random.randint(1000000000, 9999999999))

        # Ensure total_price is formatted
        price = hotel.get("total_price", "0")
        if isinstance(price, (int, float)):
            hotel["total_price"] = f"{price:.2f}"
        price_per = hotel.get("price_per_night", "0")
        if isinstance(price_per, (int, float)):
            hotel["price_per_night"] = f"{price_per:.2f}"

        # Fill template
        if os.path.exists(hotel_template_path):
            html = fill_hotel_template(hotel_template_path, hotel)
        else:
            html = f"<pre>{json.dumps(hotel, indent=2, ensure_ascii=False)}</pre>"

        output_path = os.path.join(output_dir, f"booking_hotel_{i}.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        result["hotel_htmls"].append(html)
        result["hotel_paths"].append(output_path)
        result["hotel_data"].append(hotel)

    # --- Generate flight booking HTML ---
    flight = ai_booking_data.get("flight", {})
    if flight:
        # Adapt AI output keys to match fill_flight_template expected format
        outbound = flight.get("outbound", {})
        return_fl = flight.get("return", {})

        def _clean_iata(code: str) -> str:
            """Extract 3-letter IATA code from potentially verbose AI output."""
            import re
            if not code:
                return code
            code = code.strip()
            if len(code) == 3 and code.isalpha():
                return code.upper()
            # Try to find 3-letter code in parentheses: "Noi Bai International Airport (HAN)"
            match = re.search(r'\(([A-Z]{3})\)', code)
            if match:
                return match.group(1)
            # Try to find standalone 3-letter code
            match = re.search(r'\b([A-Z]{3})\b', code.upper())
            if match:
                return match.group(1)
            return code[:3].upper() if len(code) >= 3 else code.upper()

        flight_template_data = {
            "booking_reference": flight.get("booking_reference", generate_flight_reference()),
            "passengers": flight.get("passengers", []),
            "outbound_flight": {
                "flight_number": outbound.get("flight_number", ""),
                "airline": flight.get("airline", "Vietnam Airlines"),
                "departure_date": outbound.get("departure_date", ""),
                "departure_time": outbound.get("departure_time", ""),
                "departure_airport": _clean_iata(outbound.get("departure_airport", "")),
                "departure_city": outbound.get("departure_city", "Hanoi"),
                "departure_terminal": outbound.get("departure_terminal", ""),
                "arrival_date": outbound.get("arrival_date", ""),
                "arrival_time": outbound.get("arrival_time", ""),
                "arrival_airport": _clean_iata(outbound.get("arrival_airport", "")),
                "arrival_city": outbound.get("arrival_city", "Sydney"),
                "arrival_terminal": outbound.get("arrival_terminal", ""),
                "duration": outbound.get("duration", ""),
                "baggage": flight.get("baggage", "Free baggage: 1 piece 23KG , 1 piece 23KG"),
            },
            "return_flight": {
                "flight_number": return_fl.get("flight_number", ""),
                "airline": flight.get("airline", "Vietnam Airlines"),
                "departure_date": return_fl.get("departure_date", ""),
                "departure_time": return_fl.get("departure_time", ""),
                "departure_airport": _clean_iata(return_fl.get("departure_airport", "")),
                "departure_city": return_fl.get("departure_city", "Melbourne"),
                "departure_terminal": return_fl.get("departure_terminal", ""),
                "arrival_date": return_fl.get("arrival_date", ""),
                "arrival_time": return_fl.get("arrival_time", ""),
                "arrival_airport": _clean_iata(return_fl.get("arrival_airport", "")),
                "arrival_city": return_fl.get("arrival_city", "Hanoi"),
                "arrival_terminal": return_fl.get("arrival_terminal", ""),
                "duration": return_fl.get("duration", ""),
                "baggage": flight.get("baggage", "Free baggage: 1 piece 23KG , 1 piece 23KG"),
            },
        }

        if os.path.exists(flight_template_path):
            flight_html = fill_flight_template(flight_template_path, flight_template_data)
        else:
            flight_html = f"<pre>{json.dumps(flight, indent=2, ensure_ascii=False)}</pre>"

        flight_output_path = os.path.join(output_dir, "booking_flight.html")
        with open(flight_output_path, "w", encoding="utf-8") as f:
            f.write(flight_html)

        result["flight_html"] = flight_html
        result["flight_path"] = flight_output_path
        result["flight_data"] = flight_template_data

    return result


# Main function for testing
if __name__ == "__main__":
    # Test booking generation
    hotels, flight = generate_all_bookings(
        destination="Australia",
        num_days=10,
        guest_name="NGUYEN VAN A"
    )
    
    print("=== HOTEL BOOKINGS ===")
    for i, hotel in enumerate(hotels, 1):
        print(f"\nBooking {i}:")
        print(f"  Hotel: {hotel['hotel_name']}")
        print(f"  City: {hotel['city']}")
        print(f"  Check-in: {hotel['check_in_date']}")
        print(f"  Check-out: {hotel['check_out_date']}")
        print(f"  Nights: {hotel['num_nights']}")
        print(f"  Price: {hotel['currency']} {hotel['total_price']}")
    
    print("\n=== FLIGHT BOOKING ===")
    print(f"Reference: {flight['booking_reference']}")
    print(f"Outbound: {flight['outbound_flight']['flight_number']} "
          f"{flight['outbound_flight']['departure_airport']} → "
          f"{flight['outbound_flight']['arrival_airport']}")
    print(f"Return: {flight['return_flight']['flight_number']} "
          f"{flight['return_flight']['departure_airport']} → "
          f"{flight['return_flight']['arrival_airport']}")
