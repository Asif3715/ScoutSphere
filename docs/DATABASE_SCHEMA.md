# Database schema design

Conventions: UUID PKs, `timestamptz` (UTC), `created_at`/`updated_at`, explicit FKs and indexes, money as integer minor units + ISO currency, JSONB only for genuinely flexible attributes. Tables are introduced by the migration of the phase that needs them. Extensions enabled in baseline: `pgcrypto`, `pg_trgm`, `citext`.

## Tenancy rule
Tables marked **[org]** carry `organization_id` (NOT NULL, indexed, FK). **[global]** tables are not tenant-owned. **[mixed]** tables are global entities with a visibility field plus org-owned overlay tables.

## Entities by phase

| Phase | Tables |
|---|---|
| 1 Identity | users (citext email), user_sessions (hashed refresh tokens), roles, permissions, role_permissions, organization_members [org], invitations [org], audit_logs |
| 2 Orgs/clubs | organizations, clubs [mixed: `organization_id` NULL = reference club], club_settings [org] |
| 3 Players | players [mixed: visibility enum], player_positions, player_career_history, player_statistics, player_media, player_documents, player_availability (restricted), teams [org], team_players [org], player_claims |
| 4 Scouts/matches | scout_profiles [org], scout_specializations, competitions, competition_seasons, competition_participants, matches, match_events, match_statistics |
| 5 Assignments/reports | scout_assignments [org], assignment_history [org], scouting_reports [org], scouting_report_ratings, scouting_report_versions, scouting_report_reviews, notifications |
| 6 Recruitment | recruitment_requirements [org], recruitment_candidates [org], shortlists [org], shortlist_players, recruitment_stage_history [org] |
| 7-8 Agent | conversations, conversation_messages, agent_executions, agent_approvals (args hash, expiry), idempotency_keys |
| 9 Trials | trials [org], trial_participants, trial_evaluations |
| 10 Contracts | contracts [org], transfers [org], transfer_proposals, negotiations, agents, player_representatives |
| 11 RAG | uploaded_files [org], document_chunks_metadata [org] (vectors in Qdrant) |

## Key relationships
- `clubs.organization_id` nullable: managed vs reference club.
- `player_career_history` links global `players` to `clubs` (any kind) with date ranges (CHECK start <= end; no overlapping full-time spells enforced in service).
- `team_players` links `players` to org-owned `teams`; moving club never duplicates a player.
- `scouting_reports` (subjective, org-private) are separate from `player_statistics` / `match_statistics` (objective).
- Status machines (assignments, reports, recruitment stages) use enum/check constraints plus append-only history tables.

Detailed column definitions are written with each phase's models and kept here in sync.

## Implemented so far

**Phase 1 (migration 0002):** users, user_sessions, roles, permissions, role_permissions, organizations, organization_members, audit_logs.

**Phase 2 (migration 0003):**
- `organizations` gains `description`, `created_by_user_id`.
- `clubs`: nullable `organization_id` (NULL = reference club), contact/profile fields, `archived_at`. Unique `(organization_id, lower(name))` for active managed clubs; trigram index on `name`; `founded_year` CHECK 1800-2100.
- `invitations`: `email` (citext), `role_id`, `token_hash` (sha256, unique), `status` pending/accepted/revoked, `expires_at`. Partial unique index allows one pending invitation per `(organization_id, email)`.

**Phase 3 (migration 0004, players and teams):**
- `players` (global identity): DOB, nationality, body measurements, primary position, `visibility` (private/network/public), `owner_organization_id` (creating org, nullable for self-registered players), `claimed_by_user_id` (reserved for profile claiming), `archived_at`. CHECK constraints on height, weight, foot, position, visibility. Trigram index on `lower(full_name)` for search and duplicate detection.
- `player_positions`: secondary positions. `player_career_history`: one row per club spell, `end_date >= start_date`, `team_player_id` marks spells opened by squad registration. `player_media`: org-private http(s) links.
- `teams`: belong to one managed club; unique active name per club. `team_players`: squad memberships; rows are never deleted (`status` active/left); partial unique indexes allow one active membership per player per team and one active holder per squad number.
- Deferred to later phases: contract and market-value fields (contracts phase), injury/availability records, player self-claim workflow, real file storage for media.

**Phase 4 (migration 0005, scouts and matches):**
- `scout_profiles` (one per organization member, `experience_years` CHECK 0-60, `is_active`) and `scout_specializations` (composite key of profile, kind `position|age_group|region`, value).
- `competitions` (`organization_id` NULL = global), unique active name per scope via a `coalesce(organization_id, zero-uuid), lower(name)` index. `competition_seasons` (unique name per competition, `end_date >= start_date`), `competition_participants` (unique club per season).
- `matches` (global when `organization_id` is NULL): CHECKs for different clubs, valid status, paired non-negative scores, and finished-implies-scored. `match_events` (type, minute 0-150, optional player), `match_statistics` (one row per club per match; possession 0-100, shots on target <= shots).
- Deferred: scout assignments and assigned competitions/matches (Phase 5), match-level player statistics (advanced statistics, later).

**Phase 5 (migration 0006, assignments, reports, notifications):**
- `scout_assignments`: exactly one target (match, competition or player) enforced by a CHECK; status CHECK; `deadline`, `reminder_sent_at`. `assignment_history` is append-only with a database-generated `seq` so ordering never depends on timestamps (rows written in one transaction share `created_at`).
- `scouting_reports` (subjective, org-private; optional assignment, match, club), `scouting_report_ratings` (20 attributes, 1-10 by CHECK), `scouting_report_versions` (immutable JSONB snapshot per submission), `scouting_report_reviews` (decision, comment, version reviewed).
- `notifications` (per user, `seq` ordering, `read_at`) and `notification_preferences` (per user and type).
- Deferred: configurable rating scales, WebSocket push, email delivery.
