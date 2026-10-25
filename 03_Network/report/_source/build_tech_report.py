"""Build the technical onboarding report of the lab (English): report/DC_Casablanca_Technical_Report.pdf

  python report/_source/build_tech_report.py

Everything that is a value (addresses, ports, rules, interfaces, credentials) is read from the source of truth
(inventory/dc_casa.yaml) or from the generated configurations (configs/), so the report cannot drift from the lab.
The prose explains the why. Styles and the PDF printer are those of the lab guide (build_lab_guide.py).
"""
import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

SRC = Path(__file__).resolve().parent
NET = SRC.parents[1]
sys.path.insert(0, str(SRC))
from build_lab_guide import BROWSERS, cabling, leaf_ports, table  # noqa: E402

INV = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
CFG = {p.stem: p.read_text(encoding="utf-8") for p in (NET / "configs").glob("*.cfg")}
OUT = NET / "report" / "DC_Casablanca_Technical_Report.pdf"
E = html.escape
V, TR, C, SITE, SVC = INV["vlans"], INV["transit"], INV["credentials"], INV["site"], INV["services"]


# ------------------------------------------------------------------------------------------ helpers
def block(dev, header):
    """Lines of the configuration block that starts with `header` (up to the next '!')."""
    lines, out, on = CFG[dev].splitlines(), [], False
    for ln in lines:
        if ln.rstrip() == header or (header.endswith("*") and ln.startswith(header[:-1])):
            on = True
        elif on and ln.startswith("!") and not ln.startswith("! "):
            if not header.endswith("*"):
                break
            on = False
            continue
        if on:
            out.append(ln)
    return "\n".join(out)


def pre(text, title=None):
    t = f'<p class="cap"><b>{E(title)}</b></p>' if title else ""
    body = re.sub(r"(?m)^(\s*(?:remark|description) .*)$", r'<span class="c">\1</span>', E(text))
    return t + f"<pre>{body}</pre>"


def pill(state):
    cls = {"Met": "ok", "Done": "ok", "Partial": "wip", "Gap": "bad", "Not in scope": "todo"}.get(state, "todo")
    return f'<span class="pill {cls}">{state}</span>'


def mask(prefix):
    bits = int(prefix)
    return ".".join(str((0xFFFFFFFF << (32 - bits) >> (24 - 8 * i)) & 255) for i in range(4))


def parse_interfaces(dev):
    """Every interface of a Cisco configuration: name, description, L2/L3 settings, HSRP, state."""
    rows = []
    for m in re.finditer(r"(?ms)^interface (\S+)\n(.*?)^!", CFG[dev]):
        name, body = m.group(1), m.group(2)
        g = lambda rx: (re.search(rx, body, re.M) or [None, ""])[1]  # noqa: E731
        desc = g(r"^ description (.*)$")
        desc = desc.split("|", 1)[1].strip() if "|" in desc else desc
        peer = re.search(r"-> (\S+)", g(r"^ description (.*)$"))
        mode = g(r"^ switchport mode (\S+)")
        ip = g(r"^ ip address (\S+ \S+)")
        if ip:
            a, msk = ip.split()
            ip = f"{a}/{sum(bin(int(x)).count('1') for x in msk.split('.'))}"
        vrf = g(r"^ vrf forwarding (\S+)")
        if mode == "access":
            l2 = f"access VLAN {g(r'^ switchport access vlan (\d+)')}"
        elif mode == "trunk":
            l2 = f"trunk {g(r'^ switchport trunk allowed vlan (\S+)')}"
        else:
            l2 = "routed" if ip or name.startswith(("Vlan", "Loop")) else ""
        extra = []
        if g(r"^ channel-group (\d+)"):
            extra.append(f"LACP Po{g(r'^ channel-group (\d+)')} ({g(r'^ channel-group \d+ mode (\S+)')})")
        if g(r"^ standby \d+ ip (\S+)"):
            extra.append(f"HSRP VIP {g(r'^ standby \d+ ip (\S+)')} prio {g(r'^ standby \d+ priority (\d+)') or '100'}")
        if "bpduguard enable" in body:
            extra.append("portfast + bpduguard")
        elif "portfast" in body:
            extra.append("portfast")
        if g(r"^ ip access-group (\S+)"):
            extra.append(f"ACL {g(r'^ ip access-group (\S+)')}")
        if "ip ospf" in body and "ip ospf 1" in body:
            extra.append("OSPF area 0")
        if vrf:
            extra.append(f"VRF {vrf}")
        state = '<span class="pill todo">shut</span>' if re.search(r"^ shutdown", body, re.M) else \
            '<span class="pill ok">up</span>'
        rows.append([f"<b>{name}</b>", E(peer.group(1) if peer else ""), E(l2), E(ip), E(", ".join(extra)), E(desc),
                     state])
    return rows


# ------------------------------------------------------------------------------------------ sections
def cover():
    nodes = len(INV["devices"]) + len(INV["servers"]) + len(INV["lab_switches"]) + 2 + 2
    return f"""
<div class="cover">
  <div class="tag">ESPRIM - Data Center Casablanca - 03_Network</div>
  <div class="title">Technical Report<br>and Onboarding Guide</div>
  <div class="sub">How the lab is wired, addressed, routed, protected, supervised and kept available, with the real
  configuration of every device, the rules, the credentials and the ISO/IEC 27001 mapping.</div>
  <div class="facts">
    <div class="fact"><b>{nodes}</b><span>nodes in the GNS3 project</span></div>
    <div class="fact"><b>{len(V)}</b><span>VLANs (business, transit, parking)</span></div>
    <div class="fact"><b>AS {SITE['asn']}</b><span>BGP to two providers</span></div>
    <div class="fact"><b>2N</b><span>every critical element doubled</span></div>
  </div>
  <div class="state"><b>Read this first</b><br>
    Sections 1-2 give the picture in ten minutes. Sections 3-9 are the reference (addressing, cabling, interfaces,
    routing, aggregation, availability, security). Sections 10-13 cover services, supervision, access and compliance.
    Appendices hold the full interface lists and the credentials.</div>
  <div class="meta">Document date: 25 October 2026. Generated by <span class="mono">report/_source/build_tech_report.py</span>
    from <span class="mono">inventory/dc_casa.yaml</span> and <span class="mono">configs/</span>.<br>
    Design target: ANSI/TIA-942 Rated-3 data center, 96 racks in two halls, about 1 MW of IT load.<br>
    Lab credentials only (Appendix C): never reuse them outside the lab.</div>
</div>"""


def contents():
    items = [("1", "Onboarding in ten minutes", "what it is, how to start it, where to click"),
             ("2", "Architecture and design principles", "layers, zones, 2N, source of truth"),
             ("3", "Addressing plan", "VLANs, gateways, transit, WAN, every IP"),
             ("4", "Cabling", "every link, port maps"),
             ("5", "Interfaces, device by device", "how each port is configured"),
             ("6", "Protocols and routing", "BGP, OSPF, HSRP, CARP, static routes"),
             ("7", "Aggregation and trunking", "LACP, 802.1Q, lagg, bonds"),
             ("8", "High availability and load sharing", "who takes over, how fast"),
             ("9", "Security policy", "firewall rules, NAT, core ACLs, hardening"),
             ("10", "Traffic flows", "five journeys, hop by hop"),
             ("11", "Services", "what runs where, with its configuration"),
             ("12", "Supervision and logs", "Zabbix, Grafana, syslog"),
             ("13", "Administration access and proxy", "webterm, bastion, lab proxy"),
             ("14", "ISO/IEC 27001:2022 conformity", "control by control, with gaps"),
             ("A", "Appendix: all interfaces", ""), ("B", "Appendix: full cabling plan", ""),
             ("C", "Appendix: credentials", ""), ("D", "Appendix: glossary", "")]
    return ('<h1 class="pb">Contents</h1><div class="toc">' +
            "".join(f"<div><b>{n}</b>{t}<small>{s}</small></div>" for n, t, s in items) + "</div>")


