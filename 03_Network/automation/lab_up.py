"""Start the lab in stages and measure resources after each stage (plan §2.3).

  python automation/lab_up.py [--settle 150] [--from N] [--profile full|supervision|demo|nas]
Each stage is started, left to settle, then measured: GNS3 VM memory, KSM shared pages, swap, load average,
host free RAM. Results -> report/evidence/resources_stages.csv (+ printed table).
Profile "supervision" (PLAN_02 P0.2) leaves hall A, the undeployed servers and SRV-BASTION off: it is what the
15.7 GB host carries together with SRV-MON-01. Results -> report/evidence/resources_supervision.csv.
Profile "demo" (PLAN_03 S1) is "supervision" minus EDGE-B, CCTV-SIM and SRV-INF-01: EDGE-A alone keeps BGP to
ISP-A; with SRV-INF-01 running the cores still lost HSRP hellos (20 Oct 2026), so the demo runs without NTP/DNS.
Profile "nas" (PLAN_04) keeps only the path from the administration zone to the TrueNAS SRV-BCK-01 (3-4 GB of RAM):
SW-MGMT, FW-A, CORE-A, LEAF-B1, LEAF-B2, ADMIN-WS, SYSLOG and SRV-BCK-01.
After the stages (PLAN_03 S6, so that a cold start needs no manual step): the GNS3 VM swap is flushed, cisco_heal.py
puts back an RSA key / SNMPv3 user that a Cisco device lost at boot (private-config not loaded), the lab proxy is
started when ADMIN-WS runs, and when SRV-MON-01 runs the script waits for the Zabbix API and runs
`zabbix_setup.py apply` (the maintenance "demo-off" follows the nodes started). Then: `python automation/demo_check.py`.
  python automation/lab_up.py --profile demo --from 9     only the steps after the stages (lab already started)
"""
import csv
import os
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
OFF["demo"] = OFF["supervision"] | {"EDGE-B", "CCTV-SIM", "SRV-INF-01"}
# compute: the demo set with hall A (both leafs, CMP-01/02 = keepalived VIP, PLAN_01 T4/T5) instead of the edge tier
OFF["compute"] = (OFF["demo"] - {"LEAF-A1", "LEAF-A2", "SRV-CMP-01", "SRV-CMP-02"}) | {"EDGE-A"}
# PLAN_06 D7 (video night, host baseline ~7.5 GB): the demo set + SRV-MON-01 + a recorder do not fit together.
# net = demo without the supervision server; noc = demo with it, EDGE-A and FW-B off (the guest re-uses their memory)
OFF["net"] = OFF["demo"] | {"SRV-MON-01"}
OFF["noc"] = OFF["demo"] | {"EDGE-A", "FW-B"}
# cmp = hall A (2 leafs + CMP-01/02 keepalived) in place of the edge, FW-B and the supervision server
OFF["cmp"] = (OFF["net"] | {"EDGE-A", "FW-B", "ISP-A", "ISP-B"}) - {"LEAF-A1", "LEAF-A2", "SRV-CMP-01", "SRV-CMP-02"}
OFF["nas"] = {n for _, names in STAGES for n in names} - {"SW-MGMT", "FW-A", "CORE-A", "LEAF-B1", "LEAF-B2", "ADMIN-WS",
                                                          "SYSLOG", "SRV-BCK-01"}


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
    # the boot peak pushes idle pages of the routers into the GNS3 VM swap; a core that has to page them back in
    # stalls for seconds and its HSRP peer takes over (PLAN_03 S1): bring them back to RAM once everything is up
    out = gns3vm.run("sudo swapoff -a && sudo swapon -a && sudo sysctl -q -w vm.swappiness=10; free -m | awk '/Swap:/{print $3}'",
                     sudo=True)
    print("swap flushed back to RAM, swap used now (MB):", out.strip(), flush=True)
    post(profile)
    path = NET / "report" / "evidence" / ("resources_stages.csv" if profile == "full" else f"resources_{profile}.csv")
    if rows:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print("saved", path)


def post(profile):
    """Lab proxy, then Zabbix maintenance following the nodes started (needs the proxy)."""
    here = Path(__file__).parent
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    on = {n for _, names in STAGES for n in names} - OFF[profile]
    r = subprocess.run([sys.executable, str(here / "cisco_heal.py")], capture_output=True, text=True, env=env)
    print("cisco_heal.py (RSA key + SNMPv3 user after boot):", flush=True)
    for line in r.stdout.strip().splitlines():
        print("   ", line, flush=True)
    if "ADMIN-WS" in on:
        r = subprocess.run([sys.executable, str(here / "lab_proxy.py"), "start"], capture_output=True, text=True, env=env)
        print("lab proxy:", (r.stdout.strip().splitlines() or ["?"])[-1], flush=True)
    if "SRV-BCK-01" in on and "ADMIN-WS" in on:
        # the NAS takes its settings from the inventory at each start (idempotent): a rotated secret (SNMPv3 keys,
        # 10 Nov 2026) reaches it even when it was off during the rotation. Its API needs a few minutes after boot.
        end = time.time() + 600
        while subprocess.run([sys.executable, str(here / "truenas_setup.py"), "check"], capture_output=True,
                             env=env).returncode != 0 and time.time() < end:
            time.sleep(20)
        r = subprocess.run([sys.executable, str(here / "truenas_setup.py"), "apply"], capture_output=True, text=True,
                           env=env)
        print("truenas_setup.py apply:", (r.stdout.strip().splitlines() or ["?"])[-1], flush=True)
    if "SRV-MON-01" in on and "ADMIN-WS" in on:
        import zabbix_setup as zs
        end = time.time() + 600
        while True:
            try:
                z = zs.Zabbix()
                zs.login(z)
                break
            except Exception as e:  # noqa: BLE001  services still starting after the boot
                if time.time() > end:
                    print("Zabbix API not answering after 10 min:", e, flush=True)
                    return
                time.sleep(15)
        r = subprocess.run([sys.executable, str(here / "zabbix_setup.py"), "apply"], capture_output=True, text=True,
                           env=env)
        print("zabbix_setup.py apply:", (r.stdout.strip().splitlines() or ["?"])[-1], flush=True)
    print("next: python automation/demo_check.py --profile", profile, flush=True)


# PLAN_06 D11 (24 Nov): minimal sets, each recorded after a GNS3 VM restart (VMware keeps touched guest memory)
_ALL = {n for _, names in STAGES for n in names}
_SW = {"NAT-A", "NAT-B", "SW-OUT", "SW-DMZ", "SW-MGMT"}
OFF["noc2"] = _ALL - _SW - {"FW-A", "CORE-A", "LEAF-B1", "LEAF-B2", "ADMIN-WS", "SYSLOG", "BMS-SIM", "SRV-DCIM-01",
                            "SRV-MON-01"}
OFF["cmp2"] = _ALL - _SW - {"FW-A", "CORE-A", "LEAF-A1", "LEAF-A2", "ADMIN-WS", "SRV-WEB-01", "SRV-CMP-01",
                            "SRV-CMP-02"}   # SYSLOG hangs off hall B: not reachable here

OFF["noc3"] = OFF["noc2"] | {"LEAF-B2"}

OFF["nas2"] = OFF["nas"] | {"LEAF-B2"}   # SRV-BCK-01 is dual-homed: LEAF-B1 alone carries it

# live: small hands-on demo (NOC + SOC + web + bastion), fits with a browser open on the host
OFF["live"] = OFF["noc2"] - {"SRV-WEB-01", "SRV-BASTION"}


if __name__ == "__main__":
    main()
