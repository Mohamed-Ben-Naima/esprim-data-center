# PLAN_06 – Live GNS3 walkthrough video (voiceover + subtitles) for the 25 Nov 2026 soutenance

## Context
The existing demo video (PLAN_05, `03_Network/automation/demo_video/director.py` + `edit.py`) is **silent**. It has
captions only, the master was never encoded (killed for low memory), and its "topology" scene is a page drawn from
the GNS3 API, not GNS3 itself. The user wants something else: **a real recording of GNS3 used live**. Cold-start the
lab, then open each machine (pfSense, core/leaf switches, EDGE/WAN, DMZ web, administration ADMIN-WS, services,
compute, storage, TrueNAS, Zabbix, Grafana NOC/SOC), executing commands live while following the Grafana metrics and
dashboards. Use a split screen when useful. Add a **French voiceover plus burned-in subtitles**. **For every node
opened, the narration briefly states: its role → what we verify/test → the result on screen.** The user also
explains live, so they need a separate live script.

Outcome: a long cut (≈12–15 min, full tour, submission and plan B) and a **jury cut ≤ 5:00** (Partie 3, deck v1
slide 21). Plus `.srt` files, `DEMO_SCRIPT.md`, and the deck updated. Today is 2026-11-23; the soutenance is
2026-11-25.

## Rules for the executing session (non-negotiable)
- **Full autonomy for this exact task**, all permissions granted: run every phase P0→P8 without asking or pausing.
  Stop only for user-only actions: the VM frozen ("Retry" in VMware), disk H: errors, the GNS3 VM unreachable after
  `gns3vm.py` start attempts.
