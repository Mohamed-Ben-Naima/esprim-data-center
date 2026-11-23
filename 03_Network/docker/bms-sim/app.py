"""BMS-SIM – electrical infrastructure simulator (design report §13.3, alarm thresholds Table 22).

State: UTILITY-A, UTILITY-B, UPS-A, UPS-B, GENERATOR (UP/DOWN).
Rule : path X is powered if (UTILITY-X or GENERATOR) and UPS-X.
API  : GET  /api/state                      full state, derived paths, measures, alarms (JSON)
       GET  /api/set?UTILITY-A=DOWN&...     change element states (used by resilience test T6)
       GET  /api/reset                      everything UP
       GET  /metrics                        Prometheus text format
       GET  /                               HTML dashboard
Every state change and alarm transition is sent to the central syslog (SYSLOG_HOST, UDP 514).
"""
import json
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

SYSLOG = (os.environ.get("SYSLOG_HOST", "10.60.0.12"), 514)
IT_LOAD_KW = float(os.environ.get("IT_LOAD_KW", "942"))       # design report §4.4
PATH_CAPACITY_KW = float(os.environ.get("PATH_CAPACITY_KW", "1000"))
UPS_CAPACITY_KW = 1000.0
BATTERY_MIN_AT_FULL = 10.0                                    # autonomy at 100 % UPS load
PUE = 1.45
ELEMENTS = ["UTILITY-A", "UTILITY-B", "UPS-A", "UPS-B", "GENERATOR"]

lock = threading.Lock()
state = {e: "UP" for e in ELEMENTS}
since = {e: time.time() for e in ELEMENTS}
active_alarms = {}
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def syslog(sev, msg):
    pri = 16 * 8 + {"crit": 2, "err": 3, "warning": 4, "notice": 5, "info": 6}[sev]   # facility local0
    line = f"<{pri}>{time.strftime('%b %d %H:%M:%S')} BMS-SIM bms: {msg}"
    try:
        sock.sendto(line.encode(), SYSLOG)
    except OSError:
        pass
    print(line, flush=True)


def evaluate():
    a = (state["UTILITY-A"] == "UP" or state["GENERATOR"] == "UP") and state["UPS-A"] == "UP"
    b = (state["UTILITY-B"] == "UP" or state["GENERATOR"] == "UP") and state["UPS-B"] == "UP"
    on_battery_a = state["UPS-A"] == "UP" and state["UTILITY-A"] == "DOWN" and state["GENERATOR"] == "DOWN"
    on_battery_b = state["UPS-B"] == "UP" and state["UTILITY-B"] == "DOWN" and state["GENERATOR"] == "DOWN"
    a = a or on_battery_a           # UPS keeps the path alive on battery until autonomy runs out
    b = b or on_battery_b
    live = [p for p, ok in (("A", a), ("B", b)) if ok]
    share = IT_LOAD_KW / len(live) if live else 0.0
    load = {p: (share if p in live else 0.0) for p in ("A", "B")}
    pct = {p: round(100 * load[p] / PATH_CAPACITY_KW, 1) for p in load}
    ups_pct = {p: round(100 * load[p] / UPS_CAPACITY_KW, 1) for p in load}
    autonomy = {}
    for p, on_batt in (("A", on_battery_a), ("B", on_battery_b)):
        if on_batt and load[p]:
            autonomy[p] = round(BATTERY_MIN_AT_FULL * UPS_CAPACITY_KW / load[p] * 0.9, 1)
    alarms = {}
    if not live:
        alarms["POWER-LOSS"] = ("crit", "Perte totale d'alimentation IT (chemins A et B hors tension)")
    elif len(live) == 1:
        lost = "A" if "A" not in live else "B"
        alarms[f"PATH-{lost}-LOST"] = ("crit", f"Chemin {lost} hors tension – redondance A/B perdue, chemin {live[0]} seul actif")
    for p in ("A", "B"):
        if pct[p] > 50:
            alarms[f"PATH-{p}-LOAD"] = ("crit", f"Charge chemin {p} {pct[p]} % > 50 % (redondance non assurée)")
        elif pct[p] > 45:
            alarms[f"PATH-{p}-LOAD"] = ("warning", f"Charge chemin {p} {pct[p]} % > 45 %")
        if ups_pct[p] > 85:
            alarms[f"UPS-{p}-LOAD"] = ("crit", f"Charge UPS-{p} {ups_pct[p]} % > 85 %")
        elif ups_pct[p] > 70:
            alarms[f"UPS-{p}-LOAD"] = ("warning", f"Charge UPS-{p} {ups_pct[p]} % > 70 %")
        if p in autonomy:
            sev = "crit" if autonomy[p] < 5 else "warning" if autonomy[p] < 8 else "notice"
            alarms[f"UPS-{p}-BATTERY"] = (sev, f"UPS-{p} sur batterie, autonomie estimée {autonomy[p]} min")
    if state["GENERATOR"] == "DOWN" and (state["UTILITY-A"] == "DOWN" or state["UTILITY-B"] == "DOWN"):
        alarms["GENERATOR"] = ("crit", "Groupe électrogène indisponible pendant une coupure réseau")
    return {
        "elements": dict(state),
        "since": {e: time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(since[e])) for e in ELEMENTS},
        "paths": {"A": "POWERED" if a else "DOWN", "B": "POWERED" if b else "DOWN"},
        "redundancy": "N+N (A/B)" if len(live) == 2 else ("NONE" if live else "LOST"),
        "it_load_kw": IT_LOAD_KW, "facility_kw": round(IT_LOAD_KW * PUE, 1), "pue": PUE,
        "path_load_kw": load, "path_load_pct": pct, "ups_load_pct": ups_pct, "battery_autonomy_min": autonomy,
        "alarms": [{"id": k, "severity": v[0], "message": v[1]} for k, v in sorted(alarms.items())],
        "status": "CRITICAL" if any(v[0] == "crit" for v in alarms.values()) else ("WARNING" if alarms else "OK"),
    }


