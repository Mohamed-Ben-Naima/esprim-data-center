#!/bin/sh
# dc/syslog 1.1 – rights on the log volume, retention, TLS certificate, then crond (logrotate), viewer, rsyslogd.
D=/var/log/remote
N=${LOG_RETENTION_DAYS:-30}
mkdir -p $D /var/lib/viewer
chown root:logread $D && chmod 0750 $D
find $D -type f -exec chown root:logread {} + -exec chmod 0640 {} +
sed -i "s/^\( *rotate\) .*/\1 $N/; s/^\( *maxage\) .*/\1 $N/" /etc/logrotate.d/remote
if [ ! -s /var/lib/viewer/key.pem ]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 825 -subj "/CN=${VIEWER_CN:-syslog}" \
    -addext "subjectAltName=IP:${VIEWER_IP:-127.0.0.1}" \
    -keyout /var/lib/viewer/key.pem -out /var/lib/viewer/cert.pem 2>/dev/null
  chmod 0600 /var/lib/viewer/key.pem
fi
crond -b -L /dev/null
( while true; do python3 /opt/viewer/viewer.py; sleep 3; done ) &
exec rsyslogd -n -f /etc/rsyslog.conf
