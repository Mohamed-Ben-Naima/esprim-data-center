"""syslog_audit – does every running equipment reach the central collector? (PLAN_03 S5, LOG.1)

  python automation/syslog_audit.py

1. For each started node that should log (inventory devices + servers + simulators), its file in /var/log/remote on
   SYSLOG and the age of its last line.
2. A marker "S5-AUDIT-<time>" is sent from every running source that can be driven over SSH from ADMIN-WS
   (Cisco: `send log`, pfSense / Linux / TrueNAS: `logger`), then searched in the collector's per-host files.
3. Device clocks: the stamp written by the device (%hostname% line in the per-host file) is compared to the
   collector time (%timegenerated%) for the marker line.
Sources that only log on events (simulators, webterm) are reported with the age of their last line.

  python automation/syslog_audit.py --set-clock   # first set the clock of the running Cisco devices to the collector
                                                  # time (exec `clock set`, nothing saved) - for profiles without the
                                                  # NTP server SRV-INF-01; NTP takes over again when it runs.
Exit code 1 when a marker sent to a running source is not found.
"""
import re
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import gns3vm  # noqa: E402
import labctl  # noqa: E402
from adminws import ssh_batch  # noqa: E402

NET = Path(__file__).resolve().parents[1]
INV = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
SYSLOG_IP = INV["services"]["syslog"]


def sources():
    """name -> (ip, kind) of everything that should send logs."""
    out = {}
    for n, d in INV["devices"].items():
        out[n] = (d["mgmt"]["ip"], "pfsense" if n.startswith("FW-") else "cisco")
    for n, d in INV["servers"].items():
        kind = "truenas" if d.get("platform") == "truenas" else (
            "docker" if d.get("kind") == "docker" else "linux")
        if "syslog" in d.get("roles", []):
            continue
        out[n] = (d["ip"], kind)
    return out


def collector(script):
    return gns3vm.run("c=$(docker ps -q --filter name=GNS3.SYSLOG.); [ -n \"$c\" ] || { echo NO-SYSLOG; exit 0; }\n"
                      f"docker exec $c sh -c '{script}'")


def file_ages():
    """ip -> (seconds since its last line, size, file); empty files (just rotated) fall back to their newest archive."""
    out = collector('now=$(date +%s); cd /var/log/remote; for f in *.log *.log-*.gz; do [ -s "$f" ] && '
                    'echo "$(( now - $(stat -c %Y "$f") )) $(stat -c %s "$f") $f"; done')
    ages = {}
    for line in out.splitlines():
        m = re.match(r"(\d+) (\d+) (\S+?)\.log(-\d{8}\.gz)?$", line.strip())
        if m:
            ip = m.group(3).split("_")[0]
            if ip not in ages or int(m.group(1)) < ages[ip][0]:
                ages[ip] = (int(m.group(1)), int(m.group(2)), m.group(3) + ".log")
    return ages


def set_clock(src, running):
    cisco = [n for n, (ip, kind) in src.items() if n in running and kind == "cisco"]
    now = collector('date "+%H:%M:%S %d %b %Y"').strip().splitlines()[-1]
    for (rc, out), n in zip(ssh_batch([(n.lower(), f"clock set {now}") for n in cisco]), cisco):
        print(f"clock set {now} on {n}: rc {rc} {out.strip()[:60]}")


def main(argv):
    api = labctl.Gns3()
    running = {n["name"] for n in api.nodes(api.project()) if n["status"] == "started"}
    src = sources()
    if "--set-clock" in argv:
        set_clock(src, running)
    ages = file_ages()
    marker = "S5-AUDIT-" + time.strftime("%H%M%S")
    cmd = {"cisco": f"send log 6 {marker}", "pfsense": f"logger -t s5audit {marker}",
           "linux": f"logger -t s5audit {marker}", "truenas": f"logger -t s5audit {marker}"}
    driven = [(n, ip, kind) for n, (ip, kind) in src.items() if n in running and kind in cmd]
    res = ssh_batch([(n.lower(), cmd[kind]) for n, ip, kind in driven]) if driven else []
    time.sleep(3)
    found = collector(f'grep -h -- "{marker}" /var/log/remote/*_*.log; date "+NOW %Y-%m-%dT%H:%M:%S"')
    rc = 0
    print(f"marker {marker}, collector {SYSLOG_IP}")
    print(f"{'source':12} {'ip':12} {'state':8} {'last line':>10}  marker  device clock vs collector")
    for n, (ip, kind) in sorted(src.items(), key=lambda x: x[1][0]):
        on = n in running
        age = ages.get(ip)
        last = f"{age[0] // 60} min" if age else "no file"
        mark, skew = "", ""
        if on and kind in cmd:
            i = [d[0] for d in driven].index(n)
            line = next((l for l in found.splitlines() if f" {ip} " in l), "")
            mark = "OK" if line else ("SSH rc %d" % res[i][0] if res[i][0] else "MISSING")
            if not line:
                rc = 1
            else:
                skew = clock_skew(line)
        elif on:
            mark = "events"
        print(f"{n:12} {ip:12} {'running' if on else 'stopped':8} {last:>10}  {mark:7} {skew}")
    return rc


MONTHS = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}


def clock_skew(line):
    """Collector stamp (RFC 3339, first field) vs the device's own stamp inside the Cisco message (*Mmm dd hh:mm:ss)."""
    m = re.match(r"(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)", line)
    d = re.search(r"\*?(\w{3}) +(\d+) (\d\d):(\d\d):(\d\d)(?:\.\d+)?", line[26:])
    if not (m and d and d.group(1) in MONTHS):
        return "(device stamp not in message)"
    col = time.mktime((int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]), int(m[6]), 0, 0, -1))
    dev = time.mktime((int(m[1]), MONTHS[d[1]], int(d[2]), int(d[3]), int(d[4]), int(d[5]), 0, 0, -1))
    s = int(dev - col)
    return f"{'+' if s >= 0 else '-'}{abs(s) // 3600}h{abs(s) % 3600 // 60:02d}m{abs(s) % 60:02d}s"


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
