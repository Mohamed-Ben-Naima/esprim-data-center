# Plan — Configuration complète de la topologie GNS3 « DC Casablanca TIA-942 Rated-3 »

> Copied as the first execution step to `03_Network/plans/PLAN_01_GNS3_Configuration.md`.
> Language: plan in English (working doc), **final report in French** (matches `05_Report/` and the spec PDF).

## Working rule (requested by the user)
After **every sub-task**: add its content to the report (`report/content/*.md`), rebuild the report
(`report/build.ps1` → .docx + .pdf), update the progress table, and **commit**.

## Context

The GNS3 lab (`03_Network/DC_Casablanca_TIA942_R3.gns3`, 27 nodes / 57 links) now runs on the GNS3 VM
(fixed earlier this session). Every node is still **blank**: no device configuration, no addressing, no
firewall policy. The spec `05_Report/Datacenter_Casablanca_TIA942_GNS3_detaille.pdf` (ch. 7, 9.4, 10, 11, 12,
annexes B/D) defines the target: VLAN/IP plan (Tables 15–16), servers (Table 25), routing/HA choices
(Table 17), default-deny flow matrix (Table 18), and resilience tests T1–T6 (Table 27).
Goal: configure **everything** to that spec and the applicable norms, prove it with tests, and deliver a
professional, well-structured French report with screenshots — all organized under `03_Network/`.

**User decisions (confirmed):** French report · add **SW-OUT** switch for VLAN 901 (as PDF §11.3) ·
real Internet via **GNS3 NAT nodes behind ISP-A/ISP-B** · **full Zabbix + Grafana** on SRV-MON-01.

---

## 1. Target architecture (reference for all tasks)

```
              Internet (GNS3 NAT-A / NAT-B)
                 │                 │
             ISP-A AS64500     ISP-B AS64501        FRR containers, default-originate, MASQUERADE
                 │  ╲         ╱  │                  eBGP full mesh (4 sessions), timers 3/9
             EDGE-A ══ iBGP/OSPF ══ EDGE-B          AS65100, announce 192.0.2.0/24, LP 200 via ISP-A
                 └──── SW-OUT (VLAN 901) ────┘      HSRP VIP .6 (FW default gw)
                   FW-A ══ pfsync em2 ══ FW-B       pfSense 2.7.2 CARP HA, NAT, zones, default deny
               lagg0 (em3/em4) VLAN 902   em5 DMZ ── SW-DMZ ── SRV-WEB-01
                 │                 │      em6 trunk(10,90) ── SW-MGMT ── OOB of all devices + BASTION + ADMIN-WS
             CORE-A ══ Po1 LACP ══ CORE-B           HSRPv2 SVIs, RPVST+ roots, OSPF a0 (998/902), inter-VLAN ACLs
             ╱   ╲  trunks  ╱   ╲
       LEAF-A1 LEAF-A2   LEAF-B1 LEAF-B2            Hall A / Hall B, dual-homed servers (bond active-backup)
```

### 1.1 VLANs & subnets (PDF Table 15 + technical VLANs)
| VLAN | Name | Subnet | Gateway (VIP) | Active |
|---|---|---|---|---|
| 10 | MGMT (OOB) | 10.10.0.0/24 | FW CARP **.254** (FW-A .252 / FW-B .253) ¹ | FW |
| 20 | SERVEURS | 10.20.0.0/24 | Core HSRP .1 (A .2 / B .3) | CORE-A |
| 30 | STOCKAGE | 10.30.0.0/24 | Core HSRP .1 | CORE-B |
| 40 | BACKUP | 10.40.0.0/24 | Core HSRP .1 | CORE-A |
| 50 | DMZ | 10.50.0.0/24 | FW CARP .1 (A .2 / B .3) | FW |
| 60 | MONITORING | 10.60.0.0/24 | Core HSRP .1 | CORE-A |
| 70 | BMS-DCIM | 10.70.0.0/24 | Core HSRP .1 | CORE-B |
| 80 | SECURITE-CCTV | 10.80.0.0/24 | Core HSRP .1 | CORE-B |
| 90 | ADMIN | 10.90.0.0/24 | FW CARP .1 (A .2 / B .3) | FW |
| 100 | SERVICES-INT | 10.100.0.0/24 | Core HSRP .1 | CORE-A |
| 901 | TRANSIT-EXT | 10.254.1.0/28 | FW CARP .1 · EDGE-A .2 · EDGE-B .3 · FW-A .4 · FW-B .5 · **Edge HSRP .6** ² | — |
| 902 | TRANSIT-INT | 10.254.2.0/28 | FW CARP .1 · CORE-A .2 · CORE-B .3 · FW-A .4 · FW-B .5 · **Core HSRP .6** ² | — |
| — | FW-SYNC | 10.254.3.0/30 | FW-A .1 / FW-B .2 (direct em2) | — |
| 998 | OSPF-CORE | 10.254.4.0/30 | CORE-A .1 / CORE-B .2 | — |
| — | EDGE-ISL | 10.254.0.0/30 | EDGE-A .1 / EDGE-B .2 (Gi0/2) | — |

