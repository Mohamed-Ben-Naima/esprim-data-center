#!/usr/bin/env python3
"""Generate DC_Casablanca_TIA942_R3.gns3 (Phase 1 inventory + A/B cabling)."""
import json, uuid, csv, sys

# ---- EDIT THESE to match the image filenames in your GNS3 installation ----
IMG_IOSV   = "vios-adventerprisek9-m.vmdk"      # Cisco IOSv   (Edge)
IMG_IOSVL2 = "vios_l2-adventerprisek9-m.vmdk"   # Cisco IOSvL2 (Core / Leaf)
IMG_PFSENSE = "pfSense-CE.qcow2"                # pfSense
IMG_LINUX  = "debian-12-genericcloud.qcow2"     # Linux server VM
IMG_FRR    = "frrouting/frr:latest"
IMG_TERM   = "gns3/ipterm:latest"
IMG_WEB    = "nginx:alpine"
# --------------------------------------------------------------------------

PROJECT_NAME = "DC_Casablanca_TIA942_R3"
OUT = f"/mnt/user-data/outputs/{PROJECT_NAME}.gns3"
WIRING = f"/mnt/user-data/outputs/{PROJECT_NAME}_wiring.csv"

nodes, links, wiring = {}, [], []
counter = {}

def uid(): return str(uuid.uuid4())

def add(name, kind, x, y, **kw):
    nodes[name] = dict(name=name, kind=kind, x=x, y=y, id=uid(), **kw)
    counter[name] = 0

def port(name):
    n = counter[name]; counter[name] += 1
    return n

def pname(name, adapter):
    k = nodes[name]["kind"]
    if k == "iosv":   return f"Gi0/{adapter}"
    if k == "iosvl2": return f"Gi{adapter // 4}/{adapter % 4}"
    if k == "pfsense": return f"em{adapter}"
    if k == "switch": return f"Ethernet{adapter}"
    return f"eth{adapter}"

def connect(a, b, role):
    # ethernet switches: always adapter 0, port = next free
    ends = []
    for n in (a, b):
        p = port(n)
        if nodes[n]["kind"] == "switch": ends.append((n, 0, p))
        else: ends.append((n, p, 0))
    links.append(ends)
    wiring.append([role, a, pname(a, ends[0][1] if nodes[a]["kind"] != "switch" else ends[0][2]),
                   b, pname(b, ends[1][1] if nodes[b]["kind"] != "switch" else ends[1][2])])

# ------------------------------------------------------------------ nodes
add("ISP-A", "docker", -300, -620, image=IMG_FRR, sym="docker_guest")
add("ISP-B", "docker",  300, -620, image=IMG_FRR, sym="docker_guest")
add("EDGE-A", "iosv", -300, -470, sym="router")
add("EDGE-B", "iosv",  300, -470, sym="router")
add("FW-A", "pfsense", -300, -320, sym="firewall")
add("FW-B", "pfsense",  300, -320, sym="firewall")
add("CORE-A", "iosvl2", -300, -170, sym="multilayer_switch")
add("CORE-B", "iosvl2",  300, -170, sym="multilayer_switch")
add("LEAF-A1", "iosvl2", -700, 0, sym="ethernet_switch")
add("LEAF-A2", "iosvl2", -300, 0, sym="ethernet_switch")
add("LEAF-B1", "iosvl2",  300, 0, sym="ethernet_switch")
add("LEAF-B2", "iosvl2",  700, 0, sym="ethernet_switch")

for i, (n, x) in enumerate([("SRV-CMP-01", -800), ("SRV-CMP-02", -650),
                            ("SRV-CMP-03", -500), ("SRV-STO-01", -350)]):
    add(n, "linux", x, 170, ram=512, sym="qemu_guest")
for n, x in [("SRV-BCK-01", 200), ("SRV-INF-01", 330), ("SRV-MON-01", 460)]:
    add(n, "linux", x, 170, ram=512 if n != "SRV-MON-01" else 1024, sym="qemu_guest")
add("SRV-BASTION", "linux", 1000, -320, ram=512, sym="qemu_guest")

