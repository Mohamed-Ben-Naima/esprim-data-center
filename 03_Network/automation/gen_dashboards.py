"""gen_dashboards – build the Grafana NOC dashboard from Python (PLAN_02 GRF.4, design Table 23).

  python automation/gen_dashboards.py          writes grafana/dashboards/noc.json

Rows Énergie / Réseau / Sécurité / Infrastructure. Every panel reads the Zabbix data source (uid `zabbix`) by group,
host and item name (the names `zabbix_setup.py apply` and the templates give). Hosts stopped in the demo profile are in
maintenance: problem panels hide them; metric panels only name the hosts that run (a panel without data is dropped,
not left empty). Deployed by `python automation/deploy_servers.py --role=grafana SRV-MON-01`.
"""
import json
from pathlib import Path

NET = Path(__file__).resolve().parents[1]
DS = {"type": "alexanderzobnin-zabbix-datasource", "uid": "zabbix"}
GREEN, ORANGE, RED, BLUE = "green", "orange", "red", "blue"
TEXT_STATE = {"POWERED": GREEN, "OK": GREEN, "ONLINE": GREEN, "WARNING": ORANGE, "DEGRADED": ORANGE, "DOWN": RED,
              "CRITICAL": RED, "FAULTED": RED, "UNAVAIL": RED, "OFFLINE": RED}
NO_VALUE = "hors profil"     # host stopped in the running lab profile (maintenance): said, never an empty "No data"

_id = 0


def nid():
    global _id
    _id += 1
    return _id


def metric(group, host, item, ref="A", text=False):
    t = {"refId": ref, "datasource": DS, "queryType": "2" if text else "0",
         "group": {"filter": group}, "host": {"filter": host}, "application": {"filter": ""},
         "itemTag": {"filter": ""}, "item": {"filter": item}, "functions": [],
         "options": {"showDisabledItems": False, "skipEmptyValues": False, "disableDataAlignment": False,
                     "useZabbixValueMapping": False}}
    if text:
        t.update(textFilter="", useCaptureGroups=False)
    return t


def steps(*pairs):
    return {"mode": "absolute", "steps": [{"color": c, "value": v} for v, c in pairs]}


def panel(kind, title, targets, x, y, w, h, unit="", thresholds=None, mappings=None, options=None, overrides=None,
          decimals=None, minmax=None, desc=""):
    defaults = {"unit": unit, "thresholds": thresholds or steps((None, GREEN)), "mappings": mappings or [],
                "color": {"mode": "thresholds"}, "noValue": NO_VALUE}
    if decimals is not None:
        defaults["decimals"] = decimals
    if minmax:
        defaults["min"], defaults["max"] = minmax
    return {"id": nid(), "type": kind, "title": title, "description": desc, "datasource": DS,
            "gridPos": {"x": x, "y": y, "w": w, "h": h}, "targets": targets,
            "fieldConfig": {"defaults": defaults, "overrides": overrides or []}, "options": options or {}}


def stat_opts(text_mode="value", color_mode="background", name=False):
    return {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "/.*/" if name else "", "values": False},
            "colorMode": color_mode, "graphMode": "none", "textMode": "value_and_name" if name else text_mode,
            "justifyMode": "center", "orientation": "auto", "wideLayout": True, "showPercentChange": False}


def text_map():
    return [{"type": "value", "options": {k: {"text": k, "color": c, "index": i}
                                          for i, (k, c) in enumerate(TEXT_STATE.items())}}]


def up_down_map():
    return [{"type": "value", "options": {"1": {"text": "UP", "color": GREEN, "index": 0},
                                          "0": {"text": "DOWN", "color": RED, "index": 1}}}]


def rename(pattern, to):
    """Display name of the series whose name matches `pattern` (plugin names: '<host>: <item>' or '<item>')."""
    return {"matcher": {"id": "byRegexp", "options": pattern}, "properties": [{"id": "displayName", "value": to}]}


