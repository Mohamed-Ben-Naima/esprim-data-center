"""Demo-day guide: running nodes, dashboards, verification commands (demo profile).
  python report/_source/build_demo_guide.py  ->  report/DEMO_GUIDE.pdf (+ .html)
Commands come from report/tests/tests.yaml, so they match what verify_lab.py runs."""
import html
import subprocess
from pathlib import Path

import yaml

NET = Path(__file__).resolve().parents[2]
TESTS = yaml.safe_load((NET / "report/tests/tests.yaml").read_text(encoding="utf-8"))["sections"]
E = html.escape
ON = [("NAT-A, NAT-B", "GNS3 NAT clouds", "real Internet exit"), ("ISP-A, ISP-B", "ISP simulators", "eBGP providers"),
      ("EDGE-A", "Cisco IOSv router", "Internet border, BGP"), ("SW-OUT, SW-IN, SW-DMZ, SW-MGMT", "GNS3 switches",
      "transit 901 / 902, DMZ, management"), ("FW-A, FW-B", "pfSense", "firewall pair, CARP"),
      ("CORE-A, CORE-B", "Cisco IOSvL2", "L3 core, HSRP gateways"), ("LEAF-B1, LEAF-B2", "Cisco IOSvL2",
      "hall B access switches"), ("ADMIN-WS", "Docker desktop", "admin workstation (VLAN 90)"),
      ("SRV-MON-01", "Ubuntu VM", "Zabbix + Grafana"), ("SYSLOG", "Docker", "central logs + log viewer"),
      ("BMS-SIM", "Docker", "power simulator"), ("SRV-DCIM-01", "Docker", "DCIM, 96 racks"),
      ("SRV-WEB-01", "Docker", "public web site in the DMZ")]
OFF = [("LEAF-A1, LEAF-A2, SRV-CMP-01/02/03, SRV-STO-01", "hall A (profile compute)"), ("EDGE-B", "second edge"),
       ("SRV-INF-01", "DNS/NTP"), ("SRV-BCK-01", "TrueNAS backup (profile nas)"), ("SRV-BASTION", "bastion"),
       ("CCTV-SIM", "CCTV simulator")]
SECTIONS = ["DEMO", "EDGE", "FW", "CORE", "ADM", "LOG", "MON", "WEB", "PWR"]
OFFNAMES = ["LEAF-A1", "LEAF-A2", "SRV-CMP", "SRV-STO", "EDGE-B", "SRV-INF", "SRV-BCK", "SRV-BASTION", "CCTV",
            "bastion", "srv-cmp", "fw_lan_failover", "--disruptive"]


def usable(t):
    blob = f"{t.get('from', '')} {t.get('command', '')}"
    return not any(o in blob for o in OFFNAMES)


