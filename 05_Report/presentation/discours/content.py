"""Speech content for the v1 deck (24 slides). Every figure comes from ../facts.json or the slide itself.

Markup: **bold**, `code`, [[pause]] = a breath mark shown in the script.
"""

TEAM = [
    # name, slides, colour, mission
    ("Daly", (1, 5), "#0e7490", "Accrocher le jury, poser la cible Tier III et la norme TIA-942."),
    ("Aziz", (6, 10), "#7c3aed", "Montrer de quoi le bâtiment est fait : espaces, secours, froid, énergie, sûreté."),
    ("Mohamed", (11, 16), "#b45309", "Montrer le labo et le réseau : environnement, VLAN, services, web, NAS, annuaire."),
    ("Akrem", (17, 20), "#be123c", "Montrer la protection : pare-feu, ACL, supervision, sécurité et conformité."),
    ("Iheb", (21, 24), "#15803d", "Prouver en direct, résumer les preuves, conclure."),
]

# ------------------------------------------------------------------------------------------------------------------
# Norms cheat sheet (everybody must be able to say the first column in one sentence)
NORMS = [
    ("ANSI/TIA-942-C", "Norme américaine de l'infrastructure des data centers (TIA = Telecommunications Industry "
     "Association). Elle fixe les <b>espaces</b> (ER, MDA, HDA, ZDA, EDA), le câblage, et <b>4 niveaux Rated-1 à "
     "Rated-4</b> évalués sur 4 domaines : télécom, architecture, électricité, mécanique (froid).",
     "Cible <b>Rated-3</b>. Espaces ER/MDA/HDA/EDA dans le labo. <b>6/8 exigences démontrées</b>, 1 simulée "
     "(électrique), 1 conçue (sécurité physique).", "Daly, Aziz"),
    ("Uptime Institute – Tiers I à IV", "Organisme privé qui <b>certifie</b> les data centers. « Tier » est son "
     "terme ; TIA-942 dit « Rated ». Les deux décrivent la même idée : redondance + chemins.",
     "Nous disons « Tier III » par habitude ; le terme exact de notre norme est <b>Rated-3</b>. Pas de certification "
     "demandée (projet d'école).", "Daly"),
    ("ISO/IEC 27001:2022", "Norme internationale du <b>SMSI</b> (système de management de la sécurité de "
     "l'information), certifiable. Clauses 4 à 10 = la méthode (contexte, risques, amélioration continue). "
     "<b>Annexe A = 93 mesures</b> en 4 thèmes : organisationnelles A.5 (37), humaines A.6 (8), physiques A.7 (14), "
     "technologiques A.8 (34).",
     "12 mesures retenues pour notre périmètre technique : <b>11 faites + 1 partielle</b> (A.5.17, attend "
     "l'annuaire). Nous sommes <b>alignés</b>, pas certifiés.", "Akrem (tous)"),
    ("ASHRAE TC 9.9", "Recommandations thermiques des salles informatiques : plage <b>recommandée 18 à 27 °C</b> à "
     "l'entrée des serveurs.", "Consigne <b>20–25 °C</b>, au milieu de la plage. Alerte à 27 °C, critique à 32 °C.",
     "Aziz"),
    ("PUE (ISO/IEC 30134-2)", "Indicateur d'efficacité : <b>énergie totale du site ÷ énergie des serveurs</b>. "
     "1,0 = parfait. Moyenne mondiale ≈ 1,5 à 1,6.", "Cible de conception <b>1,45</b> : pour 1 kW de serveurs, 0,45 kW "
     "de froid et de pertes.", "Daly"),
    ("TIA-606", "Norme d'<b>étiquetage</b> et d'administration : chaque baie, port, câble a un nom unique.",
     "Champ <code>tia</code> sur chaque nœud de l'inventaire : <b>fait</b>.", "Aziz"),
    ("IEEE 802.1Q", "Norme des <b>VLAN</b> : une étiquette de 12 bits dans la trame Ethernet → jusqu'à 4094 VLAN.",
     "14 VLAN, trunks 802.1Q entre cœurs et Leaf.", "Mohamed"),
    ("RFC 1918 / 5737 / 5398 / 6996", "Adresses privées <b>10.0.0.0/8</b> (1918) ; adresses de documentation "
     "<b>192.0.2.0/24</b> (5737) ; numéros d'AS de documentation 64496–64511 (5398) et privés 64512–65534 (6996).",
     "Interne en 10.x ; « public » simulé en 192.0.2.0/24 ; opérateurs AS 64500/64501 (doc), nous AS 65100 (privé).",
     "Mohamed"),
    ("RFC 6238 – TOTP", "Code à usage unique à <b>6 chiffres qui change toutes les 30 s</b> (Google Authenticator).",
     "Double facteur sur le bastion SRV-BASTION : <b>fait</b> (test ADM.4).", "Mohamed, Akrem"),
    ("Protocoles de secours", "<b>HSRP</b> (Cisco, propriétaire) ≈ <b>VRRP</b> (standard IETF, RFC 5798) ≈ "
     "<b>CARP</b> (libre, pfSense) : une adresse de passerelle virtuelle partagée par deux équipements. "
     "<b>LACP</b> (IEEE 802.1AX) : agrégation de liens.", "HSRP sur les cœurs, CARP sur les pare-feux, keepalived "
     "(VRRP) sur les serveurs de calcul, LACP entre les cœurs.", "Aziz, Akrem"),
]

ISO = [  # control, title, what we do, status
    ("A.5.15", "Contrôle d'accès", "matrice d'accès par zone, refus par défaut", "Fait"),
    ("A.5.17", "Informations d'authentification", "TOTP sur le bastion, comptes nominatifs ; annuaire à venir",
     "Partiel"),
    ("A.8.2", "Droits d'accès privilégiés", "administration uniquement depuis le VLAN 90", "Fait"),
    ("A.8.5", "Authentification sécurisée", "SSH v2, sessions web fermées après 15 min", "Fait"),
    ("A.8.9", "Gestion de la configuration", "générée depuis l'inventaire, versionnée dans Git, audit 0 écart",
     "Fait"),
    ("A.8.13", "Sauvegarde des informations", "NAS TrueNAS « pull », snapshots ZFS, restauration testée", "Fait"),
    ("A.8.15", "Journalisation", "syslog central, 30 jours, lecteur en lecture seule", "Fait"),
    ("A.8.16", "Activités de surveillance", "Zabbix + Grafana, alertes", "Fait"),
    ("A.8.17", "Synchronisation des horloges", "NTP unique 10.100.0.11", "Fait"),
    ("A.8.20", "Sécurité des réseaux", "pare-feux en HA, ACL inter-VLAN", "Fait"),
    ("A.8.21", "Sécurité des services réseau", "filtrage BGP, NAT, DMZ", "Fait"),
    ("A.8.22", "Cloisonnement des réseaux", "14 VLAN, 5 zones", "Fait"),
]

TIA = [
    ("2 opérateurs, 2 entrées", "Fait"), ("Bordure, pare-feux, cœurs doublés", "Fait"),
    ("Serveurs sur 2 Leaf", "Fait"), ("Espaces ER / MDA / HDA / EDA", "Fait"), ("Étiquetage TIA-606", "Fait"),
    ("Maintenance sans arrêt (T2–T5)", "Mesuré"), ("Chemins électriques A/B", "Simulé"),
    ("Sécurité physique 5 zones", "Conçu"),
]

