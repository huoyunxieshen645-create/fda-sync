#!/usr/bin/env python3
import httpx, json, os, time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = REPO_ROOT / "data" / "483_pdfs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.fda.gov/drugs/cder-foia-electronic-reading-room",
    "Accept": "application/pdf,*/*",
}

client = httpx.Client(follow_redirects=True, timeout=60, headers=HEADERS)
results = []

for name, url in PDFS:
    pdf_path = OUT_DIR / f"{name}.pdf"
    if pdf_path.exists() and pdf_path.stat().st_size > 1000:
        print(f"SKIP {name} (exists)")
        results.append({"name": name, "status": "skipped"})
        continue
    print(f"DOWNLOAD {name}...", end=" ", flush=True)
    try:
        time.sleep(1.5)
        resp = client.get(url)
        if len(resp.content) > 1000:
            pdf_path.write_bytes(resp.content)
            print(f"OK ({len(resp.content)//1024}KB)")
            results.append({"name": name, "status": "ok", "size": len(resp.content)})
        else:
            print(f"EMPTY ({len(resp.content)}b)")
            results.append({"name": name, "status": "empty"})
    except Exception as e:
        print(f"ERROR: {e}")
        results.append({"name": name, "status": "error", "error": str(e)})

ok = sum(1 for r in results if r["status"] == "ok")
print(f"\nDone: {ok}/{len(results)} OK")
(REPO_ROOT / "data" / "483_download_log.json").write_text(json.dumps(results, indent=2))
