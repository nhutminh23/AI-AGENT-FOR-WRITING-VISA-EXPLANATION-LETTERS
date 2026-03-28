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
5. Mã quốc gia dùng code ISO-3166 numeric: 270=Vietnam, 306=Canada, 400=USA
6. Tình trạng hôn nhân dùng code: 01=Married, 02=Single, 03=Common-law, 04=Divorced, 05=Separated, 06=Widowed, 07=Annulled

**⚠️ CẤM TUYỆT ĐỐI:**
- KHÔNG dùng "N/A" — để null nếu không có
- KHÔNG viết tắt địa chỉ — ghi đầy đủ
- KHÔNG thêm thông tin bạn không tìm thấy trong tài liệu

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
  "purpose_other": "TOURISM",
  "travel_from": "2026-06-10",
  "travel_to": "2026-06-18",
  "funds": "7000",

  "contact1_name": "World Cup Tour Group",
  "contact1_relationship": "Tour Participant",
  "contact1_address": "Toronto, Ontario, Canada",
  "contact2_name": "",
  "contact2_relationship": "",
  "contact2_address": "",

  "has_education": "N",
  "education": {
    "from_year": "", "from_month": "",
    "to_year": "", "to_month": "",
    "field": "", "school": "", "city": "", "country": "", "province": ""
  },

  "current_occupation": {
    "from_year": "2024", "from_month": "8",
    "to_year": "2026", "to_month": "3",
    "title": "MANAGER",
    "employer": "LAN ANH BGG HOUSEHOLD BUSINESS",
    "city": "BAC GIANG",
    "country": "270",
    "province": ""
  },
  "occupation_1": null,
  "occupation_2": null,

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
- Nếu có nhiều hơn 1 công việc, điền vào occupation_1, occupation_2 (cùng format với current_occupation)
- Background questions (page 4):
  - bg_medical: Q1a) Bao giờ bị lao phổi/tiếp xúc gần?
  - bg_medical_b: Q1b) Có rối loạn thể chất/tinh thần?
  - bg_medical_details: Q1c) Chi tiết nếu 1a hoặc 1b = "Y"
  - bg_overstayed: Q2a) Đã ở quá hạn/làm việc không phép?
  - bg_refused_entry: Q2b) Từng bị từ chối visa/nhập cảnh?
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

