# ESPRIM Data Center – Project Plan
Module Projet Data Center – 5ème année

## 1. Vision
Design a complete Tier III–style data center campus: the physical site, the three buildings from
"Objectif 1" (technique, informatique, logistique), their interiors, and the network that runs inside.
Every design choice answers one of the four "enjeux critiques": continuité électrique, maîtrise du froid,
sécurisation, haute disponibilité.

## 2. Working assumptions (to validate with the team / professor)
| Item | Assumption |
|---|---|
| Target level | Tier III (concurrently maintainable, N+1 everywhere, 99.982 % availability) |
| IT capacity | ~1 MW IT load |
| White space | ~1,500 m², ~200 racks (42U, 5 kW avg) |
| Power | 2 independent HV feeds (line A + line B), on-site substation, N+1 diesel generators, UPS |
| Cooling | Chillers + rooftop dry coolers (free cooling), hot/cold aisle containment, 20–25 °C |
| Security | Perimeter fence, single guarded entrance, CCTV, badge + biometric access zones |
| Site | ~260 m × 180 m campus, room for a future second IT hall |

## 3. Phases
| # | Phase | What we produce | Tools |
|---|---|---|---|
| 1 | Conception | This plan, sizing assumptions, site plan, zone list | Docs, Claude |
| 2 | Exterior (campus) | 3 buildings, parking, substation + HV pylons, generators, fence, landscaping, camera fly-through | Blender |
| 3 | Interiors | Salle blanche (racks, hot/cold aisles, raised floor), technical rooms (UPS, TGBT, chillers), NOC + offices | Blender |
| 4 | Network design | Topology (core / aggregation / access or spine–leaf), redundancy, VLAN + IP plan, DMZ, firewalls | Packet Tracer / GNS3 |
| 5 | Services & security | Servers, storage, monitoring, access policy, backup / DR plan | Packet Tracer / GNS3, docs |
| 6 | Deliverables | Renders, animation, final report, presentation | Blender, Word/PPT |

## 4. Exterior design – buildings (Phase 2)
- **Bâtiment informatique (salle blanche)** – largest, central, windowless for security. Dark facade,
  cyan LED lines, rooftop dry coolers.
- **Bâtiment technique** – next to the IT hall. Power + cooling: TGBT, UPS, chillers. Outside it:
  N+1 generator row, fuel tanks, transformer yard, HV substation fed by two pylon lines.
- **Bâtiment logistique** – near the entrance. NOC, offices, meeting rooms, break rooms. Glass facade.
- **Site** – guarded gatehouse, perimeter fence, CCTV poles, parking with solar carports, roads, trees.

## 5. Folder structure
- 00_Docs/ - course material
- 01_Planning/ - this plan, decisions
- 02_Blender/ - 01_Scenes, 02_Scripts, 03_Textures, 04_Renders
- 03_Network/ - GNS3 / Packet Tracer projects, IP plan
- 04_Code/ - automation and config scripts
- 05_Report/ - final report and presentation

## 6. Rules
- Real-world units (meters) everywhere.
- Name every object (IT_Hall_Facade, Gen_03 …) and group by collection per building.
- New version file at the end of each work session.