¹ Deviation: PDF Table 16 gives EDGE-A mgmt 10.10.0.1, which collides with "VIP .1" → VLAN 10 gateway moved to .254.
² Added next-hop VIPs so the FW (static routing) fails over without a routing protocol (see §1.4).

### 1.2 Infrastructure addressing (PDF Table 16)
Loopbacks 10.255.0.x/32: EDGE-A .1, EDGE-B .2, FW-A .11, FW-B .12, CORE-A .21, CORE-B .22, LEAF-A1/A2 .31/.32, LEAF-B1/B2 .33/.34.
OOB mgmt (VLAN 10) uses the same last octet: 10.10.0.{1,2,11,12,21,22,31,32,33,34}.
WAN /30s: EDGE-A↔ISP-A 198.51.100.0/30 (ISP .1/EDGE .2) · EDGE-B↔ISP-A 198.51.100.4/30 · EDGE-B↔ISP-B 203.0.113.0/30 · EDGE-A↔ISP-B 203.0.113.4/30.
Public: 192.0.2.0/24 (AS65100) → routed by Edges to FW VIP 10.254.1.1; SNAT 192.0.2.10, web DNAT 192.0.2.80 → 10.50.0.11.

### 1.3 Servers & services (PDF Table 25, attachments per `DC_Casablanca_TIA942_R3_wiring.csv`)
| Node | IP | Leafs (bond) | Role / services |
|---|---|---|---|
| SRV-CMP-01/02/03 | 10.20.0.11/.12/.13 (+ VRRP VIP .10 on 01/02) | A1+A2 | App :8443 (TLS), keepalived, iperf3 |
| SRV-STO-01 | 10.30.0.11 | A1+A2 | NFS 2049 export, iSCSI 3260 (tgt) |
| SRV-BCK-01 | 10.40.0.11 | B1+B2 | Backup agent: rsyncd 873, daily pull + retention |
| SRV-INF-01 | 10.100.0.11 | B1+B2 | DNS (dnsmasq, zone dc.casa.lab), NTP (chrony), DHCP (VLAN 100 pool) |
| SRV-MON-01 | 10.60.0.11 | B1+B2 | Zabbix 6.0 LTS server+web, Grafana + Zabbix plugin (RAM 1.5 GB) |
| SRV-DCIM-01 (docker) | 10.70.0.11 | B1+B2 | DCIM web (96-rack model §13.1, reads BMS-SIM) |
| SYSLOG / BMS-SIM / CCTV-SIM (docker) | 10.60.0.12 / 10.70.0.12 / 10.80.0.11 | B1 / B2 / B2 | rsyslog 514 · power-state API (§13.3) · camera event generator |
| SRV-WEB-01 (docker nginx) | 10.50.0.11 | SW-DMZ | HTTP/HTTPS site, public 192.0.2.80 |
| SRV-BASTION | 10.90.0.11 | SW-MGMT (VLAN 90) | SSH jump host, key auth + TOTP MFA, admin logs → syslog |
| ADMIN-WS (new, gns3/webterm) | 10.90.0.12 | SW-MGMT (VLAN 90) | Admin desktop (Firefox) for pfSense/Zabbix/Grafana GUIs + screenshots |

