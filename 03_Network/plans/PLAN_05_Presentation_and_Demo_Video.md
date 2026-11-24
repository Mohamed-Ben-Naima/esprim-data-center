# PLAN_05 — Final presentation + demo video (from 23 Nov 2026, presentation 25 Nov 2026)

Goal: one French slide deck that follows the official outline (I → IV) and tells **what was built, how it was
configured, how it was automated, and how it conforms to TIA-942 and ISO 27001**, plus a **real recorded demo
video** of the lab working (clicks, hovers, typed commands, live failovers). Nothing is faked: every number on a
slide comes from the inventory, the tests or the evidence files, and every scene in the video is the live lab.

## Decisions (taken 23 Nov 2026, "decide alone" rule; change them here if you disagree)

| # | Decision | Why |
|---|---|---|
| D1 | Deck built from the **Artifact Slides type** (French), exported to **.pptx and .pdf**. ~40 slides + 8 annex slides. One theme taken from the Blender renders (graphite + cyan LED). | Opens on any PC, prints, keeps speaker notes. |
| D2 | Slide rule: **1 visual + max 3 bullets**, footer "Comment c'est fait" (tool/script used) and a badge with the norm clause (TIA-942 / ISO 27001 Annex A). Full detail goes in the speaker notes. | Jury reads the picture, listens to you. "Spill the tea" without walls of text. |
| D3 | The firewall slide says **pfSense CE 2.7.2**, not OPNsense: the lab runs pfSense. One line explains the choice (same FreeBSD/pf base as OPNsense, CARP + pfsync + XMLRPC proven in T2). | The outline says OPNsense but the lab does not run it. Migrating takes days and would break T2. Never show a product we do not run. |
| D4 | **AD + LDAP: not built before the presentation** (user decision 23 Nov). Done after the presentation if time allows: Samba 4 AD DC container `SRV-AD-01` (VLAN 100, `10.100.0.12`, realm `DC-CASA.LOCAL`), LDAPS 636 for pfSense, Zabbix and Grafana. In the deck: **one slide "AD / LDAP — prévu"** with this design, no demo, no screenshot. | Keeps the time for the deck, the screenshots and the video. The outline headings stay, and nothing is shown that does not run. |
| D5 | **Database** = the MariaDB behind Zabbix on SRV-MON-01 (already running). Slides cover schema size, users, the backup pulled by TrueNAS and a restore test. No new DB server. | It exists and is real. Adding a DB only for the slide adds RAM and risk. |
| D6 | Video = **real screen recording** at 1080p30 with OBS (installed). Browser scenes are driven by **Playwright** (installed): visible cursor, click ripple, hover highlight, slow human pace. Terminal scenes are typed by a **typist script** at human speed. Every scene can be re-recorded in 1 minute. | Looks human and smooth, never shows typos or hesitations, and is repeatable. |
| D7 | Editing with **ffmpeg** (installed): French chapter cards, captions, zoom on key lines, an on-screen timer for failovers, waits sped up ×4. Outputs: **master video 8–9 min** and **one clip per scene** (20–60 s) embedded in the slides. | Clips play inside the deck; the master is the backup if the live demo fails. |
| D8 | Lab recorded **per profile** (edge/fw, compute, nas, mon), as in the demo. | Host RAM cannot run every node at once ([[lab-capacity-limits]]). |
| D9 | Files: deck and video sources in `05_Report/presentation/`, recording scripts in `03_Network/automation/demo_video/`, MP4s in Git LFS. | Matches 01_Planning (05_Report = report + presentation); scripts sit next to the other automation. |
| D10 | **Screenshots everywhere**: every technical slide (II.3 → III.15) shows at least one **real screenshot** of the live lab. `director.py` saves a PNG at each key moment of the recording, so the screenshot and the video come from the same run and show the same values. | The jury trusts what it sees. Screenshot = proof; same run = consistency rule. |
| D11 | **One visual system** for deck, diagrams and video: palette from the Blender renders (graphite background, cyan accent, one colour per security zone, same colours as the GNS3 VLAN legend), fonts Inter (text) + JetBrains Mono (commands), one icon set (Tabler, MIT licence, line style). Product logos only where the product is named. | Neat and coherent: the jury sees one designed project, not a collage. |
| D12 | **Architecture diagrams redrawn as clean SVG** (19 diagrams, list below), never a raw screenshot alone: the GNS3 screenshot is shown next to the clean drawing. Tools: artifact-diagramming (SVG), draw.io and Mermaid for the layered ones, dataviz for charts. | A screenshot proves it runs, a clean diagram explains it. Both together. |
| D13 | **Internet images**: real hardware photos (UPS, PDU, rack, CCTV camera, generator, cold aisle) and the Casablanca map, only with a free licence (Wikimedia Commons, Unsplash, Pexels; OpenStreetMap for maps), ≥ 1920 px. Each one goes in `05_Report/presentation/assets/CREDITS.md` with its source and licence, plus a credits slide. No copied vendor or Uptime Institute diagrams: we redraw. | High quality without any copyright problem in front of the jury. |
| D14 | **Canva** (connected) for the title slide, the 4 section covers, the "project in numbers" infographic and the video thumbnail/end card, in the D11 style. The deck itself stays in the Slides type (editable, exports .pptx/.pdf); a Canva copy of the deck is made only if you want to present from Canva. | Canva is strong for covers and infographics; the deck stays one source. |
| D15 | **Quality gate** before export: every slide rendered to PNG and checked (no overflow, text ≥ 18 pt, contrast AA, same fonts and margins, every number = `facts.json`), with the design-critique and accessibility-review skills. Video: 1080p, no cursor jumps, no typos, captions in sync, sound levels even, optional royalty-free music (credited). | "Neat and perfect" checked, not hoped. |
| D16 | P0 uses `lab_up.py --profile demo` (no `fw` profile exists): it is the fw/edge set (EDGE-A, FW-A/B, cores, hall B, MON). 23 Nov 01:21: lab up, `demo_check` **12/12** (first run 11/12 = Grafana panel empty just after boot, documented wait). | The prompt named a profile the script does not have; `demo` is the one the runbook rehearsed. |
| D17 | **DHCP is not deployed**: no pool on SRV-INF-01 (`dhcp` role is a no-op), no `ip helper-address` on the cores, pfSense DHCP off by design. The DHCP slide says it: servers use static addresses (the inventory is the IPAM), design = dnsmasq pool + relay on the cores, marked "prévu" like AD. | Never show what does not run (same rule as D3/D4). |
| D18 | Design numbers come from the **Casablanca spec** (PDF Tableaux 5–12: 2 halls, 96 racks, 942 kW, PUE 1.45, 4 × 750 kW, UPS 5 × 250 kW per path) and the lab. `06_Documentation/01_Architecture_Decisions.md` (Blender phase: Greater Tunis, 200 racks, 6 generators) is an older scenario: its renders are used as pictures only, its numbers are not shown. | Two design generations disagree; the spec and the lab are the ones the jury checks. To fix later in 06_Documentation. |
| D19 | Diagrams are drawn as SVG by `assets/build_diagrams.py` (values read from `facts.json` + inventory) and **rendered to PNG with the text baked in** (Playwright + installed Edge, Inter/JetBrains Mono loaded), 2x. The Slides type cannot load fonts inside an SVG, and 30 labels per diagram exceed its 24-pin limit. Playwright's own Chromium is not downloaded: `channel="msedge"`. | Crisp, same fonts as the deck; SVG sources stay editable. |
| D20 | Access heatmap V16 = **zone-to-zone policy** of the inventory (firewall rules + core ACL), not `access_matrix.csv` (most rows "not running" in the demo profile). Proof stays DEMO-05 (0 deviation, every denied flow traced). | A heatmap of "not running" says nothing. |
| D21 | **Canva generation is disabled for the team** (`create-design`: "Your team admin has disabled this tool"; `generate-design`: "Design generation is not enabled in your team"). C1–C6 are built in the deck itself, same D11 style: full-bleed Blender renders + scrim for the title and the 4 section covers, the cyan accent slide for "le projet en chiffres". C7–C8 (video thumbnail, end card) will be made the same way (HTML → PNG). | Canva is a nice-to-have; the covers stay one source with the deck. |
| D22 | **Screenshots v1 taken in P3** from the running demo profile by `automation/demo_video/shots.py` (real commands over SSH from ADMIN-WS, Playwright + Edge through the lab proxy, 1366×768 @1.5x so the text is readable on a slide). Nodes off in the demo profile (NAS, bastion) are shown as **dated evidence traces** (title says the date). P5 re-takes them from the video run. Never run `shots.py` while `verify_lab.py` runs: both use the askpass helper in ADMIN-WS, a parallel batch deletes it (FW-12/FW-15 failed once this way, PASS when re-run alone). | D10 needs screenshots on every technical slide now, not only after P5. |
| D23 | Three lab defects found by the screenshots and **fixed** (23 Nov): (1) Grafana text tiles (Chemin A/B, GTB, NAS pool) showed "hors profil" although the data source returned POWERED: the stat reducer kept numeric fields only → `reduceOptions.fields = /^(?!Time$).+$/` for text tiles (`gen_dashboards.py`, redeployed). (2) BMS-SIM web page printed a literal `%ALARMS%`: the alarm rows were built but never substituted (`docker/bms-sim/app.py`, image rebuilt, node re-created). (3) Two Zabbix "Link down" problems on CORE-A/B Gi0/1 open since 10 Nov (links to FW-B removed by FW.3, ports now parked): closed by API with the reason as message. After the fixes: `demo_check` 12/12, `check_dashboard` same panels as noc.json. | The jury sees the NOC: it has to tell the truth. |
| D24 | **No OBS:** every scene is recorded by Playwright's own recorder (1920×1080, 25 fps, VP8 → H.264 by `edit.py`), headless, so nothing depends on the PC's screen, focus or sleep. The typist types into a terminal page at human speed and the command then runs for real (SSH from ADMIN-WS, a container of the GNS3 VM, or a lab script on the PC streamed line by line). Failover scenes probe a service through the lab proxy every 0.5 s (TCP connect as ADMIN-WS) while the node is stopped through the GNS3 API; timer and outage come from the probe. An SSH key into the GNS3 VM for streaming was refused by the session's safety check: not needed. | Repeatable to the frame, no window to keep in front, same "real lab" rule. |
| D25 | **S1 topology = live view of the GNS3 project drawn from the controller API** (real positions, links, zone drawings, node status started/stopped, hover = name, TIA space, address). The GNS3 web UI did not open the project (it keeps its server list in the browser), and the desktop GUI would need the PC screen. Screenshot 30 comes from this view. | Same data as the GNS3 canvas, readable at 1080p. |
| D26 | **Recorded scenes (23 Nov 03:00–03:40, profile demo):** S1, S3, S4, S5, S6 (Zabbix) + S6b (Grafana, BMS, DCIM: a fresh browser context, Grafana takes 30–200 s to load through the proxy when the VM is busy; the slow load is cut with a `start` mark), S8 T6 (power path A cut, then reset) and T2 (FW-A stopped under a 0.5 s probe: **2.5 s** outage, `report/evidence/video_t2_failover.txt`), S9 (`demo_check` 12/12, speeded ×3 in the edit). **Not recorded:** S2 bastion/TOTP, S7 NAS and T3/T5 – those nodes are outside the demo profile (RAM); the deck shows their dated evidence traces. While recording and encoding, the GNS3 VM sits at load ≈ 10 on 6 vCPU and the leafs log loop-guard blocks (cores late on BPDUs); `demo_check` stays 12/12 with 0 inconsistent port once idle; ffmpeg runs at below-normal priority. | Real lab only; the RAM limit decides what can be filmed in one profile. |
| D27 | **Deck v1 = 24 slides (rule 20–25, whiteboard `00_Docs/Presentation data centerjpeg.jpeg` + `Sommaire général`).** The 61-slide deck stays as **v0** (https://claude.ai/artifact/9SfWhkneCwM7aaFgcNCTd1, annexes for Q&A). v1 (https://claude.ai/artifact/GTcGERUuaHRf8tavD91S4v, sources `05_Report/presentation/deck_v1/`) follows the board: Intro · Partie 1 Architecture (classification Tier I–IV, localisation, composants, redondance = éléments de secours IT + non IT, **refroidissement 20–25 °C**, UPS/PDU, caméras + compteurs) · Partie 2 Conception technique (environnement, VLAN + adressage, services DNS/DHCP, web + DB, NAS, AD/LDAP, **pfSense**, ACL, NOC, sécurité) · **Partie 3 Réalisation pratique = démo 5 min** (minute-by-minute plan + proof slide) · Conclusion. No section-divider slides: merged related topics, one visual per slide minimum. New diagram V8_cooling; cooling facts added to facts.json (spec §6, Tableaux 13/22). Gate 24/24 OK; backup PDF `DC_Casablanca_Soutenance_v1.pdf`. | The jury asked for 20–25 slides and a 5-minute demo part. |
| D28 | **DCIM inlet-temperature drift found and fixed in code (23 Nov).** `docker/dcim/app.py` walked each rack's inlet temperature randomly with no pull-back, so after hours the max reached 29.5–31.1 °C (screenshots 46, 50) – against the 20–25 °C setpoint. Now mean-reverting to each rack's own setpoint (21.0–24.5 °C), simulated max 24.6 °C after 20 000 polls. **Deployed 23 Nov 22:30 (PLAN_06 D2)** – shots 46/50 not re-taken (PLAN_06 D9): rebuild `dc/dcim`, re-create SRV-DCIM-01, re-take shots 46/50 (`shots.py` WEB). Until then slide 10 of v1 captions the 29.5 °C honestly. | The jury sees the NOC: it has to tell the truth (same rule as D23). |
| D29 | **Superseded by PLAN_06 (jury cut 2:57).** The master video must fit the 5-minute demo slot (board: « Démonstration (5 min) »). The edit planned in P6 runs ≈ 6 min: re-cut STORY in `edit.py` to ≤ 5:00 following v1 slide 21 (0:00 topologie · 0:30 réseau · 1:30 pare-feu · 2:15 supervision · 3:00 T6 · 3:45 T2 · 4:30 preuve) before the encode. | Plan B must match the live timing. |

**Needs your OK before P0:** turning off Hyper-V (`bcdedit /set hypervisorlaunchtype off` + reboot). The GNS3 VM
cannot boot without VT-x, so without it there is **no live lab and no new video**. Fallback: a deck built from the
existing evidence (screenshots, outputs, 13 Nov run), labelled with its date.

Assumptions: talk ≈ 20 min + video 8 min + questions. Change the plan if the slot is different.

## Working rule — full autonomy (user, 23 Nov 2026)

Work through **every phase P0 → P8 in one go, without asking for permission and without stopping to wait for
"continue"**. Decide alone (record each decision in the table above), fix problems yourself, commit + push after
each phase, and keep going until P8 is ticked. Stop only for something only the user can do (a reboot, an admin
prompt, a physical disk), and then say exactly what to do. Never stop at "should I go on?".

## Deck — outline mapped to content

Each line: slide(s) → visual → source in the repo → "how it was done" → norm badge.

**I. Introduction et contexte** (3)
- Title: Blender hero render `02_Blender/04_Renders/stills/01_Hero_SouthEast.png`.
- Context and goal: why a Tier III DC in Casablanca, the 6 phases (`01_Planning/ESPRIM_DC_Project_Plan.md`).
- The project in numbers: nodes, VLANs, scripts, tests 59/59, demo 12/12, documents (from `facts.json`, see P1).

**II. Architecture du Data Center**
1. Classification (2): Tier I–IV table with our position, **Rated-3 / Tier III** (concurrently maintainable,
   N+1, 99.982 %), why not Tier IV. Sources: `06_Documentation/01_Architecture_Decisions.md`, `report/content/02_normes.md`.
2. Localisation (2): campus plan `06_Documentation/img/plan_masse.png` + aerial render `03_Aerial.png`, 3 buildings,
   site choices (`06_Documentation/02_Site_and_Buildings.md`).
3. Composants (2): TIA-942 spaces ER / MDA / HDA / EDA mapped on the GNS3 canvas (zones from `layout_topology.py`),
   equipment table (IOSv, IOSvL2, pfSense, servers, containers).
4. Redondance (3): the redundant chain diagram, 2 ISPs eBGP → 2 EDGE HSRP → 2 FW CARP → 2 CORE HSRP/OSPF → 4 LEAF →
   bonded servers; **measured outage chart** T1–T6, M1 (T2 3.0 s, T3 4.5 s, T4 3.0 s, T5 3.1 s); power path A/B.
5. Infrastructure non IT (4): a) cameras: CCTV-SIM, zones and motion events into Zabbix; b) incident counters:
   BMS + Zabbix problem counters, Grafana stat tiles; c) UPS: UPS-A/B, battery, autonomy (BMS-SIM, Grafana power
   dashboard); d) PDU: feeds A/B per rack, load. Render `04_Power_Feed.png`, test T6 (path A lost → alarm ≤ 30 s).

