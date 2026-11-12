# Plan 02 — Administration bastion, firewall, log collection, Zabbix and Grafana (DC Casablanca GNS3 lab)

> Executed natively, one sub-task at a time, in this order: P0 → ADM → FW → LOG → ZBX → GRF → ISO. Steps use checkboxes.
> Revision 2 (12 Oct 2026): adds the administration webterm, the log collection server, the *Test the Lab* report,
> the ISO/IEC 27001 access and compliance matrix, and TrueNAS readiness.
> Every sub-task ends the same way: **test → report → build → progress table → commit** (see "Definition of done").

**Goal:** every equipment of the lab is explained, configured and reachable by an administrator through one controlled
entry point, in line with the security standards of the design and ISO/IEC 27001:2022; logs are collected and kept;
every device and service is supervised in Zabbix and shown in a Grafana NOC dashboard. Each step is reproducible from
the repository and testable by one documented command.

**Architecture:** nothing is clicked by hand. Firewall changes go through `inventory/dc_casa.yaml` → `gen_pfsense.py`
→ FW-A → XMLRPC sync to FW-B. Zabbix is configured through its JSON-RPC API by one idempotent script that reads the
inventory. Grafana is configured by provisioning files kept in the repository.

**Tech stack:** pfSense CE 2.7.2, Zabbix 6.0.48 LTS (MariaDB 10.3, nginx), Grafana 13.2.3 +
`alexanderzobnin-zabbix-app`, Python 3 (stdlib only), GNS3 2.2.56.1.

**Spec:** `plans/PLAN_01_GNS3_Configuration.md` §1.5 (firewall policy), §7.1–7.3 (supervision), §4 (verification);
design PDF `05_Report/Datacenter_Casablanca_TIA942_GNS3_detaille.pdf` Tables 18, 22, 23.

## Global constraints

- **Capacity:** host 15.7 GB RAM, GNS3 VM 8 GB / 6 vCPU. Never run more than the profile fixed in P0.2. Start by tiers,
  wait for each tier to settle, check host free RAM before starting SRV-MON-01.
- **Source of truth first:** a change to rules, addresses, hosts or credentials is made in `inventory/dc_casa.yaml`,
  validated with `python automation/validate_inventory.py`, then generated and deployed. No live-only change.
- **Firewall deployment:** FW-A only, then XMLRPC sync; verify FW-B after every change.
- **Consoles:** containers through their auxiliary console (ISP-A 5037, ISP-B 5039, SYSLOG 5041, BMS-SIM 5043,
  CCTV-SIM 5045, SRV-DCIM-01 5047, SRV-WEB-01 5052). Never Ctrl-C on a main console.
- **Web access from the PC:** `python automation/lab_proxy.py start` (again after ADMIN-WS or the VM restarts).
- **Credentials:** lab-only, stored in the inventory, never typed into scripts.
- **Commits:** on `main`, message `network(<sub-task>): <what>`, one sub-task per commit.
- **ISO/IEC 27001:2022 (Annex A) applies to every equipment touched:** access only from the administration zone
  (A.5.15, A.8.2, A.8.3), authenticated and encrypted administration (A.8.5, A.8.24), configuration in the repository
  (A.8.9), logs sent to the collector (A.8.15), supervised (A.8.16), clock from SRV-INF-01 (A.8.17), filtered and
  segregated (A.8.20–A.8.22). A sub-task that adds or changes an equipment states which of these it satisfies and how
  it was checked; a gap is written down as a deviation, never left silent.
- **TrueNAS comes later (storage, VLAN 30):** nothing here may block it. Reserved now: address `10.30.0.12`, Zabbix
  group `DC/Storage`, log source slot, entry in the access matrix. Its web interface is already covered by the ADMIN
  rule (TCP 443 to internal networks); NFS/iSCSI from VLAN 20 by the core ACL. Capacity warning: TrueNAS asks for about
  8 GB of RAM, as much as the whole GNS3 VM today, so it will need its own reduced profile.

## Definition of done (every sub-task)

- [ ] The test table of the sub-task passes; output saved under `report/evidence/`.
- [ ] `report/content/06_securite.md` (FW) or `report/content/08_services.md` (ZBX, GRF) gains the sub-task's
      paragraph and a table **"Vérification"** with columns *Contrôle | Commande | Depuis | Attendu | Résultat*.
- [ ] Progress table in `report/content/01_introduction.md` updated; `report/build.ps1` run without error.
- [ ] **Test the Lab** report: the sub-task's tests added to `report/tests/tests.yaml` with the date they passed;
      `python report/_source/build_lab_guide.py test_the_lab` rebuilds `report/Test_the_Lab.pdf`.
- [ ] `report/_source/lab_guide.html` updated (sections 5, 8, 9, 10) at the end of each grand task, PDF rebuilt.
- [ ] `git status --short` shows only the sub-task's files; commit made.

## Review focus (conditions no single test covers — each is pinned to a task below)

1. **Full restart:** after the GNS3 VM restarts, Zabbix, Grafana and the dashboards come back alone → GRF.5.
2. **FW-B really in sync:** a rule added on FW-A works when FW-B is master → FW.2.
3. **Part of the lab is off:** hosts that are deliberately stopped do not bury the dashboard in alarms → ZBX.7.
4. **Overload:** short polling gaps under CPU saturation do not raise false alarms → ZBX.7.
5. **Core stops with links still up:** traffic through the firewall LAN side survives → FW.3.

---

## P0 — Preparation

### P0.1 Clean baseline — done 12 Oct 2026
- [x] `ca3823f` network(6.2), `16f4429` docs (architecture report), `3e59bc9` network(tools).
- [ ] Still untracked on purpose: `report/evidence/deploy_SRV-MON-01.log*` (overwritten by a failed run); regenerated
      and committed in GRF.1.

### P0.2 Supervision profile (which nodes run during this plan)
Zabbix must see the network devices, so the edges come back; hall A stays off.
Files: `automation/lab_up.py` (add profile `supervision`), `report/content/09_mise_en_oeuvre.md`.
- [x] Add `--profile supervision` to `lab_up.py`: NAT-A/B, ISP-A/B, SW-OUT/DMZ/MGMT, EDGE-A/B, FW-A/B, CORE-A/B,
      LEAF-B1/B2, SRV-WEB-01, ADMIN-WS, SYSLOG, BMS-SIM, CCTV-SIM, SRV-DCIM-01, SRV-INF-01, SRV-MON-01 (23 nodes).
      Not started: LEAF-A1/A2, SRV-CMP-01/02/03, SRV-STO-01, SRV-BCK-01, SRV-BASTION.
      ADMIN-WS is the administration entry point of this profile (see ADM); SRV-BASTION is started only for its own tests.
