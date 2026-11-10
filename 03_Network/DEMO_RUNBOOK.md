# Runbook de la démonstration – DC Casablanca (lab GNS3)

Tout se lance depuis le PC Windows, dans un terminal ouvert sur le dossier `03_Network`.
Les identifiants sont ceux du lab (inventaire `inventory/dc_casa.yaml`, rubrique `credentials`) ; ils ne servent nulle part ailleurs.
Répété à froid le @@DATE@@ : **@@TOTAL@@** entre « tout arrêté » et « 11/11 contrôles OK », sans aucune correction manuelle.

## 1. Démarrage (T – 25 min)

| Étape | Commande / action | Durée |
|---|---|---|
| 1 | Démarrer la VM **GNS3 VM** (VMware), puis ouvrir le projet `DC_Casablanca_TIA942_R3` dans GNS3 | 2 min |
| 2 | `python automation/lab_up.py --profile demo` : 4 étapes de démarrage, vidage du swap, proxy, maintenance Zabbix | @@LABUP@@ |
| 3 | `python automation/demo_check.py` : **11 lignes OK** attendues (sinon suivre la ligne `->` affichée) | @@CHECK@@ |
| 4 | `python automation/lab_proxy.py open` : fenêtre Edge qui navigue « comme ADMIN-WS » (onglets ci-dessous) | 10 s |

Profil `demo` = 20 nœuds : NAT-A/B, ISP-A/B, SW-OUT, SW-DMZ, SW-MGMT, EDGE-A, FW-A, FW-B, CORE-A, CORE-B, LEAF-B1, LEAF-B2,
ADMIN-WS, SYSLOG, BMS-SIM, SRV-DCIM-01, SRV-WEB-01, SRV-MON-01. Hors profil (mémoire du PC) : hall A, EDGE-B, SRV-INF-01
(DNS/NTP), CCTV-SIM, bastion, NAS SRV-BCK-01 – ils sont en maintenance Zabbix `demo-off` et le tableau de bord affiche
« hors profil » pour eux.

Avant de commencer : RAM libre du PC ≥ 0,5 Go (fermer navigateurs et applications inutiles), swap de la VM GNS3 ≈ 0
(ligne `resources` de `demo_check.py`).

## 2. Adresses et comptes