def s1_onboarding():
    w = INV["web_interfaces"]
    rows = [[E(x["name"]), f"<code>{E(x['url'])}</code>", E(x["login"] or "-"), E(x["descr"])] for x in w]
    return f"""
<h1 class="pb"><span class="n">1</span>Onboarding in ten minutes</h1>
<h2>What this lab is</h2>
<p>A complete data center network of Casablanca, built in GNS3 on one PC: two Internet providers, two border routers,
a pair of firewalls, two core switches, four access switches (leafs) in two halls, and the servers and simulators
that a real data center runs (web site, DNS/NTP, monitoring, logs, power and rack management, CCTV). It proves the
design of the TIA-942 Rated-3 report: <b>every critical element exists twice</b> and the loss of one does not stop
the service.</p>
<div class="box"><b class="t">The three ideas to keep in mind</b><ul>
<li><b>One source of truth.</b> <code>inventory/dc_casa.yaml</code> describes every address, port, rule and account.
Scripts generate the configurations from it and deploy them. Nobody types a configuration by hand.</li>
<li><b>Two of everything.</b> Providers, routers, firewalls, cores, leafs, server NICs, power paths: A and B.</li>
<li><b>Zones.</b> Internet, DMZ, internal VLANs, management and administration are separate networks; only the
firewalls and the core access lists decide what crosses.</li></ul></div>
<h2>Start, look, stop</h2>
<table><thead><tr><th style="width:34%">Goal</th><th>Command (from <code>03_Network</code>, on the PC)</th></tr></thead><tbody>
<tr><td>Start the demo profile (20 nodes, about 10 min)</td><td><code>python automation/lab_up.py --profile demo</code></td></tr>
<tr><td>Open the lab's web pages from the PC</td><td><code>python automation/lab_proxy.py start</code> then <code>python automation/lab_proxy.py open</code></td></tr>
<tr><td>See every node and its state</td><td><code>python automation/labctl.py status</code></td></tr>
<tr><td>Run a command on any device over SSH</td><td><code>python automation/adminws.py core-a "show standby brief"</code></td></tr>
<tr><td>Supervision health</td><td><code>python automation/zabbix_setup.py status</code></td></tr>
<tr><td>Power-cut demonstration</td><td><code>python automation/power_test.py</code></td></tr>
<tr><td>Stop a node</td><td><code>python automation/labctl.py stop NODE</code> (close the project before stopping the GNS3 VM)</td></tr>
</tbody></table>
<h2>Web interfaces (through the lab proxy)</h2>
{table(["Page", "URL", "Login", "What you see"], rows, ["17%", "27%", "9%", None])}
<p>Passwords are in Appendix C. The certificates are self-signed: accept them in the proxy browser.</p>"""


def s2_architecture():
    return f"""
<h1 class="pb"><span class="n">2</span>Architecture and design principles</h1>
<figure><img src="arch_topology.png" style="max-height:120mm"><figcaption>Logical topology (source:
<code>report/_source/arch_topology.mmd</code>)</figcaption></figure>
<h2>Layers, from the Internet to the racks</h2>
<table><thead><tr><th style="width:17%">Layer</th><th style="width:22%">Equipment</th><th>Role</th><th style="width:13%">TIA-942 space</th></tr></thead><tbody>
<tr><td>Providers</td><td>ISP-A (AS64500), ISP-B (AS64501)</td><td>Simulated Internet (FRR containers); each reaches the real Internet through a GNS3 NAT node.</td><td>outside</td></tr>
<tr><td>Border</td><td>EDGE-A, EDGE-B (Cisco IOSv)</td><td>eBGP to both providers, announce {SITE['public_prefix']}, filter spoofed sources, share a gateway address toward the firewalls.</td><td>ER</td></tr>
<tr><td>Security</td><td>FW-A, FW-B (pfSense 2.7.2)</td><td>Stateful filtering between zones, NAT, CARP virtual addresses, state synchronisation.</td><td>MDA</td></tr>
<tr><td>Core</td><td>CORE-A, CORE-B (IOSvL2)</td><td>Gateways of the internal VLANs (HSRP), inter-VLAN filtering (ACL), spanning-tree roots, OSPF.</td><td>MDA</td></tr>
<tr><td>Access</td><td>LEAF-A1/A2 (hall A), LEAF-B1/B2 (hall B)</td><td>Server ports, dual uplinks to both cores.</td><td>HDA-A / HDA-B</td></tr>
<tr><td>Servers</td><td>Ubuntu VMs and containers</td><td>Web, DNS/NTP, monitoring, logs, DCIM, power and CCTV simulators, bastion, admin webterm.</td><td>EDA-A / EDA-B, DMZ</td></tr>
<tr><td>Out of band</td><td>SW-MGMT</td><td>Management port of every network device (VLAN 10) and the administration zone (VLAN 90).</td><td>MDA</td></tr>
</tbody></table>
<h2>Principles applied</h2>
<table><thead><tr><th style="width:25%">Principle</th><th>How it shows in the lab</th></tr></thead><tbody>
<tr><td><b>Redundancy 2N</b></td><td>Two providers, two edges, two firewalls, two cores, two leafs per hall, two NICs per server, two power paths. No single box carries a service alone.</td></tr>
<tr><td><b>Defence in depth</b></td><td>Anti-spoofing ACL on the edges, stateful firewall between zones, ACL on every core VLAN, host hardening, authentication on routing protocols.</td></tr>
<tr><td><b>Least privilege / default deny</b></td><td>Every firewall interface ends with block + log; each core VLAN ACL lists only the flows it needs; Grafana reads Zabbix with a read-only account.</td></tr>
<tr><td><b>Out-of-band management</b></td><td>Device management lives in VRF <code>MGMT</code> (VLAN 10), never routed by the cores; only the administration zone reaches it, through the firewall.</td></tr>
<tr><td><b>Single entry point for administrators</b></td><td>ADMIN-WS webterm and SRV-BASTION (password + TOTP) in VLAN 90; every session is logged centrally.</td></tr>
<tr><td><b>Infrastructure as code</b></td><td>Inventory → generators (<code>gen_configs.py</code>, <code>gen_pfsense.py</code>) → deploy scripts → audit (<code>fw_audit.py</code> = 0 difference). Git keeps one commit per change.</td></tr>
<tr><td><b>Observe everything</b></td><td>Zabbix polls every device and service; logs go to one collector; Grafana shows the state on one screen.</td></tr>
<tr><td><b>Standard naming</b></td><td>Port descriptions follow TIA-606 (<code>space-device:port -> space-device:port | role</code>).</td></tr>
</tbody></table>
<figure><img src="arch_vlans.png" style="max-height:95mm"><figcaption>Zones and VLANs</figcaption></figure>"""


