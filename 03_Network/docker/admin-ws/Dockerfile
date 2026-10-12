# Administration bastion webterm (ADMIN-WS, VLAN 90): the one workstation from which every equipment is administered.
# Browser for the web interfaces, SSH for the command line; every SSH session is announced to the log collector.
# ssh_config and portal.html are generated from inventory/dc_casa.yaml and added to the build context by build_images.py.
FROM gns3/webterm:latest
LABEL org.opencontainers.image.title="dc/admin-ws" org.opencontainers.image.description="DC Casablanca lab – administration webterm (browser + SSH)"
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends openssh-client snmp dnsutils netcat-openbsd bsdutils tzdata \
 && ln -sf /usr/share/zoneinfo/Africa/Casablanca /etc/localtime && echo Africa/Casablanca > /etc/timezone \
 && rm -rf /var/lib/apt/lists/*
ENV TZ=Africa/Casablanca
COPY ssh_config /etc/ssh/ssh_config.d/dc-casa.conf
COPY portal.html /usr/share/dc-portal/index.html
COPY policies.json /usr/lib/firefox-esr/distribution/policies.json
COPY dc-ssh /usr/local/bin/ssh
COPY dc-hosts /usr/local/bin/dc-hosts
RUN chmod 0755 /usr/local/bin/ssh /usr/local/bin/dc-hosts \
 && printf '\n# DC Casablanca: list the equipment when a terminal opens\n[ -t 1 ] && dc-hosts\n' >> /etc/bash.bashrc
