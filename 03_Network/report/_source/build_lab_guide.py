"""Build report/DC_Casablanca_Lab_Guide.pdf from report/_source/lab_guide.html.

  python report/_source/build_lab_guide.py
The cabling and leaf-port tables are generated from the wiring CSV and the inventory; the page is then printed to
PDF by a headless Chromium browser (Edge or Chrome).
"""
import csv
import html
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

SRC = Path(__file__).resolve().parent
NET = SRC.parents[1]
OUT = NET / "report" / "DC_Casablanca_Lab_Guide.pdf"
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


def main():
    inv = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
    page = (SRC / "lab_guide.html").read_text(encoding="utf-8")
    page = page.replace("<!--CABLING-->", cabling()).replace("<!--LEAFPORTS-->", leaf_ports(inv))
    page = page.replace("<head>", f'<head>\n<base href="{SRC.as_uri()}/">', 1)
    browser = next((b for b in BROWSERS if Path(b).exists()), None)
    if not browser:
        sys.exit("no Edge/Chrome found for the PDF export")
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "lab_guide.html"
        f.write_text(page, encoding="utf-8")
        subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--user-data-dir={Path(tmp) / 'profile'}", f"--print-to-pdf={OUT}", f.as_uri()],
                       check=True, timeout=180, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"{OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
