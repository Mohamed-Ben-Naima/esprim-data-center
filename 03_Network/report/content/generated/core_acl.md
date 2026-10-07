Table: Filtrage inter-VLAN sur les cœurs (ACL entrantes des SVI)
| Source | Services communs autorisés | Flux spécifiques autorisés | Refusé et journalisé |
|---|---|---|---|
| VLAN 20 SERVEURS | DNS/NTP, DNS TCP, syslog, Zabbix actif, traps SNMP | Serveurs -> stockage NFS/iSCSI; NFS UDP; Serveurs -> agent de sauvegarde; VRRP keepalived | MGMT / ADMIN / autres VLAN internes |
| VLAN 30 STOCKAGE | DNS/NTP, DNS TCP, syslog, Zabbix actif, traps SNMP | Stockage -> sauvegarde | MGMT / ADMIN / autres VLAN internes |
| VLAN 40 BACKUP | DNS/NTP, DNS TCP, syslog, Zabbix actif, traps SNMP | — | MGMT / ADMIN / autres VLAN internes |
| VLAN 60 MONITORING | DNS/NTP, DNS TCP, syslog, Zabbix actif, traps SNMP | Supervision -> SNMP; Supervision -> agents Zabbix; Supervision -> API BMS/DCIM; Supervision -> ICMP | MGMT / ADMIN / autres VLAN internes |
| VLAN 70 BMS-DCIM | DNS/NTP, DNS TCP, syslog, Zabbix actif, traps SNMP | DCIM -> BMS-SIM | MGMT / ADMIN / autres VLAN internes |
| VLAN 80 SECURITE-CCTV | DNS/NTP, DNS TCP, syslog, Zabbix actif, traps SNMP | — | MGMT / ADMIN / autres VLAN internes |
| VLAN 100 SERVICES-INT | DNS/NTP, DNS TCP, syslog, Zabbix actif, traps SNMP | — | MGMT / ADMIN / autres VLAN internes |
