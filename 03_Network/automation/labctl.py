"""labctl – drive the DC Casablanca GNS3 lab: GNS3 controller API + device consoles.

Library
  api = Gns3()                          # local controller, creds from %APPDATA%/GNS3/<ver>/gns3_server.ini
  p = api.project("DC_Casablanca_TIA942_R3"); api.open(p)
  n = api.node(p, "EDGE-A"); api.start(p, n)
  with Console.for_node(api, p, "EDGE-A") as c:      # raw telnet (Python 3.14 has no telnetlib)
      ios = Ios(c); ios.login(); print(ios.cmd("show ip int brief"))
      ios.push_config(Path("configs/EDGE-A.cfg").read_text())

CLI
  python automation/labctl.py status
  python automation/labctl.py start  EDGE-A EDGE-B      | stop NODE... | reload NODE...
  python automation/labctl.py show   EDGE-A "show ip bgp summary" [--save]
  python automation/labctl.py push   EDGE-A             (configs/EDGE-A.cfg -> running + startup)
"""
import base64
import configparser
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

NET = Path(__file__).resolve().parents[1]
EVIDENCE = NET / "report" / "evidence"
PROJECT = "DC_Casablanca_TIA942_R3"


# =========================================================================================== GNS3 API
class Gns3:
    def __init__(self):
        root = Path(os.environ["APPDATA"]) / "GNS3"
        ini = sorted(root.glob("*/gns3_server.ini"))[-1]
        cp = configparser.ConfigParser(interpolation=None)
        cp.read(ini, encoding="utf-8")
        s = cp["Server"]
        host = s.get("host", "localhost")
        self.base = f"http://{'127.0.0.1' if host in ('0.0.0.0', 'localhost') else host}:{s.get('port', '3080')}/v2"
        self.auth = None
        if s.get("auth", "False") == "True":
            self.auth = "Basic " + base64.b64encode(f"{s['user']}:{s['password']}".encode()).decode()
        self._projects = {}

    def req(self, method, path, body=None, timeout=300):
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(self.base + path, data=data, method=method)
        r.add_header("Content-Type", "application/json")
        if self.auth:
            r.add_header("Authorization", self.auth)
        try:
            with urllib.request.urlopen(r, timeout=timeout) as resp:
                raw = resp.read()
                return json.loads(raw) if raw and resp.headers.get_content_type() == "application/json" else raw
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{method} {path} -> {e.code}: {e.read()[:400]!r}") from None

    # projects
    def project(self, name=PROJECT):
        for p in self.req("GET", "/projects"):
            if p["name"] == name:
                return p
        raise KeyError(name)

    def open(self, p):
        if p["status"] != "opened":
            self.req("POST", f"/projects/{p['project_id']}/open", {})
            p["status"] = "opened"
        return p

    # nodes
    def nodes(self, p):
        return self.req("GET", f"/projects/{p['project_id']}/nodes")

    def node(self, p, name):
        for n in self.nodes(p):
            if n["name"] == name:
                return n
        raise KeyError(name)

    def start(self, p, n):
        return self.req("POST", f"/projects/{p['project_id']}/nodes/{n['node_id']}/start", {})

    def stop(self, p, n):
        return self.req("POST", f"/projects/{p['project_id']}/nodes/{n['node_id']}/stop", {})

    def reload(self, p, n):
        return self.req("POST", f"/projects/{p['project_id']}/nodes/{n['node_id']}/reload", {})

    def update_node(self, p, n, body):
        return self.req("PUT", f"/projects/{p['project_id']}/nodes/{n['node_id']}", body)

    def write_node_file(self, p, n, path, content):
        """Write a file into a node's persistent storage (docker: /etc/network/interfaces, volumes)."""
        url = f"/projects/{p['project_id']}/nodes/{n['node_id']}/files/{path.lstrip('/')}"
        r = urllib.request.Request(self.base + url, data=content.encode(), method="POST")
        if self.auth:
            r.add_header("Authorization", self.auth)
        with urllib.request.urlopen(r, timeout=60) as resp:
            return resp.status

    # links
    def links(self, p):
        return self.req("GET", f"/projects/{p['project_id']}/links")

    def find_link(self, p, node_name, port_name):
        nodes = {n["node_id"]: n for n in self.nodes(p)}
        for l in self.links(p):
            for end in l["nodes"]:
                n = nodes[end["node_id"]]
                if n["name"] == node_name:
                    for port in n["ports"]:
                        if port["adapter_number"] == end["adapter_number"] and port["port_number"] == end["port_number"] \
                                and port["name"] == port_name:
                            return l
        raise KeyError(f"{node_name}:{port_name}")

    def suspend_link(self, p, link, suspend=True):
        return self.req("PUT", f"/projects/{p['project_id']}/links/{link['link_id']}", {"suspend": suspend})


