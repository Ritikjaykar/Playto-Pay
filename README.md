# Playto Payout Engine

Minimal money-moving payout service for the Playto Founding Engineer Challenge 2026.

## Stack

- Django 5 + Django REST Framework
- PostgreSQL for production and local Docker
- Celery + Redis for background payout processing
- React + Vite + Tailwind for the merchant dashboard

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

Services:

- Backend API: http://localhost:8000
- Frontend: http://localhost:5173
- Postgres: localhost:5432
- Redis: localhost:6379

Seed data is loaded automatically by the `backend` container. To run it manually:

```bash
cd backend
python manage.py migrate
python manage.py seed_demo
```

## API

Demo merchant selection is intentionally simple for the challenge: pass `X-Merchant-Id`.

```bash
curl http://localhost:8000/api/v1/summary \
  -H "X-Merchant-Id: <merchant_uuid>"
```

Create a payout:

```bash
curl -X POST http://localhost:8000/api/v1/payouts \
  -H "Content-Type: application/json" \
  -H "X-Merchant-Id: <merchant_uuid>" \
  -H "Idempotency-Key: 42f9776c-cdd4-42ce-8f29-7d0a1e815b55" \
  -d '{"amount_paise":6000,"bank_account_id":"<bank_account_uuid>"}'
```

## Tests

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py test payouts
```

The concurrency test is designed for PostgreSQL semantics. SQLite is supported only as a lightweight fallback for local smoke checks.

## Deployment Notes

Set these environment variables on Render/Railway/Fly/Koyeb:

- `DATABASE_URL`
- `REDIS_URL`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `CORS_ALLOWED_ORIGINS`

Run one web process, one Celery worker, and one Celery beat process:

```bash
gunicorn config.wsgi:application --chdir backend
celery -A config worker -l INFO --workdir backend
celery -A config beat -l INFO --workdir backend
```
