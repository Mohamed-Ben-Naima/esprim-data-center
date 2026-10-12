# DC Casablanca TIA-942 Rated-3 — Network Architecture Report (GNS3)
Module Projet Data Center – 5ème année, ESPRIM | 2026-2027

> Source: `03_Network/` lab. Single source of truth: `03_Network/inventory/dc_casa.yaml`.
> Live project: `03_Network/DC_Casablanca_TIA942_R3.gns3` (31 nodes, 60 links verified).
> Full French build: `03_Network/report/Rapport_Reseau_GNS3_DC_Casablanca.docx/.pdf`.

## 1. Where is the GNS3 project?

```
03_Network/
  DC_Casablanca_TIA942_R3.gns3            # live project, compute `vm` (GNS3 VM)
  DC_Casablanca_TIA942_R3.generated.gns3  # output of gen_gns3.py
  DC_Casablanca_TIA942_R3_wiring.csv       # 60 links, role/node/if
  gen_gns3.py                             # topology generator
  inventory/dc_casa.yaml                  # VLANs, IPs, policy, tests
  configs/  EDGE-A/B.cfg, CORE-A/B.cfg, LEAF-*.cfg, ISP-*/frr.conf, pfsense/*.xml, servers/*.netplan
  automation/ gen_configs.py, gen_pfsense.py, labctl.py, apply_topology.py, verify_topology.py, resilience_tests.py
  docker/ frr-isp, syslog, bms-sim, cctv-sim, dcim, web
  plans/PLAN_01_GNS3_Configuration.md
  report/content/*.md + evidence/*.txt + screenshots/
```

## 2. Layered architecture

![Figure 1 - Mermaid: end-to-end layered topology](arch_topology.png)

![Figure 2 - Mermaid: VLAN / security zones and gateways](arch_vlans.png)

![Figure 3 - Mermaid: HA path with T1/T2/T3 failover targets](arch_ha.png)

