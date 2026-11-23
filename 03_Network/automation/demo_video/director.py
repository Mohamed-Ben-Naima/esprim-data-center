"""Demo video director (PLAN_05 D6, P4/P5): records every scene of the storyboard from the live lab.

  python automation/demo_video/director.py S3 S4 ...      (scenes to record; list: python director.py --list)

How it stays real and human:
- Browser scenes: Playwright drives the installed Edge through the lab proxy (SOCKS5 on ADMIN-WS, so the pages are
  reached exactly as from the administration workstation) and records the page at 1920x1080. An overlay draws the
  mouse pointer, a ripple on each click and a cyan outline on the element under the pointer; moves are smooth.
- Terminal scenes: a terminal page in which the typist types each command at human speed (35-95 ms per key, a
  longer pause at spaces and before Enter). The command then runs for real - on the equipment over SSH from
  ADMIN-WS (adminws.ssh_batch), in a container of the GNS3 VM, or on the PC for the lab scripts - and its real
  output is printed line by line. Nothing is typed by hand, nothing is edited.
- Failover scenes: a probe through the lab proxy asks a service every 0.5 s while the node is stopped through
  the GNS3 API; a timer and the measured outage are drawn from the probe results themselves.
Output: 05_Report/presentation/video/raw/<scene>.webm (+ <scene>.json: timing marks for edit.py), and the PNG of
each key moment in 03_Network/screenshots (same run as the video, D10).
"""
import json
import re
import random
import socket
import struct
import subprocess
import sys
import threading
import time
from html import escape
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import adminws  # noqa: E402
import gns3vm  # noqa: E402
import labctl  # noqa: E402

NET = HERE.parents[1]
ROOT = NET.parent
RAW = ROOT / "05_Report" / "presentation" / "video" / "raw"
SHOTS = NET / "screenshots"
INV = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
CRED = INV["credentials"]
PROXY = ("192.168.75.128", 1080)
FONTS = "https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@500;700;800&display=swap"

CURSOR_JS = r"""
(() => {
  if (window.__dcCursor) return; window.__dcCursor = true;
  const add = () => {
    const c = document.createElement('div'); c.id = '__cur';
    c.innerHTML = '<svg width="34" height="34" viewBox="0 0 24 24"><path d="M4 2l15 11-6.5 1.2L9 21z" fill="#fff" stroke="#111" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    Object.assign(c.style, {position:'fixed', left:'0px', top:'0px', zIndex:2147483647, pointerEvents:'none', transform:'translate(-6px,-4px)', filter:'drop-shadow(0 2px 4px rgba(0,0,0,.45))'});
    document.documentElement.appendChild(c);
    const hl = document.createElement('div');
    Object.assign(hl.style, {position:'fixed', zIndex:2147483646, pointerEvents:'none', border:'3px solid #3FD0E8', borderRadius:'8px', boxShadow:'0 0 18px rgba(63,208,232,.55)', transition:'all .12s ease-out', opacity:0});
    document.documentElement.appendChild(hl);
    document.addEventListener('mousemove', e => {
      c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px';
      const t = document.elementFromPoint(e.clientX, e.clientY);
      const el = t && t.closest('a,button,tr,input,select,[role=button],.panel-container,.card,li');
      if (el && el.getBoundingClientRect().width < window.innerWidth * 0.95) {
        const r = el.getBoundingClientRect();
        Object.assign(hl.style, {left:(r.left-4)+'px', top:(r.top-4)+'px', width:(r.width+8)+'px', height:(r.height+8)+'px', opacity:1});
      } else hl.style.opacity = 0;
    }, true);
    document.addEventListener('mousedown', e => {
      const r = document.createElement('div');
      Object.assign(r.style, {position:'fixed', left:(e.clientX-6)+'px', top:(e.clientY-6)+'px', width:'12px', height:'12px', borderRadius:'50%', border:'3px solid #3FD0E8', zIndex:2147483646, pointerEvents:'none', transition:'all .5s ease-out', opacity:1});
      document.documentElement.appendChild(r);
      requestAnimationFrame(() => Object.assign(r.style, {left:(e.clientX-34)+'px', top:(e.clientY-34)+'px', width:'68px', height:'68px', opacity:0}));
      setTimeout(() => r.remove(), 600);
    }, true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', add); else add();
})();
"""

