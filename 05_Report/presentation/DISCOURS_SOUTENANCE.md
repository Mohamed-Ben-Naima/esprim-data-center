# Discours de soutenance – mot à mot (24 slides, ≈ 23 min)

**Comment lire :** tu dis **exactement** le texte des encadrés « 🎤 ». La ligne **→** dit quand changer de slide.
Rythme : calme, une phrase = une respiration. Les chiffres sont ceux des slides : n'en invente aucun.

| Partie | Slides | Durée |
|---|---|---|
| Introduction | 1–3 | 2 min |
| Partie 1 – Architecture | 4–10 | 6 min |
| Partie 2 – Conception technique | 11–20 | 8 min |
| Partie 3 – Réalisation pratique (démo) | 21–22 | 6 min |
| Conclusion | 23–24 | 1 min + questions |

---

## Introduction (2 min)

**Slide 1 – Titre**
> 🎤 « Bonjour à tous. Nous allons vous présenter le Data Center Casablanca : un centre de données de niveau Tier III, conçu selon la norme TIA-942, et réalisé en laboratoire sous GNS3 pour tout ce qui est réseau, services et sécurité.
> Les quatre chiffres en bas de l'écran, trente-deux nœuds, cinquante-neuf tests réussis sur cinquante-neuf, douze contrôles sur douze, et une bascule de pare-feu de trois secondes : ce sont les chiffres que nous allons prouver pendant cette présentation. »

→ **Slide 2**

**Slide 2 – Sommaire**
> 🎤 « Notre plan suit exactement celui qui nous a été demandé. Une introduction, puis l'architecture du data center, ensuite la conception technique, puis la réalisation pratique avec une démonstration de cinq minutes, et enfin la conclusion.
> Chaque slide technique montre une capture réelle de notre laboratoire, ou un schéma généré à partir de notre inventaire. »

→ **Slide 3**

**Slide 3 – Contexte**
> 🎤 « Le besoin, c'est d'héberger des services critiques à Casablanca, le cœur économique du Maroc, sans jamais s'arrêter pour une maintenance.
> Notre cible : le niveau Rated-3 de la norme TIA-942, avec deux salles, quatre-vingt-seize baies, neuf cent quarante-deux kilowatts de charge informatique, et un PUE de 1,45.
> Notre démarche s'est faite en cinq étapes : le choix du site, le campus en 3D, le réseau, les services et la sécurité, et enfin les tests. Tout ce qui est réseau, services et sécurité tourne réellement dans GNS3, et chaque affirmation est vérifiée par un script. »

→ **Slide 4**

---

<div style="page-break-before:always"></div>

## Partie 1 – Architecture du Data Center (6 min)

**Slide 4 – Classification**
> 🎤 « Il existe quatre niveaux. Le Tier I n'a aucune redondance. Le Tier II a des composants de secours, mais un seul chemin.
> Le Tier III, notre cible, ajoute un chemin de secours : on peut arrêter n'importe quel élément pour le maintenir, sans couper le service. Cela donne une disponibilité de 99,982 %, soit au plus 1,6 heure d'arrêt par an.
> Pourquoi pas le Tier IV ? Parce qu'il double tout, ce qu'on appelle le 2N. Cela double le coût, pour gagner à peine plus d'une heure par an. Pour notre besoin, le Tier III est le bon compromis. »

→ **Slide 5**

**Slide 5 – Localisation**
> 🎤 « Nous avons comparé cinq pays sur huit critères, et retenu le Maroc. Casablanca, parce que c'est là que se trouvent les utilisateurs et l'activité économique : ils sont à quelques millisecondes du data center.
> Le site dispose de deux arrivées électriques et de plusieurs opérateurs fibre. Le climat atlantique, tempéré, permet aussi un refroidissement naturel une partie de l'année.
> C'est un site de référence : une vraie étude de terrain vérifierait encore la sismicité, les risques d'inondation, et la corrosion due à l'air marin. »

→ **Slide 6**

