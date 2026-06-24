#!/usr/bin/env python3
"""
Fetch FDA 483 PDFs — Phase 2: try multiple HTTP clients to bypass Akamai.
"""
import httpx, json, os, time, re, subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data"
OUT_DIR = DATA_DIR / "483_pdfs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

client = httpx.Client(follow_redirects=True, timeout=60, headers=HEADERS)

# Known 483 PDF URLs (verified working)
KNOWN_PDFS = [
    (90793, "Pyramid_Laboratories", "https://www.fda.gov/media/90793/download"),
    (79258, "Kenvue_Brands", "https://www.fda.gov/media/79258/download"),
    (192522, "Excel_Vision", "https://www.fda.gov/media/192522/download"),
    (70960, "Wyeth_Pharmaceutical", "https://www.fda.gov/media/70960/download"),
    (190676, "Sato_Pharmaceutical", "https://www.fda.gov/media/190676/download"),
    (86611, "Eagle_Analytical", "https://www.fda.gov/media/86611/download"),
    (70106, "Actavis_Laboratories", "https://www.fda.gov/media/70106/download"),
    (187949, "Jubilant_HollisterStier", "https://www.fda.gov/media/187949/download"),
    (89554, "ENDO_USA", "https://www.fda.gov/media/89554/download"),
    (78340, "Baxter_Healthcare", "https://www.fda.gov/media/78340/download"),
    (190881, "Simtra_Deutschland", "https://www.fda.gov/media/190881/download"),
    (190142, "ProRx_LLC", "https://www.fda.gov/media/190142/download"),
    (69958, "Grato_Holdings", "https://www.fda.gov/media/69958/download"),
    (190665, "Lupin_Limited", "https://www.fda.gov/media/190665/download"),
    (189752, "Fareva_Amboise", "https://www.fda.gov/media/189752/download"),
    (189889, "Central_Admixture_Pharmacy", "https://www.fda.gov/media/189889/download"),
    (189832, "FarmaKeio_Compounding", "https://www.fda.gov/media/189832/download"),
]

TRACK_FILE = DATA_DIR / "known_media_ids.txt"

def load_tracked_ids():
    if not TRACK_FILE.exists():
        return set(str(mid) for mid, _, _ in KNOWN_PDFS)
    return set(TRACK_FILE.read_text().strip().split("\n")) | set(str(mid) for mid, _, _ in KNOWN_PDFS)

def save_tracked_ids(ids):
    TRACK_FILE.write_text("\n".join(sorted(ids)) + "\n")

