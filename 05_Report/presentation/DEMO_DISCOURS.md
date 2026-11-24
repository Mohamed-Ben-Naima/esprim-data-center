# Discours mot à mot – Démonstration (Partie 3, 5 min)

**Comment lire ce texte :** tu lis **exactement** ce qui est écrit dans les encadrés « 🎤 ».
Les lignes **▶ / ⏸** disent quoi faire avec la vidéo. Quand la vidéo tourne, **tu te tais** : la voix off parle.
Durée totale : environ 1 min 20 de parole + 3 min 36 de vidéo = **5 min**.

---

## 1. Avant de lancer la vidéo (slide 21 à l'écran) – 25 s

> 🎤 « Nous passons à la réalisation pratique.
> Ce que vous allez voir n'est pas une animation : c'est notre laboratoire GNS3, filmé en direct.
> Pour chaque machine, la vidéo donne trois choses : son rôle, ce que l'on teste, et le résultat à l'écran.
> Je la mettrai en pause aux moments importants. »

**▶ Lancer la vidéo.** (Ne rien dire pendant le titre et le démarrage.)

---

## 2. Pause 1 – à **0:29** (console GNS3 sur CORE-A) – 15 s

**⏸ Pause** quand le tableau `show standby brief` est affiché.

> 🎤 « Ici, on est directement dans la console de GNS3, sur le cœur de réseau CORE-A.
> On voit qu'il est actif sur cinq passerelles, et que CORE-B porte les trois autres.
> Chaque cœur travaille, et chacun est le secours de l'autre : si l'un tombe, l'autre reprend tout. »

**▶ Reprendre.**

---

## 3. Pause 2 – à **1:07** (pfSense, page CARP) – 12 s

**⏸ Pause** sur la liste des adresses « MASTER ».

> 🎤 « Le pare-feu FW-A est maître sur ses cinq adresses virtuelles.
> FW-B attend en secours. Dans un instant, nous allons arrêter FW-A pour de vrai, et mesurer la coupure. »

**▶ Reprendre.** (Se taire pendant le site web et le SOC.)

---

<div style='page-break-before:always'></div>

## 4. Pause 3 – à **1:53** (Grafana) – 15 s

**⏸ Pause** quand le tableau de bord est rempli.

> 🎤 « Voici le centre de supervision, en direct.
> Les deux chemins électriques A et B sont alimentés, les quatre-vingt-seize baies sont en état normal,
> le PUE est de 1,45, et la température de la salle reste dans la consigne de vingt à vingt-cinq degrés. »

**▶ Reprendre.** (Se taire pendant la panne T6 et l'ACL.)

---

## 5. Pause 4 – à **2:47** (panne T2, chronomètre) – 12 s

**⏸ Pause** quand « coupure mesurée 2,5 s » s'affiche.

> 🎤 « Nous venons d'arrêter le pare-feu principal.
> Le service a été coupé deux secondes et demie, et FW-B a pris le relais tout seul, sans intervention humaine.
> L'objectif Tier III, c'est moins de cinq secondes. »

**▶ Reprendre.**

---

## 6. Pause 5 – à **3:09** (panne T5, serveur de calcul) – 12 s

**⏸ Pause** quand le résultat de T5 s'affiche.

> 🎤 « Même chose côté application : on arrête un serveur de calcul.
> L'adresse du service passe sur le second serveur en quatre secondes et demie.
> Pour l'utilisateur, le service continue. »

**▶ Reprendre** jusqu'à la fin (NAS TrueNAS).

---

## 7. À la fin de la vidéo – 20 s

> 🎤 « Pour résumer : le réseau, le pare-feu, l'électricité, le calcul et les sauvegardes sont redondants,
> et nous l'avons prouvé en provoquant les pannes, chronomètre en main.
> Tous ces tests sont automatisés et rejouables. Je suis à votre disposition pour vos questions. »

**→ Passer à la slide 22.**

---

<div style='page-break-before:always'></div>

## 8. Si le jury pose une question – réponses mot à mot

**« C'est vraiment en direct ? »**
> 🎤 « Oui. Presque tout a été filmé en direct dans la nuit du 23 au 24 novembre et le 24 au matin.
> Seules la panne du pare-feu et le contrôle douze sur douze viennent de l'enregistrement du 23 au matin,
> parce qu'ils demandent tout le laboratoire allumé en même temps. »

**« Pourquoi vous n'allumez pas tout en même temps ? »**
> 🎤 « Notre PC a 15,7 gigaoctets de mémoire pour trente-deux équipements virtuels.
> Nous démarrons donc le labo par profils : réseau, supervision, calcul, sauvegarde.
> C'est une limite du PC de démonstration, pas de l'architecture du data center. »

**« La slide redondance dit 3,1 secondes pour le serveur, la vidéo 4,5 ? »**
> 🎤 « Ce sont deux mesures réelles, faites à des jours différents. Dans la vidéo, un seul cœur de réseau tournait.
> Dans les deux cas, le service reprend sur le second serveur, ce qui est l'objectif. »

**« Comment vous savez que la sauvegarde fonctionne ? »**
> 🎤 « Nous avons restauré un fichier depuis un instantané ZFS du NAS, et son empreinte SHA-256 est identique à l'original.
> C'est dans la version longue de la vidéo. »

**« Vous avez un SIEM ? »**
> 🎤 « Non, nous ne l'avons pas déployé. Nous avons une journalisation centralisée : tous les équipements envoient leurs journaux
> à un serveur SYSLOG, avec une visionneuse protégée qui verrouille le compte après six mauvais mots de passe. »

**« Et Active Directory / LDAP ? »**
> 🎤 « Il est conçu, comme le montre la slide dédiée, et prévu juste après la soutenance. »

**« Et les mots de passe dans vos scripts ? »**
> 🎤 « Aucun mot de passe n'est tapé en clair : les champs sont masqués, et aucun secret ne passe sur une ligne de commande,
> parce que le poste d'administration journalise chaque commande. »

**Question que tu ne connais pas :**
> 🎤 « Bonne question. Je préfère ne pas vous répondre approximativement : je vérifie et je vous réponds précisément après. »

---

## Plan B

- **La vidéo ne démarre pas :** ouvrir le fichier avec VLC ou « Films et TV ». **Espace** = pause.
- **Rien ne marche :** rester sur la slide 21 et dire :

> 🎤 « La vidéo ne démarre pas, je vous présente donc les résultats directement. »

Puis lire la colonne « Ce que le jury voit » de la slide 21, ligne par ligne, et passer à la slide 22.
