"""Access matrix: every equipment is administered from ADMIN-WS and from nowhere else (PLAN_02 ADM.2).

  python automation/access_matrix.py            SSH banner and HTTP probes from three networks
  python automation/access_matrix.py --login    also open a real SSH session on every running equipment from ADMIN-WS

Targets come from the inventory: one SSH target per network device, firewall and server VM (the aliases of the
administration webterm) and every entry of `web_interfaces`. Each target is probed from
  ADMIN-WS    administration zone, VLAN 90   -> must answer
  SRV-INF-01  internal network, VLAN 100     -> must not answer
  SRV-WEB-01  DMZ, VLAN 50                   -> must not answer
except a web interface marked `scope: all` (the public site), which internal networks may reach.
An equipment that is stopped is reported "not running", never as a failure.
Results -> report/evidence/access_matrix.csv and report/content/generated/access_matrix.md. Exit code 1 on a failure.
"""
import csv
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gen_configs as g  # noqa: E402  (inventory + ssh_targets)
import gns3vm  # noqa: E402
import labctl  # noqa: E402

NET = Path(__file__).resolve().parents[1]
SOURCES = [("ADMIN-WS", "docker", "VLAN 90", True), ("SRV-INF-01", "vm", "VLAN 100", False), ("SRV-WEB-01", "docker", "DMZ", False)]
CONTROL = {"SRV-INF-01": 22, "SRV-WEB-01": 80}      # a local port that is open: proves the probe itself works on that source
# p: TCP connect, then the SSH banner (stdin is held open 3 s: a loaded IOSvL2 only answers after a moment)
FUNCS = """p() { if nc -z -w 4 "$2" 22 >/dev/null 2>&1; then r=$(sleep 3 | nc -w 6 "$2" 22 2>/dev/null | head -c 12 | tr -d '\\r\\n');
      echo "R $1 ${r:-open}"; else echo "R $1 none"; fi; }
ctl() { nc -z -w 4 127.0.0.1 "$1" >/dev/null 2>&1 && echo "R control ok" || echo "R control BROKEN"; }
w() { if command -v curl >/dev/null 2>&1; then c=$(curl -sk -m 6 -o /dev/null -w '%{http_code}' "$2");
      else wget -q -T 6 --no-check-certificate -O /dev/null "$2" 2>/dev/null && c=200 || c=000; fi; echo "R $1 $c"; }
"""
LOGIN_CMD = {"cisco": "show version | include uptime", "pfsense": "hostname", "linux": "hostname"}


def targets():
    T = [{"key": f"ssh:{node}", "node": node, "access": "SSH", "address": f"{user}@{ip}", "ip": ip, "alias": alias,
          "family": family, "scope": "admin"} for alias, ip, user, family, node in g.ssh_targets()]
    T += [{"key": f"web:{i}", "node": w["node"], "access": f"Web – {w['name']}", "address": w["url"], "scope": w.get("scope", "admin")}
          for i, w in enumerate(g.INV["web_interfaces"])]
    return T


def probe_script(source, T, running):
    lines = [FUNCS]
    if source in CONTROL:
        lines.append(f"ctl {CONTROL[source]}")
    for t in T:
        if not running.get(t["node"]) or t["node"] == source:
            continue
        lines.append(f"p {t['key']} {t['ip']}" if t["access"] == "SSH" else f"w {t['key']} {t['address']}")
    return "\n".join(lines) + "\n"


def parse(out):
    return {l.split()[1]: l.split()[2] for l in out.splitlines() if l.startswith("R ") and len(l.split()) >= 3}


def run_source(api, p, source, kind, script):
    if kind == "docker":
        return parse(gns3vm.run(f"c=$(docker ps -q --filter name={source})\ndocker exec -i $c sh <<'EOS'\n{script}EOS\n", sudo=True))
    with labctl.Console.for_node(api, p, source) as c:
        lx = labctl.Linux(c)
        lx.login()
        lx.put_file("/tmp/access_probe.sh", script)
        _, out = lx.run("sh /tmp/access_probe.sh; rm -f /tmp/access_probe.sh", 400)
    return parse(out)


