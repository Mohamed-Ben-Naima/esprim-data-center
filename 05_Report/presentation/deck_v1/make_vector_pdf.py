"""Vector PDF of deck v1 (real, selectable text) for import into Canva / editors.

  python 05_Report/presentation/deck_v1/make_vector_pdf.py
Output: 05_Report/presentation/DC_Casablanca_Soutenance_v1_editable.pdf (one 1920x1080 page per slide, notes dropped).
"""
import json
import re
from pathlib import Path

from pypdf import PdfWriter

import render_check as rc

OUT_PDF = rc.HERE.parent / "DC_Casablanca_Soutenance_v1_editable.pdf"


def main():
    from playwright.sync_api import sync_playwright
    deck = json.loads((rc.PROJ / "deck.json").read_text(encoding="utf-8"))
    amap = {v: k for k, v in json.loads((rc.HERE / "assets_map.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}
    files = {}
    for d in rc.SEARCH:
        for f in d.glob("*.*"):
            files.setdefault(f.name, f)
    css = (rc.PROJ / "deck.css").read_text(encoding="utf-8")
    href = deck["faces"]["inter"]["href"]
    tmpd = rc.OUT / "pdf"
    tmpd.mkdir(parents=True, exist_ok=True)
    parts = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        for i, sid in enumerate(deck["order"], 1):
            h = (rc.PROJ / "slides" / f"{sid}.html").read_text(encoding="utf-8")
            h = re.sub(r"/_blob/([0-9a-f]{32})", lambda m: files[amap[m[1]]].as_uri() if m[1] in amap else m[0], h)
            page = (f'<html><head><link rel="stylesheet" href="{href}"><style>{css}\n'
                    "@page{size:1920px 1080px;margin:0} html,body{margin:0}"
                    "section{position:relative;width:1920px;height:1080px;box-sizing:border-box;overflow:hidden}"
                    "aside{display:none} p,h1,h2,h3,ul,table{margin:0}"
                    f"</style></head><body style='counter-reset: page {i - 1}'>{h}</body></html>")
            tmp = tmpd / "_page.html"
            tmp.write_text(page, encoding="utf-8")
            pg.goto(tmp.as_uri())
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(900)
            out = tmpd / f"{i:02d}_{sid}.pdf"
            pg.pdf(path=str(out), width="1920px", height="1080px", print_background=True, page_ranges="1")
            parts.append(out)
            print("ok", i, sid, flush=True)
        b.close()
    w = PdfWriter()
    for f in parts:
        w.append(str(f))
    w.write(str(OUT_PDF))
    print(OUT_PDF, round(OUT_PDF.stat().st_size / 1e6, 1), "MB")


if __name__ == "__main__":
    main()