def build():
    on = "".join(f"<tr><td><b>{E(a)}</b></td><td>{E(b)}</td><td>{E(c)}</td></tr>" for a, b, c in ON)
    off = "".join(f"<tr><td><b>{E(a)}</b></td><td>{E(b)}</td></tr>" for a, b in OFF)
    tests = ""
    for sec in TESTS:
        if sec["id"] not in SECTIONS:
            continue
        rows = "".join(
            f"<li><b>{E(t['id'])}</b>: {E(str(t.get('proves', '')))}<br><span class=l>Where</span>{E(str(t.get('from', '')))}"
            f"<pre>{E(str(t.get('command', '')))}</pre><span class=l>Expect</span>{E(str(t.get('expected', '')))}</li>"
            for t in sec["tests"] if usable(t))
        if rows:
            tests += f"<h3>{E(sec['id'])}: {E(sec['title'])}</h3><ol>{rows}</ol>"
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Demo day guide</title><style>
@page{{size:A4;margin:13mm}} body{{font:10.5pt/1.5 "Segoe UI",system-ui,sans-serif;color:#17201d;max-width:900px;margin:auto;padding:0 16px}}
h1{{font-size:24pt;margin:0 0 4px;color:#0f7b6c}} h2{{border-bottom:2px solid #0f7b6c;padding-bottom:3px;margin-top:22px;break-after:avoid}}
h3{{margin:16px 0 6px;break-after:avoid}} table{{border-collapse:collapse;width:100%;margin:6px 0}}
td,th{{border:1px solid #d5dcd9;padding:4px 7px;text-align:left;vertical-align:top}} th{{background:#e3efe9}}
pre,code{{font-family:Consolas,monospace;background:#eaefed;border-radius:4px}} pre{{padding:6px 9px;white-space:pre-wrap;margin:4px 0}}
code{{padding:0 4px}} li{{margin-bottom:8px;break-inside:avoid}} .l{{font:600 8.5pt Consolas;color:#5b6964;margin-right:6px;text-transform:uppercase}}
.box{{background:#e3efe9;border-left:4px solid #0f7b6c;padding:8px 12px;margin:8px 0}} .warn{{background:#fbe9e3;border-color:#b5482c}}
</style></head><body>
<h1>Demo day guide</h1><p>DC Casablanca lab, profile <b>demo</b>. Passwords: <code>DEMO_RUNBOOK.md</code> section 2 or
<code>inventory/dc_casa.yaml</code> (credentials).</p>

<h2>1. What must run before anything</h2>
<ol><li><b>VMware</b>: start <b>GNS3 VM</b>, wait for IP <code>192.168.75.128</code>.</li>
<li><b>GNS3 app</b>: open project <code>DC_Casablanca_TIA942_R3</code>. Do <b>not</b> start nodes by hand.</li>
<li><b>PowerShell</b> in <code>C:\\Users\\ASUS\\Documents\\ESPRIM\\Data Center\\03_Network</code>:
<pre>python automation/lab_up.py --profile demo     # starts the 20 nodes below, about 12 min
python automation/demo_check.py                 # expect "12/12 checks OK"</pre></li></ol>

<h2>2. Nodes in the demo profile</h2>
<h3>Running (green in GNS3)</h3><table><tr><th>Node</th><th>Type</th><th>Role</th></tr>{on}</table>
<h3>Stopped on purpose (laptop RAM)</h3><table><tr><th>Node</th><th>Why off</th></tr>{off}</table>
<div class="box">Grafana shows these as "out of profile" and Zabbix has them in maintenance <code>demo-off</code>. That is
normal: say it is a RAM limit of the laptop. Hall A runs with <code>--profile compute</code>, TrueNAS with
<code>--profile nas</code>.</div>

<h2>3. Open the dashboards</h2>
<p><b>Option A (fastest), from the Windows host.</b> In PowerShell:</p>
<pre>python automation/lab_proxy.py open</pre>
<p>An Edge window opens that browses as if it were ADMIN-WS. Accept the certificate warnings, then:</p>
<table><tr><th>What</th><th>URL</th><th>Login</th></tr>
<tr><td><b>Grafana NOC dashboard</b> (home page)</td><td><code>http://10.60.0.11:3000/</code></td><td>admin</td></tr>
<tr><td>Zabbix, Monitoring &gt; Problems</td><td><code>http://10.60.0.11/</code></td><td>Admin</td></tr>
<tr><td>Central logs (read only)</td><td><code>https://10.60.0.12/</code></td><td>netadmin</td></tr>
<tr><td>pfSense, current master</td><td><code>https://10.90.0.1/</code></td><td>admin</td></tr>
<tr><td>BMS power simulator</td><td><code>http://10.70.0.12:8080/</code></td><td>none</td></tr>
<tr><td>DCIM racks</td><td><code>http://10.70.0.11:8080/</code></td><td>none</td></tr>
<tr><td>Web site (DMZ)</td><td><code>https://10.50.0.11/</code></td><td>none</td></tr></table>
<p><b>Option B, the real admin desktop.</b> In GNS3 double-click <b>ADMIN-WS</b> (VNC). Firefox opens on the portal with
every link. Its terminal is where you type <code>ssh core-a</code>, <code>ssh fw-a</code>, etc.</p>
<div class="box warn">Edge shows nothing? Run <code>python automation/lab_proxy.py start</code> then <code>open</code> again.
Grafana panel empty right after boot? Wait 5 min and rerun <code>demo_check.py</code>.</div>

<h2>4. Quick checks on the Cisco devices (ADMIN-WS terminal)</h2>
<table><tr><th>Type in ADMIN-WS terminal</th><th>What you should see</th></tr>
<tr><td><code>ssh core-a</code> then <code>show standby brief</code></td><td>CORE-A Active for VLAN 20, 40, 60, 100, 902; Standby for 30, 70, 80</td></tr>
<tr><td><code>show ip ospf neighbor</code></td><td>2 neighbours FULL (Vlan998, Vlan902)</td></tr>
<tr><td><code>show etherchannel summary</code></td><td>Po1(SU), 2 ports (P)</td></tr>
<tr><td><code>show interfaces trunk</code></td><td>trunks to the leafs and to CORE-B</td></tr>
<tr><td><code>ssh edge-a</code> then <code>show ip bgp summary</code></td><td>BGP session to ISP-A established (prefixes received)</td></tr>
<tr><td><code>ssh leaf-b1</code> then <code>show spanning-tree summary</code></td><td>mode rapid-pvst</td></tr></table>
<p>Same thing from PowerShell without the desktop: <code>python automation/adminws.py core-a "show standby brief"</code></p>

<h2>5. All verification commands for this profile</h2>
<p>Run them all at once (about 10 min, PowerShell): <code>python automation/verify_lab.py</code>
(last result: 59 PASS, 0 FAIL). Never use <code>--disruptive</code> just before the demo.</p>
{tests}
<h2>6. When finished</h2><pre>python automation/lab_down.py</pre><p>Then close the project in GNS3 and stop the GNS3 VM.</p>
</body></html>"""
    h = NET / "report/DEMO_GUIDE.html"
    h.write_text(page, encoding="utf-8")
    pdf = NET / "report/DEMO_GUIDE.pdf"
    subprocess.run([r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "--headless=new", "--disable-gpu",
                    "--no-pdf-header-footer", f"--print-to-pdf={pdf}", h.as_uri()], check=True, capture_output=True)
    print(pdf, pdf.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    build()
