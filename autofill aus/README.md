# AutoScript - UserScript Manager

Chrome Extension (MV3) quản lý và tự động chạy UserScript, tương tự Tampermonkey.

## Tính năng

- Quản lý UserScript: tạo, sửa, xóa, bật/tắt
- Parse metadata header (`@name`, `@match`, `@version`, `@description`, ...)
- Tự động inject script vào trang web khớp `@match`
- Toggle bật/tắt script ngay lập tức (không cần reload trang)
- Giao diện dark theme giống Tampermonkey
- Xuất/Nhập script dạng JSON
- Thùng rác (khôi phục script đã xóa)

## Cài đặt (Load Unpacked)

1. Mở Chrome, truy cập `chrome://extensions/`
2. Bật **Developer mode** (góc phải trên)
3. Click **Load unpacked**
4. Chọn thư mục `autofill aus` (chứa file `manifest.json`)
5. Extension sẽ xuất hiện trên toolbar

## Cách sử dụng

### Popup
- Click icon extension trên toolbar
- **Đã bật/Đã tắt**: Toggle bật/tắt toàn bộ script
- **Tạo tập lệnh mới**: Mở editor với template mẫu
- **Bảng tổng quan**: Mở dashboard quản lý

### Dashboard
- Xem danh sách tất cả script đã cài
- Toggle bật/tắt từng script
- Click tên script để mở editor
- Tìm kiếm script theo tên
- Xuất/Nhập backup JSON
- Thùng rác: khôi phục script đã xóa

### Editor
- Soạn thảo code với giao diện dark theme
- **Save** (Ctrl+S): Lưu script
- **Run** (Ctrl+Enter): Chạy ngay trên tab hiện tại
- **Delete**: Xóa script
- Hỗ trợ Tab indent, line numbers, vị trí cursor

## Cách test

### Test nhanh với example.com
1. Tạo script mới trong editor
2. Đặt `@match` là `https://example.com/*`
3. Code mẫu:
```javascript
// ==UserScript==
// @name         Test Script
// @match        https://example.com/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';
    document.body.style.background = '#1a1a2e';
    document.body.style.color = '#eee';
    const banner = document.createElement('div');
    banner.textContent = 'AutoScript đang chạy!';
    banner.style.cssText = 'position:fixed;top:0;left:0;right:0;padding:12px;background:#e8912d;color:#fff;text-align:center;font-size:18px;z-index:99999';
    document.body.prepend(banner);
})();
```
4. Save, mở `https://example.com` - sẽ thấy banner cam

### Test với DS-160
Dùng `@match` như: `https://ceac.state.gov/GenNIV/General/complete/*`

## Cấu trúc file

```
autofill aus/
├── manifest.json          # Extension config (MV3)
├── background.js          # Service worker - inject engine
├── popup.html/css/js      # Popup giao diện
├── dashboard.html/css/js  # Bảng tổng quan
├── editor.html/css/js     # Trình soạn thảo script
├── shared/
│   ├── storage.js         # CRUD chrome.storage.local
│   ├── metadata.js        # Parse UserScript header
│   └── utils.js           # Helpers (match, format, ...)
├── icons/                 # Extension icons
└── README.md
```

## Giới hạn

- Editor dùng textarea (không có syntax highlight thực sự)
- Chỉ hỗ trợ `@match` (chưa hỗ trợ `@include`, `@exclude`)
- Chưa hỗ trợ `@require`, `@resource`, `GM_*` API