- [x] Host power settings on mains (12 Oct 2026): hard-disk turn-off was 30 s and USB selective suspend was on, while the
      VM disk is on the external USB drive H:, which dropped three times that day (12:32, 13:07, 13:56) and froze the VM
      twice. Both set to off: `powercfg /setacvalueindex SCHEME_CURRENT SUB_DISK DISKIDLE 0` and the USB
      selective-suspend index to 0. Check again after an Armoury Crate update, which resets the power plan.
- [x] Start it tier by tier, then leave it idle 10 minutes and measure (12 Oct 2026, 16:13–16:42, results below).
- [ ] **Gate: not passed with 23 nodes.** Reduce and measure again (drop SRV-INF-01, then EDGE-B), or free memory on
      the host first; record the profile that holds.

**Result of the first run (12 Oct 2026).** `report/evidence/resources_supervision.csv`:

| Stage | Nodes | VM RAM used | VM RAM available | VM load | Host RAM free |
|---|---|---|---|---|---|
| before | 0 | 0.4 GB | 7.2 GB | 0.2 | 4.8 GB |
| 1 WAN / edge | 7 | 0.8 GB | 6.8 GB | 1.4 | 4.1 GB |
| 2 security / management | 6 | 3.3 GB | 4.3 GB | 3.2 | 1.0 GB |
| 3 core / distribution | 4 | 5.0 GB | 2.6 GB | 8.3 | 0.6 GB |
| 4 services | 6 | 5.8 GB | 1.8 GB | 7.7 | 0.4 GB |

- Works: BGP 3/3 on EDGE-A, gateways split as designed, pfSense, BMS, DCIM and web site reachable through the proxy,
  no disk error on H: during the whole run, node disk images clean.
- Does not hold: during 12 idle minutes both cores logged one burst of gateway changes (HSRP state-change lines
  CORE-A 9 → 27, CORE-B 37 → 67); host free RAM ended at 0.4 GB (target ≥ 0.5) and a background task of the session was
  stopped for low host memory at 16:55.
- Damage from the disk drops found and repaired: SRV-MON-01 booted with a corrupt ext4 root (services down). Repaired
  offline with `python automation/fsck_servers.py --repair SRV-MON-01`; packages verify clean (`dpkg --verify`); the
  InnoDB redo log was also broken, so the Zabbix database was re-created with the deployment role (it held defaults
  only). SRV-BASTION, SRV-CMP-01, SRV-INF-01 and both firewalls are clean. Left to delete on SRV-MON-01:
  `/var/lib/mysql.broken` (334 MB).

| Test | Command | From | Expected |
|---|---|---|---|
| Disk stays awake | `powercfg /query SCHEME_CURRENT SUB_DISK DISKIDLE` | host | AC index `0x00000000` |
| No disk error | `Get-WinEvent -FilterHashtable @{LogName='System';Id=51;StartTime=(Get-Date).AddHours(-1)}` | host PowerShell | no event |
| Server filesystems | `python automation/fsck_servers.py SRV-BASTION SRV-CMP-01` (nodes stopped) | host | `e2fsck exit 0` for each |
| Host memory | `powershell "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB"` | host | ≥ 0.5 GB |
| VM load | `python automation/gns3vm.py "cat /proc/loadavg; free -m"` | host | load < 8, swap < 300 MB |
| Gateways stable | `python automation/labctl.py show CORE-B "show logging \| count HSRP-5-STATECHANGE"` twice, 10 min apart | host | same number |
| Interfaces reachable | `curl --socks5 192.168.75.128:1080 -sk -o NUL -w "%{http_code}" http://10.60.0.11/` | host | `200` |

### P0.3 "Test the Lab" report
A separate document that answers one question: *how do I check that this equipment works, and from where?*
Files: `report/tests/tests.yaml` (one entry per test), `report/_source/test_the_lab.html` (layout),
`report/_source/build_lab_guide.py` (builds both PDFs), `report/Test_the_Lab.pdf`.
- [x] One entry per test: id, what it proves, command, where to run it (node and console port), expected result, date
      of the last successful run. A test never run is shown as "not run yet", never as passed.
- [x] Seeded with the tests that passed on 12 Oct 2026 (48 dated, 1 not run yet); every later sub-task appends its own.

| Test | Command | From | Expected |
|---|---|---|---|
| Build | `python report/_source/build_lab_guide.py test_the_lab` | host, `03_Network` | `report/Test_the_Lab.pdf` written |
| No invented result | `grep -c "verified: null" report/tests/tests.yaml` | host | equals the number of "not run yet" rows in the PDF |

---

## ADM — Administration bastion webterm

ADMIN-WS (webterm container, VLAN 90, `10.90.0.12`) becomes the single place from which an administrator reaches every
equipment: browser for the web interfaces, SSH for the command line. It already has Firefox, `ssh`, `curl`, `telnet`.

### ADM.1 Image `dc/admin-ws:1.0` — done 12 Oct 2026
Files: `docker/admin-ws/Dockerfile` (FROM `gns3/webterm`), `docker/admin-ws/portal.html.tpl`,
`automation/gen_configs.py` (generates `configs/docker/ADMIN-WS.ssh_config` and `ADMIN-WS.portal.html` from the
inventory), `inventory/dc_casa.yaml` (image name), `automation/deploy_containers.py`.
- [x] Adds `snmp`, `dnsutils`, `netcat-openbsd`; SSH client configuration with one alias per equipment
      (`ssh core-a` → `netadmin@10.10.0.21`), SSH protocol 2 only, host keys recorded on first use.
- [x] Firefox opens on a local portal page listing every web interface (pfSense × 3, Zabbix, Grafana, BMS, DCIM, web
      site, log viewer) with its role; generated, so TrueNAS appears when it is added to the inventory.
