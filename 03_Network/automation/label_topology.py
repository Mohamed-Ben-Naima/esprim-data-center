"""Put a short description note under every node of the live GNS3 project, plus a VLAN legend.

Text comes from inventory/dc_casa.yaml (role, TIA space, IPs, VLANs, protocols / config type), so it stays true
when the inventory changes. Idempotent: notes written by this script (font Consolas) are deleted and rewritten.
  python automation/label_topology.py            # write notes
  python automation/label_topology.py --dry-run  # print them only
  python automation/label_topology.py --remove   # delete them
"""
import html
import textwrap
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import labctl  # noqa: E402

NET = Path(__file__).resolve().parents[1]
INV = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
MARK = 'font-family="Consolas"'
V = INV["vlans"]
T = INV["transit"]

ROLE_TXT = {
    "edge": ("Edge router (Internet border)",
             "eBGP AS{asn} to ISP, OSPF, HSRP VIP {ev} on VLAN 901, ACL-WAN-IN"),
    "firewall": ("pfSense firewall (HA pair)",
                 "CARP VIPs, pfsync on {sync}, NAT/SNAT, zone rules WAN/DMZ/LAN/MGMT/ADMIN"),
    "core": ("Core L3 switch (inter-VLAN routing)",
             "HSRP gateways per VLAN, OSPF, LACP Po1 to peer core, per-VLAN ACLs, Rapid-PVST"),
    "leaf": ("Leaf / access switch hall {hall}",
             "802.1Q trunks to both cores, Rapid-PVST, VTP transparent"),
}
COMMON = "SSHv2, SNMPv3, syslog, NTP"
SRV_TXT = {
    "app-8443": "app HTTPS 8443", "keepalived-master": "keepalived MASTER (VRRP)",
    "keepalived-backup": "keepalived BACKUP (VRRP)", "iperf3": "iperf3", "nfs": "NFS", "iscsi": "iSCSI",
    "nas": "TrueNAS", "backup-pull": "pull backups", "snapshots": "ZFS snapshots", "dns": "DNS", "ntp": "NTP",
    "dhcp": "DHCP", "backup-source": "backup source", "zabbix": "Zabbix", "grafana": "Grafana",
    "dcim": "DCIM", "syslog": "rsyslog collector", "log-viewer": "log viewer", "bms-sim": "BMS simulator (GTB)",
    "cctv-sim": "CCTV simulator", "web": "public web (DMZ)", "bastion": "SSH bastion", "mfa": "password+TOTP",
    "admin-desktop": "admin desktop (VNC)", "admin-bastion": "SSH/web to all equipment",
}


def vname(v):
    return f"{v} {V[v]['name']}" if v in V else str(v)


def vlans_of(ifaces):
    out = set()
    for spec in (ifaces or {}).values():
        if not isinstance(spec, dict):
            continue
        for k in ("vlan", "access_vlan"):
            if isinstance(spec.get(k), int):
                out.add(spec[k])
        for k in ("vlans", "allowed", "carries"):
            val = spec.get(k)
            if isinstance(val, list):
                out.update(x for x in val if isinstance(x, int))
            elif isinstance(val, str):
                out.update(int(x) for x in re.findall(r"\d+", val))
    return sorted(out - {1})


def device_note(name, d):
    title, proto = ROLE_TXT.get(d["role"], (d["role"], ""))
    lines = [f"{title.format(hall=d.get('hall', '?'))} | TIA {d.get('tia', '?')}",
             f"mgmt {d['mgmt']['ip']} (VLAN 10) | lo {d.get('loopback', '-')}"]
    tr = [f"{k} {t[name]}" for k, t in T.items() if name in t]
    if tr:
        lines.append("transit: " + ", ".join(tr))
    if d["role"] == "core":
        act = [str(v) for v, x in V.items() if x.get("active") == name]
        lines.append(f"HSRP active VLAN {','.join(act)} (standby others)")
    vl = INV["core_vlans"] if d["role"] == "core" else vlans_of(d.get("interfaces") or d.get("ports"))
    if vl:
        lines.append(("SVI/trunk VLANs: " if d["role"] == "core" else "access VLANs: ") + ",".join(map(str, vl)))
    lines.append(proto.format(asn=INV["site"].get("asn"), ev=T["ext"].get("edge_vip"), sync=T["sync"]["subnet"]))
    lines.append(f"mgmt plane: {COMMON}")
    return lines


