from tests.conftest import hdr, login, make_user
from tests.helpers import API, add_role_member, make_club, make_player, setup_org


async def reference_club(client, name="Real Reference"):
    await make_user("root@x.com", platform_role="super_admin")
    root = await login(client, "root@x.com")
    r = await client.post(
        f"{API}/platform/clubs", json={"name": name}, headers={"Authorization": f"Bearer {root}"}
    )
    return r.json()


async def test_career_crud_and_ordering(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    p = await make_player(client, token, org)
    ref = await reference_club(client)
    base = f"{API}/players/{p['id']}/career"

    old = await client.post(
        base, headers=h,
        json={"club_id": ref["id"], "start_date": "2018-07-01", "end_date": "2021-06-30",
              "appearances": 80, "goals": 12, "assists": 9, "spell_type": "youth"},
    )  # fmt: skip
    assert old.status_code == 201, old.text
    cur = await client.post(
        base,
        headers=h,
        json={"club_id": ref["id"], "start_date": "2021-07-01", "team_label": "U23"},
    )
    assert cur.status_code == 201

    listing = (await client.get(base, headers=h)).json()
    assert [e["start_date"] for e in listing] == ["2021-07-01", "2018-07-01"]  # newest first
    assert listing[0]["club_name"] == "Real Reference" and listing[0]["editable"] is True

    r = await client.patch(
        f"{base}/{cur.json()['id']}", json={"end_date": "2023-06-30", "goals": 5}, headers=h
    )
    assert r.status_code == 200 and r.json()["end_date"] == "2023-06-30"
    assert (await client.delete(f"{base}/{old.json()['id']}", headers=h)).status_code == 204
    assert len((await client.get(base, headers=h)).json()) == 1


async def test_career_validation(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    p = await make_player(client, token, org)
    ref = await reference_club(client)
    base = f"{API}/players/{p['id']}/career"
    good = {"club_id": ref["id"], "start_date": "2020-01-01"}

    assert (
        await client.post(base, json={**good, "end_date": "2019-01-01"}, headers=h)
    ).status_code == 422
    assert (await client.post(base, json={**good, "goals": -1}, headers=h)).status_code == 422
    assert (
        await client.post(base, json={**good, "spell_type": "dream"}, headers=h)
    ).status_code == 422
    r = await client.post(
        base, json={**good, "club_id": "00000000-0000-0000-0000-000000000000"}, headers=h
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_club"

    entry = (await client.post(base, json=good, headers=h)).json()
    assert (
        await client.patch(f"{base}/{entry['id']}", json={"end_date": "1999-01-01"}, headers=h)
    ).status_code == 422
    assert (
        await client.patch(f"{base}/{entry['id']}", json={"start_date": None}, headers=h)
    ).status_code == 422


async def test_career_cannot_reference_another_orgs_managed_club(client):
    ta, oa = await setup_org(client, "a@x.com", "Org A")
    tb, ob = await setup_org(client, "b@x.com", "Org B")
    secret_club = await make_club(client, tb, ob, "B Private FC")
    p = await make_player(client, ta, oa)
    r = await client.post(
        f"{API}/players/{p['id']}/career",
        json={"club_id": secret_club["id"], "start_date": "2020-01-01"},
        headers=hdr(ta, oa),
    )
    assert r.status_code == 422


async def test_only_writers_edit_career(client):
    owner_t, org = await setup_org(client)
    scout_t = await add_role_member(client, org, "scout@x.com", "scout")
    p = await make_player(client, owner_t, org)
    ref = await reference_club(client)
    base = f"{API}/players/{p['id']}/career"
    entry = (
        await client.post(
            base, json={"club_id": ref["id"], "start_date": "2020-01-01"}, headers=hdr(owner_t, org)
        )
    ).json()

    listing = (await client.get(base, headers=hdr(scout_t, org))).json()
    assert listing[0]["editable"] is False
    assert (
        await client.post(
            base, json={"club_id": ref["id"], "start_date": "2021-01-01"}, headers=hdr(scout_t, org)
        )
    ).status_code == 403
    assert (
        await client.patch(f"{base}/{entry['id']}", json={"goals": 1}, headers=hdr(scout_t, org))
    ).status_code == 403
    assert (
        await client.delete(f"{base}/{entry['id']}", headers=hdr(scout_t, org))
    ).status_code == 403


# ---- media ---------------------------------------------------------------------------
async def test_media_is_private_to_the_organization_that_added_it(client):
    ta, oa = await setup_org(client, "a@x.com", "Org A")
    tb, ob = await setup_org(client, "b@x.com", "Org B")
    p = await make_player(client, ta, oa, visibility="network")
    url = f"{API}/players/{p['id']}/media"

    r = await client.post(
        url,
        json={"kind": "video", "title": "Highlights", "url": "https://example.com/v.mp4"},
        headers=hdr(ta, oa),
    )
    assert r.status_code == 201
    media_id = r.json()["id"]
    await client.post(
        url,
        json={"kind": "document", "title": "B notes", "url": "https://example.com/b.pdf"},
        headers=hdr(tb, ob),
    )

    assert [m["title"] for m in (await client.get(url, headers=hdr(ta, oa))).json()] == [
        "Highlights"
    ]
    assert [m["title"] for m in (await client.get(url, headers=hdr(tb, ob))).json()] == ["B notes"]
    # B cannot delete A's media
    assert (await client.delete(f"{url}/{media_id}", headers=hdr(tb, ob))).status_code == 404
    assert (await client.delete(f"{url}/{media_id}", headers=hdr(ta, oa))).status_code == 204
    assert (await client.get(url, headers=hdr(ta, oa))).json() == []


async def test_media_validation(client):
    token, org = await setup_org(client)
    p = await make_player(client, token, org)
    url = f"{API}/players/{p['id']}/media"
    h = hdr(token, org)
    for bad_url in ("javascript:alert(1)", "ftp://x.com/f", "not a url", "data:text/plain,hi"):
        r = await client.post(url, json={"kind": "image", "title": "x", "url": bad_url}, headers=h)
        assert r.status_code == 422, bad_url
    assert (
        await client.post(
            url, json={"kind": "audio", "title": "x", "url": "https://e.com"}, headers=h
        )
    ).status_code == 422
    assert (
        await client.post(
            url, json={"kind": "image", "title": "", "url": "https://e.com"}, headers=h
        )
    ).status_code == 422
