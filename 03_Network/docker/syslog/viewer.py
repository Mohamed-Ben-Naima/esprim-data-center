"""Read-only web viewer of the central syslog (dc/syslog 1.1, ISO/IEC 27001 A.8.15 protection of log information).

Standard library only. HTTPS (TLS >= 1.2, self-signed certificate made at container start), login form, sessions
closed after 15 min idle, 5 failed logins from one address -> locked 5 min. The process binds its port as root, then
runs as the account `viewer` (group logread): log files are 0640 root:logread in a 0750 directory, so the viewer can
read them and can neither change nor delete them. There is no write path in the code either: GET pages + POST /login.
Every login and every search is itself sent to the collector (tag logviewer) - who looked at what stays traceable.

Environment:  VIEWER_AUTH   user:pbkdf2_sha256$<iterations>$<salt hex>$<hash hex>[,user2:...]
              VIEWER_NAMES  10.10.0.21=CORE-A,...   (display names of the sources)
              VIEWER_PORT   443     LOG_DIR /var/log/remote     LOG_RETENTION_DAYS 30
"""
import collections
import gzip
import hashlib
import hmac
import html
import os
import pwd
import re
import secrets
import socket
import ssl
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG_DIR = os.environ.get("LOG_DIR", "/var/log/remote")
PORT = int(os.environ.get("VIEWER_PORT", "443"))
RETENTION = os.environ.get("LOG_RETENTION_DAYS", "30")
IDLE = 15 * 60
LOCK_AFTER, LOCK_FOR = 5, 300
MAX_LINES = 2000
FILE_RX = re.compile(r"^[\w.\-]+\.log$")
USERS = {}
for entry in filter(None, os.environ.get("VIEWER_AUTH", "").split(",")):
    u, _, h = entry.partition(":")
    USERS[u.strip()] = h.strip()
NAMES = dict(x.split("=", 1) for x in filter(None, os.environ.get("VIEWER_NAMES", "").split(",")) if "=" in x)
SESSIONS = {}          # token -> [user, last seen, client ip]
FAILS = {}             # client ip -> [count, locked until]


