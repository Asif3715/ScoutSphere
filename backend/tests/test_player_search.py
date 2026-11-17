from tests.conftest import hdr
from tests.helpers import API, make_club, make_player, make_team, setup_org


async def seed(client):
    token, org = await setup_org(client)
    specs = [
        ("Aaron Keeper", 30, "GK", "England", "right", 190, []),
        ("Ben Centre", 24, "CB", "England", "left", 188, ["LB"]),
        ("Carlos Mid", 19, "CM", "Spain", "right", 176, ["CAM"]),
        ("Diego Wing", 21, "LW", "Spain", "left", 172, ["RW"]),
        ("Emil Striker", 27, "ST", "Sweden", "both", 183, []),
    ]
    for name, age, pos, nat, foot, h, secs in specs:
        await make_player(
            client, token, org, name, age, primary_position=pos, nationality=nat,
            preferred_foot=foot, height_cm=h, secondary_positions=secs,
        )  # fmt: skip
    return token, org


async def names(client, token, org, query=""):
    r = await client.get(f"{API}/players?{query}", headers=hdr(token, org))
    assert r.status_code == 200, r.text
    return [p["full_name"] for p in r.json()["items"]], r.json()["total"]


async def test_text_search_and_wildcards(client):
    token, org = await seed(client)
    assert (await names(client, token, org, "q=aaron"))[0] == ["Aaron Keeper"]
    assert (await names(client, token, org, "q=ee"))[1] == 1  # Keeper
    assert (await names(client, token, org, "q=%25"))[1] == 0  # literal percent
    assert (await names(client, token, org, "q=_"))[1] == 0


async def test_position_and_group_filters_include_secondary_positions(client):
    token, org = await seed(client)
    assert (await names(client, token, org, "position=ST"))[0] == ["Emil Striker"]
    assert (await names(client, token, org, "position=LB"))[0] == ["Ben Centre"]  # secondary
    assert (await names(client, token, org, "group=goalkeeper"))[0] == ["Aaron Keeper"]
    assert sorted((await names(client, token, org, "group=forward"))[0]) == [
        "Diego Wing",
        "Emil Striker",
    ]
    assert (
        await client.get(f"{API}/players?position=XX", headers=hdr(token, org))
    ).status_code == 422
    assert (
        await client.get(f"{API}/players?group=striker", headers=hdr(token, org))
    ).status_code == 422


async def test_age_filters_are_exact(client):
    token, org = await seed(client)
    assert sorted((await names(client, token, org, "max_age=21"))[0]) == [
        "Carlos Mid",
        "Diego Wing",
    ]
    assert (await names(client, token, org, "min_age=30"))[0] == ["Aaron Keeper"]
    assert (await names(client, token, org, "min_age=21&max_age=24"))[0] == [
        "Ben Centre",
        "Diego Wing",
    ]
    assert (await names(client, token, org, "min_age=19&max_age=19"))[0] == ["Carlos Mid"]
    assert (await names(client, token, org, "min_age=40"))[1] == 0


async def test_other_filters(client):
    token, org = await seed(client)
    assert sorted((await names(client, token, org, "nationality=spain"))[0]) == [
        "Carlos Mid",
        "Diego Wing",
    ]
    assert sorted((await names(client, token, org, "foot=left"))[0]) == ["Ben Centre", "Diego Wing"]
    assert (await names(client, token, org, "min_height=189"))[0] == ["Aaron Keeper"]
    assert (await names(client, token, org, "max_height=172"))[0] == ["Diego Wing"]
    assert (await names(client, token, org, "nationality=england&foot=left"))[0] == ["Ben Centre"]


async def test_sorting_and_pagination(client):
    token, org = await seed(client)
    assert (await names(client, token, org, "sort=name"))[0][0] == "Aaron Keeper"
    assert (await names(client, token, org, "sort=age_asc"))[0][0] == "Carlos Mid"  # youngest
    assert (await names(client, token, org, "sort=age_desc"))[0][0] == "Aaron Keeper"

    seen = []
    for page in (1, 2, 3):
        got, total = await names(client, token, org, f"page={page}&page_size=2")
        assert total == 5
        seen += got
    assert len(seen) == 5 and len(set(seen)) == 5  # no duplicates, nothing missing
    assert (await names(client, token, org, "page=9&page_size=2"))[0] == []
    assert (
        await client.get(f"{API}/players?page_size=500", headers=hdr(token, org))
    ).status_code == 422
    assert (
        await client.get(f"{API}/players?sort=random", headers=hdr(token, org))
    ).status_code == 422


async def test_filter_by_club_and_team(client):
    token, org = await seed(client)
    h = hdr(token, org)
    club = await make_club(client, token, org)
    team = await make_team(client, token, org, club)
    pid = (await client.get(f"{API}/players?q=carlos", headers=h)).json()["items"][0]["id"]
    await client.post(f"{API}/teams/{team['id']}/players", json={"player_id": pid}, headers=h)

    assert (await names(client, token, org, f"club_id={club['id']}"))[0] == ["Carlos Mid"]
    assert (await names(client, token, org, f"team_id={team['id']}"))[0] == ["Carlos Mid"]
    summary = (await client.get(f"{API}/players?q=carlos", headers=h)).json()["items"][0]
    assert summary["current_club"]["club_name"] == "Alpha Senior"