GOLDEN = [  # what, number, careful
    ("Tier III (Rated-3)", "99,982 % · 1,6 h d'arrêt/an max", "Tier IV : 99,995 % · 0,4 h"),
    ("Le site", "2 halls · 96 baies · 942 kW IT · PUE 1,45", "« site de référence », pas un terrain réel"),
    ("Le labo", "32 nœuds · 62 liens · 20 en profil démo", "18 VM QEMU + 8 conteneurs + 4 switchs + 2 NAT"),
    ("Réseau", "14 VLAN · 22 règles pare-feu · 19 entrées ACL", "matrice de 28 lignes"),
    ("Tests", "59/59 réussis · 12/12 contrôles avant démo", "catalogue : 108 tests, 16 groupes"),
    ("Bascule pare-feu (T2)", "3,0 s (campagne) · 2,5 s (démo enregistrée)", "les deux < cible 5 s — voir piège"),
    ("Bascule cœur (T3)", "4,5 s (avant correction : 150 s)", "cible 5 s"),
    ("Bascule Leaf (T4)", "3,0 s", "cible ≈ 1 s : seul écart, limite de l'émulation"),
    ("Bascule serveur (T5)", "3,1 s", "keepalived, SRV-CMP-02 reprend"),
    ("Alarme chemin A (T6)", "9,4 s", "cible 30 s · 96 baies sur chemin B"),
    ("Électricité", "UPS 5 × 250 kW / chemin · groupes 4 × 750 kW", "les deux en N+1 · ≈ 10 min · démarrage 10–15 s"),
    ("Froid", "4 × 400 kW (3 + 1) → 1,2 MW en N+1", "salle 20–25 °C · ΔT ≈ 12 K · alerte 27 °C"),
    ("Supervision", "18 hôtes Zabbix · 28 panneaux Grafana", "syslog 30 jours"),
    ("Base de données", "MariaDB · 173 tables · 128 Mo", "dump 01:30, tiré par le NAS à 02:00"),
    ("Projet", "43 scripts · 7 363 lignes · 104 commits", "1 inventaire YAML"),
    ("Conformité", "ISO 27001 : 11/12 · TIA-942 : 6/8", "« sans arrondi »"),
]

WORDS = [  # say this / never this
    ("« aligné sur 12 mesures ISO 27001 »", "« certifié ISO 27001 »"),
    ("« conforme Rated-3 pour le réseau, conçu et simulé pour l'électrique »", "« 100 % Tier III »"),
    ("« pfSense, même base FreeBSD et même filtre pf qu'OPNsense »", "« OPNsense » comme s'il tournait"),
    ("« l'annuaire est conçu, pas encore réalisé »", "« l'AD fonctionne »"),
    ("« c'est simulé par BMS-SIM / CCTV-SIM »", "« nous avons des onduleurs / des caméras »"),
    ("« nous ne l'avons pas mesuré ; voici comment nous le ferions »", "inventer un chiffre"),
]

GLOSSARY = [
    ("N, N+1, 2N", "N = juste ce qu'il faut ; N+1 = un élément de secours en plus ; 2N = tout en double."),
    ("Maintenance concurrente", "Pouvoir arrêter n'importe quel équipement pour le maintenir sans couper le service : "
     "le cœur du Tier III."),
    ("ER / MDA / HDA / EDA", "Salle d'entrée des opérateurs / zone de distribution principale (cœur) / distribution "
     "d'une salle / baies des serveurs."),
    ("Leaf", "Switch d'accès en bas de rangée, où sont branchés les serveurs."),
    ("UPS / PDU", "Onduleur à batteries / barre de distribution électrique dans la baie."),
    ("CRAH", "Armoire de traitement d'air de la salle (souffle l'air froid)."),
    ("BMS / DCIM", "Gestion technique du bâtiment (électricité, froid) / gestion de l'infrastructure (baies, "
     "charge, température)."),
    ("NOC", "Centre de supervision : l'équipe qui regarde les alarmes 24 h/24."),
    ("VLAN", "Réseau séparé à l'intérieur d'un même switch."),
    ("HSRP / CARP", "Deux équipements partagent une adresse virtuelle ; si le maître tombe, le secours la prend."),
    ("ACL", "Liste de règles « autorisé / refusé » appliquée sur une interface."),
    ("DMZ", "Zone tampon exposée à Internet, isolée du reste."),
    ("NAT / DNAT", "Traduction d'adresse ; DNAT = rediriger une adresse publique vers un serveur interne."),
    ("SNMPv3 authPriv", "Supervision avec authentification (SHA) et chiffrement (AES-128) ; v1/v2c sont en clair."),
    ("Bastion", "Seul point d'entrée pour administrer, avec double facteur et journal."),
    ("TOTP", "Code à 6 chiffres qui change toutes les 30 s."),
    ("ZFS miroir / snapshot", "Deux disques identiques / photo instantanée du disque à un moment donné."),
    ("Pull", "C'est le NAS qui vient chercher les sauvegardes ; les serveurs n'ont aucun accès au NAS."),
    ("PUE", "Énergie totale ÷ énergie IT. Plus c'est proche de 1, mieux c'est."),
]

