#!/usr/bin/env python3
"""
Combine collected data into fda_combined.json.
Merges 483 download log + WL new records into a single JSON file.
"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data"

combined = {"483": [], "warning_letters": [], "fetched_at": None}

# 1. Load 483 download log
log_file = DATA_DIR / "483_download_log.json"
if log_file.exists():
    log_data = json.loads(log_file.read_text())
    # Enrich: add pdf_size_kb for each entry
    for entry in log_data:
        pdf = DATA_DIR / "483_pdfs" / f"{entry.get('name','')}.pdf"
        if pdf.exists():
            entry["pdf_size_kb"] = pdf.stat().st_size // 1024
    combined["483"] = log_data

# 2. Load WL new records (merge from individual files)
wl_file = DATA_DIR / "wl_new_records.json"
if wl_file.exists():
    combined["warning_letters"] = json.loads(wl_file.read_text())

# 3. Timestamp
from datetime import datetime
combined["fetched_at"] = datetime.utcnow().isoformat()

# 4. Write combined JSON
output_path = DATA_DIR / "fda_combined.json"
output_path.write_text(json.dumps(combined, indent=2, ensure_ascii=False))

print(f"483: {len(combined['483'])} | WL: {len(combined['warning_letters'])} | Output: {output_path}")
print(f"  Fetched at: {combined['fetched_at']}")
