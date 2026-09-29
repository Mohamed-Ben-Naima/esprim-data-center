# 06_Documentation

Technical documentation for the ESPRIM Data Center project. The final academic report (in French) is
in `05_Report/`; this folder is the working reference for the team.

| Document | What it covers |
|---|---|
| [01_Architecture_Decisions.md](01_Architecture_Decisions.md) | Every major design choice, why we made it, and what it costs (ADR format) |
| [02_Site_and_Buildings.md](02_Site_and_Buildings.md) | The campus layout, the three buildings, power, cooling and security, with dimensions |
| [03_Blender_Guide.md](03_Blender_Guide.md) | How the 3D model is organised, how to edit it, and how to render stills and the video |
| [04_Git_Workflow.md](04_Git_Workflow.md) | Cloning with Git LFS, commit conventions, versioning rules |
| [05_Roadmap.md](05_Roadmap.md) | What is done, what comes next (interiors, GNS3 network, services) |

## Diagrams

| | |
|---|---|
| ![Site plan](img/plan_masse.png) | ![Power chain](img/alimentation.png) |
| ![Cooling chain](img/refroidissement.png) | ![Security zones](img/securite.png) |

The diagrams are generated from the real coordinates of the Blender model, so they match the 3D scene.

## Project status (September 2026)

| Phase | Status |
|---|---|
| 1. Conception (plan, sizing, site plan) | Done |
| 2. Exterior 3D model (campus, 3 buildings, power, cameras) | Done – `DC_Exterior_v04.blend` |
| 3. Interiors (white room, technical rooms, NOC) | Next |
| 4. Network design in GNS3 | To do |
| 5. Services and security | To do |
| 6. Deliverables (report, video, presentation) | In progress |
