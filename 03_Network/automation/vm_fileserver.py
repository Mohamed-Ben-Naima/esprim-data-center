"""Tiny lab file server run inside the GNS3 VM (python3, stdlib) – config exchange with pfSense.

Listens on 0.0.0.0:8000 (reachable from the lab through ISP -> NAT -> virbr0 192.168.42.1).
  GET  /<name>   download /opt/gns3/labfiles/<name>      (generated config.xml -> pfSense)
  PUT  /<name>   upload   to /opt/gns3/labfiles/<name>   (pfSense baseline config.xml -> repo)
Lab-only helper: no authentication, file names restricted to [A-Za-z0-9._-].
"""
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = "/opt/gns3/labfiles"
os.makedirs(ROOT, exist_ok=True)
SAFE = re.compile(r"^/([A-Za-z0-9._-]{1,80})$")


class H(BaseHTTPRequestHandler):
    def _path(self):
        m = SAFE.match(self.path.split("?")[0])
        return os.path.join(ROOT, m.group(1)) if m else None

    def do_GET(self):
        p = self._path()
        if not p or not os.path.isfile(p):
            self.send_response(404); self.end_headers(); return
        data = open(p, "rb").read()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_PUT(self):
        p = self._path()
        n = int(self.headers.get("Content-Length", 0))
        if not p or n > 20_000_000:
            self.send_response(400); self.end_headers(); return
        with open(p, "wb") as f:
            f.write(self.rfile.read(n))
        self.send_response(201); self.end_headers()
        self.wfile.write(b"stored\n")

    do_POST = do_PUT


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), H).serve_forever()