add("SRV-DCIM-01", "docker", 590, 170, image=IMG_TERM, sym="docker_guest")
add("SYSLOG",   "docker", 720, 170, image=IMG_TERM, sym="docker_guest")
add("BMS-SIM",  "docker", 850, 170, image=IMG_TERM, sym="docker_guest")
add("CCTV-SIM", "docker", 980, 170, image=IMG_TERM, sym="docker_guest")
add("SRV-WEB-01", "docker", -1000, -320, image=IMG_WEB, sym="docker_guest")

add("SW-DMZ",  "switch", -750, -320, sym="ethernet_switch", ports=8)
add("SW-MGMT", "switch",  750, -320, sym="ethernet_switch", ports=16)

# ------------------------------------------------------------------ links
for isp in ("ISP-A", "ISP-B"):
    for edge in ("EDGE-A", "EDGE-B"):
        connect(isp, edge, "WAN eBGP")
connect("EDGE-A", "EDGE-B", "iBGP")
for edge in ("EDGE-A", "EDGE-B"):
    for fw in ("FW-A", "FW-B"):
        connect(edge, fw, "Edge-FW (outside)")
connect("FW-A", "FW-B", "FW HA sync 10.254.3.0/30")
for fw in ("FW-A", "FW-B"):
    for core in ("CORE-A", "CORE-B"):
        connect(fw, core, "FW-Core (inside)")
connect("CORE-A", "CORE-B", "Core ISL #1")
connect("CORE-A", "CORE-B", "Core ISL #2")
for core in ("CORE-A", "CORE-B"):
    for leaf in ("LEAF-A1", "LEAF-A2", "LEAF-B1", "LEAF-B2"):
        connect(core, leaf, "Core-Leaf uplink")
for fw in ("FW-A", "FW-B"):
    connect(fw, "SW-DMZ", "FW-DMZ")
connect("SRV-WEB-01", "SW-DMZ", "DMZ web")

# servers dual-homed to the two leafs of their hall
for s in ("SRV-CMP-01", "SRV-CMP-02", "SRV-CMP-03", "SRV-STO-01"):
    connect(s, "LEAF-A1", "Hall A server NIC0")
    connect(s, "LEAF-A2", "Hall A server NIC1")
for s in ("SRV-BCK-01", "SRV-INF-01", "SRV-MON-01", "SRV-DCIM-01"):
    connect(s, "LEAF-B1", "Hall B server NIC0")
    connect(s, "LEAF-B2", "Hall B server NIC1")
connect("SYSLOG", "LEAF-B1", "Hall B service")
connect("BMS-SIM", "LEAF-B2", "Hall B service")
connect("CCTV-SIM", "LEAF-B2", "Hall B service")

# out-of-band management (last adapter of each device)
for n in ("EDGE-A", "EDGE-B", "FW-A", "FW-B", "CORE-A", "CORE-B",
          "LEAF-A1", "LEAF-A2", "LEAF-B1", "LEAF-B2", "SRV-BASTION"):
    connect(n, "SW-MGMT", "OOB management")

# ------------------------------------------------------------------ build JSON
CAP = {"iosv": 8, "iosvl2": 16, "pfsense": 8}
for n, v in nodes.items():
    if v["kind"] in CAP:
        assert counter[n] <= CAP[v["kind"]], (n, counter[n])

