"""truenas_setup – configure the TrueNAS SCALE backup NAS SRV-BCK-01 from the inventory (PLAN_04 NAS.4).

  python automation/truenas_setup.py check     API reachable, login, version, disks seen
  python automation/truenas_setup.py apply     pool, datasets, snapshots, pull key/tasks, services, UI (idempotent)
  python automation/truenas_setup.py status    pool health, datasets, snapshot tasks, services, network settings
  python automation/truenas_setup.py pull      run every rsync PULL task now and wait (NAS.5)

Transport: the TrueNAS JSON-RPC 2.0 API over a websocket (wss://10.40.0.11/api/current), opened through the lab proxy
(`python automation/lab_proxy.py start`) so the traffic enters the lab as ADMIN-WS and is filtered like any
administrator. Standard library only: a minimal websocket client (RFC 6455, client frames masked, text frames).
Login with `truenas_admin` / `credentials.truenas_admin_password`. Every `apply` step reads first, then changes only
what differs from the inventory (`truenas:` section).
"""
import base64
import json
import os
import socket
import ssl
import struct
import sys
import time
from pathlib import Path

import yaml

NET = Path(__file__).resolve().parents[1]
INV = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
T, C = INV["truenas"], INV["credentials"]
NAME = "SRV-BCK-01"
HOST = INV["servers"][NAME]["ip"]
PROXY = ("192.168.75.128", 1080)


# ------------------------------------------------------------------------------------------ transport
def socks_connect(host, port, timeout=30):
    s = socket.create_connection(PROXY, timeout=timeout)
    s.sendall(b"\x05\x01\x00")
    if s.recv(2) != b"\x05\x00":
        raise ConnectionError("SOCKS5 greeting refused - is lab_proxy.py started?")
    s.sendall(b"\x05\x01\x00\x01" + socket.inet_aton(host) + struct.pack("!H", port))
    reply = s.recv(10)
    if len(reply) < 2 or reply[1] != 0:
        raise ConnectionError(f"SOCKS5 connect to {host}:{port} failed")
    return s


class ApiError(RuntimeError):
    pass


class TrueNAS:
    """JSON-RPC 2.0 over wss, one connection for the whole run."""

    def __init__(self, host=HOST, path="/api/current", timeout=60):
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE        # lab self-signed certificate
        self.s = ctx.wrap_socket(socks_connect(host, 443, timeout), server_hostname=host)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.s.recv(4096)
            if not chunk:
                raise ConnectionError("websocket handshake: connection closed")
            head += chunk
        head, self.buf = head.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n")[0]:
            raise ConnectionError(f"websocket handshake refused: {head.splitlines()[0]!r}")
        self.n = 0

    def _recv(self, n):
        while len(self.buf) < n:
            chunk = self.s.recv(65536)
            if not chunk:
                raise ConnectionError("websocket closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def _send(self, text, op=1):
        data = text.encode() if isinstance(text, str) else text
        hdr = bytes([0x80 | op])
        ln = len(data)
        hdr += bytes([0x80 | ln]) if ln < 126 else (bytes([0x80 | 126]) + struct.pack("!H", ln) if ln < 65536
                                                    else bytes([0x80 | 127]) + struct.pack("!Q", ln))
        mask = os.urandom(4)
        self.s.sendall(hdr + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _frame(self):
        msg = b""
        while True:
            b0, b1 = self._recv(2)
            ln = b1 & 0x7F
            if ln == 126:
                ln = struct.unpack("!H", self._recv(2))[0]
            elif ln == 127:
                ln = struct.unpack("!Q", self._recv(8))[0]
            data = self._recv(ln)
            op = b0 & 0x0F
            if op == 9:                                   # ping -> pong
                self._send(data, op=10)
                continue
            if op == 8:
                raise ConnectionError("websocket closed by the server")
            msg += data
            if b0 & 0x80:
                return msg.decode()

    def call(self, method, params=None):
        self.n += 1
        self._send(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method,
                               "params": params if params is not None else []}))
        while True:
            r = json.loads(self._frame())
            if r.get("id") != self.n:                     # event notifications
                continue
            if "error" in r:
                e = r["error"]
                d = e.get("data") or {}
                raise ApiError(f"{method}: {d.get('reason') or e.get('message')}")
            return r["result"]

    def run(self, method, params=None, timeout=600):
        """Call a method that may return a job id (pool.create, service.control...) and wait for the job's end."""
        jid = self.call(method, params)
        if not isinstance(jid, int) or isinstance(jid, bool):
            return jid
        end = time.time() + timeout
        while time.time() < end:
            j = self.call("core.get_jobs", [[["id", "=", jid]]])[0]
            if j["state"] == "SUCCESS":
                return j["result"]
            if j["state"] in ("FAILED", "ABORTED"):
                raise ApiError(f"{method}: job {jid} {j['state']}: {j.get('error')}")
            time.sleep(2)
        raise ApiError(f"{method}: job {jid} still running after {timeout} s")

    def login(self):
        if not self.call("auth.login", [T["admin_user"], C["truenas_admin_password"]]):
            raise ApiError("auth.login refused")


