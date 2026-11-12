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
> - Résolu en phase 5 : tant que le cœur n'était pas démarré, FW-B était également maître du vhid 2 (LAN), les
>   annonces CARP ne circulant pas sur le segment 902 ; une fois CORE-A et CORE-B configurés, FW-B est passé
>   BACKUP sur les cinq VIP.
> - Les flux autorisés et refusés par la politique seront mesurés de bout en bout lorsque les serveurs seront en
>   service (matrice de flux, phase 6).
> - Le trafic propre de FW-B vers Internet n'aboutit que lorsqu'il est maître : la traduction vers 192.0.2.10, VIP
>   détenu par le maître, est le comportement attendu d'une grappe actif/passif.

## Journalisation et synchronisation de la configuration

Une fois le cœur en service, le collecteur syslog central (10.60.0.12) reçoit les journaux de tous les équipements :
routeurs Edge, cœurs et Leaf (au travers de leur VRF de management, du pare-feu et du VLAN 60), pare-feux
(`filterlog`), serveurs et simulateurs. Cette première exploitation a révélé un bruit important : la règle de refus
journalisée du pare-feu enregistrait chaque annonce HSRP (224.0.0.102, UDP 1985) et OSPF (224.0.0.5/6) émise par les
Edge et les cœurs, soit plusieurs mégaoctets de journaux par heure. Des règles de rejet **non journalisées** ont été
ajoutées pour ce trafic de contrôle multicast, avant la règle de refus par défaut, afin que les journaux ne
contiennent que des refus significatifs.

Ces règles ont été déployées sur FW-A seul puis répliquées vers FW-B par la synchronisation **XMLRPC**
(`rc.filter_synchronize`) : contrôle de version des deux pairs (23.3), transfert de la configuration vers
`https://10.254.3.2/xmlrpc.php`, puis rechargement automatique des règles sur FW-B.

![Synchronisation XMLRPC : FW-A pousse sa configuration (haut), FW-B applique les 6 nouvelles règles (bas)](../screenshots/18_fw_xmlrpc_sync.png){width=420}

Table: Sources reçues par le collecteur syslog central
| Source | Adresse | Chemin |
|---|---|---|
| EDGE-A, EDGE-B | 10.10.0.1, 10.10.0.2 | VRF MGMT → pare-feu (MGMT) → LAN → cœur → VLAN 60 |
| CORE-A, CORE-B | 10.10.0.21, 10.10.0.22 | VRF MGMT → pare-feu → VLAN 60 |
| LEAF-A1, A2, B1, B2 | 10.10.0.31 à 10.10.0.34 | SVI VLAN 10 → pare-feu → VLAN 60 |
| FW-A, FW-B | 10.10.0.11, 10.10.0.12 | Interface MGMT |
| SRV-INF-01, SRV-DCIM-01, CCTV-SIM | VLAN 100, 70, 80 | Routage inter-VLAN par le cœur (ACL : syslog autorisé) |

## Audit des pare-feux en service

Une configuration générée n'a de valeur que si les équipements exécutent bien celle-là. Le script
`automation/fw_audit.py` le vérifie sans rien modifier : depuis le poste d'administration, il ouvre une session SSH
sur chaque pare-feu, relit `/cf/conf/config.xml` et le compare, section par section, au fichier produit par
`gen_pfsense.py` (les horodatages sont ignorés, les descriptions sont comparées après décodage des entités HTML que
pfSense y introduit). Il contrôle ensuite ce que le moteur de filtrage a réellement chargé : chaque règle générée doit
se retrouver dans `pfctl -sr` par son libellé, et aucune règle chargée ne doit être étrangère à l'inventaire.

Table: Résultat de l'audit du 12 octobre 2026 (0 écart)
| Contrôle | FW-A | FW-B |
|---|---|---|
| Sections `interfaces`, `vlans`, `laggs`, `virtualip`, `gateways`, `staticroutes` | Identiques au fichier généré | Identiques |
| Sections `aliases`, `nat`, `filter` | Identiques (40 règles, 2 redirections) | Identiques, reçues par la synchronisation XMLRPC |
| Sections `hasync`, `syslog`, `snmpd` | Identiques | Identiques |
| Règles chargées dans pf | 32 libellés sur 32, 165 lignes | 32 sur 32, 165 lignes |
| Traduction d'adresses | SNAT 192.0.2.10 et redirections de 192.0.2.80 chargés | Idem |
| Rôles CARP | MASTER sur les cinq VIP | BACKUP sur les cinq VIP |
| Assistant de première configuration | Absent | Absent |

