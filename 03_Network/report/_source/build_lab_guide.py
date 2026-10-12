"""Build the English PDFs of the lab from report/_source/*.html.

  python report/_source/build_lab_guide.py                 -> report/DC_Casablanca_Lab_Guide.pdf
  python report/_source/build_lab_guide.py test_the_lab    -> report/Test_the_Lab.pdf
Lab guide: the cabling and leaf-port tables are generated from the wiring CSV and the inventory.
Test the Lab: the test tables are generated from report/tests/tests.yaml and the page reuses the lab guide's styles.
The page is then printed to PDF by a headless Chromium browser (Edge or Chrome).
"""
import csv
import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

SRC = Path(__file__).resolve().parent
NET = SRC.parents[1]
DOCS = {"lab_guide": "DC_Casablanca_Lab_Guide.pdf", "test_the_lab": "Test_the_Lab.pdf"}
BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe"]


def table(head, rows, widths=None):
    cols = "".join(f'<th style="width:{w}">{h}</th>' if w else f"<th>{h}</th>"
                   for h, w in zip(head, widths or [None] * len(head)))
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{cols}</tr></thead><tbody>{body}</tbody></table>"


def cabling():
    with open(NET / "DC_Casablanca_TIA942_R3_wiring.csv", encoding="utf-8", newline="") as f:
        links = list(csv.DictReader(f))
    rows = [[i, html.escape(l["role"]), f"<b>{l['node_a']}</b>", l["if_a"], f"<b>{l['node_b']}</b>", l["if_b"]]
            for i, l in enumerate(links, 1)]
    return table(["#", "Role", "Device A", "Port A", "Device B", "Port B"], rows, ["5%", "30%", None, None, None, None])


def leaf_ports(inv):
    leafs = ["LEAF-A1", "LEAF-A2", "LEAF-B1", "LEAF-B2"]
    ports = sorted({p for l in leafs for p in inv["devices"][l]["ports"]},
                   key=lambda p: [int(x) for x in p[2:].split("/")])
    rows = []
    for p in ports:
        row = [f"<b>{p}</b>"]
        for l in leafs:
            d = inv["devices"][l]["ports"].get(p)
            if not d:
                row.append('<span style="color:#8a94a0">shut, VLAN 999</span>')
                continue
            peer = d["to"].replace(":", " ")
            kind = {"trunk": "trunk", "mgmt": "VLAN 10"}.get(d["mode"], f"VLAN {d.get('vlan')}")
            row.append(f"{peer}<br><i style='color:#5b6775'>{kind}</i>")
        rows.append(row)
    return "<p><b>Port map of the four leafs</b> (generated from the inventory).</p>" + table(["Port"] + leafs, rows, ["9%"] + [None] * 4)


def tests():
    data = yaml.safe_load((NET / "report" / "tests" / "tests.yaml").read_text(encoding="utf-8"))
    out, total, passed, limits = [], 0, 0, 0
    for sec in data["sections"]:
        rows = []
        for t in sec["tests"]:
            total += 1
            expected = html.escape(str(t["expected"]))
            if t.get("limit"):
                limits += 1
                when = '<span class="pill wip">known limit</span>'
                expected += f'<br><i>{html.escape(t["limit"])}</i>'
            elif t.get("verified"):
                passed += 1
                when = f'<span class="pill ok">{t["verified"]:%d %b %Y}</span>'
            else:
                when = '<span class="pill todo">not run yet</span>'
            rows.append([t["id"], html.escape(t["proves"]), f"<code>{html.escape(t['command'].strip())}</code>",
                         html.escape(t["from"]), expected, when])
        out.append(f'<div class="keep"><h1><span class="n">{sec["id"]}</span>{html.escape(sec["title"])}</h1>'
                   f'<p class="needs"><b>Must be running:</b> {html.escape(sec["needs"])}</p>'
                   + table(["ID", "What it proves", "Command", "Where to run it", "Expected", "Last passed"], rows,
                           ["8%", "19%", "30%", "16%", "18%", "9%"]).replace("<table>", '<table class="t">') + "</div>")
    counts = (f"<div><b>{total}</b>tests</div><div><b>{passed}</b>passed, with date</div>"
              f"<div><b>{limits}</b>known lab limit</div><div><b>{total - passed - limits}</b>not run yet</div><div><b>{data['updated']:%d %b %Y}</b>last update</div>")
    return "".join(out), counts


def main(name="lab_guide"):
    if name not in DOCS:
        sys.exit(f"unknown document {name!r}; choose one of {', '.join(DOCS)}")
    out_pdf = NET / "report" / DOCS[name]
    inv = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
    page = (SRC / f"{name}.html").read_text(encoding="utf-8")
    if name == "lab_guide":
        page = page.replace("<!--CABLING-->", cabling()).replace("<!--LEAFPORTS-->", leaf_ports(inv))
    else:
        style = re.search(r"<style>.*?</style>", (SRC / "lab_guide.html").read_text(encoding="utf-8"), re.S).group(0)
        body, counts = tests()
        page = (page.replace("<!--STYLE-->", style.replace("GNS3 Network Lab Guide", "Test the Lab"))
                .replace("<!--TESTS-->", body).replace("<!--COUNTS-->", counts))
    page = page.replace("<head>", f'<head>\n<base href="{SRC.as_uri()}/">', 1)
    browser = next((b for b in BROWSERS if Path(b).exists()), None)
    if not browser:
        sys.exit("no Edge/Chrome found for the PDF export")
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / f"{name}.html"
        f.write_text(page, encoding="utf-8")
        subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--user-data-dir={Path(tmp) / 'profile'}", f"--print-to-pdf={out_pdf}", f.as_uri()],
                       check=True, timeout=180, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"{out_pdf} ({out_pdf.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main(*sys.argv[1:2])
