# 🛂 Visa Automation System

> **Hệ thống tự động hóa toàn diện cho nghiệp vụ tư vấn visa** — từ phân loại tài liệu, dịch thuật, đến tạo thư giải trình và booking.

---

## 📋 Mục lục

1. [Tổng quan](#tổng-quan)
2. [Tính năng chính](#tính-năng-chính)
3. [Cấu trúc dự án](#cấu-trúc-dự-án)
4. [Cài đặt](#cài-đặt)
5. [Cấu hình môi trường](#cấu-hình-môi-trường)
6. [Khởi chạy](#khởi-chạy)
7. [Luồng nghiệp vụ](#luồng-nghiệp-vụ)
8. [API Reference](#api-reference)
9. [Công nghệ sử dụng](#công-nghệ-sử-dụng)
10. [Lịch sử phiên bản](#lịch-sử-phiên-bản)

---

## Tổng quan

Visa Automation System là ứng dụng web nội bộ (Flask + Vanilla JS) hỗ trợ đội ngũ tư vấn visa xử lý hồ sơ khách hàng nhanh hơn, chính xác hơn thông qua AI (OpenAI GPT-4o, Gemini).

**Vấn đề giải quyết:**
- Hồ sơ visa thường gồm hàng chục file PDF lộn xộn cần phân loại, đặt lại tên, dịch thuật
- Viết thư giải trình mất nhiều thời gian thủ công
- Booking khách sạn/vé máy bay cho hồ sơ phải kiểm tra nhiều nguồn
- Quản lý tiến độ nhiều hồ sơ cùng lúc

**Giải pháp:**
Pipeline tự động hóa từ đầu đến cuối: Google Drive → Precheck → Splitter → Dịch thuật → Thư giải trình → Booking → Drive.

---

## Tính năng chính

### 1. 📁 Quản lý Hồ sơ (Projects)
- Tạo/sửa/xóa project theo từng khách hàng
- **Cascade delete**: Xóa project tự động dọn sạch file trên ổ cứng
- Lưu trạng thái tiến độ từng bước vào SQLite database

### 2. 🔍 Precheck — Kiểm tra & Phân loại tài liệu
- AI Vision quét toàn bộ file trong thư mục input
- Phát hiện file cần tách (multi-doc), gợi ý tên chuẩn
- Parallel processing với ThreadPoolExecutor (10 workers)
- Phát hiện file dịch thuật (đuôi `-dịch`, `-dich`)

### 3. ✂️ AI PDF Splitter
- Upload PDF nhiều trang → AI phân loại từng trang → tách thành file riêng
- Hỗ trợ tách thủ công (kéo-thả boundaries)
- **Scan Splitter**: Tách PDF scan bằng cách nhận diện trang chứng nhận dịch thuật "Passport Lounge"
- Lưu mapping file gốc → file đã tách để save-to-source

### 4. 🌐 Dịch thuật tài liệu (Translation)
- Dịch PDF/ảnh → HTML bilingual (song ngữ Việt-Anh) với template A4
- Template tự động: a4.html, hộ khẩu, khai sinh, sổ đỏ, giấy phép kinh doanh, v.v.
- Đóng dấu chứng nhận dịch thuật (Stamp/Seal) vào PDF output
- **Translation Workspace**: Tích hợp Google Drive — tự động download folder từ Drive vào local workspace
- Bulk translate: Dịch tất cả file trong workspace cùng lúc
- Lưu HTML trung gian để chỉnh sửa trước khi xuất PDF

### 5. ✉️ Thư giải trình (Letter Generator)
Pipeline 3 bước:
1. **Ingest**: AI Vision đọc và trích xuất nội dung tất cả file input
2. **Summary**: Tạo hồ sơ tóm tắt khách hàng (tài chính, gia đình, nghề nghiệp...)
3. **Writer**: Viết thư giải trình visa hoàn chỉnh theo context

### 6. ✈️ Booking Simulator
- AI tự động chọn khách sạn & chuyến bay phù hợp với lịch trình
- Sinh HTML booking confirmation (khách sạn + vé máy bay)
- Hỗ trợ: Australia, Mỹ (DS-160), Canada, và nhiều quốc gia khác
- Cache kết quả AI để tiết kiệm token khi re-generate

### 7. 📋 Form tự động
- **Australia Form 54**: Điền PDF tự động từ JSON (Family Composition)
- **DS-160 (Mỹ)**: Script autofill Chrome Extension
- **Canada IMM5257E**: Điền form Canada tự động
- **IMMI AutoFill Hub**: Server JSON profile cho Chrome Extension tự động điền form online

### 8. 🛡️ Bảo hiểm du lịch
- Tạo PDF bảo hiểm Liberty/Chubb tự động
- AI điền thông tin từ hồ sơ khách hàng
- Tích hợp API kiểm tra phí bảo hiểm

### 9. 🗜️ Compress Tools
- Scan đệ quy thư mục, tìm file trong subfolder `Final/` vượt giới hạn kích thước
- Nén PDF (lossless → raster multi-pass) và ảnh (JPEG/PNG/WEBP)
- Tự động thay file gốc bằng file đã nén nếu đạt target size

### 10. ☁️ Google Drive Integration
- **Drive Watcher**: Background daemon theo dõi folder Drive, tự động download khi có trigger
- **Push to Drive**: Upload file đã xử lý lên Drive, tạo subfolder `Final/`, đổi tên folder theo trạng thái
- **Validator**: Kiểm tra quy chuẩn đặt tên file trước khi gửi lên Drive
- Traffic light flow: `Đang xử lý` → `CHECK` → `✅ Đang dịch` → `DONE`

---

## Cấu trúc dự án

```
visa-automation/
│
├── server.py                  # Entry point — Flask app + Drive Watcher launcher
├── config.py                  # ⚙️ Single source of truth cho mọi path/config
├── database.py                # SQLAlchemy models + CRUD functions
├── requirements.txt
├── start.bat                  # Script khởi động Windows
│
├── routes/                    # Flask Blueprints (29 files)
│   ├── projects.py            # CRUD projects + cascade delete
│   ├── pipeline.py            # Letter pipeline (ingest/summary/writer)
│   ├── pipeline_classifier.py # AI classifier pipeline
│   ├── pipeline_scan.py       # Scan splitter pipeline
│   ├── pipeline_pdf.py        # PDF tools pipeline
│   ├── pipeline_itinerary.py  # Itinerary generation
│   ├── splitter.py            # AI PDF Splitter
│   ├── splitter_manual.py     # Manual split
│   ├── splitter_translate.py  # Translation workspace
│   ├── translate_api.py       # Translation REST API
│   ├── translate_core.py      # Translation core logic
│   ├── translate_stamp.py     # Stamp/seal workflow
│   ├── precheck.py            # Document precheck scan
│   ├── precheck_helpers.py    # Classification helpers
│   ├── precheck_processor.py  # File rename/move processor
│   ├── booking.py             # Booking generator
│   ├── booking_serpapi.py     # Flight search via SerpAPI
│   ├── booking_html_builder.py
│   ├── booking_itinerary_parser.py
│   ├── push_to_drive.py       # Upload to Google Drive
│   ├── insurance.py           # Insurance PDF editor
│   ├── compress_tools.py      # PDF/image compressor
│   ├── australia_forms.py     # Australia Form 54 + IMMI hub
│   ├── canada_forms.py        # Canada IMM5257E
│   ├── ds160.py               # DS-160 (Mỹ)
│   ├── letter_gen.py          # Letter generation routes
│   └── __init__.py            # Blueprint registration
│
├── sync/                      # Google Drive automation
│   ├── drive_watcher.py       # Background daemon
│   ├── drive_downloader.py    # Download logic
│   ├── drive_ui_hacker.py     # Drive API (upload/rename/create)
│   ├── validator.py           # File naming validation
│   └── rules.json             # Validation rules
│
├── core/                      # Shared AI logic
│   ├── agents.py              # ingest_files, build_summary, letter_writer
│   ├── helpers.py             # get_vision_model, cache_dir, list_input_files
│   ├── errors.py              # QuotaExhaustedError
│   └── state.py               # GraphState TypedDict
│
├── pdf_tools/                 # PDF processing utilities
│   ├── pdf_service.py         # pdf_to_images, get_page_count
│   ├── ai_service.py          # classify_all_pages (AI vision)
│   └── stamper.py             # Seal/stamp overlay on PDF
│
├── classifier/                # Document classifier agent
├── letter_gen/                # Letter generation templates
├── booking/                   # Booking generator logic
├── services/                  # External service integrations
│   └── insurance/             # Liberty/Chubb APIs
│
├── frontend/                  # Single-page app (Vanilla JS)
│   ├── index.html             # Main SPA shell
│   ├── styles.css
│   ├── app.js
│   └── js/                    # Feature modules (21 files)
│       ├── projects.js
│       ├── pipeline.js
│       ├── splitter.js
│       ├── translation.js     # (~68KB) Translation UI
│       ├── workspace.js       # Drive workspace UI
│       ├── booking.js
│       ├── insurance.js
│       ├── compress-tools.js
│       ├── precheck.js
│       ├── push-to-drive.js
│       └── ...
│
├── storage/                   # 📦 Tất cả runtime data (gitignored trừ templates)
│   ├── input/                 # File đầu vào từ Drive Watcher
│   ├── output/                # File output tổng hợp
│   ├── uploads/               # File upload từ browser
│   │   └── translation_originals/  # Lưu bền vững file gốc dịch thuật
│   ├── splitter/              # Output AI Splitter
│   ├── scan_splitter/         # Output Scan Splitter
│   ├── translation/
│   │   ├── templates/         # HTML templates dịch thuật (versioned)
│   │   ├── output/            # PDF dịch thuật đầu ra
│   │   └── html/              # HTML trung gian
│   ├── workspace/             # Translation workspaces (từ Drive)
│   ├── insurance/             # Insurance PDF output
│   └── archive/               # Workspace đã hoàn tất (moved, không xóa)
│
├── extensions/                # Chrome Extensions (autofill)
│   ├── autofill-australia/    # IMMI online form autofill
│   └── autofill-ds160/        # DS-160 autofill scripts
│
├── australia_forms/           # Australia form logic & frontend
├── canada_forms/              # Canada form logic
├── templates/                 # PDF/HTML templates (insurance, booking)
├── docs/                      # Tài liệu bàn giao
└── tests/                     # pytest test suite
    └── test_config.py
```

---

## Cài đặt

### Yêu cầu
- Python 3.9+
- Windows (một số tính năng dùng tkinter/subprocess Windows)
- Playwright (cho stamp workflow)

### 1. Clone & tạo môi trường

```bash
git clone https://github.com/nhutminh23/AI-AGENT-FOR-WRITING-VISA-EXPLANATION-LETTERS.git
cd AI-AGENT-FOR-WRITING-VISA-EXPLANATION-LETTERS

python -m venv myenv
myenv\Scripts\activate        # Windows
```

### 2. Cài dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Cài Playwright browsers (cho stamp PDF)

```bash
playwright install chromium
```

---

## Cấu hình môi trường

Copy file mẫu và điền thông tin:

```bash
cp .env.example .env
```

```env
# ── AI Models ──────────────────────────────────────
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_VISION_MODEL=gpt-4o-mini

# Fallback (optional)
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-1.5-flash

# ── Search (cho booking) ────────────────────────────
SERPAPI_KEY=...

# ── Google Drive Sync ───────────────────────────────
GOOGLE_CREDENTIALS_PATH=credentials.json
DRIVE_ROOT_FOLDER=HỒ SƠ VISA 2026
DRIVE_TRANSLATION_FOLDER=Dịch Thuật
DRIVE_TRANSLATION_FOLDER_ID=...
DRIVE_TRANSLATION_DONE_PREFIX=DONE
DRIVE_POLL_INTERVAL=10
```

### Google Drive Setup

1. Tạo project Google Cloud, bật Drive API
2. Tạo OAuth credentials → download `credentials.json` vào root
3. Chạy lần đầu để authorize → `token.json` được tạo tự động

---

## Khởi chạy

### Windows (khuyến nghị)

```bash
start.bat
```

### Thủ công

```bash
myenv\Scripts\activate
python server.py
```

Truy cập: **http://127.0.0.1:8000**

> Drive Watcher tự động khởi động cùng server (background subprocess).

---

## Luồng nghiệp vụ

### Luồng 1: Hồ sơ Visa (Letter Generation)

```
Google Drive (trigger folder "-DONE")
    ↓  Drive Watcher download
storage/input/<khách hàng>/
    ↓  Precheck Tab — AI scan & classify
Rename files (chuẩn hóa tên)
    ↓  Send to Splitter (multi-doc files)
AI Splitter → tách PDF → storage/splitter/
    ↓  Send to Classifier
storage/input/ (classified)
    ↓  Pipeline Tab
  Step 1: Ingest (AI Vision đọc file)
  Step 2: Summary (tạo hồ sơ tóm tắt)
  Step 3: Writer (viết thư giải trình)
    ↓  Booking Tab
  AI chọn khách sạn + chuyến bay
  Sinh HTML booking confirmation
    ↓  Push to Drive
Drive: "Tên KH - CHECK"
```

### Luồng 2: Dịch thuật

```
Google Drive ("Dịch Thuật" folder)
    ↓  Drive Watcher tạo workspace
storage/workspace/<tên KH>/
    ↓  Translation Tab — chọn workspace
Upload file cần dịch
    ↓  AI dịch → HTML bilingual
Chỉnh sửa HTML (nếu cần)
    ↓  Stamp/Seal — đóng dấu Passport Lounge
PDF output → storage/translation/output/
    ↓  Workspace hoàn tất → archive
storage/archive/<tên KH>/
```

---

## API Reference

### Projects
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/api/projects` | Danh sách projects |
| POST | `/api/projects` | Tạo project mới |
| DELETE | `/api/projects/<id>` | Xóa project + cascade delete files |

### Precheck
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| POST | `/api/precheck/scan` | AI scan & classify tất cả files |
| GET | `/api/precheck/progress` | Poll tiến độ scan |
| POST | `/api/processor/rename` | Đổi tên file hàng loạt |
| POST | `/api/processor/push-to-drive` | Upload lên Drive |

### AI Splitter
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| POST | `/api/splitter/upload` | Upload PDF cần tách |
| GET | `/api/splitter/status/<id>` | Kiểm tra tiến độ tách |
| GET | `/api/splitter/files` | Danh sách file chờ tách |
| POST | `/api/pipeline/send-to-splitter` | Chuyển file vào splitter queue |
| POST | `/api/splitter/save-to-source` | Lưu kết quả về folder gốc |

### Translation
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/api/translate/workspaces` | Danh sách workspaces |
| POST | `/api/translate/upload` | Upload file cần dịch |
| POST | `/api/translate/flows` | Dịch file (single/bulk) |
| GET | `/api/translate/pages/<ref>` | Xem trang đã dịch |
| POST | `/api/translate/stamp` | Đóng dấu chứng nhận |
| POST | `/api/translate/mark-done` | Đánh dấu hoàn tất workspace |

### Letter Pipeline
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/api/ingest_stream` | SSE stream ingest files |
| POST | `/api/run_step` | Chạy từng step (ingest/summary/writer) |
| POST | `/api/run_all` | Chạy toàn bộ pipeline |
| GET | `/api/summary` | Lấy summary profile |
| GET | `/api/steps` | Trạng thái từng step |

### Booking
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| POST | `/api/booking/extract_trip` | AI trích xuất trip info từ file |
| POST | `/api/booking/ai_generate` | AI tạo booking |
| POST | `/api/booking/ai_generate_stream` | AI tạo booking (SSE stream) |
| GET | `/api/booking/latest` | Booking mới nhất |

### Forms
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| POST | `/australia/api/fill-54` | Điền Australia Form 54 |
| GET | `/australia/api/active-profile` | Lấy profile cho Chrome Extension |
| POST | `/api/insurance/generate` | Tạo PDF bảo hiểm |

### Compress Tools
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| POST | `/api/compress/pick-folder` | Mở folder picker dialog |
| POST | `/api/compress/scan` | Scan file trong `Final/` vượt giới hạn |
| POST | `/api/compress/file` | Nén một file |
| POST | `/api/compress/all` | Nén tất cả file vượt giới hạn |

---

## Công nghệ sử dụng

| Layer | Công nghệ |
|-------|-----------|
| Backend | Python 3.9+, Flask, Flask-CORS |
| AI | OpenAI GPT-4o-mini (text + vision), Google Gemini (fallback) |
| AI Framework | LangChain, LangGraph |
| PDF | PyMuPDF (fitz), pypdf, pdfplumber, reportlab, xhtml2pdf |
| Storage | SQLite (via SQLAlchemy) |
| Google Drive | google-api-python-client, google-auth |
| Search | SerpAPI (flight search) |
| Frontend | Vanilla JS (ES6+), HTML5, CSS3 |
| Testing | pytest |
| Chrome Extensions | Manifest V3, Content Scripts |

---

## Lịch sử phiên bản

### v2.0.0 — 2026-04-29 (Current)
- **Refactor Storage**: Gộp tất cả runtime data vào `storage/` (splitter, translation, insurance, workspace, archive, uploads)
- **Cascade Delete**: Xóa project → tự động xóa file liên quan trên ổ cứng
- **Config Unification**: `config.py` là single source of truth, loại bỏ toàn bộ hardcoded paths
- **Extensions**: Gộp `autofill aus/` + `autofill ds160/` vào `extensions/`
- **Tests**: Cập nhật test suite khớp cấu trúc mới (23/23 passed)

### v1.5.0
- Thêm Compress Tools (PDF + image compression)
- Thêm Scan Splitter (tách theo trang chứng nhận dịch thuật)
- Thêm IMMI AutoFill Hub (Chrome Extension profile server)

### v1.4.0
- Thêm Translation Workspace (tích hợp Google Drive)
- Stamp/Seal workflow với Playwright
- Bulk translation support

### v1.3.0
- Thêm Australia Form 54 auto-fill
- Thêm Canada IMM5257E
- Thêm Insurance PDF (Liberty/Chubb)

### v1.2.0
- Google Drive Watcher (background daemon)
- Push to Drive với tự động đổi tên folder theo trạng thái
- Validator kiểm tra quy chuẩn đặt tên file

### v1.1.0
- AI PDF Splitter với vision model
- Precheck scan parallel (10 workers)
- Manual split UI

### v1.0.0
- Letter Generation Pipeline (ingest → summary → writer)
- Project management
- Booking generator (hotel + flight HTML)
- DS-160 autofill scripts

---

## Lưu ý vận hành

- **Restart server** sau khi thay đổi `config.py`
- **Drive Watcher** chạy nền, tự tắt khi server stop
- Thư mục `storage/` chứa tất cả dữ liệu runtime — backup định kỳ
- `storage/translation/templates/` được versioned (không gitignore) — chứa HTML templates dịch thuật
- File `.env` và `credentials.json` KHÔNG commit lên Git

---

*Maintained by Passport Lounge Development Team*