- Caveman replies, sign 🍀. Commit + push after each phase. Stage **only** files this plan touches (the pre-existing
  changes to `DC_Casablanca_TIA942_R3.gns3` and `automation/collect_images.py` are not ours). End commits with:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01FJjqidtCRBpbuNM5sNbWMx`
- Read the memories first: `lab-capacity-limits`, `gns3-container-consoles`, `gns3-vm-network-setup`,
  `no-secrets-on-ssh-cmdline`, `presentation-plan05`, `demo-video-v2-spec`, `full-autonomy`.
- **No secrets on SSH command lines.** ADMIN-WS logs command lines, so pass secrets via put/stdin/file, and never
  show a password on screen (use masked fields only).
- **Never press Ctrl-C in a docker node's main console**; it kills the service. Use aux ports or `docker exec`.
- **No AD/LDAP (D4).** The lab has **no SIEM**: call it "SOC / journalisation centralisée" (SYSLOG + log viewer +
  lockout). Never claim Wazuh/ELK.
- Every number spoken or written comes from `05_Report/presentation/facts.json` or from the live output of that same
  run. Result sentences use placeholders filled from the scene marks (e.g. measured outage).
- RAM: 15.7 GB host, 8 GB GNS3 VM. Never run more than one profile's worth of nodes. Flush swap after boots
  (`lab_up.py` does it). Encode only **after the lab is stopped**, at BelowNormal priority, **scene by scene then
  concat `-c copy`** (a single big encode was OOM-killed). Run `demo_check.py` after each act.
- The background-shell reaper hits when host memory is critically low: keep waits short, re-check instead of
  re-running.

## Reuse (do not rewrite)
- `automation/demo_video/director.py`:
  - `Scene` (Playwright context through the SOCKS proxy 192.168.75.128:1080, cursor overlay `CURSOR_JS`, `mark()`,
    `shot()`, `glide_to()`, `type_into()`)
  - `Term` (typist terminal page with `run_ssh()` via `adminws.ssh_batch`, `run_local()`)
  - `failover()` (0.5 s probe + chrono panel), `login_zabbix()`, the `s8_t6` BMS cut via
    `zabbix_setup.SocksHTTPConnection`
  - existing scene bodies `s3_network`… `s9_proof` (commands and URLs below)
- `automation/demo_video/edit.py`: `ff()`, `dur()`, `render_pngs()` (chapter cards, captions, thumbnail and end card
  rendered by Edge in the deck style), `still()`.
- `automation/lab_up.py --profile demo|compute|nas` (STAGES/OFF sets, `measure()` RAM table, swap flush, `post()`),
  `lab_down.py`, `labctl.Gns3` (`project()`, `node()`, `start()`, `stop()`), `labctl.Console`,
  `gns3vm.run(..., sudo=True)`.
- Proof and test scripts: `demo_check.py` (12 checks), `verify_lab.py` (59 tests), `power_test.py` (T6),
  `fw_lan_failover.py`, `log_viewer.py demo|lock` (SOC), `flow_matrix.py`/`access_matrix.py` (ACL),
  `truenas_setup.py` (TrueNAS JSON-RPC over wss://10.40.0.11), `check_dashboard.py`.
- Known URLs:
  | Service | Address |
  |---|---|
  | pfSense FW-A | https://10.90.0.1/ (status_carp, firewall_rules?if=opt2, firewall_nat, status_logs_filter) |
  | Zabbix | http://10.60.0.11/ |
  | Grafana | http://10.60.0.11:3000/ (first load ≈34 s, cut it) |
  | Log viewer | https://10.60.0.12/ |
  | DCIM | http://10.70.0.11:8080/ |
  | BMS | http://10.70.0.12:8080/ (`/api/set?...`, `/api/reset`) |
  | Web | DMZ 10.50.0.11, public 192.0.2.80 (from ISP-A with `nc`; no curl in the ISP image) |
- Deck: `05_Report/presentation/deck_v1/` (slides `demo.html`, `surete.html`, `assets_map.json`,
  `render_check.py`, `make_vector_pdf.py`), artifact https://claude.ai/artifact/GTcGERUuaHRf8tavD91S4v.

## New files
| File | Purpose |
|---|---|
| `03_Network/plans/PLAN_06_Live_Walkthrough_Video.md` | This plan plus a decision log (D1…), written in P0 |
| `03_Network/automation/demo_video/narration.yaml` | One entry per segment: `id`, `act`, `node`, `role`, `test`, `result` (with `{placeholders}`), `vo` (spoken FR), `sub` (subtitle FR, ≤ 2 lines × 42 chars), `jury: true/false`, `jury_vo` (shorter variant) |
| `03_Network/automation/demo_video/voice.py` | edge-tts (fr-FR-HenriNeural, rate −5 %) → one mp3 per segment + durations.json. Fallback: offline Windows "Microsoft Hortense Desktop" via System.Speech. Builds the `.ass` and `.srt` timed to the VO |
| `03_Network/automation/demo_video/walkthrough.py` | Director v2: `Gns3Web` driver (GNS3 Web UI), `Split` (two Scenes recorded at the same time, 960×1080 each, aligned by t0), acts and scenes below, marks named after the narration ids |
| `03_Network/automation/demo_video/edit2.py` | Assembly: for each narration id, cut raw video between its marks and fit it to the VO length (setpts 0.75–1.5×, else tpad freeze or trim); timelapse segments get a "×10" badge; hstack for split scenes; burn ASS subtitles (needs libass); add VO (loudnorm −16 LUFS); encode per segment then concat. Outputs the long and jury cuts, chapters.txt and .srt |
| `05_Report/presentation/DEMO_SCRIPT.md` | Live script for the user: minute by minute, role/test/result points per node, when to pause the video, answers if the jury interrupts |

Outputs:
- `05_Report/presentation/video/DC_Casablanca_walkthrough.mp4` (long cut)
- `DC_Casablanca_demo_5min.mp4` (jury cut)
- `.srt` files next to each cut
- `video/clips_v2/` (one clip per segment)

Check whether `video/.gitignore` and `.gitattributes` (LFS) cover mp4 before committing videos.

## Storyboard (each node = role → test → result, in VO and subtitles)
**Act 0 · Démarrage (demo profile).** Split screen: left the GNS3 Web UI (project open, nodes turn green); right a
terminal with `lab_up.py --profile demo` and its stage/RAM table. Timelapse ×10. Narrate start by tiers (WAN → security
→ core → services) and why: 15.7 GB of RAM. Right-click a node → Console in the Web UI once, to show "opening a
machine" in GNS3 itself.

**Act 1 · Réseau, sécurité, services, supervision (demo profile).** Example segments (role / test / result):
- **ISP-A / EDGE-A.** Role: border router with eBGP to the operators. Test: `show ip bgp summary`. Result: session
  Established, routes received.
- **CORE-A / CORE-B.** Role: core that routes the 14 VLANs and shares the gateway. Tests: `show standby brief`,
  `show ip ospf neighbor`, `show etherchannel summary`. Results: Active/Standby, OSPF FULL, Po up.
- **LEAF-B1/B2.** Role: top-of-rack access for hall B. Tests: `show interfaces trunk`, `show spanning-tree summary`.
  Result: VLANs allowed, no inconsistent port.
- **FW-A / FW-B (pfSense).** Role: HA firewall, NAT and inter-zone filtering. Tests: CARP status, rules, NAT,
  refusal log. Result: 5 VIPs MASTER on A, BACKUP on B.
- **SRV-WEB-01 (DMZ).** Role: public website. Tests: `nc` from ISP-A to 192.0.2.80, then DMZ → management. Result:
  "OK SRV-WEB-01", the second flow refused.
- **ADMIN-WS.** Role: the only administration station, VLAN 90. Test: SSH from it. Result: access OK, session logged.
- **SRV-MON-01.** Role: Zabbix + Grafana + MariaDB. Tests: Zabbix hosts and problems pages, then a split screen with
  the Grafana NOC dashboard.
- **SYSLOG (SOC).** Role: central log server + viewer. Test: `log_viewer.py demo` (failed login, config change,
  DMZ block, each found in the viewer), then `lock`. Result: account locked after 6 attempts.
- **BMS-SIM / SRV-DCIM-01.** Role: building management (GTB) and DCIM. Test: live pages. Result: 20–25 °C after the
  D28 fix, 96 racks OK.
- **Failover T6** (split: BMS/terminal left, Grafana right): power path A cut → alarm, racks degraded, path B
  carries the load → reset.
- **Failover T2** (split: probe left, pfSense CARP or Grafana right): FW-A stopped → measured outage `{outage}` s →
  FW-B MASTER → FW-A restarted.
- **Proof:** `demo_check.py` → 12/12.

**Act 2 · Compute (compute profile).**
- **LEAF-A1/A2.** Role: hall A access. Test: trunks and LACP.
- **SRV-CMP-01/02.** Role: compute with a keepalived VIP. Tests: VIP owner, then stop CMP-01 under a probe (T5).
  Results: VIP moves, outage measured, Zabbix shows it.
- SRV-CMP-03 / SRV-STO-01 / SRV-INF-01 / SRV-BASTION are added only if the RAM check passes: host free ≥ 1.0 GB and
  VM available ≥ 0.5 GB after settle. Otherwise move STO-01 to act 3, and tell the jury plainly why.

**Act 3 · Stockage (nas profile).**
- **SRV-BCK-01 (TrueNAS).** Role: backup NAS that pulls backups (servers hold no credentials toward it). Tests:
  pool status, ZFS snapshots, the pull job, a live restore of a deleted file. Result: same SHA-256.
- SRV-STO-01 here if not shown in act 2.

**Fin.** `verify_lab.py` summary (non-disruptive), proof card, clean `lab_down.py`, end card.

Jury cut (≤ 5:00), uses the `jury: true` segments with `jury_vo`. It follows deck slide 21:
| Time | Segment |
|---|---|
| 0:00 | start timelapse, about 20 s |
| 0:30 | CORE-A HSRP/OSPF |
| 1:30 | pfSense CARP + DMZ web/deny |
| 2:15 | Grafana NOC + SOC log line |
| 3:00 | T6 |
| 3:45 | T2 |
| 4:30 | demo_check 12/12 |

## Phases (commit + push after each)
- **P0 Preflight (≈30 min).**
  - Write PLAN_06 into the repo.
  - GNS3 VM up (`gns3vm.py`, ping 192.168.75.128). The project opens: if a 409 stale container appears, apply the
    fix from the `gns3-container-consoles` memory.
  - **Check the GNS3 Web UI** at `http://192.168.75.128:3080/static/web-ui/` (GNS3 2.2.56.1) and that its web
    console opens on an IOSvL2 node and on pfSense. **Fallback:** record the GNS3 desktop app with ffmpeg `gdigrab`
    while driving it with pywinauto/pyautogui; log it as a decision.
  - `pip install edge-tts`; check `ffmpeg -filters` has `subtitles`/`ass`; check the Inter font for libass (else ship
    the TTF via `fontsdir`).
  - Deploy the **DCIM fix D28**: rebuild the `dc/dcim` image (`build_images.py`), re-create SRV-DCIM-01
    (`deploy_containers.py`), check inlet temperatures stay 20–25 °C.
  - Check whether `lab_up.py` stops the nodes outside a profile; if not, switching acts = `labctl` stop of the
    difference first.
