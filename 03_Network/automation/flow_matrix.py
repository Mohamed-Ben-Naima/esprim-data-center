"""End-to-end flow matrix (PDF Table 18): probes run from the lab hosts, compared with the expected verdict (FW.4).

  python automation/flow_matrix.py                 every probe; one whose source or target is stopped = "non testé"
  python automation/flow_matrix.py --running-only  same, and says "skipped (X stopped)" - the normal mode for a profile
  -> report/evidence/flow_matrix.csv + report/content/generated/flow_matrix.md

Each probe is a TCP connect (3 s), an ICMP echo, an SNMP get or an HTTP(S) request, run where the flow starts:
  VM sources (SRV-*, Ubuntu)   over SSH from ADMIN-WS (adminws.ssh_batch, one round trip for all of them)
  container sources            `docker exec` in the GNS3 VM (ADMIN-WS, SRV-WEB-01, ISP-A)
A probe passes when the observed result (open / closed-or-filtered) equals the policy decision.
Every DENIED probe that was executed must also be found in the central log (log viewer, after the run): a pfSense
`filterlog ... block` line or a core ACL `%SEC-6-IPACCESSLOG... denied` line naming its source and destination.
Exit code 1 on a deviation or a denied flow that left no trace.
"""
import base64
import csv
import re
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import gns3vm  # noqa: E402
import labctl  # noqa: E402
from adminws import ssh_batch  # noqa: E402

NET = Path(__file__).resolve().parents[1]
INV = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
COMM = INV["credentials"]["snmp_ro_community"]
FW_A_LAN = INV["transit"]["int"]["FW-A"]


# SNMP secrets never appear on a command line (the ADMIN-WS ssh wrapper logs command lines to the collector):
# they are sent once through stdin to a 0600 file on SRV-MON-01, read there with sed, and deleted after the run.
SECRETS = "/tmp/.flow_matrix_snmp"
SNMP2 = f"snmpget -v2c -c \"$(sed -n 1p {SECRETS})\" -t 2 -r 0"
SNMP3 = (f"snmpget -v3 -l authPriv -u \"$(sed -n 2p {SECRETS})\" -a SHA -A \"$(sed -n 3p {SECRETS})\" "
         f"-x AES -X \"$(sed -n 4p {SECRETS})\" -t 2 -r 0")


def tcp(ip, port):
    return f"timeout 3 bash -c '</dev/tcp/{ip}/{port}'"


def nc(ip, port):                      # busybox containers without bash
    return f"nc -z -w 3 {ip} {port}"


