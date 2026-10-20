"""Start the lab in stages and measure resources after each stage (plan §2.3).

  python automation/lab_up.py [--settle 150] [--from N] [--profile full|supervision|demo]
Each stage is started, left to settle, then measured: GNS3 VM memory, KSM shared pages, swap, load average,
host free RAM. Results -> report/evidence/resources_stages.csv (+ printed table).
Profile "supervision" (PLAN_02 P0.2) leaves hall A, the undeployed servers and SRV-BASTION off: it is what the
15.7 GB host carries together with SRV-MON-01. Results -> report/evidence/resources_supervision.csv.
Profile "demo" (PLAN_03 S1) is "supervision" minus EDGE-B and CCTV-SIM: EDGE-A alone keeps BGP to ISP-A.
"""
import csv
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gns3vm  # noqa: E402
import labctl  # noqa: E402

NET = Path(__file__).resolve().parents[1]
STAGES = [
    ("1 WAN / bordure", ["NAT-A", "NAT-B", "ISP-A", "ISP-B", "SW-OUT", "EDGE-A", "EDGE-B"]),
    ("2 Sécurité / management", ["SW-DMZ", "SW-MGMT", "FW-A", "FW-B", "SRV-WEB-01", "ADMIN-WS"]),
    ("3 Cœur / distribution", ["CORE-A", "CORE-B", "LEAF-A1", "LEAF-A2", "LEAF-B1", "LEAF-B2"]),
    ("4 Services", ["SYSLOG", "BMS-SIM", "CCTV-SIM", "SRV-DCIM-01", "SRV-INF-01", "SRV-MON-01", "SRV-BASTION"]),
    ("5 Charges", ["SRV-CMP-01", "SRV-CMP-02", "SRV-CMP-03", "SRV-STO-01", "SRV-BCK-01"]),
]
OFF = {"full": set(),
       "supervision": {"LEAF-A1", "LEAF-A2", "SRV-BASTION", "SRV-CMP-01", "SRV-CMP-02", "SRV-CMP-03", "SRV-STO-01",
                       "SRV-BCK-01"}}
OFF["demo"] = OFF["supervision"] | {"EDGE-B", "CCTV-SIM"}


def measure():
    out = gns3vm.run("free -m | awk '/Mem:/{print $2, $3, $7} /Swap:/{print $3}'; "
                     "echo $(( $(cat /sys/kernel/mm/ksm/pages_sharing) * 4 / 1024 )); cut -d' ' -f1 /proc/loadavg; "
                     "ps -e -o comm | grep -c '^qemu-system'; docker ps -q | wc -l")
    v = out.split()
    host = subprocess.run(["powershell", "-NoProfile", "-Command",
                           "[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)"],
                          capture_output=True, text=True).stdout.strip()
    return {"vm_total_mb": v[0], "vm_used_mb": v[1], "vm_avail_mb": v[2], "swap_used_mb": v[3],
            "ksm_shared_mb": v[4], "load1": v[5], "qemu_vms": v[6], "containers": v[7], "host_free_gb": host.replace(",", ".")}


def main():
    settle = int(sys.argv[sys.argv.index("--settle") + 1]) if "--settle" in sys.argv else 150
    first = int(sys.argv[sys.argv.index("--from") + 1]) if "--from" in sys.argv else 1
    profile = sys.argv[sys.argv.index("--profile") + 1] if "--profile" in sys.argv else "full"
    if profile not in OFF:
        sys.exit(f"unknown profile {profile!r}; choose one of {', '.join(OFF)}")
    api = labctl.Gns3()
    p = api.open(api.project())
    rows = [dict(stage="0 Avant démarrage", nodes="—", **measure())] if first == 1 else []
    for i, (stage, names) in enumerate(STAGES, 1):
        names = [n for n in names if n not in OFF[profile]]
        if i < first or not names:
            continue
        for n in names:
            node = api.node(p, n)
            if node["status"] != "started":
                api.start(p, node)
        print(f"stage {stage}: started {len(names)} node(s), settling {settle}s", flush=True)
        time.sleep(settle)
        m = measure()
        rows.append(dict(stage=stage, nodes=len(names), **m))
        print("   ", m, flush=True)
    path = NET / "report" / "evidence" / ("resources_stages.csv" if profile == "full" else f"resources_{profile}.csv")
    if rows:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print("saved", path)


if __name__ == "__main__":
    main()
