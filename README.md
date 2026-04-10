# 🛂 AI Visa Agent — Multi-Agent Automation System

Hệ thống multi-agent AI tự động hóa toàn bộ quy trình hồ sơ VISA: đọc tài liệu, phân loại, tách/ghép PDF, dịch thuật, tạo booking khách sạn & vé máy bay, lên lịch trình, và viết thư giải trình song ngữ (VI/EN).

---

## ⚡ Cài đặt nhanh

**Yêu cầu**: Python 3.10+ ([tải tại đây](https://www.python.org/downloads/)) — nhớ tích ✅ "Add Python to PATH".

```powershell
# 1. Clone repo
git clone <url-repo>
cd AI-AGENT-FOR-WRITING-VISA-EXPLANATION-LETTERS

# 2. Tạo môi trường ảo & cài thư viện
python -m venv myenv
myenv\Scripts\activate
pip install -r requirements.txt

# 3. Cấu hình
copy .env.example .env
# Mở .env và điền các api keys (OPENAI_API_KEY, v.v)

# 4. Cấp quyền Google Drive (Quan trọng cho Tính năng Đồng bộ)
# Tải file client_secret.json (Google Cloud Console -> APIs & Services -> Credentials -> OAuth 2.0 Client IDs (Desktop))
# Bỏ file client_secret.json vào thư mục gốc của project ngang hàng với server.py. Lần đầu tiện chạy, hệ thống sẽ mở trình duyệt để xin quyền truy cập Drive và sinh ra file token.json.
# Hãy lưu ý không bao giờ push client_secret.json và token.json lên github.

# 5. Chạy server
python server.py
```

Mở trình duyệt: **http://127.0.0.1:8000**

---

## 🔑 Biến môi trường (.env)

| Biến                  | Mô tả                                           | Bắt buộc |
| --------------------- | ------------------------------------------------ | -------- |
| `OPENAI_API_KEY`      | API key OpenAI                                   | ✅       |
| `OPENAI_MODEL`        | Model text reasoning (mặc định: `gpt-5-mini`)    | ❌       |
| `OPENAI_VISION_MODEL` | Model vision/OCR (mặc định: `gpt-4o-mini`)       | ❌       |
| `GEMINI_API_KEY`      | API key Google Gemini (fallback khi OpenAI hết quota) | ❌   |
| `GEMINI_MODEL`        | Model Gemini (mặc định: `gemini-1.5-flash`)      | ❌       |
| `SERPAPI_KEY`         | API key SerpAPI cho tìm chuyến bay               | ❌       |
| `GOOGLE_CREDENTIALS_PATH` | Đường dẫn tới file Google Credentials (mặc định: `client_secret.json`) | ❌ |

> **Lưu ý:** `TEXT_MODEL` và `VISION_MODEL` vẫn được hỗ trợ như alias tương thích ngược, nhưng nên ưu tiên `OPENAI_MODEL` và `OPENAI_VISION_MODEL`.
> Tất cả config được quản lý tập trung qua `config.py` → class `Config`. Không cần gọi `os.getenv()` trực tiếp trong code.

---

## 🖥️ 9 Tabs Chức Năng

| Tab | Chức năng | Mô tả |
|-----|-----------|-------|
| ① Tách PDF (AI) | AI Splitter | Upload scan nhiều trang → AI tự nhận diện + tách từng tài liệu tự động |
| ② Tách/Nối PDF | PDF Tools | Trộn/Merge nhiều file, rename theo format danh mục Đại sứ quán, rút trích trang |
| ③ Booking | Chuyến bay & Khách sạn | Tích hợp SerpAPI chuyến bay → Auto-check-in KHÁCH SẠN liên hoàn, vé Multi-city |
| ④ Lịch trình | Dựa trên Booking | Sinh lịch trình du lịch chi tiết từng ngày khớp hoàn toàn vé máy bay / khách sạn |
| ⑤ Bảo Hiểm | Chubb / Liberty | Sinh tự động chứng nhận bảo hiểm du lịch quốc tế (Sử dụng kiến trúc PDF Overlay) |
| ⑥ Thư giải trình | Lõi AI Agent | Đọc hiểu background người nộp → Viết thư Cover Letter chuẩn đại sứ quán (Vi/En) |
| ⑦ Kết quả | File Manager | Quản lý toàn bộ outputs ở local, xem trước, gộp chung, tải xuống |
| ⑧ Dịch thuật | Translation | Dịch và bóc tách tài liệu (Khai sinh, Tư pháp) giữ nguyên layout HTML gốc |
| ⑨ Sửa PDF | Metadata Editor | Can thiệp chỉnh sửa meta-data và fill các form điền tay dễ dàng |

> **🌟 Các Điểm Khác Biệt & Nổi Bật (Features):**
> - **Flight-First Sync:** Ngày đáp chuyến bay tự động đồng bộ làm ngày check-in khách sạn, tự nhận diện bay đêm (qua timezone) để cộng thêm `+1 Day` check-in chính xác. Tích hợp thanh Popup City Wizard tính quỹ ngày.
> - **PDF Overlay Engine:** Sinh bảo hiểm Chubb PDF chân thực qua thư viện `PyMuPDF` bằng thuật toán vẽ nền ảo (Overlay) giấu vùng chèn text và nhúng font System `[Times New Roman]` thật — giải tỏa triệt để lỗi loạn font và hỏng stream.
> - **Hỗ Trợ Form Thông Minh:** Render chính xác tờ khai IMM5257, IMM5645 (Canada) & Form 54 (Úc). Tích hợp Chrome Ext Autofill.


---

## 📂 Cấu trúc dự án

```text
├── server.py                  ← Entry point / Khởi chạy
├── config.py                  ← Config tập trung (os.getenv, bảo mật keys)
├── database.py                ← SQLite + SQLAlchemy (Project, Booking, MergedPdfs...)
├── requirements.txt           ← Dependencies & thư viện
│
├── core/                      ← Kho lõi trí tuệ nhân tạo
│   ├── agents.py              ← AI Agents (Trích xuất & phân tích DOM/PDF)
│   ├── prompts.py             ← Kho Tàng Prompt Templates (Prompt Engineering)
│   └── errors.py              ← Xử lý ngắt quãng (QuotaExhaustedError, 429)
│
├── routes/                    ← Hệ thống API (Flask Blueprints)
│   ├── __init__.py            ← Blueprint registry
│   ├── projects.py            ← CRUD dự án
│   ├── booking*.py            ← API Bookings (SerpAPI, Khách sạn, Gen vé)
│   ├── pipeline*.py           ← Các luồng Pipeline xử lý Cover Letter & PDF
│   ├── precheck.py            ← Pre-check scanner
│   ├── splitter.py            ← AI PDF splitter
│   ├── splitter_manual.py     ← Manual PDF split
│   ├── splitter_translate.py  ← Translation + OCR + HTML clone
│   └── insurance.py           ← *[New]* API endpoint cho module Bảo Hiểm
│
├── services/                  ← Business Logic Layer (Clean Architecture)
│   └── insurance/
│       └── pdf_engine.py      ← Thuật toán chèn PDF bảo hiểm tinh vi (Overlay)
│
├── booking/                   ← Logic tạo Booking (Agent + Generator)
├── pdf_tools/                 ← Hỗ trợ cắt, nối, metadata PDF 
├── classifier/                ← Classifier thông minh bóc nội dung document
│
├── australia_forms/           ← Auto-fill Úc (Xử lý Form 54 Tiếng Anh/Tiếng Việt)
├── canada_forms/              ← Auto-fill Canada (Đọc form gia đình IMM5645, File form IMM5257)
├── autofill aus/              ← Chrome Extension cho hệ thống ImmiAccount Úc
├── autofill ds160 /           ← Chrome Extension đẩy tờ khai Visa DS-160 Mỹ
│
├── frontend/                  ← Web UI Architecture (Vanilla JS)
│   ├── index.html             ← Giao diện Grid Layout Chính (9 Tabs hiển thị)
│   └── js/
│       ├── app.js             ← Global UI State (Theme, Alerts)
│       ├── booking.js         ← Booking UI
│       ├── flights.js         ← Flight search/ticket UI
│       ├── insurance.js       ← Insurance module UI
│       ├── itinerary.js       ← Itinerary generation UI
│       ├── splitter.js        ← AI splitter UI
│       ├── classifier.js      ← Document classifier UI
│       ├── steps.js           ← Pipeline steps UI
│       ├── translation.js     ← Translation UI
│       ├── pdf-tools.js       ← PDF merge/rename UI
│       ├── scan-splitter.js   ← Scan splitter UI
│       ├── manual-splitter.js ← Manual split UI
│       ├── ds160.js           ← DS-160 form UI
│       ├── canada-forms.js    ← Canada forms UI
│       ├── pdf-export.js      ← PDF export utilities 
│       └── letter-edit.js     ← Letter editor UI
│
├── tests/                     ← Hệ thống Test
│   ├── test_config.py         ← Config validation
│   ├── test_database.py       ← Database CRUD tests
│   ├── test_agents.py         ← Agent logic tests
│   ├── test_errors.py         ← Error handling tests
│   ├── test_helpers.py        ← Utility function tests
│   └── test_routes.py         ← Smoke tests for all 15 blueprints
│
├── dich/                      ← Cache HTML + Tệp JSON Template sau khi dịch 
└── splitter_uploads/          ← Nơi chứa ảnh đầu vào Tách/Phân loại
```

---

## 📐 Kiến trúc luồng hệ thống (Data Flow)

```text
       Input Trực Tiếp (Files)                        Giao Diện Điều Khiển UI
                ↓                                               ↓
 ┌─────────────────────────────┐                 ┌─────────────────────────────┐
 │       Tách PDF bằng AI      │                 │  Chubb / Tiện ích Mở rộng   │
 │   Tự động chia nhỏ tài liệu │                 │  Quản lý vé Đặt chỗ Booking │
 └─────────────────────────────┘                 └─────────────────────────────┘
                ↓                                               ↓
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │    Tầng Model Nhận Diện: OpenAI (GPT-4o-Mini) + Gemini 1.5 Flash (Fallback) │
 └─────────────────────────────────────────────────────────────────────────────┘
                ↓                                               ↓
 ┌─────────────────────────────┐                 ┌─────────────────────────────┐
 │   Trích Xuất Thông Tin (JSON│   <=========>   │  Lưu Trữ Khách/ SQLite DB   │
 │   Cây phân tích bối cảnh)   │                 │  Quản lý phiên cho Resume   │
 └─────────────────────────────┘                 └─────────────────────────────┘
                ↓                                               ↓
 ┌─────────────────────────────┐                 ┌─────────────────────────────┐
 │  Cover Letter Gen & PDF Gen │                 │ Final Review (Tab Kết Quả)  │
 │  Dịch tự động ra layout gốc │                 │ Click Tải ZIP, Merge Full   │
 └─────────────────────────────┘                 └─────────────────────────────┘
```

### Bảo mật (Security & Optimization)
- **Zero-Git-Tracking**: Những hồ sơ của người xin visa (Passport, CMND, Sao kê) tuyệt đối KHÔNG cấu trúc đồng bộ hoá lên cloud, đã config `.gitignore` chuẩn.
- **Dynamic Load Balancing**: Hệ thống có khả năng Fallback thông minh từ mô hình xử lý Text cực mạnh (GPT-4o) sang mô hình tốc độ (Gemini) ngay khi cạn Rate Limit quota. Dữ liệu Request được Resize & nén bằng JPEG 80% để siêu tiết kiệm lượng Tokens. 
- **Caching Thông Minh**: Những request đắt tiền được hệ thống caching nội bộ xuống `output/cache`, không lo chạy tốn kém qua mỗi lần reload.

---

## 🧪 Chạy Tests

```bash
# Chạy toàn bộ test suite
python -m pytest tests/ -v

# Chạy test cụ thể
python -m pytest tests/test_routes.py -v     # Smoke tests cho routes
python -m pytest tests/test_database.py -v   # Database CRUD
python -m pytest tests/test_helpers.py -v    # Utility functions
```

**Kết quả hiện tại:** ✅ 153 tests passed

---

## 📝 Database

SQLite via SQLAlchemy với 6 models:

| Model | Mô tả |
|-------|--------|
| `Project` | Container chính để chia tách ranh giới dữ liệu cho mỗi hồ sơ xin VISA riêng biệt |
| `TripInfo` | Thông tin tổng quan chuyến đi (JSON) - Dành để build context thư trình bày |
| `Booking` | Nơi lưu giữ HTML / dữ liệu sau khi AI cào tìm vé cho Chuyến bay & Khách sạn |
| `Itinerary` | Lịch trình theo ngày chi tiết chuẩn khớp với thời gian Booking do AI sinh |
| `LetterState` | Kiểm soát phiên bản và tiến độ của Cover Letter (Ingest → Summary → Writing) |
| `MergedPdf` | CSDL Vật lý theo dõi đường dẫn đến các chứng nhận bảo hiểm / pdf được cắt ghép |

---

## 📝 Ghi chú Kỹ thuật Dành cho Developer
- **PDF Overlay Strategy**: Chữ điền form (Chubb/Canada) ưu tiên kỹ thuật trỏ TextWriter nhúng kèm font TTF chân nguyên bản thay cho chức năng Redact mộc (Redact thường gây hỏng cấu trúc Text Stream gốc của nhà mạng).
- Gemini tự động fallback khi gặp lỗi `429 Rate Limit`.
- Tất cả đường dẫn và Secret Constants hiện được quản lý tại 1 nơi tập trung là class `Config` (`config.py`).
- **⚠️ Cẩn trọng Encoding**: PowerShell trên Windows không nên dùng chung cho các File có chữ Tiếng Việt nếu chưa Setup `[console]::OutputEncoding = [System.Text.Encoding]::UTF8`, do dễ gặp lỗi corruption dấu.
