"""
Quick Test Script – Verify Translation Automation Pipeline

Tests:
1. Stamper engine (stamp_pdf) with real assets
2. API endpoints (workspaces, workspace_scan, mark_complete, stamp_pdf)
3. Drive UI Hacker methods existence
"""
import sys
import os
import json
import tempfile

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

PASS = 0
FAIL = 0

def ok(name):
    global PASS
    PASS += 1
    print(f"  ✅ {name}")

def fail(name, reason=""):
    global FAIL
    FAIL += 1
    print(f"  ❌ {name} — {reason}")


# ============================================================
# TEST 1: Stamper Engine
# ============================================================
print("\n🧪 TEST 1: Stamper Engine")
print("-" * 40)

try:
    from pdf_tools.stamper import stamp_pdf, _DEFAULT_STAMP_PATH, _DEFAULT_SEAL_PATH
    ok("Import stamp_pdf")
except Exception as e:
    fail("Import stamp_pdf", str(e))

# Check assets exist
if _DEFAULT_STAMP_PATH.exists():
    ok(f"Asset exists: {_DEFAULT_STAMP_PATH.name}")
else:
    fail(f"Asset missing: {_DEFAULT_STAMP_PATH}")

if _DEFAULT_SEAL_PATH.exists():
    ok(f"Asset exists: {_DEFAULT_SEAL_PATH.name}")
else:
    fail(f"Asset missing: {_DEFAULT_SEAL_PATH}")

# Test stamping a real PDF
try:
    import fitz
    # Create a dummy 3-page PDF
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page(width=595, height=842)  # A4
        page.insert_text((72, 72), f"Test Page {i+1}", fontsize=24)
    
    tmp_input = os.path.join(tempfile.gettempdir(), "test_input.pdf")
    tmp_output = os.path.join(tempfile.gettempdir(), "test_stamped.pdf")
    doc.save(tmp_input)
    doc.close()
    
    result = stamp_pdf(tmp_input, tmp_output)
    
    if os.path.isfile(tmp_output):
        stamped = fitz.open(tmp_output)
        if len(stamped) == 3:
            ok(f"Stamped PDF: 3 pages, {os.path.getsize(tmp_output)} bytes")
        else:
            fail("Stamped PDF page count", f"Expected 3, got {len(stamped)}")
        stamped.close()
    else:
        fail("Stamped PDF not created")
    
    # Cleanup
    os.remove(tmp_input)
    os.remove(tmp_output)
    
except Exception as e:
    fail("Stamp PDF test", str(e))


# ============================================================
# TEST 2: Flask API Endpoints
# ============================================================
print("\n🧪 TEST 2: API Endpoints Registration")
print("-" * 40)

try:
    from flask import Flask
    app = Flask(__name__)
    from routes.splitter_translate import splitter_translate_bp
    app.register_blueprint(splitter_translate_bp)
    
    rules = {r.rule for r in app.url_map.iter_rules()}
    
    expected_routes = [
        "/api/translate/workspaces",
        "/api/translate/workspace_scan",
        "/api/translate/mark_complete",
        "/api/translate/stamp_pdf",
        "/api/translate/stamp_and_push",
    ]
    
    for route in expected_routes:
        if route in rules:
            ok(f"Route registered: {route}")
        else:
            fail(f"Route missing: {route}")
            
except Exception as e:
    fail("Flask API setup", str(e))


# ============================================================
# TEST 3: Drive UI Hacker Methods
# ============================================================
print("\n🧪 TEST 3: Drive UI Hacker Methods")
print("-" * 40)

try:
    from sync.drive_ui_hacker import DriveUIHacker
    
    required_methods = [
        "mark_done_translating",
        "rename_file",
        "upload_file",
        "upload_file_to_folder",
    ]
    
    for method in required_methods:
        if hasattr(DriveUIHacker, method):
            ok(f"Method exists: DriveUIHacker.{method}")
        else:
            fail(f"Method missing: DriveUIHacker.{method}")

except Exception as e:
    fail("DriveUIHacker import", str(e))


# ============================================================
# TEST 4: Config
# ============================================================
print("\n🧪 TEST 4: Configuration")
print("-" * 40)

try:
    from config import Config
    ws_dir = getattr(Config, "TRANSLATION_WORKSPACE_DIR", None)
    if ws_dir:
        ok(f"TRANSLATION_WORKSPACE_DIR = '{ws_dir}'")
    else:
        fail("TRANSLATION_WORKSPACE_DIR not set")
except Exception as e:
    fail("Config import", str(e))


# ============================================================
# TEST 5: Frontend JS Files
# ============================================================
print("\n🧪 TEST 5: Frontend Files")
print("-" * 40)

frontend_files = [
    "frontend/js/workspace.js",
    "frontend/index.html",
]

for f in frontend_files:
    if os.path.isfile(f):
        size = os.path.getsize(f)
        ok(f"{f} ({size} bytes)")
    else:
        fail(f"Missing: {f}")

# Check workspace.js has required functions
with open("frontend/js/workspace.js", "r", encoding="utf-8") as f:
    ws_content = f.read()

required_functions = [
    "loadTranslationWorkspaces",
    "runWorkspaceScan",
    "markWorkspaceComplete",
    "stampAndPushToDrive",
]
for fn in required_functions:
    if f"function {fn}" in ws_content:
        ok(f"Function defined: {fn}()")
    else:
        fail(f"Function missing: {fn}()")

# Check workspace.js does NOT have the removed duplicate
if "workspaceCreateTranslateStreams" in ws_content:
    fail("Dead code still present: workspaceCreateTranslateStreams")
else:
    ok("No dead code: workspaceCreateTranslateStreams removed")

if "_originalBulkCreateStreams" in ws_content:
    fail("Dead code still present: _originalBulkCreateStreams")
else:
    ok("No dead code: _originalBulkCreateStreams removed")

# Check translation.js has workspace mode detection
with open("frontend/js/translation.js", "r", encoding="utf-8") as f:
    tr_content = f.read()

if "isWorkspaceMode" in tr_content:
    ok("bulkCreateTranslateStreams has workspace mode detection")
else:
    fail("bulkCreateTranslateStreams missing workspace mode detection")

# Check index.html has workspace.js script
with open("frontend/index.html", "r", encoding="utf-8") as f:
    html_content = f.read()

if 'src="js/workspace.js"' in html_content:
    ok("workspace.js included in index.html")
else:
    fail("workspace.js NOT included in index.html")


# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 50)
total = PASS + FAIL
print(f"📊 Kết quả: {PASS}/{total} tests đạt")
if FAIL > 0:
    print(f"❌ {FAIL} test không đạt")
else:
    print("✅ TẤT CẢ TESTS ĐẠT!")
print("=" * 50)
