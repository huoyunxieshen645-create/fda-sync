     1|#!/usr/bin/env python3
     2|"""
     3|Fetch FDA Form 483 PDFs from known /media/ URLs
     4|Runs on GitHub Actions (US IP, no Akamai blocking)
     5|"""
     6|import httpx, re, json, os, time
     7|from pathlib import Path
     8|
     9|# 输出到仓库根目录的 data/
    10|REPO_ROOT = Path(__file__).resolve().parent.parent.parent
    11|OUT_DIR = REPO_ROOT / "data" / "483_pdfs"
    12|OUT_DIR.mkdir(parents=True, exist_ok=True)
    13|
    14|PDFS = [
    15|    ("Pyramid_Laboratories", "https://www.fda.gov/media/90793/download"),
    16|    ("Kenvue_Brands", "https://www.fda.gov/media/79258/download"),
    17|    ("Excel_Vision", "https://www.fda.gov/media/192522/download"),
    18|    ("Wyeth_Pharmaceutical", "https://www.fda.gov/media/70960/download"),
    19|    ("Sato_Pharmaceutical", "https://www.fda.gov/media/190676/download"),
    20|    ("Eagle_Analytical", "https://www.fda.gov/media/86611/download"),
    21|    ("Actavis_Laboratories", "https://www.fda.gov/media/70106/download"),
    22|    ("Jubilant_HollisterStier", "https://www.fda.gov/media/187949/download"),
    23|    ("ENDO_USA", "https://www.fda.gov/media/89554/download"),
    24|    ("Baxter_Healthcare", "https://www.fda.gov/media/78340/download"),
    25|    ("Simtra_Deutschland", "https://www.fda.gov/media/190881/download"),
    26|    ("ProRx_LLC", "https://www.fda.gov/media/190142/download"),
    27|    ("Grato_Holdings", "https://www.fda.gov/media/69958/download"),
    28|    ("Lupin_Limited", "https://www.fda.gov/media/190665/download"),
    29|    ("Fareva_Amboise", "https://www.fda.gov/media/189752/download"),
    30|    ("Central_Admixture_Pharmacy", "https://www.fda.gov/media/189889/download"),
    31|    ("FarmaKeio_Compounding", "https://www.fda.gov/media/189832/download"),
    32|]
    33|
    34|HEADERS = {
    35|    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    36|    "Referer": "https://www.fda.gov/drugs/cder-foia-electronic-reading-room",
    37|    "Accept": "application/pdf,*/*",
    38|}
    39|
    40|client = httpx.Client(follow_redirects=True, timeout=60, headers=HEADERS)
    41|
    42|results = []
    43|for name, url in PDFS:
    44|    pdf_path = OUT_DIR / f"{name}.pdf"
    45|    
    46|    if pdf_path.exists() and pdf_path.stat().st_size > 1000:
    47|        print(f"  SKIP {name} (exists)")
    48|        results.append({"name": name, "status": "skipped"})
    49|        continue
    50|    
    51|    print(f"  DOWNLOAD {name}...", end=" ", flush=True)
    52|    try:
    53|        time.sleep(1.5)
    54|        resp = client.get(url)
    55|        if len(resp.content) > 1000:
    56|            pdf_path.write_bytes(resp.content)
    57|            print(f"OK ({len(resp.content)//1024}KB)")
    58|            results.append({"name": name, "status": "ok", "size": len(resp.content)})
    59|        else:
    60|            print(f"EMPTY ({len(resp.content)} bytes)")
    61|            results.append({"name": name, "status": "empty"})
    62|    except Exception as e:
    63|        print(f"ERROR: {e}")
    64|        results.append({"name": name, "status": "error", "error": str(e)})
    65|
    66|ok = sum(1 for r in results if r["status"] == "ok")
    67|print(f"\nDone: {ok} OK, {len(results)-ok} failed/skipped")
    68|
    69|(REPO_ROOT / "data" / "483_download_log.json").write_text(json.dumps(results, indent=2))
    70|