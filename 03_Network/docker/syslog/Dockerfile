# Central syslog collector (ISO/IEC 27001 A.8.15) – one file per source host, daily rotation, read-only web viewer
FROM alpine:3.20
LABEL org.opencontainers.image.title="dc/syslog" org.opencontainers.image.version="1.1" \
      org.opencontainers.image.description="DC Casablanca lab – rsyslog collector + logrotate + read-only HTTPS viewer"
RUN apk add --no-cache rsyslog tzdata logrotate openssl python3 \
 && addgroup -S logread && adduser -S -D -H -G logread -s /sbin/nologin viewer \
 && mkdir -p /var/log/remote /var/lib/viewer /opt/viewer \
 && chown root:logread /var/log/remote && chmod 0750 /var/log/remote && chmod 0700 /var/lib/viewer
ENV TZ=Africa/Casablanca LOG_RETENTION_DAYS=30 VIEWER_PORT=443
COPY rsyslog.conf /etc/rsyslog.conf
COPY logrotate.conf /etc/logrotate.d/remote
COPY viewer.py selftest.py entrypoint.sh /opt/viewer/
RUN chmod 0755 /opt/viewer/entrypoint.sh && chmod 0644 /opt/viewer/viewer.py /opt/viewer/selftest.py /etc/logrotate.d/remote
EXPOSE 514/udp 514/tcp 443/tcp
CMD ["/opt/viewer/entrypoint.sh"]
