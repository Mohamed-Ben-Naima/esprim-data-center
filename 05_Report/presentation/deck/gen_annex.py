"""Annex slides of the deck, generated from the inventory, the tests catalogue and facts.json (PLAN_05 P3).

  python 05_Report/presentation/deck/gen_annex.py      -> project/slides/annexe-*.html
"""
import json
import re
from html import escape
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NET = ROOT / "03_Network"
INV = yaml.safe_load((NET / "inventory/dc_casa.yaml").read_text(encoding="utf-8"))
F = json.loads((HERE.parent / "facts.json").read_text(encoding="utf-8"))
SL = HERE / "project" / "slides"
TD = "padding:6px 12px"


def table(head, rows, widths=None):
    w = widths or [None] * len(head)
    th = "".join(f'<th style="{TD}' + (f';width:{x}' if x else "") + f'">{escape(h)}</th>' for h, x in zip(head, w))
    body = "".join("<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="t" style="font-size:24px"><tr>{th}</tr>{body}</table>'


def slide(sid, title, body, how, badge, notes, alt=False):
    (SL / f"{sid}.html").write_text(f"""<section id="{sid}"{' class="alt"' if alt else ''}>
<p class="eyebrow">Annexe</p>
<h2>{escape(title)}</h2>
{body}
<div class="foot"><p class="how">{escape(how)}</p><p class="badge">{escape(badge)}</p><div class="pg"></div></div>
<aside>{escape(notes)}</aside>
</section>
""", encoding="utf-8")


def two(a, b):
    return f'<div style="display:flex;gap:40px;flex:1;align-items:flex-start"><div style="flex:1">{a}</div><div style="flex:1">{b}</div></div>'


def main():
    v = [(k, d["name"], d["subnet"] or "–", d.get("vip") or "–") for k, d in INV["vlans"].items()]
    h = ["VLAN", "Nom", "Sous-réseau", "Passerelle"]
    slide("annexe-vlan", "Les 14 VLAN", two(table(h, v[:7]), table(h, v[7:])),
          "Comment c’est fait : inventory/dc_casa.yaml, rubrique vlans", "IEEE 802.1Q",
          "Tableau complet des VLAN, tiré de l’inventaire. Passerelle .1 sur les cœurs en HSRP pour les VLAN internes, VIP CARP sur les pare-feux pour 10, 50 et 90.")
    dev = [(n, d["platform"], d["tia"], d["mgmt"]["ip"], d["loopback"]) for n, d in INV["devices"].items()]
    srv = [(n, s["tia"], s["vlan"], s["ip"]) for n, s in INV["servers"].items()]
    slide("annexe-adressage", "Adresses des équipements et des serveurs",
          two(table(["Équipement", "OS", "Espace", "Mgmt", "Loopback"], dev), table(["Serveur", "Espace", "VLAN", "Adresse"], srv)),
          "Comment c’est fait : rubriques devices et servers de l’inventaire", "RFC 1918",
          "Adresse de management hors bande de chaque équipement réseau, VLAN 10, et adresse de chaque serveur ou conteneur.", alt=True)
    rules = [(i, r["ref"], r["descr"]) for i, rs in INV["firewall_rules"].items() for r in rs]
    hh = ["Interface", "Réf.", "Flux autorisé (sinon refus + journal)"]
    n = (len(rules) + 1) // 2
    slide("annexe-regles", f"Les {len(rules)} règles du pare-feu",
          two(table(hh, rules[:n], ["150px", "110px", None]), table(hh, rules[n:], ["150px", "110px", None])),
          "Comment c’est fait : firewall_rules → gen_pfsense.py ; audit fw_audit.py", "ISO 27001 A.8.20",
          "Les règles du pare-feu dans l’ordre d’évaluation par interface. Chaque interface se termine par un refus journalisé. Références T18 : tableau 18 du cahier des charges ; EXT : ajouts justifiés.")
    tests = yaml.safe_load((NET / "report/tests/tests.yaml").read_text(encoding="utf-8"))["sections"]
    fr = {"PLT": "plateforme GNS3, images, disques", "EDGE": "bordure, eBGP, HSRP, Internet", "FW": "pare-feux, CARP, NAT, audit",
          "CORE": "cœurs, HSRP, OSPF, LACP, STP", "CMP": "serveurs de calcul, keepalived", "INF": "DNS, NTP (SRV-INF-01)",
          "LOG": "journaux centralisés", "ADM": "comptes, bastion TOTP", "WT": "poste ADMIN-WS, sessions",
          "ACC": "accès SSH, refus journalisés", "PRV": "privilèges, verrouillage", "PWR": "chemins électriques A/B",
          "MON": "Zabbix, Grafana", "WEB": "interfaces web, proxy", "NAS": "TrueNAS, sauvegarde pull", "DEMO": "contrôles de démo, flux"}
    rows = [(g["id"], len([t for t in g.get("tests", []) if isinstance(t, dict)]), fr.get(g["id"], g.get("title", ""))) for g in tests]
    n = (len(rows) + 1) // 2
    hh = ["Groupe", "Tests", "Ce qu’il prouve"]
    slide("annexe-tests", f"Le catalogue « Test the Lab » : {sum(r[1] for r in rows)} tests",
          two(table(hh, rows[:n], ["130px", "90px", None]), table(hh, rows[n:], ["130px", "90px", None])),
          f"Comment c’est fait : report/tests/tests.yaml rejoué par verify_lab.py ({F['tests']['verify_lab']['pass']} PASS dans le profil démo)",
          "Recette", "Le catalogue complet, par groupe. Chaque test a une commande, une source et un résultat attendu. verify_lab exécute tous ceux que le profil permet.", alt=True)
    code = "<br>".join(escape(x) for x in [
        "python automation/lab_up.py --profile demo      # démarrage par étapes (≈ 12 min)",
        "python automation/demo_check.py                # 12 contrôles avant la démo",
        "python automation/verify_lab.py --save         # catalogue de tests (≈ 10 min)",
        "python automation/fw_audit.py                  # pare-feux = inventaire",
        "python automation/flow_matrix.py --running-only  # flux de bout en bout",
        "python automation/zabbix_setup.py status       # hôtes et maintenance",
        "python automation/power_test.py                # coupure du chemin A (T6)",
        "python automation/fw_lan_failover.py --core CORE-A  # bascule mesurée",
        "python automation/lab_down.py                  # arrêt propre (1 min)"])
    slide("annexe-commandes", "Les commandes du laboratoire", f'<p class="code" style="font-size:26px">{code}</p>',
          "Comment c’est fait : 03_Network/automation, depuis le PC hôte (dossier 03_Network)", "Exploitation",
          "Les commandes qui pilotent le labo, dans l’ordre d’une journée de démonstration : démarrer, contrôler, prouver, provoquer une panne, arrêter.")
    ver = list(F["versions"].items())
    slide("annexe-outils", "Outils et versions", two(table(["Composant", "Version"], ver[:6]), table(["Composant", "Version"], ver[6:])),
          "Comment c’est fait : show version, versions des paquets et des images (facts.json)", "ISO 27001 A.8.9",
          "Versions exactes des systèmes et outils utilisés, relevées sur les équipements et dans les images.", alt=True)
    ev = {"A.5.15": "flow_matrix.csv", "A.5.17": "adm4_accounts_totp.txt", "A.8.2": "adm3_privileged_access.txt",
          "A.8.5": "verify_lab.txt (FW-12, PRV-04)", "A.8.9": "fw_audit.txt", "A.8.13": "nas5_restore.txt",
          "A.8.15": "demo_s5_syslog_audit.txt", "A.8.16": "demo_s4_dashboard_check.txt", "A.8.17": "verify_lab.txt (WT-07)",
          "A.8.20": "fw_audit.txt", "A.8.21": "verify_lab.txt (EDGE-01)", "A.8.22": "flow_matrix.csv"}
    iso = [(k, d.split(" : ")[1] if " : " in d else d, ev.get(k, "")) for k, d in F["security"]["iso27001_controls"].items()]
    slide("annexe-iso", "ISO 27001 Annexe A : mise en œuvre et preuve",
          table(["Contrôle", "Ce qui est fait", "Preuve (report/evidence)"], iso, ["150px", None, "520px"]),
          "Comment c’est fait : report/content/02_normes.md · fichiers de preuve datés", "ISO 27001",
          "Pour chaque contrôle de l’Annexe A retenu : ce qui est fait dans le labo et le fichier de preuve à ouvrir si le jury le demande.")
    glo = [("BGP", "routage entre opérateurs (AS)"), ("CARP", "IP virtuelle partagée par 2 pare-feux"),
           ("DMZ", "zone des services exposés à Internet"), ("HSRP", "passerelle virtuelle Cisco"),
           ("LACP", "agrégation de liens (802.3ad)"), ("NOC", "centre de supervision"), ("OSPF", "routage interne à état de liens"),
           ("pfsync", "copie des états de connexion"), ("PUE", "énergie totale / énergie IT"), ("Rated-3", "Tier III TIA-942"),
           ("RPVST+", "spanning-tree rapide par VLAN"), ("SNMPv3", "supervision chiffrée, authentifiée"),
           ("TOTP", "code à usage unique (RFC 6238)"), ("UPS / PDU", "onduleur / distribution par baie"),
           ("VRF", "table de routage isolée"), ("XMLRPC", "synchro de config pfSense")]
    slide("annexe-glossaire", "Glossaire", two(table(["Terme", "Sens"], glo[:8]), table(["Terme", "Sens"], glo[8:])),
          "Comment c’est fait : termes employés dans la présentation", "Glossaire", "Les sigles utilisés dans la présentation.", alt=True)
    print("annex slides written")


if __name__ == "__main__":
    main()
