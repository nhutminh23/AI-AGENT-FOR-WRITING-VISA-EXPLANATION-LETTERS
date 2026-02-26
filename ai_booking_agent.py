"""
AI Booking Agent Module
Uses AI to extract trip information from input files and intelligently select
hotels + flights for any country in the world.
"""

import json
import os
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage

from file_utils import read_docx, read_pdf, read_text_file


# ==================== PROMPTS ====================

TRIP_EXTRACTOR_PROMPT = """Bạn là chuyên viên xử lý hồ sơ visa. Nhiệm vụ: đọc file THÔNG TIN CHUYẾN ĐI và trích xuất CHÍNH XÁC thông tin chuyến đi.

Quy tắc BẮT BUỘC:
- Chỉ dùng thông tin CÓ trong tài liệu, KHÔNG suy đoán
- Tên người phải viết HOA theo hộ chiếu  
- Ngày tháng format: YYYY-MM-DD
- Nếu không có thông tin thì để chuỗi rỗng

Trích xuất các trường sau:

1. guest_names: Danh sách TẤT CẢ người đi (người nộp hồ sơ + người đi cùng)
   - Ưu tiên tên TIẾNG ANH / viết HOA theo hộ chiếu
   - Người nộp hồ sơ chính đặt đầu tiên

2. destination_country: Nước đến (tiếng Anh, VD: "Australia")

3. cities_to_visit: Danh sách thành phố sẽ đến
   - Nếu không ghi rõ, để mảng rỗng (AI booking sẽ tự chọn)

4. city_stays: Danh sách số đêm theo từng thành phố (nếu có)
   - Ví dụ từ "Toronto (4), Niagara (2), Vancouver (4)" thì trả về:
     [
       {{"city":"Toronto","nights":4}},
       {{"city":"Niagara","nights":2}},
       {{"city":"Vancouver","nights":4}}
     ]
   - Nếu không có số đêm theo từng thành phố thì để mảng rỗng

5. travel_start_date: Ngày bắt đầu chuyến đi (YYYY-MM-DD)

6. travel_end_date: Ngày kết thúc chuyến đi (YYYY-MM-DD)

7. num_nights: Tổng số đêm ở (tính từ ngày đến - ngày về, trừ đêm bay)

8. origin_city: Điểm xuất phát (có thể là thành phố hoặc quốc gia)

9. origin_airport: Mã sân bay xuất phát
   - Chọn mã IATA phù hợp với điểm xuất phát đã nêu
   - Nếu điểm xuất phát là quốc gia, chọn sân bay quốc tế lớn hợp lý nhất

10. return_point: Điểm về (có thể là thành phố hoặc quốc gia), nếu có

11. destination_airport_hint: Mã sân bay gợi ý tại điểm đến đầu tiên (nếu suy luận được)

12. return_airport_hint: Mã sân bay gợi ý cho điểm về (nếu suy luận được)

13. travel_purpose: Mục đích (Tourism / Business / Visit Family / Study...)

14. traveler_profile: Mô tả ngắn profile người đi (nghề nghiệp, tình trạng tài chính)
    để hỗ trợ AI chọn khách sạn phù hợp

Trả về JSON hợp lệ, KHÔNG thêm chữ ngoài JSON:
{{
  "guest_names": [],
  "destination_country": "",
  "cities_to_visit": [],
  "city_stays": [],
  "travel_start_date": "",
  "travel_end_date": "",
  "num_nights": 0,
  "origin_city": "",
  "origin_airport": "",
  "return_point": "",
  "destination_airport_hint": "",
  "return_airport_hint": "",
  "travel_purpose": "",
  "traveler_profile": ""
}}

DỮ LIỆU:
{text}
"""


