# Grok Prompt Template — IMM5257E Visitor Visa Application

Copy nội dung bên dưới, paste vào Grok cùng với các file hồ sơ.

---

## PROMPT (Copy từ đây)

Tôi cần bạn đọc các tài liệu tôi gửi và trích xuất thông tin để điền vào form IMM5257E (Application for Visitor Visa - Temporary Resident Visa) của Canada.

**QUY TẮC QUAN TRỌNG:**
1. CHỈ trích xuất thông tin CÓ trong tài liệu. Nếu không tìm thấy, để null.
2. KHÔNG được đoán hay bịa dữ liệu.
3. Ngày tháng: dạng YYYY-MM-DD.
4. Tên/họ/địa chỉ: viết TIẾNG ANH, IN HOA.
5. Mã quốc gia dùng **XFA lic code** (mã nội bộ của IRCC, KHÔNG phải ISO): 270=Vietnam, 511=Canada, 461=USA, 267=Thailand, 305=Australia, 207=Japan, 258=South Korea, 202=China, 022=France, 024=Germany, 003=United Kingdom, 246=Singapore, 242=Malaysia, 227=Philippines, 205=India, 203=Taiwan, 222=Indonesia, 256=Cambodia, 260=Laos
6. Tình trạng hôn nhân dùng code: 01=Married, 02=Single, 03=Common-law, 04=Divorced, 05=Separated, 06=Widowed, 07=Annulled

**⚠️ CẤM TUYỆT ĐỐI:**
- KHÔNG dùng "N/A" — để null nếu không có
- KHÔNG viết tắt địa chỉ — ghi đầy đủ
- KHÔNG thêm thông tin bạn không tìm thấy trong tài liệu
- KHÔNG dùng mã ISO-3166 (764, 704...) — chỉ dùng XFA lic code (267, 270...)

**⚠️ QUY TẮC NGÀY THÁNG & SUY LUẬN HỢP LÝ:**
- **Ngày kết hôn**: PHẢI trích xuất từ tài liệu. Nếu tài liệu chỉ có năm (VD: 2005), dùng "2005-01-01". Nếu có tháng nhưng không có ngày, dùng ngày 01. KHÔNG để trống khi marital_status là "01" (Married).
- **Tháng tốt nghiệp education**: Nếu chỉ có năm tốt nghiệp mà KHÔNG có tháng, hãy suy luận hợp lý:
  - Đại học/Master/PhD → tháng 06 (June graduation)
  - Cao đẳng/nghề → tháng 06
  - Nếu có thông tin cụ thể hơn, dùng thông tin đó
- **Tháng bắt đầu education**: Nếu chỉ có năm, suy luận:
  - Đại học → tháng 09 (September intake)
  - Nếu có thông tin cụ thể hơn, dùng thông tin đó

**⚠️ QUY TẮC EMPLOYMENT — KHAI 10 NĂM GẦN NHẤT:**
- Form IMM5257 yêu cầu khai TẤT CẢ công việc trong 10 năm gần nhất
- `current_occupation`: Công việc HIỆN TẠI (to_year và to_month để trống nếu đang làm)
- `occupation_1`: Công việc trước đó (gần nhất)
- `occupation_2`: Công việc trước nữa
- Nếu tài liệu liệt kê >3 công việc, chọn 3 công việc GẦN NHẤT
- Mỗi occupation cần: from_year, from_month, to_year, to_month, title, employer, city, country, province
- Nếu chỉ có năm (VD: 2021-2023), dùng from_month="01" to_month="12"

**⚠️ QUY TẮC ĐỊA ĐIỂM ĐẾN (DETAILS OF VISIT):**
- Nếu tài liệu có lịch trình/booking khách sạn, trích xuất thông tin khách sạn ĐẦU TIÊN:
  - `contact1_name`: Tên khách sạn
  - `contact1_relationship`: "Hotel" hoặc "Accommodation"
  - `contact1_address`: Địa chỉ khách sạn đầy đủ (street, city, province, postal code)
- Nếu có tour group hoặc người bảo lãnh, điền thông tin tương ứng
- `funds`: Ước tính số tiền mang theo (CAD). Nếu không có, để trống.

