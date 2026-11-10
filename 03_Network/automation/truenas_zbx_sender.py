"""Runs ON the TrueNAS SRV-BCK-01 (cron job every 5 min, user root, installed by truenas_setup.py apply - PLAN_04 NAS.6).

Sends to the Zabbix trapper items of host SRV-BCK-01 what SNMP does not expose: pool health, age of the newest
snapshot of tank/backups, number of pull tasks whose last run failed. Zabbix sender protocol (TCP 10051, allowed
from VLAN 40 by the core ACL "Zabbix actif"), standard library only. Arguments: <zabbix server> <host name>.
"""
import json
import socket
import struct
import subprocess
import sys
import time

server, host = sys.argv[1], sys.argv[2]


def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout


data = [(f"nas.pool.health[{n}]", h) for n, h in (l.split("\t") for l in sh("zpool", "list", "-H", "-o", "name,health")
                                                    .splitlines() if not l.startswith("boot-pool"))]
created = [int(x) for x in sh("zfs", "list", "-H", "-p", "-t", "snapshot", "-o", "creation", "-r", "tank/backups").split()]
data.append(("nas.snapshot.age", int(time.time()) - max(created) if created else 999999))
tasks = json.loads(sh("midclt", "call", "rsynctask.query") or "[]")
data.append(("nas.rsync.failed", sum(1 for t in tasks if (t.get("job") or {}).get("state") in ("FAILED", "ABORTED"))))
body = json.dumps({"request": "sender data",
                   "data": [{"host": host, "key": k, "value": str(v)} for k, v in data]}).encode()
with socket.create_connection((server, 10051), timeout=10) as s:
    s.sendall(b"ZBXD\x01" + struct.pack("<Q", len(body)) + body)
    reply = s.recv(1024)
print(reply[13:].decode(errors="replace"), data)
