"""Gather every image the lab uses into H:/DC-Casablanca-images/ (external disk) and write a checksum manifest.

  python automation/collect_images.py            copy what is missing, then (re)write images/manifest.json + README.md
  python automation/collect_images.py --verify   only re-check sizes and SHA-256 against the manifest

Sources: the PC drives (E:\\, H:\\gns3 images, Downloads, ~/GNS3/images) and, for images that only exist inside the
GNS3 VM (Cisco vIOS, generated ISOs), /opt/gns3/images/QEMU/ via vmrun (GNS3 VM must be running).
The image files are NOT committed (size, licences: Cisco images must never be pushed); images/.gitignore keeps only
the manifest and the README in git.
"""
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

NET = Path(__file__).resolve().parents[1]
OUT = NET / "images"            # manifest + README (in git)
STORE = Path(os.environ.get("DC_IMAGES", r"H:\DC-Casablanca-images"))  # the image files (external USB disk)
HOME = Path.home()
SRC_DIRS = [Path("E:/"), Path("H:/gns3 images"), HOME / "Downloads", HOME / "GNS3/images/QEMU"]
VM_DIR = "/opt/gns3/images/QEMU"

# name, folder, used by, what it is, licence note
IMAGES = [
    ("vios-adventerprisek9-m.spa.159-3.m6.qcow2", "cisco", "EDGE-A, EDGE-B", "Cisco IOSv 15.9(3)M6 router",
     "Cisco licence (CML): private copy, never publish"),
    ("vios_l2-adventerprisek9-m.03.2017.qcow2", "cisco", "CORE-A/B, LEAF-A1/A2/B1/B2", "Cisco IOSvL2 switch (2017)",
     "Cisco licence (CML): private copy, never publish"),
    ("pfSense-CE-2.7.2-RELEASE-amd64.iso", "iso", "FW-A, FW-B", "pfSense CE 2.7.2 installer", "Apache 2.0"),
    ("TrueNAS-SCALE-25.10.7.iso", "iso", "SRV-BCK-01", "TrueNAS SCALE 25.10.7 installer", "GPL / free"),
    ("ubuntu-20.04-server-cloudimg-amd64.img", "qemu", "SRV-CMP-01/02/03, SRV-STO-01, SRV-INF-01, SRV-MON-01, "
     "SRV-BASTION", "Ubuntu 20.04 cloud image (base disk of the servers)", "free"),
    ("ubuntu-cloud-init-data.iso", "qemu", "Ubuntu servers", "cloud-init seed (first boot settings)", "lab-generated"),
    ("dc-lab-repo-focal-v2.iso", "qemu", "SRV-CMP-01/02, SRV-MON-01, SRV-BASTION",
     "offline apt repository (built by automation/build_repo.sh)", "lab-generated"),
    ("empty100G.qcow2", "qemu", "FW-A, FW-B", "blank disk (pfSense install target)", "GNS3"),
    ("empty20G.qcow2", "qemu", "SRV-BCK-01", "blank disk (TrueNAS boot)", "GNS3"),
    ("empty10G.qcow2", "qemu", "SRV-BCK-01", "blank disks (ZFS mirror of pool tank)", "GNS3"),
]
DOCKER = [("dc/admin-ws:1.0", "ADMIN-WS"), ("dc/frr-isp:1.0", "ISP-A, ISP-B"), ("dc/syslog:1.1", "SYSLOG"),
          ("dc/bms-sim:1.0", "BMS-SIM"), ("dc/cctv-sim:1.0", "CCTV-SIM"), ("dc/dcim:1.0", "SRV-DCIM-01"),
          ("dc/web:1.0", "SRV-WEB-01")]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def find_local(name):
    for d in SRC_DIRS:
        if (d / name).is_file():
            return d / name
    return None


def from_vm(name, dest):
    sys.path.insert(0, str(Path(__file__).parent))
    import gns3vm
    gns3vm.get(f"{VM_DIR}/{name}", str(dest))
    return f"GNS3 VM {VM_DIR}"


def from_vmdk(name, dest):
    """GNS3 VM off (or VT-x unavailable): read its data disk read-only (pip install dissect.hypervisor dissect.extfs dissect.volume)."""
    from dissect.extfs import ExtFS
    from dissect.hypervisor import vmdk
    from dissect.volume import disk
    d = vmdk.VMDK(open(r"H:\GNS3 VM\GNS3 VM-disk2.vmdk", "rb"))
    src = ExtFS(disk.Disk(d).partitions[0].open()).get(f"/gns3/images/QEMU/{name}").open()
    with open(dest, "wb") as o:
        shutil.copyfileobj(src, o, 1 << 22)
    return "GNS3 VM data disk (read offline, /opt/gns3/images/QEMU)"


