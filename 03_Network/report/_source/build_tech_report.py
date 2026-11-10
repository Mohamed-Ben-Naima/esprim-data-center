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
DOC_DATE = "10 November 2026"
EXTRA_CSS = """p.cap { margin: 2mm 0 0; font-size: 8.4pt; color: var(--brand); break-after: avoid; }
.bar { height: 2.6mm; background: #e3e8ee; border-radius: 2mm; overflow: hidden; min-width: 18mm; }
.bar i { display: block; height: 100%; background: var(--brand2); }
.bar.ok i { background: var(--ok); } .bar.wip i { background: #c98300; } .bar.bad i { background: var(--bad); }
.score { display: grid; grid-template-columns: repeat(3, 1fr); gap: 3mm; margin: 2mm 0 3mm; }
.score > div { border: 1.2px solid var(--line); border-radius: 4px; padding: 2.5mm 3mm; break-inside: avoid; }
.score b { display: block; font-size: 20pt; color: var(--brand); line-height: 1.1; }
.score span { font-size: 8pt; color: var(--mute); }
td .bar { margin-top: 1mm; }
"""
E = html.escape
V, TR, C, SITE, SVC = INV["vlans"], INV["transit"], INV["credentials"], INV["site"], INV["services"]


# Order of the report: sections are numbered, appendices lettered, in this order. Cross-references use ref(key).
SECTIONS = [
    ("summary", "Executive summary and scorecard", "state, completion, security score, conformity"),
    ("onboarding", "Onboarding in ten minutes", "what it is, how to start it, where to click"),
    ("architecture", "Architecture and design principles", "layers, zones, 2N, patterns"),
    ("equipment", "Equipment: role, position, placement", "every node, why it is there, what runs on it"),
    ("addressing", "Addressing plan and VLAN choices", "VLANs, gateways, transit, WAN, why"),
    ("cabling", "Cabling", "every link, port maps"),
    ("interfaces", "Interfaces, device by device", "how each port is configured"),
    ("protocols", "Protocol catalogue", "every protocol, port, why it was chosen"),
    ("routing", "Routing and first-hop redundancy", "BGP, OSPF, HSRP, CARP, static routes"),
    ("aggregation", "Aggregation and trunking", "LACP, 802.1Q, lagg, bonds"),
    ("ha", "High availability and load sharing", "who takes over, how fast"),
    ("security", "Security policy and port matrix", "firewall rules, NAT, core ACLs, every port"),
    ("hardening", "Hardening, threats and countermeasures", "per platform, threat by threat"),
    ("flows", "Traffic flows", "five journeys, hop by hop"),
    ("services", "Services and installed software", "what runs where, how it is configured"),
    ("supervision", "Supervision, logs, SIEM and EDR", "what is watched, what is detected, what is missing"),
    ("access", "Administration access and proxy", "webterm, bastion, lab proxy"),
    ("iso", "ISO/IEC 27001:2022 conformity", "control by control, with gaps"),
    ("state", "Current state and completion", "active, configured, missing, percentages"),
    ("scores", "Security score and real-world conformity", "method, scores, real-life scenarios"),
    ("roadmap", "Roadmap: the next steps", "ordered, with the score they bring"),
]
APPENDICES = [("all_interfaces", "Appendix: all interfaces"), ("cabling_plan", "Appendix: full cabling plan"),
              ("credentials", "Appendix: credentials"), ("glossary", "Appendix: glossary and keywords")]
NUM = {k: str(i + 1) for i, (k, *_) in enumerate(SECTIONS)} | {k: chr(65 + i) for i, (k, _) in enumerate(APPENDICES)}
TITLE = {k: t for k, t, *_ in SECTIONS} | dict(APPENDICES)


def h1(key):
    return f'<h1 class="pb"><span class="n">{NUM[key]}</span>{TITLE[key]}</h1>'


def ref(key):
    return f"Appendix {NUM[key]}" if NUM[key].isalpha() else f"section {NUM[key]}"


def bar(pct, cls=""):
    return f'<div class="bar {cls}"><i style="width:{pct:.0f}%"></i></div>'


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
  <div class="sub">How the lab is wired, addressed, routed, protected, supervised and kept available: every node and
  its purpose, every protocol and why it was chosen, every rule and port, the hardening, the detection, the real
  configurations, the credentials, the state of completion and an honest security score.</div>
  <div class="facts">
    <div class="fact"><b>{nodes}</b><span>nodes in the GNS3 project, {len(V)} VLANs</span></div>
    <div class="fact"><b>{completion():.0f} %</b><span>of the planned work done</span></div>
    <div class="fact"><b>{security_score():.0f} / 100</b><span>security score (weighted, {ref('scores')})</span></div>
    <div class="fact"><b>{conformity():.0f} %</b><span>conformity to real data-center practice</span></div>
  </div>
  <div class="state"><b>Read this first</b><br>
    {ref('summary').capitalize()} is the one-page answer: what works, what does not, the scores. Sections
    {NUM['onboarding']}-{NUM['equipment']} give the picture and the role of every node. Sections
    {NUM['addressing']}-{NUM['hardening']} are the network and security reference. Sections
    {NUM['flows']}-{NUM['iso']} cover services, detection, access and compliance. Sections
    {NUM['state']}-{NUM['roadmap']} give the state, the scores and the next steps.</div>
  <div class="meta">Document date: {DOC_DATE}. Generated by <span class="mono">report/_source/build_tech_report.py</span>
    from <span class="mono">inventory/dc_casa.yaml</span> and <span class="mono">configs/</span>.<br>
    Design target: ANSI/TIA-942 Rated-3 data center, 96 racks in two halls, about 1 MW of IT load.<br>
    Lab credentials only ({ref('credentials')}): never reuse them outside the lab.</div>
