# ScoutSphere

Multi-tenant football scouting and talent-intelligence platform with an integrated AI agent.
Full requirements: [docs/PRD.md](docs/PRD.md). Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API docs (OpenAPI) | http://localhost:8000/docs |
| Liveness | http://localhost:8000/api/v1/health |
| Readiness (Postgres + Redis) | http://localhost:8000/api/v1/health/ready |

Host ports for Postgres (5433) and Redis (6380) are offset so they do not clash with local installs.
The backend container runs `alembic upgrade head` on start.

## Working without Docker for app code

```bash
docker compose up -d postgres redis
cd backend && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --reload
cd frontend && pnpm install && pnpm dev
```

## Checks

```bash
cd backend  && uv run ruff check . && uv run ruff format --check . && uv run pytest
cd frontend && pnpm lint && pnpm typecheck && pnpm test
```

Backend tests need the compose Postgres and Redis running.

## Create a platform admin (for platform endpoints)

```bash
cd backend && uv run python -m app.cli create-platform-admin you@example.com "Your Name"
```
The password is prompted for, never passed on the command line.

## Migrations

```bash
cd backend
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
```

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for conventions.
