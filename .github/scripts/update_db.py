#!/usr/bin/env python3
"""
Combine collected data into fda_combined.json.
Merges 483 download log + new 483 found data + WL new records into a single JSON file.

Now includes full 483 text extraction for new discoveries.
"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data"

combined = {"483": [], "483_new": [], "warning_letters": [], "fetched_at": None}

# 1. Load 483 download log (known PDFs)
log_file = DATA_DIR / "483_download_log.json"
if log_file.exists():
    combined["483"] = json.loads(log_file.read_text())

# 2. Load new 483 findings with full text
new_file = DATA_DIR / "483_new_found.json"
if new_file.exists():
    combined["483_new"] = json.loads(new_file.read_text())

# 3. Load WL new records
wl_file = DATA_DIR / "wl_new_records.json"
if wl_file.exists():
    combined["warning_letters"] = json.loads(wl_file.read_text())

# 4. Timestamp
from datetime import datetime
combined["fetched_at"] = datetime.utcnow().isoformat()

# 5. Write combined JSON
output_path = DATA_DIR / "fda_combined.json"
output_path.write_text(json.dumps(combined, indent=2, ensure_ascii=False))

print(f"483 known: {len(combined['483'])} | 483 new: {len(combined['483_new'])} | WL: {len(combined['warning_letters'])}")
print(f"  Output: {output_path}")
print(f"  Fetched at: {combined['fetched_at']}")