**Slide 6 – Composants**
> 🎤 « À gauche, les espaces définis par la norme : l'Entrance Room, qui reçoit les deux opérateurs ; la MDA, qui porte les pare-feux et les cœurs de réseau ; et dans chaque salle, les zones de distribution et les baies.
> À droite, le même découpage dans GNS3 : trente-deux nœuds réels, rangés par zone. Ce ne sont pas des icônes : chaque équipement démarre un vrai système, des routeurs Cisco, des pare-feux pfSense, des serveurs et des conteneurs. »

→ **Slide 7**

**Slide 7 – Redondance**
> 🎤 « La redondance, ce sont les éléments de secours.
> Côté informatique, chaque niveau est doublé : deux opérateurs, deux routeurs de bordure, deux pare-feux, deux cœurs de réseau, et deux commutateurs par salle. Et nous avons mesuré chaque bascule avec une sonde toutes les demi-secondes : entre trois et quatre secondes et demie.
> Côté non informatique : deux chemins électriques A et B, des onduleurs et des groupes électrogènes en N+1, et quatre modules de froid dont un en secours. »

→ **Slide 8**

**Slide 8 – Refroidissement**
> 🎤 « Presque toute l'électricité consommée par les serveurs devient de la chaleur : pour un mégawatt informatique, il faut évacuer environ un mégawatt.
> L'air froid entre par l'allée froide entre vingt et vingt-cinq degrés, ressort environ douze degrés plus chaud dans l'allée chaude, qui est confinée pour éviter tout mélange.
> Nous avons quatre modules de quatre cents kilowatts : si l'un tombe, les trois autres couvrent encore 1,2 mégawatt. Au-delà de vingt-sept degrés on alerte, au-delà de trente-deux c'est critique. »

→ **Slide 9**

**Slide 9 – UPS et PDU**
> 🎤 « L'onduleur, ou UPS, tient la charge sur batteries environ dix minutes, le temps que les groupes électrogènes démarrent, en dix à quinze secondes.
> La PDU amène ensuite le courant jusqu'à chaque baie. Tout est doublé en chemins A et B : chaque serveur a deux alimentations, une sur chaque chemin, et chaque chemin peut porter seul toute la charge.
> C'est pour cela qu'on alerte au-delà de quarante-cinq pour cent par chemin : au-delà de cinquante, la perte d'un chemin surchargerait l'autre. »

→ **Slide 10**

**Slide 10 – Caméras et compteurs**
> 🎤 « Dix caméras couvrent les cinq zones d'accès : la clôture, le portail, le poste électrique, les groupes et les entrées. Elles sont sur un réseau isolé, le VLAN 80, qui ne parle qu'à la supervision.
> Les compteurs d'incidents sont sur le tableau du NOC : les baies saines, dégradées ou hors tension, et les alarmes en cours.
> Sur cette capture, la température affiche 29,5 degrés : c'était un défaut de notre simulateur, que nous avons trouvé et corrigé. Dans la démonstration, vous verrez la valeur en direct : environ 24,5 degrés, dans la consigne. »

→ **Slide 11**

---

<div style="page-break-before:always"></div>

## Partie 2 – Conception technique (8 min)

**Slide 11 – Environnement**
> 🎤 « Tout tourne sur un seul PC portable : Windows, VMware, et dans la machine virtuelle GNS3, les routeurs, les pare-feux, les serveurs et les conteneurs.
> Avec 15,7 gigaoctets de mémoire, on ne peut pas tout démarrer en même temps : le laboratoire démarre donc par profils.
> Et surtout, rien n'est configuré à la main. Un seul fichier d'inventaire décrit tout le data center, et quarante-trois scripts génèrent, déploient et vérifient les configurations. »

→ **Slide 12**

**Slide 12 – VLAN et adressage**
> 🎤 « Nous avons quatorze VLAN, un par fonction : serveurs, stockage, sauvegarde, DMZ, supervision, gestion technique, caméras, administration et services.
> Le plan d'adressage se lit tout seul : 10, puis le numéro du VLAN, puis l'hôte. Point 1, c'est la passerelle virtuelle, et points 2 et 3, les deux cœurs de réseau.
> Les VLAN internes ont leur passerelle sur les cœurs ; la DMZ, le management et l'administration passent par le pare-feu. »

→ **Slide 13**

