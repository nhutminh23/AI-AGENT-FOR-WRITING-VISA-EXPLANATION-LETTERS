# Multi-agent LangGraph viết thư giải trình VISA

Hệ thống multi-agent đọc nhiều loại hồ sơ và viết thư giải trình song ngữ (VI/EN) theo chuẩn hồ sơ VISA. Bao gồm AI tự tạo booking khách sạn + vé máy bay.

---

## ⚡ Cài đặt nhanh

**Yêu cầu**: Python 3.10+ ([tải tại đây](https://www.python.org/downloads/)) — nhớ tích ✅ "Add Python to PATH" khi cài.

```powershell
# Bước 1: Clone repo
git clone <url-repo>
cd AI-AGENT-FOR-WRITING-VISA-EXPLANATION-LETTERS

# Bước 2: Tạo môi trường ảo & cài thư viện
python -m venv myenv
myenv\Scripts\activate
pip install -r requirements.txt

# Bước 3: Tạo file .env
copy .env.example .env
# Mở .env và điền OPENAI_API_KEY

# Bước 4: Chạy server
python server.py
```

Mở trình duyệt: **http://127.0.0.1:8000**

---

## 🔑 Biến môi trường (.env)

| Biến                  | Mô tả                                   | Bắt buộc |
| --------------------- | ---------------------------------------- | -------- |
| `OPENAI_API_KEY`      | API key của OpenAI                       | ✅       |
| `OPENAI_MODEL`        | Model text (mặc định: `gpt-5-mini`)     | ❌       |
| `OPENAI_VISION_MODEL` | Model vision (mặc định: `gpt-4o-mini`)  | ❌       |
| `GEMINI_API_KEY`      | API key Google Gemini (tùy chọn)        | ❌       |
| `SERPAPI_KEY`         | API key SerpAPI cho booking chuyến bay   | ❌       |

---

## 📂 Cấu trúc dự án

```
├── server.py              ← Entry point (25 dòng)
├── config.py              ← Cấu hình tập trung (13 dir constants)
├── database.py            ← SQLite database layer
├── requirements.txt       ← Dependencies
│
├── core/                  ← Logic nghiệp vụ
│   ├── agents.py          ← AI agents (extractor, classifier)
│   ├── prompts.py         ← Prompt templates
│   ├── errors.py          ← Error handling
│   └── helpers.py         ← Shared utility functions
│
├── routes/                ← Flask blueprints (92 API endpoints)
│   ├── projects.py        ← CRUD dự án
│   ├── booking.py         ← Booking khách sạn + vé máy bay
│   ├── splitter.py        ← Tách PDF + dịch thuật
│   ├── precheck.py        ← Pre-check hồ sơ
│   └── pipeline.py        ← Pipeline xử lý + phân loại
│
├── classifier/            ← AI phân loại tài liệu
│   └── agent.py
│
├── booking/               ← AI tạo booking
│   ├── generator.py
│   └── ai_agent.py
│
├── pdf_tools/             ← Xử lý PDF (OCR, split, merge)
│   ├── pdf_service.py
│   └── ai_service.py
│
├── frontend/              ← Giao diện web
│   ├── index.html
│   ├── app.js             ← Main app (314 dòng)
│   └── js/                ← 12 feature modules
│       ├── projects.js
│       ├── splitter.js
│       ├── classifier.js
│       ├── steps.js
│       ├── booking.js
│       ├── itinerary.js
│       └── ...
│
├── dich/                  ← Dịch thuật (templates + output)
├── phanloai/              ← Phân loại (input → output)
├── splitter_uploads/      ← File upload cho splitter
├── splitter_outputs/      ← Kết quả split PDF
└── scan_splitter_outputs/ ← Kết quả scan + split
```

---

## 🖥️ Sử dụng

### Tab "Thư giải trình"
Chạy từng bước hoặc "Chạy tất cả" để AI phân tích hồ sơ và viết thư giải trình.

### Tab "Lịch trình"
Tạo lịch trình chi tiết từ booking vé máy bay + khách sạn.

### Tab "Booking"
- **🤖 AI Tạo Booking**: AI tự đọc hồ sơ → chọn khách sạn & chuyến bay THẬT
- **📄 Xuất PDF**: Xuất booking ra PDF để gửi lãnh sự quán
- **⚙️ Chỉnh sửa thủ công**: Tạo booking bằng database có sẵn

### Tab "Tách PDF" (Splitter)
- Upload file scan nhiều trang → AI tự nhận diện và tách từng tài liệu
- Phân loại tự động theo người + loại tài liệu
- Dịch thuật tài liệu với template HTML

### Tab "Ghép PDF" (Merge)
- Ghép nhiều file PDF thành 1 file
- Đổi tên file theo quy chuẩn

---

## 📐 Kiến trúc xử lý

```
Upload files → AI Splitter (tách tài liệu)
                    ↓
              AI Classifier (phân loại)
                    ↓
              Domain Agents (5 nhóm phân tích)
                    ↓
              Consistency Analyzer
                    ↓
              Profile Synthesizer
                    ↓
              Visa Letter Generator
```

---

## 📝 Ghi chú

- OCR ảnh và xử lý PDF dùng model OpenAI có hỗ trợ vision
- Mỗi bước xử lý lưu cache vào `output/cache` để không cần chạy lại
- Nếu PDF là scan không có text, hệ thống sẽ render trang để OCR
- Tất cả đường dẫn folder được quản lý tập trung trong `config.py`
