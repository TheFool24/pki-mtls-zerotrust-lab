# ── Stage 1: Build dependencies ──
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Copy and install dependencies into a virtual env we'll copy to stage 2
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime image ──
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Create non-root user
RUN groupadd --system --gid 1000 thesis && \
    useradd --system --uid 1000 --gid thesis --home /app --shell /bin/false thesis

# Copy virtual env from builder
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Copy application code
COPY --chown=thesis:thesis app/ ./app/

# Data directory for SQLite (will be a mounted volume)
RUN mkdir -p /app/data && chown thesis:thesis /app/data

USER thesis

EXPOSE 8000

# Healthcheck — hits internal endpoint without mTLS
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health', timeout=3)" || exit 1

# NOTE: original plan had `--log-config /dev/null` to silence uvicorn logging,
# but uvicorn tries to parse it as an INI logging config and crashes on start.
# Dropped it; structlog handles app/audit logs, uvicorn keeps its defaults.
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "172.28.0.20"]
