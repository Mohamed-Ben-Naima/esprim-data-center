"""Build "The DC Casablanca Field Book": one searchable HTML page that explains the whole lab.

Sources (so the book never drifts from the lab): inventory/dc_casa.yaml (equipment, VLANs, scenarios),
report/tests/tests.yaml (every step-by-step test), report/content/*.md (French deep-dive chapters), plus the
hand-written story, design decisions and disaster scenarios below.
  python report/_source/build_lab_book.py   ->  report/DC_Casablanca_Field_Book.html
"""
import base64
import html
import json
import re
import sys
from pathlib import Path

import markdown
import yaml

NET = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(NET / "automation"))
from label_topology import notes  # noqa: E402

INV = yaml.safe_load((NET / "inventory/dc_casa.yaml").read_text(encoding="utf-8"))
TESTS = yaml.safe_load((NET / "report/tests/tests.yaml").read_text(encoding="utf-8"))["sections"]
E = html.escape
PROJ = json.loads((NET / "DC_Casablanca_TIA942_R3.gns3").read_text(encoding="utf-8"))["topology"]
OUTAGE = {"T2": 3.0, "T3": 4.5, "T4": 3.0, "T5": 3.1}
ICONS = {
    "edge": '<circle cx="8" cy="8" r="6.5"/><path d="M4 8h8M9 5l3 3-3 3"/>',
    "firewall": '<rect x="1.5" y="2.5" width="13" height="11"/><path d="M1.5 6.2h13M1.5 9.8h13M6 2.5v3.7M10 6.2v3.6M6 9.8v3.7"/>',
    "core": '<rect x="1.5" y="4" width="13" height="8" rx="1.5"/><path d="M4 8h8M10 6l2 2-2 2M6 6L4 8l2 2"/>',
    "leaf": '<rect x="1.5" y="5" width="13" height="6" rx="1.5"/><path d="M4 8h1M7 8h1M10 8h1"/>',
    "server": '<rect x="3" y="1.5" width="10" height="4"/><rect x="3" y="6" width="10" height="4"/><rect x="3" y="10.5" width="10" height="4"/>',
    "lab switch": '<rect x="1.5" y="5" width="13" height="6" rx="1.5"/><path d="M4 8h8"/>',
    "isp": '<path d="M4 12h8a3 3 0 0 0 0-6 4 4 0 0 0-7.7-1A3.5 3.5 0 0 0 4 12z"/>',
    "cloud": '<path d="M4 12h8a3 3 0 0 0 0-6 4 4 0 0 0-7.7-1A3.5 3.5 0 0 0 4 12z"/>',
    "admin": '<rect x="2" y="2.5" width="12" height="8" rx="1"/><path d="M5 13.5h6M8 10.5v3"/>',
}


def icon(kind):
    return (f'<svg class="ico" viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" '
            f'stroke-width="1.3">{ICONS.get(kind, ICONS["admin"])}</svg>')


def img(path, caption, cls="fig"):
    f = Path(path)
    if not f.exists():
        return ""
    b = base64.b64encode(f.read_bytes()).decode()
    return (f'<figure class="{cls}"><img src="data:image/png;base64,{b}" alt="{E(caption)}" loading="lazy">'
            f'<figcaption>{E(caption)}</figcaption></figure>')


def damage(t):
    sec = OUTAGE.get(t)
    if sec is None:
        return '<div class="hp"><span class="hpl">outage</span><span class="hpt">see target below</span></div>'
    w = sec / 10 * 100
    return (f'<div class="hp" title="{sec} s"><span class="hpl">outage</span>'
            f'<svg viewBox="0 0 100 10" preserveAspectRatio="none">'
            f'<rect width="100" height="10" rx="2" fill="var(--code)"/>'
            f'<rect width="{w:.1f}" height="10" rx="2" fill="var(--warn)"/></svg>'
            f'<span class="hpt">{sec} s out of 10</span></div>')

TIERS = [
    ("Internet", "The outside world. Two simulated providers, each with a real Internet exit through a GNS3 NAT cloud.",
     ["NAT-A", "NAT-B", "ISP-A", "ISP-B"]),
    ("Entrance Room (ER)", "Where the providers' cables enter the building. Two edge routers speak BGP with the ISPs.",
     ["EDGE-A", "EDGE-B", "SW-OUT"]),
    ("Main Distribution Area: security", "The pfSense firewall pair. Every packet between zones crosses it.",
     ["FW-A", "FW-B", "SW-IN", "SW-DMZ", "SRV-WEB-01"]),
    ("Main Distribution Area: core", "Two L3 core switches: the default gateways of the internal VLANs.",
     ["CORE-A", "CORE-B"]),
    ("Hall A (HDA-A / EDA-A)", "Compute and storage. Every server is cabled to both leafs.",
     ["LEAF-A1", "LEAF-A2", "SRV-CMP-01", "SRV-CMP-02", "SRV-CMP-03", "SRV-STO-01"]),
    ("Hall B (HDA-B / EDA-B)", "Backup, internal services, supervision, logs, building systems.",
     ["LEAF-B1", "LEAF-B2", "SRV-BCK-01", "SRV-INF-01", "SRV-MON-01", "SYSLOG", "SRV-DCIM-01", "BMS-SIM", "CCTV-SIM"]),
    ("Out-of-band management", "A separate network to administer everything, even when production is broken.",
     ["SW-MGMT", "ADMIN-WS", "SRV-BASTION"]),
]

