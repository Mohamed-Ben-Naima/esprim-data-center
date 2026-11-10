"""demo_check – is the lab ready for the demo? One line per check, OK or FAIL with what to do (PLAN_03 S6).

  python automation/demo_check.py [--profile demo] [--save]     (--save -> report/evidence/demo_s6_check.txt)

Checks, in the order of the demo:
  nodes        every node of the profile is started (lab_up.OFF)
  resources    GNS3 VM swap < 200 MB and >= 500 MB available, host free RAM >= 0.5 GB
  proxy        lab proxy answers (SOCKS5 on 192.168.75.128:1080)
  SRV-MON-01   mariadb, zabbix-server, nginx, php-fpm, grafana-server active
  zabbix       zabbix_setup.py status: every running host available, stopped ones in maintenance
  grafana      check_dashboard.py: no empty panel, deployed dashboard = noc.json
  power        BMS-SIM nominal (paths A and B POWERED, only the 2 load warnings of the design margin)
  syslog       syslog_audit.py: marker found for every running source
  viewer       log viewer login + search over HTTPS
  web          DMZ site https://10.50.0.11/health from ADMIN-WS
  loop guard   no port in loop-inconsistent state now on the cores and leafs (blocks logged in 15 min shown for info)
  redundancy   HSRP pairs complete on both cores (no "unknown" peer), CARP 5 MASTER on FW-A and 5 BACKUP on FW-B
Exit code 1 if one check fails.
"""
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gns3vm  # noqa: E402
import labctl  # noqa: E402

NET = Path(__file__).resolve().parents[1]
HERE = Path(__file__).parent
ROWS = []


def row(name, ok, info, fix=""):
    line = f"{'OK  ' if ok else 'FAIL'} {name:11} {info}" + ("" if ok or not fix else f"\n     -> {fix}")
    print(line, flush=True)
    ROWS.append((ok, line))


def script(*args, timeout=600):
    r = subprocess.run([sys.executable, str(HERE / args[0]), *args[1:]], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout, cwd=NET)
    return r.returncode, (r.stdout + r.stderr).strip().splitlines()


