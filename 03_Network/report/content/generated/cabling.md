Table: Plan de câblage étiqueté selon ANSI/TIA-606-C
| Lien (espace-équipement:port) | Rôle |
|---|---|
| `ER-EDGE-A:Gi0/0 -> ER-ISP-A:eth0` | WAN eBGP ISP-A (primaire) |
| `ER-EDGE-A:Gi0/1 -> ER-ISP-B:eth0` | WAN eBGP ISP-B (secours) |
| `ER-EDGE-A:Gi0/2 -> ER-EDGE-B:Gi0/2` | ISL iBGP/OSPF |
| `ER-EDGE-A:Gi0/3 -> ER-SW-OUT:Ethernet0` | Transit externe VLAN 901 |
| `ER-EDGE-A:Gi0/5 -> MDA-SW-MGMT:Ethernet0` | OOB VLAN 10 |
| `ER-EDGE-B:Gi0/0 -> ER-ISP-A:eth1` | WAN eBGP ISP-A (primaire) |
| `ER-EDGE-B:Gi0/1 -> ER-ISP-B:eth1` | WAN eBGP ISP-B (secours) |
| `ER-EDGE-B:Gi0/3 -> ER-SW-OUT:Ethernet1` | Transit externe VLAN 901 |
| `ER-EDGE-B:Gi0/5 -> MDA-SW-MGMT:Ethernet1` | OOB VLAN 10 |
| `MDA-FW-A:em0 -> ER-SW-OUT:Ethernet2` | WAN – transit externe VLAN 901 |
| `MDA-FW-A:em2 -> MDA-FW-B:em2` | SYNC – pfsync / XMLRPC |
| `MDA-FW-A:em3 -> MDA-CORE-A:Gi0/0` | LAN – lagg0 membre primaire (VLAN 902) |
| `MDA-FW-A:em4 -> MDA-CORE-B:Gi0/0` | LAN – lagg0 membre secours (VLAN 902) |
| `MDA-FW-A:em5 -> MDA-SW-DMZ:Ethernet0` | DMZ VLAN 50 |
| `MDA-FW-A:em6 -> MDA-SW-MGMT:Ethernet2` | Trunk 802.1Q VLAN 10 (MGMT) + 90 (ADMIN) |
| `MDA-FW-B:em0 -> ER-SW-OUT:Ethernet3` | WAN – transit externe VLAN 901 |
| `MDA-FW-B:em3 -> MDA-CORE-A:Gi0/1` | LAN – lagg0 membre primaire (VLAN 902) |
| `MDA-FW-B:em4 -> MDA-CORE-B:Gi0/1` | LAN – lagg0 membre secours (VLAN 902) |
| `MDA-FW-B:em5 -> MDA-SW-DMZ:Ethernet1` | DMZ VLAN 50 |
| `MDA-FW-B:em6 -> MDA-SW-MGMT:Ethernet3` | Trunk 802.1Q VLAN 10 (MGMT) + 90 (ADMIN) |
| `MDA-CORE-A:Gi0/2 -> MDA-CORE-B:Gi0/2` | ISL Po1 LACP #1 |
| `MDA-CORE-A:Gi0/3 -> MDA-CORE-B:Gi0/3` | ISL Po1 LACP #2 |
| `MDA-CORE-A:Gi1/0 -> HDA-A-LEAF-A1:Gi0/0` | Uplink Hall A |
| `MDA-CORE-A:Gi1/1 -> HDA-A-LEAF-A2:Gi0/0` | Uplink Hall A |
| `MDA-CORE-A:Gi1/2 -> HDA-B-LEAF-B1:Gi0/0` | Uplink Hall B |
| `MDA-CORE-A:Gi1/3 -> HDA-B-LEAF-B2:Gi0/0` | Uplink Hall B |
| `MDA-CORE-A:Gi2/0 -> MDA-SW-MGMT:Ethernet4` | OOB VLAN 10 |
| `MDA-CORE-B:Gi1/0 -> HDA-A-LEAF-A1:Gi0/1` | Uplink Hall A |
| `MDA-CORE-B:Gi1/1 -> HDA-A-LEAF-A2:Gi0/1` | Uplink Hall A |
| `MDA-CORE-B:Gi1/2 -> HDA-B-LEAF-B1:Gi0/1` | Uplink Hall B |
| `MDA-CORE-B:Gi1/3 -> HDA-B-LEAF-B2:Gi0/1` | Uplink Hall B |
| `MDA-CORE-B:Gi2/0 -> MDA-SW-MGMT:Ethernet5` | OOB VLAN 10 |
| `HDA-A-LEAF-A1:Gi0/2 -> EDA-A-SRV-CMP-01:eth0` | Serveur NIC0 |
| `HDA-A-LEAF-A1:Gi0/3 -> EDA-A-SRV-CMP-02:eth0` | Serveur NIC0 |
| `HDA-A-LEAF-A1:Gi1/0 -> EDA-A-SRV-CMP-03:eth0` | Serveur NIC0 |
| `HDA-A-LEAF-A1:Gi1/1 -> EDA-A-SRV-STO-01:eth0` | Serveur NIC0 |
| `HDA-A-LEAF-A1:Gi1/2 -> MDA-SW-MGMT:Ethernet6` | OOB VLAN 10 |
| `HDA-A-LEAF-A2:Gi0/2 -> EDA-A-SRV-CMP-01:eth1` | Serveur NIC1 |
| `HDA-A-LEAF-A2:Gi0/3 -> EDA-A-SRV-CMP-02:eth1` | Serveur NIC1 |
| `HDA-A-LEAF-A2:Gi1/0 -> EDA-A-SRV-CMP-03:eth1` | Serveur NIC1 |
| `HDA-A-LEAF-A2:Gi1/1 -> EDA-A-SRV-STO-01:eth1` | Serveur NIC1 |
| `HDA-A-LEAF-A2:Gi1/2 -> MDA-SW-MGMT:Ethernet7` | OOB VLAN 10 |
| `HDA-B-LEAF-B1:Gi0/2 -> EDA-B-SRV-BCK-01:eth0` | Serveur NIC0 |
| `HDA-B-LEAF-B1:Gi0/3 -> EDA-B-SRV-INF-01:eth0` | Serveur NIC0 |
| `HDA-B-LEAF-B1:Gi1/0 -> EDA-B-SRV-MON-01:eth0` | Serveur NIC0 |
| `HDA-B-LEAF-B1:Gi1/1 -> EDA-B-SRV-DCIM-01:eth0` | Serveur NIC0 |
| `HDA-B-LEAF-B1:Gi1/2 -> EDA-B-SYSLOG:eth0` | Service syslog |
| `HDA-B-LEAF-B1:Gi1/3 -> MDA-SW-MGMT:Ethernet8` | OOB VLAN 10 |
| `HDA-B-LEAF-B2:Gi0/2 -> EDA-B-SRV-BCK-01:eth1` | Serveur NIC1 |
| `HDA-B-LEAF-B2:Gi0/3 -> EDA-B-SRV-INF-01:eth1` | Serveur NIC1 |
| `HDA-B-LEAF-B2:Gi1/0 -> EDA-B-SRV-MON-01:eth1` | Serveur NIC1 |
| `HDA-B-LEAF-B2:Gi1/1 -> EDA-B-SRV-DCIM-01:eth1` | Serveur NIC1 |
| `HDA-B-LEAF-B2:Gi1/2 -> EDA-B-BMS-SIM:eth0` | Simulateur GTB |
| `HDA-B-LEAF-B2:Gi1/3 -> EDA-B-CCTV-SIM:eth0` | Simulateur CCTV |
| `HDA-B-LEAF-B2:Gi2/0 -> MDA-SW-MGMT:Ethernet9` | OOB VLAN 10 |
| `MDA-SW-DMZ:Ethernet2 -> DMZ-SRV-WEB-01:eth0` | accès VLAN 50 |
| `MDA-SW-MGMT:Ethernet10 -> MDA-SRV-BASTION:eth0` | accès VLAN 90 |
| `MDA-SW-MGMT:Ethernet11 -> MDA-ADMIN-WS:eth0` | accès VLAN 90 |
