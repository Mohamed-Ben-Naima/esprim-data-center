"""Phase 6 – configure the Ubuntu server VMs through their serial consoles (idempotent).

  python automation/deploy_servers.py SRV-INF-01 [SRV-MON-01 ...]   (default: all VM servers in the inventory)
  python automation/deploy_servers.py --base-only SRV-CMP-01           (network/system only, no role packages)

Base (every VM): hostname, timezone, netplan (bond0 active-backup on the two NICs, or single NIC), cloud-init
network config disabled, journald -> rsyslog forwarding to SYSLOG, NTP via systemd-timesyncd -> SRV-INF-01.
Roles (packages come from the real Internet through FW SNAT 192.0.2.10): see ROLE_SCRIPTS.
"""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import labctl  # noqa: E402

NET = Path(__file__).resolve().parents[1]
INV = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
S, SITE = INV["services"], INV["site"]

ROLE_SCRIPTS = {
    "dns": f"""DEBIAN_FRONTEND=noninteractive apt-get install -y -q dnsmasq >/dev/null
cat > /etc/dnsmasq.d/dc-casa.conf <<'EOF'
# SRV-INF-01 – internal DNS for {SITE['domain']} (forwarders: public resolvers through the firewall)
domain-needed
bogus-priv
no-resolv
server=1.1.1.1
server=8.8.8.8
domain={SITE['domain']}
local=/{SITE['domain']}/
expand-hosts
listen-address=127.0.0.1,{S['dns']}
bind-interfaces
EOF
systemctl disable --now systemd-resolved >/dev/null 2>&1; rm -f /etc/resolv.conf; echo 'nameserver 127.0.0.1' > /etc/resolv.conf
systemctl enable --now dnsmasq && systemctl restart dnsmasq""",
    "ntp": f"""DEBIAN_FRONTEND=noninteractive apt-get install -y -q chrony >/dev/null
grep -q 'dc-casa' /etc/chrony/chrony.conf || cat >> /etc/chrony/chrony.conf <<'EOF'
# dc-casa: SRV-INF-01 is the NTP server of the whole lab (ISO/IEC 27001 A.8.17)
allow 10.0.0.0/8
local stratum 8
EOF
systemctl restart chrony""",
    "dhcp": "true   # DHCP pool for VLAN 100 provided by dnsmasq when needed (static addressing in the lab)",
    "nfs": """DEBIAN_FRONTEND=noninteractive apt-get install -y -q nfs-kernel-server >/dev/null
mkdir -p /srv/nfs/share && chmod 0775 /srv/nfs/share
echo '/srv/nfs/share 10.20.0.0/24(rw,sync,no_subtree_check,root_squash)' > /etc/exports
exportfs -ra && systemctl enable --now nfs-server""",
    "iscsi": """DEBIAN_FRONTEND=noninteractive apt-get install -y -q tgt >/dev/null
mkdir -p /srv/iscsi && [ -f /srv/iscsi/lun0.img ] || truncate -s 1G /srv/iscsi/lun0.img
cat > /etc/tgt/conf.d/dc-casa.conf <<'EOF'
<target iqn.2026-10.lab.casa.dc:sto01.lun0>
    backing-store /srv/iscsi/lun0.img
    initiator-address 10.20.0.0/24
</target>
EOF
systemctl restart tgt""",
    "backup-rsyncd": """DEBIAN_FRONTEND=noninteractive apt-get install -y -q rsync >/dev/null
mkdir -p /srv/backup && chmod 0750 /srv/backup
cat > /etc/rsyncd.conf <<'EOF'
# SRV-BCK-01 – backup agent endpoint (PDF Table 18: servers -> backup agent port)
uid = root
gid = root
use chroot = yes
max connections = 8
log file = /var/log/rsyncd.log
[backup]
    path = /srv/backup
    read only = no
    hosts allow = 10.20.0.0/24 10.30.0.0/24
    hosts deny = *
EOF
systemctl enable --now rsync""",
    "app-8443": """DEBIAN_FRONTEND=noninteractive apt-get install -y -q python3 openssl iperf3 >/dev/null
mkdir -p /opt/app && cd /opt/app && [ -f cert.pem ] || openssl req -x509 -nodes -newkey rsa:2048 -days 825 -subj "/CN=$(hostname).dc.casa.lab" -keyout key.pem -out cert.pem 2>/dev/null
cat > /opt/app/app.py <<'EOF'
import http.server, ssl, socket, json, time
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        b = json.dumps({"service": "app", "host": socket.gethostname(), "time": time.strftime("%H:%M:%S")}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
s = http.server.ThreadingHTTPServer(("0.0.0.0", 8443), H)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain("/opt/app/cert.pem", "/opt/app/key.pem")
s.socket = ctx.wrap_socket(s.socket, server_side=True); s.serve_forever()
EOF
cat > /etc/systemd/system/dc-app.service <<'EOF'
[Unit]
Description=DC Casablanca demo application (HTTPS 8443)
After=network-online.target
[Service]
ExecStart=/usr/bin/python3 /opt/app/app.py
Restart=always
[Install]
WantedBy=multi-user.target
EOF
cat > /etc/systemd/system/iperf3-server.service <<'EOF'
[Unit]
Description=iperf3 server (resilience tests)
[Service]
ExecStart=/usr/bin/iperf3 -s
Restart=always
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload && systemctl enable --now dc-app iperf3-server""",
    "iperf3": "true",
    "keepalived-master": "KA_PRIO=150",
    "keepalived-backup": "KA_PRIO=100",
    "bastion": f"""DEBIAN_FRONTEND=noninteractive apt-get install -y -q libpam-google-authenticator auditd >/dev/null
sed -i 's/^#\\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
grep -q '^AllowGroups' /etc/ssh/sshd_config || echo 'AllowGroups sudo' >> /etc/ssh/sshd_config
echo 'Banner /etc/issue.net' >> /etc/ssh/sshd_config
printf 'SRV-BASTION – acces reserve aux administrateurs, sessions journalisees (ISO/IEC 27001 A.8.15)\\n' > /etc/issue.net
systemctl restart ssh; systemctl enable --now auditd""",
    "mfa": "true   # TOTP (pam_google_authenticator) enrolled per administrator, see report",
}


