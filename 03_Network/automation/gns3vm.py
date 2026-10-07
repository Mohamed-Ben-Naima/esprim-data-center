"""Run shell scripts inside the GNS3 VM through VMware Tools (vmrun) – no SSH, no quoting issues.

  python automation/gns3vm.py "free -m; docker ps"          # inline script
  python automation/gns3vm.py -f path/to/script.sh            # script file
  python automation/gns3vm.py --sudo "systemctl restart gns3"
Library: from gns3vm import run; print(run("uptime"))
"""
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

VMRUN = r"C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe"
VMX = os.environ.get("GNS3_VMX", r"H:\GNS3 VM\GNS3 VM.vmx")
USER, PASSWORD = "gns3", "gns3"


def _vmrun(*args, check=True):
    r = subprocess.run([VMRUN, "-T", "ws", "-gu", USER, "-gp", PASSWORD, *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"vmrun {args[0]} failed: {r.stdout.strip()} {r.stderr.strip()}")
    return r


def put(local, remote):
    _vmrun("CopyFileFromHostToGuest", VMX, str(local), remote)


def get(remote, local):
    _vmrun("CopyFileFromGuestToHost", VMX, remote, str(local))


def run(script, sudo=False):
    """Execute a bash script in the VM; returns combined stdout/stderr (exit code appended on failure)."""
    tag = uuid.uuid4().hex[:8]
    body = "#!/bin/bash\n"
    if sudo:
        body += "sudo() { echo gns3 | command sudo -S -p '' \"$@\"; }\n"
    body += f"exec > /tmp/run_{tag}.out 2>&1\n{script}\n"
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / f"run_{tag}.sh"
        src.write_bytes(body.replace("\r\n", "\n").encode())
        put(src, f"/tmp/run_{tag}.sh")
        r = _vmrun("runProgramInGuest", VMX, "/bin/bash", f"/tmp/run_{tag}.sh", check=False)
        out = Path(td) / "out.txt"
        get(f"/tmp/run_{tag}.out", out)
        text = out.read_text(encoding="utf-8", errors="replace")
    _vmrun("runProgramInGuest", VMX, "/bin/rm", "-f", f"/tmp/run_{tag}.sh", f"/tmp/run_{tag}.out", check=False)
    if r.returncode != 0:
        text += f"\n[exit status non-zero: {r.stdout.strip()}]"
    return text


if __name__ == "__main__":
    a = sys.argv[1:]
    sudo = "--sudo" in a
    a = [x for x in a if x != "--sudo"]
    script = Path(a[1]).read_text(encoding="utf-8") if a and a[0] == "-f" else " ".join(a)
    sys.stdout.reconfigure(encoding="utf-8")
    print(run(script, sudo=sudo))
