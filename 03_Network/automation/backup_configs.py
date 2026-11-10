"""backup_configs – save the running configuration of every network device to the backup NAS (PLAN_04 NAS.5, D5).

  python automation/backup_configs.py            # every running Cisco device and pfSense firewall
  python automation/backup_configs.py CORE-A     # some devices only

Read from the administration zone like an administrator: one SSH session per device from ADMIN-WS
(`show running-config` on IOS, /cf/conf/config.xml on pfSense), then one upload as `truenas_admin` into
/mnt/tank/backups/configs/<YYYY-MM-DD_HHMM>/ with a SHA256SUMS file. The hourly and daily snapshots of tank/backups
keep the history. The configurations hold password hashes and keys: they go to the NAS only, never into Git (the
evidence file lists names, sizes and hashes).
"""
import hashlib
import io
import sys
import tarfile
import tempfile
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import labctl  # noqa: E402
from adminws import put, ssh_batch  # noqa: E402

NET = Path(__file__).resolve().parents[1]
INV = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
DEST = f"/mnt/{INV['truenas']['pool']['name']}/backups/configs"
# command and completeness marker per platform
READ = {"cisco": ("show running-config", "\nend"), "pfsense": ("cat /cf/conf/config.xml", "</pfsense>")}


def devices():
    """{name: 'cisco' | 'pfsense'} from inventory.devices (IOSv / IOSvL2 and pfSense)."""
    out = {}
    for n, d in INV["devices"].items():
        plat = str(d.get("platform", ""))
        if plat.startswith("iosv"):
            out[n] = "cisco"
        elif plat.startswith("pfsense") or n.startswith("FW-"):
            out[n] = "pfsense"
    return out


def main(argv):
    want = [a.upper() for a in argv if not a.startswith("--")]
    api = labctl.Gns3()
    p = api.project()
    running = {n["name"] for n in api.nodes(p) if n["status"] == "started"}
    devs = {n: k for n, k in sorted(devices().items()) if (not want or n in want)}
    todo = [(n, k) for n, k in devs.items() if n in running]
    skipped = [n for n in devs if n not in running]
    res = ssh_batch([(n.lower(), READ[k][0]) for n, k in todo], timeout=90)
    stamp = time.strftime("%Y-%m-%d_%H%M")
    buf, lines, bad = io.BytesIO(), [], []
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        sums = []
        for (n, k), (rc, text) in zip(todo, res):
            if rc != 0 or READ[k][1] not in text:
                bad.append(f"{n} (rc={rc}, {len(text)} bytes)")
                continue
            data = (text.strip() + "\n").encode()
            fname = f"{n}.{'xml' if k == 'pfsense' else 'cfg'}"
            info = tarfile.TarInfo(fname)
            info.size, info.mtime, info.mode = len(data), int(time.time()), 0o640
            tar.addfile(info, io.BytesIO(data))
            h = hashlib.sha256(data).hexdigest()
            sums.append(f"{h}  {fname}")
            lines.append(f"{fname:16} {len(data):>8} bytes  sha256 {h[:16]}...")
        s = ("\n".join(sums) + "\n").encode()
        info = tarfile.TarInfo("SHA256SUMS")
        info.size, info.mtime, info.mode = len(s), int(time.time()), 0o640
        tar.addfile(info, io.BytesIO(s))
    if not lines:
        print(f"no configuration read (failed: {bad}, not running: {skipped})")
        return 1
    with tempfile.TemporaryDirectory() as d:
        tgz = Path(d) / "configs.tgz"
        tgz.write_bytes(buf.getvalue())
        rc = put("srv-bck-01", tgz, f"{DEST}/incoming.tgz")
    if rc != 0:
        print(f"upload to the NAS failed (rc={rc})")
        return 1
    rc, out = ssh_batch([("srv-bck-01", f"set -e; cd {DEST}; mkdir -m 750 {stamp}; tar -xzf incoming.tgz -C {stamp}; "
                                         f"rm -f incoming.tgz; cd {stamp}; sha256sum -c --quiet SHA256SUMS && "
                                         f"echo verified; ls | wc -l")])[0]
    print(f"SRV-BCK-01:{DEST}/{stamp}/  ({len(lines)} configuration(s), check on the NAS: "
          f"{'OK' if rc == 0 and 'verified' in out else 'FAILED ' + out})")
    for line in lines:
        print(f"   {line}")
    if skipped:
        print(f"   not running: {', '.join(skipped)}")
    if bad:
        print(f"   FAILED: {', '.join(bad)}")
    return 0 if rc == 0 and not bad else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
