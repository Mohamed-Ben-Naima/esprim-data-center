# BMS / GTB electrical state simulator (report §13.3) – Python standard library only
FROM python:3.12-alpine
LABEL org.opencontainers.image.title="dc/bms-sim" org.opencontainers.image.description="DC Casablanca lab – BMS / GTB electrical state simulator (report §13.3)"
RUN apk add --no-cache tzdata
ENV TZ=Africa/Casablanca PYTHONUNBUFFERED=1 PORT=8080
COPY app.py /app/app.py
EXPOSE 8080
CMD ["python", "/app/app.py"]