def row(title, y):
    return {"id": nid(), "type": "row", "title": title, "collapsed": False, "gridPos": {"x": 0, "y": y, "w": 24, "h": 1},
            "panels": []}


def problems(title, x, y, w, h, group="/.*/", host="/.*/", min_sev=0):
    t = {"refId": "A", "datasource": DS, "queryType": "5", "group": {"filter": group}, "host": {"filter": host},
         "application": {"filter": ""}, "itemTag": {"filter": ""}, "proxy": {"filter": ""}, "trigger": {"filter": ""},
         "tags": {"filter": ""}, "functions": [],
         "options": {"hostsInMaintenance": False, "showProblems": "problems", "minSeverity": min_sev,
                     "acknowledged": 2, "sortProblems": "priority", "limit": 50, "hostProxy": False,
                     "severities": [0, 1, 2, 3, 4, 5]}}
    return {"id": nid(), "type": "alexanderzobnin-zabbix-triggers-panel", "title": title, "datasource": DS,
            "gridPos": {"x": x, "y": y, "w": w, "h": h}, "targets": [t],
            "options": {"layout": "table", "fontSize": "100%", "pageSize": 10, "showTags": False,
                        "hostField": True, "hostTechNameField": False, "hostGroups": False, "hostProxy": False,
                        "severityField": True, "statusField": True, "statusIcon": True, "ackField": False,
                        "ageField": True, "descriptionField": False, "highlightNewEvents": True,
                        "highlightNewerThan": "1h", "customLastChangeFormat": False, "allowDangerousHTML": False,
                        "resizedColumns": []}}


