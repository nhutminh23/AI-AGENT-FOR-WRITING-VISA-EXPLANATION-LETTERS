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
# Mở .env và điền OPENAI_API_KEY

# 4. Chạy server
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

> **Lưu ý:** `TEXT_MODEL` và `VISION_MODEL` vẫn được hỗ trợ như alias tương thích ngược, nhưng nên ưu tiên `OPENAI_MODEL` và `OPENAI_VISION_MODEL`.
> Tất cả config được quản lý tập trung qua `config.py` → class `Config`. Không cần gọi `os.getenv()` trực tiếp trong code.

---

## 🖥️ 9 Tabs Chức Năng

| Tab | Chức năng | Mô tả |
|-----|-----------|-------|
| ① Thư giải trình | Pipeline AI | Chạy từng bước hoặc "Chạy tất cả" → AI phân tích hồ sơ → viết thư song ngữ |
| ② PDF Tools | Ghép/tách/đổi tên PDF | Merge nhiều file, rename theo chuẩn, chỉnh sửa nội dung |
| ③ Tách tự động | AI Splitter | Upload scan nhiều trang → AI tự nhận diện + tách từng tài liệu |
| ④ Phân loại | AI Classifier | Phân loại tài liệu theo người + loại (Passport, CCCD, Bank Statement...) |
| ⑤ Booking | Tạo booking | Ưu tiên chuyến bay → Auto-check-in KHÁCH SẠN, Multi-city (Datalist Thành phố) |
| ⑥ Lịch trình | Itinerary Generator | Tạo lịch trình chi tiết từ booking |
| ⑦ Dịch thuật | Translation | Dịch tài liệu + clone layout HTML gốc |
| ⑧ Precheck | Pre-check hồ sơ | Kiểm tra thiếu sót trước khi nộp |
| ⑨ Tách thủ công | Manual Split | Tách PDF thủ công theo range trang |

> **🌟 Tính năng mới (Workflow Booking Tối ưu):**
> - **Flight-First:** Chuyến bay ưu tiên chọn trước. Ngày đáp (`window.flightArrivalDate`) tự động đồng bộ làm ngày *Check-in* khách sạn để tránh lệch múi giờ.
> - **City Wizard:** Hỗ trợ nhập danh sách thành phố tự động thông qua giao diện Pop-up, tự tính toán "Tổng số đêm" dựa trên khoảng cách "Ngày đi" & "Ngày về".

---

## 📂 Cấu trúc dự án

