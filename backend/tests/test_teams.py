from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.player import Player
from tests.conftest import hdr
from tests.helpers import (
    API,
    add_role_member,
    make_club,
    make_player,
    make_team,
    setup_org,
)


async def squad(client, token, org, team, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    r = await client.get(f"{API}/teams/{team['id']}/squad?{q}", headers=hdr(token, org))
    assert r.status_code == 200, r.text
    return r.json()


async def career(client, token, org, player):
    return (
        await client.get(f"{API}/players/{player['id']}/career", headers=hdr(token, org))
    ).json()


async def test_team_crud(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    club = await make_club(client, token, org)
    team = await make_team(client, token, org, club, "First Team", "senior")
    assert team["club_name"] == "Alpha Senior" and team["active_players"] == 0

    r = await client.patch(
        f"{API}/teams/{team['id']}", json={"name": "Reserves", "team_type": "u23"}, headers=h
    )
    assert r.status_code == 200 and r.json()["team_type"] == "u23"
    assert (await client.get(f"{API}/teams?club_id={club['id']}", headers=h)).json()[0][
        "name"
    ] == "Reserves"
    assert (await client.delete(f"{API}/teams/{team['id']}", headers=h)).status_code == 204
    assert (await client.get(f"{API}/teams/{team['id']}", headers=h)).status_code == 404


async def test_team_validation_and_uniqueness(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    club = await make_club(client, token, org)
    await make_team(client, token, org, club, "U19")
    r = await client.post(f"{API}/teams", json={"club_id": club["id"], "name": "u19"}, headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "team_exists"
    assert (
        await client.post(
            f"{API}/teams",
            json={"club_id": club["id"], "name": "X", "team_type": "bogus"},
            headers=h,
        )
    ).status_code == 422
    assert (
        await client.post(f"{API}/teams", json={"club_id": club["id"], "name": ""}, headers=h)
    ).status_code == 422
    r = await client.post(
        f"{API}/teams",
        json={"club_id": "00000000-0000-0000-0000-000000000000", "name": "Y"},
        headers=h,
    )
    assert r.status_code == 422


async def test_team_must_belong_to_own_managed_club(client):
    ta, oa = await setup_org(client, "a@x.com", "Org A")
    tb, ob = await setup_org(client, "b@x.com", "Org B")
    club_b = await make_club(client, tb, ob, "B FC")
    r = await client.post(
        f"{API}/teams", json={"club_id": club_b["id"], "name": "Hijack"}, headers=hdr(ta, oa)
    )
    assert r.status_code == 422


async def test_squad_add_number_position_and_counts(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    club = await make_club(client, token, org)
    team = await make_team(client, token, org, club)
    gk = await make_player(client, token, org, "Gus Keeper", 28, primary_position="GK")
    st = await make_player(client, token, org, "Sam Striker", 23, primary_position="ST")
    base = f"{API}/teams/{team['id']}/players"

    r = await client.post(base, json={"player_id": gk["id"], "squad_number": 1}, headers=h)
    assert r.status_code == 201
    await client.post(
        base, json={"player_id": st["id"], "squad_number": 9, "position": "CF"}, headers=h
    )

    s = await squad(client, token, org, team)
    assert [(p["full_name"], p["squad_number"], p["position"]) for p in s["players"]] == [
        ("Gus Keeper", 1, "GK"), ("Sam Striker", 9, "CF"),
    ]  # fmt: skip
    assert s["counts_by_group"] == {"goalkeeper": 1, "defender": 0, "midfielder": 0, "forward": 1}
    assert [
        p["full_name"] for p in (await squad(client, token, org, team, group="forward"))["players"]
    ] == ["Sam Striker"]
    assert s["team"]["active_players"] == 2


async def test_squad_rules(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    club = await make_club(client, token, org)
    team = await make_team(client, token, org, club)
    a = await make_player(client, token, org, "Player A", 22)
    b = await make_player(client, token, org, "Player B", 22)
    base = f"{API}/teams/{team['id']}/players"
    await client.post(base, json={"player_id": a["id"], "squad_number": 7}, headers=h)

    r = await client.post(base, json={"player_id": b["id"], "squad_number": 7}, headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "squad_number_taken"
    r = await client.post(base, json={"player_id": a["id"], "squad_number": 8}, headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_in_squad"
    for bad in (0, 100, -3):
        assert (
            await client.post(base, json={"player_id": b["id"], "squad_number": bad}, headers=h)
        ).status_code == 422
    r = await client.post(
        base, json={"player_id": "00000000-0000-0000-0000-000000000000"}, headers=h
    )
    assert r.status_code == 422

    # changing numbers: cannot take a used one, can keep own, can take a free one
    mid_b = (
        await client.post(base, json={"player_id": b["id"], "squad_number": 11}, headers=h)
    ).json()
    mem_b = next(p["membership_id"] for p in mid_b["players"] if p["full_name"] == "Player B")
    url = f"{base}/{mem_b}"
    assert (await client.patch(url, json={"squad_number": 7}, headers=h)).status_code == 409
    assert (await client.patch(url, json={"squad_number": 11}, headers=h)).status_code == 200
    assert (
        await client.patch(url, json={"squad_number": 12, "position": "CAM"}, headers=h)
    ).status_code == 200


async def test_release_closes_history_and_frees_number(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    club = await make_club(client, token, org)
    team = await make_team(client, token, org, club)
    p = await make_player(client, token, org, "Moving Man", 24)
    s = (
        await client.post(
            f"{API}/teams/{team['id']}/players",
            json={"player_id": p["id"], "squad_number": 10},
            headers=h,
        )
    ).json()
    mem = s["players"][0]["membership_id"]

    spells = await career(client, token, org, p)
    assert (
        len(spells) == 1
        and spells[0]["club_name"] == "Alpha Senior"
        and spells[0]["end_date"] is None
    )
    assert spells[0]["team_label"] == "First Team" and spells[0]["managed_by_squad"] is True
    assert (await client.get(f"{API}/players/{p['id']}", headers=h)).json()["current_club"][
        "club_name"
    ] == "Alpha Senior"

    r = await client.delete(f"{API}/teams/{team['id']}/players/{mem}", headers=h)
    assert r.status_code == 200 and r.json()["players"] == []
    spells = await career(client, token, org, p)
    assert len(spells) == 1 and spells[0]["end_date"] is not None  # closed, not deleted
    assert (await client.get(f"{API}/players/{p['id']}", headers=h)).json()["current_club"] is None
    assert (
        len((await squad(client, token, org, team, include_left="true"))["players"]) == 1
    )  # history kept

    # the number is free again, and the same player can be re-registered
    b = await make_player(client, token, org, "New Ten", 20)
    assert (
        await client.post(
            f"{API}/teams/{team['id']}/players",
            json={"player_id": b["id"], "squad_number": 10},
            headers=h,
        )
    ).status_code == 201
    assert (
        await client.post(
            f"{API}/teams/{team['id']}/players", json={"player_id": p["id"]}, headers=h
        )
    ).status_code == 201
    assert (
        await client.delete(f"{API}/teams/{team['id']}/players/{mem}", headers=h)
    ).status_code == 404  # already left


async def test_player_moves_between_clubs_without_duplicates(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    club1 = await make_club(client, token, org, "Club One")
    club2 = await make_club(client, token, org, "Club Two")
    team1 = await make_team(client, token, org, club1, "Senior")
    team2 = await make_team(client, token, org, club2, "Senior")
    p = await make_player(client, token, org, "Journeyman", 26)

    s = (
        await client.post(
            f"{API}/teams/{team1['id']}/players",
            json={"player_id": p["id"], "squad_number": 5},
            headers=h,
        )
    ).json()
    mem = s["players"][0]["membership_id"]
    r = await client.post(
        f"{API}/teams/{team1['id']}/players/{mem}/transfer",
        json={"to_team_id": team2["id"], "squad_number": 8},
        headers=h,
    )
    assert r.status_code == 200
    assert [(x["full_name"], x["squad_number"]) for x in r.json()["players"]] == [("Journeyman", 8)]

    assert (await squad(client, token, org, team1))["players"] == []
    spells = await career(client, token, org, p)
    assert sorted(s["club_name"] for s in spells) == ["Club One", "Club Two"]
    open_spells = [s for s in spells if s["end_date"] is None]
    assert [s["club_name"] for s in open_spells] == ["Club Two"]
    assert (await client.get(f"{API}/players/{p['id']}", headers=h)).json()["current_club"][
        "club_name"
    ] == "Club Two"

    async with SessionLocal() as db:  # one player row, however many moves
        assert len((await db.scalars(select(Player))).all()) == 1

    assert (
        await client.post(
            f"{API}/teams/{team2['id']}/players/{r.json()['players'][0]['membership_id']}/transfer",
            json={"to_team_id": team2["id"]},
            headers=h,
        )
    ).status_code == 422


async def test_transfer_failure_rolls_back(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    club = await make_club(client, token, org)
    t1, t2 = (
        await make_team(client, token, org, club, "A"),
        await make_team(client, token, org, club, "B"),
    )
    p, q = (
        await make_player(client, token, org, "P One", 22),
        await make_player(client, token, org, "P Two", 22),
    )
    s = (
        await client.post(
            f"{API}/teams/{t1['id']}/players",
            json={"player_id": p["id"], "squad_number": 3},
            headers=h,
        )
    ).json()
    await client.post(
        f"{API}/teams/{t2['id']}/players", json={"player_id": q["id"], "squad_number": 4}, headers=h
    )

    r = await client.post(
        f"{API}/teams/{t1['id']}/players/{s['players'][0]['membership_id']}/transfer",
        json={"to_team_id": t2["id"], "squad_number": 4},
        headers=h,
    )  # number taken in the target team
    assert r.status_code == 409
    # nothing changed: still in team 1, still has an open spell
    assert [x["full_name"] for x in (await squad(client, token, org, t1))["players"]] == ["P One"]
    assert [sp["end_date"] for sp in await career(client, token, org, p)] == [None]


async def test_cannot_archive_team_or_player_while_registered(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    club = await make_club(client, token, org)
    team = await make_team(client, token, org, club)
    p = await make_player(client, token, org)
    s = (
        await client.post(
            f"{API}/teams/{team['id']}/players", json={"player_id": p["id"]}, headers=h
        )
    ).json()
    r = await client.delete(f"{API}/teams/{team['id']}", headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "team_has_players"
    r = await client.delete(f"{API}/players/{p['id']}", headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "player_in_squad"
    await client.delete(
        f"{API}/teams/{team['id']}/players/{s['players'][0]['membership_id']}", headers=h
    )
    assert (await client.delete(f"{API}/teams/{team['id']}", headers=h)).status_code == 204
    assert (await client.delete(f"{API}/players/{p['id']}", headers=h)).status_code == 204


async def test_squad_permissions_and_isolation(client):
    owner_t, org = await setup_org(client)
    club = await make_club(client, owner_t, org)
    team = await make_team(client, owner_t, org, club)
    p = await make_player(client, owner_t, org)
    scout_t = await add_role_member(client, org, "scout@x.com", "scout")
    coach_t = await add_role_member(client, org, "coach@x.com", "coach")
    rm_t = await add_role_member(client, org, "rm@x.com", "recruitment_manager")
    admin_t = await add_role_member(client, org, "admin@x.com", "club_admin")

    for t in (scout_t, coach_t, rm_t):  # can view squads, cannot change them
        assert (
            await client.get(f"{API}/teams/{team['id']}/squad", headers=hdr(t, org))
        ).status_code == 200
        assert (
            await client.post(
                f"{API}/teams/{team['id']}/players",
                json={"player_id": p["id"]},
                headers=hdr(t, org),
            )
        ).status_code == 403
        assert (
            await client.post(
                f"{API}/teams", json={"club_id": club["id"], "name": "X"}, headers=hdr(t, org)
            )
        ).status_code == 403
    assert (
        await client.post(
            f"{API}/teams/{team['id']}/players",
            json={"player_id": p["id"]},
            headers=hdr(admin_t, org),
        )
    ).status_code == 201

    other_t, other_org = await setup_org(client, "other@x.com", "Other Org")
    ho = hdr(other_t, other_org)
    assert (await client.get(f"{API}/teams/{team['id']}", headers=ho)).status_code == 404
    assert (await client.get(f"{API}/teams/{team['id']}/squad", headers=ho)).status_code == 404
    assert (await client.get(f"{API}/teams", headers=ho)).json() == []
    assert (await client.delete(f"{API}/teams/{team['id']}", headers=ho)).status_code == 404
