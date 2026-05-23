# ParlaySplit

**Coordinate group parlays without spreadsheet math.**

ParlaySplit is a social coordination platform for sportsbook parlays. It does **not** accept wagers, hold money, process gambling transactions, guarantee payouts, or redistribute winnings. It is for coordination, tracking, and payout **estimation** only.

## Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.13, Django 5, Django Templates |
| Interactivity | HTMX, Alpine.js (minimal) |
| Database | PostgreSQL (SQLite for local dev) |
| CSS | TailwindCSS |
| OCR | Tesseract, Pillow, OpenCV |
| Tasks | Celery + Redis |
| Deploy | Docker, Gunicorn, Nginx, DigitalOcean |

## Features (MVP)

- Create parlays manually or via screenshot OCR (FanDuel / DraftKings optimized)
- Public UUID share links with live HTMX participant updates
- Nickname + contribution join flow (no login)
- Ownership % and estimated payout splits
- OpenGraph meta, QR codes, copy link
- Sitewide legal disclaimers
- `sitemap.xml`, `robots.txt`, Plausible hook

## Quick start (local)

### Prerequisites

- Python 3.13+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed and on `PATH`
- Node.js 20+ (for Tailwind build)
- Redis (optional; OCR falls back to sync without Celery)

### Setup

```bash
cp .env.example .env
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
npm install
npm run build:css
python manage.py migrate
python manage.py runserver
```

Visit http://127.0.0.1:8000/

### Celery worker (optional)

```bash
celery -A config worker -l info
```

## Docker (production-style)

```bash
cp .env.example .env
# Edit SECRET_KEY, ALLOWED_HOSTS, SITE_URL
docker compose up --build
```

- App: http://localhost (Nginx → Gunicorn)
- Admin: http://localhost/admin/ (create superuser: `docker compose exec web python manage.py createsuperuser`)

## Environment variables

See `.env.example`. Key settings:

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret |
| `DATABASE_URL` | PostgreSQL URL (defaults to SQLite) |
| `CELERY_BROKER_URL` | Redis URL for OCR tasks |
| `SITE_URL` | Canonical URL for share links & OG |
| `USE_S3` | Enable S3/DO Spaces for media |
| `PLAUSIBLE_DOMAIN` | Analytics domain |

## Project layout

```
config/           # Django settings, Celery, URLs
parlays/          # Models, views, OCR services, templates
templates/        # Base layout, robots.txt
static/           # Tailwind source + built CSS
nginx/            # Reverse proxy config
docker/           # Entrypoint scripts
```

## Models

- **Parlay** — UUID public ID, odds, wager, payout, sportsbook, status
- **ParlayLeg** — Individual bet legs
- **Participant** — Nickname + contribution; unique per parlay
- **OCRUpload** — Async/sync slip processing pipeline

## Legal

Disclaimers are rendered on every page via context processor. This product is informational coordination only; users place wagers independently with their sportsbook.

## DigitalOcean deployment notes

1. Provision droplet, install Docker.
2. Point domain A record to droplet.
3. Set `SITE_URL`, `ALLOWED_HOSTS`, production `SECRET_KEY`.
4. Use managed PostgreSQL or container `db` service.
5. Configure Spaces (`USE_S3=True`) for uploaded slip images.
6. Terminate TLS at Nginx or DO Load Balancer; set `DEBUG=False`.

## License

Proprietary MVP — all rights reserved unless otherwise specified.
