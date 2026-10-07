# Routage et haute disponibilité

## Bordure : opérateurs et routeurs Edge

La bordure relie le Data Center à deux opérateurs indépendants. Chaque routeur Edge établit une session eBGP avec
**chacun** des deux opérateurs ; les deux Edge échangent leurs routes en iBGP entre loopbacks, l'accessibilité des
loopbacks étant assurée par OSPF sur deux chemins (lien inter-Edge et segment de transit 901).

Table: Politique de routage de la bordure
| Élément | Mise en œuvre | Effet |
|---|---|---|
| Annonces sortantes | Liste de préfixes `PL-ANNOUNCE` : 192.0.2.0/24 seulement ; double *AS-path prepend* vers ISP-B | Aucun préfixe interne ne fuit ; trafic entrant préféré par ISP-A |
| Routes acceptées | Liste `PL-DEFAULT` : route par défaut seulement ; préférence locale 200 (ISP-A) / 100 (ISP-B) ; `maximum-prefix 100` | Sortie par ISP-A, bascule automatique vers ISP-B |
| Préfixe public | Route statique 192.0.2.0/24 vers le VIP CARP des pare-feux (10.254.1.1), annoncée par `network` | Le trafic de retour vers 192.0.2.10 / .80 atteint toujours le pare-feu maître |
| Détection de panne | Temporisateurs BGP 3/9 s ; OSPF hello 1 s / dead 3 s sur le lien inter-Edge | Convergence en quelques secondes (scénario T1) |
| Passerelle des pare-feux | HSRPv2 groupe 1, VIP 10.254.1.6 ; EDGE-A priorité 110 (préemption), EDGE-B 100 ; suivi de la route par défaut | Une seule adresse de sortie pour les pare-feux, indépendante de l'Edge actif |
| Sécurité | Authentification MD5 des sessions BGP, des adjacences OSPF et de HSRP ; ACL `ACL-WAN-IN` anti-usurpation ; management en VRF | Protection du plan de contrôle |

Les opérateurs simulés (conteneurs FRR) annoncent uniquement une route par défaut (`default-originate`), filtrent
les annonces du client (192.0.2.0/24 seulement) et traduisent les adresses vers l'Internet réel au travers des
nœuds NAT de GNS3.

## Vérification de la bordure

Les configurations générées ont été déployées par `labctl.py push` (aucune ligne refusée par IOS), puis vérifiées.
Les sorties complètes sont conservées dans `report/evidence/`.

```text title="EDGE-A – show ip bgp summary (extrait)"
BGP router identifier 10.255.0.1, local AS number 65100
Neighbor        V           AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
10.255.0.2      4        65100      47      48        3    0    0 00:02:10        2
198.51.100.1    4        64500     303     296        3    0    0 00:14:49        1
203.0.113.5     4        64501     303     296        3    0    0 00:14:49        1
```

```text title="EDGE-A – show ip ospf neighbor / show standby brief"
Neighbor ID     Pri   State           Dead Time   Address         Interface
10.255.0.2        1   FULL/BDR        00:00:32    10.254.1.3      GigabitEthernet0/3
10.255.0.2        0   FULL/  -        00:00:02    10.254.0.2      GigabitEthernet0/2

Interface   Grp  Pri P State   Active          Standby         Virtual IP
Gi0/3       1    110 P Active  local           10.254.1.3      10.254.1.6
```

```text title="EDGE-A – show ip route (extrait)"
Gateway of last resort is 198.51.100.1 to network 0.0.0.0
B*    0.0.0.0/0 [20/0] via 198.51.100.1, 00:14:16
O        10.255.0.2/32 [110/101] via 10.254.1.3, 00:03:36, GigabitEthernet0/3
                       [110/101] via 10.254.0.2, 00:04:03, GigabitEthernet0/2
S     192.0.2.0/24 [1/0] via 10.254.1.1
```

Table: Synthèse de la vérification de la bordure
| Contrôle | EDGE-A | EDGE-B | Attendu |
|---|---|---|---|
| Sessions BGP établies | 3/3 (iBGP, ISP-A, ISP-B) | 3/3 | 3/3 |
| Route par défaut retenue | via ISP-A (198.51.100.1) | via ISP-A (198.51.100.5) | ISP-A (LP 200) |
| Adjacences OSPF | 2 FULL (Gi0/2, Gi0/3) | 2 FULL | 2 |
| HSRP groupe 1 (VIP 10.254.1.6) | Active, priorité 110 | Standby, priorité 100 | EDGE-A actif |
| Accès Internet (ping 8.8.8.8) | 5/5, 40 ms | 5/5, 41 ms | Succès |

> [!DEV] uRPF retiré des interfaces opérateurs
> La configuration initiale activait l'uRPF en mode lâche (`ip verify unicast source reachable-via any`). Les Edge
> ne recevant qu'une route par défaut, et ce mode ignorant la route par défaut, toutes les réponses venant
> d'Internet étaient rejetées (ping 8.8.8.8 à 0 %). L'option `allow-default` rendrait le contrôle sans effet ;
> l'uRPF est donc retiré et l'anti-usurpation reste assurée par l'ACL `ACL-WAN-IN`, dont l'efficacité est visible
> lors d'un traceroute : les messages ICMP émis depuis des adresses privées sont rejetés et journalisés.

```text title="EDGE-A – traceroute 8.8.8.8 : l'ACL anti-usurpation en action"
  1 198.51.100.1 [AS 64500] 7 msec 2 msec 2 msec
  2  *
%SEC-6-IPACCESSLOGDP: list ACL-WAN-IN denied icmp 192.168.42.1 -> 198.51.100.2 (0/0), 1 packet
```
