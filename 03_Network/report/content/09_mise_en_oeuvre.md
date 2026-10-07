# Mise en œuvre sous GNS3

## Plateforme de simulation

Table: Plateforme matérielle et logicielle
| Élément | Valeur |
|---|---|
| Hôte | PC Windows 11, 15,7 Go de RAM (le dossier de conception visait 32 Go) |
| Hyperviseur | VMware Workstation, VM « GNS3 VM » stockée sur `H:\GNS3 VM` |
| GNS3 | Version 2.2.56.1 (client, serveur local et serveur de la VM identiques) |
| Ressources allouées à la VM | 10 Go de RAM, 6 vCPU (au lieu de 3, voir « Incidents de plateforme »), virtualisation imbriquée (VT-x), KSM activé |
| Exécution des nœuds | Tous les nœuds QEMU et Docker s'exécutent dans la GNS3 VM (compute `vm`) |

## Remise en état de l'environnement

Avant toute configuration, l'environnement GNS3 était inutilisable : le contrôleur ne parvenait pas à joindre la
GNS3 VM et le projet ne pouvait démarrer aucun nœud. Le diagnostic a été mené de l'hôte vers la VM, couche par couche.

Table: Diagnostic et corrections de l'environnement
| Symptôme observé | Cause identifiée | Correction appliquée |
|---|---|---|
| `Cannot connect to host unknown:80` en boucle dans le journal du serveur GNS3 | L'outil VMware ne remontait aucune adresse joignable : la VM portait une adresse statique `10.10.10.2/24` (passerelle `10.10.10.1`) dans `/etc/netplan/90_gns3vm_static_netcfg.yaml`, hors du réseau host-only VMnet1 (`192.168.75.0/24`) | Remplacement du fichier netplan par un adressage aligné sur les réseaux de l'hôte |
| Aucune adresse obtenue après retour en DHCP | Le service DHCP de VMware est désactivé sur VMnet1 et VMnet8 côté hôte | Adressage statique : `eth0` = `192.168.75.128/24` (management GNS3), `eth1` = `192.168.153.128/24`, passerelle NAT `192.168.153.2` |
| Le contrôleur conserve l'hôte `unknown` | L'adresse de la VM n'est détectée qu'au démarrage de la VM par GNS3 | Réactivation de la GNS3 VM par l'API (`PUT /v2/gns3vm` avec l'ensemble des paramètres) : adresse détectée en 29 s |
| Images Docker absentes | Les images utilisées par le projet n'avaient jamais été téléchargées | `docker pull` de `frrouting/frr`, `gns3/ipterm` et `nginx:alpine` (accès Internet rétabli par `eth1`) |
| Tous les nœuds rattachés au serveur local Windows | Projet généré avec `compute_id = local` ; Docker n'est pas disponible sur un serveur GNS3 Windows | Rattachement des 27 nœuds au compute `vm` |
| Images disques introuvables, `qemu_path` vide refusé par l'API | Noms d'images génériques dans le générateur de topologie | Alignement sur les images présentes dans la VM, chemin QEMU explicite |

> [!WARN] Piège de l'API GNS3
> Une requête `PUT /v2/gns3vm` partielle (par exemple `{"enable": false}`) **remplace** l'ensemble des paramètres au
> lieu de les fusionner ; la requête suivante échoue alors avec `KeyError: 'engine'`. Il faut toujours envoyer le
> dictionnaire complet des paramètres. Toute modification provoque en outre un redémarrage de la VM.

Table: Correspondance des images de disque
| Nœuds | Image attendue initialement | Image utilisée |
|---|---|---|
| EDGE-A, EDGE-B (Cisco IOSv) | `vios-adventerprisek9-m.vmdk` | `vios-adventerprisek9-m.spa.159-3.m6.qcow2` |
| CORE, LEAF (Cisco IOSvL2) | `vios_l2-adventerprisek9-m.vmdk` | `vios_l2-adventerprisek9-m.03.2017.qcow2` |
| FW-A, FW-B (pfSense) | `pfSense-CE.qcow2` | disque vierge `empty100G.qcow2` + ISO `pfSense-CE-2.7.2-RELEASE-amd64.iso` |
| Serveurs Linux | `debian-12-genericcloud.qcow2` | `ubuntu-20.04-server-cloudimg-amd64.img` + ISO cloud-init |

Deux défauts du générateur de topologie ont également été corrigés : le format des noms de ports IOSvL2
(`Gi{0}/{1}` inversait module et port, il devient `Gi{1}/{0}`, conforme au plan de câblage) et la mémoire allouée,
ramenée de 14,8 Go à 12,3 Go pour tenir dans la VM (IOSv 512 Mo, IOSvL2 768 Mo, pfSense 1 Go).

> [!OK] Vérification
> Projet ouvert par l'API : 27 nœuds et 57 liens créés sur la GNS3 VM. Démarrage réussi d'un nœud de chaque type
> (7 conteneurs, IOSv, IOSvL2, pfSense, Ubuntu, deux commutateurs) ; les consoles répondent sur `192.168.75.128`.