- [x] Every SSH session opened from the webterm is announced to the log collector (who, target, start, end) — A.8.15.
- [x] Node re-created by `deploy_containers.py`; then `python automation/lab_proxy.py start`.
- [x] Found on the way: `deploy_containers.py` lost the console ports when it re-created a node (fixed: ports kept)
      and could not redeploy an image rebuilt under the same tag (added: `deploy_containers.py <NODE>`).
      Web interfaces are listed once in the inventory (`web_interfaces`); report chapter `07_administration.md` created.
- [x] ADMIN-WS shows local time +00 while SYSLOG shows +01 for the same zone name (`Africa/Casablanca`): the two
      images carry different time-zone databases. **Documented as a known lab limit** (decision of 12 Oct 2026), not fixed.

| Test | Command | From | Expected |
|---|---|---|---|
| Tools | `command -v ssh firefox-esr curl snmpget dig nc` | ADMIN-WS aux console (5053) | six paths |
| Alias | `ssh core-a "show version \| include uptime"` | ADMIN-WS terminal (VNC 5904) | `CORE-A uptime is ...` after the password |
| Portal | open Firefox | ADMIN-WS (VNC 5904) | portal page, every link opens |
| Session logged | `grep "ADMIN-WS" /var/log/remote/all.log \| tail -2` | SYSLOG aux console (5041) | start and end lines of that session |

### ADM.2 Access matrix: everything reachable from the bastion, nothing from elsewhere — done 12 Oct 2026
Files: `automation/access_matrix.py` (new), `report/evidence/access_matrix.csv`,
`report/content/generated/access_matrix.md`.
- [x] For every equipment of the inventory: SSH port and banner, web interface status code, from ADMIN-WS.
      Targets: EDGE-A/B, CORE-A/B, LEAF-A1/A2/B1/B2 (management addresses), FW-A/B (SSH and HTTPS), every running
      Linux server (SSH), every web interface.
- [x] The same probes from a non-administration network (SRV-INF-01, VLAN 100) must all fail — A.8.3, A.8.22.
      Added: a third source in the DMZ (SRV-WEB-01), `scope: all` for the public site, a self-check of the probe on
      each source, and `--login` (real SSH session on every running equipment).
- [x] Equipment that is stopped is reported as "not running", not as a failure.
- [x] Result: 15 targets tested, 0 failure, 11 not running. Defect found and fixed: **LEAF-B2 had no RSA keys, SSH
      was disabled**; keys regenerated and saved. To confirm at the next full restart: LEAF-B2 still answers SSH
      (run the matrix). LEAF-A1/A2 are off and unchecked.
- [ ] For LOG.1: CORE-A stamped 19:38 on a message received at 21:14 (device clocks are far off).

| Test | Command | From | Expected |
|---|---|---|---|
| Matrix | `python automation/access_matrix.py` | host | every running equipment `reachable` from ADMIN-WS, `refused` from SRV-INF-01 |
| One by hand | `ssh edge-a`, `ssh fw-a`, `ssh srv-inf-01` | ADMIN-WS terminal | three logins |
| Refusal is logged | `show access-lists ACL-VLAN100-IN \| include deny` | CORE-A (5010) | match counters grow after the SRV-INF-01 probes (the core ACL refuses before the device does) |

### ADM.3 Privileged access rules (A.8.2, A.8.5) — done 12 Oct 2026
- [x] Decide and document the two entry points: **ADMIN-WS** (administration desktop, browser and SSH) and
      **SRV-BASTION** (SSH jump host with TOTP second factor and `auditd`, started when its tests run). SSH alias
      `ssh -J bastion core-a` provided for the path through the jump host.
- [x] Session lock and idle timeout on the devices checked (`exec-timeout 10 0` on Cisco, pfSense GUI session timeout).
      Lockout works (quiet mode at the fifth failure). Idle: EDGE-A closed an idle session by itself after 634 s of real time (10 min on its clock); LEAF-B1 had not closed it after 840 s because its clock runs slow (known lab limit).
      pfSense web session timeout is the 4 h default: **set it to 15 min in the FW.2 deployment**.
- [x] Default and shared passwords listed with their status (Zabbix default password is removed in ZBX.1).
- [x] Findings: (1) servers and SRV-BASTION accept SSH with the image default account `ubuntu`/`ubuntu`, and the
      TOTP second factor is installed but not enforced -> proposed sub-task ADM.4 below; (2) pfSense `admin` shares
      the Cisco administrator password; (3) IOSvL2 clocks run at about 55-60 % of real time on this host and no
      Cisco device is NTP-synchronised: every device timer is stretched (the 120 s quiet period lasted about 4 min).
      Known lab limit for timing measurements (phase 8); NTP is LOG.1.

| Test | Command | From | Expected |
|---|---|---|---|
| Idle timeout | open `ssh core-a`, wait 10 min | ADMIN-WS | session closed by the device |
| Lockout | 5 wrong passwords on `ssh core-a`, then a right one | ADMIN-WS | refused for 120 s; `%SEC_LOGIN-1-QUIET_MODE_ON` in the log collector |
| Jump host | `ssh -J bastion core-a` (SRV-BASTION running) | ADMIN-WS | login through 10.90.0.11 |

### ADM.4 Bastion and server accounts — confirmed and done 12 Oct 2026
Closes the two non-conformities found in ADM.3 (A.5.17, A.8.5).
- [x] Inventory: named administration account and password for the Ubuntu servers; TOTP secret for the bastion.
- [x] `deploy_servers.py`: create the account, lock the password of `ubuntu` for SSH (console login kept for the lab
      driver), SSH alias users updated by `gen_configs.py`. New: `--accounts-only`, `automation/totp.py`.
      Applied to SRV-INF-01 and SRV-BASTION. **SRV-MON-01 is stopped: run
      `python automation/deploy_servers.py --accounts-only SRV-MON-01` when it is started for ZBX.1.**
- [x] SRV-BASTION: `pam_google_authenticator` enforced for SSH (password + TOTP), secret enrolled from the inventory.
- [x] Result: six tests pass, access matrix 16 targets / 0 failure with the TOTP login.

| Test | Command | From | Expected |
|---|---|---|---|
| Default account refused | `ssh ubuntu@10.90.0.11` | ADMIN-WS | `Permission denied` |
| TOTP required | `ssh bastion` | ADMIN-WS | password prompt, then `Verification code:` |
| Matrix still passes | `python automation/access_matrix.py --login` | host | 0 failure |

