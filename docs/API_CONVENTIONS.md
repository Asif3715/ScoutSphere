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

## Input limits and hardening
- Request bodies are capped at 1 MiB (`413 payload_too_large`). NUL characters in a body, query string or path are rejected (`422 invalid_characters`) because PostgreSQL cannot store them. `page` is capped at 1,000,000.
- Surrounding whitespace is trimmed from every text field *before* validation, so a name of `"   "` is rejected rather than stored blank. Passwords are never trimmed.
- Any unexpected server fault returns the normal JSON error shape (`500 internal_error`) with no internals; data the database cannot store returns `422 invalid_input`.
- Every API response carries `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` and `Cache-Control: no-store` (plus HSTS when `COOKIE_SECURE=true`).
- Refresh tokens rotate on every use. A rotated token presented again within 10 seconds, while the login still has a live session, is treated as two browser tabs racing and gets a fresh session; any later replay, or any replay after logout, revokes the whole login.

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

## Phase 5 endpoints (header-scoped with `X-Organization-Id`, except notifications)

**Assignments** - permissions are enforced inside the service (shared with the future AI agent).

| Endpoint | Who |
|---|---|
| `GET /assignments` (`status, scout_id, target_type, overdue, mine`) | managers (`assignments:manage`) see all; others see only non-draft assignments given to them |
| `GET /assignments/summary` | counts per status, overdue, due within 48h (same visibility) |
| `POST /assignments` | managers. `assign_now=true` creates and sends in one step. Target is a match, competition or player the organization can see; the scout must be an active member with an active profile; the deadline must be in the future |
| `GET/PATCH /assignments/{id}` | detail with history, reports and `allowed_transitions` for the caller |
| `POST /assignments/{id}/transition` `{to, note}` | see workflow |

Workflow (who can move): `draft -> assigned | cancelled` (manager); `assigned -> accepted` (scout) or `cancelled` (manager); `accepted -> in_progress` (scout, automatic when the first report is started) or `cancelled`; `in_progress -> submitted` (scout; needs at least one report and none left in draft/revision) or `cancelled`; `submitted -> under_review | in_progress` (manager; returning needs a note); `under_review -> approved | rejected | in_progress` (manager; approval needs every report reviewed and at least one approved; rejecting/returning needs a note). `approved`, `rejected` and `cancelled` are final. Every change is written to the append-only history.

**Scouting reports** (`/scouting-reports`)

| Endpoint | Who |
|---|---|
| `GET /scouting-reports` (`status, player_id, scout_id, match_id, assignment_id, recommendation, mine`) | reviewers (`reports:review`) see all; writers see their own; readers (`reports:read`) see approved reports |
| `POST /scouting-reports` | scouts with an active profile (`reports:write`); optional `assignment_id` must be yours and accepted/in progress, and match its target |
| `GET /scouting-reports/{id}`, `GET .../versions/{n}` | visible reports only |
| `PATCH /scouting-reports/{id}`, `DELETE` | the author, while draft or revision requested (delete: never-submitted drafts only). Ratings merge; a `null` value removes one |
| `POST /scouting-reports/{id}/submit` | the author. Needs at least 3 ratings, a recommendation and general observations. Each submission stores an immutable version snapshot |
| `POST /scouting-reports/{id}/review` `{decision, comment}` | reviewers other than the author. `approved`, `revision_requested` or `rejected`; a comment is required unless approving. A revision request re-opens a submitted assignment |

20 rating attributes in four groups (technical, physical, tactical, mental), each 1-10. Ratings are subjective and stay separate from objective match statistics.

**Notifications** (`/notifications`, user-level: no organization header needed)
`GET /notifications` (`unread`, paging, newest first), `GET /notifications/unread-count`, `POST /notifications/{id}/read`, `POST /notifications/read-all`, `GET|PUT /notifications/preferences`. Notifications are private to their user; someone else's id returns 404. Types: assignment assigned/cancelled/accepted/submitted/approved/rejected/returned/deadline, report submitted/approved/rejected/revision requested. Users can switch any type off.