| Interface | Adresse | Compte | Mot de passe |
|---|---|---|---|
| Grafana – tableau NOC (page d'accueil) | http://10.60.0.11:3000/ | `admin` | `Grafana-DC-2026!` |
| Zabbix – problèmes | http://10.60.0.11/ | `Admin` | `Zbx-Supervision-2026!` |
| Journaux (lecture seule) | https://10.60.0.12/ | `netadmin` | `Esprim-DC-2026!` |
| pfSense (maître CARP) | https://10.90.0.1/ | `admin` | `Esprim-DC-2026!` |
| BMS-SIM (chaîne électrique) | http://10.70.0.12:8080/ | – | – |
| DCIM (96 baies) | http://10.70.0.11:8080/ | – | – |
| Site web DMZ | https://10.50.0.11/ | – | – |
| Équipements Cisco (SSH depuis ADMIN-WS) | `ssh core-a`, `ssh leaf-b1`… | `netadmin` | `Esprim-DC-2026!` |

Certificats auto-signés : accepter l'avertissement du navigateur.

## 3. Scénario de démonstration (≈ 15 min)

### A. Coupure électrique → Zabbix → Grafana rouge → retour (5 min)
1. Grafana, tableau **NOC** : toutes les rangées vertes (chemins A et B alimentés, charge ≈ 47 % chacun).
2. Onglet BMS-SIM, couper le chemin A :
   `http://10.70.0.12:8080/api/set?UTILITY-A=DOWN&UPS-A=DOWN&GENERATOR=DOWN`
3. Zabbix > Problèmes : « chemin A non alimenté » (désastre) en **6 à 10 s**.
   Grafana : rangée **Énergie** rouge en **moins de 10 s** (chemin A DOWN, chemin B à 94 %, GTB CRITICAL).
   Message : le chemin B porte toute la charge (Tier III, maintenance concurrente) mais dépasse le seuil de 50 %.
4. Rétablir : `http://10.70.0.12:8080/api/reset` → tout redevient vert en **≈ 6 s**.
   Secours scripté : `python automation/power_test.py` (coupe, chronomètre, rétablit).

### B. Échec de connexion et modification de configuration → journaux (5 min)
1. Console **ADMIN-WS** (GNS3, double-clic → poste d'administration), terminal : `ssh core-a`, taper un **mauvais** mot de passe.
2. Onglet Journaux : source **CORE-A**, texte `LOGIN_FAILED` → ligne `%SEC_LOGIN-4-LOGIN_FAILED ... [Source: 10.90.0.12]`
   en 2 à 3 s.
3. `ssh core-a` avec le bon mot de passe, `configure terminal`, `end`, `exit`.
   Journaux, texte `CONFIG_I` → `%SYS-5-CONFIG_I: Configured from console by netadmin on vty0 (10.90.0.12)`.
4. Montrer la source **SYSLOG-viewer** (127.0.0.1) : le lecteur journalise lui-même chaque connexion et chaque recherche
   (ISO 27001 A.8.15 : qui a consulté quoi). Il ne peut ni modifier ni supprimer un journal.
   Secours scripté : `python automation/log_viewer.py demo` (les 3 événements B et C, chronométrés).

### C. Flux interdit DMZ → management → blocage pare-feu journalisé (3 min)
1. Console auxiliaire de SRV-WEB-01 : `telnet 192.168.75.128 5052`, puis `nc -z -w 3 10.10.0.21 22` (aucune réponse).
2. Journaux : source **FW-A**, texte `10.50.0.11,10.10.0.21` → ligne `filterlog ... block,in ... 10.50.0.11,10.10.0.21,...,22`
   (règle T18-9 « DMZ → MGMT/ADMIN/STOCKAGE/BACKUP interdit », tracker 1700000021).
3. pfSense > Status > System Logs > Firewall : la même ligne avec le libellé de la règle.

### D. Questions fréquentes (si le temps le permet)
- Sauvegardes : NAS TrueNAS SRV-BCK-01 (profil `nas`, pas dans ce profil faute de RAM) – sauvegardes tirées par le NAS,
  restauration prouvée (`report/evidence/nas5_restore.txt`).
- Résilience : CARP FW-A/FW-B, HSRP CORE-A/CORE-B, LACP vers les leafs – voir le rapport technique.

## 4. Si quelque chose échoue

| Symptôme | Cause probable | Action |
|---|---|---|
| `demo_check.py` affiche FAIL | voir la ligne `->` sous le FAIL | appliquer la commande proposée, relancer `demo_check.py` |
| Pings qui se perdent (30-90 %), pages lentes | swap de la VM GNS3 → CORE-A ralenti → loop guard des leafs | `python automation/gns3vm.py --sudo "swapoff -a && swapon -a"` ; ligne `loop guard` de `demo_check.py` |
| Aucune page ne s'ouvre depuis Edge | proxy arrêté (ADMIN-WS redémarré) | `python automation/lab_proxy.py start` |
| Zabbix ou Grafana ne répond pas juste après le démarrage | services de SRV-MON-01 encore en démarrage | attendre 2 min ; `demo_check.py` (ligne SRV-MON-01) |
| Lecteur de journaux : pas de réponse | conteneur SYSLOG qui vient de démarrer | attendre 10 s ; sinon `python automation/labctl.py start SYSLOG` |
| Grafana « hors profil » sur un panneau | l'équipement n'est pas démarré dans ce profil | normal ; le dire (contrainte de RAM du PC) |
| Coupure BMS sans effet / bloquée | simulateur dans un état modifié | `http://10.70.0.12:8080/api/reset` |
| Heure des équipements Cisco décalée | pas de NTP dans ce profil (SRV-INF-01 arrêté), horloge émulée qui dérive | lire la 1re colonne (heure du collecteur) ; `python automation/syslog_audit.py --set-clock` |
| Ouverture du projet refusée (409) | conteneurs restés après un arrêt brutal de la VM | voir le guide du lab, section consoles Docker |
| VM GNS3 figée | mémoire du PC saturée | **ne pas** la redémarrer en pleine démo : utiliser les preuves `report/evidence/demo_s*` et les PDF |

## 5. Arrêt propre

1. `python automation/lab_down.py` : arrêt depuis l'intérieur des VM (Ubuntu, pfSense, TrueNAS), puis de tous les nœuds,
   puis du proxy (@@DOWN@@).
2. Dans GNS3 : fermer le projet, **puis** arrêter la VM GNS3.
