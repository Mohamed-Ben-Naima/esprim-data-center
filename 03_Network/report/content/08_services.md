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
