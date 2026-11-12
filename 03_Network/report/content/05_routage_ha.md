# Routage et haute disponibilité

## Bordure : opérateurs et routeurs Edge

La bordure relie le Data Center à deux opérateurs indépendants. Chaque routeur Edge établit une session eBGP avec
**chacun** des deux opérateurs ; les deux Edge échangent leurs routes en iBGP entre loopbacks, l'accessibilité des
loopbacks étant assurée par OSPF sur deux chemins (lien inter-Edge et segment de transit 901).

Table: Politique de routage de la bordure
| Élément | Mise en œuvre | Effet |
|---|---|---|
| Annonces sortantes | Liste de préfixes `PL-ANNOUNCE` : 192.0.2.0/24 seulement ; double *AS-path prepend* vers ISP-B | Aucun préfixe interne ne fuit ; trafic entrant préféré par ISP-A |
| Routes acceptées | Liste `PL-DEFAULT` : route par défaut seulement ; préférence locale 200 (ISP-A) / 100 (ISP-B) ; `maximum-prefix 100` | Sortie par ISP-A, bascule automatique vers ISP-B |
| Préfixe public | Route statique 192.0.2.0/24 vers le VIP CARP des pare-feux (10.254.1.1), annoncée par `network` | Le trafic de retour vers 192.0.2.10 / .80 atteint toujours le pare-feu maître |
| Détection de panne | Temporisateurs BGP 3/9 s ; OSPF hello 1 s / dead 3 s sur le lien inter-Edge | Convergence en quelques secondes (scénario T1) |
| Passerelle des pare-feux | HSRPv2 groupe 1, VIP 10.254.1.6 ; EDGE-A priorité 110 (préemption), EDGE-B 100 ; suivi de la route par défaut | Une seule adresse de sortie pour les pare-feux, indépendante de l'Edge actif |
| Sécurité | Authentification MD5 des sessions BGP, des adjacences OSPF et de HSRP ; ACL `ACL-WAN-IN` anti-usurpation ; management en VRF | Protection du plan de contrôle |

Les opérateurs simulés (conteneurs FRR) annoncent uniquement une route par défaut (`default-originate`), filtrent
les annonces du client (192.0.2.0/24 seulement) et traduisent les adresses vers l'Internet réel au travers des
nœuds NAT de GNS3.

## Vérification de la bordure

Les configurations générées ont été déployées par `labctl.py push` (aucune ligne refusée par IOS), puis vérifiées.
Les sorties complètes sont conservées dans `report/evidence/`.

```text title="EDGE-A – show ip bgp summary (extrait)"
BGP router identifier 10.255.0.1, local AS number 65100
Neighbor        V           AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
10.255.0.2      4        65100      47      48        3    0    0 00:02:10        2
198.51.100.1    4        64500     303     296        3    0    0 00:14:49        1
203.0.113.5     4        64501     303     296        3    0    0 00:14:49        1
```

```text title="EDGE-A – show ip ospf neighbor / show standby brief"
Neighbor ID     Pri   State           Dead Time   Address         Interface
10.255.0.2        1   FULL/BDR        00:00:32    10.254.1.3      GigabitEthernet0/3
10.255.0.2        0   FULL/  -        00:00:02    10.254.0.2      GigabitEthernet0/2

Interface   Grp  Pri P State   Active          Standby         Virtual IP
Gi0/3       1    110 P Active  local           10.254.1.3      10.254.1.6
```

```text title="EDGE-A – show ip route (extrait)"
Gateway of last resort is 198.51.100.1 to network 0.0.0.0
B*    0.0.0.0/0 [20/0] via 198.51.100.1, 00:14:16
O        10.255.0.2/32 [110/101] via 10.254.1.3, 00:03:36, GigabitEthernet0/3
                       [110/101] via 10.254.0.2, 00:04:03, GigabitEthernet0/2
S     192.0.2.0/24 [1/0] via 10.254.1.1
```

Table: Synthèse de la vérification de la bordure
| Contrôle | EDGE-A | EDGE-B | Attendu |
|---|---|---|---|
| Sessions BGP établies | 3/3 (iBGP, ISP-A, ISP-B) | 3/3 | 3/3 |
| Route par défaut retenue | via ISP-A (198.51.100.1) | via ISP-A (198.51.100.5) | ISP-A (LP 200) |
| Adjacences OSPF | 2 FULL (Gi0/2, Gi0/3) | 2 FULL | 2 |
| HSRP groupe 1 (VIP 10.254.1.6) | Active, priorité 110 | Standby, priorité 100 | EDGE-A actif |
| Accès Internet (ping 8.8.8.8) | 5/5, 40 ms | 5/5, 41 ms | Succès |

