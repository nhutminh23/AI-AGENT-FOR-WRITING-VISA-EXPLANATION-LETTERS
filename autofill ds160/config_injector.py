import json
import re
from pathlib import Path

SCRIPT_ORDER = [
    ("1. DS 160 - Personal 1.js", "personal1", "1. Personal Information 1"),
    ("2. DS-160 - Personal 2.js", "personal2", "2. Personal Information 2"),
    ("3. DS 160 - Travel.js", "travel", "3. Travel Information"),
    ("4. DS 160 - Travel Companions.js", "travelCompanions", "4. Travel Companions"),
    ("5. DS 160 - Previous U.S. Travel.js", "previousUSTravel", "5. Previous U.S. Travel"),
    ("6. DS - 160 Address & Phone.js", "addressPhone", "6. Address & Phone"),
    ("7. DS 160 - Passport Information.js", "passport", "7. Passport Information"),
    ("8. DS 160 - U.S. Point of Contact.js", "usContact", "8. U.S. Point of Contact"),
    ("9. DS 160 - Family Information.js", "family", "9. Family Information"),
    ("9.1. DS 160 - Spouse.js", "spouse", "9.1. Spouse"),
    ("10. DS 160 Work-Education 1.js", "workEducation1", "10. Work/Education 1"),
    ("11. DS 160 Work-Education 2 .js", "workEducation2", "11. Work/Education 2"),
    ("12. DS 160 Work-Education 3-2026-03-05-v6.4.user.js", "workEducation3", "12. Work/Education 3"),
    ("DS 160 Security Part 1-2026-03-05.user.js", "securityPart1", "13. Security Part 1"),
    ("DS 160 Security Part 2-2026-03-05.user.js", "securityPart2", "14. Security Part 2"),
    ("DS 160 Security Part 3-2026-03-05.user.js", "securityPart3", "15. Security Part 3"),
    ("DS 160 Security Part 4-2026-03-05.user.js", "securityPart4", "16. Security Part 4"),
    ("DS 160 Security Part 5-2026-03-05.user.js", "securityPart5", "17. Security Part 5"),
]

CONFIG_PATTERN = re.compile(
    r"(const\s+config\s*=\s*)\{[\s\S]*?\};",
    re.MULTILINE,
)


def _json_to_js_object(obj, indent=8) -> str:
    """Chuyển Python dict/list thành chuỗi JS object literal."""
    raw = json.dumps(obj, ensure_ascii=False, indent=4)
    raw = raw.replace('"true"', "true").replace('"false"', "false")
    raw = re.sub(r': true\b', ": true", raw)
    raw = re.sub(r': false\b', ": false", raw)
    raw = re.sub(r': null\b', ": null", raw)

    lines = raw.split("\n")
    prefix = " " * indent
    result_lines = []
    for i, line in enumerate(lines):
        if i == 0:
            result_lines.append(line)
        else:
            result_lines.append(prefix + line)
    return "\n".join(result_lines)


def inject_configs(script_dir: str, configs: dict, output_dir: str) -> list[dict]:
    """Inject configs vào các script templates.
    Trả về list of { filename, configKey, displayName, config, fullScript }
    """
    script_path = Path(script_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    results = []

    for filename, config_key, display_name in SCRIPT_ORDER:
        filepath = script_path / filename
        if not filepath.exists():
            results.append({
                "filename": filename,
                "configKey": config_key,
                "displayName": display_name,
                "config": {},
                "fullScript": f"// LỖI: Không tìm thấy file {filename}",
            })
            continue

        template = filepath.read_text(encoding="utf-8")
        config_obj = configs.get(config_key, {})
        js_config_str = _json_to_js_object(config_obj)

        new_script = CONFIG_PATTERN.sub(
            lambda m: f"{m.group(1)}{js_config_str};",
            template,
            count=1,
        )

        out_file = output_path / filename
        out_file.write_text(new_script, encoding="utf-8")

        results.append({
            "filename": filename,
            "configKey": config_key,
            "displayName": display_name,
            "config": config_obj,
            "fullScript": new_script,
        })

    configs_json_path = output_path / "configs.json"
    configs_json_path.write_text(
        json.dumps(configs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return results
