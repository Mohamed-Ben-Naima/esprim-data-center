"""verify_lab – run the Test the Lab checks that the running profile allows and compare each output with the expected
value (report/tests/tests.yaml). One line per test: PASS, FAIL (with what was seen) or N/A (a node it needs is off).

  python automation/verify_lab.py                 every non-disruptive test of the running set (about 6 min)
  python automation/verify_lab.py --failover      + failover measurements FW-14/FW-16 (core and firewall, ~15 min)
  python automation/verify_lab.py --disruptive   + PRV-02/PRV-03 (LEAF-B2 locked out ~4 min: never just before the demo)
  python automation/verify_lab.py --only CORE,FW  groups or test ids
  python automation/verify_lab.py --save          -> report/evidence/verify_lab.txt (dated header)

Not run here on purpose: FW-09 (redeploys the firewalls), FW-11 (CARP demotion),
LOG-06/LOG-07 (image rebuild, forced rotation), DEMO-01/02 (cold cycle: run lab_down.py / lab_up.py themselves), and
the tests that need a person at a browser or console (FW-05 login, WT-04 desktop, PRV-07 code entry).
Exit 1 if one test fails.
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import gns3vm  # noqa: E402
import labctl  # noqa: E402
from adminws import ssh_batch  # noqa: E402

NET = Path(__file__).resolve().parents[1]
HERE = Path(__file__).parent
INV = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
C = INV["credentials"]
PROXY = "192.168.75.128:1080"
ROWS = []


def all_of(*pats):
    return lambda out: all(re.search(p, out, re.M | re.S) for p in pats)


def count(pat, n):
    return lambda out: len(re.findall(pat, out, re.M)) == n


# (id, needs, kind, target, command, check, what the check means)
# kind: ssh (alias from ADMIN-WS), dock (docker exec in a container), vm (GNS3 VM shell), host (Windows shell),
#       py (python automation/<script>)
T = [
    ("PLT-01", [], "host", None, "ping -n 2 192.168.75.128", all_of(r"192\.168\.75\.128.*TTL="), "2 replies"),
    ("PLT-02", [], "py", None, "labctl.py status", lambda o: len([l for l in o.splitlines() if re.search(r"started|stopped", l)]) == 32,
     "32 nodes listed"),
    ("PLT-03", [], "vm", None, "-f check_disks.sh", all_of(r"images with problems: 0"), "images with problems: 0"),
    ("PLT-04", ["!SRV-BASTION", "!SRV-CMP-01"], "py", None, "fsck_servers.py SRV-BASTION SRV-CMP-01",
     count(r"e2fsck exit 0", 2), "e2fsck exit 0 twice (nodes stopped)"),
    ("PLT-05", [], "host", None, "powercfg /query SCHEME_CURRENT 0012ee47-9041-4b5d-9b77-535fba8b1442 "
     "6738e2c4-e8a5-4a42-b16a-e040e769756e & powercfg /query SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 "
     "48e6b7a6-50f5-4782-a5d4-53bb8f07e226",
     lambda o: len(re.findall(r"(?:AC|alternatif)[^\n]*: 0x00000000", o)) == 2,
     "AC index 0x00000000 on both"),
    ("EDGE-01", ["EDGE-A", "ISP-A", "ISP-B"], "ssh", "edge-a", "show ip bgp summary",
     lambda o: all(re.search(rf"^{ip}\s.*\s\d+\s*$", o, re.M) for ip in ("198.51.100.1", "203.0.113.5")),
     "ISP-A (198.51.100.1) and ISP-B (203.0.113.5) established, a prefix count each"),
    ("EDGE-03", ["EDGE-A"], "ssh", "edge-a", "show standby brief | include Gi0/3", all_of(r"Active.*10\.254\.1\.6"),
     "Gi0/3 group 1 Active, VIP 10.254.1.6"),
    ("EDGE-04", ["EDGE-A"], "con", "EDGE-A", "ping 8.8.8.8 repeat 5", all_of(r"Success rate is (100|80) percent"),
     "Internet reached (100 %, 80 % when the first ARP is lost)"),
    ("EDGE-05", ["EDGE-A", "EDGE-B"], "ssh", "edge-a", "show ip ospf neighbor", all_of(r"FULL"), "OSPF neighbour(s) FULL"),
    ("EDGE-06", ["ISP-A", "EDGE-A"], "dock", "ISP-A", "vtysh -c 'show ip bgp summary'",
     all_of(r"\d\d:\d\d:\d\d\s+1\s+\d+\s+EDGE-A"), "EDGE-A session up, 1 prefix received"),
    ("EDGE-07", ["ISP-A"], "dock", "ISP-A", "ping -c 2 8.8.8.8", all_of(r" 0% packet loss"), "0% packet loss"),
    ("FW-01", ["FW-A"], "ssh", "fw-a", "ifconfig | grep carp:", count(r"carp: MASTER", 5), "5 x MASTER"),
    ("FW-02", ["FW-B"], "ssh", "fw-b", "ifconfig | grep carp:", count(r"carp: BACKUP", 5), "5 x BACKUP"),
    ("FW-03", ["FW-A", "FW-B"], "ssh", "fw-a", "ifconfig pfsync0 | grep syncdev",
     all_of(r"syncdev: em2 syncpeer: 10\.254\.3\.2"), "syncdev em2, syncpeer FW-B"),
    ("FW-03b", ["FW-B"], "ssh", "fw-b", "ifconfig pfsync0 | grep syncdev",
     all_of(r"syncdev: em2 syncpeer: 10\.254\.3\.1"), "syncdev em2, syncpeer FW-A"),
    ("FW-04", ["FW-A", "EDGE-A"], "ssh", "fw-a", "ping -c 2 8.8.8.8", all_of(r" 0\.0% packet loss"), "0.0% packet loss"),
    ("FW-05", ["FW-A", "FW-B", "ADMIN-WS"], "host", None,
     f"curl --socks5 {PROXY} -sk -m 10 https://10.90.0.1/ & curl --socks5 {PROXY} -sk -m 10 https://10.90.0.3/",
     lambda o: o.count("pfSense") >= 2 and "wizard" not in o.lower(), "login page of both firewalls (no wizard)"),
    ("FW-06", ["ISP-A", "EDGE-A", "FW-A", "SRV-WEB-01"], "dock", "ISP-A",
     "printf 'GET /health HTTP/1.0\\r\\n\\r\\n' | nc -w 5 192.0.2.80 80", all_of(r"200 OK", r"OK SRV-WEB-01"),
     "200 OK, OK SRV-WEB-01 (public DNAT)"),
    ("FW-07", ["FW-A", "FW-B"], "py", None, "fw_audit.py", all_of(r"^0 difference\(s\)"), "0 difference(s)"),
    ("FW-08", ["FW-A", "FW-B"], "ssh2", ("fw-a", "fw-b"), "pfctl -sr | wc -l",
     lambda o: len(set(o.split())) == 1 and o.split()[0] != "0", "same number of pf lines on both"),
    ("FW-12", ["FW-A", "FW-B"], "py", None, "fw_audit.py", count(r"web session timeout: 15 min", 2), "15 min on both"),
    ("FW-15", ["CORE-A", "CORE-B"], "sshm", "core-a",
     "show standby brief | include Vl902 ;; show running-config interface Port-channel1 | include allowed",
     lambda o: re.search(r"Vl902.*Active", o) and "902" not in o.split("allowed")[-1], "Vl902 Active, 902 not on Po1"),
    ("CORE-01", ["CORE-A", "CORE-B"], "ssh", "core-a", "show standby brief | include Vl",
     lambda o: all(re.search(rf"Vl{v}\s.*Active", o) for v in (20, 40, 60, 100, 902))
     and all(re.search(rf"Vl{v}\s.*Standby", o) for v in (30, 70, 80)), "Active 20/40/60/100/902, Standby 30/70/80"),
    ("CORE-02", ["CORE-A", "CORE-B"], "ssh", "core-b", "show standby brief | include Vl",
     lambda o: all(re.search(rf"Vl{v}\s.*Active", o) for v in (30, 70, 80))
     and all(re.search(rf"Vl{v}\s.*Standby", o) for v in (20, 40, 60, 100, 902)), "Active 30/70/80, Standby the others"),
    ("CORE-03", ["CORE-A", "CORE-B"], "ssh", "core-a", "show etherchannel summary | begin Group",
     all_of(r"Po1\(SU\)", r"Gi0/2\(P\)", r"Gi0/3\(P\)"), "Po1(SU) Gi0/2(P) Gi0/3(P)"),
    ("CORE-04", ["CORE-A", "CORE-B"], "ssh", "core-b", "show ip ospf neighbor", count(r"FULL", 2), "2 x FULL"),
    ("CORE-05", ["CORE-A", "CORE-B"], "ssh", "core-a", "show spanning-tree root",
     lambda o: all(re.search(rf"^VLAN0+{v}\s.*\s(Po1)\s*$", o, re.M) for v in (30, 70, 80))
     and not any(re.search(rf"^VLAN0+{v}\s.*\s(Po1|Gi\S+)\s*$", o, re.M) for v in (20, 40, 60, 100, 998)),
     "root for 20/40/60/100/998, root port Po1 for 30/70/80"),
    ("CORE-06", ["CORE-A", "FW-A", "EDGE-A"], "con", "CORE-A", "ping 8.8.8.8 source vlan20 repeat 5",
     all_of(r"Success rate is (100|80) percent", r"10\.20\.0\.2"), "Internet from VLAN 20, source 10.20.0.2"),
    ("CORE-07", ["LEAF-B1", "CORE-A", "CORE-B"], "ssh", "leaf-b1", "show interfaces trunk | begin Vlans in spanning",
     all_of(r"Gi0/0\s+20,40,60,100", r"Gi0/1\s+30,70,80"), "Gi0/0 20,40,60,100; Gi0/1 30,70,80"),
    ("CORE-07b", ["LEAF-B2", "CORE-A", "CORE-B"], "ssh", "leaf-b2", "show interfaces trunk | begin Vlans in spanning",
     all_of(r"Gi0/0\s+20,40,60,100", r"Gi0/1\s+30,70,80"), "same on LEAF-B2"),
    ("LOG-01", ["SYSLOG"], "dock", "SYSLOG", "ls /var/log/remote/",
     lambda o: "all.log" in o and len(re.findall(r"10\.10\.0\.\d+", o)) >= 5, "one file per source + all.log"),
    ("LOG-02", ["SYSLOG"], "dock", "SYSLOG", "tail -1 /var/log/remote/all.log; date -Iseconds",
     lambda o: abs(_ts(o.splitlines()[0][:19]) - _ts(o.splitlines()[-1][:19])) < 300, "last line less than 5 min old"),
    ("LOG-03", ["SYSLOG"], "py", None, "syslog_audit.py", lambda o: "MISSING" not in o and " OK " in o,
     "marker OK for every running source"),
    ("LOG-04", ["SYSLOG", "ADMIN-WS"], "py", None, "log_viewer.py search LOGIN --src CORE-A",
     lambda o: "Traceback" not in o and len(o.strip()) > 0, "login + search answer"),
    ("LOG-05", ["SYSLOG", "ADMIN-WS", "CORE-A", "FW-A", "SRV-WEB-01"], "py", None, "log_viewer.py demo",
     all_of(r"LOGIN_FAILED", r"CONFIG_I", r"10\.50\.0\.11,10\.10\.0\.21"), "the 3 demo events found"),
    ("WT-01", ["ADMIN-WS"], "dock", "ADMIN-WS", "for c in ssh firefox-esr curl snmpget dig nc; do command -v $c; done",
     lambda o: len(o.split()) == 6 and o.split()[0] == "/usr/local/bin/ssh", "six paths, ssh = logging wrapper"),
    ("WT-02", ["CORE-A", "EDGE-A", "LEAF-B1"], "ssh3", ("core-a", "edge-a", "leaf-b1"), "show version | include uptime",
     all_of(r"CORE-A uptime", r"EDGE-A uptime", r"LEAF-B1 uptime"), "uptime of the 3 devices"),
    ("WT-03", ["FW-A"], "ssh", "fw-a", "hostname; pfctl -sr | wc -l", all_of(r"fw-a\.dc\.casa\.lab", r"^\s*\d{2,}\s*$"),
     "hostname + rule count"),
    ("WT-05", ["SYSLOG", "ADMIN-WS"], "dock", "SYSLOG", "grep admin-ssh /var/log/remote/all.log | tail -2",
     all_of(r"session (start|end)"), "session lines of the wrapper"),
    ("WT-06", ["ADMIN-WS"], "dock", "ADMIN-WS", "dc-hosts", lambda o: len(re.findall(r"^\s*ssh \S+(?: \(\w+\))?\s+\S+@\S+", o, re.M)) >= 10,
     "one ssh line per equipment"),
    ("WT-07", ["ADMIN-WS", "SYSLOG"], "vm", None,
     "for n in ADMIN-WS SYSLOG; do docker exec $(docker ps -q --filter name=$n) date +%z; done",
     lambda o: "LIMIT" if o.split() == ["+0000", "+0100"] else len(set(o.split())) == 1,
     "same offset on both (known limit: ADMIN-WS +0000 with tzdata 2026c, Morocco back to UTC+0 on 20 Sep 2026; "
     "SYSLOG +0100 with older tz data)"),
    ("ACC-02", ["LEAF-B2"], "ssh", "leaf-b2", "show ip ssh", all_of(r"SSH Enabled - version 2\.0"), "SSH v2 enabled"),
    ("ACC-04", ["SYSLOG"], "dock", "SYSLOG", "grep filterlog /var/log/remote/all.log | grep ',10.50.0.11,10.10.0' | tail -2",
     all_of(r"block,in.*10\.50\.0\.11,10\.10\.0\.\d+"), "DMZ -> MGMT blocks logged"),
    ("PRV-04", ["LEAF-B1"], "ssh", "leaf-b1", "show line vty 0 | begin Timeouts", all_of(r"00:10:00"), "Idle EXEC 00:10:00"),
    ("PWR-01", ["BMS-SIM", "ADMIN-WS"], "dock", "ADMIN-WS",
     "curl -s 'http://10.70.0.12:8080/api/set?UTILITY-A=DOWN&UPS-A=DOWN&GENERATOR=DOWN'",
     lambda o: _j(o)["paths"] == {"A": "DOWN", "B": "POWERED"} and _j(o)["path_load_pct"]["B"] == 94.2,
     "A DOWN, B POWERED at 94.2 %"),
    ("PWR-02", ["SRV-DCIM-01", "ADMIN-WS"], "dock", "ADMIN-WS", "sleep 15; curl -s http://10.70.0.11:8080/api/summary",
     lambda o: _j(o)["by_status"].get("DEGRADED") == 96 and _j(o).get("bms_status") == "CRITICAL",
     "DEGRADED 96, bms CRITICAL"),
    ("PWR-03", ["SYSLOG", "BMS-SIM"], "dock", "SYSLOG", "grep -i bms /var/log/remote/all.log | tail -3",
     all_of(r"(?i)bms"), "BMS alarm lines in the log"),
    ("PWR-04", ["BMS-SIM", "SRV-DCIM-01", "ADMIN-WS"], "dock", "ADMIN-WS",
     "curl -s http://10.70.0.12:8080/api/reset >/dev/null; sleep 15; curl -s http://10.70.0.12:8080/api/state; echo; "
     "curl -s http://10.70.0.11:8080/api/summary",
     lambda o: '"A": "POWERED"' in o and '"B": "POWERED"' in o and '"OK": 96' in o, "both POWERED, OK 96"),
    ("MON-01", ["SRV-MON-01"], "ssh", "srv-mon-01", "systemctl is-active zabbix-server nginx mariadb php7.4-fpm",
     count(r"^active$", 4), "active x4"),
    ("MON-02", ["SRV-MON-01"], "ssh", "srv-mon-01", "df -h /", all_of(r"7\.8G"), "size 7.8G"),
    ("MON-03", ["SRV-MON-01"], "ssh", "srv-mon-01", "curl -s -m 5 -o /dev/null -w '%{http_code}\\n' http://127.0.0.1/; "
     "curl -s -m 5 -o /dev/null -w '%{http_code}\\n' http://127.0.0.1:3000/login", count(r"^200$", 2), "200, 200"),
    ("MON-04", ["SRV-MON-01", "ADMIN-WS"], "py", None, "check_dashboard.py", all_of(r"0 empty"), "0 empty panel"),
    ("MON-05", ["SRV-MON-01", "BMS-SIM", "ADMIN-WS"], "py", None, "power_test.py",
     lambda o: re.search(r"after: [\d.]+ s", o) and re.search(r"resolved after: [\d.]+ s", o),
     "power problems raised, then resolved (seconds measured)"),
    ("WEB-01", ["ADMIN-WS"], "py", None, "lab_proxy.py status", all_of(r"1080"), "proxy listening on 1080"),
    ("WEB-02", ["ADMIN-WS", "FW-A", "SRV-MON-01", "BMS-SIM", "SRV-DCIM-01", "SYSLOG"], "host", None,
     " & ".join(f'curl --socks5 {PROXY} -sk -m 10 -o NUL -w "%{{http_code}} " {u}' for u in
                ("https://10.90.0.1/", "http://10.60.0.11/", "http://10.60.0.11:3000/login", "http://10.70.0.12:8080/",
                 "http://10.70.0.11:8080/", "https://10.50.0.11/health")),
     lambda o: o.split() == ["200"] * 6, "200 x6"),
    ("WEB-02b", ["ADMIN-WS", "SYSLOG"], "host", None, f'curl --socks5 {PROXY} -sk -m 10 -o NUL -w "%{{http_code}}" https://10.60.0.12/',
     all_of(r"^303"), "log viewer: 303 to its login page"),
    ("WEB-03", ["SRV-MON-01", "ADMIN-WS"], "py", None, "zabbix_setup.py check", all_of(r"server running: yes"),
     "API login, server running"),
    ("WEB-04", ["SRV-MON-01", "ADMIN-WS"], "host", None,
     f'curl --socks5 {PROXY} -s -m 10 -u admin:{INV["credentials"].get("grafana_admin_password", "")} http://10.60.0.11:3000/api/org',
     all_of(r'"name":"Main Org\."'), "Main Org."),
    ("WEB-05", ["CCTV-SIM", "ADMIN-WS"], "host", None,
     f'curl --socks5 {PROXY} -s -m 8 -o NUL -w "%{{http_code}}" http://10.80.0.11:8080/', all_of(r"^000"),
     "000: 8080 open to VLAN 70 only"),
    ("DEMO-03", [], "py", None, "demo_check.py", all_of(r"^(\d+)/\1 checks OK"), "every check OK"),
    ("DEMO-04", [], "py", None, "cisco_heal.py --check", lambda o: "FAIL" not in o and "ok" in o, "ssh ok, snmpv3 ok"),
    ("DEMO-05", ["ADMIN-WS"], "py", None, "flow_matrix.py --running-only",
     all_of(r" 0 deviation\(s\)", r"of which 0 without a log trace"), "0 deviation, every denied flow traced"),
]
# --disruptive: LEAF-B2 refuses SSH for 2 min (4 min of host time) after this; run it last, never just before the demo
DISRUPTIVE = [
    ("PRV-02", ["LEAF-B2", "ADMIN-WS"], "dock", "ADMIN-WS",
     "printf '#!/bin/sh\\necho not-the-password\\n' > /tmp/apw.sh; chmod 700 /tmp/apw.sh; for i in 1 2; do "
     "SSH_ASKPASS=/tmp/apw.sh SSH_ASKPASS_REQUIRE=force DISPLAY=:0 timeout 30 setsid -w ssh -o NumberOfPasswordPrompts=3 "
     "-o LogLevel=ERROR leaf-b2 show clock </dev/null; done; rm -f /tmp/apw.sh; sleep 3; "
     "nc -z -w 5 10.10.0.34 22 && echo port-open || echo port-refused",
     all_of(r"port-refused"), "SSH refused after 6 wrong passwords (quiet mode)"),
    ("PRV-03", ["SYSLOG", "LEAF-B2"], "dock", "SYSLOG",
     "sleep 5; grep -hE 'LOGIN_FAILED|QUIET_MODE_ON' /var/log/remote/10.10.0.34_*.log | tail -3",
     all_of(r"LOGIN_FAILED.*10\.90\.0\.12", r"QUIET_MODE_ON"), "LOGIN_FAILED from 10.90.0.12, then QUIET_MODE_ON"),
]
FAILOVER = [
    ("FW-14", ["CORE-A", "CORE-B", "FW-A", "BMS-SIM"], "py", None, "fw_lan_failover.py --core CORE-A --down 40 --up 200",
     lambda o: _outage(o, "fault") <= 6, "core failure outage <= 6 s"),
    ("FW-16", ["FW-A", "FW-B", "BMS-SIM"], "py", None, "fw_lan_failover.py --core FW-A --down 60 --up 300",
     lambda o: _outage(o, "fault") <= 5, "firewall failover outage <= 5 s"),
    ("CMP-03", ["SRV-CMP-01", "SRV-CMP-02", "SRV-WEB-01"], "py", None, "fw_lan_failover.py --core SRV-CMP-01 --down 60 --up 150",
     lambda o: _outage(o, "fault") <= 5 and "VIP served by srv-cmp-02" in o, "VIP moves, outage <= 5 s"),
]


def _ts(s):
    return time.mktime(time.strptime(s, "%Y-%m-%dT%H:%M:%S"))


def _j(o):
    return json.loads(o[o.index("{"):o.rindex("}") + 1])


def _outage(o, label):
    m = re.findall(rf"{label}: outage from .* = ([\d.]+) s", o)
    return max(map(float, m)) if m else 0.0


def run(t, st):
    tid, needs, kind, target, cmd, check, what = t
    off = [n for n in needs if not n.startswith("!") and st.get(n) != "started"]
    on = [n[1:] for n in needs if n.startswith("!") and st.get(n[1:]) == "started"]
    if off or on:
        return "N/A", (f"needs {', '.join(off)} started" if off else f"needs {', '.join(on)} stopped")
    if kind == "host":
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="cp850", errors="replace", timeout=300)
        out = r.stdout + r.stderr
    elif kind == "py":
        r = subprocess.run([sys.executable, str(HERE / cmd.split()[0]), *cmd.split()[1:]], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1800, cwd=NET,
                           env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
        out = r.stdout + r.stderr
    elif kind == "vm":
        out = (gns3vm.run(open(HERE / cmd.split()[1]).read(), sudo=True) if cmd.startswith("-f ") else gns3vm.run(cmd))
    elif kind == "dock":
        import base64
        b = base64.b64encode(cmd.encode()).decode()
        out = gns3vm.run(f"docker exec $(docker ps -q --filter name={target}) sh -c \"$(echo {b} | base64 -d)\" 2>&1",
                         sudo=True)
    elif kind == "con":     # IOS console: an SSH exec session ends before a ping has printed its result
        u, pw, en = labctl.creds()
        api = labctl.Gns3()
        p = api.project()
        with labctl.Console.for_node(api, p, target) as c:
            ios = labctl.Ios(c, u, pw, en)
            ios.login(timeout=120)
            out = ios.cmd(cmd, 60)
    elif kind == "sshm":    # several IOS commands (an IOS exec session takes one), " ;; " separated
        out = "\n".join(o for _, o in ssh_batch([(target, c) for c in cmd.split(" ;; ")], timeout=90))
    else:   # ssh, ssh2, ssh3
        aliases = [target] if kind == "ssh" else list(target)
        out = "\n".join(o for _, o in ssh_batch([(a, cmd) for a in aliases], timeout=90))
    try:
        ok = check(out)
        ok = ok if ok == "LIMIT" else bool(ok)
    except Exception as e:  # noqa: BLE001
        ok, out = False, f"{out}\n(check error: {e})"
    seen = " / ".join(l.strip() for l in out.strip().splitlines() if l.strip())[-220:]
    if ok == "LIMIT":
        return "LIMIT", what
    return ("PASS" if ok else "FAIL"), (what if ok else f"expected {what}; seen: {seen}")


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    only = set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv else None
    tests = T + (FAILOVER if "--failover" in argv else []) + (DISRUPTIVE if "--disruptive" in argv else [])
    if only:
        tests = [t for t in tests if t[0] in only or t[0].split("-")[0] in only]
    api = labctl.Gns3()
    p = api.project()
    st = {n["name"]: n["status"] for n in api.nodes(p)}
    t0 = time.time()
    print(time.strftime("verify_lab %Y-%m-%d %H:%M:%S"), f"- {sum(1 for v in st.values() if v == 'started')} nodes started")
    for t in tests:
        res, info = run(t, st)
        line = f"{res:4} {t[0]:8} {info}"
        print(line, flush=True)
        ROWS.append((res, line))
    n = {k: sum(1 for r, _ in ROWS if r == k) for k in ("PASS", "FAIL", "N/A", "LIMIT")}
    summary = (f"{n['PASS']} PASS, {n['FAIL']} FAIL, {n['LIMIT']} known limit, {n['N/A']} N/A (node off in this profile)"
               f" in {time.time() - t0:.0f} s")
    print(summary)
    if "--save" in argv:
        (NET / "report" / "evidence" / "verify_lab.txt").write_text(
            time.strftime("# verify_lab.py %Y-%m-%d %H:%M:%S") + f" {' '.join(argv)}\n" + "\n".join(l for _, l in ROWS)
            + "\n" + summary + "\n", encoding="utf-8")
    return 1 if n["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
