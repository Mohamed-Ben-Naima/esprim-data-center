# Simulated operator router: FRR 8.4 + NAT to the real Internet (GNS3 NAT node on eth2)
FROM frrouting/frr:latest
LABEL org.opencontainers.image.title="dc/frr-isp" org.opencontainers.image.description="DC Casablanca lab – ISP router (FRR + MASQUERADE)"
COPY config/ /config/
COPY isp-start.sh /usr/local/bin/isp-start.sh
RUN chmod +x /usr/local/bin/isp-start.sh
ENV ISP_NAME=ISP-A
CMD ["/usr/local/bin/isp-start.sh"]
