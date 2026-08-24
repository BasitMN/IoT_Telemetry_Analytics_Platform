# Multi-stage Dockerfile för IoT Telemetry API


# Stage 1: Build & Dependencies
FROM python:3.11-slim AS builder
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY api/requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime (Minimal image & non-root user)
FROM python:3.11-slim AS runtime
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /home/appuser/.local

# Kopiera API-koden (app.py, requirements.txt) till /app
COPY api/ ./
# Kopiera in kontraktet 
COPY openapi.yaml /openapi.yaml

# Konfigurera miljö och icke-root användare
ENV PATH=/home/appuser/.local/bin:$PATH
RUN useradd -u 1000 appuser && chown -R appuser:appuser /app
USER 1000

EXPOSE 5000

CMD ["python", "app.py"]