def audit(msg):
    """Send one line to the collector itself (local0.info, tag logviewer)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(f"<134>{time.strftime('%b %d %H:%M:%S')} syslog logviewer: {msg}".encode()[:1000], ("127.0.0.1", 514))
        s.close()
    except OSError:
        pass


def check_password(user, password):
    h = USERS.get(user)
    try:
        algo, it, salt, want = h.split("$")
        got = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(it)).hex()
        return algo == "pbkdf2_sha256" and hmac.compare_digest(got, want)
    except (AttributeError, ValueError):
        hashlib.pbkdf2_hmac("sha256", password.encode(), b"x" * 16, 200000)   # same time for unknown users
        return False


def sources():
    """[(file, label, size, mtime)] of the current files, all.log first."""
    out = []
    for f in os.listdir(LOG_DIR):
        if FILE_RX.match(f):
            st = os.stat(os.path.join(LOG_DIR, f))
            ip, _, host = f[:-4].partition("_")
            label = "toutes sources" if f == "all.log" else f"{NAMES.get(ip, host or ip)} ({ip})"
            out.append((f, label, st.st_size, st.st_mtime))
    return sorted(out, key=lambda x: (x[0] != "all.log", x[1].lower()))


def archives(name):
    """Rotated copies of name (logrotate dateext: name-YYYYMMDD[.gz]), oldest first."""
    rx = re.compile(re.escape(name) + r"-\d{8}(\.gz)?$")
    return sorted(f for f in os.listdir(LOG_DIR) if rx.match(f))


def lines_of(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            yield line.rstrip("\n")


def tail(path, n):
    """Last n lines of a plain file without reading all of it."""
    with open(path, "rb") as fh:
        fh.seek(0, 2)
        end, buf = fh.tell(), b""
        while end > 0 and buf.count(b"\n") <= n:
            step = min(65536, end)
            end -= step
            fh.seek(end)
            buf = fh.read(step) + buf
    return [l.decode("utf-8", "replace") for l in buf.splitlines()[-n:]]


def search(name, q, n, with_archives):
    path = os.path.join(LOG_DIR, name)
    files = ([os.path.join(LOG_DIR, a) for a in archives(name)] if with_archives else []) + [path]
    if not q and not with_archives:
        return tail(path, n), 1
    keep, ql = collections.deque(maxlen=n), q.lower()
    for f in files:
        for line in lines_of(f):
            if ql in line.lower():
                keep.append(line)
    return list(keep), len(files)


CSS = """body{font:14px system-ui,sans-serif;margin:0;background:#f4f5f7;color:#1d2330}
header{background:#1d2330;color:#fff;padding:10px 16px;display:flex;justify-content:space-between;align-items:center}
header a{color:#cfd6e4}main{padding:16px}form.q{display:flex;flex-wrap:wrap;gap:8px;align-items:end;margin-bottom:12px}
label{display:flex;flex-direction:column;font-size:12px;color:#555}input,select,button{font:inherit;padding:5px 7px}
pre{background:#fff;border:1px solid #d5d9e0;padding:8px;overflow-x:auto;font:12px ui-monospace,Consolas,monospace;
line-height:1.45;margin:0}mark{background:#ffe066}.meta{color:#555;font-size:12px;margin:6px 0}
table{border-collapse:collapse;background:#fff;font-size:12px}td,th{border:1px solid #d5d9e0;padding:3px 8px;text-align:left}
.old{color:#a33}.box{max-width:340px;margin:12vh auto;background:#fff;padding:24px;border:1px solid #d5d9e0}
.err{color:#a33}"""


def page(title, body, refresh_url=""):
    meta = f'<meta http-equiv="refresh" content="5;url={html.escape(refresh_url)}">' if refresh_url else ""
    return (f'<!doctype html><html lang="fr"><head><meta charset="utf-8">{meta}<title>{html.escape(title)}</title>'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><style>{CSS}</style></head>'
            f"<body>{body}</body></html>")


def human(n):
    for unit in ("o", "Ko", "Mo", "Go"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} To"


class Handler(BaseHTTPRequestHandler):
    server_version = "dc-logviewer/1.1"
    sys_version = ""

    def log_message(self, fmt, *args):
        pass

    def send(self, code, body, ctype="text/html; charset=utf-8", headers=()):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Strict-Transport-Security", "max-age=31536000")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'")
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, where, headers=()):
        self.send_response(303)
        self.send_header("Location", where)
        self.send_header("Content-Length", "0")
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()

    def session(self):
        for part in self.headers.get("Cookie", "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == "lv" and v in SESSIONS:
                s = SESSIONS[v]
                if time.time() - s[1] < IDLE and s[2] == self.client_address[0]:
                    s[1] = time.time()
                    return v, s[0]
                SESSIONS.pop(v, None)
        return None, None

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        if url.path == "/health":
            return self.send(200, "OK logviewer\n", "text/plain; charset=utf-8")
        if url.path == "/login":
            return self.send(200, self.login_form())
        token, user = self.session()
        if not user:
            return self.redirect("/login")
        if url.path == "/logout":
            SESSIONS.pop(token, None)
            audit(f"logout user={user} from={self.client_address[0]}")
            return self.redirect("/login", [("Set-Cookie", "lv=; Max-Age=0; Path=/; Secure; HttpOnly; SameSite=Strict")])
        if url.path == "/":
            return self.send(200, self.main(user, urllib.parse.parse_qs(url.query)))
        self.send(404, page("404", "<main>Page inconnue.</main>"))

    def do_POST(self):
        if urllib.parse.urlsplit(self.path).path != "/login":
            return self.send(405, page("405", "<main>Lecture seule.</main>"), headers=[("Allow", "GET")])
        ip = self.client_address[0]
        f = FAILS.get(ip, [0, 0])
        if f[1] > time.time():
            audit(f"login refused (locked) from={ip}")
            return self.send(429, self.login_form("Trop d'échecs : réessayez dans 5 minutes."))
        length = min(int(self.headers.get("Content-Length", "0") or 0), 4096)
        form = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
        user, password = form.get("user", [""])[0][:64], form.get("password", [""])[0][:256]
        if check_password(user, password):
            FAILS.pop(ip, None)
            token = secrets.token_urlsafe(32)
            SESSIONS[token] = [user, time.time(), ip]
            audit(f"login ok user={user} from={ip}")
            return self.redirect("/", [("Set-Cookie", f"lv={token}; Path=/; Secure; HttpOnly; SameSite=Strict")])
        f[0] += 1
        if f[0] >= LOCK_AFTER:
            f = [0, time.time() + LOCK_FOR]
        FAILS[ip] = f
        audit(f"login failed user={user!r} from={ip}")
        self.send(401, self.login_form("Identifiant ou mot de passe incorrect."))

    def login_form(self, err=""):
        e = f'<p class="err">{html.escape(err)}</p>' if err else ""
        return page("Journaux - connexion", f"""<div class="box"><h2>Journaux centralisés</h2>
<p class="meta">Collecteur syslog SYSLOG (10.60.0.12) – accès en lecture seule, ISO 27001 A.8.15.</p>{e}
<form method="post" action="/login"><label>Identifiant<input name="user" autocomplete="username" required></label><br>
<label>Mot de passe<input name="password" type="password" autocomplete="current-password" required></label><br>
<button>Se connecter</button></form></div>""")

    def main(self, user, qs):
        srcs = sources()
        names = [s[0] for s in srcs]
        src = qs.get("src", ["all.log"])[0]
        src = src if src in names else "all.log"
        q = qs.get("q", [""])[0][:200]
        try:
            n = max(10, min(MAX_LINES, int(qs.get("n", ["200"])[0])))
        except ValueError:
            n = 200
        arch = qs.get("arch", [""])[0] == "1"
        follow = qs.get("follow", [""])[0] == "1"
        t0 = time.time()
        lines, nfiles = search(src, q, n, arch)
        took = time.time() - t0
        if not follow:
            audit(f"search user={user} from={self.client_address[0]} src={src} q={q!r} lines={len(lines)}")
        opts = "".join(f'<option value="{html.escape(f)}"{" selected" if f == src else ""}>{html.escape(lbl)}</option>'
                       for f, lbl, _, _ in srcs)
        rx = re.compile(re.escape(html.escape(q)), re.I) if q else None
        shown = []
        for line in reversed(lines):
            e = html.escape(line)
            shown.append(rx.sub(lambda m: f"<mark>{m.group(0)}</mark>", e) if rx else e)
        vfs = os.statvfs(LOG_DIR)
        total = sum(os.path.getsize(os.path.join(LOG_DIR, f)) for f in os.listdir(LOG_DIR)
                    if os.path.isfile(os.path.join(LOG_DIR, f)))
        now = time.time()
        rows = "".join(
            f'<tr><td>{html.escape(lbl)}</td><td>{human(sz)}</td>'
            f'<td{" class=old" if now - mt > 600 else ""}>{int((now - mt) // 60)} min</td></tr>'
            for f, lbl, sz, mt in srcs)
        self_url = "/?" + urllib.parse.urlencode({"src": src, "q": q, "n": n, "arch": "1" if arch else "",
                                                  "follow": "1"})
        return page("Journaux centralisés", f"""<header><b>Journaux centralisés – SYSLOG 10.60.0.12</b>
<span>{html.escape(user)} · <a href="/logout">déconnexion</a></span></header><main>
<form class="q" method="get" action="/"><label>Source<select name="src">{opts}</select></label>
<label>Texte cherché<input name="q" value="{html.escape(q)}" placeholder="ex. LOGIN_FAILED"></label>
<label>Lignes<input name="n" type="number" min="10" max="{MAX_LINES}" value="{n}" style="width:6em"></label>
<label><span><input type="checkbox" name="arch" value="1"{" checked" if arch else ""}> archives</span></label>
<label><span><input type="checkbox" name="follow" value="1"{" checked" if follow else ""}> suivre (5 s)</span></label>
<button>Afficher</button></form>
<p class="meta">{len(lines)} ligne(s), plus récentes en haut · {nfiles} fichier(s) lu(s) en {took:.2f} s ·
volume {human(total)}, libre {human(vfs.f_bavail * vfs.f_frsize)} · rétention {html.escape(RETENTION)} jours ·
heure du collecteur {time.strftime('%Y-%m-%d %H:%M:%S %z')}</p>
<pre>{chr(10).join(shown) or "(aucune ligne)"}</pre>
<h3>Sources</h3><table><tr><th>Source</th><th>Taille</th><th>Dernière ligne</th></tr>{rows}</table>
</main>""", self_url if follow else "")


def main():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain("/var/lib/viewer/cert.pem", "/var/lib/viewer/key.pem")
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True, do_handshake_on_connect=False)  # handshake in the thread
    if os.getuid() == 0:                       # port bound, key loaded: drop root for good
        pw = pwd.getpwnam("viewer")
        os.setgroups([pw.pw_gid])
        os.setgid(pw.pw_gid)
        os.setuid(pw.pw_uid)
    if not USERS:
        print("viewer: VIEWER_AUTH empty, nobody can log in", file=sys.stderr)
    audit(f"viewer started on :{PORT} uid={os.getuid()} users={','.join(sorted(USERS))}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
