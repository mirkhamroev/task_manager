# ─────────────────────────────────────────────────────────────
#  Task Manager — Multi-stage Docker Image
#  Services: Django 6.x  ·  Celery Worker  ·  Celery Beat
# ─────────────────────────────────────────────────────────────

# ── Stage 1: Build dependencies ──────────────────────────────
FROM python:3.13-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install \
        -r requirements.txt \
        gunicorn psycopg2-binary

# ── Stage 2: Production image ────────────────────────────────
FROM python:3.13-slim

# Runtime dependency for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Create a non-root user
RUN groupadd -r django && useradd -r -g django -d /app -s /sbin/nologin django

WORKDIR /app

# Copy project files
COPY . .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Create static files directory
RUN mkdir -p /app/staticfiles && chown -R django:django /app

# Environment defaults
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=task_manager.settings

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]

# Default command: run Gunicorn (overridden in docker-compose for celery)
CMD ["gunicorn", "task_manager.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