def s3_addressing():
    rows = []
    who = {}
    for n, s in INV["servers"].items():
        who.setdefault(s["vlan"], []).append(f"{n} {s['ip']}")
    for vid, v in V.items():
        if v["gw_type"] == "core":
            gw = f"HSRP {v['vip']} (active {v['active']})"
        elif v["gw_type"] == "fw":
            gw = f"CARP {v['vip']} (FW-A {v['fw_a']}, FW-B {v['fw_b']})"
        else:
            gw = "-"
        hosts = ", ".join(who.get(vid, []))
        if vid == 10:
            hosts = "management address of every network device (table below)"
        rows.append([f"<b>{vid}</b>", E(v["name"]), E(v["subnet"] or "-"), E(gw), E(v["zone"]), E(v["purpose"]), E(hosts)])
    vl = table(["VLAN", "Name", "Subnet", "Gateway", "Zone", "Purpose", "Hosts"], rows,
               ["6%", "11%", "12%", "19%", "10%", "17%", None])
    tr = [[f"<b>{k}</b>", E(t["subnet"]), E(", ".join(f"{a} {b}" for a, b in t.items() if a != "subnet"))] for k, t in TR.items()]
    dev = [[f"<b>{n}</b>", E(d["role"]), E(d["platform"]), d["mgmt"]["ip"], f"{d['mgmt']['port']}", d.get("loopback", "")]
           for n, d in INV["devices"].items()]
    srv = [[f"<b>{n}</b>", s["kind"], f"VLAN {s['vlan']}", s["ip"], "yes" if s.get("bond") else "no", E(", ".join(s["roles"])),
            E(s.get("image", "Ubuntu 20.04"))] for n, s in INV["servers"].items()]
    isp = []
    for n, i in INV["isps"].items():
        for ifc, l in i["links"].items():
            isp.append([f"<b>{n}</b>", f"AS{i['asn']}", ifc, f"{l['peer']} {l['peer_ip']}", l["ip"], l["net"],
                        f"local-pref {i['lp_in']}" + (f", prepend x{i['prepend_out']}" if i["prepend_out"] else "")])
    svc = [[k, v] for k, v in SVC.items()]
    return f"""
<h1 class="pb"><span class="n">3</span>Addressing plan</h1>
<p>Private space <code>10.0.0.0/8</code> inside, one <code>/24</code> per VLAN numbered like the VLAN
(VLAN 60 = <code>10.60.0.0/24</code>), so an address tells its zone at a glance. Gateways end in <code>.1</code>
(MGMT: <code>.254</code>); the two cores take <code>.2</code> and <code>.3</code>. Public addresses come from
<code>{SITE['public_prefix']}</code> (documentation range RFC 5737), WAN links from RFC 5737 ranges too.</p>
<h2>VLANs and gateways</h2>{vl}
<p>Gateways of type HSRP are carried by the cores (the "active" core answers, the other waits); CARP gateways are
carried by the firewalls, so MGMT, DMZ and ADMIN are only reachable through the firewall policy.</p>
<h2>Transit, loopback and link networks</h2>
{table(["Link", "Subnet", "Addresses"], tr, ["12%", "16%", None])}
<p>Loopbacks <code>10.255.0.x/32</code> are the router IDs (OSPF, BGP). VLAN 999 is the parking VLAN of unused ports.</p>
<h2>Network devices</h2>
{table(["Device", "Role", "Platform", "Management IP (VLAN 10)", "Mgmt port", "Loopback"], dev, ["13%", "10%", "10%", "20%", "14%", None])}
<h2>Servers and containers</h2>
{table(["Name", "Kind", "VLAN", "IP", "Bond", "Roles", "Image"], srv, ["14%", "8%", "9%", "11%", "6%", "27%", None])}
<h2>WAN and public addresses</h2>
{table(["Provider", "AS", "Port", "Our side", "Provider side", "Link", "Policy"], isp, ["9%", "9%", "7%", "22%", "14%", "16%", None])}
<p>Public block <b>{SITE['public_prefix']}</b> (our AS {SITE['asn']}): outbound NAT address <b>{SITE['snat_ip']}</b>,
public web site <b>{SITE['web_public_ip']}</b> (forwarded to SRV-WEB-01 10.50.0.11). Domain <code>{SITE['domain']}</code>.</p>
<h2>Central services every device points to</h2>{table(["Service", "Address"], svc, ["25%", None])}"""


def s4_cabling():
    sw = []
    for n, s in INV["lab_switches"].items():
        for p, d in s["ports"].items():
            vl = f"802.1Q trunk ({', '.join(map(str, d['carries']))})" if d.get("type") == "dot1q" else f"VLAN {d['vlan']}"
            sw.append([f"<b>{n}</b>", p, E(d["to"]), vl])
    return f"""
<h1 class="pb"><span class="n">4</span>Cabling</h1>
<p>Rules of the cabling: each device of a pair has its own path (A side to A, B side to B, plus cross links where
the design asks for them); every server has one NIC on each leaf of its hall; every network device has a dedicated
management port on SW-MGMT. The full plan (60 links) is in Appendix B; here are the maps that matter day to day.</p>
<h2>Who connects to whom</h2>
<table><thead><tr><th style="width:18%">From</th><th>Links</th></tr></thead><tbody>
<tr><td>ISP-A, ISP-B</td><td>eth0 → EDGE-A, eth1 → EDGE-B (each edge reaches both providers), eth2 → NAT-A / NAT-B (real Internet).</td></tr>
<tr><td>EDGE-A, EDGE-B</td><td>Gi0/0 → ISP-A, Gi0/1 → ISP-B, Gi0/2 ↔ the other edge (ISL iBGP + OSPF), Gi0/3 → SW-OUT (VLAN 901), Gi0/5 → SW-MGMT.</td></tr>
<tr><td>FW-A, FW-B</td><td>em0 → SW-OUT (WAN), em2 ↔ the other firewall (SYNC), em3 → CORE-A and em4 → CORE-B (lagg0), em5 → SW-DMZ, em6 → SW-MGMT (trunk VLAN 10 + 90).</td></tr>
<tr><td>CORE-A, CORE-B</td><td>Gi0/0-0/1 → FW-A/FW-B (VLAN 902), Gi0/2-0/3 ↔ the other core (Port-channel 1, LACP), Gi1/0-1/3 → the four leafs (trunks), Gi2/0 → SW-MGMT.</td></tr>
<tr><td>Leafs</td><td>Gi0/0 → CORE-A, Gi0/1 → CORE-B, server ports, one management port to SW-MGMT.</td></tr>
<tr><td>Servers</td><td>NIC0 on LEAF-x1, NIC1 on LEAF-x2 (bond active-backup). Single-NIC containers: SYSLOG (LEAF-B1), BMS-SIM and CCTV-SIM (LEAF-B2), SRV-WEB-01 (SW-DMZ), ADMIN-WS and SRV-BASTION (SW-MGMT VLAN 90).</td></tr>
</tbody></table>
{leaf_ports(INV)}
<h2>GNS3 built-in switches</h2>
{table(["Switch", "Port", "Connected to", "VLAN"], sw, ["13%", "12%", "35%", None])}"""


