#!/usr/bin/env python3
"""
Fetch FDA 483 PDFs from known CDER FOIA links.
Also attempts to discover new 483 PDFs via FDA search API.

Known 483 PDFs are hardcoded because the OII FOIA page is blocked by Akamai.
We check for new PDFs by querying FDA search API.
"""
import httpx, json, os, time, re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data"
OUT_DIR = DATA_DIR / "483_pdfs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.fda.gov/drugs/cder-foia-electronic-reading-room",
    "Accept": "application/pdf,*/*",
}

client = httpx.Client(follow_redirects=True, timeout=60, headers=HEADERS)

# Known 483 PDF URLs (verified working)
KNOWN_PDFS = [
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

# Known CDER FOIA 483 PDF IDs from our tracking
KNOWN_MEDIA_IDS = {url.split("/")[-2] for _, url in KNOWN_PDFS if "/media/" in url}


def try_download(name, url, force=False):
    """Download a PDF if not already present."""
    pdf_path = OUT_DIR / f"{name}.pdf"
    
    if pdf_path.exists() and pdf_path.stat().st_size > 1000 and not force:
        return {"name": name, "status": "skipped", "size": pdf_path.stat().st_size // 1024}
    
    print(f"  DOWNLOAD {name}...", end=" ", flush=True)
    try:
        time.sleep(1.5)
        resp = client.get(url)
        if len(resp.content) > 1000:
            pdf_path.write_bytes(resp.content)
            size_kb = len(resp.content) // 1024
            print(f"OK ({size_kb}KB)")
            return {"name": name, "status": "ok", "size": size_kb}
        else:
            print(f"EMPTY ({len(resp.content)}b)")
            return {"name": name, "status": "empty"}
    except Exception as e:
        print(f"ERROR: {e}")
        return {"name": name, "status": "error", "error": str(e)}


def search_new_483s():
    """
    Attempt to discover new 483 PDFs via FDA search API.
    FDA search at /drugs/cder-foia-electronic-reading-room may list new PDFs.
    
    Returns list of (name, url) tuples for new PDFs found.
    """
    new_finds = []
    
    # Approach 1: Check FDA.gov search for new 483 entries
    search_urls = [
        "https://www.fda.gov/drugs/cder-foia-electronic-reading-room",
    ]
    
    for search_url in search_urls:
        try:
            time.sleep(2)
            resp = client.get(search_url)
            html = resp.text
            
            if "apology" in html[:500].lower():
                continue
            
            # Find links to /media/XXXX/download - these are FDA media file links
            media_links = re.findall(r'href="(/media/(\d+)/download)"', html)
            for full_path, media_id in media_links:
                if media_id not in KNOWN_MEDIA_IDS:
                    # Check surrounding context for company name
                    context_match = re.search(
                        r'(?:>([^<]{10,80})<)[^<]*href="/media/' + re.escape(media_id) + r'/download"',
                        html
                    )
                    name = context_match.group(1).strip() if context_match else f"Media_{media_id}"
                    name_clean = re.sub(r'[^a-zA-Z0-9_-]+', '_', name).strip('_')
                    full_url = f"https://www.fda.gov{full_path}"
                    new_finds.append((name_clean, full_url))
                    print(f"  Found NEW: {name_clean} ({full_url})")
            
        except Exception as e:
            print(f"  Search failed for {search_url}: {e}")
    
    return new_finds


# ===== MAIN =====
results = []

print("=== Phase 1: Known 483 PDFs ===")
for name, url in KNOWN_PDFS:
    result = try_download(name, url)
    results.append(result)

print(f"\n=== Phase 2: Search for new 483 PDFs ===")
new_pdfs = search_new_483s()
for name, url in new_pdfs:
    result = try_download(name, url, force=True)
    results.append(result)
    # Add to known for future runs
    if url not in [u for _, u in KNOWN_PDFS]:
        pass  # Will be tracked in the JSON output

ok = sum(1 for r in results if r["status"] == "ok")
skipped = sum(1 for r in results if r["status"] == "skipped")
print(f"\nDone: {ok} new, {skipped} skipped / {len(results)} total")

# Write download log
(DATA_DIR / "483_download_log.json").write_text(json.dumps(results, indent=2))