</div>"""


def contents():
    items = [(NUM[k], t, sub) for k, t, sub in SECTIONS] + [(NUM[k], t, "") for k, t in APPENDICES]
    return ('<h1 class="pb">Contents</h1><div class="toc">' +
            "".join(f"<div><b>{n}</b>{t}<small>{s}</small></div>" for n, t, s in items) + "</div>")


def s1_onboarding():
    w = INV["web_interfaces"]
    rows = [[E(x["name"]), f"<code>{E(x['url'])}</code>", E(x["login"] or "-"), E(x["descr"])] for x in w]
    return f"""
{h1('onboarding')}
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
<p>Passwords are in {ref('credentials')}. The certificates are self-signed: accept them in the proxy browser.</p>"""


def s2_architecture():
    return f"""
{h1('architecture')}
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
<h2>Design patterns used, and why</h2>
<table><thead><tr><th style="width:21%">Pattern</th><th>How it is applied</th><th style="width:30%">Why this one (and the trade-off)</th></tr></thead><tbody>
<tr><td><b>Collapsed core (two tiers)</b></td><td>Two cores do both core and distribution; leafs hang off them. No separate aggregation layer.</td><td>Right size for 96 racks and 4 leafs: fewer boxes, fewer hops. Trade-off: it relies on spanning tree; a large site would use a spine-leaf fabric (EVPN-VXLAN, ECMP).</td></tr>
<tr><td><b>Firewall sandwich</b></td><td>Edges outside, cores inside, the firewall cluster in the middle: every north-south packet crosses the firewall.</td><td>One choke point for policy, NAT and logs. Trade-off: the firewall must be HA (CARP + pfsync).</td></tr>
<tr><td><b>North-south at the firewall, east-west at the core</b></td><td>Internet, DMZ, MGMT, ADMIN are firewall zones; traffic between internal VLANs is routed by the cores and filtered by their ACLs.</td><td>Keeps heavy server-to-storage traffic off the firewall (wire speed), yet still filtered. Trade-off: core ACLs are stateless.</td></tr>
<tr><td><b>Zone model by trust level</b></td><td>Five zones: Internet (untrusted), DMZ (exposed), internal (business), management (devices), administration (people).</td><td>A breach in a zone stays in the zone; each crossing is an explicit rule.</td></tr>
<tr><td><b>Active / standby pairs</b></td><td>Providers, edges, firewalls, server NICs, keepalived VIP.</td><td>Predictable paths, simple troubleshooting, state kept on failover. Trade-off: the standby side does not carry load.</td></tr>
<tr><td><b>Split active roles</b></td><td>CORE-A is the active gateway and STP root for half the VLANs, CORE-B for the other half.</td><td>Both cores work at the same time (load sharing without a load balancer).</td></tr>
<tr><td><b>Out-of-band management + jump host</b></td><td>Management ports in VRF MGMT on a separate switch; administrators enter through VLAN 90 (webterm, bastion with TOTP).</td><td>The data network can fail or be attacked without losing control of the devices; one audited entry point.</td></tr>
<tr><td><b>Source of truth → generate → deploy → audit</b></td><td>The inventory feeds generators; deploy scripts push; audit scripts compare live and generated (0 difference).</td><td>Repeatable, reviewable in Git, no drift. Trade-off: a manual change on a device is overwritten at the next deploy.</td></tr>
<tr><td><b>Least-privilege service accounts</b></td><td>Grafana reads Zabbix with the read-only account <code>grafana</code>; SNMP is read-only; the monitoring VLAN may poll but not log in.</td><td>A stolen service credential cannot change anything.</td></tr>
<tr><td><b>Health endpoints</b></td><td><code>/health</code> on the web site, <code>/api/state</code> on the BMS, <code>/api/summary</code> on the DCIM, polled by Zabbix.</td><td>Supervision checks the service as a user sees it, not only "the box answers ping".</td></tr>
<tr><td><b>Fail closed</b></td><td>Default deny + log on every firewall interface; deny + log toward MGMT/ADMIN on every core VLAN.</td><td>Anything forgotten is blocked and visible, never silently open.</td></tr>
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
{h1('addressing')}
<p>Private space <code>10.0.0.0/8</code> inside, one <code>/24</code> per VLAN numbered like the VLAN
(VLAN 60 = <code>10.60.0.0/24</code>), so an address tells its zone at a glance. Gateways end in <code>.1</code>
(MGMT: <code>.254</code>); the two cores take <code>.2</code> and <code>.3</code>. Public addresses come from
<code>{SITE['public_prefix']}</code> (documentation range RFC 5737), WAN links from RFC 5737 ranges too.</p>
<h2>VLANs and gateways</h2>{vl}
<p>Gateways of type HSRP are carried by the cores (the "active" core answers, the other waits); CARP gateways are
carried by the firewalls, so MGMT, DMZ and ADMIN are only reachable through the firewall policy.</p>
<h2>Why these VLANs (design choices)</h2>
<table><thead><tr><th style="width:15%">Choice</th><th>Rule applied</th><th style="width:36%">Reason</th></tr></thead><tbody>
<tr><td><b>One VLAN per function</b></td><td>Servers (20), storage (30), backup (40), DMZ (50), monitoring (60), BMS/DCIM (70), CCTV (80), admin (90), internal services (100), management (10).</td><td>Each function has a different risk and different allowed flows; a VLAN is the unit the ACLs and rules talk about (ISO A.8.22).</td></tr>
<tr><td><b>VLAN number = second octet</b></td><td>VLAN 60 = 10.60.0.0/24.</td><td>An address tells its zone at a glance: faster troubleshooting, fewer mistakes in rules.</td></tr>
<tr><td><b>/24 per VLAN</b></td><td>254 hosts each; transit links /28 (four routers + VIPs) and /30 (point to point).</td><td>Room to grow without renumbering; small transit networks leave nothing to squat.</td></tr>
<tr><td><b>Gateway on the core (HSRP)</b></td><td>VLANs 20, 30, 40, 60, 70, 80, 100.</td><td>Heavy east-west traffic (storage, backup, monitoring) routed at wire speed and filtered by core ACLs.</td></tr>
<tr><td><b>Gateway on the firewall (CARP)</b></td><td>VLANs 10 (MGMT), 50 (DMZ), 90 (ADMIN).</td><td>The most sensitive or most exposed zones: every packet in or out goes through stateful inspection and is logged.</td></tr>
<tr><td><b>Storage and backup isolated</b></td><td>Storage reachable only from servers (NFS/iSCSI); backup pulled by the NAS (rsync over SSH): servers cannot write to it.</td><td>Ransomware on one server cannot browse the backups or the storage of others (ISO A.8.13).</td></tr>
<tr><td><b>BMS/DCIM and CCTV apart</b></td><td>Building systems (70) and physical security (80) separated from IT servers.</td><td>OT/IoT devices are weak and rarely patched: they must not sit with servers.</td></tr>
<tr><td><b>Monitoring in its own VLAN</b></td><td>VLAN 60 is the only one allowed to poll every device (SNMP, agent, ICMP).</td><td>The polling privilege is tied to one small, known network.</td></tr>
<tr><td><b>Technical VLANs</b></td><td>901 / 902 transit, 998 OSPF link between cores, 999 parking.</td><td>Routing adjacencies on dedicated links; unused ports parked in a VLAN that goes nowhere.</td></tr>
<tr><td><b>VLAN 1 not used</b></td><td>Interface Vlan1 shut, VLAN 1 not allowed on trunks, DTP off.</td><td>Removes the default VLAN used by VLAN-hopping attacks.</td></tr>
</tbody></table>
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
{h1('cabling')}
<p>Rules of the cabling: each device of a pair has its own path (A side to A, B side to B, plus cross links where
the design asks for them); every server has one NIC on each leaf of its hall; every network device has a dedicated
management port on SW-MGMT. The full plan (60 links) is in {ref('cabling_plan')}; here are the maps that matter day to day.</p>
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
    out = [h1("interfaces"),
           "<p>Every port carries a TIA-606 description; unused ports are shut and parked in VLAN 999 (CIS benchmark). "
           "The complete list of every interface of every Cisco device, read from <code>configs/*.cfg</code>, is in "
           f"{ref('all_interfaces')}. This section shows one real example of each kind of port.</p>"]
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
{h1('routing')}
<p>The full list of protocols, with the reason each was chosen, is in {ref('protocols')}. This section shows how the
routing and gateway redundancy are really configured, with the policy in plain words first.</p>
<table><thead><tr><th style="width:22%">Decision</th><th>What the configuration does</th></tr></thead><tbody>
<tr><td><b>Who is preferred outbound</b></td><td>Routes learnt from ISP-A get local-preference 200, ISP-B 100: every edge sends Internet traffic to ISP-A while it is up (iBGP shares the choice between the edges).</td></tr>
<tr><td><b>Who is preferred inbound</b></td><td>Our prefix is announced to ISP-B with our AS prepended twice (AS path 65100 65100 65100), so the Internet also prefers to come back through ISP-A.</td></tr>
<tr><td><b>What we accept</b></td><td>Only a default route from each provider (prefix-list PL-DEFAULT), at most 100 prefixes per session, then the session is shut.</td></tr>
<tr><td><b>What we announce</b></td><td>Only {SITE['public_prefix']} (prefix-list PL-ANNOUNCE): never a private range, never a transit network: no route leak.</td></tr>
<tr><td><b>Inside</b></td><td>OSPF area 0 carries loopbacks, transit and the internal VLAN subnets; the cores send everything unknown to the firewall CARP address; the firewalls send 10.0.0.0/8 back to the core HSRP address.</td></tr>
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
{h1('aggregation')}
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
{h1('ha')}
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
{h1('security')}
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
{pre(chr(10).join(l for l in CFG["CORE-A"].splitlines() if l.startswith(("snmp-server", "logging", "ntp "))), "CORE-A: SNMPv3, logging and NTP, all through the management VRF")}
{port_matrix()}"""


def s10_flows():
    def path(*hops):
        return '<div class="path">' + '<div class="arr">→</div>'.join(
            f'<div class="hop"><b>{E(a)}</b><i>{E(b)}</i></div>' for a, b in hops) + "</div>"
    return f"""
{h1('flows')}
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
            ["Log collection", "SYSLOG 10.60.0.12", "rsyslog UDP/TCP 514, one file per source in /var/log/remote, rotation 30 days, read-only viewer", "514, 443"],
            ["Power simulator (BMS)", "BMS-SIM 10.70.0.12", "Python API: /api/state, /api/set, /api/reset, /metrics; alarms to syslog", "8080"],
            ["DCIM", "SRV-DCIM-01 10.70.0.11", "96 racks, reads the BMS, /api/summary, dashboard", "8080"],
            ["CCTV / access control", "CCTV-SIM 10.80.0.11", "Camera, motion and badge events to syslog", "-"],
            ["Admin webterm", "ADMIN-WS 10.90.0.12", "Browser desktop (VNC), portal page, one SSH alias per device", "console"],
            ["Bastion", "SRV-BASTION 10.90.0.11", "SSH jump host, account sysadmin, password + TOTP (PAM)", "22"],
            ["Compute / storage", "SRV-CMP-01..03, SRV-STO-01", "App 8443 + keepalived, NFS/iSCSI (prepared, not deployed)", "8443, 2049, 3260"],
            ["Backup NAS", "SRV-BCK-01 10.40.0.11 (hall B)", "TrueNAS SCALE 25.10.7: bond failover, ZFS mirror tank, hourly/daily snapshots, SSH + SNMPv3 from admin zone only; nightly pulled backups, restore tested (plan 04)", "443, 22"]]
    web = (NET / "docker" / "web" / "default.conf").read_text(encoding="utf-8")
    rs = "\n".join(l for l in (NET / "docker" / "syslog" / "rsyslog.conf").read_text(encoding="utf-8").splitlines()
                   if l.strip() and not l.startswith("#"))
    ds = (NET / "grafana" / "provisioning" / "datasources" / "zabbix.yaml").read_text(encoding="utf-8")
    return f"""
{h1('services')}
{table(["Service", "Where", "What", "Ports"], rows, ["16%", "22%", None, "11%"])}
{software_table()}
<h2>Key configurations</h2>
{pre(web, "SRV-WEB-01: nginx configuration (docker/web/default.conf)")}
{pre(rs, "SYSLOG: rsyslog configuration (docker/syslog/rsyslog.conf)")}
{pre(ds, "Grafana: Zabbix data source, provisioned from the repository")}"""


def s12_supervision():
    svc = INV["monitoring"]["services"]
    trg = [[f"<b>{h}</b>", E(t["name"]), E(t["expr"]), t["severity"]] for h, s in svc.items() for t in s.get("triggers", [])]
    return f"""
{h1('supervision')}
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
Réseau, Sécurité, Stockage et sauvegardes, Infrastructure; 28 panels) is generated by <code>automation/gen_dashboards.py</code>,
provisioned by the Grafana role and checked panel by panel on live data by <code>automation/check_dashboard.py</code>
(28/28 with data on 10 Nov 2026; a power cut turns the Énergie row red in under 10 s).</p>
<h2>Logs</h2>
<p>Every Cisco device logs (informational and above) to 10.60.0.12 from its management VRF; pfSense, servers
(journald → rsyslog), BMS-SIM, CCTV-SIM and the admin webterm also send there. The collector writes one file per
source and one combined file (image <code>dc/syslog:1.1</code>). Files are <code>0640 root:logread</code> in a <code>0750</code>
directory, rotated every night, compressed and kept 30 days (<code>services.log_retention_days</code>; 119 MB became 10 MB
at the first rotation). A <b>read-only viewer</b> (<code>https://10.60.0.12/</code>, standard-library Python, TLS 1.2+) lets
the administrator search by source and text, including the archives; it runs under an account that can read the files
but not change or delete them, locks an address after 5 wrong passwords and logs every login and search back to the
collector. <code>automation/syslog_audit.py</code> sends a marker from every running equipment and finds it (6/6 on
10 Nov 2026); <code>automation/log_viewer.py demo</code> finds a failed SSH login, a configuration session and a DMZ block
in the viewer within 3 s. Known limit: without the NTP server (SRV-INF-01 off in the small profiles) the emulated Cisco
clocks lose about 7 s per minute, so the collector time is the reference.</p>
{siem_edr()}"""


