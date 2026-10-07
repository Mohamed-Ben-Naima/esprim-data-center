# Résumé {-}

Ce rapport documente la **phase réseau** (phases 4 et 5) du projet de Data Center de Casablanca, conçu au niveau
**ANSI/TIA-942-C Rated-3**. Il prolonge le dossier de conception détaillé (*Conception d'un Data Center TIA-942
Rated-3 et simulation réseau avec GNS3*) en passant de la conception à la **réalisation** : chaque équipement du
laboratoire GNS3 est configuré, chaque mécanisme de redondance est vérifié, et chaque choix est rattaché à une
exigence ou à une norme.

Le laboratoire constitue un *Digital Twin* simplifié du réseau : deux opérateurs (ISP-A, ISP-B), deux routeurs de
bordure (EDGE-A, EDGE-B), deux pare-feux pfSense en haute disponibilité (FW-A, FW-B), deux cœurs de niveau 3
(CORE-A, CORE-B), quatre commutateurs Leaf répartis sur deux halls, ainsi que des serveurs et des conteneurs
représentatifs (calcul, stockage, sauvegarde, services d'infrastructure, supervision, DCIM et simulateurs
techniques).

La réalisation suit une démarche d'**infrastructure as code** : un inventaire unique décrit le réseau (VLAN,
adresses, ports, politiques de filtrage) et des générateurs produisent les configurations des équipements ainsi que
les tableaux de ce rapport. Le document est construit de manière incrémentale : il est complété, régénéré et
versionné après chaque sous-tâche du plan d'exécution.

**Mots-clés :** Data Center, TIA-942 Rated-3, GNS3, BGP, OSPF, HSRP, CARP, pfSense, VLAN, segmentation,
haute disponibilité, supervision, Zabbix, Digital Twin.
