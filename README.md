# Smart Legal Advisory System: Backend

FastAPI backend for the Smart Legal Advisory System (FYDP). It handles accounts and login, legal
consultations (chat), document uploads, billing and usage limits, the admin area, and legal sources
(RAG). The web app in `legal-advisory-system-webapp` talks to this API.

**Written for:** anyone setting this up for the first time on their own computer.

## Contents

1. [Tech stack](#tech-stack)
2. [Project structure](#project-structure)
3. [Requirements](#requirements)
4. [Quick start (SQLite, no Docker)](#quick-start-sqlite-no-docker)
5. [Environment variables](#environment-variables)
6. [Database and migrations](#database-and-migrations)
7. [Running the API](#running-the-api)
8. [Admin accounts and demo data](#admin-accounts-and-demo-data)
9. [Running the tests](#running-the-tests)
10. [Docker](#docker)
11. [API overview](#api-overview)
12. [Troubleshooting](#troubleshooting)
13. [Current limits](#current-limits)

## Tech stack

| Part | What it does |
|---|---|
| FastAPI | HTTP API and routing |
| SQLAlchemy 2 (async) + Alembic | Database access and schema migrations |
| SQLite (default) or PostgreSQL | Database |
| pydantic / pydantic-settings | Request validation and reading `.env` |
| passlib + python-jose | Password hashing and JWT login tokens |
| pypdf, python-docx | Text extraction from uploaded PDF and Word files |
| structlog | Logging |
| pytest + httpx | Automated tests |
| Docker Compose | Optional PostgreSQL, Redis and API containers |

## Project structure

```
app/                  Feature code, one folder per area
  main.py             App factory: middleware, error handler, routers, /health
  dependencies.py     Shared FastAPI dependencies (current user, admin check)
  auth/               Register, login, refresh, logout, password reset, Google sign-in
  users/              Profile and account settings
  conversations/      Consultation threads and messages
  chat/               Legal answers (placeholder pipeline for now)
  documents/          Uploads (PDF, DOCX, TXT), listing and deletion
  generated_docs/     Saved answers and generated documents
  caselaw/            Loader for case-law data files in data/case_law/
  rag/                Legal sources uploaded by admins
  billing/            Plans, payments (demo) and usage limits
  admin/              Admin overview, users, analytics, audit log
  common/             Shared helpers: errors, pagination, security headers, rate limiting, logging, email, file storage
config/               Settings (.env), constants, logging setup
db/                   Database session, declarative base, Alembic migrations (db/migrations/)
scripts/              Helper scripts: run_dev.sh, make_admin.py, seed_demo_data.py
tests/                Pytest suite (uses its own temporary database)
docker/               Dockerfile and Docker Compose files (dev and production)
data/case_law/        Put case-law export files here (.json, .jsonl, .csv)
storage/documents/    Uploaded files are saved here (kept out of git)
requirements-lock.txt Exact package versions the project was tested with
pyproject.toml        Package list and project metadata
alembic.ini           Alembic (migrations) settings
.env.example          Template for your local .env file
```

## Requirements

- **Python 3.10 or newer.** Python 3.11 is the tested version. Check with `python3 --version`.
  Python 3.9 fails with `TypeError: unsupported operand type(s) for |`.
- **pip** and **venv** (included with Python).
- **Git**.
- **Docker Desktop** (optional). Only needed for PostgreSQL or the full Docker setup.

## Quick start (SQLite, no Docker)

Run these commands inside the `legal-advisory-system-backend` folder.

```bash
# 1. Create a virtual environment and activate it
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install the exact tested packages
pip install -r requirements-lock.txt

# 3. Create your local settings file and edit it (see Environment variables below)
cp .env.example .env
#   Set JWT_SECRET_KEY to a long random string

# 4. Create the database tables (creates app.db)
alembic upgrade head

# 5. Start the API
bash scripts/run_dev.sh

# 6. Check it is running (in a second terminal)
curl http://localhost:8000/health
# {"status": "ok", "env": "development"}
```

Interactive API docs are at <http://localhost:8000/docs> while `APP_ENV=development`.

**Important:** `.env` and `app.db` are never stored in git. Every new clone needs its own `.env`
and its own database (step 3 and step 4).

## Environment variables

Settings are read from `.env` in the backend folder. `.env.example` lists every option with comments.

| Variable | Required | Purpose |
|---|---|---|
| `JWT_SECRET_KEY` | **Yes** | Secret used to sign login tokens. Use a long random value. The app will not start without it. |
| `DATABASE_URL` | **Yes** | Database address. Default for quick start: `sqlite+aiosqlite:///./app.db` |
| `APP_ENV` | No | `development` (default) shows `/docs`. Use `production` to hide it. |
| `DEBUG` | No | `true` or `false` |
| `CORS_ORIGINS` | No | Comma-separated web app addresses allowed to call the API. Default for local work: `http://localhost:3000,http://127.0.0.1:3000` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | Login token lifetime (default 30) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | Refresh token lifetime (default 7) |
| `MAX_UPLOAD_SIZE_MB` | No | Largest allowed upload (default 20) |
| `CASE_LAW_DATA_DIR` | No | Folder for case-law files (default `data/case_law`) |
| `GOOGLE_CLIENT_IDS` | No | Google sign-in client IDs. Leave empty to turn Google sign-in off. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM` | No | Real email for password reset. **Leave empty in development:** the reset code is printed in the terminal instead. |
| `PASSWORD_RESET_CODE_MINUTES` | No | Reset code lifetime (default 15) |
| `REDIS_URL` | No | Reserved for production rate limiting. Not used yet. |

For PostgreSQL, change `DATABASE_URL` to the commented example in `.env.example` and start Postgres
(see [Docker](#docker)).

## Database and migrations

Migrations live in `db/migrations/versions/`. They must be run in order, and Alembic does this for you.

| Command | What it does |
|---|---|
| `alembic upgrade head` | Brings the database up to the latest version. **Run this after every `git pull` that adds migration files.** |
| `alembic current` | Shows which version your database is on |
| `alembic history` | Lists all migrations |
| `alembic downgrade -1` | Undoes the last migration (development only) |

Do **not** use `alembic revision --autogenerate` for the existing tables. They are already written as
migrations. Only use it when you add a new model, and review the file before running it.

The current latest migration is `f1a2b3c4d5e6` (billing, RAG, structured answers).

**Deleting the local database** (for example, to start fresh) is safe in development:

```bash
rm app.db
alembic upgrade head
```

This removes all local accounts and data. Do not do it on a shared or production database.

## Running the API

| Command | When to use |
|---|---|
| `bash scripts/run_dev.sh` | Development. Reloads automatically when code changes. Port 8000. |
| `uvicorn app.main:app --port 8000` | Same as above, without the helper script |
| `docker compose -f docker/docker-compose.yml up --build` | Full Docker setup (PostgreSQL, Redis, API) |

The web app expects the API at `http://localhost:8000`. Set `NEXT_PUBLIC_API_URL` in the web app
(see its README).

## Admin accounts and demo data

Run these from the backend folder, with the virtual environment active.

| Command | What it does |
|---|---|
| `python3 scripts/make_admin.py you@example.com` | Gives admin access to an existing account. Sign up in the app first. |
| `python3 scripts/make_admin.py you@example.com --remove` | Removes admin access |
| `python3 scripts/seed_demo_data.py` | Adds demo users, questions and documents for the admin dashboard. Demo emails end in `@demo.example.com`. Password: `DemoPass123` |
| `python3 scripts/seed_demo_data.py --remove` | Deletes all demo data again |

## Running the tests

```bash
pytest -q
```

The tests use a temporary SQLite database. They never touch `app.db`. All tests should pass.
If one fails, copy the test name and the error text when you ask for help.

## Docker

Docker runs PostgreSQL and Redis for you. Install Docker Desktop first.

**Development (code is mounted, so changes reload):**

```bash
docker compose -f docker/docker-compose.yml up --build
```

The dev file sets `DATABASE_URL` to PostgreSQL itself. Migrations still need to run once:

```bash
docker compose -f docker/docker-compose.yml exec api alembic upgrade head
```

**Production (no code mount, 4 workers, PostgreSQL port not exposed):**

```bash
docker compose -f docker/docker-compose.prod.yml up --build -d
```

Production needs `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB` in `.env`. Do not use the
development passwords in production.

## API overview

All routes below are on the same server, for example `http://localhost:8000/auth/login`.

| Prefix | Area | Routes |
|---|---|---|
| `/health` | Health check | `GET /health` |
| `/auth` | Sign up, login, tokens, password reset, Google sign-in | `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/forgot-password`, `POST /auth/reset-password`, `POST /auth/google` |
| `/users` | Your profile and account settings | `GET /users/me`, `PATCH /users/me`, `DELETE /users/me`, `POST /users/me/change-password`, `POST /users/me/change-email`, `POST /users/me/change-email/confirm` |
| `/conversations` | Consultation threads | `POST /conversations`, `GET /conversations`, `GET /conversations/with-messages`, `GET /conversations/{id}`, `GET /conversations/{id}/messages`, `DELETE /conversations/{id}` |
| `/chat` | Send a question and get an answer | `POST /chat/{conversation_id}/message` |
| `/documents` | Upload, list and delete your documents | `POST /documents/upload`, `GET /documents`, `DELETE /documents/{document_id}` |
| `/documents/generated` | Saved answers, generated documents, case-law status | `GET /documents/generated`, `POST /documents/generated`, `GET /documents/generated/{doc_id}/download`, `DELETE /documents/generated/{doc_id}`, `GET /documents/generated/case-law/status`, `POST /documents/generated/case-law` |
| `/billing` | Plans and checkout (demo) | `GET /billing/plans`, `GET /billing/subscription`, `POST /billing/checkout` |
| `/usage` | Your free-plan usage | `GET /usage/me` |
| `/admin` | Admin only: overview, users, questions, documents, system, audit log | `GET /admin/me`, `GET /admin/stats`, `GET /admin/overview`, `GET /admin/users`, `PATCH /admin/users/{user_id}`, `DELETE /admin/users/{user_id}`, `GET /admin/questions`, `GET /admin/documents`, `GET /admin/system`, `GET /admin/audit` |
| `/admin/rag` | Admin only: upload legal sources | `POST /admin/rag/documents`, `GET /admin/rag/jobs/{job_id}` |

Most routes need a login token: send `Authorization: Bearer <access_token>`.

Free plan: 6 questions, then a 6 hour wait. The server enforces this and returns HTTP 402 when the
limit is reached.

## Troubleshooting

| What you see | Cause | Fix |
|---|---|---|
| `jwt_secret_key: Field required` or `database_url: Field required` | No `.env` file, or it is missing a value | `cp .env.example .env`, then set `JWT_SECRET_KEY` |
| `no such table: users` (or any "no such table") | Migrations were not run on this database | `alembic upgrade head` |
| `TypeError: unsupported operand type(s) for |` | Python is older than 3.10 | Install Python 3.11 and create the virtual environment again |
| `ModuleNotFoundError: No module named 'app'` or `'config'` | Command run from the wrong folder | `cd legal-advisory-system-backend` first |
| `ModuleNotFoundError` for another package | Packages not installed, or installed outside the virtual environment | Activate `.venv`, then `pip install -r requirements-lock.txt` |
| `Address already in use` on port 8000 | Another API is still running | Stop it, or use another port: `uvicorn app.main:app --port 8001` |
| Browser says CORS error | Web app address missing from `CORS_ORIGINS` | Add it in `.env`, then restart the API |
| `alembic upgrade head` fails on a Postgres URL | Postgres is not running | `docker compose -f docker/docker-compose.yml up postgres -d` |
| Reset code never arrives | SMTP is empty in development | Look in the API terminal for the printed code |
| `401 Unauthorized` after a while | Access token expired | The web app refreshes it automatically. Otherwise log in again. |

## Current limits

- **Chat answers are placeholders** until the AI/GraphRAG pipeline is connected. The hook is in
  `app/chat/pipeline_client.py`.
- **`data/case_law/` is empty.** Add your export files there to use the case-law loader.
- **Checkout is a demo.** It activates the plan without charging a card.
- **Legal sources uploaded by admins are stored and tracked, but not yet indexed** for search.
- **Redis is not used yet.** Rate limits are in memory, so they reset when the server restarts.
- **Password reset codes are printed to the terminal** unless real SMTP settings are added.