# (source, flow, probe, expected True=allowed / False=denied, reference, nodes the flow needs, (src ip, dst ip, port))
# The last field is what the log line of a denied flow must name.
PROBES = [
    ("SRV-CMP-01", "Serveurs -> stockage NFS 2049", tcp("10.30.0.11", 2049), True, "T18-3", ["SRV-STO-01"], None),
    ("SRV-CMP-01", "Serveurs -> stockage iSCSI 3260", tcp("10.30.0.11", 3260), True, "T18-3", ["SRV-STO-01"], None),
    ("SRV-CMP-01", "Serveurs -> NAS 873 (push fermé, sauvegarde tirée)", tcp("10.40.0.11", 873), False, "T18-4/NAS",
     ["SRV-BCK-01"], ("10.20.0.11", "10.40.0.11", 873)),
    ("SRV-CMP-01", "Serveurs -> SSH du stockage (non autorisé)", tcp("10.30.0.11", 22), False, "T18 défaut",
     ["SRV-STO-01"], ("10.20.0.11", "10.30.0.11", 22)),
    ("SRV-CMP-01", "Serveurs -> DNS interne", "dig +time=2 +short @10.100.0.11 example.com | grep -q .", True, "commun",
     ["SRV-INF-01"], None),
    ("SRV-CMP-01", "Serveurs -> Internet HTTPS (SNAT)", "curl -s -m 6 -o /dev/null https://deb.debian.org", True, "T18-5",
     ["FW-A", "EDGE-A", "ISP-A"], None),
    ("SRV-CMP-01", "Serveurs -> management OOB (interdit)", "ping -c 1 -W 2 10.10.0.21", False, "deny MGMT",
     ["CORE-A"], ("10.20.0.11", "10.10.0.21", None)),
    ("SRV-CMP-01", "Serveurs -> site web DMZ", "curl -sk -m 5 -o /dev/null https://10.50.0.11", True, "EXT-3",
     ["FW-A", "SRV-WEB-01"], None),
    ("SRV-MON-01", "Supervision -> SNMP équipements (UDP 161)",
     f"{SNMP3} 10.10.0.21 1.3.6.1.2.1.1.5.0", True, "T18-7", ["CORE-A", "FW-A"], None),
    ("SRV-MON-01", "Supervision -> SNMP pare-feu (adresse LAN de FW-A)",
     f"{SNMP2} {FW_A_LAN} 1.3.6.1.2.1.1.5.0", True, "T18-7", ["FW-A"], None),
    ("SRV-MON-01", "Supervision -> SSH équipements (interdit, SNMP/ICMP seulement)", tcp("10.10.0.21", 22), False,
     "deny MGMT", ["CORE-A"], ("10.60.0.11", "10.10.0.21", 22)),
    ("SRV-MON-01", "Supervision -> agent Zabbix 10050", tcp("10.20.0.11", 10050), True, "T18-7", ["SRV-CMP-01"], None),
    ("SRV-STO-01", "Stockage -> Internet HTTPS", "curl -s -m 6 -o /dev/null https://deb.debian.org", True, "T18-5",
     ["FW-A", "EDGE-A", "ISP-A"], None),
    ("SRV-STO-01", "Stockage -> serveurs SSH (non autorisé)", tcp("10.20.0.11", 22), False, "T18 défaut",
     ["SRV-CMP-01"], ("10.30.0.11", "10.20.0.11", 22)),
    ("SRV-INF-01", "Services internes -> management OOB (interdit)", tcp("10.10.0.21", 22), False, "deny MGMT",
     ["CORE-A"], ("10.100.0.11", "10.10.0.21", 22)),
    ("SRV-BASTION", "Administration -> SSH serveurs", tcp("10.20.0.11", 22), True, "T18-6", ["SRV-CMP-01", "FW-A"], None),
    ("SRV-BASTION", "Administration -> SSH équipements", tcp("10.10.0.21", 22), True, "T18-6", ["CORE-A", "FW-A"], None),
    ("SRV-BASTION", "Administration -> webGUI pare-feu", "curl -sk -m 5 -o /dev/null https://10.90.0.1", True, "T18-6",
     ["FW-A"], None),
    ("ADMIN-WS", "Administration -> SSH équipements", tcp("10.10.0.21", 22), True, "T18-6", ["CORE-A", "FW-A"], None),
    ("ADMIN-WS", "Administration -> Grafana", "curl -s -m 5 -o /dev/null http://10.60.0.11:3000/login", True, "T18-6",
     ["SRV-MON-01", "FW-A"], None),
    ("ADMIN-WS", "Administration -> base Zabbix 3306 (interdit)", tcp("10.60.0.11", 3306), False, "T18 défaut ADMIN",
     ["SRV-MON-01", "FW-A"], ("10.90.0.12", "10.60.0.11", 3306)),
    ("SRV-WEB-01", "DMZ -> management (interdit)", nc("10.10.0.21", 22), False, "T18-9",
     ["CORE-A", "FW-A"], ("10.50.0.11", "10.10.0.21", 22)),
    ("SRV-WEB-01", "DMZ -> administration (interdit)", nc("10.90.0.12", 22), False, "T18-9",
     ["ADMIN-WS", "FW-A"], ("10.50.0.11", "10.90.0.12", 22)),
    ("SRV-WEB-01", "DMZ -> supervision (interdit, refus par défaut)", nc("10.60.0.11", 80), False, "T18 défaut DMZ",
     ["SRV-MON-01", "FW-A"], ("10.50.0.11", "10.60.0.11", 80)),
    ("ISP-A", "Internet -> site web public 192.0.2.80 (DNAT 80 -> 301 -> 443)",
     "timeout 8 wget -q --no-check-certificate -O /dev/null http://192.0.2.80/",
     True, "T18-1", ["EDGE-A", "FW-A", "SRV-WEB-01"], None),
    ("ISP-A", "Internet -> SSH de l'adresse SNAT 192.0.2.10 (interdit)", tcp("192.0.2.10", 22), False, "WAN défaut",
     ["EDGE-A", "FW-A"], (None, "192.0.2.10", 22)),
]
CONTAINERS = {"ADMIN-WS", "SRV-WEB-01", "ISP-A", "ISP-B"}


def run_vms(items):
    """[(src, cmd)] on Ubuntu servers over SSH from ADMIN-WS -> [rc]."""
    snmp = sorted({src for src, cmd in items if SECRETS in cmd})
    if snmp:
        import tempfile
        from adminws import put
        c = INV["credentials"]
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "s"
            f.write_bytes(("\n".join([COMM, c["snmpv3_user"], c["snmpv3_auth"], c["snmpv3_priv"]]) + "\n").encode())  # LF only
            for src in snmp:
                ssh_batch([(src.lower(), f"umask 077; : > {SECRETS}")])
                put(src.lower(), f, SECRETS)
    try:
        res = ssh_batch([(src.lower(), cmd) for src, cmd in items], timeout=30)
    finally:
        if snmp:
            ssh_batch([(src.lower(), f"rm -f {SECRETS}") for src in snmp])
    return [rc for rc, _ in res]


