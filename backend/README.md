# ARQAU Backend

FastAPI backend for the ARQAU earned wage access and financial intelligence platform.

## Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

## Environment

Copy `.env` and set:

- `OPENAI_API_KEY` — your OpenAI key
- `OPENAI_MODEL` — default `gpt-4o-mini`
- `SECRET_KEY` — change in production
- `DATABASE_URL` — default SQLite

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

## Endpoints

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`
- `GET/PUT /auth/onboarding`
- `GET /finance/summary`
- `GET/POST /transactions`
- `GET/POST /budgets`
- `GET/POST /goals`
- `GET/PUT /ewa/earned`
- `GET /ewa/available`
- `POST /ewa/request`
- `GET /ewa/requests`
- `POST /ai/analyze-withdrawal`
- `POST /ai/chat`
- `GET /health`

## Database migrations

Run migrations from this directory with the module form so they work even when the Alembic console script is not on `PATH`:

```bash
python -m alembic upgrade head
```

The initial revision has two safe paths:

- Empty SQLite or PostgreSQL database: create the seven existing application tables and record revision `20260911_0001`.
- Complete legacy SQLite database: add only the Alembic version record. It does not create, drop, rename, or rewrite application tables or data.

A database containing only some application tables is rejected instead of being treated as a baseline. Do not run `alembic downgrade base` against the legacy SQLite database; restore a backup for rollback. Disposable databases can be deleted after validation.