def main(argv):
    profile = argv[argv.index("--profile") + 1] if "--profile" in argv else "demo"
    from lab_up import OFF, STAGES
    t0 = time.time()
    print(time.strftime("demo_check %Y-%m-%d %H:%M:%S") + f", profile {profile}")
    api = labctl.Gns3()
    p = api.project()
    st = {n["name"]: n["status"] for n in api.nodes(p)}
    want = [n for _, names in STAGES for n in names if n not in OFF[profile]]
    off = [n for n in want if st.get(n) != "started"]
    row("nodes", not off, f"{len(want) - len(off)}/{len(want)} started" + (f", stopped: {', '.join(off)}" if off else ""),
        "python automation/labctl.py start " + " ".join(off))

    v = gns3vm.run("free -m | awk '/Mem:/{print $7} /Swap:/{print $3}'").split()
    host = subprocess.run(["powershell", "-NoProfile", "-Command",
                           "[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)"],
                          capture_output=True, text=True).stdout.strip().replace(",", ".")
    avail, swap = int(v[0]), int(v[1])
    ok = swap < 200 and avail >= 500 and float(host or 0) >= 0.5
    row("resources", ok, f"GNS3 VM available {avail} MB, swap {swap} MB; host free {host} GB",
        "flush swap: python automation/gns3vm.py --sudo \"swapoff -a && swapon -a\"; close other apps on the PC")

    try:
        s = socket.create_connection(("192.168.75.128", 1080), timeout=5)
        s.sendall(b"\x05\x01\x00")
        ok = s.recv(2) == b"\x05\x00"
        s.close()
    except OSError:
        ok = False
    row("proxy", ok, "SOCKS5 192.168.75.128:1080", "python automation/lab_proxy.py start")

    from adminws import ssh_batch
    svcs = "mariadb zabbix-server nginx php7.4-fpm grafana-server"
    checks = [("srv-mon-01", f"systemctl is-active {svcs} | tr '\\n' ' '"),
              ("srv-mon-01", "curl -s -m5 http://10.70.0.12:8080/api/state"),
              ("srv-mon-01", "curl -sk -m5 https://10.50.0.11/health")]
    res = ssh_batch(checks)
    states = res[0][1].split()
    ok = states == ["active"] * 5
    row("SRV-MON-01", ok, " ".join(f"{n}={s}" for n, s in zip(svcs.split(), states)) or f"no answer (rc {res[0][0]})",
        "wait 2 min after boot; else on SRV-MON-01: sudo systemctl restart mariadb zabbix-server grafana-server")

    rc, out = script("zabbix_setup.py", "status")
    summary = next((l for l in out if "hosts," in l), out[-1] if out else "no output")
    probs = [l.strip() for l in out[out.index(next((l for l in out if l.startswith("service problems")), out[-1])) + 1:]
             if l.startswith("  ")] if out else []
    row("zabbix", rc == 0, summary.strip() + (f"; service problems: {len(probs)}" if probs else "; no service problem"),
        "python automation/zabbix_setup.py apply   (maintenance follows the nodes started), then status")

    rc, out = script("check_dashboard.py")
    row("grafana", rc == 0, (out[-1] if out else "no output"),
        "just after a start some items have no value yet (polled every 5 min): wait 5 min and run demo_check again "
        "(cold start 10 Nov: 1 empty, 0 five minutes later); still empty = its host is not reporting; deployed "
        "dashboard differs = python automation/deploy_servers.py --role=grafana SRV-MON-01")

    try:
        bms = json.loads(res[1][1] or "{}")
        worse = [a["id"] for a in bms.get("alarms", []) if a.get("severity") != "warning"]
        ok = bool(bms.get("paths")) and all(v == "POWERED" for v in bms["paths"].values()) and not worse
        info = (f"paths {bms.get('paths')}, load {bms.get('path_load_pct')}, "
                f"{len(bms.get('alarms', [])) - len(worse)} warning(s) (design margin 47.1 % > 45 %)"
                + (f", ALARMS {worse}" if worse else ""))
    except ValueError:
        ok, info = False, f"no JSON (rc {res[1][0]})"
    row("power", ok, info, "reset the simulator: curl http://10.70.0.12:8080/api/reset (from ADMIN-WS)")

    rc, out = script("syslog_audit.py")
    marks = [l for l in out if l.split()[2:3] == ["running"]]
    okn = sum(1 for l in marks if " OK " in l)
    driven = sum(1 for l in marks if " OK " in l or "MISSING" in l or "SSH rc" in l)
    row("syslog", rc == 0, f"marker found for {okn}/{driven} running source(s) that can be driven",
        "check the source's 'logging host' / rsyslog forward, then the MGMT rule T18-8 on the firewall")

    try:
        from log_viewer import Viewer
        vw = Viewer()
        n = len(vw.sources())
        last = vw.search("", "all.log", 1)
        row("viewer", n > 0 and bool(last), f"login ok, {n} sources, last line {last[0][:19] if last else '-'}")
        loop = [l for l in vw.search("%SPANTREE-2-LOOPGUARD_BLOCK", "all.log", 50) if "logviewer" not in l
                and l[:19] >= time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - 900))]
    except Exception as e:  # noqa: BLE001
        loop = []
        row("viewer", False, f"{e}", "SYSLOG running? python automation/labctl.py start SYSLOG; wait 10 s")
    # loop guard: the state NOW (a block while a core was stopped on purpose is normal and clears when it is back)
    sw = [n for n in ("CORE-A", "CORE-B", "LEAF-A1", "LEAF-A2", "LEAF-B1", "LEAF-B2") if st.get(n) == "started"]
    inc = ssh_batch([(n.lower(), "show spanning-tree inconsistentports | include Number") for n in sw])
    blocked = {n: o.split(":")[-1].strip() for n, (rc, o) in zip(sw, inc) if o.split(":")[-1].strip() != "0"}
    row("loop guard", not blocked, (f"inconsistent ports now: {blocked}" if blocked else
                                    f"0 inconsistent port on {len(sw)} switches") + f"; {len(loop)} block(s) logged in 15 min",
        "GNS3 VM swapping -> flush swap (resources), stop an unused node; the leafs unblock by themselves")

    # redundancy: both halves of each pair must be alive, not only "started" in GNS3 (CORE-B hung on 10 Nov: started,
    # silent console, CORE-A carrying everything alone, and the leafs lost management through loop guard)
    pairs = ssh_batch([("core-a", "show standby brief | include Vl"), ("core-b", "show standby brief | include Vl"),
                       ("fw-a", "ifconfig | grep -c 'carp: MASTER'"), ("fw-b", "ifconfig | grep -c 'carp: BACKUP'")])
    bad = []
    for n, (rc, o) in zip(("CORE-A", "CORE-B"), pairs[:2]):
        if st.get(n) != "started":
            bad.append(f"{n} stopped")
        elif rc != 0 or not o.strip():
            bad.append(f"{n} no answer")
        else:
            groups = [l.split() for l in o.strip().splitlines()]
            lone = [g[0] for g in groups if "unknown" in g]
            if lone:
                bad.append(f"{n}: no peer on {', '.join(lone)}")
    for n, (rc, o), want in (("FW-A", pairs[2], "MASTER"), ("FW-B", pairs[3], "BACKUP")):
        if o.strip() != "5":
            bad.append(f"{n} {o.strip() or 'no answer'} x {want} (expected 5)")
    row("redundancy", not bad, "HSRP pairs CORE-A/CORE-B complete, CARP FW-A 5 MASTER / FW-B 5 BACKUP" if not bad
        else "; ".join(bad), "a node 'started' but silent is hung: python automation/labctl.py stop X, then start X, "
        "then python automation/cisco_heal.py X")
    row("web", res[2][1].strip().startswith("OK"), f"https://10.50.0.11/health -> {res[2][1].strip()[:40] or res[2][0]}",
        "python automation/labctl.py start SRV-WEB-01; FW-A DMZ interface up?")
    bad = sum(1 for ok, _ in ROWS if not ok)
    print(f"{len(ROWS) - bad}/{len(ROWS)} checks OK in {time.time() - t0:.0f} s" + ("" if not bad else " - see the -> lines"))
    if "--save" in argv:
        out = NET / "report" / "evidence" / "demo_s6_check.txt"
        out.write_text(time.strftime("# PLAN_03 S6 - demo_check.py %Y-%m-%d %H:%M:%S") + f" (profile {profile})\n"
                       + "\n".join(l for _, l in ROWS) + f"\n{len(ROWS) - bad}/{len(ROWS)} checks OK\n", encoding="utf-8")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