# ------------------------------------------------------------------------------------------------------------------
# One card per slide. say = text to recite (short sentences). Everything else = understanding + defence.
SLIDES = [
    # ============================================ DALY ============================================
    dict(n=1, id="cover", title="Couverture",
         say="Bonjour à tous. Nous sommes **Daly, Aziz, Mohamed, Akrem et Iheb**. [[pause]] Notre projet : "
             "concevoir un data center à **Casablanca**, au niveau **Tier III** de la norme **TIA-942**. Nous "
             "l'avons conçu sur le papier, et nous l'avons **réalisé en laboratoire** pour tout ce qui est réseau, "
             "services et sécurité. [[pause]] En bas, quatre chiffres : **32 nœuds**, **59 tests sur 59**, **12 "
             "contrôles sur 12**, et **3 secondes** de coupure quand un pare-feu tombe. Ce sont des mesures, et nous "
             "allons vous les prouver.",
         keys=["Deux mots à poser dès la 1re phrase : <b>Tier III</b> et <b>TIA-942</b>.",
               "Distinguer tout de suite <b>conçu</b> (bâtiment) et <b>réalisé</b> (réseau, services, sécurité).",
               "Les 4 chiffres sont des promesses : Iheb les tient à la slide 22."],
         norm="TIA-942 nommée d'entrée : le jury sait sur quoi nous juger.",
         traps=[("« 3 secondes, c'est mesuré comment ? »",
                 "Une sonde envoie un paquet toutes les 0,5 s pendant qu'on éteint le pare-feu ; on compte les "
                 "paquets perdus. Iheb le montre en direct.")],
         alt="—", improve="Regarder le jury, pas l'écran. Sourire. Phrase 1 apprise par cœur."),
    dict(n=2, id="sommaire", title="Sommaire",
         say="Notre présentation suit le plan demandé : une **introduction**, **trois parties** et une "
             "**conclusion**. [[pause]] Partie 1 : l'**architecture** du data center. Partie 2 : la **conception "
             "technique**, c'est-à-dire le réseau, les services et la sécurité. Partie 3 : la **réalisation "
             "pratique**, une démonstration de cinq minutes sur le laboratoire en marche. [[pause]] Chaque slide "
             "technique montre une **vraie capture** du laboratoire.",
         keys=["Le plan = celui imposé au tableau : le dire montre qu'on a respecté la consigne.",
               "Annoncer la démo dès maintenant crée l'attente."],
         norm="—", traps=[], alt="—", improve="20 secondes maximum : ne pas lire les sous-titres."),
    dict(n=3, id="contexte", title="Introduction et contexte",
         say="Le **besoin** : héberger des services critiques à Casablanca, le cœur économique du Maroc, **sans "
             "jamais s'arrêter pour une maintenance**. [[pause]] La **cible** : la norme ANSI/TIA-942, niveau "
             "**Rated-3**. Concrètement : **2 salles, 96 baies, 942 kilowatts** de charge informatique, et un **PUE "
             "de 1,45**. Le PUE, c'est l'énergie totale du site divisée par l'énergie des serveurs : pour 1 kilowatt "
             "de serveurs, nous dépensons 0,45 kilowatt en froid et en pertes. [[pause]] Notre démarche en cinq "
             "étapes : le site, le campus en 3D sous Blender, le réseau, les services et la sécurité, puis les "
             "tests. Et rien n'est configuré à la main : **43 scripts Python** génèrent et vérifient tout.",
         keys=["Besoin → cible → démarche : trois phrases, trois idées.",
               "Expliquer le PUE en une phrase (le jury aime qu'on définisse).",
               "« Rien à la main » = fil rouge du projet (Mohamed le reprend slide 11)."],
         norm="<b>TIA-942-C</b> : niveaux Rated-1 à 4. <b>PUE</b> défini par ISO/IEC 30134-2. "
              "<b>Conformité</b> : PUE 1,45 = cible de conception, pas une mesure.",
         traps=[("« PUE 1,45, c'est réaliste ? »",
                 "C'est une cible de conception, meilleure que la moyenne mondiale (≈ 1,5–1,6), atteignable grâce aux "
                 "allées confinées et au free cooling. Elle se mesure sur une année d'exploitation."),
                ("« 942 kW, d'où vient ce chiffre ? »", "Du cahier des charges (tableaux 5 à 12) : 96 baies × leur "
                 "puissance, GPU compris.")],
         alt="Autre norme possible : <b>EN 50600</b> (européenne, classes de disponibilité 1 à 4).",
         improve="Mesurer le PUE réel ; viser ≈ 1,3 avec plus de free cooling et du liquide pour les GPU."),
    dict(n=4, id="classification", title="Classification Tier I à IV",
         say="La norme classe les data centers en **quatre niveaux**. [[pause]] **Tier I** : aucune redondance, "
             "99,671 %, presque 29 heures d'arrêt par an. **Tier II** : des composants de secours, mais un seul "
             "chemin, environ 22 heures. [[pause]] **Tier III**, notre choix, ajoute un **chemin de secours** : on peut "
             "arrêter n'importe quel équipement pour le maintenir, sans couper le service. C'est la **maintenance "
             "concurrente** : **99,982 %, soit 1,6 heure d'arrêt par an au plus**. [[pause]] **Tier IV** double tout "
             "en 2N et tolère une panne : 0,4 heure par an. Pourquoi pas le Tier IV ? Il **double le coût** de "
             "l'électricité et du froid pour gagner à peine **1,2 heure par an**. Le Tier III est le bon équilibre.",
         keys=["N+1 = un de plus en secours ; 2N = tout en double.",
               "Mot clé du Tier III : <b>maintenance concurrente</b>.",
               "L'argument Tier IV = coût ÷ gain : 2× le prix pour 1,2 h/an."],
         norm="« Tier » = terme de l'<b>Uptime Institute</b> ; « Rated » = terme de <b>TIA-942</b>. Rated-3 exige "
              "des composants N+1 et un chemin de distribution de secours. <b>Conformité</b> : réseau doublé et "
              "bascules mesurées (T2–T5) ; électrique et froid conçus en N+1, simulés.",
         traps=[("« Votre labo est-il vraiment Tier III ? »",
                 "Le réseau oui : chaque niveau est doublé et chaque bascule est chronométrée. L'électrique et le "
                 "froid sont conçus et simulés, pas construits. Nous le disons slide 20."),
                ("« Qui certifie un Tier III ? »",
                 "L'Uptime Institute certifie la conception, puis le site construit. Pour TIA-942, ce sont des "
                 "organismes d'audit. Nous n'avons pas demandé de certification : c'est un projet d'école.")],
         alt="Tier II (moins cher, mais arrêt pour chaque maintenance) ou Tier IV (2N, banques, bourses).",
         improve="Prévoir dès la conception une évolution vers 2N sur l'électrique pour les clients les plus critiques."),
    dict(n=5, id="localisation", title="Localisation : Casablanca",
         say="Pourquoi le Maroc, et pourquoi **Casablanca** ? Nous avons comparé **cinq pays sur huit critères**. "
             "[[pause]] Casablanca, c'est le **pôle économique** : les utilisateurs sont à quelques millisecondes. Le "
             "site peut recevoir **deux arrivées électriques** et **plusieurs opérateurs fibre**, ce qui est "
             "indispensable pour un Tier III. Le **climat atlantique** tempéré permet le **free cooling** : refroidir "
             "avec l'air extérieur une partie de l'année. [[pause]] Soyons honnêtes : c'est un **site de "
             "référence**. Une vraie étude de terrain vérifierait la **sismicité**, le risque d'**inondation** et la "
             "**corrosion** due à l'air marin.",
         keys=["4 raisons : utilisateurs, énergie, connectivité, climat.",
               "1 limite assumée : pas d'étude de terrain réelle."],
         norm="TIA-942 contient des recommandations de <b>choix de site</b> (risques naturels, accès, réseaux "
              "électriques et télécom). <b>Conformité</b> : critères appliqués sur dossier, pas sur le terrain.",
         traps=[("« Pourquoi pas Tanger ou Benguerir ? »",
                 "Possible : terrain moins cher, moins d'air marin. Mais la demande et la fibre sont à Casablanca. "
                 "Un site en périphérie de Casablanca serait un bon compromis."),
                ("« L'air marin, c'est grave ? »",
                 "Le sel corrode les cartes électroniques : filtration de l'air, salle en légère surpression et "
                 "capteurs de corrosion.")],
         alt="Site en zone industrielle hors centre (coût, risque marin plus faible).",
         improve="Étude de site réelle : carte sismique, zones inondables, distance aux postes électriques.",
         relay="Maintenant que la cible et le site sont posés, **Aziz** va vous montrer de quoi le data center est fait."),
    # ============================================ AZIZ ============================================
    dict(n=6, id="composants", title="Composants : espaces TIA-942 et nœuds",
         say="La norme TIA-942 découpe un data center en **espaces**. [[pause]] L'**Entrance Room**, la salle "
             "d'entrée, reçoit les câbles des **deux opérateurs**. La **MDA**, la zone de distribution principale, "
             "porte le cœur : routeurs, pare-feux et switchs cœurs. Dans chaque salle, la **HDA** distribue vers les "
             "rangées, et l'**EDA**, ce sont les baies des serveurs. [[pause]] À droite, le même découpage dans "
             "GNS3 : **32 nœuds**, dont 18 machines virtuelles et 8 conteneurs. Ce ne sont pas des icônes : **chaque "
             "équipement démarre un vrai système**, Cisco, pfSense ou Linux.",
         keys=["ER → MDA → HDA → EDA : du câble opérateur jusqu'au serveur.",
               "Même découpage sur le papier et dans GNS3.",
               "« Pas des icônes » = vrais systèmes."],
         norm="<b>TIA-942</b> : espaces ER, MDA, HDA, ZDA (optionnelle), EDA. <b>TIA-606</b> : chaque nœud a son "
              "étiquette (champ <code>tia</code>). <b>Conformité</b> : fait.",
         traps=[("« Où est la ZDA ? »",
                 "La ZDA est optionnelle dans la norme. Avec 48 baies par salle, la HDA suffit."),
                ("« Pourquoi des Cisco émulés ? »",
                 "Ce sont les images officielles IOSv / IOSvL2 : vraies commandes, vrais protocoles. Limite : "
                 "elles sont plus lentes que du matériel (voir T4).")],
         alt="Arista vEOS, Cisco Nexus 9000v ; architecture spine-leaf.",
         improve="En production : fabric spine-leaf (EVPN-VXLAN) pour grandir sans refaire le cœur."),
    dict(n=7, id="redondance", title="Redondance : éléments de secours",
         say="La redondance, ce sont les **éléments de secours**. [[pause]] Côté **informatique**, chaque niveau est "
             "doublé : deux opérateurs, deux routeurs, deux pare-feux, deux cœurs, deux Leaf par salle, et chaque "
             "serveur branché sur deux Leaf. [[pause]] Et nous ne l'affirmons pas, **nous l'avons mesuré** : on éteint "
             "un équipement, une sonde envoie un paquet toutes les **demi-secondes**, et on chronomètre la coupure. "
             "Pare-feu : **3 secondes**. Cœur : **4,5 secondes**. Leaf : **3 secondes**. Serveur : **3,1 "
             "secondes**. [[pause]] Côté **non informatique** : deux chemins électriques **A et B**, onduleurs et "
             "groupes en **N+1**, et quatre modules de froid dont **un en secours**.",
         keys=["IT = doublé <b>et</b> chronométré ; non-IT = conçu en N+1 et simulé.",
               "4 chiffres à dire : 3 · 4,5 · 3 · 3,1 secondes."],
         norm="<b>TIA-942 Rated-3</b> : composants N+1 + un chemin de secours → maintenance concurrente. "
              "Mécanismes : BGP (opérateurs), CARP (pare-feux), HSRP (cœurs), bonding (serveurs), keepalived "
              "(calcul). <b>Conformité</b> : mesuré (T2–T5).",
         traps=[("« 4,5 s pour un cœur, c'est long ! »",
                 "Avant correction, c'était 150 s : dans GNS3, un lien reste « up » quand le nœud meurt. Un switch "
                 "de transit commun (SW-IN) l'a ramené à 4,5 s, sous la cible de 5 s."),
                ("« Le Leaf : cible 1 s, vous faites 3 s ? »",
                 "Seul écart : surveillance ARP du bond à 1 s plus reconvergence sur IOSvL2 émulé. Un intervalle "
                 "plus court faisait osciller le lien. Sur matériel réel, ce serait plus rapide."),
                ("« Et si les deux pare-feux tombent ? »",
                 "Double panne : hors périmètre du Tier III, qui garantit une panne ou une maintenance à la fois.")],
         alt="HSRP → <b>VRRP</b> (standard multi-constructeur). Cœur en <b>MLAG/vPC</b> actif-actif.",
         improve="Ajouter <b>BFD</b> (détection en millisecondes) + MLAG → bascules sous la seconde."),
    dict(n=8, id="refroidissement", title="Refroidissement : 20–25 °C, froid N+1",
         say="Presque toute l'électricité consommée par un serveur **devient de la chaleur** : pour un mégawatt "
             "informatique, il faut évacuer environ un mégawatt. [[pause]] Notre principe : l'air froid, **entre 20 et "
             "25 °C**, entre dans les serveurs par l'**allée froide**. Il ressort environ **12 degrés plus chaud** "
             "dans l'**allée chaude**, qui est **confinée** pour que les deux airs ne se mélangent pas. Ensuite la "
             "chaleur part par les armoires de climatisation, les groupes froids, puis les aéroréfrigérants. "
             "[[pause]] Nous avons **quatre modules de 400 kilowatts** : si l'un tombe, les trois autres couvrent "
             "encore **1,2 mégawatt**. C'est du **N+1**. Au-dessus de **27 °C** on alerte, au-dessus de **32 °C** "
             "c'est critique. Pour les baies GPU, très denses, un **refroidissement liquide** est prévu.",
         keys=["Électricité = chaleur : 1 MW IT ≈ 1 MW à évacuer.",
               "Allée froide / allée chaude confinée, ΔT ≈ 12 K.",
               "3 + 1 modules = N+1."],
         norm="<b>ASHRAE TC 9.9</b> : plage recommandée 18–27 °C à l'entrée serveur. Notre 20–25 °C est au milieu : "
              "marge des deux côtés. <b>TIA-942 mécanique Rated-3</b> : froid N+1. <b>Conformité</b> : conçu ; "
              "température suivie par le DCIM et Zabbix.",
         traps=[("« Pourquoi pas 18 °C, plus froid = plus sûr ? »",
                 "Plus froid = plus d'énergie, donc un PUE plus mauvais, sans gain pour les serveurs : ASHRAE dit "
                 "que 18–27 °C suffit."),
                ("« Et l'humidité ? »",
                 "ASHRAE fixe aussi une plage d'humidité ; elle se surveille avec les mêmes capteurs que la "
                 "température.")],
         alt="Refroidissement liquide direct, immersion, free cooling indirect, refroidissement adiabatique.",
         improve="Free cooling indirect plus long dans l'année ; récupération de la chaleur (bâtiments voisins)."),
    dict(n=9, id="energie", title="UPS et PDU : chemins A et B",
         say="L'électricité, maintenant. Si le réseau public coupe, l'**UPS**, l'onduleur, tient la charge sur "
             "batteries pendant **une dizaine de minutes**. C'est largement le temps pour les **groupes "
             "électrogènes** de démarrer : **10 à 15 secondes**. [[pause]] Par chemin, **5 modules d'UPS de 250 "
             "kilowatts** : 4 suffisent, le cinquième est en secours. Et **4 groupes de 750 kilowatts**, dont un en "
             "secours. [[pause]] La **PDU** amène ensuite le courant jusqu'à chaque baie. Tout est doublé en "
             "**chemins A et B** : chaque serveur a **deux alimentations**, une sur chaque chemin. Règle importante : "
             "chaque chemin doit pouvoir porter **seul toute la charge**. Donc au-delà de **45 %** par chemin on "
             "alerte, car au-delà de **50 %**, la perte d'un chemin surchargerait l'autre.",
         keys=["UPS = tenir 10 min ; groupe = prendre le relais en 10–15 s.",
               "4 + 1 UPS et 3 + 1 groupes = N+1.",
               "Règle des 50 % : chaque chemin porte tout seul."],
         norm="<b>TIA-942 électrique Rated-3</b> : UPS et groupes N+1, double chemin de distribution. <b>ISO 27001 "
              "A.7.11</b> (services généraux). <b>Conformité</b> : <b>simulé</b> par BMS-SIM, alarmé par Zabbix "
              "(démo T6).",
         traps=[("« 10 minutes d'autonomie seulement ? »",
                 "Les batteries servent à passer sur les groupes, pas à tenir des heures. Ce sont les groupes et "
                 "leur réserve de carburant qui tiennent dans la durée."),
                ("« Vous avez de vrais onduleurs ? »",
                 "Non : c'est conçu et simulé par BMS-SIM. Chaque élément a son état, et Zabbix déclenche les "
                 "alarmes, comme Iheb le montre avec la coupure du chemin A.")],
         alt="UPS rotatif (DRUPS) ; batteries lithium-ion au lieu du plomb ; 2N électrique (Tier IV).",
         improve="Batteries Li-ion (plus compactes, plus durables) ; PDU intelligentes mesurées prise par prise."),
    dict(n=10, id="surete", title="Caméras et compteurs d'incidents",
         say="Dernier élément non informatique : la **sécurité physique** et le **suivi des incidents**. [[pause]] "
             "**Dix caméras** couvrent les **cinq zones d'accès** : la clôture, le portail, le poste électrique, les "
             "groupes et les entrées. Elles sont sur un **VLAN isolé, le 80**, qui ne parle qu'à la supervision. "
             "[[pause]] Au NOC, les compteurs : sur cette capture, **96 baies OK**, 0 dégradée, 0 hors tension, et "
             "**2 alarmes**. Ces deux alarmes, c'est la marge de charge des chemins électriques : **47,1 % pour un "
             "seuil de 45 %**. [[pause]] Un détail honnête : la température affiche **29,5 °C**. C'était une "
             "**dérive de notre simulateur**, que nous avons trouvée et corrigée en préparant cette présentation.",
         keys=["Caméras = VLAN 80 isolé.",
               "2 alarmes = marge voulue (47,1 % > 45 %), pas une panne.",
               "29,5 °C : le dire <b>avant</b> que le jury le voie."],
         norm="<b>ISO 27001 A.7.4</b> (surveillance de la sécurité physique), <b>A.8.16</b> (surveillance). "
              "<b>TIA-942</b> : sécurité physique en zones. <b>Conformité</b> : caméras simulées (CCTV-SIM), "
              "5 zones <b>conçues</b> (ADR-08).",
         traps=[("« 29,5 °C, c'est au-dessus de votre seuil de 27 ! »",
                 "Oui, et c'est justement en relisant cette capture que nous avons vu la dérive du simulateur DCIM "
                 "(pas de rappel vers la consigne). Corrigée dans le code le 23/11."),
                ("« Les caméras sont réelles ? »",
                 "Simulées : un conteneur CCTV-SIM envoie des détections à Zabbix. Le plan des zones est conçu.")],
         alt="Contrôle d'accès par badge + biométrie, sas anti-retour (mantrap), détection d'intrusion.",
         improve="Lier badge et caméra (une entrée = une image) ; vidéo conservée selon la loi 09-08 (CNDP).",
         relay="Voilà pour le bâtiment. **Mohamed** va maintenant vous montrer comment nous l'avons construit en "
               "laboratoire, et le réseau qui le relie."),
    # ============================================ MOHAMED ============================================
    dict(n=11, id="environnement", title="Environnement de travail",
         say="Tout le data center tourne sur **un seul PC portable**. Windows, VMware, et dans la machine virtuelle, "
             "**GNS3** : il fait tourner les vrais systèmes Cisco et pfSense en machines **QEMU**, et les services "
             "légers en conteneurs **Docker**. [[pause]] Notre limite : **15,7 Go de mémoire**. On ne peut pas tout "
             "démarrer ensemble, alors le labo démarre **par profils** : **20 nœuds** pour la démo. [[pause]] Le point "
             "le plus important : **rien n'est configuré à la main**. Un seul **fichier d'inventaire YAML** décrit "
             "tout le data center, et **43 scripts Python** génèrent les configurations, les déploient et les "
             "vérifient. Tout est versionné dans **Git**.",
         keys=["1 PC, 32 nœuds, démarrage par profils.",
               "Inventaire unique → configs générées = « infrastructure as code ».",
               "Avantage : on reconstruit tout en ≈ 12 min."],
         norm="<b>ISO 27001 A.8.9</b> (gestion de la configuration) : configuration de référence, versionnée, "
              "contrôlée. <b>Conformité</b> : fait — l'audit compare le réel à l'inventaire : 0 écart.",
         traps=[("« Pourquoi ne pas tout démarrer ? »",
                 "Mesuré : au-delà du profil démo, la VM swappe et le HSRP oscille. Nous l'avons documenté."),
                ("« Si le PC tombe le jour J ? »",
                 "Démarrage à froid ≈ 12 min depuis l'inventaire, et la vidéo de la démo en plan B.")],
         alt="EVE-NG, Containerlab, Cisco CML ; Ansible / Terraform au lieu des scripts maison ; NetBox comme inventaire.",
         improve="Ansible + NetBox ; intégration continue qui teste chaque changement avant de le déployer."),
    dict(n=12, id="vlan", title="VLAN et plan d'adressage",
         say="Le réseau est découpé en **14 VLAN**, un par fonction : serveurs, stockage, sauvegarde, DMZ, "
             "supervision, BMS, caméras, administration, services, plus des VLAN de transit. [[pause]] Un **VLAN**, "
             "c'est un réseau séparé à l'intérieur du même switch : une machine d'un VLAN ne voit pas celles d'un "
             "autre sans passer par un routeur ou un pare-feu. [[pause]] Notre adressage se lit tout seul : **10, "
             "point, numéro du VLAN, point, l'hôte**. Par exemple, 10.20, c'est le VLAN 20, les serveurs. Le **point "
             "1** est la passerelle virtuelle HSRP, les **points 2 et 3** les deux cœurs. [[pause]] Les **ports "
             "libres** sont éteints et rangés dans un VLAN poubelle, le **999**.",
         keys=["14 VLAN = 10 VLAN de service + 4 techniques (transit, OSPF, parking).",
               "Adresse = 10.&lt;VLAN&gt;.0.&lt;hôte&gt; : lisible.",
               "Internes → passerelle sur les cœurs ; DMZ, MGMT, ADMIN → passerelle sur le pare-feu."],
         norm="<b>IEEE 802.1Q</b> (VLAN), <b>RFC 1918</b> (10.0.0.0/8), <b>RFC 5737</b> (192.0.2.0/24 pour le "
              "« public » simulé). <b>ISO 27001 A.8.22</b> (cloisonnement). <b>Conformité</b> : fait.",
         traps=[("« Pourquoi des /24 partout ? »",
                 "Lisibilité : 254 hôtes par fonction suffisent. Les transits sont en /28 et /30 pour ne pas gaspiller."),
                ("« À quoi sert le VLAN 999 ? »",
                 "Un port oublié n'est dans aucun VLAN utile : quelqu'un qui s'y branche n'accède à rien."),
                ("« Vos AS sont privés ? » (précision)",
                 "Opérateurs AS 64500 / 64501 = numéros de <b>documentation</b> (RFC 5398) ; notre AS 65100 = "
                 "<b>privé</b> (RFC 6996).")],
         alt="VXLAN / EVPN pour des milliers de segments ; IPv6 en double pile.",
         improve="IPv6 ; 802.1X sur les ports d'accès ; private VLAN pour isoler les serveurs entre eux."),
    dict(n=13, id="services", title="Services : DNS et DHCP",
         say="Chaque service a une **adresse fixe** et des **ports déclarés** dans l'inventaire, et les ACL "
             "n'ouvrent que ces ports. [[pause]] Le **DNS**, c'est l'annuaire des noms : il traduit un nom en "
             "adresse. Nous en avons **un seul**, sur **SRV-INF-01** : il sert la zone interne **dc.casa.lab** et "
             "relaie le reste vers deux résolveurs publics. Le résolveur de pfSense est désactivé, pour garder **une "
             "seule source de vérité**. [[pause]] Le **DHCP** donne une adresse automatiquement. Pour les serveurs, "
             "nous l'avons **écarté exprès** : un bail qui expire sous un service critique, c'est un risque. Les "
             "serveurs ont donc des adresses fixes, et l'inventaire sert de registre. Le relais DHCP pour de futurs "
             "postes est **conçu, pas déployé**.",
         keys=["DNS unique = cohérence.",
               "Pas de DHCP pour les serveurs = choix de sécurité, pas un oubli.",
               "Bonus : ce même serveur donne l'heure (NTP) à tout le monde."],
         norm="<b>ISO 27001 A.8.21</b> (sécurité des services réseau), <b>A.8.17</b> (horloges : NTP unique "
              "10.100.0.11, tous les journaux à la même heure). <b>Conformité</b> : fait.",
         traps=[("« Un seul DNS, c'est un point unique de défaillance ! »",
                 "Oui, dans le labo, par manque de RAM. En production : deux DNS, un par salle. C'est notre "
                 "première amélioration."),
                ("« Pourquoi pas de DHCP du tout ? »",
                 "Les serveurs d'un data center sont en adresses fixes partout. Le DHCP sert aux postes "
                 "clients : relais `ip helper-address` + pool dnsmasq conçus.")],
         alt="BIND9 / Unbound / DNS Windows intégré à l'AD ; DHCP ISC Kea ; IPAM NetBox ou phpIPAM.",
         improve="Second DNS dans la salle B ; DNSSEC ; DHCP Kea en haute disponibilité pour les postes."),
    dict(n=14, id="web-db", title="Serveur web et base de données",
         say="À gauche, le **serveur web vu depuis Internet**. Depuis l'opérateur ISP-A, l'adresse publique "
             "**192.0.2.80** répond « **OK SRV-WEB-01** ». Comment ? Le pare-feu fait une **redirection de port**, du "
             "NAT, vers le serveur **nginx** placé en **DMZ**. [[pause]] La DMZ, c'est une **zone tampon** : exposée à "
             "Internet, mais qui ne peut joindre **ni le management, ni l'administration**. [[pause]] À droite, la "
             "**base de données** : **MariaDB**, celle de la supervision Zabbix, **173 tables, 128 mégaoctets**. "
             "Elle est exportée chaque nuit à **1 h 30**, et le NAS vient la chercher à **2 h**. Nous n'avons pas "
             "ajouté de serveur pour la forme : **cette base sert vraiment**.",
         keys=["Internet → IP publique → DNAT → DMZ → nginx.",
               "DMZ = exposée mais enfermée.",
               "Base utile, sauvegardée chaque nuit, secret passé par fichier."],
         norm="<b>ISO 27001 A.8.22</b> (DMZ = cloisonnement), <b>A.8.13</b> (sauvegarde de la base). "
              "<b>Conformité</b> : fait, capture du 23/11.",
         traps=[("« Un seul serveur web, ce n'est pas Tier III ! »",
                 "Exact pour l'application : dans le labo, un seul. En production, deux serveurs web derrière un "
                 "répartiteur de charge (HAProxy) avec CARP."),
                ("« Où est le mot de passe de la base ? »",
                 "Passé par fichier, jamais en ligne de commande : nous avons appris que les lignes de commande "
                 "sont journalisées.")],
         alt="Apache, Caddy ; PostgreSQL (aussi supporté par Zabbix).",
         improve="2 web + répartiteur ; réplication de la base (Galera) ; WAF ; certificat TLS signé."),
    dict(n=15, id="nas", title="Stockage NAS TrueNAS « pull »",
         say="Le stockage de sauvegarde : un **NAS TrueNAS** dans la **salle B**, deux disques en **miroir ZFS**. Si "
             "un disque meurt, l'autre a tout. [[pause]] Le point fort, c'est le **mode « pull »** : c'est le NAS qui "
             "va chercher les sauvegardes, **en lecture seule**. Aucun serveur n'a d'identifiant vers le NAS. Donc "
             "un serveur infecté par un **rançongiciel** ne voit pas les sauvegardes : il ne peut **ni les chiffrer, "
             "ni les effacer**. [[pause]] En plus, des **snapshots** : une photo du disque chaque heure, gardée 24 "
             "heures, et chaque jour, gardée 14 jours. [[pause]] Et surtout, **nous avons testé la restauration** : "
             "fichier supprimé, retrouvé dans le snapshot, restauré, avec **la même empreinte SHA-256**. Une "
             "sauvegarde non testée n'est pas une sauvegarde.",
         keys=["Miroir = panne de disque ; snapshot = suppression ; pull = rançongiciel.",
               "Restauration prouvée (empreinte identique, 10/11/2026).",
               "NAS dans l'autre salle que les serveurs."],
         norm="<b>ISO 27001 A.8.13</b> : copies de sauvegarde <b>et tests de restauration réguliers</b>. "
              "<b>Conformité</b> : fait (test NAS.5). Règle <b>3-2-1</b> (3 copies, 2 supports, 1 hors site) : "
              "partielle, pas de copie hors site.",
         traps=[("« Le miroir, c'est une sauvegarde ? »",
                 "Non : le miroir protège seulement d'une panne de disque. Ce sont les snapshots et le pull qui "
                 "protègent les données."),
                ("« Et si le NAS lui-même est attaqué ? »",
                 "Il n'est joignable que depuis l'administration. La vraie réponse est une copie hors site "
                 "immuable : c'est dans nos améliorations.")],
         alt="Veeam, Bacula, restic / BorgBackup ; RAIDZ2 avec plus de disques ; stockage objet S3 immuable.",
         improve="Copie hors site (autre ville) immuable → règle 3-2-1 complète."),
    dict(n=16, id="ad-ldap", title="AD et LDAP",
         say="L'**annuaire central**, AD/LDAP, sert à avoir **un seul compte par personne** pour tous les "
             "équipements. [[pause]] Il est **conçu** : un contrôleur **Samba 4** compatible Active Directory, et "
             "pfSense, Zabbix et Grafana qui s'y authentifient en **LDAPS**, c'est-à-dire LDAP chiffré, port 636. "
             "[[pause]] Il n'est **pas encore réalisé**, et nous préférons le dire : **nous ne montrons rien qui ne "
             "tourne pas**. [[pause]] Ce qui tourne déjà : des **comptes nominatifs** et un **bastion à double "
             "facteur**. À droite, la trace : le compte par défaut est refusé, un mauvais code TOTP est refusé, le "
             "bon code passe.",
         keys=["Annuaire = conçu, pas réalisé : le dire calmement, sans s'excuser.",
               "Ce qui protège déjà : comptes nominatifs + TOTP.",
               "Seul contrôle ISO partiel : A.5.17."],
         norm="<b>ISO 27001 A.5.17</b> (authentification) : <b>partiel</b>. <b>RFC 6238</b> (TOTP) : fait. LDAPS = "
              "LDAP sur TLS, port 636.",
         traps=[("« Pourquoi ne pas l'avoir fait ? »",
                 "Priorités et mémoire : réseau, pare-feu et sauvegarde d'abord, car ce sont eux qui font le Tier "
                 "III. L'annuaire est la prochaine étape."),
                ("« Pourquoi Samba et pas Windows Server ? »",
                 "Gratuit, Linux, compatible Active Directory et léger en RAM.")],
         alt="Windows Server AD DS, FreeIPA, OpenLDAP ; Keycloak pour l'authentification unique (SSO).",
         improve="Réaliser l'annuaire → ISO 12/12 ; RADIUS ou TACACS+ pour les équipements Cisco.",
         relay="Le réseau est découpé ; reste à le protéger. **Akrem** va vous présenter le pare-feu, les ACL, la "
               "supervision et la sécurité."),
    # ============================================ AKREM ============================================
    dict(n=17, id="firewall", title="Pare-feu pfSense en haute disponibilité",
         say="Le pare-feu est **pfSense**, et il est **en paire**. **FW-A** est maître sur les **cinq adresses "
             "virtuelles CARP**. **FW-B** attend en secours, avec **exactement les mêmes règles**, synchronisées "
             "automatiquement. [[pause]] Si FW-A tombe, FW-B reprend les adresses en quelques secondes, et grâce à "
             "**pfsync** il garde les connexions déjà ouvertes. [[pause]] La règle de base : **tout ce qui n'est pas "
             "autorisé est refusé**, et chaque refus est **journalisé**. [[pause]] Les **22 règles** ne sont pas "
             "écrites à la main : elles sont **générées depuis l'inventaire**, et un audit compare la configuration "
             "réelle à l'inventaire. Résultat : **zéro écart**.",
         keys=["CARP = adresse partagée ; pfsync = connexions ; XMLRPC = règles.",
               "Refus par défaut + journal.",
               "22 règles générées, audit 0 écart."],
         norm="<b>ISO 27001 A.8.20</b> (sécurité des réseaux) et <b>A.8.9</b> (configuration). Principe du "
              "<b>refus par défaut</b>. <b>Conformité</b> : fait (test FW-07 : 0 différence entre FW-A et FW-B).",
         traps=[("« Le sujet demandait OPNsense ! »",
                 "pfSense et OPNsense ont la même base FreeBSD et le même filtre pf. pfSense nous a donné CARP, "
                 "pfsync et XMLRPC éprouvés en bascule. Changer aurait cassé le test T2 sans rien apporter."),
                ("« Pas d'IDS / IPS ? »",
                 "Pas dans le labo, faute de RAM. Suricata s'installe sur pfSense : c'est une amélioration.")],
         alt="OPNsense, FortiGate, Palo Alto, Cisco Firepower.",
         improve="IPS Suricata ; filtrage applicatif (NGFW) ; règles revues automatiquement à chaque changement."),
    dict(n=18, id="acl", title="ACL inter-VLAN",
         say="Entre les VLAN internes, ce sont les **cœurs** qui routent, donc ce sont eux qui filtrent, avec **une "
             "ACL par interface de VLAN**. [[pause]] La matrice se lit ligne par ligne : une **source**, et en cyan, "
             "les **destinations autorisées**, avec leurs ports. **Tout le reste est refusé**. [[pause]] La règle "
             "d'or : **l'administration peut atteindre tout le monde, mais personne ne peut atteindre "
             "l'administration**. [[pause]] À droite, la preuve : le serveur de supervision essaie de joindre le poste "
             "d'administration. C'est **refusé**, et le cœur **compte la tentative**. Enfin, un script, "
             "**flow_matrix.py**, teste chaque case de la matrice de bout en bout : **zéro écart**.",
         keys=["Lecture de la matrice : source → destinations autorisées → ports.",
               "Règle d'or : personne n'atteint l'administration.",
               "Testé case par case, 0 écart."],
         norm="<b>ISO 27001 A.5.15</b> (contrôle d'accès, moindre privilège) et <b>A.8.22</b> (cloisonnement). "
              "<b>Conformité</b> : fait (flow_matrix.csv).",
         traps=[("« Pourquoi filtrer sur les cœurs et pas tout au pare-feu ? »",
                 "Le trafic interne reste à la vitesse du switch ; le pare-feu deviendrait un goulot. Le pare-feu, "
                 "avec état, garde les flux vers DMZ, management et Internet."),
                ("« Une ACL Cisco a-t-elle un état ? »",
                 "Non, c'est un filtrage simple et rapide. Le filtrage avec état est au pare-feu.")],
         alt="Micro-segmentation (VMware NSX, Cisco ACI) ; pare-feu interne est-ouest.",
         improve="Micro-segmentation par application ; revue automatique de la matrice à chaque nouveau service."),
    dict(n=19, id="noc", title="Supervision NOC : Zabbix et Grafana",
         say="Tout remonte à **Zabbix** : les équipements Cisco en **SNMPv3 chiffré**, pfSense, les agents des "
             "serveurs, et les API du BMS et du DCIM. L'équipe du **NOC** regarde **Grafana**, qui affiche les "
             "tableaux de bord. [[pause]] À droite, la vraie liste : **18 hôtes**. En vert, les nœuds démarrés. En "
             "**maintenance**, ceux qui sont éteints dans le profil de démo : ils ne déclenchent donc **pas de fausse "
             "alerte**. Les deux problèmes restants sont la marge voulue des chemins électriques. [[pause]] Et les "
             "**journaux** de tous les équipements arrivent sur un **collecteur central**, gardés **30 jours**, avec "
             "un lecteur en lecture seule.",
         keys=["Zabbix collecte, Grafana affiche.",
               "SNMPv3 = authentifié + chiffré.",
               "Maintenance automatique = 0 fausse alerte."],
         norm="<b>ISO 27001 A.8.15</b> (journalisation), <b>A.8.16</b> (surveillance), <b>A.8.17</b> (horloges). "
              "SNMPv3 authPriv = SHA + AES-128. <b>Conformité</b> : fait.",
         traps=[("« pfSense est en SNMP v2c ? »",
                 "Oui, limité au seul VLAN de supervision (60). Passer pfSense en v3 est une amélioration."),
                ("« 30 jours de journaux, c'est assez ? »",
                 "Pour le labo oui. En production, la durée suit la politique et les obligations légales, souvent un an.")],
         alt="Prometheus + Alertmanager, Centreon, PRTG ; SIEM Wazuh ou ELK pour les journaux.",
         improve="SIEM (corrélation des journaux) ; alertes vers SMS / messagerie ; astreinte 24 h/24."),
    dict(n=20, id="securite", title="Sécurité et conformité",
         say="Pour finir la partie technique : la **défense en profondeur**, en **six couches**. Le **périmètre** "
             "filtre les routes des opérateurs. Le **pare-feu** refuse par défaut. Les **VLAN et les ACL** séparent "
             "les zones. L'**administration** n'est possible que depuis un seul endroit. Les **équipements** sont "
             "durcis. Et les **données** sont protégées par la sauvegarde pull. Un attaquant doit franchir plusieurs "
             "barrières. [[pause]] Le chemin d'administration est **unique** : depuis le **VLAN 90**, par le "
             "**bastion à double facteur**, puis en SSH ou HTTPS, et **chaque session est journalisée**. [[pause]] "
             "Côté conformité, nous avons compté **sans arrondir** : **11 contrôles ISO 27001 sur 12** sont faits, le "
             "douzième attend l'annuaire. Et **6 exigences TIA-942 sur 8** sont démontrées : l'électrique est "
             "simulé, la sécurité physique est conçue.",
         keys=["6 couches : périmètre, pare-feu, segmentation, accès admin, équipements, données.",
               "1 seul chemin d'administration.",
               "11/12 ISO et 6/8 TIA : dire « sans arrondir »."],
         norm="Voir le tableau de conformité (page « Conformité ») : 12 mesures ISO et 8 exigences TIA, avec "
              "statut. <b>Conformité</b> : <b>aligné</b>, pas certifié.",
         traps=[("« Vous êtes certifiés ISO 27001 ? »",
                 "Non. La certification porte sur un SMSI complet (analyse de risques, déclaration d'applicabilité, "
                 "audit interne, revue de direction) audité par un organisme accrédité. Nous avons mis en œuvre et "
                 "prouvé 12 mesures de l'Annexe A sur notre périmètre technique."),
                ("« Pourquoi 12 mesures sur 93 ? »",
                 "Ce sont celles qui touchent l'infrastructure que nous avons construite. Les autres sont "
                 "organisationnelles ou humaines : contrats, formation, fournisseurs."),
                ("« Et la loi marocaine ? »",
                 "Loi 05-20 sur la cybersécurité, loi 09-08 sur les données personnelles (CNDP), et la directive "
                 "nationale de la DGSSI : un vrai projet devrait s'y conformer.")],
         alt="ISO/IEC 27017 (cloud), SOC 2, PCI DSS (paiement), NIST CSF.",
         improve="Annuaire → 12/12 ; analyse de risques ISO 27005 ; audit blanc avant certification.",
         relay="Assez de théorie : **Iheb** va vous montrer tout cela **en marche**, sur le laboratoire."),
    # ============================================ IHEB ============================================
    dict(n=21, id="demo", title="Démonstration en 5 minutes",
         say="Place à la **réalisation pratique**. Le laboratoire tourne depuis le début de la soutenance. "
             "[[pause]] En cinq minutes, nous allons vous montrer le réseau, le pare-feu et la supervision, puis "
             "**provoquer deux vraies pannes** et les **chronométrer**.",
         steps=[
             ("0:00", "Topologie", "Voici le projet GNS3 : **32 nœuds**, rangés par zone TIA-942. Le profil démo en "
              "démarre **20**."),
             ("0:30", "Réseau", "Sur CORE-A, `show standby brief` : CORE-A est actif pour les VLAN **20, 40, 60 et "
              "100**, CORE-B pour **30, 70 et 80** : ils se partagent le travail. OSPF : les voisins sont **FULL**. "
              "Sur LEAF-B1, les **trunks** portent les VLAN."),
             ("1:30", "Pare-feu", "Sur pfSense, FW-A est **MASTER** sur les adresses CARP, FW-B est **BACKUP**. Et "
              "depuis l'opérateur, le site web répond grâce au **NAT**."),
             ("2:15", "Supervision", "Zabbix : **18 hôtes**. Grafana : le tableau du NOC, baies, chemins électriques, "
              "températures."),
             ("3:00", "Panne T6", "Nous **coupons le chemin électrique A** dans le BMS. Regardez : l'**alarme** monte, "
              "les **96 baies** passent en « dégradé » mais restent **alimentées par le chemin B**. Aucune baie hors "
              "tension."),
             ("3:45", "Panne T2", "Nous **arrêtons le pare-feu maître FW-A**. La sonde envoie un paquet toutes les "
              "demi-secondes… FW-B est devenu **MASTER**. Coupure mesurée : **[lire le chiffre affiché]**."),
             ("4:30", "Preuve", "Pour finir, `demo_check.py` : **12 lignes, 12 OK**."),
         ],
         keys=["Dire <b>le chiffre affiché à l'écran</b>, jamais celui du script.",
               "Pendant une attente, phrase de remplissage : « c'est exactement la maintenance concurrente du "
               "Tier III : un équipement arrêté, le service continue ».",
               "Un coéquipier peut piloter le clavier pendant qu'Iheb commente."],
         norm="La démo prouve en direct l'exigence centrale du <b>Rated-3</b> : maintenance / panne d'un élément "
              "sans arrêt du service.",
         traps=[("Le labo ne répond pas / un écran reste vide",
                 "Ne pas déboguer devant le jury. Dire : « Nous passons la vidéo enregistrée sur ce même "
                 "laboratoire le 23 novembre. » Grafana vide juste après le démarrage = attendre, ou passer la vidéo."),
                ("« Rejouez la panne ! »",
                 "Possible pour T6 (rallumer le chemin A, puis recouper). Pour T2, attendre que FW-A soit revenu "
                 "MASTER avant de recommencer.")],
         alt="Plan B : vidéo 1080p (PC + clé USB), même déroulé.",
         improve="Répéter 2 fois la démo chronométrée la veille ; ne jamais lancer de test destructif le jour même."),
    dict(n=22, id="preuves", title="Ce que la démo prouve",
         say="Ce que la démonstration prouve. [[pause]] **Un** : l'arrêt du pare-feu maître ne coupe le trafic que "
             "**2,5 secondes** pendant la démo enregistrée, **3 secondes** pendant notre campagne de tests : les deux "
             "**sous la cible de 5 secondes**. [[pause]] **Deux** : la perte du chemin électrique A lève l'alarme en "
             "**9,4 secondes**, pour une cible de **30**, et les **96 baies** restent alimentées par le chemin B. "
             "[[pause]] **Trois** : sur les **cinq bascules** mesurées, **quatre sont dans la cible**. La cinquième, le "
             "Leaf, fait 3 secondes au lieu d'une : c'est une limite de l'émulation, et nous préférons le dire. "
             "[[pause]] Enfin, le catalogue complet : **59 tests sur 59**, et **12 contrôles sur 12** avant la démo.",
         keys=["Trois preuves, numérotées « un, deux, trois ».",
               "Expliquer 3,0 s vs 2,5 s <b>avant</b> qu'on le demande.",
               "Dire l'écart du Leaf soi-même = crédibilité."],
         norm="<b>TIA-942 Rated-3</b> : maintenance concurrente prouvée par T2 à T5 ; T6 prouve le double chemin "
              "électrique (simulé).",
         traps=[("« La couverture dit 3,0 s, ici 2,5 s ? »",
                 "Deux mesures : 3,0 s pendant la campagne de tests, 2,5 s pendant la démo enregistrée. Les deux sont "
                 "sous 5 s."),
                ("« 59/59, mais votre catalogue a 108 tests ? »",
                 "verify_lab rejoue les tests non destructifs du profil démo : 59 réussis, 0 échec, 1 limite connue, "
                 "2 non applicables (nœuds éteints). Les pannes T1 à T6 sont jouées à part."),
                ("« T1 et M1 ? »",
                 "T1 (perte d'ISP-A) : bascule BGP vérifiée, pas chronométrée. M1 (double événement) : pas rejoué "
                 "dans ce profil, faute de RAM.")],
         alt="—", improve="Chronométrer T1 ; rejouer M1 sur une machine avec plus de mémoire."),
    dict(n=23, id="conclusion", title="Conclusion",
         say="Ce que nous retenons. [[pause]] **Ce qui est acquis** : un réseau Tier III qui tourne vraiment, 32 "
             "nœuds, 14 VLAN, un pare-feu en haute disponibilité, une sauvegarde pull, une supervision complète, et "
             "59 tests sur 59. [[pause]] **Ce que nous avons appris**, avec trois vrais problèmes. La perte d'un cœur "
             "coupait le réseau **150 secondes** : nous l'avons ramenée à **4,5**. Nous avons trouvé des **secrets "
             "dans les journaux** : ils passent maintenant par fichier. Et le HSRP devenait instable : nous avons "
             "**maîtrisé la mémoire** de la VM. [[pause]] **La suite** : l'annuaire et le DHCP, un cœur en MLAG, le "
             "matériel réel, une étude de terrain à Casablanca et un audit ISO formel. [[pause]] Notre règle pendant "
             "tout le projet : **tout ce qui est montré tourne, et tout ce qui ne tourne pas est dit.**",
         keys=["Acquis · Leçons · Suite : trois blocs.",
               "La dernière phrase est la signature du projet : la dire lentement, en regardant le jury."],
         norm="Amélioration continue = clause 10 d'ISO 27001 (corriger, apprendre, améliorer).",
         traps=[("« La plus grosse difficulté ? »",
                 "La perte d'un cœur : 150 s de coupure, parce qu'un lien GNS3 reste « up » quand le nœud meurt. "
                 "Le switch de transit SW-IN l'a ramenée à 4,5 s.")],
         alt="—", improve="Voir la page « Si nous avions trois mois de plus »."),
    dict(n=24, id="merci", title="Merci, questions",
         say="Merci pour votre attention. [[pause]] Nous sommes prêts pour vos questions. Si vous le souhaitez, nous "
             "pouvons **rejouer une panne en direct**, et la version longue de la présentation contient toutes les "
             "annexes : VLAN, adresses, règles et tests.",
         keys=["Toute l'équipe se lève / se rapproche.",
               "Celui qui est désigné (page Q&R) répond ; les autres complètent en une phrase."],
         norm="—", traps=[], alt="—", improve="Garder la version longue (v0, 61 slides) ouverte dans un onglet."),
]

