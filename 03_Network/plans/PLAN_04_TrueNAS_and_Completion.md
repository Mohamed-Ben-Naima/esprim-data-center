# PLAN_04 — TrueNAS backup NAS, then finish the open work (from 10 Nov 2026)

Goal: (1) integrate **TrueNAS SCALE 25.10.7** (ISO `E:\TrueNAS-SCALE-25.10.7.iso`) as the backup repository of the
data center, with snapshots, pulled backups, a restore test and supervision; (2) then close what plans 01-03 left
open, in the order that raises the security score most for the time spent.

## Decisions (taken 10 Nov 2026, "decide smartly" rule; change them here if you disagree)

| # | Decision | Why |
|---|---|---|
| D1 | TrueNAS **replaces SRV-BCK-01** (same name, VLAN 40, 10.40.0.11, LEAF-B1 Gi0/2 + LEAF-B2 Gi0/2). | SRV-BCK-01 was never deployed; the backup role is what a NAS does best; the name stays traceable to design Table 25; no new IP, port or VLAN. |
| D2 | Backup repository in **hall B**, primary storage (SRV-STO-01) stays in hall A. | Backups never in the same hall as the data (fire, flood). Hall B leafs run in every profile, hall A does not. |
| D3 | **Pull model**: TrueNAS pulls with rsync over SSH (TrueNAS rsync tasks) from a read-only `backup` account on each server. Core ACL VLAN 40 gets `tcp/22` to the server VLANs; the old push rule (servers → 10.40.0.0/24 tcp 873) is removed. | TrueNAS 24.10+ has no rsync daemon. A compromised server holds no credential to the backups, so it cannot delete them (ransomware). |
| D4 | **ZFS mirror** of two data disks (pool `tank`) + periodic snapshots (hourly kept 24 h, daily kept 14 days). | Disk redundancy + point-in-time copies a server cannot reach. |
| D5 | Device configurations (Cisco running-config, pfSense `config.xml`) copied to the NAS from the admin zone over SSH by a new `automation/backup_configs.py`. | MGMT stays unreachable from VLAN 40; the admin zone already has SSH to every internal host (T18-6), no new firewall rule. |
| D6 | Web UI HTTPS from the admin zone only (T18-6 already allows 443), SNMPv3 (same `zbxmon` user as Cisco), remote syslog, NTP/DNS from SRV-INF-01. | Same hardening level as the rest; no new protocol in clear. |
| D7 | 2 vCPU, **3 GB RAM** (4 GB during install), boot disk 20 GB, data disks 2 × 10 GB, all thin qcow2 (GNS3 empty images) on the GNS3 VM. Profile `nas` (below) leaves the rest off. | The GNS3 VM has 8 GB. TrueNAS wants 8 GB officially; a pool of 10 GB without apps runs in 3 GB (to be measured, fallback 4 GB with fewer nodes). |

Profile `nas` (lab_up.py): SW-MGMT, FW-A, CORE-A, LEAF-B1, LEAF-B2, ADMIN-WS, SYSLOG, SRV-BCK-01 (≈ 6.4 GB nominal).
For NAS.5 (backup sources) LEAF-B2 is swapped for SRV-MON-01 (TrueNAS fails over to LEAF-B1).

## Rules

- One session per phase; tick the boxes here, commit `network(NAS.<n>)` / `network(<task>)`, update memory, print
  the next-session prompt (template at the bottom).
- Inventory first, then generators (`validate_inventory.py`, `gen_configs.py`, `gen_pfsense.py`), then deploy, then
  audit. Firewall: FW-B first, `--rollback` ready, `fw_audit.py` = 0 difference.
- Before heavy steps: host free RAM ≥ 0.5 GB, VM load < 8. The GNS3 VM disk is on USB `H:`: after big copies check
  the System log (provider `disk`, Id 51/153). Close the project before stopping the VM.
- After each phase: update the data lists of `report/_source/build_tech_report.py` (WORKSTREAMS, SEC_DOMAINS,
  DC_PRACTICES, EQUIP, SOFTWARE, PROTOCOLS…) and rebuild the technical report.

## Phases — TrueNAS

### NAS.1 — Design in the inventory and generated configurations (no lab needed) — done 10 Nov 2026
- [x] Inventory: SRV-BCK-01 `platform: truenas`, roles `[nas, backup-pull, snapshots]`, ram/cpus/disks, NAS settings
      (`truenas:` pool, datasets, snapshot policy, sources); `web_interfaces` entry; Zabbix host by SNMPv3.
