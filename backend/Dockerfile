FROM python:3.13-alpine
WORKDIR /app
COPY backend/*.py /app/backend/
COPY dist /app/dist
COPY prometheus-ca.crt /usr/local/share/ca-certificates/prometheus-ca.crt
RUN apk add --no-cache ca-certificates && update-ca-certificates
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8766 DATA_MODE=simulation
USER 65534:65534
EXPOSE 8766
CMD ["python", "backend/server.py"]