TERM_HTML = """<html><head><meta charset="utf-8"><link rel="stylesheet" href="{fonts}"><style>
html,body{{margin:0;height:100%;background:#0B1015;font-family:'JetBrains Mono',Consolas,monospace}}
.w{{position:absolute;left:40px;top:40px;right:40px;bottom:40px;background:#11171D;border:1px solid #2C3742;border-radius:16px;overflow:hidden;display:flex;flex-direction:column}}
.t{{display:flex;align-items:center;gap:10px;background:#1A232C;padding:14px 22px;font-family:Inter,Arial;font-size:22px;color:#A9B8C4}}
.d{{width:15px;height:15px;border-radius:8px}} .t b{{color:#E8EEF2;margin-left:12px}} .t i{{margin-left:auto;font-style:normal}}
.body{{display:flex;flex:1;min-height:0}}
pre{{flex:1;margin:0;padding:26px 30px;font-size:26px;line-height:1.42;color:#D5DEE5;white-space:pre-wrap;overflow:hidden}}
.p{{color:#3FD0E8;font-weight:700}} .c{{color:#F4F7F9;font-weight:700}} .ok{{color:#4CC38A}} .ko{{color:#E5675F;font-weight:700}} .dim{{color:#7F909E}}
.cur{{background:#3FD0E8;color:#0B1015;animation:b 1s steps(1) infinite}} @keyframes b{{50%{{background:transparent}}}}
#panel{{width:0;overflow:hidden;background:#0E141A;border-left:1px solid #2C3742;font-family:Inter,Arial;color:#E8EEF2;display:flex;flex-direction:column;gap:22px;padding:0}}
#panel.on{{width:560px;padding:34px}}
.lbl{{font-size:22px;color:#A9B8C4;letter-spacing:2px;text-transform:uppercase;font-weight:700}}
.big{{font-size:110px;font-weight:800;font-family:'JetBrains Mono';line-height:1}}
.st{{font-size:34px;font-weight:700}}
</style></head><body><div class="w"><div class="t"><span class="d" style="background:#E5675F"></span>
<span class="d" style="background:#F0AD4E"></span><span class="d" style="background:#4CC38A"></span><b id="title">{title}</b><i id="where">{where}</i></div>
<div class="body"><pre id="out"></pre><div id="panel"></div></div></div>
<script>
const out=document.getElementById('out'); let line=null;
function prompt(p){{ line=document.createElement('span'); out.appendChild(document.createTextNode(out.textContent?'\\n':''));
  const ps=document.createElement('span'); ps.className='p'; ps.textContent=p+' '; out.appendChild(ps);
  line=document.createElement('span'); line.className='c'; out.appendChild(line); cursor(); }}
function cursor(){{ let c=document.getElementById('cur'); if(c) c.remove(); c=document.createElement('span'); c.id='cur'; c.className='cur'; c.textContent=' '; out.appendChild(c); out.scrollTop=out.scrollHeight; }}
function key(ch){{ line.textContent+=ch; cursor(); }}
function enter(){{ const c=document.getElementById('cur'); if(c) c.remove(); }}
function print(t,cls){{ const s=document.createElement('span'); if(cls) s.className=cls; s.textContent='\\n'+t; out.appendChild(s); out.scrollTop=out.scrollHeight; }}
function clearT(){{ out.textContent=''; }}
function panel(h){{ const p=document.getElementById('panel'); p.className='on'; p.innerHTML=h; }}
</script></body></html>"""