BOOKING_EXPERT_PROMPT = """Bạn là CHUYÊN GIA BOOKING cao cấp với kiến thức sâu rộng về khách sạn và hàng không quốc tế.

NHIỆM VỤ: Dựa trên thông tin chuyến đi, hãy chọn khách sạn và chuyến bay THẬT, TỒN TẠI THỰC TẾ.

THÔNG TIN CHUYẾN ĐI:
{trip_info}

QUY TẮC BẮT BUỘC CHO KHÁCH SẠN:
1. Chọn khách sạn THẬT, CÓ TỒN TẠI trên thế giới (có thể verify trên Google)
2. Địa chỉ PHẢI CHÍNH XÁC theo thực tế. ⚠️ QUAN TRỌNG: NẾU THĂM >1 THÀNH PHỐ, CÁC KHÁCH SẠN PHẢI KHÁC NHAU VÀ CÓ ĐỊA CHỈ HOÀN TOÀN KHÁC NHAU (KHÔNG DÙNG CHUNG 1 ĐỊA CHỈ CHO 2 THÀNH PHỐ).
3. Số điện thoại PHẢI ĐÚNG format quốc tế của nước đó
4. Phân chia đêm HỢP LÝ giữa các thành phố:
   - Nếu chỉ 1 thành phố: 1 khách sạn
   - Nếu 2+ thành phố: chia đều, thành phố chính nhiều đêm hơn
5. Chọn hạng 4-5 sao, phù hợp profile khách
6. Giá PHẢI HỢP LÝ theo thị trường thực tế (USD/đêm hoặc local currency)
7. Loại phòng phải có thật tại khách sạn đó. ⚠️ Tên loại phòng phải NGẮN GỌN (tối đa 2-3 từ, ví dụ: "Superior King", "Deluxe Twin", "Premier Suite"). KHÔNG dùng tên dài quá 20 ký tự.
8. Ngày check-in khách sạn đầu tiên = ngày đến nước sở tại (sau khi bay)
9. Ngày check-out khách sạn cuối = ngày về

QUY TẮC BẮT BUỘC CHO CHUYẾN BAY:

⚠️ TUYỆT ĐỐI KHÔNG ĐƯỢC BỊA SỐ HIỆU BAY. Chỉ dùng số hiệu THẬT.

BẢNG THAM KHẢO SỐ HIỆU VIETNAM AIRLINES THẬT:
  - HAN → SYD: VN 787 (bay qua SGN, nhưng ghi 1 số hiệu duy nhất VN 787)
  - SYD → HAN: VN 788
  - SGN → SYD: VN 773
  - SYD → SGN: VN 774
  - SGN → MEL: VN 781
  - MEL → SGN: VN 782  
  - SGN → MEL → HAN: VN 782 (ghi 1 số hiệu)
  - MEL → HAN: VN 778 (bay qua SGN, ghi 1 số hiệu VN 778)
  - HAN → NRT: VN 311
  - NRT → HAN: VN 312
  - HAN → ICN: VN 416
  - ICN → HAN: VN 417
  Nếu không tìm thấy số hiệu chính xác cho tuyến bay, hãy dùng số hiệu gần nhất từ bảng trên.

QUY TẮC TUYẾN BAY:
1. Chiều đi (outbound): từ origin_airport → sân bay THÀNH PHỐ ĐẦU TIÊN trong cities_to_visit
2. Chiều về (return): từ sân bay THÀNH PHỐ CUỐI CÙNG trong cities_to_visit → origin_airport
   ✅ VD: cities_to_visit = ["Sydney", "Melbourne"] → đi HAN→SYD, về MEL→HAN
   ❌ SAI: về từ SYD khi thành phố cuối là Melbourne
2b. Nếu có return_point, coi đó là điểm quay về cuối cùng của hành trình.
    Route 2 phải là: điểm đến du lịch cuối cùng → return_point
3. Phải là chuyến bay TRỰC TIẾP (hoặc transit qua 1 điểm nhưng chỉ ghi 1 số hiệu bay)
4. KHÔNG ghi 2 số hiệu bay kiểu "VN280 / VN780"

BẢNG SÂN BAY - THÀNH PHỐ:
  - Sydney → SYD
  - Melbourne → MEL
  - Tokyo → NRT hoặc HND
  - Seoul → ICN
  - Singapore → SIN
  - Bangkok → BKK
  - Hanoi → HAN
  - Ho Chi Minh City → SGN

QUY TẮC FORMAT:
1. departure_airport, arrival_airport: CHỈ mã IATA 3 chữ cái
   ✅ "HAN", "SYD", "MEL"
   ❌ "Noi Bai International Airport (HAN)"
2. flight_number: CHỈ 1 số hiệu
   ✅ "VN 787"
   ❌ "VN280 / VN780"
3. duration: format "Xh YYm"
   ✅ "9h 45m"
4. departure_time, arrival_time: format "HH:MM"
   ✅ "23:30"
4b. departure_date, arrival_date: format "DD/MM/YYYY"
4c. THỜI GIAN PHẢI NHẤT QUÁN:
   - arrival_datetime = departure_datetime + duration (không trừ múi giờ)
   - Ví dụ: duration=16h15, departure=10:00 07/07/2026 → arrival=02:15 08/07/2026
   - Không được để thời gian đến mâu thuẫn với duration
5. departure_terminal, arrival_terminal: Tự động chọn cho phù hợp giống vé máy bay Vietnam Airlines
6. baggage: Tự động chọn cho phù hợp giống vé máy bay Vietnam Airlines. Ví dụ: "Free baggage: 1 piece 23KG"
7. Thêm 2 field mới trong outbound và return:
   - departure_city: tên thành phố xuất phát (VD: "Hanoi", "Melbourne")
   - arrival_city: tên thành phố đến (VD: "Sydney", "Hanoi")

QUY TẮC VỀ TÊN HÀNH KHÁCH:
- passengers.name phải viết HOA, KHÔNG dấu tiếng Việt
- Format: TÊN ĐỆM HỌ (VD: "THI THANH HIEN DO", "NGOC KHUE VU")

QUY TẮC VỀ NGÀY THÁNG:
- check_in_date format: "Month DD, YYYY" (VD: "March 11, 2026")
- check_in_date_short format: "DD/MM/YYYY" (VD: "11/03/2026")
- departure_date format: "DD/MM/YYYY"
- Nếu bay đêm (departure sau 22:00), arrival_date = departure_date + 1

⚠️ QUAN TRỌNG: Mọi giá trị PHẢI NGẮN GỌN. KHÔNG giải thích, bổ sung, thêm text thừa. KHÔNG bịa số hiệu bay.
⚠️ Nếu không chắc chắn duration chính xác tuyệt đối, hãy chọn duration gần thực tế theo tuyến bay và vẫn đảm bảo logic thời gian đến/đi khớp.

Trả về JSON hợp lệ, KHÔNG thêm chữ ngoài JSON:
{{
  "hotels": [
    {{
      "hotel_name": "",
      "hotel_address": "",
      "hotel_phone": "",
      "star_rating": 5,
      "city": "",
      "country": "",
      "check_in_date": "",
      "check_out_date": "",
      "check_in_date_short": "",
      "check_out_date_short": "",
      "num_nights": 0,
      "room_type": "",
      "num_rooms": 1,
      "num_adults": 1,
      "num_children": 0,
      "price_per_night": "",
      "total_price": "",
      "currency": "",
      "guest_name": "",
      "benefits": "Breakfast included, Free WiFi, Non-smoking room",
      "cancellation_policy": ""
    }}
  ],
  "flight": {{
    "airline": "",
    "booking_reference": "",
    "passengers": [
      {{"name": "", "type": "Adult"}}
    ],
    "outbound": {{
      "flight_number": "",
      "departure_date": "",
      "departure_time": "",
      "departure_airport": "",
      "departure_city": "",
      "departure_terminal": "",
      "arrival_date": "",
      "arrival_time": "",
      "arrival_airport": "",
      "arrival_city": "",
      "arrival_terminal": "",
      "duration": ""
    }},
    "return": {{
      "flight_number": "",
      "departure_date": "",
      "departure_time": "",
      "departure_airport": "",
      "departure_city": "",
      "departure_terminal": "",
      "arrival_date": "",
      "arrival_time": "",
      "arrival_airport": "",
      "arrival_city": "",
      "arrival_terminal": "",
      "duration": ""
    }},
    "baggage": ""
  }},
  "reasoning": "Giải thích ngắn gọn lý do chọn khách sạn và chuyến bay"
}}
"""


