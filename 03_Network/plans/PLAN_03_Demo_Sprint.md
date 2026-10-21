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

### S3 — Zabbix services + Grafana base (ZBX.6, GRF.1–GRF.3) (≈ 2 h)
- [ ] HTTP-agent items on BMS-SIM `/api/state` (path A/B load, state, status) + triggers (45 % warning, 50 % high, not
      POWERED disaster); DCIM `/api/summary` racks; web check `https://10.50.0.11/health`; ICMP SYSLOG.
- [ ] Power test: `api/set?UTILITY-A=DOWN&UPS-A=DOWN&GENERATOR=DOWN` → problem ≤ 30 s, `api/reset` → resolved.
- [ ] Grafana: `allow_sign_up=false`, anonymous off, timezone, `root_url`.
- [ ] Zabbix plugin **offline**: download the zip on the PC (pick a version compatible with the installed Grafana:
      check `grafana-server -v` first), copy it into SRV-MON-01 (via the GNS3 VM, `vm_fileserver.py` / `gns3vm.py`),
      unzip into `/var/lib/grafana/plugins/`, enable the app. Then record the zip in `build_repo.sh` for later.
- [ ] Zabbix read-only user `grafana`; data source provisioned in `/etc/grafana/provisioning/datasources/zabbix.yaml`;
      *Test* button OK.

### S4 — NOC dashboard (GRF.4) (≈ 1.5 h)
- [ ] `03_Network/grafana/dashboards/noc.json` + provisioning, home dashboard. Rows Énergie / Réseau / Sécurité /
      Infrastructure; no "No data" panel (drop a panel rather than leave it empty).
- [ ] Power test turns the Énergie row red within 30 s, back after reset.

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
