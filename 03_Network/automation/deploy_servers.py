"""Phase 6 – configure the Ubuntu server VMs through their serial consoles (idempotent).

  python automation/deploy_servers.py SRV-INF-01 [SRV-MON-01 ...]   (default: all VM servers in the inventory)
  python automation/deploy_servers.py --base-only SRV-CMP-01           (network/system only, no role packages)
  python automation/deploy_servers.py --accounts-only SRV-INF-01       (administration account and SSH policy only)
  python automation/deploy_servers.py --role=grafana SRV-MON-01        (re-run one role only, packages already there)

Base (every VM): hostname, timezone, netplan (bond0 active-backup on the two NICs, or single NIC), cloud-init
network config disabled, journald -> rsyslog forwarding to SYSLOG, NTP via systemd-timesyncd -> SRV-INF-01.
Roles (packages come from the real Internet through FW SNAT 192.0.2.10): see ROLE_SCRIPTS.
"""
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import labctl  # noqa: E402

NET = Path(__file__).resolve().parents[1]
INV = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
S, SITE = INV["services"], INV["site"]


def grafana_role():
    """Grafana (PLAN_02 GRF.1–GRF.4): settings as GF_* variables of the service (no anonymous access, no sign-up,
    root_url, timezone), Zabbix plugin unpacked from its zip (offline, sha256 checked), data source and app enabled by
    the provisioning files of grafana/provisioning/, dashboards of grafana/dashboards/. The data source password is passed in the service environment."""
    g, c, mon = INV["monitoring"]["grafana"], INV["credentials"], INV["monitoring"]
    pl = g["plugin"]
    prov = "".join(
        f"cat > /etc/grafana/provisioning/{f.parent.name}/{f.name} <<'EOF'\n{f.read_text(encoding='utf-8')}EOF\n"
        f"chown root:grafana /etc/grafana/provisioning/{f.parent.name}/{f.name}; "
        f"chmod 0640 /etc/grafana/provisioning/{f.parent.name}/{f.name}\n"
        for f in sorted((NET / "grafana" / "provisioning").glob("*/*.yaml")))
    # dashboards sent compact (the role script travels over the serial console)
    boards = "mkdir -p /var/lib/grafana/dashboards/dc\n" + "".join(
        f"cat > /var/lib/grafana/dashboards/dc/{f.name} <<'DCJSON'\n"
        f"{json.dumps(json.loads(f.read_text(encoding='utf-8')), ensure_ascii=False, separators=(',', ':'))}\nDCJSON\n"
        for f in sorted((NET / "grafana" / "dashboards").glob("*.json"))) + \
        "chown -R root:grafana /var/lib/grafana/dashboards; chmod -R u=rwX,g=rX,o= /var/lib/grafana/dashboards\n"
    return f"""export DEBIAN_FRONTEND=noninteractive
dpkg -s grafana >/dev/null 2>&1 || apt-get install -y -q grafana >/dev/null
sed -i -e 's/^;\\?http_port = .*/http_port = 3000/' -e 's/^;\\?admin_password = .*/admin_password = {c['grafana_admin_password']}/' /etc/grafana/grafana.ini
# settings: one marked block in the service environment file (re-run = same block)
sed -i '/^# >>> dc-casa/,/^# <<< dc-casa/d' /etc/default/grafana-server
cat >> /etc/default/grafana-server <<'EOF'
# >>> dc-casa (automation/deploy_servers.py, PLAN_02 GRF.1-GRF.3)
GF_SERVER_ROOT_URL={g['root_url']}
GF_USERS_ALLOW_SIGN_UP=false
GF_AUTH_ANONYMOUS_ENABLED=false
GF_DATE_FORMATS_DEFAULT_TIMEZONE={mon['timezone']}
GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH=/var/lib/grafana/dashboards/dc/{g['home_dashboard']}
ZABBIX_GRAFANA_PASSWORD={c['zabbix_grafana_password']}
# <<< dc-casa
EOF
chown root:grafana /etc/default/grafana-server; chmod 0640 /etc/default/grafana-server
# Zabbix plugin, offline: repository ISO first, else a copy left in /tmp (the lab Internet path is too slow)
D=/var/lib/grafana/plugins/{pl['id']}
have=$(python3 -c "import json; print(json.load(open('$D/plugin.json'))['info']['version'])" 2>/dev/null || true)
if [ "$have" != "{pl['version']}" ]; then
  src=$(ls /mnt/dcrepo/plugins/{pl['zip']} /tmp/{pl['zip']} 2>/dev/null | head -1)
  if [ -z "$src" ]; then echo "plugin zip {pl['zip']} not found"; exit 1; fi
  echo "{pl['sha256']}  $src" | sha256sum -c --quiet
  rm -rf "$D"; mkdir -p /var/lib/grafana/plugins
  python3 -m zipfile -e "$src" /var/lib/grafana/plugins/
  chmod 0755 "$D"/datasource/gpx_*; chown -R grafana:grafana "$D"
  echo "plugin {pl['id']} {pl['version']} installed from $src"
fi
# provisioning (data source, app, dashboards) and the dashboards themselves
{prov}{boards}systemctl daemon-reload; systemctl enable grafana-server >/dev/null 2>&1; systemctl restart grafana-server
for i in $(seq 1 60); do curl -s -m2 http://127.0.0.1:3000/api/health | grep -q '"ok"' && break; sleep 2; done
systemctl is-active grafana-server"""


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
    timeout = 5   # a client that stalls (TLS handshake or request) frees its thread after 5 s
