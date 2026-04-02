# Grok Prompt — Trích xuất dữ liệu hồ sơ visa Úc (IMMI Visitor 600)

## Hướng dẫn sử dụng
1. Mở grok.com hoặc Web Grok
2. Upload toàn bộ file hồ sơ (passport, giấy tờ cá nhân, thư mời, booking...)
3. Copy phần PROMPT bên dưới và gửi cho Grok
4. Grok sẽ trả về JSON chuẩn cho từng người
5. Copy JSON → Dán vào Tab Australia trên web app

---

## PROMPT (Copy từ đây)

Bạn là chuyên gia trích xuất dữ liệu visa Úc. Hãy đọc TẤT CẢ file tôi gửi và trích xuất thông tin cho TỪNG NGƯỜI NỘP ĐƠN riêng biệt.

**Trả về JSON theo đúng format dưới đây cho MỖI người.** Nếu có nhiều người (gia đình), trả về một mảng JSON `[{...person1}, {...person2}]`.

Nếu không tìm thấy thông tin cho trường nào, để giá trị là `""` (chuỗi rỗng).

**LƯU Ý QUAN TRỌNG:** Số `page_X` trong JSON phải ĐÚNG theo số trang thật trên form IMMI (2/20, 3/20, 5/20, 6/20, 8/20, 9/20, 11/20).

**FORMAT JSON CHO MỖI NGƯỜI:**

```json
{
  "applicant_name": "NGUYEN VAN A",
  "page_2": {
    "_title": "Application context (Trang 2/20)",
    "outside_australia": "Yes",
    "current_location": "VIET",
    "legal_status": "1",
    "purpose_stream": "29",
    "initial_purpose": "2",
    "visit_reason": "1",
    "significant_dates": "THE APPLICANT INTENDS TO VISIT AUSTRALIA FROM 15 MARCH 2026 TO 25 MARCH 2026. HOWEVER, THIS SCHEDULE IS SUBJECT TO CHANGE BASED ON THE DATE OF VISA GRANT.",
    "group_processing": "2",
    "special_category": "2"
  },
  "page_3": {
    "_title": "Passport and identity details (Trang 3/20)",
    "family_name": "NGUYEN",
    "given_names": "VAN A",
    "sex": "F",
    "date_of_birth": "01 Jan 1990",
    "passport_number": "C1234567",
    "passport_country": "VNM",
    "passport_nationality": "VNM",
    "passport_issue_date": "01 Jan 2020",
    "passport_expiry_date": "01 Jan 2030",
    "passport_issuing_authority": "IMMIGRATION DEPARTMENT",
    "has_national_id": "Yes",
    "national_id_family_name": "NGUYEN",
    "national_id_given_names": "VAN A",
    "national_id_number": "012345678901",
    "national_id_country": "VIET",
    "national_id_issue_date": "29 Jul 2022",
    "national_id_expiry_date": "01 Jan 2028",
    "pacific_australia_card": "No",
    "place_of_birth_city": "HO CHI MINH CITY",
    "place_of_birth_state": "HO CHI MINH",
    "place_of_birth_country": "VIET",
    "relationship_status": "M",
    "other_names_used": "No",
    "citizen_of_passport_country": "Yes",
    "citizen_of_other_country": "No",
    "previously_travelled_to_australia": "No",
    "previously_applied_visa": "No",
    "has_grant_number": "No",
    "other_passports": "No",
    "other_identity_docs": "No",
    "health_examination": "No"
  },
  "page_5": {
    "_title": "Travelling companions (Trang 5/20)",
    "companions": [
      {
        "relationship": "1",
        "family_name": "NGUYEN",
        "given_names": "VAN B",
        "sex": "M",
        "date_of_birth": "16 Oct 2017"
      }
    ]
  },
  "page_6": {
    "_title": "Contact details (Trang 6/20)",
    "usual_country": "VIET",
    "closest_office": "Vietnam, Ho Chi Minh City",
    "residential_country": "VIET",
    "residential_address1": "123 NGUYEN HUE STREET",
    "residential_address2": "",
    "residential_suburb": "DISTRICT 1",
    "residential_state": "VNSG",
    "residential_postcode": "700000",
    "phone_home": "",
    "phone_business": "",
    "phone_mobile": "0901234567",
    "postal_same_as_residential": "Yes",
    "email": "example@gmail.com"
  },
  "page_9": {
    "_title": "Planned travel (Trang 9/20)",
    "multiple_entry": "No",
    "length_of_stay": "12",
    "planned_arrival": "01 May 2026",
    "planned_departure": "30 May 2026",
    "is_parent_of_australian": "No",
    "undertake_study": "No",
    "visit_relatives": "No"
  },
  "page_11": {
    "_title": "Current overseas employment (Trang 11/20)",
    "employment_status": "1",
    "occupation_grouping": "2",
    "organisation": "ABC COMPANY LTD",
    "start_date": "15 Mar 2022",
    "org_country": "VIET",
    "org_address1": "789 LE LOI STREET",
    "org_address2": "DISTRICT 1",
    "org_suburb": "PHUONG BEN NGHE",
    "org_state": "HO CHI MINH",
    "org_postcode": "700000",
    "contact_family_name": "NGUYEN",
    "contact_given_names": "VAN C",
    "contact_position": "HR MANAGER",
    "contact_business_phone": "02812345678",
    "contact_mobile": "0912345678",
    "contact_email": "hr@abc.com"
  }
}
```