**Trả về JSON đúng format sau (KHÔNG kèm text nào ngoài JSON):**

```json
{
  "visa_type": "VisitorVisa",
  "service_in": "01",

  "family_name": "DINH",
  "given_name": "THI LAN ANH",
  "has_alias": "N",
  "alias_family_name": "",
  "alias_given_name": "",
  "sex": "Female",
  "dob": "1977-10-19",
  "birth_city": "HA TINH",
  "birth_country": "270",
  "citizenship": "270",

  "cor_country": "270",
  "cor_status": "01",
  "cor_from": "",
  "cor_to": "",
  "has_prev_cor": "N",
  "same_as_cor": "Y",

  "marital_status": "01",
  "date_of_marriage": "2023-04-21",
  "spouse_family_name": "NGUYEN",
  "spouse_given_name": "THANH BANG",
  "prev_married": "N",
  "pm_family_name": "",
  "pm_given_name": "",
  "pm_dob": "",
  "pm_relationship": "",
  "pm_from": "",
  "pm_to": "",

  "passport_number": "E01370203",
  "passport_country": "270",
  "passport_issue_date": "2024-02-02",
  "passport_expiry_date": "2034-02-02",

  "native_language": "Vietnamese",
  "can_communicate": "Neither",
  "has_language_test": "N",

  "has_national_id": "Y",
  "national_id_number": "042177004939",
  "national_id_country": "270",
  "national_id_issue": "2022-06-28",
  "national_id_expiry": "2037-10-19",
  "has_us_card": "N",
  "us_card_number": "",
  "us_card_expiry": "",

  "address_pobox": "",
  "address_apt": "39",
  "address_street_num": "",
  "address_street_name": "NGUYEN THI MINH KHAI 1",
  "address_city": "BAC GIANG CITY",
  "address_country": "270",
  "address_province": "",
  "address_postal_code": "",
  "address_district": "",
  "same_mailing_address": "Y",

  "phone_type": "02",
  "phone_number": "+84372226878",
  "alt_phone": "",
  "alt_phone_type": "",
  "email": "",

  "purpose": "02",
  "purpose_other": "",
  "travel_from": "2026-06-10",
  "travel_to": "2026-06-18",
  "funds": "7000",

  "contact1_name": "Hilton Toronto Downtown",
  "contact1_relationship": "Hotel",
  "contact1_address": "145 Richmond Street West, Toronto, Ontario M5H 2L2",
  "contact2_name": "",
  "contact2_relationship": "",
  "contact2_address": "",

  "has_education": "Y",
  "education": {
    "from_year": "2008", "from_month": "09",
    "to_year": "2010", "to_month": "06",
    "field": "BUSINESS ADMINISTRATION",
    "school": "ASIAN INSTITUTE OF TECHNOLOGY",
    "city": "BANGKOK",
    "country": "267",
    "province": ""
  },

  "current_occupation": {
    "from_year": "2024", "from_month": "06",
    "to_year": "", "to_month": "",
    "title": "DEPUTY DIRECTOR",
    "employer": "LPBANK INSURANCE COMPANY VUNG TAU BRANCH",
    "city": "VUNG TAU",
    "country": "270",
    "province": "BA RIA VUNG TAU"
  },
  "occupation_1": {
    "from_year": "2023", "from_month": "01",
    "to_year": "2024", "to_month": "05",
    "title": "DEPUTY DIRECTOR",
    "employer": "MIC INSURANCE VUNG TAU BRANCH",
    "city": "VUNG TAU",
    "country": "270",
    "province": "BA RIA VUNG TAU"
  },
  "occupation_2": {
    "from_year": "2021", "from_month": "01",
    "to_year": "2023", "to_month": "12",
    "title": "DEPUTY DIRECTOR",
    "employer": "HUNG VUONG INSURANCE BA RIA VUNG TAU",
    "city": "VUNG TAU",
    "country": "270",
    "province": "BA RIA VUNG TAU"
  },

  "bg_medical": "N",
  "bg_medical_b": "N",
  "bg_medical_details": "",
  "bg_overstayed": "N",
  "bg_refused_visa": "N",
  "bg_refused_details": "",
  "bg_applied_before": "N",
  "bg_crime": "N",
  "bg_crime_details": "",
  "bg_military": "N",
  "bg_military_details": "",
  "bg_political": "N",
  "bg_witnessed": "N"
}
```