s = http.server.ThreadingHTTPServer(("0.0.0.0", 8443), H)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain("/opt/app/cert.pem", "/opt/app/key.pem")
# handshake in the worker thread, not in accept(): one stalled client froze the whole server (T5, keepalived FAULT)
s.socket = ctx.wrap_socket(s.socket, server_side=True, do_handshake_on_connect=False); s.serve_forever()
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
systemctl daemon-reload && systemctl enable --now dc-app iperf3-server && systemctl restart dc-app""",
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
    "zabbix-agent": f"""DEBIAN_FRONTEND=noninteractive apt-get install -y -q zabbix-agent >/dev/null
sed -i -e 's/^Server=.*/Server={S['monitoring']}/' -e 's/^ServerActive=.*/ServerActive={S['monitoring']}/' \\
       -e "s/^Hostname=.*/Hostname=$(hostname | tr a-z A-Z)/" /etc/zabbix/zabbix_agentd.conf
systemctl enable zabbix-agent >/dev/null 2>&1; systemctl restart zabbix-agent""",
    "zabbix": f"""export DEBIAN_FRONTEND=noninteractive
apt-get install -y -q mariadb-server zabbix-server-mysql zabbix-frontend-php zabbix-nginx-conf zabbix-sql-scripts \\
    php7.4-fpm php7.4-mysql nginx >/dev/null
systemctl enable --now mariadb
mysql -e "CREATE DATABASE IF NOT EXISTS zabbix CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
          CREATE USER IF NOT EXISTS 'zabbix'@'localhost' IDENTIFIED BY '{INV['credentials']['zabbix_db_password']}';
          GRANT ALL PRIVILEGES ON zabbix.* TO 'zabbix'@'localhost'; SET GLOBAL log_bin_trust_function_creators = 1;"
if ! mysql -N -e "SELECT 1 FROM zabbix.users LIMIT 1" >/dev/null 2>&1; then
  zcat /usr/share/zabbix-sql-scripts/mysql/server.sql.gz | mysql --default-character-set=utf8mb4 -uzabbix -p'{INV['credentials']['zabbix_db_password']}' zabbix
