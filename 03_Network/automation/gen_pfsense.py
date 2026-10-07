"""Generate FW-A / FW-B config.xml (pfSense CE 2.7.2) from a factory baseline + inventory/dc_casa.yaml.

  python automation/gen_pfsense.py configs/pfsense/baseline.xml
      -> configs/pfsense/FW-A.config.xml, FW-B.config.xml

The baseline is the config.xml of a freshly installed pfSense (pulled from the firewall), so every
version-specific section stays valid; this script only rewrites the parts it owns:
system identity/services, interfaces (WAN em0, SYNC em2, LAN lagg0 failover em3/em4, DMZ em5,
MGMT em6.10, ADMIN em6.90), VLANs, LAGG, CARP + 'other' VIPs, gateways, static routes, aliases,
outbound NAT (hybrid), port forwards, filter rules (PDF Table 18, default deny + log),
HA (pfsync + XMLRPC), remote syslog, SNMP, NTP.
"""
import copy
import re
import ipaddress
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import bcrypt
import yaml

NET = Path(__file__).resolve().parents[1]
INV = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
OUT = NET / "configs" / "pfsense"
C, S, SITE, VL, TR = INV["credentials"], INV["services"], INV["site"], INV["vlans"], INV["transit"]

# pfSense interface keys (WAN/LAN are mandatory names)
IFACES = {
    "wan":  {"if": "em0",    "descr": "WAN",   "net": TR["ext"]["subnet"],  "key": "ext"},
    "lan":  {"if": "lagg0",  "descr": "LAN",   "net": TR["int"]["subnet"],  "key": "int"},
    "opt1": {"if": "em2",    "descr": "SYNC",  "net": TR["sync"]["subnet"], "key": "sync"},
    "opt2": {"if": "em5",    "descr": "DMZ",   "net": VL[50]["subnet"],     "vlan": 50},
    "opt3": {"if": "em6.10", "descr": "MGMT",  "net": VL[10]["subnet"],     "vlan": 10},
    "opt4": {"if": "em6.90", "descr": "ADMIN", "net": VL[90]["subnet"],     "vlan": 90},
}
CARP = [  # (interface, vhid, vip)
    ("wan", 1, TR["ext"]["fw_vip"]), ("lan", 2, TR["int"]["fw_vip"]), ("opt2", 50, VL[50]["vip"]),
    ("opt3", 10, VL[10]["vip"]), ("opt4", 90, VL[90]["vip"]),
]
IFNAME = {v["descr"]: k for k, v in IFACES.items()}
TRACKER = [1700000000]          # deterministic rule trackers / alias names (stable diffs)


def el(parent, tag, text=None, **_):
    e = ET.SubElement(parent, tag)
    if text is not None:
        e.text = str(text)
    return e


def reset(parent, tag):
    """Remove all <tag> children and return a fresh empty one."""
    for e in parent.findall(tag):
        parent.remove(e)
    return el(parent, tag)


def sub(parent, tag):
    e = parent.find(tag)
    return e if e is not None else el(parent, tag)


def setv(parent, tag, value):
    e = sub(parent, tag)
    e.text = None if value is None else str(value)
    for c in list(e):
        e.remove(c)
    return e


def flag(parent, tag, on=True):
    e = parent.find(tag)
    if on and e is None:
        el(parent, tag)
    if not on and e is not None:
        parent.remove(e)


def ip_for(fw, i):
    d = IFACES[i]
    if "key" in d:
        return TR[d["key"]][fw]
    return VL[d["vlan"]]["fw_a" if fw == "FW-A" else "fw_b"]


def created(rule, who="gen_pfsense.py"):
    c = el(rule, "created")
    el(c, "time", int(time.time()))
    el(c, "username", who)


def addr(parent, tag, spec, iface):
    """source/destination block. spec: any | <IF>_NET | alias | cidr | host | !cidr | any_internal."""
    blk = el(parent, tag)
    if spec in ("any",):
        el(blk, "any")
    elif spec == "any_internal":
        el(blk, "address", "ALL_INTERNAL")
    elif spec.endswith("_NET"):
        el(blk, "network", IFNAME[spec[:-4]] if spec[:-4] in IFNAME else iface)
    elif spec.startswith("!"):
        el(blk, "not")
        el(blk, "address", spec[1:])
    else:
        el(blk, "address", spec)
    return blk


