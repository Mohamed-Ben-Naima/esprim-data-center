# PLAN_03 — Demo sprint: log server, Zabbix, Grafana (20 → 21 Oct 2026)

Goal: on 21 Oct the lab shows, live and from a cold start, (1) central logs readable from the administration zone,
(2) Zabbix watching the network, firewalls, servers and power, (3) a Grafana NOC dashboard that turns red when a
power path is cut and green again after reset.

Source sub-tasks: PLAN_02 LOG / ZBX / GRF (tests tables there are still the reference). This plan only re-orders and
trims them for the demo.

## Rules of the sprint

- **One session per phase.** Each session reads `AGENTS.md`-style context only as needed: this file, memory, and the
  PLAN_02 section of its phase. It ends by ticking its boxes here, committing, updating memory, and printing the prompt
  for the next session (template at the bottom).
- **No report work** (no `report/content`, no `build.ps1`, no lab guide, no Test the Lab). Deferred to PLAN_02 after the
  demo. Evidence files in `report/evidence/` are fine when they are free (command output).
- **Commit after every sub-task**: `network(DEMO.<n>): ...`. Never commit secrets beyond what the inventory already holds.
- **Lab stays running between sessions.** Do not halt, restart or re-create nodes unless the phase says so. Before any
  heavy step: host free RAM ≥ 0.5 GB (`(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB`), VM load < 8.
- **Safe changes only:** firewall changes through `gen_pfsense.py` + `deploy_pfsense.py` (FW-B first, `--rollback`
  ready) then `fw_audit.py` = 0 difference. Idempotent scripts (get, then create/update).
- If a step burns more than ~45 min, take the fallback written in the phase and move on.

## Phases

### S1 — Demo profile up and stable (≈ 45 min) — done 20 Oct 2026 (DEMO.1–DEMO.5)
- [x] Add `--profile demo` to `automation/lab_up.py`: supervision profile **minus EDGE-B and CCTV-SIM** (keep SRV-INF-01:
      NTP/DNS; EDGE-A alone keeps BGP to ISP-A). Adjust after measuring if the gate fails.
      → adjusted: **SRV-INF-01 also off** (gate B failed with it). No NTP/DNS during the demo.
- [x] `python automation/lab_up.py --profile demo`, then `lab_proxy.py start`.
- [x] Gate (idle 10 min): host free ≥ 0.5 GB, VM load < 8, HSRP state-change count unchanged on CORE-B, Zabbix
      `http://10.60.0.11/` and Grafana `:3000` answer through the proxy.
      → two fixes were needed: core HSRP timers 250/750 ms → **1 s / 3 s** (DEMO.2, live + saved), and the GNS3 VM swap
      flushed after boot (CORE-A had 144 MB swapped out; `lab_up.py` now does `swapoff/swapon`, swappiness 10).
      Count with `show standby | include state change` (the logging buffer wraps). Details:
      `report/evidence/demo_s1_gate.txt`. Host RAM stays tight (0.5–0.7 GB free; another Claude window ≈ 0.65 GB).
- [x] SRV-MON-01 housekeeping: `deploy_servers.py --accounts-only SRV-MON-01` (still pending from ADM.4), delete
      `/var/lib/mysql.broken`, `systemctl is-active mariadb zabbix-server nginx grafana-server` = 4 × active.
      → accounts-ok; `/var/lib/mysql.broken` was already gone; 4 × active.
- [x] `python automation/access_matrix.py` still 0 failure (re-run after a full restart).
      → 16 tested, 0 failure (internal-network leg not probed: SRV-INF-01 off). Re-run in S6.

