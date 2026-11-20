"""Rules for recruitment requirements, the candidate pipeline and shortlists."""

PRIORITIES = ["low", "medium", "high", "urgent"]
REQUIREMENT_STATUSES = ["draft", "open", "on_hold", "fulfilled", "cancelled"]
REQUIREMENT_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"open", "cancelled"},
    "open": {"on_hold", "fulfilled", "cancelled"},
    "on_hold": {"open", "cancelled"},
    "fulfilled": set(),
    "cancelled": set(),
}

# The forward flow of a candidate, in order. `rejected` and `archived` can be entered from
# any active stage; both can only go back to `discovered` (re-opening).
STAGE_ORDER = [
    "discovered", "under_evaluation", "shortlisted", "scout_assigned", "report_submitted",
    "under_review", "trial_proposed", "negotiation", "signed",
]  # fmt: skip
OUT_STAGES = ["rejected", "archived"]
STAGES = STAGE_ORDER + OUT_STAGES
DEFAULT_STAGE = "discovered"


def can_move(current: str, target: str) -> bool:
    """Stage rules: no no-op moves; `signed` is final; `signed` is only reachable from
    `negotiation`; out-stages re-open to `discovered` only; everything else may move
    forwards, skip ahead or step back (to correct a mistake)."""
    if current == target or current == "signed":
        return False
    if current in OUT_STAGES:
        return target == "discovered"
    if target in OUT_STAGES:
        return True
    if target == "signed":
        return current == "negotiation"
    return True


MAX_COMPARE = 5
MIN_COMPARE = 2
