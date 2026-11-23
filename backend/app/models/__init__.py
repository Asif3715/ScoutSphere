"""Import every model module here so Alembic autogenerate sees it."""

from app.models.assignment import Assignment, AssignmentHistory
from app.models.audit import AuditLog
from app.models.club import Club
from app.models.competition import (
    Competition,
    CompetitionParticipant,
    CompetitionSeason,
    Match,
    MatchEvent,
    MatchStatistics,
)
from app.models.invitation import Invitation
from app.models.notification import Notification, NotificationPreference
from app.models.organization import Organization, OrganizationMember
from app.models.player import (  # noqa: F401
    Player,
    PlayerCareer,
    PlayerClaim,
    PlayerMedia,
    PlayerPosition,
)
from app.models.rbac import Permission, Role, RolePermission
from app.models.recruitment import (
    RecruitmentCandidate,
    RecruitmentRequirement,
    RecruitmentStageHistory,
    RequirementAttribute,
    Shortlist,
    ShortlistPlayer,
    ShortlistShare,
)
from app.models.report import (
    ScoutingReport,
    ScoutingReportRating,
    ScoutingReportReview,
    ScoutingReportVersion,
)
from app.models.scout import ScoutProfile, ScoutSpecialization
from app.models.team import Team, TeamPlayer
from app.models.user import User, UserSession

__all__ = [
    "Assignment",
    "AssignmentHistory",
    "AuditLog",
    "Notification",
    "NotificationPreference",
    "ScoutingReport",
    "ScoutingReportRating",
    "ScoutingReportReview",
    "ScoutingReportVersion",
    "Club",
    "Competition",
    "CompetitionParticipant",
    "CompetitionSeason",
    "Match",
    "MatchEvent",
    "MatchStatistics",
    "ScoutProfile",
    "ScoutSpecialization",
    "Invitation",
    "Organization",
    "OrganizationMember",
    "Permission",
    "Player",
    "RecruitmentCandidate",
    "RecruitmentRequirement",
    "RecruitmentStageHistory",
    "RequirementAttribute",
    "Shortlist",
    "ShortlistPlayer",
    "ShortlistShare",
    "PlayerCareer",
    "PlayerMedia",
    "PlayerPosition",
    "Role",
    "RolePermission",
    "Team",
    "TeamPlayer",
    "User",
    "UserSession",
]