def connect(retry=1, wait=10):
    for i in range(retry):
        try:
            c = TrueNAS()
            c.login()
            return c
        except (OSError, ConnectionError, ApiError):
            if i == retry - 1:
                raise
            time.sleep(wait)


# ------------------------------------------------------------------------------------------ desired state
SVC = INV["services"]
POOL = T["pool"]["name"]
SECRET = {"v3_password", "v3_privpassphrase"}          # write-only: not compared once the SNMPv3 user exists


def cron(expr):
    mi, h, dom, mo, dow = expr.split()
    return {"minute": mi, "hour": h, "dom": dom, "month": mo, "dow": dow, "begin": "00:00", "end": "23:59"}


def snapshot_tasks():
    out = []
    for s in T["snapshots"]:
        value, unit = s["lifetime"].split()
        out.append({"dataset": f"{POOL}/backups", "recursive": True, "lifetime_value": int(value),
                    "lifetime_unit": unit, "enabled": True, "naming_schema": f"{s['name']}-%Y-%m-%d_%H-%M",
                    "allow_empty": True, "exclude": [], "schedule": cron(s["schedule"])})
    return out


def wanted():
    allow = T["admin_from"]
    return {
        "system.general": {"timezone": INV["site"]["timezone"], "ui_httpsredirect": True, "ui_allowlist": allow,
                           "usage_collection": False, "ui_httpsprotocols": ["TLSv1.2", "TLSv1.3"]},
        "system.advanced": {"syslogservers": [{"host": SVC["syslog"], "transport": "UDP", "tls_certificate": None}],
                            "sysloglevel": "F_INFO", "fqdn_syslog": True, "login_banner": T["login_banner"],
                            "uploadcrash": False},
        "network.configuration": {"service_announcement": {"netbios": False, "mdns": False, "wsd": False}},
        "ssh": {"passwordauth": True, "tcpfwd": False, "weak_ciphers": [],
                "options": "AllowUsers " + " ".join(f"{T['admin_user']}@{n}" for n in allow)},
        "snmp": {"v3": True, "v3_username": C["snmpv3_user"], "v3_authtype": "SHA", "v3_password": C["snmpv3_auth"],
                 "v3_privproto": "AES", "v3_privpassphrase": C["snmpv3_priv"], "community": "",
                 "location": f"DC Casablanca {INV['servers'][NAME]['tia']}", "contact": "noc", "traps": False},
    }


def differs(have, want):
    return {k: v for k, v in want.items() if have.get(k) != v}


def data_disks(c):
    size = T["disks"]["data_gb"] * 2 ** 30
    free = sorted(d["name"] for d in c.call("disk.details")["unused"] if d["size"] == size)
    if len(free) < T["disks"]["data_count"]:
        raise SystemExit(f"need {T['disks']['data_count']} unused {T['disks']['data_gb']} GB disks, found {free}")
    return free[:T["disks"]["data_count"]]


# ------------------------------------------------------------------------------------------ actions
def check():
    c = connect()
    me = next(s for s in c.call("auth.sessions") if s.get("current"))
    pools = [p["name"] for p in c.call("pool.query")]
    unused = [f"{d['name']} {d['size'] // 2 ** 30} GB" for d in c.call("disk.details")["unused"] if d["size"] > 2 ** 30]
    print(f"{NAME}: {c.call('system.version')}, logged in as {T['admin_user']} from {me['origin']}")
    print(f"   pools {pools or 'none'}, unused disks {unused}")
    return 0


