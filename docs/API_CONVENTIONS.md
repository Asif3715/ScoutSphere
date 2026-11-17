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
| 409 | `email_taken`, `club_exists`, `already_member`, `invitation_exists`, `last_owner` |
| 400 | `invalid_invitation` (same error for bad, expired, revoked or used tokens), `invalid_organization` |
| 403 (more) | `owner_required`, `email_mismatch`, `account_type_not_allowed` |
| 404 | `not_found` (also returned for resources of other organizations) |
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

## Phase 2 endpoints
Two ways to scope to an organization: header-scoped routes (`/clubs`) use `X-Organization-Id`; path-scoped routes (`/organizations/{org_id}/...`) use the path id. Both verify an active membership.

| Endpoint | Permission |
|---|---|
| `POST /organizations` | any `standard` account; creator becomes Club Owner |
| `GET/PATCH /organizations/{id}` | `org:read` / `org:update` (owner only) |
| `GET /organizations/{id}/dashboard` | `org:read` |
| `GET /organizations/{id}/members` | `members:read` |
| `PATCH/DELETE /organizations/{id}/members/{member_id}` | `members:manage` (owner rules below) |
| `POST/GET /organizations/{id}/invitations`, `DELETE .../{invitation_id}` | `members:manage` |
| `POST /invitations/preview`, `POST /invitations/accept` | token is the credential; accept needs login and matching email |
| `GET/POST /clubs`, `GET/PATCH/DELETE /clubs/{id}` | `clubs:read` / `clubs:manage`; `?scope=mine\|reference&q=&country=&page=&page_size=` |
| `GET /platform/organizations`, `PATCH /platform/organizations/{id}/status`, `POST /platform/clubs` | `platform:orgs_manage` |

Business rules: only a Club Owner may grant, change or remove owner access; an organization always keeps at least one owner; removed members keep their history and can be re-invited; clubs are archived (soft delete), never hard-deleted; reference clubs are global and read-only for tenants. Lists return `{items,total,page,page_size}` with `page_size` max 100.

## Planned (later phases)
Pagination (`page`, `page_size`), sorting (`sort`), filtering by query params, rate limiting, password recovery and email verification.
