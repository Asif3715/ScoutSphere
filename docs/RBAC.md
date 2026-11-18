# RBAC design

Permissions are string constants in code (`resource:action`); roles are seeded DB rows mapping to them.
Every service call receives an `AuthContext(user_id, org_id | None, role, permissions, platform_role | None)`.
The AI agent receives the same object; the model never decides its own permissions.

## Scopes
- **Platform:** `super_admin`, `platform_support`. Support has no default access to org-private data (needs an audited, time-limited grant).
- **Organization:** `club_owner`, `club_admin`, `recruitment_manager`, `scout`, `coach` (via `organization_members`; a user may hold different roles in different orgs).
- **Individual accounts:** `player`, `agent` (no org membership).

## Matrix (O = own/assigned only, R = read, W = write, A = approve)

| Resource | Owner | Admin | Recruit. Mgr | Scout | Coach |
|---|---|---|---|---|---|
| Org settings / members / roles | W | W (no owner changes) | - | - | - |
| Clubs, teams, squads | W | W | R | R | R |
| Players (org-added) | W | W | W | R | R |
| Player injury / medical | R | R | - | - | R |
| Assignments | W | W | W | O (R, accept, progress) | R |
| Scouting reports | R | R | R, A | O (W draft/submit) | R (permitted) |
| Requirements, shortlists, pipeline | W | W | W | - | R / recommend |
| Trials | W | W | W | R | W (evaluate) |
| Contracts, transfers, finances | W | W | W | - | - |
| Analytics | R | R | R (recruitment) | O (own) | R (squad) |
| AI agent | all above, constrained by the user's own permissions; writes risk-classified (see PRD 4.5) |

Platform: `super_admin` manages organizations, platform users, audit logs and agent executions; no implicit read of org-private content.

## Phase 4 permissions
- `scouts:read` (owner, admin, recruitment manager, scout), `scouts:manage` (owner, admin). Coaches have no scout-directory access.
- `matches:read` (all organization roles), `matches:manage` (owner, admin). Covers competitions, seasons, participants, matches, events and statistics.
- Global competitions/matches are managed through the platform permission `platform:orgs_manage` (super admin only; Platform Support cannot).

## Phase 5 visibility rules
- **Assignments:** managers (`assignments:manage`: owner, admin, recruitment manager) see and move all of them. Everyone else sees only the non-draft assignments assigned to them; coaches therefore see none.
- **Reports:** `reports:review` (owner, admin, recruitment manager) sees every report and may review any report except their own; `reports:write` (scouts, owner, admin) sees and edits their own; `reports:read` (also coaches) sees approved reports of the organization. Scouts can therefore read colleagues' *approved* reports.
- **Notifications:** only ever visible to the user they were sent to.

## Rules
1. Authorize in the service layer, on every operation.
2. Org-scoped queries always include `organization_id` from `AuthContext`, never from client input alone.
3. Ownership checks (e.g. a scout's own reports) are separate from role permissions.
4. Sensitive actions write to `audit_logs`.

The authoritative permission list and role mapping is `backend/app/permissions/catalog.py` (32 permissions, 7 roles as of Phase 4). Tests assert platform and organization permissions never overlap and that Platform Support holds no organization permission.