def s13_access():
    return f"""
{h1('access')}
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
<tr><td><b>nginx in front of Zabbix</b></td><td>nginx serves the Zabbix frontend and hands PHP to PHP-FPM.</td><td>Plain HTTP inside VLAN 60 (gap, see {ref('iso')}).</td></tr>
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
        ("A.8.14", "Redundancy", f"2N at every layer ({ref('ha')}).", "Failover times not yet measured", "Partial"),
        ("A.8.15", "Logging", "Central collector for devices, firewalls, servers, simulators, admin sessions.", "No integrity seal (hash chain) or off-site copy; no TLS transport", "Partial"),
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
{h1('iso')}
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


# ------------------------------------------------------------------------------------------ state, scores
# Facts behind sections "state", "scores" and "roadmap". Evidence: plans/PLAN_0x checkboxes, report/tests/tests.yaml,
# lab guide section 10 (last verified run: 21 Oct 2026). Change a value here when a task is done, then rebuild.
RUNNING_DEMO = {"NAT-A", "NAT-B", "ISP-A", "ISP-B", "SW-OUT", "SW-DMZ", "SW-MGMT", "EDGE-A", "FW-A", "FW-B", "CORE-A",
                "CORE-B", "LEAF-B1", "LEAF-B2", "ADMIN-WS", "SYSLOG", "BMS-SIM", "SRV-DCIM-01", "SRV-WEB-01", "SRV-MON-01"}
NOT_DEPLOYED = {"SRV-CMP-01", "SRV-CMP-02", "SRV-CMP-03", "SRV-STO-01"}
TESTS_PASSED = 78        # dated tests in report/tests/tests.yaml (2 more written, not run yet)

WORKSTREAMS = [  # (work, weight, % done, what proves it / what is left)
    ("Design, inventory, generators, lab driver (plan 01 phases 0-2)", 10, 100, "Inventory checked (98 links, 92 IPs); generators for Cisco, pfSense, servers and tables."),
    ("Providers and border routers (phase 3)", 8, 100, "BGP 3/3 sessions on both edges, OSPF FULL, HSRP, Internet reachable."),
    ("Firewall cluster (phase 4, FW.1-FW.5)", 12, 70, "Cluster, 33 rules, NAT, CARP, pfsync, audit 0 difference. Left: LAN side when a core stops (FW.3), flow matrix (FW.4), evidence (FW.5)."),
    ("Core and leafs (phase 5)", 10, 100, "VLANs, HSRP, Rapid PVST+, LACP, OSPF, ACLs, VRF MGMT."),
    ("Servers and containers (phase 6)", 12, 71, "10 of 14 deployed. SRV-CMP-01..03, SRV-STO-01: configuration generated, not deployed."),
    ("TrueNAS backup NAS (plan 04, NAS.1-NAS.6)", 6, 100, "Installed, bond failover tested (0-1 ping lost), configuration as code (truenas_setup.py), mirror pool, snapshots, nightly pull of SRV-MON-01/SRV-INF-01 (read-only rrsync account), network configs saved by backup_configs.py, restore from a snapshot with the same SHA-256, Zabbix SNMPv3 + trapper items, 3 triggers proven on real faults."),
    ("Administration (ADM.1-ADM.4)", 6, 100, "Webterm, bastion with TOTP, access matrix 16 targets / 0 failure."),
    ("Log collection (LOG.1-LOG.6)", 8, 75, "Every running source proven (syslog_audit.py), rotation 30 days, files protected, read-only HTTPS viewer, 3 demo events found. Left: sender filter + disk queue (LOG.3), NTP in every profile, LOG.6 write-up."),
    ("Zabbix (ZBX.1-ZBX.7)", 8, 85, "17 hosts, service triggers, power alarm in 6-10 s. Left: BGP/OSPF triggers and alert timing (ZBX.7)."),
    ("Grafana (GRF.1-GRF.5)", 6, 90, "Base, offline plugin, data source; NOC dashboard (28 panels, storage row) provisioned and validated on live data, power cut red in 9.6 s. Left: GRF.5 documentation."),
    ("Resilience tests (phase 8)", 8, 10, "Only the power scenario T6 is measured; T1-T5 and M1 are not run."),
    ("Compliance matrix (ISO)", 4, 40, "Mapping written in this report; the automated matrix is not built."),
    ("Documentation (phase 9)", 8, 70, f"Lab guide, Test the Lab ({TESTS_PASSED} dated tests), this report. French report last rebuilt 12 Oct; screenshots partial."),
]

SEC_DOMAINS = [  # (domain, weight %, score now /5, target /5 after the roadmap, strengths, weaknesses)
    ("Network segmentation and filtering", 15, 4.5, 5.0, "10 VLANs in 5 zones, default deny + log, core ACL per VLAN, DMZ isolated", "Policy not measured end to end (FW.4); core ACLs are stateless"),
    ("Perimeter protection", 10, 3.5, 4.5, "Anti-spoofing, one exposed service, BGP filters, MD5, max-prefix", "No IDS/IPS, no WAF, no DDoS mitigation, no RPKI"),
    ("Identity and privileged access", 15, 4.0, 4.5, "OOB + jump host, TOTP on the bastion, named accounts, lockout, SSH only", "Local accounts only (no TACACS+/RADIUS), shared netadmin, no MFA on Zabbix/Grafana/pfSense, console without timeout"),
    ("Cryptography in transit", 10, 2.5, 4.0, "SSH v2, SNMPv3 AES-128, TLS 1.2/1.3 on the web site, HTTPS on pfSense", "Zabbix/Grafana over HTTP, syslog in clear, SNMP v2c on pfSense, MD5 for routing auth, self-signed certificates"),
    ("Hardening and configuration management", 10, 4.0, 4.5, "Generated configs, audit 0 difference, CIS-style IOS hardening, unused ports shut", "No storm-control / DHCP snooping / DAI, no config archive, container images on latest tags"),
    ("Logging and detection (SIEM)", 15, 2.0, 4.0, "Central collector for every device, firewall blocks and admin sessions logged, Zabbix alarms", "No SIEM, no correlation, no integrity seal, clocks not synchronised in the demo"),
    ("Endpoint protection (EDR)", 5, 1.0, 3.5, "auditd on the bastion, Zabbix agents", "No EDR/antivirus, no file integrity monitoring, no host firewall"),
    ("Resilience and availability", 10, 3.5, 4.5, "2N at every layer, CARP + pfsync, HSRP, bonds, power paths A/B", "Failover not measured; DNS/NTP and monitoring are single servers"),
    ("Vulnerability and patch management", 5, 0.5, 3.0, "Fixed, known versions", "No scanner, automatic updates disabled on purpose, no patch cycle"),
    ("Secrets management", 5, 1.5, 4.0, "Private repository, redacted pfSense copies, secrets never in reports for outsiders", "Plain-text secrets in the inventory, no vault, no rotation"),
]

DC_PRACTICES = [  # (real data-center practice, what the lab has, status)
    ("Two carriers, two entrance paths", "ISP-A and ISP-B, each reaching both edges", "Met"),
    ("Multihoming with own AS and BGP policy", "AS 65100, local-pref + prepend, prefix filters", "Met"),
    ("Redundant border routers", "EDGE-A / EDGE-B with HSRP + iBGP", "Met"),
    ("Stateful firewall cluster with state sync", "pfSense CARP + pfsync + XMLRPC", "Met"),
    ("Redundant core, no single point of failure", "CORE-A / CORE-B, LACP, HSRP split", "Met"),
    ("Dual-homed servers", "bond active-backup on two leafs (deployed VMs)", "Met"),
    ("Out-of-band management network", "VRF MGMT, SW-MGMT, firewall gateway", "Met"),
    ("Privileged access through a bastion with MFA", "Bastion + TOTP; no session recording or vault", "Partial"),
    ("Central AAA (TACACS+ / RADIUS)", "Local accounts on every device", "Gap"),
    ("NTP hierarchy, authenticated", "One NTP server, off in the demo, no authentication", "Partial"),
    ("Redundant DNS", "One DNS server (SRV-INF-01)", "Partial"),
    ("Central logging with retention", "Collector, 30-day rotation, read-only viewer; no integrity seal", "Met"),
    ("SIEM with correlation and use cases", "None", "Gap"),
    ("IDS / IPS", "None", "Gap"),
    ("EDR on servers", "None", "Gap"),
    ("Network monitoring (NMS) with alerting", "Zabbix 17 hosts, triggers", "Met"),
    ("DCIM / BMS integrated with supervision", "BMS-SIM and DCIM polled by Zabbix (simulated)", "Met"),
    ("2N power with alarms", "Paths A/B, alarms in 6-10 s (simulated)", "Met"),
    ("Physical security (CCTV, badges) logged", "CCTV-SIM to syslog (simulated)", "Partial"),
    ("Application load balancing", "keepalived VIP only, no load balancer", "Gap"),
    ("WAF and DDoS protection", "None (only one exposed service)", "Gap"),
    ("Backups with restore tests", "TrueNAS in hall B: ZFS mirror, hourly (24 h) / daily (14 d) snapshots, nightly pull, restore tested (same SHA-256); one copy only, no off-site copy", "Partial"),
    ("Vulnerability management", "None", "Gap"),
    ("Change management and infrastructure as code", "Plans, Git, generators, audit", "Met"),
    ("Labelling and documentation (TIA-606)", "Port descriptions, generated reports", "Met"),
    ("Failover tested and measured", "Power only", "Partial"),
    ("Encrypted management protocols everywhere", "SSH/SNMPv3/HTTPS partly; HTTP and clear syslog remain", "Partial"),
    ("Secrets in a vault", "Plain text in a private repository", "Gap"),
    ("IPv6 ready", "IPv4 only", "Gap"),
    ("Modern fabric (spine-leaf, EVPN-VXLAN)", "Collapsed core with spanning tree (fits the size)", "Partial"),
]


def completion():
    return sum(w * d for _, w, d, _ in WORKSTREAMS) / sum(w for _, w, *_ in WORKSTREAMS)


def security_score(col=2):
    return sum(r[1] * r[col] for r in SEC_DOMAINS) / 5


def conformity():
    pts = {"Met": 1, "Partial": .5, "Gap": 0}
    return 100 * sum(pts[s] for *_, s in DC_PRACTICES) / len(DC_PRACTICES)


def grade(score):
    return next(g for lim, g in ((80, "strong"), (60, "good lab baseline, not production-ready"), (40, "basic"),
                                 (0, "weak")) if score >= lim)


def tone(pct):
    return "ok" if pct >= 75 else "wip" if pct >= 40 else "bad"


# ------------------------------------------------------------------------------------------ new sections
def s0_summary():
    met = sum(s == "Met" for *_, s in DC_PRACTICES)
    gaps = [p for p, _, s in DC_PRACTICES if s == "Gap"]
    gaps = [g[0].lower() + g[1:] if g[1:2].islower() else g for g in gaps]
    return f"""
{h1('summary')}
<p>The lab is a working, two-of-everything data center network: two providers, two border routers, a firewall
cluster, two cores, four leafs, the servers that run and watch it, and an administration zone that is the only way
in. It is built from one inventory file by scripts, and every claim below has a test or a configuration behind it.</p>
<div class="score">
  <div><b>{completion():.0f} %</b><span>of the planned work done (weighted, {ref('state')})</span>{bar(completion(), tone(completion()))}</div>
  <div><b>{security_score():.0f} / 100</b><span>security score: {grade(security_score())} ({ref('scores')})</span>{bar(security_score(), tone(security_score()))}</div>
  <div><b>{conformity():.0f} %</b><span>conformity to real data-center practice: {met} of {len(DC_PRACTICES)} practices fully met</span>{bar(conformity(), tone(conformity()))}</div>
