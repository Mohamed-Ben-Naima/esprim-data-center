"""Run commands on lab equipment over SSH from ADMIN-WS, the administration webterm – the path an administrator uses.

  from adminws import ssh_batch
  (rc, out), = ssh_batch([("fw-a", "pfctl -sr | wc -l")])

The aliases are those of configs/docker/ADMIN-WS.ssh_config. Passwords (and the TOTP code of the bastion) come from the
inventory and are answered by an SSH_ASKPASS helper that exists in the webterm only for the duration of the batch.
Every session goes through /usr/local/bin/ssh in the webterm, so it is recorded on the log collector like any other.
"""
import base64
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import gns3vm  # noqa: E402
from totp import TOTP_SOURCE  # noqa: E402

NET = Path(__file__).resolve().parents[1]


def ssh_batch(items, timeout=60):
    """items: [(alias, command)] -> [(exit code, stdout)] in the same order (one VM round trip for the whole batch)."""
    inv = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
    c = inv["credentials"]
    assert all("'" not in c[k] for k in ("admin_password", "server_admin_password", "truenas_admin_password"))
    mfa = {n.lower() for n, s in inv["servers"].items() if "mfa" in s.get("roles", [])} | {"bastion"}
    s = ["c=$(docker ps -q --filter name=ADMIN-WS)", "[ -n \"$c\" ] || { echo '@@NO-ADMIN-WS'; exit 0; }",
         "cat > /tmp/totp_now.py <<'EOP'\n" + TOTP_SOURCE + f"print(totp('{c['bastion_totp_secret']}'))\nEOP",
         "cat > /tmp/ap_adm.sh <<'EOP'\n#!/bin/sh\ncase \"$1\" in\n  *erification*) cat /tmp/totp ;;\n"
         f"  *sysadmin@*) echo '{c['server_admin_password']}' ;;\n"
         f"  *truenas_admin@*) echo '{c['truenas_admin_password']}' ;;\n  *) echo '{c['admin_password']}' ;;\nesac\nEOP",
         "chmod 700 /tmp/ap_adm.sh; docker cp /tmp/ap_adm.sh $c:/tmp/ap_adm.sh; rm -f /tmp/ap_adm.sh"]
    for i, (alias, command) in enumerate(items):
        if alias in mfa:
            s.append("docker exec $c sh -c \"echo $(python3 /tmp/totp_now.py) > /tmp/totp\"")
        b64 = base64.b64encode(command.encode()).decode()
        s.append(f"cmd=$(echo {b64} | base64 -d); echo '@@BEGIN {i}'\n"
                 f"docker exec -e SSH_ASKPASS=/tmp/ap_adm.sh -e SSH_ASKPASS_REQUIRE=force -e DISPLAY=:0 $c timeout {timeout} "
                 f"setsid -w ssh -o NumberOfPasswordPrompts=1 -o LogLevel=ERROR {alias} \"$cmd\" 2>/dev/null\necho; echo \"@@END {i} $?\"")
    s.append("docker exec $c sh -c 'rm -f /tmp/ap_adm.sh /tmp/totp'; rm -f /tmp/totp_now.py")
    out = gns3vm.run("\n".join(s), sudo=True)
    if "@@NO-ADMIN-WS" in out:
        raise RuntimeError("ADMIN-WS is not running")
    res = []
    for i in range(len(items)):
        m = re.search(rf"@@BEGIN {i}\n(.*?)\n?@@END {i} (\d+)", out, re.S)
        res.append((int(m.group(2)), m.group(1).replace("\r", "").rstrip("\n")) if m else (255, ""))
    return res


def put(alias, local, remote, timeout=60):
    """Copy a local file to an equipment (ssh "cat > remote" from ADMIN-WS); returns the exit code."""
    inv = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
    c = inv["credentials"]
    gns3vm.put(Path(local), "/tmp/adminws_put.bin")
    out = gns3vm.run(f"""c=$(docker ps -q --filter name=ADMIN-WS)
cat > /tmp/ap_put.sh <<'EOP'
#!/bin/sh
case "$1" in *sysadmin@*) echo '{c['server_admin_password']}' ;; *truenas_admin@*) echo '{c['truenas_admin_password']}' ;; *) echo '{c['admin_password']}' ;; esac
EOP
chmod 700 /tmp/ap_put.sh; docker cp /tmp/ap_put.sh $c:/tmp/ap_put.sh; docker cp /tmp/adminws_put.bin $c:/tmp/adminws_put.bin
docker exec -e SSH_ASKPASS=/tmp/ap_put.sh -e SSH_ASKPASS_REQUIRE=force -e DISPLAY=:0 $c sh -c 'timeout {timeout} setsid -w ssh -o NumberOfPasswordPrompts=1 -o LogLevel=ERROR {alias} "cat > {remote}" < /tmp/adminws_put.bin' 2>/dev/null
echo "@@PUT $?"
docker exec $c rm -f /tmp/ap_put.sh /tmp/adminws_put.bin; rm -f /tmp/ap_put.sh /tmp/adminws_put.bin""", sudo=True)
    m = re.search(r"@@PUT (\d+)", out)
    return int(m.group(1)) if m else 255


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("usage: python automation/adminws.py <alias> <command>")
    rc, text = ssh_batch([(sys.argv[1], " ".join(sys.argv[2:]))])[0]
    print(text)
    sys.exit(rc)
