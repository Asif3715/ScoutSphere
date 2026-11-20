from tests.conftest import hdr
from tests.helpers import (
    API,
    REC,
    add_role_member,
    make_player,
    make_requirement,
    notes,
    scouting_setup,
    setup_org,
    unread,
)

SL = f"{REC}/shortlists"


async def user_id(client, s, email):
    ms = (await client.get(f"{API}/organizations/{s.org['id']}/members", headers=s.owner_h)).json()
    return next(m["user_id"] for m in ms if m["email"] == email)


async def make_shortlist(client, s, headers=None, **kw):
    r = await client.post(SL, json={"name": "Summer targets", **kw}, headers=headers or s.rm_h)
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_update_delete(client):
    s = await scouting_setup(client)
    req = await make_requirement(client, s)
    sl = await make_shortlist(
        client, s, description="Midfield", priority="high", requirement_id=req["id"]
    )
    assert (
        sl["is_owner"]
        and sl["priority"] == "high"
        and sl["requirement_title"] == "Creative midfielder"
    )
    assert sl["players"] == [] and sl["shared_with"] == [] and sl["owner_name"] == "rm"
    out = await client.patch(
        f"{SL}/{sl['id']}", json={"name": "Renamed", "priority": "low"}, headers=s.rm_h
    )
    assert out.json()["name"] == "Renamed" and out.json()["priority"] == "low"
    for bad in (
        {"name": "x"},
        {"name": "   "},
        {"priority": "asap"},
        {"requirement_id": "00000000-0000-0000-0000-000000000000"},
    ):
        r = await client.post(SL, json={"name": "Valid name", **bad}, headers=s.rm_h)
        assert r.status_code == 422, bad
    assert (
        await client.patch(f"{SL}/{sl['id']}", json={"name": None}, headers=s.rm_h)
    ).status_code == 422
    assert (await client.delete(f"{SL}/{sl['id']}", headers=s.rm_h)).status_code == 204
    assert (await client.get(f"{SL}/{sl['id']}", headers=s.rm_h)).status_code == 404


async def test_shortlists_are_private_until_shared(client):
    s = await scouting_setup(client)
    sl = await make_shortlist(client, s)
    # nobody else sees it, not even the organization's owner
    for h in (s.owner_h, s.coach_h):
        assert (await client.get(SL, headers=h)).json()["total"] == 0
        assert (await client.get(f"{SL}/{sl['id']}", headers=h)).status_code == 404
    assert (
        await client.get(SL, headers=s.scout_h)
    ).status_code == 403  # scouts have no recruitment access

    coach_id = await user_id(client, s, "coach@x.com")
    shared = await client.put(
        f"{SL}/{sl['id']}/shares", json={"user_ids": [coach_id]}, headers=s.rm_h
    )
    assert shared.status_code == 200 and [x["full_name"] for x in shared.json()["shared_with"]] == [
        "coach"
    ]
    seen = await client.get(f"{SL}/{sl['id']}", headers=s.coach_h)
    assert (
        seen.status_code == 200
        and seen.json()["is_owner"] is False
        and seen.json()["shared_with"] == []
    )  # names stay private
    assert (await client.get(f"{SL}?scope=shared", headers=s.coach_h)).json()["total"] == 1
    assert (await client.get(f"{SL}?scope=mine", headers=s.coach_h)).json()["total"] == 0
    assert (await notes(client, s.coach_t))[0]["type"] == "shortlist_shared"

    # shared people can read but not change anything
    p = await make_player(client, s.owner_t, s.org, "Shared Target", 22)
    assert (
        await client.post(
            f"{SL}/{sl['id']}/players", json={"player_id": p["id"]}, headers=s.coach_h
        )
    ).status_code == 403
    assert (
        await client.patch(f"{SL}/{sl['id']}", json={"name": "Hijack"}, headers=s.coach_h)
    ).status_code == 403
    assert (await client.delete(f"{SL}/{sl['id']}", headers=s.coach_h)).status_code == 403
    assert (
        await client.put(f"{SL}/{sl['id']}/shares", json={"user_ids": []}, headers=s.coach_h)
    ).status_code == 403

    await client.put(f"{SL}/{sl['id']}/shares", json={"user_ids": []}, headers=s.rm_h)  # unshare
    assert (await client.get(f"{SL}/{sl['id']}", headers=s.coach_h)).status_code == 404