> Mermaid sources (editable in https://mermaid.live): `_source/arch_topo_simple.mmd`, `_source/arch_vlans.mmd`, `_source/arch_ha.mmd`. Rendered via mermaid.ink.

```
Internet (NAT-A/NAT-B)
  |             |
ISP-A AS64500 ISP-B AS64501      # FRR docker, default-originate + MASQUERADE
  |  \       /  |
EDGE-A ==IS L== EDGE-B           # IOSv, eBGP x4 + iBGP + OSPF a0, HSRP VIP .6
  └-- SW-OUT VLAN901 --┘         # shared transit 10.254.1.0/28
  FW-A ==pfsync== FW-B           # pfSense 2.7.2 CARP HA
  lagg0 VLAN902 | em5 DMZ | em6 trunk 10+90
CORE-A ==Po1 LACP== CORE-B       # IOSvL2, HSRP SVIs + RPVST+ + OSPF a0
 /  \  trunks  /  \
LEAF-A1 LEAF-A2 LEAF-B1 LEAF-B2  # Hall A / Hall B access
```

TIA-942 mapping (`report/content/02_normes.md`):
ER/MMR: ISP-A/B, EDGE-A/B, SW-OUT | MDA: FW-A/B, CORE-A/B, SW-DMZ/MGMT, BASTION, ADMIN-WS | HDA-A/B: LEAFs | EDA-A/B: servers/containers.

## 3. Every node — job + what was configured

### 3.1 WAN / Edge

| Node | Job | Key configuration |
|---|---|---|
| NAT-A / NAT-B | Give simulated ISPs real Internet for apt/install + real-destination tests | GNS3 `nat` node on `ISP eth2` |
| ISP-A (64500) / ISP-B (64501) | Simulate operators; only default route to customer, only accept 192.0.2.0/24 | FRR `dc/frr-isp:1.0`: eBGP to both Edges, `default-originate`, `MASQUERADE -o eth2`, prefix-filter, eth0/eth1 /30s (.1/.5 + cross links) |
| EDGE-A 10.255.0.1 / EDGE-B 10.255.0.2 | Border routing, public announcement, first HA hop | IOSv: Loopback, Gi0/0-1 WAN /30s, Gi0/2 ISL 10.254.0.0/30, Gi0/3 transit 10.254.1.2/3; eBGP (LP200 ISP-A / LP100 ISP-B, prepend x2 to ISP-B, PL-ANNOUNCE/PL-DEFAULT, max-prefix 100, timers 3/9, MD5 `Bgp-DC-2026`); iBGP next-hop-self; OSPF a0 (hello1/dead3); HSRP Grp1 VIP 10.254.1.6 prio 110/90 preempt + `track 10` default; static 192.0.2.0/24 -> 10.254.1.1; VRF MGMT Gi0/5 10.10.0.1/2; ACL-WAN-IN anti-spoofing; SSHv2, SNMPv3, syslog, NTP, TIA-606 descr |
| SW-OUT | Shared broadcast for CARP+HSRP on VLAN 901 | Built-in switch, 4x access 901 |

Justification: 4 eBGP sessions (each Edge to both ISPs) = no SPOF; iBGP+OSPF gives 2 paths for loopbacks; HSRP VIP isolates FWs from Edge failure; LP+prepend makes ISP-A primary both directions without manual failover.

### 3.2 Security (MDA)

| Node | Job | Key configuration |
|---|---|---|
| FW-A / FW-B | Zone filtering, NAT, DMZ/MGMT/ADMIN gateways, HA | pfSense 2.7.2: em0 WAN .4/.5 VIP .1 vhid1; lagg0 failover em3/em4 .4/.5 VIP .1 vhid2; em2 SYNC 10.254.3.1/2 (pfsync + XMLRPC); em5 DMZ .2/.3 VIP .1; em6.10 MGMT .11/.12 VIP .254; em6.90 ADMIN .2/.3 VIP .1; advskew 0/100; static default -> 10.254.1.6, 10.0.0.0/8 -> 10.254.2.6; SNAT 10.0.0.0/8->192.0.2.10, DNAT 192.0.2.80->10.50.0.11; 32 rules default-deny+log per Table-18, anti-lockout only on ADMIN, multicast no-log before deny; UFS/MBR install via VNC, generated `config.xml` |
| SW-DMZ | Isolate public service | Built-in switch, 3x access VLAN 50 |
| SRV-WEB-01 10.50.0.11 | Public website target | `dc/web:1.0` nginx, HTTP->HTTPS, TLS1.2/1.3, HSTS/CSP/X-Frame |

Justification: CARP+pfsync+XMLRPC = stateful FW failover ≤5s; static-to-VIP avoids OSPF on FW (no FRR pkg + no Internet); lagg0 failover across CORE-A/B survives Core loss; CARP gateways force MGMT/DMZ/ADMIN through inspection.

### 3.3 Core / Distribution

| Node | Job | Key configuration |
|---|---|---|
| CORE-A .21 / CORE-B .22 | Inter-VLAN routing + filtering + HA gateways | IOSvL2: VLANs 20-100/902/998/999, VTP transparent, RPVST+ roots split (4096 active / 8192 standby aligned with HSRP), Po1 LACP Gi0/2-3 trunk, Gi0/0-1 access 902 to FWs, Gi1/x trunks to Leafs (no VLAN 10), SVIs HSRPv2 VIP .1 (+902 VIP .6) timers 250/750 preempt 30s MD5, OSPF a0 passive-default on 998/902+loopbacks, default -> 10.254.2.1, inbound SVI ACLs (common DNS/NTP/syslog/Zabbix + per-VLAN NFS/iSCSI/backup/SNMP), VRF MGMT Gi2/0, hardening (AAA, SSHv2 only, SNMPv3 authPriv, syslog, NTP, banner, 999 shutdown) |
| LEAF-A1 .31 / A2 .32 / B1 .33 / B2 .34 | Server access per hall | IOSvL2: uplinks Gi0/0-1 to both Cores, access ports per wiring.csv (PortFast, BPDU-guard, storm-control omitted on IOSvL2 – documented), unused -> 999 shutdown, Vlan10 mgmt + `ip default-gateway .254` |

Justification: HSRP split balances routing load; STP root = HSRP active avoids tromboning over ISL; LACP doubles Core bandwidth + survives 1 link; Leaf dual-homing + server bond = leaf loss ≈1s.

### 3.4 Servers / services (EDA)

| Node | Job | Key configuration |
|---|---|---|
| SRV-CMP-01 .11 / -02 .12 / -03 .13 VIP .10 | App tier | Ubuntu bond active-backup to A1+A2, app :8443 TLS, keepalived MASTER/BACKUP (T5), iperf3, netplan + DNS/NTP .11 |
| SRV-STO-01 10.30.0.11 | Storage | NFS 2049 + iSCSI 3260 (tgt), bond A1+A2 |
| SRV-BCK-01 10.40.0.11 | Backup | rsyncd 873, cron daily pull + retention, bond B1+B2 |
| SRV-INF-01 10.100.0.11 | DNS+NTP+DHCP (dependency of all) | dnsmasq `dc.casa.lab` fwd 1.1.1.1/8.8.8.8, chrony stratum, DHCP VLAN100, bond B1+B2 |
| SRV-MON-01 10.60.0.11 (1536MB) | Observability | Zabbix 6.0 LTS + Grafana + plugin, SNMPv3/agents/HTTP, triggers Table-22 |
| SYSLOG 10.60.0.12 / BMS-SIM 10.70.0.12 / CCTV-SIM 10.80.0.11 / DCIM 10.70.0.11 | Logs, facility twin, security sim, rack twin | Docker: rsyslog per-host files; BMS power API + PATH A/B logic + alarms; CCTV camera/badge events; DCIM 96 racks / 892kW dashboard polling BMS 10s |
| SW-MGMT + SRV-BASTION 10.90.0.11 + ADMIN-WS 10.90.0.12 | OOB + admin entry | SW-MGMT: 10x access 10, 2x dot1q 10+90 to FWs, 2x access 90; BASTION SSH jump key+TOTP + session log; ADMIN-WS `gns3/webterm` Firefox VNC |

## 4. Resources + metrics (measured, `report/evidence/resources_stages.csv`)

Host: Win11 15.7GB (spec wanted 32GB). GNS3 VM: 10GB RAM, 6 vCPU (raised from 3 – IOSvL2 34%/core idle, IOSv 17%), KSM on (200pp/100ms `ksm-tune`), nested VT-x. Images: IOSv 512MB, IOSvL2 768MB + `-machine pc-q35-4.2` (fixes Overflow(4) crash on QEMU 8), pfSense 1GB UFS, Ubuntu cloud + seed ISO.

| Stage | Nodes | VM used | KSM saved | Host free | Load |
|---|---|---|---|---|---|
| WAN/Edge | 7 | 1.2GB | 0.1GB | 5.9GB | 1.9 |
| +FW/MGMT | +6 | 3.4GB | 0.5GB | 3.1GB | 1.7 |
| +Core/Leaf | +6 | 6.2GB | 0.5GB | 0.2GB | 12.7 |
| +containers | +4 | 6.2GB | 0.5GB | 0.1GB | 17.9 |

Rule: run by tiers (Network / Services / Test profiles), staged boot, stop Hall-A Leafs when deploying Hall-B. With 25 nodes: 3.6/9.9GB via KSM (~6GB dedup). 8 Ubuntu (+4.5GB) cannot run all at once – test only involved servers per scenario. Smoke tests: `rsyslogd -N1`, `nginx -t`, BMS path-A-DOWN -> CRITICAL + alarms, DCIM 96 bays.

## 5. How to test / prove it works

Deploy: `validate_inventory.py` (98 links, 92 IPs -> OK) -> `gen_configs.py` -> `labctl.py push` (8-line batches, <2min/Edge, 0 refused lines) -> `write memory` -> save `show` to `evidence/`.

| Check | Command / action | Pass criteria (evidence present) |
|---|---|---|
| BGP | `show ip bgp summary` | 3/3 Established per Edge, 1 prefix from each ISP, default via ISP-A (LP200) |
| OSPF | `show ip ospf neighbor` | 2 FULL per Edge (Gi0/2+Gi0/3), 2 FULL per Core (Vlan998+902) |
| HSRP/CARP | `show standby brief` / Status>CARP | Edge .6 Active EDGE-A; Core VIPs split per table; FW-A MASTER 5 VIPs, FW-B BACKUP |
| LACP/STP | `show etherchannel summary`, `show spanning-tree root` | Po1 SU/P 2/2; roots = HSRP active; Leaf uplinks FWD/BLK split |
| Data | `ping 8.8.8.8`, `ping … source Vlan20`, `curl http://192.0.2.80`, `dig @10.100.0.11`, `traceroute` + ACL log | 5/5 Internet, web returns SRV-WEB-01, DNS ok, spoofed ICMP denied+logged |
| Mgmt isolation | `show vrf`, `show ip route` | 10.10.0.0/24 only in VRF MGMT, absent global; Core denies .10/.90 |
| Topology | `verify_topology.py` | `live 60 inventory 60 nodes 31 -> OK` |
| Resilience | `resilience_tests.py` ping -i0.2 + iperf + stop_node/suspend_link | T1 ISP-A ≤10s via ISP-B; T2 FW-A ≤5s keep states; T3 CORE-A ≤5s; T4 LEAF-A1 ≈1s bond; T5 CMP-01 -> VIP on CMP-02 alert ≤1min; T6 BMS path-A DOWN alarm ≤30s; M1 double fault maintained |

## 6. Security principles + norms (explicit)

| Norm | Requirement | Implementation in this lab |
|---|---|---|
| ANSI/TIA-942-C Rated-3 | Concurrently maintainable, no SPOF | Doubled ISP/Edge/FW/Core/Leaf, dual-homed servers, T1-T6+M1 |
| TIA-942 spaces + 606-C + 568 | ER/MMR/MDA/HDA/EDA, unique labels, A/B paths | Per-node `tia` + `MDA-CORE-A:Gi1/0 -> HDA-A:LEAF-A1:Gi0/0` descr + dual uplinks/NICs |
| ISO 27001 A.8.22 | Segregation | 14 VLANs, zones Externe/DMZ/Interne/MGMT/ADMIN, default-deny |
| A.8.20/A.8.21 | Net + net-service security | FW HA + Core SVI ACLs + BGP prefix/max-prefix/MD5 |
| A.8.2/A.5.17 | Privileged access + auth | Admin only VLAN90 via BASTION, SSHv2, TOTP MFA, VTY ACL 60/90, login block |
| A.8.9 | Config management | IaC: yaml -> generated configs + report tables, Git versioned, validator |
| A.8.15/A.8.16 | Logging/monitoring | Central syslog .12, Zabbix/Grafana, deny-log, SNMP traps |
| A.8.17 | Time sync | Single NTP 10.100.0.11, chrony, `clock timezone MAR` |
| 802.1Q/1w/3ad | VLAN/RSTP/LACP | dot1q trunks, RPVST+loopguard, Po1 LACP |
| RFC 1918/5737/5398 | Private + doc addresses | 10/8 inside; 192.0.2/24, 198.51.100/24, 203.0.113/24; AS 64500/64501/65100 |
| RFC 4271/2328/2281, HSRPv2, CARP | BGP/OSPF/gateway redundancy | eBGP/iBGP, OSPF a0, HSRP 250/750 + MD5, CARP+pfsync+XMLRPC |
| CIS-style hardening | Attack-surface reduction | No telnet/http, password-encryption, SNMPv3 authPriv, banner, 999 shutdown, BPDU-guard/storm-control, NTP/syslog/timestamps |

## 7. Who did / does what per layer

Git evidence: `Mohamed Ben Naima` 19 commits (GNS3 fix, inventory, generators, labctl, topology, images, WAN/Edge, FW, Core/Leaf, INF/services); `AsseliDaly` 4 commits (network arch draft, rack 3D, TIA942 PDF).

| Layer | Built by | Operated by (RACI) |
|---|---|---|
| Site/power/cooling/Blender | Prior phases (report 05) | Facilities / DC Manager – UPS/GEN/chillers, E1/E2 |
| ISP/WAN/Edge (BGP/OSPF/HSRP) | M. Ben Naima (Phase 3) | NetOps – peering, prefix-lists, LP/prepend; NOC monitors BGP/OSPF/Zabbix |
| FW/DMZ/NAT/policy | M. Ben Naima (Phase 4) + spec Table-18 | SecOps – CARP/pfsync, rules T18-x, SNAT/DNAT, logs; Admin only via BASTION |
| Core/Leaf/VLAN/ACL | M. Ben Naima (Phase 5) | NetOps – HSRP/STP/LACP/OSPF/ACLs; NOC – traps, port status |
| Servers/storage/backup/INF | M. Ben Naima (Phase 6.1 INF done, 6.2-6.4 in progress) | SysAdmin – bond/DNS/NTP/NFS/iSCSI/rsyncd; Backup owner – restores |
| Monitoring/BMS/DCIM/CCTV/syslog | M. Ben Naima (images) / Phase 7 TODO | NOC/SOC – Zabbix/Grafana dashboards Table-22/23, syslog triage; Facilities – BMS/DCIM alarms |
| Resilience/QA | `resilience_tests.py` Phase 8 TODO (T1-T6+M1) | QA/Chaos + NOC – execute faults, measure convergence vs targets, alert delay |
| Docs/IaC/report | M. Ben Naima (pipeline) + AsseliDaly (spec PDF, arch overview) | Tech Writer / Release – yaml change -> regen -> rebuild docx/pdf -> commit |

Deviations accepted: SW-OUT added (§11.3), MGMT GW .254 (Table-16 collision), FW static-to-VIP (no OSPF pkg), cross-ISP links, NAT-A/B + ADMIN-WS for install/screenshots, uRPF removed (breaks default-only Edge – kept ACL-WAN-IN), storm-control omitted on IOSvL2.
