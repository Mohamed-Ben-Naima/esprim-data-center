# Kit de répétition – soutenance du 25 novembre 2026

Présentation : https://claude.ai/artifact/9SfWhkneCwM7aaFgcNCTd1 (61 slides, notes de l’orateur sous chaque slide).
Vidéo : `05_Report/presentation/video/DC_Casablanca_demo.mp4` (master) et `video/clips/` (un clip par scène).
Chiffres : tous dans `05_Report/presentation/facts.json` – ne jamais en citer un autre.

## 1. Minutage (20 min de parole + vidéo 8 min + questions)

| Partie | Slides | Durée | Repère |
|---|---|---|---|
| I. Introduction | 1–5 | 2 min | finir sur « 59/59, 12/12, 3 secondes » |
| II. Architecture | 6–21 | 6 min | redondance + bascules = le cœur (2 min) |
| III. Conception technique | 22–46 | 9 min | 20 s par slide de service, 40 s pour pare-feu, NAS, matrice |
| IV. Conclusion | 47–53 | 3 min | coulisses = 1 min, raconter 2 histoires (SW-IN, secrets) |
| Démo vidéo ou en direct | 51 | 8 min | au choix du jury ; clips T2 (slide 15) et T6 (slide 21) intégrés |
| Questions | annexes 54–61 | reste | ouvrir l’annexe qui répond |

## 2. Fiches de rappel (une phrase par slide clé)

- **Classification** : « Tier III = maintenable sans arrêt, N+1, 99,982 %, 1,6 h/an. »
- **Pourquoi pas Tier IV** : « 2N double le coût pour gagner une heure par an ; et nous mesurons la maintenance concurrente. »
- **Localisation** : « Choix de conception, pas un terrain réel ; une étude de site vérifierait énergie, fibre, sismique, corrosion. »
- **Redondance** : « Chaque niveau doublé ; pare-feu 3,0 s, cœur 4,5 s, Leaf 3,0 s, serveur 3,1 s. »
- **T4 au-dessus de la cible** : « Limite de l’émulation IOSvL2 ; on le dit plutôt que de le cacher. »
- **Électrique** : « Deux chemins A/B, chacun porte 100 % ; T6 lève l’alarme en 9,4 s. »
- **Automatisation** : « Un fichier YAML, tout le reste est généré et vérifié. »
- **Pare-feu** : « pfSense, pas OPNsense : même base FreeBSD/pf, et c’est ce qui tourne. »
- **NAS** : « Le NAS tire en lecture seule ; un serveur compromis ne voit pas les sauvegardes. »
- **DHCP** : « Adresses fixes par choix ; relais conçu, réalisé avec l’annuaire. »
- **AD/LDAP** : « Conçu, pas montré : nous ne montrons rien qui ne tourne pas. »
- **Conformité** : « 11/12 contrôles ISO, 6/8 exigences TIA, sans arrondi. »

## 3. Vingt questions probables et nos réponses

