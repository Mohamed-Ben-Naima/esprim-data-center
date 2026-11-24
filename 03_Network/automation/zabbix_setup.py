"""zabbix_setup – configure Zabbix (SRV-MON-01) from the inventory, over its JSON-RPC API (PLAN_02 ZBX.1–ZBX.6).

  python automation/zabbix_setup.py check     API version, login, is the server process collecting
  python automation/zabbix_setup.py apply     Admin password, timezone, groups, hosts, services, maintenance (idempotent)
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
SIMPLE, HTTP_AGENT, DEPENDENT, TRAPPER = 3, 19, 18, 2     # item types
VTYPE = {"float": 0, "char": 1, "uint": 3, "text": 4}
SEVERITY = {"info": 1, "warning": 2, "average": 3, "high": 4, "disaster": 5}
JSONPATH, ON_FAIL_SET = 12, 2                              # preprocessing step type, error handler "set value to"


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
        out.append({"name": name, "group": g[d["role"]], "templates": how["templates"], "interface": iface,
                    "off_triggers": how.get("off_triggers", [])})
    for name, d in MON.get("snmp_servers", {}).items():           # PLAN_04 NAS.6: SNMPv3 instead of an agent
        iface = {"type": IF_SNMP, "ip": INV["servers"][name]["ip"], "port": "161",
                 "details": {"version": "3", "bulk": "1", "securityname": cred["snmpv3_user"], "securitylevel": "2",
                             "authprotocol": "1", "authpassphrase": cred["snmpv3_auth"],
                             "privprotocol": "1", "privpassphrase": cred["snmpv3_priv"], "contextname": ""}}
        out.append({"name": name, "group": g[d.get("group", "server")], "templates": d["templates"],
                    "fallback": d.get("fallback", []), "interface": iface})
    for name, a in MON["agents"].items():
        active = a["mode"] == "active"
        out.append({"name": name, "group": g["server"],
                    "templates": ["Linux by Zabbix agent active" if active else "Linux by Zabbix agent"],
                    "interface": None if active else {"type": IF_AGENT, "ip": INV["servers"][name]["ip"], "port": "10050"}})
    return out


def wanted_items(name, svc, interfaceid, master_itemid=None):
    """Item bodies of a service host (`monitoring.services`), keyed by item key. Dependent items need the master id."""
    out = {}
    src = svc.get("source")
    if src:
        out[src["key"]] = {"name": f"{name} API", "key_": src["key"], "type": HTTP_AGENT, "value_type": VTYPE["text"],
                           "url": src["url"], "delay": src["delay"], "timeout": "5s", "history": "1h"}
        for i in svc["items"]:
            step = {"type": JSONPATH, "params": i["path"], "error_handler": 0, "error_handler_params": ""}
            if "default" in i:
                step.update(error_handler=ON_FAIL_SET, error_handler_params=str(i["default"]))
            out[i["key"]] = {"name": i["name"], "key_": i["key"], "type": DEPENDENT, "value_type": VTYPE[i["type"]],
                             "master_itemid": master_itemid, "delay": "0", "units": i.get("units", ""),
                             "preprocessing": [step]}
    if svc.get("trapper"):                             # values pushed by the host itself (Zabbix sender)
        for i in svc["items"]:
            out[i["key"]] = {"name": i["name"], "key_": i["key"], "type": TRAPPER, "value_type": VTYPE[i["type"]],
                             "trapper_hosts": svc["trapper"]["allowed"], "units": i.get("units", "")}
    if svc.get("icmp"):
        out["icmpping"] = {"name": "ICMP ping", "key_": "icmpping", "type": SIMPLE, "value_type": VTYPE["uint"],
                           "delay": "30s", "interfaceid": interfaceid}
        out["icmppingsec"] = {"name": "ICMP temps de réponse", "key_": "icmppingsec", "type": SIMPLE,
                              "value_type": VTYPE["float"], "delay": "30s", "units": "s", "interfaceid": interfaceid}
    return out


def differs(have, want):
    for k, v in want.items():
        if k == "preprocessing":
            got = [{f: str(p[f]) for f in ("type", "params", "error_handler", "error_handler_params")}
                   for p in have.get("preprocessing", [])]
            if got != [{f: str(p[f]) for f in p} for p in v]:
                return True
        elif str(have.get(k)) != str(v):
            return True
    return False


def apply_services(z, group_ids):
    """ZBX.6: service hosts in DC/Services with HTTP-agent + dependent items, web scenario, ICMP, triggers."""
    for name, svc in MON["services"].items():
        gid = group_ids[MON["groups"][svc.get("group", "service")]]
        notes = []
        ip = INV["servers"][name]["ip"]
        h = z.call("host.get", {"output": ["hostid"], "filter": {"host": name}, "selectInterfaces": ["interfaceid", "ip"]})
        if not h:
            body = {"host": name, "groups": [{"groupid": gid}]}
            if svc.get("icmp"):     # simple checks need an interface; the agent type is only its address holder
                body["interfaces"] = [{"type": IF_AGENT, "main": "1", "useip": "1", "ip": ip, "dns": "", "port": "10050"}]
            hostid = z.call("host.create", body)["hostids"][0]
            notes.append("host created")
            h = z.call("host.get", {"output": ["hostid"], "hostids": hostid, "selectInterfaces": ["interfaceid", "ip"]})
        else:
            z.call("host.update", {"hostid": h[0]["hostid"], "groups": [{"groupid": gid}]})
        hostid = h[0]["hostid"]
        ifid = h[0]["interfaces"][0]["interfaceid"] if h[0]["interfaces"] else None
        # items: master first (dependent items point at it), then the others
        have = {i["key_"]: i for i in z.call("item.get", {"output": "extend", "hostids": hostid,
                                                          "selectPreprocessing": "extend", "webitems": False})}
        master = svc.get("source", {}).get("key")
        order = ([master] if master else []) + [k for k in wanted_items(name, svc, ifid) if k != master]
        for key in order:
            mid = have[master]["itemid"] if master in have else None
            want = wanted_items(name, svc, ifid, mid)[key]
            if key not in have:
                r = z.call("item.create", dict(want, hostid=hostid))
                have[key] = dict(want, itemid=r["itemids"][0])
                notes.append(f"item {key} created")
            elif differs(have[key], want):
                z.call("item.update", dict(want, itemid=have[key]["itemid"]))
                notes.append(f"item {key} updated")
        # web scenario
        web = svc.get("web")
        if web:
            want = {"name": web["name"], "delay": web["delay"], "retries": 2, "verify_peer": 0, "verify_host": 0,
                    "steps": [{"name": "health", "no": 1, "url": web["url"], "required": web["required"],
                               "status_codes": "200", "timeout": "5s"}]}
            cur = z.call("httptest.get", {"output": "extend", "hostids": hostid, "selectSteps": "extend",
                                          "filter": {"name": web["name"]}})
            if not cur:
                z.call("httptest.create", dict(want, hostid=hostid))
                notes.append("web scenario created")
            else:
                s = cur[0]["steps"][0] if cur[0]["steps"] else {}
                if differs(cur[0], {k: v for k, v in want.items() if k != "steps"}) or \
                        differs(s, {k: v for k, v in want["steps"][0].items()}):
                    z.call("httptest.update", dict(want, httptestid=cur[0]["httptestid"]))
                    notes.append("web scenario updated")
        # triggers, then their dependencies (by name, on the same host)
        cur = {t["description"]: t for t in z.call("trigger.get", {"output": ["description", "expression", "priority"],
                                                                    "hostids": hostid, "expandExpression": True,
                                                                    "selectDependencies": ["triggerid"]})}
        for t in svc.get("triggers", []):
            want = {"description": t["name"], "expression": t["expr"], "priority": SEVERITY[t["severity"]]}
            if t["name"] not in cur:
                tid = z.call("trigger.create", want)["triggerids"][0]
                cur[t["name"]] = dict(want, triggerid=tid, dependencies=[])
                notes.append(f"trigger created: {t['name']}")
            elif differs(cur[t["name"]], want):
                z.call("trigger.update", dict(want, triggerid=cur[t["name"]]["triggerid"]))
                notes.append(f"trigger updated: {t['name']}")
        for t in svc.get("triggers", []):
            deps = [cur[t["depends"]]["triggerid"]] if t.get("depends") else []
            if sorted(d["triggerid"] for d in cur[t["name"]]["dependencies"]) != deps:
                z.call("trigger.update", {"triggerid": cur[t["name"]]["triggerid"],
                                          "dependencies": [{"triggerid": d} for d in deps]})
                notes.append(f"dependency set: {t['name']}")
        print(f"service {name}: {'; '.join(notes) if notes else 'up to date'}")


def apply_grafana_user(z, group_ids):
    """GRF.3: read-only account for the Grafana data source - built-in "User role" (no configuration menu), one user
    group with read permission on every DC/* group. The password is checked by logging in with it."""
    name, group = MON["grafana"]["zabbix_user"], "Grafana (read-only)"
    rights = [{"id": group_ids[g], "permission": 2} for g in sorted(set(MON["groups"].values()))]   # 2 = read
    notes = []
    ug = z.call("usergroup.get", {"output": ["usrgrpid"], "filter": {"name": group}, "selectRights": "extend"})
    if not ug:
        gid = z.call("usergroup.create", {"name": group, "rights": rights})["usrgrpids"][0]
        notes.append("user group created")
    else:
        gid = ug[0]["usrgrpid"]
        if sorted((r["id"], str(r["permission"])) for r in ug[0]["rights"]) != \
                sorted((r["id"], str(r["permission"])) for r in rights):
            z.call("usergroup.update", {"usrgrpid": gid, "rights": rights})
            notes.append("rights updated")
    roleid = z.call("role.get", {"output": ["roleid"], "filter": {"name": "User role"}})[0]["roleid"]
    u = z.call("user.get", {"output": ["userid", "roleid"], "filter": {"username": name}, "selectUsrgrps": ["usrgrpid"]})
    if not u:
        z.call("user.create", {"username": name, "name": "Grafana NOC", "passwd": C["zabbix_grafana_password"],
                               "roleid": roleid, "usrgrps": [{"usrgrpid": gid}]})
        notes.append("user created")
    else:
        if u[0]["roleid"] != roleid or [g["usrgrpid"] for g in u[0]["usrgrps"]] != [gid]:
            z.call("user.update", {"userid": u[0]["userid"], "roleid": roleid, "usrgrps": [{"usrgrpid": gid}]})
            notes.append("role/group updated")
        try:
            probe = Zabbix()
            probe.auth = probe.call("user.login", {"username": name, "password": C["zabbix_grafana_password"]})
            probe.call("user.logout")
        except ZabbixError:
            z.call("user.update", {"userid": u[0]["userid"], "passwd": C["zabbix_grafana_password"]})
            notes.append("password set from the inventory")
    print(f"user {name}: {', '.join(notes) if notes else 'up to date'}")


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
        z.call("user.update", {"userid": admin["userid"], "passwd": C["zabbix_admin_password"]})   # 6.0: no current_passwd
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
    names = sorted({t for h in want for t in h["templates"] + h.get("fallback", [])})
    tpl = {t["host"]: t["templateid"] for t in z.call("template.get", {"output": ["host"], "filter": {"host": names}})}
    for h in want:                                     # a template absent from this Zabbix version: its fallback
        if h.get("fallback") and any(t not in tpl for t in h["templates"]):
            print(f"host {h['name']}: {h['templates']} not found, fallback {h['fallback']}")
            h["templates"] = h["fallback"]
    names = sorted({t for h in want for t in h["templates"]})
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
    # 5. template triggers that do not apply to this design (inventory `off_triggers`): disabled on the host
    for w in want:
        if not w.get("off_triggers"):
            continue
        trg = z.call("trigger.get", {"output": ["description", "status"], "host": w["name"],
                                     "filter": {"description": w["off_triggers"]}})
        for t in trg:
            if t["status"] == "0":
                z.call("trigger.update", {"triggerid": t["triggerid"], "status": 1})
                print(f"trigger disabled on {w['name']}: {t['description']}")
    # 6. services: power, racks, web site, log collector (ZBX.6)
    apply_services(z, have)
    # 6b. read-only account of the Grafana data source (GRF.3)
    apply_grafana_user(z, have)
    # 7. maintenance for the hosts whose node is stopped
    off = sorted(stopped_nodes() & ({w["name"] for w in want} | set(MON["services"])))
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
    hosts = z.call("host.get", {"output": ["host", "maintenance_status"],
                                "groupids": [g["groupid"] for g in groups],
                                "selectInterfaces": ["type", "ip", "available", "error"],
                                "selectParentTemplates": ["host"], "sortfield": "host"})
    bad = 0
    print(f"{'host':12} {'interface':24} {'state':12} {'maintenance':11} templates")
    for h in hosts:
        maint = "yes" if h["maintenance_status"] == "1" else "-"
        tpls = ", ".join(t["host"] for t in h["parentTemplates"])
        if h["host"] in MON["services"]:      # no agent/SNMP: healthy when every item (web ones too) got a fresh value
            items = z.call("item.get", {"output": ["key_", "state", "lastclock", "lastvalue", "error"],
                                        "hostids": h["hostid"], "webitems": True})
            stale = [i["key_"] for i in items if not i["key_"].startswith("web.test.error")      # value on failure only
                     and (i["state"] != "0" or int(i["lastclock"]) < time.time() - 120)]
            if (stale or not items) and maint == "-":
                bad += 1
            shown = [i for i in items if i["key_"] in svc_keys(h["host"])]
            print(f"{h['host']:12} {'service ' + str(len(items)) + ' items':24} "
                  f"{('stale: ' + ', '.join(stale)) if stale else 'ok':12} {maint:11} "
                  + "  ".join(f"{i['key_']}={i['lastvalue']}" for i in shown))
            continue
        rows = [(("agent" if i["type"] == "1" else "snmp") + " " + i["ip"], AVAIL[i["available"]], i["error"])
                for i in h["interfaces"]]
        if not rows:    # 6.0 has no availability for active-only hosts: healthy when the agent sent data in the last 5 min
            items = z.call("item.get", {"output": ["lastclock"], "hostids": h["hostid"]})
            fresh = any(int(i["lastclock"]) > time.time() - 300 for i in items)
            rows = [("agent active", "available" if fresh else "unknown", "" if fresh else "no data for 5 min")]
        for where, state, err in rows:
            if state != "available" and maint == "-":
                bad += 1
            print(f"{h['host']:12} {where:24} {state:12} {maint:11} {tpls}" + (f"  ({err})" if err and maint == "-" else ""))
    print(f"\n{len(hosts)} hosts, {bad} running host(s) not available")
    # open problems of the service hosts (what the NOC Énergie row shows), dependent ones hidden like the frontend
    svc = [h["hostid"] for h in hosts if h["host"] in MON["services"]]
    if svc:
        trg = z.call("trigger.get", {"output": ["description", "priority", "lastchange"], "hostids": svc,
                                     "only_true": True, "monitored": True, "skipDependent": True,
                                     "filter": {"value": 1}, "selectHosts": ["host"], "sortfield": "priority",
                                     "sortorder": "DESC"})
        print(f"service problems ({len(trg)}):")
        for t in trg:
            sev = {v: k for k, v in SEVERITY.items()}[int(t["priority"])]
            print(f"  {time.strftime('%H:%M:%S', time.localtime(int(t['lastchange'])))} {sev:8} "
                  f"{t['hosts'][0]['host']}: {t['description']}")
    return 1 if bad else 0


def svc_keys(name):
    """Keys whose last value `status` prints for a service host (all of them except the raw JSON)."""
    s = MON["services"][name]
    keys = [i["key"] for i in s.get("items", [])] + (["icmpping"] if s.get("icmp") else [])
    return keys + ([f"web.test.fail[{s['web']['name']}]"] if s.get("web") else [])


if __name__ == "__main__":
    op = sys.argv[1] if len(sys.argv) > 1 else ""
    if op not in ("check", "apply", "status"):
        sys.exit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit({"check": check, "apply": apply, "status": status}[op]())
