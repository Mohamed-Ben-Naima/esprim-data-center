"""zabbix_setup – configure Zabbix (SRV-MON-01) from the inventory, over its JSON-RPC API (PLAN_02 ZBX.1–ZBX.5).

  python automation/zabbix_setup.py check     API version, login, is the server process collecting
  python automation/zabbix_setup.py apply     Admin password, timezone, groups, hosts, maintenance (idempotent)
  python automation/zabbix_setup.py status    groups, hosts, interface availability, maintenance

The API is reached through the lab proxy (`python automation/lab_proxy.py start`): a SOCKS5 connection opened from the
administration webterm ADMIN-WS, filtered by the pfSense ADMIN rules like any administrator. Standard library only.
Every `apply` step reads first, then creates or updates; templates are found by name, never by id.
Hosts whose GNS3 node is stopped go into the maintenance `monitoring.maintenance` (no data collected, no alarm).
"""
import http.client
import json
import socket
import struct
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import labctl  # noqa: E402

NET = Path(__file__).resolve().parents[1]
INV = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
MON = INV["monitoring"]
C = INV["credentials"]
PROXY = ("192.168.75.128", 1080)
DEFAULT_PASSWORD = "zabbix"            # Zabbix package default, replaced by `apply`
IF_AGENT, IF_SNMP = 1, 2
AVAIL = {"0": "unknown", "1": "available", "2": "UNAVAILABLE"}


# ------------------------------------------------------------------------------------------ transport
class SocksHTTPConnection(http.client.HTTPConnection):
    """HTTP over a SOCKS5 CONNECT (no authentication), the protocol lab_proxy.py serves."""

    def connect(self):
        s = socket.create_connection(PROXY, timeout=self.timeout)
        s.sendall(b"\x05\x01\x00")
        if s.recv(2) != b"\x05\x00":
            raise ConnectionError("SOCKS5 greeting refused - is lab_proxy.py started?")
        s.sendall(b"\x05\x01\x00\x01" + socket.inet_aton(self.host) + struct.pack("!H", self.port))
        reply = s.recv(10)
        if len(reply) < 2 or reply[1] != 0:
            raise ConnectionError(f"SOCKS5 connect to {self.host}:{self.port} failed")
        self.sock = s


class ZabbixError(RuntimeError):
    pass


class Zabbix:
    def __init__(self, url=MON["api"]):
        u = urlparse(url)
        self.host, self.port, self.path = u.hostname, u.port or 80, u.path
        self.auth = None

    def call(self, method, params=None):
        body = {"jsonrpc": "2.0", "method": method, "params": params if params is not None else {}, "id": 1}
        if self.auth and method not in ("apiinfo.version", "user.login"):
            body["auth"] = self.auth
        con = SocksHTTPConnection(self.host, self.port, timeout=60)
        try:
            con.request("POST", self.path, json.dumps(body), {"Content-Type": "application/json-rpc"})
            r = json.loads(con.getresponse().read())
        finally:
            con.close()
        if "error" in r:
            raise ZabbixError(f"{method}: {r['error'].get('data') or r['error'].get('message')}")
        return r["result"]

    def login(self, password):
        self.auth = self.call("user.login", {"username": "Admin", "password": password})
        return self.auth


def login(z, allow_default=False):
    """Log in as Admin with the inventory password (or the package default when `apply` has not run yet)."""
    try:
        z.login(C["zabbix_admin_password"])
        return "inventory"
    except ZabbixError:
        if not allow_default:
            raise
    z.login(DEFAULT_PASSWORD)
    return "default"


