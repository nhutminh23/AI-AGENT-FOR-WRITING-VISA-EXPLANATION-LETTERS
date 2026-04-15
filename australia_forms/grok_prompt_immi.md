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

## 🚫🚫🚫 QUY TẮC TUYỆT ĐỐI — KHÔNG ĐƯỢC VI PHẠM 🚫🚫🚫

**TUYỆT ĐỐI KHÔNG ĐƯỢC BỊA / SUY LUẬN / ĐOÁN bất kỳ thông tin nào.** Bạn CHỈ ĐƯỢC trích xuất thông tin CÓ THẬT trong file tôi gửi.

⚠️ **Nếu một thông tin KHÔNG CÓ trong bất kỳ file nào tôi gửi → BẮT BUỘC để `""` (chuỗi rỗng).** KHÔNG BAO GIỜ được tự bịa ra.

**Cụ thể KHÔNG ĐƯỢC BỊA:**
- ❌ Tên người (họ tên vợ/chồng, cha mẹ, con cái) → nếu file không ghi tên → để `""`
- ❌ Ngày sinh → nếu file không ghi → để `""`
- ❌ Số CCCD/CMND → nếu file không ghi → để `""`
- ❌ Số dư ngân hàng, tên ngân hàng → nếu file không có sao kê/xác nhận → để `""`
- ❌ Địa chỉ → nếu file không ghi rõ → để `""`
- ❌ Nghề nghiệp, nơi làm việc → nếu file không ghi → để `""`
- ❌ Quan hệ gia đình → nếu file không xác nhận rõ → để `""`

**CÁCH KIỂM TRA:** Trước khi điền MỖI trường, hãy tự hỏi: "Thông tin này CÓ ĐÚNG NẰM TRONG file không?" Nếu câu trả lời là KHÔNG hoặc KHÔNG CHẮC → để `""`.

**VÍ DỤ SAI:** Suy luận tên vợ từ tên con (thấy con họ Nguyễn → đoán mẹ cũng họ Nguyễn). ĐÂY LÀ BỊA — KHÔNG ĐƯỢC LÀM.

