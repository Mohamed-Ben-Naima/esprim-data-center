# Services et supervision

## Gestion technique du bâtiment et DCIM

Le simulateur GTB (BMS-SIM) applique la règle d'alimentation du dossier (§13.3) et les seuils du tableau 22 ; le DCIM
(SRV-DCIM-01) interroge la GTB toutes les 10 secondes et dérive l'état de chacune des 96 baies.

> [!INFO] Constat de dimensionnement révélé par la simulation
> Au nominal, la charge IT de 942 kW répartie sur les deux chemins représente **47,1 % de la capacité de chaque
> chemin**, au-delà du seuil d'avertissement de 45 % fixé par le dossier (tableau 22) : la GTB signale en permanence
> un état **WARNING**. Le site fonctionne donc près de la limite de 50 % au-delà de laquelle la perte d'un chemin ne
> pourrait plus être absorbée. La simulation confirme l'intérêt de l'extension progressive prévue (§4.6) ou d'une
> révision des seuils avant la mise en service.

## Services d'infrastructure : SRV-INF-01

SRV-INF-01 (VLAN 100, 10.100.0.11) fournit les deux services dont dépendent tous les autres : la résolution de noms
et l'heure. Ses deux cartes sont agrégées en `bond0` actif/passif (LEAF-B1 / LEAF-B2).

Table: Services de SRV-INF-01
| Service | Logiciel | Configuration | Vérification |
|---|---|---|---|
| DNS | dnsmasq | Zone `dc.casa.lab`, réexpédition vers 1.1.1.1 / 8.8.8.8 au travers du pare-feu, écoute sur 10.100.0.11:53 | `dig @10.100.0.11 deb.debian.org` → réponse |
| NTP | chrony | Synchronisé sur des serveurs publics (strates 2-3), sert `10.0.0.0/8`, strate locale 8 en secours | `chronyc sources` : 4 sources, écoute UDP 123 |
| Journalisation | rsyslog | Envoi de tous les journaux vers 10.60.0.12 | Fichier `10.100.0.11_srv-inf-01.log` sur SYSLOG |

Table: Difficultés rencontrées lors du déploiement des serveurs et corrections
| Difficulté | Cause | Correction (`deploy_servers.py`) |
|---|---|---|
| `apt` ne résout aucun nom | SRV-INF-01 est son propre serveur DNS, encore absent | Résolveurs publics pendant l'installation, puis DNS interne |
| `archive.ubuntu.com` injoignable | Les serveurs de Canonical ne répondent pas depuis l'accès Internet du site (constaté aussi depuis la GNS3 VM) | Miroir `mirrors.edge.kernel.org`, IPv4 uniquement (le laboratoire n'achemine pas IPv6) |
| Mise à jour des index trop longue | Débit de quelques centaines de ko/s au travers des routeurs et pare-feux logiciels | Index réduits (`focal`, `focal-security`, `main universe`, sans traductions) |
| Verrou `dpkg` occupé | Mise à niveau automatique lancée au démarrage | Arrêt propre par SIGTERM, contrôle `dpkg --audit`, minuteries désactivées |
| Console bloquée | Commande interrompue lors d'une session précédente | Envoi de Ctrl-C à chaque connexion à la console |
| Latence et pertes ponctuelles | Saturation CPU de la VM (six IOSvL2 à 50-70 % d'un cœur chacun) | Profil « services » : Leaf du hall A arrêtés pendant les déploiements du hall B |
