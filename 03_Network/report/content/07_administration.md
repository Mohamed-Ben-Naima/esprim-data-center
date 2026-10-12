# Administration et accès privilégiés

## Principe : un point d'entrée unique

Aucun équipement du centre de données ne s'administre depuis les réseaux de production. Les ports de management
vivent dans le VLAN 10 (hors bande), et seule la **zone d'administration** (VLAN 90) est autorisée par les pare-feux à
les joindre en SSH et en HTTPS. Deux équipements composent cette zone :

Table: Points d'entrée de la zone d'administration
| Équipement | Adresse | Rôle | État dans le laboratoire |
|---|---|---|---|
| ADMIN-WS | 10.90.0.12 | Poste d'administration : navigateur pour les interfaces web, client SSH pour la ligne de commande | En service en permanence |
| SRV-BASTION | 10.90.0.11 | Rebond SSH : mot de passe **et** code TOTP, audit (`auditd`) | Démarré pour ses propres essais (capacité de l'hôte) |

Cette organisation répond aux mesures de l'ISO/IEC 27001:2022 sur le contrôle d'accès (A.5.15), les droits d'accès
privilégiés (A.8.2), la restriction d'accès à l'information (A.8.3) et la séparation des réseaux (A.8.22).

## Poste d'administration ADMIN-WS

Le poste est un conteneur « webterm » (bureau graphique accessible par la console VNC de GNS3). Son image
`dc/admin-ws:1.0` est construite à partir de `gns3/webterm` par `automation/build_images.py` ; tout ce qui dépend du
réseau est **généré depuis l'inventaire**, de sorte qu'un équipement ajouté à l'inventaire (par exemple le futur
serveur de stockage TrueNAS) apparaît dans le poste à la génération suivante.

Table: Contenu de l'image dc/admin-ws:1.0
| Élément | Rôle | Origine |
|---|---|---|
| Firefox ESR, OpenSSH 9.2, `curl`, `telnet` | Navigateur et clients d'administration | Image de base `gns3/webterm` (Debian 12) |
| `snmp`, `dnsutils`, `netcat` | Diagnostic (interrogation SNMP, résolution de noms, test de ports) | Ajoutés par le Dockerfile |
| `/etc/ssh/ssh_config.d/dc-casa.conf` | Un alias SSH par équipement : `ssh core-a`, `ssh fw-a`, `ssh srv-inf-01`… | Généré (`configs/docker/ADMIN-WS.ssh_config`) |
| `/usr/share/dc-portal/index.html` | Portail : toutes les interfaces web et toutes les commandes SSH | Généré (`configs/docker/ADMIN-WS.portal.html`) |
| `policies.json` de Firefox | Le portail est la page d'accueil, verrouillée ; pas de mémorisation des mots de passe | `docker/admin-ws/` |
| `/usr/local/bin/ssh` | Enveloppe du client SSH : annonce le début et la fin de chaque session au collecteur de journaux | `docker/admin-ws/dc-ssh` |
| `dc-hosts` | Rappel des alias à l'ouverture d'un terminal | `docker/admin-ws/` |

![Portail d'administration : page d'accueil du navigateur d'ADMIN-WS, générée depuis l'inventaire](../screenshots/20_admin-ws_portal.png){width=600}

Chaque session SSH ouverte depuis le poste laisse deux lignes sur le collecteur central, une au début et une à la fin,
avec la cible et le code de retour (A.8.15) :

```text title="Collecteur SYSLOG – sessions SSH ouvertes depuis ADMIN-WS (12 octobre 2026)"
17:54:26 10.90.0.12 ADMIN-WS admin-ssh session start user=root target=[edge-a show version | include uptime]
17:54:30 10.90.0.12 ADMIN-WS admin-ssh session end   user=root target=[edge-a show version | include uptime] rc=0
17:59:50 10.90.0.12 ADMIN-WS admin-ssh session start user=root target=[fw-a hostname; pfctl -sr | wc -l]
17:59:51 10.90.0.12 ADMIN-WS admin-ssh session end   user=root target=[fw-a hostname; pfctl -sr | wc -l] rc=0
```

