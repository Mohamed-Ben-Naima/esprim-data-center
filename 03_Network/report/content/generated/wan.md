Table: Liens opérateurs et politique BGP
| Lien | Réseau | Côté opérateur | Côté Edge | Politique |
|---|---|---|---|---|
| ISP-A eth0 ↔ EDGE-A Gi0/0 | `198.51.100.0/30` | `198.51.100.1` (AS64500) | `198.51.100.2` (AS65100) | LP 200 |
| ISP-A eth1 ↔ EDGE-B Gi0/0 | `198.51.100.4/30` | `198.51.100.5` (AS64500) | `198.51.100.6` (AS65100) | LP 200 |
| ISP-B eth0 ↔ EDGE-A Gi0/1 | `203.0.113.4/30` | `203.0.113.5` (AS64501) | `203.0.113.6` (AS65100) | LP 100, prepend ×2 |
| ISP-B eth1 ↔ EDGE-B Gi0/1 | `203.0.113.0/30` | `203.0.113.1` (AS64501) | `203.0.113.2` (AS65100) | LP 100, prepend ×2 |
