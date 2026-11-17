"""Shared builders for player/team tests."""

from datetime import date, timedelta

from tests.conftest import hdr
from tests.test_clubs import add_role_member, setup_org  # noqa: F401
from tests.test_organizations import API  # noqa: F401


def dob_for_age(age: int, extra_days: int = 30) -> str:
    """A date of birth that makes the person `age` today (extra_days past the birthday)."""
    today = date.today()
    try:
        d = today.replace(year=today.year - age)
    except ValueError:
        d = today.replace(year=today.year - age, day=28)
    return (d - timedelta(days=extra_days)).isoformat()


def player_body(name="Luka Novak", age=22, **kw) -> dict:
    return {
        "full_name": name,
        "date_of_birth": dob_for_age(age),
        "nationality": "Croatia",
        "primary_position": "CM",
        **kw,
    }


async def make_player(client, token, org, name="Luka Novak", age=22, **kw) -> dict:
    r = await client.post(
        f"{API}/players",
        json=player_body(name, age, allow_duplicate=True, **kw),
        headers=hdr(token, org),
    )
    assert r.status_code == 201, r.text
    return r.json()


async def make_club(client, token, org, name="Alpha Senior") -> dict:
    r = await client.post(f"{API}/clubs", json={"name": name}, headers=hdr(token, org))
    assert r.status_code == 201, r.text
    return r.json()


async def make_team(client, token, org, club, name="First Team", team_type="senior") -> dict:
    r = await client.post(
        f"{API}/teams",
        json={"club_id": club["id"], "name": name, "team_type": team_type},
        headers=hdr(token, org),
    )
    assert r.status_code == 201, r.text
    return r.json()
