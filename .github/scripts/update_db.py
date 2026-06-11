#!/usr/bin/env python3
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data"

combined = {"483": [], "warning_letters": [], "fetched_at": None}

log_file = DATA_DIR / "483_download_log.json"
if log_file.exists():
    combined["483"] = json.loads(log_file.read_text())

wl_file = DATA_DIR / "wl_new_records.json"
if wl_file.exists():
    combined["warning_letters"] = json.loads(wl_file.read_text())

for entry in combined["483"]:
    pdf = DATA_DIR / "483_pdfs" / f"{entry.get('name','')}.pdf"
    if pdf.exists():
        entry["pdf_size_kb"] = pdf.stat().st_size // 1024

from datetime import datetime
combined["fetched_at"] = datetime.utcnow().isoformat()

output_path = DATA_DIR / "fda_combined.json"
output_path.write_text(json.dumps(combined, indent=2, ensure_ascii=False))
print(f"483: {len(combined['483'])} | WL: {len(combined['warning_letters'])} | Output: {output_path}")
