# Multi-agent LangGraph viết thư giải trình VISA

Hệ thống multi-agent đọc nhiều loại hồ sơ và viết thư giải trình song ngữ (VI/EN) theo chuẩn hồ sơ VISA. Bao gồm AI tự tạo booking khách sạn + vé máy bay.

---

## ⚡ Cài đặt nhanh (1 click)

**Yêu cầu**: Python 3.10+ ([tải tại đây](https://www.python.org/downloads/)) — nhớ tích ✅ "Add Python to PATH" khi cài.

```powershell
# Bước 1: Clone repo
git clone <url-repo>
cd AI-AGENT-FOR-WRITING-VISA-EXPLANATION-LETTERS

# Bước 2: Chạy setup tự động
setup.bat
```

Script `setup.bat` sẽ tự động:

- ✅ Kiểm tra phiên bản Python
- ✅ Tạo môi trường ảo (`venv/`)
- ✅ Cài đặt tất cả thư viện
- ✅ Tạo thư mục `input/`, `output/`
- ✅ Tạo file `.env` mẫu

**Sau khi setup xong:**

1. Mở file `.env` → điền `OPENAI_API_KEY` của bạn
2. Đặt file hồ sơ vào thư mục `input/`
3. Chạy server:

```powershell
python -m venv .venv
.venv\Scripts\activate
python server.py
```

4. Mở trình duyệt: http://127.0.0.1:8000

---

## 📋 Cài đặt thủ công

```powershell
# 1. Tạo môi trường ảo
python -m venv venv
venv\Scripts\activate

# 2. Cài thư viện
pip install -r requirements.txt

# 3. Tạo file .env
copy .env.example .env
# Mở .env và điền OPENAI_API_KEY

# 4. Tạo thư mục
mkdir input
mkdir output

# 5. Chạy server
python server.py
```

---

## 📂 Chuẩn bị dữ liệu đầu vào

Đặt các file vào thư mục `input/`. Tên file có tiền tố để phân loại:

- `HO SO CA NHAN` — Hộ chiếu, CMND, sơ yếu lý lịch
- `LICH SU DU LICH` — Lịch sử xuất nhập cảnh
- `CONG VIEC` — Hợp đồng lao động, giấy phép kinh doanh
- `TAI CHINH` — Sao kê ngân hàng, sổ tiết kiệm
- `MUC DICH CHUYEN DI` — Thư mời, kế hoạch du lịch
- `TONG QUAN` — Form khai thông tin, nội dung hồ sơ giải trình, hoặc tài liệu bổ sung tự do; dùng để bổ sung dữ liệu quan trọng cho bước tổng hợp và viết thư giải trình

Ví dụ:

```
HO SO CA NHAN - passport.pdf
CONG VIEC - hop_dong_lao_dong.docx
TAI CHINH - sao_ke_6_thang.pdf
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

---

## 🔑 Biến môi trường (.env)

| Biến             | Mô tả                                   | Bắt buộc |
| ---------------- | --------------------------------------- | -------- |
| `OPENAI_API_KEY` | API key của OpenAI                      | ✅       |
| `OPENAI_MODEL`   | Model sử dụng (mặc định: `gpt-4o-mini`) | ❌       |

---

## 📐 Kiến trúc

```
Ingest files
   ↓
Classifier + Extractor (theo tiền tố)
   ↓
Domain Agents (5 nhóm)
   ↓
Consistency Analyzer
   ↓
Profile Synthesizer
   ↓
Visa Explanation Letter Generator
```

---

## 🛠️ CLI (tuỳ chọn)

```powershell
venv\Scripts\activate
python main.py --input_dir .\input --output .\output\letter.txt
```

## 📝 Ghi chú

- OCR ảnh và xử lý PDF dùng model OpenAI có hỗ trợ vision
- Mỗi bước xử lý lưu cache vào `output/cache` để không cần chạy lại
- Nếu PDF là scan không có text, hệ thống sẽ render trang để OCR