</div>
<div class="cols"><div>
<div class="box good"><b class="t">What is strong</b><ul>
<li>Redundancy designed and configured at every layer (2N): providers, edges, firewalls, cores, leafs, NICs, power.</li>
<li>Clear zoning: 10 VLANs in 5 trust zones, default deny + log, management out of band.</li>
<li>One audited way in: administration zone, bastion with TOTP, SSH v2, login lockout.</li>
<li>Infrastructure as code: generated configurations, audit = 0 difference, one Git commit per change.</li>
<li>Supervision live: Zabbix on 17 hosts, power-cut alarm in 6 to 10 s, Grafana on a read-only account.</li>
</ul></div></div><div>
<div class="box warn"><b class="t">What is missing or weak</b><ul>
<li>No SIEM, no IDS/IPS, no EDR: logs are collected but nobody correlates them ({ref('supervision')}).</li>
<li>Some management traffic in clear: Zabbix and Grafana over HTTP, syslog over UDP, SNMP v2c on pfSense.</li>
<li>Failover designed but not measured (only the power scenario is); five servers not deployed.</li>
<li>No vulnerability or patch process; secrets in plain text in the private repository.</li>
<li>Single DNS/NTP and monitoring servers; clocks unsynchronised in the demo profile.</li>
</ul></div></div></div>
<h2>Where the lab stands today</h2>
<table><thead><tr><th style="width:24%">Question</th><th>Answer</th></tr></thead><tbody>
<tr><td><b>Is it running now?</b></td><td>On {DOC_DATE} the profile <code>nas</code> runs (8 nodes: admin zone, FW-A, CORE-A, hall B leafs, SYSLOG, TrueNAS). The last full run is the demo of 21 October 2026 (20 nodes, cold start in about 10 minutes, 0 running host unavailable in Zabbix).</td></tr>
<tr><td><b>What is configured?</b></td><td>Every network device, both firewalls, 9 of 14 servers and containers, supervision (Zabbix, Grafana), administration (webterm, bastion).</td></tr>
<tr><td><b>What is not?</b></td><td>Compute and storage servers (generated, not deployed);  log retention and viewer; network triggers (BGP/OSPF); measured failover; SIEM / IDS / EDR (not in the plans).</td></tr>
<tr><td><b>How proven?</b></td><td>{TESTS_PASSED} dated tests in "Test the Lab", firewall audit 0 difference, access matrix 0 failure, power test 6-10 s.</td></tr>
<tr><td><b>Real-world gaps (not met)</b></td><td>{E(", ".join(gaps))}.</td></tr>
</tbody></table>"""


EQUIP = {  # node: (layer, placement and why there, role / purpose, software, protection)
    "ISP-A": ("Provider", "Outside the site, reaches EDGE-A and EDGE-B", "Simulated primary carrier AS64500; gives a default route and carries our prefix to the Internet", "FRRouting (Docker)", "BGP MD5, filters on our side"),
    "ISP-B": ("Provider", "Outside the site, reaches EDGE-A and EDGE-B", "Simulated backup carrier AS64501", "FRRouting (Docker)", "BGP MD5, filters on our side"),
    "NAT-A": ("Lab uplink", "GNS3 VM", "Gives ISP-A access to the real Internet (updates, tests)", "GNS3 NAT node (libvirt)", "Lab only"),
    "NAT-B": ("Lab uplink", "GNS3 VM", "Same for ISP-B", "GNS3 NAT node", "Lab only"),
    "EDGE-A": ("Border", "ER: where the carriers enter the building, outside the firewalls", "eBGP to both providers, iBGP to EDGE-B, primary holder of the gateway 10.254.1.6", "Cisco IOSv 15.9", "Anti-spoofing ACL, BGP filters, MD5, VRF MGMT, SSH only"),
    "EDGE-B": ("Border", "ER, second entrance path", "Same role, takes over if EDGE-A fails", "Cisco IOSv 15.9", "Same as EDGE-A"),
    "SW-OUT": ("Transit switch", "ER: joins edges and firewalls (VLAN 901)", "Lets both edges reach both firewalls", "GNS3 built-in switch", "Carries only transit"),
    "FW-A": ("Security", "MDA: between the border and the inside, next to the cores", "Stateful firewall, NAT, gateway of DMZ/MGMT/ADMIN, CARP master", "pfSense 2.7.2", "Default deny + log, GUI from ADMIN only, 15 min timeout, generated + audited"),
    "FW-B": ("Security", "MDA, same rack row, own power path", "Hot standby with the same states (pfsync)", "pfSense 2.7.2", "Same as FW-A"),
    "SW-DMZ": ("DMZ switch", "MDA", "Joins the firewalls and the public web server (VLAN 50)", "GNS3 built-in switch", "Only reachable through the firewall"),
    "SW-MGMT": ("OOB switch", "MDA: central, one port per device", "Management port of every device (VLAN 10) and admin zone (VLAN 90)", "GNS3 built-in switch", "No data VLAN ever reaches it"),
    "CORE-A": ("Core", "MDA: the center of the star, one cable to each leaf", "Gateway of VLANs 20/40/60/100, STP root of them, inter-VLAN ACLs, OSPF", "Cisco IOSvL2 15.2", "ACL per VLAN, HSRP MD5, loopguard, VRF MGMT"),
    "CORE-B": ("Core", "MDA, second core, own power path", "Gateway and root of VLANs 30/70/80, backup of the others", "Cisco IOSvL2 15.2", "Same as CORE-A"),
    "LEAF-A1": ("Access", "HDA-A: row end of hall A", "Server ports of hall A (NIC0)", "Cisco IOSvL2 15.2", "Portfast + BPDU guard, unused ports shut in VLAN 999"),
    "LEAF-A2": ("Access", "HDA-A, second leaf of hall A", "Server ports of hall A (NIC1)", "Cisco IOSvL2 15.2", "Same"),
    "LEAF-B1": ("Access", "HDA-B: row end of hall B", "Server ports of hall B (NIC0), log collector", "Cisco IOSvL2 15.2", "Same"),
    "LEAF-B2": ("Access", "HDA-B, second leaf of hall B", "Server ports of hall B (NIC1), BMS and CCTV simulators", "Cisco IOSvL2 15.2", "Same"),
    "SRV-CMP-01": ("Compute", "EDA-A (hall A racks)", "Application server :8443, keepalived master of VIP 10.20.0.10", "Ubuntu 20.04, Python app, keepalived, iperf3", "Bond, named admin account, core ACL"),
    "SRV-CMP-02": ("Compute", "EDA-A", "Application server, keepalived backup", "Same", "Same"),
    "SRV-CMP-03": ("Compute", "EDA-A", "Application server", "Same", "Same"),
    "SRV-STO-01": ("Storage", "EDA-A, next to compute (short path)", "NFS and iSCSI for the servers", "Ubuntu, nfs-kernel-server, tgt", "Reachable only from VLAN 20"),
    "SRV-BCK-01": ("Backup NAS", "EDA-B: the other hall, so a fire in hall A spares the backups", "TrueNAS backup repository: ZFS mirror, snapshots, backups pulled from the servers", "TrueNAS SCALE 25.10.7 (3 GB RAM, 3 SATA disks)", "Bond failover, UI/API and SSH allowlisted to VLAN 90, SNMPv3 only (v2c off), every other service off, servers hold no credential to it"),
    "SRV-INF-01": ("Infrastructure", "EDA-B", "DNS (dnsmasq, zone dc.casa.lab), NTP (chrony), DHCP ready", "Ubuntu, dnsmasq, chrony, Zabbix agent", "Bond, named admin account"),
    "SRV-MON-01": ("Supervision", "EDA-B", "Zabbix server and Grafana", "Ubuntu, Zabbix 6.0.48, MariaDB, nginx, PHP-FPM, Grafana 13.2.3", "Read-only Grafana account, default passwords replaced"),
    "SRV-DCIM-01": ("Facilities", "EDA-B", "DCIM: state of the 96 racks, reads the BMS", "Python (Docker)", "VLAN 70, API read by Zabbix"),
    "SYSLOG": ("Supervision", "EDA-B", "Central log collector", "rsyslog on Alpine (Docker)", "Separate from the devices it records"),
    "BMS-SIM": ("Facilities", "EDA-B", "Building management simulator: utility, UPS, generator, paths A/B, PUE", "Python (Docker)", "VLAN 70, alarms to syslog"),
    "CCTV-SIM": ("Physical security", "EDA-B", "Cameras, motion and badge events", "Python (Docker)", "VLAN 80, events to syslog"),
    "SRV-WEB-01": ("DMZ", "DMZ behind the firewall, never on the inside", "Public web site (192.0.2.80)", "nginx (Alpine)", "TLS 1.2/1.3, HSTS, CSP, only 80/443 exposed"),
    "SRV-BASTION": ("Administration", "MDA, admin zone VLAN 90", "SSH jump host", "Ubuntu, PAM google-authenticator, auditd", "Password + TOTP, ubuntu account refused"),
    "ADMIN-WS": ("Administration", "MDA, admin zone VLAN 90", "Browser desktop and SSH to every device; sessions logged", "gns3/webterm (Debian), Firefox, SSH, SNMP tools", "Only the admin zone reaches devices"),
}


def node_state(n):
    if n in NOT_DEPLOYED:
        return '<span class="pill todo">not deployed</span>'
    return '<span class="pill ok">running</span>' if n in RUNNING_DEMO else '<span class="pill wip">off in demo</span>'


def s_equipment():
    rows = [[f"<b>{n}</b>", E(l), E(pl), E(r), E(sw), E(pr), node_state(n)] for n, (l, pl, r, sw, pr) in EQUIP.items()]
    return f"""
{h1('equipment')}
<p>Every node of the GNS3 project, the layer it belongs to, where it sits in the TIA-942 building and why, what it is
for, what runs on it and how it is protected. "State" is the demo profile of 21 October 2026 (the profile that fits
the 16 GB host); "off in demo" nodes are configured and verified, only stopped to save memory.</p>
<h2>TIA-942 spaces: what the position names mean</h2>
<table><thead><tr><th style="width:12%">Space</th><th style="width:30%">Real data center</th><th>In the lab</th></tr></thead><tbody>
<tr><td><b>ER</b></td><td>Entrance Room: where carrier cables enter, carrier demarcation.</td><td>ISP links, EDGE-A/B, SW-OUT. Two carriers, two paths.</td></tr>
<tr><td><b>MDA</b></td><td>Main Distribution Area: core switches, firewalls, central cross-connect.</td><td>FW-A/B, CORE-A/B, SW-DMZ, SW-MGMT, administration zone.</td></tr>
<tr><td><b>HDA</b></td><td>Horizontal Distribution Area: row switches serving a hall.</td><td>LEAF-A1/A2 (hall A), LEAF-B1/B2 (hall B).</td></tr>
<tr><td><b>EDA</b></td><td>Equipment Distribution Area: the server racks.</td><td>Compute and storage in hall A, backup, supervision and facilities in hall B.</td></tr>
</tbody></table>
<p>Placement rule: each element of a pair is fed by its own power path and its own cables, so one fault (power,
cable, rack) takes one side only. Backups sit in the other hall than the data they protect.</p>
<h2>Every node</h2>
{table(["Node", "Layer", "Position and why", "Role / purpose", "Software", "Protection", "State"], rows,
       ["11%", "8%", "17%", "22%", "15%", None, "8%"])}"""


PROTOCOLS = [  # (protocol, layer / port, where, why chosen, alternatives, protection, state)
    ("IEEE 802.1Q trunking", "L2", "Cores ↔ leafs, FW em6, Po1", "Many VLANs on one cable", "One cable per VLAN (does not scale)", "Allowed-VLAN lists, DTP off, VLAN 1 pruned", "Active"),
    ("LACP (802.3ad)", "L2", "CORE-A ↔ CORE-B (Po1)", "Double bandwidth and survive a link loss; detects mis-cabling", "Static EtherChannel (no checks), PAgP (Cisco only)", "Mode active", "Active"),
    ("Rapid PVST+ (802.1w)", "L2", "Cores and leafs", "Loop-free L2 with ~1 s convergence; per-VLAN roots aligned with HSRP", "802.1D (30-50 s), MST (better for hundreds of VLANs)", "Root priorities, loopguard, BPDU guard", "Active"),
    ("LLDP (802.1AB)", "L2", "Cores, leafs", "Standard neighbour discovery for cabling checks", "CDP (Cisco only)", "Not sent on WAN ports; CDP off on WAN", "Active"),
    ("VTP transparent", "L2", "Cores, leafs", "VLANs defined by the generator on each switch", "VTP server/client (one mistake wipes all VLANs)", "-", "Active"),
    ("pfSense lagg failover", "L2", "FW em3/em4 → cores", "One firewall port to each core without MLAG on the cores", "LACP to two switches (needs vPC/stack)", "-", "Active"),
    ("Linux bonding active-backup", "L2", "Servers (bond0)", "Dual-homing on two independent leafs, no switch support needed", "802.3ad bond (needs MLAG)", "MII 100 ms", "Active"),
    ("HSRP v2", "L3, UDP 1985", "Cores (all internal VLANs + 902), edges (901)", "Cisco first-hop redundancy, fast timers, v2 for group numbers above 255", "VRRP (open, used on servers), GLBP (balancing, more complex)", "MD5 key, preempt delay 30 s", "Active"),
    ("CARP", "L3, IP proto 112", "FW-A / FW-B", "pfSense native virtual IPs, works with pfsync", "VRRP (not native on pfSense)", "Password, advskew 0/100", "Active"),
    ("pfsync", "L3, IP proto 240", "FW SYNC link", "Copies connection states: sessions survive a firewall failover", "None on pfSense", "Dedicated cable 10.254.3.0/30", "Active"),
    ("XMLRPC sync", "TCP 443", "FW-A → FW-B", "Copies rules, NAT, aliases on every change", "Manual copy (drift)", "HTTPS, admin credentials, SYNC link", "Active"),
    ("VRRP (keepalived)", "IP proto 112", "SRV-CMP-01/02", "Shared application VIP 10.20.0.10, standard, Linux native", "Pacemaker (heavier)", "Allowed by the VLAN 20 ACL only", "Configured"),
    ("OSPFv2 area 0", "L3, IP proto 89", "Edges, cores", "Fast internal convergence, standard, one area is enough for this size", "EIGRP (Cisco only), IS-IS (less known), static (no failover)", "MD5, passive by default, hello 1 s / dead 3 s", "Active"),
    ("BGP-4 (eBGP + iBGP)", "TCP 179", "Edges ↔ ISPs, EDGE-A ↔ EDGE-B", "The only way to multihome with our own AS and prefix and to steer traffic", "Two static defaults (no inbound control, no own prefix)", "MD5, prefix-lists, max-prefix 100, timers 3/9 s", "Active"),
    ("Static routes", "L3", "Firewalls, cores, edges", "Simple, deterministic, toward virtual addresses (HSRP/CARP)", "OSPF on pfSense (extra package)", "Point to VIPs", "Active"),
    ("VRF-lite MGMT", "L3", "Every Cisco device", "Separate routing table for management: never routed with data", "Management in a data VLAN", "Only the firewall routes to it", "Active"),
    ("NAT / PAT", "L3/L4", "Firewalls", "Private addressing inside; one public address out; one DNAT in", "Public addresses inside (wastes space, exposes)", "Only TCP 80/443 forwarded", "Active"),
    ("ICMP", "L3", "Everywhere", "Diagnostics, Zabbix ping", "-", "No redirects/unreachables on WAN", "Active"),
    ("SSH v2", "TCP 22", "Every device and server", "Encrypted administration", "Telnet (clear text)", "vty ACL, lockout, 10 min timeout, TOTP on bastion", "Active"),
    ("HTTPS / TLS 1.2-1.3", "TCP 443", "Web site, pfSense GUI", "Encrypted web", "-", "HSTS, CSP; self-signed certificates", "Active"),
    ("HTTP", "TCP 80, 3000, 8080", "Zabbix UI, Grafana, BMS/DCIM API", "Simplicity in the lab", "HTTPS with an internal CA (planned)", "Reachable only from VLANs 60 and 90", "Active (gap)"),
    ("SNMPv3 authPriv", "UDP 161/162", "Cisco devices ↔ Zabbix", "Authenticated and encrypted polling and traps", "SNMP v2c (clear community)", "SHA + AES-128, view + ACL", "Active"),
    ("SNMP v2c", "UDP 161", "pfSense ↔ Zabbix", "pfSense base SNMP daemon has no v3", "net-snmp package with v3", "Read-only, bound to LAN, VLAN 60 only", "Active (gap)"),
    ("Syslog", "UDP 514", "Everything → 10.60.0.12", "Universal, every device speaks it", "Syslog over TLS (RFC 5425), RELP", "Firewall and ACL limit senders", "Active"),
    ("NTP", "UDP 123", "Everything → 10.100.0.11", "Coherent timestamps for logs and TOTP", "PTP (overkill)", "None (no NTP authentication)", "Configured, off in demo"),
    ("DNS", "UDP/TCP 53", "Everything → 10.100.0.11", "Internal zone dc.casa.lab, forwarding", "-", "Only from internal zones", "Configured, off in demo"),
    ("DHCP", "UDP 67/68", "-", "Not used: static addressing, generated", "-", "pfSense DHCP off", "Off by design"),
    ("Zabbix agent / trapper", "TCP 10050 / 10051", "Servers ↔ SRV-MON-01", "Host metrics", "SNMP on servers", "Core ACL + firewall rule EXT-8", "Active"),
    ("Zabbix JSON-RPC API", "HTTP 80", "zabbix_setup.py, Grafana", "Configuration as code, dashboards", "-", "Read-only account for Grafana", "Active"),
    ("TOTP (RFC 6238)", "-", "SRV-BASTION (PAM)", "Second factor for remote administration", "Hardware keys, push MFA", "Secret 0600, per user", "Active"),
    ("NFS / iSCSI", "TCP 2049, 111, 3260", "SRV-STO-01", "File and block storage for servers", "SMB", "VLAN 20 only", "Configured"),
    ("rsync over SSH (pull)", "TCP 22", "SRV-BCK-01 → servers", "Incremental backups started by the NAS: a hacked server cannot delete them", "Push to an rsync daemon (none in TrueNAS 24.10+), Bacula, Veeam", "Core ACL VLAN 40 only; account nasbackup: NAS key from 10.40.0.11 only, forced rrsync -ro", "Running"),
    ("Telnet / VNC consoles", "TCP 50xx / 59xx", "GNS3 VM (host-only network)", "Lab console access to every node", "-", "Reachable from the PC only", "Lab only"),
    ("SOCKS5", "TCP 1080", "Lab proxy in the GNS3 VM", "PC browser acts as ADMIN-WS", "VPN", "Host-only network; ADMIN rules apply", "Lab only"),
    ("MD5 (routing auth)", "-", "HSRP, OSPF, BGP", "Supported everywhere in IOSv 15", "OSPF HMAC-SHA, BGP TCP-AO", "Keys in inventory", "Active (weak hash)"),
]


def s_protocols():
    st = {"Active": "ok", "Configured": "wip", "Lab only": "todo", "Off by design": "todo"}
    rows = [[f"<strong>{E(p)}</strong>", E(l), E(w), E(y), E(a), E(pr),
             f'<span class="pill {st.get(s, "bad" if "gap" in s or "weak" in s else "wip")}">{E(s)}</span>']
            for p, l, w, y, a, pr, s in PROTOCOLS]
    n = {k: sum(1 for *_, s in PROTOCOLS if s.startswith(k)) for k in ("Active", "Configured")}
    return f"""
{h1('protocols')}
<p>{len(PROTOCOLS)} protocols are in use or prepared. For each: where it runs, why it was chosen over the usual
alternatives, how it is protected and whether it is active. {n['Active']} are active, {n['Configured']} configured but
not running in the demo profile. "Gap" marks a protocol that works but is weaker than a production standard.</p>
{table(["Protocol", "Layer / port", "Where", "Why chosen", "Alternatives not chosen", "Protection", "State"], rows,
       ["13%", "8%", "13%", "21%", "16%", None, "9%"])}
