# Roadmap

## Done

- [x] Phase 1 – Conception: objectives, Tier III target, sizing, location scenario, site plan
- [x] Phase 2 – Exterior 3D model: campus, three buildings, energy yard, security, landscape
- [x] Photorealistic pass: Cycles, procedural materials, grass, hills, clouds
- [x] 5 still renders and the drone fly-through camera
- [x] Git repository with LFS, pushed to GitHub (private)
- [x] Documentation (this folder) and phase 1–2 report (`05_Report/`)

## Phase 3 – Interiors (Blender)

- [ ] White room: raised floor, about 200 racks (42U, 600 × 1200 mm) in rows with cold-aisle containment,
      CRAH units along the walls, overhead cable trays, fire detection and suppression
- [ ] Meet-me room (operator entry, fibre patch panels)
- [ ] Technical rooms: TGBT A/B, UPS A/B with battery rooms, chilled-water pumps
- [ ] NOC: video wall, operator desks
- [ ] Walk-through camera from the entrance to a rack
- [ ] Suggested file: `02_Blender/01_Scenes/DC_Interior_v01.blend`, linked to the exterior file

## Phase 4 – Network (GNS3), in `03_Network/`

- [ ] Choose the architecture: **spine-leaf** (recommended for a modern DC: predictable latency, easy to grow)
      or classic core / aggregation / access
- [ ] Redundancy: two spines, a pair of leaves per rack row, dual-homed servers (matches the A/B power logic)
- [ ] Edge: two border routers, two operators (BGP), two firewalls in HA
- [ ] Segmentation: management, production, storage, DMZ, backup (VLAN / VRF)
- [ ] IP addressing plan and naming convention
- [ ] Out-of-band management network for the NOC
- [ ] Tests: failover of a link, a switch, a firewall

## Phase 5 – Services and security

- [ ] Core services: DNS, DHCP, NTP, AAA (RADIUS/TACACS+), syslog
- [ ] Monitoring from the NOC (e.g. Zabbix or Prometheus + Grafana): temperature, power, network
- [ ] Backup and disaster recovery plan
- [ ] Access and security policy

## Phase 6 – Deliverables

- [ ] Final report (update `05_Report` with phases 3–5)
- [ ] Presentation slides
- [ ] Final video: exterior drone flight + interior walkthrough + network demo
