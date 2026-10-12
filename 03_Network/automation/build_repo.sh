#!/bin/bash
# Build an offline APT repository (Ubuntu 20.04 "focal") for the lab servers, as an ISO volume labelled DCREPO.
# Runs inside the GNS3 VM (fast Internet access), in a throw-away ubuntu:focal container:
#   bash build_repo.sh  ->  /opt/gns3/images/QEMU/dc-lab-repo-focal.iso
# The ISO is attached to each server VM as a second disk (/dev/vdb) and used as "deb [trusted=yes] file:/mnt/dcrepo ./".
# Why: the lab's emulated forwarding chain (Leaf, Core, pfSense, IOSv, ISP) gives ~70 KB/s; datacenters commonly
# install from a controlled internal mirror anyway.
set -euo pipefail
OUT=/opt/gns3/labrepo
ISO=/opt/gns3/images/QEMU/dc-lab-repo-focal-v2.iso
PKGS="dnsmasq chrony nfs-kernel-server tgt rsync python3 openssl iperf3 keepalived curl dnsutils snmp
      libpam-google-authenticator auditd
      zabbix-agent zabbix-server-mysql zabbix-frontend-php zabbix-nginx-conf zabbix-sql-scripts
      mariadb-server nginx php7.4-fpm php7.4-mysql grafana"
PKGS=$(echo $PKGS | tr -s " 
" " ")    # single line: the list is spliced into the container command
rm -rf "$OUT"; mkdir -p "$OUT/pool"
docker pull -q ubuntu:focal >/dev/null
docker run --rm -v "$OUT":/out ubuntu:focal bash -c '
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
sed -i "s|http://archive.ubuntu.com|http://mirrors.edge.kernel.org|; s|http://security.ubuntu.com|http://mirrors.edge.kernel.org|" /etc/apt/sources.list
echo "Acquire::ForceIPv4 \"true\";" > /etc/apt/apt.conf.d/99v4
apt-get update -qq
apt-get install -y -qq wget gnupg ca-certificates dpkg-dev genisoimage >/dev/null
cd /tmp
wget -q https://repo.zabbix.com/zabbix/6.0/ubuntu/pool/main/z/zabbix-release/zabbix-release_latest_6.0+ubuntu20.04_all.deb
dpkg -i zabbix-release_latest_6.0+ubuntu20.04_all.deb >/dev/null
wget -q -O - https://apt.grafana.com/gpg.key | gpg --dearmor > /usr/share/keyrings/grafana.gpg
echo "deb [signed-by=/usr/share/keyrings/grafana.gpg] https://apt.grafana.com stable main" > /etc/apt/sources.list.d/grafana.list
apt-get update -qq
# complete dependency closure (servers start from a cloud image, so every dependency is shipped)
apt-cache depends --recurse --no-recommends --no-suggests --no-conflicts --no-breaks --no-replaces --no-enhances '"$PKGS"' \
  | grep "^\w" | sort -u > /tmp/closure.txt
echo "closure: $(wc -l < /tmp/closure.txt) packages"
cd /out/pool
# keep real packages only (virtual names like <debconf-2.0> cannot be downloaded), then one batch download
for p in $(cat /tmp/closure.txt); do apt-cache show "$p" >/dev/null 2>&1 && echo "$p"; done > /tmp/real.txt
echo "real packages: $(wc -l < /tmp/real.txt)"
apt-get download -qq $(cat /tmp/real.txt) || for p in $(cat /tmp/real.txt); do apt-get download -qq "$p" 2>/dev/null || true; done
cp /tmp/zabbix-release_latest_6.0+ubuntu20.04_all.deb /out/pool/
# apt-get download keeps the epoch URL-encoded ("_1%3a6.0.48"): apt mis-decodes it in a file: repository.
# Debian pool convention: no epoch in file names.
cd /out/pool && for f in *%3a*; do [ -e "$f" ] && mv "$f" "$(echo "$f" | sed "s/_[0-9]*%3a/_/")"; done
cd /out && dpkg-scanpackages -m pool /dev/null 2>/dev/null > Packages && gzip -9k Packages
echo "downloaded: $(ls pool | wc -l) .deb, $(du -sh pool | cut -f1)"
# build from the repository directory itself so that pool/ is kept (file arguments are merged at the ISO root)
genisoimage -quiet -V DCREPO -r -J -o /tmp/dc-lab-repo.iso /out && mv /tmp/dc-lab-repo.iso /out/dc-lab-repo.iso
'
mv "$OUT/dc-lab-repo.iso" "$ISO"
md5sum "$ISO" | cut -d" " -f1 > "$ISO.md5sum"
ls -la "$ISO"
echo BUILD-REPO-DONE
