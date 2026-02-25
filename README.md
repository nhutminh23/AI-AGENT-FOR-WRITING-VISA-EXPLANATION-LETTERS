# Multi-agent LangGraph viết thư giải trình VISA

Mục tiêu: hệ thống multi-agent đọc nhiều loại hồ sơ và viết thư giải trình song ngữ (VI/EN) theo chuẩn hồ sơ VISA.

## 1) Yêu cầu
- Python 3.10+
- API key OpenAI
- (Tuỳ chọn) Tesseract OCR nếu cần đọc ảnh scan

## 2) Thiết lập môi trường ảo
```powershell
python -m venv .venv
.venv\Scripts\activate
deactivate
pip install -r requirements.txt
```

Tạo file `.env` từ `.env.example` và điền `OPENAI_API_KEY`.

## 3) Chuẩn bị dữ liệu đầu vào
Đặt các file vào thư mục `input/`. Tên file có tiền tố để phân loại:
- `HO SO CA NHAN`
- `LICH SU DU LICH`
- `CONG VIEC`
- `TAI CHINH`
- `MUC DICH CHUYEN DI`
Nếu file không thuộc các tiền tố trên, hệ thống sẽ xếp vào nhóm thông tin bổ sung (additional) để cung cấp thêm bối cảnh/vấn đề cho AI.

Ví dụ:
```
HO SO CA NHAN - passport.pdf
CONG VIEC - hop_dong_lao_dong.docx
TAI CHINH - sao_ke_6_thang.pdf
```

## 4) Chạy giao diện (frontend) - khuyến nghị
```powershell
python server.py
```
Mở trình duyệt: `http://127.0.0.1:8000`
Agent **chỉ chạy khi bấm nút từng bước** trên giao diện. Mỗi bước sẽ lưu kết quả
vào `output/cache` để tái sử dụng (không cần chạy lại từ đầu).

## 5) Chạy bằng CLI (tuỳ chọn)
```powershell
python main.py --input_dir .\input --output .\output\letter.txt
```

Kết quả sẽ được ghi vào `output/letter.txt`.

## 6) Ghi chú về OCR/PDF
- OCR ảnh và xử lý PDF dùng `OPENAI_MODEL` (model có hỗ trợ vision).
- Nếu PDF là scan không có text, hệ thống sẽ thử render trang để OCR bằng OpenAI.

## 7) Kiến trúc
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