def s5_interfaces():
    out = ['<h1 class="pb"><span class="n">5</span>Interfaces, device by device</h1>',
           "<p>Every port carries a TIA-606 description; unused ports are shut and parked in VLAN 999 (CIS benchmark). "
           "The complete list of every interface of every Cisco device, read from <code>configs/*.cfg</code>, is in "
           "Appendix A. This section shows one real example of each kind of port.</p>"]
    out.append("<h2>Border router EDGE-A</h2>")
    out.append(pre(block("EDGE-A", "interface Gi0/0"), "WAN port toward ISP-A: anti-spoofing ACL, no redirects, no discovery protocols"))
    out.append(pre(block("EDGE-A", "interface Gi0/3"), "Transit toward the firewalls: OSPF + HSRP shared address 10.254.1.6, tracked default route"))
    out.append(pre(block("EDGE-A", "interface Gi0/5"), "Management port in VRF MGMT"))
    out.append("<h2>Core switch CORE-A</h2>")
    out.append(pre(block("CORE-A", "interface Gi0/0"), "Access port to the firewall lagg (VLAN 902)"))
    out.append(pre(block("CORE-A", "interface Gi1/2"), "Trunk to a leaf"))
    out.append(pre(block("CORE-A", "interface Vlan60"), "Gateway of a VLAN (SVI): HSRP, inbound ACL, OSPF"))
    out.append("<h2>Leaf LEAF-B1</h2>")
    out.append(pre(block("LEAF-B1", "interface Gi1/0"), "Server port: access VLAN, portfast, BPDU guard"))
    out.append(pre(block("LEAF-B1", "interface Gi2/0"), "Unused port: parked and shut"))
    fw = []
    for key, i in (("WAN", ("em0", TR["ext"]["FW-A"], TR["ext"]["FW-B"], TR["ext"]["fw_vip"], "VLAN 901 to the edges")),
                   ("LAN", ("lagg0 (em3+em4)", TR["int"]["FW-A"], TR["int"]["FW-B"], TR["int"]["fw_vip"], "VLAN 902 to the cores")),
                   ("SYNC", ("em2", TR["sync"]["FW-A"], TR["sync"]["FW-B"], "-", "pfsync + XMLRPC, cable between the firewalls")),
                   ("DMZ", ("em5", V[50]["fw_a"], V[50]["fw_b"], V[50]["vip"], "SW-DMZ, web server")),
                   ("MGMT", ("em6.10", V[10]["fw_a"], V[10]["fw_b"], V[10]["vip"], "802.1Q on em6, out-of-band network")),
                   ("ADMIN", ("em6.90", V[90]["fw_a"], V[90]["fw_b"], V[90]["vip"], "802.1Q on em6, administration zone"))):
        fw.append([f"<b>{key}</b>", i[0], i[1], i[2], i[3], i[4]])
    out.append("<h2>Firewalls FW-A / FW-B</h2>")
    out.append(table(["Interface", "Port", "FW-A", "FW-B", "CARP VIP", "Use"], fw, ["10%", "16%", "13%", "13%", "13%", None]))
    srv = (NET / "configs" / "servers" / "SRV-MON-01.netplan.yaml").read_text(encoding="utf-8")
    out.append("<h2>Servers (Ubuntu VMs)</h2>")
    out.append(pre(srv, "SRV-MON-01 netplan: two NICs in bond0 active-backup, one on each leaf"))
    out.append(pre((NET / "configs" / "docker" / "BMS-SIM.interfaces").read_text(encoding="utf-8"),
                   "Containers: static address written by GNS3 from the inventory (BMS-SIM)"))
    return "\n".join(out)


def s6_routing():
    return f"""
<h1 class="pb"><span class="n">6</span>Protocols and routing</h1>
<table><thead><tr><th style="width:15%">Protocol</th><th style="width:22%">Where</th><th>What it does here</th><th style="width:20%">Protection / timers</th></tr></thead><tbody>
<tr><td><b>eBGP</b></td><td>EDGE-A/B ↔ ISP-A/B</td><td>Receives only a default route, announces only {SITE['public_prefix']}. ISP-A preferred (local-pref 200), ISP-B backup (100, our prefix prepended twice toward it so return traffic also prefers ISP-A).</td><td>MD5 password, timers 3/9 s, max-prefix 100</td></tr>
<tr><td><b>iBGP</b></td><td>EDGE-A ↔ EDGE-B (loopbacks)</td><td>Each edge knows the other's provider routes; next-hop-self.</td><td>MD5, 3/9 s</td></tr>
<tr><td><b>OSPF area 0</b></td><td>edges (ISL + transit), cores (VLAN 998, 902, all SVIs)</td><td>Reachability of loopbacks and transit; internal subnets advertised by the cores, interfaces passive by default.</td><td>MD5 authentication, hello 1 s / dead 3 s on the links</td></tr>
<tr><td><b>HSRP v2</b></td><td>edges (VLAN 901, VIP 10.254.1.6), cores (every internal VLAN + 902)</td><td>One virtual gateway per VLAN, active role split between the two cores.</td><td>MD5, preempt delay 30 s; cores 1 s / 3 s, edges 250 / 750 ms with tracking of the default route</td></tr>
<tr><td><b>CARP</b></td><td>FW-A / FW-B</td><td>Virtual addresses on WAN, LAN, DMZ, MGMT, ADMIN; FW-A master (skew 0).</td><td>Password, advbase 1 s</td></tr>
<tr><td><b>pfsync + XMLRPC</b></td><td>FW-A → FW-B over SYNC</td><td>Connection states copied live; rules, NAT, users copied on every change.</td><td>Dedicated cable 10.254.3.0/30</td></tr>
<tr><td><b>Static routes</b></td><td>firewalls, cores, edges</td><td>FW: 10.0.0.0/8 via the core VIP 10.254.2.6, default via the edge VIP 10.254.1.6. Cores: default via the FW LAN VIP 10.254.2.1. Edges: {SITE['public_prefix']} via the FW WAN VIP 10.254.1.1.</td><td>Point to virtual addresses, so they survive the loss of one box</td></tr>
<tr><td><b>Rapid PVST+</b></td><td>cores and leafs</td><td>Loop-free L2 per VLAN; CORE-A root of 20/40/60/100/902/998, CORE-B root of 30/70/80 (same split as HSRP).</td><td>loopguard, BPDU guard on edge ports</td></tr>
<tr><td><b>LACP 802.3ad</b></td><td>CORE-A ↔ CORE-B</td><td>Two links bundled in Port-channel 1.</td><td>mode active</td></tr>
</tbody></table>
<div class="box warn"><b class="t">Deviation from the design</b>The design wanted OSPF down to the firewalls. pfSense has no
OSPF without an extra package, so the firewalls use static routes toward the HSRP virtual addresses. The effect is the
same for availability (the virtual address moves with the active router).</div>
<h2>BGP on EDGE-A</h2>
{pre(block("EDGE-A", "route-map *"), "Routing policy")}
{pre(block("EDGE-A", "router bgp 65100"), "router bgp")}
<h2>OSPF and default routes</h2>
{pre(block("CORE-A", "router ospf 1") + chr(10) + "!" + chr(10) + "ip route 0.0.0.0 0.0.0.0 10.254.2.1 name DEFAULT-VIA-FW-CARP", "CORE-A: OSPF + default route to the firewall CARP address")}
{pre(block("CORE-A", "interface Vlan998"), "CORE-A: dedicated OSPF link between the cores")}
<h2>Firewall gateways and routes (pfSense, generated)</h2>
<pre>Gateways : WAN_EDGE_VIP = 10.254.1.6 (edge HSRP VIP, default route)
           CORE_VIP     = 10.254.2.6 (core HSRP VIP)
Static   : 10.0.0.0/8 -> CORE_VIP   "Internal VLANs behind the cores"
CARP VIPs: WAN 10.254.1.1 (vhid 1) | LAN 10.254.2.1 (vhid 2) | DMZ 10.50.0.1 (vhid 50)
           MGMT 10.10.0.254 (vhid 10) | ADMIN 10.90.0.1 (vhid 90)</pre>"""


def s7_aggregation():
    return f"""
<h1 class="pb"><span class="n">7</span>Aggregation and trunking</h1>
<table><thead><tr><th style="width:19%">Bundle / trunk</th><th style="width:20%">Between</th><th>Technology and behaviour</th><th style="width:22%">VLANs carried</th></tr></thead><tbody>
<tr><td><b>Port-channel 1</b></td><td>CORE-A Gi0/2-0/3 ↔ CORE-B Gi0/2-0/3</td><td>LACP (802.3ad) mode active, 802.1Q trunk. Both links forward; traffic is spread per flow (hash). One link lost = half the bandwidth, no outage.</td><td>20,30,40,60,70,80,100,902,998</td></tr>
<tr><td><b>Leaf uplinks</b></td><td>each leaf Gi0/0 → CORE-A, Gi0/1 → CORE-B</td><td>802.1Q trunks, DTP off (<code>nonegotiate</code>). Spanning tree keeps one path per VLAN forwarding; the other takes over in about a second (Rapid PVST+).</td><td>20,30,40,60,70,80,100</td></tr>
<tr><td><b>lagg0</b></td><td>FW em3 → CORE-A, em4 → CORE-B</td><td>pfSense lagg in <b>failover</b> mode: em3 active, em4 standby. Survives the loss of a core or a cable.</td><td>access VLAN 902</td></tr>
<tr><td><b>em6 trunk</b></td><td>FW em6 → SW-MGMT</td><td>802.1Q sub-interfaces em6.10 and em6.90.</td><td>10, 90</td></tr>
<tr><td><b>bond0</b></td><td>server NIC0 → leaf x1, NIC1 → leaf x2</td><td>Linux bonding active-backup, MII monitoring 100 ms, MAC follows the active NIC.</td><td>one access VLAN</td></tr>
</tbody></table>
{pre(block("CORE-A", "interface Port-channel1") + chr(10) + "!" + chr(10) + block("CORE-A", "interface Gi0/2"), "CORE-A: the LACP bundle and one member")}
{pre(block("LEAF-B1", "interface Gi0/0"), "LEAF-B1: trunk uplink to CORE-A")}
<pre>&lt;lagg&gt;  members em3,em4 | proto failover | failovermaster em3 | descr "LAN failover CORE-A (em3) / CORE-B (em4)"</pre>"""