- [x] Core ACL: VLAN 40 → VLANs 20/30/60/100 tcp 22 (pull); remove VLAN 20 → 40 tcp 873 and VLAN 30 → 40 tcp 873.
- [x] `gen_configs.py`: no netplan for a `truenas` server; tables and leaf descriptions regenerated;
      `validate_inventory.py` OK; `lab_up.py --profile nas`.
      → also: ADMIN-WS alias `ssh srv-bck-01` = `truenas_admin`, portal entry TrueNAS, access matrix family `truenas`,
      flow matrix probe SRV-CMP-01 → 10.40.0.11:873 now **expected denied**, ISO sha256 `54ce9441…7a007c8e` in the
      inventory. Port alias `BACKUP_AGENT` (873) renamed `BACKUP_PULL` (22): the firewalls still carry the old alias
      (unused) until the redeploy of NAS.3.
| Test | Command | From | Expected |
|---|---|---|---|
| Inventory | `python automation/validate_inventory.py` | host | `OK` |
| ACL generated | `grep -A3 "ACL-VLAN40-IN" configs/CORE-A.cfg; grep -c "eq 873" configs/CORE-A.cfg` | host | tcp 22 lines toward 10.20/30/60/100; `0` |

### NAS.2 — Image and GNS3 node — done 10 Nov 2026
- [x] ISO copied to `/opt/gns3/images/QEMU/` in the GNS3 VM (sha256 recorded); empty qcow2 disks created.
      → upload through the GNS3 API (2 min 21 s; vmrun copy ran at ~1 MB/s); disks = GNS3 `empty20G`/`empty10G`.
- [x] Node SRV-BCK-01 re-created as QEMU TrueNAS: hda boot 20 GB, hdb/hdd data 10 GB (SATA, serial numbers for ZFS), cdrom ISO, 2 × virtio NICs,
      console VNC, same links (LEAF-B1 Gi0/2, LEAF-B2 Gi0/2) — new `automation/nas_node.py` (idempotent; keeps the
      node position; `--installed` later removes the ISO and sets RAM 3 GB). Evidence `report/evidence/nas2_node.txt`.
| Test | Command | From | Expected |
|---|---|---|---|
| Image | `sha256sum /opt/gns3/images/QEMU/TrueNAS-SCALE-25.10.7.iso` | GNS3 VM | same hash as on `E:` |
| Node | `python automation/labctl.py status` | host | SRV-BCK-01 qemu, 2 links |

### NAS.3 — Install and network — done 10 Nov 2026 (SSH and the refusal test move to NAS.4)
- [x] `lab_up.py --profile nas`; install from the ISO over VNC (`vnc.py`), boot disk = hda; admin `truenas_admin` with
      the inventory password; remove the ISO, boot from disk.
      → profile up in ~8 min, VM 4.2 GB used, host **0.3 GB free** (below the 0.5 GB rule: other host apps; held stable).
      Install ~10 min, legacy BIOS boot; `nas_node.py --installed`; first boot with **3 GB RAM works**.
- [x] Console: LAGG failover (NIC0 primary, NIC1 backup), 10.40.0.11/24, gateway 10.40.0.1, DNS 10.100.0.11.
      → via `midclt` in the Linux shell: bond0 = ens6 (LEAF-B1) + ens7 (LEAF-B2), hostname srv-bck-01.dc.casa.lab.
      **Finding:** shutting the leaf port does not drop the virtual NIC carrier in GNS3 (no failover, 27 s lost); a GNS3
      link suspend does. First suspend test: failover lost 1 ping, but the failback left LEAF-B1 with the NAS MAC on its
      uplink (the single gratuitous ARP was lost). Fix kept as a POSTINIT script: `primary_reselect=failure`,
      `num_grat_arp=5`, `peer_notif_delay=200` → eth0 suspended 20 s: **0/300 lost**; eth1: **1/250 lost** (0.2 s).
- [ ] Firewalls: `gen_pfsense.py`, `deploy_pfsense.py` (FW-B first; alias BACKUP_AGENT → BACKUP_PULL), `fw_audit.py` = 0.
      → generated 10 Nov; **deploy deferred** to the first session where FW-A and FW-B both run (FW-B is off in `nas`).
      Only difference: the unused alias.
