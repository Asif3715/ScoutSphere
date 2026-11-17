# ScoutSphere
## Master Product Requirements & Technical Implementation Blueprint

**Project:** ScoutSphere — AI-Powered Sports Scouting & Talent Intelligence Platform  
**Product Type:** Multi-tenant SaaS Web Application  
**Initial Sport:** Football (Soccer)  
**Development Approach:** Modular Monolith  
**Primary Objective:** Build a complete, production-oriented web application with a fully integrated, role-aware AI agent capable of retrieving information, analyzing data, and executing authorized operations.

---

# 0. Resolved Decisions and Clarifications

This section was added after reviewing the original blueprint. Where it conflicts with anything below, **this section wins**. It resolves ambiguities and contradictions so the coding agent does not have to invent business rules.

## 0.1 Tenancy and data-ownership model

- **Organization = tenant.** All private operational data (members, reports, shortlists, requirements, assignments, notes, trials, contracts) carries `organization_id` and is invisible to other organizations.
- **Clubs can be "managed" or "reference".** A *managed* club belongs to one organization. A *reference* club is a global record (e.g. an opponent, or a past club in a player's career) that is not a tenant and has no members. A managed club can be linked to / claim a reference club later. Matches, competitions and career history may therefore reference clubs that are not on the platform.
- **Players are global identities** with a visibility setting (`private_to_creator_org` | `network` | `public_profile`). Basic identity and objective career facts follow the visibility setting; everything an organization *adds* to a player (scout reports, ratings, notes, shortlist entries, contract data) is organization-private. Injury/medical, contract and financial data are always restricted regardless of visibility.
- **Players may be created in two ways:** an organization adds a player (record owned by that org until claimed/merged), or a Player user self-registers. A Player user can *claim* an existing identity (requires admin verification). Duplicate detection (name + DOB + nationality fuzzy match) runs on every create and proposes a merge rather than auto-merging.
- **Minors:** many players (U19, academy) are under 18. Personal data of minors is restricted by default (no public profile, no contact details, no documents visible outside the owning org). Treat this as a GDPR-style requirement from day one.

## 0.2 Roles and permissions

- Two scopes: **platform scope** (Super Admin, Platform Support) and **organization scope** (Club Owner, Club Admin, Recruitment Manager, Scout, Coach). **Player** and **Football Agent** are *individual account types* without an organization membership (an agent may also be linked to organizations by relationship records).
- Permissions are code-defined string constants (e.g. `players:read`, `reports:approve`); roles are seeded database rows mapping to those permissions. Authorization is checked in the service layer through a single `AuthContext` object (user, active organization, role, permissions) that is also what the AI agent receives.
- The active organization is chosen per request via a header/claim and re-validated against membership on every request. Platform Support has **no** default access to club-private data; access requires an explicit, time-limited, audited grant.

- **Organization creation:** any individual `standard` account can found an organization and becomes its Club Owner (Phase 2 decision). Player and agent accounts join organizations by invitation only. Platform admins can suspend or reactivate any organization.

- **Player visibility (Phase 3):** new players are `private`. Cross-organization duplicate detection only considers players visible to the creating organization, so it can never reveal a hidden player; resolving duplicates across private records is a future platform-admin merge tool.
- **Squad registration and career history:** adding a player to a team opens a career spell at that team's club; releasing closes it. Moving a player between teams is a single transaction. Closing spells at clubs managed by other organizations is those organizations' responsibility.

## 0.3 Authentication details

- Argon2id password hashing. Short-lived access JWT (about 15 min) plus rotating, revocable refresh tokens stored hashed in `user_sessions`. Refresh token in an `httpOnly`, `Secure`, `SameSite` cookie; access token held in memory by the frontend.
- Email delivery is stubbed (console/log backend) until a provider is chosen; verification and password-reset flows must still be implemented against that stub.

## 0.4 Agent decisions

- **The agent arrives earlier than in the original roadmap** (see revised Section 12). It is the product's differentiator and should grow alongside the modules it operates on, with tools added in the same phase as the module they wrap.
- Agent tools call the **same application services** as the REST API, with the same `AuthContext`. No separate "agent-only" data paths.
- LangGraph with a **Postgres checkpointer**; human-in-the-loop approvals use LangGraph interrupts. An approval record stores the exact tool name, validated arguments and a hash of them, the requesting user, and an expiry; execution is bound to that hash. Only an authenticated user action through the approvals API can approve; model output never can.
- Write tools take an **idempotency key**; every write tool call is recorded in `agent_executions` and `audit_logs`.
- LLM access goes through a provider abstraction (Groq / OpenRouter / later others). Use a mock provider for deterministic tests.
- **Embeddings:** BGE-M3 is the target, but it is large and slow on CPU. Put embeddings behind an interface so the model can run locally (if the dev machine can handle it), via a hosted API, or via a smaller model during development. Decide when Phase 11 starts.

## 0.5 Scope and infrastructure discipline

- **Add infrastructure only when a phase needs it.** Phase 0 requires only frontend, backend, PostgreSQL and Redis. Celery workers arrive with the first background job (notifications / deadline reminders); WebSockets with real-time notifications; Qdrant and object storage with RAG/document upload. Do not stand up unused services.
- PostgreSQL Row-Level Security is a defense-in-depth layer. Phase 1 establishes tenant-scoped repository helpers that cannot run a query without an organization filter; RLS policies are added and tested during hardening (or earlier if cheap).
- Money: store amounts as integer minor units plus an ISO currency code. Dates and times are timezone-aware UTC.
- Ratings and objective statistics live in separate tables and are never merged into a single number without a configurable, documented formula.

## 0.6 Things deliberately out of scope for now

Video analysis and upload processing, external football-data APIs, mobile app, specialized subagents, predictive evaluation, email provider integration, payment processing, and any real financial transaction execution. Contracts and transfers are *records and workflows*, not payment systems.

---

# 1. Product Vision

ScoutSphere is a centralized sports scouting, recruitment, club management, and talent intelligence platform.

The platform connects multiple football clubs, scouts, coaches, players, recruitment managers, and football agents in one ecosystem.

Each organization should be able to manage its own operations while participating in a broader player discovery and scouting network, subject to data-sharing permissions.

The platform should provide:

1. Club and organization management.
2. Player profiles and career histories.
3. Scout management and assignments.
4. Match and competition management.
5. Scouting reports and player evaluations.
6. Recruitment and transfer management.
7. Player shortlisting and comparisons.
8. Trials and recruitment pipelines.
9. Performance analytics and reporting.
10. An AI agent capable of operating across all these modules.

The AI agent is a central product feature, not an isolated chatbot.

It should understand the platform's data, retrieve relevant information, analyze it, and perform real application operations through controlled backend tools.

## 1.1 Product principles

- Every organization must have isolated private data.
- The platform must support multiple clubs and organizations.
- Player profiles should support career histories across multiple clubs.
- Objective performance statistics must be separated from subjective scout evaluations.
- Users should only access functionality allowed by their permissions.
- AI actions must follow the same authorization and validation rules as normal application operations.
- Important operations must be auditable.
- The architecture should support future expansion into other sports.

---

# 2. User Roles and Permission System

Implement role-based access control (RBAC), with organization-specific memberships.

A user can potentially have different roles in different organizations.

## 2.1 Platform-level roles

### Super Admin

Responsible for the entire platform.

Capabilities:
- View and manage registered organizations.
- Activate, suspend, or deactivate organizations.
- Manage platform users.
- View platform-wide statistics.
- Monitor system activity.
- Inspect AI execution logs.
- Manage platform-level configurations.
- Investigate reported issues.

### Platform Support

Capabilities:
- View permitted platform and organization information.
- Investigate user issues.
- Review operational logs.
- Assist with account management.

Support users should not automatically receive unrestricted access to private club data.

## 2.2 Organization-level roles

### Club Owner

- Manage club profile.
- Manage organization settings.
- Invite and remove members.
- Assign organizational roles.
- Manage teams.
- Access club analytics.
- Manage recruitment activities.

### Club Administrator

- Manage club operations.
- Manage squads, players, scouts, and matches.
- Assign responsibilities.
- Manage reports and notifications.

### Recruitment Manager

- Create recruitment requirements.
- Search for players.
- Create and manage shortlists.
- Compare candidates.
- Assign scouts.
- Manage trials and recruitment pipelines.
- Track transfer opportunities.

### Scout

- View assigned scouting tasks.
- View permitted player information.
- Submit scouting reports.
- Rate players.
- Add observations and recommendations.
- Track assignments.

### Coach

- View squad information.
- Review player performance.
- Access permitted scouting reports.
- Identify team weaknesses.
- Recommend recruitment requirements.

## 2.3 Individual platform users

### Player

- Maintain personal profile.
- Update permitted personal information.
- Upload relevant documents.
- View their career information.
- Track their performance history.
- Manage visibility preferences.

### Football Agent

- Maintain agent profile.
- Manage represented players.
- View permitted opportunities.
- Communicate with clubs where authorized.
- Track recruitment and transfer discussions.

## 2.4 Authorization requirements

Implement:
- Role-based permissions.
- Organization-level data isolation.
- Resource ownership checks.
- Permission checks on every backend operation.
- Separate platform and organization privileges.
- Audit records for sensitive actions.

Never rely on frontend hiding alone to enforce permissions.

The backend must independently authorize every request.

---

# 3. Main Application Modules

Develop the following modules independently, while keeping their data and workflows interconnected.

## Module 1: Authentication and User Management

Implement the complete authentication system.

Features:
- User registration.
- Login and logout.
- Password hashing.
- Access and refresh tokens.
- Token refresh and revocation.
- Password recovery.
- Email verification architecture.
- User profile management.
- Account status management.
- Session management.
- User invitations.

Initial authentication can use JWT access and refresh tokens.

Use secure password hashing such as Argon2 or bcrypt.

## Module 2: Organization and Club Management

The platform must support multiple independent organizations.

Features:
- Create organizations.
- Register football clubs.
- Edit club profiles.
- Club logos and images.
- Club location and country.
- Club description.
- Club contact information.
- Organization membership.
- Member invitations.
- Role assignment.
- Team and department management.
- Organization settings.

Each organization must have its own membership, operational data, and permissions.

A club can have multiple teams, such as:
- Senior team.
- U23 team.
- U19 team.
- Academy team.
- Women's team.

Do not assume that a user can belong to only one organization.

## Module 3: Player Management

Create a centralized player directory.

Player information should include:

**Basic information**
- Full name.
- Date of birth.
- Nationality.
- Profile picture.
- Height.
- Weight.
- Preferred foot.
- Current playing position.
- Secondary positions.
- Biography.

**Football information**
- Current club.
- Current team.
- Previous clubs.
- Career history.
- Competition history.
- Match appearances.
- Goals.
- Assists.
- Other position-relevant statistics.

**Recruitment information**
- Contract status.
- Contract expiry date.
- Transfer availability.
- Estimated market value.
- Player availability.
- Representation/agent information where authorized.

**Additional information**
- Injury and availability history, with restricted access.
- Uploaded documents.
- Videos and performance evidence.
- Scout evaluations.
- Development history.

Important distinction:

A player is a global football entity, while their membership in a club or team is a separate relationship.

A player must be able to move between clubs without creating duplicate player records.

Implement player identity management and duplicate detection.

## Module 4: Team and Squad Management

Features:
- Create teams.
- Add and remove players.
- Assign squad numbers.
- Assign positions.
- Record player registration dates.
- Track squad availability.
- View squad composition.
- Track team history.

Provide squad visualizations and position-based filters.

## Module 5: Scout Management

Features:
- Scout profiles.
- Scout experience and specializations.
- Areas of operation.
- Preferred age groups.
- Preferred positions.
- Assigned competitions.
- Assigned matches.
- Assignment history.
- Performance statistics.
- Report submission history.

A scout should have an assignment dashboard displaying:
- Pending assignments.
- Completed assignments.
- Upcoming matches.
- Overdue reports.
- Recently evaluated players.

## Module 6: Competition and Match Management

Implement football competitions and match records.

Competition information:
- Name.
- Country.
- Season.
- Competition type.
- Participating clubs.
- Start and end dates.

Match information:
- Home team.
- Away team.
- Competition.
- Match date.
- Venue.
- Final score.
- Match status.
- Match events.
- Match statistics.

Initially, match information can be entered manually by administrators.

External football data integrations can be introduced later.

## Module 7: Scouting Assignments

This module connects scouts, matches, and players.

Workflow:

1. Recruitment manager or club administrator creates an assignment.
2. Selects a scout.
3. Selects a match, competition, or individual player.
4. Adds instructions and evaluation criteria.
5. Assigns a deadline.
6. Scout receives a notification.
7. Scout completes the assignment.
8. Scout submits reports.
9. Recruitment manager reviews the submission.

Assignment statuses:

- Draft.
- Assigned.
- Accepted.
- In Progress.
- Submitted.
- Under Review.
- Approved.
- Rejected.
- Cancelled.

Maintain a complete assignment history.

## Module 8: Scouting Reports and Evaluations

This is one of the most important modules.

A scouting report should contain:

**General information**
- Player.
- Scout.
- Match.
- Club.
- Date observed.
- Position observed.

**Technical evaluation**
- Passing.
- Ball control.
- Dribbling.
- Shooting.
- First touch.
- Crossing.

**Physical evaluation**
- Speed.
- Acceleration.
- Strength.
- Stamina.
- Agility.

**Tactical evaluation**
- Positioning.
- Decision-making.
- Awareness.
- Defensive contribution.
- Movement.

**Mental evaluation**
- Work rate.
- Discipline.
- Confidence.
- Leadership.

**Written observations**
- Strengths.
- Weaknesses.
- Development areas.
- General observations.
- Final recommendation.

Use configurable rating scales, initially 1–10.

Recommendations:
- Strongly Recommend.
- Recommend.
- Monitor.
- Not Recommended.

Allow draft saving, submission, revision requests, approval, and report version history.

Important: Scout ratings are subjective evaluations. Do not mix them with objective match statistics.

## Module 9: Recruitment Management

Recruitment should be implemented as a structured workflow.

### Recruitment requirement

A recruitment manager creates a requirement containing:
- Position.
- Age range.
- Preferred nationality, optionally.
- Preferred foot.
- Minimum experience.
- Required attributes.
- Budget range.
- Contract requirements.
- Additional instructions.
- Priority.
- Status.

### Candidate discovery

Search for players matching the requirement.

Support:
- Structured filters.
- Statistical filtering.
- Scout rating filters.
- Club visibility restrictions.
- Availability filters.
- Text-based search.

### Recruitment pipeline

Candidate statuses:

1. Discovered.
2. Under Evaluation.
3. Shortlisted.
4. Scout Assigned.
5. Report Submitted.
6. Under Review.
7. Trial Proposed.
8. Negotiation.
9. Signed.
10. Rejected.
11. Archived.

Maintain a history of every status transition.

## Module 10: Shortlists and Player Comparisons

Shortlists should be organization-specific and private by default.

Features:
- Create shortlist.
- Add players.
- Remove players.
- Add internal notes.
- Set priority.
- Compare selected players.
- Share with authorized members.
- Track recruitment status.

Player comparison should include:
- Age.
- Position.
- Physical attributes.
- Objective statistics.
- Scout ratings.
- Recent performance.
- Contract status.
- Recruitment suitability.

Avoid ranking players using arbitrary unexplained formulas.

Any composite score should be configurable, transparent, and accompanied by its contributing metrics.

## Module 11: Contracts and Transfers

Features:
- Contract records.
- Contract start and expiry.
- Contract status.
- Transfer history.
- Transfer proposals.
- Negotiation records.
- Loan records.
- Transfer fees.
- Contract expiry notifications.
- Agent and representation information.

Restrict financial and contractual information to authorized users.

## Module 12: Trials and Recruitment Events

Features:
- Create trials.
- Select players.
- Assign coaches and evaluators.
- Set trial schedules.
- Record attendance.
- Submit trial evaluations.
- Record final decisions.
- Update recruitment pipeline.

## Module 13: Notifications

Implement an internal notification system.

Events:
- New assignment.
- Assignment deadline approaching.
- Report submitted.
- Report approved or rejected.
- Player shortlisted.
- Trial scheduled.
- Recruitment status updated.
- Contract expiry approaching.
- Organization invitation.

Features:
- Unread/read status.
- Notification history.
- Notification preferences.
- Real-time delivery using WebSockets.
- Background notification processing.

Email delivery can be integrated later.

## Module 14: Analytics and Reporting

Create dashboards for different roles.

### Platform dashboard
- Total organizations.
- Registered clubs.
- Registered players.
- Active scouts.
- Total assignments.
- Reports submitted.
- Platform activity.

### Club dashboard
- Total squads.
- Total players.
- Active scouts.
- Open assignments.
- Reports awaiting review.
- Recruitment pipeline.
- Upcoming trials.
- Contract expiries.

### Scout dashboard
- Total assignments.
- Completed assignments.
- Pending reports.
- Report acceptance rate.
- Recently evaluated players.

### Recruitment dashboard
- Active requirements.
- Candidates discovered.
- Shortlisted players.
- Players under evaluation.
- Trials scheduled.
- Successful recruitment.

Include date filters, charts, tables, and export functionality.

Use backend aggregations instead of calculating all analytics in the browser.

---

# 4. AI Agent System

The AI agent must be developed as a separate, well-defined subsystem integrated into the application.

It should operate as an intelligent assistant and an authorized application operator.

Use LangGraph for orchestration.

## 4.1 Agent architecture

Implement a single primary orchestrator initially.

The orchestrator receives:
- User message.
- Authenticated user ID.
- Organization context.
- Role and permissions.
- Conversation ID.
- Available tools.

The agent determines which tools are necessary, invokes them, interprets their results, and produces a response.

The agent must never receive unrestricted database credentials.

All operations must go through backend services.

## 4.2 Agent capabilities

### Capability A: Information retrieval

Examples:
- Find players under 21.
- Find all scouts in an organization.
- Retrieve a player's career history.
- Find recent scouting reports.
- Show pending assignments.
- Retrieve recruitment requirements.

### Capability B: Data analysis

Examples:
- Compare two players.
- Analyze a squad.
- Identify missing positions.
- Analyze scout productivity.
- Evaluate recruitment pipelines.
- Generate performance summaries.

### Capability C: Application operations

Examples:
- Create a player shortlist.
- Assign a scout to a match.
- Create a recruitment requirement.
- Create a draft scouting report.
- Update an assignment.
- Schedule a trial.
- Send a notification.

### Capability D: Document intelligence

Examples:
- Search scouting reports.
- Search uploaded documents.
- Summarize player evaluations.
- Compare observations from multiple scouts.
- Answer questions using document evidence.

### Capability E: External information retrieval

Later integration:
- Football news search.
- Competition information.
- Publicly available player information.
- External football statistics.

External information must be distinguished from verified platform records.

## 4.3 Agent tools

Create tools as typed backend functions with clear input and output schemas.

Suggested initial tool inventory:

**Player tools**
- `search_players`
- `get_player_profile`
- `get_player_career_history`
- `get_player_statistics`
- `compare_players`

**Club tools**
- `get_club_details`
- `search_clubs`
- `get_club_squad`
- `get_club_statistics`

**Scout tools**
- `search_scouts`
- `get_scout_profile`
- `get_scout_assignments`
- `get_scout_reports`

**Match tools**
- `search_matches`
- `get_match_details`
- `get_competition_details`

**Recruitment tools**
- `get_recruitment_requirements`
- `search_recruitment_candidates`
- `create_shortlist`
- `add_player_to_shortlist`
- `compare_shortlisted_players`
- `update_recruitment_status`

**Assignment tools**
- `create_scout_assignment`
- `assign_scout_to_match`
- `update_assignment`
- `get_pending_assignments`

**Report tools**
- `create_scout_report_draft`
- `get_scout_report`
- `search_scouting_reports`
- `submit_scout_report`

**Analytics tools**
- `analyze_squad`
- `analyze_scout_performance`
- `get_recruitment_analytics`
- `generate_club_report`

**Notification tools**
- `send_notification`
- `get_user_notifications`

Implement tools incrementally as their corresponding application modules become available.

## 4.4 Tool execution requirements

Every tool must:
- Have a defined input schema.
- Have a defined output schema.
- Validate input.
- Check authenticated user permissions.
- Apply organization-level restrictions.
- Handle errors consistently.
- Log execution details.
- Return structured results.

The LLM must never determine its own permissions.

The authenticated backend context must determine which records a user can access.

## 4.5 Human-in-the-loop approvals

Not every tool requires approval.

Classify tools into:

**Read-only**
- Search players.
- Retrieve reports.
- Compare statistics.
- View assignments.

These can execute immediately when authorized.

**Low-risk writes**
- Save a draft.
- Create an internal note.
- Add a player to a private shortlist.

These can follow configurable approval policies.

**Sensitive writes**
- Publish or approve a scouting report.
- Change player visibility.
- Assign or reassign scouts.
- Change recruitment status.
- Modify contractual information.

Require appropriate authorization and, where configured, confirmation.

**High-impact operations**
- Delete records.
- Suspend organizations.
- Execute financial or contractual operations.
- Perform irreversible actions.

Require explicit human authorization, strict validation, and audit logging.

Never allow an LLM-generated statement to count as user approval.

## 4.6 Agent conversation interface

Create a dedicated AI workspace.

Features:
- Conversation history.
- New conversation.
- Conversation titles.
- Streaming responses.
- Markdown rendering.
- Tables and structured results.
- Tool execution indicators.
- Tool result visibility.
- Approval cards.
- Error handling.
- Conversation search.
- Context management.

The user should be able to see when the agent is:
- Thinking.
- Searching the database.
- Analyzing statistics.
- Retrieving documents.
- Preparing an operation.
- Waiting for approval.
- Executing an operation.

## 4.7 Agent memory

Implement three distinct concepts:

1. Conversation history: previous messages and tool results.
2. User preferences: explicitly stored preferences relevant to future interactions.
3. Organizational knowledge: authorized scouting reports, uploaded documents, and other searchable records.

Do not confuse conversational memory with database truth.

Always retrieve current player, club, and assignment information from the backend rather than trusting old conversation messages.

## 4.8 RAG subsystem

Introduce RAG after the core application and agent tools work.

Document ingestion pipeline:

1. Upload document.
2. Validate file type and size.
3. Store original file.
4. Extract text.
5. Clean extracted text.
6. Chunk the text.
7. Generate embeddings.
8. Store chunks and metadata in Qdrant.
9. Retrieve relevant chunks during queries.
10. Generate responses with citations.

Initial document types:
- Scouting reports.
- Player evaluation documents.
- Club recruitment policies.
- Competition documents.
- Authorized player-related PDFs.

Use BGE-M3 embeddings and Qdrant as the initial vector search solution.

Include document ownership, organization ID, access permissions, and source references in metadata.

Retrieval must enforce access restrictions before returning document content.

## 4.9 Agent observability

Store:
- Conversation ID.
- User ID.
- Organization ID.
- Model name.
- Tool name.
- Tool arguments, with sensitive fields redacted.
- Execution duration.
- Token usage.
- Execution status.
- Error information.
- Approval status.

Provide an administrator interface for inspecting agent executions.

Never store passwords, secrets, or unnecessary sensitive information in logs.

---

# 5. Technical Architecture

Use a modular monolith initially.

Do not start with microservices. Keep the backend modular and establish clear service boundaries so components can be extracted later if needed.

## 5.1 Technology stack

### Frontend
- Next.js.
- React.
- TypeScript.
- Tailwind CSS.
- shadcn/ui.
- TanStack Query.
- React Hook Form.
- Zod.
- Recharts.
- Zustand where shared client state is needed.

### Backend
- Python.
- FastAPI.
- Pydantic.
- SQLAlchemy 2.x.
- Alembic.
- PostgreSQL.
- JWT authentication.

### AI subsystem
- LangGraph.
- LangChain where useful for integrations.
- Groq or OpenRouter for initial inference.
- BGE-M3 for embeddings.
- Qdrant for vector search.
- Server-Sent Events for agent response streaming.

### Infrastructure
- Redis.
- Celery for background jobs.
- Docker.
- Docker Compose.
- S3-compatible object storage.
- Nginx or a suitable production reverse proxy.

### Testing and quality
- Pytest.
- HTTPX.
- Vitest.
- Playwright.
- Ruff.
- ESLint.
- Prettier.

Infrastructure components are introduced phase by phase (see Section 0.5); the list above is the eventual target, not the Phase 0 scope.

Do not add Elasticsearch initially. PostgreSQL search and indexes should handle the initial use cases. Introduce a dedicated search engine only when justified by performance or search requirements.

## 5.2 System architecture

```text
                 USERS
                   |
                   v
          NEXT.JS FRONTEND
                   |
            HTTPS / SSE
                   |
                   v
             FASTAPI API
                   |
       AUTHENTICATION / RBAC
                   |
             APPLICATION
               SERVICES
                   |
       +-----------+-----------+
       |           |           |
       v           v           v
   PostgreSQL    Redis     Object Storage
       |
       |
  AGENT SUBSYSTEM
       |
       v
  LANGGRAPH ORCHESTRATOR
       |
       +--------+---------+
       |        |         |
       v        v         v
   DB Tools   RAG Tools  Analytics
       |        |         |
       v        v         v
  PostgreSQL  Qdrant   App Services
       |
       v
  LLM PROVIDER
```

The agent must invoke application services, not bypass them.

## 5.3 API conventions

Use REST APIs with a consistent prefix:

`/api/v1/`

Examples:

```text
/api/v1/auth/login
/api/v1/auth/refresh

/api/v1/users
/api/v1/organizations
/api/v1/clubs
/api/v1/teams

/api/v1/players
/api/v1/players/{player_id}/statistics
/api/v1/players/{player_id}/career

/api/v1/scouts
/api/v1/assignments
/api/v1/scouting-reports

/api/v1/competitions
/api/v1/matches

/api/v1/recruitment/requirements
/api/v1/recruitment/shortlists
/api/v1/recruitment/trials

/api/v1/contracts
/api/v1/transfers

/api/v1/analytics
/api/v1/notifications

/api/v1/agent/conversations
/api/v1/agent/conversations/{conversation_id}/messages
/api/v1/agent/approvals
/api/v1/agent/executions
```

Use:
- Appropriate HTTP methods.
- Consistent status codes.
- Request validation.
- Pagination.
- Filtering.
- Sorting.
- Structured error responses.
- API documentation through OpenAPI.

---

# 6. Database Architecture

Use PostgreSQL as the primary source of truth.

Design the schema before implementing business modules.

## 6.1 Core entities

### Identity and organizations
- users
- user_sessions
- organizations
- organization_members
- roles
- permissions
- role_permissions
- invitations

### Clubs and teams
- clubs
- club_settings
- teams
- team_players

### Players
- players
- player_positions
- player_career_history
- player_statistics
- player_media
- player_documents
- player_availability

### Scouts
- scout_profiles
- scout_specializations
- scout_assignments

### Matches
- competitions
- competition_seasons
- competition_participants
- matches
- match_events
- match_statistics

### Evaluations
- scouting_reports
- scouting_report_ratings
- scouting_report_versions
- scouting_report_reviews

### Recruitment
- recruitment_requirements
- recruitment_candidates
- shortlists
- shortlist_players
- recruitment_stage_history
- trials
- trial_participants
- trial_evaluations

### Contracts and transfers
- contracts
- transfers
- transfer_proposals
- negotiations
- agents
- player_representatives

### Platform infrastructure
- notifications
- audit_logs
- uploaded_files
- conversations
- conversation_messages
- agent_executions
- agent_approvals
- document_chunks_metadata

## 6.2 Database design rules

- Use UUID primary keys.
- Use timezone-aware timestamps.
- Add created_at and updated_at where appropriate.
- Define explicit foreign keys.
- Add appropriate indexes.
- Use database constraints.
- Use Alembic migrations.
- Avoid storing relational data as arbitrary JSON.
- Use JSONB only for genuinely flexible attributes.
- Maintain referential integrity.
- Use transactions for multi-step operations.

## 6.3 Multi-tenancy

Use shared PostgreSQL infrastructure with organization-level data ownership.

For organization-specific records, include organization_id.

For global records such as canonical player identities, use explicit visibility and ownership relationships rather than assuming every record belongs to one organization.

Implement authorization in the service/repository layer.

Consider PostgreSQL Row-Level Security as an additional defense-in-depth measure.

Never assume that filtering in the frontend is sufficient.

---

# 7. Frontend Application Structure

Build a professional SaaS dashboard with a consistent design system.

Suggested design direction:
- Dark navy or neutral dashboard surfaces.
- Blue/teal accents.
- Clean typography.
- Data-dense but readable tables.
- Consistent spacing.
- Responsive layouts.
- Accessible controls.

Do not build every page as a separate disconnected design.

Create reusable components.

## 7.1 Main navigation

Sidebar:

```text
SCOUTSPHERE

Overview

ORGANIZATION
  Clubs
  Teams
  Players
  Scouts

SCOUTING
  Assignments
  Matches
  Scouting Reports
  Evaluations

RECRUITMENT
  Requirements
  Shortlists
  Trials
  Transfers
  Contracts

INTELLIGENCE
  Analytics
  Reports
  AI Workspace

SYSTEM
  Notifications
  Settings
  User Management
```

Navigation must be role-aware.

## 7.2 Required frontend pages

### Public pages
- Landing page.
- Login.
- Registration.
- Forgot password.
- Organization onboarding.

### Application pages
- Dashboard.
- Player directory.
- Player details.
- Club directory.
- Club details.
- Team details.
- Scout directory.
- Scout profile.
- Match directory.
- Match details.
- Assignment management.
- Scouting report editor.
- Report details.
- Recruitment requirements.
- Shortlist details.
- Player comparison.
- Trial management.
- Transfer management.
- Contract management.
- Analytics.
- Notifications.
- AI workspace.
- Settings.
- User management.

### Platform admin pages
- Organization directory.
- Platform users.
- Platform analytics.
- Audit logs.
- Agent execution monitoring.
- Platform configuration.

## 7.3 Reusable UI components

Build reusable components for:
- Sidebar.
- Header.
- Breadcrumbs.
- Data tables.
- Search bars.
- Filter panels.
- Pagination.
- Modals.
- Confirmation dialogs.
- Forms.
- Status badges.
- Player cards.
- Scout cards.
- Statistics cards.
- Charts.
- Empty states.
- Loading states.
- Error states.
- Toast notifications.
- File uploaders.
- AI tool execution cards.

---

# 8. Demo Data and Initial Business Environment

The project must be usable without relying on external commercial sports APIs.

Create a realistic demo environment.

## 8.1 Initial seed data

Recommended initial dataset:

| Entity | Suggested records |
|---|---:|
| Organizations | 10 |
| Football clubs | 50 |
| Users | 150 |
| Scouts | 100 |
| Players | 5,000 |
| Teams | 100 |
| Competitions | 20 |
| Matches | 1,000 |
| Scouting reports | 2,000 |
| Recruitment requirements | 100 |
| Shortlists | 100 |

These are development targets, not hard database limits.

Generate internally consistent synthetic records.

Examples:
- Clubs should belong to valid organizations.
- Teams should belong to valid clubs.
- Player career histories should contain plausible chronological club memberships.
- Assignments should connect valid scouts and matches.
- Reports should connect valid players, scouts, and matches.
- Recruitment requirements should have realistic filters.
- Recruitment stages should have consistent histories.

Use Faker and custom seed scripts.

Never use fabricated demo data in a way that implies it represents real verified football records.

## 8.2 Demo accounts

Create seed accounts for:
- Platform super admin.
- Club owner.
- Club administrator.
- Recruitment manager.
- Scout.
- Coach.
- Player.
- Football agent.

Provide credentials only in local development documentation.

Use safe, non-production seed passwords.

---

# 9. Security and Reliability

Security must be built into the architecture from the beginning.

Requirements:

1. Password hashing.
2. Secure JWT handling.
3. Token expiration and refresh.
4. Authorization on every protected endpoint.
5. Organization-level isolation.
6. Input validation.
7. SQL injection protection through parameterized queries and ORM usage.
8. Rate limiting.
9. CORS configuration.
10. Secure file uploads.
11. File type and size validation.
12. Audit logs.
13. Sensitive-data redaction.
14. Secret management through environment variables.
15. Protection against unauthorized agent tool calls.
16. Protection against prompt injection in uploaded documents and retrieved content.
17. Human approval for consequential operations.
18. Transactional consistency for multi-step business operations.

For agent security:
- Treat retrieved documents as untrusted data.
- Never let documents redefine agent instructions.
- Never let the model bypass backend authorization.
- Validate all tool arguments.
- Enforce permissions at execution time.
- Make sensitive operations idempotent where possible.
- Log the actor, action, target, and outcome.

---

# 10. Testing Strategy

Every module must have tests before being considered complete.

## Backend tests
- Unit tests for services.
- API endpoint tests.
- Authentication tests.
- Permission tests.
- Organization isolation tests.
- Database integrity tests.
- Transaction tests.
- Error handling tests.

## Frontend tests
- Component tests.
- Form validation tests.
- Navigation tests.
- API integration tests.
- Role-based UI tests.

## End-to-end tests

Test complete business workflows.

Example:

1. Create organization.
2. Create club.
3. Invite recruitment manager.
4. Add players.
5. Create a recruitment requirement.
6. Find candidates.
7. Create shortlist.
8. Assign scout.
9. Submit scouting report.
10. Review report.
11. Move candidate to trial.
12. Complete trial evaluation.

## AI agent tests

Test:
- Correct tool selection.
- Correct tool arguments.
- Permission enforcement.
- Invalid tool arguments.
- Tool failure recovery.
- Multi-step workflows.
- Confirmation handling.
- Conversation persistence.
- Retrieval relevance.
- Prompt injection resistance.
- Grounded responses.

Agent tests must use mocked LLM responses where deterministic behavior is needed.

---

# 11. Deployment and DevOps

Use Docker Compose for local development.

Suggested services:

```text
frontend
backend
postgres
redis
worker
qdrant
```

Add object storage when the document module is introduced.

Development should support:

```bash
docker compose up --build
```

Recommended environments:
- Local development.
- Testing.
- Staging.
- Production.

Implement:
- Environment-specific configuration.
- Database migrations.
- Health checks.
- Structured logging.
- Automated testing.
- CI/CD.
- Database backup strategy.
- Error monitoring.

Do not expose PostgreSQL, Redis, or Qdrant publicly without appropriate network and authentication controls.

---

# 12. Module-by-Module Development Roadmap

The following is the actual implementation sequence.

Do not instruct the coding agent to implement all modules at once.

## Phase 0 — Project foundation

Deliverables:
- Repository initialization.
- Architecture documentation.
- Development conventions.
- Frontend project.
- Backend project.
- Docker Compose.
- PostgreSQL connection.
- Redis connection.
- Environment configuration.
- Health-check endpoints.
- Initial CI pipeline.

Acceptance criteria:
- Entire project starts locally.
- Frontend communicates with backend.
- Backend connects to PostgreSQL.
- Database migrations work.
- Health endpoints return valid results.

## Phase 1 — Authentication and RBAC

Deliverables:
- User model.
- Registration.
- Login.
- Logout.
- JWT authentication.
- Refresh token flow.
- Roles and permissions.
- Organization membership foundation.
- Protected frontend routes.
- Backend permission dependencies.

Acceptance criteria:
- Users can authenticate.
- Protected routes reject unauthenticated requests.
- Different roles have different permissions.
- Invalid tokens are rejected.
- Tests verify authorization.

## Phase 2 — Organizations and Clubs

Deliverables:
- Organization CRUD.
- Club CRUD.
- Membership management.
- Invitations.
- Club profiles.
- Organization dashboards.
- Organization isolation.

Acceptance criteria:
- Multiple organizations can exist.
- Users can belong to multiple organizations.
- Unauthorized organizations cannot access private records.
- Organization administrators can manage authorized members.

## Phase 3 — Players and Teams

Deliverables:
- Player CRUD.
- Global player identity.
- Team management.
- Player-team relationships.
- Career history.
- Position management.
- Player search and filters.
- Player profile pages.
- Player media and document metadata.

Acceptance criteria:
- Players can be managed.
- Players can move between teams and clubs.
- Duplicate detection works.
- Player history is preserved.
- Search and pagination work.

## Phase 4 — Scouts and Competitions

Deliverables:
- Scout profiles.
- Scout specializations.
- Competition management.
- Season management.
- Match management.
- Match statistics.
- Scout directory.
- Scout detail pages.

Acceptance criteria:
- Scouts can be registered.
- Competitions and matches can be created.
- Match and competition relationships are consistent.
- Scout profiles can be searched.

## Phase 5 — Assignments and Scouting Reports

Deliverables:
- Assignment creation.
- Scout assignment workflow.
- Notifications.
- Scouting report forms.
- Rating system.
- Report submission.
- Report reviews.
- Report history.

Acceptance criteria:
- Scouts can see only authorized assignments.
- Reports can be submitted.
- Recruitment managers can review reports.
- Report versions are preserved.
- Status transitions are validated.

## Phase 6 — Recruitment and Shortlists

Deliverables:
- Recruitment requirements.
- Candidate discovery.
- Candidate matching filters.
- Shortlists.
- Player comparisons.
- Recruitment pipeline.
- Status history.

Acceptance criteria:
- Recruitment managers can create requirements.
- Candidates can be discovered.
- Players can be shortlisted.
- Comparisons show meaningful statistics.
- Recruitment transitions are recorded.

## Phase 7 — AI Agent Foundation (read-only)

Deliverables:
- Agent module and `AuthContext`-based tool context.
- LLM provider abstraction (with mock provider for tests).
- LangGraph orchestrator with Postgres checkpointer.
- Conversation persistence.
- SSE streaming to the frontend.
- AI workspace page (conversation list, streaming, tool execution cards).
- Read-only tools for modules that already exist:
  `search_players`, `get_player_profile`, `get_player_career_history`, `get_club_squad`,
  `search_scouts`, `get_scout_assignments`, `get_scout_reports`, `search_scouting_reports`,
  `get_recruitment_requirements`, `compare_players`, `search_matches`.
- Tool execution logs (`agent_executions`) and an admin inspection view.

Acceptance criteria:
- User can chat with the agent and responses stream.
- Agent retrieves real database records.
- Tool calls respect the user's permissions and organization.
- Conversations persist; tool execution is observable.
- Tests with a mocked LLM cover tool selection, permission denial and invalid arguments.

## Phase 8 — Agent Operations and Approvals

Deliverables:
- Write tools: `create_shortlist`, `add_player_to_shortlist`, `create_recruitment_requirement`,
  `create_scout_assignment`, `assign_scout_to_match`, `update_assignment`,
  `create_scout_report_draft`, `update_recruitment_status`, `send_notification`.
- Risk classification (read / low-risk write / sensitive write / high-impact) enforced in code.
- Approval mechanism (LangGraph interrupt + approvals API + approval cards in the UI).
- Idempotency keys, operation tracking, tool error recovery.
- Multi-step workflows: find candidates and create a shortlist; assign a scout to a match;
  create a requirement; analyze a squad and propose recruitment actions.

Acceptance criteria:
- The core demo prompt (Section 16) works end to end.
- Unauthorized operations are rejected at execution time.
- Sensitive actions require approval bound to the exact arguments.
- Every operation is auditable; failed operations leave no inconsistent data.

## Phase 9 — Analytics and Lightweight Trials (completes the MVP)

Deliverables:
- Club, scout, recruitment and platform dashboards using backend aggregations.
- Date filters, charts, CSV export.
- Basic trials: create trial, select players, record attendance and a single evaluation, record the decision, update the recruitment pipeline.
- Analytics agent tools: `analyze_squad`, `analyze_scout_performance`, `get_recruitment_analytics`.

Acceptance criteria:
- Dashboards use real data and are role-aware.
- Exports match the underlying data.
- The full scenario in Section 16 can be completed through the UI and through the agent.

## Phase 10 — Contracts and Transfers

Deliverables:
- Contract records, expiry notifications, transfer history and proposals, negotiation records, loans, agent/representation relationships.
- Extended trial features (multiple evaluators, schedules).

Acceptance criteria:
- Contracts and transfers are tracked with history.
- Financial and contractual data is restricted to authorized roles (and verified by tests).
- Contract changes through the agent are always approval-gated.

## Phase 11 — RAG and Document Intelligence

Deliverables:
- Document upload with validation, object storage, text extraction, cleaning, chunking, embeddings, Qdrant indexing.
- Semantic (and hybrid, where useful) retrieval with citations.
- Organization- and role-level document permissions enforced before content is returned.
- Prompt-injection defenses: retrieved text is untrusted data and never alters agent instructions.

Acceptance criteria:
- Authorized documents can be indexed and queried; answers cite sources.
- Unauthorized documents never appear in retrieval results (tested).

## Phase 12 — Production Readiness

Deliverables:
- Security review.
- Performance testing.
- Database optimization.
- Frontend polish.
- Automated test coverage.
- Logging and monitoring.
- Deployment configuration.
- Backups.
- CI/CD.
- Documentation.

Acceptance criteria:
- Critical workflows pass end-to-end tests.
- Authorization and tenant-isolation tests pass.
- Production configuration is documented.
- Deployment and recovery procedures are documented.

---

# 13. Repository Structure

Use a monorepo initially.

Suggested structure:

```text
scoutsphere/
│
├── frontend/
│   ├── app/
│   ├── components/
│   │   ├── ui/
│   │   ├── layout/
│   │   ├── players/
│   │   ├── clubs/
│   │   ├── scouts/
│   │   ├── recruitment/
│   │   └── agent/
│   ├── features/
│   ├── hooks/
│   ├── lib/
│   ├── services/
│   ├── types/
│   └── tests/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── repositories/
│   │   ├── services/
│   │   ├── permissions/
│   │   ├── modules/
│   │   │   ├── auth/
│   │   │   ├── organizations/
│   │   │   ├── clubs/
│   │   │   ├── players/
│   │   │   ├── teams/
│   │   │   ├── scouts/
│   │   │   ├── competitions/
│   │   │   ├── matches/
│   │   │   ├── assignments/
│   │   │   ├── scouting_reports/
│   │   │   ├── recruitment/
│   │   │   ├── transfers/
│   │   │   ├── trials/
│   │   │   ├── analytics/
│   │   │   ├── notifications/
│   │   │   └── agent/
│   │   ├── workers/
│   │   └── main.py
│   │
│   ├── alembic/
│   └── tests/
│
├── infrastructure/
│   ├── docker/
│   └── scripts/
│
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── DATABASE_SCHEMA.md
│   ├── API_CONVENTIONS.md
│   ├── RBAC.md
│   ├── AGENT_DESIGN.md
│   └── DEVELOPMENT_ROADMAP.md
│
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

Keep business logic inside services, not route handlers.

Keep database access separate from API controllers.

Avoid circular dependencies between modules.

The agent should use the same application services as the normal API wherever possible.

---

# 14. Coding Agent Development Instructions

These instructions are mandatory throughout development.

## 14.1 Development behavior

1. Read the project documentation before implementing anything.
2. Inspect the existing repository before creating files.
3. Follow the established architecture.
4. Implement one module at a time.
5. Do not generate the entire application in one response.
6. Do not skip database design.
7. Do not create fake API responses to make pages appear functional.
8. Connect frontend pages to actual backend APIs.
9. Use real database persistence.
10. Implement proper error handling.
11. Write tests alongside implementation.
12. Update documentation when architecture or APIs change.
13. Avoid unnecessary dependencies.
14. Avoid premature microservices.
15. Keep components and services modular.
16. Never hardcode API keys, passwords, or secrets.
17. Do not silently change existing database schemas.
18. Use Alembic migrations for database changes.
19. Do not delete existing functionality when adding new modules.
20. Ask for clarification when a major business rule is ambiguous rather than inventing one.

## 14.2 Module completion protocol

For each module, the coding agent must:

**Step 1: Analyze**
- Understand requirements.
- Inspect existing modules.
- Identify dependencies.
- Identify affected database entities.

**Step 2: Design**
- Define models.
- Define schemas.
- Define APIs.
- Define services.
- Define permissions.
- Define frontend pages.

**Step 3: Implement backend**
- Database models.
- Migrations.
- Repositories.
- Services.
- API routes.
- Validation.
- Authorization.

**Step 4: Implement frontend**
- Pages.
- Components.
- Forms.
- API integration.
- Loading and error states.
- Role-aware navigation.

**Step 5: Test**
- Unit tests.
- API tests.
- Permission tests.
- Integration tests.
- Relevant end-to-end tests.

**Step 6: Document**
- API endpoints.
- Database changes.
- Setup instructions.
- Known limitations.

**Step 7: Verify**
- Run the application.
- Run migrations.
- Execute tests.
- Fix regressions.
- Confirm acceptance criteria.

Only then mark the module complete.

## 14.3 Git workflow

Initialize a git repository in Phase 0 (the project folder is not one yet). Use `main` plus short-lived feature branches; a separate `develop` branch is unnecessary for a small team.

Examples:

```bash
main
feature/authentication
feature/organization-management
feature/player-management
feature/scout-management
feature/ai-agent
```

Make small, meaningful commits.

Do not work directly on main.

---

# 15. Initial Scope and Priorities

Although the complete platform has many modules, the first usable version should focus on a coherent business workflow.

### MVP must include

- Authentication.
- Multiple organizations.
- Club management.
- User roles and permissions.
- Player directory.
- Team management.
- Scout management.
- Match management.
- Scout assignments.
- Scouting reports.
- Recruitment requirements.
- Shortlists.
- Basic analytics.
- Lightweight trials (needed by the Section 16 scenario).
- AI assistant with read tools and approval-gated write tools (shortlists, assignments, requirements).

### Later enhancements

- Contracts and transfer negotiations.
- Advanced trial management.
- Advanced player statistics.
- Video analysis.
- External football data APIs.
- Advanced RAG.
- Specialized subagents.
- Advanced predictive player evaluation.
- Mobile application.

Do not delay the first usable product by implementing every advanced feature upfront.

---

# 16. Definition of Success

The project should ultimately demonstrate the following complete scenario:

1. A platform administrator registers an organization.
2. The organization creates a football club.
3. The club owner invites recruitment managers and scouts.
4. The club registers its squads.
5. Players are added to the centralized player directory.
6. The recruitment manager creates a requirement for a young attacking midfielder.
7. The system discovers matching players.
8. The recruitment manager creates a shortlist.
9. A scout is assigned to evaluate selected players.
10. The scout attends a match and submits scouting reports.
11. The recruitment manager reviews the reports.
12. The club compares candidates.
13. The club schedules a trial.
14. The coach submits a trial evaluation.
15. The recruitment manager advances the selected candidate.
16. The club records the resulting recruitment decision.

At multiple stages, the AI agent should be capable of helping users perform these operations through natural language.

For example:

"Find five attacking midfielders under 23 with strong passing and ball control, compare them against our current squad, and prepare a shortlist."

The agent should:
- Interpret the request.
- Retrieve real player records.
- Apply filters.
- Analyze available evidence.
- Compare candidates.
- Prepare the shortlist.
- Ask for confirmation if required.
- Execute the authorized operation.
- Return a summary with links to the created records.

This is the core demonstration of ScoutSphere.

---

# 17. First Task for the Coding Agent

Do not start implementing all the business modules yet.

Start with **Phase 0: Project Foundation and Architecture**.

Your first assignment is:

1. Inspect the development environment (Docker, Node, Python versions).
2. Initialize the git repository and monorepo; move this document into `docs/PRD.md`.
3. Create the frontend using Next.js, React, and TypeScript.
4. Create the backend using FastAPI.
5. Configure PostgreSQL and Redis through Docker Compose.
6. Configure SQLAlchemy and Alembic.
7. Establish environment configuration.
8. Create backend health-check endpoints.
9. Establish frontend-to-backend communication.
10. Add initial automated testing.
11. Write the architecture and development documentation.
12. Run everything locally and verify it works.

Also in Phase 0: create `docs/DATABASE_SCHEMA.md` with the full entity design (the schema is designed before business modules are built), and `docs/RBAC.md` with the role/permission matrix.

Before implementing the first business module, present:
- The completed repository structure.
- The architecture decisions.
- The Docker Compose configuration.
- The environment configuration.
- The initial database connection.
- The results of the initial tests.

Then wait for the next module assignment.

**Important:** Build the project incrementally. Preserve working functionality, maintain documentation, and never mark a feature complete until it has been implemented, tested, and verified.

---

**Final product objective:** ScoutSphere should be a fully functional multi-tenant sports scouting and talent intelligence SaaS platform, with an integrated AI agent that can understand, analyze, and operate the platform through secure, auditable application tools.
