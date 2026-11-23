"""Screenshots of the live lab for the deck (PLAN_05 D10): terminal captures and browser pages.

  python automation/demo_video/shots.py [32 33 ... | term | web]

Terminal shots: the command runs for real on the equipment over SSH from ADMIN-WS (adminws.ssh_batch, the
administrator's path) or in a container of the GNS3 VM; its output is drawn in a terminal window (Edge + JetBrains
Mono) with the time it ran. Nothing is typed by hand or edited.
Browser shots: Playwright drives the installed Edge through the lab proxy (SOCKS5 on ADMIN-WS), 1920x1080.
Output: 03_Network/screenshots/<nn>_<node>_<what>.png (same names as PLAN_05 "Screenshots").
"""
import html
import sys
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import adminws  # noqa: E402
import gns3vm  # noqa: E402

NET = HERE.parents[1]
SHOTS = NET / "screenshots"
INV = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
CRED = INV["credentials"]
PROXY = {"server": "socks5://192.168.75.128:1080"}
FONTS = "https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@500;700&display=swap"

# nn, file, title, [(alias, prompt, command)]  - alias "@<container>" = docker exec in the GNS3 VM
TERM = {
    "32": ("32_core-a_hsrp_ospf", "CORE-A – passerelles HSRP et voisins OSPF",
           [("core-a", "CORE-A#", "show standby brief"), ("core-a", "CORE-A#", "show ip ospf neighbor")]),
    "33": ("33_edge-a_bgp", "EDGE-A – sessions eBGP vers les deux opérateurs",
           [("edge-a", "EDGE-A#", "show ip bgp summary | begin Neighbor"), ("edge-a", "EDGE-A#", "show standby brief | begin Interface")]),
    "34": ("34_core-a_etherchannel_stp", "CORE-A – Port-channel LACP et racines Rapid-PVST+",
           [("core-a", "CORE-A#", "show etherchannel summary | begin Group"), ("core-a", "CORE-A#", "show spanning-tree root | exclude ^$")]),
    "35": ("35_leaf-b1_vlan_trunks", "LEAF-B1 – trunks 802.1Q vers les deux cœurs",
           [("leaf-b1", "LEAF-B1#", "show interfaces trunk | begin Vlans allowed and active"),
            ("leaf-b1", "LEAF-B1#", "show spanning-tree vlan 60 | begin Interface")]),
    "38": ("38_isp-a_web_via_nat", "Internet (ISP-A) – le site DMZ joint par l'adresse publique 192.0.2.80",
           [("@ISP-A", "root@isp-a:~#", "printf 'GET /health HTTP/1.0\\r\\n\\r\\n' | nc -w 5 192.0.2.80 80")]),
    "42": ("42_srv-mon-01_mariadb_zabbix_db", "SRV-MON-01 – base MariaDB de Zabbix",
           [("srv-mon-01", "sysadmin@srv-mon-01:~$",
             "mysql -t -e \"SELECT table_schema AS base, COUNT(*) AS tables, "
             "ROUND(SUM(data_length+index_length)/1048576) AS Mo FROM information_schema.tables "
             "WHERE table_schema='zabbix' GROUP BY table_schema; SELECT COUNT(*) AS hotes_supervises FROM zabbix.hosts "
             "WHERE status=0 AND flags=0; SELECT VERSION() AS mariadb;\"")]),
    "43": ("43_core_acl_denied", "ACL du cœur – flux VLAN 60 → administration refusé et compté",
           [("srv-mon-01", "sysadmin@srv-mon-01:~$", "nc -zv -w 3 10.90.0.12 22; echo \"code retour $?\""),
            ("core-a", "CORE-A#", "show ip access-lists ACL-VLAN60-IN | include deny")]),
}

# evidence traces drawn as a terminal (nodes off in the demo profile); the title carries the date of the run
EVID = {
    "53t": ("53t_truenas_restore_trace", "SRV-BCK-01 – test de restauration (trace du 10/11/2026)", "nas5_restore.txt", "type report/evidence/nas5_restore.txt"),
    "31t": ("31t_bastion_totp_trace", "SRV-BASTION – second facteur TOTP (trace du 12/10/2026)", "adm4_accounts_totp.txt", "type report/evidence/adm4_accounts_totp.txt"),
}

