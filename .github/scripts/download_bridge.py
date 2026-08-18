#!/usr/bin/env python3
"""Download bridge: fetch URL from downloads/.request.txt and save result under downloads/."""
import re, shutil, subprocess, sys, urllib.parse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DL = REPO_ROOT / "downloads"
REQ = DL / ".request.txt"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


def log(*a):
    print(*a, flush=True)


def main():
    url = REQ.read_text().strip().splitlines()[0].strip()
    log("requested:", url)
    m = re.search(r"/document/(\d+)", url)
    doc_id = m.group(1) if m else None
    slug = re.sub(r"[^\w.-]+", "-", urllib.parse.unquote(url.rstrip("/").split("/")[-1]))
    slug = slug or f"doc-{doc_id or 'unknown'}"
    out = DL / f"{slug}.pdf"
    log("output:", out)

    ok = False
    if doc_id and "scribd" in url:
        ok = try_scribd_dl(url, out)
        if not ok:
            log("scribd-dl failed, falling back to embed text extraction")
            ok = scribd_embed_text(doc_id, out)
    else:
        ok = plain_download(url, out)

    if not ok:
        log("FAILED: no output file produced")
        sys.exit(1)
    log("OK:", out.name, out.stat().st_size, "bytes")


def plain_download(url, out):
    r = subprocess.run(["curl", "-sL", "-A", UA, "-o", str(out), url], timeout=300)
    return r.returncode == 0 and out.exists() and out.stat().st_size > 0


def try_scribd_dl(url, out):
    if not shutil.which("scribd-dl"):
        log("scribd-dl not installed")
        return False
    log("running scribd-dl ...")
    try:
        r = subprocess.run(["scribd-dl", url], cwd=str(DL), timeout=300,
                           capture_output=True, text=True)
        log("scribd-dl rc:", r.returncode)
        if r.stdout:
            log("stdout tail:", r.stdout[-2000:])
        if r.stderr:
            log("stderr tail:", r.stderr[-2000:])
    except Exception as e:
        log("scribd-dl exception:", e)
        return False
    cands = sorted(DL.glob("*.pdf"), key=lambda p: p.stat().st_mtime)
    if cands:
        latest = cands[-1]
        if latest.name != out.name:
            shutil.move(str(latest), str(out))
    return out.exists() and out.stat().st_size > 1000


def scribd_embed_text(doc_id, out):
    from xml.sax.saxutils import escape
    import requests
    from bs4 import BeautifulSoup
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

    url = f"https://www.scribd.com/embeds/{doc_id}/content"
    log("embed url:", url)
    try:
        r = requests.get(url, headers={"User-Agent": UA,
                                       "Referer": f"https://www.scribd.com/document/{doc_id}"},
                         timeout=60)
        log("embed http:", r.status_code, "len:", len(r.text))
        (DL / "_embed_dump.html").write_text(r.text)
    except Exception as e:
        log("embed fetch failed:", e)
        return False

    soup = BeautifulSoup(r.text, "html.parser")
    pages = soup.select(".page, .text_layer, [data-page]")
    texts = []
    if pages:
        for p in pages:
            t = p.get_text("\n", strip=True)
            if t:
                texts.append(t)
    else:
        body = soup.get_text("\n", strip=True)
        if len(body) > 200:
            texts = [body]
    if not texts:
        log("no text extracted from embed")
        return False
    log("pages extracted:", len(texts), "chars:", sum(len(t) for t in texts))

    doc = SimpleDocTemplate(str(out), pagesize=A4,
                            rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()
    story = []
    for i, t in enumerate(texts):
        if i:
            story.append(Spacer(1, 12))
        story.append(Paragraph(escape(t).replace("\n", "<br/>"), styles["BodyText"]))
    doc.build(story)
    return out.exists() and out.stat().st_size > 1000


if __name__ == "__main__":
    main()