La procédure a été généralisée dans le script `03_Network/fixgns3.ps1`, utilisable sur un autre poste présentant le
même défaut : il découvre la VM, les réseaux VMware et leurs passerelles, applique l'adressage adapté (DHCP lorsqu'il
est disponible, statique sinon), corrige Docker, réactive la VM par l'API et peut rattacher un projet à la VM.
Un mode `-DryRun` permet un diagnostic sans aucune modification.

## Source unique de vérité

L'ensemble du réseau est décrit dans un seul fichier, `inventory/dc_casa.yaml`. Les générateurs de configuration,
les scripts de pilotage et les tableaux de ce rapport lisent ce fichier : une modification du réseau se fait à un
seul endroit et se propage partout, ce qui évite les divergences entre documentation et équipements.

Table: Structure de l'inventaire
| Section | Contenu |
|---|---|
| `site`, `services` | Domaine, fuseau horaire, AS 65100, préfixe public, serveurs DNS/NTP/syslog/supervision |
| `vlans`, `transit` | Plan de VLAN (sous-réseau, passerelle, VIP, zone) et segments de transit |
| `isps` | Opérateurs : AS, préférence locale, liens et adresses |
| `devices` | Équipements réseau : rôle, plateforme, espace TIA-942, loopback, management, ports et voisins |
| `lab_switches` | Commutateurs GNS3 (SW-OUT, SW-DMZ, SW-MGMT) : VLAN par port, trunks 802.1Q |
| `servers` | Serveurs et conteneurs : VLAN, adresse, bonding, rôles |
| `firewall_rules`, `core_acl` | Politique de filtrage par interface et ACL inter-VLAN, avec renvoi au tableau 18 du dossier |
| `tests` | Scénarios de panne T1 à T6 et M1, actions et objectifs |

```yaml title="Extrait de inventory/dc_casa.yaml"
  CORE-A:
    role: core
    platform: iosvl2
    tia: MDA
    loopback: 10.255.0.21
    mgmt: {ip: 10.10.0.21, port: Gi2/0}
    ports:
      Gi0/0: {to: "FW-A:em3", mode: access, vlan: 902, role: "Vers FW-A lagg0"}
      Gi0/2: {to: "CORE-B:Gi0/2", mode: portchannel, channel: 1, role: "ISL Po1 LACP #1"}
      Gi1/0: {to: "LEAF-A1:Gi0/0", mode: trunk, role: "Uplink Hall A"}
```

Un contrôle automatique (`automation/validate_inventory.py`) vérifie la cohérence avant toute génération : symétrie
de chaque lien déclaré aux deux extrémités, appartenance de chaque adresse à son sous-réseau, absence de doublon et
conformité au plan de câblage GNS3.

```text title="Résultat du contrôle de l'inventaire"
links checked: 98, IPs checked: 92
  note: re-cabled (SW-OUT): EDGE-A:Gi0/3 <-> FW-A:em0
  note: re-cabled (SW-OUT): EDGE-A:Gi0/4 <-> FW-B:em0
  note: re-cabled (SW-OUT): EDGE-B:Gi0/3 <-> FW-A:em1
  note: re-cabled (SW-OUT): EDGE-B:Gi0/4 <-> FW-B:em1
RESULT: OK
```

Les seules différences avec le câblage initial sont les quatre liens Edge–pare-feu remplacés par le segment SW-OUT.

## Génération des configurations

Le script `automation/gen_configs.py` lit l'inventaire et produit l'ensemble des fichiers de configuration ainsi
que les tableaux de ce rapport. Les configurations sont versionnées dans `configs/` : toute évolution du réseau est
visible dans l'historique Git.

Table: Fichiers produits par le générateur
| Fichier | Équipements | Contenu principal |
|---|---|---|
| `configs/EDGE-A.cfg`, `EDGE-B.cfg` | Cisco IOSv | VRF MGMT, eBGP/iBGP et politiques, OSPF, HSRP de transit avec suivi de route, anti-usurpation |
| `configs/CORE-A.cfg`, `CORE-B.cfg` | Cisco IOSvL2 | VLAN, Rapid PVST+, Port-channel LACP, SVI HSRPv2, ACL inter-VLAN, OSPF, route par défaut vers le pare-feu |
| `configs/LEAF-*.cfg` | Cisco IOSvL2 | VLAN, trunks vers les deux cœurs, ports serveurs protégés, management VLAN 10 |
| `configs/ISP-*/frr.conf` | FRR | Interfaces, eBGP vers les deux Edge, route par défaut, filtrage du préfixe client |
| `configs/servers/*.netplan.yaml` | Ubuntu | Bond actif/passif, adresse, passerelle, DNS |
| `configs/docker/*.interfaces` | Conteneurs | Adressage statique des conteneurs |
| `report/content/generated/*.md` | Rapport | Tableaux d'adressage, de câblage et de filtrage |

