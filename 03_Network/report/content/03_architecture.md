# Architecture cible

## Architecture en couches

Le réseau reprend l'architecture hiérarchique du dossier de conception. Chaque couche est doublée et chaque élément
d'une couche est relié aux deux éléments de la couche voisine, de sorte qu'aucune panne simple n'interrompe le
service.

Table: Couches du réseau et mécanismes de redondance
| Couche | Équipements (plateforme) | Fonctions | Redondance |
|---|---|---|---|
| Opérateurs | ISP-A AS 64500, ISP-B AS 64501 (FRR, conteneurs) | Transit Internet, route par défaut | Deux opérateurs, deux sessions eBGP par opérateur |
| Bordure (ER) | EDGE-A, EDGE-B (Cisco IOSv) | eBGP, iBGP, annonce de 192.0.2.0/24 | iBGP + OSPF entre Edge, HSRP vers les pare-feux |
| Sécurité (MDA) | FW-A, FW-B (pfSense 2.7.2) | Filtrage par zone, NAT, DMZ | CARP actif/passif, pfsync, synchronisation de configuration |
| Cœur (MDA) | CORE-A, CORE-B (Cisco IOSvL2) | Passerelles des VLAN métier, routage inter-VLAN, filtrage | HSRPv2 réparti, Port-channel LACP, OSPF, racines spanning-tree réparties |
| Distribution (HDA) | LEAF-A1/A2, LEAF-B1/B2 (Cisco IOSvL2) | Accès des serveurs par hall | Chaque Leaf relié aux deux cœurs ; serveurs sur deux Leaf |
| Serveurs (EDA) | VM Ubuntu et conteneurs | Calcul, stockage, sauvegarde, services, supervision | Bonding actif/passif ; VIP VRRP entre SRV-CMP-01 et 02 |
| Management | SW-MGMT, SRV-BASTION, ADMIN-WS | Accès hors bande, administration | Passerelle portée par le VIP CARP des pare-feux |

## Zones de sécurité

Table: Zones et VLAN associés
| Zone | VLAN | Passerelle | Principe |
|---|---|---|---|
| Externe | 901 | Pare-feu (VIP 10.254.1.1) | Aucun flux entrant hors publication web |
| DMZ | 50 | Pare-feu (VIP 10.50.0.1) | Services exposés, isolés de l'interne et du management |
| Interne | 20, 30, 40, 60, 70, 80, 100 | Cœurs (HSRP) | Flux inter-VLAN filtrés par ACL ; sortie Internet via le pare-feu |
| Management | 10 | Pare-feu (VIP 10.10.0.254) | Réseau hors bande, jamais routé par les cœurs |
| Administration | 90 | Pare-feu (VIP 10.90.0.1) | Seul point d'entrée des administrateurs (bastion) |

## Écarts assumés par rapport au dossier de conception

Le dossier de conception fixe les principes ; leur réalisation dans GNS3 a imposé quelques ajustements, tous
documentés ci-dessous et sans effet sur le niveau de redondance visé.

> [!DEV] Segment de transit externe (VLAN 901)
> Le projet GNS3 initial reliait chaque Edge directement à chaque pare-feu (quatre liens point à point), ce qui
> empêche de porter une adresse virtuelle partagée. Un commutateur **SW-OUT** est ajouté, comme le prévoit la section
> 11.3 du dossier, pour créer le segment 10.254.1.0/28 commun aux deux Edge et aux deux pare-feux.

> [!DEV] Passerelle du VLAN 10
> Le tableau 16 du dossier attribue 10.10.0.1 à EDGE-A tout en annonçant « VIP .1 » pour le VLAN 10. Les adresses
> d'équipements du tableau 16 sont conservées et la passerelle du management est placée en **10.10.0.254**.

> [!DEV] Routage des pare-feux
> pfSense ne dispose d'OSPF qu'au travers d'un paquet additionnel. Les pare-feux utilisent donc un routage
> **statique vers des adresses virtuelles** : route par défaut vers le VIP HSRP des Edge (10.254.1.6) et
> 10.0.0.0/8 vers le VIP HSRP des cœurs (10.254.2.6). La bascule reste automatique à chaque niveau ; OSPF est
> conservé entre les Edge et entre les cœurs.

> [!DEV] Liens opérateurs croisés
> Chaque Edge est relié aux deux opérateurs (quatre sessions eBGP au lieu de deux) : la perte d'un Edge ne fait
> perdre aucun opérateur. Les liens primaires du tableau 16 sont conservés ; les liens croisés utilisent
> 198.51.100.4/30 et 203.0.113.4/30.

> [!DEV] Accès Internet réel et poste d'administration
> Deux nœuds NAT GNS3 raccordent les opérateurs simulés à Internet afin d'installer les services (Zabbix, NFS, DNS)
> et de tester des destinations réelles ; le trafic traverse toujours le NAT du pare-feu, Edge et ISP. Un poste
> **ADMIN-WS** (conteneur avec navigateur) est ajouté dans le VLAN 90 pour administrer les interfaces web et
> produire les captures d'écran.
