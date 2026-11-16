# 03_Network – Réseau du Data Center Casablanca (GNS3)

Lab GNS3 du Data Center TIA-942 Rated-3 : configuration complète, tests de résilience et rapport.

| Path | Contents |
|---|---|
| `DC_Casablanca_TIA942_R3.gns3` | GNS3 project (runs on the GNS3 VM, compute `vm`) |
| `DC_Casablanca_TIA942_R3_wiring.csv` | Cabling plan (role, endpoints, interfaces) |
| `plans/` | Execution plan (`PLAN_01_GNS3_Configuration.md`) |
| `inventory/` | Single source of truth (`dc_casa.yaml`) |
| `automation/` | Generators, GNS3 API / console driver, resilience tests |
| `configs/` | Generated device configurations |
| `docker/` | Custom service images (built inside the GNS3 VM) |
| `screenshots/` | Numbered screenshots used by the report |
| `report/` | French report: `content/*.md` → `Rapport_Reseau_GNS3_DC_Casablanca.docx/.pdf` |
| `fixgns3.ps1` | Repairs an unreachable VMware GNS3 VM (see report, "Mise en œuvre") |
| `gen_gns3.py` | Generates the topology file |

## Build the report

```powershell
powershell -ExecutionPolicy Bypass -File 03_Network\report\build.ps1
```
Needs Node.js (installs `docx` on first run) and Microsoft Word (TOC refresh + PDF export).

## Lab images (`images/`)

The lab boots from 10 images: 2 Cisco images, 2 installers (pfSense, TrueNAS) and 6 QEMU files (Ubuntu cloud
image, cloud-init seed, offline apt repository ISO, blank disks). They are kept in **three places**:

| Where | What | Size |
|---|---|---|
| **External disk** `H:\DC-Casablanca-images\` | the original files in `cisco\`, `iso\`, `qemu\`, plus a copy of `README.md` and `manifest.json` | 4.2 GB |
| **GitHub** (Git LFS) `03_Network/images/archives/` | the same files zipped: `cisco.zip`, `qemu.zip`, `iso-pfsense.zip`, `iso-truenas.zip.001` + `.002` (split: GitHub refuses LFS files over 2 GB), `archives.json` with the SHA-256 of each part | 3.9 GB |
| **This repo** `03_Network/images/` | `README.md` (every file: size, SHA-256, source, nodes that use it, licence) and `manifest.json` | a few KB |

| Folder | Content |
|---|---|
| `cisco` | Cisco IOSv 15.9(3)M6 (EDGE-A/B) and IOSvL2 2017 (cores, leafs). Cisco licence: keep the repo private |
| `iso` | pfSense CE 2.7.2 (FW-A/B) and TrueNAS SCALE 25.10.7 (SRV-BCK-01) installers |
| `qemu` | Ubuntu 20.04 cloud image, cloud-init seed, offline apt repository ISO, blank disks 100G/20G/10G |

On the lab PC the archives are **not checked out**, to save disk space: git keeps small LFS pointer files in
`images/archives/` (`git config lfs.fetchexclude "03_Network/images/archives/*"`). The images live on H: and GitHub.

| Task | Command (PowerShell, repo root or `03_Network`) |
|---|---|
| Download the archives from GitHub | `git lfs pull --include "03_Network/images/archives/*"` |
| Join, unzip to `H:\DC-Casablanca-images` and check every SHA-256 | `python automation/pack_images.py --unpack` (other folder: add it as argument) |
| Re-pack after an image changes | `python automation/pack_images.py` then commit `images/archives/` |
| Re-gather the originals (PC drives, GNS3 VM, or its disk read offline when the VM cannot boot) | `python automation/collect_images.py` |
| Check the files on H: against the manifest | `python automation/collect_images.py --verify` |
| Put an image back in the GNS3 VM | copy it to `/opt/gns3/images/QEMU/` (GNS3 app: Preferences > QEMU VMs, or `gns3vm.put`) |

Container images (`dc/*`) are not stored as files: they are rebuilt from `docker/` with
`python automation/build_images.py`.
