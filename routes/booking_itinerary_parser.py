import re
from datetime import datetime

def parse_trip_from_html(flight_html: str, hotel_htmls: list) -> dict:
    def _strip_tags(html_str):
        text = re.sub(r'<style[^>]*>.*?</style>', '', html_str, flags=re.DOTALL)
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    all_text = _strip_tags(flight_html)
    for h in hotel_htmls:
        all_text += "\n" + _strip_tags(h)

    # Extract dates (YYYY-MM-DD or DD/MM/YYYY patterns)
    dates = []
    for m in re.finditer(r'(\d{4}-\d{2}-\d{2})', all_text):
        dates.append(m.group(1))
    for m in re.finditer(r'(\d{2}/\d{2}/\d{4})', all_text):
        parts = m.group(1).split("/")
        dates.append(f"{parts[2]}-{parts[1]}-{parts[0]}")

    travel_start = min(dates) if dates else ""
    travel_end = max(dates) if dates else ""

    # Extract passenger/guest names from common patterns
    names = set()
    for m in re.finditer(r'(?:Passenger|Guest|Họ tên|Name|Tên)\s*[:\-]\s*([A-ZÀ-Ỹ][A-ZÀ-Ỹa-zà-ỹ\s]{2,40})', all_text):
        name = m.group(1).strip()
        if len(name) > 2 and not any(w in name.lower() for w in ['hotel', 'airline', 'booking', 'check', 'room']):
            names.add(name)
    for m in re.finditer(r'(?:Mr|Mrs|Ms|MR|MRS|MS)\.?\s+([A-ZÀ-Ỹ][A-ZÀ-Ỹa-zà-ỹ\s]{2,40})', all_text):
        name = m.group(1).strip()
        if len(name) > 2:
            names.add(name)
    for m in re.finditer(r'\b([A-ZÀ-Ỹ]{2,}\s+[A-ZÀ-Ỹ]{2,}(?:\s+[A-ZÀ-Ỹ]{2,})*)\b', all_text):
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
    return {
        "guest_names": guest_names,
        "travel_start_date": travel_start,
        "travel_end_date": travel_end,
        "travel_purpose": "Tourism",
    }


def parse_trip_from_text(all_text: str) -> dict:
    if not all_text.strip():
        return {
            "guest_names": [],
            "travel_start_date": "",
            "travel_end_date": "",
            "travel_purpose": "Tourism"
        }

    lines = all_text.split("\n")

    MONTH_MAP = {
        'january': '01', 'february': '02', 'march': '03', 'april': '04',
        'may': '05', 'june': '06', 'july': '07', 'august': '08',
        'september': '09', 'october': '10', 'november': '11', 'december': '12',
    }
    dates = []

    for line in lines:
        for m in re.finditer(r'(\d{4})-(\d{2})-(\d{2})', line):
            dates.append(m.group(0))
        for m in re.finditer(r'(\d{2})/(\d{2})/(\d{4})', line):
            d, mo, y = m.group(1), m.group(2), m.group(3)
            dates.append(f"{y}-{mo}-{d}")
        for m in re.finditer(r'(\b(?:' + '|'.join(MONTH_MAP.keys()) + r')\b)\s+(\d{1,2}),?\s+(\d{4})', line, re.IGNORECASE):
            mo_str = MONTH_MAP.get(m.group(1).lower(), "01")
            dates.append(f"{m.group(3)}-{mo_str}-{int(m.group(2)):02d}")
        for m in re.finditer(r'(\d{1,2})\s+(\b(?:' + '|'.join(MONTH_MAP.keys()) + r')\b)\s+(\d{4})', line, re.IGNORECASE):
            mo_str = MONTH_MAP.get(m.group(2).lower(), "01")
            dates.append(f"{m.group(3)}-{mo_str}-{int(m.group(1)):02d}")

    travel_start = min(dates) if dates else ""
    travel_end = max(dates) if dates else ""

    SKIP_HEADINGS = {
        'CHECK IN', 'CHECK OUT', 'HOTEL NAME', 'ROOM TYPE', 'BOOKING ID',
        'MEMBER ID', 'CONFIRMATION', 'TOTAL PRICE', 'FLIGHT NUMBER',
        'DEPARTURE TIME', 'ARRIVAL TIME', 'BOOKING CONFIRMATION',
        'ECONOMY CLASS', 'BUSINESS CLASS', 'FIRST CLASS', 'ONE WAY',
        'ROUND TRIP', 'GUEST NAME', 'HOTEL BOOKING', 'FLIGHT BOOKING',
        'IATA CODE', 'MEMBER NUMBER', 'BOOKING REFERENCE',
        'TRAVEL ITINERARY', 'VISA APPLICATION', 'DAY NAME', 'HOTEL ADDRESS',
        'TRANSPORTATION', 'DETAILED PROGRAM', 'PURPOSE OF VISIT',
        'MAIN DESTINATION', 'TRAVEL DATES', 'TRAVEL PERIOD', 'FILE OUTPUT',
        'ADDITIONAL INFORMATION', 'TRAVEL PURPOSE', 'APPLICANT NAME',
        'APPLICANTS', 'PARTICIPANTS', 'PAGE', 'TABLE OF CONTENTS',
        'DETAILED ITINERARY', 'ACCOMMODATION', 'FLIGHT DETAILS',
        'HOTEL DETAILS', 'DAY ACTIVITIES', 'MORNING ACTIVITIES',
        'AFTERNOON ACTIVITIES', 'EVENING ACTIVITIES', 'CONTACT INFORMATION',
        'EMERGENCY CONTACT', 'VISA INFORMATION', 'INSURANCE INFORMATION',
        'IMPORTANT NOTES', 'GENERAL NOTES', 'BOOKING DETAILS',
        'HO CHI MINH', 'HO CHI MINH CITY', 'HA NOI', 'DA NANG',
        'ESTIMATED COST', 'TOTAL COST', 'EMAIL ADDRESS',
    }

    names = set()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        m = re.match(r'(?:Applicant|Passenger|Guest|Name|Họ tên|Tên)\s*[:\-]\s*(.+)', stripped, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if 2 < len(candidate) < 40 and candidate.upper() not in SKIP_HEADINGS:
                names.add(candidate.upper())
            continue

        m = re.match(r'(?:Mr|Mrs|Ms|MR|MRS|MS)\.?\s+([A-ZÀ-Ỹ][A-ZÀ-Ỹa-zà-ỹ ]{2,35})$', stripped)
        if m:
            candidate = m.group(1).strip()
            if 2 < len(candidate) < 40 and candidate.upper() not in SKIP_HEADINGS:
                names.add(candidate.upper())
            continue

        if i > 0:
            prev = lines[i-1].strip().upper()
            if prev in ('APPLICANTS', 'PARTICIPANTS', 'APPLICANT', 'PARTICIPANT', 'MRS', 'MR', 'MS'):
                if re.match(r'^[A-ZÀ-Ỹa-zà-ỹ ]{3,35}$', stripped) and stripped.upper() not in SKIP_HEADINGS:
                    names.add(stripped.upper())
                    continue

    guest_names = sorted(set(n.strip() for n in names if len(n.strip()) > 2))

    return {
        "guest_names": guest_names,
        "travel_start_date": travel_start,
        "travel_end_date": travel_end,
        "travel_purpose": "Tourism",
    }