# boss fights: (id, name, what breaks, defence, measured result, test id to replay)
BOSSES = [
    ("T1", "The Provider Blackout", "ISP-A (the preferred provider) goes dark.",
     "Two providers over eBGP. ISP-A routes get local-preference 200 so it is preferred; when its session dies (BGP "
     "timers 3/9 s) the edges fall back to ISP-B. HSRP on the edges keeps the firewalls' next hop (10.254.1.6) alive.",
     "Target: " + INV["tests"]["T1"]["target"], "EDGE"),
    ("T2", "The Firewall Falls", "FW-A, the master firewall, stops.",
     "CARP: FW-B listens to FW-A's adverts (advskew 0 vs 100). Silence means FW-B takes the 5 virtual IPs. pfsync has "
     "already copied the state table, so open sessions survive.",
     "Measured: 3.0 s outage, 1.5 s when FW-A takes back.", "FW"),
    ("T3", "The Core Meltdown", "CORE-A, gateway of VLANs 20/40/60/100, dies (or hangs with its link up).",
     "HSRP per VLAN moves the gateway to CORE-B. On the firewall side, SW-IN puts both cores and both firewalls on "
     "one VLAN 902 segment so a hung core is bypassed even when its cable still looks up.",
     "Measured: 4.5 s (was 150 s or more before SW-IN).", "CORE"),
    ("T4", "The Leaf Collapse", "LEAF-A1, one of the two access switches of hall A, stops.",
     "Every server is bonded to LEAF-A1 and LEAF-A2 (active-backup). ARP monitoring every 1 s detects even a hung "
     "switch, then the bond moves to the second NIC.",
     "Measured: one 3.0 s outage, 0 lost when the leaf comes back.", "CMP"),
    ("T5", "The Server Dies", "SRV-CMP-01, the server holding the application address, stops.",
     "keepalived (VRRP) between SRV-CMP-01 and SRV-CMP-02: the backup takes the VIP 10.20.0.10. preempt_delay 30 s "
     "stops the master from grabbing it back before it is really ready.",
     "Measured: 3.1 s outage, failback 0 loss, backup reboot 0 loss.", "CMP"),
    ("T6", "The Power Cut", "The building's power feed fails (simulated by BMS-SIM).",
     "The BMS simulator raises the alarm, supervision picks it up and the runbook tells you what shuts down first.",
     "Target: " + INV["tests"]["T6"]["target"], "PWR"),
]

# why this, not that: (decision, rejected alternative, reason)
WHY = [
    ("Two pfSense firewalls in CARP + pfsync", "One firewall",
     "One box is a single point of failure for every flow. With pfsync even TCP sessions survive the switch."),
    ("HSRP active split per VLAN (CORE-A: 20/40/60/100, CORE-B: 30/70/80)", "Everything active on CORE-A",
     "Both cores work all the time. Spanning-tree roots follow the HSRP active core, so traffic never takes a detour."),
    ("SW-IN shared segment for VLAN 902", "Direct firewall-to-core cables with lagg0 failover",
     "A core can hang while its link stays up. lagg0 only watches the link, so the firewalls kept sending into a dead "
     "core for 150 s or more. On a shared segment the CARP and HSRP protocols decide instead: 4.5 s."),
    ("Bond active-backup with ARP monitoring", "Bond watching only the link (MII)",
     "MII sees a cut cable, not a frozen switch. ARP probes to the gateways check that the path really answers."),
    ("keepalived with preempt_delay 30 s", "Immediate preempt",
     "A rebooting master would steal the VIP before its application is ready, causing a second outage."),
    ("Out-of-band management in a VRF (VLAN 10)", "Managing devices over the production VLANs",
     "When production breaks you still reach every device. 10.10.0.0/24 is not even in the global routing table."),
    ("Bastion with password + TOTP, personal sysadmin accounts", "Shared ubuntu/ubuntu logins",
     "Every session has a name and a second factor (ISO/IEC 27001 A.8.5). ubuntu only works on the console."),
    ("Every config generated from one inventory", "Hand-typed configs",
     "One source of truth: gen_configs.py and gen_pfsense.py build the configs, fw_audit.py proves 0 difference."),
    ("Default deny, and every refusal logged", "Allow by default, block the bad",
     "Only declared flows pass. Each denied flow lands in the central log, so you can trace any refusal."),
    ("Backups pulled by TrueNAS", "Servers pushing their own backups",
     "A compromised server holds no credentials to the NAS, so it cannot wipe its own backups."),
    ("SNMPv3 (auth + priv)", "SNMPv2c community strings",
     "v2c sends its password in clear text. v3 authenticates and encrypts."),
    ("Secrets sent through stdin, never on the SSH command line", "Passwords as command arguments",
     "The admin workstation logs every command line to syslog. Learned the hard way in FW.4, secrets rotated since."),
]

