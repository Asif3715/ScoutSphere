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

## Phase 3 endpoints (header-scoped with `X-Organization-Id`)

| Endpoint | Permission |
|---|---|
| `GET /players` | `players:read`. Filters: `q, position, group, nationality, foot, min_age, max_age, min_height, max_height, club_id, team_id, scope=all\|mine\|network, sort=name\|age_asc\|age_desc\|newest, page, page_size` |
| `POST /players` | `players:write`. Returns 409 `possible_duplicate` (with candidates in `details`) unless `allow_duplicate=true` |
| `GET /players/{id}` | `players:read` (only if visible to your organization, else 404) |
| `PATCH/DELETE /players/{id}` | `players:write`, and your organization must have created the player |
| `GET/POST /players/{id}/career`, `PATCH/DELETE .../{entry_id}` | read / `players:write` |
| `GET/POST /players/{id}/media`, `DELETE .../{media_id}` | read / `players:write`; links are private to the adding organization |
| `GET/POST /teams`, `GET/PATCH/DELETE /teams/{id}` | `clubs:read` / `clubs:manage` |
| `GET /teams/{id}/squad?include_left=&group=` | `clubs:read` + `players:read` |
| `POST /teams/{id}/players`, `PATCH/DELETE .../{membership_id}`, `POST .../{membership_id}/transfer` | `clubs:manage` |

Player visibility: a player is visible to your organization if it created them, if they are in one of your squads, or if their visibility is `network`/`public`. Anything else returns 404, never 403. Players under 18 cannot be `public`; other organizations never receive a minor's biography or photo.

New error codes: `possible_duplicate`, `minor_cannot_be_public`, `player_in_squad`, `team_exists`, `team_has_players`, `squad_number_taken`, `already_in_squad`, `invalid_club`, `invalid_player`, `managed_by_squad`.

## Phase 4 endpoints (header-scoped with `X-Organization-Id`)

| Endpoint | Permission |
|---|---|
| `GET /scouts` (`q, position, age_group, region, min_experience, status=active\|inactive\|all`) | `scouts:read` |
| `POST /scouts` | `scouts:manage` to profile another member; a scout (`reports:write`) can create their own |
| `GET /scouts/{id}`, `PATCH /scouts/{id}` | read / own profile or `scouts:manage` (`is_active` is manager-only) |
| `GET/POST /competitions`, `GET/PATCH/DELETE /competitions/{id}` | `matches:read` / `matches:manage` |
| `POST /competitions/{id}/seasons`, `GET/PATCH/DELETE /seasons/{id}` | read / manage |
| `POST /seasons/{id}/participants`, `DELETE /seasons/{id}/participants/{club_id}` | manage |
| `GET/POST /matches`, `GET/PATCH/DELETE /matches/{id}` | `matches:read` / `matches:manage` |
| `POST /matches/{id}/events`, `DELETE .../events/{event_id}`, `PUT /matches/{id}/statistics` | manage; match must be live or finished |

**Global vs organization data.** Competitions, seasons and matches are either private to one organization or *global* (maintained by platform admins by calling the same endpoints with no `X-Organization-Id`). Tenants can read global rows but never change them (404). A global competition can only list global reference clubs.

**Match rules.** Both clubs must be participants of the match's season. Status moves `scheduled -> live -> finished` (or `postponed`/`cancelled`; a finished match cannot be re-opened). A finished match needs a score; scheduled, postponed and cancelled matches have none (moving a live match to cancelled clears the provisional score). Played matches cannot be deleted. Statistics validate `shots_on_target <= shots` and combined possession <= 100.

New error codes: `scout_exists`, `not_a_member`, `competition_exists`, `season_exists`, `already_participant`, `participant_has_matches`, `season_has_matches`, `club_not_in_season`, `invalid_season`, `invalid_transition`, `scores_required`, `scores_incomplete`, `scores_not_allowed`, `match_not_started`, `match_played`, `invalid_possession`, `player_not_allowed`.

## Planned (later phases)
Pagination (`page`, `page_size`), sorting (`sort`), filtering by query params, rate limiting, password recovery and email verification.