# =========================================================================================== console
IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240


class Console:
    """Minimal telnet client: strips/refuses option negotiation, buffered expect()."""

    def __init__(self, host, port, name="", log=None):
        self.name, self.host, self.port = name, host, port
        self.sock = socket.create_connection((host, port), timeout=10)
        self.sock.settimeout(0.2)
        self.buf = ""
        self.log = log

    @classmethod
    def for_node(cls, api, p, name):
        n = api.node(p, name)
        host = n["console_host"]
        if host in ("0.0.0.0", "::", "unknown"):
            host = api.req("GET", "/computes/" + n["compute_id"])["host"]
        return cls(host, n["console"], name)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

    def _negotiate(self, data):
        out, i, reply = bytearray(), 0, bytearray()
        while i < len(data):
            b = data[i]
            if b == IAC and i + 1 < len(data):
                cmd = data[i + 1]
                if cmd in (DO, DONT, WILL, WONT) and i + 2 < len(data):
                    opt = data[i + 2]
                    if cmd == DO:
                        reply += bytes([IAC, WILL if opt in (1, 3) else WONT, opt])  # echo / suppress-go-ahead ok
                    elif cmd == WILL:
                        reply += bytes([IAC, DO if opt in (1, 3) else DONT, opt])
                    i += 3
                    continue
                if cmd == SB:
                    j = data.find(bytes([IAC, SE]), i)
                    i = j + 2 if j >= 0 else len(data)
                    continue
                if cmd == IAC:
                    out.append(IAC)
                i += 2
                continue
            out.append(b)
            i += 1
        if reply:
            self.sock.sendall(bytes(reply))
        return bytes(out)

    def read(self, wait=0.3):
        start = time.time()
        end, hard = start + wait, start + wait + 2.0      # hard cap: a chatty console must not block forever
        got = b""
        while time.time() < min(end, hard):
            try:
                chunk = self.sock.recv(65536)
                if not chunk:
                    break
                got += self._negotiate(chunk)
                end = max(end, time.time() + 0.15)
            except socket.timeout:
                pass
        text = got.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "")
        if self.log is not None and text:
            self.log.write(text)
        self.buf += text
        return text

    def send(self, s, eol="\r"):
        self.sock.sendall((s + eol).encode())

    def expect(self, patterns, timeout=30):
        """Wait until one regex matches the buffer; return (index, match, text_before) and consume."""
        if isinstance(patterns, str):
            patterns = [patterns]
        regs = [re.compile(p, re.M) for p in patterns]
        end = time.time() + timeout
        while True:
            for k, r in enumerate(regs):
                m = r.search(self.buf)
                if m:
                    before = self.buf[:m.start()]
                    self.buf = self.buf[m.end():]
                    return k, m, before
            if time.time() > end:
                tail = self.buf[-300:]
                raise TimeoutError(f"[{self.name}] timeout waiting for {patterns}; tail={tail!r}")
            self.read(0.5)