def keepalived(prio):
    vip = INV["servers"]["SRV-CMP-01"]["vip"]
    return f"""DEBIAN_FRONTEND=noninteractive apt-get install -y -q keepalived >/dev/null
cat > /etc/keepalived/keepalived.conf <<'EOF'
vrrp_script chk_app {{ script "/usr/bin/curl -sk -m 2 https://127.0.0.1:8443/" interval 2 fall 2 rise 2 }}
vrrp_instance APP {{
    state BACKUP
    interface bond0
    virtual_router_id 20
    priority {prio}
    advert_int 1
    authentication {{ auth_type PASS auth_pass {INV['credentials']['hsrp_key'][:8]} }}
    virtual_ipaddress {{ {vip}/24 }}
    track_script {{ chk_app }}
}}
EOF
systemctl enable --now keepalived && systemctl restart keepalived"""


def base_script(name, s):
    v = INV["vlans"][s["vlan"]]
    plen = v["subnet"].split("/")[1]
    tmpl = (NET / "configs" / "servers" / f"{name}.netplan.yaml").read_text(encoding="utf-8")
    return tmpl, f"""hostnamectl set-hostname {name.lower()}
grep -q '{name.lower()}' /etc/hosts || echo '127.0.1.1 {name.lower()}.{SITE['domain']} {name.lower()}' >> /etc/hosts
timedatectl set-timezone {SITE['timezone']}
echo 'network: {{config: disabled}}' > /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg
rm -f /etc/netplan/50-cloud-init.yaml
mkdir -p /etc/systemd/timesyncd.conf.d && printf '[Time]\\nNTP={S['ntp']}\\n' > /etc/systemd/timesyncd.conf.d/dc.conf
printf '*.* @{S['syslog']}:514\\n' > /etc/rsyslog.d/90-dc-remote.conf && systemctl restart rsyslog
systemctl restart systemd-timesyncd 2>/dev/null || true"""