fi
mysql -e "SET GLOBAL log_bin_trust_function_creators = 0;"
sed -i "s/^# DBPassword=.*/DBPassword={INV['credentials']['zabbix_db_password']}/" /etc/zabbix/zabbix_server.conf
# Ubuntu 20.04 ships MariaDB 10.3; Zabbix 6.0 refuses to start below 10.5 unless told otherwise (lab only)
grep -q '^AllowUnsupportedDBVersions=1' /etc/zabbix/zabbix_server.conf || echo 'AllowUnsupportedDBVersions=1' >> /etc/zabbix/zabbix_server.conf
sed -i -e 's/^#\\?\\s*listen\\s.*;/        listen 80;/' -e 's/^#\\?\\s*server_name\\s.*;/        server_name zabbix.{SITE['domain']} {S['monitoring']};/' /etc/zabbix/nginx.conf
rm -f /etc/nginx/sites-enabled/default
cat > /etc/zabbix/web/zabbix.conf.php <<'PHPEOF'
<?php
$DB['TYPE'] = 'MYSQL'; $DB['SERVER'] = 'localhost'; $DB['PORT'] = '0'; $DB['DATABASE'] = 'zabbix';
$DB['USER'] = 'zabbix'; $DB['PASSWORD'] = '{INV['credentials']['zabbix_db_password']}'; $DB['SCHEMA'] = '';
$DB['ENCRYPTION'] = false; $DB['KEY_FILE'] = ''; $DB['CERT_FILE'] = ''; $DB['CA_FILE'] = ''; $DB['VERIFY_HOST'] = false;
$DB['CIPHER_LIST'] = ''; $DB['VAULT_URL'] = ''; $DB['VAULT_DB_PATH'] = ''; $DB['VAULT_TOKEN'] = ''; $DB['DOUBLE_IEEE754'] = true;
$ZBX_SERVER_NAME = 'DC Casablanca NOC';
$IMAGE_FORMAT_DEFAULT = IMAGE_FORMAT_PNG;
PHPEOF
chown www-data:www-data /etc/zabbix/web/zabbix.conf.php
systemctl enable zabbix-server nginx php7.4-fpm >/dev/null 2>&1
systemctl restart zabbix-server php7.4-fpm nginx
sleep 3; systemctl is-active zabbix-server nginx mariadb""",
    "grafana": grafana_role(),
}


def keepalived(prio):
    vip = INV["servers"]["SRV-CMP-01"]["vip"]
    return f"""DEBIAN_FRONTEND=noninteractive apt-get install -y -q keepalived >/dev/null
cat > /etc/keepalived/keepalived.conf <<'EOF'
vrrp_script chk_app {{ script "/usr/bin/curl -sk -m 1 https://127.0.0.1:8443/" interval 2 timeout 2 fall 2 rise 2 init_fail }}
# preempt_delay 30 (like HSRP preempt delay on the cores, PLAN_01 T5): a master that boots takes the VIP back only
# once its bond has validated both NICs; without it, failback cost 10.6 s (VIP taken while the bond was settling)
vrrp_instance APP {{
    state BACKUP
    interface bond0
    virtual_router_id 20
    priority {prio}
    preempt_delay 30
    advert_int 1
    # no 'authentication': keepalived 2.0.19 ignored it ("no password given"), and VRRPv2 PASS is cleartext, removed
    # from RFC 3768; the segment is protected by VLAN 20 itself (servers only) and ACL-VLAN20-IN on the cores
    virtual_ipaddress {{ {vip}/24 }}
    track_script {{ chk_app }}
}}
EOF
# keepalived waits for the network: at boot the bond ARP monitor takes 10-15 s to validate the NICs; started earlier,
# the node heard no advert, declared itself MASTER while the other held the VIP (split brain, 10-15 s outage, T5).
# Both NICs 'up' is not enough (they start up and fail ARP validation ~7 s later): the proof is hearing the master.
cat > /usr/local/sbin/wait-bond.sh <<'EOF'
#!/bin/sh
# 1) bond0 and both NICs up 5 s in a row (at most 90 s)
ok=0
for i in $(seq 1 90); do
  if [ "$(grep -c 'MII Status: up' /proc/net/bonding/bond0 2>/dev/null)" -ge 3 ]; then ok=$((ok+1)); else ok=0; fi
  [ $ok -ge 5 ] && break
  sleep 1
done
# 2) 3 VRRP adverts heard on bond0 = a master exists and reaches us; none within 60 s (both nodes starting) = elect
timeout 60 tcpdump -c 3 -ni bond0 'ip proto 112' >/dev/null 2>&1
exit 0
EOF
chmod 755 /usr/local/sbin/wait-bond.sh
mkdir -p /etc/systemd/system/keepalived.service.d
printf '[Service]\\nExecStartPre=/usr/local/sbin/wait-bond.sh\\nTimeoutStartSec=120\\n' > /etc/systemd/system/keepalived.service.d/wait-bond.conf
systemctl daemon-reload
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


