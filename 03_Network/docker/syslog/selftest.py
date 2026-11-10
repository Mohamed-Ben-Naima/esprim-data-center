"""Self-test of dc/syslog 1.1 inside a throw-away container (build_images.py smoke). Prints SELFTEST-OK when all pass.
Needs VIEWER_AUTH for user `selftest` / password `selftest`."""
import http.cookiejar
import os
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

B = "https://127.0.0.1:%s" % os.environ.get("VIEWER_PORT", "443")
ctx = ssl.create_default_context()
ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
op = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),
                                 urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
bad = []


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name} {info}")
    if not ok:
        bad.append(name)


def req(path, data=None, method=None):
    r = urllib.request.Request(B + path, data=data, method=method)
    try:
        with op.open(r, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


for _ in range(20):
    try:
        if req("/health")[0] == 200:
            break
    except OSError:
        time.sleep(0.5)
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.sendto(b"<14>Nov 10 10:00:00 testhost selftest: SELFTEST-MARK <script>", ("127.0.0.1", 514))
time.sleep(1.5)
check("health", req("/health") == (200, "OK logviewer\n"))
check("anonymous page refused", "Mot de passe" in req("/")[1])
with ctx.wrap_socket(socket.create_connection(("127.0.0.1", int(B.rsplit(":", 1)[1]))), server_hostname="x") as t:
    check("TLS >= 1.2", t.version() in ("TLSv1.2", "TLSv1.3"), t.version())
code, body = req("/login", urllib.parse.urlencode({"user": "selftest", "password": "wrong"}).encode())
check("wrong password -> 401", code == 401, str(code))
code, body = req("/login", urllib.parse.urlencode({"user": "selftest", "password": "selftest"}).encode())
check("login", code == 200 and "déconnexion" in body, str(code))
code, body = req("/?src=all.log&q=SELFTEST-MARK&n=50")
check("search finds the test line", "<mark>SELFTEST-MARK</mark>" in body)
check("HTML escaped", "&lt;script&gt;" in body and "<script>" not in body)
check("PUT refused", req("/", b"x", "PUT")[0] in (405, 501))
check("POST elsewhere refused", req("/", b"x")[0] == 405)
check("path traversal ignored", "toutes sources" in req("/?src=../../etc/passwd")[1])
uids = []
for pid in filter(str.isdigit, os.listdir("/proc")):
    try:
        cmd = open(f"/proc/{pid}/cmdline", "rb").read()
        if b"viewer.py" in cmd and cmd.startswith(b"python3"):
            uids.append(next(l.split()[1] for l in open(f"/proc/{pid}/status") if l.startswith("Uid:")))
    except OSError:
        pass
check("viewer not running as root", uids and "0" not in uids, str(uids))
d = os.stat("/var/log/remote")
check("directory 0750 root:logread", oct(d.st_mode & 0o777) == "0o750", oct(d.st_mode & 0o777))
f = os.stat("/var/log/remote/all.log")
check("files 0640", oct(f.st_mode & 0o777) == "0o640", oct(f.st_mode & 0o777))
w = subprocess.run(["su", "-s", "/bin/sh", "viewer", "-c", "echo x >> /var/log/remote/all.log"], capture_output=True)
check("viewer account cannot write", w.returncode != 0, str(w.returncode))
subprocess.run(["su", "-s", "/bin/sh", "viewer", "-c", "rm -f /var/log/remote/all.log"], capture_output=True)
check("viewer account cannot delete", os.path.exists("/var/log/remote/all.log"))
lr = subprocess.run(["logrotate", "-d", "/etc/logrotate.d/remote"], capture_output=True, text=True)
check("logrotate config valid", lr.returncode == 0 and "rotating pattern" in (lr.stdout + lr.stderr))
time.sleep(1)
check("viewer actions logged", "login ok user=selftest" in open("/var/log/remote/all.log").read())
print("SELFTEST-OK" if not bad else f"SELFTEST-FAILED {bad}")
sys.exit(1 if bad else 0)