def s8_ha():
    return f"""
<h1 class="pb"><span class="n">8</span>High availability and load sharing</h1>
<figure><img src="arch_ha.png" style="max-height:95mm"><figcaption>Redundancy, layer by layer</figcaption></figure>
<table><thead><tr><th style="width:15%">Layer</th><th>If this fails…</th><th>…this takes over</th><th style="width:20%">Mechanism / design target</th></tr></thead><tbody>
<tr><td>Provider</td><td>ISP-A (link or provider)</td><td>ISP-B routes; announcements still reach the Internet through ISP-B</td><td>BGP 3/9 s, target ≤ 10 s (T1)</td></tr>
<tr><td>Border</td><td>EDGE-A</td><td>EDGE-B takes the shared address 10.254.1.6</td><td>HSRP 250/750 ms + tracking, iBGP</td></tr>
<tr><td>Firewall</td><td>FW-A</td><td>FW-B becomes CARP master with the same connection states</td><td>CARP + pfsync, target ≤ 5 s</td></tr>
<tr><td>Firewall LAN link</td><td>em3 or CORE-A</td><td>em4 to CORE-B</td><td>lagg failover</td></tr>
<tr><td>Core</td><td>CORE-A</td><td>CORE-B answers every gateway and becomes root</td><td>HSRP 1/3 s, Rapid PVST+, target ≤ 5 s</td></tr>
<tr><td>Core link</td><td>one member of Po1</td><td>the other member</td><td>LACP, sub-second</td></tr>
<tr><td>Leaf</td><td>LEAF-x1</td><td>servers keep running on their NIC1 (LEAF-x2)</td><td>bond active-backup, target ≤ 1 s</td></tr>
<tr><td>Server</td><td>SRV-CMP-01</td><td>SRV-CMP-02 takes the application VIP 10.20.0.10</td><td>keepalived (VRRP)</td></tr>
<tr><td>Power</td><td>path A (utility, UPS)</td><td>path B carries 94 % of the IT load; alarms raised</td><td>BMS-SIM, Zabbix triggers</td></tr>
</tbody></table>
<h2>Load sharing (what is balanced, and what is not)</h2>
<ul>
<li><b>Gateways split between the cores:</b> CORE-A is active for VLANs 20, 40, 60, 100; CORE-B for 30, 70, 80.
Both cores forward traffic at the same time, each for its own VLANs; the spanning-tree root of each VLAN is placed on
the same core to keep the path short.</li>
<li><b>Per-flow balancing on the core bundle:</b> LACP spreads flows over the two links of Port-channel 1.</li>
<li><b>Providers: active / backup, not balanced.</b> Outbound traffic leaves by ISP-A (local preference); inbound
traffic is pulled to ISP-A by prepending toward ISP-B. Chosen for predictability; balancing would be a policy change.</li>
<li><b>Firewalls: active / passive.</b> FW-A forwards everything while healthy; FW-B is hot standby.</li>
<li><b>Applications:</b> the compute servers share one virtual address in active / backup (keepalived). There is
<b>no application load balancer</b> (such as HAProxy) in this lab: a known gap if the web or application tier must
spread load.</li>
</ul>
{pre(block("CORE-A", "interface Vlan20"), "CORE-A: active gateway of VLAN 20 (priority 110, preempt after 30 s, MD5)")}
<div class="box warn"><b class="t">Measured or not?</b>Power alarms are measured (6 to 10 s). The failover targets of
the network (T1 to T6) are design values; the resilience campaign is still to run. During the demo profile, EDGE-B,
hall A and SRV-INF-01 are stopped to save memory, so their redundancy is not active.</div>"""


def resolve(x):
    if isinstance(x, list):
        return ", ".join(map(str, x))
    return str(x)


def s9_security():
    fr = []
    for ifc, rules in INV["firewall_rules"].items():
        for r in rules:
            act = '<span class="pill ok">pass</span>' if r["action"] == "pass" else '<span class="pill bad">block</span>'
            fr.append([f"<b>{ifc}</b>", act, E(r["proto"]), E(resolve(r["src"])), E(resolve(r["dst"])),
                       E(resolve(r.get("ports", "any"))), E(r["descr"]), r.get("ref", "")])
    ali = [[f"<b>{k}</b>", E(resolve(v))] for k, v in {**INV["host_aliases"], **INV["port_aliases"]}.items()]
    ca = INV["core_acl"]
    acl = [["every data VLAN", E(f"{r['proto']} → {r['dst']} {resolve(r.get('ports', ''))}"), E(r["descr"])] for r in ca["common_out"]]
    for vid, rules in ca["per_vlan"].items():
        for r in rules:
            acl.append([f"VLAN {vid}", E(f"{r['proto']} → {r['dst']} {resolve(r.get('ports', ''))}"), E(r["descr"])])
    for r in ca["deny_log"]:
        acl.append(['<span class="pill bad">deny + log</span>', E(f"any → {r['dst']}"), E(r["descr"])])
    return f"""
<h1 class="pb"><span class="n">9</span>Security policy</h1>
<h2>Firewall rules (pfSense, both firewalls, read top to bottom, first match wins)</h2>
<p>Each interface filters what <i>enters</i> the firewall from that zone. After the listed rules, everything else is
<b>blocked and logged</b>. Rules are generated from the inventory (<code>gen_pfsense.py</code>), deployed on FW-B
then FW-A, and audited (<code>fw_audit.py</code> = 0 difference). References T18-x are the design's Table 18; EXT-x
are additions needed by the lab.</p>
<table class="fw"><thead><tr><th>If</th><th>Action</th><th>Proto</th><th>Source</th><th>Destination</th><th>Ports</th><th>Purpose</th><th>Ref</th></tr></thead><tbody>
{"".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in fr)}</tbody></table>
<h2>Aliases used by the rules</h2>{table(["Alias", "Value"], ali, ["20%", None])}
<h2>Address translation</h2>
<table><thead><tr><th style="width:18%">Type</th><th>Rule</th></tr></thead><tbody>
<tr><td>Outbound (SNAT)</td><td>Internal networks → Internet leave as <b>{SITE['snat_ip']}</b> (hybrid outbound NAT on WAN).</td></tr>
<tr><td>Port forward (DNAT)</td><td><b>{SITE['web_public_ip']}</b> TCP 80/443 → SRV-WEB-01 <b>10.50.0.11</b>, with the associated WAN pass rule T18-1.</td></tr>
</tbody></table>
<h2>Filtering between internal VLANs (core ACLs, inbound on each SVI)</h2>
<p>Traffic between two internal VLANs never reaches the firewall: the cores route it, so each VLAN interface carries
an inbound ACL that allows only the flows below, plus replies (<code>established</code>) and the HSRP/VRRP control
packets. Management and administration networks are refused and logged.</p>
{table(["Applies to", "Allowed flow", "Why"], acl, ["16%", "38%", None])}
{pre(block("CORE-A", "ip access-list extended ACL-VLAN60-IN"), "Example: ACL of the monitoring VLAN on CORE-A")}
<h2>Device hardening (every Cisco device)</h2>
{pre(chr(10).join(CFG["CORE-A"].splitlines()[5:36]), "CORE-A: services, accounts, AAA, login protection, SSH")}
{pre(block("EDGE-A", "ip access-list extended ACL-WAN-IN"), "EDGE-A: anti-spoofing on the WAN ports")}
{pre(chr(10).join(l for l in CFG["CORE-A"].splitlines() if l.startswith(("snmp-server", "logging", "ntp "))), "CORE-A: SNMPv3, logging and NTP, all through the management VRF")}"""


