# Sécurité : pare-feux en haute disponibilité

## Architecture des pare-feux

Les deux pare-feux pfSense CE 2.7.2 forment une grappe actif/passif. Chacun dispose de six interfaces logiques ;
les adresses virtuelles **CARP** portent les passerelles et migrent vers FW-B en cas de défaillance de FW-A, la
table d'états est répliquée en continu par **pfsync** (lien dédié em2) et la configuration de FW-A est poussée vers
FW-B par **XMLRPC**.

Table: Interfaces des pare-feux
| Interface | Port | FW-A | FW-B | VIP CARP (vhid) | Rôle |
|---|---|---|---|---|---|
| WAN | em0 | 10.254.1.4/28 | 10.254.1.5/28 | 10.254.1.1 (1) | Transit externe VLAN 901 (SW-OUT) |
| LAN | lagg0 = em3 + em4 (failover) | 10.254.2.4/28 | 10.254.2.5/28 | 10.254.2.1 (2) | Transit interne VLAN 902 vers CORE-A (em3) et CORE-B (em4) |
| SYNC | em2 | 10.254.3.1/30 | 10.254.3.2/30 | — | pfsync et XMLRPC (lien direct) |
| DMZ | em5 | 10.50.0.2/24 | 10.50.0.3/24 | 10.50.0.1 (50) | VLAN 50, SRV-WEB-01 |
| MGMT | em6.10 (802.1Q) | 10.10.0.11/24 | 10.10.0.12/24 | 10.10.0.254 (10) | Management hors bande des équipements |
| ADMIN | em6.90 (802.1Q) | 10.90.0.2/24 | 10.90.0.3/24 | 10.90.0.1 (90) | Administration (bastion, poste ADMIN-WS) |

FW-A annonce ses VIP avec un *advskew* de 0, FW-B de 100 : FW-A est maître en fonctionnement nominal. Les adresses
publiques 192.0.2.10 (traduction des sorties) et 192.0.2.80 (publication web) sont déclarées comme VIP de type
*Other* : le préfixe 192.0.2.0/24 est routé par les Edge vers le VIP CARP 10.254.1.1, seul le maître les reçoit.

Table: Routage des pare-feux
| Destination | Passerelle | Justification |
|---|---|---|
| 0.0.0.0/0 | WAN_EDGE_VIP 10.254.1.6 (HSRP des Edge) | Sortie Internet indépendante de l'Edge actif |
| 10.0.0.0/8 | CORE_VIP 10.254.2.6 (HSRP des cœurs) | Retour vers les VLAN internes routés par les cœurs |

## Installation et déploiement de la configuration

L'installation de pfSense a été pilotée au travers de la console VNC de chaque nœud (`automation/vnc.py`) : partition
**UFS** (plus économe que ZFS avec 1 Go de RAM), table MBR, disque entier. La notice de copyright du programme
d'installation a été acceptée pour procéder à l'installation.

![Installation pilotée par VNC : choix du partitionnement UFS sur FW-A](../screenshots/pfsense_install/fw-a_04_ufs.png){width=380}

La configuration n'est pas saisie dans l'interface web : elle est **générée**. Le fichier `config.xml` d'usine
de FW-A sert de base (sections propres à la version conservées), puis `automation/gen_pfsense.py` réécrit les
sections décrites par l'inventaire : identité, interfaces, VLAN, LAGG, VIP, passerelles, routes, alias, NAT,
règles, haute disponibilité, journalisation, SNMP et NTP.

Table: Chaîne de déploiement des pare-feux
| Étape | Action | Contrôle |
|---|---|---|
| 1. Amorçage | Menu console (option 2) : WAN statique 10.254.1.4/.5 /28, passerelle 10.254.1.6 | Ping de ISP-A au travers des Edge |
| 2. Récupération de la base | `nc` depuis le pare-feu vers ISP-A (198.51.100.1), route de retour temporaire sur ISP-A | Fichier de 11,5 Ko, version 23.3 |
| 3. Génération | `gen_pfsense.py` : 32 règles, 7 VIP, 29 alias, 2 redirections par pare-feu | Analyse XML, revue des sections |
| 4. Transfert | `nc` depuis ISP-A vers le pare-feu | Empreintes MD5 identiques à la source, `xmllint` valide |
| 5. Installation | Sauvegarde `config.factory.xml`, remplacement de `/conf/config.xml`, redémarrage | Interfaces conformes à l'inventaire au démarrage |
| 6. Nettoyage | Route temporaire et écouteurs supprimés sur ISP-A | Accès Internet du pare-feu via 192.0.2.10 |

