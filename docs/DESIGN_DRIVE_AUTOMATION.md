# 🎨 DESIGN: Visa Drive Automation (Traffic Light)

Ngày tạo: 2026-04-09
Dựa trên: [Implementation Plan - The Traffic Light]

---

## 1. Cách Lưu Thông Tin (Database)

Thay vì cơ sở dữ liệu lớn, hệ thống sử dụng kho ghi nhớ nhỏ dạng JSON/SQLite gọn nhẹ.

┌─────────────────────────────────────────────────────────────┐
│  💾 FOLDER_STATES (Sổ Ghi Nhớ Thư Mục)                      │
│  ├── id: String (Google Drive Folder ID)                    │
│  ├── last_name: String (Úc - A - Nhân - DONE)               │
│  ├── current_color: String (Red/Green/None)                 │
│  └── last_modified_time: Timestamp                          │
└─────────────────────────────────────────────────────────────┘
                              
┌─────────────────────────────────────────────────────────────┐
│  📘 DICTIONARY_RULES (Từ Điển Luật & Từ Lóng alias)         │
│  ├── categories: [Form, Passport, CCCD, Financial, Portrait]│
│  ├── alias_financial: ["so do", "land", "tai chinh", ...]   │
│  └── conditional: "employment_contract" -> "leave_request"  │
└─────────────────────────────────────────────────────────────┘

## 2. Danh Sách Các Bô Phận (Headless Components)

| # | Tên Component | Mục đích | Công nghệ |
|---|-----|----------|-------------|
| 1 | `drive_watcher.py` | Quét & bắt sự kiện tên `-DONE` | Google Drive API (Folder Polling) |
| 2 | `validator.py` | Phân loại & Chén luật (Luật từ lóng, Luật điều kiện HĐLĐ) | Python Regex + Text Normalization (Zero-cost) |
| 3 | `drive_ui_hacker.py` | Đổi màu & Gán lỗi lên tên Folder | Google Drive API (Metadata update) |
| 4 | `drive_downloader.py` | Sao chép Folder về Local | Google Drive API (File Download) + OS shutil |

## 3. Luồng Hoạt Động (User Journey)

**Hành trình Sale Nộp Đủ Bộ:**
1. Sale gộp 4 file: `to_khai.docx`, `passport.pdf`, `cccd.jpg`, `so_dat.pdf`.
2. Sửa tên thành: `ÚC - NGUYEN VAN A - NHAN - DONE`.
3. Hệ thống quét Tên -> Báo Đủ -> Đổi Xanh.
4. Download thẳng về `d:\Study... \input\ÚC - NGUYEN VAN A - NHAN`.

## 4. Checklist Kiểm Tra (Test Cases)
SPECS Reference: Keyword Matching & Folder Coloring

- [ ] TC-01: (Happy Path) Đủ file -> Màu Xanh -> Trả về Local đúng đường dẫn.
- [ ] TC-02: Đặt tên file kỳ quặc (vd: `land123 cua H.pdf`) -> Validator bóc đúng Alias tài chính.
- [ ] TC-03: (Missing Match) Thiếu Hộ Chiếu -> Báo Đỏ -> Folder thêm đuôi `THIẾU (Passport)`.
- [ ] TC-04: (Conditional Rule) Thả file `hdld.pdf`, không thả `xin nghỉ phép` -> Phải báo Đỏ thiếu đơn xin nghỉ phép.