def s10_flows():
    def path(*hops):
        return '<div class="path">' + '<div class="arr">→</div>'.join(
            f'<div class="hop"><b>{E(a)}</b><i>{E(b)}</i></div>' for a, b in hops) + "</div>"
    return f"""
<h1 class="pb"><span class="n">10</span>Traffic flows</h1>
<p>Five journeys that explain the whole design. Each box is a hop; the grey line is what is decided there.</p>
<h2>1. An Internet user opens the web site</h2>
{path(("Client", "→ 192.0.2.80:443"), ("ISP-A", "BGP: 192.0.2.0/24 via AS65100"), ("EDGE-A Gi0/0", "ACL-WAN-IN, static route to FW VIP"),
      ("FW WAN (CARP .1)", "DNAT → 10.50.0.11, rule T18-1"), ("SW-DMZ", "VLAN 50"), ("SRV-WEB-01", "nginx TLS 1.2/1.3"))}
<h2>2. A server reaches the Internet (updates)</h2>
{path(("SRV (VLAN 20)", "gateway 10.20.0.1"), ("CORE-A", "HSRP active, ACL-VLAN20-IN, default → 10.254.2.1"),
      ("FW LAN (lagg0)", "rule T18-5, SNAT 192.0.2.10"), ("FW WAN", "gateway 10.254.1.6"), ("EDGE-A", "best path ISP-A (local-pref 200)"), ("Internet", ""))}
<h2>3. Server to storage (east-west, never through the firewall)</h2>
{path(("SRV-CMP (VLAN 20)", "→ 10.30.0.11:2049"), ("CORE-A SVI 20", "ACL-VLAN20-IN permits NFS/iSCSI"), ("routed to VLAN 30", "CORE-B is active for 30; both route"), ("LEAF-A1/A2", "access VLAN 30"), ("SRV-STO-01", "NFS / iSCSI"))}
<h2>4. An administrator configures a core switch</h2>
{path(("ADMIN-WS 10.90.0.12", "ssh core-a"), ("FW ADMIN (CARP 10.90.0.1)", "rule T18-6 SSH/HTTPS"), ("FW MGMT em6.10", "FW is the gateway of VLAN 10"), ("SW-MGMT", "VLAN 10"), ("CORE-A Gi2/0", "VRF MGMT 10.10.0.21, SSH v2, AAA"))}
<p>Session logged by the webterm to the log collector (tag <code>admin-ssh</code>); the core refuses any routed
attempt toward 10.10.0.0/24 from the data VLANs (deny + log).</p>
<h2>5. Supervision and logs</h2>
{path(("SRV-MON-01 10.60.0.11", "Zabbix poller"), ("CORE-A SVI 60", "ACL permits SNMP/agent/ICMP/8080"), ("FW LAN", "rule T18-7 → MGMT"), ("device mgmt port", "SNMPv3 authPriv"))}
{path(("Device (VRF MGMT)", "syslog UDP 514"), ("FW MGMT", "rule T18-8"), ("FW LAN → CORE", "routed to VLAN 60"), ("SYSLOG 10.60.0.12", "one file per source"))}
{path(("SRV-MON-01", "HTTP every 10 s"), ("CORE (60 → 70)", "ACL permits 8080"), ("BMS-SIM / DCIM", "JSON API"), ("Zabbix trigger", "problem in 6-10 s"), ("Grafana", "plugin, read-only user"))}"""


def s11_services():
    rows = [["Web site", "SRV-WEB-01 10.50.0.11 (DMZ)", "nginx: HTTP → HTTPS redirect, TLS 1.2/1.3, HSTS, CSP, /health", "80, 443"],
            ["DNS / NTP / DHCP", "SRV-INF-01 10.100.0.11", "dnsmasq (zone dc.casa.lab, forwarders 1.1.1.1 / 8.8.8.8), chrony", "53, 123"],
            ["Monitoring", "SRV-MON-01 10.60.0.11", "Zabbix 6.0.48 (MariaDB, nginx + PHP-FPM), Grafana 13.2.3 + Zabbix plugin 6.8.0", "80, 3000, 10051"],
            ["Log collection", "SYSLOG 10.60.0.12", "rsyslog UDP/TCP 514, one file per source in /var/log/remote", "514"],
            ["Power simulator (BMS)", "BMS-SIM 10.70.0.12", "Python API: /api/state, /api/set, /api/reset, /metrics; alarms to syslog", "8080"],
            ["DCIM", "SRV-DCIM-01 10.70.0.11", "96 racks, reads the BMS, /api/summary, dashboard", "8080"],
            ["CCTV / access control", "CCTV-SIM 10.80.0.11", "Camera, motion and badge events to syslog", "-"],
            ["Admin webterm", "ADMIN-WS 10.90.0.12", "Browser desktop (VNC), portal page, one SSH alias per device", "console"],
            ["Bastion", "SRV-BASTION 10.90.0.11", "SSH jump host, account sysadmin, password + TOTP (PAM)", "22"],
            ["Compute / storage / backup", "SRV-CMP-01..03, SRV-STO-01, SRV-BCK-01", "App 8443 + keepalived, NFS/iSCSI, rsync (prepared, not deployed)", "8443, 2049, 3260, 873"]]
    web = (NET / "docker" / "web" / "default.conf").read_text(encoding="utf-8")
    rs = "\n".join(l for l in (NET / "docker" / "syslog" / "rsyslog.conf").read_text(encoding="utf-8").splitlines()
                   if l.strip() and not l.startswith("#"))
    ds = (NET / "grafana" / "provisioning" / "datasources" / "zabbix.yaml").read_text(encoding="utf-8")
    return f"""
<h1 class="pb"><span class="n">11</span>Services</h1>
{table(["Service", "Where", "What", "Ports"], rows, ["16%", "22%", None, "11%"])}
{pre(web, "SRV-WEB-01: nginx configuration (docker/web/default.conf)")}
{pre(rs, "SYSLOG: rsyslog configuration (docker/syslog/rsyslog.conf)")}
{pre(ds, "Grafana: Zabbix data source, provisioned from the repository")}"""