### S2 — Zabbix base and devices (PLAN_02 ZBX.1–ZBX.5) (≈ 2 h) — done 21 Oct 2026 (DEMO.6–DEMO.9)
- [x] `automation/zabbix_setup.py` (`check` / `apply` / `status`), JSON-RPC through the SOCKS proxy, standard library,
      inventory section `monitoring:` (groups, templates by name, interfaces) + `credentials.zabbix_admin_password`.
      → hosts derived from the inventory: `devices` platform → template/interface, role → group; `monitoring.agents`
      for the Linux servers; `off_triggers` per platform. `check` = API 6.0.48, login, server collecting.
- [x] apply: Admin password from inventory, timezone `Africa/Casablanca`, groups `DC/*`.
      → password is `Zbx-Supervision-2026!` (6.0 refuses a password containing the user name); Admin / zabbix refused.
      The package's "Zabbix server" host became SRV-MON-01 (agent on 10.60.0.11, not 127.0.0.1). Re-run = all up to date.
- [x] Prove SNMPv3 by hand from SRV-MON-01 (`snmpget ... 10.10.0.21`), then hosts: running Cisco devices (SNMPv3
      authPriv `zbxmon`), stopped ones in maintenance `demo-off`; FW-A/FW-B SNMP v2c; agents on SRV-MON-01 (SRV-INF-01 is off in the demo
      profile: add it in maintenance `demo-off`).
      → `snmp` installed on SRV-MON-01 from the offline repo. **LEAF-B2 had lost its SNMPv3 user** ("Unknown user"):
      re-applied from `configs/LEAF-B2.cfg` and saved. Templates `Cisco IOS by SNMP` / `PFSense by SNMP` (they already
      hold the ICMP items; the extra `ICMP Ping` template collides). pfSense "DHCP/DNS server is not running" triggers
      disabled on FW-A/FW-B (off by design). `demo-off` = EDGE-B, LEAF-A1/A2, SRV-INF-01, SRV-BASTION (no data);
      their first ICMP problems stay open but **suppressed** — S4 panels must hide suppressed problems.
      The 4 pfSense DHCP/DNS problems also stay in `problem.get` (disabled trigger, value still 1; the Zabbix frontend
      hides them). S4: problem panels = monitored/enabled triggers only, suppressed hidden (`trigger.get
      only_true+monitored` = 3, all suppressed ICMP).
      Evidence: `report/evidence/demo_s2_snmp_proof.txt`, `demo_s2_zabbix_apply.txt`.
- [x] `zabbix_setup.py status`: every running host available. Fallback if SNMP to a device fails: ICMP-only host for it.
      → 13 hosts, 8 running ones available (6 Cisco SNMPv3, 2 pfSense v2c, SRV-MON-01 agent), 0 failure, no fallback
      needed. SNMP polling did not move the CORE-A/CORE-B HSRP counters. Evidence: `demo_s2_zabbix_status.txt`.
      Not run (node off in the demo profile): agent port to SRV-INF-01, "refused elsewhere" from SRV-BASTION.
      After a cold start (S6): re-run `apply` (maintenance follows the stopped nodes) then `status`.

### S3 — Zabbix services + Grafana base (ZBX.6, GRF.1–GRF.3) (≈ 2 h) — done 21 Oct 2026 (DEMO.10–DEMO.14)
- [x] HTTP-agent items on BMS-SIM `/api/state` (path A/B load, state, status) + triggers (45 % warning, 50 % high, not
      POWERED disaster); DCIM `/api/summary` racks; web check `https://10.50.0.11/health`; ICMP SYSLOG.
      → inventory `monitoring.services` → `zabbix_setup.py apply` (group DC/Services, 4 hosts: BMS-SIM, SRV-DCIM-01,
      SRV-WEB-01, SYSLOG). One HTTP-agent master item per API (10 s) + dependent JSONPath items. Keys for S4:
      `bms.path.load[A|B]`, `bms.path.state[A|B]`, `bms.status`, `bms.alarms`, `bms.it_load`, `bms.pue`,
      `dcim.racks[OK|DEGRADED|DOWN]`, `dcim.inlet.max`, web scenario "Site web DMZ" (`web.test.fail[Site web DMZ]`),
      `icmpping`/`icmppingsec` on SYSLOG. Trigger names in French; 45 % warning depends on the 50 % high one.
      Nominal = 2 warnings "Charge chemin A/B > 45 %" (47.1 %). `status` now shows service items + service problems:
      17 hosts, 0 running host not available. Evidence: `report/evidence/demo_s3_zabbix_services.txt`.