def deploy(api, p, name, base_only=False):
    s = INV["servers"][name]
    tmpl, script = base_script(name, s)
    with labctl.Console.for_node(api, p, name) as c:
        lx = labctl.Linux(c)
        lx.login()
        rc, nics = lx.run("ls /sys/class/net | grep -E '^(ens|eth|enp)' | sort | tr '\\n' ' '")
        nics = nics.split()
        netplan = tmpl.replace("{nic0}", nics[0]).replace("{nic1}", nics[1] if len(nics) > 1 else nics[0])
        lx.put_file("/etc/netplan/60-dc-casa.yaml", netplan, "600")
        for line in script.splitlines():
            lx.run(line)
        rc, out = lx.run("netplan apply && sleep 4 && ip -br -4 addr | grep -v lo", 90)
        print(f"[{name}] nics={nics} netplan rc={rc}\n{out}")
        rc, gw = lx.run(f"ping -c 2 -W 2 {INV['vlans'][s['vlan']]['vip']} | tail -1")
        print(f"[{name}] gateway: {gw}")
        if base_only:
            return
        rc, inet = lx.run("ping -c 2 -W 3 8.8.8.8 | tail -1")
        print(f"[{name}] internet: {inet}")
        # bootstrap resolvers while installing packages (SRV-INF-01 cannot resolve through itself yet)
        lx.run("rm -f /etc/resolv.conf; echo 'nameserver 1.1.1.1' > /etc/resolv.conf; echo 'nameserver 8.8.8.8' >> /etc/resolv.conf")
        # archive/security.ubuntu.com are unreachable from the site's upstream: use the kernel.org mirror, IPv4 only
        lx.put_file("/etc/apt/sources.list", "\n".join(
            f"deb http://mirrors.edge.kernel.org/ubuntu focal{suite} main restricted universe multiverse"
            for suite in ("", "-updates", "-security", "-backports")) + "\n")
        lx.run("echo 'Acquire::ForceIPv4 \"true\";' > /etc/apt/apt.conf.d/99force-ipv4")
        rc, out = lx.run("DEBIAN_FRONTEND=noninteractive apt-get update -q > /root/apt.log 2>&1; echo apt-update-rc=$?; grep -c '^Err' /root/apt.log", 600)
        print(f"[{name}] {out}")
        for role in s["roles"]:
            if role.startswith("keepalived"):
                body = keepalived(150 if role.endswith("master") else 100)
            else:
                body = ROLE_SCRIPTS.get(role, "true")
            lx.put_file("/root/role.sh", "set -e\n" + body + "\n", "700")
            rc, out = lx.run("bash /root/role.sh > /root/role.log 2>&1; r=$?; tail -4 /root/role.log; (exit $r)", 900)
            print(f"[{name}] role {role}: rc={rc} {out[-300:]}")
        # final resolver: internal DNS (dnsmasq on SRV-INF-01 manages its own resolv.conf)
        if "dns" not in s["roles"]:
            lx.run("ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf")
        rc, out = lx.run("getent hosts deb.debian.org >/dev/null && echo dns-ok; timedatectl show -p NTPSynchronized --value")
        print(f"[{name}] final: {out}")


if __name__ == "__main__":
    args = sys.argv[1:]
    base_only = "--base-only" in args
    names = [a for a in args if not a.startswith("--")] or [n for n, s in INV["servers"].items() if s["kind"] == "vm"]
    api = labctl.Gns3()
    p = api.project()
    for n in names:
        deploy(api, p, n, base_only)