LIMITS = [
    "IOSvL2 clocks run at about 55-60 % of real time: Cisco timer values in the lab are not the real-world ones.",
    "ADMIN-WS shows Morocco as +00 and SYSLOG as +01 (different tzdata versions). Documented, not fixed.",
    "Measured failovers (3 s) are slower than real hardware because the switches are emulated.",
]


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def tests_for(name):
    out = []
    for sec in TESTS:
        for t in sec["tests"]:
            blob = " ".join(str(t.get(k, "")) for k in ("from", "command", "proves"))
            if re.search(rf"\b{re.escape(name)}\b", blob, re.I):
                out.append(t["id"])
    return out


def kind_of(name):
    if name in INV["devices"]:
        return INV["devices"][name]["role"]
    if name in INV["servers"]:
        return "server"
    if name in INV["lab_switches"]:
        return "lab switch"
    if name in INV["isps"]:
        return "isp"
    if name in INV["internet_uplinks"]:
        return "cloud"
    return "admin"


def card(name, lines):
    tid = tests_for(name)
    links = " ".join(f'<a class="tid" href="#t-{slug(t)}">{E(t)}</a>' for t in tid[:14]) or "<em>no dedicated test</em>"
    body = "".join(f"<li>{E(l)}</li>" for l in lines)
    return (f'<article class="card entry" id="n-{slug(name)}" data-title="{E(name)}">'
            f'<header>{icon(kind_of(name))}<span class="tag">{E(kind_of(name))}</span><h4>{E(name)}</h4></header>'
            f'<ul>{body}</ul><p class="explore"><b>Explore it:</b> {links}</p></article>')