def build():
    p = []
    load = steps((None, GREEN), (45, ORANGE), (50, RED))
    svc, bms, dcim = "DC/Services", "BMS-SIM", "SRV-DCIM-01"
    # ------------------------------------------------------------------ Énergie
    p.append(row("Énergie", 0))
    for i, path in enumerate("AB"):
        p.append(panel("gauge", f"Chemin {path} – charge", [metric(svc, bms, f"Charge chemin {path}")],
                       i * 4, 1, 4, 6, unit="percent", thresholds=load, decimals=1, minmax=(0, 100),
                       options={"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                                "showThresholdMarkers": True, "showThresholdLabels": False},
                       desc="Seuils Table 22 : 45 % avertissement, 50 % redondance N+N non assurée"))
    for i, path in enumerate("AB"):
        p.append(panel("stat", f"Chemin {path}", [metric(svc, bms, f"État chemin {path}", text=True)],
                       8 + i * 3, 1, 3, 3, mappings=text_map(), options=stat_opts()))
    p.append(panel("stat", "GTB", [metric(svc, bms, "État global GTB", text=True)], 8, 4, 6, 3,
                   mappings=text_map(), options=stat_opts()))
    racks = steps((None, GREEN), (1, RED))
    p.append(panel("stat", "Baies OK", [metric(svc, dcim, "Baies OK")], 14, 1, 3, 6,
                   thresholds=steps((None, RED), (96, GREEN)), options=stat_opts()))
    p.append(panel("stat", "Baies DEGRADED", [metric(svc, dcim, "Baies DEGRADED")], 17, 1, 3, 6,
                   thresholds=steps((None, GREEN), (1, ORANGE)), options=stat_opts()))
    p.append(panel("stat", "Baies DOWN", [metric(svc, dcim, "Baies DOWN")], 20, 1, 4, 6,
                   thresholds=racks, options=stat_opts()))
    p.append(panel("timeseries", "Charge des chemins A / B",
                   [metric(svc, bms, "Charge chemin A", "A"), metric(svc, bms, "Charge chemin B", "B")],
                   0, 7, 12, 7, unit="percent", thresholds=load, minmax=(0, 100),
                   overrides=[rename(".*chemin A.*", "Chemin A"), rename(".*chemin B.*", "Chemin B")],
                   options={"legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
                            "tooltip": {"mode": "multi"}}))
    for i, (title, host, item, unit, dec) in enumerate([("Charge IT", bms, "Charge IT", "kwatt", 0),
                                                         ("PUE", bms, "PUE", "none", 2),
                                                         ("Température entrée max", dcim, "Température entrée max",
                                                          "celsius", 1),
                                                         ("Alarmes GTB actives", bms, "Alarmes GTB actives", "none", 0)]):
        th = steps((None, GREEN), (27, ORANGE), (32, RED)) if unit == "celsius" else \
            steps((None, GREEN), (3, ORANGE), (4, RED)) if "Alarmes" in title else steps((None, BLUE))
        p.append(panel("stat", title, [metric(svc, host, item)], 12 + (i % 2) * 6, 7 + (i // 2) * 3 + (i // 2) // 2,
                       6, 3 if i < 2 else 4, unit=unit, decimals=dec, thresholds=th, options=stat_opts()))
    # ------------------------------------------------------------------ Réseau
    y = 15
    p.append(row("Réseau", y))
    p.append(panel("stat", "Disponibilité bordure / cœur / distribution (ICMP)",
                   [metric("/DC\\/(Edge|Core|Leaf)/", "/^(EDGE-A|CORE-A|CORE-B|LEAF-B1|LEAF-B2)$/",
                           "Cisco IOS: ICMP ping")],
                   0, y + 1, 12, 4, mappings=up_down_map(), thresholds=steps((None, RED), (1, GREEN)),
                   options=stat_opts(name=True), overrides=[rename("([^:]*): .*", "$1")],
                   desc="Équipements de l'arrêt « demo » (EDGE-B, LEAF-A1/A2) en maintenance, non affichés"))
    p.append(panel("timeseries", "Trafic EDGE-A – liens opérateurs (Gi0/0 ISP-A, Gi0/1 ISP-B)",
                   [metric("DC/Edge", "EDGE-A", "/Interface Gi0\\/[01].*: Bits (received|sent)/")],
                   12, y + 1, 12, 8, unit="bps",
                   options={"legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
                            "tooltip": {"mode": "multi"}}))
    p.append(panel("timeseries", "Temps de réponse ICMP", [metric("/DC\\/(Edge|Core|Leaf)/",
                                                                  "/^(EDGE-A|CORE-A|CORE-B|LEAF-B1|LEAF-B2)$/",
                                                                  "Cisco IOS: ICMP response time")],
                   0, y + 5, 12, 4, unit="s", overrides=[rename("([^:]*): .*", "$1")],
                   options={"legend": {"displayMode": "list", "placement": "right", "showLegend": True},
                            "tooltip": {"mode": "multi"}}))
    # ------------------------------------------------------------------ Sécurité
    y = 25
    p.append(row("Sécurité", y))
    p.append(panel("stat", "Pare-feux (agent SNMP)",
                   [metric("DC/Firewalls", "/FW-[AB]/", "PFSense: SNMP agent availability")], 0, y + 1, 6, 4,
                   mappings=up_down_map(), thresholds=steps((None, RED), (1, GREEN)), options=stat_opts(name=True),
                   overrides=[rename("([^:]*): .*", "$1")],
                   desc="Le modèle PFSense by SNMP n'a pas d'élément ICMP : disponibilité de l'agent SNMP"))
    p.append(panel("timeseries", "Pare-feux – états (table pf)",
                   [metric("DC/Firewalls", "/FW-[AB]/", "PFSense: States table current")], 0, y + 5, 6, 6,
                   overrides=[rename("([^:]*): .*", "$1")],
                   options={"legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
                            "tooltip": {"mode": "multi"}}))
    p.append(problems("Problèmes actifs (hors maintenance)", 6, y + 1, 18, 10))
    # ------------------------------------------------------------------ Stockage (PLAN_04: TrueNAS SRV-BCK-01)
    y, sto, nas = 37, "DC/Storage", "SRV-BCK-01"
    p.append(row("Stockage et sauvegardes", y))
    p.append(panel("stat", "NAS – pool tank", [metric(sto, nas, "Pool tank - état ZFS", text=True)], 0, y + 1, 6, 5,
                   mappings=text_map(), options=stat_opts(), desc="Miroir ZFS (2 disques) ; DEGRADED = un disque perdu"))
    p.append(panel("stat", "Âge du dernier snapshot", [metric(sto, nas, "Âge du dernier snapshot")], 6, y + 1, 6, 5,
                   unit="s", decimals=0, thresholds=steps((None, GREEN), (3900, ORANGE), (7200, RED)),
                   options=stat_opts(), desc="Snapshots horaires de tank/backups ; alarme au-delà de 2 h"))
    p.append(panel("stat", "Sauvegardes en échec", [metric(sto, nas, "Tâches de sauvegarde en échec")], 12, y + 1, 6, 5,
                   decimals=0, thresholds=steps((None, GREEN), (1, RED)), options=stat_opts(),
                   desc="Tâches rsync tirées par le NAS (SRV-MON-01, SRV-INF-01) dont la dernière exécution a échoué"))
    p.append(panel("stat", "NAS (ICMP)", [metric(sto, nas, "TrueNAS CORE: ICMP ping")], 18, y + 1, 6, 5, mappings=up_down_map(),
                   thresholds=steps((None, RED), (1, GREEN)), options=stat_opts()))
    # ------------------------------------------------------------------ Infrastructure
    y = 44
    p.append(row("Infrastructure", y))
    for i, (title, item, unit) in enumerate([("SRV-MON-01 – CPU", "Linux: CPU utilization", "percent"),
                                             ("SRV-MON-01 – mémoire", "Linux: Memory utilization", "percent"),
                                             ("SRV-MON-01 – disque /", "/: Space utilization", "percent")]):
        p.append(panel("gauge", title, [metric("DC/Servers", "SRV-MON-01", item)], i * 4, y + 1, 4, 5, unit=unit,
                       decimals=1, minmax=(0, 100), thresholds=steps((None, GREEN), (80, ORANGE), (90, RED)),
                       options={"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                                "showThresholdMarkers": True, "showThresholdLabels": False}))
    checks = [("Site web DMZ", "SRV-WEB-01", "Failed step of scenario \"Site web DMZ\".", "fail"),
              ("Collecteur syslog", "SYSLOG", "ICMP ping", "ping")]
    for i, (title, host, item, kind) in enumerate(checks):
        mp = up_down_map() if kind == "ping" else \
            [{"type": "value", "options": {"0": {"text": "OK", "color": GREEN, "index": 0}}},
             {"type": "range", "options": {"from": 1, "to": 99, "result": {"text": "ÉCHEC", "color": RED, "index": 1}}}]
        th = steps((None, RED), (1, GREEN)) if kind == "ping" else steps((None, GREEN), (1, RED))
        p.append(panel("stat", title, [metric(svc, host, item)], 12 + i * 6, y + 1, 6, 5, mappings=mp, thresholds=th,
                       options=stat_opts()))
    return {"uid": "dc-noc", "title": "NOC – DC Casablanca", "tags": ["dc-casablanca", "noc"], "timezone": "",
            "editable": False, "graphTooltip": 1, "refresh": "10s", "schemaVersion": 39, "version": 1,
            "time": {"from": "now-30m", "to": "now"}, "timepicker": {"refresh_intervals": ["10s", "30s", "1m"]},
            "templating": {"list": []}, "annotations": {"list": []}, "links": [], "panels": p}


if __name__ == "__main__":
    out = NET / "grafana" / "dashboards" / "noc.json"
    out.write_text(json.dumps(build(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{out.relative_to(NET)}: {len(build()['panels'])} panels")
