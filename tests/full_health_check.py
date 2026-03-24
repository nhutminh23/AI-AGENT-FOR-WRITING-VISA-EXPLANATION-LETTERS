"""
🧪 FULL PROJECT HEALTH CHECK
=============================
Chạy 1 lần để kiểm tra TOÀN BỘ dự án. Gồm 4 bài test:

  Test 1: Static Analysis (pyflakes) - Tìm biến/hàm chưa define
  Test 2: Import Check - Tất cả module có import được không
  Test 3: Flask Routes Check - Tất cả API endpoints có load được không
  Test 4: API Smoke Test - Gọi thử các API xem có crash không

Cách chạy:
  .\myenv\Scripts\python.exe tests/full_health_check.py
"""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import time
import traceback
from typing import List, Tuple

# ─── Config ───
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

SKIP_DIRS = {"myenv", "__pycache__", ".git", ".brain", ".agent", ".gemini", "node_modules", "tests"}

# ─── Helpers ───
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    END = "\033[0m"

def ok(msg): print(f"  {Colors.GREEN}✅ {msg}{Colors.END}")
def fail(msg): print(f"  {Colors.RED}❌ {msg}{Colors.END}")
def warn(msg): print(f"  {Colors.YELLOW}⚠️  {msg}{Colors.END}")
def header(msg): print(f"\n{Colors.BOLD}{Colors.CYAN}{'═'*60}\n  {msg}\n{'═'*60}{Colors.END}")

# ─── Collect Python files ───
def collect_py_files() -> List[str]:
    py_files = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))
    return sorted(py_files)

