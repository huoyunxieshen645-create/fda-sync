#!/usr/bin/env python3
"""
Merge fetched FDA data into combined JSON for your Termux to pull
"""
import json, re
from pathlib import Path

DATA_DIR = Path("data")

combined = {
    "483": [],
    "warning_letters": [],
    "fetched_at": None,
}

# 1. 合并 483 PDF 文本
pdf_dir = DATA_DIR / "483_pdfs"
if pdf_dir.exists():
    for txt_file in sorted(pdf_dir.glob("*.txt")):
        name = txt_file.stem
        pdf_file = pdf_dir / f"{name}.pdf"
        text = txt_file.read_text()
        pdf_size = pdf_file.stat().st_size if pdf_file.exists() else 0
        
        # 尝试解析 observations
        observations = []
        parts = re.split(r'\n\s*OBSERVATION\s+(\d+)\s*\n', text)
        if len(parts) >= 3:
            i = 1
            while i < len(parts) - 1:
                obs_text = parts[i+1].strip()[:2000]
                # 提取法规
                clean = re.sub(r'\s+', ' ', obs_text)
                cites = set()
                for m in re.finditer(r'\d+\s+CFR\s+\d+\.?\d*[a-z]?\(?[^)\s]*\)?', clean, re.I):
                    c = m.group().strip().rstrip('.')
                    if 5 < len(c) < 30:
                        cites.add(c)
                observations.append({
                    "number": int(parts[i]),
                    "text": obs_text,
                    "citations": sorted(cites),
                })
                i += 2
        
        # 提取公司名
        firm = ""
        for m in re.finditer(r'(?:Inspected Firm|Establishment Name|Firm Name)[:\s]*\n\s*(.+?)(?:\n|$)', text, re.I):
            firm = m.group(1).strip()
            break
        
        combined["483"].append({
            "company": firm or name,
            "pdf_file": str(pdf_file),
            "pdf_size": pdf_size,
            "text_length": len(text),
            "observations": observations,
        })

# 2. 合并 WL
wl_file = DATA_DIR / "wl_new_records.json"
if wl_file.exists():
    combined["warning_letters"] = json.loads(wl_file.read_text())

# 3. 输出
from datetime import datetime
combined["fetched_at"] = datetime.utcnow().isoformat()

output_path = DATA_DIR / "fda_combined.json"
output_path.write_text(json.dumps(combined, indent=2, ensure_ascii=False))

print(f"483: {len(combined['483'])} records")
print(f"WL: {len(combined['warning_letters'])} records")
print(f"Output: {output_path} ({output_path.stat().st_size//1024}KB)")
