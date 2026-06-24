#!/usr/bin/env python3
"""
Fetch FDA 483 PDFs from CDER/CBER/ORA FOIA pages and known hardcoded links.
On GitHub Actions (US IP) we can access FDA.gov without Akamai blocking.

Two strategies:
  1. Download known 483 PDFs (hardcoded, verified)
  2. Scan CDER/CBER FOIA pages for new /media/XXXX/download links

New media IDs are tracked in data/known_media_ids.txt for incremental updates.
"""
import httpx, json, os, time, re
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

# --- Tracking file for discovered media IDs ---
TRACK_FILE = DATA_DIR / "known_media_ids.txt"

def load_tracked_ids():
    if not TRACK_FILE.exists():
        return set(str(mid) for mid, _, _ in KNOWN_PDFS)
    return set(TRACK_FILE.read_text().strip().split("\n")) | set(str(mid) for mid, _, _ in KNOWN_PDFS)

def save_tracked_ids(ids):
    TRACK_FILE.write_text("\n".join(sorted(ids)) + "\n")

# --- Download ---
def try_download(media_id, name, url, force=False):
    pdf_path = OUT_DIR / f"{name}.pdf"
    if pdf_path.exists() and pdf_path.stat().st_size > 1000 and not force:
        return {"media_id": media_id, "name": name, "status": "skipped", "size": pdf_path.stat().st_size // 1024}
    print(f"  DOWNLOAD {name} (media {media_id})...", end=" ", flush=True)
    try:
        time.sleep(1.5)
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

# --- Scan FOIA pages for new media links ---
FOIA_PAGES = [
    # CDER FOIA — Drug-related 483s
    "https://www.fda.gov/drugs/cder-foia-electronic-reading-room",
    # CBER FOIA — Biologics (sterile injectables, vaccines)
    "https://www.fda.gov/vaccines-blood-biologics/cber-foia-electronic-reading-room",
    # ORA FOIA (may redirect but trying)
    "https://www.fda.gov/about-fda/office-regulatory-affairs/ora-foia-electronic-reading-room",
    # OII FOIA
    "https://www.fda.gov/about-fda/office-inspections-and-investigations/oii-foia-electronic-reading-room",
]

def scan_foia_pages(tracked_ids):
    """Scan FOIA pages for /media/XXXX/download links not yet tracked."""
    new_finds = []
    for url in FOIA_PAGES:
        try:
            time.sleep(2)
            label = url.rstrip("/").split("/")[-1][:40]
            print(f"  Scanning {label}...", end=" ", flush=True)
            resp = client.get(url)
            html = resp.text
            if "apology" in html[:500].lower() or "abuse" in html[:500].lower():
                print(f"BLOCKED ({len(resp.text)}b, 'apology' in head)")
                # Still save a snippet
                (REPO_ROOT / "data" / f"scan_{label}_blocked.html").write_text(resp.text[:30000])
                continue
            if len(html) < 2000:
                print(f"TOO SHORT ({len(resp.text)}b, likely redirect/empty)")
                continue
            print(f"{len(resp.text)} bytes — searching for /media/ links...")

            # Find ALL /media/XXXX/download links
            media_links = re.findall(r'/media/(\d+)/download', html)
            media_set = set(media_links)
            print(f"    Found {len(media_links)} media links ({len(media_set)} unique)")

            for mid in sorted(media_set):
                if mid in tracked_ids:
                    continue
                # Try to extract company name from surrounding HTML — broader search
                # Look backwards from the link for the nearest <td> or <a> text
                context_patterns = [
                    r'<td[^>]*>([^<]{10,120})</td>\s*<td[^>]*>[^<]*</td>\s*<td[^>]*>[^<]*</td>\s*<td[^>]*>[^<]*href="[^"]*/media/' + re.escape(mid) + r'/download"',
                    r'(?:>([^<]{10,120})<)[^<]*href="[^"]*/media/' + re.escape(mid) + r'/download"',
                ]
                name = None
                for pat in context_patterns:
                    cm = re.search(pat, html)
                    if cm:
                        name = cm.group(1).strip()
                        break
                if not name:
                    name = f"Media_{mid}"
                name_clean = re.sub(r'[^a-zA-Z0-9_\-]+', '_', name)[:60].strip('_')
                full_url = f"https://www.fda.gov/media/{mid}/download"
                new_finds.append((mid, name_clean, full_url))
                print(f"    >> NEW: {name_clean} (media {mid})")
                tracked_ids.add(mid)  # Track immediately so we don't re-download

            # Also search for PDF links outside /media/
            pdf_links = re.findall(r'href="([^"]*\.pdf)"', html)
            print(f"    Found {len(pdf_links)} direct PDF links")
            for pl in pdf_links[:5]:  # first 5
                print(f"      {pl[:100]}")

        except Exception as e:
            print(f"SCAN ERROR: {e}")
    return new_finds

# --- Extract 483 text from PDF (basic, just enough to identify) ---
def extract_pdf_text(pdf_path):
    """Extract text from PDF using pdftotext or fallback."""
    import subprocess
    r = subprocess.run(["pdftotext", str(pdf_path), "-"], capture_output=True, text=True, timeout=15)
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip()
    # Fallback: try python libs
    try:
        import PyPDF2
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""

def parse_483_info(text, name):
    """Extract basic info from PDF text: company, dates, observations."""
    info = {"name": name, "company": name.replace("_", " ")}
    # Date range
    dm = re.search(r'(\d{1,2}/\d{1,2}/\d{4})\s*-?\s*(\d{1,2}/\d{1,2}/\d{4})', text)
    if dm:
        info["inspection_start"] = dm.group(1)
        info["inspection_end"] = dm.group(2)
    # Issued date (last date in text, often)
    dates = re.findall(r'(\d{1,2}/\d{1,2}/\d{4})', text)
    if len(dates) >= 2:
        info["issued_date"] = dates[-1]
    # Observations count
    obs_nums = set(re.findall(r'OBSERVATION\s+(\d+)', text, re.IGNORECASE))
    info["observation_count"] = len(obs_nums)
    # Citations
    cites = set()
    for m in re.finditer(r'\d+\s+CFR\s+\d+\.?\d*[a-z]?\(?[^)\s]*\)?', text, re.I):
        c = m.group().strip().rstrip('.')
        if len(c) > 5:
            cites.add(c)
    info["citations"] = sorted(cites)
    # Extract observations text
    info["observations"] = []
    current_obs = None
    current_text = []
    for line in text.split("\n"):
        m = re.match(r'OBSERVATION\s+(\d+)', line.strip(), re.I)
        if m:
            if current_obs is not None:
                info["observations"].append({
                    "obs_number": current_obs,
                    "description": " ".join(current_text)[:3000],
                })
            current_obs = int(m.group(1))
            current_text = []
        elif current_obs is not None:
            current_text.append(line.strip())
    if current_obs is not None:
        info["observations"].append({
            "obs_number": current_obs,
            "description": " ".join(current_text)[:3000],
        })
    return info

# ===== MAIN =====
tracked_ids = load_tracked_ids()
results = []

# Phase 1: Download known 483 PDFs
print("=== Phase 1: Known 483 PDFs ===")
for media_id, name, url in KNOWN_PDFS:
    result = try_download(str(media_id), name, url)
    results.append(result)

# Phase 2: Scan FOIA pages for new 483s
print("\n=== Phase 2: Scan FOIA pages for new 483 PDFs ===")
new_finds = scan_foia_pages(tracked_ids)

if new_finds:
    print(f"\nFound {len(new_finds)} new 483 PDFs!")
    for mid, name, url in new_finds:
        result = try_download(mid, name, url, force=True)
        results.append(result)
        tracked_ids.add(mid)

    # Save enriched data for the combined JSON
    enriched = []
    for mid, name, url in new_finds:
        pdf_path = OUT_DIR / f"{name}.pdf"
        info = {"media_id": mid, "name": name, "url": url}
        if pdf_path.exists() and pdf_path.stat().st_size > 1000:
            text = extract_pdf_text(pdf_path)
            if text:
                parsed = parse_483_info(text, name)
                info.update(parsed)
                info["text_preview"] = text[:2000]
            info["pdf_size_kb"] = pdf_path.stat().st_size // 1024
        enriched.append(info)
    (DATA_DIR / "483_new_found.json").write_text(json.dumps(enriched, indent=2, ensure_ascii=False))
else:
    print("No new 483 PDFs found.")
    # Write empty to clear old data
    (DATA_DIR / "483_new_found.json").write_text("[]")

# Save FOIA page snapshots for debugging
print("=== Phase 3: Save FOIA page snapshots ===")
for url in FOIA_PAGES:
    try:
        label2 = url.rstrip("/").split("/")[-1][:30]
        time.sleep(1)
        resp2 = client.get(url)
        snapped = resp2.text[:80000]
        (DATA_DIR / f"debug_{label2}.html").write_text(snapped)
        status = "BLOCKED" if "apology" in snapped[:500].lower() else f"OK ({len(snapped)}b)"
        print(f"  {label2}: {status}")
    except Exception as e:
        print(f"  {label2}: ERROR {e}")

# Update tracking file
save_tracked_ids(tracked_ids)

# Summary
ok = sum(1 for r in results if r["status"] == "ok")
skipped = sum(1 for r in results if r["status"] == "skipped")
print(f"\nDone: {ok} new, {skipped} skipped / {len(results)} total")

# Write download log (for combined JSON)
log_data = []
for r in results:
    entry = dict(r)
    pdf = OUT_DIR / f"{entry.get('name','')}.pdf"
    if pdf.exists():
        entry["pdf_size_kb"] = pdf.stat().st_size // 1024
    log_data.append(entry)
(DATA_DIR / "483_download_log.json").write_text(json.dumps(log_data, indent=2))
