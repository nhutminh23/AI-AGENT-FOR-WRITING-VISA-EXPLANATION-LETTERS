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
  "passport_issuing_authority": "IMMIGRATION DEPARTMENT OF VIETNAM",

  "has_national_id": "Yes",
  "national_id_family_name": "NGUYEN",
  "national_id_given_names": "VAN A",
  "national_id_number": "012345678901",
  "national_id_country": "VIET",
  "national_id_issue_date": "29 Jul 2022",
  "national_id_expiry_date": "01 Jan 2028",
  "national_id_reason": "",

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
  "page_8": {
    "_title": "Non-accompanying members of the family unit (Trang 8/20)",
    "non_accompanying_members": [
      {
        "relationship": "3",
        "family_name": "NGUYEN",
        "given_names": "VAN C",
        "sex": "M",
        "date_of_birth": "15 Mar 1988",
        "country_of_birth": "VIET"
      }
    ]
  },
  "page_9": {
    "_title": "Planned travel (Trang 9/20)",
    "multiple_entry": "No",
    "length_of_stay": "3",
    "planned_arrival": "01 May 2026",
    "planned_departure": "30 May 2026",
    "is_parent_of_australian": "No",
    "undertake_study": "No",
    "visit_relatives": "Yes",
    "contact_in_australia": {
      "relationship": "36",
      "family_name": "NGUYEN",
      "given_names": "THI PHUONG THAO",
      "sex": "F",
      "date_of_birth": "28 May 1990",
      "address1": "380 KEIRA ST",
      "address2": "",
      "suburb": "WOLLONGONG",
      "state": "NSW",
      "postcode": "2500",
      "phone_home": "",
      "phone_business": "",
      "phone_mobile": "",
      "email": "",
      "residency_status": "3"
    }
  },
  "page_11": {
    "_title": "Current overseas employment (Trang 11/20)",
    "employment_status": "1",
    "occupation_grouping": "2",
    "occupation": "SOFTWARE ENGINEER",
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
  },
  "page_12": {
    "_title": "Financial support (Trang 12/20)",
    "funding_source": "1",
    "available_funds": "THE APPLICANT WILL SELF-FUND THE TRIP USING PERSONAL SAVINGS OF APPROXIMATELY 5000 AUD. ACCOMMODATION AND FLIGHTS HAVE BEEN PRE-BOOKED AND PAID FOR."
  },
  "page_16": {
    "_title": "Health declarations (Trang 16/20)",
    "lived_outside_3months": "No",
    "enter_hospital": "No",
    "healthcare_worker": "No",
    "aged_disability_care": "No",
    "child_care_centre": "No",
    "classroom_3months": "No",
    "tuberculosis": "No",
    "medical_conditions": "No",
    "ongoing_medical_care": "No"
  },
  "page_17": {
    "_title": "Character declarations (Trang 17/20)",
    "charged_offence": "No",
    "convicted_offence": "No",
    "domestic_violence_order": "No",
    "arrest_warrant_interpol": "No",
    "sexual_offence_child": "No",
    "sex_offender_register": "No",
    "acquitted_unsound_mind": "No",
    "not_fit_to_plead": "No",
    "risk_national_security": "No",
    "genocide_war_crimes": "No",
    "associated_criminal": "No",
    "associated_violence": "No",
    "military_service": "No",
    "military_training": "No",
    "people_smuggling": "No",
    "removed_deported": "No",
    "overstayed_visa": "No",
    "outstanding_debts": "No"
  },
  "page_18": {
    "_title": "Visa history (Trang 18/20)",
    "held_visa": "Yes",
    "held_visa_details": "THE APPLICANT HAS PREVIOUSLY HELD TOURIST VISAS TO JAPAN (2023), SOUTH KOREA (2024), AND THAILAND (2025). ALL VISAS WERE COMPLIED WITH AND THE APPLICANT DEPARTED WITHIN THE AUTHORISED PERIOD.",
    "not_complied": "No",
    "not_complied_details": "",
    "visa_refused": "No",
    "visa_refused_details": ""
  },
  "page_20": {
    "_title": "Declarations (Trang 20/20)",
    "_note": "ALL YES - consent and declarations"
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

### Page 3 — Passport and identity details (Trang 3/20) — RẤT QUAN TRỌNG

Grok phải tự động xử lý logic sau dựa trên thông tin hồ sơ và độ tuổi của applicant:

- `has_national_id`:
  - `"Yes"` nếu là người lớn và có thông tin CCCD (số CCCD, ngày cấp, ngày hết hạn).
  - `"No"` nếu là trẻ em (thường dưới 14-16 tuổi) hoặc hồ sơ không có CCCD.

- Khi `has_national_id` = `"Yes"`:
  - Điền đầy đủ các trường national_id (family_name, given_names, number, country, issue_date, expiry_date).
  - `national_id_reason`: `""` (rỗng)
  - `other_identity_docs`: `"No"`

- Khi `has_national_id` = `"No"`:
  - Để tất cả trường `national_id_*` là `""`
  - `national_id_reason`: **BẮT BUỘC** phải điền câu lý do rõ ràng, lịch sự.  
    **Ví dụ tốt nhất:**
    "The applicant is a minor and has not yet been issued a national identity card (CCCD) by the Vietnamese authorities. Birth certificate is provided as other identity document."
  - `other_identity_docs`: **PHẢI là "Yes"**

- `other_identity_docs`:
  - `"Yes"` → Grok phải chuẩn bị dữ liệu cho bảng **Other identity documents** (xuất hiện khi nhấn Add):
    - Family name → giống `family_name` của applicant
    - Given names → giống `given_names` của applicant
    - Type of document → `"BRT_CRT"` (Birth certificate)
    - Identification number → số giấy khai sinh nếu có trong hồ sơ, nếu không thì để `"Birth Certificate"` hoặc số từ giấy khai sinh
    - Country of issue → `"VIET"`
  - `"No"` → không cần dữ liệu bổ sung

**Các trường khác bắt buộc:**
- `sex`: `"F"`, `"M"`, hoặc `"U"`
- `relationship_status`: `"M"` (Married), `"N"` (Never Married), `"D"` (Divorced), `"W"` (Widowed), `"F"` (De Facto), `"E"` (Engaged), `"S"` (Separated)
- `place_of_birth_state`: viết hoa tên tỉnh/thành (ví dụ: `"HO CHI MINH"`, `"HA NOI"`, `"DA NANG"`)
- Ngày tháng: định dạng chính xác `"DD MMM YYYY"`
- `passport_issuing_authority`: `"IMMIGRATION DEPARTMENT OF VIETNAM"`
- Passport country/nationality: mã 3 chữ `"VNM"`

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

### Page 8 — Non-accompanying family members (Trang 8/20)
- Người thân trong gia đình **KHÔNG ĐI CÙNG** (ví dụ: chồng/vợ ở nhà, cha mẹ, anh chị em)
- **QUAN TRỌNG:** Chỉ liệt kê người KHÔNG CÓ trong `page_5` (travelling companions)
- Nếu `relationship_status` là `"M"` (Married) → vợ/chồng PHẢI có trong page_8 (nếu không đi cùng)
- Nếu applicant có cha/mẹ, anh/chị em → liệt kê vào đây
- Nếu applicant KHÔNG có ai (orphan, single, v.v.) → `non_accompanying_members` = `[]` (mảng rỗng)
- `relationship`: dùng cùng bảng mã như page_5
- `country_of_birth`: mã nước, vd: `"VIET"` = Vietnam

### Page 6 — Contact details (Trang 6/20)
- `usual_country`: mã nước: `"VIET"` = Vietnam
- `closest_office`: text, vd `"Vietnam, Ho Chi Minh City"` hoặc `"Vietnam, Hanoi"`
- `residential_state`: mã tỉnh VN: `"VNSG"` = HCM, `"VNHN"` = Hà Nội (hoặc text nếu nước khác)
- `postal_same_as_residential`: `"Yes"` hoặc `"No"`

### Page 9 — Planned travel (Trang 9/20)
- `multiple_entry`: `"Yes"` hoặc `"No"`
- `length_of_stay`: **CHỈ DÙNG 3 GIÁ TRỊ:** `"3"` (Up to 3 months), `"6"` (Up to 6 months), `"12"` (Up to 12 months). **QUAN TRỌNG: Không dùng số khác!** Chọn giá trị nhỏ nhất phù hợp với thời gian ở (vd: ở 11 ngày → `"3"`, ở 4 tháng → `"6"`)
- Ngày tháng: `DD MMM YYYY`
- `is_parent_of_australian`: `"Yes"` / `"No"`
- `undertake_study`: `"Yes"` / `"No"`
- `visit_relatives`: `"Yes"` / `"No"` — Nếu applicant có người thân/bạn ở Úc → `"Yes"`
- **Nếu `visit_relatives` = `"Yes"`**, PHẢI kèm `contact_in_australia` với:
  - `relationship`: dùng bảng mã như page_5
  - `family_name`, `given_names`, `sex`, `date_of_birth`: thông tin người thân ở Úc
  - `address1`, `address2`, `suburb`, `state`, `postcode`: địa chỉ tại Úc
  - `state`: mã bang Úc (VD: `"NSW"`, `"VIC"`, `"QLD"`, `"SA"`, `"WA"`, `"TAS"`, `"NT"`, `"ACT"`)
  - `phone_home`, `phone_business`, `phone_mobile`, `email`: liên lạc
  - `residency_status`: `"1"` = Citizen, `"2"` = Permanent Resident, `"3"` = Temporary Visa Holder
- **Nếu `visit_relatives` = `"No"`**, không cần `contact_in_australia`

### Page 11 — Employment (Trang 11/20)
- `employment_status`: **ĐÚNG GIÁ TRỊ:**
  - `"1"` = Employed
  - `"2"` = Self employed
  - `"3"` = Unemployed
  - `"4"` = Retired
  - `"5"` = Student
  - `"99"` = Other
- **Nếu `employment_status` = `"1"` (Employed) hoặc `"2"` (Self employed):**
  - `occupation_grouping`: `"1"` = Managers, `"2"` = Professionals, `"3"` = Technicians, `"4"` = Community Workers, `"5"` = Clerical, `"6"` = Sales, `"7"` = Operators, `"8"` = Labourers, `"070299"` = Other
  - `occupation`: text, vd `"SOFTWARE ENGINEER"`
  - `organisation`: tên công ty/tổ chức
  - `start_date`: `DD MMM YYYY`
- **Nếu `employment_status` = `"2"` (Self employed) — thêm:**
  - `legal_registered_name`: tên đăng ký pháp lý
  - `trading_name`: tên giao dịch (có thể giống legal_registered_name)
  - `industry_type`: mã ngành (VD: `"M"` = Professional/Scientific/Technical, `"G"` = Retail, `"H"` = Accommodation/Food, `"P"` = Education, `"Q"` = Health Care)
  - `business_structure`: `"SOLE"` = Sole proprietor, `"COMP"` = Company, `"PART"` = Partnership, `"PROP"` = Proprietary company
  - `business_reg_type`: loại đăng ký kinh doanh (text)
  - `business_reg_id`: mã số đăng ký (text)
  - `org_website`: website (nếu có)
- **Nếu `employment_status` = `"3"` (Unemployed):**
  - `unemployment_date_from`: `DD MMM YYYY`
  - `last_employment_position`: text
- **Nếu `employment_status` = `"4"` (Retired):**
  - `retirement_date`: `DD MMM YYYY`
- **Nếu `employment_status` = `"5"` (Student):**
  - `course_name`: text
  - `institution_name`: text
  - `course_date_from`: `DD MMM YYYY`
  - `course_date_to`: `DD MMM YYYY`
- **Nếu `employment_status` = `"99"` (Other):**  
  - `give_details`: **BẮT BUỘC** — text mô tả chi tiết lý do (ví dụ: "Housewife with rental income", "Property owner", "Self-funded by investments"...). Đây chính là nội dung điền vào ô "Give details" trên form.
- Tất cả trường hợp: org_country, org_address, org_suburb, org_state, org_postcode
- Ngày tháng: `DD MMM YYYY`

### Page 12 — Financial support (Trang 12/20)
- `funding_source`: **ĐÚNG GIÁ TRỊ:**
  - `"1"` = Self funded (tự túc)
  - `"2"` = Supported by current overseas employer (có công ty hỗ trợ)
  - `"3"` = Supported by other organisation (tổ chức khác hỗ trợ)
  - `"4"` = Supported by other person (người khác hỗ trợ)
- `available_funds`: text mô tả nguồn tài chính (BẮT BUỘC), vd: `"PERSONAL SAVINGS OF 5000 AUD. ACCOMMODATION AND FLIGHTS PRE-BOOKED."`
- **Nếu `funding_source` = `"2"` hoặc `"3"` (Employer/Organisation):**
  - `support_type`: `"1"` = Financial, `"2"` = Accommodation, `"3"` = All costs, `"99"` = Other
  - `paying_org`: `"1"` = Current overseas employer, `"2"` = Organisation in Australia, `"3"` = Other organisation
  - `org_legal_name`: tên đăng ký pháp lý
  - `org_trading_name`: tên giao dịch
  - `org_industry_type`: mã ngành (giống page_11)
  - `org_business_structure`: mã cấu trúc (giống page_11)
  - `org_country`, `org_address1`, `org_suburb`, `org_state`, `org_postcode`: địa chỉ tổ chức
- **Nếu `funding_source` = `"4"` (Other person):**
  - `support_type`: `"1"` = Financial, `"2"` = Accommodation, `"3"` = All costs, `"99"` = Other
  - `supporter_relationship`: mã quan hệ (dùng bảng mã như page_5)
  - `supporter_family_name`: họ người hỗ trợ
  - `supporter_given_names`: tên người hỗ trợ
- **Với du lịch thông thường:** hầu hết là `"1"` (Self funded)

### Page 16 — Health declarations (Trang 16/20)
- **MẶC ĐỊNH TẤT CẢ LÀ `"No"`** cho visa du lịch thông thường
- `lived_outside_3months`: Đã sống ngoài nước passport >3 tháng trong 5 năm? `"Yes"` / `"No"`
- `enter_hospital`: Dự định vào bệnh viện/cơ sở y tế ở Úc? `"Yes"` / `"No"`
- `healthcare_worker`: Dự định làm/học nhân viên y tế ở Úc? `"Yes"` / `"No"`
- `aged_disability_care`: Dự định làm việc tại cơ sở chăm sóc người già/khuyết tật? `"Yes"` / `"No"`
- `child_care_centre`: Dự định làm việc tại trung tâm trẻ em? `"Yes"` / `"No"`
- `classroom_3months`: Dự định ở lớp học >3 tháng? `"Yes"` / `"No"`
- `tuberculosis`: Từng mắc/tiếp xúc lao phổi, chụp X-quang bất thường? `"Yes"` / `"No"`
- `medical_conditions`: Cần điều trị bệnh (ung thư, tim, HIV, thận, v.v.)? `"Yes"` / `"No"`
- `ongoing_medical_care`: Cần chăm sóc y tế liên tục/thiết bị hỗ trợ? `"Yes"` / `"No"`
- **QUAN TRỌNG:** Luôn trả `page_16` với tất cả giá trị `"No"` trừ khi hồ sơ có thông tin y tế đặc biệt

### Page 17 — Character declarations (Trang 17/20)
- **MẶC ĐỊNH TẤT CẢ LÀ `"No"`** cho visa du lịch thông thường
- 18 câu hỏi về tiền án, bạo lực gia đình, an ninh quốc gia, quân sự, buôn người, trục xuất, nợ chính phủ Úc
- **QUAN TRỌNG:** Luôn trả `page_17` với tất cả giá trị `"No"` trừ khi hồ sơ có thông tin đặc biệt

### Page 18 — Visa history (Trang 18/20)
- `held_visa`: Từng có/đang có visa đi Úc hoặc nước khác? `"Yes"` / `"No"`
  - Nếu `"Yes"` → `held_visa_details`: mô tả lịch sử visa (max 300 ký tự), liệt kê nước + năm + loại visa
- `not_complied`: Từng vi phạm điều kiện visa? `"Yes"` / `"No"`
  - Nếu `"Yes"` → `not_complied_details`: mô tả chi tiết (max 300 ký tự)
- `visa_refused`: Từng bị từ chối/hủy visa? `"Yes"` / `"No"`
  - Nếu `"Yes"` → `visa_refused_details`: mô tả chi tiết (max 300 ký tự)
- **QUAN TRỌNG:** Dựa vào travel history trong hồ sơ để xác định `held_visa`. Nếu có lịch sử du lịch → `"Yes"` + liệt kê chi tiết

### Quy tắc chung
- Tên viết HOA HẾT
- Nếu có nhiều người cùng gia đình, trả về JSON array: `[{person1}, {person2}, ...]`
- **Mỗi người PHẢI có `page_5`** liệt kê người đi cùng
- **Mỗi người PHẢI có `page_8`** liệt kê người thân KHÔNG đi cùng (chồng/vợ, cha mẹ, anh chị em)
- Nếu trong hồ sơ KHÔNG có thông tin người thân → `non_accompanying_members` = `[]`
