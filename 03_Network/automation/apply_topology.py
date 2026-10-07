"""Bring the live GNS3 project in line with the inventory (idempotent, via the GNS3 API).

Changes (plan §2.1):
  * SW-OUT built-in switch = VLAN 901 segment; the 4 direct Edge<->FW links are replaced by
    EDGE-A Gi0/3, EDGE-B Gi0/3, FW-A em0, FW-B em0 -> SW-OUT
  * ISP-A / ISP-B get a 3rd interface (eth2) linked to GNS3 NAT nodes NAT-A / NAT-B (real Internet)
  * ADMIN-WS (gns3/webterm, VNC) on SW-MGMT Ethernet11, VLAN 90
  * port VLANs of SW-OUT, SW-DMZ and SW-MGMT from inventory.lab_switches (FW em6 = 802.1Q trunk)
Re-running is safe: existing nodes/links are detected and left untouched.
"""
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import labctl  # noqa: E402

NET = Path(__file__).resolve().parents[1]
INV = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
api = labctl.Gns3()
P = api.open(api.project())
PID = P["project_id"]
log = []


def nodes():
    return {n["name"]: n for n in api.nodes(P)}


def port_of(node, port_name):
    for pt in node["ports"]:
        if pt["name"] == port_name or pt["short_name"] == port_name:
            return pt["adapter_number"], pt["port_number"]
    raise KeyError(f"{node['name']}:{port_name} (ports: {[p['name'] for p in node['ports']]})")


def link_at(node, port_name):
    a, p = port_of(node, port_name)
    for l in api.links(P):
        for e in l["nodes"]:
            if e["node_id"] == node["node_id"] and e["adapter_number"] == a and e["port_number"] == p:
                return l
    return None


def ensure_link(n1, p1, n2, p2):
    N = nodes()
    a, b = N[n1], N[n2]
    la, lb = link_at(a, p1), link_at(b, p2)
    if la and lb and la["link_id"] == lb["link_id"]:
        return
    for l in (la, lb):
        if l:
            api.req("DELETE", f"/projects/{PID}/links/{l['link_id']}")
            log.append(f"removed link on {n1}:{p1} / {n2}:{p2}")
    (aa, ap), (ba, bp) = port_of(a, p1), port_of(b, p2)
    api.req("POST", f"/projects/{PID}/links", {"nodes": [
        {"node_id": a["node_id"], "adapter_number": aa, "port_number": ap},
        {"node_id": b["node_id"], "adapter_number": ba, "port_number": bp}]})
    log.append(f"link {n1}:{p1} <-> {n2}:{p2}")


def ensure_node(name, body):
    N = nodes()
    if name in N:
        return N[name]
    body = {"name": name, "compute_id": "vm", **body}
    n = api.req("POST", f"/projects/{PID}/nodes", body)
    log.append(f"node {name} ({body['node_type']}) created")
    return n


def stop(name):
    n = nodes()[name]
    if n["status"] != "stopped":
        api.stop(P, n)


def switch_mapping(sw_name, n_ports):
    sw = INV["lab_switches"][sw_name]
    mapping = []
    for i in range(n_ports):
        p = sw["ports"].get(f"Ethernet{i}", {"vlan": 999})
        mapping.append({"name": f"Ethernet{i}", "port_number": i,
                        "type": p.get("type", "access"), "vlan": p["vlan"],
                        **({"ethertype": "0x8100"} if p.get("type") == "dot1q" else {})})
    return mapping


# ------------------------------------------------------------------ 1. SW-OUT and the VLAN 901 segment
for d in ("EDGE-A", "EDGE-B", "FW-A", "FW-B"):
    stop(d)
N = nodes()
for n, p in (("EDGE-A", "Gi0/4"), ("EDGE-B", "Gi0/4"), ("FW-A", "em1"), ("FW-B", "em1")):
    l = link_at(N[n], p)
    if l:
        api.req("DELETE", f"/projects/{PID}/links/{l['link_id']}")
        log.append(f"removed direct Edge-FW link on {n}:{p}")
ensure_node("SW-OUT", {"node_type": "ethernet_switch", "x": -40, "y": -395, "symbol": ":/symbols/classic/ethernet_switch.svg",
                       "properties": {"ports_mapping": switch_mapping("SW-OUT", 4)}})
for port, p in INV["lab_switches"]["SW-OUT"]["ports"].items():
    dev, dport = p["to"].split(":")
    ensure_link("SW-OUT", port, dev, dport)

# ------------------------------------------------------------------ 2. Internet uplinks
for isp, i in INV["isps"].items():
    n = nodes()[isp]
    if n["properties"]["adapters"] < 3:
        stop(isp)
        api.update_node(P, n, {"properties": {"adapters": 3}})
        log.append(f"{isp}: adapters 2 -> 3")
