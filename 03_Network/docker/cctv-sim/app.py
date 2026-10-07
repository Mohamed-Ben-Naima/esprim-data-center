"""CCTV-SIM – video surveillance & access-control event generator (design report §9.1–9.2).

Emits realistic events (camera health, motion, badge access granted/denied, mantrap) to the central syslog
so that they can be correlated with the access-control logs, and exposes the camera inventory:
  GET /api/cameras   camera list and status (JSON)
  GET /api/events    last 50 events (JSON)
  GET /              HTML page
"""
import json
import os
import random
import socket
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SYSLOG = (os.environ.get("SYSLOG_HOST", "10.60.0.12"), 514)
PERIOD = float(os.environ.get("EVENT_PERIOD_S", "45"))
CAMERAS = [
    ("CAM-PER-01", "Périmètre nord"), ("CAM-PER-02", "Périmètre sud"), ("CAM-GATE-01", "Portail véhicules"),
    ("CAM-ENT-01", "Accueil / sécurité"), ("CAM-MTR-01", "Sas (mantrap)"), ("CAM-HALLA-01", "Data Hall A – allée froide"),
    ("CAM-HALLA-02", "Data Hall A – allée chaude"), ("CAM-HALLB-01", "Data Hall B – allée froide"),
    ("CAM-HALLB-02", "Data Hall B – allée chaude"), ("CAM-TECH-01", "Salle UPS / TGBT"), ("CAM-NOC-01", "NOC"),
]
DOORS = ["PORTE-ACCUEIL", "SAS-MANTRAP", "DATA-HALL-A", "DATA-HALL-B", "SALLE-ELEC", "NOC"]
USERS = ["tech.ahmed", "tech.salma", "noc.youssef", "ext.maintenance", "inconnu"]
cams = {c: {"location": loc, "status": "ONLINE", "recording": True} for c, loc in CAMERAS}
events = deque(maxlen=50)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def emit(sev, msg):
    pri = 17 * 8 + {"warning": 4, "notice": 5, "info": 6}[sev]       # facility local1
    line = f"<{pri}>{time.strftime('%b %d %H:%M:%S')} CCTV-SIM cctv: {msg}"
    try:
        sock.sendto(line.encode(), SYSLOG)
    except OSError:
        pass
    events.appendleft({"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "severity": sev, "message": msg})


def generator():
    emit("notice", f"CCTV-SIM started, {len(cams)} cameras online")
    while True:
        time.sleep(PERIOD * random.uniform(0.6, 1.4))
        r = random.random()
        if r < 0.45:
            user, door = random.choice(USERS), random.choice(DOORS)
            if user == "inconnu" or (door in ("DATA-HALL-A", "DATA-HALL-B", "SALLE-ELEC") and user == "ext.maintenance"):
                emit("warning", f"ACCESS DENIED badge={user} door={door}")
            else:
                emit("info", f"ACCESS GRANTED badge={user} door={door}")
        elif r < 0.75:
            cam = random.choice(list(cams))
            emit("info", f"MOTION camera={cam} location=\"{cams[cam]['location']}\"")
        elif r < 0.9:
            cam = random.choice(list(cams))
            if cams[cam]["status"] == "ONLINE":
                cams[cam]["status"], cams[cam]["recording"] = "OFFLINE", False
                emit("warning", f"CAMERA OFFLINE camera={cam} location=\"{cams[cam]['location']}\"")
            else:
                cams[cam]["status"], cams[cam]["recording"] = "ONLINE", True
                emit("notice", f"CAMERA ONLINE camera={cam}")
        else:
            emit("warning", "MANTRAP tailgating suspected door=SAS-MANTRAP (two persons detected)")


class H(BaseHTTPRequestHandler):
    def _send(self, body, ctype="application/json"):
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/api/cameras"):
            return self._send(json.dumps(cams, ensure_ascii=False, indent=1))
        if self.path.startswith("/api/events"):
            return self._send(json.dumps(list(events), ensure_ascii=False, indent=1))
        rows = "".join(f"<tr><td>{c}</td><td>{v['location']}</td><td>{v['status']}</td></tr>" for c, v in cams.items())
        ev = "".join(f"<tr><td>{e['time']}</td><td>{e['severity']}</td><td>{e['message']}</td></tr>" for e in events)
        self._send(f"<!doctype html><meta charset=utf-8><title>CCTV – DC Casablanca</title><body style='font-family:Calibri'>"
                   f"<h2>Vidéosurveillance – {sum(v['status'] == 'ONLINE' for v in cams.values())}/{len(cams)} caméras en ligne</h2>"
                   f"<table border=1 cellpadding=4>{rows}</table><h3>Derniers événements</h3><table border=1 cellpadding=4>{ev}</table>",
                   "text/html")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    threading.Thread(target=generator, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), H).serve_forever()
