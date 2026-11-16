# ESPRIM Data Center

Academic project for the *Module Projet Data Center* (5th year, ESPRIM). We design a Tier III-style
data center campus end to end: the physical site and buildings, their interiors, the network, and the
services that run on it.

## Repository layout

| Folder | Contents |
|---|---|
| `00_Docs/` | Course material and reference documents |
| `01_Planning/` | Project plan, assumptions, design decisions |
| `02_Blender/` | 3D model of the campus (scenes, scripts, textures, renders) |
| `03_Network/` | GNS3 / Packet Tracer projects, topology, IP and VLAN plan |
| `04_Code/` | Automation and configuration scripts |
| `05_Report/` | Report (French, .docx + .pdf) and presentation |
| `06_Documentation/` | Technical documentation: architecture decisions, site, Blender guide, Git workflow, roadmap |

## Phases

1. Conception - plan and sizing (done)
2. Exterior in Blender - campus, three buildings, parking, power, cameras (done, v04: photoreal renders + drone video)
3. Interiors - white room, technical rooms, NOC
4. Network design in GNS3
5. Services and security
6. Deliverables - renders, video, report, presentation

See `06_Documentation/` for the full technical documentation and `05_Report/` for the phase 1–2 report.

## Working rules

- Numbered folders and versioned scene files (`DC_Exterior_v02.blend`, ...).
- Binary files (`.blend`, images, video, Office files, GNS3 archives) are stored with **Git LFS**.
- Lab VM images (Cisco, pfSense, TrueNAS, Ubuntu): zipped in `03_Network/images/archives/` (Git LFS, not checked out on the lab PC), originals on the external disk `H:\DC-Casablanca-images\`. See [`03_Network/README.md`](03_Network/README.md#lab-images-images) and [`03_Network/images/README.md`](03_Network/images/README.md).
  Run `git lfs install` once on every computer before cloning.
- Clone **without** the 3.9 GB of lab images (everything else, PDFs included, still downloads):
  ```powershell
  git -c lfs.fetchexclude="03_Network/images/archives/*" clone <repo-url>
  cd <repo-folder>
  git config lfs.fetchexclude "03_Network/images/archives/*"   # future pulls skip them too
  ```
  Get them later with `git lfs pull --include "03_Network/images/archives/*"`. Details:
  [Clone or pull without the images](03_Network/README.md#clone-or-pull-without-the-images).
- Commit at the end of each work session with a clear message, e.g. `blender: add IT hall racks`.