**Slide 13 – Services, DNS, DHCP**
> 🎤 « Chaque service a une adresse fixe et ses ports dans l'inventaire, et les règles n'ouvrent que ces ports.
> Le DNS interne est unique, sur le serveur SRV-INF-01 : il sert la zone du data center et relaie le reste vers Internet.
> Pour le DHCP, c'est un choix assumé : dans un data center, les serveurs ont des adresses fixes, car un bail qui expire sous un service critique est un risque. Le relais pour des postes clients est conçu, mais pas déployé. »

→ **Slide 14**

**Slide 14 – Web et base de données**
> 🎤 « À gauche, le serveur web vu depuis Internet : depuis l'opérateur, l'adresse publique répond, grâce à une redirection de port vers la DMZ. Et la DMZ ne peut joindre ni le management, ni l'administration.
> À droite, la base de données : MariaDB, derrière Zabbix, avec cent soixante-treize tables. Elle est sauvegardée chaque nuit, et la sauvegarde est récupérée par le NAS. »

→ **Slide 15**

**Slide 15 – NAS**
> 🎤 « Notre NAS TrueNAS fonctionne en mode “pull” : c'est lui qui va chercher les sauvegardes, en lecture seule. Aucun serveur n'a d'identifiant vers le NAS.
> Concrètement, si un serveur est attaqué par un rançongiciel, il ne voit pas les sauvegardes : il ne peut ni les chiffrer, ni les effacer.
> Et nous avons testé la restauration : un fichier relu depuis un instantané ZFS a exactement la même empreinte que l'original. »

→ **Slide 16**

**Slide 16 – AD et LDAP**
> 🎤 « L'annuaire central est conçu : un contrôleur Samba 4 compatible Active Directory, auquel pfSense, Zabbix et Grafana s'authentifieront en LDAPS. Il sera réalisé après la soutenance : nous ne montrons rien qui ne tourne pas.
> Ce qui tourne déjà : des comptes nominatifs, et un bastion à double facteur. À droite, la trace : un mauvais code est refusé, le bon code passe. »

→ **Slide 17**

**Slide 17 – Pare-feu pfSense**
> 🎤 « Le pare-feu est pfSense, en paire. FW-A est maître sur les cinq adresses virtuelles, et FW-B attend en secours, avec exactement les mêmes règles, synchronisées automatiquement.
> Tout ce qui n'est pas autorisé est refusé, et le refus est journalisé. Les vingt-deux règles sont générées depuis l'inventaire, et un audit compare la configuration réelle à l'inventaire : zéro écart. »

→ **Slide 18**

**Slide 18 – ACL**
> 🎤 « Ce tableau est notre politique de flux, zone par zone. Une ligne, c'est une source ; en bleu, les destinations autorisées avec leurs ports. Tout le reste est refusé.
> La règle la plus importante : l'administration peut atteindre tout le monde, mais personne ne peut atteindre l'administration.
> À droite, la preuve : le serveur de supervision essaie de se connecter au poste d'administration, c'est refusé, et le cœur de réseau compte la tentative. »

→ **Slide 19**

**Slide 19 – Supervision NOC**
> 🎤 « Tout remonte à Zabbix : les équipements Cisco en SNMPv3 chiffré, les pare-feux, les serveurs, et la gestion technique du bâtiment. Le NOC regarde le tableau de bord Grafana.
> Les nœuds volontairement éteints sont mis en maintenance automatiquement : il n'y a donc pas de fausse alerte.
> Et les journaux de tous les équipements arrivent sur un collecteur central, où ils restent trente jours. »

→ **Slide 20**

**Slide 20 – Sécurité**
> 🎤 « Notre sécurité est une défense en profondeur, en six couches, du périmètre jusqu'aux journaux. Et il n'existe qu'un seul chemin pour administrer : depuis le VLAN 90, par le bastion à double facteur, avec chaque session journalisée.
> Nous avons compté sans arrondir : onze contrôles ISO 27001 sur douze sont faits, le douzième attend l'annuaire. Et six exigences TIA-942 sur huit sont démontrées, les deux autres étant simulées ou conçues. »

→ **Slide 21**

---

<div style="page-break-before:always"></div>

## Partie 3 – Réalisation pratique (6 min)

