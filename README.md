# legal-chatbot-api

Backend API for the Smart Legal Advisory System (FYDP).

## Phase 1 — Foundation Setup (this state)

What's included:
- FastAPI app factory (`app/main.py`) with a `/health` endpoint
- Typed settings via `pydantic-settings` (`config/settings.py`), reading from `.env`
- Structured logging via `structlog` (`config/logging.py`)
- Async SQLAlchemy engine + session dependency (`db/session.py`, `db/base.py`)
- Alembic migrations wired to the async engine (`db/migrations/`)
- Docker setup: Postgres + Redis + API (`docker/`)

Not yet included (later phases): auth, conversations, documents, chat — see
project roadmap. `app/dependencies.py` and `db/base.py` are intentionally
built to be extended without modification as those phases land.

## Getting started

1. Copy environment file:
   ```bash
   cp .env.example .env
   # edit .env, especially JWT_SECRET_KEY and DATABASE_URL if not using Docker
   ```

2. Install dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

3. Start Postgres + Redis (via Docker):
   ```bash
   docker compose -f docker/docker-compose.yml up postgres redis -d
   ```

4. Run the first migration (once you have models — Phase 2 onward):
   ```bash
   alembic revision --autogenerate -m "initial tables"
   alembic upgrade head
   ```

5. Run the API:
   ```bash
   bash scripts/run_dev.sh
   ```

6. Check it's alive:
   ```bash
   curl http://localhost:8000/health
   # {"status": "ok", "env": "development"}
   ```

## Running everything in Docker

```bash
docker compose -f docker/docker-compose.yml up --build
```

## Project structure

See the full target structure in the project roadmap doc. This phase
populates `config/`, `db/`, `app/main.py`, `app/dependencies.py`, and `docker/`.
Feature folders (`app/auth/`, `app/users/`, `app/conversations/`,
`app/documents/`, `app/chat/`) are added in Phases 2–5.
