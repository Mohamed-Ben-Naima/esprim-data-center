Table: Serveurs et conteneurs (source : inventaire)
| Nœud | Type | VLAN | Adresse | Raccordement | Liaison | Rôles |
|---|---|---|---|---|---|---|
| **SRV-CMP-01** | VM | 20 | `10.20.0.11` | LEAF-A1 Gi0/2 + LEAF-A2 Gi0/2 | bond0 actif/passif | app-8443, keepalived-master, iperf3 |
| **SRV-CMP-02** | VM | 20 | `10.20.0.12` | LEAF-A1 Gi0/3 + LEAF-A2 Gi0/3 | bond0 actif/passif | app-8443, keepalived-backup, iperf3 |
| **SRV-CMP-03** | VM | 20 | `10.20.0.13` | LEAF-A1 Gi1/0 + LEAF-A2 Gi1/0 | bond0 actif/passif | app-8443, iperf3 |
| **SRV-STO-01** | VM | 30 | `10.30.0.11` | LEAF-A1 Gi1/1 + LEAF-A2 Gi1/1 | bond0 actif/passif | nfs, iscsi |
| **SRV-BCK-01** | VM | 40 | `10.40.0.11` | LEAF-B1 Gi0/2 + LEAF-B2 Gi0/2 | bond0 actif/passif | nas, backup-pull, snapshots |
| **SRV-INF-01** | VM | 100 | `10.100.0.11` | LEAF-B1 Gi0/3 + LEAF-B2 Gi0/3 | bond0 actif/passif | dns, ntp, dhcp |
| **SRV-MON-01** | VM | 60 | `10.60.0.11` | LEAF-B1 Gi1/0 + LEAF-B2 Gi1/0 | bond0 actif/passif | zabbix, grafana |
| **SRV-DCIM-01** | Conteneur | 70 | `10.70.0.11` | LEAF-B1 Gi1/1 + LEAF-B2 Gi1/1 | bond0 actif/passif | dcim |
| **SYSLOG** | Conteneur | 60 | `10.60.0.12` | LEAF-B1 Gi1/2 | simple | syslog |
| **BMS-SIM** | Conteneur | 70 | `10.70.0.12` | LEAF-B2 Gi1/2 | simple | bms-sim |
| **CCTV-SIM** | Conteneur | 80 | `10.80.0.11` | LEAF-B2 Gi1/3 | simple | cctv-sim |
| **SRV-WEB-01** | Conteneur | 50 | `10.50.0.11` | SW-DMZ Ethernet2 | simple | web |
| **SRV-BASTION** | VM | 90 | `10.90.0.11` | SW-MGMT Ethernet10 | simple | bastion, mfa |
| **ADMIN-WS** | Conteneur | 90 | `10.90.0.12` | SW-MGMT Ethernet11 | simple | admin-desktop, admin-bastion |
