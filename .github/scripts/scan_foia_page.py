#!/usr/bin/env python3
"""
Scan OII FOIA page for 483 download links and RSS feed
"""
import httpx, re, json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

URL = "https://www.fda.gov/about-fda/office-inspections-and-investigations/oii-foia-electronic-reading-room"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

print(f"Scanning {URL}...")
client = httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS)
resp = client.get(URL)
print(f"Status: {resp.status_code}, Size: {len(resp.text)} bytes")

links = set()
for m in re.finditer(r'href="([^"]*)"', resp.text):
    h = m.group(1)
    if h.startswith("/"):
        links.add("https://www.fda.gov" + h)
    elif h.startswith("http"):
        links.add(h)

print(f"\nTotal links: {len(links)}")

# 找 483/PDF/RSS 相关链接
for l in sorted(links):
    lc = l.lower()
    if any(x in lc for x in ["483", "foia", "reading", "inspection", "rss", "xml", "feed", "download", "media/"]):
        print(f"  {l[:150]}")

# 找 RSS
for l in links:
    if "rss" in l.lower() or "feed" in l.lower():
        print(f"\nRSS: {l}")

# 找 iframe
for m in re.finditer(r'<iframe[^>]*src="([^"]*)"', resp.text, re.I):
    print(f"  IFRAME: {m.group(1)[:150]}")

# 保存页面
(REPO_ROOT / "data" / "oii_foia_page.html").write_text(resp.text[:50000])
print(f"Page saved ({len(resp.text)} chars)")