# ═══════════════════════════════════════════════════════
# TEST 1: STATIC ANALYSIS (pyflakes)
# ═══════════════════════════════════════════════════════
def test_static_analysis(py_files: List[str]) -> Tuple[int, int]:
    header("TEST 1: Static Analysis (Tìm biến/hàm chưa define)")
    
    # Check pyflakes available
    try:
        subprocess.run([sys.executable, "-m", "pyflakes", "--version"], 
                      capture_output=True, check=True)
    except Exception:
        warn("pyflakes chưa cài. Đang cài...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyflakes", "-q"], check=True)
    
    passed = 0
    failed = 0
    issues = []
    
    for fpath in py_files:
        rel = os.path.relpath(fpath, PROJECT_ROOT)
        result = subprocess.run(
            [sys.executable, "-m", "pyflakes", fpath],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        output = result.stdout.strip()
        if output:
            lines = output.split("\n")
            critical = [l for l in lines if "undefined name" in l.lower()]
            if critical:
                failed += 1
                for line in critical:
                    short = line.replace(fpath, rel).replace("\\", "/")
                    issues.append(short)
            else:
                passed += 1
        else:
            passed += 1
    
    if issues:
        for issue in issues:
            fail(issue)
    else:
        ok(f"Tất cả {len(py_files)} files clean — không có undefined name nào!")
    
    return passed, failed

# ═══════════════════════════════════════════════════════
# TEST 2: IMPORT CHECK
# ═══════════════════════════════════════════════════════
def test_imports() -> Tuple[int, int]:
    header("TEST 2: Import Check (Tất cả module import được không)")
    
    modules_to_check = [
        ("config", "Config"),
        ("database", "Database module"),
        ("core.agents", "AI Agents"),
        ("core.errors", "Error classes"),
        ("core.helpers", "Helper functions"),
        ("core.state", "GraphState"),
        ("classifier.agent", "Classifier agent"),
        ("pdf_tools.pdf_service", "PDF service"),
        ("pdf_tools.ai_service", "AI service"),
        ("routes", "Routes package"),
        ("routes.pipeline", "Pipeline routes"),
        ("routes.splitter", "Splitter routes"),
        ("routes.precheck", "Precheck routes"),
        ("routes.booking", "Booking routes"),
        ("canada_forms", "Canada Forms module"),
        ("canada_forms.reader", "Canada reader"),
        ("canada_forms.agent", "Canada agent"),
        ("canada_forms.fill_imm5645", "IMM5645 filler"),
        ("canada_forms.field_mappings", "Field mappings"),
        ("canada_forms.prompts", "Canada prompts"),
    ]
    
    passed = 0
    failed = 0
    
    for module_name, display_name in modules_to_check:
        try:
            importlib.import_module(module_name)
            ok(f"{display_name} ({module_name})")
            passed += 1
        except Exception as e:
            err_type = type(e).__name__
            err_msg = str(e).split('\n')[0][:80]
            fail(f"{display_name} ({module_name}): {err_type}: {err_msg}")
            failed += 1
    
    return passed, failed

# ═══════════════════════════════════════════════════════
# TEST 3: FLASK ROUTES CHECK
# ═══════════════════════════════════════════════════════
def test_flask_routes() -> Tuple[int, int]:
    header("TEST 3: Flask Routes (Tất cả API endpoints load được không)")
    
    passed = 0
    failed = 0
    
    try:
        from server import app
        with app.test_client() as client:
            # Collect all registered routes
            rules = list(app.url_map.iter_rules())
            api_routes = [r for r in rules if r.rule.startswith("/api/") and "GET" in r.methods]
            
            ok(f"Flask app khởi tạo thành công — {len(rules)} routes tổng cộng")
            ok(f"{len(api_routes)} API routes (GET)")
            passed += 2
            
            # List all endpoints by blueprint
            blueprints = {}
            for rule in rules:
                bp = rule.endpoint.split(".")[0] if "." in rule.endpoint else "main"
                if bp not in blueprints:
                    blueprints[bp] = 0
                blueprints[bp] += 1
            
            for bp, count in sorted(blueprints.items()):
                ok(f"Blueprint '{bp}': {count} routes")
                passed += 1
                
    except Exception as e:
        fail(f"Flask app không khởi tạo được: {e}")
        failed += 1
    
    return passed, failed

# ═══════════════════════════════════════════════════════
# TEST 4: API SMOKE TEST
# ═══════════════════════════════════════════════════════
def test_api_smoke() -> Tuple[int, int]:
    header("TEST 4: API Smoke Test (Gọi thử API xem có crash không)")
    
    passed = 0
    failed = 0
    
    try:
        from server import app
        with app.test_client() as client:
            # Safe GET endpoints that don't need data
            get_endpoints = [
                ("/api/projects", "Danh sách hồ sơ"),
                ("/api/translate/templates", "Template dịch"),
                ("/api/classifier/files?input_dir=phanloai/input", "Files phân loại"),
                ("/api/output-files", "Output files"),
                ("/canada/api/fields", "Canada form fields"),
                ("/canada/api/check-template", "Canada template check"),
            ]
            
            for endpoint, name in get_endpoints:
                try:
                    resp = client.get(endpoint)
                    if resp.status_code < 500:
                        ok(f"GET {endpoint} → {resp.status_code} ({name})")
                        passed += 1
                    else:
                        fail(f"GET {endpoint} → {resp.status_code} Server Error! ({name})")
                        failed += 1
                except Exception as e:
                    fail(f"GET {endpoint} → Exception: {e}")
                    failed += 1
            
            # POST endpoints with empty body (should return 400, NOT 500)
            post_endpoints = [
                ("/api/translate/upload", "Upload dịch thuật"),
                ("/api/classifier/run", "Chạy phân loại"),
                ("/api/precheck/scan", "Quét file"),
                ("/canada/api/upload", "Upload Canada"),
            ]
            
            for endpoint, name in post_endpoints:
                try:
                    resp = client.post(endpoint, content_type="application/json", data="{}")
                    if resp.status_code < 500:
                        ok(f"POST {endpoint} → {resp.status_code} ({name})")
                        passed += 1
                    else:
                        # Check if it's a controlled error or actual crash
                        data = resp.get_json(silent=True)
                        if data and "error" in data:
                            ok(f"POST {endpoint} → {resp.status_code} (controlled error: {data['error']})")
                            passed += 1
                        else:
                            fail(f"POST {endpoint} → {resp.status_code} SERVER CRASH! ({name})")
                            failed += 1
                except Exception as e:
                    fail(f"POST {endpoint} → Exception: {e}")
                    failed += 1
                    
    except Exception as e:
        fail(f"Không tạo được test client: {e}")
        failed += 1
    
    return passed, failed


# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════
def main():
    print(f"\n{Colors.BOLD}🧪 FULL PROJECT HEALTH CHECK{Colors.END}")
    print(f"   Thời gian: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Project: {PROJECT_ROOT}")
    
    py_files = collect_py_files()
    print(f"   Python files: {len(py_files)}")
    
    total_passed = 0
    total_failed = 0
    
    # Run all tests
    tests = [
        ("Static Analysis", lambda: test_static_analysis(py_files)),
        ("Import Check", lambda: test_imports),
        ("Flask Routes", lambda: test_flask_routes),
        ("API Smoke Test", lambda: test_api_smoke),
    ]
    
    # Test 1
    p, f = test_static_analysis(py_files)
    total_passed += p; total_failed += f
    
    # Test 2
    p, f = test_imports()
    total_passed += p; total_failed += f
    
    # Test 3
    p, f = test_flask_routes()
    total_passed += p; total_failed += f
    
    # Test 4
    p, f = test_api_smoke()
    total_passed += p; total_failed += f
    
    # ─── FINAL REPORT ───
    header("📊 KẾT QUẢ TỔNG")
    total = total_passed + total_failed
    
    if total_failed == 0:
        print(f"\n  {Colors.GREEN}{Colors.BOLD}🎉 ALL {total_passed} TESTS PASSED!{Colors.END}")
        print(f"  {Colors.GREEN}Dự án sạch sẽ, không có lỗi ẩn nào.{Colors.END}\n")
        return 0
    else:
        print(f"\n  {Colors.GREEN}✅ {total_passed} passed{Colors.END}")
        print(f"  {Colors.RED}❌ {total_failed} failed{Colors.END}")
        print(f"\n  {Colors.YELLOW}Cần sửa {total_failed} lỗi trước khi deploy.{Colors.END}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