Chaque configuration Cisco intègre le même socle de durcissement : horodatage des journaux, chiffrement des mots de
passe, authentification locale AAA, SSH v2 seul sur les lignes VTY (filtrées par liste d'accès sur les VLAN 60 et
90), blocage après échecs de connexion, bannière légale, SNMPv3 *authPriv*, journalisation vers le serveur syslog,
synchronisation NTP et ports inutilisés désactivés.

```text title="Extrait généré – EDGE-A, politique vers ISP-B"
route-map RM-ISP-B-IN permit 10
 description accept default only, set provider preference
 match ip address prefix-list PL-DEFAULT
 set local-preference 100
!
route-map RM-ISP-B-OUT permit 10
 description announce only our public prefix
 match ip address prefix-list PL-ANNOUNCE
 set as-path prepend 65100 65100
```

> [!INFO] Comportement en cas de double perte opérateur sur un Edge
> Le suivi `track 10` diminue la priorité HSRP d'un Edge qui perd sa route par défaut. Comme chaque Edge reçoit
> aussi la route par défaut de son voisin en iBGP, un Edge isolé de ses deux opérateurs continue d'acheminer le
> trafic via l'autre Edge : le service est maintenu, au prix d'un détour par le lien inter-Edge.

## Pilotage du laboratoire

Les équipements ne sont jamais configurés « à la main » dans les consoles. Le module `automation/labctl.py` pilote
le laboratoire de bout en bout :

- **client de l'API GNS3** (`/v2`) : ouverture du projet, démarrage et arrêt des nœuds, suspension de liens pour
  les tests de panne, écriture de fichiers dans les conteneurs ;
- **pilote de console** : client telnet minimal (négociation d'options, attente d'invites par expressions
  régulières), gestion des dialogues du premier démarrage IOS, authentification AAA, mode privilégié ;
- **déploiement** : collage de la configuration générée ligne par ligne, détection des lignes refusées par
  l'équipement (`% Invalid input`, `% Incomplete command`…), puis `write memory` ;
- **preuves** : chaque commande de vérification peut être enregistrée dans `report/evidence/` avec son horodatage,
  pour être reprise dans ce rapport.

Le module `automation/gns3vm.py` exécute des scripts dans la GNS3 VM au travers de VMware Tools (sans SSH) ; il sert
aux opérations de plateforme (Docker, réglages du noyau, diagnostics).

```text title="labctl.py show CORE-A (show version | include IOS|uptime) --save"
Cisco IOS Software, vios_l2 Software (vios_l2-ADVENTERPRISEK9-M), Experimental Version 15.2(20170321:233949) [mmen 101]
ROM: Bootstrap program is IOSv
Switch uptime is 8 minutes
Cisco IOSv () processor (revision 1.0) with 574705K/209920K bytes of memory.
saved report/evidence/CORE-A__show_version_include_ios_uptime.txt
```

## Incidents de plateforme

La mise au point du pilote a révélé deux défauts de la plateforme, qui auraient rendu les tests de résilience
non significatifs s'ils n'avaient pas été corrigés.

Table: Incidents de plateforme et corrections
| Incident | Diagnostic | Correction |
|---|---|---|
| Saturation CPU de la GNS3 VM (charge ≈ 8 pour 3 vCPU, 98 % d'occupation) avec les 25 nœuds démarrés | Chaque IOSvL2 consomme ≈ 34 % d'un cœur au repos (pas d'optimisation *idle-PC*), les IOSv ≈ 17 %, KSM ≈ 24 % | VM portée à **6 vCPU** (hôte i5-11400H, 12 threads) par l'API GNS3 ; KSM ralenti (200 pages / 100 ms, service `ksm-tune` persistant) ; démarrage des nœuds par étapes |
| Plantage systématique des IOSvL2 environ une minute après le démarrage (`CPU exception occurred: Overflow(4)`, `PC/EIP = 0x8E18E9`), console muette, CPU à 100 % | Défaut connu de l'image IOSvL2 03.2017 avec les types de machine QEMU récents (QEMU 8.0.4 dans la VM) ; le disque était sain (`qemu-img check`) | Option QEMU `-machine pc-q35-4.2` appliquée aux 6 nœuds IOSvL2, au modèle GNS3 et au générateur de topologie |

![Écran VGA de CORE-A capturé par le moniteur QEMU : démarrage bloqué après le plantage IOSvL2](../screenshots/01_iosvl2_boot_hang.png){width=420}

> [!OK] Vérification
> Après correction, CORE-A démarre et reste stable ; la console répond (`Switch#`) et le pilote récupère la sortie
> des commandes. Mémoire de la VM avec les 25 nœuds démarrés : 3,6 Go utilisés sur 9,9 Go grâce à la déduplication
> KSM (≈ 6 Go de pages identiques partagées entre les IOSv, IOSvL2 et Ubuntu).