def s12_supervision():
    svc = INV["monitoring"]["services"]
    trg = [[f"<b>{h}</b>", E(t["name"]), E(t["expr"]), t["severity"]] for h, s in svc.items() for t in s.get("triggers", [])]
    return f"""
<h1 class="pb"><span class="n">12</span>Supervision and logs</h1>
<h2>What Zabbix watches (17 hosts)</h2>
<table><thead><tr><th style="width:18%">Group</th><th style="width:28%">Hosts</th><th>How</th></tr></thead><tbody>
<tr><td>DC/Edge, DC/Core, DC/Leaf</td><td>EDGE-A/B, CORE-A/B, LEAF-A1/A2/B1/B2</td><td>SNMPv3 authPriv (user <code>zbxmon</code>, SHA + AES-128), template "Cisco IOS by SNMP" (CPU, memory, interfaces, ICMP)</td></tr>
<tr><td>DC/Firewalls</td><td>FW-A, FW-B</td><td>SNMP v2c restricted to VLAN 60, template "PFSense by SNMP"; DHCP/DNS triggers disabled (off by design)</td></tr>
<tr><td>DC/Servers</td><td>SRV-MON-01, SRV-INF-01, SRV-BASTION</td><td>Zabbix agent (passive, or active for the bastion)</td></tr>
<tr><td>DC/Services</td><td>BMS-SIM, SRV-DCIM-01, SRV-WEB-01, SYSLOG</td><td>HTTP agent + JSONPath (10 s), web scenario on /health, ICMP</td></tr>
</tbody></table>
<p>Hosts whose node is stopped go into the maintenance <code>demo-off</code> (no data collected, no alarm). Everything
is applied by <code>python automation/zabbix_setup.py apply</code> from the inventory; <code>status</code> checks it.</p>
<h2>Service triggers</h2>{table(["Host", "Problem", "Expression", "Severity"], trg, ["14%", "30%", None, "10%"])}
<p>The 45 % warning depends on the 50 % problem, so only the worse one shows. Nominal state: two warnings (each path
at 47.1 %, a finding on the design margin).</p>
<h2>Grafana</h2>
<p>Grafana (port 3000) has no data of its own: its Zabbix plugin queries the Zabbix API on the same server with the
read-only account <code>grafana</code>. Anonymous access and sign-up are off. The NOC dashboard (rows Énergie,
Réseau, Sécurité, Infrastructure) is generated by <code>automation/gen_dashboards.py</code>; it is a draft being
validated.</p>
<h2>Logs</h2>
<p>Every Cisco device logs (informational and above) to 10.60.0.12 from its management VRF; pfSense, servers
(journald → rsyslog), BMS-SIM, CCTV-SIM and the admin webterm also send there. The collector writes one file per
source and one combined file. Retention, permissions and a read-only viewer are the next step (plan 03 S5).</p>"""


def s13_access():
    return f"""
<h1 class="pb"><span class="n">13</span>Administration access and proxy</h1>
<h2>The only way in: the administration zone (VLAN 90)</h2>
<ul>
<li><b>ADMIN-WS</b> (10.90.0.12): a browser desktop with a portal page and one SSH alias per device
(<code>ssh core-a</code>, <code>ssh fw-a</code>…). Every session is announced to the log collector.</li>
<li><b>SRV-BASTION</b> (10.90.0.11): SSH jump host for administrators who come from outside the webterm; account
<code>sysadmin</code> with password <b>and</b> a TOTP code (RFC 6238, PAM google-authenticator).</li>
<li>Network devices: local account <code>netadmin</code> (privilege 15), SSH v2 only, 5 failures in 60 s block logins
for 120 s, every login logged. Servers: account <code>sysadmin</code>; the image account <code>ubuntu</code> is refused by SSH.</li>
<li>pfSense web interface: HTTPS from the admin zone only, idle sessions closed after 15 minutes.</li>
</ul>
{pre((NET / "configs" / "docker" / "ADMIN-WS.ssh_config").read_text(encoding="utf-8").split("Host core-b")[0].strip(), "ADMIN-WS: SSH aliases (generated from the inventory, extract)")}
<h2>Proxies in the lab</h2>
<table><thead><tr><th style="width:20%">Proxy</th><th>What it does</th><th style="width:28%">Security</th></tr></thead><tbody>
<tr><td><b>Lab proxy</b> (<code>lab_proxy.py</code>)</td><td>SOCKS5 server in the GNS3 VM on 192.168.75.128:1080 (host-only network: reachable from the PC only). Each connection is opened from inside the network namespace of ADMIN-WS, so the PC browses <b>as the admin workstation</b>.</td><td>Traffic is filtered by the ADMIN firewall rules like any administrator; no shortcut around the policy. No authentication: lab helper only.</td></tr>
<tr><td><b>Grafana data-source proxy</b></td><td>Browsers never talk to Zabbix: Grafana's server side calls <code>http://127.0.0.1/api_jsonrpc.php</code> (access mode "proxy").</td><td>Credentials stay on the server; read-only Zabbix account.</td></tr>
<tr><td><b>nginx in front of Zabbix</b></td><td>nginx serves the Zabbix frontend and hands PHP to PHP-FPM.</td><td>Plain HTTP inside VLAN 60 (gap, see section 14).</td></tr>
<tr><td><b>Firewall NAT</b></td><td>Not a proxy, but the only exposure: 192.0.2.80 is forwarded to the DMZ web server.</td><td>Only TCP 80/443, only to the DMZ.</td></tr>
</tbody></table>
<p>There is no forward web proxy for Internet access (servers leave through the firewall NAT) and no reverse proxy or
load balancer in front of the web site.</p>"""


def s14_iso():
    rows = [
        ("A.5.15", "Access control", "Administration only from VLAN 90 through the firewall; core ACLs deny + log toward MGMT/ADMIN.", "access_matrix.py: 16 accesses, 0 failure", "Met"),
        ("A.5.17", "Authentication information", "Named accounts; secrets kept in the inventory.", "Plain-text lab secrets in a private repository: acceptable for a lab, not for production", "Partial"),
        ("A.7.11", "Supporting utilities", "Two power paths, UPS and generator simulated; load thresholds 45 / 50 % watched.", "power_test.py: alarm in 6-10 s", "Met"),
        ("A.8.2", "Privileged access rights", "Privilege 15 only for netadmin; sudo for sysadmin; enable secret.", "Configurations", "Met"),
        ("A.8.3", "Information access restriction", "Zones and VLANs; read-only Zabbix account for Grafana.", "Write call refused for grafana", "Met"),
        ("A.8.5", "Secure authentication", "SSH v2, login lockout, TOTP on the bastion, 15 min web timeout on pfSense.", "Zabbix and Grafana logins over HTTP; console account ubuntu kept", "Partial"),
        ("A.8.6", "Capacity management", "Start-up by tiers, profiles sized to the host, resources measured.", "Host 15.7 GB for a 32 GB design: about 0.5 GB free", "Partial"),
        ("A.8.9", "Configuration management", "Inventory = source of truth, generated configurations, audit, one Git commit per change.", "fw_audit.py: 0 difference", "Met"),
        ("A.8.13", "Information backup", "Configurations versioned in Git.", "No scheduled device backup or restore test yet (ISO.2)", "Partial"),
        ("A.8.14", "Redundancy", "2N at every layer (section 8).", "Failover times not yet measured", "Partial"),
        ("A.8.15", "Logging", "Central collector for devices, firewalls, servers, simulators, admin sessions.", "Retention and protection not configured yet (LOG.2)", "Partial"),
        ("A.8.16", "Monitoring activities", "Zabbix on 17 hosts, service triggers, Grafana.", "zabbix_setup.py status: 0 running host unavailable", "Met"),
        ("A.8.17", "Clock synchronisation", "Every device points to SRV-INF-01 (NTP).", "SRV-INF-01 off in the demo profile; IOSvL2 clocks run slow", "Gap"),
        ("A.8.20", "Network security", "Hardening, anti-spoofing, routing protocol authentication (MD5).", "Configurations", "Met"),
        ("A.8.21", "Security of network services", "SNMPv3 authPriv on Cisco devices.", "pfSense uses SNMP v2c (community restricted to VLAN 60)", "Partial"),
        ("A.8.22", "Segregation of networks", "Ten VLANs in five zones; DMZ blocked toward MGMT/ADMIN/storage/backup.", "Flow matrix (FW.4) not run yet", "Met"),
        ("A.8.24", "Use of cryptography", "SSH, SNMPv3 AES, TLS 1.2/1.3 on the web site, MD5 on BGP/OSPF/HSRP.", "Zabbix and Grafana not in HTTPS", "Partial"),
        ("A.8.8", "Technical vulnerabilities", "-", "No vulnerability scan or patch process in the lab", "Gap"),
        ("A.8.32", "Change management", "Plans, one commit per change, deploy with rollback (pfSense).", "Git history", "Met"),
    ]
    met = sum(r[4] == "Met" for r in rows)
    return f"""
<h1 class="pb"><span class="n">14</span>ISO/IEC 27001:2022 conformity</h1>
<p>Annex A controls that the network touches, how the lab answers them, the proof, and the honest status.
<b>{met} of {len(rows)}</b> are met; the others are partial or open and listed with their cause. Gaps are written down
as deviations, never left silent.</p>
<table><thead><tr><th style="width:7%">Control</th><th style="width:16%">Name</th><th>Implementation</th><th style="width:26%">Evidence / limit</th><th style="width:8%">Status</th></tr></thead><tbody>
{"".join(f"<tr><td><b>{a}</b></td><td>{E(b)}</td><td>{E(c)}</td><td>{E(d)}</td><td>{pill(s)}</td></tr>" for a, b, c, d, s in rows)}
</tbody></table>
<h2>To close the gaps</h2>
<ol>
<li>HTTPS on Zabbix and Grafana (certificate from an internal CA), and SNMPv3 on pfSense (A.8.24, A.8.21).</li>
<li>Run NTP in every profile and check <code>show ntp status</code> (A.8.17).</li>
<li>Log retention, permissions and a read-only viewer (A.8.15); scheduled configuration backups with a restore test (A.8.13).</li>
<li>Measure the failover scenarios T1-T6 (A.8.14); run the flow matrix (A.8.22).</li>
<li>Secrets out of the repository (vault or encrypted file) before any real use (A.5.17).</li>
</ol>"""