- [x] Power test: `api/set?UTILITY-A=DOWN&UPS-A=DOWN&GENERATOR=DOWN` → problem ≤ 30 s, `api/reset` → resolved.
      → `python automation/power_test.py` (reuse in S4/S6): disaster "Chemin A hors tension" + high "Charge chemin B >
      50 %" + high "Baies en mode dégradé" in 6.3 s / 9.5 s, resolved in 6.3 s. Evidence: `demo_s3_power_test.txt`.
- [x] Grafana: `allow_sign_up=false`, anonymous off, timezone, `root_url`.
      → Grafana role of `deploy_servers.py` (new `--role=grafana SRV-MON-01`, console): GF_* block in
      `/etc/default/grafana-server` (0640). Home without login = 401. Evidence: `demo_s3_grafana_base.txt`.
- [x] Zabbix plugin **offline**: download the zip on the PC (pick a version compatible with the installed Grafana:
      check `grafana-server -v` first), copy it into SRV-MON-01 (via the GNS3 VM, `vm_fileserver.py` / `gns3vm.py`),
      unzip into `/var/lib/grafana/plugins/`, enable the app. Then record the zip in `build_repo.sh` for later.
      → Grafana 13.2.3; plugin **6.8.0** linux-amd64 (needs ≥ 11.6; 6.9.1 skipped, 15 days old), sha256 checked,
      copied with `adminws.put` to `/tmp`, unpacked by the role, app enabled by `grafana/provisioning/plugins/`.
      `build_repo.sh` ships it in `plugins/` of ISO **v3** (not rebuilt; `attach_repo.py` stays on v2 until then).