---

## FW — Firewall completion

### FW.1 Audit: live firewalls against the generated configuration — done 12 Oct 2026
Files: `automation/fw_audit.py` (new), `report/evidence/fw_audit.txt`.
- [x] `fw_audit.py` reads `config.xml`, `pfctl -sr`, `pfctl -sn`, CARP state and the wizard trigger on FW-A and FW-B
      **over SSH from ADMIN-WS** (new module `automation/adminws.py`, simpler than the VNC + file-server path first
      planned) and compares them with the generated `configs/pfsense/<FW>.config.xml`.
- [x] Record every difference: **0 difference on both firewalls**. Known candidates: rules EXT-7 and ADMIN→syslog (generated after the last deployment),
      wizard trigger file (removed live on 12 Oct 2026, not in the deployment procedure).
- [x] No redeployment needed (EXT-7 and the ADMIN -> syslog rule are live on both). Trigger-file removal documented in
      `06_securite.md`; it becomes a step of the FW.2 deployment.

| Test | Command | From | Expected |
|---|---|---|---|
| Rule labels | `pfctl -sr \| grep -c "EXT-7"` | FW-A and FW-B shell (VNC 5900 / 5901, option 8) | ≥ 1 on both |
| Rule count equal | `pfctl -sr \| wc -l` | FW-A and FW-B | same number |
| Audit | `python automation/fw_audit.py` | host | `0 differences` |
| GUI | open `https://10.90.0.1` | host browser via proxy | dashboard, no setup wizard |

### FW.2 Rules needed by supervision — done 12 Oct 2026
Zabbix agent on SRV-BASTION (VLAN 90) cannot reach the Zabbix server today: no ADMIN rule for TCP 10051.
Files: `inventory/dc_casa.yaml` (rule `EXT-8`: ADMIN_NET → MON_SERVER tcp ZABBIX_TRAPPER), generated files.
- [x] Add the rule, validate, `gen_configs.py` (tables), `gen_pfsense.py`, deploy. New `automation/deploy_pfsense.py`:
      each firewall receives its own generated file over SSH from ADMIN-WS (FW-B first), checksum and XML checked,
      previous file kept as `config.xml.before-deploy`, filter reloaded without reboot; `--rollback` restores it.
      (Each firewall gets its own file because XMLRPC sync does not carry the web-interface settings.)
- [x] Same deployment: web session timeout of pfSense set to 15 minutes (finding of ADM.3); wizard trigger removed by the script.
- [x] Review-focus 2: FW-B forced master (`sysctl net.inet.carp.demotion=240` on FW-A), test repeated, FW-A restored
      (`=-240`). EXT-8 packet counter rises on FW-B only, block of port 3306 logged by FW-B.
- [ ] Left for ZBX.5 (SRV-MON-01 is off): port 10051 really open end to end from SRV-BASTION.

| Test | Command | From | Expected |
|---|---|---|---|
| Allowed | `timeout 3 bash -c '</dev/tcp/10.60.0.11/10051' && echo open` | SRV-BASTION console (5036) | `open` |
| Still denied | `timeout 3 bash -c '</dev/tcp/10.60.0.11/3306' \|\| echo closed` | SRV-BASTION | `closed` |
| Block is logged | `grep "10.90.0.11" /var/log/remote/all.log \| grep block \| tail -1` | SYSLOG aux console (5041) | line with port 3306 |
| Same on FW-B | first test again while FW-B is master | SRV-BASTION | `open` |

### FW.3 Firewall LAN side when a core stops (finding of 12 Oct 2026)
When CORE-A hung, CORE-B took every gateway but traffic through the firewalls stopped: `lagg0` kept using `em3`
because a GNS3 link stays up when the peer node stops.
Files: `report/evidence/fw_lan_failover.txt`; then, depending on the gate, inventory + topology.
- [x] Reproduce on purpose: continuous probe, `python automation/labctl.py stop CORE-A`, measure, restart CORE-A.
      → `automation/fw_lan_failover.py` (probe ADMIN-WS → FW-A → BMS-SIM every 0.5 s, stop/start through the GNS3
      API, lagg + HSRP state during the fault, cisco_heal after). 10 Nov 2026 12:13: FW-A lagg0 stays on
      `em3 <MASTER,ACTIVE>` while CORE-A is off, CORE-B is HSRP active for everything: **outage ≥ 89 s (whole fault)
      + 62 s at the restart** (CORE-A booting behind a link that never went down).
- [x] **Gate (your decision, with the measurement in hand):**
      (a) add a built-in switch **SW-IN** on VLAN 902 (FW-A, FW-B, CORE-A, CORE-B), as SW-OUT does for VLAN 901, and put
      the firewall LAN on one interface; or (b) keep `lagg0` and document the limit as a lab artefact.
      → **(a), decided alone (user rule "decide smartly").** Why: the 12 Oct failure was a *hung* core with its link up,
      a real-world gray failure, not only a GNS3 artefact; (b) would leave a 2.5 min outage in the Tier III story.
      Variant chosen: both lagg members of each firewall go into SW-IN (pfSense interfaces unchanged, only the lagg
      description), one port per core (Gi0/1 parked). Two traps found before deploying: VLAN 902 also crossed the
      core ISL Po1 → L2 loop through SW-IN → **902 removed from Po1** (gen_configs drops from the ISL any VLAN that
      both cores reach through a lab switch); and with STP across SW-IN, CORE-B's Gi0/0 would be its root port and
      `loopguard default` would block it when CORE-A dies (the S4 failure) → **`spanning-tree bpdufilter enable`** on
      the core transit ports. In production: MLAG/vPC core pair or two transit switches.