<h2>Rules that guided the choices</h2>
<ul>
<li><b>Open standards first</b> (802.1Q, LACP, 802.1w, OSPF, BGP, VRRP, SNMPv3, syslog), Cisco-only protocols only where
the platform offers nothing better (HSRP on IOS).</li>
<li><b>Every control protocol authenticated</b>: BGP, OSPF, HSRP, CARP carry a key, so a rogue box cannot join.</li>
<li><b>Encrypted where people log in</b>: SSH, HTTPS, TOTP. Clear-text protocols that remain are listed as gaps.</li>
<li><b>Fast but stable timers</b>: BGP 3/9 s, OSPF 1/3 s, HSRP 1/3 s on the cores (250/750 ms on the edges); faster
core timers flapped on the overloaded host and were relaxed on 20 Oct 2026.</li>
</ul>"""


def port_matrix():
    rows = [
        ("22", "TCP", "SSH", "Every device and server", "ADMIN zone (VLAN 90)"),
        ("53", "UDP/TCP", "DNS", "SRV-INF-01", "Internal VLANs, DMZ, MGMT, ADMIN"),
        ("80", "TCP", "HTTP", "SRV-WEB-01 (redirect), SRV-MON-01 (Zabbix)", "Internet (web), VLAN 90 (Zabbix)"),
        ("123", "UDP", "NTP", "SRV-INF-01", "Internal VLANs, DMZ, MGMT, ADMIN"),
        ("161", "UDP", "SNMP", "Every network device", "VLAN 60 (polling), VLAN 90"),
        ("162", "UDP", "SNMP traps", "SRV-MON-01", "MGMT network, internal VLANs"),
        ("179", "TCP", "BGP", "EDGE-A/B", "ISP neighbours, the other edge"),
        ("443", "TCP", "HTTPS", "SRV-WEB-01, pfSense GUI", "Internet (web), VLAN 90 (GUI)"),
        ("514", "UDP", "Syslog", "SYSLOG 10.60.0.12", "Every device, server and zone"),
        ("22 (pull)", "TCP", "rsync over SSH", "Servers (VLANs 20, 30, SRV-MON-01, SRV-INF-01)", "SRV-BCK-01 (VLAN 40)"),
        ("1985", "UDP", "HSRP", "Cores, edges (multicast 224.0.0.102)", "Same VLAN only"),
        ("2049 / 111", "TCP/UDP", "NFS / portmap", "SRV-STO-01", "VLAN 20"),
        ("3000", "TCP", "Grafana", "SRV-MON-01", "VLAN 90"),
        ("3260", "TCP", "iSCSI", "SRV-STO-01", "VLAN 20"),
        ("8080", "TCP", "BMS / DCIM API", "BMS-SIM, SRV-DCIM-01", "VLAN 60, VLAN 70, VLAN 90"),
        ("8443", "TCP", "Application", "SRV-CMP-01..03, VIP 10.20.0.10", "DMZ (web tier)"),
        ("10050", "TCP", "Zabbix agent (passive)", "Servers", "VLAN 60"),
        ("10051", "TCP", "Zabbix trapper (active)", "SRV-MON-01", "Every data VLAN, bastion (EXT-8)"),
        ("proto 89 / 112 / 240", "IP", "OSPF / CARP-VRRP / pfsync", "Routers, firewalls, compute", "Link-local or dedicated links"),
    ]
    return ('<h2>Port matrix: every port that is open, and to whom</h2>'
            + table(["Port", "Proto", "Service", "Listens on", "Allowed from"], [[f"<b>{a}</b>", b, E(c), E(d), E(e)]
                                                                               for a, b, c, d, e in rows],
                    ["13%", "8%", "17%", "31%", None])
            + "<p>Everything not in this table is closed: by the firewall default deny, by the core ACLs, or because no "
              "service listens.</p>")


HARDENING = {  # platform: [(measure, status, note)]
    "Cisco IOS / IOSvL2 (edges, cores, leafs)": [
        ("SSH v2 only, Telnet off on vty, vty ACL ACL-MGMT-ACCESS", "Met", "transport input ssh"),
        ("AAA new-model, local named account privilege 15, enable secret", "Met", "Central TACACS+/RADIUS missing"),
        ("Login protection: block 120 s after 5 failures in 60 s, log success and failure", "Met", "login block-for"),
        ("Idle timeout 10 min on vty; legal banner", "Met", "Console has no timeout (lab convenience)"),
        ("Unneeded services off: HTTP server, source-route, BOOTP, PAD, domain lookup", "Met", ""),
        ("WAN ports: no redirects, no unreachables, no proxy-ARP, no CDP/LLDP transmit", "Met", ""),
        ("Anti-spoofing ACL on WAN (private, loopback, own prefix denied + logged)", "Met", "uRPF removed: dropped replies with a default-only table"),
        ("Management in VRF MGMT, SNMPv3 authPriv with view + ACL, logs and NTP sourced from it", "Met", ""),
        ("Routing protocol authentication (BGP, OSPF, HSRP)", "Partial", "MD5 is old; HMAC-SHA / TCP-AO preferred"),
        ("BGP: prefix-lists in/out, max-prefix 100, no default IPv4 unicast", "Met", "GTSM (ttl-security) and RPKI missing"),
        ("L2: DTP off, VLAN 1 shut and pruned, unused ports shut in VLAN 999", "Met", ""),
        ("L2: portfast + BPDU guard on server ports, loopguard, fixed root priorities", "Met", ""),
        ("L2: storm-control, DHCP snooping, dynamic ARP inspection, port-security", "Gap", "Static addressing lowers the risk"),
        ("Configuration archive and change logging, AAA accounting", "Gap", "Config changes reach syslog only as %SYS-5-CONFIG_I"),
        ("Passwords stored hashed (secret, service password-encryption)", "Met", ""),
    ],
    "pfSense (FW-A, FW-B)": [
        ("Default deny + log on every interface; rules generated and audited (0 difference)", "Met", ""),
        ("Web GUI HTTPS, reachable from the ADMIN zone only, idle sessions closed after 15 min", "Met", ""),
        ("Unused services off: DHCP server, DNS resolver", "Met", "Smaller attack surface"),
        ("Remote syslog of everything to 10.60.0.12", "Met", ""),
        ("HA on a dedicated cable (pfsync, XMLRPC), CARP with password", "Met", ""),
        ("SNMP read-only, bound to LAN, VLAN 60 only", "Partial", "v2c community, not v3"),
        ("Self-signed GUI certificate, shared admin account, no MFA on the GUI", "Partial", ""),
        ("IDS/IPS (Suricata or Snort), pfBlockerNG reputation lists", "Gap", ""),
    ],
    "Ubuntu servers (VMs)": [
        ("Named sudo account sysadmin; image account ubuntu refused by SSH", "Met", "ADM.4"),
        ("Bastion: password + TOTP (PAM), AllowGroups sudo, banner, auditd", "Met", ""),
        ("Bonded NICs, static addressing, Zabbix agent", "Met", ""),
        ("SSH keys only (no passwords)", "Gap", "Passwords + TOTP today"),
        ("Host firewall (ufw/nftables), fail2ban", "Gap", "Network ACLs only"),
        ("Automatic security updates", "Gap", "Disabled on purpose: apt locks broke deployments"),
        ("File integrity monitoring, EDR", "Gap", "See " + ref("supervision")),
    ],
    "Containers and services": [
        ("Small Alpine-based images, one process each, static addresses", "Met", ""),
        ("Web: TLS 1.2/1.3, HSTS, CSP, X-Frame-Options DENY, nosniff, no-referrer, server_tokens off", "Met", ""),
        ("Grafana: anonymous and sign-up off, settings file 0640, plugin checked by SHA-256", "Met", ""),
        ("Zabbix: default Admin password replaced, read-only account for Grafana", "Met", ""),
        ("Images pinned to exact versions", "Gap", "frr, webterm and nginx use latest tags"),
        ("TLS on Zabbix and Grafana, WAF in front of the web site", "Gap", ""),
    ],
}

THREATS = [  # (threat, example, countermeasure in place, status, what is missing)
    ("IP spoofing from the Internet", "Packets claiming 10.x or 192.0.2.x sources", "ACL-WAN-IN on both edges drops and logs private, loopback and own-prefix sources", "Met", "-"),
    ("Route hijack / BGP attack", "Fake routes or session reset from a provider", "MD5, accept default only, announce our /24 only, max-prefix 100", "Met", "RPKI, GTSM"),
    ("Scan and attack of exposed services", "Port scan of 192.0.2.0/24", "Only 192.0.2.80 TCP 80/443 is forwarded; the rest hits default deny", "Met", "IPS, WAF, DDoS scrubbing"),
    ("Pivot from a compromised DMZ server", "Web shell on SRV-WEB-01", "DMZ may reach only the app VIP on 8443 and DNS/NTP; MGMT, ADMIN, storage, backup blocked + logged", "Met", "IDS on DMZ"),
    ("Lateral movement / ransomware inside", "Infected compute server scans the network", "Core ACL per VLAN: storage only via NFS/iSCSI, backups pulled by the NAS (no write path from servers), MGMT/ADMIN denied + logged", "Met", "Micro-segmentation inside a VLAN, EDR"),
    ("Attack on the management plane", "SSH to a switch from a server VLAN", "OOB VRF, vty ACL, deny + log toward 10.10/10.90 on every SVI", "Met", "-"),
    ("Password brute force", "Repeated SSH logins", "Lockout 120 s after 5 failures, logged; TOTP on the bastion", "Met", "Lockout on Zabbix/Grafana"),
    ("Stolen administrator password", "Phished netadmin password", "Usable only from the admin zone; bastion needs TOTP", "Partial", "MFA on every device (TACACS+ with MFA)"),
    ("Rogue switch / STP manipulation", "Switch plugged on a server port", "BPDU guard err-disables the port; root priorities fixed; loopguard", "Met", "-"),
    ("VLAN hopping", "DTP or double tagging", "DTP off, VLAN 1 unused, static access ports", "Met", "Native VLAN tagging"),
    ("ARP / DHCP spoofing in a VLAN", "Man in the middle on VLAN 20", "Static addressing, DHCP off", "Gap", "DHCP snooping, DAI"),
    ("Gateway hijack (rogue HSRP/CARP)", "Fake router with higher priority", "HSRP MD5, CARP password", "Met", "-"),
    ("Eavesdropping on management", "Sniffing SNMP or web logins", "SSH, SNMPv3 AES, HTTPS on pfSense", "Partial", "HTTPS on Zabbix/Grafana, TLS syslog, SNMPv3 on pfSense"),
    ("Log tampering / denial", "Attacker deletes local logs", "Logs copied at once to a separate collector, 0640 files, viewer cannot write", "Partial", "Integrity seal, off-site copy, NTP"),
    ("Malware on a server", "Crypto-miner on SRV-CMP-01", "Network ACLs limit its reach; Zabbix sees CPU", "Gap", "EDR, FIM, antivirus"),
    ("Unpatched vulnerability", "Known CVE in nginx", "Small images, few services", "Gap", "Scanner, patch cycle"),
    ("Secret leak", "Repository copied", "Private repository, redacted pfSense exports", "Partial", "Vault, rotation"),
    ("Denial of service", "Flood toward the web site", "pfSense state table, BGP max-prefix", "Partial", "Rate limits, storm-control, provider DDoS service"),
    ("Equipment failure", "CORE-A dies", "2N everywhere (HSRP, CARP, LACP, bonds)", "Met", "Measured failover"),
    ("Power failure", "Utility A + UPS A lost", "Two power paths; BMS alarm in 6-10 s; Zabbix disaster trigger", "Met", "-"),
    ("Physical intrusion", "Badge forced at night", "CCTV/badge events to syslog (simulated)", "Partial", "Correlation and alerting (SIEM)"),
    ("Unauthorised configuration change", "Manual change on a firewall", "Generated configs, fw_audit.py finds any difference", "Partial", "Alert on Cisco config change, config archive"),
]


def s_hardening():
    hard = []
    for plat, items in HARDENING.items():
        met = sum(1 for _, s, _ in items if s == "Met")
        hard.append(f"<h3>{E(plat)}: {met} of {len(items)} measures met</h3>")
        hard.append(table(["Measure", "Status", "Note"], [[E(m), pill(s), E(n)] for m, s, n in items], [None, "9%", "32%"]))
    met = sum(1 for *_, s, _ in THREATS if s == "Met")
    return f"""
{h1('hardening')}
<p>Hardening is what makes each box hard to break; countermeasures are what stop a given attack. Both are listed
with an honest status. The configurations quoted in {ref('security')} are the proof of the "Met" lines.</p>
<h2>Hardening, platform by platform</h2>
{"".join(hard)}
<h2>Threats and countermeasures</h2>
<p>{met} of {len(THREATS)} threats are fully countered; the others are reduced but need the item in the last column.</p>
{table(["Threat", "Example", "Countermeasure in place", "Status", "Still missing"],
       [[f"<strong>{E(a)}</strong>", E(b), E(c), pill(d), E(e)] for a, b, c, d, e in THREATS], ["16%", "17%", None, "8%", "19%"])}"""


SOFTWARE = [  # (software, version, node, how it is configured)
    ("Cisco IOSv", "15.9", "EDGE-A/B", "configs/EDGE-*.cfg generated by gen_configs.py, pushed by labctl.py"),
    ("Cisco IOSvL2", "15.2", "CORE-A/B, LEAF-*", "configs/CORE-*.cfg, LEAF-*.cfg, same chain"),
    ("pfSense CE", "2.7.2", "FW-A/B", "gen_pfsense.py → config.xml per firewall, deploy_pfsense.py (FW-B first, rollback), fw_audit.py"),
    ("FRRouting", "image latest", "ISP-A/B", "Baked into the Docker image (docker/frr-isp), applied at start"),
    ("Ubuntu Server", "20.04", "SRV-* VMs", "netplan bond + roles by deploy_servers.py over the serial console"),
    ("Zabbix server + frontend", "6.0.48 LTS", "SRV-MON-01", "Packages from the offline repository; hosts, items, triggers by zabbix_setup.py apply"),
    ("MariaDB, nginx, PHP-FPM", "Ubuntu packages", "SRV-MON-01", "Zabbix back-end and web front-end"),
    ("Grafana", "13.2.3", "SRV-MON-01", "GF_* settings, provisioning from grafana/, deploy_servers.py --role=grafana"),
    ("Zabbix plugin for Grafana", "6.8.0", "SRV-MON-01", "Offline zip checked by SHA-256, data source provisioned"),
    ("Zabbix agent", "Ubuntu package", "SRV-MON-01, SRV-INF-01, SRV-BASTION", "Passive (10050) or active (10051)"),
    ("dnsmasq, chrony", "Ubuntu packages", "SRV-INF-01", "Zone dc.casa.lab, forwarders 1.1.1.1 / 8.8.8.8; NTP for every device"),
    ("libpam-google-authenticator, auditd", "Ubuntu packages", "SRV-BASTION", "TOTP enforced for SSH, audit of commands"),
    ("rsyslog + logrotate + viewer", "Alpine 3.20", "SYSLOG", "UDP/TCP 514, one file per source, 30-day rotation, read-only HTTPS viewer (docker/syslog)"),
    ("nginx", "Alpine (latest)", "SRV-WEB-01", "docker/web/default.conf: HTTPS, security headers, /health"),
    ("Python simulators", "Python 3.12 Alpine", "BMS-SIM, SRV-DCIM-01, CCTV-SIM", "docker/bms-sim, dcim, cctv-sim: JSON APIs, events to syslog"),
    ("gns3/webterm + tools", "Debian (latest)", "ADMIN-WS", "Firefox portal, SSH aliases and portal generated from the inventory"),
    ("nfs-kernel-server, tgt, keepalived, iperf3", "Ubuntu packages", "SRV-STO-01, SRV-CMP-*", "Roles written in deploy_servers.py, not deployed yet"),
    ("TrueNAS SCALE", "25.10.7", "SRV-BCK-01", "ISO checked by SHA-256, nas_node.py (GNS3 node), installed over VNC, network by midclt; configured by truenas_setup.py (JSON-RPC over wss, idempotent); backup_configs.py saves the network configs"),
]


def software_table():
    return ("<h2>Installed software and how it is configured</h2>"
            + table(["Software", "Version", "Node", "Configured by"],
                    [[f"<strong>{E(a)}</strong>", E(b), E(c), E(d)] for a, b, c, d in SOFTWARE], ["22%", "12%", "20%", None]))


def siem_edr():
    uc = [("Brute force on SSH", "Cisco %SEC_LOGIN-1-QUIET_MODE_ON, sshd failures", "5 failures from one source in 1 min", "Alert, block source on the firewall"),
          ("Login outside the bastion", "Device login logs", "Successful login whose source is not 10.90.0.0/24", "Critical alert"),
          ("Configuration change", "%SYS-5-CONFIG_I, pfSense config history", "Any change outside a planned window", "Alert + diff from fw_audit.py"),
          ("Firewall block burst", "pfSense filterlog", "> 100 blocks / min from one source", "Alert, possible scan"),
          ("Failover event", "CARP, HSRP state change, BGP neighbour down", "Any state change", "Alert NOC, correlate with power/BMS"),
          ("Rogue device", "%SPANTREE-2-BLOCK_BPDUGUARD", "Any occurrence", "Alert, port stays err-disabled"),
          ("Physical + logical", "CCTV badge event + admin login", "Badge at night followed by a login", "Critical alert"),
          ("Lateral movement", "Core ACL deny logs toward MGMT/ADMIN", "Any deny from a server VLAN", "Investigate the source server")]
    return f"""