def build():
    N = notes()
    toc, parts = [], []

    def chapter(cid, title, inner, kicker=""):
        toc.append((cid, title))
        parts.append(f'<section class="chapter" id="{cid}"><p class="kicker">{E(kicker)}</p>'
                     f'<h2>{E(title)}</h2>{inner}</section>')

    s = INV["site"]
    chapter("start", "Welcome to the data center", f"""
<div class="entry" data-title="What is this project">
<p class="lead">This book is the guide to <b>{E(s['name'])}</b>: a full Tier-style data center for Casablanca, built
inside GNS3 on one laptop. It has {len(N)} nodes on the canvas: real Cisco IOS images, two pfSense firewalls,
Ubuntu servers, a TrueNAS backup box and Docker services. It is laid out following the <b>TIA-942</b> data center
standard and run according to <b>ISO/IEC 27001</b>.</p>
<p>The goal in one sentence: <b>any single piece of equipment can die and the service keeps answering within a few
seconds</b>, while every access is named, every flow is declared and every refusal is logged.</p>
<p>Use the search box (press <kbd>/</kbd>) to find any device, IP, VLAN, protocol or test. Every equipment card links
to the tests that let you poke it yourself.</p></div>
<div class="grid3">
<div class="stat"><b>{len(N)}</b><span>nodes on the canvas</span></div>
<div class="stat"><b>{len([v for v in INV['vlans'] if INV['vlans'][v].get('subnet')])}</b><span>VLANs with a subnet</span></div>
<div class="stat"><b>{sum(len(x['tests']) for x in TESTS)}</b><span>step-by-step tests</span></div>
</div>
<div class="entry" data-title="TIA-942 zones explained"><h3>How to read the building (TIA-942)</h3>
<dl class="dl">
<dt>ER, Entrance Room</dt><dd>where the providers' cables come in: the edge routers.</dd>
<dt>MDA, Main Distribution Area</dt><dd>the heart: firewalls and core switches.</dd>
<dt>HDA, Horizontal Distribution Area</dt><dd>one per hall: the leaf (access) switches.</dd>
<dt>EDA, Equipment Distribution Area</dt><dd>the racks with the servers.</dd></dl></div>""", "Chapter 0")

    tiers = ""
    for title, blurb, names in TIERS:
        cards = "".join(card(n, N.get(n, ["(no description)"])) for n in names)
        tiers += f'<h3 id="z-{slug(title)}">{E(title)}</h3><p class="blurb">{E(blurb)}</p><div class="cards">{cards}</div>'
    chapter("map", "The map, tier by tier", f"""
<p class="lead">A packet from the Internet travels top to bottom: provider, edge router, firewall, core, leaf, server.
Each tier has an A and a B twin. That symmetry is the whole HA story.</p>
{img(NET / "report/_source/topology_book.png", "The live GNS3 canvas: zones from Internet (top) to the halls (bottom)", "fig wide")}
<pre class="flow">Internet ─ ISP-A / ISP-B ─ EDGE-A / EDGE-B ─[VLAN 901 SW-OUT]─ FW-A / FW-B ─[VLAN 902 SW-IN]─ CORE-A / CORE-B
                                                         │                                  │
                                                 SW-DMZ (VLAN 50)              LEAF-A1/A2 (hall A)  LEAF-B1/B2 (hall B)
                                                   SRV-WEB-01                        servers, each bonded to 2 leafs</pre>
{tiers}""", "Chapter 1: Equipment encyclopedia")

    rows = "".join(
        f'<tr class="entry" data-title="VLAN {v} {E(x["name"])}"><td class="num">{v}</td><td><b>{E(x["name"])}</b></td>'
        f'<td class="mono">{E(x.get("subnet") or "-")}</td><td class="mono">{E(str(x.get("vip", "-")))}</td>'
        f'<td>{E(x["gw_type"])}{(" (" + x["active"] + ")") if x.get("active") else ""}</td><td>{E(x["zone"])}</td>'
        f'<td>{E(x["purpose"])}</td></tr>' for v, x in INV["vlans"].items())
    chapter("vlans", "VLANs and addressing", f"""
<p class="lead">Every function lives in its own VLAN, and the VLAN tells you where its gateway is: <b>core</b> = HSRP
on the two core switches (the active one is in brackets), <b>fw</b> = CARP on the firewalls, so the traffic is
filtered.</p>
<div class="tablewrap"><table><thead><tr><th>VLAN</th><th>Name</th><th>Subnet</th><th>Gateway VIP</th><th>Gateway</th>
<th>Zone</th><th>Purpose</th></tr></thead><tbody>{rows}</tbody></table></div>""", "Chapter 2")

    PW = {"admin": "admin_password", "Admin": "zabbix_admin_password", "truenas_admin": "truenas_admin_password",
          "netadmin": "admin_password"}

    def pw_for(w):
        if not w.get("login"):
            return ""
        return "grafana_admin_password" if "Grafana" in w["name"] else PW.get(w["login"], "")
    wrows = "".join(
        f'<tr class="entry" data-title="{E(w["name"])} {E(w["url"])}"><td><b>{E(w["name"])}</b><br><span class="muted">'
        f'{E(w["node"])}</span></td><td class="mono">{E(w["url"])}</td><td class="mono">{E(w.get("login") or "none")}</td>'
        f'<td class="mono">{E(pw_for(w) or "-")}</td><td>{E(w["descr"])}</td></tr>' for w in INV["web_interfaces"])
    crow = "".join(
        f'<tr class="entry" data-title="console {E(n["name"])}"><td><b>{E(n["name"])}</b></td>'
        f'<td>{E(str(n.get("console_type") or "-"))}</td><td class="num">{E(str(n.get("console") or "-"))}</td>'
        f'<td class="num">{E(str((n.get("properties") or {}).get("aux") or "-"))}</td></tr>'
        for n in sorted(PROJ["nodes"], key=lambda n: n["name"]) if n.get("console"))
    C = INV["credentials"]
    chapter("access", "How to get in: the access cheat sheet", f"""
<p class="lead">All administration goes through <b>ADMIN-WS</b>, the admin workstation in VLAN 90. Open its desktop
(VNC console of ADMIN-WS in GNS3), then use its Firefox (start page = portal with every link) or its terminal.
From the Windows host you can also browse through the lab proxy: run <code>python automation/lab_proxy.py start</code>
and set the SOCKS5 proxy <code>192.168.75.128:1080</code> in the browser.</p>
<div class="callout entry" data-title="where are the passwords"><b>Passwords are never printed in this book.</b>
Each one sits in <code>inventory/dc_casa.yaml</code>, section <code>credentials</code>, under the key shown in the
table. The bastion also asks for a TOTP code: <code>python automation/totp.py</code>.</div>
<h3>Web interfaces</h3>
<div class="tablewrap"><table><thead><tr><th>Service</th><th>URL (from ADMIN-WS)</th><th>Login</th>
<th>Password key</th><th>What you see</th></tr></thead><tbody>{wrows}</tbody></table></div>
{img(NET / "screenshots/20_admin-ws_portal.png", "The ADMIN-WS portal: one click per web interface")}
<h3>SSH to any equipment</h3>
<div class="entry" data-title="ssh accounts aliases"><p>In the ADMIN-WS terminal type <code>ssh &lt;name&gt;</code>
with the device name in lower case (for example <code>ssh core-a</code>, <code>ssh fw-b</code>,
<code>ssh srv-cmp-01</code>). Every session start and end is logged on SYSLOG with the tag <code>admin-ssh</code>.</p>
<div class="tablewrap"><table><thead><tr><th>Equipment</th><th>Account</th><th>Password key</th></tr></thead><tbody>
<tr><td>Cisco routers and switches</td><td class="mono">{E(C["admin_user"])}</td><td class="mono">admin_password (enable: enable_secret)</td></tr>
<tr><td>pfSense FW-A / FW-B</td><td class="mono">admin</td><td class="mono">admin_password</td></tr>
<tr><td>Ubuntu servers</td><td class="mono">{E(C["server_admin_user"])}</td><td class="mono">server_admin_password (ubuntu works on the console only)</td></tr>
<tr><td>SRV-BASTION</td><td class="mono">{E(C["server_admin_user"])}</td><td class="mono">server_admin_password + TOTP code</td></tr>
<tr><td>TrueNAS SRV-BCK-01</td><td class="mono">truenas_admin</td><td class="mono">truenas_admin_password</td></tr>
</tbody></table></div>
<p>From the Windows host, without opening the desktop:
<code>python automation/adminws.py core-a "show standby brief"</code>.</p></div>
<h3>Console ports (GNS3 VM 192.168.75.128)</h3>
<p>The console works even when the network is down: <code>telnet 192.168.75.128 &lt;port&gt;</code> or a double-click
in GNS3. On Docker nodes use the aux port: on the main console, Ctrl-C stops the service.</p>
<div class="tablewrap"><table><thead><tr><th>Node</th><th>Type</th><th>Console</th><th>Aux</th></tr></thead>
<tbody>{crow}</tbody></table></div>
""", "Chapter 3")

    boss = "".join(f"""<article class="boss entry" id="b-{t.lower()}" data-title="{t} {E(n)}">
<div class="bhead"><span class="bid">{t}</span><h3>{E(n)}</h3></div>{damage(t)}
<p><b>The attack:</b> {E(a)}</p><p><b>The defence:</b> {E(d)}</p>
<p class="score">{E(r)}</p><p class="explore">Replay it: section <a href="#s-{slug(sec)}">{E(sec)}</a></p></article>"""
                   for t, n, a, d, r, sec in BOSSES)
    chapter("bosses", "Boss fights: what we survive", f"""
<p class="lead">High availability means planning how things fail. Each scenario below was actually triggered in the
lab: a node is killed through the GNS3 API while a probe hits the service every 0.5 s, and the outage is
measured.</p><div class="bosses">{boss}</div>""", "Chapter 4: Resilience scenarios")

    why = "".join(f"""<article class="why entry" data-title="{E(d)}"><h4>{E(d)}</h4>
<p class="vs">instead of <s>{E(alt)}</s></p><p>{E(r)}</p></article>""" for d, alt, r in WHY)
    lim = "".join(f'<li class="entry" data-title="lab limit">{E(l)}</li>' for l in LIMITS)
    chapter("why", "Why it is built this way", f"""
<p class="lead">For each choice, the option we rejected and the reason.</p><div class="whys">{why}</div>
<h3>Known lab limits (no secrets kept)</h3><ul class="limits">{lim}</ul>""", "Chapter 5: Design decisions")

    seen, gal = set(), ""
    for f in sorted((NET / "report/content").glob("[0-9]*.md")):
        for alt, path in re.findall(r"!\[([^\]]*)\]\(\.\./([^)]*)\)", f.read_text(encoding="utf-8")):
            if path in seen or "boot_hang" in path:
                continue
            seen.add(path)
            gal += img(NET / path, alt, "fig entry")
    chapter("gallery", "The lab in pictures", f"""
<p class="lead">Real screenshots taken in the running lab: consoles, the firewall web interface, the admin portal.</p>
<div class="gallery">{gal}</div>""", "Chapter 6")

    tsec = ""
    for sec in TESTS:
        items = ""
        for t in sec["tests"]:
            ver = t.get("verified")
            items += f"""<li class="step entry" id="t-{slug(t['id'])}" data-title="{E(t['id'])} {E(t.get('proves', ''))}">
<div class="sh"><span class="tid">{E(t['id'])}</span><b>{E(t.get('proves', ''))}</b>
<span class="ver {'ok' if ver else 'no'}">{'verified ' + E(str(ver)) if ver else 'not run yet'}</span></div>
<p><span class="lbl">From</span> {E(str(t.get('from', '')))}</p>
<pre class="cmd"><button class="copy" type="button">copy</button><code>{E(str(t.get('command', '')))}</code></pre>
<p><span class="lbl">Expect</span> {E(str(t.get('expected', '')))}</p></li>"""
        tsec += (f'<div class="tsec" id="s-{slug(sec["id"])}"><h3>{E(sec["id"])}: {E(sec["title"])}</h3>'
                 f'<p class="needs"><b>Needs running:</b> {E(str(sec.get("needs", "")))}</p><ol>{items}</ol></div>')
    chapter("tests", "Test the lab yourself", f"""
<p class="lead">Every test says where to stand, what to type and what you should see. Start the lab with
<code>python automation/lab_up.py --profile demo</code>, check it with <code>python automation/demo_check.py</code>,
then explore. Run everything at once with <code>python automation/verify_lab.py</code>.</p>{tsec}""",
            "Chapter 7: Step-by-step guide")

    deep = ""
    for f in sorted((NET / "report/content").glob("[0-9]*.md")):
        txt = f.read_text(encoding="utf-8")
        txt = re.sub(r"!\[([^\]]*)\]\(\.\./([^)]*)\)(\{[^}]*\})?",
                     lambda m: "\n\n" + img(NET / m.group(2), m.group(1)) + "\n\n", txt)
        txt = re.sub(r"^Table: (.*)$", r"**\1**\n", txt, flags=re.M)
        txt = re.sub(r"```(\w+)[^\n]*\n", "```\n", txt)
        h = markdown.markdown(txt, extensions=["tables", "fenced_code"])
        h = re.sub(r"<h1>", "<h3>", h).replace("</h1>", "</h3>")
        h = re.sub(r"<h([2-4])>", lambda m: f"<h{int(m.group(1)) + 2}>", h)
        h = re.sub(r"</h([2-4])>", lambda m: f"</h{int(m.group(1)) + 2}>", h)
        h = h.replace("<table>", '<div class="tablewrap"><table>').replace("</table>", "</table></div>")
        title = (re.search(r"^# (.+)$", txt, re.M) or [None, f.stem])[1]
        deep += (f'<details class="deep entry" id="d-{slug(f.stem)}" data-title="{E(title)}">'
                 f'<summary>{E(title)}</summary><div class="md" lang="fr">{h}</div></details>')
    chapter("deep", "Deep dive: the full technical report (French)", f"""
<p class="lead">The full network report, chapter by chapter. Click a chapter to open it. The search covers these
too.</p>{deep}""", "Chapter 8")

    man = json.loads((NET / "images/manifest.json").read_text(encoding="utf-8"))
    irows = "".join(
        f'<tr class="entry" data-title="image {E(r["file"])}"><td class="mono">images/{E(r["file"])}</td>'
        f'<td class="num">{(r["size"] or 0) / 1048576:,.0f} MB</td><td>{E(r["used_by"])}</td><td>{E(r["what"])}</td>'
        f'<td>{E(r["licence"])}</td></tr>' for r in man["images"])
    drows = "".join(f'<tr class="entry" data-title="docker {E(d["image"])}"><td class="mono">{E(d["image"])}</td>'
                    f'<td>{E(d["used_by"])}</td></tr>' for d in man["docker"])
    chapter("images", "The images behind every node", f"""
<p class="lead">Each node boots from an image. They are all kept on the external USB disk in <code>H:/DC-Casablanca-images/</code>
(cisco, iso, qemu), with size and SHA-256 in <code>03_Network/images/manifest.json</code>. A zipped copy is on GitHub in <code>03_Network/images/archives/</code> (Git LFS, TrueNAS split in two parts): <code>git lfs pull --include "03_Network/images/archives/*"</code> then <code>python automation/pack_images.py --unpack</code>. They are not in git: too big, and the Cisco licence forbids
publishing them. <code>python automation/collect_images.py --verify</code> checks them.</p>
<div class="tablewrap"><table><thead><tr><th>File</th><th>Size</th><th>Used by</th><th>What</th><th>Licence</th></tr>
</thead><tbody>{irows}</tbody></table></div>
<h3>Container images (rebuilt from <code>docker/</code>)</h3>
<div class="tablewrap"><table><thead><tr><th>Image</th><th>Used by</th></tr></thead><tbody>{drows}</tbody></table></div>
""", "Appendix")

    nav = "".join(f'<a href="#{c}">{E(t)}</a>' for c, t in toc)
    page = TEMPLATE.replace("%NAV%", nav).replace("%BODY%", "".join(parts))
    out = NET / "report/DC_Casablanca_Field_Book.html"
    out.write_text(page, encoding="utf-8")
    print(f"{out} ({out.stat().st_size // 1024} KB)")
    toc_print = "".join(f'<li><a href="#{c}">{E(t)}</a></li>' for c, t in toc)
    cover = (f'<section class="cover"><p class="kicker">GNS3 lab - TIA-942 - ISO/IEC 27001</p>'
             f'<h1>DC Casablanca<br><span>Field Book</span></h1>'
             f'{img(NET / "report/_source/topology_book.png", "The lab on one page", "fig")}<p class="lead">Everything about the lab: equipment, '
             f'VLANs, resilience scenarios, design decisions and every step-by-step test.</p>'
             f'<h3>Contents</h3><ol class="ptoc">{toc_print}</ol></section>')
    pp = ('<!doctype html><html lang="en" data-theme="light"><head><meta charset="utf-8">'
          + page.replace('<details class="deep entry"', '<details open class="deep entry"')
          .replace("<main>", "<main>" + cover) + PRINT_CSS + "</html>")
    pout = NET / "report/_source/field_book_print.html"
    pout.write_text(pp, encoding="utf-8")
    import subprocess
    pdf = NET / "report/DC_Casablanca_Field_Book.pdf"
    edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    subprocess.run([edge, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=15000",
                    f"--print-to-pdf={pdf}", pout.as_uri()], check=True, capture_output=True)
    print(f"{pdf} ({pdf.stat().st_size // 1024} KB)")


