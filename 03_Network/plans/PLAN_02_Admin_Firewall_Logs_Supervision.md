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
- [ ] Add `--profile supervision` to `lab_up.py`: NAT-A/B, ISP-A/B, SW-OUT/DMZ/MGMT, EDGE-A/B, FW-A/B, CORE-A/B,
      LEAF-B1/B2, SRV-WEB-01, ADMIN-WS, SYSLOG, BMS-SIM, CCTV-SIM, SRV-DCIM-01, SRV-INF-01, SRV-MON-01 (24 nodes).
      Not started: LEAF-A1/A2, SRV-CMP-01/02/03, SRV-STO-01, SRV-BCK-01, SRV-BASTION.
      ADMIN-WS is the administration entry point of this profile (see ADM); SRV-BASTION is started only for its own tests.
- [ ] Start it tier by tier, then leave it idle 10 minutes and measure.
- [ ] **Gate:** if the cores flap, drop SRV-INF-01, then EDGE-B, and record the profile that holds.

| Test | Command | From | Expected |
|---|---|---|---|
| Host memory | `powershell "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB"` | host | ≥ 0.5 GB |
| VM load | `python automation/gns3vm.py "cat /proc/loadavg; free -m"` | host | load < 8, swap < 300 MB |
| Gateways stable | `python automation/labctl.py show CORE-B "show logging \| count HSRP-5-STATECHANGE"` twice, 10 min apart | host | same number |
| Interfaces reachable | `curl --socks5 192.168.75.128:1080 -sk -o NUL -w "%{http_code}" http://10.60.0.11/` | host | `200` |

### P0.3 "Test the Lab" report
A separate document that answers one question: *how do I check that this equipment works, and from where?*
Files: `report/tests/tests.yaml` (one entry per test), `report/_source/test_the_lab.html` (layout),
`report/_source/build_lab_guide.py` (builds both PDFs), `report/Test_the_Lab.pdf`.
- [ ] One entry per test: id, what it proves, command, where to run it (node and console port), expected result, date
      of the last successful run. A test never run is shown as "not run yet", never as passed.
- [ ] Seeded with the tests that passed on 12 Oct 2026; every later sub-task appends its own.

| Test | Command | From | Expected |
|---|---|---|---|
| Build | `python report/_source/build_lab_guide.py test_the_lab` | host, `03_Network` | `report/Test_the_Lab.pdf` written |
| No invented result | `grep -c "verified: null" report/tests/tests.yaml` | host | equals the number of "not run yet" rows in the PDF |

---

## ADM — Administration bastion webterm

ADMIN-WS (webterm container, VLAN 90, `10.90.0.12`) becomes the single place from which an administrator reaches every
equipment: browser for the web interfaces, SSH for the command line. It already has Firefox, `ssh`, `curl`, `telnet`.

### ADM.1 Image `dc/admin-ws:1.0`
Files: `docker/admin-ws/Dockerfile` (FROM `gns3/webterm`), `docker/admin-ws/portal.html.tpl`,
`automation/gen_configs.py` (generates `configs/docker/ADMIN-WS.ssh_config` and `ADMIN-WS.portal.html` from the
inventory), `inventory/dc_casa.yaml` (image name), `automation/deploy_containers.py`.
- [ ] Adds `snmp`, `dnsutils`, `netcat-openbsd`; SSH client configuration with one alias per equipment
      (`ssh core-a` → `netadmin@10.10.0.21`), SSH protocol 2 only, host keys recorded on first use.
- [ ] Firefox opens on a local portal page listing every web interface (pfSense × 3, Zabbix, Grafana, BMS, DCIM, web
      site, log viewer) with its role; generated, so TrueNAS appears when it is added to the inventory.
- [ ] Every SSH session opened from the webterm is announced to the log collector (who, target, start, end) — A.8.15.
- [ ] Node re-created by `deploy_containers.py`; then `python automation/lab_proxy.py start`.

