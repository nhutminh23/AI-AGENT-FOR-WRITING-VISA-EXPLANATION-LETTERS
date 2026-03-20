"""Remove pipeline section from server.py"""
lines = open('server.py', 'r', encoding='utf-8').readlines()
si = None
ei = None
for i, l in enumerate(lines):
    if si is None and '@app.post("/api/pipeline/send-to-splitter")' in l:
        si = i
    if 'if __name__' in l:
        ei = i
        break

new_lines = lines[:si] + [
    '# ==================== ALL ROUTE ENDPOINTS -> routes/ ====================\r\n',
    '\r\n',
] + lines[ei:]

open('server.py', 'w', encoding='utf-8').writelines(new_lines)
print(f'Old: {len(lines)} -> New: {len(new_lines)} lines (removed {len(lines) - len(new_lines)})')