def appendix_interfaces():
    out = ['<h1 class="pb"><span class="n">A</span>Appendix: all interfaces</h1>',
           "<p>Read from the configurations that are deployed (<code>configs/*.cfg</code>). Peer = the device at the "
           "other end of the cable (TIA-606 description).</p>"]
    for dev in ["EDGE-A", "EDGE-B", "CORE-A", "CORE-B", "LEAF-A1", "LEAF-A2", "LEAF-B1", "LEAF-B2"]:
        out.append(f'<h2>{dev}</h2>' + table(["Interface", "Peer", "Layer 2", "IP", "Features", "Role", "State"],
                                             parse_interfaces(dev), ["11%", "17%", "17%", "12%", "20%", None, "6%"]))
    return "\n".join(out)


def appendix_credentials():
    rows = [
        ("Cisco devices (SSH)", "netadmin", C["admin_password"], "privilege 15"),
        ("Cisco enable", "-", C["enable_secret"], ""),
        ("pfSense web / SSH", "admin", C["admin_password"], "from VLAN 90"),
        ("Servers (SSH)", C["server_admin_user"], C["server_admin_password"], "SRV-BASTION also asks a TOTP code"),
        ("Bastion TOTP secret", "-", C["bastion_totp_secret"], "code: python automation/totp.py"),
        ("Servers (console only)", C["server_user"], C["server_password"], "refused by SSH"),
        ("Zabbix web", "Admin", C["zabbix_admin_password"], "http://10.60.0.11/"),
        ("Zabbix read-only (Grafana)", "grafana", C["zabbix_grafana_password"], "API only in practice"),
        ("Zabbix database", "zabbix", C["zabbix_db_password"], "MariaDB, local"),
        ("Grafana web", "admin", C["grafana_admin_password"], "http://10.60.0.11:3000/"),
        ("SNMPv3", C["snmpv3_user"], f"auth {C['snmpv3_auth']} / priv {C['snmpv3_priv']}", "SHA / AES-128"),
        ("SNMP v2c (pfSense)", "community", C["snmp_ro_community"], "read-only, VLAN 60"),
        ("HSRP key", "-", C["hsrp_key"], "MD5"),
        ("OSPF key", "-", C["ospf_key"], "MD5, key 1"),
        ("BGP password", "-", C["bgp_password"], "all sessions"),
        ("CARP password", "-", C["carp_password"], "all VHIDs"),
    ]
    return ('<h1 class="pb"><span class="n">C</span>Appendix: credentials</h1>'
            '<div class="box warn"><b class="t">Lab only</b>These secrets exist only in this lab and in its private '
            'repository (<code>inventory/dc_casa.yaml</code>). Never reuse them elsewhere.</div>'
            + table(["System", "Account", "Secret", "Note"], [[E(a), f"<code>{E(b)}</code>", f"<code>{E(c)}</code>", E(d)]
                                                               for a, b, c, d in rows], ["24%", "14%", "34%", None]))


def appendix_glossary():
    g = [("BGP", "Border Gateway Protocol: exchange of routes between autonomous systems (providers)."),
         ("CARP", "Common Address Redundancy Protocol: a virtual IP shared by the two firewalls."),
         ("DMZ", "Demilitarised zone: network for services exposed to the Internet."),
         ("HSRP", "Hot Standby Router Protocol (Cisco): a virtual gateway shared by two routers or switches."),
         ("LACP", "Link Aggregation Control Protocol (802.3ad): several links act as one."),
         ("lagg", "pfSense link aggregation; here in failover mode."),
         ("OOB", "Out-of-band management: a separate network used only to administer devices."),
         ("OSPF", "Open Shortest Path First: internal dynamic routing."),
         ("pfsync", "pfSense protocol that copies connection states to the peer firewall."),
         ("Rapid PVST+", "Rapid spanning tree, one instance per VLAN: prevents L2 loops, converges in about a second."),
         ("SVI", "Switch virtual interface (interface VlanX): the routed gateway of a VLAN on a switch."),
         ("TIA-942 / TIA-606", "Data center design standard / labelling standard used for names and descriptions."),
         ("TOTP", "Time-based one-time password, the 6-digit second factor of the bastion."),
         ("VRF", "Virtual routing table: the management VRF keeps management traffic apart from data traffic."),
         ("Trunk / 802.1Q", "A link that carries several VLANs, each frame tagged with its VLAN number.")]
    return ('<h1 class="pb"><span class="n">D</span>Appendix: glossary</h1>' +
            table(["Term", "Meaning"], [[f"<b>{E(a)}</b>", E(b)] for a, b in g], ["20%", None]))


def main():
    style = re.search(r"<style>.*?</style>", (SRC / "lab_guide.html").read_text(encoding="utf-8"), re.S).group(0)
    style = style.replace("DC Casablanca - GNS3 Network Lab Guide", "DC Casablanca - Technical Report")
    style = style.replace("</style>", "p.cap { margin: 2mm 0 0; font-size: 8.4pt; color: var(--brand); break-after: avoid; }\n</style>")
    body = "".join([cover(), contents(), s1_onboarding(), s2_architecture(), s3_addressing(), s4_cabling(),
                    s5_interfaces(), s6_routing(), s7_aggregation(), s8_ha(), s9_security(), s10_flows(),
                    s11_services(), s12_supervision(), s13_access(), s14_iso(), appendix_interfaces(),
                    '<h1 class="pb"><span class="n">B</span>Appendix: full cabling plan</h1>' + cabling(),
                    appendix_credentials(), appendix_glossary()])
    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><base href="{SRC.as_uri()}/">'
            f"<title>DC Casablanca - Technical Report</title>{style}</head><body>{body}</body></html>")
    browser = next((b for b in BROWSERS if Path(b).exists()), None)
    if not browser:
        sys.exit("no Edge/Chrome found for the PDF export")
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "tech_report.html"
        f.write_text(page, encoding="utf-8")
        if "--html" in sys.argv:
            (NET / "report" / "_source" / "tech_report.preview.html").write_text(page, encoding="utf-8")
        subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--user-data-dir={Path(tmp) / 'profile'}", f"--print-to-pdf={OUT}", f.as_uri()],
                       check=True, timeout=180, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"{OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