- [x] If (a): inventory `lab_switches.SW-IN` + device ports, `validate_inventory.py`, `apply_topology.py`,
      `gen_configs.py`, `gen_pfsense.py`, deploy, `verify_topology.py`.
      → validate OK (SW-IN re-cabling documented like SW-OUT; the design CSV keeps the original cables); cores: delta
      pushed on the console (0 rejected) then saved; `apply_topology.py` now changes links hot and no longer stops
      the edges/firewalls when SW-OUT is already done: SW-IN created, 6 links; pfSense deployed FW-B first,
      `fw_audit.py` 0 difference; `verify_topology.py` 62 links = inventory; Po1(SU); HSRP 902 hellos over SW-IN
      (CORE-A active, CORE-B standby); `demo_check.py` 11/11 (loop-guard check now reads the live
      inconsistent-port count, the logged blocks of a planned core stop are normal).
      **Result:** stop CORE-A → **4.5 s** (3 probes lost; the GNS3 stop call itself takes ~8 s), restart 0-1.5 s
      (preempt); stop CORE-B (gateway of VLAN 70) → **4.5 s**, restart none. Evidence `fw_lan_failover.txt`.
      Diagram `arch_topology.mmd` + PNG rendered locally (`report/_source/render_mmd.py`, no online renderer).

| Test | Command | From | Expected |
|---|---|---|---|
| Probe | `while true; do curl -s -m 1 -o /dev/null -w "%{http_code} " http://10.70.0.12:8080/; sleep 1; done` | SRV-BASTION | `200` every second |
| Fault | `python automation/labctl.py stop CORE-A` | host | probe recovers in ≤ 5 s (target of PLAN_01 T3) |
| Active member | `ifconfig lagg0 \| grep -E "laggport\|status"` | FW-A shell | shows which port carries traffic |
| Restore | `python automation/labctl.py start CORE-A`, wait for `Po1(SU)` | host | no second outage |

### FW.4 Policy measured end to end on the running set
Files: `automation/flow_matrix.py` (option `--running-only`, new probes), `report/evidence/flow_matrix.csv`,
`report/content/generated/flow_matrix.md`.
- [x] `--running-only` skips a probe whose source or target node is stopped and says so in the output.
      → every probe now lists the nodes its flow needs; "ignoré (X arrêté)". VM sources run over SSH from ADMIN-WS
      (one round trip, real exit codes since S6), containers by `docker exec` - no slow serial console any more.
- [x] Add probes that need no hall A server: DMZ → management (denied, from SRV-WEB-01 aux console),
      ISP-A → `192.0.2.80:80` (allowed), ISP-A → `192.0.2.10:22` (denied), SRV-MON-01 → SNMP of FW-A LAN address
      (allowed), SRV-INF-01 → `10.10.0.21` (denied).
      → all added (SRV-INF-01 one skipped: off in the demo profile) + DMZ → admin, DMZ → supervision, admin → SSH /
      Grafana (allowed), admin → MariaDB 3306 (denied), supervision → SSH of the devices (denied, core ACL),
      supervision → SNMPv3 CORE-A. The DNAT probe follows 80 → 301 → 443 (first version failed on the
      self-signed certificate, not on the policy). **11 executed, 0 deviation** (15 skipped: hall A, bastion, NAS,
      SRV-INF-01 off). 26 probes in total.
- [x] Every denied probe must be found in the firewall log or in the core ACL counters.
      → checked automatically in the central log after the run (log viewer): **6/6 denied flows traced**, 5 pfSense
      `filterlog ... block` lines (T18-9, ADMIN and DMZ default deny, WAN default) and 1 core
      `%SEC-6-IPACCESSLOGP ... ACL-VLAN60-IN denied` (counter "deny 10.10.0.0/24" 6 matches on CORE-A).
      **Incident found and fixed:** the first runs put the SNMP secrets on the SSH command line, which the ADMIN-WS
      wrapper logs → 8 lines with the SNMPv3 keys / v2c community on the collector. The probes now read them from a
      0600 temp file sent through stdin (`adminws.put`), deleted after. Redacting the collector was refused by the
      Claude Code safety classifier (audit-log tampering) → **user decision pending: rotate the SNMP secrets or
      allow the redaction.** Also seen: 90 packets dropped once by CORE-B's VLAN 60 inbound ACL while it rebooted
      in the FW.3 test (counter static afterwards) - transient, noted.

| Test | Command | From | Expected |
|---|---|---|---|
| Matrix | `python automation/flow_matrix.py --running-only` | host | every executed probe `PASS` |
| Denied flows logged | `grep -c "block" /var/log/remote/10.10.0.11_10.10.0.11.log` | SYSLOG aux console | grows after the run |
| Core counters | `show access-lists ACL-VLAN100-IN \| include deny` | CORE-A (5010) | matches > 0 |

### FW.5 Firewall evidence and documentation
Files: `screenshots/2x_*.png`, `report/content/06_securite.md`, lab guide.
- [x] Screenshots through ADMIN-WS (`vnc.py ADMIN-WS shot`): Status > CARP on both firewalls, Firewall > Rules > ADMIN,
      Firewall > NAT, Status > System Logs > Firewall.
- [x] `06_securite.md`: results of FW.1–FW.4, the LAN-side decision, updated rule table.

| Test | Command | From | Expected |
|---|---|---|---|
| Report builds | `powershell -ExecutionPolicy Bypass -File report\build.ps1` | host | `.docx` and `.pdf` updated, no error |

---

## LOG — Log collection server (SYSLOG, `10.60.0.12`, ISO/IEC 27001 A.8.15–A.8.17)

Today: rsyslog on UDP/TCP 514, one file per source plus `all.log` on a persistent volume, 52 MB after one day, no
rotation, files readable by everyone in the container, no way to read the logs except the console.

### LOG.1 Audit: who sends, who is missing, are the clocks right
Files: `automation/log_audit.py` (new), `report/evidence/log_audit.txt`.
- [ ] Expected sources come from the inventory (10 network devices, 2 firewalls, servers, simulators, ADMIN-WS).
      Report the silent ones.
- [x] Time zone: ADMIN-WS (+00) and SYSLOG (+01) disagree on the offset of `Africa/Casablanca` (found in ADM.1).
      Accepted as a known lab limit; LOG.1 only has to list it with the other clock findings.
- [ ] Clock check: on 12 Oct the devices stamped their messages about 5 minutes behind the collector. Check
      `show ntp status` on every Cisco device and the NTP state of the firewalls; fix the cause (SRV-INF-01 must run;
      management rule EXT-4 carries NTP).