- [x] Leaf and core configs pushed (descriptions, ACL); access matrix gets the NAS (HTTPS + SSH from ADMIN-WS, refused
      from elsewhere).
      → new `automation/acl_sync.py` (live ACL vs generated, inserts/removes by sequence number, no open window):
      CORE-A 6 changes, re-check in line, saved. **CORE-B pending** (off): `acl_sync.py CORE-B` at its next start.
      Leaf descriptions unchanged. Matrix: TrueNAS web reachable (HTTPS 302 → /ui/ 200, TLS 1.3, port 80 blocked by the
      firewall); SSH refused = service off until NAS.4; refusal sources (SRV-INF-01, SRV-WEB-01) off in this profile.
| Test | Command | From | Expected |
|---|---|---|---|
| UI | `curl -sk -o /dev/null -w "%{http_code}" https://10.40.0.11/` | ADMIN-WS | `200` |
| Failover | shut LEAF-B1 Gi0/2, ping 10.40.0.11 | ADMIN-WS | ≤ 2 lost pings |
| Matrix | `python automation/access_matrix.py` | host | NAS reachable from ADMIN-WS, refused from SRV-INF-01 |

### NAS.4 — Configuration as code (`automation/truenas_setup.py check|apply|status`)
- [ ] API (JSON-RPC over websocket, API key in inventory) through the lab proxy; idempotent.
- [ ] Pool `tank` mirror, datasets `tank/backups/servers`, `tank/backups/configs`; snapshot tasks (D4).
- [ ] Services: SSH (password + network restriction like the other servers; keys-only comes with the quick wins), SNMPv3, remote syslog 10.60.0.12, NTP 10.100.0.11; UI HTTPS only,
      session timeout 15 min; everything else off.
| Test | Command | From | Expected |
|---|---|---|---|
| Status | `python automation/truenas_setup.py status` | host | pool ONLINE (mirror), 2 snapshot tasks, services as listed |
| Logs | `grep 10.40.0.11 /var/log/remote/all.log \| tail -2` | SYSLOG aux console | recent lines |

### NAS.5 — Backups and restore test
- [ ] `deploy_servers.py --role=backup-source`: account `backup` (rrsync read-only) on SRV-MON-01 and SRV-INF-01,
      NAS public key; Zabbix DB dump + Grafana data + /etc pulled nightly (+ once by hand).
- [ ] `automation/backup_configs.py`: running configs of 8 Cisco devices + 2 pfSense → `tank/backups/configs/<date>/`.
- [ ] Restore test: delete a file on a server, restore it from a snapshot, compare checksums.
| Test | Command | From | Expected |
|---|---|---|---|
| Pull | rsync task "run now" | TrueNAS | `SUCCESS`, files in the dataset |
| Server cannot delete | `ssh backup@10.40.0.11` from SRV-MON-01 | SRV-MON-01 | refused (no route/credential) |
| Restore | `sha256sum` before / after | server | same hash |

### NAS.6 — Supervision and documentation
- [ ] Zabbix host SRV-BCK-01 by SNMPv3 (template "TrueNAS by SNMP" if present in 6.0.48, else "Linux by SNMP"),
      triggers: pool not ONLINE (disaster), last snapshot older than 2 h (high), backup task failed (high).
- [ ] Reports: technical report data lists, lab guide section 10, Test the Lab entries; commit.

## Then — finish the open work (each one session)

1. PLAN_03 **S4** NOC dashboard validated on live data (+ storage row with the NAS), **S5** log viewer and retention,
   **S6** cold-start rehearsal + `DEMO_RUNBOOK.md`.
2. PLAN_02 **FW.3** LAN side when a core stops, **FW.4** flow matrix (with NAS flows), **FW.5** evidence.
3. PLAN_02 **ZBX.7** BGP/OSPF triggers and alert timing; **LOG.1–LOG.6**.
4. PLAN_01 phase 8: **resilience tests** T1–T6 + M1 measured (`resilience_tests.py`).
5. Quick security wins (technical report, roadmap stage 2): HTTPS on Zabbix/Grafana, SNMPv3 on pfSense, NTP in every
   profile, console timeout, storm-control/DHCP snooping/DAI, config archive, pinned images, SSH keys.

## Next-session prompt template

```
Read memory, then 03_Network/plans/PLAN_04_TrueNAS_and_Completion.md. Do phase <NAS.n | task> only: tick the
boxes, run its test table, commit network(<id>), update memory and the technical report, then give me the prompt for
the next session. Brief caveman replies.
```