- **P1 Narration (≈1 h).** Write `narration.yaml` (all segments, role/test/result, VO ≤ 15 s per node) and the
  `DEMO_SCRIPT.md` draft. Cross-check every number against facts.json.
- **P2 Voice + subtitles (≈45 min).** `voice.py`; test 3 segments and listen to them (ffprobe durations). Then build
  the ASS/SRT and a 20 s test render with burned subtitles + VO to verify sync and legibility (view frames).
- **P3 Director v2 (≈2 h).** `walkthrough.py`: `Gns3Web`, `Split`, act scenes reusing the director.py bodies. Marks =
  narration ids. Dry-run each scene briefly on the lab.
- **P4 Record act 0 + act 1 (≈1 h).** Cold start from all-off, record, `demo_check` afterwards. Retake a scene if it
  fails.
- **P5 Record act 2 + act 3 (≈1 h).** Profile switches (each boot is timelapsed), RAM check before the extras, then
  `lab_down.py`, VM idle.
- **P6 Assemble + encode (≈1 h).** `edit2.py` long cut + jury cut, scene by scene at BelowNormal, concat; chapters,
  srt, thumbnail v2.
- **P7 QA (≈45 min).**
  - Contact sheets (a frame every 10 s) viewed one by one.
  - VO/subtitle sync at 5 random points.
  - No secret visible on screen or in typed commands.
  - Numbers match facts.json and live output.
  - `ffprobe`: jury cut ≤ 300 s, 1080p, AAC audio.
  - Listen to the start, middle and end of the VO.