def server_note(name, s):
    v = s.get("vlan")
    lines = [f"{s.get('kind', '')} server | TIA {s.get('tia', '?')} | VLAN {vname(v)}",
             f"IP {s.get('ip', '?')}" + (f" | VIP {s['vip']}" if s.get("vip") else "")
             + (" | bond (2 leafs)" if s.get("bond") else "")]
    roles = [SRV_TXT.get(r, r) for r in s.get("roles", [])]
    if roles:
        lines.append(", ".join(roles))
    return lines


def switch_note(name, sw):
    vl = vlans_of(sw.get("ports"))
    purpose = {"SW-OUT": "edge <-> firewall transit", "SW-IN": "firewall <-> core transit",
               "SW-DMZ": "DMZ segment", "SW-MGMT": "out-of-band management + admin"}.get(name, "")
    return [f"GNS3 lab switch: {purpose}", "VLANs: " + ", ".join(vname(v) for v in vl)]


def notes():
    out = {n: device_note(n, d) for n, d in INV["devices"].items()}
    out.update({n: server_note(n, s) for n, s in INV["servers"].items()})
    out.update({n: switch_note(n, s) for n, s in INV["lab_switches"].items()})
    for n, isp in INV["isps"].items():
        links = ", ".join(f"{p} {x['ip']}->{x['peer']}" for p, x in isp["links"].items())
        out[n] = [f"ISP simulator AS{isp['asn']} (eBGP)", links, f"Internet via {isp.get('nat_uplink')}"]
    for n, u in INV["internet_uplinks"].items():
        out[n] = [f"GNS3 NAT cloud = real Internet for {u['to'].split(':')[0]}"]
    out.setdefault("SRV-BASTION", ["SSH bastion | VLAN 90 ADMIN", "password + TOTP (MFA)"])
    out.setdefault("ADMIN-WS", ["Admin workstation | VLAN 90 ADMIN", "SSH/web to all equipment, sessions logged"])
    return out


def legend():
    rows = ["VLAN PLAN (gateway: core = HSRP on cores, fw = CARP on firewalls)"]
    for v, x in V.items():
        if x.get("subnet"):
            gw = x.get("vip", "-")
            rows.append(f"{v:>4} {x['name']:<14} {x['subnet']:<15} gw {gw:<12} {x['gw_type']:<4} {x['zone']}")
    return rows


def svg(lines, size=8, color="#1f3a5f", wrap=46):
    if wrap:
        lines = [w for s in lines for w in textwrap.wrap(s, wrap, subsequent_indent="  ")]
    w = max(len(s) for s in lines) * size * 0.62 + 8
    h = len(lines) * size * 1.45 + 6
    txt = html.escape("\n".join(lines))
    return (f'<svg width="{int(w)}" height="{int(h)}"><text {MARK} font-size="{size}.0" fill="{color}" '
            f'fill-opacity="1.0">{txt}</text></svg>')


def main(argv):
    n = notes()
    if "--dry-run" in argv:
        for k, v in n.items():
            print(f"[{k}]\n  " + "\n  ".join(v))
        print("\n".join(legend()))
        return 0
    api = labctl.Gns3()
    p = api.open(api.project())
    pid = p["project_id"]
    for d in api.req("GET", f"/projects/{pid}/drawings"):
        if MARK in d.get("svg", ""):
            api.req("DELETE", f"/projects/{pid}/drawings/{d['drawing_id']}")
    if "--remove" in argv:
        print("notes removed")
        return 0
    done, minx, miny = 0, 0, 0
    for node in api.nodes(p):
        minx, miny = min(minx, node["x"]), min(miny, node["y"])
        lines = n.get(node["name"])
        if not lines:
            continue
        api.req("POST", f"/projects/{pid}/drawings",
                dict(svg=svg(lines), x=node["x"] - 20, y=node["y"] + node.get("height", 60) + 22, z=2))
        done += 1
    api.req("POST", f"/projects/{pid}/drawings", dict(svg=svg(legend(), 9, "#000000", wrap=0), x=minx - 560, y=miny, z=2))
    print(f"{done} node notes + VLAN legend written")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
