"""power_test – cut power path A on BMS-SIM, time the Zabbix problems, reset, time the recovery (PLAN_03 S3, ZBX.6).

  python automation/power_test.py                     UTILITY-A, UPS-A and GENERATOR down, then /api/reset
  python automation/power_test.py "UPS-B=DOWN"        another cut (the wait still looks for path A problems)

The cut and the reset are sent from SRV-MON-01 (SSH from ADMIN-WS); the problems are read from the Zabbix API
(service hosts, dependent triggers hidden: what the NOC shows). Needs `lab_proxy.py start`.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import zabbix_setup as zs  # noqa: E402
from adminws import ssh_batch  # noqa: E402

NAMES = {1: "info", 2: "warning", 3: "average", 4: "high", 5: "disaster"}


def problems(z, hosts):
    t = z.call("trigger.get", {"output": ["description", "priority"], "hostids": hosts, "only_true": True,
                               "monitored": True, "skipDependent": True, "filter": {"value": 1},
                               "selectHosts": ["host"]})
    return sorted(f"{NAMES[int(x['priority'])]:8} {x['hosts'][0]['host']}: {x['description']}" for x in t)


def wait(z, hosts, cond, t0, limit=90):
    while time.time() - t0 < limit:
        p = problems(z, hosts)
        if cond(p):
            return round(time.time() - t0, 1), p
        time.sleep(3)
    return None, problems(z, hosts)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    z = zs.Zabbix()
    zs.login(z)
    hosts = [h["hostid"] for h in z.call("host.get", {"output": ["host"], "filter": {"host": list(zs.MON["services"])}})]
    print("before:", time.strftime("%H:%M:%S"))
    for p in problems(z, hosts):
        print("   ", p)
    cut = sys.argv[1] if len(sys.argv) > 1 else "UTILITY-A=DOWN&UPS-A=DOWN&GENERATOR=DOWN"
    rc, out = ssh_batch([("srv-mon-01", f"curl -s -m5 'http://10.70.0.12:8080/api/set?{cut}' | grep -A6 elements")])[0]
    t0 = time.time()
    print(f"\n{time.strftime('%H:%M:%S')} SRV-MON-01: curl 'http://10.70.0.12:8080/api/set?{cut}' -> rc={rc}\n{out}")
    dt, p = wait(z, hosts, lambda p: any("Chemin A hors tension" in x for x in p) and any("dégradé" in x for x in p), t0)
    print(f"problems 'Chemin A hors tension' + 'Baies en mode dégradé' after: {dt} s")
    for x in p:
        print("   ", x)
    rc, out = ssh_batch([("srv-mon-01", "curl -s -m5 http://10.70.0.12:8080/api/reset | grep -A6 elements")])[0]
    t1 = time.time()
    print(f"\n{time.strftime('%H:%M:%S')} SRV-MON-01: curl http://10.70.0.12:8080/api/reset -> rc={rc}\n{out}")
    dt2, p = wait(z, hosts, lambda p: not any(("hors tension" in x or "dégradé" in x or "> 50" in x) for x in p), t1)
    print(f"power problems resolved after: {dt2} s")
    for x in p:
        print("   ", x)
    return 0 if dt is not None and dt2 is not None and dt <= 30 and dt2 <= 30 else 1


if __name__ == "__main__":
    sys.exit(main())
