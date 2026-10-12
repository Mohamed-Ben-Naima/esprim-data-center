# Administration et accès privilégiés

## Principe : un point d'entrée unique

Aucun équipement du centre de données ne s'administre depuis les réseaux de production. Les ports de management
vivent dans le VLAN 10 (hors bande), et seule la **zone d'administration** (VLAN 90) est autorisée par les pare-feux à
les joindre en SSH et en HTTPS. Deux équipements composent cette zone :

Table: Points d'entrée de la zone d'administration
| Équipement | Adresse | Rôle | État dans le laboratoire |
|---|---|---|---|
| ADMIN-WS | 10.90.0.12 | Poste d'administration : navigateur pour les interfaces web, client SSH pour la ligne de commande | En service en permanence |
| SRV-BASTION | 10.90.0.11 | Rebond SSH avec second facteur (TOTP) et audit (`auditd`) | Démarré pour ses propres essais (capacité de l'hôte) |

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