# ------------------------------------------------------------------------------------------ desired state
def wanted_hosts():
    """[{name, group, templates, interface: {...} | None, mode}] built from the inventory."""
    g, cred, out = MON["groups"], C, []
    for name, d in INV["devices"].items():
        how = MON["platforms"].get(d.get("platform"))
        if not how:
            continue
        if how["interface"] == "snmpv3":
            iface = {"type": IF_SNMP, "ip": d["mgmt"]["ip"], "port": "161",
                     "details": {"version": "3", "bulk": "1", "securityname": cred["snmpv3_user"], "securitylevel": "2",
                                 "authprotocol": "1", "authpassphrase": cred["snmpv3_auth"],         # SHA1
                                 "privprotocol": "1", "privpassphrase": cred["snmpv3_priv"],         # AES128
                                 "contextname": ""}}
        else:   # snmpv2: pfSense answers on its LAN (transit int) address only
            iface = {"type": IF_SNMP, "ip": INV["transit"]["int"][name], "port": "161",
                     "details": {"version": "2", "bulk": "1", "community": cred["snmp_ro_community"]}}
        out.append({"name": name, "group": g[d["role"]], "templates": how["templates"], "interface": iface})
    for name, a in MON["agents"].items():
        active = a["mode"] == "active"
        out.append({"name": name, "group": g["server"],
                    "templates": ["Linux by Zabbix agent active" if active else "Linux by Zabbix agent"],
                    "interface": None if active else {"type": IF_AGENT, "ip": INV["servers"][name]["ip"], "port": "10050"}})
    return out


def stopped_nodes():
    api = labctl.Gns3()
    return {n["name"] for n in api.nodes(api.project()) if n["status"] != "started"}


# ------------------------------------------------------------------------------------------ commands
def check():
    z = Zabbix()
    print("API version:", z.call("apiinfo.version"))
    print("login Admin:", login(z, allow_default=True), "password")
    # the server process is collecting if its own internal items (busy rate of its processes, every minute)
    # got a value in the last 2 minutes
    items = z.call("item.get", {"output": ["key_", "lastclock"], "search": {"key_": "zabbix[process,"},
                                "templated": False})
    fresh = [i for i in items if int(i["lastclock"]) > time.time() - 120]
    print("server running:", "yes" if fresh else "NO (no internal zabbix[process,...] value in the last 2 min)")
    return 0 if fresh else 1


def apply():
    z = Zabbix()
    # 1. Admin password from the inventory
    if login(z, allow_default=True) == "default":
        admin = z.call("user.get", {"output": ["userid"], "filter": {"username": "Admin"}})[0]
        z.call("user.update", {"userid": admin["userid"], "current_passwd": DEFAULT_PASSWORD,
                               "passwd": C["zabbix_admin_password"]})
        z.login(C["zabbix_admin_password"])
        print("Admin password: replaced by the inventory one")
    else:
        print("Admin password: already the inventory one")
    # 2. default timezone
    if z.call("settings.get", {"output": ["default_timezone"]})["default_timezone"] != MON["timezone"]:
        z.call("settings.update", {"default_timezone": MON["timezone"]})
        print("timezone: set to", MON["timezone"])
    else:
        print("timezone:", MON["timezone"], "(unchanged)")
    # 3. host groups
    have = {g["name"]: g["groupid"] for g in z.call("hostgroup.get", {"output": ["name"]})}
    for name in MON["groups"].values():
        if name not in have:
            have[name] = z.call("hostgroup.create", {"name": name})["groupids"][0]
            print("group created:", name)
    # 4. hosts
    want = wanted_hosts()
    names = sorted({t for h in want for t in h["templates"]})
    tpl = {t["host"]: t["templateid"] for t in z.call("template.get", {"output": ["host"], "filter": {"host": names}})}
    missing = set(names) - set(tpl)
    if missing:
        raise ZabbixError(f"templates not found: {', '.join(sorted(missing))}")
    current = {h["host"]: h for h in z.call("host.get", {"output": ["host"], "selectInterfaces": "extend",
                                                         "selectParentTemplates": ["templateid"]})}
    # the server watches itself through the first agent host: take over the package's "Zabbix server" host
    first_agent = next(iter(MON["agents"]))
    if first_agent not in current and "Zabbix server" in current:
        h = current.pop("Zabbix server")
        z.call("host.update", {"hostid": h["hostid"], "host": first_agent, "name": first_agent})
        current[first_agent] = h
        print(f"host renamed: Zabbix server -> {first_agent}")
    for w in want:
        groups = [{"groupid": have[w["group"]]}]
        tids = {tpl[t] for t in w["templates"]}
        h = current.get(w["name"])
        if not h:
            body = {"host": w["name"], "groups": groups, "templates": [{"templateid": t} for t in sorted(tids)]}
            if w["interface"]:
                body["interfaces"] = [dict(w["interface"], main="1", useip="1", dns="")]
            z.call("host.create", body)
            print("host created:", w["name"])
            continue
        # existing host: replace groups, add missing templates (never unlink: that would delete history)
        linked = {t["templateid"] for t in h["parentTemplates"]}
        z.call("host.update", {"hostid": h["hostid"], "groups": groups,
                               "templates": [{"templateid": t} for t in sorted(linked | tids)]})
        changed = sorted(tids - linked)
        if w["interface"]:
            same = [i for i in h["interfaces"] if int(i["type"]) == w["interface"]["type"]]
            if not same:
                z.call("hostinterface.create", dict(w["interface"], hostid=h["hostid"], main="1", useip="1", dns=""))
                changed.append("interface created")
            else:
                i = same[0]
                details = i.get("details") or {}
                if (i["ip"], i["port"], i["useip"]) != (w["interface"]["ip"], w["interface"]["port"], "1") or \
                        any(str(details.get(k)) != v for k, v in w["interface"].get("details", {}).items()):
                    z.call("hostinterface.update", dict(w["interface"], interfaceid=i["interfaceid"], useip="1"))
                    changed.append("interface updated")
        print(f"host {w['name']}: {'updated (' + ', '.join(changed) + ')' if changed else 'up to date'}")
    # 5. maintenance for the hosts whose node is stopped
    off = sorted(stopped_nodes() & {w["name"] for w in want})
    ids = {h["host"]: h["hostid"] for h in z.call("host.get", {"output": ["host"], "filter": {"host": off}})} if off else {}
    m = z.call("maintenance.get", {"output": ["maintenanceid"], "filter": {"name": MON["maintenance"]}})
    if not off:
        if m:
            z.call("maintenance.delete", [m[0]["maintenanceid"]])
        print(f"maintenance {MON['maintenance']}: no stopped host" + (" (removed)" if m else ""))
        return 0
    now = int(time.time()) // 60 * 60
    days = 30 * 86400
    body = {"name": MON["maintenance"], "maintenance_type": 1,              # 1 = no data collection
            "description": "Equipment stopped in the current lab profile (zabbix_setup.py apply)",
            "active_since": now, "active_till": now + days, "hosts": [{"hostid": ids[n]} for n in off],
            "timeperiods": [{"timeperiod_type": 0, "start_date": now, "period": days}]}
    if m:
        z.call("maintenance.update", dict(body, maintenanceid=m[0]["maintenanceid"]))
    else:
        z.call("maintenance.create", body)
    print(f"maintenance {MON['maintenance']}: {', '.join(off)}")
    return 0


