import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from docx_reader import read_all_input_files, read_notes
from agent import run_agent
from config_injector import inject_configs, SCRIPT_ORDER

BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
SCRIPT_DIR = BASE_DIR / "script"
NOTES_PATH = BASE_DIR / "notes.md"

app = FastAPI(title="DS-160 Auto Config Generator")

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "frontend")), name="static")
app.mount("/assets", StaticFiles(directory=str(BASE_DIR / "assets")), name="assets")


@app.get("/")
async def serve_index():
    return FileResponse(str(BASE_DIR / "frontend" / "index.html"))


@app.get("/api/check-input")
async def check_input():
    """Kiểm tra thư mục /input có file .docx hoặc .pdf không."""
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    input_files = []
    for ext in ("*.docx", "*.pdf"):
        input_files.extend(INPUT_DIR.glob(ext))
    input_files = [f for f in input_files if not f.name.startswith("~$")]
    return {
        "hasFiles": len(input_files) > 0,
        "files": [f.name for f in input_files],
        "count": len(input_files),
    }


@app.get("/api/output")
async def get_saved_output():
    """Lấy kết quả đã lưu từ /output (nếu có)."""
    configs_path = OUTPUT_DIR / "configs.json"
    if not configs_path.exists():
        return JSONResponse(
            status_code=404,
            content={"detail": "Chưa có kết quả đã lưu. Hãy nhấn 'Xử lý dữ liệu' trước."},
        )

    configs = json.loads(configs_path.read_text(encoding="utf-8"))

    results = []
    for filename, config_key, display_name in SCRIPT_ORDER:
        script_path = OUTPUT_DIR / filename
        full_script = ""
        if script_path.exists():
            full_script = script_path.read_text(encoding="utf-8")

        results.append({
            "filename": filename,
            "configKey": config_key,
            "displayName": display_name,
            "config": configs.get(config_key, {}),
            "fullScript": full_script,
        })

    return {"scripts": results, "source": "saved"}


@app.post("/api/process")
async def process_data():
    """Xử lý chính: đọc file input -> AI -> inject -> trả kết quả."""
    INPUT_DIR.mkdir(parents=True, exist_ok=True)

    input_files = read_all_input_files(str(INPUT_DIR))
    if not input_files:
        raise HTTPException(
            status_code=400,
            detail="Không tìm thấy file .docx hoặc .pdf nào trong thư mục /input. Hãy đặt file vào thư mục input/.",
        )

    docx_content_parts = []
    for fname, content in input_files.items():
        docx_content_parts.append(f"=== FILE: {fname} ===\n{content}")
    docx_content = "\n\n".join(docx_content_parts)

    rules = read_notes(str(NOTES_PATH))

    try:
        configs = run_agent(docx_content, rules)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi gọi AI Agent: {str(e)}",
        )

    try:
        results = inject_configs(str(SCRIPT_DIR), configs, str(OUTPUT_DIR))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi inject config vào script: {str(e)}",
        )

    return {"scripts": results, "source": "generated"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.5", port=8008)
