"""DEMO_SCRIPT.md -> DEMO_SCRIPT.pdf (A4 landscape, deck colours), rendered by Edge.

  python 05_Report/presentation/build_demo_script_pdf.py [DEMO_DISCOURS]     (default DEMO_SCRIPT)
"""
import sys
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
FONTS = (HERE.parents[1] / "03_Network/automation/demo_video/fonts").as_uri()

CSS = f"""
@font-face{{font-family:Inter;src:url('{FONTS}/Inter-Medium.ttf');font-weight:500}}
@font-face{{font-family:Inter;src:url('{FONTS}/Inter-Bold.ttf');font-weight:700}}
@font-face{{font-family:Inter;src:url('{FONTS}/Inter-ExtraBold.ttf');font-weight:800}}
@font-face{{font-family:JBM;src:url('{FONTS}/JetBrainsMono-Medium.ttf')}}
@page{{size:A4 landscape;margin:14mm 14mm 16mm}}
body{{font-family:Inter,Arial;font-size:10.5pt;color:#1B2A33;line-height:1.38}}
h1{{font-size:20pt;font-weight:800;color:#0B1015;margin:0 0 4px;border-bottom:4px solid #3FD0E8;padding-bottom:6px}}
h2{{font-size:13.5pt;font-weight:800;color:#0B6E80;margin:16px 0 6px}}
p{{margin:5px 0}}
code{{font-family:JBM,Consolas;font-size:9pt;background:#E9FAFD;padding:1px 4px;border-radius:4px}}
table{{border-collapse:collapse;width:100%;margin:6px 0;font-size:9.6pt}}
th{{background:#0B1015;color:#fff;text-align:left;padding:6px 7px;font-weight:700}}
td{{border-bottom:1px solid #D5E3EA;padding:5px 7px;vertical-align:top}}
tr:nth-child(even) td{{background:#F5FBFD}}
td:first-child{{font-family:JBM;font-weight:700;white-space:nowrap;color:#0B6E80;width:52px}}
td:nth-child(2){{width:150px;font-weight:700}}
td:last-child{{width:34%}}
strong{{color:#0B1015}}
ul{{margin:4px 0 4px 18px;padding:0}} li{{margin:3px 0}}
tr{{page-break-inside:avoid}} h2{{page-break-after:avoid}}
.foot{{margin-top:14px;font-size:8.5pt;color:#6B7A88}}
"""


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "DEMO_SCRIPT"
    md = (HERE / f"{name}.md").read_text(encoding="utf-8")
    css = CSS
    if name == "DEMO_DISCOURS":   # read aloud: portrait, bigger text, spoken lines in boxes
        css = (CSS.replace("size:A4 landscape", "size:A4").replace("font-size:10.5pt", "font-size:12pt")
               + "blockquote{margin:6px 0 8px;padding:8px 14px;background:#E9FAFD;border-left:5px solid #3FD0E8;"
                 "border-radius:6px;font-size:13pt;line-height:1.45;page-break-inside:avoid}"
                 "blockquote p{margin:2px 0} hr{border:0;border-top:1px solid #D5E3EA;margin:10px 0}")
    body = markdown.markdown(md, extensions=["tables"])
    html = (f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>{body}"
            "<p class='foot'>DC Casablanca · soutenance du 25/11/2026 · vidéo : video/DC_Casablanca_demo_5min.mp4 "
            "(3:36) · version longue : video/DC_Casablanca_walkthrough.mp4 (9:30)</p></body></html>")
    tmp = HERE / "_demo_script.html"
    tmp.write_text(html, encoding="utf-8")
    out = HERE / f"{name}.pdf"
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        pg = b.new_page()
        pg.goto(tmp.as_uri())
        pg.evaluate("document.fonts.ready")
        pg.pdf(path=str(out), format="A4", landscape=name != "DEMO_DISCOURS", print_background=True,
               margin={"top": "14mm", "bottom": "16mm", "left": "14mm", "right": "14mm"})
        b.close()
    tmp.unlink()
    print(out)


if __name__ == "__main__":
    main()