def accounts_script(name, s):
    """Administration account (PLAN_02 ADM.4, ISO/IEC 27001 A.5.17, A.8.5): a named account with the inventory password,
    SSH closed to the image default account (its console login stays, the lab driver uses it) and, on the server that
    carries the role `mfa`, a TOTP second factor enforced by PAM (password, then verification code)."""
    c = INV["credentials"]
    u = c["server_admin_user"]
    sshd = "# DC Casablanca - administration by the named account only (generated by deploy_servers.py)\nDenyUsers ubuntu\n"
    mfa = ""
    if "mfa" in s["roles"]:
        sshd += "ChallengeResponseAuthentication yes\nAuthenticationMethods keyboard-interactive\nPasswordAuthentication no\n"
        mfa = f"""cat > /home/{u}/.google_authenticator <<'EOF'
{c['bastion_totp_secret']}
" RATE_LIMIT 3 30
" WINDOW_SIZE 3
" DISALLOW_REUSE
" TOTP_AUTH
EOF
chown {u}:{u} /home/{u}/.google_authenticator && chmod 0600 /home/{u}/.google_authenticator
grep -q pam_google_authenticator /etc/pam.d/sshd || sed -i '/^@include common-auth/a auth required pam_google_authenticator.so' /etc/pam.d/sshd
"""
    else:
        sshd += "PasswordAuthentication yes\n"
    return f"""set -e
id {u} >/dev/null 2>&1 || useradd -m -s /bin/bash -G sudo {u}
echo '{u}:{c['server_admin_password']}' | chpasswd
{mfa}printf '{sshd}' > /etc/ssh/sshd_config.d/10-dc-casa.conf
grep -q '^Include /etc/ssh/sshd_config.d' /etc/ssh/sshd_config || sed -i '1i Include /etc/ssh/sshd_config.d/*.conf' /etc/ssh/sshd_config
sshd -t
systemctl reload ssh
echo accounts-ok
"""


def accounts(lx, name, s):
    lx.put_file("/root/accounts.sh", accounts_script(name, s), "700")
    rc, out = lx.run("bash /root/accounts.sh 2>&1 | tail -3; r=${PIPESTATUS[0]}; rm -f /root/accounts.sh; (exit $r)", 120)
    print(f"[{name}] administration account: rc={rc} {out.strip()[-120:]}", flush=True)
    return rc


PULL_KEY = NET / "configs" / "servers" / "SRV-BCK-01.backup_pull.pub"   # written by truenas_setup.py apply