> [!DEV] uRPF retiré des interfaces opérateurs
> La configuration initiale activait l'uRPF en mode lâche (`ip verify unicast source reachable-via any`). Les Edge
> ne recevant qu'une route par défaut, et ce mode ignorant la route par défaut, toutes les réponses venant
> d'Internet étaient rejetées (ping 8.8.8.8 à 0 %). L'option `allow-default` rendrait le contrôle sans effet ;
> l'uRPF est donc retiré et l'anti-usurpation reste assurée par l'ACL `ACL-WAN-IN`, dont l'efficacité est visible
> lors d'un traceroute : les messages ICMP émis depuis des adresses privées sont rejetés et journalisés.

```text title="EDGE-A – traceroute 8.8.8.8 : l'ACL anti-usurpation en action"
  1 198.51.100.1 [AS 64500] 7 msec 2 msec 2 msec
  2  *
%SEC-6-IPACCESSLOGDP: list ACL-WAN-IN denied icmp 192.168.42.1 -> 198.51.100.2 (0/0), 1 packet
```

## Cœur et distribution

Le cœur (MDA) est constitué de deux commutateurs de niveau 3 reliés par un **Port-channel LACP** de deux liens.
Ils portent les passerelles des VLAN métier en **HSRPv2** et routent entre ces VLAN en appliquant le filtrage du
tableau 18. Chaque Leaf (HDA) est relié aux deux cœurs ; les serveurs sont raccordés à deux Leaf du même hall.

Table: Répartition des rôles entre les cœurs (racine spanning-tree alignée sur la passerelle active)
| VLAN | Passerelle virtuelle | HSRP actif (priorité 110) | Racine RPVST+ (priorité 4096) | Secours |
|---|---|---|---|---|
| 20 SERVEURS | 10.20.0.1 | CORE-A | CORE-A | CORE-B (90 / 8192) |
| 30 STOCKAGE | 10.30.0.1 | CORE-B | CORE-B | CORE-A |
| 40 BACKUP | 10.40.0.1 | CORE-A | CORE-A | CORE-B |
| 60 MONITORING | 10.60.0.1 | CORE-A | CORE-A | CORE-B |
| 70 BMS-DCIM | 10.70.0.1 | CORE-B | CORE-B | CORE-A |
| 80 SECURITE-CCTV | 10.80.0.1 | CORE-B | CORE-B | CORE-A |
| 100 SERVICES-INT | 10.100.0.1 | CORE-A | CORE-A | CORE-B |
| 902 TRANSIT-INT | 10.254.2.6 (pour les pare-feux) | CORE-A | CORE-A | CORE-B |

Aligner la racine spanning-tree sur la passerelle HSRP active évite que le trafic d'un VLAN traverse le lien
inter-cœurs pour atteindre sa passerelle : le chemin de commutation et le chemin de routage coïncident.

Table: Mécanismes de la couche cœur/distribution
| Mécanisme | Configuration | Objectif |
|---|---|---|
| Rapid PVST+ (IEEE 802.1w) | Une instance par VLAN, racines réparties, *loop guard* global | Reconvergence rapide, aucune boucle |
| LACP (IEEE 802.3ad) | Po1 = Gi0/2 + Gi0/3, trunk des VLAN 20–100, 902, 998 | Lien inter-cœurs redondant |
| HSRPv2 | Temporisateurs 250/750 ms, préemption différée 30 s, authentification MD5 | Bascule de passerelle en moins d'une seconde |
| OSPF zone 0 | Adjacence sur Vlan998 (point à point) et Vlan902 ; interfaces passives par défaut | Accessibilité des loopbacks, redondance |
| Route par défaut | `0.0.0.0/0` vers le VIP CARP des pare-feux 10.254.2.1 | Sortie Internet et DMZ inspectée |
| ACL inter-VLAN | ACL entrante sur chaque SVI : flux du tableau 18, réponses, refus journalisé | Segmentation interne (A.8.22) |
| Ports serveurs (Leaf) | Accès dans le VLAN du serveur, PortFast, BPDU Guard, *storm-control* | Protection contre boucles et tempêtes |
| Ports inutilisés | VLAN 999, désactivés | Réduction de la surface d'attaque |
| Management | VRF MGMT sur Gi2/0 (cœurs), SVI VLAN 10 non transportée (Leaf) | Isolation du plan de gestion |

## Vérification du cœur et de la distribution

Les six commutateurs IOSvL2 ont été configurés par `labctl.py push` puis contrôlés. Deux limites de l'image IOSvL2
sont apparues lors du déploiement, sans effet sur la fonction : la commande `storm-control` n'est pas implémentée
(elle est désormais omise pour cette plateforme et conservée pour des commutateurs physiques), et la console refuse
les caractères non ASCII des descriptions et remarques (le générateur translittère désormais les accents).