**LƯU Ý QUAN TRỌNG:**
- visa_type: "VisitorVisa" (du lịch), "StudyPermit" (du học), "WorkPermit" (lao động)
- service_in: "01" = English, "02" = French
- purpose codes: 01=Business, 02=Tourism, 03=Short-Term Studies, 04=Returning Student, 05=Returning Worker, 06=Super Visa, 07=Other, 08=Family Visit, 13=Visit
- phone_type: 01=Residence, 02=Cellular, 03=Business
- can_communicate: "English", "French", "Both", "Neither"
- sex: "Male" hoặc "Female"
- cor_status: "01"=Citizen, "02"=Permanent Resident, "03"=Visitor, "04"=Worker, "05"=Student, "06"=Other, "07"=Protected Person, "08"=Refugee Claimant
- same_as_cor: "Y" nếu quốc gia nộp đơn = quốc gia cư trú, "N" nếu khác
- has_language_test: "Y" nếu có chứng chỉ ngôn ngữ (IELTS, TEF...), "N" nếu không
- prev_married: "N" mặc định. Nếu "Y" thì PHẢI điền pm_family_name, pm_given_name, pm_dob, pm_relationship, pm_from, pm_to
- **MÃ QUỐC GIA XFA lic** (QUAN TRỌNG — KHÔNG DÙNG ISO):
  270=Vietnam, 511=Canada, 461=USA, 267=Thailand, 305=Australia,
  207=Japan, 258=South Korea, 202=China, 022=France, 024=Germany,
  003=United Kingdom, 246=Singapore, 242=Malaysia, 227=Philippines,
  205=India, 203=Taiwan, 028=Italy, 025=Greece, 045=Turkey,
  026=Hungary, 501=Mexico, 222=Indonesia, 256=Cambodia, 260=Laos,
  241=Myanmar/Burma, 037=Spain, 709=Brazil, 339=New Zealand
- **OCCUPATION**: PHẢI khai TẤT CẢ công việc 10 năm gần nhất. Tối đa 3 dòng (current + occupation_1 + occupation_2). Chọn 3 mới nhất nếu >3 công việc.
- **EDUCATION tháng**: NẾU chỉ có năm, infer from_month="09", to_month="06"
- **MARRIAGE**: NẾU marital_status="01" thì date_of_marriage PHẢI có giá trị
- **CONTACT/HOTEL**: Lấy từ lịch trình/booking khách sạn nếu có
- Background questions (page 4):
  - bg_medical: Q1a) Bao giờ bị lao phổi/tiếp xúc gần?
  - bg_medical_b: Q1b) Có rối loạn thể chất/tinh thần?
  - bg_medical_details: Q1c) Chi tiết nếu 1a hoặc 1b = "Y"
  - bg_overstayed: Q2a) Đã ở quá hạn/làm việc không phép?
  - bg_refused_visa: Q2b) Từng bị từ chối visa/nhập cảnh?
  - bg_refused_details: Chi tiết refusal nếu 2b = "Y" (quốc gia, năm, lý do)
  - bg_applied_before: Q2c) Đã nộp đơn vào Canada trước đây?
  - bg_crime: Q3) Từng bị bắt/kết án tội phạm?
  - bg_crime_details: Chi tiết nếu Q3 = "Y"
  - bg_military: Q4) Từng phục vụ quân đội/dân quân?
  - bg_military_details: Chi tiết nếu Q4 = "Y"
  - bg_political: Q5) Liên kết tổ chức chính trị/bạo lực?
  - bg_witnessed: Q6) Từng chứng kiến/tham gia ngược đãi tù nhân?
  - Mặc định ALL "N". CHỈ đặt "Y" nếu tài liệu cho thấy có
- Nếu không có education, để has_education = "N" và education = object rỗng