**Slide 21 – Démonstration**
> 🎤 « Nous passons à la réalisation pratique. Ce que vous allez voir n'est pas une animation : c'est notre laboratoire GNS3, filmé en direct.
> Pour chaque machine, la vidéo donne trois choses : son rôle, ce que l'on teste, et le résultat à l'écran. Je la mettrai en pause aux moments importants. »

**▶ Lancer la vidéo** et suivre **`DEMO_DISCOURS.pdf`** : 5 pauses, une phrase chacune (0:29, 1:07, 1:53, 2:47, 3:09).

**À la fin de la vidéo :**
> 🎤 « Pour résumer : le réseau, le pare-feu, l'électricité, le calcul et les sauvegardes sont redondants, et nous l'avons prouvé en provoquant les pannes, chronomètre en main. »

→ **Slide 22**

**Slide 22 – Ce que la démo prouve**
> 🎤 « Voici ce que la démonstration prouve. L'arrêt du pare-feu maître ne coupe le trafic que deux secondes et demie. La perte du chemin électrique A lève l'alarme en 9,4 secondes, pour une cible de trente, et les baies restent alimentées par le chemin B.
> Sur les cinq bascules mesurées, quatre sont dans la cible. La cinquième, celle du commutateur d'accès, fait trois secondes au lieu d'une : c'est la limite de l'émulation, et nous préférons le dire.
> Et le catalogue complet de tests : cinquante-neuf sur cinquante-neuf. »

→ **Slide 23**

---

## Conclusion (1 min)

**Slide 23 – Conclusion**
> 🎤 « Pour conclure. Ce qui tourne : tout le réseau, les services et la sécurité, avec des preuves datées.
> Ce que nous avons appris : au début, la perte d'un cœur de réseau coupait tout pendant cent cinquante secondes ; nous l'avons ramenée à quatre secondes et demie. Nous avons aussi trouvé des mots de passe dans les journaux, et nous avons changé notre façon de faire.
> Et la suite : l'annuaire, le DHCP, puis le passage du laboratoire au matériel réel.
> Notre règle a été simple : tout ce qui est montré tourne, et tout ce qui ne tourne pas est dit. »

→ **Slide 24**

**Slide 24 – Merci**
> 🎤 « Merci pour votre attention. Nous sommes prêts pour vos questions. »

---

<div style="page-break-before:always"></div>

## Questions du jury – réponses mot à mot

**« Pourquoi Tier III et pas Tier IV ? »**
> 🎤 « Le Tier IV double tout en 2N : le coût double, pour gagner environ une heure de disponibilité par an. Le Tier III permet déjà de tout maintenir sans arrêt, ce qui correspond à notre besoin. »

**« Pourquoi pfSense et pas un pare-feu du marché ? »**
> 🎤 « pfSense est libre, tourne dans GNS3, et offre la haute disponibilité avec CARP et pfsync. L'architecture reste la même avec un pare-feu commercial : seule la configuration change. »

**« Pourquoi pas de DHCP ? »**
> 🎤 « Dans un data center, les serveurs ont des adresses fixes : c'est plus sûr. Notre inventaire sert de registre d'adresses. Le relais DHCP pour des postes clients est conçu, pas déployé. »

**« Comment vous êtes sûrs qu'il n'y a pas d'erreur de configuration ? »**
> 🎤 « Les configurations sont générées depuis un seul inventaire, puis vérifiées : un audit du pare-feu, un test de chaque flux de la matrice, et cinquante-neuf tests automatiques, tous au vert. »

**« Qu'est-ce qui manque pour passer en production ? »**
> 🎤 « L'annuaire AD/LDAP, le DHCP, un cœur en MLAG, du matériel réel, une étude de terrain à Casablanca, et un audit ISO 27001 formel. »

**« Pourquoi la température affichait 29,5 degrés ? »**
> 🎤 « Notre simulateur DCIM faisait dériver la température sans la ramener vers la consigne. Nous avons corrigé le code et redéployé : en direct, la valeur est autour de 24,5 degrés. »

**Questions sur la démo** : voir la page « Si le jury pose une question » de `DEMO_DISCOURS.pdf`.

**Question inconnue :**
> 🎤 « Bonne question. Je préfère ne pas répondre approximativement : je vérifie et je vous réponds précisément après. »