```text title="CORE-A – show standby brief"
Interface   Grp  Pri P State   Active          Standby         Virtual IP
Vl20        20   110 P Active  local           10.20.0.3       10.20.0.1
Vl30        30   90  P Standby 10.30.0.3       local           10.30.0.1
Vl40        40   110 P Active  local           10.40.0.3       10.40.0.1
Vl60        60   110 P Active  local           10.60.0.3       10.60.0.1
Vl70        70   90  P Standby 10.70.0.3       local           10.70.0.1
Vl80        80   90  P Standby 10.80.0.3       local           10.80.0.1
Vl100       100  110 P Active  local           10.100.0.3      10.100.0.1
Vl902       902  110 P Active  local           10.254.2.3      10.254.2.6
```

```text title="CORE-A – show etherchannel summary / show ip ospf neighbor"
Group  Port-channel  Protocol    Ports
1      Po1(SU)         LACP      Gi0/2(P)    Gi0/3(P)

Neighbor ID     Pri   State           Dead Time   Address         Interface
10.255.0.22       1   FULL/BDR        00:00:31    10.254.2.3      Vlan902
10.255.0.22       0   FULL/  -        00:00:02    10.254.4.2      Vlan998
```

```text title="LEAF-A1 – répartition des VLAN sur les deux uplinks (Rapid PVST+)"
Port        Vlans in spanning tree forwarding state and not pruned
Gi0/0       20,40,60,100          <- vers CORE-A (racine de ces VLAN)
Gi0/1       30,70,80              <- vers CORE-B (racine de ces VLAN)
VLAN 20 :  Gi0/0  Root FWD   |   Gi0/1  Altn BLK
```

Table: Synthèse de la vérification du cœur et de la distribution
| Contrôle | Résultat | Attendu |
|---|---|---|
| HSRP actif par VLAN | CORE-A : 20, 40, 60, 100, 902 ; CORE-B : 30, 70, 80 | Conforme au tableau 15 du dossier |
| Racines RPVST+ | Alignées sur la passerelle active de chaque VLAN | Alignées |
| Port-channel Po1 | LACP, 2 membres actifs (SU / P) | 2/2 |
| OSPF entre cœurs | 2 adjacences FULL (Vlan998, Vlan902) | 2 |
| Uplinks des Leaf | Chaque uplink achemine les VLAN de « son » cœur, l'autre est en secours (BLK) | Partage de charge par VLAN |
| Management | VRF MGMT sur Gi2/0 ; 10.10.0.0/24 absent de la table globale | Isolé |
| Sortie Internet depuis le VLAN 20 | `ping 8.8.8.8 source Vlan20` : 5/5 (cœur → pare-feu → SNAT → Edge → ISP) | Succès |
| ICMP vers le VIP du pare-feu depuis le transit | 0/3 (seul le VLAN 60 est autorisé, T18-7) | Refusé |
| CARP sur le LAN des pare-feux | FW-B BACKUP sur les 5 VIP, lagg0 actif sur em3 | FW-A maître |

![FW-B après démarrage du cœur : BACKUP sur les cinq VIP, lagg0 en basculement em3 (actif) / em4 (secours)](../screenshots/16_fw-b_carp_backup_all.png){width=440}

### Panne d'un Leaf (scénario T4, mesuré le 12/11/2026)

Les serveurs de calcul SRV-CMP-01/02 sont raccordés aux deux Leaf du hall A (bond active-backup, surveillance ARP
toutes les 1 s). Le test arrête LEAF-A1 pendant 90 s par l'API GNS3 et interroge en continu l'adresse applicative
partagée `https://10.20.0.10:8443/` depuis SRV-WEB-01 (DMZ), toutes les 0,5 s
(`python automation/fw_lan_failover.py --core LEAF-A1`, trace `report/evidence/fw_lan_failover.txt`).

Table: Résultat du scénario T4 (panne de LEAF-A1)
| Mesure | Résultat | Attendu |
|---|---|---|
| Coupure à l'arrêt de LEAF-A1 | 1 coupure de 3,0 s (3 sondes perdues sur 704) | ≈ 1 s (limite du labo : détection ARP 1 s + reconvergence RPVST+ sur IOSvL2 émulé) |
| Bond des serveurs | ens3 down, ens4 actif sur SRV-CMP-01 et SRV-CMP-02 | Bascule vers LEAF-A2 |
| Adresse applicative | Toujours servie par srv-cmp-01 (pas de bascule keepalived) | Pas de bascule |
| Retour de LEAF-A1 | 0 sonde perdue ; bonds revenus sur ens3 | Sans coupure |