# ------------------------------------------------------------------------------------------------ helpers
def socks_tcp(host, port, timeout=1.0):
    """TCP connect to host:port through the lab proxy (= from ADMIN-WS). Returns rtt ms or None."""
    t0 = time.perf_counter()
    try:
        s = socket.create_connection(PROXY, timeout=timeout)
        s.settimeout(timeout)
        s.sendall(b"\x05\x01\x00")
        if s.recv(2) != b"\x05\x00":
            return None
        s.sendall(b"\x05\x01\x00\x01" + socket.inet_aton(host) + struct.pack("!H", port))
        rep = s.recv(10)
        s.close()
        return (time.perf_counter() - t0) * 1000 if len(rep) >= 2 and rep[1] == 0 else None
    except OSError:
        return None


class Scene:
    def __init__(self, browser, name, http_credentials=None):
        RAW.mkdir(parents=True, exist_ok=True)
        self.name, self.marks, self.t0 = name, [], None
        self.ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, record_video_dir=str(RAW / "_tmp"),
                                       record_video_size={"width": 1920, "height": 1080}, ignore_https_errors=True,
                                       proxy={"server": f"socks5://{PROXY[0]}:{PROXY[1]}", "bypass": "fonts.googleapis.com,fonts.gstatic.com,localhost,127.0.0.1"}, locale="fr-FR",
                                       http_credentials=http_credentials)
        self.ctx.add_init_script(CURSOR_JS)
        self.page = self.ctx.new_page()
        self.t0 = time.time()
        self.mx, self.my = 960, 600

    def go(self, url, until="networkidle", timeout=90000):
        """Navigate with retries: the lab proxy sometimes drops the first connection to a page (transient)."""
        for attempt in range(3):
            try:
                return self.page.goto(url, wait_until=until, timeout=timeout)
            except Exception as e:  # noqa: BLE001
                print(f"   retry {url}: {str(e).splitlines()[0][:80]}", flush=True)
                self.page.wait_for_timeout(3000)
        raise RuntimeError(f"cannot open {url}")

    def mark(self, label):
        self.marks.append({"t": round(time.time() - self.t0, 2), "label": label})

    def shot(self, name):
        self.page.screenshot(path=str(SHOTS / f"{name}.png"))
        self.mark(f"shot {name}")

    def wait(self, s):
        self.page.wait_for_timeout(int(s * 1000))

    def glide(self, x, y, pause=0.35):
        d = ((x - self.mx) ** 2 + (y - self.my) ** 2) ** 0.5
        self.page.mouse.move(x, y, steps=max(12, int(d / 18)))
        self.mx, self.my = x, y
        self.wait(pause)

    def glide_to(self, locator, click=False, pause=0.5):
        try:   # pages that refresh themselves (Zabbix lists) can replace the element under the pointer
            locator.scroll_into_view_if_needed(timeout=3000)
            b = locator.bounding_box(timeout=3000)
        except Exception:  # noqa: BLE001
            return
        if not b:
            return
        self.glide(b["x"] + b["width"] * random.uniform(0.35, 0.6), b["y"] + b["height"] / 2, 0.25)
        if click:
            self.page.mouse.down()
            self.wait(0.08)
            self.page.mouse.up()
        self.wait(pause)

    def type_into(self, locator, text):
        self.glide_to(locator, click=True, pause=0.2)
        for ch in text:
            self.page.keyboard.type(ch)
            self.wait(random.uniform(0.045, 0.11))

    def close(self):
        v = self.page.video
        self.ctx.close()
        dst = RAW / f"{self.name}.webm"
        if dst.exists():
            dst.unlink()
        Path(v.path()).rename(dst)
        (RAW / f"{self.name}.json").write_text(json.dumps({"scene": self.name, "marks": self.marks}, indent=1), encoding="utf-8")
        print(f"   {self.name}: {dst.name}, {len(self.marks)} marks", flush=True)


