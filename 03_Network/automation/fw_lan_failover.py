"""fw_lan_failover – stop one node of a redundant pair, measure the outage seen by a client (PLAN_01 T2-T5, PLAN_02 FW.3).

  python automation/fw_lan_failover.py [--core CORE-A] [--down 90] [--up 300]      core failure (FW.3 / T3)
  python automation/fw_lan_failover.py --core FW-A ...                             firewall failover (CARP, T2)
  python automation/fw_lan_failover.py --core SRV-CMP-01 ...                       application VIP (keepalived, T5)
  python automation/fw_lan_failover.py --core LEAF-A1 ...                          leaf failure, server bonds (T4)

A probe runs in a container every 0.5 s and logs the HTTP code (and, for the application, the server that answered):
  cores / firewalls: ADMIN-WS (VLAN 90) -> BMS-SIM 10.70.0.12:8080, path FW ADMIN -> FW LAN -> core HSRP -> leaf
  compute / leafs:   SRV-WEB-01 (DMZ)   -> application VIP https://10.20.0.10:8443, path FW DMZ -> core -> leaf -> VIP
The node is stopped through the GNS3 API (the qemu process ends; its GNS3 links stay "up" on the peer side, like a hung
device), left down --down seconds, started again, and watched --up seconds. What the surviving node reports is read
during the fault. Outages = runs of failed probes. After the restart cisco_heal.py repairs a Cisco node
(private-config, see memory). Evidence -> report/evidence/fw_lan_failover.txt (append with a header per run).
"""
import base64
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gns3vm  # noqa: E402
import labctl  # noqa: E402
from adminws import ssh_batch  # noqa: E402

NET = Path(__file__).resolve().parents[1]
BMS = ("ADMIN-WS", "http://10.70.0.12:8080/api/state")
APP = ("SRV-WEB-01", "https://10.20.0.10:8443/")
LOG = []
PAIR = {"CORE-A": "CORE-B", "CORE-B": "CORE-A", "FW-A": "FW-B", "FW-B": "FW-A",
        "SRV-CMP-01": "SRV-CMP-02", "SRV-CMP-02": "SRV-CMP-01", "LEAF-A1": "LEAF-A2", "LEAF-A2": "LEAF-A1"}
CARP = "ifconfig | grep 'carp:' | awk '{print $2}' | sort | uniq -c | tr '\\n' ' '"
BOND = ("grep -E 'Currently Active|Slave Interface|MII Status' /proc/net/bonding/bond0 | sed 's/.*: //' | tr '\\n' ' '; "
        "ip -br -4 addr show bond0 | awk '{print $3, $4}'")


def say(s):
    s = time.strftime("%H:%M:%S ") + s
    print(s, flush=True)
    LOG.append(s)


def probe(action, src, url):
    """Probe loop as a script in the source container (pid file: stopping it must not match the reader's own line)."""
    who = "docker ps -q --filter name=" + src
    if action == "start":
        # busybox date has no %N: the time is the kernel uptime (shared by the containers), converted on stop
        loop = ("#!/bin/sh\necho $$ > /tmp/fw3.pid\nwhile :; do t=$(cut -d' ' -f1 /proc/uptime); "
                f"b=$(curl -sk -m 1 -w ' %{{http_code}}' {url}); c=${{b##* }}; "
                "h=$(echo \"$b\" | sed -n 's/.*\"host\": *\"\\([^\"]*\\)\".*/\\1/p'); "
                "echo \"$t $c ${h:--}\" >> /tmp/fw3.txt; sleep 0.5; done\n")
        b = base64.b64encode(loop.encode()).decode()
        gns3vm.run(f"a=$({who}); docker exec $a sh -c 'rm -f /tmp/fw3.txt; "
                   f"echo {b} | base64 -d > /tmp/fw3.sh; chmod 700 /tmp/fw3.sh'; docker exec -d $a /tmp/fw3.sh")
        return []
    out = gns3vm.run(f"echo OFFSET $(date +%s.%N) $(cut -d' ' -f1 /proc/uptime); a=$({who}); docker exec $a sh -c "
                     "'kill $(cat /tmp/fw3.pid); cat /tmp/fw3.txt; rm -f /tmp/fw3.txt /tmp/fw3.sh /tmp/fw3.pid'")
    off = next(float(l.split()[1]) - float(l.split()[2]) for l in out.splitlines() if l.startswith("OFFSET"))
    rows = []
    for line in out.splitlines():
        p = line.split()
        if len(p) == 3 and not line.startswith("OFFSET"):
            try:
                rows.append((float(p[0]) + off, p[1] == "200", p[2]))
            except ValueError:
                pass
    return rows


