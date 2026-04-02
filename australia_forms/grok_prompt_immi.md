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

**FORMAT JSON CHO MỖI NGƯỜI:**

```json
{
  "applicant_name": "NGUYEN VAN A",
  "page_2": {
    "_title": "Application context",
    "outside_australia": "Yes",
    "current_location": "VIET",
    "legal_status": "1",
    "purpose_stream": "29",
    "initial_purpose": "2",
    "visit_reason": "4",
    "significant_dates": "THE APPLICANT INTENDS TO VISIT AUSTRALIA FROM 15 MARCH 2026 TO 25 MARCH 2026. HOWEVER, THIS SCHEDULE IS SUBJECT TO CHANGE BASED ON THE DATE OF VISA GRANT.",
    "group_processing": "2",
    "special_category": "2"
  },
  "page_3": {
    "_title": "Passport details",
    "family_name": "NGUYEN",
    "given_names": "VAN A",
    "sex": "Male",
    "date_of_birth": "01/01/1990",
    "place_of_birth_city": "HO CHI MINH CITY",
    "place_of_birth_country": "VIET",
    "relationship_status": "Married",
    "passport_number": "C1234567",
    "passport_country": "VIET",
    "passport_nationality": "VNM",
    "passport_issue_date": "01/01/2020",
    "passport_expiry_date": "01/01/2030",
    "passport_issuing_authority": "IMMIGRATION DEPARTMENT",
    "national_id_number": "012345678901"
  },
  "page_5": {
    "_title": "Other identity documents",
    "other_names_used": "No",
    "other_passports": "No",
    "other_citizenships": "No",
    "citizen_of_birth_country": "Yes"
  },
  "page_6": {
    "_title": "Critical dates",
    "proposed_arrival_date": "15/03/2026",
    "proposed_departure_date": "25/03/2026",
    "proposed_duration_months": "0",
    "proposed_duration_days": "10",
    "previous_australian_visa": "No",
    "previous_visa_details": ""
  },
  "page_8": {
    "_title": "Address and contact",
    "residential_address_line1": "123 NGUYEN HUE STREET",
    "residential_address_line2": "",
    "residential_city": "HO CHI MINH CITY",
    "residential_state": "",
    "residential_postcode": "700000",
    "residential_country": "VIET",
    "postal_same_as_residential": "Yes",
    "phone_home": "02812345678",
    "phone_mobile": "0901234567",
    "email": "example@gmail.com",
    "address_in_australia": "456 GEORGE STREET, SYDNEY NSW 2000"
  },
  "page_9": {
    "_title": "Employment and education",
    "employment_status": "Employed",
    "employer_name": "ABC COMPANY LTD",
    "employer_address": "789 LE LOI STREET, DISTRICT 1, HCMC",
    "job_title": "ACCOUNTANT",
    "employment_start_date": "01/06/2015",
    "annual_income_aud": "15000",
    "highest_qualification": "Bachelor degree",
    "qualification_field": "Accounting"
  },
  "page_11": {
    "_title": "Travel companion and sponsor",
    "travelling_with_others": "Yes",
    "companion_names": "TRAN THI B (Wife), NGUYEN VAN C (Son)",
    "sponsor_type": "friend_or_relative",
    "sponsor_name": "NGUYEN THI D",
    "sponsor_address": "456 GEORGE STREET, SYDNEY NSW 2000",
    "sponsor_phone": "+61412345678",
    "sponsor_relationship": "Sister",
    "sponsor_citizenship": "Australian citizen",
    "financial_support": "Self-funded with partial support from sponsor"
  }
}
```

**QUAN TRỌNG:**
- Giá trị `purpose_stream`: `"29"` = Tourist, `"30"` = Business, `"61"` = Frequent Traveller
- Giá trị `visit_reason`: `"1"` = Holiday, `"4"` = Family visit, `"6"` = Business
- Giá trị `legal_status`: `"1"` = Citizen, `"2"` = Permanent resident
- Giá trị `group_processing`: `"1"` = Yes, `"2"` = No
- Giá trị `special_category`: `"1"` = Yes, `"2"` = No
- Giá trị `sex`: `"Male"` hoặc `"Female"`
- Ngày tháng format: `DD/MM/YYYY`
- Country code: `"VIET"` = Vietnam, `"AUST"` = Australia, etc.
- Tên viết HOA HẾT

Nếu có nhiều người cùng gia đình, trả về JSON array: `[{person1}, {person2}, ...]`
