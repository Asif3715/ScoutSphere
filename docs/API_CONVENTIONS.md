# API conventions

Base path `/api/v1`. OpenAPI at `/docs` and `/api/v1/openapi.json`.

## Errors
Every error has the same shape:
```json
{"error": {"code": "invalid_credentials", "message": "Invalid email or password", "details": []}}
```
`details` appears only for `validation_error` (422): `[{"field": "email", "message": "..."}]`.

| Status | Codes |
|---|---|
| 401 | `not_authenticated`, `invalid_token`, `invalid_credentials`, `invalid_refresh_token` |
| 403 | `forbidden` (missing permission), `not_a_member`, `account_disabled` |
| 409 | `email_taken` |
| 422 | `validation_error` |

## Authentication
- Access token: JWT (HS256, 15 min), sent as `Authorization: Bearer <token>`. Held in memory by the frontend.
- Refresh token: opaque, rotated on every use, stored hashed server-side, delivered as an `httpOnly` `SameSite=Lax` cookie scoped to `/api/v1/auth`. Re-using a rotated token revokes the whole token family.
- Active organization: `X-Organization-Id` header. The backend re-validates it against an active membership on every request; the header alone grants nothing.

| Endpoint | Purpose |
|---|---|
| `POST /auth/register` | Create account (`account_type`: standard, player, agent). Platform roles cannot be self-assigned. |
| `POST /auth/login` | Returns access token + user, sets refresh cookie |
| `POST /auth/refresh` | Rotates refresh cookie, returns new access token |
| `POST /auth/logout` | Revokes the token family, clears cookie (always 204) |
| `GET /auth/me` | Current user and active memberships with permissions |

## Authorization in code
- `get_current_user` authenticates; `get_auth_context` builds the `AuthContext`; `require_permission("resource:action")` is the route dependency that enforces a permission and writes an `authz.denied` audit row on failure.
- Permissions and role mappings live in `backend/app/permissions/catalog.py` and are mirrored into the DB at startup.

## Planned (later phases)
Pagination (`page`, `page_size`), sorting (`sort`), filtering by query params, rate limiting, password recovery and email verification.
