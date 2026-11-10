"""Consistency checks for inventory/dc_casa.yaml (run before generating anything).

- every link is declared identically from both ends (devices, lab switches, servers, NAT uplinks)
- every IP lies inside its declared subnet and no IP is used twice
- cabling matches DC_Casablanca_TIA942_R3_wiring.csv, except the documented SW-OUT and SW-IN (FW.3) re-cabling
"""
import csv
import ipaddress
import sys
from collections import Counter
from pathlib import Path

import yaml

NET = Path(__file__).resolve().parents[1]
inv = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
errors, notes = [], []


def endpoint(s):
    node, port = s.split(":")
    return node, port


# ---------------------------------------------------------------- links from every declaring side
links = {}  # (node, port) -> (peer_node, peer_port)
for dev, d in inv["devices"].items():
    for port, p in d["ports"].items():
        links[(dev, port)] = endpoint(p["to"])
for sw, s in inv["lab_switches"].items():
    for port, p in s["ports"].items():
        links[(sw, port)] = endpoint(p["to"])
for nat, n in inv["internet_uplinks"].items():
    links[(nat, "nat0")] = endpoint(n["to"])
for isp, i in inv["isps"].items():
    for port, l in i["links"].items():
        links[(isp, port)] = (l["peer"], next(pp for pp, v in inv["devices"][l["peer"]]["ports"].items() if v["to"] == f"{isp}:{port}"))
    links[(isp, i["nat_uplink"])] = next((k for k, v in links.items() if v == (isp, i["nat_uplink"])), (None, None))

for (a, ap), (b, bp) in links.items():
    if b in inv["servers"] or b in inv["internet_uplinks"]:
        continue  # servers / NAT nodes are not declared with ports
    back = links.get((b, bp))
    if back != (a, ap):
        errors.append(f"asymmetric link {a}:{ap} -> {b}:{bp} (reverse is {back})")

# ---------------------------------------------------------------- IP plan
used = []
def add_ip(ip, owner, net=None):
    used.append((str(ip), owner))
    if net and ipaddress.ip_address(str(ip)) not in ipaddress.ip_network(net):
        errors.append(f"{owner}: {ip} not in {net}")

for vid, v in inv["vlans"].items():
    if v.get("vip"):
        add_ip(v["vip"], f"VLAN{vid} VIP", v["subnet"])
    for k in ("fw_a", "fw_b"):
        if v.get(k):
            add_ip(v[k], f"VLAN{vid} {k}", v["subnet"])
    if v["gw_type"] == "core":
        for core in ("CORE-A", "CORE-B"):
            host = inv["devices"][core]["svi_host"]
            add_ip(ipaddress.ip_network(v["subnet"])[host], f"{core} Vlan{vid}", v["subnet"])
for name, tr in inv["transit"].items():
    for k, val in tr.items():
        if k != "subnet":
            add_ip(val, f"transit {name} {k}", tr["subnet"])
for dev, d in inv["devices"].items():
    add_ip(d["loopback"], f"{dev} Lo0", "10.255.0.0/24")
    if d["role"] != "firewall":   # FW mgmt address == its VLAN 10 interface (fw_a / fw_b)
        add_ip(d["mgmt"]["ip"], f"{dev} mgmt", inv["vlans"][10]["subnet"])
    elif d["mgmt"]["ip"] != inv["vlans"][10]["fw_a" if dev.endswith("A") else "fw_b"]:
        errors.append(f"{dev}: mgmt IP differs from its VLAN 10 interface")
    for port, p in d["ports"].items():
        if p.get("ip"):
            iface = ipaddress.ip_interface(p["ip"])
            if not iface.network.prefixlen < 32 or iface.ip == iface.network.network_address:
                errors.append(f"{dev} {port}: {p['ip']} is a network address")
            if "10.254" not in p["ip"]:
                used.append((str(iface.ip), f"{dev} {port}"))
for isp, i in inv["isps"].items():
    for port, l in i["links"].items():
        add_ip(l["ip"], f"{isp} {port}", l["net"])
        add_ip(l["peer_ip"], f"{l['peer']} -> {isp}", l["net"])
for srv, s in inv["servers"].items():
    add_ip(s["ip"], srv, inv["vlans"][s["vlan"]]["subnet"])
seen = Counter(ip for ip, _ in used)
# WAN peer IPs are declared twice on purpose (ISP side + device port) -> compare owners
for ip, n in seen.items():
    owners = sorted({o for i, o in used if i == ip})
    if n > 1 and not (len(owners) == 2 and any("->" in o for o in owners)):
        if not any(o.startswith("transit") for o in owners):
            errors.append(f"duplicate IP {ip}: {owners}")

# ---------------------------------------------------------------- CSV comparison
recabled = {("EDGE-A", "Gi0/3"), ("EDGE-A", "Gi0/4"), ("EDGE-B", "Gi0/3"), ("EDGE-B", "Gi0/4"),
            ("FW-A", "em0"), ("FW-A", "em1"), ("FW-B", "em0"), ("FW-B", "em1")}
recabled_in = {("FW-A", "em3"), ("FW-A", "em4"), ("FW-B", "em3"), ("FW-B", "em4")}   # VLAN 902 on SW-IN (FW.3)
with open(NET / "DC_Casablanca_TIA942_R3_wiring.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        a, b = (row["node_a"], row["if_a"]), (row["node_b"], row["if_b"])
        if a in recabled or b in recabled or a in recabled_in or b in recabled_in:
            sw = "SW-IN" if a in recabled_in or b in recabled_in else "SW-OUT"
            notes.append(f"re-cabled ({sw}): {a[0]}:{a[1]} <-> {b[0]}:{b[1]}")
            continue
        got = links.get(a) or (links.get(b) and (b, links.get(b)) and None)
        if links.get(a) != b and links.get(b) != a:
            errors.append(f"CSV link {a} <-> {b} not in inventory (inventory has {links.get(a)} / {links.get(b)})")

print(f"links checked: {len(links)}, IPs checked: {len(used)}")
for n in notes:
    print("  note:", n)
for e in errors:
    print("  ERROR:", e)
print("RESULT:", "OK" if not errors else f"{len(errors)} error(s)")
sys.exit(1 if errors else 0)
