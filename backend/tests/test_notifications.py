from tests.helpers import API, make_assignment, notes, scouting_setup, setup_org, unread


def auth(token):
    return {"Authorization": f"Bearer {token}"}


async def test_list_unread_count_and_mark_read(client):
    s = await scouting_setup(client)
    for _ in range(3):
        await make_assignment(client, s)
    assert await unread(client, s.scout_t) == 3
    items = await notes(client, s.scout_t)
    assert len(items) == 3 and all(not n["read"] for n in items)

    r = await client.post(f"{API}/notifications/{items[0]['id']}/read", headers=auth(s.scout_t))
    assert r.status_code == 204
    assert await unread(client, s.scout_t) == 2
    assert [n["id"] for n in await notes(client, s.scout_t, unread="true")] == [
        items[1]["id"],
        items[2]["id"],
    ]
    assert len(await notes(client, s.scout_t)) == 3  # history is kept
    # reading twice is harmless
    assert (
        await client.post(f"{API}/notifications/{items[0]['id']}/read", headers=auth(s.scout_t))
    ).status_code == 204

    assert (
        await client.post(f"{API}/notifications/read-all", headers=auth(s.scout_t))
    ).status_code == 204
    assert await unread(client, s.scout_t) == 0 and len(await notes(client, s.scout_t)) == 3


async def test_notifications_are_private_to_their_user(client):
    s = await scouting_setup(client)
    await make_assignment(client, s)
    note = (await notes(client, s.scout_t))[0]
    # another user cannot read or mark it; the owner has none of their own
    assert (
        await client.post(f"{API}/notifications/{note['id']}/read", headers=auth(s.owner_t))
    ).status_code == 404
    assert await notes(client, s.owner_t) == [] and await unread(client, s.owner_t) == 0
    assert await unread(client, s.scout_t) == 1  # untouched
    assert (
        await client.post(f"{API}/notifications/read-all", headers=auth(s.owner_t))
    ).status_code == 204
    assert await unread(client, s.scout_t) == 1  # still untouched
    assert (await client.get(f"{API}/notifications")).status_code == 401
    assert (
        await client.post(
            f"{API}/notifications/00000000-0000-0000-0000-000000000000/read",
            headers=auth(s.scout_t),
        )
    ).status_code == 404


async def test_pagination(client):
    s = await scouting_setup(client)
    for _ in range(5):
        await make_assignment(client, s)
    r = await client.get(f"{API}/notifications?page=2&page_size=2", headers=auth(s.scout_t))
    assert r.json()["total"] == 5 and len(r.json()["items"]) == 2
    assert (
        await client.get(f"{API}/notifications?page_size=500", headers=auth(s.scout_t))
    ).status_code == 422
    newest_first = [n["created_at"] for n in await notes(client, s.scout_t)]
    assert newest_first == sorted(newest_first, reverse=True)


async def test_preferences_default_on_and_can_opt_out(client):
    s = await scouting_setup(client)
    prefs = (await client.get(f"{API}/notifications/preferences", headers=auth(s.scout_t))).json()
    assert len(prefs) == 18 and all(p["enabled"] for p in prefs)
    types = {p["type"] for p in prefs}
    assert {"assignment_assigned", "report_submitted", "assignment_deadline"} <= types

    r = await client.put(
        f"{API}/notifications/preferences",
        json={"preferences": {"assignment_assigned": False}},
        headers=auth(s.scout_t),
    )
    assert (
        r.status_code == 200
        and {p["type"]: p["enabled"] for p in r.json()}["assignment_assigned"] is False
    )
    await make_assignment(client, s)
    assert await unread(client, s.scout_t) == 0  # opted out, nothing delivered

    await client.put(
        f"{API}/notifications/preferences",
        json={"preferences": {"assignment_assigned": True}},
        headers=auth(s.scout_t),
    )
    await make_assignment(client, s, "player")
    assert await unread(client, s.scout_t) == 1
    # the choice belongs to one user only
    other = (await client.get(f"{API}/notifications/preferences", headers=auth(s.rm_t))).json()
    assert all(p["enabled"] for p in other)


async def test_preferences_validation(client):
    s = await scouting_setup(client)
    r = await client.put(
        f"{API}/notifications/preferences",
        json={"preferences": {"made_up": False}},
        headers=auth(s.scout_t),
    )
    assert r.status_code == 422
    assert (
        await client.put(
            f"{API}/notifications/preferences",
            json={"preferences": {"report_approved": "nope"}},
            headers=auth(s.scout_t),
        )
    ).status_code == 422
    assert (
        await client.put(
            f"{API}/notifications/preferences", json={"preferences": {}}, headers=auth(s.scout_t)
        )
    ).status_code == 200


async def test_notification_records_its_organization(client):
    s = await scouting_setup(client)
    await make_assignment(client, s)
    assert (await notes(client, s.scout_t))[0]["organization_id"] == s.org["id"]
    other_t, _ = await setup_org(client, "o2@x.com", "Other Org")
    assert await unread(client, other_t) == 0  # nothing leaks to other organizations' users
