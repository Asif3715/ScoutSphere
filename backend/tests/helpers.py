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


# ---- scouting workflow -----------------------------------------------------------------
from datetime import UTC, datetime  # noqa: E402
from types import SimpleNamespace  # noqa: E402


def in_days(days: float) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


async def scouting_setup(client) -> SimpleNamespace:
    """Org with an owner, recruitment manager, scout (with profile), coach, a player and a match."""
    token, org, h, c1, c2, comp, season = await match_setup(client)
    rm_t = await add_role_member(client, org, "rm@x.com", "recruitment_manager")
    scout_t = await add_role_member(client, org, "scout@x.com", "scout")
    coach_t = await add_role_member(client, org, "coach@x.com", "coach")
    r = await client.post(f"{API}/scouts", json={"positions": ["CM"]}, headers=hdr(scout_t, org))
    assert r.status_code == 201, r.text
    player = await make_player(client, token, org, "Target Player", 20)
    match = await make_match(client, h, season, c1, c2)
    return SimpleNamespace(
        org=org, owner_t=token, owner_h=h, rm_t=rm_t, rm_h=hdr(rm_t, org), scout_t=scout_t,
        scout_h=hdr(scout_t, org), coach_t=coach_t, coach_h=hdr(coach_t, org),
        scout_id=r.json()["id"], player=player, match=match, comp=comp, season=season, c1=c1, c2=c2,
    )  # fmt: skip


async def make_assignment(
    client, s, target="match", *, headers=None, assign_now=True, **kw
) -> dict:
    target_id = {"match": s.match["id"], "player": s.player["id"], "competition": s.comp["id"]}[
        target
    ]
    body = {
        "scout_id": s.scout_id, "target_type": target, "target_id": target_id,
        "title": f"Watch the {target}", "deadline": in_days(3), "assign_now": assign_now, **kw,
    }  # fmt: skip
    r = await client.post(f"{API}/assignments", json=body, headers=headers or s.rm_h)
    assert r.status_code == 201, r.text
    return r.json()


async def move(client, headers, assignment, to, note=None):
    body = {"to": to, **({"note": note} if note else {})}
    return await client.post(
        f"{API}/assignments/{assignment['id']}/transition", json=body, headers=headers
    )


def full_ratings() -> dict:
    return {"passing": 8, "ball_control": 7, "dribbling": 6, "speed": 7, "positioning": 8}


def report_body(s, **kw) -> dict:
    return {
        "player_id": s.player["id"], "observed_on": datetime.now(UTC).date().isoformat(),
        "recommendation": "recommend", "general_observations": "Calm on the ball.",
        "strengths": "Passing range", "ratings": full_ratings(), **kw,
    }  # fmt: skip


async def make_report(client, s, headers=None, **kw) -> dict:
    r = await client.post(
        f"{API}/scouting-reports", json=report_body(s, **kw), headers=headers or s.scout_h
    )
    assert r.status_code == 201, r.text
    return r.json()


async def unread(client, token) -> int:
    r = await client.get(
        f"{API}/notifications/unread-count", headers={"Authorization": f"Bearer {token}"}
    )
    return r.json()["unread"]


async def notes(client, token, **params) -> list[dict]:
    r = await client.get(
        f"{API}/notifications", params=params, headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200, r.text
    return r.json()["items"]