**III. Conception technique**
1. Environnement de travail (3): host, VMware GNS3 VM, GNS3, Docker, Python, Git/LFS, Blender. **Automation pipeline
   diagram**: `inventory/dc_casa.yaml` → generators (`gen_gns3.py`, `gen_configs.py`, `gen_pfsense.py`) → push →
   audits (`fw_audit.py`) → `verify_lab.py` → reports. Script table by family.
2. VLAN (2): table from `report/content/generated/vlans.md`, zones, trunks, Rapid-PVST roots, LACP.
3. Services (1): service map, who serves what, VLAN, port (`inventory` service ports).
4. Stockage NAS (2): TrueNAS SCALE, ZFS mirror, snapshots, **pull model** (ransomware argument), hall B, restore test.
5. Plan d'adressage (1): `10.<vlan>.0.0/24`, gateways `.1` (HSRP VIP), /30 transit, RFC 5737 ISP ranges, MGMT.
6. DNS (1): SRV-INF-01 dnsmasq, internal zone, forwarders, pfSense resolver off by design.
7. DHCP (1): SRV-INF-01 + relay (P1 checks how the relay is configured before writing the slide).
8. Web Server (1): SRV-WEB-01 nginx in the DMZ (VLAN 50), NAT port forward, path from the Internet.
9. AD and 10. LDAP (1 slide together): design only, marked "prévu", per D4.
11. Firewall (3): pfSense, CARP/pfsync/XMLRPC, rule sets, NAT, logs. Screenshots `screenshots/21–25`.
12. Base de données (1): per D5.
13. ACLs (2): core ACL (`generated/core_acl.md`), **access-matrix heatmap** from `report/evidence/access_matrix.csv`.
14. Supervision NOC (2): Zabbix (SNMPv3, templates, triggers), Grafana, syslog viewer, alert ≤ 1 min, NOC render.
15. Sécurité (3): defence in depth diagram; bastion + TOTP, SNMPv3, SSH keys, no secrets on command lines;
    **ISO 27001 Annex A matrix** (control → what we did → evidence file); TIA-942 checklist.