Deadline reminders run via `uv run python -m app.cli send-deadline-reminders` (idempotent; schedule it hourly). Delivery to the browser is by polling every 30 seconds; WebSockets and a Celery worker are deferred until needed.

New error codes (QA round): `invalid_characters`, `payload_too_large`, `invalid_input`, `internal_error`, `match_in_use`, `slug_unavailable`.

New error codes: `invalid_scout`, `invalid_target`, `deadline_in_past`, `not_editable`, `scout_locked`, `no_reports`, `reports_incomplete`, `reports_not_reviewed`, `note_required`, `scout_profile_required`, `invalid_assignment`, `assignment_not_open`, `assignment_mismatch`, `incomplete_report` (details list what is missing), `comment_required`, `not_submitted`, `cannot_review_own`, `has_history`.

## Phase 6 endpoints (header-scoped with `X-Organization-Id`, prefix `/recruitment`)

| Endpoint | Purpose |
|---|---|
| `GET/POST /requirements`, `GET/PATCH /requirements/{id}` | Recruitment requirements (position, age, nationality, foot, min appearances, per-attribute minimum ratings, budget, deadline, status) |
| `GET /requirements/{id}/matches` | Discovery: players that satisfy every criterion, each with a per-criterion breakdown |
| `GET /requirements/{id}/candidates`, `POST .../candidates` (+ `/bulk`) | Pipeline candidates for a requirement |
| `GET /candidates/{id}`, `POST /candidates/{id}/stage`, `POST /candidates/{id}/assign-scout` | Candidate detail with status history, stage moves, scout assignment |
| `GET /search` | Ad hoc discovery with the same filters (`min_rating=attribute:value`, repeatable) |
| `POST /compare` | Compare 2-5 players, optionally against a requirement |
| `GET/POST /shortlists`, `GET/PATCH/DELETE /shortlists/{id}` | Shortlists (`scope=all|mine|shared`) |
| `POST/PATCH/DELETE /shortlists/{id}/players[/{player_id}]`, `PUT /shortlists/{id}/shares`, `GET /shortlists/{id}/compare` | Shortlist players, sharing, comparison |

Pipeline stages: discovered, under_evaluation, shortlisted, scout_assigned, report_submitted, under_review, trial_proposed, negotiation, signed, rejected, archived. `signed` is reachable only from negotiation; `rejected` and `archived` reopen only to `discovered`. Closed (fulfilled or cancelled) requirements freeze their pipeline except for archive/reject.

Scouting reports move candidates automatically (`services/recruitment.sync_with_report`), for the organization's open candidates of the report's player. If the report belongs to an assignment, only candidates tied to that assignment (or to none) are affected; a report with no assignment affects candidates tied to none. Submitting moves a candidate to `report_submitted`; approving moves it to `under_review`; requesting changes sends it back to `scout_assigned` (only from those two stages). A candidate already further along is never pulled back, and a rejected report changes nothing. Each move is written to the stage history with an "Automatic: ..." note and notifies the requirement's creator, like a manual move.

New error codes: `invalid_transition`, `same_stage`, `requirement_closed`, `already_candidate`, `already_shortlisted`, `invalid_player`, `invalid_requirement`, `invalid_selection`, `invalid_user`, `not_editable`.

## Player photos

| Endpoint | Purpose |
|---|---|
| `PUT /players/{id}/photo` | Multipart upload (`file`, optional `crop_x`, `crop_y`, `crop_size` in pixels of the upright image). Same rights as editing the player. Replaces any previous photo. |
| `DELETE /players/{id}/photo` | Removes the uploaded photo and any external photo link. |
| `GET /media/{key}?exp=&sig=` | Serves a stored image through an HMAC-signed, expiring URL (no bearer token, so `<img>` tags work). Any failure is a plain 404. |

