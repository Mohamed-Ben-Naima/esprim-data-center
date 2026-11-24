"""Give the host its RAM back between recordings (PLAN_06 D11).

  python automation/demo_video/vm_cycle.py [--cap 1500000] [--start PROFILE]
VMware keeps every guest page the VM ever touched, so after a profile has run the host stays short even with every
node stopped. This script: lab_down (clean guest shutdowns) -> close the project -> soft-stop the GNS3 VM -> start
it -> set vm.min_free_kbytes=<cap> in the guest BEFORE any node starts (the guest then never touches more than
8 GB - cap, i.e. the host keeps that much) -> remove our project's leftover containers (409 on open, see memory)
-> open the project. --start PROFILE then starts the nodes of that profile through the API (stage order).
"""
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import gns3vm  # noqa: E402
import labctl  # noqa: E402

NET = HERE.parents[1]
VMRUN = gns3vm.VMRUN
VMX = gns3vm.VMX


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


def main(argv):
    cap = int(argv[argv.index("--cap") + 1]) if "--cap" in argv else 1500000
    prof = argv[argv.index("--start") + 1] if "--start" in argv else None
    api = labctl.Gns3()
    p = api.project()
    if any(n["status"] == "started" and n["node_type"] in ("qemu", "docker") for n in api.nodes(api.open(p))):
        subprocess.run([sys.executable, str(NET / "automation" / "lab_down.py")], cwd=NET)
    pid = p["project_id"]
    api.req("POST", f"/projects/{pid}/close")
    say("project closed")
    subprocess.run([VMRUN, "-T", "ws", "stop", VMX, "soft"], check=True)
    say("VM stopped")
    time.sleep(5)
    subprocess.run([VMRUN, "-T", "ws", "start", VMX, "nogui"], check=True)
    end = time.time() + 300
    while time.time() < end:
        try:
            urllib.request.urlopen("http://192.168.75.128/v2/version", timeout=5)
            break
        except Exception:  # noqa: BLE001
            time.sleep(5)
    say("GNS3 VM server up")
    out = gns3vm.run(f"sudo sysctl -w vm.min_free_kbytes={cap} vm.swappiness=10; "
                     f"for c in $(docker ps -aq --filter name={pid}); do sudo docker rm -f $c >/dev/null; done; "
                     "free -m | head -2", sudo=True)
    say("guest: " + " | ".join(l.strip() for l in out.strip().splitlines()[-3:]))
    for attempt in range(3):
        try:
            api.open(api.project())
            break
        except RuntimeError as e:
            say(f"open retry: {str(e)[:120]}")
            gns3vm.run(f"for c in $(docker ps -aq --filter name={pid}); do sudo docker rm -f $c >/dev/null; done", sudo=True)
            time.sleep(5)
    say("project open")
    if prof:
        from lab_up import OFF, STAGES
        p = api.project()
        for _, names in STAGES:
            for n in names:
                if n not in OFF[prof]:
                    api.start(p, api.node(p, n))
        say(f"profile {prof} started")


if __name__ == "__main__":
    main(sys.argv[1:])
