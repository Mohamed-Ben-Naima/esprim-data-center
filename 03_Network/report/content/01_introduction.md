# Introduction

## Contexte

Le dossier de conception a défini un Data Center de production de 96 baies réparties en deux halls, pour une
charge informatique d'environ 1 MW, avec un objectif de résilience **Rated-3** : tout composant critique doit pouvoir
être maintenu sans interruption du service. Côté réseau, cela se traduit par une architecture **hiérarchique et
entièrement doublée** : deux opérateurs, deux routeurs de bordure, deux pare-feux, deux cœurs et des Leaf par paires.

La validation de cette architecture est réalisée dans **GNS3**, sur un PC personnel. Le présent rapport décrit la
configuration effective du laboratoire, les mesures prises pour respecter les normes et les résultats des tests de
résilience.

## Objectifs

- configurer l'ensemble des équipements du laboratoire conformément au plan de VLAN et d'adressage ;
- mettre en œuvre la haute disponibilité à chaque niveau : BGP multi-opérateur, HSRP, CARP, spanning-tree rapide,
  agrégation LACP, bonding des serveurs ;
- appliquer une politique de sécurité en **refus par défaut** avec segmentation en zones (DMZ, interne,
  management, administration) ;
- déployer les services d'infrastructure et la supervision (DNS, NTP, syslog, Zabbix, Grafana, DCIM) ;
- exécuter les scénarios de panne T1 à T6 et mesurer les temps de reconvergence ;
- documenter chaque choix de façon traçable vis-à-vis des normes.

## Démarche

La configuration n'est pas saisie à la main équipement par équipement. Une **source unique de vérité**
(`inventory/dc_casa.yaml`) décrit le réseau ; des scripts génèrent les configurations, les poussent sur les consoles
des équipements via l'API de GNS3, collectent les preuves (sorties de commandes, captures d'écran) et alimentent les
tableaux du rapport. Cette approche garantit la cohérence entre la documentation et le réseau réel, et rend le
laboratoire reproductible.

Table: Phases du plan d'exécution
| Phase | Contenu | Livrables principaux |
|---|---|---|
| 0 | Sauvegarde du travail, arborescence, chaîne de génération du rapport | `plans/`, `report/`, `screenshots/` |
| 1 | Source de vérité et générateurs | `inventory/dc_casa.yaml`, `automation/` |
| 2 | Évolutions de topologie, préparation de la plateforme | SW-OUT, NAT, ADMIN-WS, images Docker |
| 3 | WAN et bordure (ISP, EDGE) | eBGP/iBGP, OSPF, HSRP de transit |
| 4 | Pare-feux pfSense en haute disponibilité | CARP, pfsync, NAT, règles par zone |
| 5 | Cœur et Leaf | VLAN, RPVST+, LACP, HSRP, OSPF, ACL inter-VLAN |
| 6 | Serveurs et conteneurs | Bonding, rôles (stockage, sauvegarde, DNS/NTP, web) |
| 7 | Supervision | Zabbix, Grafana, syslog, DCIM/BMS |
| 8 | Tests de résilience | Scénarios T1 à T6, maintenance combinée |
| 9 | Documentation finale | Rapport, figures, captures |

## Organisation du dossier réseau

Table: Arborescence du dossier `03_Network`
| Dossier / fichier | Contenu |
|---|---|
| `DC_Casablanca_TIA942_R3.gns3` | Projet GNS3 (topologie, nœuds, liens) |
| `DC_Casablanca_TIA942_R3_wiring.csv` | Plan de câblage (rôle, extrémités, interfaces) |
| `plans/` | Plan d'exécution et suivi |
| `inventory/` | Source unique de vérité du réseau |
| `automation/` | Générateurs, pilotage des consoles, tests de résilience |
| `configs/` | Configurations générées des équipements |
| `docker/` | Images des services conteneurisés |
| `screenshots/` | Captures d'écran numérotées |
| `report/` | Ce rapport (`content/*.md` → `.docx` / `.pdf`) et ses preuves |
| `fixgns3.ps1`, `gen_gns3.py` | Réparation de l'environnement GNS3, génération de la topologie |

## Suivi de réalisation

Le tableau ci-dessous est mis à jour à chaque sous-tâche ; l'historique détaillé est conservé dans Git.

Table: Avancement des sous-tâches
| Sous-tâche | Description | État |
|---|---|---|
| Préalable | Remise en état de l'environnement GNS3 (VM, Docker, projet) | **Terminé** |
| 0.1 | Sauvegarde Git du travail de remise en état | **Terminé** |
| 0.2 | Arborescence `03_Network`, plan, chaîne de génération du rapport | **Terminé** |
| 1.1 | Inventaire source de vérité et contrôle de cohérence | **Terminé** |
| 1.2 | Générateurs de configurations et de tableaux | **Terminé** |
| 1.3 | Pilotage du laboratoire (API GNS3, consoles) et correctifs de plateforme | **Terminé** |
| 2.1 | Évolutions de topologie (SW-OUT, NAT, ADMIN-WS, VLAN, disposition) | **Terminé** |
| 2.2 | Images Docker des services (ISP, syslog, GTB, CCTV, DCIM, web) | **Terminé** |
| 2.3 | Budget de ressources et démarrage par étapes | **Terminé** |
| 3.1 – 3.3 | WAN et bordure : FRR opérateurs, Edge (BGP, OSPF, HSRP), vérification | **Terminé** |
| 4.1 – 4.4 | Pare-feux pfSense HA : installation, configuration générée, CARP, pfsync, NAT | **Terminé** (validation de bout en bout en phase 6) |
| 5.1 – 5.3 | Cœur, Leaf, durcissement : HSRP, RPVST+, LACP, OSPF, ACL, VRF MGMT | **Terminé** |
| 6.1 | Serveurs : SRV-INF-01 (DNS, NTP), conteneurs de services | **Terminé** |
| 6.2 – 6.4 | Autres serveurs (bastion, stockage, sauvegarde, calcul), matrice de flux | En cours |
| P0 (plan 02) | Base Git propre, profil de travail mesuré, rapport « Test the Lab » | **Terminé** (SRV-MON-01 démarré seulement pour la supervision) |
| ADM.1 | Poste d'administration `dc/admin-ws:1.0` : portail, alias SSH, sessions journalisées | **Terminé** |
| ADM.2 – ADM.3 | Matrice d'accès, règles d'accès privilégié | À faire |
| FW.1 – FW.5 | Pare-feux : audit, règles de supervision, bascule côté LAN, matrice de flux | À faire |
| LOG.1 – LOG.6 | Collecte des journaux : sources, horloges, rétention, consultation | À faire |
| 7.1 – 7.3 | Supervision (ZBX.1 – ZBX.7, GRF.1 – GRF.5 du plan 02) | À faire |
| ISO.1 – ISO.2 | Matrice d'accès et de conformité ISO/IEC 27001, sauvegarde des configurations | À faire |
| 8.1 – 8.2 | Tests de résilience | À faire |
| 9.1 – 9.4 | Documentation finale | À faire |