Les deux règles d'administration ajoutées après le premier déploiement (EXT-7, DNS/NTP ; journalisation des sessions
vers le collecteur) sont bien en service sur les deux pare-feux. Deux points sont relevés pour le prochain
déploiement : le délai de session de l'interface web est celui par défaut de pfSense (4 heures), et le fichier
`/cf/conf/trigger_initial_wizard`, laissé par l'installation, doit être supprimé à l'étape 5 de la chaîne de
déploiement (sinon l'interface web ouvre l'assistant de première configuration au lieu du tableau de bord ; il a été
supprimé à la main le 12 octobre 2026 sur les deux pare-feux).

> [!NOTE] Nouvelle voie d'accès pour l'automatisation
> Jusqu'ici, les pare-feux n'étaient pilotés que par leur console VNC. Le module `automation/adminws.py` exécute
> désormais des commandes par SSH **depuis ADMIN-WS**, c'est-à-dire par le chemin d'un administrateur : règles de la
> zone ADMIN, compte `admin`, session inscrite au journal central. L'audit et les déploiements suivants l'utilisent.

Table: Vérification – FW.1, audit des pare-feux (12 octobre 2026)
| Contrôle | Commande | Depuis | Attendu | Résultat |
|---|---|---|---|---|
| Audit complet | `python automation/fw_audit.py` | Hôte, dossier `03_Network` | `0 difference(s)`, code de retour 0 | Conforme |
| L'audit sait voir un écart | Comparaison des fichiers générés de FW-A et de FW-B par la même fonction | Hôte | Sections `interfaces`, `virtualip`, `hasync` différentes | Conforme |
| Règle ajoutée présente | `python automation/adminws.py fw-a "pfctl -sr"` puis recherche de `EXT-7` | Hôte | Au moins une ligne | Conforme : 2 lignes sur FW-A et sur FW-B |
| Même nombre de règles | `pfctl -sr` compté sur les deux pare-feux | FW-A et FW-B | Nombres égaux | Conforme : 165 et 165 |
| Tableau de bord sans assistant | Ouvrir `https://10.90.0.1` | Navigateur de l'hôte par le proxy, ou ADMIN-WS | Page « Status: Dashboard » | Conforme |

## Déploiement sans redémarrage et règles de supervision

Le premier déploiement remplaçait `config.xml` puis redémarrait le pare-feu, par la console. Le script
`automation/deploy_pfsense.py` reprend la même idée – on déploie **le fichier généré**, jamais une retouche à la main –
mais par SSH depuis le poste d'administration et sans coupure :

Table: Chaîne de déploiement des pare-feux (depuis le 12 octobre 2026)
| Étape | Action | Garde-fou |
|---|---|---|
| 1. Ordre | Le pare-feu de secours (FW-B) d'abord, le maître (FW-A) ensuite | Un fichier défectueux n'atteint jamais le maître |
| 2. Transfert | Copie du fichier généré dans `/tmp/config.new` | Empreinte MD5 comparée au fichier local, `xmllint`, nom d'hôte attendu ; arrêt avant toute installation en cas d'écart |
| 3. Sauvegarde | `config.xml` en service copié en `config.xml.before-deploy` | Retour arrière : `deploy_pfsense.py --rollback FW-x` |
| 4. Installation | Remplacement de `/cf/conf/config.xml`, purge du cache de configuration, suppression de `trigger_initial_wizard` | – |
| 5. Application | `/etc/rc.filter_configure` (rechargement du filtrage, sans redémarrage) | Nombre de règles chargées et rôles CARP affichés |
| 6. Contrôle | `python automation/fw_audit.py` | `0 difference(s)` |

Ce déploiement apporte deux changements, tous deux issus de l'inventaire :

- la règle **EXT-8** (zone ADMIN vers le serveur de supervision, TCP 10051), nécessaire à l'agent Zabbix actif du
  bastion ; elle figure dans le tableau des règles ci-dessus ;
- le **délai de session de l'interface web** des pare-feux, ramené de 4 heures (valeur par défaut) à 15 minutes
  (`firewall_settings.gui_session_timeout_min`), écart relevé lors du contrôle des accès privilégiés.

Avant le déploiement, l'audit signalait précisément ces écarts (10 différences : section `filter`, section `aliases`,
règle EXT-8 absente de pf, délai de session, sur chacun des deux pare-feux) ; après, il n'en signale plus aucune.