def outages(rows, t_from, t_to):
    """[(start, end, seconds)] of failed runs between t_from and t_to (end = first success after the run)."""
    out, start = [], None
    for t, ok, _ in rows:
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


def observe(node):
    """[(label, state)] read on the nodes that stay up while `node` is down."""
    other = PAIR[node]
    if node.startswith("SRV-CMP"):
        items = [(other, other.lower(), BOND)]
    elif node.startswith("LEAF"):
        items = [(f"{s} bond", s.lower(), BOND) for s in ("SRV-CMP-01", "SRV-CMP-02")]
    else:
        fw = "FW-B" if node == "FW-A" else "FW-A"
        items = [(fw, fw.lower(), "ifconfig lagg0 | grep -E 'laggproto|laggport|status'"),
                 (other, other.lower(), CARP if other.startswith("FW-") else "show standby brief | include Vl70|Vl902")]
    res = ssh_batch([(a, c) for _, a, c in items])
    return [(label, " | ".join(r[1].strip().splitlines()) or f"no answer (rc {r[0]})") for (label, _, _), r in zip(items, res)]


def main(argv):
    node = argv[argv.index("--core") + 1] if "--core" in argv else "CORE-A"
    down = int(argv[argv.index("--down") + 1]) if "--down" in argv else 90
    up = int(argv[argv.index("--up") + 1]) if "--up" in argv else 300
    src, url = APP if node.startswith(("SRV-CMP", "LEAF-A")) else BMS
    api = labctl.Gns3()
    p = api.project()
    say(f"stop {node} for {down} s, probe {src} -> {url} every 0.5 s")
    if node.startswith(("SRV-CMP", "LEAF")):
        for label, st in observe("LEAF-A1"):
            say(f"before: {label}: {st}")
    for label, st in observe(node):
        say(f"before: {label}: {st}")
    if node.startswith("FW-"):
        say("before: CARP " + " / ".join(f"{f}: " + observe(PAIR[f])[1][1] for f in ("FW-A", "FW-B")))
    probe("start", src, url)
    time.sleep(10)
    t_stop = time.time()
    api.stop(p, api.node(p, node))
    say(f"{node} stopped (GNS3 API)")
    time.sleep(min(30, down))
    for label, st in observe(node):
        say(f"+30 s: {label}: {st}")
    time.sleep(max(0, down - 30))
    t_start = time.time()
    api.start(p, api.node(p, node))
    say(f"{node} started again")
    time.sleep(up)
    rows = probe("stop", src, url)
    t_end = time.time()
    say(f"{len(rows)} probes, {sum(1 for _, ok, _ in rows if not ok)} failed")
    for label, a, b in (("fault", t_stop, t_start), ("restart", t_start, t_end)):
        o = outages(rows, a, b)
        served = sorted({h for t, ok, h in rows if a <= t <= b and ok and h != "-"})
        say(f"{label}: " + ("no outage" if not o else f"{len(o)} outage(s)")
            + (f", answered by {', '.join(served)}" if served else ""))
        for s, e, d in o:
            say(f"{label}: outage from +{s - a:.1f} s to "
                + (f"+{e - a:.1f} s = {d:.1f} s" if e else f"end of window (still down, >= {d:.1f} s)"))
            near = [(t, ok, h) for t, ok, h in rows if s - 3 <= t <= (e or s) + 2]
            say("   samples: " + " ".join(f"{t - a:+.1f}{'' if ok else 'X'}{h[-2:] if h != '-' else ''}"
                                          for t, ok, h in near))
        # switch of the answering server (keepalived VIP moves) even without a failed probe
        prev = None
        for t, ok, h in rows:
            if a <= t <= b and ok and h != "-":
                if prev and h != prev:
                    say(f"{label}: VIP served by {h} from +{t - a:.1f} s (was {prev})")
                prev = h
    if node.startswith("FW-"):
        say("after: CARP " + " / ".join(f"{f}: " + observe(PAIR[f])[1][1] for f in ("FW-A", "FW-B")))
    elif not node.startswith("SRV-"):
        r = subprocess.run([sys.executable, str(Path(__file__).parent / "cisco_heal.py"), node], capture_output=True,
                           text=True)
        say("cisco_heal: " + r.stdout.strip())
    for label, st in observe(PAIR[node] if node.startswith("SRV-CMP") else node):
        say(f"after: {label}: {st}")
    ev = NET / "report" / "evidence" / "fw_lan_failover.txt"
    with open(ev, "a", encoding="utf-8") as f:
        f.write(f"\n# PLAN_02 FW.3 / PLAN_01 T2-T5 - fw_lan_failover.py {' '.join(argv)} - {time.strftime('%Y-%m-%d %H:%M')}\n"
                + "\n".join(LOG) + "\n")
    print("->", ev.relative_to(NET))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
