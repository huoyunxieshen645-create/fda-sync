#!/usr/bin/env python3
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

PHARMA_KW = ["drug", "pharma", "sterile", "cgmp", "gmp", "api", "adulterated",
             "manufactur", "compounding", "aseptic", "bacteria", "contamination", "batch"]
NON_PHARMA_KW = ["hospital", "clinic", "restaurant", "food", "cosmetic", "tobacco", "veterinary"]
WL_URL = "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/compliance-actions-and-activities/warning-letters"

known = set(KNOWN_FILE.read_text().strip().split("\n")) if KNOWN_FILE.exists() else set()
client = httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS)

print("Fetching WL list...")
resp = client.get(WL_URL)
tds = re.findall(r'<td[^>]*>([\s\S]*?)</td>', resp.text)
items = [re.sub(r'<[^>]+>', '', td).strip() for td in tds]
records = []
for i in range(0, len(items), 5):
    if i + 4 < len(items):
        rec = {"posted": items[i], "issued": items[i+1], "company": items[i+2], "office": items[i+3], "subject": items[i+4]}
        text = json.dumps(rec).lower()
        score = 0
        if any(kw in text for kw in PHARMA_KW): score += 3
        if "CDER" in rec.get("office", ""): score += 2
        if any(kw in text for kw in NON_PHARMA_KW): score -= 2
        if score >= 3:
            records.append(rec)
print(f"  Pharma-related: {len(records)}")

links = {}
for m in re.finditer(r'href="(/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/[^"]*)"', resp.text):
    links[m.group(1).split("/")[-1]] = "https://www.fda.gov" + m.group(1)

new_records = []
for rec in records:
    slug = re.sub(r'[^a-z0-9]+', '-', rec["company"].lower()).strip('-')
    url = None
    for s, l in links.items():
        if slug[:20] in s or s[:20] in slug:
            url = l
            break
    if not url:
        continue
    link_id = f"wl_{rec['issued']}_{rec['company']}"
    if link_id in known:
        continue
    print(f"  Fetch: {rec['company'][:40]}...", end=" ", flush=True)
    time.sleep(3)
    try:
        r2 = client.get(url)
        html = r2.text
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text)
        start = text.find("WARNING LETTER")
        if start < 0:
            start = text.find("Dear")
        body = text[start:] if start >= 0 else text[:5000]
        end = body.find("Sincerely")
        if end > 0:
            body = body[:end+20]
        body = body[:5000]
        safe = re.sub(r'[^a-zA-Z0-9_-]', '_', rec["company"])[:40]
        (OUT_DIR / f"{safe}.txt").write_text(body)
        clean = re.sub(r'\s+', ' ', body)
        cites = sorted(set(m.group().strip().rstrip('.') for m in re.finditer(r'\d+\s+CFR\s+\d+\.?\d*[a-z]?\(?[^)\s]*\)?', clean, re.I) if 5 < len(m.group()) < 30))
        new_records.append({"company": rec["company"], "issued": rec["issued"], "subject": rec["subject"], "url": url, "body": body, "citations": cites})
        known.add(link_id)
        print(f"OK ({len(body)} chars)")
    except Exception as e:
        print(f"ERROR: {e}")

if new_records:
    (REPO_ROOT / "data" / "wl_new_records.json").write_text(json.dumps(new_records, indent=2, ensure_ascii=False))
    KNOWN_FILE.write_text("\n".join(sorted(known)))
print(f"\nDone: {len(new_records)} new WL records")