TEMPLATE = r"""<title>DC Casablanca Field Book</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;700;800&family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono:wght@400;600&display=swap">
<style>
/* layout: rack-room field manual. sticky index rail on the left, cable-tag colours mark kinds of things */
:root{--bg:#f3f5f4;--panel:#ffffff;--fg:#17201d;--muted:#5b6964;--line:#d5dcd9;--accent:#0f7b6c;--warn:#b5482c;
--tag:#e3efe9;--code:#eaefed;--hl:#ffe58a;
--display:"Archivo",system-ui,sans-serif;--body:"IBM Plex Sans",system-ui,sans-serif;--mono:"IBM Plex Mono",ui-monospace,Consolas,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f1513;--panel:#161e1b;--fg:#e4ebe8;--muted:#93a39d;
--line:#2a3532;--accent:#35c2a8;--warn:#f08a6a;--tag:#1d2b27;--code:#1b2421;--hl:#6b5a12;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0f1513;--panel:#161e1b;--fg:#e4ebe8;--muted:#93a39d;--line:#2a3532;--accent:#35c2a8;
--warn:#f08a6a;--tag:#1d2b27;--code:#1b2421;--hl:#6b5a12;color-scheme:dark}
body{background:var(--bg);color:var(--fg);font:15px/1.6 var(--body)}
.wrap{display:grid;grid-template-columns:250px minmax(0,1fr);gap:32px;max-width:1240px;margin:0 auto;
padding-block:24px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
aside{position:sticky;top:env(safe-area-inset-top,0px);align-self:start;max-height:100vh;overflow:auto;padding-block:8px}
.brand{font:800 22px/1.1 var(--display);letter-spacing:-.01em;margin:0 0 4px}
.brand span{color:var(--accent)}
.sub{color:var(--muted);font-size:13px;margin:0 0 16px}
#q{width:100%;box-sizing:border-box;padding:10px 12px;border:1.5px solid var(--line);border-radius:8px;background:var(--panel);
color:var(--fg);font:15px var(--body)}
#q:focus{outline:none;border-color:var(--accent)}
nav{display:flex;flex-direction:column;gap:2px;margin-top:16px}
nav a{color:var(--fg);text-decoration:none;padding:6px 10px;border-radius:6px;font-size:14px}
nav a:hover,nav a:focus-visible{background:var(--tag)}
#results{margin-top:10px;display:flex;flex-direction:column;gap:2px;font-size:13px}
#results a{color:var(--fg);text-decoration:none;padding:5px 8px;border-left:3px solid var(--accent);background:var(--panel)}
#results .none{color:var(--muted)}
main{min-width:0}
.chapter{padding-block:8px 40px;border-bottom:1px solid var(--line)}
.kicker{font:600 12px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--accent);margin:24px 0 4px}
h2{font:800 34px/1.1 var(--display);letter-spacing:-.02em;margin:0 0 16px;text-wrap:balance}
h3{font:700 21px/1.25 var(--display);margin:28px 0 8px;text-wrap:balance}
h4{font:700 16px/1.3 var(--display);margin:0}
.lead{font-size:17px;max-width:68ch}
p,li,dd{max-width:72ch}
.blurb{color:var(--muted);margin-top:0}
code,kbd,.mono{font-family:var(--mono);font-size:.9em}
kbd{border:1px solid var(--line);border-bottom-width:2px;border-radius:4px;padding:0 5px;background:var(--panel)}
.grid3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-block:20px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.stat b{display:block;font:800 32px/1 var(--display);color:var(--accent);font-variant-numeric:tabular-nums}
.stat span{color:var(--muted);font-size:13px}
.dl{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:6px 16px}
.dl dt{font-weight:600}.dl dd{margin:0}
.flow{overflow-x:auto;background:var(--code);padding:14px;border-radius:8px;font:12.5px/1.5 var(--mono)}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px;min-width:0}
.card header{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.tag{font:600 10.5px var(--mono);text-transform:uppercase;letter-spacing:.06em;background:var(--tag);color:var(--accent);
padding:2px 7px;border-radius:3px;clip-path:polygon(0 0,100% 0,92% 50%,100% 100%,0 100%)}
.card ul{margin:0;padding-left:18px;font-size:13.5px}
.explore{font-size:13px;margin:8px 0 0;color:var(--muted)}
a.tid,.tid{font:600 12px var(--mono);color:var(--accent);text-decoration:none;margin-right:4px}
.tablewrap{overflow-x:auto;margin-block:12px}
table{border-collapse:collapse;font-size:13.5px;width:100%}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{font:600 12px var(--mono);text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
td.num{font-variant-numeric:tabular-nums;font-weight:700}
.bosses{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}
.boss{background:var(--panel);border:1px solid var(--line);border-top:4px solid var(--warn);border-radius:10px;padding:14px 16px;min-width:0}
.bhead{display:flex;align-items:center;gap:10px}
.bhead h3{margin:0;font-size:18px}
.bid{font:800 13px var(--mono);color:var(--panel);background:var(--warn);padding:3px 8px;border-radius:4px}
.score{font-weight:600;color:var(--accent);border-top:1px dashed var(--line);padding-top:8px}
.whys{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.why{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px;min-width:0}
.vs{color:var(--muted);font-size:13px;margin:4px 0}
.limits li{margin-bottom:4px}
.tsec{margin-top:8px}
.needs{color:var(--muted);font-size:13.5px}
.tsec ol{list-style:none;padding:0;display:flex;flex-direction:column;gap:10px}
.step{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px;min-width:0}
.step p{margin:4px 0;font-size:14px}
.sh{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline}
.ver{margin-left:auto;font:600 11px var(--mono);padding:1px 7px;border-radius:10px}
.ver.ok{background:var(--tag);color:var(--accent)}.ver.no{background:var(--code);color:var(--warn)}
.lbl{font:600 11px var(--mono);text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-right:6px}
.cmd{position:relative;background:var(--code);border-radius:6px;padding:10px 60px 10px 12px;overflow-x:auto;margin:6px 0;
font:13px/1.45 var(--mono);white-space:pre-wrap;word-break:break-word}
.copy{position:absolute;top:6px;right:6px;font:600 11px var(--mono);border:1px solid var(--line);background:var(--panel);
color:var(--fg);border-radius:4px;padding:2px 8px;cursor:pointer}
.copy:focus-visible,nav a:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.deep{background:var(--panel);border:1px solid var(--line);border-radius:10px;margin-bottom:8px}
.deep summary{cursor:pointer;padding:12px 16px;font:700 16px var(--display)}
.md{padding:0 16px 16px;min-width:0}
.md pre{background:var(--code);padding:10px;border-radius:6px;overflow-x:auto;font-size:12.5px}
.ico{width:18px;height:18px;color:var(--accent);flex:none}
.muted{color:var(--muted);font-size:12px}
.fig{margin:14px 0;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px}
.fig img{display:block;width:100%;height:auto;border-radius:6px}
.fig figcaption{font-size:12.5px;color:var(--muted);padding:6px 4px 0}
.gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}
.gallery .fig{margin:0}
.hp{display:flex;align-items:center;gap:8px;margin:8px 0}
.hp svg{flex:1;height:12px;min-width:60px}
.hpl{font:600 10.5px var(--mono);text-transform:uppercase;color:var(--muted)}
.hpt{font:600 12px var(--mono);color:var(--warn);white-space:nowrap}
.callout{border-left:4px solid var(--accent);background:var(--tag);padding:10px 14px;border-radius:0 8px 8px 0;margin:12px 0}
.entry.hit{outline:3px solid var(--hl);outline-offset:2px}
mark{background:var(--hl);color:inherit}
@media (max-width:860px){.wrap{grid-template-columns:minmax(0,1fr)}aside{position:static;max-height:none}
nav{flex-direction:row;flex-wrap:wrap}.grid3{grid-template-columns:minmax(0,1fr)}h2{font-size:28px}}
@media (prefers-reduced-motion:no-preference){html{scroll-behavior:smooth}}
</style>
<div class="wrap">
<aside>
<p class="brand">DC Casablanca<br><span>Field Book</span></p>
<p class="sub">Everything about the lab, in one place.</p>
<label for="q" class="lbl">Search the book</label>
<input id="q" type="search" placeholder="FW-A, VLAN 30, HSRP, 10.20.0.10…" autocomplete="off">
<div id="results"></div>
<nav>%NAV%</nav>
</aside>
<main>%BODY%</main>
</div>
<script>
(function(){
const q=document.getElementById('q'),res=document.getElementById('results');
const entries=[...document.querySelectorAll('.entry')].map(el=>({el,text:el.textContent.toLowerCase(),
 title:el.dataset.title||el.textContent.trim().slice(0,60),id:el.id||''}));
entries.forEach((e,i)=>{if(!e.id){e.el.id='e-'+i;e.id=e.el.id}});
function go(e){if(e.el.tagName==='DETAILS')e.el.open=true;const d=e.el.closest('details');if(d)d.open=true;
 document.querySelectorAll('.hit').forEach(x=>x.classList.remove('hit'));e.el.classList.add('hit');
 e.el.scrollIntoView({block:'start'})}
q.addEventListener('input',()=>{const v=q.value.trim().toLowerCase();res.innerHTML='';if(v.length<2)return;
 const words=v.split(/\s+/);const hits=entries.filter(e=>words.every(w=>e.text.includes(w)));
 hits.sort((a,b)=>(b.title.toLowerCase().includes(v)?1:0)-(a.title.toLowerCase().includes(v)?1:0));
 if(!hits.length){res.innerHTML='<span class="none">Nothing found. Try a device name, an IP or a protocol.</span>';return}
 hits.slice(0,25).forEach(e=>{const a=document.createElement('a');a.href='#'+e.id;a.textContent=e.title;
  a.addEventListener('click',ev=>{ev.preventDefault();go(e)});res.appendChild(a)});
 if(hits.length>25){const s=document.createElement('span');s.className='none';s.textContent=(hits.length-25)+' more, refine the search';res.appendChild(s)}});
q.addEventListener('keydown',ev=>{if(ev.key==='Enter'){const a=res.querySelector('a');if(a)a.click()}});
document.addEventListener('keydown',ev=>{if(ev.key==='/'&&document.activeElement!==q){ev.preventDefault();q.focus()}});
document.querySelectorAll('.copy').forEach(b=>b.addEventListener('click',()=>{const t=b.nextElementSibling.textContent;
 const done=()=>{b.textContent='copied';setTimeout(()=>b.textContent='copy',1200)};
 (navigator.clipboard?navigator.clipboard.writeText(t):Promise.reject()).then(done).catch(()=>{const r=document.createRange();
 r.selectNodeContents(b.nextElementSibling);const s=getSelection();s.removeAllRanges();s.addRange(r)})}));
})();
</script>
"""