# =========================================================================================== Cisco IOS
class Ios:
    PROMPT = r"^[\w.\-]+(\(config[^)]*\))?[>#]\s*$"

    def __init__(self, con, user=None, password=None, enable=None):
        self.c = con
        self.user, self.password, self.enable = user, password, enable

    def login(self, timeout=600):
        """Bring the console to privileged EXEC, handling first-boot dialogs and AAA login.

        The console is nudged with <Enter> whenever it stays silent for 10 s (booting device,
        prompt already consumed, banner scrolled), so the loop never waits blindly.
        """
        c = self.c
        end = time.time() + timeout
        pats = [
            r"initial configuration dialog\? \[yes/no\]:",      # 0
            r"terminate autoinstall\? \[yes\]:",                   # 1
            r"Press RETURN to get started",                        # 2
            r"Username:\s*$",                                      # 3
            r"Password:\s*$",                                      # 4
            r"^[\w.\-]+>\s*$",                                     # 5
            r"^[\w.\-]+\(config[^)]*\)#\s*$",                      # 6
            r"^[\w.\-]+#\s*$",                                     # 7
        ]
        c.send("")
        while time.time() < end:
            try:
                k, _, _ = c.expect(pats, timeout=10)
            except TimeoutError:
                c.send("")
                continue
            if k == 0:
                c.send("no")
            elif k == 1:
                c.send("yes")
            elif k == 2:
                time.sleep(1); c.send("")
            elif k == 3:
                c.send(self.user or "netadmin")
            elif k == 4:
                c.send(self.password if self.user or self.password else (self.enable or ""))
            elif k == 5:
                c.send("enable")
                k2, _, _ = c.expect([r"Password:\s*$", r"#\s*$"], 15)
                if k2 == 0:
                    c.send(self.enable or "")
                else:
                    c.send("")              # the '#' prompt was consumed: ask for a fresh one
            elif k == 6:
                c.send("end")
            elif k == 7:
                c.send("terminal length 0"); c.expect(r"#\s*$", 15)
                c.send("terminal width 0"); c.expect(r"#\s*$", 15)
                return True
        raise TimeoutError("login")

    def cmd(self, command, timeout=60):
        self.c.read(0.3)                       # drain late output (e.g. prompts from terminal settings)
        self.c.buf = ""
        self.c.send(command)
        self.c.expect(re.escape(command[:60]), 30)   # consume our own echo, then everything up to the prompt
        _, _, before = self.c.expect(r"^[\w.\-]+#[ \t]*$", timeout)
        return before.strip("\n")

    def push_config(self, text, pace=0.05):
        """Paste a config in config mode; return list of (line, error) for rejected lines."""
        c = self.c
        lines = [l.rstrip() for l in text.splitlines()
                 if l.strip() and not l.lstrip().startswith("!") and l.strip() not in ("end", "version 15.2", "version 15.9")]
        c.read(0.3)
        c.send("configure terminal"); c.expect(r"\(config\)#\s*$", 15)
        transcript = []
        batch = 8                                   # IOS buffers pasted input; small batches avoid overruns
        for i in range(0, len(lines), batch):
            chunk = lines[i:i + batch]
            c.buf = ""
            for l in chunk:
                c.send(l)
                time.sleep(pace)
            slow = any("crypto key" in l for l in chunk)
            deadline = time.time() + (60 if slow else 20)
            while time.time() < deadline:               # until the chunk's last line is echoed and a prompt follows
                c.read(0.5)
                tail = c.buf.rstrip()
                if chunk[-1].strip()[:40] in c.buf and re.search(r"\)#\s*$|#\s*$", tail):
                    break
            transcript.append(c.buf)
        c.send("end"); c.expect(r"#\s*$", 30)
        # attribute IOS error lines to the command echoed just before them
        errors, last = [], None
        for t in transcript:
            for ln in t.split("\n"):
                m = re.match(r"^[\w.\-]+\(config[^)]*\)#(.*)$", ln)
                if m:
                    last = m.group(1).strip() or last
                elif ln.startswith("%") and any(k in ln for k in ("Invalid", "Incomplete", "Ambiguous", "Unknown", "not supported", "Unrecognized")):
                    errors.append((last, ln.strip()))
        return errors

    def save(self):
        self.c.send("write memory")
        k, _, _ = self.c.expect([r"\[confirm\]", r"\[OK\]", r"#\s*$"], 120)
        if k == 0:
            self.c.send("")
        if k != 2:
            self.c.expect(r"#\s*$", 120)