| Test | Command | From | Expected |
|---|---|---|---|
| Tools | `command -v ssh firefox-esr curl snmpget dig nc` | ADMIN-WS aux console (5053) | six paths |
| Alias | `ssh core-a "show version \| include uptime"` | ADMIN-WS terminal (VNC 5904) | `CORE-A uptime is ...` after the password |
| Portal | open Firefox | ADMIN-WS (VNC 5904) | portal page, every link opens |
| Session logged | `grep "ADMIN-WS" /var/log/remote/all.log \| tail -2` | SYSLOG aux console (5041) | start and end lines of that session |

### ADM.2 Access matrix: everything reachable from the bastion, nothing from elsewhere
Files: `automation/access_matrix.py` (new), `report/evidence/access_matrix.csv`,
`report/content/generated/access_matrix.md`.
- [ ] For every equipment of the inventory: SSH port and banner, web interface status code, from ADMIN-WS.
      Targets: EDGE-A/B, CORE-A/B, LEAF-A1/A2/B1/B2 (management addresses), FW-A/B (SSH and HTTPS), every running
      Linux server (SSH), every web interface.
- [ ] The same probes from a non-administration network (SRV-INF-01, VLAN 100) must all fail — A.8.3, A.8.22.
- [ ] Equipment that is stopped is reported as "not running", not as a failure.

| Test | Command | From | Expected |
|---|---|---|---|
| Matrix | `python automation/access_matrix.py` | host | every running equipment `reachable` from ADMIN-WS, `refused` from SRV-INF-01 |
| One by hand | `ssh edge-a`, `ssh fw-a`, `ssh srv-inf-01` | ADMIN-WS terminal | three logins |
| Refusal is logged | `show access-lists ACL-MGMT-ACCESS` | CORE-A (5010) | hits on `deny any log` after the SRV-INF-01 probes |

### ADM.3 Privileged access rules (A.8.2, A.8.5)
- [ ] Decide and document the two entry points: **ADMIN-WS** (administration desktop, browser and SSH) and
      **SRV-BASTION** (SSH jump host with TOTP second factor and `auditd`, started when its tests run). SSH alias
      `ssh -J bastion core-a` provided for the path through the jump host.
- [ ] Session lock and idle timeout on the devices checked (`exec-timeout 10 0` on Cisco, pfSense GUI session timeout).
- [ ] Default and shared passwords listed with their status (Zabbix default password is removed in ZBX.1).

| Test | Command | From | Expected |
|---|---|---|---|
| Idle timeout | open `ssh core-a`, wait 10 min | ADMIN-WS | session closed by the device |
| Lockout | 5 wrong passwords on `ssh core-a`, then a right one | ADMIN-WS | refused for 120 s; `%SEC_LOGIN-1-QUIET_MODE_ON` in the log collector |
| Jump host | `ssh -J bastion core-a` (SRV-BASTION running) | ADMIN-WS | login through 10.90.0.11 |

---

## FW — Firewall completion

### FW.1 Audit: live firewalls against the generated configuration
Files: `automation/fw_audit.py` (new), `report/evidence/fw_audit.txt`.
- [ ] `fw_audit.py` runs `pfctl -sr`, `pfctl -sn`, `ifconfig | grep carp:` and `ls /cf/conf/trigger_initial_wizard` on
      FW-A and FW-B through `vnc.py`, writes the output to a file on the firewall, fetches it with the existing
      `vm_fileserver.py` path, and compares rule labels with `inventory.firewall_rules`.
- [ ] Record every difference. Known candidates: rules EXT-7 and ADMIN→syslog (generated after the last deployment),
      wizard trigger file (removed live on 12 Oct 2026, not in the deployment procedure).
- [ ] Redeploy with `gen_pfsense.py` if a generated rule is missing live; add the trigger-file removal to the
      deployment step documented in `06_securite.md`.

