"""Director v2 (PLAN_06): the live GNS3 walkthrough, recorded act by act from the running lab.

  python automation/demo_video/walkthrough.py A0 A1 ...       (list: --list ; dry layout test: --dry A0)
Every node shown follows role -> test -> result; the marks of each recording are the narration ids of
narration.yaml, so edit2.py cuts each segment exactly and fits it to its voiceover.
Reuses director.py (Scene, Term, failover, login_zabbix, socks_tcp). New here:
- Gns3Web: the real GNS3 Web UI (v2.2.54, served by the local controller) driven by Playwright; the server entry is
  pre-seeded in localStorage (D1) so the project opens directly; consoles open in the Web UI widget.
- Split: two pages recorded at the same time, 960x1080 each, aligned on a common t0 (edit2.py hstacks them).
Output: 05_Report/presentation/video/raw2/<rec>.webm + <rec>.json (marks), like director.py.
"""
import base64
import json
import random
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import director as D  # noqa: E402
import labctl  # noqa: E402
import adminws  # noqa: E402
import gns3vm  # noqa: E402

RAW2 = D.ROOT / "05_Report" / "presentation" / "video" / "raw2"
D.RAW = RAW2                      # director's Scene writes into raw2/ for this video
NET = D.NET
PY = sys.executable
DRY = "--dry" in sys.argv
PROFILE = sys.argv[sys.argv.index("--profile") + 1] if "--profile" in sys.argv else "net"


class Rec(D.Scene):
    """director.Scene with a chosen size, an optional proxy and a shared t0 (for split recordings)."""

    def __init__(self, browser, name, size=(1280, 720), proxy=True, http_credentials=None, t0=None, init=None):
        RAW2.mkdir(parents=True, exist_ok=True)
        self.name, self.marks = name, []
        kw = dict(viewport={"width": size[0], "height": size[1]}, record_video_dir=str(RAW2 / "_tmp"),
                  record_video_size={"width": size[0], "height": size[1]}, ignore_https_errors=True, locale="fr-FR",
                  http_credentials=http_credentials)
        if proxy:
            kw["proxy"] = {"server": f"socks5://{D.PROXY[0]}:{D.PROXY[1]}",
                           "bypass": "fonts.googleapis.com,fonts.gstatic.com,localhost,127.0.0.1"}
        self.ctx = browser.new_context(**kw)
        self.ctx.add_init_script(D.CURSOR_JS)
        if init:
            self.ctx.add_init_script(init)
        self.page = self.ctx.new_page()
        self.vstart = time.time()                 # the video starts with the page
        self.t0 = t0 or self.vstart
        self.mx, self.my = size[0] // 2, size[1] // 2

    def close(self):
        v = self.page.video
        self.ctx.close()
        dst = RAW2 / f"{self.name}.webm"
        if dst.exists():
            dst.unlink()
        Path(v.path()).rename(dst)
        (RAW2 / f"{self.name}.json").write_text(json.dumps({"rec": self.name, "t0": self.t0, "vstart": self.vstart, "marks": self.marks},
                                                           indent=1), encoding="utf-8")
        print(f"   {self.name}: {dst.name}, {len(self.marks)} marks", flush=True)


def mark_all(recs, label):
    for r in recs:
        r.mark(label)


def small_term(t, px=19):
    """Term page sized for a 1280x720 recording (D8)."""
    t.p.evaluate("px => { document.querySelector('pre').style.fontSize = px + 'px'; "
                 "document.querySelector('.w').style.inset = '20px'; document.querySelector('.t').style.fontSize = '17px'; }", px)
    return t