| Test | Command | From | Expected |
|---|---|---|---|
| Sources | `python automation/log_audit.py` | host | every running equipment has a file younger than 10 min |
| Clock | `show ntp status` | each Cisco console | `Clock is synchronized`, reference `10.100.0.11` |
| Skew | `tail -1 /var/log/remote/10.10.0.21_*.log` | SYSLOG aux console (5041) | device time and reception time differ by < 2 s |

### LOG.2 Retention and protection
Files: `docker/syslog/Dockerfile`, `docker/syslog/logrotate.conf` (new), image `dc/syslog:1.1`.
- [ ] Daily rotation, compression, retention period written in the inventory (`services.log_retention_days`).
- [ ] Directory `0750`, files `0640`; the volume survives a re-creation of the container.
- [ ] Disk usage of the log volume exposed for Zabbix (item and trigger added in ZBX.6).

| Test | Command | From | Expected |
|---|---|---|---|
| Rotation | `logrotate -f /etc/logrotate.d/remote && ls /var/log/remote \| grep -c gz` | SYSLOG aux console | > 0, new messages still arrive |
| Permissions | `stat -c "%a" /var/log/remote /var/log/remote/all.log` | SYSLOG aux console | `750`, `640` |
| Persistence | stop and start the node, `ls /var/log/remote \| wc -l` | host, then SYSLOG | same files as before |

### LOG.3 Only known sources, no loss
Files: `docker/syslog/rsyslog.conf`.
- [ ] Accept messages only from the lab networks declared in the inventory; drop and count the rest.
- [ ] Queue on disk so a burst (firewall blocks) is not lost. TLS transport is **not** deployed: written down as a
      lab deviation with its reason.

| Test | Command | From | Expected |
|---|---|---|---|
| Accepted | `logger -n 10.60.0.12 "log-test $(hostname)"` | SRV-INF-01 (5032) | line in `all.log` within 2 s |
| Config valid | `rsyslogd -N1` | SYSLOG aux console | no error |

### LOG.4 Reading the logs from the administration zone
A small read-only viewer in the image (search by source, text and time; last lines), HTTPS with a login, port 8443.
Files: `docker/syslog/viewer.py` (new, standard library), inventory rule `EXT-9` (ADMIN_NET → SYSLOG_SERVER tcp 8443),
portal entry in ADM.1.
- [ ] Viewer cannot modify or delete anything (A.8.15: protection of log information).
- [ ] Firewall rule deployed on FW-A, synced to FW-B.

| Test | Command | From | Expected |
|---|---|---|---|
| From the bastion | `curl -sk -u '<user>:<pw>' "https://10.60.0.12:8443/search?q=HSRP" \| head -3` | ADMIN-WS | log lines |
| No login, no logs | `curl -sk -o /dev/null -w "%{http_code}" https://10.60.0.12:8443/` | ADMIN-WS | `401` |
| Not from elsewhere | same `curl` | SRV-WEB-01 aux console (5052) | timeout |
| From the PC | open `https://10.60.0.12:8443` | host browser via proxy | viewer after login |

### LOG.5 The security events that must be there
- [ ] One deliberate action per event, then find its line: firewall block (rule label), failed and successful login
      on a Cisco device, configuration change on a Cisco device, pfSense web login, SSH session from ADMIN-WS,
      BMS state change, CCTV badge event.

| Test | Command | From | Expected |
|---|---|---|---|
| Failed login | `ssh baduser@10.10.0.21` then `grep SEC_LOGIN /var/log/remote/10.10.0.21_*.log \| tail -1` | ADMIN-WS, then SYSLOG | `%SEC_LOGIN-4-LOGIN_FAILED` |
| Config change | `conf t` / `end` on CORE-A, then `grep CONFIG_I ... \| tail -1` | CORE-A, then SYSLOG | `%SYS-5-CONFIG_I ... by netadmin` |
| Firewall block | `ping -c1 10.10.0.21` from SRV-WEB-01, then `grep "10.50.0.11" all.log \| grep block \| tail -1` | SRV-WEB-01, then SYSLOG | block line with rule T18-9 |

### LOG.6 Evidence and documentation
- [ ] `08_services.md` section "Journalisation centralisée", Test the Lab entries, lab guide.

---

## ZBX — Zabbix (PLAN_01 §7.1)

### ZBX.1 Base and API driver
Files: `inventory/dc_casa.yaml` (`credentials.zabbix_admin_password`, section `monitoring:`),
`automation/zabbix_setup.py` (new), `automation/deploy_servers.py`.
- [ ] `zabbix_setup.py` talks JSON-RPC to `http://10.60.0.11/api_jsonrpc.php` through the lab proxy (SOCKS5 connector
      from the standard library, no new package). Commands: `check`, `apply`, `status`. Every `apply` is idempotent
      (get, then create or update).
- [ ] `apply` step 1: replace the default `Admin` / `zabbix` password by the inventory one; set the default timezone to
      `Africa/Casablanca`.
- [ ] `deploy_servers.py`: grow the disk when `servers.<name>.disk_gb` is set (GNS3 `resize_disk` + `growpart`), so
      SRV-MON-01 is reproducible (`disk_gb: 8`).

| Test | Command | From | Expected |
|---|---|---|---|
| API | `python automation/zabbix_setup.py check` | host | `Zabbix 6.0.48`, server running: yes |
| Old password dead | log in with `Admin` / `zabbix` at `http://10.60.0.11` | host browser via proxy | refused |
| Server process | `systemctl is-active zabbix-server; tail -3 /var/log/zabbix/zabbix_server.log` | SRV-MON-01 console (5034) | `active`, no error |

### ZBX.2 Host groups and inventory mapping
Files: `inventory/dc_casa.yaml` `monitoring:` (group per role, template per platform, interface per device).
- [ ] Groups `DC/Edge`, `DC/Firewalls`, `DC/Core`, `DC/Leaf`, `DC/Servers`, `DC/Services`, `DC/Storage` (empty until
      TrueNAS); templates found by name
      with `template.get` (never by hard-coded id).

| Test | Command | From | Expected |
|---|---|---|---|
| Groups | `python automation/zabbix_setup.py status` | host | 7 groups listed |

### ZBX.3 Cisco devices by SNMPv3 (EDGE-A/B, CORE-A/B, LEAF-A1/A2/B1/B2)
Path: SRV-MON-01 → core → firewall LAN rule T18-7 → management VLAN 10 → device.
- [ ] Prove the path by hand before touching Zabbix (first test below).
- [ ] `apply` creates the 8 hosts on `10.10.0.x:161`, SNMPv3 `authPriv`, user `zbxmon`, SHA / AES-128 from the
      inventory, the Cisco IOS SNMP template, plus an ICMP ping template.