Table: Vérification – FW.2, déploiement et règle de supervision (12 octobre 2026)
| Contrôle | Commande | Depuis | Attendu | Résultat |
|---|---|---|---|---|
| Audit avant déploiement | `python automation/fw_audit.py` | Hôte | Les changements en attente sont signalés | Conforme : 10 différences, toutes attendues |
| Déploiement | `python automation/deploy_pfsense.py` | Hôte | « checksum identical, XML valid », « installed » sur FW-B puis FW-A | Conforme |
| Audit après déploiement | `python automation/fw_audit.py` | Hôte | `0 difference(s)`, 33 règles sur 33, délai de session 15 min | Conforme : 166 lignes pf sur chaque pare-feu |
| La règle laisse passer | Tentative vers `10.60.0.11:10051`, puis compteur de la règle (`pfctl -vvsr`) | SRV-BASTION, puis FW-A | Compteur de paquets d'EXT-8 en hausse | Conforme : 2 → 7 paquets |
| Le port voisin reste fermé | Tentative vers `10.60.0.11:3306`, puis `/var/log/filter.log` | SRV-BASTION, puis FW-A | Ligne `block` sur `em6.90` | Conforme, également reçue par le collecteur |
| Même comportement sur FW-B | FW-A rétrogradé (`sysctl net.inet.carp.demotion=240`), mêmes tentatives | SRV-BASTION, puis FW-B | FW-B MASTER sur les cinq VIP ; compteur d'EXT-8 en hausse sur FW-B ; blocage journalisé par FW-B | Conforme : 2 → 5 paquets sur FW-B, 7 → 7 sur FW-A |
| Retour à la normale | `sysctl net.inet.carp.demotion=-240` | FW-A | FW-A MASTER, FW-B BACKUP, démotion 0 | Conforme |
| Accès au travers des pare-feux | Interface web et tableau de bord BMS | Navigateur de l'hôte par le proxy | Réponses HTTP 200 | Conforme |

Le serveur de supervision étant arrêté pendant ces travaux (capacité de l'hôte), la preuve finale – le port 10051
réellement ouvert de bout en bout – sera apportée avec la mise en service des agents Zabbix (ZBX.5).


## Bilan de la phase pare-feux et vues de l'interface d'administration

Table: Résultats des sous-tâches FW.1 à FW.4 et du scénario T2
| Sous-tâche | Méthode | Résultat mesuré |
|---|---|---|
| FW.1 Audit | `fw_audit.py` compare la configuration en service à l'inventaire | 0 différence sur FW-A et FW-B |
| FW.2 Déploiement | `gen_pfsense.py` puis `deploy_pfsense.py` (FW-B d'abord, sans redémarrage, retour arrière possible) | Règle EXT-8 et délai de session web de 15 min en service |
| FW.3 Côté LAN | Arrêt de CORE-A puis de CORE-B, sonde ADMIN-WS → BMS-SIM | Coupure 4,5 s (au lieu de ≥ 150 s avant la correction) ; retour du cœur 0 à 1,5 s |
| Décision FW.3 | Commutateur SW-IN dédié au VLAN 902 (em3/em4 des pare-feux, Gi0/0 des cœurs), VLAN 902 retiré du lien inter-cœurs, BPDU filter sur les ports de transit | Un cœur bloqué avec son lien actif (panne « grise ») est désormais contourné |
| FW.4 Matrice de flux | `flow_matrix.py --running-only` : 26 sondes, exécutées selon les nœuds démarrés | 11 sondes exécutées, 0 écart ; 6/6 flux refusés retrouvés dans le journal central |
| T2 Bascule pare-feu | Arrêt de FW-A, FW-B devient maître CARP | Coupure 3,0 s ; 1,5 s au retour de FW-A |
| Incident FW.4 | Secrets SNMP passés en ligne de commande SSH, donc journalisés | Secrets transmis par l'entrée standard, puis renouvelés (rotation SNMPv3) |

Les captures suivantes sont prises depuis le poste d'administration ADMIN-WS (VLAN 90), dans le navigateur, par le seul
chemin autorisé : règle [T18-6] de l'interface ADMIN vers l'interface web du pare-feu
(`python automation/vnc.py ADMIN-WS shot <fichier>`).

![FW-A, Status > CARP : maître sur les cinq VIP (WAN, LAN, DMZ, MGMT, ADMIN) ; pfsync voit les deux identifiants d'hôte](../screenshots/21_fw-a_carp_master_gui.png){width=440}

![FW-B, Status > CARP : secours (BACKUP) sur les cinq VIP, mêmes identifiants pfsync : la table d'états est partagée](../screenshots/25_fw-b_carp_backup_gui.png){width=440}

![Firewall > Rules > ADMIN : flux autorisés depuis le VLAN d'administration (webGUI/SSH, DNS/NTP, syslog, SSH/HTTPS, SNMP, Zabbix), chaque règle référencée](../screenshots/22_fw-a_rules_admin.png){width=440}

![Firewall > NAT > Port Forward : publication de SRV-WEB-01 (10.50.0.11) sur l'adresse publique 192.0.2.80, ports 80 et 443](../screenshots/23_fw-a_nat_port_forward.png){width=440}

![Status > System Logs > Firewall : refus par défaut journalisés sur le WAN (règle T18), source et destination visibles pour l'audit](../screenshots/24_fw-a_firewall_logs.png){width=440}
