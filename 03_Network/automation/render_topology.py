"""Render the live GNS3 project (node positions, links, zone drawings) to a PNG for the report.

  python automation/render_topology.py [out.png]
Colours follow the device role; links are coloured by segment type (WAN, transit, data, management).
"""
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
import labctl  # noqa: E402

NET = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else NET / "screenshots" / "02_topologie_gns3.png"

api = labctl.Gns3()
P = api.open(api.project())
nodes = {n["node_id"]: n for n in api.nodes(P)}
links = api.links(P)
drawings = api.req("GET", f"/projects/{P['project_id']}/drawings")

ROLE = [  # (regex on name, fill, edge, text)
    (r"^ISP|^NAT", "#ECEBE6", "#8A877C", "#3A372F"),
    (r"^EDGE", "#E2F3F1", "#2E8B7F", "#14514A"),
    (r"^FW", "#FBEAE6", "#C0533A", "#7A2A18"),
    (r"^CORE", "#E3EEF8", "#3B6EA8", "#1D3E66"),
    (r"^LEAF", "#E8F2E4", "#4E8F3A", "#2B5520"),
    (r"^SW-", "#F2F2F2", "#8C8C8C", "#333333"),
    (r"^SRV|^ADMIN", "#F6F0FA", "#7D5BA6", "#4A2F6E"),
    (r".*", "#FFF6E5", "#C77700", "#6B4000"),
]


def style(name):
    for rx, *c in ROLE:
        if re.match(rx, name):
            return c


def link_color(a, b):
    names = {a, b}
    if any(n.startswith(("ISP", "NAT")) for n in names):
        return "#8A877C", 1.6
    if "SW-MGMT" in names:
        return "#B0B0B0", 0.9
    if "SW-OUT" in names or names <= {"EDGE-A", "EDGE-B"} or names <= {"FW-A", "FW-B"}:
        return "#C0533A", 1.6
    if any(n.startswith("FW") for n in names) or names <= {"CORE-A", "CORE-B"}:
        return "#3B6EA8", 1.8
    return "#5E8F52", 1.0


fig, ax = plt.subplots(figsize=(12, 7.6), dpi=200)
ax.set_aspect("equal")
ax.axis("off")
# zone drawings (svg rect + title)
for d in drawings:
    m = re.search(r'height="(\d+)" width="(\d+)"', d["svg"])
    col = re.search(r'fill="(#[0-9a-fA-F]{6})"', d["svg"])
    title = re.search(r">([^<]+)</text>", d["svg"])
    if not m:
        continue
    h, w = int(m.group(1)), int(m.group(2))
    c = col.group(1) if col else "#999999"
    ax.add_patch(FancyBboxPatch((d["x"], -d["y"] - h), w, h, boxstyle="round,pad=0,rounding_size=14",
                                fc=c, alpha=0.08, ec=c, lw=1.2, ls="--"))
    if title:
        ax.text(d["x"] + 14, -d["y"] - 22, title.group(1), fontsize=8, color=c, weight="bold", va="center")

centre = {nid: (n["x"] + n["width"] / 2, -(n["y"] + n["height"] / 2)) for nid, n in nodes.items()}
for l in links:
    a, b = (nodes[e["node_id"]] for e in l["nodes"])
    (x1, y1), (x2, y2) = centre[a["node_id"]], centre[b["node_id"]]
    c, w = link_color(a["name"], b["name"])
    ax.plot([x1, x2], [y1, y2], color=c, lw=w, alpha=0.85, zorder=1, solid_capstyle="round")
for nid, n in nodes.items():
    x, y = centre[nid]
    fill, edge, txt = style(n["name"])
    w = 168 if n["name"].startswith(("SRV", "SYSLOG", "BMS", "CCTV", "ADMIN")) else 138
    ax.add_patch(FancyBboxPatch((x - w / 2, y - 24), w, 48, boxstyle="round,pad=0,rounding_size=8",
                                fc=fill, ec=edge, lw=1.3, zorder=3))
    dense = n["name"].startswith(("SRV", "SYSLOG", "BMS", "CCTV", "ADMIN"))
    ax.text(x, y + 6, n["name"], ha="center", va="center", fontsize=6.0 if dense else 7.6, weight="bold", color=txt, zorder=4)
    kind = {"qemu": "QEMU", "docker": "Docker", "ethernet_switch": "switch GNS3", "nat": "NAT"}.get(n["node_type"], n["node_type"])
    ax.text(x, y - 12, kind, ha="center", va="center", fontsize=5.0 if dense else 5.8, color=txt, alpha=0.8, zorder=4)

xs = [c[0] for c in centre.values()]
ys = [c[1] for c in centre.values()]
for d in drawings:
    m = re.search(r'height="(\d+)" width="(\d+)"', d["svg"])
    if m:
        xs += [d["x"], d["x"] + int(m.group(2))]
        ys += [-d["y"], -d["y"] - int(m.group(1))]
ax.set_xlim(min(xs) - 30, max(xs) + 30)
ax.set_ylim(min(ys) - 30, max(ys) + 30)
legend = [("#8A877C", "WAN / Internet"), ("#C0533A", "Transit externe 901, synchro HA"),
          ("#3B6EA8", "Transit interne 902, ISL cœur"), ("#5E8F52", "Uplinks Leaf, serveurs"), ("#B0B0B0", "Management OOB")]
for i, (c, t) in enumerate(legend):
    ax.plot([], [], color=c, lw=2.2, label=t)
ax.legend(loc="lower left", fontsize=6.8, frameon=False, ncol=5, bbox_to_anchor=(0, -0.07))
OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT, bbox_inches="tight", facecolor="white")
print(f"{OUT}  nodes={len(nodes)} links={len(links)}")
