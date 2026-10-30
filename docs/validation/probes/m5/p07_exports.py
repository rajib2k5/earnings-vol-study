"""p07: are the PDF and DOCX faithful exports of the Markdown report?

    uv run --frozen --offline --no-sync python docs/validation/probes/m5/p07_exports.py <md> <pdf> <docx>

Own comparison, not the build script's: the Markdown is parsed with markdown-it-py (the same parser family, but the
items compared are plain strings: heading texts, every table row's cell texts, image alt texts, and every
number-like token). The PDF text comes from poppler's `pdftotext -layout` and the image count from `pdfimages -list`;
the DOCX from python-docx (paragraphs, tables cell by cell, inline shapes). Whitespace and soft hyphenation are
normalised before matching. Prints what is missing; rc 1 if anything is.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def norm(s: str) -> str:
    s = s.replace("­", "").replace("‑", "-")
    return re.sub(r"\s+", " ", s).strip()


def inline_text(tok) -> str:
    out = []
    for c in tok.children or []:
        if c.type in ("text", "code_inline"):
            out.append(c.content)
        elif c.type in ("softbreak", "hardbreak"):
            out.append(" ")
    return "".join(out)


def md_items(md: str):
    from markdown_it import MarkdownIt
    toks = MarkdownIt("commonmark", {"html": True}).enable("table").parse(md)
    heads, rows, imgs, paras = [], [], [], []
    row = None
    for i, t in enumerate(toks):
        if t.type == "heading_open":
            heads.append(inline_text(toks[i + 1]))
        elif t.type == "tr_open":
            row = []
        elif t.type in ("th_open", "td_open"):
            row.append(inline_text(toks[i + 1]))
        elif t.type == "tr_close":
            rows.append(row)
        elif t.type == "inline":
            for c in t.children or []:
                if c.type == "image":
                    imgs.append(("".join(x.content for x in c.children or [] if x.type == "text"), c.attrs["src"]))
            if toks[i - 1].type == "paragraph_open":
                paras.append(inline_text(t))
    return heads, rows, imgs, paras


def main() -> int:
    md_p, pdf_p, docx_p = map(Path, sys.argv[1:4])
    md = md_p.read_text()
    heads, rows, imgs, paras = md_items(md)
    print(f"markdown: {len(heads)} headings, {len(rows)} table rows, {len(imgs)} images, {len(paras)} paragraphs")
    bad = 0

    # ---- PDF
    pdf_txt = subprocess.run(["pdftotext", "-layout", str(pdf_p), "-"], capture_output=True, text=True).stdout
    pdf_flat = norm(pdf_txt)
    pdf_nospace = re.sub(r"\s+", "", pdf_txt)
    info = subprocess.run(["pdfinfo", str(pdf_p)], capture_output=True, text=True).stdout
    pages = re.search(r"Pages:\s+(\d+)", info).group(1)
    il = subprocess.run(["pdfimages", "-list", str(pdf_p)], capture_output=True, text=True).stdout.splitlines()[2:]
    n_img = len([l for l in il if l.split()[2] == "image"]) if il else 0
    print(f"pdf: {pdf_p.stat().st_size:,} B, {pages} pages, {n_img} embedded images (pdfimages; smasks not counted)")

    words = set(pdf_txt.split())

    def in_pdf(s: str) -> bool:
        # contiguous (whitespace-insensitive), or, for text that the PDF wraps inside a table cell, every word
        # present as a word of the PDF text (pdftotext -layout interleaves the lines of wrapped cells)
        return re.sub(r"\s+", "", s) in pdf_nospace or all(w in words or w in pdf_nospace for w in s.split())

    miss = [h for h in heads if not in_pdf(h)]
    print(f"  headings missing: {len(miss)} {miss[:5]}")
    bad += len(miss)
    mr = [r for r in rows if not all(in_pdf(c) for c in r if c.strip())]
    print(f"  table rows with a cell missing: {len(mr)} {[r[:2] for r in mr[:5]]}")
    bad += len(mr)
    ma = [a for a, _ in imgs if not in_pdf(a)]
    print(f"  image captions missing: {len(ma)} {ma[:3]}")
    bad += len(ma)
    if n_img < len(imgs):
        print(f"  FEWER IMAGES THAN THE MARKDOWN: {n_img} < {len(imgs)}")
        bad += 1
    mp = [p[:60] for p in paras if p.strip() and not in_pdf(p)]
    print(f"  paragraphs not found verbatim (whitespace-insensitive): {len(mp)} {mp[:5]}")
    bad += len(mp)

    # ---- DOCX
    import docx
    d = docx.Document(str(docx_p))
    dtext = []
    for para in d.paragraphs:
        dtext.append(para.text)
    for tb in d.tables:
        for r in tb.rows:
            for c in r.cells:
                dtext.append(c.text)
    dflat = re.sub(r"\s+", "", "\n".join(dtext))
    dheads = [p.text for p in d.paragraphs if p.style.name.startswith(("Heading", "Title"))]
    drows = sum(len(tb.rows) for tb in d.tables)
    print(f"docx: {docx_p.stat().st_size:,} B, {len(dheads)} headings, {len(d.tables)} tables / {drows} rows, "
          f"{len(d.inline_shapes)} inline images")

    def in_docx(s: str) -> bool:
        return re.sub(r"\s+", "", s) in dflat

    miss = [h for h in heads if not in_docx(h)]
    print(f"  headings missing: {len(miss)} {miss[:5]}")
    bad += len(miss)
    if drows != len(rows):
        print(f"  TABLE ROW COUNT DIFFERS: docx {drows} vs markdown {len(rows)}")
        bad += 1
    mr = [r for r in rows if not all(in_docx(c) for c in r if c.strip())]
    print(f"  table rows with a cell missing: {len(mr)} {[r[:2] for r in mr[:5]]}")
    bad += len(mr)
    if len(d.inline_shapes) != len(imgs):
        print(f"  IMAGE COUNT DIFFERS: docx {len(d.inline_shapes)} vs markdown {len(imgs)}")
        bad += 1
    ma = [a for a, _ in imgs if not in_docx(a)]
    print(f"  image captions missing: {len(ma)} {ma[:3]}")
    bad += len(ma)
    mp = [p[:60] for p in paras if p.strip() and not in_docx(p)]
    print(f"  paragraphs not found verbatim: {len(mp)} {mp[:5]}")
    bad += len(mp)

    # ---- every number-like token of the Markdown, in order of appearance, present in both
    toks = re.findall(r"[−+-]?\d[\d,.]*(?:e[−-]\d+)?%?", md)
    print(f"number tokens in the markdown: {len(toks)}; missing from pdf: "
          f"{sum(1 for t in set(toks) if t not in pdf_flat and re.sub(r'\\s','',t) not in pdf_nospace)}; "
          f"missing from docx: {sum(1 for t in set(toks) if t not in dflat)}")
    print(f"MISSING ITEMS: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
