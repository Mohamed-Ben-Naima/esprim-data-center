"""Check (or repair) the ext4 root filesystem of stopped Ubuntu server nodes, from the GNS3 VM.

  python automation/fsck_servers.py SRV-MON-01 SRV-BASTION       read-only check (e2fsck -f -n)
  python automation/fsck_servers.py --repair SRV-MON-01          repair (e2fsck -f -y)

`qemu-img check` only validates the disk image container; a host disk incident can still corrupt the filesystem
inside (SRV-MON-01, 12 Oct 2026). The node must be stopped: its disk is attached with qemu-nbd, checked, detached.
e2fsck exit code: 0 clean, 1 errors corrected, 4 errors left uncorrected, 8 operational error.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gns3vm  # noqa: E402
import labctl  # noqa: E402


def main(argv):
    repair = "--repair" in argv
    names = [a for a in argv if not a.startswith("--")]
    if not names:
        print(__doc__); return 1
    api = labctl.Gns3()
    p = api.project()
    worst = 0
    for name in names:
        n = api.node(p, name)
        if n["status"] != "stopped":
            print(f"{name}: skipped, node is {n['status']} (stop it first)"); worst = max(worst, 8); continue
        disk = f"/opt/gns3/projects/{p['project_id']}/project-files/qemu/{n['node_id']}/hda_disk.qcow2"
        out = gns3vm.run(f"""sudo modprobe nbd max_part=8
sudo qemu-nbd --disconnect /dev/nbd0 >/dev/null 2>&1
sudo qemu-nbd --connect=/dev/nbd0 {disk} || exit 8
sleep 2; sudo partprobe /dev/nbd0 2>/dev/null; sleep 1
sudo e2fsck -f {'-y' if repair else '-n'} /dev/nbd0p1 2>&1 | tail -12
echo "e2fsck-exit=${{PIPESTATUS[0]}}"
sudo qemu-nbd --disconnect /dev/nbd0 >/dev/null""", sudo=True)
        code = int(out.split("e2fsck-exit=")[1].split()[0]) if "e2fsck-exit=" in out else 8
        worst = max(worst, code)
        print(f"== {name} ({'repair' if repair else 'check'}): e2fsck exit {code}\n" + "\n".join("   " + l for l in out.strip().splitlines()))
    return 0 if worst == 0 else worst


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
