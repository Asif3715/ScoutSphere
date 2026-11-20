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

## Demo data

`backend/scripts/seed_demo.py` fills an existing organization with realistic test data: demo staff
(admin, recruitment manager, scouts, coach), clubs and squads with generated player portraits,
career histories, a league season with results and match statistics, assignments and scouting
reports in every workflow state, recruitment requirements with pipelines, and shortlists.

```bash
cd backend
uv run python scripts/seed_demo.py "Your Organization Name" --size full   # or --size small
```

- Runs only in the `local`/`test` environment and refuses to seed the same organization twice.
- Everything goes through the API (so rules, histories and notifications are real); only the demo
  staff memberships are inserted directly, since joining normally needs the owner's invitation.
- Demo logins share one password, listed in `demo-accounts.md` at the repository root (git-ignored).
- Clubs it creates carry `[demo data]` in their description; that is how a second run is detected.
