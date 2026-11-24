# Script de la démo en direct – Partie 3 (5 min)

Vidéo jury : `video/DC_Casablanca_demo_5min.mp4` (**3:36**, voix off + sous-titres FR, 1080p).
Version longue : `video/DC_Casablanca_walkthrough.mp4` (**9:30**, 4 actes : réseau, supervision, calcul, sauvegarde).
Sous-titres : fichiers `.srt` à côté. Règle : la vidéo parle déjà. Toi, tu **mets en pause** aux repères ★ et tu dis
la phrase en gras. Le reste du temps, silence.

## Minute par minute (vidéo jury)

| Temps | Écran | Rôle → test → résultat (ce que dit la voix) | Toi (pendant la pause, ≤ 15 s) |
|---|---|---|---|
| 0:00 | Titre | Labo GNS3 en direct ; pour chaque machine : rôle, test, résultat | « Tout ce que vous allez voir est enregistré sur notre labo GNS3, rien n’est monté. » |
| 0:13 | GNS3 Web UI + lab_up (×27) | Démarrage à froid par étages, mémoire mesurée, PC 15,7 Go | « Les liens passent du rouge au vert ; on démarre par étages parce que le PC n’a que 15,7 Go. » |
| 0:29 ★ | Console GNS3 sur CORE-A | Cœur L3 → `show standby brief` → actif sur 5 groupes HSRP, CORE-B sur les 3 autres | **Pause.** « Chaque cœur est maître sur une partie des VLAN et secours de l’autre. » |
| 0:57 | SSH depuis ADMIN-WS | OSPF + LACP → 2 voisins FULL, Po1 avec 2 liens | – |
| 1:07 ★ | pfSense FW-A › CARP | Pare-feu HA → 5 VIP MASTER sur FW-A | **Pause.** « Cinq adresses virtuelles maîtres ; FW-B les reprend si FW-A tombe : vous le verrez à 2:47. » |
| 1:21 | ISP-A → 192.0.2.80 | Site public en DMZ → « OK SRV-WEB-01 » via le NAT | – |
| 1:33 | log_viewer.py demo | SOC : 3 événements retrouvés en moins de 0,5 s | – |
| 1:53 ★ | Grafana en direct | Chemins A/B 47,1 %, 96 baies, 942 kW, PUE 1,45, entrée max ≈ 24,5 °C | **Pause.** « Le NOC en direct : énergie, baies, PUE, et la salle dans sa consigne de 20 à 25 °C. » |
| 2:13 | GTB / DCIM | T6 : chemin A coupé → alarme, baies en dégradé, chemin B seul, puis retour | – |
| 2:27 | SRV-MON-01 → ADMIN-WS | Cloisonnement : connexion échoue, compteur deny 210 : 0 → 1 | « Refus par défaut : la supervision ne peut pas ouvrir de session sur l’administration. » |
| 2:47 ★ | Sonde 0,5 s + chrono | T2 : FW-A arrêté → FW-B maître, **coupure 2,5 s** (prise du 23/11, profil complet) | **Pause sur « 2,5 s ».** « Cible Tier III : moins de 5 s. Mesuré : 2,5 s, sans intervention. » |
| 3:03 | demo_check.py | Preuve sur le profil démo complet : 12/12 | – |
| 3:09 ★ | fw_lan_failover.py | T5 : SRV-CMP-01 arrêté → la VIP passe sur SRV-CMP-02, **coupure 4,5 s** | **Pause.** « Le service applicatif survit à la perte d’un serveur : keepalived déplace l’adresse. » |
| 3:23 | TrueNAS | NAS en mode pull : pool `tank` ONLINE en miroir, 21 snapshots, 3 tâches de tirage | « Le NAS tire les sauvegardes : un serveur compromis ne peut pas effacer ses copies. » |

Il reste ≈ 1 min 30 sur les 5 : questions du jury pendant la démo.

## Si le jury interrompt

- **« C’est vraiment en direct ? »** Oui. Le démarrage, la console GNS3, le SSH, pfSense, le web, le SOC, Zabbix, Grafana, T6, l’ACL, le calcul (T5) et le NAS ont été filmés en direct la nuit du 23 au 24/11 et le matin du 24/11. Seules T2 et la preuve 12/12 viennent de la prise du 23/11 au matin : elles exigent les deux pare-feux et tout le profil démo en même temps.
- **« Pourquoi pas tout allumé ? »** 15,7 Go de RAM pour 32 nœuds : on démarre par profils (réseau, supervision, calcul, NAS), et la VM GNS3 est redémarrée entre deux profils pour rendre la mémoire au PC. C’est de la gestion de capacité du labo, pas une limite de l’architecture cible.
- **« T5 : 4,5 s ici, 3,1 s sur la slide redondance ? »** Deux mesures réelles à des jours différents ; ici CORE-A était seul (profil réduit). Les deux restent dans la cible « service repris par SRV-CMP-02 ».
- **« La restauration ? »** Version longue (8:52) : un fichier recopié depuis le snapshot ZFS a la même empreinte SHA-256 que la copie en ligne.
- **« Un SIEM ? »** Non : journalisation centralisée (SYSLOG + visionneuse + verrouillage après 6 essais). Pas de Wazuh/ELK.
- **« AD / LDAP ? »** Prévu après la soutenance (slide AD/LDAP).
- **« Les mots de passe ? »** Jamais tapés en clair : champs masqués, rien de secret sur une ligne de commande SSH (ADMIN-WS journalise chaque commande).

## Plan B / technique

- Lecteur Windows (Films et TV) ou VLC ; **Espace** = pause.
- Sous-titres déjà incrustés ; les `.srt` servent seulement si on veut les changer.
- Si la vidéo ne se lance pas : slide 21 (minutage) + slide 22 (preuves) suffisent à raconter la démo.
