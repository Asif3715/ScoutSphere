"""Who can see (and edit) which players. This is the core privacy rule of the platform."""

from tests.conftest import hdr
from tests.helpers import (
    API,
    make_club,
    make_player,
    make_team,
    player_body,
    setup_org,
)


async def two_orgs(client):
    ta, oa = await setup_org(client, "a@x.com", "Org A")
    tb, ob = await setup_org(client, "b@x.com", "Org B")
    return ta, oa, tb, ob


async def visible_to_b(client, tb, ob, pid) -> int:
    return (await client.get(f"{API}/players/{pid}", headers=hdr(tb, ob))).status_code


async def test_private_player_invisible_to_other_orgs(client):
    ta, oa, tb, ob = await two_orgs(client)
    p = await make_player(client, ta, oa)  # default private
    assert await visible_to_b(client, tb, ob, p["id"]) == 404
    assert (await client.get(f"{API}/players", headers=hdr(tb, ob))).json()["total"] == 0
    assert (await client.get(f"{API}/players?q=luka", headers=hdr(tb, ob))).json()["total"] == 0
    for path in ("career", "media"):
        assert (
            await client.get(f"{API}/players/{p['id']}/{path}", headers=hdr(tb, ob))
        ).status_code == 404


async def test_network_and_public_players_are_visible_but_read_only(client):
    ta, oa, tb, ob = await two_orgs(client)
    net = await make_player(client, ta, oa, "Net Player", 24, visibility="network")
    pub = await make_player(client, ta, oa, "Pub Player", 24, visibility="public")
    hb = hdr(tb, ob)
    for p in (net, pub):
        r = await client.get(f"{API}/players/{p['id']}", headers=hb)
        assert r.status_code == 200 and r.json()["is_owner"] is False
        # but B can neither edit, archive nor edit the career of A's player
        assert (
            await client.patch(f"{API}/players/{p['id']}", json={"height_cm": 190}, headers=hb)
        ).status_code == 404
        assert (await client.delete(f"{API}/players/{p['id']}", headers=hb)).status_code == 404
        r = await client.post(
            f"{API}/players/{p['id']}/career",
            json={
                "club_id": (await make_club(client, tb, ob, f"B {p['full_name']}"))["id"],
                "start_date": "2020-01-01",
            },
            headers=hb,
        )
        assert r.status_code == 404
    assert (await client.get(f"{API}/players", headers=hb)).json()["total"] == 2


async def test_making_a_player_private_again_hides_it(client):
    ta, oa, tb, ob = await two_orgs(client)
    p = await make_player(client, ta, oa, visibility="network")
    assert await visible_to_b(client, tb, ob, p["id"]) == 200
    await client.patch(
        f"{API}/players/{p['id']}", json={"visibility": "private"}, headers=hdr(ta, oa)
    )
    assert await visible_to_b(client, tb, ob, p["id"]) == 404


async def test_squad_membership_grants_visibility_to_that_org(client):
    ta, oa, tb, ob = await two_orgs(client)
    p = await make_player(client, ta, oa, "Signed Player", 24, visibility="network")
    club = await make_club(client, tb, ob)
    team = await make_team(client, tb, ob, club)
    await client.post(
        f"{API}/teams/{team['id']}/players", json={"player_id": p["id"]}, headers=hdr(tb, ob)
    )

    # A switches the player back to private; B still sees them because they are in B's squad
    await client.patch(
        f"{API}/players/{p['id']}", json={"visibility": "private"}, headers=hdr(ta, oa)
    )
    assert await visible_to_b(client, tb, ob, p["id"]) == 200
    # a third organization cannot
    tc, oc = await setup_org(client, "c@x.com", "Org C")
    assert (await client.get(f"{API}/players/{p['id']}", headers=hdr(tc, oc))).status_code == 404


async def test_minor_data_redacted_for_other_organizations(client):
    ta, oa, tb, ob = await two_orgs(client)
    p = await make_player(
        client, ta, oa, "Young Star", 16, visibility="network",
        biography="Private family details", profile_picture_url="https://example.com/kid.jpg",
    )  # fmt: skip
    owner_view = (await client.get(f"{API}/players/{p['id']}", headers=hdr(ta, oa))).json()
    assert owner_view["biography"] and owner_view["profile_picture_url"]

    other = (await client.get(f"{API}/players/{p['id']}", headers=hdr(tb, ob))).json()
    assert other["is_minor"] is True
    assert other["biography"] is None and other["profile_picture_url"] is None
    assert other["full_name"] == "Young Star"  # football-relevant identity stays visible

    # adults are not redacted
    adult = await make_player(
        client, ta, oa, "Grown Pro", 26, visibility="network", biography="Public bio"
    )
    assert (await client.get(f"{API}/players/{adult['id']}", headers=hdr(tb, ob))).json()[
        "biography"
    ] == "Public bio"


async def test_search_scope_mine_vs_network(client):
    ta, oa, tb, ob = await two_orgs(client)
    await make_player(client, ta, oa, "A Mine", 22)
    await make_player(client, ta, oa, "A Shared", 22, visibility="network")
    await make_player(client, tb, ob, "B Mine", 22)
    hb = hdr(tb, ob)
    names = lambda r: sorted(i["full_name"] for i in r.json()["items"])  # noqa: E731
    assert names(await client.get(f"{API}/players?scope=all", headers=hb)) == ["A Shared", "B Mine"]
    assert names(await client.get(f"{API}/players?scope=mine", headers=hb)) == ["B Mine"]
    assert names(await client.get(f"{API}/players?scope=network", headers=hb)) == ["A Shared"]


async def test_non_members_and_spoofed_headers_are_blocked(client):
    ta, oa, tb, ob = await two_orgs(client)
    await make_player(client, ta, oa)
    r = await client.get(f"{API}/players", headers=hdr(tb, oa))  # B claims to act as A
    assert r.status_code == 403
    r = await client.post(f"{API}/players", json=player_body("Injected"), headers=hdr(tb, oa))
    assert r.status_code == 403