def apply_storage(c, done):
    if not c.call("pool.query", [[["name", "=", POOL]]]):
        disks = data_disks(c)
        c.run("pool.create", [{"name": POOL, "encryption": False,
                               "topology": {"data": [{"type": T["pool"]["layout"], "disks": disks}]}}], timeout=900)
        done.append(f"pool {POOL} created ({T['pool']['layout']} {disks})")
    have = {d["name"] for d in c.call("pool.dataset.query", [[], {"select": ["name"]}])}
    for ds in T["datasets"]:
        if f"{POOL}/{ds}" not in have:
            c.call("pool.dataset.create", [{"name": f"{POOL}/{ds}"}])
            done.append(f"dataset {POOL}/{ds}")
    tasks = c.call("pool.snapshottask.query")
    for t in snapshot_tasks():
        cur = next((x for x in tasks if x["dataset"] == t["dataset"] and x["naming_schema"] == t["naming_schema"]), None)
        if cur is None:
            c.call("pool.snapshottask.create", [t])
            done.append(f"snapshot task {t['naming_schema']}")
            continue
        d = {k: v for k, v in t.items() if k != "schedule" and cur.get(k) != v}
        if any(cur["schedule"].get(k) != v for k, v in t["schedule"].items()):
            d["schedule"] = t["schedule"]
        if d:
            c.call("pool.snapshottask.update", [cur["id"], d])
            done.append(f"snapshot task {t['naming_schema']}: {sorted(d)}")


def apply_settings(c, done):
    w = wanted()
    ntp = c.call("system.ntpserver.query")                 # the DC time server only
    for n in ntp:
        if n["address"] != SVC["ntp"]:
            c.call("system.ntpserver.delete", [n["id"]])
            done.append(f"ntp {n['address']} removed")
    if not any(n["address"] == SVC["ntp"] for n in ntp):
        c.call("system.ntpserver.create", [{"address": SVC["ntp"], "iburst": True, "prefer": True, "force": True}])
        done.append(f"ntp {SVC['ntp']} added")
    changed = set()
    for ns in ("system.advanced", "network.configuration", "ssh", "snmp"):
        have = c.call(f"{ns}.config")
        d = differs(have, w[ns])
        if ns == "snmp" and have.get("v3_username") == w[ns]["v3_username"]:
            d = {k: v for k, v in d.items() if k not in SECRET}
        if d:
            c.call(f"{ns}.update", [d])
            done.append(f"{ns}: {sorted(d)}")
            changed.add(ns)
    u = c.call("user.query", [[["username", "=", T["admin_user"]]]])[0]
    if not u["ssh_password_enabled"]:
        c.call("user.update", [u["id"], {"ssh_password_enabled": True}])
        done.append(f"user {T['admin_user']}: SSH password login allowed")
    for s in c.call("service.query"):                      # only the listed services run
        on = s["service"] in T["services_on"]
        if s["enable"] != on:
            c.call("service.update", [s["id"], {"enable": on}])
            done.append(f"service {s['service']} enable={on}")
        if on and s["state"] != "RUNNING":
            c.run("service.control", ["START", s["service"], {"silent": False}])
            done.append(f"service {s['service']} started")
        elif on and s["service"] in changed:
            c.run("service.control", ["RESTART", s["service"], {"silent": False}])
            done.append(f"service {s['service']} restarted")
        elif not on and s["state"] == "RUNNING":
            c.run("service.control", ["STOP", s["service"], {"silent": False}])
            done.append(f"service {s['service']} stopped")
    prefs = dict(((c.call("auth.me").get("attributes") or {}).get("preferences")) or {})
    if prefs.get("lifetime") != T["ui_session_timeout_min"] * 60:   # web UI preference "Session Timeout"
        prefs["lifetime"] = T["ui_session_timeout_min"] * 60
        c.call("auth.set_attribute", ["preferences", prefs])
        done.append(f"UI session timeout {T['ui_session_timeout_min']} min")
    d = differs(c.call("system.general.config"), w["system.general"])
    if d:                                                  # last: restarts the web server carrying this session
        c.call("system.general.update", [d])
        done.append(f"system.general: {sorted(d)}")
        try:
            c.call("system.general.ui_restart", [2])
        except (ConnectionError, OSError, ApiError):
            pass
    return bool(d)


PULL_KEY = NET / "configs" / "servers" / f"{NAME}.backup_pull.pub"
KEY_NAME = "nas-backup-pull"
SERVERS_DIR = f"/mnt/{POOL}/backups/servers"
CONFIGS_DIR = f"/mnt/{POOL}/backups/configs"


