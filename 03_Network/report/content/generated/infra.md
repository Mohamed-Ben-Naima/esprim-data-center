Table: Adressage des équipements d'infrastructure (source : inventaire)
| Équipement | Espace | Plateforme | Loopback | Management OOB | Interfaces de transit |
|---|---|---|---|---|---|
| **EDGE-A** | ER | iosv | `10.255.0.1` | `10.10.0.1` (Gi0/5) | Gi0/0 `198.51.100.2/30` · Gi0/1 `203.0.113.6/30` · Gi0/2 `10.254.0.1/30` · Gi0/3 `10.254.1.2/28` |
| **EDGE-B** | ER | iosv | `10.255.0.2` | `10.10.0.2` (Gi0/5) | Gi0/0 `198.51.100.6/30` · Gi0/1 `203.0.113.2/30` · Gi0/2 `10.254.0.2/30` · Gi0/3 `10.254.1.3/28` |
| **FW-A** | MDA | pfsense | `10.255.0.11` | `10.10.0.11` (em6.10) | 901 `10.254.1.4` · 902 `10.254.2.4` · sync `10.254.3.1` |
| **FW-B** | MDA | pfsense | `10.255.0.12` | `10.10.0.12` (em6.10) | 901 `10.254.1.5` · 902 `10.254.2.5` · sync `10.254.3.2` |
| **CORE-A** | MDA | iosvl2 | `10.255.0.21` | `10.10.0.21` (Gi2/0) | 902 `10.254.2.2` · 998 `10.254.4.1` · SVI `.2` |
| **CORE-B** | MDA | iosvl2 | `10.255.0.22` | `10.10.0.22` (Gi2/0) | 902 `10.254.2.3` · 998 `10.254.4.2` · SVI `.3` |
| **LEAF-A1** | HDA-A | iosvl2 | `10.255.0.31` (réservée) | `10.10.0.31` (Gi1/2) | Trunks vers CORE-A et CORE-B |
| **LEAF-A2** | HDA-A | iosvl2 | `10.255.0.32` (réservée) | `10.10.0.32` (Gi1/2) | Trunks vers CORE-A et CORE-B |
| **LEAF-B1** | HDA-B | iosvl2 | `10.255.0.33` (réservée) | `10.10.0.33` (Gi1/3) | Trunks vers CORE-A et CORE-B |
| **LEAF-B2** | HDA-B | iosvl2 | `10.255.0.34` (réservée) | `10.10.0.34` (Gi2/0) | Trunks vers CORE-A et CORE-B |
