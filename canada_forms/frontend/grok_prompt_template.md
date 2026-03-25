# Grok Prompt Template — IMM5645E Family Information

Copy nội dung bên dưới, paste vào Grok cùng với các file hồ sơ.

---

## PROMPT (Copy từ đây)

Tôi cần bạn đọc các tài liệu tôi gửi và trích xuất thông tin gia đình để điền vào form IMM5645E (Family Information) của Canada visa.

**QUY TẮC QUAN TRỌNG:**
1. CHỈ trích xuất thông tin CÓ trong tài liệu. Nếu không tìm thấy, để null.
2. KHÔNG được đoán hay bịa dữ liệu.
3. Ngày tháng: dạng YYYY-MM-DD. Nếu thiếu ngày → dùng 01. Nếu thiếu tháng → dùng 01.
4. Tình trạng hôn nhân: "Single", "Married", "Common-Law", "Divorced", "Separated", "Widowed", "Annulled". KHÔNG dùng "Unknown".
5. Tên quốc gia/thành phố bằng tiếng Anh. VD: "Viet Nam", "Ho Chi Minh City"
6. accompanying = true nếu người đó ĐI CÙNG sang Canada

**⚠️ CẤM TUYỆT ĐỐI:**
- KHÔNG dùng "same as applicant" — phải ghi ĐỊA CHỈ ĐẦY ĐỦ cho mỗi người, kể cả giống nhau
- KHÔNG dùng "N/A" — nếu là học sinh/sinh viên thì ghi "Student", nếu chưa đi làm thì ghi "None", nếu là trẻ em thì ghi "Minor"
- KHÔNG dùng "Unknown" — nếu không biết thì để null
- KHÔNG viết tắt địa chỉ — phải ghi đầy đủ số nhà, phường/xã, quận/huyện, tỉnh/thành phố, quốc gia

**Trả về JSON đúng format sau (KHÔNG kèm text nào ngoài JSON):**

```json
{
  "application_type": "visitor",

  "applicant": {
    "name": "NGUYEN VAN A",
    "dob": "1990-01-15",
    "country_of_birth": "Viet Nam",
    "address": "123 Nguyen Hue Street, Ben Nghe Ward, District 1, Ho Chi Minh City, Viet Nam",
    "occupation": "Software Engineer",
    "marital_status": "Married"
  },

  "spouse": {
    "name": "TRAN THI B",
    "dob": "1992-03-20",
    "country_of_birth": "Viet Nam",
    "address": "123 Nguyen Hue Street, Ben Nghe Ward, District 1, Ho Chi Minh City, Viet Nam",
    "occupation": "Teacher",
    "marital_status": "Married",
    "accompanying": true
  },

  "mother": {
    "name": "LE THI C",
    "dob": "1965-05-10",
    "country_of_birth": "Viet Nam",
    "address": "45 Tran Phu Street, Ward 5, Vung Tau City, Ba Ria - Vung Tau Province, Viet Nam",
    "occupation": "Retired",
    "marital_status": "Married",
    "accompanying": false
  },

  "father": {
    "name": "NGUYEN VAN D",
    "dob": "1960-08-22",
    "country_of_birth": "Viet Nam",
    "address": "45 Tran Phu Street, Ward 5, Vung Tau City, Ba Ria - Vung Tau Province, Viet Nam",
    "occupation": "Retired",
    "marital_status": "Married",
    "accompanying": false
  },

  "children": [
    {
      "name": "NGUYEN VAN E",
      "relationship": "Son",
      "dob": "2020-01-01",
      "country_of_birth": "Viet Nam",
      "address": "123 Nguyen Hue Street, Ben Nghe Ward, District 1, Ho Chi Minh City, Viet Nam",
      "occupation": "Student",
      "marital_status": "Single",
      "accompanying": true
    }
  ],

  "siblings": [
    {
      "name": "NGUYEN VAN F",
      "relationship": "Brother",
      "dob": "1988-06-15",
      "country_of_birth": "Viet Nam",
      "address": "78 Le Loi Street, Ward 1, District 5, Ho Chi Minh City, Viet Nam",
      "occupation": "Business Owner",
      "marital_status": "Married",
      "accompanying": false
    }
  ]
}
```

**LƯU Ý:**
- children: tối đa 4 người (giới hạn của form)
- siblings: tối đa 7 người (giới hạn của form)
- Nếu không có spouse/mother/father, để toàn bộ fields = null
- Nếu không có children/siblings, để mảng rỗng []
- MỖI NGƯỜI phải có ĐỊA CHỈ ĐẦY ĐỦ riêng, KHÔNG được viết "same as applicant"
- Nghề nghiệp của trẻ em/học sinh: ghi "Student", KHÔNG ghi "N/A"
