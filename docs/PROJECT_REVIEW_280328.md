# 📊 PROJECT REVIEW: AI Agent for Writing Visa Explanation Letters
> **Date**: 28/03/2026 | **Status**: Post-Refactor | **Server**: Running ✅

---

## 🎯 App này làm gì?

AI Agent hỗ trợ viết thư giải trình visa + tạo booking + lịch trình + dịch tài liệu + phân loại hồ sơ.
Pipeline: Upload hồ sơ → AI trích xuất → Tạo booking (flight/hotel) → Tạo itinerary → Viết letter → Phân loại & dịch tài liệu.

---

## 🛠️ Tech Stack

| Thành phần | Công nghệ |
|------------|-----------|
| Backend | **Flask** (Python 3.x) |
| AI Engine | **LangGraph** + OpenAI GPT + Google Gemini |
| Frontend | Vanilla **HTML/CSS/JS** (no framework) |
| Database | **SQLite** (visa_app.db) |
| PDF Tools | **PyMuPDF (fitz)** + **pypdf** + **Pillow** |
| Search | **SerpAPI** (flights + hotels) |

---

## 📁 Cấu trúc sau Refactor

```
📦 AI-AGENT-FOR-WRITING-VISA-EXPLANATION-LETTERS/
├── 🖥️  server.py              (Entry point - 468B)
├── ⚙️  config.py               (Config - 1.6KB)
├── 🗄️  database.py             (498L - ORM & queries)
│
├── 🧠 core/                    (AI Engine)
│   ├── agents.py               (747L - LangGraph agent nodes)
│   ├── prompts.py              (771L - AI prompt templates)
│   ├── state.py                (25L - Graph state def)
│   ├── helpers.py              (42L)
│   ├── file_utils.py           (40L)
│   └── errors.py               (20L)
│
├── 🛣️  routes/                  (19 modules, 15 blueprints)
│   ├── __init__.py             (38L - Blueprint hub)
│   ├── splitter_translate.py   (1002L ⚠️)
│   ├── pipeline.py             (727L)
│   ├── booking_serpapi.py       (713L)
│   ├── booking.py              (619L)
│   ├── precheck_helpers.py     (532L)
│   ├── splitter.py             (471L)
│   ├── pipeline_pdf.py         (437L)
│   ├── pipeline_classifier.py  (345L)
│   ├── pipeline_itinerary.py   (319L)
│   ├── pipeline_scan.py        (257L)
│   ├── splitter_manual.py      (184L)
│   ├── canada_forms.py         (170L)
│   ├── precheck.py             (169L)
│   ├── precheck_processor.py   (144L)
│   ├── pipeline_helpers.py     (106L)
│   ├── ds160.py                (104L)
│   ├── projects.py             (99L)
│   └── booking_helpers.py      (14L)
│
├── ✈️  booking/                 (Ticket Generator)
│   ├── generator.py            (1327L ⚠️)
│   └── ai_agent.py             (1030L ⚠️)
│
├── 📄 pdf_tools/                (PDF Processing)
│   ├── ai_service.py           (499L)
│   └── pdf_service.py          (200L)
│
├── 🌐 frontend/                 (Web UI)
│   ├── index.html              (975L)
│   ├── app.js                  (327L)
│   └── js/                     (16 modules ✅)
│       ├── translation.js      (820L)
│       ├── booking.js          (567L)
│       ├── projects.js         (542L)
│       ├── pipeline.js         (539L)
│       ├── flights.js          (498L)
│       ├── splitter.js         (491L)
│       ├── events.js           (468L)
│       ├── pdf-tools.js        (457L)
│       ├── manual-split.js     (439L)
│       ├── ui-helpers.js       (368L)
│       ├── hotels.js           (311L)
│       ├── pdf-editor.js       (251L)
│       ├── output.js           (218L)
│       ├── scan-splitter.js    (201L)
│       ├── precheck.js         (130L)
│       └── tab-nav.js          (53L)
│
├── 📂 dich/                     (116 files - Translation templates & assets)
├── 📂 templates/                (HTML templates for booking/itinerary)
├── 📂 canada_forms/             (IMM5257 auto-fill)
└── 📂 tests/                    (Test files)
```

---

## 📊 Sức Khỏe Code

### ✅ Điểm tốt (sau 2 session refactor)

| Điều | Chi tiết |
|------|----------|
| Frontend modular | 16 file JS, max 820L, **0 God file** ✅ |
| Backend modular | 19 route modules, 15 blueprints ✅ |
| No dead imports | Đã xóa ~60 imports thừa ✅ |
| 108+ API endpoints | Tất cả registered đúng ✅ |
| Server running | Flask dev server OK ✅ |
| Clean root | Xóa `imm5257-.pdf` (2.1MB) + `design-system/` ✅ |

### ⚠️ Cần cải thiện

| Vấn đề | File | Lines | Ưu tiên | Gợi ý |
|--------|------|-------|---------|-------|
| Backend God file | `booking/generator.py` | 1,327L | 🟡 Trung bình | Stable, but could be split by template type |
| Backend God file | `booking/ai_agent.py` | 1,030L | 🟡 Trung bình | Stable, low change frequency |
| Backend near-limit | `routes/splitter_translate.py` | 1,002L | 🟢 Thấp | Stable, decided to keep as-is |
| Frontend HTML | `index.html` | 975L | 🟡 Trung bình | Mostly UI structure, hard to split without framework |
| Deprecation pending | `google.generativeai` | - | 🟡 Trung bình | Migrate to `google-genai` in `pdf_tools/ai_service.py` |
| PDF Signature | IMM5257 auto-fill | - | 🟢 Thấp | Needs manual "Validate" in Adobe Reader |

### 📈 Refactor Progress (Biểu đồ)

```
BEFORE (26/03):
  splitter.js    █████████████████████████████████████ 1,728L 🔴
  pipeline.js    ██████████████████████████████████ 1,574L 🔴
  precheck.py    █████████████████████████ 1,300L 🔴 (estimated, pre-split)

AFTER (28/03):
  translation.js ████████████████ 820L ✅
  booking.js     ███████████ 567L ✅
  pipeline.js    ██████████ 539L ✅
  splitter.js    █████████ 491L ✅
  pdf-tools.js   █████████ 457L ✅
  manual-split.js████████ 439L ✅
  ... (all < 500L)
```

---

## 🚀 Cách Chạy

```bash
# Activate venv
.\myenv\Scripts\activate

# Run server  
python server.py

# Open browser
http://127.0.0.1:8000
```

Hoặc dùng `start.bat` đã có sẵn.

---

## 🔮 Next Steps (khuyến nghị)

| # | Việc | Ưu tiên | Effort |
|---|------|---------|--------|
| 1 | Migrate `google.generativeai` → `google-genai` | 🟡 | 2-3 giờ |
| 2 | Split `booking/generator.py` (1,327L) nếu muốn | 🟢 | 3-4 giờ |
| 3 | Thêm integration tests cho routes mới | 🟡 | 2-3 giờ |
| 4 | Tách `index.html` sections thành template partials (Jinja2) | 🟢 | 4-5 giờ |
