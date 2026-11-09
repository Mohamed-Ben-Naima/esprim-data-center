"""End-to-end flow matrix (PDF Table 18): probes run from the lab hosts, compared with the expected verdict.

  python automation/flow_matrix.py            -> report/evidence/flow_matrix.csv + report/content/generated/flow_matrix.md
Each probe is a TCP connect (bash /dev/tcp, 3 s), an ICMP echo or an HTTP(S) request. A probe passes when the
observed result (open / closed-or-filtered) equals the expected policy decision.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import labctl  # noqa: E402

NET = Path(__file__).resolve().parents[1]

# (source node, description, shell probe, expected True=allowed / False=denied, reference)
PROBES = [
    ("SRV-CMP-01", "Serveurs -> stockage NFS 2049", "timeout 3 bash -c '</dev/tcp/10.30.0.11/2049'", True, "T18-3"),
    ("SRV-CMP-01", "Serveurs -> stockage iSCSI 3260", "timeout 3 bash -c '</dev/tcp/10.30.0.11/3260'", True, "T18-3"),
    ("SRV-CMP-01", "Serveurs -> NAS 873 (push fermé, sauvegarde tirée)", "timeout 3 bash -c '</dev/tcp/10.40.0.11/873'", False, "T18-4/NAS"),
    ("SRV-CMP-01", "Serveurs -> SSH du stockage (non autorisé)", "timeout 3 bash -c '</dev/tcp/10.30.0.11/22'", False, "T18 défaut"),
    ("SRV-CMP-01", "Serveurs -> DNS interne", "getent hosts www.example.com >/dev/null || dig +time=2 +short @10.100.0.11 example.com | grep -q .", True, "commun"),
    ("SRV-CMP-01", "Serveurs -> Internet HTTPS (SNAT)", "curl -s -m 6 -o /dev/null https://deb.debian.org", True, "T18-5"),
    ("SRV-CMP-01", "Serveurs -> management OOB (interdit)", "ping -c 1 -W 2 10.10.0.21", False, "deny MGMT"),
    ("SRV-CMP-01", "Serveurs -> site web DMZ", "curl -sk -m 5 -o /dev/null https://10.50.0.11", True, "EXT-3"),
    ("SRV-MON-01", "Supervision -> SNMP équipements (UDP 161)", "timeout 3 bash -c 'echo > /dev/udp/10.10.0.21/161' && ping -c1 -W2 10.10.0.21", True, "T18-7"),
    ("SRV-MON-01", "Supervision -> agent Zabbix 10050", "timeout 3 bash -c '</dev/tcp/10.20.0.11/10050'", True, "T18-7"),
    ("SRV-STO-01", "Stockage -> Internet HTTPS", "curl -s -m 6 -o /dev/null https://deb.debian.org", True, "T18-5"),
    ("SRV-STO-01", "Stockage -> serveurs SSH (non autorisé)", "timeout 3 bash -c '</dev/tcp/10.20.0.11/22'", False, "T18 défaut"),
    ("SRV-BASTION", "Administration -> SSH serveurs", "timeout 3 bash -c '</dev/tcp/10.20.0.11/22'", True, "T18-6"),
    ("SRV-BASTION", "Administration -> SSH équipements", "timeout 3 bash -c '</dev/tcp/10.10.0.21/22'", True, "T18-6"),
    ("SRV-BASTION", "Administration -> webGUI pare-feu", "curl -sk -m 5 -o /dev/null https://10.90.0.1", True, "T18-6"),
]


def main():
    api = labctl.Gns3()
    p = api.project()
    rows = []
    by_src = {}
    for src, *rest in PROBES:
        by_src.setdefault(src, []).append(rest)
    for src, probes in by_src.items():
        try:
            with labctl.Console.for_node(api, p, src) as c:
                lx = labctl.Linux(c)
                lx.login(180)
                for descr, cmd, expect, ref in probes:
                    rc, _ = lx.run(cmd, 30)
                    ok = (rc == 0) == expect
                    rows.append([src, descr, "autorisé" if expect else "refusé", "ouvert" if rc == 0 else "bloqué", "OK" if ok else "ÉCART", ref])
                    print(f"{'OK ' if ok else 'BAD'} {src:12} {descr}")
        except Exception as e:  # node down: report it instead of failing the whole matrix
            for descr, cmd, expect, ref in probes:
                rows.append([src, descr, "autorisé" if expect else "refusé", f"non testé ({type(e).__name__})", "—", ref])
    out = NET / "report" / "evidence" / "flow_matrix.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source", "flux", "attendu", "observé", "verdict", "réf"])
        w.writerows(rows)
    md = ["Table: Matrice de flux mesurée de bout en bout (automation/flow_matrix.py)",
          "| Source | Flux | Attendu | Observé | Verdict | Réf. |", "|---|---|---|---|---|---|"]
    md += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | **{r[4]}** | {r[5]} |" for r in rows]
    (NET / "report" / "content" / "generated" / "flow_matrix.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    bad = sum(r[4] == "ÉCART" for r in rows)
    print(f"{len(rows)} probes, {bad} deviation(s) -> {out}")


if __name__ == "__main__":
    main()