**IV. Conclusion** (4)
- Results: 59/59 checks, 12/12 demo, outage times, conformity scorecard (TIA-942 + ISO 27001).
- **Behind the scenes** (spill the tea): the real problems and fixes, e.g. IOSvL2 boot hang, missing RSA keys
  (`cisco_heal.py`), HSRP flap from fast timers + VM swap, USB disk freeze, pfSense via VNC, 2 GB LFS limit,
  Hyper-V blocking VT-x.
- Limits and next steps. Thanks + questions.

**Annex** (8, for questions): full VLAN and address tables, ACL matrix, test list, commands cheat sheet, tools and
versions, ISO detail, glossary.

## Demo video — storyboard (master ≈ 8 min 30)

| # | Scene | What is shown (live) | Profile |
|---|---|---|---|
| S0 | Opening 0:00–0:25 | Blender drone flythrough (existing MP4) + title | — |
| S1 | Topology 0:25–1:00 | GNS3 canvas, zoom on the zones, hover on node labels | any |
| S2 | Admin entry 1:00–1:40 | SSH to the bastion with TOTP, ADMIN-WS portal | fw |
| S3 | Network 1:40–2:40 | Typed: `show standby brief`, OSPF neighbours, BGP summary, etherchannel, STP | edge/fw |
| S4 | Firewall 2:40–3:30 | pfSense GUI: CARP status, rules (hover), NAT, live logs | fw |
| S5 | Services 3:30–4:20 | `dig` on DNS, DHCP lease, `curl` to the web site through NAT | fw + mon |
| S6 | NOC 4:20–5:20 | Zabbix problems, Grafana power (UPS/PDU), CCTV, DCIM racks | mon |
| S7 | NAS 5:20–5:55 | TrueNAS pool, snapshots, last pull, restore one file | nas |
| S8 | Chaos 5:55–7:45 | Continuous ping + timer: T2 FW-A off, T3 CORE-A off, T5 SRV-CMP-01 off (keepalived), T6 BMS path A, then recovery | per test |
| S9 | Proof 7:45–8:30 | `verify_lab.py` → PASS count, end card | any |