class Gns3Web(Rec):
    """The GNS3 Web UI of the local controller, project DC_Casablanca open."""

    def __init__(self, browser, name, size=(1280, 720), t0=None):
        self.api = labctl.Gns3()
        self.pr = self.api.project()
        user, pw = base64.b64decode(self.api.auth.split()[1]).decode().split(":", 1)
        srv = {"id": 1, "name": "local", "location": "remote", "host": "127.0.0.1", "port": 3080, "path": "",
               "ubridge_path": "", "status": "running", "protocol": "http:", "authorization": "basic",
               "login": user, "password": pw}
        init = ("if(!sessionStorage.getItem('dcinit')){sessionStorage.setItem('dcinit','1');localStorage.clear();"
                "localStorage.setItem('serverIds','server-1');"
                f"localStorage.setItem('server-1', {json.dumps(json.dumps(srv))});localStorage.setItem('theme','dark');"
                "localStorage.setItem('openConsolesInWidget','true');localStorage.setItem('showInterfaceLabels','false')}")
        super().__init__(browser, name, size=size, proxy=False, http_credentials={"username": user, "password": pw},
                         t0=t0, init=init)
        self.url = f"http://127.0.0.1:3080/static/web-ui/server/1/project/{self.pr['project_id']}"

    def open(self, zoom_out=2):
        self.page.goto("http://127.0.0.1:3080/static/web-ui/index.html", wait_until="networkidle")
        self.page.goto(self.url, wait_until="networkidle")
        self.page.locator("svg").first.wait_for(timeout=60000)
        self.wait(3)
        for _ in range(zoom_out):
            self.glide_to(self.page.locator("button[mattooltip='Zoom out']"), click=True, pause=0.4)
        self.center()
        self.center()

    def bbox(self, names=None):
        """Screen box of the node symbols (all, or the named ones)."""
        return self.page.evaluate("""names => { let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
          document.querySelectorAll('svg g.node, svg g[node]').forEach(g => { const t=g.querySelector('text');
            if (names && !(t && names.includes(t.textContent.trim()))) return;
            const r=g.getBoundingClientRect(); if (!r.width) return;
            x0=Math.min(x0,r.left); y0=Math.min(y0,r.top); x1=Math.max(x1,r.right); y1=Math.max(y1,r.bottom); });
          return x0<1e9 ? [x0,y0,x1,y1] : null; }""", names)

    def center(self, names=None, cx=None, cy=None):
        """Pan the map (pan tool + drag) so the nodes (all or named) are centred in the free area."""
        bb = self.bbox(names)
        if not bb:
            print("   gns3web: no node box", flush=True)
            return
        vw, vh = self.page.viewport_size["width"], self.page.viewport_size["height"]
        cx = cx or (vw + 90) / 2
        cy = cy or (vh + 60) / 2
        dx, dy = cx - (bb[0] + bb[2]) / 2, cy - (bb[1] + bb[3]) / 2
        self.btn("Pan workspace", pause=0.3)
        sx, sy = vw / 2, vh * 0.75
        self.glide(sx, sy, 0.2)
        self.page.mouse.down()
        self.page.mouse.move(sx + dx, sy + dy, steps=30)
        self.page.mouse.up()
        self.mx, self.my = sx + dx, sy + dy
        self.wait(0.5)
        self.btn("Selection mode", pause=0.3)

    def btn(self, tip, click=True, pause=0.6):
        self.glide_to(self.page.locator(f"button[mattooltip='{tip}']"), click=click, pause=pause)

    def node_el(self, name):
        """The node label in the map (svg text)."""
        return self.page.locator("svg text", has_text=name).first

    def hover_node(self, name, pause=1.2):
        self.glide_to(self.node_el(name), pause=pause)

    def console(self, name):
        """Right-click the node -> 'Console' (opens in the Web UI console widget)."""
        el = self.node_el(name)
        self.glide_to(el, pause=0.4)
        self.page.mouse.click(self.mx, self.my, button="right")
        self.wait(0.8)
        item = self.page.locator("button.mat-menu-item, [role=menuitem]", has_text="Console").first
        self.glide_to(item, click=True, pause=2.5)

    def type_console(self, text, enter=True):
        for ch in text:
            self.page.keyboard.type(ch)
            self.wait(random.uniform(0.04, 0.1))
        if enter:
            self.wait(0.3)
            self.page.keyboard.press("Enter")


# ------------------------------------------------------------------------------------------------ act 0
def a0_boot(b):
    """Cold start, split: left the GNS3 Web UI (nodes turn green), right lab_up.py with its stage/RAM table."""
    t0 = time.time()
    left = Gns3Web(b, "A0_left_gns3", size=(960, 1080), t0=t0)
    right = Rec(b, "A0_right_labup", size=(960, 1080), proxy=False, t0=t0)
    recs = [left, right]
    left.open(zoom_out=8)
    t = D.Term(right, "Démarrage à froid · profil demo", "PC hôte · 03_Network")
    mark_all(recs, "a0_intro")
    left.btn("Toggle topology/servers summary", pause=1.0)
    left.btn("Toggle topology/servers summary", pause=1.0)
    argv = [PY, "automation/lab_up.py", "--profile", "demo"] if not DRY else [PY, "-c", "import time\nfor i in range(4): print('stage', i); time.sleep(3)"]
    t.typed("PS 03_Network>", "python automation/lab_up.py --profile demo")
    mark_all(recs, "a0_boot")
    p = subprocess.Popen(argv, cwd=NET, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                         errors="replace", env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8",
                                                "PYTHONDONTWRITEBYTECODE": "1"})
    for ln in p.stdout:
        ln = ln.rstrip("\n")
        print("   lab_up:", ln[:150], flush=True)
        show = ln
        if ln.strip().startswith("{"):   # measure dict -> compact RAM line
            try:
                m = eval(ln.strip(), {})  # noqa: S307  our own script's printed dict
                show = (f"    VM {m['vm_used_mb']} Mo utilisés / {m['vm_avail_mb']} Mo dispo · swap {m['swap_used_mb']} Mo · "
                        f"charge {m['load1']} · hôte libre {m['host_free_gb']} Go")
            except Exception:  # noqa: BLE001
                pass
        cls = "ok" if ln.startswith(("stage", "swap", "lab proxy", "zabbix")) else None
        right.page.evaluate("([t, c]) => print(t, c)", [show, cls])
        if ln.startswith("stage"):
            mark_all(recs, "stage " + ln.split(":")[0][6:])
        if ln.startswith("swap flushed"):
            mark_all(recs, "a0_post")
    p.wait()
    mark_all(recs, "a0_done")
    left.wait(4)
    left.shot("60_gns3_webui_demo_profile")
    for r in recs:
        r.close()
    return p.returncode