### 1.4 Routing/HA mechanisms (PDF Table 17, with justified deviations)
- eBGP to both ISPs from both Edges, iBGP over loopbacks (next-hop-self), OSPF area 0 between Edges; LP 200 for ISP-A, AS-path prepend ×2 to ISP-B; prefix-lists (announce only 192.0.2.0/24), max-prefix, BGP timers 3/9.
- **Firewalls use static routing + VIPs** (pfSense has no OSPF without the FRR package / Internet): default → Edge HSRP 10.254.1.6, 10.0.0.0/8 → Core HSRP 10.254.2.6. Documented as deviation from "OSPF zone 0 incl. firewalls".
- Core: HSRPv2 (prio 110/90, preempt) split per PDF; RPVST+ root aligned with HSRP active; Po1 LACP (Gi0/2-3); OSPF area 0 on Vlan998/902 + loopbacks; default → FW VIP 10.254.2.1.
- FW HA: CARP (FW-A advskew 0, FW-B 100), pfsync on em2, XMLRPC config sync FW-A→FW-B; lagg0 failover em3(CORE-A)/em4(CORE-B).
- Servers: Linux bond active-backup to two Leafs, **ARP monitoring** (1 s, targets = gateway VIP + both cores + the other servers of the VLAN, validate all; MII never failed over: a stopped GNS3 leaf keeps the carrier up), single bond MAC; CMP-01/02 keepalived VIP 10.20.0.10 for T5.
  - **T5 done 2026-11-10** (fw_lan_failover.py --core SRV-CMP-01): master stop 3.1 s, CMP-02 serves; failback after preempt_delay 30 with 0 loss; master boot 4.5 s (was 10.6 s); backup reboot 0 loss. Fixes on the way: app TLS handshake out of accept() (one stalled client froze it), keepalived waits to hear the master (split brain at boot), bond MAC no longer follows the NIC (core sent to the old MAC), ARP interval 200 ms -> 1 s (flapped under IOSvL2).

### 1.5 Firewall policy (PDF Table 18, default deny + log)
| Interface | Allowed (everything else blocked & logged) |
|---|---|
| WAN | TCP 80/443 → 192.0.2.80 (DNAT SRV-WEB-01) |
| DMZ | → APP_SERVERS (10.20.0.11-13) TCP 8443; → SRV-INF-01 53/123 (documented extension) |
| LAN (902) | INTERNAL → Internet DNS/HTTP/HTTPS/NTP/ICMP (SNAT 192.0.2.10); VLAN 60 → MGMT SNMP 161/ICMP |
| MGMT (10) | devices → SYSLOG 514/udp, MON 162/udp traps, INF 53/123 |
| ADMIN (90) | → all internal & devices: SSH 22, HTTPS 443, SNMP 161, ICMP; webGUI/SSH of FW only from ADMIN |
| SYNC | pfsync + XMLRPC between peers only |
Inter-VLAN flows routed by the Cores (20→30 NFS/iSCSI, 20→40 backup agent, *→60 syslog/zabbix, 60→* SNMP/10050, *→100 DNS/NTP) are enforced by **inbound ACLs on Core SVIs**; Internet/DMZ → MGMT/STO/BCK explicitly denied.

### 1.6 Norms applied (traceable in the report)
ANSI/TIA-942-C (Rated-3: no SPOF per layer, MMR/MDA/HDA/EDA mapping) · ANSI/TIA-606-C labeling in interface
descriptions (`MDA-CORE-A:Gi1/0 -> HDA-A:LEAF-A1:Gi0/0`) · ISO/IEC 27001/27002 controls (segmentation A.8.22,
logging A.8.15, clock sync A.8.17, privileged access A.8.2/MFA, secure config A.8.9) · IEEE 802.1w, 802.3ad,
802.1Q · RFC 1918/5737/5398, 4271, 2328, 5798, 3768/2281 (HSRP), CARP · CIS-style hardening (SSHv2 only,
no telnet, SNMPv3 authPriv on Cisco, login banners, `service password-encryption`, unused ports shutdown in
parking VLAN 999, BPDU guard / storm-control on access ports, NTP + syslog + timestamps everywhere).

