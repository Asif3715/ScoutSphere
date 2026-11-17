"""Football vocabulary shared by models, schemas and services.

Kept sport-specific on purpose and in one place so other sports can be added later
without touching business logic.
"""

from datetime import date

POSITION_GROUPS: dict[str, list[str]] = {
    "goalkeeper": ["GK"],
    "defender": ["CB", "LB", "RB", "LWB", "RWB"],
    "midfielder": ["CDM", "CM", "CAM", "LM", "RM"],
    "forward": ["LW", "RW", "CF", "ST"],
}
POSITIONS: list[str] = [p for group in POSITION_GROUPS.values() for p in group]
POSITION_TO_GROUP = {p: g for g, ps in POSITION_GROUPS.items() for p in ps}

FEET = ["left", "right", "both"]
VISIBILITIES = ["private", "network", "public"]
SPELL_TYPES = ["permanent", "loan", "youth", "trial"]
MEDIA_KINDS = ["video", "image", "document"]
TEAM_TYPES = [
    "senior", "u23", "u21", "u19", "u18", "u17", "u16", "academy", "womens", "other",
]  # fmt: skip

ADULT_AGE = 18


def age_on(dob: date, today: date | None = None) -> int:
    today = today or date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def is_minor(dob: date, today: date | None = None) -> bool:
    return age_on(dob, today) < ADULT_AGE


def dob_bounds_for_age(
    min_age: int | None, max_age: int | None, today: date | None = None
) -> tuple[date | None, date | None]:
    """Returns (earliest_dob, latest_dob) such that dob in [earliest, latest] <=> age in range."""
    today = today or date.today()

    def shift(years: int) -> date:
        try:
            return today.replace(year=today.year - years)
        except ValueError:  # 29 Feb
            return today.replace(year=today.year - years, day=28)

    earliest = latest = None
    if max_age is not None:  # age <= max  <=>  dob > today - (max+1) years
        from datetime import timedelta

        earliest = shift(max_age + 1) + timedelta(days=1)
    if min_age is not None:  # age >= min  <=>  dob <= today - min years
        latest = shift(min_age)
    return earliest, latest