WEB = {
    "44": ("44_zabbix_problems", "http://10.60.0.11/zabbix.php?action=problem.view&filter_reset=1", "zabbix"),
    "45": ("45_zabbix_hosts", "http://10.60.0.11/zabbix.php?action=host.view", "zabbix"),
    "46": ("46_grafana_noc", "http://10.60.0.11:3000/", "grafana"),
    "47": ("47_syslog_viewer", "https://10.60.0.12/", "viewer"),
    "49": ("49_bms_power_paths", "http://10.70.0.12:8080/", None),
    "50": ("50_dcim_racks", "http://10.70.0.11:8080/", None),
}


def run_term(items):
    ssh = [(a, c) for a, _, c in items if not a.startswith("@")]
    res = iter(adminws.ssh_batch(ssh, timeout=40)) if ssh else iter(())
    out = []
    for a, prompt, c in items:
        if a.startswith("@"):
            o = gns3vm.run(f"docker exec $(docker ps -q --filter name={a[1:]}) sh -c {sh_quote(c)}", sudo=True)
            out.append((prompt, c, o.replace("\r", "").rstrip()))
        else:
            rc, o = next(res)
            out.append((prompt, c, o))
    return out


def sh_quote(s):
    return "'" + s.replace("'", "'\\''") + "'"


def term_html(title, blocks, stamp):
    body = []
    for prompt, cmd, out in blocks:
        body.append(f'<span class="p">{html.escape(prompt)}</span> <span class="c">{html.escape(cmd)}</span>')
        body.append(html.escape(out))
    return f"""<html><head><link rel="stylesheet" href="{FONTS}"><style>
body{{margin:0;background:#0B1015;padding:24px;width:1240px;font-family:'JetBrains Mono',Consolas,monospace}}
.w{{background:#11171D;border:1px solid #2C3742;border-radius:14px;overflow:hidden;box-shadow:0 20px 60px #000a}}
.t{{display:flex;align-items:center;gap:10px;background:#1A232C;padding:14px 20px;font-family:Inter,Arial;font-size:20px;color:#A9B8C4}}
.d{{width:14px;height:14px;border-radius:7px}} .t b{{color:#E8EEF2;margin-left:12px}} .t i{{margin-left:auto;font-style:normal}}
pre{{margin:0;padding:22px 26px;font-size:23px;line-height:1.4;color:#D5DEE5;white-space:pre-wrap}}
.p{{color:#3FD0E8;font-weight:700}} .c{{color:#F0F4F7;font-weight:700}}
</style></head><body><div class="w"><div class="t"><span class="d" style="background:#E5675F"></span>
<span class="d" style="background:#F0AD4E"></span><span class="d" style="background:#4CC38A"></span>
<b>{html.escape(title)}</b><i>ADMIN-WS (VLAN 90) · {stamp}</i></div><pre>{chr(10).join(body)}</pre></div></body></html>"""


def my_cnf(on):
    """Shot 42: a temporary ~/.my.cnf on SRV-MON-01. The DB secret travels as a file (adminws.put), never on a
    command line (ADMIN-WS logs command lines to syslog); removed right after the shot."""
    if on:
        import tempfile
        f = Path(tempfile.gettempdir()) / "dc_my.cnf"
        f.write_text(f"[client]\nuser=zabbix\npassword={CRED['zabbix_db_password']}\n", encoding="utf-8")
        adminws.put("srv-mon-01", f, ".my.cnf")
        f.unlink()
        adminws.ssh_batch([("srv-mon-01", "chmod 600 .my.cnf")])
    else:
        adminws.ssh_batch([("srv-mon-01", "rm -f .my.cnf")])


