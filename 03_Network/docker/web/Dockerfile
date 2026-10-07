# DMZ web server SRV-WEB-01 – HTTP + HTTPS (self-signed, lab) behind pfSense DNAT 192.0.2.80
FROM nginx:alpine
LABEL org.opencontainers.image.title="dc/web" org.opencontainers.image.description="DC Casablanca lab – public web site (DMZ)"
RUN apk add --no-cache openssl tzdata \
 && mkdir -p /etc/nginx/tls \
 && openssl req -x509 -nodes -newkey rsa:2048 -days 825 -subj "/C=MA/L=Casablanca/O=DC Casablanca Lab/CN=www.dc.casa.lab" \
      -addext "subjectAltName=DNS:www.dc.casa.lab,IP:192.0.2.80,IP:10.50.0.11" \
      -keyout /etc/nginx/tls/site.key -out /etc/nginx/tls/site.crt
ENV TZ=Africa/Casablanca
COPY default.conf /etc/nginx/conf.d/default.conf
COPY html/ /usr/share/nginx/html/
