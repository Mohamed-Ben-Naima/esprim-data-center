"""log_viewer – client of the read-only log viewer of SYSLOG (https://10.60.0.12/, dc/syslog 1.1) and the S5 demo.

  python automation/log_viewer.py search <text> [--src CORE-A] [-n 20] [--arch]   lines of the viewer (newest first),
                                                                         --arch: rotated .gz files too
  python automation/log_viewer.py demo                                   3 demo events, each found in the viewer
  python automation/log_viewer.py lock                                   6 wrong logins from SRV-MON-01 -> locked

Requests go through the lab proxy (ADMIN-WS network namespace, so the viewer sees 10.90.0.12, the admin webterm) and
log in as credentials.admin_user, the way an administrator does from the portal page. The demo:
  1. failed SSH login on CORE-A from ADMIN-WS (wrong password)         -> %SEC_LOGIN-4-LOGIN_FAILED
  2. `configure terminal` / `end` on CORE-A from ADMIN-WS              -> %SYS-5-CONFIG_I ... by netadmin on vty
  3. DMZ host SRV-WEB-01 tries the management network (10.10.0.21:22) -> pfSense filterlog block, rule T18-9
and measures the time until the line is shown by the viewer. Output -> report/evidence/demo_s5_log_viewer.txt.
"""
import base64
import html
import http.client
import re
import ssl
import sys
import time
import urllib.parse
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import gns3vm  # noqa: E402
from adminws import ssh_batch  # noqa: E402
from truenas_setup import socks_connect  # noqa: E402

NET = Path(__file__).resolve().parents[1]
INV = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
HOST = INV["services"]["syslog"]
CTX = ssl.create_default_context()
CTX.check_hostname, CTX.verify_mode = False, ssl.CERT_NONE          # lab self-signed certificate


class Conn(http.client.HTTPSConnection):
    def connect(self):
        self.sock = CTX.wrap_socket(socks_connect(self.host, self.port, self.timeout), server_hostname=self.host)


class Viewer:
    def __init__(self, user=None, password=None):
        c = INV["credentials"]
        self.cookie = ""
        code, _, hdr = self.req("POST", "/login", urllib.parse.urlencode(
            {"user": user or c["admin_user"], "password": password or c["admin_password"]}))
        m = re.search(r"lv=([^;]+)", hdr.get("Set-Cookie", ""))
        if code != 303 or not m:
            raise RuntimeError(f"viewer login refused (HTTP {code})")
        self.cookie = "lv=" + m.group(1)

    def req(self, method, path, body=None):
        con = Conn(HOST, 443, timeout=30, context=CTX)
        try:
            h = {"Content-Type": "application/x-www-form-urlencoded"} if body else {}
            if self.cookie:
                h["Cookie"] = self.cookie
            con.request(method, path, body, h)
            r = con.getresponse()
            return r.status, r.read().decode("utf-8", "replace"), dict(r.getheaders())
        finally:
            con.close()

    def sources(self):
        _, page, _ = self.req("GET", "/")
        return re.findall(r'<option value="([^"]+)"', page)

    def search(self, q, src="all.log", n=50, arch=False):
        if src != "all.log" and not src.endswith(".log"):          # equipment name -> its file (ip_hostname.log)
            ip = (INV["devices"].get(src, {}).get("mgmt") or {}).get("ip") or INV["servers"].get(src, {}).get("ip")
            src = next((f for f in self.sources() if f.startswith(f"{ip}_")), "all.log")
        _, page, _ = self.req("GET", "/?" + urllib.parse.urlencode({"src": src, "q": q, "n": n, "arch": "1" if arch else ""}))
        pre = re.search(r"<pre>(.*?)</pre>", page, re.S).group(1)
        lines = [html.unescape(re.sub(r"</?mark>", "", l)) for l in pre.split("\n")]
        return [l for l in lines if l and l != "(aucune ligne)"]


def askpass(password):
    """Shell lines that put an SSH_ASKPASS helper answering `password` into ADMIN-WS (base64: no quoting issue)."""
    b = base64.b64encode(f"#!/bin/sh\ncat <<'EOP'\n{password}\nEOP\n".encode()).decode()
    return (f"c=$(docker ps -q --filter name=ADMIN-WS)\necho {b} | base64 -d > /tmp/ap_demo.sh; chmod 700 /tmp/ap_demo.sh; "
            "docker cp /tmp/ap_demo.sh $c:/tmp/ap_demo.sh; rm -f /tmp/ap_demo.sh\n")


def failed_login():
    """One SSH login on CORE-A with a wrong password, from the admin webterm (its wrapper logs the session too)."""
    out = gns3vm.run(askpass("not-the-password") + """docker exec -e SSH_ASKPASS=/tmp/ap_demo.sh -e SSH_ASKPASS_REQUIRE=force \
 -e DISPLAY=:0 $c timeout 30 setsid -w ssh -o NumberOfPasswordPrompts=1 -o LogLevel=ERROR core-a 'show clock' 2>&1 | tail -1
echo "@@rc $?"; docker exec $c rm -f /tmp/ap_demo.sh""", sudo=True)
    return out.strip().splitlines()[-2:] if out.strip() else ["(no output)"]


