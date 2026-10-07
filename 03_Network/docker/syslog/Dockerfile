# Central syslog collector (ISO/IEC 27001 A.8.15) – one file per source host
FROM alpine:3.20
LABEL org.opencontainers.image.title="dc/syslog" org.opencontainers.image.description="DC Casablanca lab – rsyslog collector"
RUN apk add --no-cache rsyslog tzdata && mkdir -p /var/log/remote
ENV TZ=Africa/Casablanca
COPY rsyslog.conf /etc/rsyslog.conf
EXPOSE 514/udp 514/tcp
CMD ["rsyslogd", "-n", "-f", "/etc/rsyslog.conf"]