---

## 2. Repository layout to create (all under `03_Network/`)
```
plans/        PLAN_01_GNS3_Configuration.md (this plan) + progress checklist
inventory/    dc_casa.yaml            ← single source of truth (nodes, ports, VLANs, IPs, policy)
automation/   gen_configs.py · gen_pfsense.py · labctl.py · apply_topology.py · resilience_tests.py · render_cli.py
configs/      <DEVICE>.cfg (Cisco), isp-a/b frr.conf, fw-a/b.config.xml, servers/*.yaml (netplan), docker/*
docker/       Dockerfiles: frr-isp, syslog, bms-sim, cctv-sim, dcim (+ web content)
screenshots/  NN_<topic>.png (GNS3 topology, pfSense GUI/console, Zabbix, Grafana, DCIM, CLI evidence)
report/       Rapport_Reseau_GNS3_DC_Casablanca.docx + .pdf · _source/ (build.js, figs.py) · evidence/*.txt, tests.csv
```
Reuse: report toolchain pattern of `05_Report/_source/build.js` (docx npm helpers `H1/H2/table/figure`, Calibri,
ACCENT 00838F) and `figs.py` style; PDF via Word COM export (Word 2016 present). `gen_gns3.py` and the wiring CSV
are updated to the new topology; `fixgns3.ps1` stays as-is.

---

## 3. Execution plan (sub-tasks, each phase ends with verification + commit)

### Phase 0 — Commit & scaffolding
0.1 Commit current work: `DC_Casablanca_TIA942_R3.gns3`, `gen_gns3.py`, `fixgns3.ps1`, `05_Report/...detaille.pdf`
    → `gns3: run DC lab on GNS3 VM (images, qemu_path, IOSvL2 port names) + fixgns3.ps1 repair script`.
0.2 Create folders (§2), copy this plan to `plans/`, add `03_Network/README.md` index.

### Phase 1 — Source of truth & generators
1.1 Write `inventory/dc_casa.yaml` (all tables of §1, per-port mapping from the wiring CSV, TIA-606 labels).
1.2 `automation/gen_configs.py` → Cisco configs (EDGE/CORE/LEAF), FRR configs, netplan per server, docker
    `/etc/network/interfaces`, and Markdown/CSV tables reused by the report (no hand-copied addresses).
1.3 `automation/labctl.py` — GNS3 API client (localhost:3080, creds from `gns3_server.ini`) + raw-socket telnet
    console driver (Python 3.14 has no telnetlib): start/stop nodes, wait for prompt, push config with pacing,
    `write memory`, capture `show` outputs to `report/evidence/`.

### Phase 2 — Topology changes & platform prep
2.1 `apply_topology.py` (idempotent, via API): add **SW-OUT**; re-cable EDGE-A Gi0/3, EDGE-B Gi0/3, FW-A em0,
    FW-B em0 → SW-OUT (remove the 4 Edge–FW direct links); add **NAT-A/NAT-B** to ISP eth2 (ISP adapters 2→3);
    add **ADMIN-WS** on SW-MGMT; set SW-MGMT port VLANs (10 access, FW ports dot1q 10/90, bastion/ADMIN-WS 90),
    SW-DMZ 50; zone drawings + link labels; mirror changes in `gen_gns3.py` + wiring CSV.
2.2 GNS3 VM: enable KSM (persistent systemd unit), build custom images from `docker/` (frr-isp, syslog, bms-sim,
    cctv-sim, dcim), set docker nodes' images/volumes (`/etc/frr`, web root, logs).
2.3 RAM budget check: staged bring-up order (WAN → FW → Core/Leaf → servers → services); record `free -m` + KSM savings.

### Phase 3 — WAN & Edge
3.1 ISP-A/B FRR: interfaces, eBGP to both Edges, default-originate, MASQUERADE to NAT, Internet test reachability.
3.2 EDGE-A/B IOSv: loopbacks, ISL OSPF, iBGP, eBGP policy (LP/prepend/prefix-lists/max-prefix), static
    192.0.2.0/24 → 10.254.1.1, HSRP 901 VIP .6 with route tracking, mgmt **VRF MGMT** on Gi0/5, hardening.