## Screenshots — list (D10)

Saved in `03_Network/screenshots/` (PNG, 1920×1080 or cropped to the useful part), named `<nn>_<node>_<what>.png`.
Already there and reused: `02` topology, `12/13` CARP console, `14/15` NAT and rules console, `18` XMLRPC sync,
`20` ADMIN-WS portal, `21–25` pfSense GUI (CARP master, rules, NAT, logs, CARP backup). New ones:

| # | File | Slide | How |
|---|---|---|---|
| 30 | `30_gns3_topology_zones.png` | II.3, III.1 | GNS3 GUI, zones + labels |
| 31 | `31_bastion_totp_login.png` | III.15 | terminal, SSH + TOTP code |
| 32–34 | `32_core-a_hsrp_ospf.png`, `33_edge-a_bgp.png`, `34_leaf-a1_etherchannel_stp.png` | II.4, III.2 | terminal, typed `show` commands |
| 35 | `35_vlan_trunks.png` | III.2 | terminal, `show interfaces trunk` |
| 36–37 | `36_srv-inf-01_dns_dig.png`, `37_dhcp_lease.png` | III.6, III.7 | terminal |
| 38 | `38_srv-web-01_site_via_nat.png` | III.8 | browser through the WAN NAT |
| 42 | `42_mariadb_zabbix_db.png` | III.12 | terminal, DB size + tables |
| 43 | `43_core_acl_denied.png` | III.13 | terminal, denied flow + ACL hit counters |
| 44–47 | `44_zabbix_problems.png`, `45_zabbix_hosts.png`, `46_grafana_power_ups_pdu.png`, `47_syslog_viewer.png` | II.5, III.14 | browser |
| 48–50 | `48_cctv_cameras.png`, `49_bms_incident_counters.png`, `50_dcim_racks.png` | II.5 | browser |
| 51–53 | `51_truenas_pool.png`, `52_truenas_snapshots.png`, `53_truenas_restore.png` | III.4 | browser |
| 54–58 | `54_t2_fw_failover.png`, `55_t3_core_failover.png`, `56_t4_leaf_failover.png`, `57_t5_keepalived.png`, `58_t6_bms_alarm.png` | II.4 | ping + timer, before/after |
| 59 | `59_verify_lab_pass.png` | IV | terminal, final PASS count |