class Term:
    """The terminal page inside a Scene."""

    def __init__(self, sc, title, where="ADMIN-WS (VLAN 90)"):
        self.sc, self.p = sc, sc.page
        self.p.set_content(TERM_HTML.format(fonts=FONTS, title=escape(title), where=escape(where)))
        self.p.evaluate("document.fonts.ready")
        self.sc.wait(0.6)

    def title(self, t):
        self.p.evaluate("t => document.getElementById('title').textContent = t", t)

    def typed(self, prompt, cmd):
        self.p.evaluate("p => prompt(p)", prompt)
        self.sc.wait(0.5)
        for ch in cmd:
            self.p.evaluate("c => key(c)", ch)
            time.sleep(random.uniform(0.035, 0.095) + (0.08 if ch == " " else 0))
        self.sc.wait(0.45)
        self.p.evaluate("enter()")

    def show(self, text, per_line=0.03, cls=None):
        for ln in text.replace("\r", "").split("\n"):
            self.p.evaluate("([t, c]) => print(t, c)", [ln, cls])
            time.sleep(per_line)

    def run_ssh(self, items, pause=2.5):
        """items [(alias, prompt, command)]: type, run for real over SSH from ADMIN-WS, print the real output."""
        res = adminws.ssh_batch([(a, c) for a, _, c in items], timeout=40)
        for (a, prompt, c), (rc, o) in zip(items, res):
            self.typed(prompt, c)
            self.show(o)
            self.sc.wait(pause)

    def run_local(self, prompt, cmd, argv, pause=3):
        """Type, then run a lab script on the PC and stream its real output line by line."""
        self.typed(prompt, cmd)
        p = subprocess.Popen(argv, cwd=NET, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding="utf-8", errors="replace", env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
        for ln in p.stdout:
            ln = ln.rstrip("\n")
            cls = "ok" if ln.startswith(("OK", "PASS")) else "ko" if ln.startswith(("FAIL",)) else None
            self.p.evaluate("([t, c]) => print(t, c)", [ln, cls])
        p.wait()
        self.sc.wait(pause)
        return p.returncode


# ------------------------------------------------------------------------------------------------ scenes
def login_zabbix(sc):
    pg = sc.page
    sc.go("http://10.60.0.11/index.php", until="domcontentloaded")
    sc.wait(1)
    sc.type_into(pg.locator("#name"), "Admin")
    pg.fill("#password", CRED["zabbix_admin_password"])
    with pg.expect_navigation(timeout=120000):
        sc.glide_to(pg.locator("#enter"), click=True)
    pg.wait_for_load_state("networkidle", timeout=120000)


def topology_html():
    """Live view of the GNS3 project drawn from the controller API: positions, links, zone drawings, node status."""
    api = labctl.Gns3()
    p = api.project()
    pid = p["project_id"]
    nodes = api.nodes(p)
    links = api.req("GET", f"/projects/{pid}/links")
    draws = api.req("GET", f"/projects/{pid}/drawings")
    ip = {n: d["mgmt"]["ip"] for n, d in INV["devices"].items()} | {n: s["ip"] for n, s in INV["servers"].items()}
    tia = {n: d["tia"] for n, d in INV["devices"].items()} | {n: s["tia"] for n, s in INV["servers"].items()}
    xs = [n["x"] for n in nodes] + [d["x"] for d in draws]
    ys = [n["y"] for n in nodes] + [d["y"] for d in draws]
    minx, miny = min(xs) - 60, min(ys) - 60
    w = max([n["x"] + n["width"] for n in nodes] + [d["x"] + int(re.search(r'width="(\d+)', d["svg"]).group(1)) for d in draws
                                                    if re.search(r'width="(\d+)', d["svg"])]) - minx + 60
    h = max(n["y"] + n["height"] for n in nodes) - miny + 120
    pos = {n["node_id"]: (n["x"] - minx + n["width"] / 2, n["y"] - miny + n["height"] / 2) for n in nodes}
    g = []
    for d in sorted(draws, key=lambda d: d["z"]):
        sv = re.sub(r'fill="#0{6}"|fill="#000000"', 'fill="#C9D6DF"', d["svg"]).replace("fill:#000000", "fill:#C9D6DF")
        g.append(f'<g transform="translate({d["x"] - minx},{d["y"] - miny})">{sv}</g>')
    for l in links:
        a, c = pos.get(l["nodes"][0]["node_id"]), pos.get(l["nodes"][1]["node_id"])
        if a and c:
            g.append(f'<line x1="{a[0]}" y1="{a[1]}" x2="{c[0]}" y2="{c[1]}" stroke="#6B7A88" stroke-width="2.4" opacity=".75"/>')
    for n in nodes:
        x, y = pos[n["node_id"]]
        on = n["status"] == "started"
        col = "#4CC38A" if on else "#5A6672"
        tip = f'{n["name"]} · {tia.get(n["name"], n["node_type"])} · {ip.get(n["name"], n["node_type"])} · {"démarré" if on else "arrêté (hors profil)"}'
        g.append(f'<g class="n" data-tip="{escape(tip)}"><rect x="{x - 66}" y="{y - 26}" width="132" height="52" rx="10" fill="#1A232C" '
                 f'stroke="{col}" stroke-width="3"/><circle cx="{x - 50}" cy="{y}" r="8" fill="{col}"/>'
                 f'<text x="{x + 8}" y="{y + 8}" text-anchor="middle" font-family="Inter" font-size="21" font-weight="700" fill="#E8EEF2">'
                 f'{escape(n["name"][:11])}</text></g>')
    on = sum(n["status"] == "started" for n in nodes)
    return f"""<html><head><meta charset="utf-8"><link rel="stylesheet" href="{FONTS}"><style>
html,body{{margin:0;background:#0E1318;font-family:Inter;overflow:hidden}} svg{{position:absolute;left:0;top:76px;transition:transform 1.4s ease}}
.bar{{position:absolute;left:0;right:0;top:0;height:76px;background:#1A232C;display:flex;align-items:center;gap:24px;padding:0 32px;color:#E8EEF2;font-size:26px;font-weight:700;z-index:2}}
.bar i{{font-style:normal;color:#A9B8C4;font-weight:500;font-size:22px}} .bar b{{margin-left:auto;color:#4CC38A}}
#tip{{position:absolute;z-index:3;background:#0B1015;border:2px solid #3FD0E8;border-radius:10px;padding:10px 16px;color:#E8EEF2;font-size:22px;display:none;white-space:nowrap}}
text{{pointer-events:none}}
</style></head><body><div class="bar">Projet GNS3 {escape(p["name"])}<i>vue en direct de l’API du contrôleur GNS3 2.2.56</i>
<b>{on}/{len(nodes)} nœuds démarrés · {len(links)} liens</b></div><div id="tip"></div>
<svg id="s" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{"".join(g)}</svg>
<script>
const s=document.getElementById('s'), tip=document.getElementById('tip');
function fit(){{ const k=Math.min(1920/{w},1004/{h}); s.style.transformOrigin='0 0'; s.style.transform=`scale(${{k}})`; }}
function zoom(cx,cy,k){{ s.style.transform=`translate(${{960-cx*k}}px,${{460-cy*k}}px) scale(${{k}})`; }}
fit();
document.querySelectorAll('.n').forEach(e=>{{ e.addEventListener('mouseenter',ev=>{{tip.textContent=e.dataset.tip; tip.style.display='block';}});
 e.addEventListener('mousemove',ev=>{{tip.style.left=(ev.clientX+24)+'px'; tip.style.top=(ev.clientY+18)+'px';}});
 e.addEventListener('mouseleave',()=>tip.style.display='none'); }});
window.__pos={json.dumps({n["name"]: pos[n["node_id"]] for n in nodes})};
</script></body></html>"""


def s1_topology(b):
    sc = Scene(b, "S1_topology")
    pg = sc.page
    pg.set_content(topology_html())
    pg.evaluate("document.fonts.ready")
    sc.wait(2.5)
    sc.mark("overview")
    sc.shot("30_gns3_topology_zones")
    for name, k in [("FW-A", 1.6), ("CORE-A", 1.6), ("LEAF-B1", 1.4)]:
        x, y = pg.evaluate(f"window.__pos['{name}']")
        pg.evaluate(f"zoom({x},{y},{k})")
        sc.mark(f"zoom {name}")
        sc.wait(1.8)
        for nm in [n for n in ("ISP-A", "EDGE-A", "FW-A", "FW-B", "CORE-A", "CORE-B", "LEAF-B1", "LEAF-B2", "SRV-MON-01", "SYSLOG")]:
            el = pg.locator(f'.n[data-tip^="{nm} "] rect')
            bb = el.bounding_box() if el.count() else None
            if bb and 80 < bb["x"] < 1800 and 120 < bb["y"] < 1000:
                sc.glide(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2, pause=1.1)
        sc.wait(0.8)
    pg.evaluate("fit()")
    sc.wait(2.5)
    sc.close()


def s3_network(b):
    sc = Scene(b, "S3_network")
    t = Term(sc, "Réseau – redondance de bout en bout")
    sc.mark("bgp")
    t.run_ssh([("edge-a", "EDGE-A#", "show ip bgp summary | begin Neighbor")])
    sc.mark("hsrp")
    t.run_ssh([("core-a", "CORE-A#", "show standby brief | begin Interface")])
    sc.shot("32v_core-a_hsrp_video")
    sc.mark("ospf")
    t.run_ssh([("core-a", "CORE-A#", "show ip ospf neighbor"), ("core-a", "CORE-A#", "show etherchannel summary | begin Group")])
    sc.mark("trunk")
    t.run_ssh([("leaf-b1", "LEAF-B1#", "show interfaces trunk | begin Vlans allowed and active")], pause=3)
    sc.close()


def s4_firewall(b):
    sc = Scene(b, "S4_firewall")
    pg = sc.page
    sc.go("https://10.90.0.1/", until="domcontentloaded")
    sc.wait(1.2)
    sc.type_into(pg.locator("#usernamefld"), "admin")
    pg.fill("#passwordfld", CRED["admin_password"])
    sc.glide_to(pg.locator("button[name=login], input[name=login]").first, click=True)
    pg.wait_for_load_state("networkidle", timeout=120000)
    sc.mark("dashboard")
    sc.wait(2)
    for url, label, rows in [("status_carp.php", "carp", "table tbody tr"), ("firewall_rules.php?if=opt2", "rules", "table tbody tr"),
                             ("firewall_nat.php", "nat", "table tbody tr"), ("status_logs_filter.php", "logs", "table tbody tr")]:
        sc.go(f"https://10.90.0.1/{url}", until="networkidle")
        sc.mark(label)
        sc.wait(1.2)
        trs = pg.locator(rows)
        for i in range(min(trs.count(), 5)):
            sc.glide_to(trs.nth(i), pause=0.45)
        if label == "carp":
            sc.shot("21v_fw-a_carp_video")
        sc.wait(1.5)
    sc.close()


def s5_services(b):
    sc = Scene(b, "S5_services")
    t = Term(sc, "Services – site public par le NAT, base de données", "ISP-A (Internet) puis ADMIN-WS")
    sc.mark("web")
    t.typed("root@isp-a:~#", "printf 'GET /health HTTP/1.0\\r\\n\\r\\n' | nc -w 5 192.0.2.80 80")
    out = gns3vm.run("docker exec $(docker ps -q --filter name=ISP-A) sh -c \"printf 'GET /health HTTP/1.0\\r\\n\\r\\n' | nc -w 5 192.0.2.80 80\"", sudo=True)
    t.show(out.strip())
    sc.wait(3)
    sc.mark("acl")
    t.run_ssh([("srv-mon-01", "sysadmin@srv-mon-01:~$", "nc -zv -w 3 10.90.0.12 22; echo \"code retour $?\""),
               ("core-a", "CORE-A#", "show ip access-lists ACL-VLAN60-IN | include deny")], pause=3)
    sc.close()


def s6_noc(b):
    sc = Scene(b, "S6_noc")
    pg = sc.page
    login_zabbix(sc)
    sc.go("http://10.60.0.11/zabbix.php?action=host.view", until="networkidle")
    sc.mark("zabbix hosts")
    trs = pg.locator("table.list-table tbody tr")
    for i in range(0, min(trs.count(), 18), 2):
        sc.glide_to(trs.nth(i), pause=0.3)
    sc.go("http://10.60.0.11/zabbix.php?action=problem.view&filter_reset=1", until="networkidle")
    sc.mark("zabbix problems")
    sc.wait(2.5)
    sc.close()


def s6b_grafana(b):
    # a fresh browser context: after the Zabbix pages the Grafana login did not load through the lab proxy (twice)
    sc = Scene(b, "S6b_grafana")
    pg = sc.page
    sc.go("http://10.60.0.11:3000/login", until="domcontentloaded", timeout=200000)  # ~34 s server side through the proxy
    sc.wait(1.5)
    sc.type_into(pg.locator("input[name=user]"), "admin")
    pg.fill("input[name=password]", CRED["grafana_admin_password"])
    pg.keyboard.press("Enter")
    pg.wait_for_url(lambda u: "/login" not in u, timeout=300000)
    pg.wait_for_load_state("networkidle", timeout=300000)
    pg.locator(".react-grid-item").first.wait_for(timeout=200000)
    sc.wait(6)
    sc.mark("start")   # edit.py starts the clip here: the login and the slow first load are cut
    sc.mark("grafana")
    for sel in [".react-grid-item"]:
        items = pg.locator(sel)
        for i in range(min(items.count(), 9)):
            sc.glide_to(items.nth(i), pause=0.5)
    sc.shot("46v_grafana_noc_video")
    sc.go("http://10.70.0.12:8080/", until="networkidle")
    sc.mark("bms")
    sc.wait(3)
    sc.go("http://10.70.0.11:8080/", until="networkidle")
    sc.mark("dcim")
    sc.wait(3)
    sc.close()


def failover(b, name, node, title, host, port, hold=60, back=False):
    """Stop `node` through the GNS3 API while a probe asks host:port every 0.5 s; draw timer and outage."""
    sc = Scene(b, name)
    t = Term(sc, title, f"sonde ADMIN-WS → {host}:{port} toutes les 0,5 s")
    api = labctl.Gns3()
    pr = api.project()
    rows, stop = [], {"t": None}
    t.show(f"# sonde TCP {host}:{port} depuis ADMIN-WS, toutes les 0,5 s", cls="dim")
    t0 = time.time()
    lost_since, outages = None, []

    def panel(state, colour):
        el = time.time() - t0
        ttxt = f"{el:5.1f}".replace(".", ",")
        msr = "" if not outages else f"<div class='lbl'>coupure mesurée</div><div class='big' style='color:#4CC38A'>{outages[-1]:.1f} s</div>".replace(".", ",")
        t.p.evaluate("h => panel(h)", f"<div class='lbl'>chrono</div><div class='big'>{ttxt} s</div>"
                                      f"<div class='lbl'>{escape(node)}</div><div class='st' style='color:{colour}'>{state}</div>{msr}")

    def stopper():
        time.sleep(6)
        stop["t"] = time.time()
        api.stop(pr, api.node(pr, node))

    threading.Thread(target=stopper, daemon=True).start()
    sc.mark("probe start")
    while time.time() - t0 < hold:
        ms = socks_tcp(host, port, timeout=0.45)
        now = time.time()
        stamp = time.strftime("%H:%M:%S", time.localtime(now)) + f".{int(now * 10) % 10}"
        if ms is None:
            lost_since = lost_since or now
            t.p.evaluate("([t, c]) => print(t, c)", [f"{stamp}  {host}:{port}  pas de réponse", "ko"])
        else:
            if lost_since:
                outages.append(now - lost_since)
                sc.mark(f"outage {outages[-1]:.1f}s")
                lost_since = None
            t.p.evaluate("([t, c]) => print(t, c)", [f"{stamp}  {host}:{port}  ouvert  {ms:4.0f} ms", "ok"])
        state = "en marche" if stop["t"] is None else "ARRÊTÉ (API GNS3)"
        panel(state, "#4CC38A" if stop["t"] is None else "#E5675F")
        time.sleep(max(0, 0.5 - (time.time() - now)))
        if outages and time.time() - (stop["t"] or now) > 25:
            break
    sc.shot(f"{name.lower()}_outage")
    sc.wait(2)
    sc.close()
    print(f"   {node} outages: {[round(o, 1) for o in outages]}", flush=True)
    if back:
        api.start(pr, api.node(pr, node))
        print(f"   {node} restarted (boot takes minutes)", flush=True)
    return outages


def s8_t2(b):
    return failover(b, "S8_T2_fw", "FW-A", "T2 – arrêt du pare-feu maître FW-A", "10.70.0.12", 8080, back=True)


def s8_t6(b):
    sc = Scene(b, "S8_T6_power")
    pg = sc.page
    sc.go("http://10.70.0.12:8080/", until="networkidle")
    sc.mark("bms nominal")
    sc.wait(3)
    import urllib.request  # noqa: F401  (the API call goes through the proxy like the page)
    import http.client
    sys.path.insert(0, str(HERE.parent))
    from zabbix_setup import SocksHTTPConnection
    con = SocksHTTPConnection("10.70.0.12", 8080, timeout=10)
    con.request("GET", "/api/set?UTILITY-A=DOWN&UPS-A=DOWN&GENERATOR=DOWN")
    con.getresponse().read()
    con.close()
    sc.mark("cut path A")
    for _ in range(4):
        sc.wait(2.5)
        pg.reload(wait_until="networkidle")
    sc.shot("58v_t6_bms_video")
    sc.go("http://10.70.0.11:8080/", until="networkidle")
    sc.mark("dcim degraded")
    sc.wait(4)
    con = SocksHTTPConnection("10.70.0.12", 8080, timeout=10)
    con.request("GET", "/api/reset")
    con.getresponse().read()
    con.close()
    sc.mark("reset")
    sc.wait(3)
    pg.reload(wait_until="networkidle")
    sc.wait(3)
    sc.close()


def s9_proof(b):
    sc = Scene(b, "S9_proof")
    t = Term(sc, "Preuve – 12 contrôles avant la démonstration", "PC hôte, dossier 03_Network")
    sc.mark("demo_check")
    t.run_local("PS 03_Network>", "python automation/demo_check.py", [sys.executable, "automation/demo_check.py"], pause=4)
    sc.shot("59v_demo_check_video")
    sc.close()


SCENES = {"S1": s1_topology, "S3": s3_network, "S4": s4_firewall, "S5": s5_services, "S6": s6_noc, "S6b": s6b_grafana, "S8T2": s8_t2, "S8T6": s8_t6, "S9": s9_proof}


def main(argv):
    if "--list" in argv or not argv:
        print("scenes:", " ".join(SCENES))
        return
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        for s in argv:
            print(time.strftime("%H:%M:%S"), "recording", s, flush=True)
            SCENES[s](b)
        b.close()


if __name__ == "__main__":
    main(sys.argv[1:])