- **P8 Integrate (≈45 min).**
  - Deck v1: slide 21 timings from the jury-cut chapters plus the new thumbnail; slide 10 gets the new Grafana shot
    46 (re-upload the asset, update `assets_map.json`) and loses the 29.5 °C caption.
  - `render_check.py` 24/24, republish the artifact (same URL), rebuild both PDFs.
  - Update `REPETITION.md`, `05_Report/README.md`, PLAN_05 D28/D29 → done/superseded by PLAN_06.
  - Copy the videos to H: if it is safe.
  - Update the memory (`demo-video-v2-spec`, `presentation-plan05`).
  - Final caveman reply with paths and links 🍀.

**Estimate: ≈ 8–9 h, plus ≈ 2 h buffer** (VM freeze, USB disk H:, retakes).

## Verification (end to end)
- `python automation/demo_check.py` → 12/12 after each act. The `verify_lab.py` summary is shown in the video.
- `ffprobe` both cuts: duration (jury ≤ 5:00), 1920×1080, an audio stream. The `.srt` files exist and their cue
  count equals the narration segments.
- Frame contact sheets reviewed: GNS3 Web UI visible in act 0; each node segment shows role/test/result in the
  subtitle; split scenes are readable (text ≥ 22 px at 960 wide).
- `grep` narration.yaml and DEMO_SCRIPT.md numbers against facts.json (no orphan number).
- Deck: `render_check.py` 24/24 OK, artifact republished, slide 10 without the caption.

## Handoff prompt for the new session
"Execute `C:\Users\ASUS\.claude\plans\starry-singing-cocoa-of-008dec52-952e-44d7-b545-309541e4cbdf.md`
(PLAN_06, live GNS3 walkthrough video with voiceover and subtitles). Full autonomy, all permissions for this task;
do P0→P8 without stopping, commit + push after each phase, caveman replies, sign 🍀. Read the memories it lists
first."

## Decision log (executing session, 23–24 Nov 2026)
| # | Decision | Why |
|---|---|---|
| D1 | **GNS3 Web UI = local controller** `http://127.0.0.1:3080/static/web-ui/` (Web UI v2.2.54), not the VM (`:80` there is only a compute). The recorder pre-seeds `localStorage` (`serverIds=server-1`, `server-1={host 127.0.0.1, port 3080, authorization basic}`) and opens `/server/1/project/<id>`. | Preflight: the plan's `192.168.75.128:3080` does not listen; the project lives on the local controller. |
| D2 | **D28 deployed**: `build_images.py dcim` (sha256 fa36738b…, smoke 96 racks OK), `deploy_containers.py SRV-DCIM-01` (re-created, 2 links restored). The `.gns3` file changes again (new node id) but is **not committed**: it already carried the user's own uncommitted diff. | Slide 10 / NOC must show 20–25 °C. |
| D3 | Subtitle fonts shipped in `demo_video/fonts/` (Inter 500/700/800, JetBrains Mono, OFL) and passed to libass with `fontsdir`. | Inter is not installed on Windows. |
| D4 | `lab_up.py` only starts nodes: a profile switch = stop the nodes of the old profile that the new one does not use, **then** start (RAM never holds two profiles). | Preflight read of lab_up.py. |
| D5 | `ramguard.py` runs during every recording: logs host free RAM every 5 s; < 0.45 GB twice → kills the recording browser and any ffmpeg (the lab stays up). | User: the PC powers off when RAM saturates. |
| D6 | Deadline 05:00 (user asleep). Priority: jury cut ≤ 5:00 first, long cut second; split scenes only where they add value. | Time. |
