     1|#!/usr/bin/env python3
     2|"""
     3|Fetch FDA Warning Letters - pharmaceutical related only
     4|从 FDA 警告信列表页获取最新 WL，提取正文
     5|"""
     6|import httpx, re, json, os, subprocess, time
     7|from pathlib import Path
     8|
     9|REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = REPO_ROOT / "data" / "warning_letters"
    10|OUT_DIR.mkdir(parents=True, exist_ok=True)
    11|KNOWN_FILE = REPO_ROOT / "data" / "known_urls.txt"
    12|
    13|HEADERS = {
    14|    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    15|    "Accept": "text/html,*/*",
    16|}
    17|
    18|PHARMA_KW = ["drug", "pharma", "sterile", "cgmp", "gmp", "api", "adulterated",
    19|             "outsourcing facility", "producer", "manufactur", "compounding",
    20|             "aseptic", "bacteria", "contamination", "batch"]
    21|NON_PHARMA_KW = ["hospital", "clinic", "restaurant", "food", "cosmetic", "tobacco", "veterinary"]
    22|
    23|WL_URL = "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/compliance-actions-and-activities/warning-letters"
    24|
    25|# 加载已处理的 URL
    26|if KNOWN_FILE.exists():
    27|    known = set(KNOWN_FILE.read_text().strip().split("\n"))
    28|else:
    29|    known = set()
    30|
    31|client = httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS)
    32|
    33|# 1. 获取列表
    34|print("Fetching WL list...")
    35|resp = client.get(WL_URL)
    36|tds = re.findall(r'<td[^>]*>([\s\S]*?)</td>', resp.text)
    37|items = [re.sub(r'<[^>]+>', '', td).strip() for td in tds if re.sub(r'<[^>]+>', '', td).strip()]
    38|
    39|records = []
    40|for i in range(0, len(items), 5):
    41|    if i + 4 < len(items):
    42|        rec = {
    43|            "posted": items[i], "issued": items[i+1],
    44|            "company": items[i+2], "office": items[i+3], "subject": items[i+4],
    45|        }
    46|        # 制药筛选
    47|        text = json.dumps(rec).lower()
    48|        score = 0
    49|        if any(kw in text for kw in PHARMA_KW):
    50|            score += 3
    51|        if "CDER" in rec.get("office", ""):
    52|            score += 2
    53|        if any(kw in text for kw in NON_PHARMA_KW):
    54|            score -= 2
    55|        if score >= 3:
    56|            records.append(rec)
    57|
    58|print(f"  Pharma-related: {len(records)} / {len(items)//5} total")
    59|
    60|# 2. 找每个 WL 的详情页 URL
    61|# 从 HTML 找 href
    62|links = {}
    63|for m in re.finditer(r'href="(/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/[^"]*)"', resp.text):
    64|    full = "https://www.fda.gov" + m.group(1)
    65|    # 从 URL 里提取公司名
    66|    slug = m.group(1).split("/")[-1]
    67|    links[slug] = full
    68|
    69|# 3. 下载正文
    70|new_records = []
    71|for rec in records:
    72|    company_slug = re.sub(r'[^a-z0-9]+', '-', rec["company"].lower()).strip('-')
    73|    # 匹配 URL
    74|    url = None
    75|    for slug, link in links.items():
    76|        if company_slug[:20] in slug or slug[:20] in company_slug:
    77|            url = link
    78|            break
    79|    if not url:
    80|        continue
    81|    
    82|    link_id = f"wl_{rec['issued']}_{rec['company']}"
    83|    if link_id in known:
    84|        continue
    85|    
    86|    print(f"  Fetching: {rec['company'][:40]}...", end=" ", flush=True)
    87|    time.sleep(3)
    88|    try:
    89|        resp2 = client.get(url)
    90|        html = resp2.text
    91|        
    92|        # 用简易方式提取正文
    93|        text = re.sub(r'<[^>]+>', ' ', html)
    94|        text = re.sub(r'\s+', ' ', text)
    95|        
    96|        start = text.find("WARNING LETTER")
    97|        if start < 0:
    98|            start = text.find("Dear")
    99|        if start >= 0:
   100|            body = text[start:]
   101|            end = body.find("Sincerely")
   102|            if end > 0:
   103|                body = body[:end+20]
   104|            body = body[:5000]
   105|        else:
   106|            body = text[:5000]
   107|        
   108|        # 保存
   109|        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', rec["company"])[:40]
   110|        (OUT_DIR / f"{safe_name}.txt").write_text(body)
   111|        
   112|        # 提取 citations
   113|        clean = re.sub(r'\s+', ' ', body)
   114|        cites = set()
   115|        for m in re.finditer(r'\d+\s+CFR\s+\d+\.?\d*[a-z]?\(?[^)\s]*\)?', clean, re.I):
   116|            c = m.group().strip().rstrip('.')
   117|            if 5 < len(c) < 30:
   118|                cites.add(c)
   119|        
   120|        record = {
   121|            "company": rec["company"],
   122|            "issued": rec["issued"],
   123|            "subject": rec["subject"],
   124|            "url": url,
   125|            "body": body,
   126|            "citations": sorted(cites),
   127|        }
   128|        new_records.append(record)
   129|        known.add(link_id)
   130|        print(f"OK ({len(body)} chars)")
   131|    except Exception as e:
   132|        print(f"ERROR: {e}")
   133|
   134|# 4. 保存
   135|if new_records:
   136|    (REPO_ROOT / "data" / "wl_new_records.json").write_text(json.dumps(new_records, indent=2, ensure_ascii=False))
   137|    KNOWN_FILE.write_text("\n".join(sorted(known)))
   138|
   139|print(f"\nDone: {len(new_records)} new WL records")
   140|