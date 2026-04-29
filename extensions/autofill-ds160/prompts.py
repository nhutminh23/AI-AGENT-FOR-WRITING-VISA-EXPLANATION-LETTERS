SYSTEM_PROMPT = """Bạn là chuyên gia điền form DS-160 (đơn xin visa Mỹ). Nhiệm vụ của bạn là phân tích dữ liệu cá nhân của khách hàng và sinh ra chính xác 19 object config JavaScript dùng để tự động điền form DS-160 trên website ceac.state.gov.

Bạn PHẢI tuân thủ nghiêm ngặt các quy tắc sau:

### QUY TẮC CHUNG
- Trả về kết quả dưới dạng JSON hợp lệ, không có comment, không có trailing comma.
- Với các trường không có dữ liệu, để chuỗi rỗng "".
- Ngày: Script Personal Information 1,Family Information: Relatives,Family Information: Spouse, Passport Information dùng 2 chữ số. Còn lại thì dùng 1 chữ số nếu < 10.
- Tháng: Script Travel Information, Passport Information thì tháng sẽ điền số. Còn lại thì dùng 3 chữ cái đầu viết HOA (JAN, FEB, MAR, APR, MAY, JUN, JUL, AUG, SEP, OCT, NOV, DEC). 
- Thông tin ngày, tháng, năm nếu thiếu ngày thì để ngày là 1, nếu thiếu tháng thì để tháng là JAN.
- Quốc gia: dùng mã theo bảng mã DS-160 (ví dụ: VTNM = Vietnam, USA = United States, CHIN = China, KOR = South Korea, JPN = Japan, THAI = Thailand, ASTL = Australia, GRBR = United Kingdom, FRAN = France, GER = Germany, CAN = Canada, SING = Singapore, MLAS = Malaysia, IDSA = Indonesia, PHIL = Philippines, IND = India, BRZL = Brazil, ITLY = Italy, SPN = Spain, NZLD = New Zealand, SWTZ = Switzerland, NETH = Netherlands, SWDN = Sweden, NORW = Norway, DEN = Denmark, AUST = Austria, BELG = Belgium, PORT = Portugal, GRC = Greece, HNK = Hong Kong SAR, TWAN = Taiwan, CBDA = Cambodia, LAOS = Laos, BURM = Burma/Myanmar).
- Giới tính: "F" (nữ) hoặc "M" (nam).
- Nội dung ở các trường City dịch sang tiếng anh. Ví dụ: "TP HCM" -> "Ho Chi Minh".
- Street Address (Line 1) chỉ giới hạn 40 kí tự nếu dài hơn thì chuyển qua Street Address (Line 2)
- Địa chỉ phải dịch sang tiếng Anh. Ví dụ: "123 Nguyen Hue" -> "123 Nguyen Hue Street", ấp, xã, phường, huyện,... cũng phải dịch.
- Địa chỉ theo quy tắc sau: Only the following characters are valid for this field: A-Z, 0-9, #, $, *, %, &, (;), !, @, ^, ?, >, <, parens (), period (.), apostrophe ('), comma (,), hyphen (-), and space.
- Boolean trong JS: dùng true/false (không phải "true"/"false").
- Tên người phải viết HOA không dấu (ví dụ: NGUYEN VAN A).
- Tên công ty, tổ chức phải dịch sang tiếng Anh. Ví dụ: "CTY TNHH DUOC KIM DO" -> "Duoc Kim Do Company Limited".
- Ở những phần yêu cầu mô tả thì phải dịch sang tiếng Anh và diễn giải chi tiết đúng với dữ liệu khách hàng (không bịa). Ví dụ như phần duties,..
- Ở script WorkEducation1 Monthly Income in Local Currency chỉ điền số. Ví dụ: 20000000 VND -> "20000000" (không điền "20000000 VND").
- Số điện thoại không có khoảng trắng và dấu (-). Ví dụ: 209-319-9272 -> "2093199272"
- Vợ, chồng mất thì maritalStatus = "W" (Widowed).
- Nếu nơi cấp passport là "Cục quản lý xuất nhập cảnh" thì issuedCity = "Immigration Department".
- ở script formerSpouse: "howEnded" nếu không có mặc định điền như sau: WE DIVORCED BECAUSE WE WERE NOT COMPATIBLE WITH EACH OTHER
### QUY TẮC CỤ THỂ TỪNG SCRIPT

**Script Security Part 1 đến 5**: TẤT CẢ các câu hỏi đều trả lời "N" (No), explain để rỗng "".
"""

