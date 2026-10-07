# Normes et référentiels appliqués

Le laboratoire applique les référentiels retenus dans le dossier de conception. Le tableau suivant indique, pour
chaque norme, l'exigence retenue et sa traduction concrète dans la configuration ; il sert de grille de contrôle
pour la recette.

Table: Traçabilité des normes dans la configuration du laboratoire
| Référentiel | Exigence retenue | Mise en œuvre dans le laboratoire |
|---|---|---|
| ANSI/TIA-942-C, Rated-3 | Maintenance de tout composant sans interruption ; pas de point unique de défaillance | Chaque niveau est doublé (ISP, Edge, pare-feu, cœur, Leaf) ; serveurs critiques raccordés à deux Leaf ; tests T1 à T6 |
| ANSI/TIA-942-C, espaces | Séparation ER/MMR, MDA, HDA, EDA | Rattachement de chaque nœud à un espace (tableau suivant) et repris dans les libellés d'interfaces |
| ANSI/TIA-606-C | Identification univoque des liens et des ports | Description de chaque interface au format `ESPACE-ÉQUIPEMENT:port -> ESPACE-ÉQUIPEMENT:port` |
| ANSI/TIA-568 | Câblage structuré, chemins A et B | Doublement des uplinks (Leaf vers les deux cœurs) et des liens serveurs (NIC0 / NIC1) |
| ISO/IEC 27001/27002 – A.8.22 | Ségrégation des réseaux | 14 VLAN, zones DMZ / interne / management / administration, refus par défaut |
| ISO/IEC 27001/27002 – A.8.20, A.8.21 | Sécurité des réseaux et des services réseau | Pare-feux en HA, ACL inter-VLAN sur les cœurs, filtrage BGP (préfixes, max-prefix) |
| ISO/IEC 27001/27002 – A.8.2, A.5.17 | Accès privilégiés, authentification | Accès d'administration uniquement depuis le VLAN 90 (bastion), SSH v2, MFA (TOTP) sur le bastion |
| ISO/IEC 27001/27002 – A.8.9 | Gestion des configurations | Configurations générées depuis l'inventaire et versionnées dans Git |
| ISO/IEC 27001/27002 – A.8.15, A.8.16 | Journalisation, surveillance | Syslog centralisé (10.60.0.12), Zabbix, journalisation des règles de refus |
| ISO/IEC 27001/27002 – A.8.17 | Synchronisation des horloges | NTP unique (10.100.0.11) pour tous les équipements et serveurs |
| IEEE 802.1Q / 802.1w / 802.3ad | VLAN, spanning-tree rapide, agrégation | Trunks 802.1Q, Rapid PVST+, Port-channel LACP entre cœurs |
| RFC 1918, 5737, 5398 | Adressage privé, adresses et ASN de documentation | 10.0.0.0/8 interne ; 192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24 ; AS 64500/64501, AS 65100 (privé) |
| RFC 4271, 2328, 2281 / HSRPv2, CARP | BGP-4, OSPFv2, redondance de passerelle | eBGP/iBGP en bordure, OSPF zone 0, HSRPv2 sur les cœurs et la bordure, CARP sur les pare-feux |
| Guides de durcissement (type CIS) | Réduction de la surface d'attaque | Telnet désactivé, bannières légales, chiffrement des mots de passe, SNMPv3 authPriv, ports inutilisés désactivés dans le VLAN 999, BPDU Guard et storm-control sur les ports serveurs |

Table: Correspondance entre espaces TIA-942 et nœuds du laboratoire
| Espace TIA-942 | Rôle | Nœuds du laboratoire |
|---|---|---|
| ER / MMR (Entrance Room) | Arrivée des opérateurs, démarcation | ISP-A, ISP-B, EDGE-A, EDGE-B, SW-OUT |
| MDA (Main Distribution Area) | Cœur, sécurité, management | FW-A, FW-B, CORE-A, CORE-B, SW-DMZ, SW-MGMT, SRV-BASTION, ADMIN-WS |
| HDA-A / HDA-B (Horizontal Distribution Area) | Distribution par hall | LEAF-A1, LEAF-A2 (hall A) ; LEAF-B1, LEAF-B2 (hall B) |
| EDA-A / EDA-B (Equipment Distribution Area) | Baies serveurs | Serveurs et conteneurs du hall A et du hall B |

> [!NOTE] Convention de libellé
> Exemple de description d'interface sur CORE-A : `MDA-CORE-A:Gi1/0 -> HDA-A-LEAF-A1:Gi0/0 | Uplink Hall A`.
> Le même libellé se retrouve dans le plan de câblage, ce qui permet de suivre un lien de bout en bout.