ACTS = {"A0": a0_boot}


# ------------------------------------------------------------------------------------------------ live values
VALUES = RAW2 / "values.json"


def put_values(**kw):
    """Live results of this run -> values.json (voice.py fills the narration placeholders from it)."""
    v = json.loads(VALUES.read_text(encoding="utf-8")) if VALUES.exists() else {}
    v.update(kw)
    VALUES.write_text(json.dumps(v, indent=1, ensure_ascii=False), encoding="utf-8")
    print("   values:", kw, flush=True)


def fr(x, nd=1):
    return f"{x:.{nd}f}".replace(".", ",")


def run_stream(t, prompt, cmd, argv, keep=None, pause=3):
    """Like Term.run_local, but returns the output and prints only the lines `keep(line)` accepts."""
    t.typed(prompt, cmd)
    p = subprocess.Popen(argv, cwd=NET, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                         errors="replace", env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8",
                                                "PYTHONDONTWRITEBYTECODE": "1"})
    lines = []
    for ln in p.stdout:
        ln = ln.rstrip("\n")
        lines.append(ln)
        if keep is None or keep(ln):
            cls = ("ok" if re.search(r"\b(OK|PASS|found|locked)", ln) else "ko" if re.search(r"\bFAIL", ln) else None)
            t.p.evaluate("([t, c]) => print(t, c)", [ln[:160], cls])
    p.wait()
    t.sc.wait(pause)
    return "\n".join(lines)


def ssh_show(t, items, pause=2.5):
    """Term.run_ssh that also returns the outputs."""
    res = adminws.ssh_batch([(a, c) for a, _, c in items], timeout=40)
    outs = []
    for (a, prompt, c), (rc, o) in zip(items, res):
        t.typed(prompt, c)
        t.show(o)
        outs.append(o)
        t.sc.wait(pause)
    return outs


# ------------------------------------------------------------------------------------------------ act 1
def a1_console(b):
    """The GNS3 Web UI, full screen: zoom on the core, right-click CORE-A -> Console, show standby brief."""
    g = Gns3Web(b, "A1_console")
    g.open(zoom_out=3)
    g.center(["CORE-A", "CORE-B", "FW-A", "FW-B"])
    g.mark("a1_console")
    g.hover_node("CORE-B", 0.8)
    g.hover_node("CORE-A", 0.8)
    g.console("CORE-A")
    g.wait(2)
    g.page.keyboard.press("Enter")
    g.wait(2)

    def term():
        return g.page.evaluate("() => [...document.querySelectorAll('.xterm-rows')].map(e => e.innerText).join('\\n')")
    for _ in range(8):
        lines = [l.strip() for l in term().splitlines() if l.strip()]
        last = lines[-1] if lines else ""
        if last.endswith("Username:"):
            g.type_console(D.CRED["admin_user"])
        elif last.endswith("Password:"):
            for ch in D.CRED["admin_password"]:      # not echoed by IOS: nothing appears on screen
                g.page.keyboard.type(ch)
            g.page.keyboard.press("Enter")
        elif last.endswith(">"):
            g.type_console("enable")
        elif last.endswith("#"):
            break
        else:
            g.page.keyboard.press("Enter")
        g.wait(2.5)
    g.type_console("terminal length 0")
    g.wait(1)
    g.mark("a1_console_cmd")
    g.type_console("show standby brief")
    g.wait(5)
    g.shot("61_gns3_webui_console_core-a")
    (RAW2 / "A1_console_screen.txt").write_text(term(), encoding="utf-8")
    out = adminws.ssh_batch([("core-a", "show standby brief")], timeout=40)[0][1]
    act = len(re.findall(r"\bActive\s+local\b", out))
    put_values(hsrp_result=f"CORE-A est actif sur {act} groupes HSRP, CORE-B porte les autres et reste en secours"
               if act else "voir l'écran")
    g.wait(3)
    g.type_console("exit")
    g.wait(2)
    g.close()