Players carry `photo_url`, `photo_thumb_url` (signed paths; prefix with the API origin) and `has_uploaded_photo`; summaries (lists, shortlists, pipeline, comparison) carry `photo_thumb_url`. An uploaded photo wins over the legacy `profile_picture_url` link. Photos of minors are withheld from other organizations, as biographies are.

Processing: JPEG, PNG or WebP up to 5 MB, at least 100x100. Decoded with Pillow (decompression bombs rejected), rotated upright from EXIF, cropped to a square, resized to 640 px and 160 px, re-encoded as WebP. Re-encoding drops all metadata (GPS, camera). Only the processed files are kept. The request guard allows a larger multipart body, without the NUL-byte check, on this one route only.

New error codes: `photo_too_large` (413), `photo_too_small`, `unsupported_photo_type`, `invalid_photo`, `invalid_crop`.

## Planned (later phases)
Pagination (`page`, `page_size`), sorting (`sort`), filtering by query params, rate limiting, password recovery and email verification.

## Player accounts

A player account (`account_type: "player"`) is a person, not a club: it has no organization. It gains a profile only when the organization that owns a player record approves a **claim**. These routes need a signed-in player account and no `X-Organization-Id`:

| Route | Notes |
|---|---|
| `GET /me/player/search?name=&date_of_birth=` | Unclaimed records matching the name AND the exact date of birth (max 10). Nobody can browse for people |
| `POST /me/player/claims` | `{player_id, date_of_birth, message?}`. A wrong date of birth, an unknown, archived or already-claimed player all return the same 404. One waiting request per account. Notifies members who can edit players |
| `GET /me/player/claims`, `DELETE /me/player/claims/{id}` | Own requests; cancel a waiting one |
| `GET /me/player`, `PATCH /me/player` | The linked profile (404 `no_profile` before approval) and what the player may edit: nationality, height, weight, foot, positions, biography, `visibility` (`private` or `network`), `open_to_offers`, `contact_email`. Name, date of birth, contract and medical data stay with the club |
| `PUT/DELETE /me/player/photo` | Same processing as club uploads (multipart; crop fields optional) |

The organization's side uses the normal header: `GET /player-claims?status=` and `POST /player-claims/{id}/decision` (`{decision: approved|rejected, note}`; a decline needs a note), both `players:write`. Another organization's claim is a 404. Approving declines any competing waiting claims for the same profile.

Rules once a profile is claimed: only the player changes `visibility` (the organization gets 409 `controlled_by_player`; it can still edit everything else). Other organizations see `contact_email` only while `open_to_offers` is on, never for a minor; the owning organization always does. Players under 18 cannot change `visibility`, `open_to_offers` or `contact_email` (403 `guardian_required`) until a guardian-consent flow exists. `PlayerOut` gains `claimed`, `open_to_offers`, `contact_email`.

New error codes: `no_profile`, `claim_pending`, `already_claimed`, `not_pending`, `controlled_by_player`, `guardian_required`, `contact_required`, `account_type_not_allowed`.

## Signing and squads

- Moving a candidate to `signed` notifies the organization's club managers (`candidate_signed`, link to the requirement) unless the player is already in one of its teams, and never the person who did it. It does not add the player to a team: that is `POST /teams/{id}/players`, which needs `clubs:manage`. The pipeline page offers it inline for people with that permission.
- Candidates carry `squad_team_id` and `squad_team_name` ("Team · Club"): the caller's own organization's active team for that player, or null.
- A player with a linked account is notified (`squad_joined`, `squad_left`, link `/player`) when added to a team, transferred between teams, or released. Players without an account are skipped.
- `POST /teams/{id}/players` accepts the organization's own players directly. A player whose record belongs to another organization needs a candidate of the caller's organization at the `signed` stage (any requirement), otherwise 409 `signing_required`. A candidate signed by a different organization does not count.