# ==================== HELPER FUNCTIONS ====================

AIRPORT_BY_CITY = {
    "hanoi": "HAN",
    "ho chi minh": "SGN",
    "da nang": "DAD",
    "sydney": "SYD",
    "melbourne": "MEL",
    "brisbane": "BNE",
    "perth": "PER",
    "toronto": "YYZ",
    "niagara": "YYZ",
    "vancouver": "YVR",
    "montreal": "YUL",
    "calgary": "YYC",
    "new york": "JFK",
    "los angeles": "LAX",
    "san francisco": "SFO",
    "london": "LHR",
    "paris": "CDG",
    "singapore": "SIN",
    "bangkok": "BKK",
    "tokyo": "NRT",
    "osaka": "KIX",
    "seoul": "ICN",
    "auckland": "AKL",
}

AIRPORT_BY_COUNTRY = {
    "vietnam": "HAN",
    "australia": "SYD",
    "canada": "YYZ",
    "united states": "JFK",
    "usa": "JFK",
    "united kingdom": "LHR",
    "uk": "LHR",
    "france": "CDG",
    "singapore": "SIN",
    "thailand": "BKK",
    "japan": "NRT",
    "south korea": "ICN",
    "new zealand": "AKL",
}

TRIP_FILE_PREFIXES = [
    "THONG TIN CHUYEN DI",
    "HO SO CA NHAN",
    "MUC DICH CHUYEN DI",
]

