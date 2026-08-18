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
    msg = " ".join(str(x) for x in a)
    print(msg, flush=True)
    try:
        with open(DL / "_last_run.log", "a") as f:
            f.write(msg + "\n")
    except OSError:
        pass


def log_traceback():
    import traceback
    log("TRACEBACK:", traceback.format_exc().replace("\n", " | "))


def main():
    url = REQ.read_text().strip().splitlines()[0].strip()
    log("requested:", url)
    m = re.search(r"/document/(\d+)", url)
    doc_id = m.group(1) if m else None
    slug = re.sub(r"[^\w.-]+", "-", urllib.parse.unquote(url.rstrip("/").split("/")[-1]))
    slug = slug or f"doc-{doc_id or 'unknown'}"
    out = DL / f"{slug}.pdf"
    log("output:", out)

    # make scribdl importable without md2pdf (weasyprint trap) — fake it
    import types, sys as _sys
    fake = types.ModuleType("md2pdf")
    fake_core = types.ModuleType("md2pdf.core")
    def _disabled(*a, **k):
        raise RuntimeError("md2pdf disabled")
    fake_core.md2pdf = _disabled
    fake.core = fake_core
    _sys.modules["md2pdf"] = fake
    _sys.modules["md2pdf.core"] = fake_core

    try:
        ok = False
        if doc_id and "scribd" in url:
            ok = scribdl_download(url, out, image_doc=False)
            if not ok:
                log("scribdl textual failed, trying image mode")
                ok = scribdl_download(url, out, image_doc=True)
            if not ok:
                log("scribdl failed, falling back to embed text extraction")
                ok = scribd_embed_text(doc_id, out)
        else:
            ok = plain_download(url, out)

        # cleanup intermediates
        for p in list(DL.glob("*.md")) + list(DL.glob("*.jpg")) + list(DL.glob("*.png")):
            try:
                p.unlink()
            except OSError:
                pass

        if not ok:
            log("FAILED: no output file produced")
            sys.exit(1)
        log("OK:", out.name, out.stat().st_size, "bytes")
    except Exception:
        log_traceback()
        sys.exit(1)


def plain_download(url, out):
    r = subprocess.run(["curl", "-sL", "-A", UA, "-o", str(out), url], timeout=300)
    return r.returncode == 0 and out.exists() and out.stat().st_size > 0


def scribdl_download(url, out, image_doc):
    try:
        from scribdl.downloader import Downloader
    except Exception:
        log_traceback()
        return False
    log("scribdl image_doc:", image_doc)
    try:
        dl = Downloader(url)
        if dl._is_audiobook or dl._is_book:
            log("scribdl: audiobook/book not supported here")
            return False
        content = dl.download(is_image_document=image_doc)
    except Exception as e:
        log("scribdl download exception:", repr(e)[:300])
        return False

    if image_doc:
        if not content.content_path:
            log("scribdl: no images extracted")
            return False
        try:
            import img2pdf
            with open(str(out), "wb") as f:
                imgs = [open(str(p), "rb") for p in content.content_path]
                f.write(img2pdf.convert(imgs))
                for im in imgs:
                    im.close()
            return out.exists() and out.stat().st_size > 1000
        except Exception as e:
            log("scribdl img2pdf exception:", repr(e)[:300])
            return False

    # textual: content.content_path is a .md file
    md = Path(content.content_path) if content.content_path else None
    if not md or not md.exists() or md.stat().st_size < 100:
        log("scribdl: text too small / missing:", md)
        return False
    log("scribdl md bytes:", md.stat().st_size)
    return md_to_pdf(md, out)


def md_to_pdf(md, out):
    from xml.sax.saxutils import escape
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    text = md.read_text(errors="replace")
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paras:
        paras = [text.strip()]
    doc = SimpleDocTemplate(str(out), pagesize=A4,
                            rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    body.fontSize = 10.5
    body.leading = 15
    story = []
    for p in paras:
        if story:
            story.append(Spacer(1, 8))
        story.append(Paragraph(escape(p).replace("\n", "<br/>"), body))
    doc.build(story)
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
    body = styles["BodyText"]
    body.fontSize = 10.5
    body.leading = 15
    story = []
    for i, t in enumerate(texts):
        if i:
            story.append(Spacer(1, 12))
        story.append(Paragraph(escape(t).replace("\n", "<br/>"), body))
    doc.build(story)
    return out.exists() and out.stat().st_size > 1000


if __name__ == "__main__":
    main()