<h2>Security detection: SIEM, EDR, IDS (honest state)</h2>
<table><thead><tr><th style="width:18%">Capability</th><th style="width:12%">State</th><th>What exists today</th></tr></thead><tbody>
<tr><td><b>Supervision (NMS)</b></td><td>{pill("Met")}</td><td>Zabbix: availability, performance, power, racks, web site, collector; alarms in seconds.</td></tr>
<tr><td><b>Central log collection</b></td><td>{pill("Partial")}</td><td>Every device, firewall, server, simulator and admin session sends to 10.60.0.12. This is the first brick of a SIEM, not a SIEM: no parsing, no correlation, no alert on log content. Retention 30 days and a read-only viewer are in place.</td></tr>
<tr><td><b>SIEM</b></td><td>{pill("Gap")}</td><td>None. Security events are written but only found by a person who searches the files.</td></tr>
<tr><td><b>EDR / XDR</b></td><td>{pill("Gap")}</td><td>None. auditd on the bastion only; Zabbix agents give metrics, not security telemetry.</td></tr>
<tr><td><b>IDS / IPS</b></td><td>{pill("Gap")}</td><td>None. The firewall filters by address and port, it does not inspect content.</td></tr>
</tbody></table>
<h2>Target design (recommended, not built)</h2>
<ul>
<li><b>SIEM + EDR: Wazuh</b> (open source) on a new SRV-SIEM-01 in VLAN 60 (10.60.0.13): manager, indexer, dashboard.
Agents on every Ubuntu server give EDR functions: file integrity monitoring, rootkit checks, CIS configuration
assessment, vulnerability detection, active response. The log collector forwards everything to it, so Cisco and pfSense
logs are parsed too. Ports: 1514/TCP (agents), 1515/TCP (enrolment), 55000/TCP (API), 443 (dashboard, from VLAN 90).</li>
<li><b>IDS then IPS: Suricata on pfSense</b>, first in alert mode on WAN and DMZ (ET Open rules), alerts to syslog and
Wazuh; inline blocking once tuned.</li>
<li><b>Cheap first step that fits the host today:</b> Zabbix log items on the collector (agent in the SYSLOG container)
for the use cases below; no new VM needed.</li>
<li><b>Constraint:</b> Wazuh needs about 4 GB of RAM minimum; the host has about 0.5 GB free with the demo profile. It
needs a bigger host, or stopping simulators while it runs.</li>
</ul>
<h3>Detection use cases to implement first</h3>
{table(["Use case", "Source", "Logic", "Response"], [[f"<strong>{E(a)}</strong>", E(b), E(c), E(d)] for a, b, c, d in uc], ["19%", "28%", None, "22%"])}"""


def s_state():
    ws = [[E(w), f"{wt}", f"<b>{d} %</b>{bar(d, tone(d))}", E(ev)] for w, wt, d, ev in WORKSTREAMS]
    feats = [
        ("Active (running in the demo profile)", "ok", "BGP to ISP-A and ISP-B from EDGE-A, NAT and Internet access, firewall cluster with CARP + pfsync, all firewall rules, core HSRP/OSPF/RPVST+/LACP/ACLs, hall B leafs, DMZ web site with TLS, central syslog with a read-only viewer, Zabbix on 17 hosts, Grafana with read-only data source, BMS/DCIM simulators, admin webterm, lab proxy."),
        ("Configured and verified, off in the demo (memory)", "wip", "EDGE-B (second border router), LEAF-A1/A2 (hall A), SRV-INF-01 (DNS/NTP), SRV-BASTION (TOTP jump host), CCTV-SIM. They are in the Zabbix maintenance demo-off and start with the full profile."),
        ("Configured, not deployed", "todo", "SRV-CMP-01..03 (application + keepalived VIP), SRV-STO-01 (NFS/iSCSI): netplan and role scripts exist; the VMs were never installed (host RAM)."),
        ("Done (plan 04, profile nas)", "ok", "TrueNAS SRV-BCK-01: configured as code; nightly pulled backups and config backups; restore tested; supervised by Zabbix (pool, snapshot age, failed pulls)."),
        ("Done (plan 03 S5)", "ok", "Log server: every running source proven, 30-day rotation, protected files, read-only HTTPS viewer with login lock and audit trail, demo events found."),
        ("In progress", "wip", "Cold-start rehearsal and French demo runbook (plan 03 S6)."),
        ("Not configured (planned)", "bad", "Network triggers BGP/OSPF (ZBX.7), firewall LAN test when a core stops (FW.3), flow matrix (FW.4), measured failover T1-T6 and M1, NTP in every profile, HTTPS on Zabbix/Grafana."),
        ("Not in any plan yet", "bad", "SIEM, IDS/IPS, EDR, vulnerability scanning, secrets vault, central AAA, application load balancer, IPv6."),
    ]
    dev = []
    for n in EQUIP:
        if n in NOT_DEPLOYED:
            c, v = pill("Partial"), pill("Gap")
        else:
            c, v = pill("Done"), pill("Done")
        dev.append([f"<b>{n}</b>", c, v, node_state(n)])
    return f"""
{h1('state')}
<p>State on {DOC_DATE} (profile <code>nas</code> running for the TrueNAS work); "running" below refers to the demo profile (21 October
2026). Completion is weighted by the effort of each workstream of plans 01, 02 and 03.</p>
<div class="score">
  <div><b>{completion():.0f} %</b><span>overall completion of the planned work</span>{bar(completion(), tone(completion()))}</div>
  <div><b>{len(EQUIP) - len(NOT_DEPLOYED)} / {len(EQUIP)}</b><span>nodes configured and verified</span>{bar(100 * (len(EQUIP) - len(NOT_DEPLOYED)) / len(EQUIP), "ok")}</div>
  <div><b>{TESTS_PASSED}</b><span>dated tests passed (Test the Lab)</span>{bar(100 * TESTS_PASSED / (TESTS_PASSED + 2), "ok")}</div>
