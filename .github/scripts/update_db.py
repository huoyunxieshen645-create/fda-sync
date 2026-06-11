#!/usr/bin/env python3
"""
Merge fetched FDA data into combined JSON for Termux to pull
"""
import json
from pathlib import Path

DATA_DIR = Path("data")

combined = {
    "483": [],
    "warning_letters": [],
    "fetched_at": None,
}

# 合并 483 下载结果
log_file = DATA_DIR / "483_download_log.json"
if log_file.exists():
    combined["483"] = json.loads(log_file.read_text())

# 合并 WL
wl_file = DATA_DIR / "wl_new_records.json"
if wl_file.exists():
    combined["warning_letters"] = json.loads(wl_file.read_text())
    
# 按 PDF 是否实际存在补充文件信息
pdf_dir = DATA_DIR / "483_pdfs"
if pdf_dir.exists():
    for entry in combined["483"]:
        name = entry.get("name", "")
        pdf = pdf_dir / f"{name}.pdf"
        if pdf.exists():
            entry["pdf_size_kb"] = pdf.stat().st_size // 1024

from datetime import datetime
combined["fetched_at"] = datetime.utcnow().isoformat()

output_path = DATA_DIR / "fda_combined.json"
output_path.write_text(json.dumps(combined, indent=2, ensure_ascii=False))

print(f"483: {len(combined['483'])} records")
print(f"WL: {len(combined['warning_letters'])} records")
print(f"Output: {output_path}")
