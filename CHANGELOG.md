# Changelog

## [2026-04-16]
### Fixed
- Sửa lỗi UI progress bị chặn do `loadLatestLetterV2` không defined.
- Sửa lỗi override `participants` trong `pipeline.js` bằng cách sử dụng đúng `formData`.
- Khắc phục lỗi caching file JS tĩnh trong `server.py` để trình duyệt tải code mới nhất.
- Chỉnh lại style iframe booking máy bay trong `index.html` (min-height 600px).
- Làm chặt chẽ AI Prompt trong `core/prompts.py` bắt buộc ghép lịch trình đi thăm thân từ profile vào itinerary nhưng vẫn phải về khách sạn, không ở qua đêm và đi cách ngày.