# =========================================================================================== Linux (serial console)
class Linux:
    """Ubuntu cloud image on a serial console: login (ubuntu/ubuntu via GNS3 cloud-init ISO), root shell,
    commands with an exit-code marker so output and status are captured reliably."""

    def __init__(self, con, user="ubuntu", password="ubuntu"):
        self.c, self.user, self.password = con, user, password
        self.n = 0

    def login(self, timeout=600):
        c = self.c
        end = time.time() + timeout
        c.send("")
        while time.time() < end:
            try:
                k, _, _ = c.expect([r"login:\s*$", r"Password:\s*$", r"\$\s*$", r"#\s*$"], timeout=10)
            except TimeoutError:
                c.send("")
                continue
            if k == 0:
                c.send(self.user)
            elif k == 1:
                c.send(self.password)
            elif k == 2:
                c.send("sudo -i")
            elif k == 3:
                c.send("export TERM=dumb PS1='# '; stty -echo cols 250; dmesg -n 1")
                time.sleep(1); c.read(1)
                return True
        raise TimeoutError("linux login")

    def run(self, cmd, timeout=120):
        """Run a shell command as root; returns (rc, output)."""
        self.n += 1
        tag = f"__RC{self.n}_"
        self.c.read(0.2)
        self.c.buf = ""
        self.c.send(f"{cmd} ; echo {tag}$?__")
        _, m, before = self.c.expect(re.escape(tag) + r"(\d+)__", timeout)
        rc = int(m.group(1))
        out = before.replace(cmd, "", 1).strip("\n")
        return rc, out

    def put_file(self, path, text, mode="644"):
        """Write a text file through the console (base64, chunked)."""
        b = base64.b64encode(text.replace("\r\n", "\n").encode()).decode()
        self.run(f"rm -f /tmp/.up && : > /tmp/.up")
        for i in range(0, len(b), 600):
            self.run(f"echo '{b[i:i + 600]}' >> /tmp/.up")
        return self.run(f"base64 -d /tmp/.up > {path} && chmod {mode} {path} && rm -f /tmp/.up")


# =========================================================================================== evidence
def save_evidence(node, command, output):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", command.lower()).strip("_")[:50]
    path = EVIDENCE / f"{node}__{slug}.txt"
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    path.write_text(f"# {node} – {command} – {stamp}\n{output.rstrip()}\n", encoding="utf-8", newline="\n")
    return path


def creds():
    import yaml
    c = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))["credentials"]
    return c["admin_user"], c["admin_password"], c["enable_secret"]


# =========================================================================================== CLI
def main(argv):
    if not argv:
        print(__doc__); return 1
    api = Gns3()
    p = api.open(api.project())
    op, args = argv[0], argv[1:]
    if op == "status":
        for n in sorted(api.nodes(p), key=lambda n: n["name"]):
            print(f"{n['name']:12} {n['node_type']:16} {n['status']:8} {n['console_host']}:{n['console']}")
    elif op in ("start", "stop", "reload"):
        for name in args:
            getattr(api, op)(p, api.node(p, name)); print(f"{op} {name}")
    elif op == "show":
        name, command = args[0], args[1]
        u, pw, en = creds()
        with Console.for_node(api, p, name) as c:
            ios = Ios(c, u, pw, en); ios.login()
            out = ios.cmd(command)
        print(out)
        if "--save" in args:
            print("saved", save_evidence(name, command, out))
    elif op == "push":
        u, pw, en = creds()
        for name in args:
            text = (NET / "configs" / f"{name}.cfg").read_text(encoding="utf-8")
            with Console.for_node(api, p, name) as c:
                ios = Ios(c, u, pw, en); ios.login()
                errs = ios.push_config(text)
                ios.save()
            print(f"{name}: pushed, {len(errs)} rejected line(s)")
            for l, e in errs:
                print(f"   {l!r} -> {e}")
    else:
        print(__doc__); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
