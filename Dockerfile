# syntax=docker/dockerfile:1

FROM node:22-alpine AS tailwind
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci 2>/dev/null || npm install
COPY tailwind.config.js ./
COPY static/src/input.css ./static/src/input.css
COPY templates ./templates
COPY parlays/templates ./parlays/templates
RUN npm run build:css

FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .
COPY --from=tailwind /app/static/css/output.css ./static/css/output.css

RUN python manage.py collectstatic --noinput 2>/dev/null || true

FROM base AS web
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]

FROM base AS celery
CMD ["celery", "-A", "config", "worker", "-l", "info", "--concurrency=2"]
