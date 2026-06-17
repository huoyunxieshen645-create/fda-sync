#!/usr/bin/env python3
"""
Fetch FDA Warning Letters from the Drupal DataTables page.
FDA 2026 Drupal redesign: WL table is SSR in HTML with class-based columns.
We parse the HTML table directly.
"""
import httpx, re, json, os, time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = REPO_ROOT / "data" / "warning_letters"
OUT_DIR.mkdir(parents=True, exist_ok=True)
KNOWN_FILE = REPO_ROOT / "data" / "known_urls.txt"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,*/*",
}

WL_LIST_URL = "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/compliance-actions-and-activities/warning-letters"

# Pharma CGMP keywords — ONLY match actual CGMP/drug quality violations
# NOT telehealth, false claims, or food/device letters
PHARMA_KW = [
    "cgmp", "c.g.m.p.", "current good manufacturing",
    "finished pharmaceuticals", "active pharmaceutical",
    "drug product", "api ", "adulterated",
    "sterile drug", "aseptic", "compounding",
    "contamination", "microbiological",
    "over-the-counter drug", "otc drug",
]
# Explicit exclusion — these subjects are NOT pharma CGMP even if they mention drugs
EXCLUDE_SUBJECT_KW = [
    "false and misleading", "misbranded", "misleading claims",
    "telehealth", "unapproved", "new drug",
    "clinical investigator", "clinical trial",
    "research", "irb", "institutional review",
]
NON_PHARMA_KW = [
    "hospital", "clinic", "restaurant", "food", "cosmetic", "tobacco",
    "veterinary", "seafood", "dietary supplement", "medical device",
]

client = httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS)

def is_pharma_related(company, subject, office):
    """Score WL relevance to pharma CGMP.
    Only returns True for drug CGMP, sterile, and compounding violations.
    Excludes: telehealth false claims, food, devices, tobacco, clinical research.
    """
    subj_lower = subject.lower()
    text = f"{company} {subject} {office}".lower()
    
    # Explicit exclusion check first
    if any(kw in subj_lower for kw in EXCLUDE_SUBJECT_KW):
        return False
    
    score = 0
    if any(kw in text for kw in PHARMA_KW):
        score += 4  # Strong signal
    if "CDER" in office:
        score += 1
    if any(kw in text for kw in NON_PHARMA_KW):
        score -= 3
    if "CFSAN" in office or "Center for Food" in office:
        return False
    if "CDRH" in office or "Center for Devices" in office:
        return False
    # Telehealth compounding is still regulatory but not CGMP — exclude
    if "telehealth" in subj_lower:
        return False
    
    return score >= 3

def parse_wl_table(html):
    """Parse the Drupal DataTables SSR table for WL entries."""
    records = []
    
    # Extract rows from the table body
    # Drupal 2026: table with class 'table table-bordered table-hover sticky-enabled'
    # Columns: Posted Date | Letter Issue Date | Company Name | Issuing Office | Subject/Product | CMS # | FEI # | Actions
    
    # Find all <tr> inside the table body
    table_match = re.search(
        r'<table[^>]*class="[^"]*\btable\b[^"]*"[^>]*>.*?</table>',
        html, re.DOTALL
    )
    if not table_match:
        print("  WARN: No table found in HTML")
        return records
    
    table_html = table_match.group(0)
    
    # Find rows - skip header row
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL)
    
    for row in rows[1:]:  # skip header
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(cells) < 7:
            continue
        
        # Extract text from each cell
        clean_cells = []
        for c in cells:
            text = re.sub(r'<[^>]+>', ' ', c)
            text = re.sub(r'\s+', ' ', text).strip()
            clean_cells.append(text)
        
        # Extract link to WL detail page
        link_match = re.search(r'href="([^"]*)"', cells[2] if len(cells) > 2 else '')
        url = ""
        if link_match:
            href = link_match.group(1)
            if href.startswith("/"):
                url = "https://www.fda.gov" + href
            elif href.startswith("http"):
                url = href
        
        rec = {
            "posted": clean_cells[0] if len(clean_cells) > 0 else "",
            "issued": clean_cells[1] if len(clean_cells) > 1 else "",
            "company": clean_cells[2] if len(clean_cells) > 2 else "",
            "office": clean_cells[3] if len(clean_cells) > 3 else "",
            "subject": clean_cells[4] if len(clean_cells) > 4 else "",
            "cms": clean_cells[5] if len(clean_cells) > 5 else "",
            "fei": clean_cells[6] if len(clean_cells) > 6 else "",
            "url": url,
        }
        
        # Filter to pharma-related only
        if is_pharma_related(rec["company"], rec["subject"], rec["office"]):
            records.append(rec)
    
    return records

def fetch_wl_body(url):
    """Fetch the full WL body from detail page."""
    try:
        resp = client.get(url, timeout=30)
        html = resp.text
        
        # Check for abuse/apology page
        if "apology" in html[:500].lower() or "abuse" in html[:500].lower():
            return None, "BLOCKED_BY_AKAMAI"
        
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text)
        
        # Find the actual warning letter content
        start = text.find("WARNING LETTER")
        if start < 0:
            start = text.find("Dear ")
        if start < 0:
            start = 0
        
        body = text[start:]
        
        # Truncate at "Content current as of:" or similar footer
        for marker in ["Content current as of", "Back to Top", "FDA Archive"]:
            idx = body.find(marker)
            if idx > 0:
                body = body[:idx]
        
        body = body[:10000]  # cap at 10K chars
        return body, None
    except Exception as e:
        return None, str(e)

def extract_citations(text):
    """Extract regulatory citations (e.g. '21 CFR 211.22') from text."""
    pattern = r'\d+\s+CFR\s+\d+\.?\d*[a-z]?\(?[^)\s]*\)?'
    cites = set()
    for m in re.finditer(pattern, text, re.IGNORECASE):
        c = m.group().strip().rstrip('.')
        if 5 < len(c) < 30:
            cites.add(c)
    return sorted(cites)

# ===== MAIN =====
# Load existing WL data for dedup
existing_before = []
wl_output_path = REPO_ROOT / "data" / "wl_new_records.json"
if wl_output_path.exists():
    existing_before = json.loads(wl_output_path.read_text())

known = set()
if KNOWN_FILE.exists():
    known = set(KNOWN_FILE.read_text().strip().split("\n"))
    known.discard("")

print("Fetching WL list page...")
resp = client.get(WL_LIST_URL)
html = resp.text

# Check for block
if "apology" in html[:500].lower():
    print("  WARN: Akamai abuse detection page returned")
    print("  Trying alternate approach...")
    records = []
else:
    records = parse_wl_table(html)

print(f"  Pharma-related WLs found: {len(records)}")

# Also check page 2 if available
page2_url = WL_LIST_URL + "?page=1"
try:
    resp2 = client.get(page2_url, timeout=30)
    if resp2.status_code == 200 and "apology" not in resp2.text[:500].lower():
        records2 = parse_wl_table(resp2.text)
        print(f"  Page 2 pharma WLs: {len(records2)}")
        records.extend(records2)
except Exception:
    pass

# Fetch detail for each new record
new_records = []
for rec in records:
    if not rec["url"]:
        print(f"  SKIP {rec['company'][:40]} (no URL)")
        continue
    
    # Dedup by CMS number (if available) or URL slug
    if rec["cms"]:
        link_id = f"wl_cms_{rec['cms']}"
    else:
        slug = rec["url"].rstrip("/").split("/")[-1]
        link_id = f"wl_{slug}"
    
    if link_id in known:
        print(f"  SKIP {rec['company'][:40]} (known)")
        continue
    
    # Double-check: skip if same CMS already in WL file (legacy dedup)
    cms_num = rec.get("cms", "")
    if cms_num and any(wl.get("url", "").endswith(cms_num) for wl in existing_before):
        print(f"  SKIP {rec['company'][:40]} (CMS {cms_num} already in output)")
        known.add(link_id)
        continue
    
    print(f"  FETCH {rec['company'][:40]}...", end=" ", flush=True)
    time.sleep(2)
    
    body, error = fetch_wl_body(rec["url"])
    if body is None:
        print(f"FAIL ({error})")
        continue
    
    # Save raw text
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', rec["company"])[:60] or f"wl_{rec['cms']}"
    (OUT_DIR / f"{safe_name}.txt").write_text(body)
    
    # Extract citations from full text
    cites = extract_citations(body)
    
    new_records.append({
        "company": rec["company"],
        "issued": rec["issued"],
        "subject": rec["subject"],
        "url": rec["url"],
        "body": body,
        "citations": cites,
    })
    known.add(link_id)
    print(f"OK ({len(body)} chars, {len(cites)} citations)")

# Update known_urls.txt
if new_records:
    KNOWN_FILE.write_text("\n".join(sorted(known)) + "\n")

# Save new records to JSON
if new_records:
    output_path = REPO_ROOT / "data" / "wl_new_records.json"
    # Merge with existing
    existing = []
    if output_path.exists():
        existing = json.loads(output_path.read_text())
    existing.extend(new_records)
    output_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
    print(f"\n  Saved {len(new_records)} new records to {output_path}")
else:
    print("\n  No new WL records")

print(f"\nDone")