</div>
<h2>Completion by workstream</h2>
{table(["Workstream", "Weight", "Done", "Proof / what is left"], ws, ["31%", "7%", "13%", None])}
<h2>What is active, configured, missing</h2>
{table(["Level", "Items"], [[f'<span class="pill {c}">{E(l)}</span>', E(t)] for l, c, t in feats], ["24%", None])}
<h2>Node by node</h2>
{table(["Node", "Configured", "Verified", "State (demo profile)"], dev, ["22%", "18%", "18%", None])}"""


SCENARIOS = [  # (real-life scenario, what the lab does, detected by, verdict)
    ("Provider ISP-A goes down at noon", "BGP hold timer (9 s) expires, routes via ISP-B; inbound traffic follows because our prefix is still announced to ISP-B", "Zabbix interface/ICMP; BGP trigger planned (ZBX.7)", "Handled (target ≤ 10 s, not measured)"),
    ("FW-A crashes during business hours", "FW-B becomes CARP master with the same connection states: open sessions continue", "Zabbix host unavailable, CARP event in syslog", "Handled (target ≤ 5 s, not measured)"),
    ("A core switch is replaced (maintenance)", "CORE-B takes every gateway and STP root; LACP and leaf uplinks reroute", "Zabbix", "Handled; firewall LAN side to measure (FW.3)"),
    ("Utility power A is lost, UPS A fails", "Path B carries the load; disaster alarm in 6-10 s; the Grafana Énergie row turns red in under 10 s, green 5.5 s after the reset (S4)", "Zabbix triggers on BMS-SIM", "Handled and measured"),
    ("The public web site is hacked", "Attacker is stuck in the DMZ: only port 8443 of the app VIP and DNS/NTP are open; every other try is blocked and logged", "Firewall logs (manual search)", "Contained; detection needs a SIEM"),
    ("Ransomware on a compute server", "Can reach storage by NFS/iSCSI only and has no path to write or delete backups (pulled by the NAS); cannot reach management or admin zones", "Nothing automatic", "Partly contained; backups must be immutable, EDR missing"),
    ("An intern plugs a switch into a server port", "BPDU guard shuts the port at once", "Syslog %SPANTREE (manual)", "Handled"),
    ("Brute force on a core switch", "Blocked 120 s after 5 failures, logged", "Syslog (manual)", "Handled; alert needs a SIEM"),
    ("An admin laptop is stolen", "No access from outside the admin zone; bastion asks a TOTP code", "-", "Mostly handled; device logins have no MFA"),
    ("The DNS/NTP server dies", "Names and time stop for everyone: single server", "Zabbix agent unavailable", "Not handled: second server needed"),
    ("The monitoring server dies", "No alarms at all until it returns", "Nobody (no watcher of the watcher)", "Not handled: external heartbeat needed"),
    ("A critical CVE in nginx is published", "Nothing tells us; no scanner, no update process", "-", "Not handled"),
]


def s_scores():
    dom = [[f"<strong>{E(d)}</strong>", f"{w} %", f"<b>{n:.1f}</b>{bar(n * 20, tone(n * 20))}", f"{t:.1f}", E(s), E(g)]
           for d, w, n, t, s, g in SEC_DOMAINS]
    pr = [[E(p), E(l), pill(s)] for p, l, s in DC_PRACTICES]
    sc = [[f"<strong>{E(a)}</strong>", E(b), E(c), E(d)] for a, b, c, d in SCENARIOS]
    return f"""
{h1('scores')}
<h2>Method</h2>
<p>Ten security domains, weighted by their weight in a real data-center risk analysis. Each gets a score from 0 to
5 on evidence only (0 = nothing, 1 = idea, 2 = partial, 3 = in place, 4 = in place and verified, 5 = verified and
monitored). Score = Σ(weight × score) / 5. A second score checks the lab against {len(DC_PRACTICES)} practices that
any real Tier III / Rated-3 data center applies (met = 1, partial = 0.5, gap = 0).</p>
<div class="score">
  <div><b>{security_score():.0f} / 100</b><span>security score today: {grade(security_score())}</span>{bar(security_score(), tone(security_score()))}</div>
  <div><b>{security_score(3):.0f} / 100</b><span>after the roadmap ({ref('roadmap')})</span>{bar(security_score(3), tone(security_score(3)))}</div>
  <div><b>{conformity():.0f} %</b><span>conformity to real data-center practice</span>{bar(conformity(), tone(conformity()))}</div>
