# Mise en œuvre sous GNS3

## Plateforme de simulation

Table: Plateforme matérielle et logicielle
| Élément | Valeur |
|---|---|
| Hôte | PC Windows 11, 15,7 Go de RAM (le dossier de conception visait 32 Go) |
| Hyperviseur | VMware Workstation, VM « GNS3 VM » stockée sur `H:\GNS3 VM` |
| GNS3 | Version 2.2.56.1 (client, serveur local et serveur de la VM identiques) |
| Ressources allouées à la VM | 10 Go de RAM, 3 vCPU, virtualisation imbriquée (VT-x) activée |
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
