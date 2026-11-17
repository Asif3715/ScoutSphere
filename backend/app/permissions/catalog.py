"""Single source of truth for permissions and role->permission mapping.

Roles and permissions are mirrored into the database by `sync_rbac` (idempotent, run at
startup), so adding a permission later is a code change, not a hand-written data migration.
Permission keys follow `resource:action`.
"""

# --- permissions (grow as modules arrive) -----------------------------------
ORG_READ = "org:read"
ORG_UPDATE = "org:update"
MEMBERS_READ = "members:read"
MEMBERS_MANAGE = "members:manage"  # invite / remove / change roles
CLUBS_READ = "clubs:read"
CLUBS_MANAGE = "clubs:manage"
SCOUTS_READ = "scouts:read"
SCOUTS_MANAGE = "scouts:manage"  # create/edit any scout profile
MATCHES_READ = "matches:read"  # competitions, seasons, matches
MATCHES_MANAGE = "matches:manage"
PLAYERS_READ = "players:read"
PLAYERS_WRITE = "players:write"
PLAYERS_MEDICAL_READ = "players:medical_read"
ASSIGNMENTS_READ = "assignments:read"
ASSIGNMENTS_MANAGE = "assignments:manage"
REPORTS_READ = "reports:read"
REPORTS_WRITE = "reports:write"  # own drafts / submit
REPORTS_REVIEW = "reports:review"  # approve / reject
RECRUITMENT_READ = "recruitment:read"
RECRUITMENT_MANAGE = "recruitment:manage"
TRIALS_READ = "trials:read"
TRIALS_MANAGE = "trials:manage"
TRIALS_EVALUATE = "trials:evaluate"
CONTRACTS_READ = "contracts:read"
CONTRACTS_MANAGE = "contracts:manage"
ANALYTICS_READ = "analytics:read"
AGENT_USE = "agent:use"

# platform-scope
PLATFORM_ORGS_MANAGE = "platform:orgs_manage"
PLATFORM_USERS_MANAGE = "platform:users_manage"
PLATFORM_AUDIT_READ = "platform:audit_read"
PLATFORM_AGENT_LOGS_READ = "platform:agent_logs_read"
PLATFORM_SUPPORT_VIEW = "platform:support_view"

ALL_ORG_PERMISSIONS = [
    ORG_READ, ORG_UPDATE, MEMBERS_READ, MEMBERS_MANAGE, CLUBS_READ, CLUBS_MANAGE,
    SCOUTS_READ,
    SCOUTS_MANAGE,
    MATCHES_READ,
    MATCHES_MANAGE,
    PLAYERS_READ, PLAYERS_WRITE, PLAYERS_MEDICAL_READ, ASSIGNMENTS_READ, ASSIGNMENTS_MANAGE,
    REPORTS_READ, REPORTS_WRITE, REPORTS_REVIEW, RECRUITMENT_READ, RECRUITMENT_MANAGE,
    TRIALS_READ, TRIALS_MANAGE, TRIALS_EVALUATE, CONTRACTS_READ, CONTRACTS_MANAGE,
    ANALYTICS_READ, AGENT_USE,
]  # fmt: skip

PLATFORM_PERMISSIONS = [
    PLATFORM_ORGS_MANAGE, PLATFORM_USERS_MANAGE, PLATFORM_AUDIT_READ,
    PLATFORM_AGENT_LOGS_READ, PLATFORM_SUPPORT_VIEW,
]  # fmt: skip

ALL_PERMISSIONS = ALL_ORG_PERMISSIONS + PLATFORM_PERMISSIONS

# --- roles --------------------------------------------------------------------
# key -> (display name, scope, permissions)
ROLES: dict[str, tuple[str, str, list[str]]] = {
    "club_owner": ("Club Owner", "organization", ALL_ORG_PERMISSIONS),
    "club_admin": (
        "Club Administrator",
        "organization",
        [p for p in ALL_ORG_PERMISSIONS if p != ORG_UPDATE],
    ),
    "recruitment_manager": (
        "Recruitment Manager",
        "organization",
        [
            ORG_READ,
            SCOUTS_READ,
            MATCHES_READ,
            MEMBERS_READ,
            CLUBS_READ,
            PLAYERS_READ,
            PLAYERS_WRITE,
            ASSIGNMENTS_READ,
            ASSIGNMENTS_MANAGE,
            REPORTS_READ,
            REPORTS_REVIEW,
            RECRUITMENT_READ,
            RECRUITMENT_MANAGE,
            TRIALS_READ,
            TRIALS_MANAGE,
            CONTRACTS_READ,
            CONTRACTS_MANAGE,
            ANALYTICS_READ,
            AGENT_USE,
        ],
    ),  # fmt: skip
    "scout": (
        "Scout",
        "organization",
        [
            ORG_READ,
            SCOUTS_READ,
            MATCHES_READ,
            CLUBS_READ,
            PLAYERS_READ,
            ASSIGNMENTS_READ,
            REPORTS_READ,
            REPORTS_WRITE,
            TRIALS_READ,
            ANALYTICS_READ,
            AGENT_USE,
        ],
    ),  # fmt: skip
    "coach": (
        "Coach",
        "organization",
        [
            ORG_READ,
            MATCHES_READ,
            CLUBS_READ,
            PLAYERS_READ,
            PLAYERS_MEDICAL_READ,
            ASSIGNMENTS_READ,
            REPORTS_READ,
            RECRUITMENT_READ,
            TRIALS_READ,
            TRIALS_EVALUATE,
            ANALYTICS_READ,
            AGENT_USE,
        ],
    ),  # fmt: skip
    "super_admin": ("Super Admin", "platform", PLATFORM_PERMISSIONS),
    # Support gets NO org-private access by default (PRD 0.2).
    "platform_support": ("Platform Support", "platform", [PLATFORM_SUPPORT_VIEW]),
}

PLATFORM_ROLES = {"super_admin", "platform_support"}
ORG_ROLES = {k for k, v in ROLES.items() if v[1] == "organization"}
