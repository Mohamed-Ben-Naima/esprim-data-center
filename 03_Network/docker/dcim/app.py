"""SRV-DCIM-01 – lightweight DCIM / Digital Twin (design report §10.1, §13.1–13.2).

Logical model of the 96 racks (2 halls x 48) with power, inlet temperature, network attachment and A/B PDUs.
The power state of every rack is derived from BMS-SIM (polled every POLL_S seconds):
  path A and B powered -> OK ; one path lost -> DEGRADED (running on the remaining path) ; none -> DOWN.
API: GET /api/racks, /api/racks/<id>, /api/summary ; GET / = NOC-style dashboard.
"""
import json
import os
import random
import socket
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BMS = os.environ.get("BMS_URL", "http://10.70.0.12:8080/api/state")
SYSLOG = (os.environ.get("SYSLOG_HOST", "10.60.0.12"), 514)
POLL_S = float(os.environ.get("POLL_S", "10"))
random.seed(942)

# rack mix per hall (design report §4.3): compute, storage, network, GPU, backup
LAYOUT = (["compute"] * 30 + ["storage"] * 8 + ["network"] * 4 + ["gpu"] * 4 + ["backup"] * 2)
KW = {"compute": 9.0, "storage": 7.5, "network": 4.0, "gpu": 25.0, "backup": 6.0}
racks = {}
for hall in ("A", "B"):
    for i in range(1, 49):
        typ = LAYOUT[i - 1]
        leaf = f"LEAF-{hall}{1 if i <= 24 else 2}"
        rid = f"RACK-{hall}{i:02d}"
        racks[rid] = {"rack_id": rid, "hall": hall, "type": typ,
                      "power_kw": round(KW[typ] * random.uniform(0.85, 1.1), 1),
                      "inlet_temp_c": round(random.uniform(22.0, 25.5), 1),
                      "network": leaf, "pdu_a": f"PDU-A-{hall}{i:02d}", "pdu_b": f"PDU-B-{hall}{i:02d}", "status": "OK"}
bms = {"paths": {"A": "UNKNOWN", "B": "UNKNOWN"}, "status": "UNKNOWN", "alarms": [], "pue": 1.45}
last_status = None
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def syslog(msg, sev=5):
    try:
        sock.sendto(f"<{18 * 8 + sev}>{time.strftime('%b %d %H:%M:%S')} SRV-DCIM-01 dcim: {msg}".encode(), SYSLOG)
    except OSError:
        pass


def poll():
    global last_status
    while True:
        try:
            with urllib.request.urlopen(BMS, timeout=4) as r:
                bms.update(json.loads(r.read()))
        except Exception as e:  # noqa: BLE001
            bms["status"], bms["paths"] = f"BMS UNREACHABLE ({type(e).__name__})", {"A": "UNKNOWN", "B": "UNKNOWN"}
        up = [p for p, v in bms["paths"].items() if v == "POWERED"]
        status = "OK" if len(up) == 2 else "DEGRADED" if up else ("DOWN" if "UNKNOWN" not in bms["paths"].values() else "UNKNOWN")
        for r in racks.values():
            r["status"] = status
            r["inlet_temp_c"] = round(min(32.0, max(20.0, r["inlet_temp_c"] + random.uniform(-0.2, 0.2))), 1)
        if status != last_status:
            syslog(f"rack power status {last_status} -> {status} (paths A={bms['paths']['A']} B={bms['paths']['B']})",
                   2 if status in ("DOWN", "DEGRADED") else 5)
            last_status = status
        time.sleep(POLL_S)


def summary():
    it = sum(r["power_kw"] for r in racks.values())
    by_type, by_status = {}, {}
    for r in racks.values():
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    return {"racks": len(racks), "it_load_kw": round(it, 1), "facility_kw": round(it * bms.get("pue", 1.45), 1),
            "pue": bms.get("pue"), "by_type": by_type, "by_status": by_status, "power_paths": bms["paths"],
            "bms_status": bms["status"], "bms_alarms": bms.get("alarms", []),
            "max_inlet_c": max(r["inlet_temp_c"] for r in racks.values())}


COLOR = {"OK": "#2e7d32", "DEGRADED": "#c77700", "DOWN": "#c62828", "UNKNOWN": "#777"}


def page():
    s = summary()
    cells = []
    for hall in ("A", "B"):
        row = "".join(f'<div class="r" style="background:{COLOR[r["status"]]}" title="{r["rack_id"]} {r["type"]} '
                      f'{r["power_kw"]} kW {r["inlet_temp_c"]} °C {r["network"]}">{r["rack_id"][-3:]}</div>'
                      for r in racks.values() if r["hall"] == hall)
        cells.append(f"<h3>Hall {hall}</h3><div class='g'>{row}</div>")
    al = "".join(f"<li>{a['severity']}: {a['message']}</li>" for a in s["bms_alarms"]) or "<li>Aucune</li>"
    return f"""<!doctype html><html lang=fr><meta charset=utf-8><meta http-equiv=refresh content=10>
<title>DCIM – DC Casablanca</title><style>body{{font-family:Segoe UI,Calibri,sans-serif;margin:24px;background:#f4f6f8}}
.k{{display:inline-block;background:#fff;border:1px solid #d8dde3;border-radius:10px;padding:10px 16px;margin:0 10px 12px 0}}
.k b{{display:block;font-size:20px}}.g{{display:grid;grid-template-columns:repeat(12,1fr);gap:4px;max-width:900px}}
.r{{color:#fff;font-size:11px;text-align:center;padding:6px 0;border-radius:4px}}</style>
<h2>DCIM – Data Center Casablanca (Digital Twin)</h2>
<div class=k>Baies<b>{s['racks']}</b></div><div class=k>Charge IT<b>{s['it_load_kw']} kW</b></div>
<div class=k>PUE<b>{s['pue']}</b></div><div class=k>Chemin A<b>{s['power_paths']['A']}</b></div>
<div class=k>Chemin B<b>{s['power_paths']['B']}</b></div><div class=k>T° entrée max<b>{s['max_inlet_c']} °C</b></div>
{''.join(cells)}<h3>Alarmes GTB</h3><ul>{al}</ul></html>"""


class H(BaseHTTPRequestHandler):
    def _send(self, body, ctype="application/json", code=200):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = self.path.split("?")[0].rstrip("/")
        if p == "/api/summary":
            return self._send(json.dumps(summary(), ensure_ascii=False, indent=1))
        if p == "/api/racks":
            return self._send(json.dumps(list(racks.values()), ensure_ascii=False, indent=1))
        if p.startswith("/api/racks/"):
            r = racks.get(p.rsplit("/", 1)[1].upper())
            return self._send(json.dumps(r, ensure_ascii=False), code=200 if r else 404)
        return self._send(page(), "text/html")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    syslog("DCIM started, 96 racks loaded")
    threading.Thread(target=poll, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), H).serve_forever()
