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
| `05_Report/` | Final report and presentation |

## Phases

1. Conception - plan and sizing (done)
2. Exterior in Blender - campus, three buildings, parking, power, cameras (done, v02)
3. Interiors - white room, technical rooms, NOC
4. Network design in GNS3
5. Services and security
6. Deliverables - renders, video, report, presentation

See `01_Planning/ESPRIM_DC_Project_Plan.md` for details.

## Working rules

- Numbered folders and versioned scene files (`DC_Exterior_v02.blend`, ...).
- Binary files (`.blend`, images, video, Office files, GNS3 archives) are stored with **Git LFS**.
  Run `git lfs install` once on every computer before cloning.
- Commit at the end of each work session with a clear message, e.g. `blender: add IT hall racks`.
