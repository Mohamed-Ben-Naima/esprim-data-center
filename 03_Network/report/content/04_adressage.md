# Plan de VLAN et d'adressage

Tous les tableaux de ce chapitre sont **générés automatiquement** à partir de l'inventaire
(`inventory/dc_casa.yaml`) par `automation/gen_configs.py` ; ils sont donc identiques, par construction, aux
configurations déployées. Les plages privées RFC 1918 sont utilisées en interne ; les plages de documentation
RFC 5737 représentent l'Internet public.

## VLAN et sous-réseaux

Les passerelles des VLAN métier sont portées par les cœurs en **HSRPv2** (adresse virtuelle `.1`, CORE-A en `.2`,
CORE-B en `.3`) ; les rôles actifs sont répartis entre les deux cœurs pour équilibrer la charge de routage. Les
passerelles de la DMZ, du management et de l'administration sont portées par les pare-feux en **CARP**, afin que
ces flux soient systématiquement inspectés.

@include generated/vlans.md

> [!NOTE] Règles de construction
> - le troisième octet de chaque sous-réseau métier reprend le numéro de VLAN (VLAN 20 = 10.20.0.0/24) ;
> - les adresses `.1` à `.9` sont réservées aux passerelles, les serveurs commencent en `.11` ;
> - le VLAN 10 (management) n'est jamais transporté sur les trunks de production ; le VLAN 999 regroupe les ports
>   inutilisés, désactivés.

## Équipements d'infrastructure

Chaque équipement dispose d'une loopback `/32` dans 10.255.0.0/24 (identifiant de routeur, source iBGP) et d'une
adresse de management hors bande dont le dernier octet reprend celui de la loopback (convention de l'annexe B du
dossier). Sur les Edge et les cœurs, l'interface de management est placée dans une **VRF MGMT** : le réseau de
management n'est jamais routé dans la table de production.

@include generated/infra.md

## Liens opérateurs

@include generated/wan.md

Seul le préfixe 192.0.2.0/24 est annoncé (liste de préfixes en sortie) et seule la route par défaut est acceptée
des opérateurs. La préférence locale 200 fait sortir le trafic par ISP-A ; le préfixe est annoncé à ISP-B avec un
double *AS-path prepend*, ce qui rend ISP-A également préféré pour le trafic entrant.

## Serveurs et conteneurs

@include generated/servers.md

## Plan de câblage étiqueté

Chaque lien est décrit par ses deux extrémités au format ANSI/TIA-606-C `ESPACE-ÉQUIPEMENT:port` ; cette chaîne est
reprise mot pour mot dans la description des interfaces des équipements. Le plan complet (64 liens) figure en
**annexe A**.