> [!DEV] Écarts assumés du poste d'administration
> - Les images Cisco IOSv et IOSvL2 du laboratoire ne proposent qu'une pile SSH ancienne : les algorithmes
>   `diffie-hellman-group14-sha1` et `ssh-rsa` sont réactivés **pour ces huit hôtes seulement** ; les pare-feux et les
>   serveurs utilisent les algorithmes par défaut d'OpenSSH 9.2.
> - Le bureau du conteneur s'exécute sous un compte unique : l'identité de l'administrateur est celle du compte utilisé
>   sur l'équipement cible (`netadmin`, `admin`, `ubuntu`). L'authentification nominative à deux facteurs est portée
>   par SRV-BASTION.
> - Le volume `/root` du poste (profil du navigateur, clés d'hôtes connues) est recréé avec le nœud.

## Vérification

Table: Vérification – ADM.1, poste d'administration (12 octobre 2026)
| Contrôle | Commande | Depuis | Attendu | Résultat |
|---|---|---|---|---|
| Outils présents | `command -v ssh firefox-esr curl snmpget dig nc` | ADMIN-WS, console auxiliaire (5053) | Six chemins | Conforme |
| Alias vers un cœur | `ssh core-a "show version"` | Terminal d'ADMIN-WS (VNC 5904) | Bannière légale puis `CORE-A uptime is …` | Conforme (également EDGE-A et LEAF-B1) |
| Alias vers un pare-feu | `ssh fw-a hostname` | Terminal d'ADMIN-WS | `fw-a.dc.casa.lab` | Conforme (165 règles lues par `pfctl -sr`) |
| Portail | Ouvrir Firefox | ADMIN-WS (VNC 5904) | Page « DC-CASA - administration portal » | Conforme |
| Session journalisée | `grep admin-ssh /var/log/remote/all.log` | SYSLOG, console auxiliaire (5041) | Lignes `session start` et `session end` | Conforme (16 lignes après 8 sessions) |
| Heure locale | `date` | ADMIN-WS puis SYSLOG | Même heure sur les deux | **Limite connue du laboratoire** : fuseau `Africa/Casablanca` des deux côtés, mais ADMIN-WS affiche +00 et SYSLOG +01 (bases de fuseaux horaires différentes dans les deux images). Les journaux sont horodatés par le collecteur : l'ordre des événements n'est pas affecté |
| Topologie inchangée | `python automation/verify_topology.py` | Hôte | `RESULT: OK`, 60 liens | Conforme |

## Matrice d'accès : tout depuis la zone d'administration, rien depuis ailleurs

Le script `automation/access_matrix.py` lit dans l'inventaire la liste des équipements administrables (alias SSH du
poste d'administration et interfaces web) et sonde chacun d'eux depuis **trois réseaux** : la zone d'administration
(ADMIN-WS, VLAN 90), un réseau interne (SRV-INF-01, VLAN 100) et la DMZ (SRV-WEB-01, VLAN 50). Un accès n'est conforme
que s'il répond depuis ADMIN-WS **et** reste muet depuis les deux autres réseaux ; seul le site web public, déclaré
`scope: all`, peut répondre aux réseaux internes. Avec l'option `--login`, une vraie session SSH est ouverte sur chaque
équipement en marche. Un équipement arrêté est signalé « arrêté », jamais en échec.

@include generated/access_matrix.md

Les refus ne sont pas silencieux : ils sont comptés et journalisés par l'équipement qui les prononce.

```text title="Traces des refus sur le collecteur central (12 octobre 2026)"
CORE-A  %SEC-6-IPACCESSLOGP: list ACL-VLAN100-IN denied tcp 10.100.0.11(57938) -> 10.70.0.12(8080), 1 packet
FW-A    filterlog: em5,match,block,in,4,...,tcp,60,10.50.0.11,10.10.0.34,37803,22
CORE-A# show access-lists ACL-VLAN100-IN | include deny
    180 deny ip any 10.10.0.0 0.0.0.255 log (22 matches)
    190 deny ip any 10.90.0.0 0.0.0.255 log (20 matches)
```

> [!WARN] Défaut révélé par la matrice : LEAF-B2 sans SSH
> Au premier passage, LEAF-B2 refusait la connexion sur le port 22 : le commutateur n'avait plus de clés RSA
> (`show ip ssh` : *SSH Disabled – Please create RSA keys*), il n'était donc administrable que par sa console.
> Les clés ont été régénérées (`crypto key generate rsa modulus 2048`) et la configuration sauvegardée ; la matrice
> est ensuite passée sans échec. Leur conservation après un redémarrage du commutateur reste à constater : la matrice
> sert de contrôle de non-régression à chaque démarrage du laboratoire.

Table: Vérification – ADM.2, matrice d'accès (12 octobre 2026)
| Contrôle | Commande | Depuis | Attendu | Résultat |
|---|---|---|---|---|
| Matrice complète avec sessions SSH | `python automation/access_matrix.py --login` | Hôte, dossier `03_Network` | Chaque équipement en marche joignable depuis ADMIN-WS, refusé ailleurs ; code de retour 0 | Conforme : 15 accès testés, 0 échec, 11 équipements arrêtés |
| Sessions SSH réelles | Colonne « Session SSH » de la matrice | ADMIN-WS | Une réponse de chaque équipement | Conforme : EDGE-A/B, CORE-A/B, LEAF-B1/B2, FW-A/B, SRV-INF-01 |
| Refus comptés par le cœur | `show access-lists ACL-VLAN100-IN` | CORE-A (console 5010) | Compteurs des lignes `deny … log` en hausse | Conforme : 22 et 20 correspondances |
| Refus journalisés | `grep filterlog /var/log/remote/all.log` | SYSLOG, console auxiliaire (5041) | Lignes `block` pour la source 10.50.0.11 | Conforme : 36 lignes vers le réseau de management |
| La sonde fonctionne sur chaque source | Port local de contrôle intégré au script | SRV-INF-01, SRV-WEB-01 | `control ok` | Conforme |

## Règles d'accès privilégié

Deux chemins mènent à un équipement, tous deux depuis le VLAN 90 : la session directe depuis ADMIN-WS
(`ssh core-a`) et le rebond par SRV-BASTION (`ssh -J bastion core-a`), qui ajoute la bannière, l'audit `auditd` et
les journaux `sshd` du bastion. Une session ouverte par rebond laisse trois traces indépendantes sur le collecteur :

```text title="Une session par rebond, vue par les trois équipements (12 octobre 2026, 21 h 26)"
ADMIN-WS     admin-ssh session start user=root target=[-J bastion core-a show users]
SRV-BASTION  sshd: Disconnected from user ubuntu 10.90.0.12 port 49424
CORE-A       %SEC_LOGIN-5-LOGIN_SUCCESS: Login Success [user: netadmin] [Source: 10.90.0.11] [localport: 22]
```

Table: Protection des sessions d'administration
| Mesure | Réglage | Équipements | Constat |
|---|---|---|---|
| Accès distant restreint | SSH v2 seul, lignes VTY filtrées par `ACL-MGMT-ACCESS` (VLAN 90 et 60) | Cisco | Conforme (matrice d'accès) |
| Verrouillage après échecs | `login block-for 120 attempts 5 within 60` | Cisco | Conforme : au cinquième échec le commutateur refuse toute connexion SSH, y compris avec le bon mot de passe, et le signale (`%SEC_LOGIN-1-QUIET_MODE_ON`) |
| Délai d'inactivité | `exec-timeout` 10 minutes (valeur par défaut d'IOS, `show line vty 0`) | Cisco | Conforme sur EDGE-A : session fermée par l'équipement après 634 secondes réelles (10 minutes à son horloge). Sur LEAF-B1, la session était encore ouverte à 840 secondes : horloge ralentie (limite décrite ci-dessous) |
| Journalisation des connexions | `login on-failure log`, `login on-success log` | Cisco | Conforme : 30 réussites et les échecs du test sur le collecteur |
| Session web des pare-feux | Délai de session par défaut de pfSense (4 heures) | FW-A, FW-B | **Écart** : à ramener à 15 minutes lors du prochain déploiement des pare-feux (FW.2) |
| Bastion | Bannière, `AllowGroups sudo`, `auditd`, journaux `sshd` centralisés, second facteur TOTP | SRV-BASTION | Conforme depuis ADM.4 : mot de passe puis code de vérification exigés |

> [!WARN] Limite du laboratoire : les horloges des commutateurs virtuels retardent
> Les images IOSvL2 ne reçoivent pas assez de temps processeur sur le poste hôte : leur horloge n'avance qu'à environ
> 55 à 60 % de la vitesse réelle (CORE-A affichait 19 h 47 à 21 h 28 après 3 h 30 de fonctionnement), et aucun
> équipement Cisco n'est synchronisé par NTP. Conséquence mesurée : la période de silence de 120 secondes après
> verrouillage a duré environ quatre minutes réelles. Toutes les temporisations de ces équipements (HSRP,
> verrouillage, inactivité) sont allongées d'autant ; les temps de convergence mesurés en phase 8 devront être lus
> avec cette réserve. La synchronisation NTP est traitée avec la collecte des journaux (LOG.1).

Table: Comptes et secrets d'administration – état au 12 octobre 2026
| Compte | Portée | État | Suite |
|---|---|---|---|
| `netadmin` et secret `enable` | Les huit équipements Cisco | Compte partagé, mot de passe propre au laboratoire | Écart assumé : pas de comptes nominatifs dans le laboratoire |
| `admin` (pfSense) | Interface web et SSH des deux pare-feux | Même mot de passe que `netadmin` | Écart : secret à distinguer |
| `ubuntu` / mot de passe par défaut | Console série des serveurs Ubuntu uniquement (pilotage du laboratoire) | Refusé en SSH depuis ADM.4 (`DenyUsers ubuntu`) | Écart résiduel : le compte subsiste sur la console de GNS3 |
| `sysadmin` | SSH de tous les serveurs Ubuntu déployés | Mot de passe de l'inventaire ; sur SRV-BASTION, second facteur TOTP | Conforme |
| `Admin` / `zabbix` | Interface web de Zabbix | Mot de passe par défaut du produit | Remplacé en ZBX.1 |
| `admin` (Grafana) | Interface web de Grafana | Mot de passe de l'inventaire | Conforme |
| Communauté SNMP v2c | Pare-feux, lecture seule, limitée au VLAN 60 | Secret en clair sur le réseau | Écart assumé (pfSense sans SNMPv3 natif) |

Table: Vérification – ADM.3, règles d'accès privilégié (12 octobre 2026)
| Contrôle | Commande | Depuis | Attendu | Résultat |
|---|---|---|---|---|
| Rebond par le bastion | `ssh -J bastion core-a "show users"` | Terminal d'ADMIN-WS | Bannière du bastion puis réponse de CORE-A | Conforme ; source `10.90.0.11` dans le journal de CORE-A |
| Bastion dans la matrice | `python automation/access_matrix.py --login` | Hôte | SRV-BASTION joignable depuis ADMIN-WS, refusé ailleurs | Conforme : 16 accès testés, 0 échec |
| Verrouillage | Six tentatives `ssh leaf-b2` avec un mauvais mot de passe, puis une avec le bon | Terminal d'ADMIN-WS | Refus de connexion pendant la période de silence | Conforme : `Connection refused` dès le cinquième échec, connexion de nouveau acceptée ensuite |
| Trace du verrouillage | `grep SEC_LOGIN /var/log/remote/all.log` | SYSLOG, console auxiliaire (5041) | Lignes `LOGIN_FAILED` puis `QUIET_MODE_ON` | Conforme, source `10.90.0.12` |
| Délai d'inactivité configuré | `show line vty 0` | LEAF-B1 (console 5018) | `Idle EXEC 00:10:00` | Conforme |
| Délai d'inactivité constaté | Session SSH laissée sans saisie | ADMIN-WS vers EDGE-A | Fermeture par l'équipement | Conforme sur EDGE-A : session fermée par l'équipement après 634 secondes réelles (10 minutes à son horloge). Sur LEAF-B1, la session était encore ouverte à 840 secondes : horloge ralentie (limite décrite ci-dessous) |

## Comptes des serveurs et second facteur du bastion

Le contrôle des comptes (ADM.3) avait relevé deux non-conformités : les serveurs, bastion compris, acceptaient en SSH
le compte par défaut de l'image, et le second facteur du bastion était installé sans être exigé. La sous-tâche ADM.4
les corrige dans `automation/deploy_servers.py` (étape « comptes », rejouable seule avec `--accounts-only`) :

Table: Politique de comptes des serveurs Ubuntu
| Mesure | Réalisation | Portée |
|---|---|---|
| Compte d'administration nommé | `sysadmin`, membre de `sudo`, mot de passe pris dans l'inventaire | Tous les serveurs déployés |
| Compte par défaut fermé à distance | `DenyUsers ubuntu` dans `/etc/ssh/sshd_config.d/10-dc-casa.conf` ; la console série reste utilisable par l'automatisation | Tous les serveurs déployés |
| Second facteur | `pam_google_authenticator` requis après le mot de passe, `AuthenticationMethods keyboard-interactive`, code à usage unique (TOTP, RFC 6238, 30 s), réutilisation interdite, 3 essais par 30 s | SRV-BASTION |
| Secret du second facteur | Dans l'inventaire (`bastion_totp_secret`) ; code courant donné par `python automation/totp.py` | Laboratoire |

Les alias SSH du poste d'administration utilisent désormais `sysadmin` ; le rebond `ssh -J bastion core-a` demande donc
trois réponses : mot de passe du bastion, code de vérification, mot de passe de l'équipement.

```text title="Questions posées par SSH lors d'un rebond par le bastion (12 octobre 2026)"
(sysadmin@10.90.0.11) Password:
(sysadmin@10.90.0.11) Verification code:
(netadmin@10.10.0.21) Password:
CORE-A uptime is 3 hours, 40 minutes
```

Table: Vérification – ADM.4, comptes des serveurs et second facteur (12 octobre 2026)
| Contrôle | Commande | Depuis | Attendu | Résultat |
|---|---|---|---|---|
| Compte par défaut refusé sur le bastion | `ssh ubuntu@10.90.0.11` | Terminal d'ADMIN-WS | `Permission denied` | Conforme |
| Compte par défaut refusé sur un serveur | `ssh ubuntu@10.100.0.11` | Terminal d'ADMIN-WS | `Permission denied` | Conforme |
| Compte d'administration accepté | `ssh srv-inf-01 hostname` | Terminal d'ADMIN-WS | `srv-inf-01` après le mot de passe | Conforme |
| Mauvais code refusé | `ssh bastion`, bon mot de passe, code `000000` | Terminal d'ADMIN-WS | Deux questions puis `Permission denied` | Conforme |
| Bon code accepté | `ssh bastion`, code de `python automation/totp.py` | Terminal d'ADMIN-WS | `srv-bastion` | Conforme ; `Accepted google_authenticator for sysadmin` sur le collecteur |
| Rebond avec second facteur | `ssh -J bastion core-a "show version"` | Terminal d'ADMIN-WS | Trois questions puis réponse de CORE-A | Conforme |
| Matrice d'accès | `python automation/access_matrix.py --login` | Hôte | 0 échec | Conforme : 16 accès testés |

