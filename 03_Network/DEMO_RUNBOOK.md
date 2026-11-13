# Runbook de la démonstration – DC Casablanca (lab GNS3)

Tout se lance depuis le PC Windows, dans un terminal ouvert sur le dossier `03_Network`.
Les identifiants sont ceux du lab (inventaire `inventory/dc_casa.yaml`, rubrique `credentials`) ; ils ne servent nulle part ailleurs.
Répété à froid le 10 novembre 2026 : arrêt propre en **1 min**, démarrage en **≈ 12 min**, puis **12/12 contrôles OK**
(en 65 s), sans aucune correction manuelle (après rotation des clés SNMP : les 5 équipements Cisco redémarrent avec le
nouvel utilisateur). Puis `verify_lab.py` : **59 PASS, 0 FAIL**, 1 limite connue, 2 N/A (`report/evidence/verify_lab.txt`).
Si `grafana` montre 1 panneau vide juste après le démarrage : attendre 5 min et relancer `demo_check.py`. Lancer le démarrage **25 min avant** la démonstration.

## 1. Démarrage (T – 25 min)

| Étape | Commande / action | Durée |
|---|---|---|
| 1 | Démarrer la VM **GNS3 VM** (VMware), puis ouvrir le projet `DC_Casablanca_TIA942_R3` dans GNS3 | 2 min |
| 2 | `python automation/lab_up.py --profile demo` : 4 étapes de démarrage (2 min 30 chacune), vidage du swap, réparation Cisco (`cisco_heal.py`), proxy, maintenance Zabbix | ≈ 12 min |
| 3 | `python automation/demo_check.py` : **12 lignes OK** attendues (sinon suivre la ligne `->` affichée) | 1 min |
| 4 | `python automation/lab_proxy.py open` : fenêtre Edge qui navigue « comme ADMIN-WS » (onglets ci-dessous) | 10 s |

Profil `demo` = 20 nœuds : NAT-A/B, ISP-A/B, SW-OUT, SW-DMZ, SW-MGMT, EDGE-A, FW-A, FW-B, CORE-A, CORE-B, LEAF-B1, LEAF-B2,
ADMIN-WS, SYSLOG, BMS-SIM, SRV-DCIM-01, SRV-WEB-01, SRV-MON-01. Hors profil (mémoire du PC) : hall A, EDGE-B, SRV-INF-01
(DNS/NTP), CCTV-SIM, bastion, NAS SRV-BCK-01 – ils sont en maintenance Zabbix `demo-off` et le tableau de bord affiche
« hors profil » pour eux.

La veille : `python automation/verify_lab.py --save` (≈ 10 min, tous les tests de « Test the Lab » possibles dans ce
profil : PASS attendu partout, 1 limite connue (heure ADMIN-WS), N/A pour les nœuds hors profil). **Jamais `--disruptive`
juste avant la démonstration** (LEAF-B2 refuse SSH pendant ≈ 4 min).

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
4. Rétablir : `http://10.70.0.12:8080/api/reset` → Grafana redevient vert en **≈ 6 s**, les problèmes Zabbix se ferment
   en **12 à 16 s**.
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
- Résilience (chiffres mesurés, preuves `report/evidence/fw_lan_failover.txt`) :
  - pare-feu : FW-A arrêté → FW-B maître des 5 adresses CARP, coupure **3,0 s** ;
  - cœur : CORE-A ou CORE-B arrêté → l'autre reprend toutes les passerelles HSRP, coupure **4,5 s** vue à travers les pare-feu ;
  - calcul : SRV-CMP-01 arrêté → SRV-CMP-02 reprend l'adresse applicative 10.20.0.10 (keepalived), coupure **3,1 s** ;
    au retour de SRV-CMP-01 : 4,5 s pendant son démarrage, puis aucune perte quand l'adresse revient (profil `compute`,
    pas dans ce profil faute de RAM) ;
  - chaque serveur a deux cartes vers deux leafs (bond actif/secours surveillé par ARP) ; LACP (Po1) relie les deux cœurs.
  - Non redondants (assumé, lab sur un PC) : le nœud de stockage SRV-STO-01 (non déployé), Zabbix/Grafana, le collecteur
    syslog, DNS/NTP. Perte d'un leaf (T4, 12 nov.) : coupure 3,0 s, aucune perte au retour. Non mesuré : perte d'un fournisseur Internet (T1).