3.3 Verify: `show ip bgp summary`, `show ip route`, `show standby brief`, traceroute to 8.8.8.8 from Edges.

### Phase 4 — Firewalls FW-A / FW-B (pfSense HA)  ← priority
4.1 Install pfSense 2.7.2 on both nodes from ISO over VNC (automated with `vncdotool` keystrokes + screen captures;
    fallback: guided manual install, ~5 min each). Screenshots of installer/console saved.
4.2 Bootstrap via console menu: assign em0 WAN = 10.254.1.4/.5 /28, gw 10.254.1.6 (gives temp reach to GNS3 VM
    192.168.42.1 through Edge→ISP→NAT); pull the **baseline config.xml** to a tiny HTTP upload server on the GNS3 VM.
4.3 `gen_pfsense.py` patches the baseline (ElementTree) per §1.1/§1.5: interfaces (WAN em0, SYNC em2, LAN lagg0
    failover em3/em4, DMZ em5, MGMT em6.10, ADMIN em6.90), CARP VIPs + vhid/advskew, pfsync + XMLRPC sync,
    gateways, static routes, aliases, outbound NAT (hybrid → 192.0.2.10), port forward 192.0.2.80, rules per
    interface with logging, anti-lockout on ADMIN only, SSH/webGUI restricted, DNS/NTP → 10.100.0.11, remote
    syslog → 10.60.0.12, SNMP (bsnmpd, restricted to VLAN 60), timezone Africa/Casablanca, hostnames, admin password.
4.4 Push (`fetch` from GNS3 VM → `/conf/config.xml`, clear cache, reboot); verify Status > CARP (MASTER/BACKUP),
    pfsync states, rules, NAT; GUI screenshots taken from ADMIN-WS (Firefox) via VNC.

### Phase 5 — Core & Leaf (IOSvL2)
5.1 CORE-A/B: VTP transparent, VLANs 20–100/902/998/999, RPVST+ roots per PDF, Po1 LACP trunk, Leaf trunks
    (allowed data VLANs only, VLAN 10 never trunked), Gi0/0-1 access 902 to FW lagg, SVIs + HSRPv2 (incl. 902 VIP .6),
    OSPF area 0 (passive default), default → 10.254.2.1, inter-VLAN ACLs (§1.5), mgmt VRF on Gi2/0
    (fallback if IOSvL2 lacks VRF: deny 10.10.0.0/24 on all data SVIs).
5.2 LEAF-A1/A2/B1/B2: VLANs, uplink trunks to both Cores, server access ports per CSV (portfast, BPDU guard,
    storm-control), unused → VLAN 999 shutdown, mgmt SVI Vlan10 + `ip default-gateway 10.10.0.254`.
5.3 Hardening on all Cisco: SSHv2 + local admin, `transport input ssh`, SNMPv3 authPriv → MON, syslog → 10.60.0.12,
    NTP → 10.100.0.11, banners, TIA-606 interface descriptions. Verify: `show standby brief`, `show spanning-tree summary`,
    `show etherchannel summary`, `show ip ospf neighbor`.

### Phase 6 — Servers & containers
6.1 Ubuntu VMs via serial console (ubuntu/ubuntu cloud-init): hostname, netplan bond active-backup + static IP,
    DNS/NTP, Zabbix agent, SSH keys from BASTION; role packages via the lab Internet (Phase 3 path).
6.2 Roles: CMP app :8443 + keepalived VIP; STO NFS/iSCSI; BCK rsyncd + cron jobs; INF dnsmasq/chrony/DHCP;
    BASTION SSH jump + TOTP (libpam-google-authenticator) + session logging.
6.3 Containers: GNS3 network config files (static IPs), SYSLOG rsyslog per-host files, BMS-SIM API (UTILITY-A/B,
    UPS-A/B, GENERATOR, path A/B logic), CCTV-SIM events, DCIM dashboard, SRV-WEB-01 site (HTTP+HTTPS).
6.4 Verify: `cat /proc/net/bonding/bond0`, flows allowed vs denied per matrix (scripted reachability matrix).