Each new screenshot is listed in `report/content` (French report) and in the Field Book gallery too.

## Visual kit (D11–D14)

Files in `05_Report/presentation/assets/` (`diagrams/*.svg`, `photos/`, `icons/`, `canva/`, `CREDITS.md`).

| # | Diagram / visual | Slide | Tool |
|---|---|---|---|
| V1 | Casablanca location map + campus plan (3 buildings, gate, power feeds) | II.2 | OpenStreetMap + `plan_masse.png` redrawn |
| V2 | Tier I–IV comparison with our position (Rated-3) | II.1 | SVG |
| V3 | TIA-942 spaces (ER, MDA, HDA, EDA, halls A/B) as a floor plan | II.3 | SVG |
| V4 | **Full logical architecture** in layers: ISP → EDGE → FW → CORE → LEAF → servers, zones coloured | II.3, III | draw.io / SVG |
| V5 | Redundancy chain with the protocol of each tier (eBGP, HSRP, CARP, OSPF, LACP, bond, keepalived) | II.4 | SVG |
| V6 | Measured outage times T1–T6, M1 vs target | II.4 | dataviz chart |
| V7 | Power path A/B: utility → UPS → PDU → rack, generator | II.5 | SVG + real photos |
| V8 | Non-IT: cameras, BMS counters, UPS, PDU (photo + live screenshot side by side) | II.5 | photos + screenshots |
| V9 | Lab environment stack (host → VMware → GNS3 VM → QEMU/Docker nodes) | III.1 | SVG |
| V10 | **Automation pipeline** (inventory → generators → push → audit → verify → reports) | III.1 | SVG |
| V11 | VLAN and zone map | III.2 | SVG |
| V12 | Addressing plan as blocks (10.<vlan>.0.0/24, VIPs, /30 transit) | III.5 | SVG |
| V13 | Service map (who serves whom, port) incl. DNS, DHCP, web DMZ path | III.3, III.6–8 | SVG |
| V14 | Backup pull flow (TrueNAS pulls, server cannot delete) | III.4 | SVG |
| V15 | Firewall zones and flows, CARP/pfsync/XMLRPC pair | III.11 | SVG |
| V16 | Access matrix heatmap | III.13 | dataviz |
| V17 | Monitoring pipeline (SNMPv3 → Zabbix → Grafana, syslog, alerts) | III.14 | SVG |
| V18 | Defence in depth + admin path (admin → bastion TOTP → ADMIN-WS → devices) | III.15 | SVG |
| V19 | ISO 27001 / TIA-942 conformity scorecard; AD/LDAP "prévu" design (dashed) | III.9–10, III.15, IV | dataviz / SVG |
| C1–C6 | Title, 4 section covers, "project in numbers" infographic | I–IV | Canva |
| C7–C8 | Video thumbnail + end card | video | Canva |

