Table: Matrice d'accès d'administration (générée par `automation/access_matrix.py` le 10/11/2026)
| Équipement | Accès | Adresse | Depuis ADMIN-WS (VLAN 90) | Depuis SRV-INF-01 (VLAN 100) | Depuis SRV-WEB-01 (DMZ) | Session SSH | Verdict |
|---|---|---|---|---|---|---|---|
| EDGE-A | SSH | `netadmin@10.10.0.1` | – | – | – | – | arrêté |
| EDGE-B | SSH | `netadmin@10.10.0.2` | – | – | – | – | arrêté |
| FW-A | SSH | `admin@10.90.0.2` | joignable | source arrêtée | source arrêtée | non testée | Conforme |
| FW-B | SSH | `admin@10.90.0.3` | – | – | – | – | arrêté |
| CORE-A | SSH | `netadmin@10.10.0.21` | joignable | source arrêtée | source arrêtée | non testée | Conforme |
| CORE-B | SSH | `netadmin@10.10.0.22` | – | – | – | – | arrêté |
| LEAF-A1 | SSH | `netadmin@10.10.0.31` | – | – | – | – | arrêté |
| LEAF-A2 | SSH | `netadmin@10.10.0.32` | – | – | – | – | arrêté |
| LEAF-B1 | SSH | `netadmin@10.10.0.33` | joignable | source arrêtée | source arrêtée | non testée | Conforme |
| LEAF-B2 | SSH | `netadmin@10.10.0.34` | joignable | source arrêtée | source arrêtée | non testée | Conforme |
| SRV-CMP-01 | SSH | `sysadmin@10.20.0.11` | – | – | – | – | arrêté |
| SRV-CMP-02 | SSH | `sysadmin@10.20.0.12` | – | – | – | – | arrêté |
| SRV-CMP-03 | SSH | `sysadmin@10.20.0.13` | – | – | – | – | arrêté |
| SRV-STO-01 | SSH | `sysadmin@10.30.0.11` | – | – | – | – | arrêté |
| SRV-BCK-01 | SSH | `truenas_admin@10.40.0.11` | joignable | source arrêtée | source arrêtée | non testée | Conforme |
| SRV-INF-01 | SSH | `sysadmin@10.100.0.11` | – | – | – | – | arrêté |
| SRV-MON-01 | SSH | `sysadmin@10.60.0.11` | – | – | – | – | arrêté |
| SRV-BASTION | SSH | `sysadmin@10.90.0.11` | – | – | – | – | arrêté |
| FW-A | Web – pfSense - cluster | `https://10.90.0.1/` | joignable | source arrêtée | source arrêtée | – | Conforme |
| FW-A | Web – pfSense - FW-A | `https://10.90.0.2/` | joignable | source arrêtée | source arrêtée | – | Conforme |
| FW-B | Web – pfSense - FW-B | `https://10.90.0.3/` | – | – | – | – | arrêté |
| SRV-MON-01 | Web – Zabbix | `http://10.60.0.11/` | – | – | – | – | arrêté |
| SRV-MON-01 | Web – Grafana | `http://10.60.0.11:3000/` | – | – | – | – | arrêté |
| BMS-SIM | Web – BMS-SIM | `http://10.70.0.12:8080/` | – | – | – | – | arrêté |
| SRV-BCK-01 | Web – TrueNAS | `https://10.40.0.11/` | joignable | source arrêtée | source arrêtée | – | Conforme |
| SRV-DCIM-01 | Web – DCIM | `http://10.70.0.11:8080/` | – | – | – | – | arrêté |
| SRV-WEB-01 | Web – Web site (DMZ) | `https://10.50.0.11/` | – | – | – | – | arrêté |