- TrueNAS = **NAS de sauvegarde SRV-BCK-01** (salle B, autre salle que les données), pas le stockage de production :
  il **tire** chaque nuit à 02:00 (rsync en lecture seule, les serveurs n'ont aucun accès aux sauvegardes) la base Zabbix,
  Grafana et /etc de SRV-MON-01, /etc de SRV-INF-01 ; instantanés ZFS horaires (24 h) et quotidiens (14 j) sur un miroir
  de 2 disques ; restauration prouvée (`report/evidence/nas5_restore.txt`). Profil `nas`, pas dans ce profil faute de RAM.
  S'il tombe : la production continue, seules les sauvegardes s'arrêtent, Zabbix alerte (ICMP). Rien ne le remplace
  (une 2e copie hors site serait l'étape suivante).

## 4. Si quelque chose échoue

| Symptôme | Cause probable | Action |
|---|---|---|
| `demo_check.py` affiche FAIL | voir la ligne `->` sous le FAIL | appliquer la commande proposée, relancer `demo_check.py` |
| `ssh core-a` refusé ou « REMOTE HOST IDENTIFICATION HAS CHANGED », Zabbix « Unknown user name » | l'IOSvL2 a démarré sans sa clé RSA ni son utilisateur SNMPv3 (private-config non chargée, CORE-A à chaque démarrage) | `python automation/cisco_heal.py` (déjà lancé par `lab_up.py`) |
| Pings qui se perdent (30-90 %), pages lentes | swap de la VM GNS3 → CORE-A ralenti → loop guard des leafs | `python automation/gns3vm.py --sudo "swapoff -a && swapon -a"` ; ligne `loop guard` de `demo_check.py` |
| Aucune page ne s'ouvre depuis Edge | proxy arrêté (ADMIN-WS redémarré) | `python automation/lab_proxy.py start` |
| Zabbix ou Grafana ne répond pas juste après le démarrage | services de SRV-MON-01 encore en démarrage | attendre 2 min ; `demo_check.py` (ligne SRV-MON-01) |
| Lecteur de journaux : pas de réponse | conteneur SYSLOG qui vient de démarrer | attendre 10 s ; sinon `python automation/labctl.py start SYSLOG` |
| Grafana « hors profil » sur un panneau | l'équipement n'est pas démarré dans ce profil | normal ; le dire (contrainte de RAM du PC) |
| Coupure BMS sans effet / bloquée | simulateur dans un état modifié | `http://10.70.0.12:8080/api/reset` |
| Heure des équipements Cisco décalée | pas de NTP dans ce profil (SRV-INF-01 arrêté), horloge émulée qui dérive | lire la 1re colonne (heure du collecteur) ; `python automation/syslog_audit.py --set-clock` |
| 1 h d'écart entre ADMIN-WS (+00) et le collecteur / Zabbix / pfSense (+01) | le Maroc est revenu à UTC+0 le 20 sept. 2026 (tzdata 2026c, Windows) ; seules les images récentes le savent (ADMIN-WS, BMS, DCIM, web) | le dire ; chaque ligne de journal porte son décalage (+01:00), l'ordre des événements est juste |
| `demo_check` : ligne `redundancy` FAIL | un nœud « started » dans GNS3 mais figé (CORE-B le 10 nov.) | `python automation/labctl.py stop X`, puis `start X`, puis `python automation/cisco_heal.py X` |
| Ouverture du projet refusée (409) | conteneurs restés après un arrêt brutal de la VM | voir le guide du lab, section consoles Docker |
| VM GNS3 figée | mémoire du PC saturée | **ne pas** la redémarrer en pleine démo : utiliser les preuves `report/evidence/demo_s*` et les PDF |

## 5. Arrêt propre

1. `python automation/lab_down.py` : arrêt depuis l'intérieur des VM (Ubuntu, pfSense, TrueNAS), puis de tous les nœuds,
   puis du proxy (≈ 1 min).
2. Dans GNS3 : fermer le projet, **puis** arrêter la VM GNS3.