def main(argv):
    OUT.mkdir(exist_ok=True)
    man_path = OUT / "manifest.json"
    old = {i["file"]: i for i in json.loads(man_path.read_text(encoding="utf-8"))["images"]} if man_path.exists() else {}
    rows, bad = [], 0
    for name, folder, used, what, lic in IMAGES:
        dest = STORE / folder / name
        dest.parent.mkdir(exist_ok=True)
        src = old.get(f"{folder}/{name}", {}).get("source", "")
        if "--verify" not in argv and not dest.exists():
            local = find_local(name)
            try:
                if local:
                    shutil.copy2(local, dest)
                    src = str(local)
                else:
                    try:
                        src = from_vm(name, dest)
                    except Exception:  # noqa: BLE001
                        src = from_vmdk(name, dest)
                print(f"copied  {folder}/{name}  <- {src}")
            except Exception as e:  # noqa: BLE001
                print(f"MISSING {folder}/{name}: {e}")
        if not dest.exists():
            bad += 1
            rows.append(dict(file=f"{folder}/{name}", used_by=used, what=what, licence=lic, source=src, size=None,
                             sha256=None))
            continue
        digest = sha256(dest)
        ref = old.get(f"{folder}/{name}", {}).get("sha256")
        if "--verify" in argv:
            ok = digest == ref
            bad += not ok
            print(f"{'OK  ' if ok else 'BAD '} {folder}/{name}")
        rows.append(dict(file=f"{folder}/{name}", used_by=used, what=what, licence=lic, source=src,
                         size=dest.stat().st_size, sha256=digest))
    if "--verify" in argv:
        print(f"{len(rows) - bad}/{len(rows)} image(s) match the manifest")
        return 1 if bad else 0
    man_path.write_text(json.dumps(dict(images=rows, docker=[dict(image=i, used_by=u) for i, u in DOCKER]),
                                   indent=1), encoding="utf-8")
    mb = lambda s: f"{s / 1048576:,.1f} MB" if s else "missing"  # noqa: E731
    table = "\n".join(f"| `{r['file']}` | {mb(r['size'])} | {r['used_by']} | {r['what']} | {r['licence']} |"
                      for r in rows)
    sums = "\n".join(f"{r['sha256'] or 'missing'}  {r['file']}" for r in rows)
    dock = "\n".join(f"| `{i}` | {u} | `docker/{i.split('/')[1].split(':')[0]}/` |" for i, u in DOCKER)
    (OUT / "README.md").write_text(f"""# Lab images

Every disk image, ISO and container image the GNS3 lab uses. The files are kept on the external USB disk in
**`H:/DC-Casablanca-images/`** (`cisco/`, `iso/`, `qemu/`, with a copy of this README and the manifest). They are
**not in git** (size, and the Cisco licence forbids publishing them): only this README and `manifest.json` are
tracked. Re-gather them with `python automation/collect_images.py`, check them with `--verify`.

| File | Size | Used by | What | Licence |
|---|---|---|---|---|
{table}

## Where they go in the GNS3 VM

All QEMU images and ISOs live in `/opt/gns3/images/QEMU/` in the GNS3 VM. To restore one, upload it from the GNS3 app
(Edit > Preferences > QEMU VMs > New, or drag the file onto the template) or copy it with
`python -c "import sys; sys.path.insert(0,'automation'); import gns3vm; gns3vm.put('images/<folder>/<file>', '/opt/gns3/images/QEMU/<file>')"`.

## Container images (rebuilt from this repo, not stored as files)

| Image | Used by | Source folder |
|---|---|---|
{dock}

Rebuild them in the GNS3 VM with `python automation/build_images.py`, then re-create a node with
`python automation/deploy_containers.py <NODE>`.

## Copy on GitHub (Git LFS, zipped)

The same images are in the repo as zip archives in `images/archives/` (Git LFS; the TrueNAS ISO is split into
`.001`/`.002` parts because GitHub refuses LFS files over 2 GB). `archives.json` lists each part with its SHA-256.

```powershell
git lfs pull --include "03_Network/images/archives/*"      # download the archives (about 3.9 GB)
python automation/pack_images.py --unpack                  # join, unzip to H:\DC-Casablanca-images, verify SHA-256
python automation/pack_images.py                           # re-pack after an image changes
```

On the lab PC the archives are not kept checked out (pointer files only, `lfs.fetchexclude`), to save disk space.

## SHA-256

```
{sums}
```
""", encoding="utf-8")
    print(f"manifest: {len(rows) - bad}/{len(rows)} image(s) present -> images/README.md")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