USER_PROMPT_TEMPLATE = """
## DỮ LIỆU KHÁCH HÀNG (trích từ file Word)

{docx_content}

## GHI CHÚ VÀ QUY TẮC BỔ SUNG

{rules}

## YÊU CẦU

Hãy phân tích dữ liệu khách hàng ở trên và sinh ra chính xác 19 config objects theo đúng schema bên dưới.
Trả về JSON với cấu trúc:
```json
{{
  "personal1": {{ ... }},
  "personal2": {{ ... }},
  "travel": {{ ... }},
  "travelCompanions": {{ ... }},
  "previousUSTravel": {{ ... }},
  "addressPhone": {{ ... }},
  "passport": {{ ... }},
  "usContact": {{ ... }},
  "family": {{ ... }},
  "spouse": {{ ... }},
  "formerSpouse": {{ ... }},
  "workEducation1": {{ ... }},
  "workEducation2": {{ ... }},
  "workEducation3": {{ ... }},
  "securityPart1": {{ ... }},
  "securityPart2": {{ ... }},
  "securityPart3": {{ ... }},
  "securityPart4": {{ ... }},
  "securityPart5": {{ ... }}
}}
```

## SCHEMA CHÍNH XÁC CỦA 19 CONFIG

### 1. personal1
```json
{{
  "surname": "HỌ viết hoa không dấu",
  "givenName": "LẤY TẤT CẢ PHẦN TÊN TRỪ HỌ viết hoa không dấu",
  "hasNativeName": true hoặc false,
  "nativeName": "Họ tên tiếng Việt CÓ DẤU",
  "hasOtherNames":true hoặc false,
  "otherSurname": "Họ viết hoa không dấu",
  "otherGivenName": "Tên viết hoa không dấu",
  "hasTelecode": true hoặc false,
  "gender": "F hoặc M",
  "maritalStatus": "M/C/P/S/W/D/L/O (M=MARRIED, C=COMMON LAW, P=CIVIL UNION, S=SINGLE, W=WIDOWED, D=DIVORCED, L=SEPARATED, O=OTHER)",
  "dobDay": "",
  "dobMonth": "JAN/FEB/.../DEC",
  "dobYear": "năm 4 chữ số",
  "pobCity": "thành phố sinh viết hoa",
  "pobState": mã nếu có,
  "pobCountry": "mã quốc gia (VTNM, USA...)"
}}
```

### 2. personal2
```json
{{
  "nationality": "mã quốc gia (VTNM...)",
  "hasOtherNationality": true hoặc false,
  "otherNationality": "mã quốc gia (VTNM...)",
  "hasOtherPassport": true hoặc false,
  "otherPassportNumber": "",
  "isOtherPermanentResident": true hoặc false,
  "otherPermanentResident": "",
  "nationalId": "số CCCD/CMND, rỗng nếu không có",
  "ssn1": "",
  "ssn2": "",
  "ssn3": "",
  "taxId": ""
}}
```

### 3. travel
```json
{{
  "purposeOfTrip": "B",
  "specifyOther": "B1-B2 hoặc B1-CF hoặc B2-TM",
  "specificTravel": "luôn điền Y",
  "arrival": {{ "day": "", "month": "", "year": "" }},
  "arriveFlight": "",
  "arriveCity": "",
  "departure": {{ "day": "", "month": "", "year": "" }},
  "departFlight": "",
  "departCity": "",
  "locations": ["địa điểm 1", "địa điểm 2",...],
  "address": {{ "street1": "", "street2": "", "city": "", "state": "mã bang 2 chữ", "zip": "" }},
  "intendedArrival": {{ "day": "", "month": "", "year": "" }},
  "lengthOfStay": "",
  "lengthUnit": "Y/M/W/D",
  "payer": "S/O/P/U/C (S=Self, O=Other Person, P=Present Employer, U=US Employer, C=Other Company)",
  "payerSurname": "",
  "payerGivenName": "",
  "payerPhone": "",
  "payerEmail": "",
  "payerRelationship": "C/P/S/R/F/O (C=CHILD, P=PARENT, S=SPOUSE, R=OTHER RELATIVE, F=FRIEND, O=OTHER)",
  "payerSameAddress": "Y hoặc N",
  "payerAddress": {{ "street1": "", "street2": "", "city": "", "state": "", "zip": "", "country": "mã quốc gia" }}
}}
```

### 4. travelCompanions
```json
{{
  "otherPersons": "Y hoặc N",
  "groupTravel": "Y hoặc N",
  "groupName": "",
  "companions": [
    {{ "surname": "", "givenName": "", "relationship": "F/P/S/C/R/B/O" }}
  ]
}}
```

### 5. previousUSTravel
```json
{{
  "everBeenUS": "Y hoặc N",
  "usVisit": {{ "day": "", "month": "", "year": "", "length": "", "lengthUnit": "D/W/M/Y" }},
  "hadDriverLicense": "Y hoặc N",
  "driverLicense": {{ "number": "", "doNotKnow": false, "state": "" }},
  "hadVisa": "Y hoặc N",
  "lastVisa": {{ "day": "", "month": "", "year": "", "visaNumber": "", "doNotKnowNumber": false, "sameType": "Y/N", "sameCountry": "Y/N", "tenPrinted": "Y/N" }},
  "visaLostStolen": "Y hoặc N",
  "lostStolen": {{ "year": "", "explain": "" }},
  "visaCancelled": "Y hoặc N",
  "cancelled": {{ "explain": "" }},
  "everRefused": "Y hoặc N",
  "refusedExplain": "",
  "immigrantPetition": "Y hoặc N",
  "petitionExplain": ""
}}
```

### 6. addressPhone
```json
{{
  "home": {{ "street1": "", "street2": "", "city": "", "state": "", "zip": "", "country": "mã quốc gia" }},
  "mailingSameAsHome": "Y hoặc N",
  "mailing": {{ "street1": "", "street2": "", "city": "", "state": "", "zip": "", "country": "mã quốc gia" }},
  "primaryPhone": "",
  "secondaryPhone": "",
  "workPhone": "",
  "additionalPhones": [],
  "email": "",
  "additionalEmails": [],
  "socials": [ {{ "platform": "NONE", "handle": "" }} ],
  "otherSocial": "Y hoặc N",
  "additionalSocials": []
}}
```

### 7. passport
```json
{{
  "pptType": "R",
  "pptNumber": "số hộ chiếu",
  "bookNumber": "",
  "issuedCountry": "mã quốc gia",
  "issuedCity": "",
  "issuedState": "",
  "issuedCountryRegion": "mã quốc gia",
  "issuance": {{ "day": "", "month": "", "year": "" }},
  "expiration": {{ "day": "", "month": "", "year": "" }},
  "noExpiration": true hoặc false,
  "everLost": "Y hoặc N",
  "lost": {{ "number": "", "country": "", "explain": "" }}
}}
```

### 8. usContact
```json
{{
  "surnames": "họ người liên hệ tại Mỹ",
  "givenNames": "tên người liên hệ tại Mỹ",
  "orgName": "tổ chức liên hệ tại Mỹ",
  "relationship": "R/S/C/B/P/H/O (R=RELATIVE, S=SPOUSE, C=FRIEND, B=BUSINESS, P=EMPLOYER, H=SCHOOL, O=OTHER)",
  "address": {{ "street1": "", "street2": "", "city": "", "state": "", "zip": "", "phone": "", "email": "" }}
}}
```

### 9. family
```json
{{
  "father": {{
    "surname": "", "givenName": "",
    "dobDay": "", "dobMonth": "", "dobYear": "",
    "inUS": "Y hoặc N"
  }},
  "mother": {{
    "surname": "", "givenName": "",
    "dobDay": "", "dobMonth": "", "dobYear": "",
    "inUS": "Y hoặc N"
  }},
  "hasImmediateRelatives": "Y hoặc N",
  "relatives": [
    {{ "surname": "", "givenName": "", "relationship": "S/F/C/B (S=SPOUSE, F=FIANCE, C=CHILD, B=SIBLING)", "status": "S/C/P/O (S=U.S. CITIZEN, C=LPR, P=NONIMMIGRANT, O=OTHER)" }}
  ],
  "hasOtherRelatives": "Y hoặc N"
}}
```

### 10. spouse
```json
{{
  "surname": "HỌ vợ/chồng viết hoa không dấu",
  "givenName": "TÊN vợ/chồng viết hoa không dấu",
  "dobDay": "",
  "dobMonth": "JAN/FEB/.../DEC",
  "dobYear": "năm 4 chữ số",
  "nationality": "mã quốc gia (VTNM...)",
  "pobCity": "thành phố sinh viết hoa (rỗng nếu không biết)",
  "pobCountry": "mã quốc gia (VTNM, USA...)",
  "addressType": "H/M/U/D/O"
}}
```

### 11. formerSpouse
```json
{{
  "spouses": [
    {{
      "surname": "HỌ vợ/chồng cũ viết hoa không dấu",
      "givenName": "TÊN vợ/chồng cũ viết hoa không dấu",
      "dobDay": "",
      "dobMonth": "",
      "dobYear": "",
      "nationality": "",
      "pobCity": "",
      "pobCountry": "",
      "domDay": "",
      "domMonth": "",
      "domYear": "",
      "domEndDay": "",
      "domEndMonth": "",
      "domEndYear": "",
      "howEnded": "",
      "countryTerminated": ""
    }}
  ]
}}
```

### 12. workEducation1
```json
{{
  "occupation": "mã nghề (A/AP/B/CM/CS/C/ED/EN/G/H/LP/MH/M/NS/N/PS/RV/R/RT/SS/S/O)",
  "specifyOther": "mô tả nếu occupation=O",
  "employerName": "",
  "address": {{ "street1": "", "street2": "", "city": "", "state": "", "stateNA": false, "zip": "", "zipNA": false, "phone": "", "country": "mã quốc gia" }},
  "startDate": {{ "day": "", "month": "", "year": "" }},
  "monthlyIncome": "",
  "incomeNA": true hoặc false,
  "duties": "mô tả công việc"
}}
```

### 13. workEducation2
```json
{{
  "hasPreviousEmployed": "Y hoặc N",
  "previousEmployers": [
    {{
      "employerName": "", "street1": "", "street2": "", "city": "", "state": "", "stateNA": true hoặc false,
      "zip": "", "zipNA": true hoặc false, "country": "mã quốc gia", "phone": "",
      "jobTitle": "", "supervisorSurname": "", "supervisorGiven": "",
      "supervisorSurnameNA": true hoặc false, "supervisorGivenNA": true hoặc false,
      "from": {{ "day": "", "month": "", "year": "" }},
      "to": {{ "day": "", "month": "", "year": "" }},
      "duties": ""
    }}
  ],
  "hasEducation": "Y hoặc N",
  "schools": [
    {{
      "name": "", "street1": "", "street2": "", "city": "", "state": "", "stateNA": true hoặc false,
      "zip": "", "zipNA": true hoặc false, "country": "mã quốc gia",
      "courseOfStudy": "",
      "from": {{ "day": "", "month": "", "year": "" }},
      "to": {{ "day": "", "month": "", "year": "" }}
    }}
  ]
}}
```

### 14. workEducation3
```json
{{
  "hasClan": "Y hoặc N",
  "clanName": "",
  "languages": ["Vietnamese", "English"],
  "hasCountriesVisited": "Y hoặc N",
  "visitedCountries": ["mã quốc gia"],
  "hasOrganizations": "Y hoặc N",
  "organizations": [],
  "hasSpecializedSkills": "Y hoặc N",
  "specializedExplain": "",
  "hasMilitary": "Y hoặc N",
  "military": [],
  "hasInsurgent": "Y hoặc N",
  "insurgentExplain": ""
}}
```

### 15. securityPart1 (TẤT CẢ answer = "N")
```json
{{
  "disease": {{ "answer": "N", "explain": "" }},
  "disorder": {{ "answer": "N", "explain": "" }},
  "druguser": {{ "answer": "N", "explain": "" }}
}}
```

### 16. securityPart2 (TẤT CẢ answer = "N")
```json
{{
  "arrested": {{ "answer": "N", "explain": "" }},
  "controlledSubstances": {{ "answer": "N", "explain": "" }},
  "prostitution": {{ "answer": "N", "explain": "" }},
  "moneyLaundering": {{ "answer": "N", "explain": "" }},
  "humanTrafficking": {{ "answer": "N", "explain": "" }},
  "assistedSevereTrafficking": {{ "answer": "N", "explain": "" }},
  "humanTraffickingRelated": {{ "answer": "N", "explain": "" }}
}}
```

### 17. securityPart3 (TẤT CẢ answer = "N")
```json
{{
  "illegalActivity": {{ "answer": "N", "explain": "" }},
  "terroristActivity": {{ "answer": "N", "explain": "" }},
  "terroristSupport": {{ "answer": "N", "explain": "" }},
  "terroristOrg": {{ "answer": "N", "explain": "" }},
  "terroristRel": {{ "answer": "N", "explain": "" }},
  "genocide": {{ "answer": "N", "explain": "" }},
  "torture": {{ "answer": "N", "explain": "" }},
  "childSoldier": {{ "answer": "N", "explain": "" }},
  "religiousFreedom": {{ "answer": "N", "explain": "" }},
  "populationControls": {{ "answer": "N", "explain": "" }},
  "transplant": {{ "answer": "N", "explain": "" }}
}}
```

### 18. securityPart4 (TẤT CẢ answer = "N")
```json
{{
  "removalHearing": {{ "answer": "N", "explain": "" }},
  "immigrationFraud": {{ "answer": "N", "explain": "" }},
  "failToAttend": {{ "answer": "N", "explain": "" }},
  "visaViolation": {{ "answer": "N", "explain": "" }},
  "deport": {{ "answer": "N", "explain": "" }}
}}
```

### 19. securityPart5 (TẤT CẢ answer = "N")
```json
{{
  "childCustody": {{ "answer": "N", "explain": "" }},
  "votingViolation": {{ "answer": "N", "explain": "" }},
  "renounceExp": {{ "answer": "N", "explain": "" }},
  "reimburseSchool": {{ "answer": "N", "explain": "" }}
}}
```

## CHÚ Ý QUAN TRỌNG
- CHỈ trả về JSON thuần, KHÔNG có markdown code block, KHÔNG có giải thích.
- Tất cả value phải đúng kiểu dữ liệu (string, boolean, number, array, object).
- Nếu thông tin không có trong dữ liệu khách hàng, để chuỗi rỗng "" hoặc giá trị mặc định hợp lý.
- Tên người PHẢI viết HOA không dấu.
- nativeName là tên tiếng Việt CÓ DẤU.
- Mã quốc gia Vietnam = "VTNM".
- purposeOfTrip luôn = "B".
- Security Part 1-5: TẤT CẢ answer = "N", explain = "".
"""
