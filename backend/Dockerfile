# ============================================================
# Ghost Negotiator — Production Dockerfile
# ============================================================
# Multi-stage is unnecessary here as we ship source directly.
# The image is built on the official Python 3.12 slim variant to
# keep the layer size small while retaining all C-extension
# build tooling (e.g. for asyncpg).
# ============================================================

FROM python:3.12-slim AS runtime

# Prevent Python from writing .pyc files and enable unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system-level dependencies required by asyncpg / psycopg
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifest first to leverage Docker layer caching
COPY pyproject.toml .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# Copy application source
COPY . .

EXPOSE 8000

# Health-check against the /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
