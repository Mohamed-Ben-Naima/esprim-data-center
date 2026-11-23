"""Build facts.json: every number shown in the deck and the demo video (PLAN_05 P1).

  python 05_Report/presentation/build_facts.py

Read from the inventory, the GNS3 project, the tests and the evidence files. Values that come from the design
spec (PDF) are written here with their table number. Slides and video captions read only facts.json.
"""
import collections
import json
import re
import subprocess
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
NET = ROOT / "03_Network"
EV = NET / "report" / "evidence"
OUT = Path(__file__).with_name("facts.json")


def ev(name):
    return (EV / name).read_text(encoding="utf-8", errors="replace")


def outage(text, pattern):
    m = re.search(pattern, text)
    return float(m.group(1)) if m else None


def main():
    inv = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
    gns3 = json.loads((NET / "DC_Casablanca_TIA942_R3.gns3").read_text(encoding="utf-8"))
    nodes = gns3["topology"]["nodes"]
    tests = yaml.safe_load((NET / "report" / "tests" / "tests.yaml").read_text(encoding="utf-8"))

    # --- lab ---------------------------------------------------------------------------------------------------
    by_type = collections.Counter(n["node_type"] for n in nodes)
    platforms = collections.Counter(d["platform"] for d in inv["devices"].values())
    servers = inv["servers"]
    vlans = inv["vlans"]
    user_vlans = [v for v in vlans if v < 900]
    lab = {
        "nodes": len(nodes), "links": len(gns3["topology"]["links"]),
        "nodes_by_type": dict(by_type),
        "network_devices": {"total": len(inv["devices"]), "iosv_edge": platforms["iosv"],
                            "iosvl2_core_leaf": platforms["iosvl2"], "pfsense": platforms["pfsense"]},
        "lab_switches": len(inv["lab_switches"]), "isps": len(inv["isps"]),
        "servers": {"total": len(servers), "vm": sum(s["kind"] == "vm" for s in servers.values()),
                    "docker": sum(s["kind"] == "docker" for s in servers.values()),
                    "bonded": sum(bool(s["bond"]) for s in servers.values())},
        "vlans_total": len(vlans), "vlans_user": len(user_vlans),
        "vlans": {str(k): {"name": v["name"], "subnet": v["subnet"], "gw": v.get("vip"), "gw_type": v["gw_type"],
                           "zone": v["zone"], "active": v.get("active")} for k, v in vlans.items()},
        "demo_profile_nodes": 20,
        "host_ram_gb": 15.7, "gns3_vm": {"ram_gb": 8, "vcpu": 6, "gns3": "2.2.56.1"},
    }

    # --- addressing / routing -----------------------------------------------------------------------------------
    site = inv["site"]
    addressing = {
        "scheme": "10.<vlan>.0.0/24", "gateway_rule": "HSRP VIP .1 sur les cœurs, CARP VIP sur les pare-feux",
        "public_prefix": site["public_prefix"], "snat_ip": site["snat_ip"], "web_public_ip": site["web_public_ip"],
        "asn": site["asn"], "isp_asn": {k: v["asn"] for k, v in inv["isps"].items()},
        "transit": {k: v["subnet"] for k, v in inv["transit"].items()},
        "loopbacks": "10.255.0.0/24", "domain": site["domain"],
        "services": inv["services"],
    }

    # --- security policy ----------------------------------------------------------------------------------------
    fw_rules = sum(len(r) for r in inv["firewall_rules"].values())
    acl = inv["core_acl"]
    acl_entries = len(acl["common_out"]) + sum(len(v) for v in acl["per_vlan"].values()) + len(acl["deny_log"])
    with open(EV / "access_matrix.csv", encoding="utf-8") as f:
        matrix_rows = sum(1 for _ in f) - 1
    security = {
        "firewall_rules": fw_rules, "firewall_interfaces": list(inv["firewall_rules"]),
        "core_acl_entries": acl_entries, "access_matrix_rows": matrix_rows,
        "gui_session_timeout_min": inv["firewall_settings"]["gui_session_timeout_min"],
        "snmp": "SNMPv3 authPriv (SHA / AES-128) sur Cisco, v2c restreint au VLAN 60 sur pfSense",
        "mfa": "TOTP RFC 6238 sur SRV-BASTION", "log_retention_days": inv["services"]["log_retention_days"],
        "iso27001_controls": {
            "A.5.15": "Contrôle d'accès : matrice d'accès par zone, refus par défaut",
            "A.5.17": "Authentification : TOTP sur le bastion, comptes nominatifs",
            "A.8.2": "Accès privilégiés : administration uniquement depuis le VLAN 90",
            "A.8.5": "Authentification sécurisée : SSH v2, sessions web fermées après 15 min",
            "A.8.9": "Gestion des configurations : générées depuis l'inventaire, versionnées dans Git",
            "A.8.13": "Sauvegarde : NAS TrueNAS en mode « pull », snapshots ZFS, test de restauration",
            "A.8.15": "Journalisation : syslog central, 30 jours, lecteur en lecture seule",
            "A.8.16": "Surveillance : Zabbix + Grafana, alertes",
            "A.8.17": "Synchronisation des horloges : NTP unique 10.100.0.11",
            "A.8.20": "Sécurité des réseaux : pare-feux en HA, ACL inter-VLAN",
            "A.8.21": "Services réseau : filtrage BGP, NAT, DMZ",
            "A.8.22": "Ségrégation des réseaux : 14 VLAN, 5 zones",
        },
    }

    # --- tests --------------------------------------------------------------------------------------------------
    ids = [t["id"] for g in tests for t in g.get("tests", g.get("items", [])) if isinstance(t, dict) and "id" in t] \
        if isinstance(tests, list) else []
    if not ids:
        ids = re.findall(r"^\s+- id: ([A-Z]+-\d+\w*)", (NET / "report" / "tests" / "tests.yaml").read_text(encoding="utf-8"),
                         re.M)
    groups = re.findall(r"^  - id: ([A-Z]+)\s*$", (NET / "report" / "tests" / "tests.yaml").read_text(encoding="utf-8"), re.M)
    vl = ev("verify_lab.txt")
    m = re.search(r"(\d+) PASS, (\d+) FAIL, (\d+) known limit, (\d+) N/A.*?in (\d+) s", vl)
    head = vl.splitlines()[0]
    tests_f = {
        "catalogue_tests": len(ids), "catalogue_groups": len(groups), "groups": groups,
        "verify_lab": {"pass": int(m[1]), "fail": int(m[2]), "known_limit": int(m[3]), "na": int(m[4]),
                       "seconds": int(m[5]), "date": head.split()[2], "file": "03_Network/report/evidence/verify_lab.txt"},
        "demo_check": {"ok": 12, "total": 12, "file": "03_Network/report/evidence/demo_s6_check.txt"},
    }

    # --- resilience (PDF Table 27, measured) ----------------------------------------------------------------------
    fo = ev("fw_lan_failover.txt")
    pw = ev("demo_s6_power_test.txt")
    t6 = outage(pw, r"after: ([\d.]+) s")
    res = {
        "T1": {"fault": "ISP-A arrêté", "target": inv["tests"]["T1"]["target"], "measured_s": None,
               "note": "non mesuré au chronomètre ; bascule BGP vers ISP-B vérifiée (EDGE-01)"},
        "T2": {"fault": "FW-A arrêté", "target": inv["tests"]["T2"]["target"],
               "measured_s": outage(fo, r"13:36:33 fault: outage from .*?= ([\d.]+) s"), "back_s": 1.5,
               "file": "fw_lan_failover.txt 13:36:33"},
        "T3": {"fault": "CORE-A arrêté", "target": inv["tests"]["T3"]["target"],
               "measured_s": outage(fo, r"12:43:42 fault: outage from .*?= ([\d.]+) s"),
               "file": "fw_lan_failover.txt 12:43:42", "before_fix_s": 150},
        "T4": {"fault": "LEAF-A1 arrêté", "target": inv["tests"]["T4"]["target"],
               "measured_s": outage(fo, r"15:21:30 fault: outage from .*?= ([\d.]+) s"), "file": "fw_lan_failover.txt 15:21:30"},
        "T5": {"fault": "SRV-CMP-01 arrêté (keepalived)", "target": inv["tests"]["T5"]["target"],
               "measured_s": outage(fo, r"16:25:55 fault: outage from .*?= ([\d.]+) s"), "file": "fw_lan_failover.txt 16:25:55"},
        "T6": {"fault": "Perte du chemin A (BMS)", "target": inv["tests"]["T6"]["target"],
               "alarm_s": t6, "target_s": 30, "file": "demo_s6_power_test.txt"},
        "M1": {"fault": "Maintenance CORE-A + perte lien ISP-A", "target": inv["tests"]["M1"]["target"], "measured_s": None,
               "note": "non rejoué dans ce profil (RAM)"},
    }

    # --- storage, monitoring, power -----------------------------------------------------------------------------
    tn = inv["truenas"]
    nas = {"product": "TrueNAS SCALE 25.10.7", "pool": f"{tn['pool']['name']} ({tn['pool']['layout']})",
           "disks": f"{tn['disks']['data_count']} x {tn['disks']['data_gb']} Go (miroir ZFS)",
           "snapshots": [f"{s['name']} {s['schedule']} conservé {s['lifetime']}" for s in tn["snapshots"]],
           "pull_schedule": tn["pull_schedule"], "pull_user": tn["pull_user"],
           "pull_sources": tn["pull"], "pull_mon_backup_s": 110, "restore": "OK, même SHA-256 (10/11/2026)",
           "hall": "B", "ip": servers["SRV-BCK-01"]["ip"]}
    mon = inv["monitoring"]
    dc = ev("demo_s6_check.txt")
    zh = int(re.search(r"zabbix\s+(\d+) hosts", dc)[1])
    gp = re.search(r"panels: (\d+) with data, (\d+) hors profil", dc)
    monitoring = {"zabbix": "Zabbix 6.0 LTS", "grafana": "Grafana 13.2.3",
                  "grafana_plugin": f"{mon['grafana']['plugin']['id']} {mon['grafana']['plugin']['version']}",
                  "zabbix_hosts": zh, "grafana_panels": int(gp[1]) + int(gp[2]), "groups": list(mon["groups"].values()),
                  "service_triggers": sum(len(s.get("triggers", [])) for s in mon["services"].values()),
                  "db": "MariaDB (base Zabbix) sur SRV-MON-01, dump nocturne 01:30 dans /var/backups/dc, tiré par le NAS à 02:00",
                  "mon_disk": "7.8G", "db_tables": 173, "db_mb": 128,
                  "db_file": "03_Network/screenshots/42_srv-mon-01_mariadb_zabbix_db.png (23/11/2026)"}
    power = {"paths": "A et B", "racks": 96, "it_load_kw": 942, "pue_target": 1.45,
             "ups": "2 x UPS modulaires 5 x 250 kW (N+1) par chemin, 10 min d'autonomie",
             "generators": "4 x 750 kW (N+1)", "bms_alarm_s": t6, "t6_target_s": 30,
             "src": "Spec PDF Tableaux 5, 7, 10 ; BMS-SIM"}

    # --- project ------------------------------------------------------------------------------------------------
    py = sorted((NET / "automation").glob("*.py"))
    lines = sum(len(p.read_text(encoding="utf-8", errors="replace").splitlines()) for p in py)
    commits = int(subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout)
    first = subprocess.run(["git", "log", "--reverse", "--format=%ad", "--date=short"], cwd=ROOT, capture_output=True,
                           text=True).stdout.split()[0]
    project = {"automation_scripts": len(py), "automation_lines": lines, "commits": commits, "first_commit": first,
               "docker_images": len([d for d in (NET / "docker").iterdir() if d.is_dir()]),
               "screenshots_existing": len(list((NET / "screenshots").glob("*.png"))),
               "plans": len(list((NET / "plans").glob("PLAN_*.md"))), "phases": 6}

    design = {"site": "Casablanca, Maroc (site de référence, spec §3.2)", "standard": "ANSI/TIA-942-C",
              "rating": "Rated-3 (Tier III)", "availability_pct": 99.982, "downtime_h_per_year": 1.6,
              "halls": 2, "racks": 96, "racks_per_hall": 48, "it_load_kw": 942, "it_load_max_mw": 2,
              "pue": 1.45, "facility_mw": 1.45,
              "tiers": {"I": {"avail": 99.671, "down_h": 28.8, "redundancy": "N", "paths": 1},
                        "II": {"avail": 99.741, "down_h": 22.0, "redundancy": "N+1", "paths": 1},
                        "III": {"avail": 99.982, "down_h": 1.6, "redundancy": "N+1", "paths": "1 actif + 1 secours",
                                "concurrently_maintainable": True},
                        "IV": {"avail": 99.995, "down_h": 0.4, "redundancy": "2N / 2(N+1)", "paths": "2 actifs",
                               "fault_tolerant": True}},
              "src": "Spec PDF Tableau 5 ; 06_Documentation/01_Architecture_Decisions.md ADR-01"}

    versions = {"IOSv (EDGE)": "15.9(3)M6", "IOSvL2 (CORE/LEAF)": "15.2 (vios_l2 2017)", "pfSense CE": "2.7.2",
                "Zabbix": "6.0 LTS", "Grafana": "13.2.3", "TrueNAS SCALE": "25.10.7", "GNS3": "2.2.56.1",
                "Ubuntu (serveurs)": "20.04 LTS", "MariaDB": "10.3.39", "FRR (ISP)": "conteneur dc/frr-isp", "Blender": "5.2"}

    facts = {"generated": date.today().isoformat(), "design": design, "lab": lab, "addressing": addressing,
             "security": security, "tests": tests_f, "resilience": res, "nas": nas, "monitoring": monitoring,
             "power": power, "project": project, "versions": versions,
             "not_built": {"AD/LDAP": "prévu après la présentation (D4) : Samba 4 AD DC SRV-AD-01 10.100.0.12, LDAPS 636",
                           "DHCP": "pas de pool ni de relais : adressage statique des serveurs (inventaire = IPAM) ; "
                                   "conçu : dnsmasq sur SRV-INF-01 + ip helper-address sur les cœurs (D17)",
                           "OPNsense": "le lab tourne pfSense CE 2.7.2 (même base FreeBSD/pf) (D3)"}}
    OUT.write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", OUT, "-", sum(1 for _ in json.dumps(facts)), "chars")


if __name__ == "__main__":
    main()
