# CCTV & access-control event generator (report §9.2) – Python standard library only
FROM python:3.12-alpine
LABEL org.opencontainers.image.title="dc/cctv-sim" org.opencontainers.image.description="DC Casablanca lab – CCTV & access-control event generator (report §9.2)"
RUN apk add --no-cache tzdata
ENV TZ=Africa/Casablanca PYTHONUNBUFFERED=1 PORT=8080
COPY app.py /app/app.py
EXPOSE 8080
CMD ["python", "/app/app.py"]
