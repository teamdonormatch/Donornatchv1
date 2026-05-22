# ============================================================
# DonorMatch — Multi-stage Production Dockerfile
# ============================================================

# ---------- Stage 1: Builder ----------
FROM python:3.12-slim AS builder

WORKDIR /app

# System dependencies for psycopg2, Pillow, scikit-learn
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into a prefix directory
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --prefix=/install --no-cache-dir -r requirements.txt

# ---------- Stage 2: Runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=donormatch.settings

WORKDIR /app

# Runtime system libraries only (no compilers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libjpeg62-turbo \
    zlib1g \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Create non-root user for security
RUN groupadd -r donormatch && useradd -r -g donormatch -d /app donormatch

# Copy project source
COPY --chown=donormatch:donormatch . .

# Create required directories
RUN mkdir -p \
    /app/media/hospital_logos \
    /app/media/payment_proofs \
    /app/ml_models \
    /app/static \
    && chown -R donormatch:donormatch /app

# Collect static files
RUN python manage.py collectstatic --noinput

USER donormatch

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Entrypoint: migrate then serve
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn donormatch.wsgi:application --bind 0.0.0.0:8000 --workers 4 --timeout 120 --access-logfile - --error-logfile -"]
