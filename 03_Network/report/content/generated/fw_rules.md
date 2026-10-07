Table: Politique des pare-feux par interface (évaluation de haut en bas)
| Interface | Action | Proto | Source | Destination | Ports | Description | Réf. |
|---|---|---|---|---|---|---|---|
| WAN | **autoriser** | tcp | any | WEB_SERVER | WEB [80, 443] | Internet -> DMZ web (DNAT 192.0.2.80) | T18-1 |
| WAN | **bloquer** | any | any | any | — | Refus par défaut (journalisé) | T18 |
| DMZ | **autoriser** | tcp | DMZ_NET | APP_SERVERS | APP [8443] | DMZ -> applicatif interne 8443 | T18-2 |
| DMZ | **autoriser** | udp | DMZ_NET | INF_SERVER | [53, 123] | DMZ -> DNS/NTP internes | EXT-1 |
| DMZ | **bloquer** | any | DMZ_NET | 10.10.0.0/24, 10.90.0.0/24, 10.30.0.0/24, 10.40.0.0/24 | — | DMZ -> MGMT/ADMIN/STOCKAGE/BACKUP interdit | T18-9 |
| DMZ | **bloquer** | any | any | any | — | Refus par défaut (journalisé) | T18 |
| LAN | **autoriser** | tcp/udp | INTERNAL_NETS | !RFC1918 | [53, 80, 443, 123] | Interne -> Internet DNS/HTTP(S)/NTP via NAT | T18-5 |
| LAN | **autoriser** | icmp | INTERNAL_NETS | !RFC1918 | — | Interne -> Internet ICMP (diagnostic) | EXT-2 |
| LAN | **autoriser** | udp | 10.60.0.0/24 | 10.10.0.0/24 | SNMP [161] | Supervision -> équipements SNMP | T18-7 |
| LAN | **autoriser** | icmp | 10.60.0.0/24 | 10.10.0.0/24 | — | Supervision -> équipements ICMP | T18-7 |
| LAN | **autoriser** | tcp | INTERNAL_NETS | WEB_SERVER | WEB [80, 443] | Interne -> site web DMZ | EXT-3 |
| LAN | **bloquer** | any | any | any | — | Refus par défaut (journalisé) | T18 |
| MGMT | **autoriser** | udp | MGMT_NET | SYSLOG_SERVER | SYSLOG [514] | Équipements -> syslog | T18-8 |
| MGMT | **autoriser** | udp | MGMT_NET | MON_SERVER | SNMP_TRAP [162] | Équipements -> traps SNMP | T18-8 |
| MGMT | **autoriser** | udp | MGMT_NET | INF_SERVER | [53, 123] | Équipements -> DNS/NTP | EXT-4 |
| MGMT | **bloquer** | any | any | any | — | Refus par défaut (journalisé) | T18 |
| ADMIN | **autoriser** | tcp | ADMIN_NET | any_internal | ADMIN_SVC [22, 443] | Administration -> tous équipements SSH/HTTPS | T18-6 |
| ADMIN | **autoriser** | udp | ADMIN_NET | any_internal | SNMP [161] | Administration -> SNMP | T18-6 |
| ADMIN | **autoriser** | tcp | ADMIN_NET | MON_SERVER | [3000, 80] | Administration -> Zabbix/Grafana | T18-6 |
| ADMIN | **autoriser** | tcp | ADMIN_NET | 10.70.0.0/24 | [8080] | Administration -> DCIM/BMS | T18-6 |
| ADMIN | **autoriser** | icmp | ADMIN_NET | any_internal | — | Administration -> ICMP | T18-6 |
| ADMIN | **autoriser** | tcp/udp | ADMIN_NET | !RFC1918 | [53, 80, 443, 123] | Administration -> Internet (mises à jour) | EXT-5 |
| ADMIN | **bloquer** | any | any | any | — | Refus par défaut (journalisé) | T18 |
| SYNC | **autoriser** | any | SYNC_NET | SYNC_NET | — | pfsync + XMLRPC entre pairs | HA |
| SYNC | **bloquer** | any | any | any | — | Refus par défaut (journalisé) | T18 |