def pull_jobs():
    """[(source, remote path, local path, description)] from truenas.pull."""
    out = []
    for src, paths in T["pull"].items():
        for rp in paths:
            out.append((src, rp.rstrip("/") + "/", f"{SERVERS_DIR}/{src}/{rp.strip('/').replace('/', '_')}",
                        f"pull {src}:{rp}"))
    return out


def mkdirs(c, path):
    parts = path.split("/")
    for i in range(4, len(parts) + 1):                     # below /mnt/<pool>
        p = "/".join(parts[:i])
        try:
            c.call("filesystem.stat", [p])
        except ApiError:
            c.call("filesystem.mkdir", [{"path": p, "options": {"mode": "700"}}])


def apply_pull(c, done):
    """Key pair of the NAS, one SSH credential per source (host key pinned by a scan), one rsync PULL task per path."""
    creds = {k["name"]: k for k in c.call("keychaincredential.query")}
    if KEY_NAME not in creds:
        kp = c.call("keychaincredential.generate_ssh_key_pair")
        creds[KEY_NAME] = c.call("keychaincredential.create", [{"name": KEY_NAME, "type": "SSH_KEY_PAIR",
                                                                 "attributes": kp}])
        done.append(f"key pair {KEY_NAME} generated on the NAS (private key never leaves it)")
    pub = creds[KEY_NAME]["attributes"]["public_key"].strip() + f" {KEY_NAME}@{NAME.lower()}"
    if not PULL_KEY.exists() or PULL_KEY.read_text(encoding="utf-8").strip() != pub:
        PULL_KEY.write_text(pub + "\n", encoding="utf-8")
        done.append(f"public key -> {PULL_KEY.relative_to(NET)}")
    tasks = {t["desc"]: t for t in c.call("rsynctask.query")}
    sched = cron(T["pull_schedule"])
    sched.pop("begin"), sched.pop("end")
    for src, rp, lp, desc in pull_jobs():
        ip, cname = INV["servers"][src]["ip"], f"pull-{src}"
        if cname not in creds:
            try:
                hk = c.call("keychaincredential.remote_ssh_host_key_scan", [{"host": ip, "connect_timeout": 10}])
            except ApiError as e:
                print(f"   {src} ({ip}) not reachable for the host key scan, skipped: {e}")
                continue
            creds[cname] = c.call("keychaincredential.create", [{"name": cname, "type": "SSH_CREDENTIALS", "attributes": {
                "host": ip, "port": 22, "username": T["pull_user"], "private_key": creds[KEY_NAME]["id"],
                "remote_host_key": hk, "connect_timeout": 10}}])
            done.append(f"SSH credential {cname} ({T['pull_user']}@{ip}, host key pinned)")
        mkdirs(c, lp)
        want = {"path": lp, "user": "root", "mode": "SSH", "ssh_credentials": creds[cname]["id"], "remotepath": rp,
                "direction": "PULL", "desc": desc, "schedule": sched, "recursive": True, "times": True,
                "compress": True, "archive": True, "delete": True, "preserveperm": True, "delayupdates": True,
                "validate_rpath": False, "enabled": True}
        cur = tasks.get(desc)
        if cur is None:
            c.call("rsynctask.create", [want])
            done.append(f"rsync task '{desc}' -> {lp}")
            continue
        d = {k: v for k, v in want.items() if k not in ("ssh_credentials", "schedule", "validate_rpath") and cur.get(k) != v}
        if (cur.get("ssh_credentials") or {}).get("id", cur.get("ssh_credentials")) != want["ssh_credentials"]:
            d["ssh_credentials"] = want["ssh_credentials"]
        if any(cur["schedule"].get(k) != v for k, v in sched.items()):
            d["schedule"] = sched
        if d:
            c.call("rsynctask.update", [cur["id"], d])
            done.append(f"rsync task '{desc}': {sorted(d)}")
    # restores are read by the admin account (group builtin_administrators): the top folders only, the pulled files
    # keep their source permissions (secrets such as /etc/shadow stay root-only)
    for d in [SERVERS_DIR] + sorted({f"{SERVERS_DIR}/{src}" for src in T["pull"]}):
        st = c.call("filesystem.stat", [d])
        if st["group"] != "builtin_administrators" or st["mode"] & 0o777 != 0o750:
            c.run("filesystem.setperm", [{"path": d, "user": "root", "group": "builtin_administrators", "mode": "750"}])
            done.append(f"{d}: root:builtin_administrators 750")
    st = c.call("filesystem.stat", [CONFIGS_DIR])         # backup_configs.py writes here as the admin account
    if st["user"] != T["admin_user"]:
        c.run("filesystem.setperm", [{"path": CONFIGS_DIR, "user": T["admin_user"], "group": "root", "mode": "750"}])
        done.append(f"{CONFIGS_DIR} owned by {T['admin_user']}")


