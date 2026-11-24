# Script de la démo en direct – Partie 3 (5 min)

Vidéo jury : `video/DC_Casablanca_demo_5min.mp4` (**2:57**, voix off + sous-titres FR, 1080p).
Version longue : `video/DC_Casablanca_walkthrough.mp4` (**6:33**, plan B / annexe). Sous-titres : fichiers `.srt` à côté.
Règle : la vidéo parle déjà. Toi, tu **mets en pause** aux 4 repères ★ et tu dis la phrase en gras. Le reste du temps, silence.

## Minute par minute (vidéo jury)

| Temps | Écran | Rôle → test → résultat (ce que dit la voix) | Toi (pendant la pause, ≤ 15 s) |
|---|---|---|---|
| 0:00 | Titre | Labo GNS3 en direct ; pour chaque machine : rôle, test, résultat | « Tout ce que vous allez voir est enregistré sur notre labo GNS3, rien n’est monté. » |
| 0:13 | GNS3 Web UI + lab_up (×27) | Démarrage à froid par étages (WAN, sécurité, cœur), mémoire mesurée, PC 15,7 Go | « Les liens passent du rouge au vert. On démarre par étages parce que le PC n’a que 15,7 Go. » |
| 0:29 ★ | Console GNS3 sur CORE-A | Cœur L3, passerelles HSRP partagées avec CORE-B → `show standby brief` → actif sur 5 groupes, CORE-B sur les 3 autres | **Pause.** « Chaque cœur est maître sur une partie des VLAN et secours de l’autre : aucun équipement ne porte tout seul. » |
| 0:57 | SSH depuis ADMIN-WS | OSPF + LACP entre les cœurs → 2 voisins FULL, Po1 avec 2 liens | – |
| 1:07 ★ | pfSense FW-A, Status › CARP | Pare-feu HA (CARP + pfsync) → 5 VIP MASTER sur FW-A, FW-B en secours | **Pause.** « Cinq adresses virtuelles maîtres sur FW-A ; FW-B les reprend si FW-A tombe : vous le verrez dans une minute. » |
| 1:21 | ISP-A → 192.0.2.80 | Site public en DMZ, testé depuis Internet → « OK SRV-WEB-01 » via le NAT | – |
| 1:33 | SRV-MON-01 → ADMIN-WS | Cloisonnement : VLAN 60 → administration → code retour 1, compteurs deny de l’ACL | « Refus par défaut : la supervision ne peut pas ouvrir de session sur l’administration. » |
| 1:46 | log_viewer.py demo | SOC : 3 événements provoqués, retrouvés en moins de 0,5 s dans la visionneuse | – |
| 2:06 | Grafana NOC (capture) | Chemins A/B 47,1 %, 96 baies, 942 kW, PUE 1,45 ; 29,5 °C = dérive simulateur, corrigée | Si le jury relève les 29,5 °C : « dérive du simulateur DCIM, corrigée en code et déployée (D28) ; la consigne reste 20–25 °C. » |
| 2:21 | GTB / DCIM | Panne T6 : chemin A coupé → alarme, baies en dégradé, chemin B seul, puis retour | – |
| 2:35 ★ | Sonde 0,5 s + chrono | Panne T2 : FW-A arrêté → FW-B maître, **coupure 2,5 s** | **Pause sur « 2,5 s ».** « Cible Tier III : moins de 5 s. Mesuré : 2,5 s, sans intervention humaine. » |
| 2:51 ★ | demo_check.py | Preuve : 12 contrôles sur 12 | **Pause.** « Douze contrôles automatiques, des nœuds jusqu’à la redondance : 12 sur 12. » |

Il reste ≈ 2 min sur les 5 : questions du jury pendant la démo.

## Si le jury interrompt

- **« C’est vraiment en direct ? »** Le démarrage, la console GNS3, le SSH, pfSense, le site web et le SOC ont été filmés la nuit du 23 au 24/11. Zabbix, Grafana, T6, T2 et demo_check viennent des prises en direct du 23/11 au matin (profil démo complet). Le PC ne peut pas filmer la supervision et faire tourner tous les nœuds en même temps.
- **« Pourquoi pas tout allumé ? »** 15,7 Go de RAM pour 32 nœuds : on démarre par profils (démo, calcul, NAS). C’est de la gestion de capacité, pas un défaut de l’architecture cible.
- **« Et le calcul, le NAS ? »** Montrés dans le rapport : bascule T5 keepalived 3,1 s, NAS TrueNAS en mode pull, restauration avec le même SHA-256.
- **« Un SIEM ? »** Non : journalisation centralisée (SYSLOG + visionneuse + verrouillage). Pas de Wazuh/ELK dans le labo.
- **« AD / LDAP ? »** Prévu après la soutenance (slide AD/LDAP).
- **« Les mots de passe ? »** Jamais tapés en clair : champs masqués, et rien de secret sur une ligne de commande SSH (ADMIN-WS journalise chaque commande).

## Plan B / technique

- Ouvrir la vidéo avec le lecteur Windows (Films et TV) ou VLC ; touche **Espace** = pause.
- Sous-titres déjà incrustés ; les `.srt` servent seulement si on veut les changer.
- Si la vidéo ne se lance pas : slide 21 (minutage) + slide 22 (preuves) suffisent à raconter la démo.