def a1_net(b):
    sc = Rec(b, "A1_net")
    t = small_term(D.Term(sc, "Réseau · commandes réelles en SSH", "ADMIN-WS (VLAN 90)"))
    sc.mark("a1_edge")
    o = ssh_show(t, [("edge-a", "EDGE-A#", "show ip bgp summary | begin Neighbor")])[0]
    rows = [l.split() for l in o.splitlines() if re.match(r"^\d+\.\d+\.\d+\.\d+\s", l)]
    est = [r for r in rows if r[-1].isdigit()]
    put_values(bgp_result=(f"la session vers ISP-A est établie, {est[0][-1]} préfixes reçus" if est else "voir l'écran")
               + (", la session vers EDGE-B attend, car EDGE-B est éteint dans ce profil" if len(rows) > len(est) else ""))
    sc.mark("a1_ospf")
    o1, o2 = ssh_show(t, [("core-a", "CORE-A#", "show ip ospf neighbor"),
                          ("core-a", "CORE-A#", "show etherchannel summary | begin Group")])
    full = len(re.findall(r"FULL", o1))
    po = re.search(r"(Po\d+)\((\w+)\)", o2)
    nlinks = len(re.findall(r"\(P\)", o2))
    put_values(ospf_result=(f"{full} voisin OSPF à l'état FULL, et l'agrégat {po.group(1) if po else 'Po1'} est en service "
                            f"avec {nlinks} liens") if full else "voir l'écran")
    sc.mark("a1_leaf")
    ssh_show(t, [("leaf-b1", "LEAF-B1#", "show interfaces trunk | begin Vlans allowed and active"),
                 ("leaf-b1", "LEAF-B1#", "show spanning-tree summary | include inconsistent|Name|Total")], pause=3)
    sc.mark("a1_adminws")
    ssh_show(t, [("core-a", "CORE-A#", "show users")], pause=4)
    sc.close()


def a1_fw(b):
    sc = Rec(b, "A1_fw")
    pg = sc.page
    sc.go("https://10.90.0.1/", until="domcontentloaded")
    sc.wait(1.2)
    sc.type_into(pg.locator("#usernamefld"), "admin")
    pg.fill("#passwordfld", D.CRED["admin_password"])          # masked field, never typed visibly
    sc.glide_to(pg.locator("button[name=login], input[name=login]").first, click=True)
    pg.wait_for_load_state("networkidle", timeout=120000)
    sc.go("https://10.90.0.1/status_carp.php", until="networkidle")
    sc.mark("a1_fw_carp")
    sc.wait(1.2)
    trs = pg.locator("table tbody tr")
    for i in range(min(trs.count(), 6)):
        sc.glide_to(trs.nth(i), pause=0.5)
    n = len(re.findall(r"MASTER", pg.inner_text("body")))
    put_values(carp_result=f"{n} adresses virtuelles sont MASTER sur FW-A, FW-B les tient en secours" if n else "voir l'écran")
    sc.shot("21v2_fw-a_carp")
    sc.wait(1.5)
    sc.go("https://10.90.0.1/firewall_rules.php?if=opt2", until="networkidle")
    sc.mark("a1_fw_rules")
    sc.wait(1)
    trs = pg.locator("table tbody tr")
    for i in range(min(trs.count(), 5)):
        sc.glide_to(trs.nth(i), pause=0.4)
    for url in ("firewall_nat.php", "status_logs_filter.php"):
        sc.go(f"https://10.90.0.1/{url}", until="networkidle")
        sc.wait(1)
        trs = pg.locator("table tbody tr")
        for i in range(min(trs.count(), 4)):
            sc.glide_to(trs.nth(i), pause=0.4)
        sc.wait(1.2)
    sc.close()


def a1_svc(b):
    sc = Rec(b, "A1_svc")
    t = small_term(D.Term(sc, "Services · site public et cloisonnement", "ISP-A (Internet) puis ADMIN-WS"))
    sc.mark("a1_web")
    t.typed("root@isp-a:~#", "printf 'GET /health HTTP/1.0\\r\\n\\r\\n' | nc -w 5 192.0.2.80 80")
    out = gns3vm.run("docker exec $(docker ps -q --filter name=ISP-A) sh -c \"printf 'GET /health HTTP/1.0\\r\\n\\r\\n' | "
                     "nc -w 5 192.0.2.80 80\"", sudo=True)
    t.show(out.strip())
    m = re.search(r"OK[^\n]*", out)
    put_values(web_result=f"le serveur répond « {m.group(0).strip()} », à travers le NAT du pare-feu" if m else "voir l'écran")
    sc.wait(3)
    sc.mark("a1_acl")
    o1, o2 = ssh_show(t, [("srv-mon-01", "sysadmin@srv-mon-01:~$", "nc -zv -w 3 10.90.0.12 22; echo \"code retour $?\""),
                          ("core-a", "CORE-A#", "show ip access-lists ACL-VLAN60-IN | include deny")], pause=3)
    put_values(acl_result="la connexion est refusée, et le compteur de la règle deny de l'ACL du cœur augmente"
               if "code retour 0" not in o1 else "voir l'écran")
    sc.close()