PRINT_CSS = r"""<style>
@page{size:A4;margin:14mm 13mm}
body{font-size:10.5pt;background:#fff}
aside{display:none}.wrap{display:block;max-width:none;padding:0}
.copy,#results{display:none}
.cover{min-height:250mm;display:flex;flex-direction:column;justify-content:center}
.cover h1{font:800 48pt/1 var(--display);letter-spacing:-.02em;margin:8px 0 16px}.cover h1 span{color:var(--accent)}
.ptoc{font-size:13pt;line-height:2}.ptoc a{color:var(--fg);text-decoration:none}
.chapter{break-before:page;border:0}
.card,.boss,.step,.why,.stat,tr{break-inside:avoid}
h2,h3,h4{break-after:avoid}
.cards,.bosses,.whys{grid-template-columns:repeat(2,minmax(0,1fr))}
.cmd{white-space:pre-wrap}
.deep{border:0}.deep summary{font-size:15pt;padding:12px 0;list-style:none}.md{padding:0}
.flow{white-space:pre;font-size:8pt}
.fig,.boss,.callout{break-inside:avoid}.gallery{grid-template-columns:repeat(2,minmax(0,1fr))}
.cover{min-height:auto}.cover .fig{max-width:150mm}
</style>"""


if __name__ == "__main__":
    build()