def status():
    z = Zabbix()
    login(z)
    ours = set(MON["groups"].values())
    groups = z.call("hostgroup.get", {"output": ["name"], "filter": {"name": sorted(ours)}, "selectHosts": ["host"]})
    print(f"groups ({len(groups)}):", ", ".join(f"{g['name']} [{len(g['hosts'])}]" for g in sorted(groups, key=lambda g: g["name"])))
    hosts = z.call("host.get", {"output": ["host", "maintenance_status", "active_available"],
                                "groupids": [g["groupid"] for g in groups],
                                "selectInterfaces": ["type", "ip", "available", "error"],
                                "selectParentTemplates": ["host"], "sortfield": "host"})
    bad = 0
    print(f"{'host':12} {'interface':24} {'state':12} {'maintenance':11} templates")
    for h in hosts:
        maint = "yes" if h["maintenance_status"] == "1" else "-"
        tpls = ", ".join(t["host"] for t in h["parentTemplates"])
        rows = [(("agent" if i["type"] == "1" else "snmp") + " " + i["ip"], AVAIL[i["available"]], i["error"])
                for i in h["interfaces"]] or [("agent active", AVAIL[h["active_available"]], "")]
        for where, state, err in rows:
            if state != "available" and maint == "-":
                bad += 1
            print(f"{h['host']:12} {where:24} {state:12} {maint:11} {tpls}" + (f"  ({err})" if err and maint == "-" else ""))
    print(f"\n{len(hosts)} hosts, {bad} running host(s) not available")
    return 1 if bad else 0


if __name__ == "__main__":
    op = sys.argv[1] if len(sys.argv) > 1 else ""
    if op not in ("check", "apply", "status"):
        sys.exit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit({"check": check, "apply": apply, "status": status}[op]())
