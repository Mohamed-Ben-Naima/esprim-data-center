"""Deploy the generated pfSense configuration on the live firewalls, over SSH from ADMIN-WS (PLAN_02 FW.2).

  python automation/gen_pfsense.py                     generate configs/pfsense/FW-A.config.xml, FW-B.config.xml
  python automation/deploy_pfsense.py                  deploy both: the backup firewall first, then the master
  python automation/deploy_pfsense.py FW-B             one firewall only
  python automation/deploy_pfsense.py --rollback FW-B  put back the configuration saved by the last deployment

For each firewall: the generated file is copied to /tmp, its MD5 is compared with the local file and it is checked
with xmllint; the running config.xml is saved as /cf/conf/config.xml.before-deploy; the new file is installed, the
configuration cache is dropped, the leftover first-time-setup trigger is removed, the packet filter is reloaded and the SNMP, syslog
and NTP daemons are regenerated (no reboot). The deployment of a firewall stops at the first step that fails, before the running file is replaced.
Run `python automation/fw_audit.py` afterwards: it must report 0 difference.
"""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import adminws  # noqa: E402

NET = Path(__file__).resolve().parents[1]
ALIAS = {"FW-A": "fw-a", "FW-B": "fw-b"}
ORDER = ["FW-B", "FW-A"]                  # the backup first: a bad file never reaches the master
# rc.filter_configure reloads the rules only: the daemons that read config.xml keep their old settings (the SNMP
# community rotated on 10 Nov 2026 stayed old in bsnmpd, Zabbix timed out). They are regenerated here.
SVC = ("/usr/local/bin/php -r 'require_once(\"config.inc\"); require_once(\"functions.inc\"); require_once(\"services.inc\"); "
       "require_once(\"system.inc\"); foreach ([\"services_snmpd_configure\", \"system_syslogd_start\", \"system_ntp_configure\"] "
       "as $f) { if (function_exists($f)) { $f(); echo \"$f \"; } }'")


def run(alias, command, timeout=90):
    return adminws.ssh_batch([(alias, command)], timeout=timeout)[0]


def deploy(fw):
    alias = ALIAS[fw]
    local = NET / "configs" / "pfsense" / f"{fw}.config.xml"
    md5 = hashlib.md5(local.read_bytes()).hexdigest()
    print(f"== {fw}: {local.name} ({local.stat().st_size} bytes, md5 {md5})")
    if adminws.put(alias, local, "/tmp/config.new") != 0:
        print("   transfer failed"); return False
    rc, out = run(alias, "md5 -q /tmp/config.new; xmllint --noout /tmp/config.new && echo xml-ok; "
                         "grep -c '<hostname>" + fw.lower() + "</hostname>' /tmp/config.new")
    lines = out.split()
    if lines[:1] != [md5] or "xml-ok" not in lines or lines[-1:] != ["1"]:
        print(f"   check failed, nothing installed: {out!r}"); return False
    print("   transferred, checksum identical, XML valid, hostname matches")
    rc, out = run(alias, "cp -p /cf/conf/config.xml /cf/conf/config.xml.before-deploy && cp /tmp/config.new /cf/conf/config.xml "
                         "&& rm -f /tmp/config.cache /tmp/config.new /cf/conf/trigger_initial_wizard && /etc/rc.filter_configure "
                         f"&& {SVC} && sleep 5 && echo installed; pfctl -sr | wc -l; ifconfig | grep -c 'carp:'", timeout=150)
    print("   " + " | ".join(out.split("\n")[-3:]))
    return "installed" in out


def rollback(fw):
    rc, out = run(ALIAS[fw], "test -f /cf/conf/config.xml.before-deploy && cp -p /cf/conf/config.xml.before-deploy /cf/conf/config.xml "
                             f"&& rm -f /tmp/config.cache && /etc/rc.filter_configure && {SVC} && sleep 5 && echo rolled-back; pfctl -sr | wc -l", timeout=150)
    print(f"== {fw}: " + " | ".join(out.split("\n")[-2:]))
    return "rolled-back" in out


if __name__ == "__main__":
    args = sys.argv[1:]
    names = [a for a in args if not a.startswith("--")] or ORDER
    action = rollback if "--rollback" in args else deploy
    for fw in sorted(names, key=ORDER.index):
        if not action(fw):
            sys.exit(f"{fw}: stopped; the firewalls after it were not touched")