## Phases

### Day 1 — Mon 23 Nov
- [x] **P0 Unblock the lab** (30 min, needs your OK): Hyper-V off + reboot, start the GNS3 VM, `demo_check.py` 12/12.
      Done 23 Nov 01:21: HypervisorPresent False, VM started by vmrun, `lab_up --profile demo` (D16), 12/12 (`report/evidence/demo_s6_check.txt`).
- [x] **P1 Fact sheet** (1 h, no lab): `05_Report/presentation/facts.json` with every number used (nodes, VLANs,
      IPs, tests, outage times, versions, ISO controls) from the inventory, tests and evidence. Check the DHCP relay,
      the DB backup and the DCIM storage. Slides and video read only from this file.
      Done: `build_facts.py` -> `facts.json`. Found: no DHCP (D17); DB = nightly dump 01:30 pulled by the NAS 02:00 (110 s);
      DCIM keeps no store (state computed from BMS-SIM every poll); design numbers from the spec (D18).
- [x] **P2 Visual kit** (3 h, no lab): D11 style sheet, diagrams V1–V19 (SVG), licensed photos + `CREDITS.md`,
      Canva covers C1–C6. Every diagram checked against the inventory (names, IPs, VLANs).
      Done: `assets/build_diagrams.py` → 18 SVG + PNG (V2–V19, V19b), values from facts.json/inventory, each one reviewed
      rendered; 6 Commons photos + OSM map with licences in `assets/CREDITS.md`; covers per D21.