def node_json(n):
    v, c = nodes[n], counter[n]
    base = dict(compute_id="local", console_auto_start=False, console_type="telnet",
                height=45, width=66, locked=False, name=n, node_id=v["id"],
                x=v["x"], y=v["y"], z=1,
                label=dict(rotation=0, style="font-family: TypeWriter;font-size: 10.0;font-weight: bold;",
                           text=n, x=-5, y=-25),
                symbol=f":/symbols/classic/{v['sym']}.svg")
    k = v["kind"]
    qemu_common = dict(platform="x86_64", qemu_path="", cpus=1, linked_clone=True, on_close="power_off",
                       options="", boot_priority="c", cpu_throttling=0, process_priority="normal",
                       replicate_network_connection_state=True)
    if k == "iosv":
        base.update(node_type="qemu", first_port_name="", port_name_format="Gi0/{0}", port_segment_size=0,
                    properties=dict(qemu_common, adapters=CAP[k], adapter_type="e1000",
                                    hda_disk_image=IMG_IOSV, hda_disk_interface="virtio", ram=1024))
    elif k == "iosvl2":
        ram = 1024 if n.startswith("CORE") else 768
        base.update(node_type="qemu", first_port_name="", port_name_format="Gi{0}/{1}", port_segment_size=4,
                    properties=dict(qemu_common, adapters=CAP[k], adapter_type="e1000",
                                    hda_disk_image=IMG_IOSVL2, hda_disk_interface="virtio", ram=ram))
    elif k == "pfsense":
        base.update(node_type="qemu", first_port_name="", port_name_format="em{0}", port_segment_size=0,
                    properties=dict(qemu_common, adapters=CAP[k], adapter_type="e1000", cpus=2,
                                    hda_disk_image=IMG_PFSENSE, hda_disk_interface="virtio", ram=1536))
    elif k == "linux":
        base.update(node_type="qemu", first_port_name="", port_name_format="eth{0}", port_segment_size=0,
                    properties=dict(qemu_common, adapters=max(c, 1), adapter_type="virtio-net-pci",
                                    hda_disk_image=IMG_LINUX, hda_disk_interface="virtio", ram=v["ram"]))
    elif k == "docker":
        base.update(node_type="docker", port_name_format="eth{0}", port_segment_size=0, first_port_name="",
                    properties=dict(adapters=max(c, 1), image=v["image"], start_command="", environment="",
                                    extra_hosts="", extra_volumes=[], console_resolution="1024x768",
                                    console_http_port=80, console_http_path="/", console_type="telnet"))
    elif k == "switch":
        base.update(node_type="ethernet_switch", console_type="none", port_name_format="Ethernet{0}",
                    port_segment_size=0, first_port_name="",
                    properties=dict(ports_mapping=[dict(name=f"Ethernet{i}", port_number=i, type="access", vlan=1)
                                                   for i in range(v["ports"])]))
        base["console_type"] = "none"
    return base

link_json = []
for (a, b) in links:
    link_json.append(dict(
        link_id=uid(), filters={}, link_style={}, suspend=False,
        nodes=[dict(node_id=nodes[n]["id"], adapter_number=ad, port_number=pt) for (n, ad, pt) in (a, b)]))

def zone(x, y, w, h, title, color):
    svg = (f'<svg height="{h}" width="{w}"><rect fill="{color}" fill-opacity="0.12" height="{h}" width="{w}" '
           f'rx="12" stroke="{color}" stroke-width="2" stroke-dasharray="8 4" />'
           f'<text fill="#444444" font-family="TypeWriter" font-size="16" font-weight="bold" x="12" y="24">{title}</text></svg>')
    return dict(drawing_id=uid(), rotation=0, svg=svg, x=x, y=y, z=0, locked=False)

drawings = [
    zone(-480, -700, 960, 130, "INTERNET / WAN  (ISP AS64500 / AS64501)", "#1f77b4"),
    zone(-480, -540, 960, 130, "EDGE  (AS 65100)", "#17becf"),
    zone(-480, -390, 960, 130, "FIREWALL HA  (FW-A ACTIVE / FW-B STANDBY)", "#d62728"),
    zone(-480, -240, 960, 130, "CORE  (OSPF / HSRP)", "#ff7f0e"),
    zone(-900, -70, 800, 330, "HALL A  (48 racks)", "#2ca02c"),
    zone(100, -70, 1000, 330, "HALL B  (48 racks)", "#9467bd"),
    zone(-1100, -400, 450, 160, "DMZ  (VLAN 50)", "#e377c2"),
    zone(650, -400, 450, 160, "MANAGEMENT  (VLAN 90)", "#7f7f7f"),
]

project = dict(
    project_id=uid(), name=PROJECT_NAME, type="topology", revision=9, version="2.2.50",
    auto_start=False, auto_close=True, auto_open=False,
    scene_width=2600, scene_height=1600, zoom=100,
    show_layers=False, show_grid=False, show_interface_labels=False, snap_to_grid=False,
    grid_size=75, drawing_grid_size=25, supplier=None, variables=None,
    topology=dict(computes=[], drawings=drawings, links=link_json,
                  nodes=[node_json(n) for n in nodes]))

with open(OUT, "w") as f: json.dump(project, f, indent=2)
with open(WIRING, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["role", "node_a", "if_a", "node_b", "if_b"]); w.writerows(wiring)
print(len(nodes), "nodes,", len(links), "links")