def a1_noc(b):
    sc = Rec(b, "A1_noc")
    pg = sc.page
    D.login_zabbix(sc)
    sc.go("http://10.60.0.11/zabbix.php?action=host.view", until="networkidle")
    sc.mark("a1_zabbix")
    trs = pg.locator("table.list-table tbody tr")
    for i in range(0, min(trs.count(), 18), 2):
        sc.glide_to(trs.nth(i), pause=0.3)
    sc.go("http://10.60.0.11/zabbix.php?action=problem.view&filter_reset=1", until="networkidle")
    sc.wait(3)
    sc.close()


def a1_grafana(b):
    sc = Rec(b, "A1_grafana")
    pg = sc.page
    sc.go("http://10.60.0.11:3000/login", until="domcontentloaded", timeout=200000)
    sc.wait(1.5)
    sc.type_into(pg.locator("input[name=user]"), "admin")
    pg.fill("input[name=password]", D.CRED["grafana_admin_password"])
    pg.keyboard.press("Enter")
    pg.wait_for_url(lambda u: "/login" not in u, timeout=300000)
    pg.wait_for_load_state("networkidle", timeout=300000)
    pg.locator(".react-grid-item").first.wait_for(timeout=200000)
    sc.wait(6)
    sc.mark("a1_grafana")
    items = pg.locator(".react-grid-item")
    for i in range(min(items.count(), 10)):
        sc.glide_to(items.nth(i), pause=0.6)
    sc.shot("46v2_grafana_noc")
    sc.go("http://10.70.0.12:8080/", until="networkidle")
    sc.mark("a1_bms")
    sc.wait(4)
    sc.go("http://10.70.0.11:8080/", until="networkidle")
    sc.wait(2)
    for el in pg.locator("tr").all()[:6]:
        sc.glide_to(el, pause=0.4)
    sc.shot("50v2_dcim")
    sc.wait(2)
    sc.close()


def a1_soc(b):
    sc = Rec(b, "A1_soc")
    t = small_term(D.Term(sc, "SOC · journalisation centralisée (SYSLOG)", "PC hôte → visionneuse https://10.60.0.12/"))
    sc.mark("a1_soc")
    raw = lambda l: re.match(r"^\s*\S*\s*20\d\d-\d\d-\d\dT", l) is not None  # noqa: E731  raw syslog lines: too long
    out = run_stream(t, "PS 03_Network>", "python automation/log_viewer.py demo", [PY, "automation/log_viewer.py", "demo"],
                     keep=lambda l: not raw(l) and "audit trail" not in l, pause=3)
    found = [float(x) for x in re.findall(r"found in the viewer after ([\d.]+) s", out)]
    put_values(soc_result=("les trois événements sont retrouvés dans la visionneuse, chacun en moins de "
                           f"{fr(max(found) + 0.05)} seconde" if len(found) == 3 else
                           f"{len(found)} événements sur 3 retrouvés dans la visionneuse"))
    (RAW2 / "A1_soc_demo.txt").write_text(out, encoding="utf-8")
    t.p.evaluate("clearT()")
    sc.mark("a1_lock")
    out = run_stream(t, "PS 03_Network>", "python automation/log_viewer.py lock", [PY, "automation/log_viewer.py", "lock"],
                     keep=lambda l: not raw(l), pause=4)
    (RAW2 / "A1_soc_lock.txt").write_text(out, encoding="utf-8")
    put_values(lock_result="le compte est verrouillé après six tentatives, et le verrouillage est lui-même journalisé"
               if re.search(r"lock", out, re.I) else "voir l'écran")
    sc.close()


def a1_t6(b):
    sc = Rec(b, "A1_t6")
    pg = sc.page
    from zabbix_setup import SocksHTTPConnection

    def api(path):
        con = SocksHTTPConnection("10.70.0.12", 8080, timeout=10)
        con.request("GET", path)
        body = con.getresponse().read()
        con.close()
        return body
    sc.go("http://10.70.0.12:8080/", until="networkidle")
    sc.mark("a1_t6")
    sc.wait(3)
    api("/api/set?UTILITY-A=DOWN&UPS-A=DOWN&GENERATOR=DOWN")
    sc.mark("a1_t6_cut")
    for _ in range(4):
        sc.wait(2.5)
        pg.reload(wait_until="networkidle")
    sc.shot("58v2_t6_bms")
    sc.go("http://10.70.0.11:8080/", until="networkidle")
    sc.mark("a1_t6_dcim")
    sc.wait(4)
    api("/api/reset")
    sc.go("http://10.70.0.12:8080/", until="networkidle")
    sc.mark("a1_t6_reset")
    sc.wait(4)
    sc.close()