DEFAULT_TRIP_INFO: Dict[str, Any] = {
    "guest_names": [],
    "destination_country": "",
    "cities_to_visit": [],
    "city_stays": [],
    "travel_start_date": "",
    "travel_end_date": "",
    "num_nights": 0,
    "origin_city": "",
    "origin_airport": "",
    "return_point": "",
    "destination_airport_hint": "",
    "return_airport_hint": "",
    "travel_purpose": "",
    "traveler_profile": "",
}


def _normalize_key(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return text


def _is_trip_info_filename(filename: str) -> bool:
    stem = os.path.splitext(filename)[0]
    normalized = re.sub(r"[\s\-_]+", " ", stem.upper()).strip()
    return any(normalized.startswith(prefix) for prefix in TRIP_FILE_PREFIXES)


def _clean_city_name(city: str) -> str:
    if not city:
        return ""
    city = re.sub(r"\s*\([^)]*\)\s*$", "", city).strip()
    return city


def _parse_city_stays(values: List[str]) -> List[Dict[str, Any]]:
    city_stays: List[Dict[str, Any]] = []
    for raw in values:
        part = (raw or "").strip()
        if not part:
            continue
        match = re.match(r"^(.*?)\s*\((\d+)\)\s*$", part)
        if match:
            city = _clean_city_name(match.group(1))
            nights = int(match.group(2))
            if city and nights > 0:
                city_stays.append({"city": city, "nights": nights})
        else:
            city = _clean_city_name(part)
            if city:
                city_stays.append({"city": city, "nights": 0})
    return city_stays


def _infer_airport_from_location(location: str, fallback: str = "") -> str:
    key = _normalize_key(location)
    if not key:
        return fallback

    for city, code in AIRPORT_BY_CITY.items():
        if city in key or key in city:
            return code
    for country, code in AIRPORT_BY_COUNTRY.items():
        if country in key or key in country:
            return code
    return fallback


def _airport_to_city_name(code: str) -> str:
    by_airport = {
        "HAN": "Hanoi",
        "SGN": "Ho Chi Minh City",
        "DAD": "Da Nang",
        "SYD": "Sydney",
        "MEL": "Melbourne",
        "BNE": "Brisbane",
        "PER": "Perth",
        "YYZ": "Toronto",
        "YVR": "Vancouver",
        "YUL": "Montreal",
        "JFK": "New York",
        "LAX": "Los Angeles",
        "LHR": "London",
        "CDG": "Paris",
        "SIN": "Singapore",
        "BKK": "Bangkok",
        "NRT": "Tokyo",
        "KIX": "Osaka",
        "ICN": "Seoul",
        "AKL": "Auckland",
    }
    return by_airport.get((code or "").strip().upper(), "")


def _to_passport_name(name: str) -> str:
    n = _normalize_key(name).upper()
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _format_dmy(date_ymd: str) -> str:
    try:
        dt = datetime.strptime(date_ymd, "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return ""


def _parse_duration_minutes(duration_text: str) -> Optional[int]:
    if not duration_text:
        return None
    m = re.search(r"(\d+)\s*h\s*(\d+)", duration_text.lower())
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m = re.search(r"(\d+)\s*h", duration_text.lower())
    if m:
        return int(m.group(1)) * 60
    return None


def _enforce_leg_time_consistency(leg: Dict[str, Any]) -> None:
    dep_date = (leg.get("departure_date") or "").strip()
    dep_time = (leg.get("departure_time") or "").strip()
    duration = (leg.get("duration") or "").strip()
    if not dep_date or not dep_time or not duration:
        return

    duration_min = _parse_duration_minutes(duration)
    if duration_min is None:
        return

    try:
        dep_dt = datetime.strptime(f"{dep_date} {dep_time}", "%d/%m/%Y %H:%M")
    except ValueError:
        return

    arr_dt = dep_dt + timedelta(minutes=duration_min)
    leg["arrival_date"] = arr_dt.strftime("%d/%m/%Y")
    leg["arrival_time"] = arr_dt.strftime("%H:%M")

def _extract_text_from_file(llm: Any, path: str) -> str:
    """Extract text from a file (PDF, DOCX, image, or text)."""
    ext = os.path.splitext(path)[1].lower()

    if ext == ".docx":
        return read_docx(path)
    elif ext == ".txt":
        return read_text_file(path)
    elif ext == ".pdf":
        return _extract_pdf_with_openai(llm, path)
    elif ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"):
        return _extract_image_with_openai(llm, path)
    else:
        return ""


def _extract_pdf_with_openai(llm: Any, path: str) -> str:
    """Extract text from PDF using OpenAI vision."""
    try:
        text = read_pdf(path)
        if text and len(text.strip()) > 50:
            return text
    except Exception:
        pass

    # Fallback: render pages as images
    try:
        import fitz  # PyMuPDF
        import base64
        doc = fitz.open(path)
        all_text = []
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            b64 = base64.b64encode(img_bytes).decode()
            msg = HumanMessage(content=[
                {"type": "text", "text": "Trích xuất toàn bộ văn bản từ hình ảnh này. Giữ nguyên format, số, ngày tháng."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ])
            resp = llm.invoke([msg])
            all_text.append(resp.content)
        doc.close()
        return "\n\n".join(all_text)
    except ImportError:
        return ""


def _extract_image_with_openai(llm: Any, path: str) -> str:
    """Extract text from image using OpenAI vision."""
    import base64
    with open(path, "rb") as f:
        img_bytes = f.read()
    b64 = base64.b64encode(img_bytes).decode()

    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime = f"image/{ext}" if ext != "jpg" else "image/jpeg"

    msg = HumanMessage(content=[
        {"type": "text", "text": "Trích xuất toàn bộ văn bản từ hình ảnh này. Giữ nguyên format, số, ngày tháng."},
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
    ])
    resp = llm.invoke([msg])
    return resp.content


def _safe_json_loads(text: str) -> dict:
    """Safely parse JSON from LLM response, handling markdown code blocks."""
    text = text.strip()
    # Remove markdown code blocks
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {}


# ==================== AGENT 1: TRIP INFO EXTRACTOR ====================

def extract_trip_info(llm: Any, input_dir: str) -> Dict[str, Any]:
    """
    Read only files prefixed with "THONG TIN CHUYEN DI" and extract trip information.
    This is the Booking tab's own extraction - independent from the Letter tab.

    Args:
        llm: Language model instance
        input_dir: Path to input directory containing documents

    Returns:
        Dictionary with trip information
    """
    # Collect text from files prefixed with "THONG TIN CHUYEN DI"
    all_texts = []
    for root, _, filenames in os.walk(input_dir):
        for fname in sorted(filenames):
            if not _is_trip_info_filename(fname):
                continue
            path = os.path.join(root, fname)
            text = _extract_text_from_file(llm, path)
            if text:
                all_texts.append(f"--- FILE: {fname} ---\n{text}")

    if not all_texts:
        return dict(DEFAULT_TRIP_INFO)

    combined_text = "\n\n".join(all_texts)

    # Call AI to extract trip info
    prompt = TRIP_EXTRACTOR_PROMPT.format(text=combined_text)
    response = llm.invoke([
        SystemMessage(content="Bạn là chuyên viên xử lý hồ sơ visa. Trả về JSON hợp lệ."),
        HumanMessage(content=prompt),
    ])

    trip_info = _safe_json_loads(response.content)
    if not isinstance(trip_info, dict):
        trip_info = {}
    # Always keep full schema so frontend can render all fields.
    merged = dict(DEFAULT_TRIP_INFO)
    merged.update(trip_info)
    trip_info = merged

    # Post-process: normalize required fields
    if not trip_info.get("guest_names"):
        trip_info["guest_names"] = []
    if isinstance(trip_info.get("guest_names"), str):
        trip_info["guest_names"] = [
            n.strip()
            for n in re.split(r"[,\n;]+", trip_info.get("guest_names", ""))
            if n.strip()
        ]

    raw_city_values: List[str] = []
    if not isinstance(trip_info.get("cities_to_visit"), list):
        raw_cities = trip_info.get("cities_to_visit", "")
        if isinstance(raw_cities, str):
            raw_city_values = [c.strip() for c in re.split(r"[,\n;]+", raw_cities) if c.strip()]
        else:
            raw_city_values = []
    else:
        raw_city_values = [str(c).strip() for c in trip_info.get("cities_to_visit", []) if str(c).strip()]

    city_stays = trip_info.get("city_stays", [])
    normalized_city_stays: List[Dict[str, Any]] = []
    if isinstance(city_stays, list):
        for item in city_stays:
            if not isinstance(item, dict):
                continue
            city = _clean_city_name(str(item.get("city", "")))
            nights_raw = item.get("nights", 0)
            try:
                nights = int(nights_raw)
            except (TypeError, ValueError):
                nights = 0
            if city:
                normalized_city_stays.append({"city": city, "nights": max(0, nights)})

    if not normalized_city_stays:
        normalized_city_stays = _parse_city_stays(raw_city_values)

    cleaned_cities = [s["city"] for s in normalized_city_stays if s.get("city")]
    if not cleaned_cities:
        cleaned_cities = [_clean_city_name(c) for c in raw_city_values if _clean_city_name(c)]
    trip_info["cities_to_visit"] = cleaned_cities
    trip_info["city_stays"] = normalized_city_stays

    # Infer airports based on origin/destination/return points when missing
    origin_point = trip_info.get("origin_city") or ""
    return_point = trip_info.get("return_point") or ""
    first_city = trip_info["cities_to_visit"][0] if trip_info.get("cities_to_visit") else ""
    last_city = trip_info["cities_to_visit"][-1] if trip_info.get("cities_to_visit") else ""
    destination_country = trip_info.get("destination_country") or ""

    trip_info["origin_airport"] = (
        (trip_info.get("origin_airport") or "").strip().upper()
        or _infer_airport_from_location(origin_point)
        or _infer_airport_from_location(return_point)
    )
    trip_info["destination_airport_hint"] = (
        (trip_info.get("destination_airport_hint") or "").strip().upper()
        or _infer_airport_from_location(first_city)
        or _infer_airport_from_location(destination_country)
    )
    trip_info["return_airport_hint"] = (
        (trip_info.get("return_airport_hint") or "").strip().upper()
        or _infer_airport_from_location(last_city)
        or _infer_airport_from_location(return_point)
        or trip_info.get("origin_airport", "")
    )

    if not trip_info.get("num_nights") and trip_info.get("travel_start_date") and trip_info.get("travel_end_date"):
        try:
            start = datetime.strptime(trip_info["travel_start_date"], "%Y-%m-%d")
            end = datetime.strptime(trip_info["travel_end_date"], "%Y-%m-%d")
            trip_info["num_nights"] = (end - start).days
        except (ValueError, TypeError):
            pass

    # If city_stays exists but nights are missing, distribute from total nights.
    total_nights = int(trip_info.get("num_nights") or 0)
    if trip_info["city_stays"]:
        known = sum(int(s.get("nights") or 0) for s in trip_info["city_stays"])
        if known == 0 and total_nights > 0:
            n = len(trip_info["city_stays"])
            base = total_nights // n
            rem = total_nights % n
            for i, stay in enumerate(trip_info["city_stays"]):
                stay["nights"] = base + (1 if i < rem else 0)

    return trip_info


# ==================== AGENT 2: BOOKING EXPERT ====================

def ai_select_bookings(llm: Any, trip_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Use AI to intelligently select real hotels and flights for the trip.
    Works for ANY country in the world - no database dependency.

    Args:
        llm: Language model instance
        trip_info: Trip information from extract_trip_info()

    Returns:
        Dictionary with hotel bookings and flight booking data
    """
    if not trip_info:
        return {}

    # Format trip info for the prompt
    trip_info_str = json.dumps(trip_info, ensure_ascii=False, indent=2)
    prompt = BOOKING_EXPERT_PROMPT.format(trip_info=trip_info_str)

    response = llm.invoke([
        SystemMessage(content="Bạn là chuyên gia booking quốc tế. Trả về JSON hợp lệ với thông tin khách sạn và chuyến bay THẬT."),
        HumanMessage(content=prompt),
    ])

    booking_data = _safe_json_loads(response.content)

    # Post-process hotels
    for hotel in booking_data.get("hotels", []):
        # Generate booking IDs
        import random
        if "booking_id" not in hotel:
            hotel["booking_id"] = str(random.randint(1000000000, 9999999999))
        if "booking_reference" not in hotel:
            hotel["booking_reference"] = str(random.randint(1000000000, 9999999999))
        # Ensure cancellation policy
        if not hotel.get("cancellation_policy"):
            try:
                check_in = datetime.strptime(hotel.get("check_in_date_short", ""), "%d/%m/%Y")
                free_cancel = (check_in - timedelta(days=3)).strftime("%B %d, %Y")
                hotel["cancellation_policy"] = f"Free cancellation before {free_cancel}"
            except (ValueError, TypeError):
                hotel["cancellation_policy"] = "Free cancellation up to 3 days before check-in"

    # Enforce hotel count/nights by city_stays if available.
    city_stays = trip_info.get("city_stays", [])
    hotels = booking_data.get("hotels", [])
    if isinstance(city_stays, list) and city_stays and hotels:
        start_date_raw = trip_info.get("travel_start_date", "")
        start_dt = None
        try:
            start_dt = datetime.strptime(start_date_raw, "%Y-%m-%d")
        except (TypeError, ValueError):
            start_dt = None

        adjusted_hotels: List[Dict[str, Any]] = []
        cursor = start_dt
        for i, stay in enumerate(city_stays):
            if not isinstance(stay, dict):
                continue
            city = _clean_city_name(str(stay.get("city", "")))
            nights = int(stay.get("nights") or 0)
            base_hotel = dict(hotels[i % len(hotels)])
            if city:
                base_hotel["city"] = city
            if trip_info.get("destination_country"):
                base_hotel["country"] = trip_info.get("destination_country")
            if nights > 0:
                base_hotel["num_nights"] = nights
                if cursor:
                    checkout = cursor + timedelta(days=nights)
                    base_hotel["check_in_date"] = cursor.strftime("%B %d, %Y")
                    base_hotel["check_in_date_short"] = cursor.strftime("%d/%m/%Y")
                    base_hotel["check_out_date"] = checkout.strftime("%B %d, %Y")
                    base_hotel["check_out_date_short"] = checkout.strftime("%d/%m/%Y")
                    cursor = checkout
            adjusted_hotels.append(base_hotel)

        if adjusted_hotels:
            booking_data["hotels"] = adjusted_hotels

    # Post-process flight - sanitize all fields
    flight = booking_data.get("flight", {})
    if flight:
        if not flight.get("booking_reference"):
            import random
            chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            flight["booking_reference"] = "".join(random.choice(chars) for _ in range(6))

        # Clean airline name (remove parenthetical notes)
        airline = flight.get("airline", "")
        if "(" in airline:
            flight["airline"] = airline.split("(")[0].strip()

        # Enforce passenger list from extracted trip info.
        guest_names = trip_info.get("guest_names", [])
        if isinstance(guest_names, list) and guest_names:
            flight["passengers"] = [
                {"name": _to_passport_name(str(name)), "type": "Adult"}
                for name in guest_names
                if str(name).strip()
            ]

        # Enforce route based on origin -> destination -> return_point.
        origin_airport = (trip_info.get("origin_airport") or "").strip().upper()
        first_city = (trip_info.get("cities_to_visit") or [""])[0] if trip_info.get("cities_to_visit") else ""
        last_city = (trip_info.get("cities_to_visit") or [""])[-1] if trip_info.get("cities_to_visit") else ""
        destination_country = (trip_info.get("destination_country") or "").strip()
        return_point = (trip_info.get("return_point") or "").strip()

        destination_airport = (
            (trip_info.get("destination_airport_hint") or "").strip().upper()
            or _infer_airport_from_location(first_city)
            or _infer_airport_from_location(destination_country)
        )
        return_departure_airport = (
            _infer_airport_from_location(last_city)
            or destination_airport
        )
        return_arrival_airport = (
            (trip_info.get("return_airport_hint") or "").strip().upper()
            or _infer_airport_from_location(return_point)
            or origin_airport
        )

        outbound = flight.setdefault("outbound", {})
        inbound = flight.setdefault("return", {})
        if origin_airport:
            outbound["departure_airport"] = origin_airport
        if destination_airport:
            outbound["arrival_airport"] = destination_airport
        if return_departure_airport:
            inbound["departure_airport"] = return_departure_airport
        if return_arrival_airport:
            inbound["arrival_airport"] = return_arrival_airport

        origin_city_label = (trip_info.get("origin_city") or "").strip() or _airport_to_city_name(outbound.get("departure_airport", ""))
        dest_city_label = _clean_city_name(first_city) or destination_country or _airport_to_city_name(outbound.get("arrival_airport", ""))
        return_dep_city_label = _clean_city_name(last_city) or destination_country or _airport_to_city_name(inbound.get("departure_airport", ""))
        return_arr_city_label = return_point or (trip_info.get("origin_city") or "").strip() or _airport_to_city_name(inbound.get("arrival_airport", ""))

        outbound["departure_city"] = origin_city_label
        outbound["arrival_city"] = dest_city_label
        inbound["departure_city"] = return_dep_city_label
        inbound["arrival_city"] = return_arr_city_label

        dep_dmy = _format_dmy(trip_info.get("travel_start_date", ""))
        ret_dmy = _format_dmy(trip_info.get("travel_end_date", ""))
        if dep_dmy:
            outbound["departure_date"] = dep_dmy
        if ret_dmy:
            inbound["departure_date"] = ret_dmy

        # Sanitize flight sub-objects
        for leg_key in ("outbound", "return"):
            leg = flight.get(leg_key, {})
            if not leg:
                continue

            # Clean airport codes → 3-letter IATA only
            # Handles: "HAN (Noi Bai...)", "Noi Bai (HAN)", "HAN", etc.
            for ap_key in ("departure_airport", "arrival_airport"):
                val = leg.get(ap_key, "")
                if val and len(val) > 3:
                    # Pattern 1: "HAN (full name)" - code at start
                    match = re.match(r'^([A-Z]{3})\s', val)
                    if match:
                        leg[ap_key] = match.group(1)
                        continue
                    # Pattern 2: "full name (HAN)" - code in parentheses  
                    match = re.search(r'\(([A-Z]{3})\)', val)
                    if match:
                        leg[ap_key] = match.group(1)
                        continue
                    # Pattern 3: any 3 uppercase letters
                    match = re.search(r'\b([A-Z]{3})\b', val)
                    if match:
                        leg[ap_key] = match.group(1)
                elif val:
                    leg[ap_key] = val.strip().upper()[:3]

            # Clean duration → "Xh YYm" only
            dur = leg.get("duration", "")
            if dur and (len(dur) > 10 or "(" in dur):
                match = re.search(r'(\d+)h\s*(\d+)', dur)
                if match:
                    leg["duration"] = f"{match.group(1)}h {match.group(2)}m"
                else:
                    # Try "XhYY" without space
                    match = re.search(r'(\d+)h(\d+)', dur)
                    if match:
                        leg["duration"] = f"{match.group(1)}h {match.group(2)}m"

            # Clean flight number → single number only (no compound "SQ179 / SQ221")
            fn = leg.get("flight_number", "")
            if "/" in fn:
                leg["flight_number"] = fn.split("/")[0].strip()
            if "connecting" in fn.lower():
                leg["flight_number"] = fn.split("connecting")[0].strip()

            # Clean terminal → remove parenthetical notes
            for t_key in ("departure_terminal", "arrival_terminal"):
                t_val = leg.get(t_key, "")
                if "(" in t_val:
                    leg[t_key] = t_val.split("(")[0].strip()

            # Clean time → HH:MM only
            for t_key in ("departure_time", "arrival_time"):
                t_val = leg.get(t_key, "")
                if t_val:
                    match = re.search(r'(\d{2}:\d{2})', t_val)
                    if match:
                        leg[t_key] = match.group(1)

            # Enforce arrival datetime consistency with duration.
            _enforce_leg_time_consistency(leg)

        # Clean baggage → short format
        bag = flight.get("baggage", "")
        if bag and len(bag) > 60:
            flight["baggage"] = "Free baggage: 1 piece 23KG , 1 piece 23KG"

    return booking_data


# ==================== MAIN ORCHESTRATOR ====================

def generate_ai_booking(
    llm: Any,
    input_dir: str,
    trip_info: Optional[Dict] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Full AI booking generation pipeline:
    1. Extract trip info from input files (or use provided trip_info)
    2. AI selects hotels + flights
    3. Return structured data ready for template filling

    Args:
        llm: Language model instance
        input_dir: Path to input directory
        trip_info: Optional pre-extracted trip info (skip extraction if provided)

    Returns:
        Tuple of (trip_info, booking_data)
    """
    # Step 1: Extract trip info if not provided
    if not trip_info:
        trip_info = extract_trip_info(llm, input_dir)

    if not trip_info or not trip_info.get("destination_country"):
        raise ValueError("Không thể trích xuất thông tin chuyến đi từ các file input.")

    # Step 2: AI select bookings
    booking_data = ai_select_bookings(llm, trip_info)

    if not booking_data or not booking_data.get("hotels"):
        raise ValueError("AI không thể tạo booking. Vui lòng thử lại.")

    return trip_info, booking_data
