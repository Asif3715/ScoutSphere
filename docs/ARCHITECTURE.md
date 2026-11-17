# Architecture (Phase 0)

ScoutSphere is a **modular monolith**: one FastAPI backend, one Next.js frontend, PostgreSQL as the
source of truth, Redis for cache/queues. Decisions that override the original blueprint are in
[PRD.md](PRD.md) section 0.

```
Browser -> Next.js (3000) -> FastAPI /api/v1 (8000) -> PostgreSQL (SQLAlchemy 2 async)
                                                    -> Redis
```

## Backend layout (`backend/app`)

| Dir | Purpose |
|---|---|
| `api/v1` | Thin route handlers only; no business logic |
| `core` | Settings (pydantic-settings), logging (structlog JSON) |
| `db` | `Base`, naming convention, UUID/timestamp mixins, async session |
| `models` | SQLAlchemy models; imported in `models/__init__.py` for Alembic |
| `schemas` | Pydantic request/response models |
| `repositories` | All database access; tenant-scoped helpers arrive in Phase 1 |
| `services` / `modules` | Business logic per domain; the AI agent will call these same services |
| `permissions` | RBAC constants and `AuthContext` (Phase 1) |
| `workers` | Celery tasks (added with first background job) |

## Decisions

- **Async SQLAlchemy (asyncpg) for the app, sync psycopg2 for Alembic.** Alembic derives its URL from the same settings.
- **Constraint naming convention** on `Base.metadata` so migrations are deterministic.
- **UUID primary keys, timezone-aware timestamps** via mixins.
- **Baseline migration** enables `pgcrypto`, `pg_trgm` (fuzzy search/duplicate detection) and `citext`.
- **Health:** `/health` is liveness (no dependencies); `/health/ready` checks Postgres and Redis and returns 503 if either is down.
- **Host ports** 5433/6380 avoid clashes with local Postgres/Redis; services bind to 127.0.0.1 only.
- **Infrastructure on demand:** Celery, Qdrant, object storage and WebSockets are not present until a phase needs them.
- **Frontend** uses the Next.js App Router with Tailwind; shadcn/ui, TanStack Query and form libraries are added in Phase 1 with the first real screens.