def run_containers(items):
    """[(src, cmd)] by docker exec in the GNS3 VM -> [rc]."""
    lines = []
    for i, (src, cmd) in enumerate(items):
        b = base64.b64encode(cmd.encode()).decode()
        lines.append(f"c=$(docker ps -q --filter name=GNS3.{src}.); cmd=$(echo {b} | base64 -d); "
                     f"if [ -n \"$c\" ]; then docker exec $c sh -c \"$cmd\" >/dev/null 2>&1; echo \"@@{i} $?\"; "
                     f"else echo \"@@{i} 255\"; fi")
    out = gns3vm.run("\n".join(lines), sudo=True)
    rcs = dict(re.findall(r"@@(\d+) (\d+)", out))
    return [int(rcs.get(str(i), 255)) for i in range(len(items))]


def traces(since, denied):
    """For each denied (src, dst, port): the first log line naming it (pfSense block or core ACL deny), or ''."""
    from log_viewer import Viewer
    v = Viewer()
    out = []
    for src, dst, port in denied:
        lines = v.search(dst, "all.log", 400)
        hit = ""
        for l in lines:
            if l[:19] < since:
                continue
            fw = "filterlog" in l and ",block," in l and f",{dst}," in l and (src is None or f",{src}," in l) \
                and (port is None or re.search(rf",{dst},\d+,{port},", l))
            acl = "denied" in l and (src is None or f"{src}(" in l or f" {src} " in l) and dst in l
            if fw or acl:
                hit = l
                break
        out.append(hit)
    return out


def main(argv):
    running_only = "--running-only" in argv
    api = labctl.Gns3()
    up = {n["name"] for n in api.nodes(api.project()) if n["status"] == "started"}
    t_since = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - 5))
    plan, rows = [], []
    for src, descr, cmd, expect, ref, needs, trace in PROBES:
        stopped = [n for n in [src] + needs if n not in up]
        if stopped:
            rows.append([src, descr, "autorisé" if expect else "refusé",
                         f"ignoré ({', '.join(stopped)} arrêté)" if running_only else "non testé", "—", ref, ""])
            continue
        plan.append((len(rows), src, cmd, expect, trace))
        rows.append([src, descr, "autorisé" if expect else "refusé", "", "", ref, ""])
    vm = [(i, s, c) for i, s, c, _, _ in plan if s not in CONTAINERS]
    ct = [(i, s, c) for i, s, c, _, _ in plan if s in CONTAINERS]
    rc = {}
    if vm:
        rc.update(zip([i for i, _, _ in vm], run_vms([(s, c) for _, s, c in vm])))
    if ct:
        rc.update(zip([i for i, _, _ in ct], run_containers([(s, c) for _, s, c in ct])))
    for i, src, cmd, expect, trace in plan:
        ok = (rc[i] == 0) == expect
        rows[i][3] = "ouvert" if rc[i] == 0 else ("bloqué" if rc[i] != 255 else "erreur")
        rows[i][4] = "OK" if ok else "ÉCART"
    denied = [(i, trace) for i, src, cmd, expect, trace in plan if not expect and trace and rows[i][4] == "OK"]
    if denied:
        time.sleep(4)                                    # let the last log lines reach the collector
        for (i, _), hit in zip(denied, traces(t_since, [t for _, t in denied])):
            m = re.search(r"\s(\S+)\s(\S+)\s(filterlog|\d+:)", hit)
            rows[i][6] = ("pare-feu " if "filterlog" in hit else "ACL cœur ") + (m.group(1) if m else "") if hit else "AUCUNE TRACE"
    for r in rows:
        flag = {"OK": "OK ", "ÉCART": "BAD", "—": "-- "}.get(r[4], "?? ")
        print(f"{flag} {r[0]:12} {r[1][:62]:62} {r[3]:28} {r[6]}")
    out = NET / "report" / "evidence" / "flow_matrix.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source", "flux", "attendu", "observé", "verdict", "réf", "trace du refus"])
        w.writerows(rows)
    md = [f"Table: Matrice de flux mesurée de bout en bout le {time.strftime('%d/%m/%Y')} "
          "(automation/flow_matrix.py --running-only)",
          "| Source | Flux | Attendu | Observé | Verdict | Réf. | Trace du refus |", "|---|---|---|---|---|---|---|"]
    md += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | **{r[4]}** | {r[5]} | {r[6]} |" for r in rows]
    (NET / "report" / "content" / "generated" / "flow_matrix.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    run = [r for r in rows if r[4] in ("OK", "ÉCART")]
    bad = sum(r[4] == "ÉCART" for r in rows)
    untraced = sum(r[6] == "AUCUNE TRACE" for r in rows)
    print(f"{len(rows)} probes: {len(run)} executed, {bad} deviation(s), "
          f"{sum(1 for r in run if r[2] == 'refusé')} denied of which {untraced} without a log trace -> {out.relative_to(NET)}")
    return 1 if bad or untraced else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
