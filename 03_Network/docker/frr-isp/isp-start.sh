#!/bin/bash
# Configs come from 03_Network/configs/<ISP>/ (generated from the inventory) and are applied at every start.
src=/config/${ISP_NAME:-ISP-A}
cp "$src/frr.conf" /etc/frr/frr.conf
cp "$src/daemons" /etc/frr/daemons
touch /etc/frr/vtysh.conf
chown -R frr:frr /etc/frr
sysctl -w net.ipv4.ip_forward=1 >/dev/null
# customers' traffic leaves to the real Internet through eth2 (GNS3 NAT node, DHCP)
iptables -t nat -C POSTROUTING -o eth2 -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -o eth2 -j MASQUERADE
exec /usr/lib/frr/docker-start