def logins(T, running):
    cred = g.C
    pw = {"cisco": cred["admin_password"], "pfsense": cred["admin_password"], "linux": cred["server_password"]}
    assert all("'" not in v for v in pw.values())
    s = ["c=$(docker ps -q --filter name=ADMIN-WS)"]
    for fam, v in pw.items():
        s.append(f"docker exec $c sh -c 'umask 077; printf \"#!/bin/sh\\necho %s\\n\" \"$1\" > /tmp/ap_{fam}.sh; chmod 700 /tmp/ap_{fam}.sh' _ '{v}'")
    for t in T:
        if t["access"] == "SSH" and running.get(t["node"]):
            s.append(f"out=$(docker exec -e SSH_ASKPASS=/tmp/ap_{t['family']}.sh -e SSH_ASKPASS_REQUIRE=force -e DISPLAY=:0 $c "
                     f"timeout 45 setsid -w ssh -o NumberOfPasswordPrompts=1 {t['alias']} '{LOGIN_CMD[t['family']]}' 2>/dev/null); rc=$?\n"
                     f"echo \"L {t['key']} $rc $(echo \"$out\" | tr -d '\\r' | grep -v '^[*]' | grep -v '^$' | tail -1)\"")
    s.append("docker exec $c sh -c 'rm -f /tmp/ap_*.sh'")
    out = gns3vm.run("\n".join(s), sudo=True)
    res = {}
    for l in out.splitlines():
        if l.startswith("L "):
            _, key, rc, *rest = l.split(" ", 3)
            res[key] = (rc == "0" and bool(rest), " ".join(rest))
    return res


def answered(t, value):
    if value is None:
        return None
    return value != "none" if t["access"] == "SSH" else value != "000"


def main(argv):
    api = labctl.Gns3()
    p = api.project()
    running = {n["name"]: n["status"] == "started" for n in api.nodes(p)}
    T = targets()
    res = {}
    for source, kind, _, _ in SOURCES:
        res[source] = run_source(api, p, source, kind, probe_script(source, T, running)) if running.get(source) else None
    login = logins(T, running) if "--login" in argv and running.get("ADMIN-WS") else {}
    rows, fails = [], 0
    for t in T:
        row = {"equipment": t["node"], "access": t["access"], "address": t["address"]}
        if not running.get(t["node"]):
            row.update({s: "–" for s, *_ in SOURCES}, login="–", verdict="not running")
            rows.append(row)
            continue
        ok = True
        for source, _, _, admin in SOURCES:
            if res[source] is None:
                row[source] = "source off"
            elif source in CONTROL and res[source].get("control") != "ok":
                row[source] = "probe broken"
                ok = False
            elif t["node"] == source:
                row[source] = "itself"
            else:
                got = answered(t, res[source].get(t["key"]))
                want = admin or t["scope"] == "all"
                row[source] = ("reachable" if got else "refused") + ("" if got == want else " (UNEXPECTED)")
                ok &= got == want
        if t["key"] in login:
            good, text = login[t["key"]]
            row["login"] = text[:60] if good else "LOGIN FAILED"
            ok &= good
        else:
            row["login"] = "–" if t["access"] != "SSH" else "not tested"
        row["verdict"] = "OK" if ok else "FAIL"
        fails += not ok
        rows.append(row)
    cols = ["equipment", "access", "address"] + [s for s, *_ in SOURCES] + ["login", "verdict"]
    with open(NET / "report" / "evidence" / "access_matrix.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    fr = {"reachable": "joignable", "refused": "refusé", "itself": "lui-même", "source off": "source arrêtée", "not running": "arrêté",
          "not tested": "non testée", "probe broken": "sonde en défaut", "LOGIN FAILED": "ÉCHEC", "OK": "Conforme", "FAIL": "**Non conforme**"}
    tr = lambda v: " ".join(fr.get(x, x) for x in [v.replace(" (UNEXPECTED)", "")]) + (" (inattendu)" if "UNEXPECTED" in v else "")
    md = [f"Table: Matrice d'accès d'administration (générée par `automation/access_matrix.py` le {datetime.date.today():%d/%m/%Y})",
          "| Équipement | Accès | Adresse | Depuis ADMIN-WS (VLAN 90) | Depuis SRV-INF-01 (VLAN 100) | Depuis SRV-WEB-01 (DMZ) | Session SSH | Verdict |",
          "|---|---|---|---|---|---|---|---|"]
    md += ["| " + " | ".join([r["equipment"], r["access"], f"`{r['address']}`"] + [tr(r[s]) for s, *_ in SOURCES]
                            + [fr.get(r["login"], r["login"]).replace("|", "/"), fr.get(r["verdict"], r["verdict"])]) + " |" for r in rows]
    (NET / "report" / "content" / "generated" / "access_matrix.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    width = max(len(r["access"]) for r in rows)
    for r in rows:
        print(f"{r['equipment']:12} {r['access']:{width}}  " + "  ".join(f"{r[s]:24}" for s, *_ in SOURCES) + f" {r['login'][:34]:34} {r['verdict']}")
    done = [r for r in rows if r["verdict"] != "not running"]
    print(f"\n{len(done)} target(s) tested, {fails} failure(s), {len(rows) - len(done)} not running")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