1. **Pourquoi Casablanca ?** Pôle économique, proximité des utilisateurs, connectivité, climat atlantique favorable au free cooling. C’est un site de référence, pas un terrain validé.
2. **Pourquoi Tier III et pas IV ?** Le 2N du Tier IV double électrique et froid pour passer de 1,6 h à 0,4 h d’arrêt par an ; le besoin ne le justifie pas.
3. **Votre labo est-il vraiment Tier III ?** Le réseau l’est (chaque niveau doublé, bascules mesurées). L’électrique et le froid sont conçus et simulés (BMS-SIM), pas construits.
4. **Pourquoi pfSense alors que le sujet dit OPNsense ?** Même base FreeBSD et même filtre pf ; pfSense nous a donné CARP, pfsync et XMLRPC éprouvés en bascule. Migrer aurait cassé T2 sans rien apporter au jury.
5. **Que se passe-t-il si les deux pare-feux tombent ?** Plus de sortie Internet ni d’accès DMZ/administration ; l’est-ouest interne continue par les cœurs. C’est un double incident hors périmètre Tier III.
6. **Pourquoi la bascule du Leaf fait 3 s et pas 1 s ?** Surveillance ARP du bond à 1 s plus reconvergence Rapid-PVST+ sur IOSvL2 émulé ; sur matériel réel ce serait plus rapide (et un intervalle plus court faisait osciller le bond).
7. **Comment évitez-vous la boucle entre les cœurs ?** Port-channel LACP entre cœurs, Rapid-PVST+ avec racines réparties, loop guard et BPDU guard ; le VLAN 902 de transit n’est pas sur le Po1.
8. **Comment l’administrateur se connecte-t-il ?** Par le VLAN 90 uniquement : bastion avec TOTP, puis SSH v2 ou HTTPS ; le pare-feu n’autorise que SSH, HTTPS et SNMP ; chaque session est journalisée.
9. **Où sont les mots de passe ?** Dans l’inventaire du labo (comptes de labo, jamais réutilisés). Nous avons trouvé que des clés SNMP passaient en ligne de commande, donc dans les journaux : rotation et règle « secrets par fichier ».
10. **Comment prouvez-vous que les ACL marchent ?** flow_matrix.py teste chaque flux autorisé et interdit de bout en bout ; 0 écart, et chaque refus est retrouvé dans le journal.
11. **Pourquoi une sauvegarde « pull » ?** Un serveur compromis ne détient aucun identifiant vers le NAS ; il ne peut ni lire, ni chiffrer, ni effacer les sauvegardes. Les snapshots ZFS protègent d’une suppression propagée.
12. **Avez-vous testé la restauration ?** Oui : fichier supprimé sur le serveur, relu dans le snapshot, restauré avec la même empreinte SHA-256 (trace du 10/11/2026).
13. **Pourquoi pas de DHCP ?** Les serveurs d’un Data Center ont des adresses fixes ; l’inventaire sert d’IPAM. Le relais (`ip helper-address`) et le pool dnsmasq sont conçus pour les postes clients.
14. **Quelle base de données ?** MariaDB derrière Zabbix : 173 tables, 128 Mo, dump nocturne tiré par le NAS. Pas de serveur ajouté pour la forme.
15. **Comment savez-vous qu’une alerte n’est pas fausse ?** Les nœuds éteints passent en maintenance automatiquement ; seuls les vrais problèmes restent (aujourd’hui : la marge de charge voulue des chemins A/B).
16. **Que montre exactement « 59/59 » ?** Tous les tests du catalogue exécutables dans le profil de démo ont réussi ; 1 limite connue (fuseau ADMIN-WS), 2 non applicables car leur nœud est éteint.
17. **Pourquoi ne pas tout démarrer en même temps ?** 15,7 Go de RAM : au-delà du profil de démo, la VM GNS3 swappe et le HSRP oscille. Nous l’avons mesuré et documenté.
18. **Combien de temps pour reconstruire le labo ?** Démarrage à froid ≈ 12 min (`lab_up.py`), contrôle 1 min (`demo_check.py`) ; les configurations sont régénérées depuis l’inventaire.
19. **Qu’est-ce qui manque pour la production ?** Cœur en MLAG/vPC, matériel réel, annuaire central, étude de terrain, audit ISO par un organisme compétent.
20. **Quelle a été la plus grosse difficulté ?** La perte d’un cœur coupait le LAN 150 s, car un lien GNS3 reste « up » quand le nœud meurt ; le segment de transit SW-IN l’a ramenée à 4,5 s.

## 4. Démo en direct : ordre et plan B

1. 25 min avant : VM GNS3 démarrée (VMware), GNS3 ouvert sur le projet.
2. `python automation/lab_up.py --profile demo` (≈ 12 min), puis `python automation/demo_check.py` : **12 lignes OK**.
3. Si une ligne échoue : suivre la ligne `->` affichée ; Grafana vide juste après le démarrage = attendre 5 min.
4. Ordre de démonstration : topologie → `show standby brief` (CORE-A) → pfSense CARP → Grafana NOC → coupure chemin A (BMS) → arrêt FW-A avec sonde.
5. **Plan B** : la vidéo master (8 chapitres) sur le PC, sur la clé USB et sur `H:` ; le PDF de la présentation au même endroit.
6. Ne jamais lancer `verify_lab.py --disruptive` le jour même. Ne pas lancer de captures pendant `verify_lab.py`.
