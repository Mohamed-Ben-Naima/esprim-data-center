# Lab images

Every disk image, ISO and container image the GNS3 lab uses. The files are kept on the external USB disk in
**`H:/DC-Casablanca-images/`** (`cisco/`, `iso/`, `qemu/`, with a copy of this README and the manifest). They are
**not in git** (size, and the Cisco licence forbids publishing them): only this README and `manifest.json` are
tracked. Re-gather them with `python automation/collect_images.py`, check them with `--verify`.

| File | Size | Used by | What | Licence |
|---|---|---|---|---|
| `cisco/vios-adventerprisek9-m.spa.159-3.m6.qcow2` | 54.7 MB | EDGE-A, EDGE-B | Cisco IOSv 15.9(3)M6 router | Cisco licence (CML): private copy, never publish |
| `cisco/vios_l2-adventerprisek9-m.03.2017.qcow2` | 39.3 MB | CORE-A/B, LEAF-A1/A2/B1/B2 | Cisco IOSvL2 switch (2017) | Cisco licence (CML): private copy, never publish |
| `iso/pfSense-CE-2.7.2-RELEASE-amd64.iso` | 834.2 MB | FW-A, FW-B | pfSense CE 2.7.2 installer | Apache 2.0 |
| `iso/TrueNAS-SCALE-25.10.7.iso` | 2,230.9 MB | SRV-BCK-01 | TrueNAS SCALE 25.10.7 installer | GPL / free |
| `qemu/ubuntu-20.04-server-cloudimg-amd64.img` | 598.2 MB | SRV-CMP-01/02/03, SRV-STO-01, SRV-INF-01, SRV-MON-01, SRV-BASTION | Ubuntu 20.04 cloud image (base disk of the servers) | free |
| `qemu/ubuntu-cloud-init-data.iso` | 0.4 MB | Ubuntu servers | cloud-init seed (first boot settings) | lab-generated |
| `qemu/dc-lab-repo-focal-v2.iso` | 476.6 MB | SRV-CMP-01/02, SRV-MON-01, SRV-BASTION | offline apt repository (built by automation/build_repo.sh) | lab-generated |
| `qemu/empty100G.qcow2` | 0.2 MB | FW-A, FW-B | blank disk (pfSense install target) | GNS3 |
| `qemu/empty20G.qcow2` | 0.2 MB | SRV-BCK-01 | blank disk (TrueNAS boot) | GNS3 |
| `qemu/empty10G.qcow2` | 0.2 MB | SRV-BCK-01 | blank disks (ZFS mirror of pool tank) | GNS3 |

## Where they go in the GNS3 VM

All QEMU images and ISOs live in `/opt/gns3/images/QEMU/` in the GNS3 VM. To restore one, upload it from the GNS3 app
(Edit > Preferences > QEMU VMs > New, or drag the file onto the template) or copy it with
`python -c "import sys; sys.path.insert(0,'automation'); import gns3vm; gns3vm.put('images/<folder>/<file>', '/opt/gns3/images/QEMU/<file>')"`.

## Container images (rebuilt from this repo, not stored as files)

| Image | Used by | Source folder |
|---|---|---|
| `dc/admin-ws:1.0` | ADMIN-WS | `docker/admin-ws/` |
| `dc/frr-isp:1.0` | ISP-A, ISP-B | `docker/frr-isp/` |
| `dc/syslog:1.1` | SYSLOG | `docker/syslog/` |
| `dc/bms-sim:1.0` | BMS-SIM | `docker/bms-sim/` |
| `dc/cctv-sim:1.0` | CCTV-SIM | `docker/cctv-sim/` |
| `dc/dcim:1.0` | SRV-DCIM-01 | `docker/dcim/` |
| `dc/web:1.0` | SRV-WEB-01 | `docker/web/` |

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
3a1aac6ea18d641206a8ccb511122b3ae25b71f139c90b2a9a3d02350ff8d857  cisco/vios-adventerprisek9-m.spa.159-3.m6.qcow2
6f98da74fefa2a5232802fae72907ede62833c0b7bec491b6e0594cf4fb84389  cisco/vios_l2-adventerprisek9-m.03.2017.qcow2
441005f79ea0c155bc4b830a2b4207f8c0804cf7b075d2a6489c0a136cbc5d51  iso/pfSense-CE-2.7.2-RELEASE-amd64.iso
54ce9441ce66966a392e28f63604ca3c2c083d0bec4db7bb5af2f74f7a007c8e  iso/TrueNAS-SCALE-25.10.7.iso
500a4be0e6dda27d911a3b658ceaad09595b81f10b602b58afb630904a8b04f4  qemu/ubuntu-20.04-server-cloudimg-amd64.img
612cec78d76d933909e4d784d1424a1192fe48c19363cb21b07b6c4bd3b6b7c2  qemu/ubuntu-cloud-init-data.iso
7a161472b0ba230df962f768209011d63afccca4ce43767aa0967cbc4e2c6c01  qemu/dc-lab-repo-focal-v2.iso
b333b43b2548e1f9581d4fb52f5c2d603c7d43a14b70a689ddd3e3bc913e6bb4  qemu/empty100G.qcow2
693313d3d5af9d7c4b7f145b141bb3342d439bfa1a445b5ffd1f1cdef5716476  qemu/empty20G.qcow2
23a1edeac969b498874484637169fd08de4a7f18f438594fee7103236ba000db  qemu/empty10G.qcow2
```
