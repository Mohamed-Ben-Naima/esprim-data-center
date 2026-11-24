"""Guide du labo en direct (profil `live`) -> GUIDE_LABO_LIVE.md + .pdf, généré depuis l'inventaire et l'API GNS3.

  python 05_Report/presentation/build_lab_guide.py
Contient les identifiants du labo : le .md et le .pdf sont ignorés par git (05_Report/presentation/.gitignore).
Adresses, VLAN, ports et câblage viennent de 03_Network/inventory/dc_casa.yaml ; ports de console de l'API GNS3.
"""
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
NET = HERE.parents[1] / "03_Network"
sys.path.insert(0, str(NET / "automation"))
INV = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
C = INV["credentials"]
NETDIR = r"C:\Users\ASUS\Documents\ESPRIM\Data Center\03_Network"

ROLE = {
    "EDGE-A": "Routeur de bordure (Entrance Room) : eBGP vers les 2 opérateurs, NAT amont, transit VLAN 901",
    "EDGE-B": "Routeur de bordure de secours (même rôle qu'EDGE-A)",
    "FW-A": "Pare-feu pfSense MAÎTRE : filtrage entre zones, NAT, 5 VIP CARP, VPN aucun",
    "FW-B": "Pare-feu pfSense de SECOURS : mêmes règles synchronisées (pfsync/XMLRPC)",
    "CORE-A": "Cœur L3 : passerelles HSRP des VLAN internes, OSPF, ACL inter-VLAN",
    "CORE-B": "Cœur L3 de secours (HSRP actif sur 30/70/80)",
    "LEAF-A1": "Commutateur d'accès salle A (calcul/stockage)", "LEAF-A2": "Commutateur d'accès salle A (2e lien des serveurs)",
    "LEAF-B1": "Commutateur d'accès salle B (services, supervision)", "LEAF-B2": "Commutateur d'accès salle B (2e lien des serveurs)",
}
PROTO = {
    "edge": "eBGP (AS 65100 ↔ 64500/64501), iBGP + OSPF sur l'ISL, HSRP externe, SSHv2, SNMPv3, syslog",
    "firewall": "CARP, pfsync, XMLRPC, NAT, filtrage pf, HTTPS (GUI), SSH, SNMP v2c (VLAN 60), syslog",
    "core": "HSRP, OSPF, LACP (Po1), 802.1Q, Rapid-PVST, ACL, SSHv2, SNMPv3, syslog",
    "leaf": "802.1Q trunks, Rapid-PVST + loop guard, SSHv2, SNMPv3, syslog",
}
SRV = {
    "SRV-MON-01": ("Supervision : Zabbix 6.0, Grafana, MariaDB (base zabbix)", "HTTP 80 (Zabbix), 3000 (Grafana), 10050/10051, SNMP, SSH"),
    "SYSLOG": ("Collecteur de journaux central (rsyslog) + visionneuse en lecture seule", "syslog 514/udp, HTTPS 443 (visionneuse)"),
    "BMS-SIM": ("Simulateur de GTB : chemins électriques A/B, UPS, groupe", "HTTP 8080 (page + API /api/state, /api/set, /api/reset)"),
    "SRV-DCIM-01": ("DCIM : 96 baies, températures d'entrée, charge", "HTTP 8080"),
    "SRV-WEB-01": ("Site web public en DMZ (nginx), publié en 192.0.2.80 par le NAT", "HTTP 80 / HTTPS 443"),
    "ADMIN-WS": ("Poste d'administration (seul autorisé à administrer), journalise chaque commande SSH", "SSH client, navigateur, curl"),
    "SRV-BASTION": ("Bastion SSH à double facteur (mot de passe + TOTP)", "SSH 22"),
    "SRV-BCK-01": ("NAS TrueNAS : sauvegardes en mode pull, snapshots ZFS", "SSH, HTTPS, rsync"),
    "SRV-INF-01": ("DNS (dnsmasq) + NTP", "DNS 53, NTP 123"),
    "SRV-CMP-01": ("Calcul : service applicatif, VIP keepalived 10.20.0.10 (maître)", "HTTPS 8443, VRRP"),
    "SRV-CMP-02": ("Calcul : service applicatif, VIP keepalived (secours)", "HTTPS 8443, VRRP"),
    "SRV-CMP-03": ("Calcul (3e serveur)", "HTTPS 8443"), "SRV-STO-01": ("Stockage NFS/iSCSI (non déployé)", "NFS, iSCSI"),
    "CCTV-SIM": ("Simulateur de caméras (VLAN 80 isolé)", "HTTP"),
}