### Phase 7 — Supervision
7.1 SRV-MON-01: Zabbix 6.0 LTS (MariaDB, nginx), hosts via SNMPv3 (Cisco), SNMP (pfSense), agents (Linux),
    HTTP item on BMS-SIM; triggers per PDF Table 22 (link/BGP/OSPF loss, path A/B > 50 %, battery autonomy).
7.2 Grafana + Zabbix plugin: NOC dashboard (PDF Table 23 sections: Énergie, Réseau, Sécurité, Infrastructure).
7.3 Verify alerts fire; screenshots of Zabbix problems, Grafana NOC, DCIM.

### Phase 8 — Validation & resilience tests (PDF ch. 12)
8.1 `resilience_tests.py`: per scenario T1 ISP-A, T2 FW-A, T3 CORE-A, T4 LEAF-A1, T5 SRV-CMP-01, T6 power via BMS-SIM,
    plus maintenance combo (CORE-A down + ISP-A link loss): `ping -i 0.2` (+ iperf3) from SRV-CMP-01, fault via GNS3 API
    (stop node / suspend link), measure loss → convergence, failback check, alert delay; results → `report/evidence/tests.csv`.
8.2 Compare to PDF targets (≤10 s ISP, ≤5 s FW/Core, ~1 s bond, alarm ≤30 s/≤1 min); document any miss with cause.

### Phase 9 — Documentation & delivery
9.1 Screenshots (`screenshots/NN_*.png`): GNS3 topology (PowerShell window capture), pfSense dashboard/CARP/rules/NAT,
    Zabbix, Grafana, DCIM, bastion MFA; CLI evidence rendered as terminal-style PNGs (`render_cli.py`, Pillow).
9.2 Diagrams (`report/_source/figs.py`, matplotlib): layered architecture, VLAN/zone map, addressing, HA paths, flow matrix.
9.3 French report `report/Rapport_Reseau_GNS3_DC_Casablanca.docx` + `.pdf` (build.js pattern, Word COM export):
    Résumé · 1 Contexte/objectifs · 2 Normes appliquées (traceability table) · 3 Architecture en couches · 4 Plan VLAN &
    adressage · 5 Routage & HA · 6 Sécurité (zones, matrice, NAT, durcissement) · 7 Management OOB & bastion ·
    8 Services · 9 Mise en œuvre GNS3 (ressources, images, automatisation) · 10 Tests de résilience (résultats) ·
    11 Écarts vs conception & limites · 12 Conclusion · Annexes (configs, commandes, câblage, identifiants lab).
9.4 Update `03_Network/README.md`, `06_Documentation/05_Roadmap.md` (tick Phase 4/5 items), final commit(s).

---

## 4. Verification (end-to-end)
- Control plane: BGP 4/4 Established on Edges, OSPF FULL (Edges, Cores), HSRP Active/Standby as per §1.1, CARP MASTER on FW-A,
  RPVST roots correct, Po1 bundled, bonds up on all dual-homed servers.
- Data plane: scripted reachability matrix (allowed flows succeed, denied flows fail + logged on FW/ACL), SRV-CMP-01 → 8.8.8.8
  via SNAT 192.0.2.10, `curl http://192.0.2.80` from ISP-A returns SRV-WEB-01, DNS/NTP from INF-01 on all hosts.
- Ops: syslog files per device on SYSLOG, Zabbix hosts green, alert fires on T1–T6.
- Resilience: T1–T6 + combo results table meets/flags PDF targets.
- Deliverables: report .docx/.pdf open cleanly, every figure/table numbered, screenshots present, configs reproducible from
  `inventory/dc_casa.yaml` (`gen_configs.py` re-run gives no diff).

## 5. Risks & mitigations
- **RAM (15.7 GB host)**: KSM, staged starts, IOSv 512 MB; if needed stop non-test nodes during individual scenarios.
- **pfSense install automation**: fallback to guided manual VNC install; config push path independent of it.
- **IOSvL2 feature gaps (VRF/ACL on SVI)**: verified early in Phase 5 with documented fallbacks.
- **Docker in-container bonding (SRV-DCIM-01)**: if unsupported, single NIC + documented limitation.
- Lab credentials are lab-only, documented in the report annex.