def a1_t2(b):
    scene0, term0 = D.Scene, D.Term

    class SmallTerm(term0):
        def __init__(self, sc, title, where="ADMIN-WS (VLAN 90)"):
            super().__init__(sc, title, where)
            small_term(self, 17)
            self.p.add_style_tag(content="#panel.on{width:380px !important;padding:22px !important} .big{font-size:72px !important}"
                                         " .st{font-size:24px !important} .lbl{font-size:16px !important}")
    D.Scene, D.Term = (lambda br, name, **kw: Rec(br, name)), SmallTerm
    try:
        outages = D.failover(b, "A1_t2", "FW-A", "T2 · arrêt du pare-feu maître FW-A", "10.70.0.12", 8080, back=True)
    finally:
        D.Scene, D.Term = scene0, term0
    js = RAW2 / "A1_t2.json"
    d = json.loads(js.read_text(encoding="utf-8"))
    d["marks"].insert(0, {"t": 0.0, "label": "a1_t2"})
    js.write_text(json.dumps(d, indent=1), encoding="utf-8")
    if outages:
        put_values(t2=fr(max(outages)))


def wait_fw_a(limit=480):
    """After T2: FW-A answering and MASTER again (CARP preempt) before the proof."""
    end = time.time() + limit
    while time.time() < end:
        if D.socks_tcp("10.90.0.1", 443, timeout=1.0):
            try:
                o = adminws.ssh_batch([("fw-a", "ifconfig | grep -c 'carp: MASTER'")], timeout=30)[0][1].strip()
                first = o.splitlines()[0].strip() if o else ""
                if first.isdigit() and int(first) >= 5:
                    print("   FW-A MASTER again", flush=True)
                    return True
            except Exception:  # noqa: BLE001
                pass
        time.sleep(15)
    print("   FW-A not MASTER yet after wait", flush=True)
    return False


def a1_proof(b):
    wait_fw_a()
    sc = Rec(b, "A1_proof")
    t = small_term(D.Term(sc, "Preuve · contrôles automatiques du laboratoire", "PC hôte · 03_Network"))
    sc.mark("a1_proof")
    prof = PROFILE
    out = run_stream(t, "PS 03_Network>", f"python automation/demo_check.py --profile {prof}",
                     [PY, "automation/demo_check.py", "--profile", prof], pause=5)
    m = re.findall(r"(\d+)\s*/\s*(\d+)", out)
    if m:
        put_values(demo_ok=m[-1][0], demo_total=m[-1][1])
    (RAW2 / "A1_proof_output.txt").write_text(out, encoding="utf-8")
    sc.shot("59v2_demo_check")
    sc.close()


ACTS.update({"A1_console": a1_console, "A1_net": a1_net, "A1_fw": a1_fw, "A1_svc": a1_svc, "A1_noc": a1_noc,
             "A1_grafana": a1_grafana, "A1_soc": a1_soc, "A1_t6": a1_t6, "A1_t2": a1_t2, "A1_proof": a1_proof})


# ------------------------------------------------------------------------------------------------ profile switches
def node_g(g, name):
    """The node group of the GNS3 map whose label is exactly `name`."""
    return g.page.locator("svg g.node").filter(has=g.page.locator("text", has_text=re.compile(rf"^\s*{re.escape(name)}\s*$"))).first


def ui_action(g, name, action):
    """Right-click the node in the GNS3 Web UI -> Start/Stop; the API is the fallback (same effect)."""
    try:
        el = node_g(g, name)
        g.glide_to(el, pause=0.3)
        g.page.mouse.click(g.mx, g.my, button="right")
        g.wait(0.7)
        item = g.page.locator("button[role=menuitem], button.mat-menu-item").filter(
            has_text=re.compile(rf"^\s*{action}\s*$")).first
        item.wait_for(timeout=3000)
        g.glide_to(item, click=True, pause=0.8)
        return "ui"
    except Exception as e:  # noqa: BLE001
        g.page.keyboard.press("Escape")
        api = g.api
        getattr(api, action.lower())(g.pr, api.node(g.pr, name))
        print(f"   {name}: {action} via API ({str(e).splitlines()[0][:60]})", flush=True)
        return "api"


def switch(b, rec, mark, done, target, ready, limit=900):
    """Profile switch shown in the GNS3 Web UI: stop what the target does not use, then start the rest (D7)."""
    from lab_up import OFF, STAGES
    api = labctl.Gns3()
    pr = api.project()
    st = {n["name"]: n["status"] for n in api.nodes(pr)}
    want = {n for _, names in STAGES for n in names} - OFF[target]
    stop = [n for _, names in STAGES for n in names if n not in want and st.get(n) == "started"]
    start = [n for _, names in STAGES for n in names if n in want and st.get(n) != "started"]
    print(f"   switch -> {target}: stop {stop}, start {start}", flush=True)
    g = Gns3Web(b, rec)
    g.open(zoom_out=6)
    g.center()
    g.mark(mark)
    for n in stop:
        ui_action(g, n, "Stop")
    g.wait(8)
    for n in start:
        ui_action(g, n, "Start")
    end = time.time() + limit
    while time.time() < end and not ready():
        g.wait(10)
    g.mark(done)
    g.wait(4)
    g.close()


def ready_zabbix():
    import zabbix_setup as zs
    try:
        z = zs.Zabbix()
        zs.login(z)
        return True
    except Exception:  # noqa: BLE001
        return False