def shoot_term(keys, pg):
    for k in keys:
        name, title, items = TERM[k]
        if k == "42":
            my_cnf(True)
        try:
            blocks = run_term(items)
        finally:
            if k == "42":
                my_cnf(False)
        stamp = time.strftime("%d/%m/%Y %H:%M")
        pg.set_viewport_size({"width": 1288, "height": 400})
        pg.set_content(term_html(title, blocks, stamp))
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(300)
        pg.locator("body").screenshot(path=str(SHOTS / f"{name}.png"))
        print("ok", name, "|", " / ".join(b[2].splitlines()[-1][:60] if b[2] else "(vide)" for b in blocks), flush=True)


def shoot_evid(keys, pg):
    for k in keys:
        name, title, f, cmd = EVID[k]
        text = (NET / "report" / "evidence" / f).read_text(encoding="utf-8").rstrip()
        pg.set_viewport_size({"width": 1288, "height": 400})
        pg.set_content(term_html(title, [("PS 03_Network>", cmd, text)], "report/evidence/" + f))
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(300)
        pg.locator("body").screenshot(path=str(SHOTS / f"{name}.png"))
        print("ok", name, flush=True)


def login(pg, kind):
    if kind == "zabbix":
        pg.goto("http://10.60.0.11/index.php", wait_until="domcontentloaded", timeout=120000)
        pg.fill("#name", "Admin")
        pg.fill("#password", CRED["zabbix_admin_password"])
        pg.click("#enter")
    elif kind == "grafana":
        pg.goto("http://10.60.0.11:3000/login", wait_until="domcontentloaded", timeout=120000)
        pg.fill("input[name=user]", "admin")
        pg.fill("input[name=password]", CRED["grafana_admin_password"])
        pg.keyboard.press("Enter")
        pg.wait_for_url(lambda u: "/login" not in u, timeout=120000)
    elif kind == "viewer":
        pg.goto("https://10.60.0.12/", wait_until="domcontentloaded", timeout=120000)
        pg.fill("input[type=text], input[name=user], input[name=username]", CRED["admin_user"])
        pg.fill("input[type=password]", CRED["admin_password"])
        pg.keyboard.press("Enter")
    elif kind == "pfsense":
        pg.goto("https://10.90.0.1/", wait_until="domcontentloaded", timeout=120000)
        pg.fill("#usernamefld", "admin")
        pg.fill("#passwordfld", CRED["admin_password"])
        pg.click("button[name=login], input[name=login]")
    pg.wait_for_load_state("networkidle", timeout=120000)


def shoot_web(keys, browser):
    done = set()
    # 1366x768 at 1.5x: the page text is ~40 % larger in the picture than at 1920 wide, readable on a slide
    ctx = browser.new_context(viewport={"width": 1366, "height": 768}, device_scale_factor=1.5, ignore_https_errors=True,
                              proxy=PROXY, locale="fr-FR")
    pg = ctx.new_page()
    for k in keys:
        name, url, kind = WEB[k]
        if kind and kind not in done:
            login(pg, kind)
            done.add(kind)
        for attempt in range(3):
            try:
                pg.goto(url, wait_until="networkidle", timeout=120000)
                break
            except Exception as e:  # noqa: BLE001  a client-side redirect can abort the first navigation
                print("   retry", name, str(e).splitlines()[0], flush=True)
                pg.wait_for_timeout(3000)
        pg.wait_for_timeout(6000 if kind == "grafana" else 1500)
        pg.screenshot(path=str(SHOTS / f"{name}.png"))
        print("ok", name, pg.title(), flush=True)
    ctx.close()


def main(argv):
    from playwright.sync_api import sync_playwright
    keys = argv or list(TERM) + list(WEB)
    if keys == ["term"]:
        keys = list(TERM)
    if keys == ["web"]:
        keys = list(WEB)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        t = [k for k in keys if k in TERM]
        if t:
            pg = b.new_page(device_scale_factor=1)
            shoot_term(t, pg)
        e = [k for k in keys if k in EVID]
        if e:
            shoot_evid(e, b.new_page())
        w = [k for k in keys if k in WEB]
        if w:
            shoot_web(w, b)
        b.close()


if __name__ == "__main__":
    main(sys.argv[1:])