**QUAN TRỌNG — Quy tắc giá trị:**

### Page 2 — Application context (Trang 2/20)
- `purpose_stream`: `"29"` = Tourist, `"30"` = Business, `"61"` = Frequent Traveller
- `visit_reason`: `"1"` = Holiday, `"3"` = Tourism, `"4"` = Family visit, `"2"` = Business
- `legal_status`: `"1"` = Citizen, `"2"` = Permanent resident
- `group_processing`: `"1"` = Yes, `"2"` = No
- `special_category`: `"1"` = Yes, `"2"` = No
- Country code: `"VIET"` = Vietnam, `"AUST"` = Australia

### Page 3 — Passport details (Trang 3/20)
- `sex`: `"F"` = Female, `"M"` = Male
- `relationship_status` (đúng theo IMMI form): `"M"` = Married, `"N"` = Never Married, `"D"` = Divorced, `"W"` = Widowed, `"F"` = De Facto, `"E"` = Engaged, `"S"` = Separated
- `place_of_birth_state`: **BẮT BUỘC** — dùng tên tỉnh/thành phố (vd: `"HO CHI MINH"`, `"HA NOI"`)
- Ngày tháng page 3: **`DD MMM YYYY`** (vd: `"10 Mar 1988"`)
- Tất cả câu hỏi Yes/No: `"Yes"` hoặc `"No"`
- `has_national_id`: `"Yes"` nếu có CCCD/CMND
- Passport country/nationality dùng mã 3 chữ: `"VNM"` = Vietnam

### Page 5 — Travelling companions (Trang 5/20)
- **Nếu có nhiều applicant**, mỗi người PHẢI có `page_5` khai người đi cùng
- Mẹ + Con → Mẹ khai Con ở page_5, Con khai Mẹ ở page_5
- `relationship` (đúng theo IMMI form):
  - `"1"` = Child (Con)
  - `"2"` = Parent (Cha/Mẹ)
  - `"3"` = Spouse/De Facto Partner
  - `"13"` = Fiance/Fiancee
  - `"18"` = Grandparent
  - `"19"` = Grandchild
  - `"31"` = Cousin
  - `"33"` = Friend
  - `"35"` = Brother
  - `"36"` = Sister
  - `"39"` = Aunt
  - `"40"` = Uncle
  - `"41"` = Niece
  - `"42"` = Nephew
- `sex`: `"F"` hoặc `"M"`, `date_of_birth`: `DD MMM YYYY`

### Page 6 — Contact details (Trang 6/20)
- `usual_country`: mã nước: `"VIET"` = Vietnam
- `closest_office`: text, vd `"Vietnam, Ho Chi Minh City"` hoặc `"Vietnam, Hanoi"`
- `residential_state`: mã tỉnh VN: `"VNSG"` = HCM, `"VNHN"` = Hà Nội (hoặc text nếu nước khác)
- `postal_same_as_residential`: `"Yes"` hoặc `"No"`

### Page 9 — Planned travel (Trang 9/20)
- `multiple_entry`: `"Yes"` hoặc `"No"`
- `length_of_stay`: số tháng (string), vd: `"12"`, `"3"`
- Ngày tháng: `DD MMM YYYY`
- `is_parent_of_australian`: `"Yes"` / `"No"`
- `undertake_study`: `"Yes"` / `"No"`
- `visit_relatives`: `"Yes"` / `"No"`

### Page 11 — Employment (Trang 11/20)
- `employment_status`: `"1"` = Employed, `"2"` = Unemployed, `"3"` = Student, `"4"` = Retired
- `occupation_grouping`: `"1"` = Managers, `"2"` = Professionals, `"3"` = Technicians...
- Ngày tháng: `DD MMM YYYY`

### Quy tắc chung
- Tên viết HOA HẾT
- Nếu có nhiều người cùng gia đình, trả về JSON array: `[{person1}, {person2}, ...]`
- **Mỗi người PHẢI có `page_5`** liệt kê người đi cùng
