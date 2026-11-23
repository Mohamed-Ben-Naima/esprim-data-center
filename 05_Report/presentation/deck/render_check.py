"""Quality gate D15: render every slide to PNG (1920x1080) and check it.

  python 05_Report/presentation/deck/render_check.py [slide-id ...]

Checks per slide: content past the 1920x1080 canvas or into the footer band, text smaller than 24 px, boxes whose
text overflows them, images that did not load. Assets are the local files behind each /_blob/<id> (assets_map.json).
Output: deck/render/<nn>_<id>.png + render/report.txt. Exit 1 when a slide has a problem.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROJ = HERE / "project"
OUT = HERE / "render"
SEARCH = [ROOT / "05_Report/presentation/assets/diagrams/png", ROOT / "05_Report/presentation/assets/photos",
          ROOT / "02_Blender/04_Renders/stills", ROOT / "06_Documentation/img", ROOT / "03_Network/screenshots"]

CHECK_JS = """() => {
  const sec = document.querySelector('section'); const R = sec.getBoundingClientRect(); const out = [];
  const foot = sec.querySelector('.foot');
  for (const el of sec.querySelectorAll('*')) {
    if (el.closest('aside')) continue;
    const r = el.getBoundingClientRect(); if (!r.width || !r.height) continue;
    const cs = getComputedStyle(el);
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (own && parseFloat(cs.fontSize) < 24) out.push(`small text ${cs.fontSize} in <${el.tagName.toLowerCase()} class="${el.className}">: ${el.textContent.trim().slice(0,40)}`);
    if (r.right > R.right + 1 || r.bottom > R.bottom + 1 || r.left < R.left - 1 || r.top < R.top - 1)
      if (!el.classList.contains('bleed') && !el.classList.contains('scrim')) out.push(`off canvas <${el.tagName.toLowerCase()} class="${el.className}"> ${Math.round(r.right)}x${Math.round(r.bottom)}`);
    if (foot && !foot.contains(el) && !el.closest('.cover-txt') && own && r.bottom > 930 && !sec.classList.contains('cover'))
      out.push(`into footer band (bottom ${Math.round(r.bottom)}): ${el.textContent.trim().slice(0,40)}`);
    if (own && (el.scrollHeight > el.clientHeight + 4 || el.scrollWidth > el.clientWidth + 4) && cs.overflow !== 'visible')
      out.push(`text overflows <${el.tagName.toLowerCase()} class="${el.className}">`);
    if (el.tagName === 'IMG' && el.getAttribute('src') && !(el.complete && el.naturalWidth)) out.push(`image not loaded ${el.getAttribute('src')}`);
  }
  return out;
}"""


def main(ids):
    from playwright.sync_api import sync_playwright
    deck = json.loads((PROJ / "deck.json").read_text(encoding="utf-8"))
    amap = {v: k for k, v in json.loads((HERE / "assets_map.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}
    files = {}
    for d in SEARCH:
        for f in d.glob("*.*"):
            files.setdefault(f.name, f)
    css = (PROJ / "deck.css").read_text(encoding="utf-8")
    href = deck["faces"]["inter"]["href"]
    OUT.mkdir(exist_ok=True)
    order = deck["order"]
    bad = 0
    lines = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        for i, sid in enumerate(order, 1):
            if ids and sid not in ids:
                continue
            f = PROJ / "slides" / f"{sid}.html"
            if not f.exists():
                continue
            h = f.read_text(encoding="utf-8")
            h = re.sub(r"/_blob/([0-9a-f]{32})", lambda m: files[amap[m[1]]].as_uri() if m[1] in amap else m[0], h)
            h = h.replace(f'id="{sid}"', f'id="{sid}" style="counter-reset: page {i - 1}"', 1) if 'style="' not in h.split(">")[0] else h
            page = (f'<html><head><link rel="stylesheet" href="{href}"><style>{css}\n'
                    "html,body{margin:0} section{position:relative;width:1920px;height:1080px;box-sizing:border-box;overflow:hidden}"
                    "aside{display:none} p,h1,h2,h3,ul,table{margin:0}"
                    f"</style></head><body style='counter-reset: page {i - 1}'>{h}</body></html>")
            tmp = OUT / "_page.html"
            tmp.write_text(page, encoding="utf-8")
            pg.goto(tmp.as_uri())
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(900)
            pg.screenshot(path=str(OUT / f"{i:02d}_{sid}.png"))
            probs = pg.evaluate(CHECK_JS)
            if probs:
                bad += 1
            lines.append(f"{'FAIL' if probs else 'OK  '} {i:02d} {sid}" + "".join(f"\n      - {x}" for x in probs[:8]))
            print(lines[-1], flush=True)
        b.close()
    (OUT / "report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
