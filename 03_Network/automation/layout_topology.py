"""Lay the live GNS3 canvas out as a clean top-down tier diagram (Internet -> edge -> firewalls -> core -> halls).

A side mirrored on B side so cables run straight and symmetric; soft zone backgrounds with titles.
Moves nodes only (no stop/start, links untouched). Zone drawings are rewritten; node notes are redone after by
label_topology.py (run automatically).  python automation/layout_topology.py
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import labctl  # noqa: E402

Y = dict(nat=-1250, isp=-1050, edge=-850, out=-650, fw=-450, inn=-250, core=-50, leaf=170, srv=400)
POS = {
    "NAT-A": (-260, Y["nat"]), "NAT-B": (260, Y["nat"]), "ISP-A": (-260, Y["isp"]), "ISP-B": (260, Y["isp"]),
    "EDGE-A": (-260, Y["edge"]), "EDGE-B": (260, Y["edge"]), "SW-OUT": (0, Y["out"]),
    "FW-A": (-260, Y["fw"]), "FW-B": (260, Y["fw"]), "SW-IN": (0, Y["inn"]),
    "CORE-A": (-260, Y["core"]), "CORE-B": (260, Y["core"]),
    "SW-DMZ": (700, Y["fw"]), "SRV-WEB-01": (1000, Y["fw"]),
    "SW-MGMT": (-800, Y["fw"] - 80), "ADMIN-WS": (-1220, -620), "SRV-BASTION": (-1220, -330),
    "LEAF-A1": (-850, Y["leaf"]), "LEAF-A2": (-550, Y["leaf"]),
    "LEAF-B1": (750, Y["leaf"]), "LEAF-B2": (1050, Y["leaf"]),
}
for i, n in enumerate(["SRV-CMP-01", "SRV-CMP-02", "SRV-CMP-03", "SRV-STO-01"]):
    POS[n] = (-1105 + 270 * i, Y["srv"])
for i, n in enumerate(["SRV-BCK-01", "SRV-INF-01", "SRV-MON-01", "SYSLOG", "SRV-DCIM-01", "BMS-SIM", "CCTV-SIM"]):
    POS[n] = (90 + 270 * i, Y["srv"])

# title, x, y, w, h, colour
ZONES = [
    ("INTERNET - ISP simulators (AS64500 / AS64501) + NAT clouds", -560, -1300, 1120, 360, "#4a90d9"),
    ("ENTRANCE ROOM (ER) - edge routers, eBGP, transit VLAN 901", -560, -900, 1120, 360, "#7b8794"),
    ("MDA SECURITY - pfSense HA (CARP/pfsync), transit VLAN 902", -560, -500, 1120, 380, "#d9534f"),
    ("DMZ - VLAN 50", 620, -500, 680, 240, "#f0ad4e"),
    ("MANAGEMENT OOB - VLAN 10 + ADMIN VLAN 90", -1300, -700, 680, 580, "#8e6bbf"),
    ("MDA CORE - L3 gateways (HSRP), OSPF, LACP", -560, -100, 1120, 200, "#2a9d8f"),
    ("HALL A (HDA-A / EDA-A) - compute + storage", -1300, 130, 1140, 500, "#5cb85c"),
    ("HALL B (HDA-B / EDA-B) - backup, services, supervision, BMS/CCTV", 40, 130, 1960, 500, "#3c9d5d"),
]


def main():
    api = labctl.Gns3()
    p = api.open(api.project())
    pid = p["project_id"]
    for d in api.req("GET", f"/projects/{pid}/drawings"):
        if 'font-family="Consolas"' not in d.get("svg", ""):
            api.req("DELETE", f"/projects/{pid}/drawings/{d['drawing_id']}")
    moved = 0
    for n in api.nodes(p):
        if n["name"] in POS:
            x, y = POS[n["name"]]
            api.req("PUT", f"/projects/{pid}/nodes/{n['node_id']}", dict(x=x, y=y))
            moved += 1
        else:
            print("not placed:", n["name"])
    for title, x, y, w, h, c in ZONES:
        api.req("POST", f"/projects/{pid}/drawings", dict(x=x, y=y, z=0, svg=(
            f'<svg width="{w}" height="{h}"><rect width="{w}" height="{h}" rx="18" ry="18" fill="{c}" '
            f'fill-opacity="0.07" stroke="{c}" stroke-width="2" stroke-opacity="0.6" /></svg>')))
        api.req("POST", f"/projects/{pid}/drawings", dict(x=x + 14, y=y + 8, z=1, svg=(
            f'<svg width="{len(title) * 8}" height="22"><text font-family="Verdana" font-size="11.0" '
            f'font-weight="bold" fill="{c}" fill-opacity="1.0">{title}</text></svg>')))
    print(f"{moved} nodes placed, {len(ZONES)} zones drawn")
    subprocess.run([sys.executable, str(Path(__file__).with_name("label_topology.py"))], check=True)


if __name__ == "__main__":
    main()