QA = [  # who, question, answer
    ("Daly", "Pourquoi Tier III et pas Tier IV ?",
     "Le 2N double l'électrique et le froid pour passer de 1,6 h à 0,4 h d'arrêt par an : le besoin ne le justifie pas."),
    ("Daly", "Quelle différence entre Tier et Rated ?",
     "Même idée. « Tier » est le terme de l'Uptime Institute (qui certifie) ; « Rated » celui de TIA-942."),
    ("Aziz", "Votre labo est-il vraiment Tier III ?",
     "Le réseau oui : doublé et bascules mesurées. L'électrique et le froid sont conçus et simulés (BMS-SIM)."),
    ("Aziz", "Comment évitez-vous les boucles entre les cœurs ?",
     "Port-channel LACP entre cœurs, Rapid-PVST+ avec racines réparties, loop guard et BPDU guard."),
    ("Mohamed", "Combien de temps pour reconstruire le labo ?",
     "≈ 12 min à froid (lab_up.py), 1 min de contrôle (demo_check.py) ; tout est régénéré depuis l'inventaire."),
    ("Mohamed", "Pourquoi une sauvegarde « pull » ?",
     "Un serveur compromis n'a aucun identifiant vers le NAS : il ne peut ni lire, ni chiffrer, ni effacer les sauvegardes."),
    ("Mohamed", "Où sont les mots de passe ?",
     "Dans l'inventaire du labo (comptes de labo). Nous avons vu des clés SNMP dans les journaux : rotation et "
     "règle « secrets par fichier »."),
    ("Akrem", "Comment l'administrateur se connecte-t-il ?",
     "Uniquement depuis le VLAN 90 : bastion avec TOTP, puis SSH v2 ou HTTPS ; chaque session est journalisée."),
    ("Akrem", "Comment prouvez-vous que les ACL marchent ?",
     "flow_matrix.py teste chaque flux autorisé et interdit de bout en bout : 0 écart, et chaque refus est dans le journal."),
    ("Akrem", "Comment savez-vous qu'une alerte n'est pas fausse ?",
     "Les nœuds éteints passent automatiquement en maintenance ; seules restent les vraies alarmes."),
    ("Iheb", "Que montre exactement « 59/59 » ?",
     "Tous les tests non destructifs du profil démo réussis ; 1 limite connue (fuseau d'ADMIN-WS), 2 non applicables."),
    ("Iheb", "Qu'est-ce qui manque pour la production ?",
     "Cœur MLAG/vPC, matériel réel, annuaire central, second DNS, copie hors site, étude de terrain, audit ISO."),
    ("Tous", "Une question dont on ne connaît pas la réponse",
     "« Nous ne l'avons pas mesuré. Voici comment nous le ferions : … » — jamais de chiffre inventé."),
]

