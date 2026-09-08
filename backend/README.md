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