def pull():
    """Run every rsync task now and wait (NAS.5 test)."""
    c, rc = connect(), 0
    for t in c.call("rsynctask.query"):
        t0 = time.time()
        try:
            c.run("rsynctask.run", [t["id"]], timeout=1800)
            print(f"   {t['desc']}: SUCCESS in {time.time() - t0:.0f} s")
        except ApiError as e:
            rc = 1
            print(f"   {t['desc']}: FAILED {str(e)[:400]}")
    return rc


def apply():
    c, done = connect(), []
    apply_storage(c, done)
    apply_pull(c, done)
    ui_restarted = apply_settings(c, done)
    print(f"{NAME}: {len(done)} change(s)")
    for x in done:
        print(f"   {x}")
    if ui_restarted:
        time.sleep(15)
    return status()


def status():
    c, out = connect(retry=6), []
    for p in c.call("pool.query"):
        vdevs = " ".join(f"{v['type']}({len(v['children'])} disks)" for v in p["topology"]["data"])
        out.append(f"pool {p['name']}: {p['status']}, healthy={p['healthy']}, {vdevs}")
    ds = c.call("pool.dataset.query", [[["pool", "=", POOL]], {"select": ["name"]}])
    out.append("datasets " + ", ".join(d["name"] for d in ds))
    for t in c.call("pool.snapshottask.query"):
        s = t["schedule"]
        out.append(f"snapshot task {t['dataset']} {t['naming_schema']} '{s['minute']} {s['hour']} {s['dom']} "
                   f"{s['month']} {s['dow']}' keep {t['lifetime_value']} {t['lifetime_unit']} "
                   f"recursive={t['recursive']} enabled={t['enabled']}")
    out.append(f"snapshots on {POOL}: {c.call('pool.snapshot.query', [[['pool', '=', POOL]], {'count': True}])}")
    for t in c.call("rsynctask.query"):
        j = t.get("job") or {}
        s = t["schedule"]
        out.append(f"rsync {t['direction']} '{t['desc']}' -> {t['path']} '{s['minute']} {s['hour']} {s['dom']} "
                   f"{s['month']} {s['dow']}' last={j.get('state', 'never')}")
    out.append("services " + ", ".join(f"{s['service']}={'on' if s['enable'] else 'off'}/{s['state']}"
                                        for s in c.call("service.query")))
    g, a = c.call("system.general.config"), c.call("system.advanced.config")
    sh, sn = c.call("ssh.config"), c.call("snmp.config")
    out.append(f"UI https_redirect={g['ui_httpsredirect']} allowlist={g['ui_allowlist']} tls={g['ui_httpsprotocols']} "
               f"timezone={g['timezone']} usage_collection={g['usage_collection']}")
    out.append(f"syslog {[x['host'] + '/' + x['transport'] for x in a['syslogservers']]} level={a['sysloglevel']}")
    out.append("ntp " + ", ".join(n["address"] for n in c.call("system.ntpserver.query")))
    out.append(f"ssh passwordauth={sh['passwordauth']} tcpfwd={sh['tcpfwd']} options='{sh['options']}'")
    out.append(f"snmp v3={sn['v3']} user={sn['v3_username']} auth={sn['v3_authtype']} priv={sn['v3_privproto']} "
               f"v2c_community={'none' if not sn['community'] else 'SET'}")
    prefs = (c.call("auth.me").get("attributes") or {}).get("preferences") or {}
    out.append(f"UI session timeout {prefs.get('lifetime', 'default')} s")
    for s in c.call("initshutdownscript.query"):
        out.append(f"init script {s['id']} {s['when']} enabled={s['enabled']}: "
                   f"{(s.get('command') or s.get('script') or '')[:100]}")
    print(f"{NAME}:")
    for line in out:
        print(f"   {line}")
    return 0


if __name__ == "__main__":
    act = sys.argv[1] if len(sys.argv) > 1 else "status"
    sys.exit({"check": check, "apply": apply, "status": status, "pull": pull}[act]())