def backup_source(name):
    """PLAN_04 NAS.5: read-only source for the backups the NAS pulls (rsync over SSH). Account `pull_user` with no
    password; its only key is the NAS key, usable from the NAS address only, and forced to `sudo rrsync -ro /`
    (rsync as sender only: no write, no delete, no shell). On SRV-MON-01 a nightly dump of the Zabbix database and
    the Grafana data lands in /var/backups/dc (01:30), before the 02:00 pull."""
    if not PULL_KEY.exists():
        raise SystemExit(f"{PULL_KEY} missing: run `python automation/truenas_setup.py apply` first")
    T = INV["truenas"]
    u, nas = T["pull_user"], INV["servers"]["SRV-BCK-01"]["ip"]
    key = PULL_KEY.read_text(encoding="utf-8").strip()
    dump = ""
    if "zabbix" in INV["servers"][name]["roles"]:
        dump = """mkdir -p /var/backups/dc && chmod 0700 /var/backups/dc
cat > /usr/local/sbin/dc-dump.sh <<'EOF'
#!/bin/sh
# nightly dump for the NAS pull (PLAN_04 NAS.5): Zabbix database + Grafana data, kept 1 copy (history is on the NAS)
set -e
umask 077
mysqldump --single-transaction --quick zabbix | gzip -1 > /var/backups/dc/zabbix.sql.gz.tmp
mv /var/backups/dc/zabbix.sql.gz.tmp /var/backups/dc/zabbix.sql.gz
# Grafana writes its SQLite DB continuously: exit code 1 ("file changed as we read it") is accepted
# plugins and plugins-bundled (~390 MB) come with the package: only the Grafana database and state are kept
tar --warning=no-file-changed --exclude=./plugins --exclude=./plugins-bundled -czf /var/backups/dc/grafana.tar.gz.tmp -C /var/lib/grafana . || [ $? -eq 1 ]
mv /var/backups/dc/grafana.tar.gz.tmp /var/backups/dc/grafana.tar.gz
sha256sum /var/backups/dc/*.gz > /var/backups/dc/SHA256SUMS
EOF
chmod 0700 /usr/local/sbin/dc-dump.sh
echo '30 1 * * * root /usr/local/sbin/dc-dump.sh' > /etc/cron.d/dc-dump
/usr/local/sbin/dc-dump.sh && ls -la /var/backups/dc
"""
    return f"""[ -x /usr/bin/rrsync ] && RR=/usr/bin/rrsync || {{ zcat /usr/share/doc/rsync/scripts/rrsync.gz > /usr/local/bin/rrsync; chmod 0755 /usr/local/bin/rrsync; RR=/usr/local/bin/rrsync; }}
id {u} >/dev/null 2>&1 || useradd -r -m -d /var/lib/{u} -s /bin/sh -c "NAS backup pull (read-only)" {u}
passwd -l {u} >/dev/null
install -d -m 0700 -o {u} -g {u} /var/lib/{u}/.ssh
echo 'restrict,from="{nas}",command="sudo -n '$RR' -ro /" {key}' > /var/lib/{u}/.ssh/authorized_keys
chown {u}:{u} /var/lib/{u}/.ssh/authorized_keys && chmod 0600 /var/lib/{u}/.ssh/authorized_keys
printf 'Defaults!%s env_keep += "SSH_ORIGINAL_COMMAND"\\n{u} ALL=(root) NOPASSWD: %s -ro /\\n' $RR $RR > /etc/sudoers.d/90-{u}
chmod 0440 /etc/sudoers.d/90-{u} && visudo -cf /etc/sudoers.d/90-{u}
{dump}echo backup-source-ok"""


def run_role(lx, name, role):
    print(f"[{name}] role {role} ...", flush=True)
    if role.startswith("keepalived"):
        body = keepalived(150 if role.endswith("master") else 100)
    elif role == "backup-source":
        body = backup_source(name)
    else:
        body = ROLE_SCRIPTS.get(role, "true")
    lx.put_file("/root/role.sh", "set -e\n" + body + "\n", "700")
    # the script holds secrets of the inventory: removed once run
    rc, out = lx.run("bash /root/role.sh > /root/role.log 2>&1; r=$?; tail -4 /root/role.log; rm -f /root/role.sh; (exit $r)", 1500)
    print(f"[{name}] role {role}: rc={rc} {out[-300:]}")
    return rc


