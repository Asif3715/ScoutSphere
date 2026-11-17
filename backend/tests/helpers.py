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


# ---- competitions / matches -----------------------------------------------------------
async def platform_headers(client, email="root@x.com") -> dict:
    from sqlalchemy.exc import IntegrityError

    from tests.conftest import login, make_user

    try:
        await make_user(email, platform_role="super_admin")
    except IntegrityError:  # already created earlier in the same test
        pass
    return {"Authorization": f"Bearer {await login(client, email)}"}


async def ref_club(client, ph, name) -> dict:
    r = await client.post(f"{API}/platform/clubs", json={"name": name}, headers=ph)
    assert r.status_code == 201, r.text
    return r.json()


async def make_comp(client, headers, name="Alpha League", **kw) -> dict:
    r = await client.post(f"{API}/competitions", json={"name": name, **kw}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def make_season(client, headers, comp, name="2025/26") -> dict:
    r = await client.post(
        f"{API}/competitions/{comp['id']}/seasons",
        json={"name": name, "start_date": "2025-08-01", "end_date": "2026-05-31"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def add_clubs(client, headers, season, *clubs):
    for c in clubs:
        r = await client.post(
            f"{API}/seasons/{season['id']}/participants", json={"club_id": c["id"]}, headers=headers
        )
        assert r.status_code == 201, r.text


async def make_match(client, headers, season, home, away, **kw) -> dict:
    body = {
        "season_id": season["id"], "home_club_id": home["id"], "away_club_id": away["id"],
        "kickoff_at": "2026-03-01T15:00:00Z", **kw,
    }  # fmt: skip
    r = await client.post(f"{API}/matches", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def match_setup(client, email="own@x.com", org_name="Alpha FC"):
    """Org with a private competition+season and two reference clubs registered in it."""
    token, org = await setup_org(client, email, org_name)
    h = hdr(token, org)
    ph = await platform_headers(client)
    c1, c2 = await ref_club(client, ph, "North United"), await ref_club(client, ph, "South Rovers")
    comp = await make_comp(client, h)
    season = await make_season(client, h, comp)
    await add_clubs(client, h, season, c1, c2)
    return token, org, h, c1, c2, comp, season