- [x] Zabbix read-only user `grafana`; data source provisioned in `/etc/grafana/provisioning/datasources/zabbix.yaml`;
      *Test* button OK.
      → user group "Grafana (read-only)" (read on DC/*), built-in "User role"; data source uid `zabbix` (default,
      not editable), password from the service environment. Health = "Zabbix API version 6.0.48"; write call as
      grafana refused. Evidence: `demo_s3_grafana_datasource.txt`.
      S4 note: the role copies `grafana/provisioning/*/*.yaml` only — add the dashboard provider yaml there and
      extend the role to copy `grafana/dashboards/*.json`. Re-run: `deploy_servers.py --role=grafana SRV-MON-01`
      (plugin already installed: the /tmp zip is not needed again).

### S4 — NOC dashboard (GRF.4) (≈ 1.5 h) — done 10 Nov 2026 (after the demo, profile nas + SRV-MON-01 + containers)
- [x] `03_Network/grafana/dashboards/noc.json` + provisioning, home dashboard. Rows Énergie / Réseau / Sécurité /
      Infrastructure; no "No data" panel (drop a panel rather than leave it empty).
      → new **`automation/check_dashboard.py`**: every panel's queries sent to Grafana `/api/ds/query` (text
      queries run in the browser: read from Zabbix instead), problem panel from Zabbix; DATA / HORS PROFIL / EMPTY.
      First run on the draft: **23 of 28 panels empty**: item names without the Zabbix 6.0 template prefix
      (`Linux: CPU utilization`, `Cisco IOS: ICMP ping`, `TrueNAS CORE: ICMP ping`), no ICMP item in "PFSense by SNMP"
      (panel now = `PFSense: SNMP agent availability`), web item name ends with a dot, BMS/DCIM in maintenance.
      Fixed in `gen_dashboards.py`; series renamed to the host; **row "Stockage et sauvegardes"** added (pool state,
      snapshot age, failed pulls, NAS ICMP — PLAN_04); every panel has `noValue` "hors profil" (stopped host in
      maintenance) instead of an empty "No data". Deployed with `deploy_servers.py --role=grafana SRV-MON-01`
      (dashboard version 2 = noc.json): **28/28 panels with data**. Evidence `demo_s4_dashboard_check.txt`.
- [x] Power test turns the Énergie row red within 30 s, back after reset.
      → panel values + their own thresholds read from the deployed dashboard: cut → Chemin A DOWN, Chemin B 94.2 %,
      GTB CRITICAL, alarms 4 in red after **9.6 s**; reset → all green after **5.5 s** (`demo_s4_power_dashboard.txt`).
      **Finding:** first attempts lost 30-90 % of packets and one reset: GNS3 VM swap at 916 MB → CORE-A stalled →
      leafs missed BPDUs → **loop guard blocked the CORE-A uplinks** (no CORE-B in this profile = leaf isolated) and
      every unblock flushed the MAC tables. `sudo swapoff -a && sudo swapon -a` (as lab_up.py) + SRV-INF-01 stopped
      → no loop-guard event since, 0 % loss. Rule: GNS3 VM swap ≈ 0 and ≥ 0.5 GB available before a test.

### S5 — Log server for the demo (LOG.1, LOG.2, LOG.4, LOG.5 trimmed) (≈ 2 h)
- [ ] Quick audit: which running equipment has a file in `/var/log/remote` younger than 10 min; fix silent ones if cheap.
      Cisco NTP to SRV-INF-01 if not synced (`show ntp status`) — SRV-INF-01 is off in the demo profile: skip NTP
      (known limit) rather than add load.
- [ ] Image `dc/syslog:1.1`: logrotate daily + compression, dir 0750 / files 0640, read-only viewer `viewer.py`
      (standard library, HTTPS 8443, login, search by source/text, last lines). Redeploy with
      `deploy_containers.py SYSLOG` — volume must survive (check file count before/after).
- [ ] Firewall rule EXT-9 (ADMIN_NET → SYSLOG_SERVER tcp 8443) via generator + deploy + audit; portal entry on ADMIN-WS.
- [ ] Demo events found in the viewer: failed SSH login on CORE-A, `conf t`/`end` on CORE-A, firewall block.
      Fallback if the viewer slips: show `tail -f` on the SYSLOG aux console (5042) from ADMIN-WS.

### S6 — Cold-start rehearsal and demo runbook (≈ 1 h) — mandatory
- [ ] Clean stop of all nodes, then `lab_up.py --profile demo` + `lab_proxy.py start`; no manual fix allowed. Time it.
- [ ] Check: 4 services active on SRV-MON-01, `zabbix_setup.py status`, Grafana NOC live, log viewer answers.
- [ ] `03_Network/DEMO_RUNBOOK.md` (French): start commands + wait time, URLs and logins, the demo script (power cut →
      Zabbix problem → Grafana red → reset; failed login → log viewer; firewall block → log), what to do if X fails.
- [ ] Leave the lab stopped cleanly or running, as the user prefers for the morning.

## After the demo (back to PLAN_02)
FW.3–FW.5, LOG.3, LOG.6, ZBX.7, GRF.5 documentation, ISO.1–2, all report chapters, Test the Lab entries, lab guide.

## Next-session prompt template
```
Demo sprint, phase S<n> of 03_Network/plans/PLAN_03_Demo_Sprint.md (demo is 21 Oct 2026).
Read that plan, memory, and the PLAN_02 sections it cites for S<n>; do only S<n>.
State left by the previous session: <one or two lines>.
No report work. Commit per sub-task. Lab stays running. Brief caveman replies.
At the end: tick the boxes, commit, update memory, give me the prompt for S<n+1>.
```
