"""fw_lan_failover – what the firewall LAN side does when a core stops (PLAN_02 FW.3, PLAN_01 T3).

  python automation/fw_lan_failover.py [--core CORE-A] [--down 90] [--up 300]
  python automation/fw_lan_failover.py --core FW-A ...     firewall failover (CARP + pfsync, PLAN_01 T2)

A probe runs in ADMIN-WS (VLAN 90): every 0.5 s an HTTP request to BMS-SIM (10.70.0.12:8080, VLAN 70). The path is
ADMIN-WS -> FW (ADMIN em6.90) -> FW LAN (lagg0, VLAN 902) -> core HSRP gateway -> leaf -> BMS-SIM, and back.
The core is stopped through the GNS3 API (the qemu process ends; its GNS3 links stay "up" on the peer side), left
down --down seconds, started again, and watched --up seconds. The firewall lagg state and the HSRP state of CORE-B
are read during the fault. Outages = runs of failed probes. After the restart cisco_heal.py repairs the core
(private-config, see memory). Evidence -> report/evidence/fw_lan_failover.txt (append with a header per run).
"""
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gns3vm  # noqa: E402
import labctl  # noqa: E402
from adminws import ssh_batch  # noqa: E402

NET = Path(__file__).resolve().parents[1]
TARGET = "http://10.70.0.12:8080/api/state"
LOG = []


def say(s):
    s = time.strftime("%H:%M:%S ") + s
    print(s, flush=True)
    LOG.append(s)


def probe(action):
    """Probe loop as a script in ADMIN-WS (pid file: stopping it must not match the reader's own command line)."""
    if action == "start":
        loop = ("#!/bin/sh\necho $$ > /tmp/fw3.pid\nwhile :; do t=$(date +%s.%N | cut -c1-14); "
                f"c=$(curl -s -m 1 -o /dev/null -w '%{{http_code}}' {TARGET}); echo \"$t $c\" >> /tmp/fw3.txt; "
                "sleep 0.5; done\n")
        import base64
        b = base64.b64encode(loop.encode()).decode()
        gns3vm.run(f"a=$(docker ps -q --filter name=ADMIN-WS); docker exec $a sh -c 'rm -f /tmp/fw3.txt; "
                   f"echo {b} | base64 -d > /tmp/fw3.sh; chmod 700 /tmp/fw3.sh'; docker exec -d $a /tmp/fw3.sh")
        return []
    out = gns3vm.run("a=$(docker ps -q --filter name=ADMIN-WS); docker exec $a sh -c "
                     "'kill $(cat /tmp/fw3.pid); cat /tmp/fw3.txt; rm -f /tmp/fw3.txt /tmp/fw3.sh /tmp/fw3.pid'")
    rows = []
    for line in out.splitlines():
        p = line.split()
        if len(p) == 2:
            try:
                rows.append((float(p[0]), p[1] == "200"))
            except ValueError:
                pass
    return rows


def outages(rows, t_from, t_to):
    """[(start, end, seconds)] of failed runs between t_from and t_to (end = first success after the run)."""
    out, start = [], None
    for t, ok in rows:
        if t < t_from or t > t_to:
            continue
        if not ok and start is None:
            start = t
        elif ok and start is not None:
            out.append((start, t, t - start))
            start = None
    if start is not None:
        out.append((start, None, t_to - start))
    return out


PAIR = {"CORE-A": "CORE-B", "CORE-B": "CORE-A", "FW-A": "FW-B", "FW-B": "FW-A"}
CARP = "ifconfig | grep 'carp:' | awk '{print $2}' | sort | uniq -c | tr '\\n' ' '"


def fw_state(other="CORE-B", fw="fw-a"):
    """lagg members of a running firewall, and what the node that stays up reports (HSRP of a core, CARP of a FW)."""
    res = ssh_batch([(fw, "ifconfig lagg0 | grep -E 'laggproto|laggport|status'"),
                     (other.lower(), CARP if other.startswith("FW-") else "show standby brief | include Vl70|Vl902")])
    return res[0][1].strip(), res[1][1].strip()


def main(argv):
    core = argv[argv.index("--core") + 1] if "--core" in argv else "CORE-A"
    down = int(argv[argv.index("--down") + 1]) if "--down" in argv else 90
    up = int(argv[argv.index("--up") + 1]) if "--up" in argv else 300
    api = labctl.Gns3()
    p = api.project()
    other = PAIR[core]
    say(f"stop {core} for {down} s, probe ADMIN-WS -> {TARGET} every 0.5 s")
    lagg, hsrp = fw_state()
    say("before: FW-A " + " | ".join(lagg.splitlines()))
    if core.startswith("FW-"):
        say("before: CARP " + " / ".join(f"{f}: " + fw_state(f)[1] for f in ("FW-A", "FW-B")))
    probe("start")
    time.sleep(10)
    t_stop = time.time()
    api.stop(p, api.node(p, core))
    say(f"{core} stopped (GNS3 API)")
    time.sleep(min(30, down))
    lagg, hsrp = fw_state(other, "fw-b" if core == "FW-A" else "fw-a")
    say(f"+30 s: {'FW-B' if core == 'FW-A' else 'FW-A'} " + " | ".join(lagg.splitlines()))
    say(f"+30 s: {other} " + " | ".join(hsrp.splitlines()))
    time.sleep(max(0, down - 30))
    t_start = time.time()
    api.start(p, api.node(p, core))
    say(f"{core} started again")
    time.sleep(up)
    rows = probe("stop")
    t_end = time.time()
    say(f"{len(rows)} probes, {sum(1 for _, ok in rows if not ok)} failed")
    for label, a, b in (("fault", t_stop, t_start), ("restart", t_start, t_end)):
        o = outages(rows, a, b)
        if not o:
            say(f"{label}: no outage")
        for s, e, d in o:
            say(f"{label}: outage from +{s - a:.1f} s to "
                + (f"+{e - a:.1f} s = {d:.1f} s" if e else f"end of window (still down, >= {d:.1f} s)"))
            near = [(t, ok) for t, ok in rows if s - 3 <= t <= (e or s) + 2]
            say("   samples: " + " ".join(f"{t - a:+.1f}{'' if ok else 'X'}" for t, ok in near))
    if core.startswith("FW-"):
        say("after: CARP " + " / ".join(f"{f}: " + fw_state(f)[1] for f in ("FW-A", "FW-B")))
    else:
        r = subprocess.run([sys.executable, str(Path(__file__).parent / "cisco_heal.py"), core], capture_output=True,
                           text=True)
        say("cisco_heal: " + r.stdout.strip())
    lagg, hsrp = fw_state()
    say("after: FW-A " + " | ".join(lagg.splitlines()))
    ev = NET / "report" / "evidence" / "fw_lan_failover.txt"
    with open(ev, "a", encoding="utf-8") as f:
        f.write(f"\n# PLAN_02 FW.3 / PLAN_01 T2-T3 - fw_lan_failover.py {' '.join(argv)} - {time.strftime('%Y-%m-%d %H:%M')}\n"
                + "\n".join(LOG) + "\n")
    print("->", ev.relative_to(NET))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