def post_noc():
    env = {**__import__("os").environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    for args in (["automation/zabbix_setup.py", "apply"], ["automation/zabbix_setup.py", "status"]):
        r = subprocess.run([PY, *args], cwd=NET, capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")
        print("  ", " ".join(args), "->", (r.stdout.strip().splitlines() or ["?"])[-1], flush=True)


def a1b_switch(b):
    switch(b, "A1b_switch", "a1b_switch", "a1b_done", "noc", ready_zabbix)
    post_noc()


def proof(b, rec, mark, profile):
    sc = Rec(b, rec)
    t = small_term(D.Term(sc, "Preuve · contrôles automatiques du laboratoire", f"PC hôte · profil {profile}"))
    sc.mark(mark)
    out = run_stream(t, "PS 03_Network>", f"python automation/demo_check.py --profile {profile}",
                     [PY, "automation/demo_check.py", "--profile", profile], pause=5)
    m = re.findall(r"(\d+)\s*/\s*(\d+) checks OK", out)
    (RAW2 / f"{rec}_output.txt").write_text(out, encoding="utf-8")
    sc.close()
    return m[-1] if m else None


def a1b_proof(b):
    m = proof(b, "A1b_proof", "a1b_proof", "noc")
    if m:
        put_values(noc_ok=m[0], noc_total=m[1])


def ready_cmp():
    return bool(D.socks_tcp("10.20.0.10", 8443, timeout=1.5))


def a2_switch(b):
    switch(b, "A2_switch", "a2_switch", "a2_done", "cmp", ready_cmp)
    r = subprocess.run([PY, "automation/cisco_heal.py", "LEAF-A1", "LEAF-A2"], cwd=NET, capture_output=True, text=True)
    print("   cisco_heal:", r.stdout.strip()[-200:], flush=True)


def a2_net(b):
    sc = Rec(b, "A2_net")
    t = small_term(D.Term(sc, "Calcul · salle A", "ADMIN-WS (VLAN 90)"))
    sc.mark("a2_leafa")
    o = ssh_show(t, [("leaf-a1", "LEAF-A1#", "show interfaces trunk | begin Vlans allowed and active"),
                     ("leaf-a1", "LEAF-A1#", "show interfaces status | include connected")])[0]
    trunks = re.findall(r"^(Gi\S+)\s", o, re.M)
    put_values(leafa_result=f"{len(set(trunks))} trunks actifs vers les cœurs, les VLAN 20 et 30 autorisés" if trunks else "voir l'écran")
    sc.mark("a2_cmp")
    o1, o2 = ssh_show(t, [("srv-cmp-01", "sysadmin@srv-cmp-01:~$", "ip -br addr show | grep -E 'bond|ens'"),
                          ("srv-cmp-02", "sysadmin@srv-cmp-02:~$", "ip -br addr show | grep -E 'bond|ens'")], pause=3)
    owner = "SRV-CMP-01" if "10.20.0.10" in o1 else "SRV-CMP-02" if "10.20.0.10" in o2 else None
    put_values(vip_result=f"{owner} porte la VIP, l'autre serveur attend en secours" if owner else "voir l'écran")
    sc.close()


def a2_t5(b):
    sc = Rec(b, "A2_t5")
    t = small_term(D.Term(sc, "T5 · arrêt de SRV-CMP-01 sous sonde", "SRV-WEB-01 → VIP https://10.20.0.10:8443 toutes les 0,5 s"), 16)
    sc.mark("a2_t5")
    out = run_stream(t, "PS 03_Network>", "python automation/fw_lan_failover.py --core SRV-CMP-01 --down 45 --up 90",
                     [PY, "automation/fw_lan_failover.py", "--core", "SRV-CMP-01", "--down", "45", "--up", "90"],
                     keep=lambda l: "samples:" not in l, pause=5)
    (RAW2 / "A2_t5_output.txt").write_text(out, encoding="utf-8")
    m = re.search(r"fault: outage from [^=]*= ([\d.]+) s", out)
    vip = re.search(r"fault: VIP served by (\S+) from \+([\d.]+) s", out)
    if m:
        put_values(t5=fr(float(m.group(1))))
    elif vip:
        put_values(t5=fr(float(vip.group(2))))
    sc.close()


def a2_proof(b):
    m = proof(b, "A2_proof", "a2_proof", "cmp")
    if m:
        put_values(cmp_ok=m[0], cmp_total=m[1])


def ready_nas():
    r = subprocess.run([PY, "automation/truenas_setup.py", "check"], cwd=NET, capture_output=True)
    return r.returncode == 0


def a3_switch(b):
    switch(b, "A3_switch", "a3_switch", "a3_done", "nas", ready_nas, limit=1200)
    r = subprocess.run([PY, "automation/truenas_setup.py", "apply"], cwd=NET, capture_output=True, text=True)
    print("   truenas apply:", (r.stdout.strip().splitlines() or ["?"])[-1], flush=True)


def a3_nas(b):
    sc = Rec(b, "A3_nas")
    t = small_term(D.Term(sc, "Sauvegarde · NAS TrueNAS SRV-BCK-01", "PC hôte → API TrueNAS (wss://10.40.0.11)"), 16)
    sc.mark("a3_nas")
    out = run_stream(t, "PS 03_Network>", "python automation/truenas_setup.py status",
                     [PY, "automation/truenas_setup.py", "status"],
                     keep=lambda l: not re.search(r"\b(UI |ntp |ssh |snmp |init script|services )", l), pause=4)
    (RAW2 / "A3_nas_status.txt").write_text(out, encoding="utf-8")
    pool = re.search(r"pool (\S+): (\w+), healthy=(\w+), (.*)", out)
    snaps = re.search(r"snapshots on \S+: (\d+)", out)
    rs = re.findall(r"rsync PULL '([^']*)' -> (\S+) .* last=(\w+)", out)
    put_values(nas_result=(f"le pool {pool.group(1)} est {pool.group(2)}, en miroir, {snaps.group(1) if snaps else '?'} "
                           f"snapshots ZFS, et {len(rs)} tâches de tirage" if pool else "voir l'écran"))
    t.p.evaluate("clearT()")
    sc.mark("a3_restore")
    # restore proof, read-only: the same file in the live copy and in the newest ZFS snapshot -> same SHA-256
    path = rs[0][1] if rs else "/mnt/tank/backups/SRV-MON-01"
    cmd = (f"f=$(find {path} -type f -name hostname | head -1); s=$(ls -1t {path.split('/backups')[0]}/backups/.zfs/snapshot 2>/dev/null | head -1); "
           f"echo fichier: $f; echo snapshot: $s; sha256sum \"$f\"; "
           f"sha256sum {path.split('/backups')[0]}/backups/.zfs/snapshot/$s/${{f#{path.split('/backups')[0]}/backups/}}")
    o = ssh_show(t, [("srv-bck-01", "truenas_admin@srv-bck-01:~$", cmd)], pause=4)[0]
    sums = re.findall(r"^([0-9a-f]{64})\s", o, re.M)
    put_values(restore_result=("le fichier relu depuis le snapshot a exactement la même empreinte SHA-256"
                               if len(sums) == 2 and sums[0] == sums[1] else "voir l'écran"))
    sc.close()


def a1_acl(b):
    """VLAN 60 (SRV-MON-01) -> administration: refused by the core ACL (needs SRV-MON-01 running: noc profile)."""
    sc = Rec(b, "A1_acl")
    t = small_term(D.Term(sc, "Cloisonnement · VLAN 60 vers l'administration", "ADMIN-WS → SRV-MON-01 puis CORE-A"))
    sc.mark("a1_acl")
    o0, o1, o2 = ssh_show(t, [("core-a", "CORE-A#", "show ip access-lists ACL-VLAN60-IN | include 210"),
                              ("srv-mon-01", "sysadmin@srv-mon-01:~$", "nc -zv -w 3 10.90.0.12 22; echo \"code retour $?\""),
                              ("core-a", "CORE-A#", "show ip access-lists ACL-VLAN60-IN | include 210")], pause=3)
    n0 = re.search(r"\((\d+) match", o0)
    n2 = re.search(r"\((\d+) match", o2)
    ok = "code retour" in o1 and "code retour 0" not in o1
    put_values(acl_result=("la connexion échoue, et le compteur de la règle deny 210 du cœur passe de "
                           f"{n0.group(1) if n0 else 0} à {n2.group(1)} correspondances") if ok and n2 else
               ("la connexion est refusée par l'ACL du cœur" if ok else "voir l'écran"))
    (RAW2 / "A1_acl_output.txt").write_text("
---
".join((o0, o1, o2)), encoding="utf-8")
    sc.close()


ACTS.update({"A1_acl": a1_acl, "A1b_switch": a1b_switch, "A1b_proof": a1b_proof, "A2_switch": a2_switch, "A2_net": a2_net,
             "A2_t5": a2_t5, "A2_proof": a2_proof, "A3_switch": a3_switch, "A3_nas": a3_nas})


def main(argv):
    names = [a for a in argv if a in ACTS]
    if "--list" in argv or not names:
        print("recordings:", " ".join(ACTS))
        return
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        # low-RAM Edge (PLAN_06 D7): no GPU process, few renderers, small JS heap; one browser per recording
        b = p.chromium.launch(channel="msedge", args=["--disable-gpu", "--renderer-process-limit=2",
                                                       "--disable-extensions", "--disable-background-networking",
                                                       "--disable-component-update", "--js-flags=--max-old-space-size=256"])
        for s in names:
            print(time.strftime("%H:%M:%S"), "recording", s, flush=True)
            ACTS[s](b)
        b.close()


if __name__ == "__main__":
    main(sys.argv[1:])