</div>
<h2>Security score by domain</h2>
{table(["Domain", "Weight", "Now /5", "Target /5", "Strengths", "Weaknesses"], dom, ["17%", "7%", "10%", "7%", None, "29%"])}
<p>Reading: the network design (segmentation, access, resilience) scores like a real site; the score is pulled down by
what a lab usually leaves out: detection, endpoint protection, patching and secrets. Those are exactly the domains an
auditor asks about first.</p>
<h2>Conformity to real data-center practice</h2>
{table(["Practice", "In the lab", "Status"], pr, ["36%", None, "9%"])}
<h2>Real-life scenarios</h2>
{table(["Scenario", "What the lab does", "Detected by", "Verdict"], sc, ["19%", None, "19%", "20%"])}"""


ROADMAP = [  # (horizon, action, why / control, effort)
    ("1. Finish the plans", "Cold-start rehearsal + runbook (S6)", "Demo-ready", "0.5 day"),
    ("1. Finish the plans", "FW.3 firewall LAN side when a core stops, FW.4 flow matrix, FW.5 evidence", "Policy proven end to end, A.8.22", "1 day"),
    ("1. Finish the plans", "ZBX.7 BGP/OSPF triggers and alert timing", "Network faults alarmed, A.8.16", "0.5 day"),
    ("1. Finish the plans", "Resilience campaign T1-T6 and M1, measured (resilience_tests.py)", "Rated-3 claim proven, A.8.14", "1 day"),
    ("1. Finish the plans", "Deploy SRV-CMP-01..03, SRV-STO-01 (needs RAM or a bigger host)", "Complete service chain, backups real", "1 day"),
    ("2. Quick security wins", "HTTPS on Zabbix and Grafana with an internal CA; SNMPv3 on pfSense", "Cryptography 2.5 → 4", "0.5 day"),
    ("2. Quick security wins", "NTP in every profile, NTP authentication, console exec-timeout", "Trustworthy logs, A.8.17", "2 h"),
    ("2. Quick security wins", "storm-control, DHCP snooping + DAI, config archive + log on change, AAA accounting", "Hardening 4 → 4.5", "0.5 day"),
    ("2. Quick security wins", "OSPF HMAC-SHA, BGP TTL-security; pin container image versions", "Stronger control plane, supply chain", "2 h"),
    ("2. Quick security wins", "SSH keys only, ufw on servers, secrets in an encrypted file (sops / Ansible Vault)", "Access 4 → 4.5, secrets 1.5 → 4", "0.5 day"),
    ("3. Detection", "Zabbix log items on the collector for the 8 use cases (fits today's host)", "First alerts on security events", "0.5 day"),
    ("3. Detection", "Wazuh SIEM + agents (EDR functions), Suricata IDS on pfSense", "Detection 2 → 4, endpoint 1 → 3.5", "2 days + host RAM"),
    ("3. Detection", "Vulnerability scan (Wazuh or OpenVAS) and a monthly patch window", "Vulnerability 0.5 → 3, A.8.8", "1 day"),
    ("4. Production grade", "Second DNS/NTP server, external heartbeat for monitoring, TACACS+ with MFA", "Remove single points of failure", "2 days"),
    ("4. Production grade", "HAProxy pair (keepalived) in the DMZ, WAF, provider DDoS service", "Load balancing and exposure protection", "2 days"),
    ("2. Production grade", "Second backup copy off site (TrueNAS replication to another site or cloud), immutable snapshots", "3-2-1 rule, ransomware, A.8.13", "1 day"),
    ("4. Production grade", "IPv6 dual stack, RPKI origin validation; spine-leaf EVPN-VXLAN if the site grows", "Real-world parity", "weeks"),
]


def s_roadmap():
    rows = [[f"<strong>{E(h)}</strong>", E(a), E(w), E(e)] for h, a, w, e in ROADMAP]
    return f"""
{h1('roadmap')}
<p>Ordered so that each step builds on the previous one: first finish and prove what is planned, then the cheap
security wins, then detection, then production-grade features. With the whole roadmap the security score goes from
<b>{security_score():.0f}</b> to about <b>{security_score(3):.0f} / 100</b>.</p>
{table(["Horizon", "Action", "What it brings", "Effort"], rows, ["15%", None, "28%", "10%"])}
<div class="box"><b class="t">Rule for every step</b>Change the inventory, regenerate, deploy (FW-B first for the
firewalls), audit, add the test to "Test the Lab", rebuild this report, one Git commit. A step is done only when its
test has passed and is dated.</div>"""


def appendix_interfaces():
    out = [h1("all_interfaces"),
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
    hygiene = ("<h2>Credential hygiene (state and target)</h2><ul>"
               "<li>All secrets live in <code>inventory/dc_casa.yaml</code> (private repository); pfSense exports are "
               "also kept redacted (<code>configs/pfsense/*.redacted.xml</code>).</li>"
               "<li>Default passwords replaced: Zabbix <code>Admin/zabbix</code>, Ubuntu <code>ubuntu</code> refused by "
               "SSH, Grafana admin set from the inventory.</li>"
               "<li>Not yet: rotation, one account per person on the network devices, a vault (sops / Ansible Vault), "
               "SSH keys instead of passwords. Before any real use, every secret here must be changed.</li></ul>")
    return (h1("credentials") +
            '<div class="box warn"><b class="t">Lab only</b>These secrets exist only in this lab and in its private '
            'repository (<code>inventory/dc_casa.yaml</code>). Never reuse them elsewhere.</div>'
            + table(["System", "Account", "Secret", "Note"], [[E(a), f"<code>{E(b)}</code>", f"<code>{E(c)}</code>", E(d)]
                                                               for a, b, c, d in rows], ["24%", "14%", "34%", None])
            + hygiene)


def appendix_glossary():
    g = [("2N / N+1", "Redundancy levels: 2N = a full second copy of everything; N+1 = one spare for N units."),
         ("AAA", "Authentication, authorisation, accounting: who you are, what you may do, what you did."),
         ("ACL", "Access control list: ordered permit/deny rules on a router or switch interface."),
         ("Active / standby", "One element works, its twin waits and takes over on failure."),
         ("Anti-spoofing", "Dropping packets whose source address cannot be genuine on that interface."),
         ("AS / ASN", "Autonomous system (number): a network under one routing policy; ours is AS 65100."),
         ("authPriv", "SNMPv3 security level with authentication (SHA) and encryption (AES)."),
         ("Bastion / jump host", "The single hardened server administrators go through to reach devices."),
         ("BGP / eBGP / iBGP", "Border Gateway Protocol, between ASes (eBGP) or inside one AS (iBGP)."),
         ("BMS / GTB", "Building management system: power, cooling, UPS, generator."),
         ("BPDU guard", "Shuts an access port that receives spanning-tree frames (a switch where a server should be)."),
         ("CARP", "Common Address Redundancy Protocol: a virtual IP shared by the two firewalls."),
         ("CIS benchmark", "Public hardening checklist per platform (Center for Internet Security)."),
         ("Collapsed core", "Two-tier design where the core also does distribution."),
         ("Concurrently maintainable", "Rated-3 property: any element can be taken down for maintenance without stopping the service."),
         ("CSP / HSTS", "Web security headers: allowed content sources / force HTTPS in the browser."),
         ("DAI / DHCP snooping", "Switch features that block forged ARP replies and rogue DHCP servers."),
         ("DCIM", "Data center infrastructure management: racks, power, temperatures."),
         ("Default deny", "Everything not explicitly allowed is blocked (and here, logged)."),
         ("Defence in depth", "Several independent layers of protection, so one failure is not a breach."),
         ("DMZ", "Demilitarised zone: network for services exposed to the Internet."),
         ("DNAT / SNAT / PAT", "Destination NAT (publish a server), source NAT (hide inside addresses), port address translation."),
         ("DTP", "Dynamic Trunking Protocol (Cisco): automatic trunk negotiation, disabled here."),
         ("East-west / north-south", "Traffic between servers inside the site / traffic in and out of the site."),
         ("EDR / XDR", "Endpoint detection and response: an agent that detects and stops attacks on a host."),
         ("ER / MDA / HDA / EDA", "TIA-942 spaces: entrance room, main / horizontal / equipment distribution areas."),
         ("EVPN-VXLAN", "Modern data-center fabric: L2 over an L3 spine-leaf, BGP control plane."),
         ("FHRP", "First-hop redundancy protocol (HSRP, VRRP, CARP): a gateway that survives a router loss."),
         ("FIM", "File integrity monitoring: alerts when system files change."),
         ("GTSM / TTL security", "Accept BGP packets only from a directly connected peer (TTL 255)."),
         ("HSRP", "Hot Standby Router Protocol (Cisco): a virtual gateway shared by two routers or switches."),
         ("IaC", "Infrastructure as code: configurations generated and versioned like software."),
         ("IDS / IPS", "Intrusion detection / prevention system: inspects traffic content for attacks."),
         ("ISO/IEC 27001 Annex A", "The 93 security controls of the 2022 standard (A.5 to A.8)."),
         ("keepalived / VRRP", "Linux daemon / standard protocol for a shared virtual IP."),
         ("LACP", "Link Aggregation Control Protocol (802.3ad): several links act as one."),
         ("lagg", "pfSense link aggregation; here in failover mode."),
         ("LLDP / CDP", "Neighbour discovery protocols (standard / Cisco)."),
         ("Local preference / AS-path prepend", "BGP knobs: choose the outbound exit / make an inbound path look longer."),
         ("Loopguard", "Stops a port from forwarding when spanning-tree frames stop arriving unexpectedly."),
         ("Max-prefix", "Shuts a BGP session if the peer sends too many routes (leak protection)."),
         ("MD5 / HMAC-SHA", "Hashes used to authenticate routing packets; MD5 is old, SHA preferred."),
         ("MFA / TOTP", "Multi-factor authentication / time-based 6-digit code (RFC 6238)."),
         ("NMS", "Network management system (here Zabbix)."),
         ("NOC", "Network operations center: the team and screen that watch the site."),
         ("NTP", "Network Time Protocol: same clock everywhere, required for logs and TOTP."),
         ("OOB", "Out-of-band management: a separate network used only to administer devices."),
         ("OSPF", "Open Shortest Path First: internal dynamic routing."),
         ("PAM", "Pluggable authentication modules (Linux); also privileged access management (product family)."),
         ("pfsync", "pfSense protocol that copies connection states to the peer firewall."),
         ("Portfast", "Server port goes forwarding at once, without spanning-tree delay."),
         ("PUE", "Power usage effectiveness: total power / IT power (1.0 is perfect)."),
         ("Rapid PVST+", "Rapid spanning tree, one instance per VLAN: prevents L2 loops, converges in about a second."),
         ("Rated-3 / Tier III", "TIA-942 / Uptime Institute level: redundant and concurrently maintainable."),
         ("RFC 5737", "Address ranges reserved for documentation (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24)."),
         ("RPKI", "Resource PKI: cryptographic check that an AS may announce a prefix."),
         ("SIEM", "Security information and event management: collects, correlates and alerts on logs."),
         ("SNMPv3", "Simple Network Management Protocol with users, authentication and encryption."),
         ("SOCKS5", "Generic proxy protocol; the lab proxy uses it to browse from ADMIN-WS."),
         ("Source of truth", "The one file all configurations come from: inventory/dc_casa.yaml."),
         ("SPOF", "Single point of failure."),
         ("Storm-control", "Limits broadcast/multicast floods on a switch port."),
         ("SVI", "Switch virtual interface (interface VlanX): the routed gateway of a VLAN on a switch."),
         ("Syslog", "Standard protocol to send log messages to a collector (UDP 514)."),
         ("TIA-942 / TIA-606", "Data center design standard / labelling standard used for names and descriptions."),
         ("Trunk / 802.1Q", "A link that carries several VLANs, each frame tagged with its VLAN number."),
         ("uRPF", "Unicast reverse path forwarding: drop packets whose source is not routed back via that port."),
         ("VIP", "Virtual IP: an address owned by whichever member of a pair is active."),
         ("VLAN", "Virtual LAN: a separate L2 network on shared switches."),
         ("VRF", "Virtual routing table: the management VRF keeps management traffic apart from data traffic."),
         ("VTP", "VLAN Trunking Protocol (Cisco); transparent mode = VLANs stay local."),
         ("WAF", "Web application firewall: filters HTTP requests for attacks (SQL injection, XSS)."),
         ("XMLRPC", "Channel pfSense uses to copy its configuration to the peer firewall."),
         ("Zabbix / Grafana", "Supervision server (collects, alarms) / dashboards (reads Zabbix)."),
         ("Zone", "Group of networks with the same trust level; crossings are filtered.")]
    keywords = ("TIA-942 Rated-3, 2N, concurrently maintainable, collapsed core, zone model, DMZ, OOB, VRF, 802.1Q, "
                "LACP, Rapid PVST+, BPDU guard, HSRP, CARP, pfsync, VRRP, OSPF, eBGP, iBGP, local preference, AS-path "
                "prepend, max-prefix, NAT, default deny, anti-spoofing, ACL, SSH v2, SNMPv3 authPriv, TLS 1.3, HSTS, "
                "TOTP, bastion, AAA, syslog, NTP, Zabbix, Grafana, DCIM, BMS, PUE, SIEM, EDR, IDS/IPS, infrastructure "
                "as code, source of truth, ISO/IEC 27001:2022")
    return (h1("glossary") + f'<div class="box"><b class="t">Keywords of this report</b>{E(keywords)}</div>' +
            table(["Term", "Meaning"], [[f"<strong>{E(a)}</strong>", E(b)] for a, b in g], ["22%", None]))


def main():
    style = re.search(r"<style>.*?</style>", (SRC / "lab_guide.html").read_text(encoding="utf-8"), re.S).group(0)
    style = style.replace("DC Casablanca - GNS3 Network Lab Guide", "DC Casablanca - Technical Report")
    style = style.replace("</style>", EXTRA_CSS + "</style>")
    parts = {"summary": s0_summary, "onboarding": s1_onboarding, "architecture": s2_architecture,
             "equipment": s_equipment, "addressing": s3_addressing, "cabling": s4_cabling, "interfaces": s5_interfaces,
             "protocols": s_protocols, "routing": s6_routing, "aggregation": s7_aggregation, "ha": s8_ha,
             "security": s9_security, "hardening": s_hardening, "flows": s10_flows, "services": s11_services,
             "supervision": s12_supervision, "access": s13_access, "iso": s14_iso, "state": s_state,
             "scores": s_scores, "roadmap": s_roadmap, "all_interfaces": appendix_interfaces,
             "cabling_plan": lambda: h1("cabling_plan") + cabling(), "credentials": appendix_credentials,
             "glossary": appendix_glossary}
    assert set(parts) == set(NUM), set(parts) ^ set(NUM)
    order = [k for k, *_ in SECTIONS] + [k for k, _ in APPENDICES]
    body = "".join([cover(), contents()] + [parts[k]() for k in order])
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