IMPROVE = [  # priority, what, why
    ("1", "Annuaire AD (Samba 4) + RADIUS/TACACS+", "un compte par personne ; ISO 27001 passe à 12/12"),
    ("2", "Second DNS, 2 serveurs web + répartiteur", "supprimer les derniers points uniques de défaillance"),
    ("3", "Cœur MLAG/vPC + BFD", "bascules sous la seconde, Leaf dans la cible de 1 s"),
    ("4", "Copie de sauvegarde hors site et immuable", "règle 3-2-1 complète, résiste à la perte d'un site"),
    ("5", "SIEM (Wazuh) + IPS Suricata + SNMPv3 partout", "détecter, pas seulement journaliser"),
    ("6", "IPv6 en double pile, 802.1X", "réseau d'avenir, ports authentifiés"),
    ("7", "Étude de site réelle + PUE mesuré", "transformer le site de référence en vrai projet"),
    ("8", "SMSI complet : analyse de risques ISO 27005, audit blanc", "préparer une vraie certification"),
]

CHECKLIST = [
    "Chacun connaît par cœur sa <b>première phrase</b> et sa <b>phrase de relais</b>.",
    "Chacun peut dire en une phrase <b>TIA-942</b>, <b>ISO 27001</b> et <b>Tier III</b> (page Normes).",
    "Tous les chiffres = page « Chiffres d'or » (source facts.json) — personne n'en cite un autre.",
    "À vérifier avant le 25/11 : une alerte Zabbix est-elle bien branchée sur la température max d'entrée "
    "(seuil 27 °C) ? Si non, le dire comme amélioration à la slide 10.",
    "Vidéo de démo ≤ 5 min prête (PC + clé USB) ; PDF de la présentation au même endroit.",
    "Labo démarré 25 min avant : <code>lab_up.py --profile demo</code> puis <code>demo_check.py</code> = 12 OK.",
    "Jamais <code>verify_lab.py --disruptive</code> le jour même ; pas de captures pendant verify_lab.",
    "Répétition complète chronométrée au moins 2 fois ; cible ≈ 24 min de parole + 5 min de démo.",
]
