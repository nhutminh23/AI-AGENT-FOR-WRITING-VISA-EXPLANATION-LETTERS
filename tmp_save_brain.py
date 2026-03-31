import json
import os
from datetime import datetime, timezone

def update_brain_and_session():
    brain_path = '.brain/brain.json'
    session_path = '.brain/session.json'

    # Load brain.json
    try:
        with open(brain_path, 'r', encoding='utf-8') as f:
            brain_data = json.load(f)
    except FileNotFoundError:
        brain_data = {
            "meta": {"schema_version": "1.1.0", "awf_version": "3.3.0"},
            "project": {"name": "AI Agent Visa Info", "type": "backend", "status": "active"},
            "tech_stack": {},
            "database_schema": {"tables": [], "relationships": []},
            "api_endpoints": [],
            "business_rules": [],
            "features": [],
            "knowledge_items": {"patterns": [], "gotchas": [], "conventions": []}
        }
    
    # Update brain.json gotchas (if not already there)
    gotchas = brain_data.get("knowledge_items", {}).get("gotchas", [])
    new_gotcha = "Khi điền PDF có ký tự rỗng (như dấu / cho ngày tháng), KHÔNG ĐƯỢC để thư viện điền form (pypdf) fill field ngày tháng, nếu không chữ sẽ bị in bóng (ghost text) qua annotation layer. Thay vào đó, dùng PyMuPDF vẽ rectangle đè lên và vẽ chữ trực tiếp lên page content layer."
    if new_gotcha not in gotchas:
        if "knowledge_items" not in brain_data:
            brain_data["knowledge_items"] = {"patterns": [], "gotchas": [], "conventions": []}
        if "gotchas" not in brain_data["knowledge_items"]:
            brain_data["knowledge_items"]["gotchas"] = []
        brain_data["knowledge_items"]["gotchas"].append(new_gotcha)
        
    with open(brain_path, 'w', encoding='utf-8') as f:
        json.dump(brain_data, f, indent=2, ensure_ascii=False)

    # Load session.json
    try:
        with open(session_path, 'r', encoding='utf-8') as f:
            session_data = json.load(f)
    except FileNotFoundError:
        session_data = {
            "updated_at": "",
            "working_on": {},
            "pending_tasks": [],
            "recent_changes": [],
            "errors_encountered": [],
            "decisions_made": []
        }
    
    now = datetime.now(timezone.utc).isoformat()
    session_data["updated_at"] = now
    
    # Append recent change
    session_data["recent_changes"].append({
        "timestamp": now,
        "type": "bugfix",
        "description": "Fix bug duplicate text/slashes rendering tren PDF form 54 bang cach dung fitz ve truc tiep text+background trang de lap len ky tu /, dong thoi update /V va /AS property dung on-state ('/visitor (600)') de trick checkbox visa",
        "files": ["australia_forms/fill_54.py"]
    })
    
    session_data["working_on"] = {
        "feature": "Bugfix PDF Rendering",
        "task": "Fixed double text and checkbox tick on Australia form 54",
        "status": "completed",
        "files": ["australia_forms/fill_54.py"],
        "blockers": [],
        "notes": ""
    }
    
    session_data["decisions_made"].append({
        "decision": "Drop pypdf text fill for date fields completely, manually paint date fields using fitz to fix dual-layer rendering ghosting bugs",
        "reason": "PDF template format sets static background slashes causing overlapping elements"
    })
    
    session_data["errors_encountered"].append({
        "error": "Set checkbox value as '/Yes' didn't visibly tick the box",
        "solution": "Found the actual AP/N states are /visitor (600) and /other. Set /V and kid /AS to '/visitor (600)' instead of '/Yes'",
        "resolved": True
    })

    with open(session_path, 'w', encoding='utf-8') as f:
        json.dump(session_data, f, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    update_brain_and_session()
