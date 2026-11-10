"""check_dashboard – check every panel of the Grafana NOC dashboard against live data (PLAN_03 S4).

  python automation/check_dashboard.py              # dashboard as deployed in Grafana (uid dc-noc)
  python automation/check_dashboard.py --local      # grafana/dashboards/noc.json (before deploying it)

Each panel's queries are sent to Grafana's query API (/api/ds/query, the path the browser uses, through the lab proxy)
and the answer is reduced to "series with values / last value". Problem panels are checked against Zabbix
(problem.get without maintenance and suppressed problems, enabled triggers). A panel is reported:
  DATA        at least one series with a value (last values shown)
  HORS PROFIL no value, and every host it names is stopped in the running profile (the panel shows "hors profil")
  EMPTY       no value although a host it names runs -> to fix
Exit code 1 when a panel is EMPTY or the deployed dashboard differs from grafana/dashboards/noc.json.
"""
import base64
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import labctl  # noqa: E402
import zabbix_setup as zs  # noqa: E402

NET = Path(__file__).resolve().parents[1]
INV = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
GRAFANA = ("10.60.0.11", 3000)
AUTH = "Basic " + base64.b64encode(f"admin:{INV['credentials']['grafana_admin_password']}".encode()).decode()


def grafana(method, path, body=None):
    con = zs.SocksHTTPConnection(*GRAFANA, timeout=60)
    try:
        con.request(method, path, json.dumps(body) if body is not None else None,
                    {"Authorization": AUTH, "Content-Type": "application/json"})
        r = con.getresponse()
        data = r.read()
        if r.status >= 300:
            raise RuntimeError(f"Grafana {method} {path}: HTTP {r.status} {data[:300]!r}")
        return json.loads(data or b"{}")
    finally:
        con.close()


def hosts_named(panel):
    """Host names a panel's queries select (plain name or /regex/ over the inventory names)."""
    names = set(INV["devices"]) | set(INV["servers"])
    out = set()
    for t in panel.get("targets", []):
        f = t.get("host", {}).get("filter", "")
        if f.startswith("/") and f.endswith("/"):
            rx = re.compile(f[1:-1])
            out |= {n for n in names if rx.search(n)}
        elif f:
            out.add(f)
    return out


def last_values(answer):
    vals = []
    for res in answer.get("results", {}).values():
        if res.get("error"):
            raise RuntimeError(res["error"])
        for fr in res.get("frames", []):
            fields = fr["schema"]["fields"]
            cols = fr["data"]["values"]
            for i, f in enumerate(fields):
                if f.get("type") == "time" or i >= len(cols):
                    continue
                col = [v for v in cols[i] if v is not None]
                if col:
                    name = (f.get("config") or {}).get("displayNameFromDS") or f.get("name") or "?"
                    labels = f.get("labels") or {}
                    tag = labels.get("host") or labels.get("item") or name
                    vals.append((str(tag)[:28], col[-1]))
    return vals


_Z = None


def zabbix():
    global _Z
    if _Z is None:
        _Z = zs.Zabbix()
        zs.login(_Z)
    return _Z


def text_values(target):
    """Text queries run in the browser (the plugin backend refuses them): read the same item from Zabbix."""
    import time
    items = zabbix().call("item.get", {"output": ["name", "lastvalue", "lastclock"], "host": target["host"]["filter"],
                                       "filter": {"name": target["item"]["filter"]}})
    return [(target["host"]["filter"], i["lastvalue"]) for i in items if int(i["lastclock"]) > time.time() - 1800]


def zabbix_problems():
    z = zabbix()
    trg = z.call("trigger.get", {"output": ["description", "priority"], "only_true": True, "monitored": True,
                                 "skipDependent": True, "maintenance": False, "filter": {"value": 1},
                                 "selectHosts": ["host"], "selectLastEvent": ["suppressed"]})
    return [f"{t['hosts'][0]['host']}: {t['description']}" for t in trg
            if not (t.get("lastEvent") or {}).get("suppressed") == "1"]


def main(argv):
    local = json.loads((NET / "grafana" / "dashboards" / "noc.json").read_text(encoding="utf-8"))
    dash, rc = local, 0
    if "--local" not in argv:
        dash = grafana("GET", "/api/dashboards/uid/dc-noc")["dashboard"]
        same = [p["title"] for p in dash["panels"]] == [p["title"] for p in local["panels"]]
        print(f"deployed dashboard '{dash['title']}' version {dash.get('version')}: "
              f"{'same panels as noc.json' if same else 'DIFFERENT from noc.json (deploy it)'}")
        rc |= 0 if same else 1
    api = labctl.Gns3()
    p = api.project()
    running = {n["name"] for n in api.nodes(p) if n["status"] == "started"}
    counts = {"DATA": 0, "HORS PROFIL": 0, "EMPTY": 0}
    section = ""
    for pan in dash["panels"]:
        if pan["type"] == "row":
            section = pan["title"]
            print(f"== {section}")
            continue
        if pan["type"].endswith("triggers-panel"):
            probs = zabbix_problems()
            state = "DATA"
            print(f"   {'DATA':11} {pan['title']}: {len(probs)} problem(s) "
                  f"{'; '.join(probs[:4])}{' ...' if len(probs) > 4 else ''}")
            counts[state] += 1
            continue
        queries = [dict(t, intervalMs=10000, maxDataPoints=500) for t in pan["targets"] if t.get("queryType") != "2"]
        vals, err = [v for t in pan["targets"] if t.get("queryType") == "2" for v in text_values(t)], ""
        if queries:
            try:
                vals += last_values(grafana("POST", "/api/ds/query",
                                            {"queries": queries, "from": "now-30m", "to": "now"}))
            except RuntimeError as e:
                err = str(e)[:120]
        named = hosts_named(pan)
        if vals:
            state = "DATA"
        elif named and not (named & running):
            state = "HORS PROFIL"
        else:
            state = "EMPTY"
            rc = 1
        counts[state] += 1
        shown = ", ".join(f"{k}={round(v, 2) if isinstance(v, float) else v}" for k, v in vals[:6])
        print(f"   {state:11} {pan['title']}: {shown or err or '(no value)'}"
              + (f"  [stopped: {', '.join(sorted(named - running))}]" if named - running else ""))
    print(f"panels: {counts['DATA']} with data, {counts['HORS PROFIL']} hors profil, {counts['EMPTY']} empty")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