for nat, u in INV["internet_uplinks"].items():
    isp = u["to"].split(":")[0]
    x = nodes()[isp]["x"]
    ensure_node(nat, {"node_type": "nat", "x": x, "y": -760, "symbol": ":/symbols/classic/cloud.svg"})
    ensure_link(nat, "nat0", isp, u["to"].split(":")[1])

# ------------------------------------------------------------------ 3. ADMIN-WS
ensure_node("ADMIN-WS", {"node_type": "docker", "x": 1000, "y": -230, "symbol": ":/symbols/classic/computer.svg",
                         "console_type": "vnc",
                         "properties": {"image": "gns3/webterm:latest", "adapters": 1, "console_resolution": "1280x800",
                                        "environment": "TZ=Africa/Casablanca"}})

# ------------------------------------------------------------------ 4. switch port VLANs (+ SW-MGMT links)
for sw, size in (("SW-OUT", 4), ("SW-DMZ", 8), ("SW-MGMT", 16)):
    n = nodes()[sw]
    want = switch_mapping(sw, size)
    if n["properties"].get("ports_mapping") != want:
        api.update_node(P, n, {"properties": {"ports_mapping": want}})
        log.append(f"{sw}: port VLANs set")
for port, p in INV["lab_switches"]["SW-MGMT"]["ports"].items():
    dev, dport = p["to"].split(":")
    ensure_link("SW-MGMT", port, dev, dport)

# ------------------------------------------------------------------ 5. layered layout + TIA-942 zone drawings
LAYOUT = {
    "NAT-A": (-300, -900), "NAT-B": (300, -900), "ISP-A": (-300, -770), "ISP-B": (300, -770),
    "EDGE-A": (-300, -640), "EDGE-B": (300, -640), "SW-OUT": (0, -565),
    "SRV-WEB-01": (-1050, -425), "SW-DMZ": (-760, -425), "FW-A": (-300, -440), "FW-B": (300, -440),
    "SW-MGMT": (760, -440), "SRV-BASTION": (1050, -470), "ADMIN-WS": (1050, -370),
    "CORE-A": (-300, -300), "CORE-B": (300, -300),
    "LEAF-A1": (-950, -120), "LEAF-A2": (-550, -120), "LEAF-B1": (450, -120), "LEAF-B2": (950, -120),
    "SRV-CMP-01": (-1200, 60), "SRV-CMP-02": (-1000, 60), "SRV-CMP-03": (-800, 60), "SRV-STO-01": (-600, 60),
    "SRV-BCK-01": (200, 60), "SRV-INF-01": (380, 60), "SRV-MON-01": (560, 60), "SRV-DCIM-01": (740, 60),
    "SYSLOG": (920, 60), "BMS-SIM": (1100, 60), "CCTV-SIM": (1280, 60),
}
ZONES = [  # x, y, w, h, title, colour
    (-560, -950, 1180, 440, "ER / MMR – opérateurs et bordure (AS 65100)", "#8A877C"),
    (-1150, -500, 2400, 285, "MDA – pare-feux HA, cœur, DMZ (VLAN 50), management (VLAN 10/90)", "#3B6EA8"),
    (-1260, -165, 860, 300, "Hall A – HDA-A / EDA-A (48 baies)", "#4E8F3A"),
    (150, -165, 1250, 300, "Hall B – HDA-B / EDA-B (48 baies)", "#7D5BA6"),
]
moved = 0
for name, (x, y) in LAYOUT.items():
    n = nodes()[name]
    if (n["x"], n["y"]) != (x, y):
        api.update_node(P, n, {"x": x, "y": y}); moved += 1
if moved:
    log.append(f"layout: {moved} node(s) moved")
existing = api.req("GET", f"/projects/{PID}/drawings")
want = sorted((z[0], z[1], z[3]) for z in ZONES)
have = sorted((d["x"], d["y"], int(re.search(r'height="(\d+)"', d["svg"]).group(1))) for d in existing)
if want != have:
    for d in existing:
        api.req("DELETE", f"/projects/{PID}/drawings/{d['drawing_id']}")
    for x, y, w, h, title, c in ZONES:
        svg = (f'<svg height="{h}" width="{w}"><rect fill="{c}" fill-opacity="0.08" height="{h}" width="{w}" rx="14" '
               f'stroke="{c}" stroke-width="2" stroke-dasharray="8 4" /><text fill="{c}" font-family="Calibri" '
               f'font-size="15" font-weight="bold" x="14" y="24">{title}</text></svg>')
        api.req("POST", f"/projects/{PID}/drawings", {"svg": svg, "x": x, "y": y, "z": 0})
    log.append(f"zones: {len(ZONES)} TIA-942 zone drawings")

# ------------------------------------------------------------------ 6. show interface labels (screenshots)
api.req("PUT", f"/projects/{PID}", {"show_interface_labels": True})

print("\n".join(log) or "already up to date")
N = nodes()
print(f"nodes={len(N)} links={len(api.links(P))}")
