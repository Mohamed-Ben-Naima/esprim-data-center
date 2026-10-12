Table: Matrice d'accès d'administration (générée par `automation/access_matrix.py` le 12/10/2026)
| Équipement | Accès | Adresse | Depuis ADMIN-WS (VLAN 90) | Depuis SRV-INF-01 (VLAN 100) | Depuis SRV-WEB-01 (DMZ) | Session SSH | Verdict |
|---|---|---|---|---|---|---|---|
| EDGE-A | SSH | `netadmin@10.10.0.1` | joignable | refusé | refusé | EDGE-A uptime is 5 hours, 6 minutes | Conforme |
| EDGE-B | SSH | `netadmin@10.10.0.2` | joignable | refusé | refusé | EDGE-B uptime is 5 hours, 8 minutes | Conforme |
| FW-A | SSH | `admin@10.90.0.2` | joignable | refusé | refusé | fw-a.dc.casa.lab | Conforme |
| FW-B | SSH | `admin@10.90.0.3` | joignable | refusé | refusé | fw-b.dc.casa.lab | Conforme |
| CORE-A | SSH | `netadmin@10.10.0.21` | joignable | refusé | refusé | CORE-A uptime is 3 hours, 42 minutes | Conforme |
| CORE-B | SSH | `netadmin@10.10.0.22` | joignable | refusé | refusé | CORE-B uptime is 3 hours, 50 minutes | Conforme |
| LEAF-A1 | SSH | `netadmin@10.10.0.31` | – | – | – | – | arrêté |
| LEAF-A2 | SSH | `netadmin@10.10.0.32` | – | – | – | – | arrêté |
| LEAF-B1 | SSH | `netadmin@10.10.0.33` | joignable | refusé | refusé | LEAF-B1 uptime is 3 hours, 53 minutes | Conforme |
| LEAF-B2 | SSH | `netadmin@10.10.0.34` | joignable | refusé | refusé | LEAF-B2 uptime is 3 hours, 52 minutes | Conforme |
| SRV-CMP-01 | SSH | `sysadmin@10.20.0.11` | – | – | – | – | arrêté |
| SRV-CMP-02 | SSH | `sysadmin@10.20.0.12` | – | – | – | – | arrêté |
| SRV-CMP-03 | SSH | `sysadmin@10.20.0.13` | – | – | – | – | arrêté |
| SRV-STO-01 | SSH | `sysadmin@10.30.0.11` | – | – | – | – | arrêté |
| SRV-BCK-01 | SSH | `sysadmin@10.40.0.11` | – | – | – | – | arrêté |
| SRV-INF-01 | SSH | `sysadmin@10.100.0.11` | joignable | lui-même | refusé | srv-inf-01 | Conforme |
| SRV-MON-01 | SSH | `sysadmin@10.60.0.11` | – | – | – | – | arrêté |
| SRV-BASTION | SSH | `sysadmin@10.90.0.11` | joignable | refusé | refusé | srv-bastion | Conforme |
| FW-A | Web – pfSense - cluster | `https://10.90.0.1/` | joignable | refusé | refusé | – | Conforme |
| FW-A | Web – pfSense - FW-A | `https://10.90.0.2/` | joignable | refusé | refusé | – | Conforme |
| FW-B | Web – pfSense - FW-B | `https://10.90.0.3/` | joignable | refusé | refusé | – | Conforme |
| SRV-MON-01 | Web – Zabbix | `http://10.60.0.11/` | – | – | – | – | arrêté |
| SRV-MON-01 | Web – Grafana | `http://10.60.0.11:3000/` | – | – | – | – | arrêté |
| BMS-SIM | Web – BMS-SIM | `http://10.70.0.12:8080/` | joignable | refusé | refusé | – | Conforme |
| SRV-DCIM-01 | Web – DCIM | `http://10.70.0.11:8080/` | joignable | refusé | refusé | – | Conforme |
| SRV-WEB-01 | Web – Web site (DMZ) | `https://10.50.0.11/` | joignable | joignable | lui-même | – | Conforme |