def try_download(media_id, name, url, force=False):
    pdf_path = OUT_DIR / f"{name}.pdf"
    if pdf_path.exists() and pdf_path.stat().st_size > 1000 and not force:
        return {"media_id": media_id, "name": name, "status": "skipped", "size": pdf_path.stat().st_size // 1024}
    print(f"  DOWNLOAD {name} (media {media_id})...", end=" ", flush=True)
    try:
        time.sleep(2)
        resp = client.get(url)
        if len(resp.content) > 1000:
            pdf_path.write_bytes(resp.content)
            size_kb = len(resp.content) // 1024
            print(f"OK ({size_kb}KB)")
            return {"media_id": media_id, "name": name, "status": "ok", "size": size_kb}
        else:
            print(f"EMPTY ({len(resp.content)}b)")
            return {"media_id": media_id, "name": name, "status": "empty"}
    except Exception as e:
        print(f"ERROR: {e}")
        return {"media_id": media_id, "name": name, "status": "error", "error": str(e)}

# FOIA pages to scan
FOIA_PAGES = [
    "https://www.fda.gov/drugs/cder-foia-electronic-reading-room",
    "https://www.fda.gov/vaccines-blood-biologics/cber-foia-electronic-reading-room",
]

def try_with_curl(url):
    """Try curl (OpenSSL TLS fingerprint — different from httpx) to bypass Akamai."""
    try:
        r = subprocess.run(
            ["curl", "-s", "-L", "-m", "15",
             "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
             "-H", "Accept: text/html,*/*",
             url],
            capture_output=True, text=True, timeout=20
        )
        return r.stdout
    except Exception as e:
        print(f"    curl failed: {e}")
        return ""

def scan_foia_pages(tracked_ids):
    """Scan FOIA pages for new 483 PDF media IDs."""
    new_finds = []
    scan_log = []
    
    for url in FOIA_PAGES:
        label = url.rstrip("/").split("/")[-1][:30]
        print(f"  Scanning {label}...")
        
        # Try 1: httpx
        time.sleep(1)
        try:
            resp = client.get(url)
            html = resp.text
            print(f"    httpx: {len(html)} bytes")
        except Exception as e:
            html = ""
            print(f"    httpx failed: {e}")
        
        # Try 2: curl (OpenSSL fingerprint)
        curl_html = try_with_curl(url)
        if curl_html and len(curl_html) > len(html):
            print(f"    curl: {len(curl_html)} bytes (better!)")
            html = curl_html
        
        if len(html) < 1000:
            snippet = repr(html[:300])
            print(f"    Both failed — page too short ({len(html)}b): {snippet}")
            scan_log.append(f"{label}: FAILED ({len(html)}b) {snippet}")
            continue
        
        # Check if it's an Akamai block page
        if "apology" in html[:1000].lower() or "Just a moment" in html:
            print(f"    BLOCKED by Akamai")
            scan_log.append(f"{label}: BLOCKED ({len(html)}b)")
            continue
        
        # Parse media links
        media_links = set(re.findall(r'/media/(\d+)/download', html))
        pdf_links = re.findall(r'href="([^"]*\.pdf)"', html, re.I)
        print(f"    media links: {len(media_links)}, PDF links: {len(pdf_links)}")
        scan_log.append(f"{label}: OK ({len(html)}b, media={len(media_links)}, pdf={len(pdf_links)})")
        
        # Check each media link against tracked IDs
        for mid in sorted(media_links):
            if mid in tracked_ids:
                continue
            name = f"Media_{mid}"
            # Try to find company name in context
            cm = re.search(
                r'<td[^>]*>([^<]{10,120})</td>\s*<td[^>]*>[^<]*</td>\s*<td[^>]*>[^<]*</td>\s*<td[^>]*>[^<]*href="[^"]*/media/' + re.escape(mid) + r'/download"',
                html
            )
            if cm:
                name = cm.group(1).strip()
            name_clean = re.sub(r'[^a-zA-Z0-9_\-]+', '_', name)[:60].strip('_')
            full_url = f"https://www.fda.gov/media/{mid}/download"
            new_finds.append((mid, name_clean, full_url))
            print(f"    >> NEW 483: {name_clean} (media {mid})")
            tracked_ids.add(mid)
        
        # Also check direct PDF links
        for pl in pdf_links[:10]:
            print(f"    PDF: {pl[:100]}")
    
    # Write scan log to repo
    (DATA_DIR / "scan_summary.txt").write_text("\n".join(scan_log) + "\n")
    return new_finds

# ===== MAIN =====
tracked_ids = load_tracked_ids()
results = []

# Phase 1: Known PDFs
print("=== Phase 1: Known 483 PDFs ===")
for media_id, name, url in KNOWN_PDFS:
    result = try_download(str(media_id), name, url)
    results.append(result)

# Phase 2: Scan for new 483s
print("\n=== Phase 2: Scan FOIA pages ===")
new_finds = scan_foia_pages(tracked_ids)

if new_finds:
    print(f"\nFound {len(new_finds)} new 483 PDFs!")
    for mid, name, url in new_finds:
        result = try_download(mid, name, url, force=True)
        results.append(result)
    
    # Save enriched data
    enriched = []
    for mid, name, url in new_finds:
        pdf_path = OUT_DIR / f"{name}.pdf"
        info = {"media_id": mid, "name": name, "url": url}
        if pdf_path.exists() and pdf_path.stat().st_size > 1000:
            r2 = subprocess.run(["pdftotext", str(pdf_path), "-"], capture_output=True, text=True, timeout=15)
            text = r2.stdout
            if text:
                info["text_preview"] = text[:2000]
                # Parse basic info
                dm = re.search(r'(\d{1,2}/\d{1,2}/\d{4})\s*-?\s*(\d{1,2}/\d{1,2}/\d{4})', text)
                if dm:
                    info["inspection_start"] = dm.group(1)
                    info["inspection_end"] = dm.group(2)
                dates = re.findall(r'(\d{1,2}/\d{1,2}/\d{4})', text)
                if len(dates) >= 2:
                    info["issued_date"] = dates[-1]
                # Observations
                info["observations"] = []
                cur_obs = None
                cur_text = []
                for line in text.split("\n"):
                    m = re.match(r'OBSERVATION\s+(\d+)', line.strip(), re.I)
                    if m:
                        if cur_obs is not None:
                            info["observations"].append({"obs_number": cur_obs, "description": " ".join(cur_text)[:3000]})
                        cur_obs = int(m.group(1))
                        cur_text = []
                    elif cur_obs is not None:
                        cur_text.append(line.strip())
                if cur_obs is not None:
                    info["observations"].append({"obs_number": cur_obs, "description": " ".join(cur_text)[:3000]})
                # Citations
                cites = set()
                for m in re.finditer(r'\d+\s+CFR\s+\d+\.?\d*[a-z]?\(?[^)\s]*\)?', text, re.I):
                    c = m.group().strip().rstrip('.')
                    if len(c) > 5:
                        cites.add(c)
                info["citations"] = sorted(cites)
                info["pdf_size_kb"] = pdf_path.stat().st_size // 1024
        enriched.append(info)
    (DATA_DIR / "483_new_found.json").write_text(json.dumps(enriched, indent=2, ensure_ascii=False))
else:
    print("No new 483 PDFs found.")
    (DATA_DIR / "483_new_found.json").write_text("[]")

save_tracked_ids(tracked_ids)

# Summary
ok = sum(1 for r in results if r["status"] == "ok")
skipped = sum(1 for r in results if r["status"] == "skipped")
print(f"\nDone: {ok} new, {skipped} skipped / {len(results)} total")
# Write download log
log_data = []
for r in results:
    entry = dict(r)
    pdf = OUT_DIR / f"{entry.get('name','')}.pdf"
    if pdf.exists():
        entry["pdf_size_kb"] = pdf.stat().st_size // 1024
    log_data.append(entry)
(DATA_DIR / "483_download_log.json").write_text(json.dumps(log_data, indent=2))
