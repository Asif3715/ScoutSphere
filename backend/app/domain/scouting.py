"""Rules for assignments, scouting reports and notifications."""

RATING_MIN, RATING_MAX = 1, 10  # configurable scales are a later enhancement (PRD 8)

RATING_GROUPS: dict[str, list[str]] = {
    "technical": ["passing", "ball_control", "dribbling", "shooting", "first_touch", "crossing"],
    "physical": ["speed", "acceleration", "strength", "stamina", "agility"],
    "tactical": [
        "positioning", "decision_making", "awareness", "defensive_contribution", "movement",
    ],
    "mental": ["work_rate", "discipline", "confidence", "leadership"],
}  # fmt: skip
RATING_ATTRIBUTES: list[str] = [a for attrs in RATING_GROUPS.values() for a in attrs]
RECOMMENDATIONS = ["strongly_recommend", "recommend", "monitor", "not_recommended"]
MIN_RATINGS_TO_SUBMIT = 3

REPORT_STATUSES = ["draft", "submitted", "revision_requested", "approved", "rejected"]
REVIEW_DECISIONS = ["approved", "revision_requested", "rejected"]
EDITABLE_REPORT_STATUSES = {"draft", "revision_requested"}

ASSIGNMENT_STATUSES = [
    "draft", "assigned", "accepted", "in_progress", "submitted",
    "under_review", "approved", "rejected", "cancelled",
]  # fmt: skip
ASSIGNMENT_TARGETS = ["match", "competition", "player"]
OPEN_ASSIGNMENT_STATUSES = {"assigned", "accepted", "in_progress"}  # scout still has work to do

# status -> next statuses, by who may perform the move
MANAGER_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"assigned", "cancelled"},
    "assigned": {"cancelled"},
    "accepted": {"cancelled"},
    "in_progress": {"cancelled"},
    "submitted": {"under_review", "in_progress"},
    "under_review": {"approved", "rejected", "in_progress"},
}
SCOUT_TRANSITIONS: dict[str, set[str]] = {
    "assigned": {"accepted"},
    "accepted": {"in_progress"},
    "in_progress": {"submitted"},
}

NOTIFICATION_TYPES = [
    "assignment_assigned", "assignment_cancelled", "assignment_accepted", "assignment_submitted",
    "assignment_approved", "assignment_rejected", "assignment_returned", "assignment_deadline",
    "report_submitted", "report_approved", "report_rejected", "report_revision_requested",
    "recruitment_status_updated", "player_shortlisted", "shortlist_shared",
]  # fmt: skip
