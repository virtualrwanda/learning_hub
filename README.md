# CLH Backend

FastAPI backend for Customized Learning Hub — subscription-based e-learning platform.
Implements Phases 1–2 of the CLH Technical Blueprint: project scaffold, DB schema,
authentication with single-active-session enforcement, and RBAC.

## Stack

- FastAPI + Pydantic v2
- SQLAlchemy 2.0 (async) + Alembic
- PostgreSQL 16
- Redis 7 (sessions + cache)
- Argon2id password hashing

## Quickstart

```bash
# 1. Install dependencies
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
pip install -e ".[dev]"

# 2. Start infrastructure
docker compose up -d

# 3. Create the dev database (if not already)
docker exec -it clh_postgres psql -U clh -c "CREATE DATABASE clh;"
docker exec -it clh_postgres psql -U clh -c "CREATE DATABASE clh_test;"

# 4. Configure
copy .env.example .env      # Windows
# cp .env.example .env      # macOS/Linux

# 5. Migrate
alembic revision --autogenerate -m "initial schema"
alembic upgrade head

# 6. Seed RBAC + settings
python -m scripts.seed_rbac

# 7. Run
uvicorn app.main:app --reload --port 8000
```

- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/health>

## Tests

```bash
# ensure clh_test DB exists (see step 3 above)
pytest -v
```

## What's implemented (Phase 1–2)

- ✅ Project scaffold and env-driven config (no hard-coded secrets)
- ✅ Full Postgres schema via SQLAlchemy 2.0 + Alembic migrations
- ✅ Argon2id password hashing, opaque session tokens
- ✅ **Single-active-session enforcement** — new login revokes prior session (Redis + DB)
- ✅ Table-driven RBAC (roles, permissions, role_permissions, user_roles)
- ✅ `require_permissions()` / `require_roles()` route guards
- ✅ `SystemSetting` table — every business value configurable (Rule 3)
- ✅ Audit log model + `AuditService` (immutable by convention; DB trigger to come)
- ✅ Security headers middleware, HttpOnly + SameSite cookie

## What's next (Phase 3+)

- Content CMS routes (curricula → grades → subjects → courses → units → lessons)
- Video pipeline (managed service, playback-token endpoint)
- Payment abstraction (MoMo, PayPal) with idempotent webhook handlers
- Subscription state machine + nightly expiry sweep
- Notification queue (ARQ / Celery)
- Reports + CSV/PDF export