- [ ] LEAF-A1/A2 are created but put in a Zabbix maintenance period named `hall-A-off` (review-focus 3).

| Test | Command | From | Expected |
|---|---|---|---|
| SNMP path | `snmpget -v3 -l authPriv -u zbxmon -a SHA -A '<auth>' -x AES -X '<priv>' 10.10.0.21 1.3.6.1.2.1.1.5.0` | SRV-MON-01 | `STRING: "CORE-A.dc.casa.lab"` |
| Availability | `python automation/zabbix_setup.py status` | host | 6 running Cisco hosts: SNMP `available` |
| Data | *Monitoring > Latest data*, host CORE-A, item uptime | host browser | value younger than 2 min |
| Device side | `show snmp user` and `show access-lists ACL-MGMT-ACCESS` | CORE-A (5010) | user `zbxmon`, hits on `permit 10.60.0.0` |

### ZBX.4 Firewalls by SNMP v2c
pfSense answers SNMP on its LAN address (FW-A `10.254.2.4`, FW-B `10.254.2.5`), community from the inventory.
- [ ] Hosts FW-A, FW-B with the pfSense SNMP template; item for CARP state from `ifconfig` is not available by SNMP, so
      the cluster role is read from the interface/packet-filter items and an ICMP check of each virtual IP.

| Test | Command | From | Expected |
|---|---|---|---|
| SNMP path | `snmpget -v2c -c '<community>' 10.254.2.4 1.3.6.1.2.1.1.5.0` | SRV-MON-01 | `fw-a.dc.casa.lab` |
| Availability | `python automation/zabbix_setup.py status` | host | FW-A, FW-B: SNMP `available` |
| Refused elsewhere | same `snmpget` | SRV-BASTION | timeout (community limited to VLAN 60) |

### ZBX.5 Linux servers by agent
- [ ] SRV-MON-01 (local), SRV-INF-01 (passive, TCP 10050 from VLAN 60), SRV-BASTION (active, needs FW.2).
      Template Linux by Zabbix agent. Servers not deployed yet are not created.

| Test | Command | From | Expected |
|---|---|---|---|
| Agent port | `timeout 3 bash -c '</dev/tcp/10.100.0.11/10050' && echo open` | SRV-MON-01 | `open` |
| Availability | `python automation/zabbix_setup.py status` | host | agent `available` on each running server |
| Agent side | `systemctl is-active zabbix-agent; grep -E "^Server" /etc/zabbix/zabbix_agentd.conf` | SRV-INF-01 (5032) | `active`, `10.60.0.11` |

### ZBX.6 Services: power, racks, web site, log collector
- [ ] HTTP-agent items on BMS-SIM `http://10.70.0.12:8080/api/state`: `$.path_load_pct.A`, `$.path_load_pct.B`,
      `$.paths.A`, `$.paths.B`, `$.status`, number of alarms. Interval 10 s.
- [ ] Triggers from the design thresholds: path load > 45 % (warning), > 50 % (high), path not `POWERED` (disaster).
- [ ] DCIM `http://10.70.0.11:8080/api/summary`: racks OK / DEGRADED / DOWN; trigger DEGRADED > 0.
- [ ] Web scenario on `https://10.50.0.11/health` (expects `OK SRV-WEB-01`); ICMP check of SYSLOG `10.60.0.12`.

| Test | Command | From | Expected |
|---|---|---|---|
| Source value | `curl -s http://10.70.0.12:8080/api/state \| grep -A2 path_load_pct` | SRV-MON-01 | `47.1` twice |
| Nominal state | *Monitoring > Problems* | host browser | two warnings "path load > 45 %", nothing else from BMS |
| Alarm | `curl "http://10.70.0.12:8080/api/set?UTILITY-A=DOWN&UPS-A=DOWN&GENERATOR=DOWN"` | SRV-MON-01 | problem "path A not powered" in ≤ 30 s; racks DEGRADED |
| Recovery | `curl http://10.70.0.12:8080/api/reset` | SRV-MON-01 | problems resolved in ≤ 30 s |

### ZBX.7 Network triggers and alert timing
- [ ] BGP on the edges: item per neighbour on `1.3.6.1.2.1.15.3.1.2.<peer>` (6 = established), trigger when ≠ 6.
- [ ] OSPF neighbour state `1.3.6.1.2.1.14.10.1.6` on edges and cores; interface-down triggers come from the template.
- [ ] Review-focus 3 and 4: triggers on "unreachable" need 3 failed checks; maintenance period `hall-A-off` covers
      stopped nodes.
- [ ] Measure the alert delay for one fault per layer and save it in `report/evidence/alerts.csv`.

| Test | Command | From | Expected |
|---|---|---|---|
| BGP alarm | `python automation/labctl.py stop ISP-A` | host | problem "BGP peer 198.51.100.1 down" on EDGE-A and EDGE-B in ≤ 60 s |
| Recovery | `python automation/labctl.py start ISP-A` | host | resolved in ≤ 60 s |
| No false alarm | leave the profile idle 15 min | host browser | no new problem |
| Stopped nodes silent | *Monitoring > Problems* | host browser | nothing for LEAF-A1/A2 |

---

## GRF — Grafana (PLAN_01 §7.2)

### GRF.1 Base
Files: `automation/deploy_servers.py` (Grafana role), `grafana/grafana.ini.patch` documented in the role.
- [ ] Role sets `root_url = http://10.60.0.11:3000/`, timezone, `allow_sign_up = false`, anonymous access off; service
      enabled at boot.

| Test | Command | From | Expected |
|---|---|---|---|
| Health | `curl --socks5 192.168.75.128:1080 -s http://10.60.0.11:3000/api/health` | host | `"database": "ok"` |
| Login | `curl --socks5 192.168.75.128:1080 -s -u admin:'<pw>' http://10.60.0.11:3000/api/org` | host | `Main Org.` |
| No anonymous | `curl --socks5 192.168.75.128:1080 -s -o NUL -w "%{http_code}" http://10.60.0.11:3000/api/dashboards/home` | host | `401` |