def build(baseline, fw):
    root = ET.fromstring(baseline)
    TRACKER[0] = 1700000000                      # same rule ids / alias names on both firewalls
    peer = "FW-B" if fw == "FW-A" else "FW-A"
    advskew = INV["devices"][fw]["carp_advskew"]

    # ---------------------------------------------------------------- system
    sysn = root.find("system")
    setv(sysn, "hostname", fw.lower())
    setv(sysn, "domain", SITE["domain"])
    for e in sysn.findall("dnsserver"):
        sysn.remove(e)
    el(sysn, "dnsserver", S["dns"])
    flag(sysn, "dnsallowoverride", False)
    setv(sysn, "timezone", SITE["timezone"])
    setv(sysn, "timeservers", S["ntp"])
    pw = bcrypt.hashpw(C["admin_password"].encode(), bcrypt.gensalt(10)).decode().replace("$2b$", "$2y$")
    for u in sysn.findall("user"):
        if u.findtext("name") == "admin":
            setv(u, "bcrypt-hash", pw)
            for old in ("password", "md5-hash"):
                flag(u, old, False)
    web = sub(sysn, "webgui")
    setv(web, "protocol", "https")
    flag(web, "noantilockout", True)          # GUI reachable only through the explicit ADMIN rule
    flag(web, "loginautocomplete", False)
    setv(sysn, "ssh", None)
    ssh = sysn.find("ssh")
    el(ssh, "enable", "enabled")
    flag(sysn, "disablechecksumoffloading", True)
    setv(sysn, "maximumstates", None)

    # ---------------------------------------------------------------- interfaces
    old = root.find("interfaces")
    ifs = ET.Element("interfaces")
    for k, d in IFACES.items():
        i = el(ifs, k)
        el(i, "enable")
        el(i, "if", d["if"])
        el(i, "descr", d["descr"])
        el(i, "ipaddr", ip_for(fw, k))
        el(i, "subnet", ipaddress.ip_network(d["net"]).prefixlen)
        el(i, "spoofmac")
    root.insert(list(root).index(old), ifs)
    root.remove(old)

    vl = reset(root, "vlans")
    for tag, name in ((10, "MGMT"), (90, "ADMIN")):
        v = el(vl, "vlan")
        el(v, "if", "em6"); el(v, "tag", tag); el(v, "pcp"); el(v, "descr", f"VLAN {tag} {name}"); el(v, "vlanif", f"em6.{tag}")
    lg = reset(root, "laggs")
    l = el(lg, "lagg")
    el(l, "members", "em3,em4"); el(l, "descr", "LAN failover CORE-A (em3) / CORE-B (em4)"); el(l, "laggif", "lagg0")
    el(l, "proto", "failover"); el(l, "failovermaster", "em3"); el(l, "lacptimeout", "slow"); el(l, "lagghash", "l2,l3,l4")

    # DHCP server off everywhere, DNS resolver off (DNS = SRV-INF-01)
    reset(root, "dhcpd")
    ub = root.find("unbound")
    if ub is not None:
        flag(ub, "enable", False)

    # ---------------------------------------------------------------- VIPs
    vips = reset(root, "virtualip")
    for iface, vhid, vip in CARP:
        v = el(vips, "vip")
        el(v, "mode", "carp"); el(v, "interface", iface); el(v, "vhid", vhid); el(v, "advskew", advskew)
        el(v, "advbase", 1); el(v, "password", C["carp_password"]); el(v, "uniqid", f"carp{vhid:04d}")
        el(v, "descr", f"CARP {IFACES[iface]['descr']} VIP"); el(v, "type", "single")
        el(v, "subnet_bits", ipaddress.ip_network(IFACES[iface]["net"]).prefixlen); el(v, "subnet", vip)
    for ip, d in ((SITE["snat_ip"], "Public SNAT address"), (SITE["web_public_ip"], "Public web (DNAT SRV-WEB-01)")):
        v = el(vips, "vip")
        el(v, "mode", "other"); el(v, "interface", "wan"); el(v, "uniqid", "other" + ip.split(".")[-1])
        el(v, "descr", d); el(v, "type", "single"); el(v, "subnet_bits", 32); el(v, "subnet", ip)

    # ---------------------------------------------------------------- gateways, routes
    gws = reset(root, "gateways")
    for name, iface, gw, d in (("WAN_EDGE_VIP", "wan", TR["ext"]["edge_vip"], "Edge HSRP VIP (VLAN 901)"),
                               ("CORE_VIP", "lan", TR["int"]["core_vip"], "Core HSRP VIP (VLAN 902)")):
        g = el(gws, "gateway_item")
        el(g, "interface", iface); el(g, "gateway", gw); el(g, "name", name); el(g, "weight", 1)
        el(g, "ipprotocol", "inet"); el(g, "descr", d)
    el(gws, "defaultgw4", "WAN_EDGE_VIP")
    sr = reset(root, "staticroutes")
    r = el(sr, "route")
    el(r, "network", "10.0.0.0/8"); el(r, "gateway", "CORE_VIP"); el(r, "descr", "Internal VLANs behind the cores")

    # ---------------------------------------------------------------- aliases
    al = reset(root, "aliases")

    def alias(name, typ, items, descr):
        a = el(al, "alias")
        el(a, "name", name); el(a, "type", typ); el(a, "address", " ".join(str(x) for x in items))
        el(a, "descr", descr); el(a, "detail", "||".join("" for _ in items))
    for name, items in INV["host_aliases"].items():
        alias(name, "network" if any("/" in str(x) for x in items) else "host", items, f"inventory host alias {name}")
    alias("ALL_INTERNAL", "network", ["10.0.0.0/8"], "All internal networks (devices, VLANs)")
    for name, ports in INV["port_aliases"].items():
        alias(f"P_{name}", "port", ports, f"inventory port alias {name}")

    # ---------------------------------------------------------------- NAT
    nat = reset(root, "nat")
    ob = el(nat, "outbound")
    el(ob, "mode", "hybrid")
    rule = el(ob, "rule")
    s = el(rule, "source"); el(s, "network", "10.0.0.0/8")
    el(rule, "sourceport"); el(rule, "descr", "Internal networks -> Internet via public SNAT 192.0.2.10")
    el(rule, "target", SITE["snat_ip"]); el(rule, "targetip"); el(rule, "targetip_subnet"); el(rule, "interface", "wan")
    el(rule, "poolopts"); el(rule, "source_hash_key")
    d = el(rule, "destination"); el(d, "any")
    created(rule)
    # the firewall's own traffic (DNS, NTP, updates) leaves from its private transit address:
    # translate it too, otherwise the operators cannot route the replies back
    rule = el(ob, "rule")
    s2 = el(rule, "source"); el(s2, "network", TR["ext"]["subnet"])
    el(rule, "sourceport"); el(rule, "descr", "Firewall own traffic (transit 901) -> Internet via 192.0.2.10")
    el(rule, "target", SITE["snat_ip"]); el(rule, "targetip"); el(rule, "targetip_subnet"); el(rule, "interface", "wan")
    el(rule, "poolopts"); el(rule, "source_hash_key")
    d = el(rule, "destination"); el(d, "any")
    created(rule)
    for port in (80, 443):
        pf = el(nat, "rule")
        s = el(pf, "source"); el(s, "any")
        d = el(pf, "destination"); el(d, "address", SITE["web_public_ip"]); el(d, "port", port)
        el(pf, "ipprotocol", "inet"); el(pf, "protocol", "tcp"); el(pf, "target", INV["servers"]["SRV-WEB-01"]["ip"])
        el(pf, "local-port", port); el(pf, "interface", "wan")
        el(pf, "descr", f"Publication web {port}/tcp -> SRV-WEB-01 (T18-1)"); el(pf, "associated-rule-id", "pass")
        created(pf)

    # ---------------------------------------------------------------- filter
    flt = reset(root, "filter")
    order = ["WAN", "LAN", "SYNC", "DMZ", "MGMT", "ADMIN"]
    extra = {  # firewall-own services, before the inventory policy
        "ADMIN": [{"action": "pass", "proto": "tcp", "src": "ADMIN_NET", "dst": "(self)", "ports": [443, 22],
                   "descr": "Administration -> webGUI/SSH du pare-feu (anti-lockout explicite)", "ref": "T18-6"}],
        "LAN": [{"action": "pass", "proto": "udp", "src": "10.60.0.0/24", "dst": "(self)", "ports": [161],
                 "descr": "Supervision -> SNMP du pare-feu", "ref": "T18-7"},
                {"action": "pass", "proto": "icmp", "src": "10.60.0.0/24", "dst": "(self)",
                 "descr": "Supervision -> ICMP du pare-feu", "ref": "T18-7"}],
    }
    for itf in order:
        iface = IFNAME[itf]
        for rd in extra.get(itf, []) + INV["firewall_rules"].get(itf, []):
            if itf == "WAN":
                continue            # WAN publication handled by NAT port forwards with associated pass rules
            protos = ["tcp", "udp"] if rd["proto"] == "tcp/udp" else [rd["proto"]]
            dsts = rd["dst"] if isinstance(rd["dst"], list) else [rd["dst"]]
            for proto in protos:
                for dst in dsts:
                    r = el(flt, "rule")
                    TRACKER[0] += 1
                    el(r, "id"); el(r, "tracker", TRACKER[0]); el(r, "type", rd["action"]); el(r, "interface", iface)
                    el(r, "ipprotocol", "inet"); el(r, "tag"); el(r, "tagged"); el(r, "max"); el(r, "max-src-nodes")
                    el(r, "max-src-conn"); el(r, "max-src-states"); el(r, "statetimeout"); el(r, "statetype", "keep state")
                    el(r, "os")
                    if proto != "any":
                        el(r, "protocol", proto)
                    addr(r, "source", rd["src"], iface)
                    if dst == "(self)":
                        dblk = el(r, "destination"); el(dblk, "network", "(self)")
                    else:
                        dblk = addr(r, "destination", dst, iface)
                    ports = rd.get("ports")
                    if ports and proto in ("tcp", "udp"):
                        if isinstance(ports, str):
                            el(dblk, "port", f"P_{ports}")
                        elif len(ports) == 1:
                            el(dblk, "port", ports[0])
                        else:
                            pa = f"P_{iface.upper()}_{TRACKER[0] - 1700000000:03d}"
                            a = el(al, "alias"); el(a, "name", pa); el(a, "type", "port")
                            el(a, "address", " ".join(map(str, ports))); el(a, "descr", rd["descr"]); el(a, "detail", "")
                            el(dblk, "port", pa)
                    if rd["action"] == "block" or rd.get("log"):
                        el(r, "log")
                    el(r, "descr", f"[{rd['ref']}] {rd['descr']}")
                    created(r)
        # explicit default deny with logging (pfSense also denies implicitly; this one is visible and logged)
        r = el(flt, "rule")
        TRACKER[0] += 1
        el(r, "tracker", TRACKER[0]); el(r, "type", "block"); el(r, "interface", iface); el(r, "ipprotocol", "inet")
        s = el(r, "source"); el(s, "any")
        d = el(r, "destination"); el(d, "any")
        el(r, "log"); el(r, "descr", f"[T18] Refus par défaut {itf} (journalisé)")
        created(r)

    # ---------------------------------------------------------------- HA
    ha = reset(root, "hasync")
    el(ha, "pfsyncenabled", "on"); el(ha, "pfsyncinterface", "opt1"); el(ha, "pfsyncpeerip", TR["sync"][peer])
    if fw == "FW-A":
        el(ha, "synchronizetoip", TR["sync"][peer]); el(ha, "username", "admin"); el(ha, "password", C["admin_password"])
        for f in ("synchronizeusers", "synchronizeauthservers", "synchronizecerts", "synchronizerules", "synchronizeschedules",
                  "synchronizealiases", "synchronizenat", "synchronizevirtualip", "synchronizestaticroutes"):
            el(ha, f, "on")

    # ---------------------------------------------------------------- logging, SNMP, NTP
    sl = reset(root, "syslog")
    el(sl, "filterdescriptions", 1); el(sl, "nentries", 500); el(sl, "enable")
    el(sl, "remoteserver", f"{S['syslog']}:514"); el(sl, "sourceip", "opt3"); el(sl, "ipproto", "ipv4"); el(sl, "logall")
    sn = reset(root, "snmpd")
    el(sn, "syslocation", f"{SITE['name']} / MDA"); el(sn, "syscontact", f"noc@{SITE['domain']}")
    el(sn, "rocommunity", C["snmp_ro_community"]); el(sn, "enable"); el(sn, "pollport", 161); el(sn, "bindip", "lan")
    mods = el(sn, "modules")
    for m in ("mibii", "netgraph", "pf", "hostres", "ucd", "regex"):
        el(mods, m)
    nt = sub(root, "ntpd")
    setv(nt, "interface", "opt3,opt4")

    # ---------------------------------------------------------------- revision
    rev = reset(root, "revision")
    el(rev, "time", int(time.time())); el(rev, "description", f"gen_pfsense.py – {fw} from inventory/dc_casa.yaml")
    el(rev, "username", "gen_pfsense.py")
    ET.indent(root, space="\t")
    return '<?xml version="1.0"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


if __name__ == "__main__":
    base = Path(sys.argv[1] if len(sys.argv) > 1 else OUT / "baseline.xml").read_text(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    for fw in ("FW-A", "FW-B"):
        xml = build(base, fw)
        (OUT / f"{fw}.config.xml").write_text(xml, encoding="utf-8", newline="\n")       # deployable (secrets, gitignored)
        red = re.sub(r"<prv>.*?</prv>", "<prv>REDACTED</prv>", xml, flags=re.S)
        red = re.sub(r"<(bcrypt-hash|password)>[^<]*</", r"<\1>REDACTED</", red)
        (OUT / f"{fw}.config.redacted.xml").write_text(red, encoding="utf-8", newline="\n")  # documentation copy
        root = ET.fromstring(xml)
        print(f"{fw}: {len(root.find('filter'))} filter rules, {len(root.find('virtualip'))} VIPs, "
              f"{len(root.find('aliases'))} aliases, {len(root.find('nat').findall('rule'))} port forwards")