---

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
    "significant_dates": "[Grok tự động chèn ngày và chọn 1 trong 4 câu chuẩn bên dưới tùy hồ sơ]",
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
  "grant_number": "",

  "other_passports": "No",
  "other_identity_docs": "No",

  "health_examination": "No"
  },
  "page_5": {
    "_title": "Travelling companions (Trang 5/20)",
    "_WARNING_MINOR_CHECK": "⚠️ BẮT BUỘC: Tính tuổi từ page_3.date_of_birth so với NGÀY HIỆN TẠI. Nếu dưới 18 tuổi → is_minor='Yes' + PHẢI có parents_guardians[]. Nếu từ 18 tuổi trở lên → is_minor='No' + BỎ parents_guardians. VD: DOB='04 Sep 2009', ngày hiện tại=2026 → tuổi=16 → is_minor='Yes'",
    "is_minor": "Yes hoặc No (BẮT BUỘC tính từ DOB)",
    "travelling_with_parent": "Yes nếu có cha/mẹ đi cùng (chỉ khi is_minor=Yes)",
    "not_with_parent_reason": "",
    "not_with_parent_details": "",
    "parents_guardians": [
      {
        "_NOTE": "Lấy passport info từ hồ sơ của NGƯỜI CHA/MẸ trong cùng bộ hồ sơ. Nếu cha/mẹ cũng nộp visa → has_submitted_visa=Yes + ref_number=TRN của cha/mẹ",
        "relationship": "2",
        "family_name": "VU",
        "given_names": "THI DAN",
        "sex": "F",
        "date_of_birth": "20 Jul 1976",
        "passport_number": "P02685236 (lấy từ page_3 của applicant cha/mẹ)",
        "passport_country": "VNM",
        "passport_nationality": "VNM",
        "passport_issue_date": "",
        "passport_expiry_date": "",
        "passport_issuing_authority": "IMMIGRATION DEPARTMENT OF VIETNAM",
        "has_submitted_visa": "Yes (nếu cha/mẹ cũng nộp visa)",
        "ref_number_type": "1 (1=TRN, 10=Application ID, 3=Visa grant number)",
        "ref_number": "TRN hoặc Application ID của cha/mẹ"
      }
    ],
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
    "_ADDRESS_RULE": "⚠️ ĐỊA CHỈ PHẢI DỊCH SANG TIẾNG ANH. Không được để nguyên tiếng Việt bỏ dấu!",
    "usual_country": "VIET",
    "closest_office": "Vietnam, Ho Chi Minh City hoặc Vietnam, Hanoi (chọn gần nhất)",
    "residential_country": "VIET",
    "residential_address1": "123 NGUYEN HUE STREET (dịch: ĐƯỜNG→STREET, QUỐC LỘ→HIGHWAY, NGÕ/HẺM→ALLEY, THÔN/XÓM→HAMLET)",
    "residential_address2": "(nếu cần dòng 2)",
    "residential_suburb": "DISTRICT 1 (dịch: QUẬN→DISTRICT, HUYỆN→DISTRICT, PHƯỜNG→WARD, XÃ→COMMUNE, THỊ TRẤN→TOWN)",
    "residential_state": "HO CHI MINH (tên tỉnh/thành phố bỏ dấu, không thêm tiền tố)",
    "residential_postcode": "700000 (nếu có, để trống nếu không biết)",
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
    "know_dates_of_entry": "No",
    "dates_of_entry_reason": "The applicant has a confirmed itinerary for only one short tourist visit to Australia from 01 May 2026 to 30 May 2026. Although the visa allows multiple entries, they have not planned any subsequent visits and therefore do not know the entry dates for any future occasions after the first arrival.",
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
    "org_suburb": "BEN NGHE WARD",
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
    "available_funds": "THE APPLICANT WILL SELF-FUND THE TRIP. BANK STATEMENTS FROM VIETCOMBANK SHOW: (1) SAVINGS ACCOUNT BALANCE: VND 150,000,000 (APPROX. AUD 9,500), (2) FIXED DEPOSIT: VND 200,000,000 (APPROX. AUD 12,500). THE APPLICANT ALSO OWNS A RESIDENTIAL PROPERTY (85 SQM APARTMENT) IN DISTRICT 7, HO CHI MINH CITY. MONTHLY SALARY: VND 25,000,000. ROUND-TRIP FLIGHTS AND ACCOMMODATION HAVE BEEN PRE-BOOKED AND PAID.",
    "_IF_funding_source_4": "Nếu funding_source=4 (người khác hỗ trợ), PHẢI thêm các trường sau:",
    "support_type": "1 (1=Financial, 2=Accommodation, 3=All costs, 99=Other)",
    "supporter_relationship": "36 (dùng bảng mã quan hệ như page_5)",
    "supporter_family_name": "TRAN",
    "supporter_given_names": "THI MY LINH",
    "supporter_country": "A (A=Australia, VIET=Vietnam — dùng mã IMMI)",
    "supporter_address1": "12 SMITH STREET",
    "supporter_address2": "",
    "supporter_suburb": "BANKSTOWN",
    "supporter_state": "NSW (nếu ở Úc: ACT/NSW/NT/QLD/SA/TAS/VIC/WA)",
    "supporter_postcode": "2200"
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
- `significant_dates`: **ĐIỀN TEXT IN HOA**. Tìm ngày dự định bay trong lịch trình/booking và dùng 1 trong 4 câu chuẩn sau đây tùy theo chức nghiệp và mục đích chuyến đi:
  - Nếu đi Tự túc mà có Khai Công việc / Hợp đồng lđ: `"THE APPLICANT INTENDS TO VISIT AUSTRALIA FROM [NGÀY ĐI] TO [NGÀY VỀ]. THESE DATES HAVE BEEN SPECIFICALLY CHOSEN TO ALIGN WITH THEIR APPROVED ANNUAL LEAVE FROM THEIR EMPLOYER IN VIETNAM."`
  - Nếu có thăm thân nhân (Family visit): `"THE APPLICANT INTENDS TO VISIT AUSTRALIA FROM [NGÀY ĐI] TO [NGÀY VỀ] TO SPEND QUALITY TIME WITH THEIR RELATIVES AND EXPERIENCE THE LOCAL CULTURE, BEFORE RETURNING TO VIETNAM AS PLANNED."`
  - Nếu khách Tự do / Nội trợ / Kinh doanh riêng: `"THE APPLICANT INTENDS TO VISIT AUSTRALIA FOR A SHORT HOLIDAY COMMENCING FROM [NGÀY ĐI] UNTIL [NGÀY VỀ]. THIS TIMEFRAME DIRECTLY ALIGNS WITH THEIR PRE-BOOKED ROUND-TRIP FLIGHT TICKETS AND ACCOMMODATION ARRANGEMENTS."`
  - Nếu không rõ ràng (Mặc định): `"THE APPLICANT CONFIRMS THEIR INTENTION TO VISIT AUSTRALIA FROM [NGÀY ĐI] TO [NGÀY VỀ] FOR TOURISM PURPOSES, AND FULLY INTENDS TO DEPART AUSTRALIA ON OR BEFORE THE PLANNED RETURN DATE."`
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

- **`previously_applied_visa` và `has_grant_number` — LOGIC VISA GRANT:**
  - Nếu applicant **đã từng xin visa Úc** → `previously_applied_visa`: `"Yes"`
  - Nếu có **grant number** (từ lá thư cấp visa, lịch sử visa) → `has_grant_number`: `"Yes"`
  - `grant_number`: **BẮT BUỘC** khi `has_grant_number` = `"Yes"` — điền số grant (VD: `"2909579417223"`). Tìm trong:
    - Visa grant letter/notification
    - VEVO check result
    - Lịch sử visa trước đó
  - Nếu không có grant number → `has_grant_number`: `"No"`, `grant_number`: `""`

**Các trường khác bắt buộc:**
- `sex`: `"F"`, `"M"`, hoặc `"U"`
- `relationship_status`: `"M"` (Married), `"N"` (Never Married), `"D"` (Divorced), `"W"` (Widowed), `"F"` (De Facto), `"E"` (Engaged), `"S"` (Separated)
- `place_of_birth_state`: viết hoa tên tỉnh/thành (ví dụ: `"HO CHI MINH"`, `"HA NOI"`, `"DA NANG"`)
- Ngày tháng: định dạng chính xác `"DD MMM YYYY"`
- `passport_issuing_authority`: `"IMMIGRATION DEPARTMENT OF VIETNAM"`
- Passport country/nationality: mã 3 chữ `"VNM"`

**⚠️ QUY TẮC TUYỆT ĐỐI VỀ NGÀY THÁNG — PASSPORT vs CCCD:**
> **PASSPORT và CCCD (National ID) là 2 GIẤY TỜ HOÀN TOÀN KHÁC NHAU. TUYỆT ĐỐI KHÔNG ĐƯỢC LẪN LỘN NGÀY CẤP/HẾT HẠN GIỮA CHÚNG!**

- `passport_issue_date`: Chỉ lấy từ **trang thông tin passport** (nơi có ảnh, số passport). KHÔNG BAO GIỜ lấy từ CCCD.
- `passport_expiry_date`: Chỉ lấy từ **trang thông tin passport**. KHÔNG BAO GIỜ lấy từ CCCD.
- `national_id_issue_date`: Chỉ lấy từ **CCCD/CMND** (Căn cước công dân). KHÔNG BAO GIỜ lấy từ passport.
- `national_id_expiry_date`: Chỉ lấy từ **CCCD/CMND**. KHÔNG BAO GIỜ lấy từ passport.

**QUY TẮC "ĐỂ TRỐNG":** Nếu KHÔNG TÌM THẤY ngày cấp hoặc hết hạn trong đúng giấy tờ tương ứng → **để `""` (chuỗi rỗng)**. TUYỆT ĐỐI KHÔNG tự bịa, không suy luận, không lấy ngày từ giấy tờ khác để chèn vào.

- ✅ `"passport_issue_date": ""` (nếu không thấy trên passport) → **ĐÚNG**
- ✅ `"national_id_expiry_date": ""` (nếu CCCD không ghi ngày hết hạn) → **ĐÚNG**
- ❌ `"passport_issue_date": "29 Jul 2022"` (lấy từ ngày cấp CCCD) → **SAI NGHIÊM TRỌNG**
- ❌ `"national_id_issue_date": "05 Apr 2023"` (lấy từ ngày cấp passport) → **SAI NGHIÊM TRỌNG**
- ❌ `"passport_expiry_date": "29 Jul 2047"` (lấy từ hạn CCCD) → **SAI NGHIÊM TRỌNG**

### Page 5 — Travelling companions (Trang 5/20)

### 🚨🚨🚨 CRITICAL: MINOR DETECTION — KHÔNG ĐƯỢC BỎ QUA 🚨🚨🚨

**BƯỚC 1 — Tính tuổi BẮT BUỘC cho MỌI applicant:**
- Công thức: `tuổi = NĂM HIỆN TẠI - NĂM SINH` (điều chỉnh nếu chưa qua sinh nhật)
- Ví dụ: `date_of_birth = "04 Sep 2009"`, ngày hiện tại = tháng 4/2026 → tuổi = 16 → **MINOR**
- Nếu tuổi < 18 → `is_minor`: `"Yes"` → **BẮT BUỘC có `parents_guardians`**
- Nếu tuổi >= 18 → `is_minor`: `"No"` → KHÔNG cần `parents_guardians`

**BƯỚC 2 — Khi `is_minor` = `"Yes"` — BẮT BUỘC thêm `parents_guardians`:**

1. `travelling_with_parent`: `"Yes"` nếu có cha/mẹ/người giám hộ đi cùng, `"No"` nếu không
2. **Nếu `travelling_with_parent` = `"Yes"`:**
   - `parents_guardians`: mảng thông tin cha/mẹ đi cùng (**"Responsible person details" form**):
     - `relationship`: `"2"` = Parent, `"14"` = Step Parent, `"87"` = Legal guardian
     - `family_name`, `given_names`: tên trên passport (viết HOA)
     - `sex`: `"F"` / `"M"` / `"U"`
     - `date_of_birth`: `DD MMM YYYY`
     - `passport_number`: số passport
     - `passport_country`: mã 3 chữ (VD: `"VNM"`)
     - `passport_nationality`: mã 3 chữ (VD: `"VNM"`)
     - `passport_issue_date`: `DD MMM YYYY` — **CHỈ lấy từ passport**, KHÔNG lấy từ CCCD
     - `passport_expiry_date`: `DD MMM YYYY` — **CHỈ lấy từ passport**, KHÔNG lấy từ CCCD
     - `passport_issuing_authority`: `"IMMIGRATION DEPARTMENT OF VIETNAM"` (hoặc cơ quan cấp trên passport)
     - `has_submitted_visa`: `"Yes"` nếu cha/mẹ đã nộp đơn visa riêng, `"No"` nếu chưa
     - **Nếu `has_submitted_visa` = `"Yes"`:**
       - `ref_number_type`: `"1"` = TRN, `"10"` = Application ID, `"3"` = Visa grant number
       - `ref_number`: mã tham chiếu (VD: `"EGPC7ZXB8D"` cho TRN)
   - `not_with_parent_reason`: `""` (rỗng)
   - `not_with_parent_details`: `""` (rỗng)

3. **Nếu `travelling_with_parent` = `"No"`:**
   - `not_with_parent_reason`: lý do không đi cùng cha mẹ:
     - `"1"` = Travelling with another relative aged over 21 (e.g., grandparent)
     - `"2"` = Visiting parents already in Australia (travelling unaccompanied)
     - `"3"` = Visiting other relatives already in Australia (travelling unaccompanied)
     - `"4"` = Travelling on an organised tour (e.g., study tour)
     - `"5"` = Other reason
   - `not_with_parent_details`: text giải thích chi tiết (nếu chọn `"5"` Other), max 300 ký tự
   - `parents_guardians`: `[]` (mảng rỗng) — HOẶC vẫn khai người thân đi cùng nếu có (VD: ông bà)

**Companions (dùng chung cho cả adult và minor):**
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

**🚨 ĐỊA CHỈ BẮT BUỘC DỊCH SANG TIẾNG ANH — KHÔNG để nguyên tiếng Việt bỏ dấu!**

**Bảng dịch đơn vị hành chính Việt Nam:**
| Tiếng Việt | Tiếng Anh | Ví dụ |
|------------|-----------|-------|
| Xóm / Thôn / Ấp | Hamlet | XOM 7C → HAMLET 7C |
| Đường / Phố | Street | DUONG NGUYEN HUE → NGUYEN HUE STREET |
| Ngõ / Hẻm | Alley / Lane | NGO 12 → ALLEY 12 |
| Xã | Commune | XA CON THOI → CON THOI COMMUNE |
| Phường | Ward | PHUONG 5 → WARD 5 |
| Thị trấn | Town | THI TRAN PHO YEN → PHO YEN TOWN |
| Quận | District | QUAN 1 → DISTRICT 1 |
| Huyện | District | HUYEN KIM SON → KIM SON DISTRICT |
| Thị xã | Town | THI XA SON TAY → SON TAY TOWN |
| Tỉnh | Province | (chỉ ghi tên, VD: NINH BINH) |
| Thành phố | City | (chỉ ghi tên, VD: HO CHI MINH) |

**Cách điền:**
- `residential_address1`: Địa chỉ chi tiết (số nhà, tên đường/thôn/xóm). VD: `"HAMLET 7C"` hoặc `"123 NGUYEN HUE STREET"`
- `residential_address2`: Phần bổ sung nếu cần. VD: `"CON THOI COMMUNE"` (xã)
- `residential_suburb`: Quận/Huyện/Phường. VD: `"KIM SON DISTRICT"` (KHÔNG viết `"HUYEN KIM SON"`)
- `residential_state`: Tỉnh/Thành phố — **CHỈ ghi tên**, bỏ dấu. VD: `"NINH BINH"` (KHÔNG viết `"TINH NINH BINH"`)
- `residential_postcode`: Mã bưu chính nếu có, để `""` nếu không biết

**❌ SAI:**
```
"residential_address1": "XOM 7C"
"residential_address2": "XA CON THOI"
"residential_suburb": "HUYEN KIM SON"
```

**✅ ĐÚNG:**
```
"residential_address1": "HAMLET 7C"
"residential_address2": "CON THOI COMMUNE"
"residential_suburb": "KIM SON DISTRICT"
```

**`closest_office`:** Chọn văn phòng gần nhất:
- Bắc/Trung bộ (Hà Nội, Ninh Bình, Đà Nẵng, Nghệ An...) → `"Vietnam, Hanoi"`
- Nam bộ (HCM, Bình Dương, Cần Thơ, Đồng Nai...) → `"Vietnam, Ho Chi Minh City"`

### Page 8 — Non-accompanying family members (Trang 8/20)
- Người thân trong gia đình **KHÔNG ĐI CÙNG** (ví dụ: chồng/vợ ở nhà, cha mẹ, anh chị em)
- **QUAN TRỌNG:** Chỉ liệt kê người KHÔNG CÓ trong `page_5` (travelling companions)
- Nếu `relationship_status` là `"M"` (Married) → vợ/chồng PHẢI có trong page_8 (nếu không đi cùng) **NHƯNG CHỈ KHI file hồ sơ CÓ GHI TÊN vợ/chồng**. Nếu phần thông tin vợ/chồng trong form khai TRỐNG hoặc KHÔNG CÓ trong file → để `family_name: ""`, `given_names: ""`, `date_of_birth: ""`
- Nếu applicant có cha/mẹ, anh/chị em **CÓ GHI RÕ TRONG FILE** → liệt kê vào đây
- Nếu applicant KHÔNG có ai (orphan, single, v.v.) HOẶC file không ghi thông tin người thân → `non_accompanying_members` = `[]` (mảng rỗng)
- ⚠️ **KHÔNG ĐƯỢC suy luận tên vợ/chồng từ giấy khai sinh con hay bất kỳ nguồn gián tiếp nào. CHỈ lấy từ form khai hoặc giấy tờ CÓ GHI RÕ.**
- `relationship`: dùng cùng bảng mã như page_5
- `country_of_birth`: mã nước, vd: `"VIET"` = Vietnam

### Page 6 — Contact details (Trang 6/20)
- `usual_country`: mã nước: `"VIET"` = Vietnam
- `closest_office`: text, vd `"Vietnam, Ho Chi Minh City"` hoặc `"Vietnam, Hanoi"`
- `residential_state`: **PHẢI dùng TÊN ĐẦY ĐỦ TIẾNG ANH viết hoa**, KHÔNG dùng mã code:
  - ✅ `"HO CHI MINH"`, `"HA NOI"`, `"BEN TRE"`, `"DA NANG"`, `"BINH DUONG"`
  - ❌ KHÔNG dùng `"VNSG"`, `"VNHN"` — đây là mã code, form sẽ không fill đúng
  - Tên tỉnh dùng romanized Vietnamese không dấu
- `postal_same_as_residential`: `"Yes"` hoặc `"No"`

### Page 9 — Planned travel (Trang 9/20)
- `multiple_entry`: `"Yes"` hoặc `"No"`
- `length_of_stay`: **CHỈ DÙNG 3 GIÁ TRỊ:** `"3"` (Up to 3 months), `"6"` (Up to 6 months), `"12"` (Up to 12 months). **QUAN TRỌNG: Không dùng số khác!** Chọn giá trị nhỏ nhất phù hợp với thời gian ở (vd: ở 11 ngày → `"3"`, ở 4 tháng → `"6"`)
- Ngày tháng: `DD MMM YYYY`
- **`know_dates_of_entry`** — Trường này **XUẤT HIỆN KHI** applicant đã từng có visa Úc hoặc chọn multiple entry:
  - `"Yes"` nếu applicant biết chính xác ngày nhập cảnh cho mỗi lần sau lần đầu
  - `"No"` nếu chỉ có kế hoạch 1 chuyến đi (THÔNG THƯỜNG là `"No"`)
  - **Nếu `"No"`** → `dates_of_entry_reason`: **BẮT BUỘC** — text giải thích lý do bằng tiếng Anh.  
    **Ví dụ:** `"The applicant has a confirmed itinerary for only one short tourist visit to Australia from 05 Jun 2026 to 15 Jun 2026. Although the visa allows multiple entries, they have not planned any subsequent visits and therefore do not know the entry dates for any future occasions after the first arrival."`
  - **Nếu `"Yes"`** → `dates_of_entry_reason`: `""` (rỗng)
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
  - `give_details`: **BẮT BUỘC** — text mô tả chi tiết BẰNG TIẾNG ANH ĐẦY ĐỦ (KHÔNG dùng tiếng Việt, KHÔNG dùng tiếng Việt không dấu).
    - ✅ `"BUDDHIST NUN AND ABBESS OF TU HUE PAGODA (TU HUE TEMPLE), TAM PHUOC COMMUNE, CHAU THANH DISTRICT, BEN TRE PROVINCE, SERVING SINCE 2007"`
    - ✅ `"HOMEMAKER AND PROPERTY OWNER, MANAGING FAMILY RENTAL PROPERTIES IN HO CHI MINH CITY"`
    - ❌ KHÔNG dùng: `"TRU TRI CHUA TU HUE"` (tiếng Việt không dấu)
    - ❌ KHÔNG dùng: `"NI SU CHUA TU HUE"` (tiếng Việt)
    - **Quy tắc:** Dịch chức danh, tên chùa, tên tổ chức sang tiếng Anh. Có thể kèm tên gốc trong ngoặc nếu cần: `"ABBESS OF TU HUE PAGODA (CHUA TU HUE)"`
- Tất cả trường hợp: org_country, org_address, org_suburb, org_state, org_postcode
- Ngày tháng: `DD MMM YYYY`

### Page 12 — Financial support (Trang 12/20)
- `funding_source`: **ĐÚNG GIÁ TRỊ:**
  - `"1"` = Self funded (tự túc)
  - `"2"` = Supported by current overseas employer (có công ty hỗ trợ)
  - `"3"` = Supported by other organisation (tổ chức khác hỗ trợ)
  - `"4"` = Supported by other person (người khác hỗ trợ)
- `available_funds`: **BẮT BUỘC PHẢI CỤ THỂ VỀ TÀI CHÍNH** — TẬP TRUNG VÀO TÀI SẢN VÀ SỐ DƯ, KHÔNG ĐƯỢC chung chung!
  - **ƯU TIÊN CAO (phải có nếu có trong hồ sơ):**
    - 🏦 Tên ngân hàng + số dư tài khoản bằng VND VÀ quy đổi AUD (ví dụ: `"AGRIBANK SAVINGS ACCOUNT: VND 250,000,000 (APPROX. AUD 15,600)"`)
    - 🏦 Nếu có nhiều tài khoản ngân hàng → liệt kê TẤT CẢ với số dư từng cái
    - 💰 Tiền gửi tiết kiệm / fixed deposit (số tiền, kỳ hạn nếu có)
    - 🏠 Bất động sản / đất đai (diện tích, vị trí, giá trị ước tính nếu có)
    - 📊 Thu nhập hàng tháng / nguồn thu nhập (lương, cho thuê, kinh doanh)
  - **ƯU TIÊN THẤP (nhắc ngắn gọn, không cần chi tiết giá):**
    - ✈️ Vé máy bay đã đặt (chỉ cần ghi "ROUND-TRIP FLIGHTS HAVE BEEN PRE-BOOKED")
    - 🏨 Khách sạn đã đặt (chỉ cần ghi "ACCOMMODATION HAS BEEN ARRANGED")
  - **Ví dụ tốt:** `"THE APPLICANT WILL SELF-FUND THE TRIP. BANK STATEMENTS FROM AGRIBANK SHOW: (1) SAVINGS ACCOUNT BALANCE: VND 250,000,000 (APPROX. AUD 15,600), (2) FIXED DEPOSIT: VND 100,000,000 (APPROX. AUD 6,250). THE APPLICANT ALSO OWNS RESIDENTIAL LAND (200 SQM) IN BEN TRE PROVINCE AND A HOUSE IN TAM PHUOC COMMUNE. MONTHLY INCOME FROM DONATIONS AND TEMPLE ACTIVITIES: APPROX. VND 15,000,000. ROUND-TRIP FLIGHTS AND ACCOMMODATION HAVE BEEN PRE-BOOKED AND PAID."`
  - **❌ KHÔNG viết:** `"PERSONAL SAVINGS. FLIGHTS AND HOTEL PRE-BOOKED."` (quá chung chung, thiếu số liệu)
  - **❌ KHÔNG viết:** `"THE APPLICANT WILL SELF-FUND THE TRIP USING PERSONAL SAVINGS AND BANK BALANCE AS SHOWN IN AGRIBANK STATEMENTS."` (thiếu số dư cụ thể)
  - ⚠️ **QUAN TRỌNG: CHỈ GHI SỐ TIỀN VÀ TÊN NGÂN HÀNG CHÍNH XÁC TỪ FILE.** Nếu sao kê ngân hàng mờ/không đọc được số dư → ghi `"BANK STATEMENTS FROM [TÊN NGÂN HÀNG] ATTACHED"` thay vì bịa số. KHÔNG ĐƯỢC tự ước tính hoặc bịa số dư.
  - ⚠️ **Nếu hồ sơ KHÔNG CÓ sao kê ngân hàng** → KHÔNG được ghi tên ngân hàng hay số dư. Chỉ ghi những tài sản/nghề nghiệp CÓ TRONG FILE.
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
  - `supporter_country`: mã quốc gia nơi supporter sống (VD: `"A"` = Australia, `"VIET"` = Vietnam)
  - `supporter_address1`: dòng 1 địa chỉ supporter (tối đa 40 ký tự)
  - `supporter_address2`: dòng 2 địa chỉ (nếu có)
  - `supporter_suburb`: Suburb/Town nơi supporter sống
  - `supporter_state`: State/Territory (nếu ở Úc: `"NSW"`, `"VIC"`, `"QLD"`, `"SA"`, `"WA"`, `"TAS"`, `"NT"`, `"ACT"`)
  - `supporter_postcode`: postcode
  - **⚠️ Nếu supporter ở Úc** → dùng thông tin từ thư mời / giấy tờ sponsor. Địa chỉ PHẢI bằng tiếng Anh.
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

### 🚫 QUY TẮC CHỐNG BỊA THÔNG TIN (NHẮC LẠI)
- **TUYỆT ĐỐI KHÔNG ĐƯỢC SUY LUẬN hoặc BỊA tên, ngày sinh, số CCCD, số tiền, tên ngân hàng, địa chỉ, hay bất kỳ thông tin nào KHÔNG CÓ TRONG FILE.**
- Nếu phần "Thông tin vợ/chồng" trong form khai trống → để `""` cho tất cả trường liên quan. KHÔNG được đoán từ tên con hay giấy khai sinh.
- Nếu sao kê ngân hàng không rõ số dư → KHÔNG được bịa số dư. Chỉ ghi những gì đọc được rõ ràng trong file.
- Nếu hồ sơ không có thông tin ngày sinh cha/mẹ → để `""`. KHÔNG ĐƯỢC ước đoán.
- **Nguyên tắc vàng: THIẾU TỐT HƠN SAI. Để trống `""` tốt hơn bịa thông tin sai.**
- Sau khi hoàn thành JSON, hãy KIỂM TRA LẠI từng trường: nếu không tìm thấy nguồn gốc thông tin trong file → xóa và để `""`.