- [x] **P3 Deck v1** (3 h): every slide, diagrams (SVG), charts (outage times, access heatmap, conformity
      scorecard), screenshots, speaker notes in French. Text pass with the humanizer skill.
      Done: Slides artifact https://claude.ai/artifact/9SfWhkneCwM7aaFgcNCTd1 – 58 slides (50 + 8 annexes generated by
      `deck/gen_annex.py`), sources in `05_Report/presentation/deck/project/`. Gate D15: `deck/render_check.py` renders every
      slide (Edge) and checks canvas overflow, footer band, text < 24 px, broken images: 58/58 OK; every number on the
      slides checked against facts.json (14/14). Fresh proof 23 Nov: verify_lab 59 PASS / 0 FAIL, demo_check 12/12.

### Day 2 — Tue 24 Nov
- [x] **P4 Video tooling** (2 h): `automation/demo_video/director.py` (Playwright scenes, cursor/ripple/hover
      overlay), `typist.py` (human-speed typing), `edit.py` (ffmpeg: cards, captions, zooms, timer, speed-ups),
      OBS scene 1080p30. Dry run on S1.
      Done (D24, D25): `director.py` (scenes S1 S3 S4 S5 S6 S8T2 S8T6 S9, cursor/ripple/hover overlay, typist terminal,
      live probe + timer), `edit.py` (cards/captions/thumbnail/end card rendered by Edge, ffmpeg clips + master). Dry runs
      S1 and S3 checked frame by frame (1080p, crisp text). Rehearsal kit drafted early: `05_Report/presentation/REPETITION.md`.
- [x] **P5 Record + screenshots** (3 h): scenes S1–S9 per profile, PNGs 30–59 (except 39–41) saved by the same run; retake until
      clean; RAM check between profiles. Check every screenshot shows the value written on its slide.
      Done (D26): 9 scenes recorded from the live demo profile; screenshots 30, 21v, 32v, 46v, 58v, 59v and the T2
      outage frame come from the same run. Bastion, NAS, T3/T5 stay as dated traces (outside the RAM profile).
