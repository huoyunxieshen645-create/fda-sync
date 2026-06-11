#!/usr/bin/env python3
"""
Fetch FDA Form 483 PDFs from known /media/ URLs
Runs on GitHub Actions (US IP, no Akamai blocking)
"""
import httpx, re, json, os, time
from pathlib import Path

OUT_DIR = Path("data/483_pdfs")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 已知的 17 条 483 PDF
PDFS = [
    ("Pyramid_Laboratories", "https://www.fda.gov/media/90793/download"),
    ("Kenvue_Brands", "https://www.fda.gov/media/79258/download"),
    ("Excel_Vision", "https://www.fda.gov/media/192522/download"),
    ("Wyeth_Pharmaceutical", "https://www.fda.gov/media/70960/download"),
    ("Sato_Pharmaceutical", "https://www.fda.gov/media/190676/download"),
    ("Eagle_Analytical", "https://www.fda.gov/media/86611/download"),
    ("Actavis_Laboratories", "https://www.fda.gov/media/70106/download"),
    ("Jubilant_HollisterStier", "https://www.fda.gov/media/187949/download"),
    ("ENDO_USA", "https://www.fda.gov/media/89554/download"),
    ("Baxter_Healthcare", "https://www.fda.gov/media/78340/download"),
    ("Simtra_Deutschland", "https://www.fda.gov/media/190881/download"),
    ("ProRx_LLC", "https://www.fda.gov/media/190142/download"),
    ("Grato_Holdings", "https://www.fda.gov/media/69958/download"),
    ("Lupin_Limited", "https://www.fda.gov/media/190665/download"),
    ("Fareva_Amboise", "https://www.fda.gov/media/189752/download"),
    ("Central_Admixture_Pharmacy", "https://www.fda.gov/media/189889/download"),
    ("FarmaKeio_Compounding", "https://www.fda.gov/media/189832/download"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://www.fda.gov/drugs/cder-foia-electronic-reading-room",
    "Accept": "application/pdf,*/*",
}

client = httpx.Client(follow_redirects=True, timeout=60, headers=HEADERS)

results = []
for name, url in PDFS:
    pdf_path = OUT_DIR / f"{name}.pdf"
    txt_path = OUT_DIR / f"{name}.txt"
    
    # 跳过已下载的
    if pdf_path.exists():
        print(f"  SKIP {name} (already exists)")
        results.append({"name": name, "status": "skipped"})
        continue
    
    print(f"  DOWNLOAD {name}...", end=" ", flush=True)
    try:
        time.sleep(2)
        resp = client.get(url)
        if len(resp.content) > 1000:
            pdf_path.write_bytes(resp.content)
            # mutool 提取文本
            import subprocess
            r = subprocess.run(
                ["mutool", "draw", "-F", "text", str(pdf_path)],
                capture_output=True, text=True, timeout=30
            )
            txt_path.write_text(r.stdout)
            print(f"OK ({len(resp.content)//1024}KB, {len(r.stdout)} chars)")
            results.append({"name": name, "status": "ok", "size": len(resp.content)})
        else:
            print(f"BLOCKED ({len(resp.content)} bytes)")
            results.append({"name": name, "status": "blocked"})
    except Exception as e:
        print(f"ERROR: {e}")
        results.append({"name": name, "status": "error", "error": str(e)})

# 汇总
ok = sum(1 for r in results if r["status"] == "ok")
blocked = sum(1 for r in results if r["status"] == "blocked")
skipped = sum(1 for r in results if r["status"] == "skipped")
print(f"\nDone: {ok} OK, {blocked} blocked, {skipped} skipped, {len(results)} total")

# 保存结果清单
Path("data/483_download_log.json").write_text(json.dumps(results, indent=2))