```
├── server.py                  ← Entry point (23 dòng)
├── config.py                  ← Config tập trung (1 class, 20+ constants)
├── database.py                ← SQLite + SQLAlchemy (6 models, CRUD helpers)
├── requirements.txt           ← 18 dependencies
│
├── core/                      ← Logic nghiệp vụ chính
│   ├── agents.py              ← AI agents (domain extractor, classifier)
│   ├── prompts.py             ← Prompt templates (35KB)
│   ├── errors.py              ← QuotaExhaustedError + error detection
│   └── helpers.py             ← Shared helpers (model selection, file listing)
│
├── routes/                    ← Flask blueprints (15 blueprints, 98 endpoints)
│   ├── __init__.py            ← Blueprint registry
│   ├── projects.py            ← CRUD dự án
│   ├── booking.py             ← AI booking generation
│   ├── booking_serpapi.py     ← SerpAPI flight & hotel search
│   ├── booking_helpers.py     ← Shared booking constants
│   ├── splitter.py            ← AI PDF splitter
│   ├── splitter_manual.py     ← Manual PDF split
│   ├── splitter_translate.py  ← Translation + OCR + HTML clone
│   ├── precheck.py            ← Pre-check scanner
│   ├── precheck_helpers.py    ← Precheck helpers
│   ├── precheck_processor.py  ← File renaming & merging
│   ├── pipeline.py            ← Main pipeline orchestration
│   ├── pipeline_classifier.py ← Document classification
│   ├── pipeline_scan.py       ← Scan splitter
│   ├── pipeline_pdf.py        ← PDF merge/edit/rename
│   ├── pipeline_itinerary.py  ← Itinerary generation
│   └── pipeline_helpers.py    ← Path safety + naming helpers
│
├── classifier/                ← AI document classifier module
│   └── agent.py
│
├── booking/                   ← Booking generation module
│   ├── generator.py
│   └── ai_agent.py
│
├── pdf_tools/                 ← PDF processing + AI classification
│   ├── pdf_service.py
│   └── ai_service.py          ← OpenAI Vision + Gemini fallback
│
├── canada_forms/              ← Canada IMM form auto-fill
│   ├── agent.py               ← AI family info extraction
│   ├── reader.py              ← Multi-format document reader
│   ├── fill_imm5257.py        ← IMM5257 form filler
│   └── fill_imm5645.py        ← IMM5645 form filler
│
├── frontend/                  ← Web UI (Vanilla JS, modular)
│   ├── index.html             ← Main layout (9 tabs)
│   ├── app.js                 ← App init + global state (314 dòng)
│   └── js/                    ← 16 feature modules
│       ├── projects.js        ← Project CRUD UI
│       ├── splitter.js        ← AI splitter UI
│       ├── classifier.js      ← Document classifier UI
│       ├── steps.js           ← Pipeline steps UI
│       ├── booking.js         ← Booking UI
│       ├── flights.js         ← Flight search/ticket UI
│       ├── itinerary.js       ← Itinerary generation UI
│       ├── translation.js     ← Translation UI
│       ├── precheck.js        ← Pre-check UI
│       ├── pdf-tools.js       ← PDF merge/rename UI
│       ├── scan-splitter.js   ← Scan splitter UI
│       ├── manual-splitter.js ← Manual split UI
│       ├── ds160.js           ← DS-160 form UI
│       ├── canada-forms.js    ← Canada forms UI
│       ├── pdf-export.js      ← PDF export utilities
│       └── letter-edit.js     ← Letter editor UI
│
├── tests/                     ← Test suite (153 tests)
│   ├── test_config.py         ← Config validation
│   ├── test_database.py       ← Database CRUD tests
│   ├── test_agents.py         ← Agent logic tests
│   ├── test_errors.py         ← Error handling tests
│   ├── test_helpers.py        ← Utility function tests
│   └── test_routes.py         ← Smoke tests for all 15 blueprints
│
├── dich/                      ← Translation templates + output
├── phanloai/                  ← Classifier input → output
├── splitter_uploads/          ← Splitter file uploads
├── splitter_outputs/          ← Split PDF results
└── scan_splitter_outputs/     ← Scan split results
```

---

## 📐 Kiến trúc xử lý

```
Upload files → AI Splitter (tách tài liệu)
                    ↓
              AI Classifier (phân loại theo người + loại)
                    ↓
              Domain Agents (5 nhóm: personal, financial, employment, travel, purpose)
                    ↓
              Consistency Analyzer (kiểm tra mâu thuẫn)
                    ↓
              Profile Synthesizer (tổng hợp hồ sơ)
                    ↓
              Visa Letter Generator (viết thư song ngữ VI/EN)
```

### AI Models
- **GPT-5-mini**: Text reasoning, viết thư, phân tích nội dung
- **GPT-4o-mini**: Vision/OCR, đọc ảnh scan, phân loại tài liệu
- **Gemini 1.5-flash**: Fallback tự động khi OpenAI hết quota

### Token Optimization
- Image resize → 1024px JPEG 80% trước khi gửi AI → tiết kiệm ~60% tokens
- Batch processing: 5 pages/batch × 5 parallel waves
- Smart caching: mỗi bước lưu cache vào `output/cache`

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
| `Project` | Container chính cho mỗi hồ sơ VISA |
| `TripInfo` | Thông tin chuyến đi (versioned) |
| `Booking` | Dữ liệu booking khách sạn + vé máy bay |
| `Itinerary` | Lịch trình chi tiết (versioned) |
| `LetterState` | Trạng thái + nội dung thư giải trình |
| `MergedPdf` | File PDF đã ghép (standalone, không cần project) |

---

## 📝 Ghi chú

- OCR và xử lý ảnh dùng model OpenAI Vision (GPT-4o-mini)
- Gemini tự động fallback khi gặp lỗi 429 Rate Limit
- Mỗi bước xử lý lưu cache → không cần chạy lại từ đầu
- PDF scan không có text sẽ tự render page → OCR
- Tất cả đường dẫn quản lý tập trung trong `config.py`
- **⚠️ PowerShell không nên dùng cho file operations với Vietnamese text** (UTF-8 corruption)