def consoles():
    try:
        from labctl import Gns3
        a = Gns3()
        p = a.project()
        return {n["name"]: (n["console_type"], n["console"], n["properties"].get("aux"), n["status"]) for n in a.nodes(p)}
    except Exception:  # noqa: BLE001
        return {}


def live_nodes():
    from lab_up import OFF, STAGES
    return {n for _, ns in STAGES for n in ns} - OFF["live"]


def attach():
    """server -> list of 'LEAF:port' from the leaf port tables."""
    out = {}
    for dev, d in INV["devices"].items():
        for port, pd in (d.get("ports") or {}).items():
            to = str(pd.get("to", ""))
            if to.split(":")[0] in INV["servers"]:
                out.setdefault(to.split(":")[0], []).append(f"{dev} {port} ↔ {to.split(':')[1]}")
    for sw, d in INV["lab_switches"].items():
        for port, pd in d["ports"].items():
            to = str(pd.get("to", ""))
            if to.split(":")[0] in INV["servers"]:
                out.setdefault(to.split(":")[0], []).append(f"{sw} {port} ↔ {to.split(':')[1]} (VLAN {pd.get('vlan')})")
    return out


def md():
    con, live, att = consoles(), live_nodes(), attach()
    L = []
    w = L.append
    w("# Guide du labo en direct – DC Casablanca (profil `live`)\n")
    w("**Ce document contient les mots de passe du labo : ne pas le diffuser.** Tout a été exécuté et vérifié le "
      "24/11/2026 sur le labo (profil `live`, 16 nœuds).\n")
    w("## 0. Les 3 terminaux\n")
    w("| Nom | Quoi | Comment l'ouvrir |\n|---|---|---|")
    w(f"| **T1 – PowerShell du PC** | lance, vérifie et arrête le labo | Démarrer › PowerShell, puis `cd \"{NETDIR}\"` |")
    w("| **T2 – Shell d'ADMIN-WS** | le poste d'administration : toutes les commandes SSH | dans T1 : `& \"C:\\Program Files\\GNS3\\putty_standalone.exe\" -telnet 192.168.75.128 "
      f"{con.get('ADMIN-WS', (0, 0, 5053))[2] or 5053}` puis **Entrée** (invite `/ #`) |")
    w("| **T3 – Navigateur « comme ADMIN-WS »** | Grafana, Zabbix, pfSense, journaux, GTB, DCIM | dans T1 : `python automation/lab_proxy.py open` (fenêtre Edge passant par ADMIN-WS) |\n")
    w("> Avant de commencer : **fermer Chrome et les applis inutiles** (le PC n'a que 15,7 Go ; il faut ≥ 1 Go libre).\n")

    w("## 1. Démarrer le labo (T1) – ≈ 8 min\n")
    w("Copier-coller **une ligne à la fois**, dans T1 :\n")
    w("```powershell")
    w(f"cd \"{NETDIR}\"")
    w("python automation/demo_video/vm_cycle.py --cap 1200000 --start live")
    w("```")
    w("Attendu (≈ 2 min 30) : `GNS3 VM server up` … `project open` … `profile live started`. "
      "Ce script redémarre proprement la VM GNS3 (rend la RAM au PC), réserve 1,2 Go pour le PC, puis démarre les 16 nœuds.\n")
    w("Attendre **1 minute**, puis :\n")
    w("```powershell\npython automation/lab_proxy.py start\n```")
    w("Attendu : `SOCKS5 on 192.168.75.128:1080 -> network namespace of ADMIN-WS`.\n")
    w("Attendre **2 minutes** (démarrage de Zabbix), puis :\n")
    w("```powershell\npython automation/gns3vm.py --sudo \"sudo swapoff -a && sudo swapon -a\"\npython automation/cisco_heal.py\n"
      "python automation/zabbix_setup.py apply\n```")
    w("Attendu : `OK CORE-A ssh ok, snmpv3 user ok` (idem LEAF-B1, LEAF-B2), puis `maintenance demo-off: CORE-B, EDGE-A, …` "
      "(les nœuds éteints passent en maintenance : pas de fausse alerte). "
      "Si `zabbix_setup.py apply` répond une erreur de connexion : Zabbix démarre encore, attendre 1 min et relancer.\n")

    w("## 2. Vérifier (T1) – ≈ 1 min\n")
    w("```powershell\npython automation/demo_check.py --profile live\n```")
    w("Attendu (vérifié le 24/11 à 11:41) : **`11/12 checks OK`**. La seule ligne `FAIL` attendue est **`zabbix … 1 running "
      "host(s) not available`** : c'est **SRV-BASTION**, dont l'agent Zabbix n'envoie pas de données (le bastion n'est pas dans "
      "le profil démo habituel). Sans gravité : la connexion au bastion avec double facteur marche (test du §4). "
      "Toute autre ligne `FAIL` est suivie d'une ligne `->` qui dit quoi faire. Juste après le démarrage, `grafana` peut "
      "afficher 1 panneau vide : relancer après 5 min.\n")
    w("Ouvrir ensuite les outils : **T3** (`python automation/lab_proxy.py open`) et **T2** (PuTTY, ci-dessus).\n")

    w("## 3. Identifiants\n")
    w("| Accès | Adresse | Compte | Mot de passe |\n|---|---|---|---|")
    rows = [
        ("Grafana (tableau NOC)", "http://10.60.0.11:3000/", "admin", C["grafana_admin_password"]),
        ("Zabbix", "http://10.60.0.11/", "Admin", C["zabbix_admin_password"]),
        ("Visionneuse de journaux", "https://10.60.0.12/", C["admin_user"], C["admin_password"]),
        ("pfSense FW-A (web)", "https://10.90.0.1/", "admin", C["admin_password"]),
        ("Cisco (SSH depuis ADMIN-WS)", "`ssh core-a`, `ssh leaf-b1`…", C["admin_user"], C["admin_password"]),
        ("Cisco – mode enable (console)", "`enable`", "–", C["enable_secret"]),
        ("Serveurs Ubuntu (SSH depuis ADMIN-WS)", "`ssh srv-mon-01`, `ssh bastion`", C["server_admin_user"], C["server_admin_password"]),
        ("Bastion – 2e facteur", "code à 6 chiffres", "–", "dans T1 : `python automation/totp.py`"),
        ("TrueNAS (profil nas seulement)", "https://10.40.0.11/", "truenas_admin", C["truenas_admin_password"]),
        ("GNS3 Web UI", "http://127.0.0.1:3080/static/web-ui/index.html", "admin", "(dans %APPDATA%\\GNS3\\2.2\\gns3_server.ini)"),
        ("GTB / DCIM / site web", "http://10.70.0.12:8080/ · http://10.70.0.11:8080/ · https://10.50.0.11/", "–", "–"),
    ]
    for r in rows:
        w("| " + " | ".join(r) + " |")
    w("\nCertificats auto-signés : accepter l'avertissement du navigateur. Les mots de passe se tapent **à l'invite** "
      "(jamais sur la ligne de commande : ADMIN-WS journalise chaque commande).\n")

    w("## 4. Tests à faire depuis ADMIN-WS (T2) – tous vérifiés\n")
    w("Chaque commande : copier-coller **une ligne** à l'invite `/ #`, taper le mot de passe quand il est demandé (rien ne "
      "s'affiche, c'est normal), lire le résultat. Pour une session interactive, taper seulement `ssh core-a` (puis `exit`).\n")
    tests = [
        ("Cœur de réseau – passerelles HSRP", "ssh core-a 'show standby brief'",
         "les groupes HSRP en `Active local` (CORE-B est éteint dans ce profil ; sinon il est actif sur 30, 70 et 80)"),
        ("Cœur – interfaces de passerelle", "ssh core-a 'show ip interface brief | include Vlan'", "les SVI Vlan20…Vlan902 en `up up`"),
        ("Cœur – ACL du VLAN supervision", "ssh core-a 'show ip access-lists ACL-VLAN60-IN'",
         "règles `deny` vers le management (10.10.0.0/24) et l'administration (10.90.0.0/24), avec `(N matches)`"),
        ("Commutateur d'accès salle B – trunks", "ssh leaf-b1 'show interfaces trunk'",
         "Gi0/0 et Gi0/1 en `trunking`, VLAN autorisés 20,30,40,60,70,80,100"),
        ("Commutateur d'accès – boucles", "ssh leaf-b1 'show spanning-tree inconsistentports'", "`Number of inconsistent ports … : 0`"),
        ("Pare-feu – état CARP", "ssh fw-a 'ifconfig | grep carp:'", "5 lignes `carp: MASTER` : FW-A est maître des 5 adresses virtuelles"),
        ("Supervision – services", "ssh srv-mon-01 'systemctl is-active zabbix-server grafana-server mariadb nginx'", "4 × `active`"),
        ("Cloisonnement (ACL) : la supervision tente l'administration", "ssh srv-mon-01 'nc -zv -w 3 10.90.0.12 22; echo code=$?'",
         "`code=1` (refusé) ; relancer le test ACL de CORE-A : le compteur `matches` a augmenté"),
        ("Site web (DMZ)", "curl -sk https://10.50.0.11/health", "`OK SRV-WEB-01 (TLS)`"),
        ("GTB – état électrique", "curl -s http://10.70.0.12:8080/api/state", "JSON : `UTILITY-A UP`, `UPS-A UP`, … chemins A et B `POWERED`"),
        ("Bastion à double facteur", "ssh bastion 'hostname; id -un'",
         "mot de passe serveur, puis « Verification code » = le code de `python automation/totp.py` (T1) → `srv-bastion` / `sysadmin` ; un mauvais code est refusé"),
    ]
    for title, cmd, exp in tests:
        w(f"**{title}**\n")
        w("```bash\n" + cmd + "\n```")
        w(f"Attendu : {exp}\n")

    w("## 5. Scénarios de démo (T3 + T2)\n")
    w("**A. Panne électrique T6 (2 min)** – T3, ouvrir Grafana (tableau NOC) dans un onglet, et dans un autre onglet :\n")
    w("```text\nhttp://10.70.0.12:8080/api/set?UTILITY-A=DOWN&UPS-A=DOWN&GENERATOR=DOWN\n```")
    w("Grafana : rangée Énergie rouge en < 10 s (chemin A DOWN, chemin B ≈ 94 %) ; Zabbix › Problèmes : « chemin A non alimenté ». "
      "Rétablir :\n")
    w("```text\nhttp://10.70.0.12:8080/api/reset\n```")
    w("**B. Échec de connexion → journaux (2 min)** – T2 : `ssh core-a` et taper un **mauvais** mot de passe (3 fois), "
      "puis T3 › https://10.60.0.12/ › source **CORE-A**, recherche `LOGIN_FAILED` → `%SEC_LOGIN-4-LOGIN_FAILED … [Source: 10.90.0.12]`.\n")
    w("**C. Modification de configuration → journaux (1 min)** – T2 : `ssh core-a` (bon mot de passe), `configure terminal`, `end`, `exit` ; "
      "journaux, recherche `CONFIG_I` → `Configured from console by netadmin on vty0 (10.90.0.12)`.\n")
    w("**D. Scénarios scriptés (secours, T1)** : `python automation/power_test.py` (T6 chronométrée) · "
      "`python automation/log_viewer.py demo` (3 événements retrouvés) · `python automation/log_viewer.py lock` "
      "(6 mauvais mots de passe → compte verrouillé 5 min ; à faire en dernier).\n")

    w("<div style='page-break-before:always'></div>\n")
    w("## 6. Équipements réseau\n")
    w("| Équipement | Rôle | IP de gestion | Zone TIA | Protocoles | Accès | Démarré en `live` |\n|---|---|---|---|---|---|---|")
    for n, d in INV["devices"].items():
        ct = con.get(n)
        acc = f"`ssh {n.lower()}` (T2) · console GNS3 {ct[0]} {ct[1]}" if ct else f"`ssh {n.lower()}`"
        w(f"| **{n}** | {ROLE.get(n, d['role'])} | {d['mgmt']['ip']} (VLAN 10, port {d['mgmt']['port']}) · lo {d.get('loopback', '')} | "
          f"{d['tia']} | {PROTO.get(d['role'], '')} | {acc} | {'oui' if n in live else 'non'} |")
    w("\n### Interfaces des équipements réseau\n")
    w("| Équipement | Interface | Relié à | Mode / VLAN | Rôle |\n|---|---|---|---|---|")
    for n, d in INV["devices"].items():
        for port, pd in (d.get("ports") or {}).items():
            mode = pd.get("mode", "")
            vl = pd.get("vlan") or (pd.get("ip") or "")
            if pd.get("channel"):
                vl = f"Po{pd['channel']}"
            w(f"| {n} | {port} | {pd.get('to', '')} | {mode} {vl} | {pd.get('role', '')} |")

    w("<div style='page-break-before:always'></div>\n")
    w("## 7. Serveurs et conteneurs\n")
    w("| Nœud | Rôle / ce qui tourne dessus | IP | VLAN | Type | Ports / protocoles | Raccordement | Accès | `live` |\n|---|---|---|---|---|---|---|---|---|")
    for n, s in INV["servers"].items():
        role, ports = SRV.get(n, (", ".join(s.get("roles", [])), ""))
        ct = con.get(n)
        acc = []
        if n in ("SRV-MON-01", "SRV-BASTION", "SRV-CMP-01", "SRV-CMP-02", "SRV-INF-01", "SRV-BCK-01"):
            acc.append(f"`ssh {n.lower().replace('srv-bastion', 'bastion')}` (T2)")
        if ct and ct[2]:
            acc.append(f"shell : telnet 192.168.75.128 {ct[2]} (console AUX)")
        elif ct:
            acc.append(f"console GNS3 {ct[0]} {ct[1]}")
        vip = f" · VIP {s['vip']}" if s.get("vip") else ""
        w(f"| **{n}** | {role} | {s['ip']}{vip} | {s['vlan']} | {s['kind']}{' (2 liens, bond)' if s.get('bond') else ''} | {ports} | "
          f"{'<br>'.join(att.get(n, ['–']))} | {' · '.join(acc) or '–'} | {'oui' if n in live else 'non'} |")
    w("\n**Opérateurs simulés** : ISP-A (AS 64500, lien EDGE-A 198.51.100.0/30, préféré) et ISP-B (AS 64501, 203.0.113.4/30) – "
      "conteneurs FRR ; shell par la console AUX dans GNS3. Pas démarrés dans le profil `live`.\n")
    w("**Commutateurs de labo** : SW-OUT (VLAN 901, transit bordure ↔ pare-feux), SW-IN (VLAN 902, transit pare-feux ↔ cœurs), "
      "SW-DMZ (VLAN 50), SW-MGMT (hors bande : VLAN 10 management + 90 administration).\n")

    w("## 8. VLAN et adressage\n")
    w("| VLAN | Nom | Réseau | Passerelle | Où est la passerelle | Zone |\n|---|---|---|---|---|---|")
    for vid, v in INV["vlans"].items():
        w(f"| {vid} | {v.get('name', '')} | {v.get('subnet') or '–'} | {v.get('gw') or '–'} | "
          f"{ {'core': 'cœurs (HSRP)', 'fw': 'pare-feux (CARP)', 'none': '–'}.get(v.get('gw_type'), v.get('gw_type') or '–') } | {v.get('zone', '')} |")
    w("\nRègle : `10.<VLAN>.0.0/24` ; `.1` = passerelle virtuelle, `.2` / `.3` = CORE-A / CORE-B. Public : 192.0.2.0/24 "
      "(site web 192.0.2.80). Ports libres des commutateurs : VLAN 999, éteints.\n")

    w("## 9. Arrêter proprement (T1) – ≈ 2 min\n")
    w("Une ligne à la fois :\n")
    w("```powershell\npython automation/lab_down.py\n"
      "python -c \"import sys; sys.path.insert(0,'automation'); from labctl import Gns3; a=Gns3(); p=a.project(); "
      "a.req('POST','/projects/'+p['project_id']+'/close'); print('project closed')\"\n"
      "& \"C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmrun.exe\" -T ws stop \"H:\\GNS3 VM\\GNS3 VM.vmx\" soft\n```")
    w("1) éteint chaque machine de l'intérieur (pfSense, Ubuntu, TrueNAS) puis tous les nœuds ; 2) ferme le projet GNS3 ; "
      "3) arrête la VM GNS3. Après ça, le disque H: peut être débranché.\n")
    w("> Ne jamais débrancher H: pendant que la VM tourne. Ne jamais faire Ctrl-C dans la console **principale** d'un conteneur "
      "(ça arrête son service) : utiliser la console AUX.\n")

    w("## 10. Si quelque chose ne marche pas\n")
    w("| Symptôme | Action (T1) |\n|---|---|")
    for a, b in [
        ("Aucune page ne s'ouvre dans T3", "`python automation/lab_proxy.py start` puis `python automation/lab_proxy.py open`"),
        ("`ssh core-a` refusé / « host identification has changed »", "`python automation/cisco_heal.py`"),
        ("Zabbix/Grafana ne répondent pas", "attendre 2 min après le démarrage, puis `python automation/demo_check.py --profile live`"),
        ("Grafana : 1 panneau vide", "normal juste après le démarrage : attendre 5 min"),
        ("Pages lentes, pings perdus", "`python automation/gns3vm.py --sudo \"sudo swapoff -a && sudo swapon -a\"`"),
        ("GTB bloquée en panne", "ouvrir http://10.70.0.12:8080/api/reset dans T3"),
        ("Compte de la visionneuse verrouillé (après `lock`)", "attendre 5 min"),
        ("Projet GNS3 refuse de s'ouvrir (409)", "relancer `python automation/demo_video/vm_cycle.py --cap 1200000 --start live` (il nettoie les conteneurs)"),
        ("PC très lent / RAM pleine", "fermer le navigateur T3 ; ne pas ouvrir d'autres applications"),
    ]:
        w(f"| {a} | {b} |")
    return "\n".join(L) + "\n"


def main():
    text = md()
    (HERE / "GUIDE_LABO_LIVE.md").write_text(text, encoding="utf-8")
    subprocess.run([sys.executable, str(HERE / "build_demo_script_pdf.py"), "GUIDE_LABO_LIVE"], check=True)


if __name__ == "__main__":
    main()
