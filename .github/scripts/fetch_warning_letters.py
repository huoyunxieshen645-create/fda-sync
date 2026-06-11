#!/usr/bin/env python3
"""
Fetch FDA Warning Letters - pharmaceutical related only
从 FDA 警告信列表页获取最新 WL，提取正文
"""
import httpx, re, json, os, subprocess, time
from pathlib import Path

OUT_DIR = Path("data/warning_letters")
OUT_DIR.mkdir(parents=True, exist_ok=True)
KNOWN_FILE = Path("data/known_urls.txt")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,*/*",
}

PHARMA_KW = ["drug", "pharma", "sterile", "cgmp", "gmp", "api", "adulterated",
             "outsourcing facility", "producer", "manufactur", "compounding",
             "aseptic", "bacteria", "contamination", "batch"]
NON_PHARMA_KW = ["hospital", "clinic", "restaurant", "food", "cosmetic", "tobacco", "veterinary"]

WL_URL = "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/compliance-actions-and-activities/warning-letters"

# 加载已处理的 URL
if KNOWN_FILE.exists():
    known = set(KNOWN_FILE.read_text().strip().split("\n"))
else:
    known = set()

client = httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS)

# 1. 获取列表
print("Fetching WL list...")
resp = client.get(WL_URL)
tds = re.findall(r'<td[^>]*>([\s\S]*?)</td>', resp.text)
items = [re.sub(r'<[^>]+>', '', td).strip() for td in tds if re.sub(r'<[^>]+>', '', td).strip()]

records = []
for i in range(0, len(items), 5):
    if i + 4 < len(items):
        rec = {
            "posted": items[i], "issued": items[i+1],
            "company": items[i+2], "office": items[i+3], "subject": items[i+4],
        }
        # 制药筛选
        text = json.dumps(rec).lower()
        score = 0
        if any(kw in text for kw in PHARMA_KW):
            score += 3
        if "CDER" in rec.get("office", ""):
            score += 2
        if any(kw in text for kw in NON_PHARMA_KW):
            score -= 2
        if score >= 3:
            records.append(rec)

print(f"  Pharma-related: {len(records)} / {len(items)//5} total")

# 2. 找每个 WL 的详情页 URL
# 从 HTML 找 href
links = {}
for m in re.finditer(r'href="(/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/[^"]*)"', resp.text):
    full = "https://www.fda.gov" + m.group(1)
    # 从 URL 里提取公司名
    slug = m.group(1).split("/")[-1]
    links[slug] = full

# 3. 下载正文
new_records = []
for rec in records:
    company_slug = re.sub(r'[^a-z0-9]+', '-', rec["company"].lower()).strip('-')
    # 匹配 URL
    url = None
    for slug, link in links.items():
        if company_slug[:20] in slug or slug[:20] in company_slug:
            url = link
            break
    if not url:
        continue
    
    link_id = f"wl_{rec['issued']}_{rec['company']}"
    if link_id in known:
        continue
    
    print(f"  Fetching: {rec['company'][:40]}...", end=" ", flush=True)
    time.sleep(3)
    try:
        resp2 = client.get(url)
        html = resp2.text
        
        # 用简易方式提取正文
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text)
        
        start = text.find("WARNING LETTER")
        if start < 0:
            start = text.find("Dear")
        if start >= 0:
            body = text[start:]
            end = body.find("Sincerely")
            if end > 0:
                body = body[:end+20]
            body = body[:5000]
        else:
            body = text[:5000]
        
        # 保存
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', rec["company"])[:40]
        (OUT_DIR / f"{safe_name}.txt").write_text(body)
        
        # 提取 citations
        clean = re.sub(r'\s+', ' ', body)
        cites = set()
        for m in re.finditer(r'\d+\s+CFR\s+\d+\.?\d*[a-z]?\(?[^)\s]*\)?', clean, re.I):
            c = m.group().strip().rstrip('.')
            if 5 < len(c) < 30:
                cites.add(c)
        
        record = {
            "company": rec["company"],
            "issued": rec["issued"],
            "subject": rec["subject"],
            "url": url,
            "body": body,
            "citations": sorted(cites),
        }
        new_records.append(record)
        known.add(link_id)
        print(f"OK ({len(body)} chars)")
    except Exception as e:
        print(f"ERROR: {e}")

# 4. 保存
if new_records:
    Path("data/wl_new_records.json").write_text(json.dumps(new_records, indent=2, ensure_ascii=False))
    KNOWN_FILE.write_text("\n".join(sorted(known)))

print(f"\nDone: {len(new_records)} new WL records")