async def test_sharing_rules(client):
    s = await scouting_setup(client)
    sl = await make_shortlist(client, s)
    scout_id, owner_id = (
        await user_id(client, s, "scout@x.com"),
        await user_id(client, s, "own@x.com"),
    )
    r = await client.put(f"{SL}/{sl['id']}/shares", json={"user_ids": [scout_id]}, headers=s.rm_h)
    assert (
        r.status_code == 422 and r.json()["error"]["code"] == "invalid_user"
    )  # scouts lack recruitment access
    r = await client.put(
        f"{SL}/{sl['id']}/shares",
        json={"user_ids": ["00000000-0000-0000-0000-000000000000"]},
        headers=s.rm_h,
    )
    assert r.status_code == 422
    other_t, other_org = await setup_org(client, "o2@x.com", "Other Org")
    foreign = (
        await client.get(
            f"{API}/organizations/{other_org['id']}/members", headers=hdr(other_t, other_org)
        )
    ).json()[0]["user_id"]
    assert (
        await client.put(f"{SL}/{sl['id']}/shares", json={"user_ids": [foreign]}, headers=s.rm_h)
    ).status_code == 422
    ok = await client.put(
        f"{SL}/{sl['id']}/shares", json={"user_ids": [owner_id, owner_id]}, headers=s.rm_h
    )
    assert ok.status_code == 200 and len(ok.json()["shared_with"]) == 1  # duplicates collapse
    # re-sharing the same person does not notify again
    before = await unread(client, s.owner_t)
    await client.put(f"{SL}/{sl['id']}/shares", json={"user_ids": [owner_id]}, headers=s.rm_h)
    assert await unread(client, s.owner_t) == before
    assert (
        await client.put(
            f"{SL}/{sl['id']}/shares", json={"user_ids": [owner_id] * 51}, headers=s.rm_h
        )
    ).status_code == 422


