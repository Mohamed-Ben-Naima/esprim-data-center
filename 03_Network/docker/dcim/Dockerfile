# DCIM / Digital Twin – 96-rack model (report §13.1) – Python standard library only
FROM python:3.12-alpine
LABEL org.opencontainers.image.title="dc/dcim" org.opencontainers.image.description="DC Casablanca lab – DCIM / Digital Twin – 96-rack model (report §13.1)"
RUN apk add --no-cache tzdata
ENV TZ=Africa/Casablanca PYTHONUNBUFFERED=1 PORT=8080
COPY app.py /app/app.py
EXPOSE 8080
CMD ["python", "/app/app.py"]