| Test | Command | From | Expected |
|---|---|---|---|
| Rule labels | `pfctl -sr \| grep -c "EXT-7"` | FW-A and FW-B shell (VNC 5900 / 5901, option 8) | ≥ 1 on both |
| Rule count equal | `pfctl -sr \| wc -l` | FW-A and FW-B | same number |
| Audit | `python automation/fw_audit.py` | host | `0 differences` |
| GUI | open `https://10.90.0.1` | host browser via proxy | dashboard, no setup wizard |

### FW.2 Rules needed by supervision
Zabbix agent on SRV-BASTION (VLAN 90) cannot reach the Zabbix server today: no ADMIN rule for TCP 10051.
Files: `inventory/dc_casa.yaml` (rule `EXT-8`: ADMIN_NET → MON_SERVER tcp ZABBIX_TRAPPER), generated files.
- [ ] Add the rule, validate, `gen_configs.py` (tables), `gen_pfsense.py`, deploy on FW-A, sync to FW-B.
- [ ] Review-focus 2: force FW-B master (`ifconfig carp` maintenance mode on FW-A: *Status > CARP > Enter Persistent
      CARP Maintenance Mode*), repeat the test, leave maintenance mode.

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
- [ ] Reproduce on purpose: continuous probe, `python automation/labctl.py stop CORE-A`, measure, restart CORE-A.
- [ ] **Gate (your decision, with the measurement in hand):**
      (a) add a built-in switch **SW-IN** on VLAN 902 (FW-A, FW-B, CORE-A, CORE-B), as SW-OUT does for VLAN 901, and put
      the firewall LAN on one interface; or (b) keep `lagg0` and document the limit as a lab artefact.
- [ ] If (a): inventory `lab_switches.SW-IN` + device ports, `validate_inventory.py`, `apply_topology.py`,
      `gen_configs.py`, `gen_pfsense.py`, deploy, `verify_topology.py`.

| Test | Command | From | Expected |
|---|---|---|---|
| Probe | `while true; do curl -s -m 1 -o /dev/null -w "%{http_code} " http://10.70.0.12:8080/; sleep 1; done` | SRV-BASTION | `200` every second |
| Fault | `python automation/labctl.py stop CORE-A` | host | probe recovers in ≤ 5 s (target of PLAN_01 T3) |
| Active member | `ifconfig lagg0 \| grep -E "laggport\|status"` | FW-A shell | shows which port carries traffic |
| Restore | `python automation/labctl.py start CORE-A`, wait for `Po1(SU)` | host | no second outage |

### FW.4 Policy measured end to end on the running set
Files: `automation/flow_matrix.py` (option `--running-only`, new probes), `report/evidence/flow_matrix.csv`,
`report/content/generated/flow_matrix.md`.
- [ ] `--running-only` skips a probe whose source or target node is stopped and says so in the output.
- [ ] Add probes that need no hall A server: DMZ → management (denied, from SRV-WEB-01 aux console),
      ISP-A → `192.0.2.80:80` (allowed), ISP-A → `192.0.2.10:22` (denied), SRV-MON-01 → SNMP of FW-A LAN address
      (allowed), SRV-INF-01 → `10.10.0.21` (denied).
- [ ] Every denied probe must be found in the firewall log or in the core ACL counters.

| Test | Command | From | Expected |
|---|---|---|---|
| Matrix | `python automation/flow_matrix.py --running-only` | host | every executed probe `PASS` |
| Denied flows logged | `grep -c "block" /var/log/remote/10.10.0.11_10.10.0.11.log` | SYSLOG aux console | grows after the run |
| Core counters | `show access-lists ACL-VLAN100-IN \| include deny` | CORE-A (5010) | matches > 0 |

### FW.5 Firewall evidence and documentation
Files: `screenshots/2x_*.png`, `report/content/06_securite.md`, lab guide.
- [ ] Screenshots through ADMIN-WS (`vnc.py ADMIN-WS shot`): Status > CARP on both firewalls, Firewall > Rules > ADMIN,
      Firewall > NAT, Status > System Logs > Firewall.
- [ ] `06_securite.md`: results of FW.1–FW.4, the LAN-side decision, updated rule table.

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