async def test_players_on_a_shortlist(client):
    s = await scouting_setup(client)
    sl = await make_shortlist(client, s)
    p1 = await make_player(client, s.owner_t, s.org, "Short One", 22)
    p2 = await make_player(client, s.owner_t, s.org, "Short Two", 24)
    url = f"{SL}/{sl['id']}/players"
    out = await client.post(
        url, json={"player_id": p1["id"], "notes": "Left foot", "priority": "high"}, headers=s.rm_h
    )
    assert out.status_code == 201
    entry = out.json()["players"][0]
    assert (
        entry["player"]["full_name"] == "Short One"
        and entry["notes"] == "Left foot"
        and entry["priority"] == "high"
    )
    r = await client.post(url, json={"player_id": p1["id"]}, headers=s.rm_h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_shortlisted"
    await client.post(url, json={"player_id": p2["id"]}, headers=s.rm_h)
    assert (await client.get(SL, headers=s.rm_h)).json()["items"][0]["player_count"] == 2

    upd = await client.patch(
        f"{url}/{p2['id']}", json={"notes": "Needs fitness work", "priority": "low"}, headers=s.rm_h
    )
    assert {e["player"]["full_name"]: (e["notes"], e["priority"]) for e in upd.json()["players"]}[
        "Short Two"
    ] == ("Needs fitness work", "low")
    assert (
        await client.patch(f"{url}/{p2['id']}", json={"priority": None}, headers=s.rm_h)
    ).status_code == 422
    assert (
        await client.patch(
            f"{url}/00000000-0000-0000-0000-000000000000", json={"notes": "x"}, headers=s.rm_h
        )
    ).status_code == 404
    rem = await client.delete(f"{url}/{p1['id']}", headers=s.rm_h)
    assert [e["player"]["full_name"] for e in rem.json()["players"]] == ["Short Two"]
    assert (await client.delete(f"{url}/{p1['id']}", headers=s.rm_h)).status_code == 404
    assert (
        await client.get(f"{API}/players/{p1['id']}", headers=s.owner_h)
    ).status_code == 200  # the player itself is untouched


async def test_cannot_shortlist_hidden_players_and_notes_stay_internal(client):
    s = await scouting_setup(client)
    sl = await make_shortlist(client, s)
    other_t, other_org = await setup_org(client, "o2@x.com", "Other Org")
    hidden = await make_player(client, other_t, other_org, "Hidden", 22)
    r = await client.post(
        f"{SL}/{sl['id']}/players", json={"player_id": hidden["id"]}, headers=s.rm_h
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_player"
    # a network player of another org can be shortlisted, and our notes are never visible to them
    shared = await make_player(client, other_t, other_org, "Network Star", 22, visibility="network")
    await client.post(
        f"{SL}/{sl['id']}/players",
        json={"player_id": shared["id"], "notes": "Our secret view"},
        headers=s.rm_h,
    )
    ho = hdr(other_t, other_org)
    assert (await client.get(SL, headers=ho)).json()["total"] == 0
    assert (await client.get(f"{SL}/{sl['id']}", headers=ho)).status_code == 404


async def test_shared_users_are_told_when_players_are_added(client):
    s = await scouting_setup(client)
    sl = await make_shortlist(client, s)
    coach_id = await user_id(client, s, "coach@x.com")
    await client.put(f"{SL}/{sl['id']}/shares", json={"user_ids": [coach_id]}, headers=s.rm_h)
    p = await make_player(client, s.owner_t, s.org, "Announce Me", 22)
    await client.post(f"{SL}/{sl['id']}/players", json={"player_id": p["id"]}, headers=s.rm_h)
    n = (await notes(client, s.coach_t))[0]
    assert (
        n["type"] == "player_shortlisted"
        and "Announce Me" in n["title"]
        and n["link_path"] == f"/shortlists/{sl['id']}"
    )
    assert await unread(client, s.rm_t) == 0  # the creator is not notified of their own action


async def test_pipeline_status_is_shown_next_to_shortlisted_players(client):
    s = await scouting_setup(client)
    req = await make_requirement(client, s)
    sl = await make_shortlist(client, s)
    p = await make_player(client, s.owner_t, s.org, "Tracked Player", 22)
    await client.post(f"{SL}/{sl['id']}/players", json={"player_id": p["id"]}, headers=s.rm_h)
    cand = (
        await client.post(
            f"{REC}/requirements/{req['id']}/candidates",
            json={"player_id": p["id"]},
            headers=s.rm_h,
        )
    ).json()
    await client.post(
        f"{REC}/candidates/{cand['id']}/stage", json={"to": "negotiation"}, headers=s.rm_h
    )
    entry = (await client.get(f"{SL}/{sl['id']}", headers=s.rm_h)).json()["players"][0]
    assert entry["pipeline"] == [
        {"requirement_id": req["id"], "requirement_title": req["title"], "stage": "negotiation"}
    ]


async def test_list_filters_pagination_and_isolation(client):
    s = await scouting_setup(client)
    for i in range(3):
        await make_shortlist(client, s, name=f"List number {i}")
    assert (await client.get(f"{SL}?q=number 1", headers=s.rm_h)).json()["total"] == 1
    assert (await client.get(f"{SL}?q=%25", headers=s.rm_h)).json()["total"] == 0
    assert len((await client.get(f"{SL}?page_size=2", headers=s.rm_h)).json()["items"]) == 2
    assert (await client.get(f"{SL}?scope=other", headers=s.rm_h)).status_code == 422
    for h in (s.scout_h, s.coach_h):
        r = await client.post(SL, json={"name": "Not allowed"}, headers=h)
        assert r.status_code == 403
    other_t, other_org = await setup_org(client, "o2@x.com", "Other Org")
    assert (await client.get(SL, headers=hdr(other_t, other_org))).json()["total"] == 0
    assert add_role_member  # (shared import)
