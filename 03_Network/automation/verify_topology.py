"""Compare the live GNS3 project with inventory/dc_casa.yaml (links + switch port VLANs).

Exit 0 when every inventory link exists in GNS3 and no unexpected link is present.
"""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import labctl  # noqa: E402

NET = Path(__file__).resolve().parents[1]
INV = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
api = labctl.Gns3()
P = api.open(api.project())
nodes = {n["node_id"]: n for n in api.nodes(P)}


def pname(n, a, p):
    for pt in n["ports"]:
        if pt["adapter_number"] == a and pt["port_number"] == p:
            return pt["short_name"] if n["node_type"] == "qemu" and pt["short_name"].startswith("Gi") else pt["name"]
    return f"{a}/{p}"


live = set()
for l in api.links(P):
    ends = []
    for e in l["nodes"]:
        n = nodes[e["node_id"]]
        ends.append(f"{n['name']}:{pname(n, e['adapter_number'], e['port_number'])}")
    live.add(tuple(sorted(ends)))

want = set()
for dev, d in INV["devices"].items():
    for port, p in d["ports"].items():
        want.add(tuple(sorted([f"{dev}:{port}", p["to"]])))
for sw, s in INV["lab_switches"].items():
    for port, p in s["ports"].items():
        want.add(tuple(sorted([f"{sw}:{port}", p["to"]])))
for isp, i in INV["isps"].items():
    for port, l in i["links"].items():
        dport = next(pp for pp, v in INV["devices"][l["peer"]]["ports"].items() if v["to"] == f"{isp}:{port}")
        want.add(tuple(sorted([f"{isp}:{port}", f"{l['peer']}:{dport}"])))
for nat, u in INV["internet_uplinks"].items():
    want.add(tuple(sorted([f"{nat}:nat0", u["to"]])))

missing, extra = sorted(want - live), sorted(live - want)
vlan_err = []
by_name = {n["name"]: n for n in nodes.values()}
for sw, s in INV["lab_switches"].items():
    pm = {m["name"]: m for m in by_name[sw]["properties"]["ports_mapping"]}
    for port, p in s["ports"].items():
        m = pm.get(port, {})
        if m.get("vlan") != p["vlan"] or m.get("type", "access") != p.get("type", "access"):
            vlan_err.append(f"{sw}:{port} has {m.get('type')}/{m.get('vlan')}, want {p.get('type', 'access')}/{p['vlan']}")

print(f"live links: {len(live)}  inventory links: {len(want)}  nodes: {len(nodes)}")
for m in missing:
    print("  MISSING in GNS3:", " <-> ".join(m))
for x in extra:
    print("  EXTRA in GNS3:  ", " <-> ".join(x))
for v in vlan_err:
    print("  VLAN mismatch:  ", v)
ok = not (missing or extra or vlan_err)
print("RESULT:", "OK - GNS3 topology matches the inventory" if ok else "DIFFERENCES FOUND")
sys.exit(0 if ok else 1)