def deploy(api, p, name, base_only=False, accounts_only=False, roles=None):
    s = INV["servers"][name]
    tmpl, script = base_script(name, s)
    with labctl.Console.for_node(api, p, name) as c:
        lx = labctl.Linux(c)
        lx.login()
        if accounts_only:
            accounts(lx, name, s)
            return
        if roles:
            for role in roles:
                run_role(lx, name, role)
            return
        rc, nics = lx.run("ls /sys/class/net | grep -E '^(ens|eth|enp)' | sort | tr '\\n' ' '")
        nics = nics.split()
        netplan = tmpl.replace("{nic0}", nics[0]).replace("{nic1}", nics[1] if len(nics) > 1 else nics[0])
        lx.put_file("/etc/netplan/60-dc-casa.yaml", netplan, "600")
        print(f"[{name}] base system ...", flush=True)
        for line in script.splitlines():
            lx.run(line)
        rc, out = lx.run("netplan apply && sleep 4 && ip -br -4 addr | grep -v lo", 90)
        print(f"[{name}] nics={nics} netplan rc={rc}\n{out}")
        rc, gw = lx.run(f"ping -c 2 -W 2 {INV['vlans'][s['vlan']]['vip']} | tail -1")
        print(f"[{name}] gateway: {gw}")
        accounts(lx, name, s)
        if base_only:
            return
        rc, inet = lx.run("ping -c 2 -W 3 8.8.8.8 | tail -1")
        print(f"[{name}] internet: {inet}")
        # bootstrap resolvers while installing packages (SRV-INF-01 cannot resolve through itself yet)
        lx.run("rm -f /etc/resolv.conf; echo 'nameserver 1.1.1.1' > /etc/resolv.conf; echo 'nameserver 8.8.8.8' >> /etc/resolv.conf")
        # preferred source: the offline repository disk (ISO labelled DCREPO attached as the second disk, built by
        # automation/build_repo.sh); fallback: kernel.org mirror over the lab Internet path, IPv4 only
        rc, _ = lx.run("blkid -L DCREPO >/dev/null 2>&1 || blkid /dev/vdb 2>/dev/null | grep -q DCREPO")
        if rc == 0:
            lx.run("mkdir -p /mnt/dcrepo; mountpoint -q /mnt/dcrepo || mount -o ro $(blkid -L DCREPO || echo /dev/vdb) /mnt/dcrepo")
            lx.run("grep -q dcrepo /etc/fstab || echo 'LABEL=DCREPO /mnt/dcrepo iso9660 ro,nofail 0 0' >> /etc/fstab")
            lx.put_file("/etc/apt/sources.list", "deb [trusted=yes] file:/mnt/dcrepo ./\n")
            print(f"[{name}] package source: offline repository DCREPO", flush=True)
        else:
            lx.put_file("/etc/apt/sources.list", "\n".join(
                f"deb http://mirrors.edge.kernel.org/ubuntu focal{suite} main universe"
                for suite in ("", "-security")) + "\n")
            print(f"[{name}] package source: network mirror", flush=True)
        # the lab path (IOSv / pfSense software forwarding) gives a few hundred KB/s: keep the indexes small
        lx.put_file("/etc/apt/apt.conf.d/99dc-lab",
                    'Acquire::ForceIPv4 "true";\nAcquire::Languages "none";\nAcquire::Retries "3";\nDPkg::Lock::Timeout "900";\n')
        # automatic upgrades would hold the dpkg lock for a long time over the slow lab path
        # (--no-block: never wait for an upgrade in progress; installs below wait for the dpkg lock instead)
        lx.run("systemctl disable --now --no-block unattended-upgrades apt-daily.timer apt-daily-upgrade.timer >/dev/null 2>&1; true")
        # an upgrade already started at boot keeps the dpkg lock for a long time: SIGTERM makes it finish the
        # current package and exit cleanly (checked afterwards with dpkg --audit)
        lx.run("pkill -TERM -f unattended-upgrade; for i in $(seq 1 30); do pgrep -f unattended-upgrade >/dev/null || break; sleep 5; done; dpkg --audit", 200)
        # the boot-time 'apt-daily' index refresh holds /var/lib/apt/lists/lock: it only downloads indexes,
        # so it is safe to stop before running our own update
        lx.run("systemctl stop apt-daily.service >/dev/null 2>&1; pkill -TERM -f 'apt.systemd.daily|apt-get -qq -y update|apt-get update'; sleep 3; true", 60)
        rc, out = lx.run("DEBIAN_FRONTEND=noninteractive apt-get update -q > /root/apt.log 2>&1; echo apt-update-rc=$?; grep -c '^Err' /root/apt.log", 1500)
        print(f"[{name}] {out}")
        for role in s["roles"] + ["zabbix-agent"]:
            run_role(lx, name, role)
        # final resolver: internal DNS (dnsmasq on SRV-INF-01 manages its own resolv.conf)
        if "dns" not in s["roles"]:
            lx.run("ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf")
        rc, out = lx.run("getent hosts deb.debian.org >/dev/null && echo dns-ok; timedatectl show -p NTPSynchronized --value")
        print(f"[{name}] final: {out}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # console output can hold UTF-8 (apt arrows)
    args = sys.argv[1:]
    base_only = "--base-only" in args
    accounts_only = "--accounts-only" in args
    roles = [r for a in args if a.startswith("--role=") for r in a.split("=", 1)[1].split(",")]
    names = [a for a in args if not a.startswith("--")] or [n for n, s in INV["servers"].items()
                                                         if s["kind"] == "vm" and s.get("platform") != "truenas"]
    api = labctl.Gns3()
    p = api.project()
    for n in names:
        deploy(api, p, n, base_only, accounts_only, roles)