def refresh_alarms():
    """Emit syslog on alarm raise/clear (monitoring detects T6 within seconds)."""
    s = evaluate()
    now = {a["id"]: a for a in s["alarms"]}
    for k, a in now.items():
        if active_alarms.get(k, {}).get("severity") != a["severity"]:
            syslog(a["severity"], f"ALARM RAISED {k}: {a['message']}")
    for k in list(active_alarms):
        if k not in now:
            syslog("notice", f"ALARM CLEARED {k}")
    active_alarms.clear()
    active_alarms.update(now)
    return s


PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta http-equiv="refresh" content="5">
<title>BMS – DC Casablanca</title><style>
body{font-family:Segoe UI,Calibri,sans-serif;background:#f4f6f8;color:#1f2328;margin:24px}
h1{font-size:20px;margin:0 0 4px}.sub{color:#5b6168;margin-bottom:18px}
.grid{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:16px}
.card{background:#fff;border-radius:10px;padding:12px;border:1px solid #d8dde3}
.UP,.POWERED{color:#2e7d32;font-weight:700}.DOWN{color:#c62828;font-weight:700}
.st{font-size:22px;font-weight:700}.OK{color:#2e7d32}.WARNING{color:#c77700}.CRITICAL{color:#c62828}
table{border-collapse:collapse;width:100%;background:#fff}td,th{border:1px solid #d8dde3;padding:6px 10px;text-align:left}
th{background:#23272e;color:#fff}.crit{color:#c62828}.warning{color:#c77700}.notice{color:#3b6ea8}
</style></head><body><h1>GTB / BMS – Data Center Casablanca</h1><div class="sub">Simulateur des états électriques
(rapport §13.3) – actualisation 5 s</div><div class="grid">%ELEMENTS%</div>
<div class="grid" style="grid-template-columns:repeat(3,1fr)">
<div class="card">État global<div class="st %STATUS%">%STATUS%</div>Redondance : %RED%</div>
<div class="card">Chemin A : <span class="%PA%">%PA%</span><br>charge %LA% %%</div>
<div class="card">Chemin B : <span class="%PB%">%PB%</span><br>charge %LB% %%</div></div>
<table><tr><th>Alarme</th><th>Sévérité</th><th>Message</th></tr>%ALARMS%</table></body></html>"""


def html(s):
    el = "".join(f'<div class="card">{e}<div class="{v}">{v}</div></div>' for e, v in s["elements"].items())
    al = "".join(f'<tr><td>{a["id"]}</td><td class="{a["severity"]}">{a["severity"]}</td><td>{a["message"]}</td></tr>'
                 for a in s["alarms"]) or '<tr><td colspan="3">Aucune alarme</td></tr>'
    return (PAGE.replace("%ELEMENTS%", el).replace("%STATUS%", s["status"]).replace("%RED%", s["redundancy"])
            .replace("%PA%", s["paths"]["A"]).replace("%PB%", s["paths"]["B"])
            .replace("%LA%", str(s["path_load_pct"]["A"])).replace("%LB%", str(s["path_load_pct"]["B"]))
            .replace("%ALARMS%", al).replace("%%", "%"))


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        with lock:
            if u.path == "/api/set":
                changed = []
                for k, v in parse_qs(u.query).items():
                    v = v[0].upper()
                    if k in state and v in ("UP", "DOWN") and state[k] != v:
                        state[k], since[k] = v, time.time()
                        changed.append(f"{k}={v}")
                if changed:
                    syslog("warning", "STATE CHANGE " + " ".join(changed) + f" (source {self.client_address[0]})")
                s = refresh_alarms()
                return self._send(200, json.dumps(s, ensure_ascii=False, indent=1))
            if u.path == "/api/reset":
                for e in ELEMENTS:
                    if state[e] != "UP":
                        state[e], since[e] = "UP", time.time()
                syslog("notice", "STATE RESET all elements UP")
                return self._send(200, json.dumps(refresh_alarms(), ensure_ascii=False, indent=1))
            s = evaluate()
        if u.path == "/api/state":
            return self._send(200, json.dumps(s, ensure_ascii=False, indent=1))
        if u.path == "/metrics":
            lines = [f'bms_element_up{{element="{e}"}} {1 if v == "UP" else 0}' for e, v in s["elements"].items()]
            lines += [f'bms_path_powered{{path="{p}"}} {1 if v == "POWERED" else 0}' for p, v in s["paths"].items()]
            lines += [f'bms_path_load_percent{{path="{p}"}} {v}' for p, v in s["path_load_pct"].items()]
            lines += [f"bms_alarms_active {len(s['alarms'])}", f"bms_pue {s['pue']}"]
            return self._send(200, "\n".join(lines) + "\n", "text/plain")
        if u.path in ("/", "/index.html"):
            return self._send(200, html(s), "text/html")
        return self._send(404, '{"error":"not found"}')

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    syslog("notice", "BMS-SIM started, all elements UP")
    refresh_alarms()
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), H).serve_forever()
