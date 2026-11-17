# Development conventions

- Work on short-lived branches off `main` (`feature/<module>`); small, meaningful commits.
- Business logic lives in services, database access in repositories, never in route handlers.
- Every schema change goes through an Alembic migration; never edit applied migrations.
- Every endpoint authorizes on the backend; frontend hiding is cosmetic.
- No secrets in code; configuration via environment (`.env.example` documents every variable).
- Write tests with each module: unit, API, permission and tenant-isolation tests.
- Backend: `ruff` (lint + format), `pytest`. Frontend: `eslint`, `tsc`, `vitest`, `prettier`.
- Update `docs/` whenever architecture, APIs or the schema change.
- Phase 0 pending docs: `DATABASE_SCHEMA.md` and `RBAC.md` (designed before Phase 1 begins).