### GRF.2 Zabbix plugin from the offline repository
The download through the lab failed twice (≈ 70 KB/s). The plugin joins the offline ISO, like the packages.
Files: `automation/build_repo.sh` (adds `plugins/alexanderzobnin-zabbix-app-<version>.zip`, ISO `v3`),
`automation/attach_repo.py` (ISO name), `automation/deploy_servers.py`.
- [ ] Rebuild the ISO in the GNS3 VM, attach it to SRV-MON-01, role unzips the plugin into
      `/var/lib/grafana/plugins/` and enables the app.

| Test | Command | From | Expected |
|---|---|---|---|
| ISO content | `ls /mnt/dcrepo/plugins/` | SRV-MON-01 | the plugin zip |
| Installed | `grafana-cli plugins ls` | SRV-MON-01 | `alexanderzobnin-zabbix-app` |
| Enabled | `curl -s -u admin:'<pw>' http://127.0.0.1:3000/api/plugins/alexanderzobnin-zabbix-app/settings \| grep enabled` | SRV-MON-01 | `"enabled":true` |

### GRF.3 Data source by provisioning
Files: `grafana/provisioning/datasources/zabbix.yaml` (new), `automation/zabbix_setup.py` (read-only user
`grafana`), inventory (`credentials.zabbix_grafana_password`).
- [ ] Zabbix user `grafana`, read-only role, read access to the six `DC/*` groups.
- [ ] Data source `Zabbix`, URL `http://127.0.0.1/api_jsonrpc.php`, copied to `/etc/grafana/provisioning/` by the role.

| Test | Command | From | Expected |
|---|---|---|---|
| Declared | `curl -s -u admin:'<pw>' http://127.0.0.1:3000/api/datasources/name/Zabbix \| grep '"type"'` | SRV-MON-01 | Zabbix data source type |
| Works | *Connections > Data sources > Zabbix > Test* | host browser | "Zabbix API version 6.0.48" |
| Read-only | log in to Zabbix as `grafana`, open *Configuration* | host browser | menu absent |

### GRF.4 NOC dashboard (design Table 23)
Files: `grafana/dashboards/noc.json` (new), `grafana/provisioning/dashboards/dc.yaml` (new).
- [ ] Four rows. **Énergie:** path A / B load gauges with 45 % and 50 % thresholds, path state, BMS status, racks
      OK / DEGRADED / DOWN. **Réseau:** BGP sessions per edge, core and edge availability, uplink traffic.
      **Sécurité:** firewall availability and states, active problems by severity. **Infrastructure:** server CPU,
      memory, disk, service checks.
- [ ] Dashboard provisioned from the repository (read-only in the UI), set as home dashboard.

| Test | Command | From | Expected |
|---|---|---|---|
| Provisioned | `curl -s -u admin:'<pw>' "http://127.0.0.1:3000/api/search?query=NOC" \| grep -c uid` | SRV-MON-01 | `1` |
| Live values | open `http://10.60.0.11:3000` | host browser | path A and B at 47.1 %, no "No data" panel |
| Reacts | `curl "http://10.70.0.12:8080/api/set?UTILITY-A=DOWN&UPS-A=DOWN&GENERATOR=DOWN"` then `.../api/reset` | SRV-MON-01 | Énergie row turns red within 30 s, back after reset |

### GRF.5 Restart test, evidence, documentation
- [ ] Review-focus 1: shut SRV-MON-01 down cleanly, start it, run `lab_proxy.py start`, and check without any manual
      action.
- [ ] Screenshots: Zabbix hosts, Zabbix problems during the power test, Grafana NOC nominal and degraded.
- [ ] `08_services.md` (Zabbix and Grafana sections), progress table (7.1–7.3 done), lab guide sections 5, 8, 9, 10.

| Test | Command | From | Expected |
|---|---|---|---|
| Services after restart | `systemctl is-active mariadb zabbix-server nginx grafana-server` | SRV-MON-01 | four times `active` |
| Dashboard after restart | open `http://10.60.0.11:3000` | host browser | NOC dashboard with live values |
| Hosts after restart | `python automation/zabbix_setup.py status` | host | same availability as before |
| Report | `powershell -ExecutionPolicy Bypass -File report\build.ps1` | host | builds, new figures present |

---

## ISO — Access and compliance matrix (closing task)

### ISO.1 One line per equipment
Files: `automation/gen_configs.py` (table), `report/content/generated/compliance.md`, `report/content/02_normes.md`,
lab guide, Test the Lab.
- [ ] For each of the 31 nodes (and the reserved TrueNAS line): role, how it is administered, from where, how the
      administrator is authenticated, where its logs go, its time source, where its configuration is kept, how it is
      supervised, and the Annex A controls covered. Each cell points to the test that proves it.
- [ ] Every gap is listed as a deviation with its reason (examples known today: no TLS on syslog, SNMP v2c on pfSense,
      self-signed certificates, default Zabbix password until ZBX.1).

| Test | Command | From | Expected |
|---|---|---|---|
| Complete | `python automation/gen_configs.py && grep -c "^| " report/content/generated/compliance.md` | host | 32 equipment lines + header |
| No empty cell | `grep -c "| |" report/content/generated/compliance.md` | host | `0` |

### ISO.2 Configuration backup and restore (A.8.9, A.8.13)
- [ ] Zabbix configuration exported by `zabbix_setup.py export` into `configs/zabbix/`; Grafana by provisioning files;
      pfSense by the redacted `config.xml`; Cisco by the generated configurations.
- [ ] One restore proven: delete a Zabbix host, `zabbix_setup.py apply`, host back.

| Test | Command | From | Expected |
|---|---|---|---|
| Export | `python automation/zabbix_setup.py export && git status --short configs/zabbix` | host | files listed |
| Restore | delete host CORE-B in Zabbix, `python automation/zabbix_setup.py apply`, `status` | host | CORE-B present and available |

---

## Not in this plan

Resilience scenarios T1–T5 and M1 with measured convergence (PLAN_01 phase 8), deployment of SRV-CMP/STO/BCK
(phase 6.2–6.4), SNMP trap reception on SRV-MON-01 (devices already send traps to `10.60.0.11:162`; nothing listens),
installation of TrueNAS itself (only its place is reserved here).