> [!NOTE] Secrets
> Les fichiers déployés contiennent la clé privée du certificat de l'interface web et les empreintes de mots de
> passe : ils sont exclus de Git. Des copies expurgées (`*.config.redacted.xml`) sont versionnées pour la
> documentation.

## Politique de filtrage

La politique applique le tableau 18 du dossier : chaque interface n'autorise que les flux nécessaires, tout le reste
est refusé et **journalisé** (règle de refus explicite en fin de chaque interface). La publication web utilise des
redirections de port avec règle de passage associée ; l'interface web et SSH des pare-feux ne sont accessibles que
depuis le VLAN d'administration (la règle « anti-lockout » implicite est désactivée).

@include generated/fw_rules.md

Table: Traduction d'adresses
| Type | Correspondance | Usage |
|---|---|---|
| SNAT (sortant, mode hybride) | 10.0.0.0/8 → 192.0.2.10 | Accès Internet des réseaux internes |
| SNAT (sortant) | 10.254.1.0/28 → 192.0.2.10 | Trafic propre des pare-feux (DNS, NTP, mises à jour) : le transit privé n'est pas routable chez les opérateurs |
| DNAT (redirection) | 192.0.2.80:80/443 → 10.50.0.11:80/443 | Publication de SRV-WEB-01 |

## Vérification des pare-feux

![FW-A après déploiement : interfaces et adresses conformes à l'inventaire](../screenshots/10_fw-a_console_interfaces.png){width=440}

![FW-A maître CARP sur les cinq VIP, pfsync actif vers 10.254.3.2, Internet joignable via 192.0.2.10](../screenshots/12_fw-a_carp_master.png){width=440}

![FW-B secours (advskew 100) – le vhid 2 du LAN reste maître tant que le cœur n'est pas démarré](../screenshots/13_fw-b_carp_backup.png){width=440}

![Règles NAT actives et nombre de règles de filtrage chargées (156 dont 85 de passage et 53 de blocage)](../screenshots/14_fw-a_nat_rules.png){width=440}

Table: Synthèse de la vérification des pare-feux
| Contrôle | Résultat | Attendu |
|---|---|---|
| Interfaces et adresses (FW-A / FW-B) | Conformes (6 interfaces chacun) | Conformes à l'inventaire |
| Rôles CARP | FW-A MASTER sur vhid 1, 2, 10, 50, 90 ; FW-B BACKUP sur 1, 10, 50, 90 | FW-A maître |
| pfsync | Actif sur em2, pair 10.254.3.2 / 10.254.3.1 | Actif |
| NAT | SNAT 192.0.2.10 et DNAT 192.0.2.80 chargés | Conformes |
| Accès Internet du pare-feu | 8.8.8.8 joignable (2/2) après suppression de la route temporaire | Via SNAT |
| Règles étiquetées | Chaque règle porte sa référence (T18-x) dans son libellé pf | Traçabilité |

> [!WARN] Points en attente des phases suivantes
> - Sur le segment LAN (VLAN 902), FW-B est également maître du vhid 2 : les annonces CARP ne circulent pas encore
>   entre les deux pare-feux car CORE-A et CORE-B, qui portent ce segment, ne sont pas démarrés. La situation sera
>   vérifiée après la configuration du cœur (phase 5).
> - Les flux autorisés et refusés par la politique seront mesurés de bout en bout lorsque les serveurs seront en
>   service (matrice de flux, phase 6).
> - Le trafic propre de FW-B vers Internet n'aboutit que lorsqu'il est maître : la traduction vers 192.0.2.10, VIP
>   détenu par le maître, est le comportement attendu d'une grappe actif/passif.