def config_session():
    """configure terminal / end on CORE-A in an interactive SSH session (nothing changed, nothing saved)."""
    out = gns3vm.run(askpass(INV["credentials"]["admin_password"]) + """(sleep 4; printf 'configure terminal\\r\\n'; sleep 2; printf 'end\\r\\n'; sleep 2; \
printf 'exit\\r\\n'; sleep 1) | docker exec -i -e SSH_ASKPASS=/tmp/ap_demo.sh -e SSH_ASKPASS_REQUIRE=force -e DISPLAY=:0 $c \
 timeout 40 setsid -w ssh -tt -o NumberOfPasswordPrompts=1 -o LogLevel=ERROR core-a 2>&1 | tr -d '\\r' | grep -E '#' | tail -3
docker exec $c rm -f /tmp/ap_demo.sh""", sudo=True)
    return out.strip().splitlines()


def firewall_block():
    """SRV-WEB-01 (DMZ) tries SSH on CORE-A's management address: refused and logged by FW-A (rule T18-9)."""
    target = INV["devices"]["CORE-A"]["mgmt"]["ip"]
    out = gns3vm.run(f"w=$(docker ps -q --filter name=GNS3.SRV-WEB-01.); docker exec $w nc -z -w 3 {target} 22; "
                     "echo \"@@rc $?\"")
    return target, out.strip()


def wait_for(v, q, src, before, limit=60):
    t0 = time.time()
    while time.time() - t0 < limit:
        hits = [l for l in v.search(q, src, 20) if l not in before]
        if hits:
            return time.time() - t0, hits
        time.sleep(2)
    return None, []


def demo():
    log, rc = [], 0

    def say(s):
        s = time.strftime("%H:%M:%S ") + s
        print(s, flush=True)
        log.append(s)

    v = Viewer()
    say(f"viewer https://{HOST}/ login {INV['credentials']['admin_user']} from ADMIN-WS: OK, "
        f"{len(v.sources())} sources listed")
    fw_ip = INV["devices"]["FW-A"]["mgmt"]["ip"]
    core_ip = INV["devices"]["CORE-A"]["mgmt"]["ip"]
    steps = [("1. failed SSH login on CORE-A (wrong password, from ADMIN-WS)", failed_login, "LOGIN_FAILED", "CORE-A"),
             ("2. configure terminal / end on CORE-A (from ADMIN-WS)", config_session, "CONFIG_I", "CORE-A"),
             ("3. DMZ SRV-WEB-01 -> CORE-A 10.10.0.21:22 (management network)", firewall_block,
              f"{INV['servers']['SRV-WEB-01']['ip']},{core_ip}", "FW-A")]
    for title, act, q, src in steps:
        before = set(v.search(q, src, 50))
        say(title)
        r = act()
        say(f"   action: {r}")
        took, hits = wait_for(v, q, src, before)
        if hits:
            say(f"   found in the viewer after {took:.1f} s (source {src}, search '{q}'):")
            for h in hits[:3]:
                say("     " + h[:230])
        else:
            say(f"   NOT FOUND in the viewer within 60 s (source {src}, search '{q}')")
            rc = 1
    audit = v.search("logviewer", f"127.0.0.1_syslog.log", 4)
    say("viewer's own audit trail (127.0.0.1 syslog logviewer):")
    for h in audit[:4]:
        say("     " + h[:200])
    out = NET / "report" / "evidence" / "demo_s5_log_viewer.txt"
    out.write_text(f"# PLAN_03 S5 - demo events found in the log viewer https://{HOST}/ ({time.strftime('%d %b %Y')})\n"
                   f"# FW-A = {fw_ip}, CORE-A = {core_ip}; lines: collector time, source ip, hostname, message\n"
                   + "\n".join(log) + "\n", encoding="utf-8")
    print(f"-> {out.relative_to(NET)}")
    return rc


def lock():
    """Brute force on the viewer from SRV-MON-01: the 6th try is refused even before the password is checked."""
    cmd = ("for i in 1 2 3 4 5 6; do curl -sk -m5 -o /dev/null -w '%{http_code} ' -d 'user=netadmin&password=guess'$i "
           f"https://{HOST}/login; done; echo")
    rc, out = ssh_batch([("srv-mon-01", cmd)])[0]
    print(f"6 wrong logins from SRV-MON-01: {out.strip()}  (401 x5 then 429 = locked 5 min)")
    return 0 if out.split()[-1:] == ["429"] else 1


def main(argv):
    if argv[:1] == ["demo"]:
        return demo()
    if argv[:1] == ["lock"]:
        return lock()
    if argv[:1] == ["search"] and len(argv) > 1:
        src = argv[argv.index("--src") + 1] if "--src" in argv else "all.log"
        n = int(argv[argv.index("-n") + 1]) if "-n" in argv else 20
        for line in Viewer().search(argv[1], src, n, "--arch" in argv):
            print(line)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
