"""lab_down – stop the whole lab cleanly (PLAN_03 S6), the reverse of lab_up.py.

  python automation/lab_down.py            guest shutdown of the VMs, then stop every node, then the lab proxy
  python automation/lab_down.py --hard     skip the guest shutdown (GNS3 stop = power cut for VMs)

1. VMs that hold data are shut down from inside, in parallel, so their disks are clean (no fsck at next boot):
   Ubuntu servers (serial console, `systemctl poweroff`), TrueNAS (API system.shutdown), pfSense (`shutdown -p now`
   over SSH from ADMIN-WS). Wait until GNS3 reports them stopped (max 240 s), else stop them.
2. Every other started node (Cisco, containers, switches, NAT) is stopped by the GNS3 API.
3. The lab proxy is stopped (it lives in the ADMIN-WS namespace).
The GNS3 VM itself keeps running: close the project in the GUI before stopping the VM (lab rule).
"""
import sys
import threading
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import gns3vm  # noqa: E402
import labctl  # noqa: E402

NET = Path(__file__).resolve().parents[1]
INV = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


def linux_poweroff(api, p, name):
    try:
        with labctl.Console.for_node(api, p, name) as c:
            lx = labctl.Linux(c)
            lx.login(timeout=60)
            c.send("systemctl poweroff")
            time.sleep(3)
            c.read(2)          # let the command leave before the telnet session closes
        say(f"{name}: systemctl poweroff sent")
    except Exception as e:  # noqa: BLE001  console busy or frozen: GNS3 stop later
        say(f"{name}: guest shutdown failed ({e}), will be stopped")


def truenas_shutdown(name):
    try:
        import truenas_setup as ts
        t = ts.connect(retry=1, wait=5)
        try:
            t.call("system.shutdown", ["lab_down.py"])
        except Exception:  # noqa: BLE001  the socket closes while the NAS goes down
            pass
        say(f"{name}: TrueNAS system.shutdown sent")
    except Exception as e:  # noqa: BLE001
        say(f"{name}: guest shutdown failed ({e}), will be stopped")


def pfsense_shutdown(names):
    from adminws import ssh_batch
    try:
        res = ssh_batch([(n.lower(), "/sbin/shutdown -p now") for n in names], timeout=20)
        for n, (rc, _) in zip(names, res):
            say(f"{n}: shutdown -p now sent (rc {rc})")
    except Exception as e:  # noqa: BLE001
        say(f"pfSense guest shutdown failed ({e}), will be stopped")


def main(argv):
    t0 = time.time()
    api = labctl.Gns3()
    p = api.open(api.project())
    started = {n["name"]: n for n in api.nodes(p) if n["status"] == "started"}
    say(f"{len(started)} node(s) started")
    servers = {n: d for n, d in INV["servers"].items() if d.get("kind") == "vm" and n in started}
    fws = [n for n in INV["devices"] if n.startswith("FW-") and n in started]
    vms = list(servers) + fws
    if vms and "--hard" not in argv:
        jobs = []
        for n, d in servers.items():
            target = (truenas_shutdown, (n,)) if d.get("platform") == "truenas" else (linux_poweroff, (api, p, n))
            jobs.append(threading.Thread(target=target[0], args=target[1]))
        if fws:
            jobs.append(threading.Thread(target=pfsense_shutdown, args=(fws,)))   # needs ADMIN-WS: before step 2
        for j in jobs:
            j.start()
        for j in jobs:
            j.join(120)
        end = time.time() + 240
        while time.time() < end:
            left = [n for n in vms if api.node(p, n)["status"] == "started"]
            if not left:
                break
            time.sleep(5)
        down = [n for n in vms if api.node(p, n)["status"] != "started"]
        say(f"guest shutdown done for {len(down)}/{len(vms)} VM(s): {', '.join(down) or '-'}")
    for n in api.nodes(p):
        if n["status"] == "started":
            api.stop(p, n)
    say("every node stopped")
    try:
        import subprocess
        subprocess.run([sys.executable, str(Path(__file__).parent / "lab_proxy.py"), "stop"], timeout=60,
                       capture_output=True)
    except Exception:  # noqa: BLE001
        pass
    mem = gns3vm.run("free -m | awk '/Mem:/{print $7} /Swap:/{print $3}'").split()
    say(f"lab stopped in {time.time() - t0:.0f} s; GNS3 VM available {mem[0]} MB, swap {mem[1]} MB")


if __name__ == "__main__":
    main(sys.argv[1:])