- [ ] **P6 Edit and embed** (2 h): master MP4 + scene clips (Canva thumbnail/end card C7–C8), clips into the
      slides, quality gate D15, export .pptx + .pdf.
      Partly done (23 Nov ~04:10): deck 61 slides (T2 and T6 slides with the live stills, video chapters slide with
      the thumbnail), gate 61/61 OK, backup PDF `05_Report/presentation/DC_Casablanca_Soutenance.pdf` (also on H:).
      Clips S1–S6b encoded; the last encode (T6, T2, S9 clips + master) was **stopped by Claude Code: PC critically low
      on memory** – not relaunched without the user's OK. Lab and GNS3 VM since stopped (10.8 GB free). To finish:
      `python automation/demo_video/edit.py` (≈ 10 min, skips the scenes already encoded), then upload clips
      S8_T2_fw/S8_T6_power and add `data-video` on slides demo-t2/demo-t6. Editable .pptx: Share › Export on the page.
- [x] **P7 Rehearsal kit** (1 h): timing per section, cue cards, **20 likely jury questions with answers**, live-demo
      fallback (master MP4 + PDF on USB and `H:`), node start order for a live demo.
      Done: `05_Report/presentation/REPETITION.md` (timing, cue cards, 20 Q&A, plan B); PDF + kit copied to
      `H:\DC_Casablanca_Soutenance\`. USB stick copy = user (physical); master MP4 joins after the last encode.
- [ ] **P8 Close** (30 min): READMEs + Field Book mention the presentation, commit `presentation(P<n>)`, push (MP4 in
      LFS), lab stopped cleanly.
      Partly done: READMEs (05_Report, 03_Network) list the presentation files; `lab_down.py` 55 s, project closed,
      GNS3 VM soft-stopped. Field Book not rebuilt (no new section); master MP4 to commit after the last encode.

### Wed 25 Nov — present.

Priority if time runs out: deck (P1, P3) → screenshots + video (P4–P6) → rehearsal kit (P7).

### After the presentation (if time)
- [ ] **P9 AD/LDAP** per D4: image `dc/samba-ad`, inventory + ACL + DNS forward, users/groups, LDAPS to
      pfSense/Zabbix/Grafana, tests `ADM-AD-*` in `tests.yaml`, `verify_lab.py` still all PASS.

## Before the next session — reboot (you do it)

1. PowerShell **as administrator**: `bcdedit /set hypervisorlaunchtype off`
2. Reboot the PC. Plug in the external disk `H:` (the GNS3 VM disk is on it).
3. Open Claude Code in `C:\Users\ASUS\Documents\ESPRIM\Data Center` and paste the prompt below.

Undo later (only if WSL2, Docker Desktop or Windows Sandbox are needed): `bcdedit /set hypervisorlaunchtype auto` + reboot.

## Next-session prompt (paste after the reboot)

```
Read 03_Network/plans/PLAN_05_Presentation_and_Demo_Video.md and do it, starting at P0.
P0: check VT-x is free (bcdedit /enum shows hypervisorlaunchtype Off, H: present), start the GNS3 VM with vmrun,
open the project, lab_up.py --profile fw, demo_check.py 12/12. If the VM still refuses VT-x, stop and tell me.
Then P1 (facts.json), P2 (visual kit D11-D14: SVG diagrams, licensed photos, Canva covers) and P3
(deck v1 from the Slides type, French, screenshots of D10, quality gate D15).
No Samba/AD/LDAP before the presentation (D4). Tick the boxes in PLAN_05, commit + push after each phase.
Full autonomy: do every phase P0 -> P8 without asking permission and without stopping for "continue";
stop only for something only I can do. Decide alone, caveman replies, sign 🍀.
```

## Skills and tools used

Artifact Slides type + `artifact-design` (deck), Canva (covers, infographic,
thumbnail), draw.io / Mermaid, `design-critique` + `accessibility-review` (quality gate), web search for licensed
photos, `artifact-diagramming` (architecture, pipeline, defence in depth),
`dataviz` (outage chart, heatmap, scorecard), `humanizer` (French text), `pptx`/`pdf` (exports and checks), Playwright,
OBS, ffmpeg, the lab's own scripts (`lab_up.py`, `demo_check.py`, `verify_lab.py`, `vnc.py`, `render_topology.py`).
