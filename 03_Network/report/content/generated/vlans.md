Table: Plan de VLAN et de sous-réseaux (source : inventaire)
| VLAN | Nom | Sous-réseau | Passerelle | Actif | Zone | Usage |
|---|---|---|---|---|---|---|
| 10 | **MGMT** | `10.10.0.0/24` | `10.10.0.254` CARP (FW-A 11 / FW-B 12) | FW-A (MASTER) | Management | Management hors bande (OOB) des équipements |
| 20 | **SERVEURS** | `10.20.0.0/24` | `10.20.0.1` HSRP (CORE-A .2 / CORE-B .3) | CORE-A | Interne | Serveurs de calcul / applicatifs |
| 30 | **STOCKAGE** | `10.30.0.0/24` | `10.30.0.1` HSRP (CORE-A .2 / CORE-B .3) | CORE-B | Interne | Stockage (NFS, iSCSI) |
| 40 | **BACKUP** | `10.40.0.0/24` | `10.40.0.1` HSRP (CORE-A .2 / CORE-B .3) | CORE-A | Interne | Sauvegarde |
| 50 | **DMZ** | `10.50.0.0/24` | `10.50.0.1` CARP (FW-A 2 / FW-B 3) | FW-A (MASTER) | Dmz | Services exposés à Internet |
| 60 | **MONITORING** | `10.60.0.0/24` | `10.60.0.1` HSRP (CORE-A .2 / CORE-B .3) | CORE-A | Interne | Supervision et journalisation |
| 70 | **BMS-DCIM** | `10.70.0.0/24` | `10.70.0.1` HSRP (CORE-A .2 / CORE-B .3) | CORE-B | Interne | GTB / DCIM |
| 80 | **SECURITE-CCTV** | `10.80.0.0/24` | `10.80.0.1` HSRP (CORE-A .2 / CORE-B .3) | CORE-B | Interne | Vidéosurveillance, contrôle d'accès |
| 90 | **ADMIN** | `10.90.0.0/24` | `10.90.0.1` CARP (FW-A 2 / FW-B 3) | FW-A (MASTER) | Administration | Poste d'administration, bastion |
| 100 | **SERVICES-INT** | `10.100.0.0/24` | `10.100.0.1` HSRP (CORE-A .2 / CORE-B .3) | CORE-A | Interne | DNS, NTP, DHCP, services internes |
| 901 | **TRANSIT-EXT** | `10.254.1.0/28` | — | — | Transit | Transit Edge – pare-feux (SW-OUT) |
| 902 | **TRANSIT-INT** | `10.254.2.0/28` | — | — | Transit | Transit pare-feux – cœur |
| 998 | **OSPF-CORE** | `10.254.4.0/30` | — | — | Transit | Adjacence OSPF entre cœurs |
| 999 | **PARKING** | — | — | — | None | Ports inutilisés (désactivés) |
