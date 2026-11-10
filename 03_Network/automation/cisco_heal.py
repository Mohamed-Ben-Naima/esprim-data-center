"""cisco_heal – after a boot, put back what IOSvL2 keeps outside the configuration (PLAN_03 S6).

  python automation/cisco_heal.py [NODE ...]        (default: every running Cisco device; lab_up.py calls it)
  python automation/cisco_heal.py --check [NODE...] (report only)

IOS stores the RSA host key and the SNMPv3 users in nvram:private-config, not in the startup configuration. On the
emulated IOSvL2 a power-off (GNS3 stop) can leave a private-config that is not loaded at the next boot (seen on
LEAF-B2 on 21 Oct and CORE-A on 10 Nov 2026): the device then boots with SSH disabled ("Please create RSA keys") and
answers SNMPv3 with "Unknown user name", while its running configuration looks complete.
For each device the script checks `show ip ssh` and `show snmp user` on the serial console and, if needed, pushes the
lines of configs/<NODE>.cfg that recreate them (crypto key generate rsa ..., snmp-server user ...), then
`write memory` so a fresh private-config is written. Devices are handled in parallel (one console each).
A new RSA key means a new SSH host key: the old one pinned in ADMIN-WS known_hosts is removed (ssh-keygen -R), only
for a key this script made itself over the console, so the next session from ADMIN-WS learns the new key
(StrictHostKeyChecking accept-new) instead of refusing with "REMOTE HOST IDENTIFICATION HAS CHANGED".
"""
import re
import sys
import threading
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import gns3vm  # noqa: E402
import labctl  # noqa: E402

NET = Path(__file__).resolve().parents[1]
INV = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
OUT = {}


def heal(api, p, name, fix):
    u, pw, en = labctl.creds()
    cfg = (NET / "configs" / f"{name}.cfg").read_text(encoding="utf-8").splitlines()
    try:
        with labctl.Console.for_node(api, p, name) as c:
            ios = labctl.Ios(c, u, pw, en)
            ios.login(timeout=300)
            ssh_ok = "SSH Enabled" in ios.cmd("show ip ssh")
            want_user = INV["credentials"]["snmpv3_user"]
            names = set(re.findall(r"User name: (\S+)", ios.cmd("show snmp user")))   # exact names (zbxmon is in zbxmon2)
            snmp_ok = want_user in names
            hosts = [l.strip() for l in ios.cmd("show running-config | include ^snmp-server host").splitlines()
                     if l.startswith("snmp-server host")]
            lines = []
            if not ssh_ok:
                lines += [l for l in cfg if l.startswith("crypto key generate rsa")]
            # the user name carries the key version (rotated with the keys): any other user is an old one, removed
            old = sorted(names - {want_user})
            if not snmp_ok:
                lines += [l for l in cfg if l.startswith(f"snmp-server user {want_user} ")]
            lines += [f"no snmp-server user {o} G-MONITORING v3" for o in old]
            # trap destinations name the user too: old ones removed, the configuration's ones put back
            want_hosts = [l for l in cfg if l.startswith("snmp-server host")]
            lines += [f"no {h}" for h in hosts if h not in want_hosts]
            lines += [h for h in want_hosts if h not in hosts]
            state = (f"ssh {'ok' if ssh_ok else 'DISABLED'}, snmpv3 user {'ok' if snmp_ok else 'MISSING'}"
                     + (f", old user(s) {', '.join(old)}" if old else "")
                     + (", trap host updated" if any("snmp-server host" in l for l in lines) else ""))
            if lines and fix:
                errs = ios.push_config("\n".join(lines))
                ios.save()
                ssh_ok = "SSH Enabled" in ios.cmd("show ip ssh")
                names = set(re.findall(r"User name: (\S+)", ios.cmd("show snmp user")))
                snmp_ok = names == {want_user}
                state += f" -> repaired ({len(lines)} line(s), {len(errs)} rejected, saved): " \
                         f"ssh {'ok' if ssh_ok else 'STILL DISABLED'}, snmpv3 {'ok' if snmp_ok else 'STILL MISSING'}"
            if fix and any(l.startswith("crypto key") for l in lines):
                ip = INV["devices"][name]["mgmt"]["ip"]
                gns3vm.run("a=$(docker ps -q --filter name=ADMIN-WS); [ -n \"$a\" ] && docker exec $a sh -c "
                           f"'ssh-keygen -R {ip} >/dev/null 2>&1; ssh-keygen -R {name.lower()} >/dev/null 2>&1'", sudo=True)
                state += "; old host key removed from ADMIN-WS known_hosts"
            OUT[name] = (ssh_ok and snmp_ok and (fix or not old), state)
    except Exception as e:  # noqa: BLE001
        OUT[name] = (False, f"console error: {e}")


def main(argv):
    fix = "--check" not in argv
    names = [a for a in argv if not a.startswith("--")]
    api = labctl.Gns3()
    p = api.project()
    started = {n["name"] for n in api.nodes(p) if n["status"] == "started"}
    cisco = [n for n, d in INV["devices"].items() if not n.startswith("FW-")]
    todo = [n for n in (names or cisco) if n in started]
    jobs = [threading.Thread(target=heal, args=(api, p, n, fix)) for n in todo]
    for j in jobs:
        j.start()
    for j in jobs:
        j.join(900)
    for n in todo:
        ok, state = OUT.get(n, (False, "no answer"))
        print(f"{'OK  ' if ok else 'FAIL'} {n:8} {state}")
    return 0 if all(OUT.get(n, (False,))[0] for n in todo) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
