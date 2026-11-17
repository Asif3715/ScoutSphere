from tests.conftest import add_member, hdr, login, make_user
from tests.test_organizations import API, found_org, new_user

CLUB = {"name": "Alpha Senior", "country": "England", "city": "Leeds", "founded_year": 1904}


async def setup_org(client, email="own@x.com", name="Alpha FC"):
    token = await new_user(client, email)
    org = await found_org(client, token, name)
    return token, org


async def add_role_member(client, org, email, role):
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models.organization import Organization

    user = await make_user(email)
    async with SessionLocal() as db:
        org_row = await db.scalar(select(Organization).where(Organization.id == org["id"]))
    await add_member(user, org_row, role)
    return await login(client, email)


async def test_club_crud_roundtrip(client):
    token, org = await setup_org(client)
    h = hdr(token, org)

    r = await client.post(f"{API}/clubs", json=CLUB, headers=h)
    assert r.status_code == 201, r.text
    club = r.json()
    assert club["organization_id"] == org["id"] and club["is_reference"] is False

    r = await client.get(f"{API}/clubs/{club['id']}", headers=h)
    assert r.status_code == 200 and r.json()["city"] == "Leeds"

    r = await client.patch(f"{API}/clubs/{club['id']}", json={"city": "Manchester"}, headers=h)
    assert r.status_code == 200 and r.json()["city"] == "Manchester"
    assert r.json()["name"] == "Alpha Senior"  # untouched fields preserved

    r = await client.delete(f"{API}/clubs/{club['id']}", headers=h)
    assert r.status_code == 204
    assert (await client.get(f"{API}/clubs/{club['id']}", headers=h)).status_code == 404
    assert (await client.get(f"{API}/clubs", headers=h)).json()["total"] == 0


async def test_club_validation(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    assert (await client.post(f"{API}/clubs", json={"name": ""}, headers=h)).status_code == 422
    r = await client.post(f"{API}/clubs", json={"name": "X", "founded_year": 1500}, headers=h)
    assert r.status_code == 422
    r = await client.post(f"{API}/clubs", json={"name": "X", "contact_email": "bad"}, headers=h)
    assert r.status_code == 422
    r = await client.post(f"{API}/clubs", json=CLUB, headers=h)
    cid = r.json()["id"]
    assert (
        await client.patch(f"{API}/clubs/{cid}", json={"name": None}, headers=h)
    ).status_code == 422


async def test_duplicate_club_name_per_org_case_insensitive(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    assert (await client.post(f"{API}/clubs", json=CLUB, headers=h)).status_code == 201
    r = await client.post(f"{API}/clubs", json={**CLUB, "name": "ALPHA senior"}, headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "club_exists"
    # archiving frees the name
    cid = (await client.get(f"{API}/clubs", headers=h)).json()["items"][0]["id"]
    await client.delete(f"{API}/clubs/{cid}", headers=h)
    assert (await client.post(f"{API}/clubs", json=CLUB, headers=h)).status_code == 201


async def test_same_club_name_allowed_in_different_orgs(client):
    t1, o1 = await setup_org(client, "a@x.com", "Org A")
    t2, o2 = await setup_org(client, "b@x.com", "Org B")
    assert (await client.post(f"{API}/clubs", json=CLUB, headers=hdr(t1, o1))).status_code == 201
    assert (await client.post(f"{API}/clubs", json=CLUB, headers=hdr(t2, o2))).status_code == 201


async def test_list_pagination_search_and_filter(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    for name, country in [
        ("Ajax Youth", "Netherlands"),
        ("Arsenal U21", "England"),
        ("Benfica B", "Portugal"),
    ]:
        await client.post(f"{API}/clubs", json={"name": name, "country": country}, headers=h)

    r = await client.get(f"{API}/clubs?page_size=2", headers=h)
    body = r.json()
    assert body["total"] == 3 and len(body["items"]) == 2 and body["page_size"] == 2
    assert [c["name"] for c in body["items"]] == ["Ajax Youth", "Arsenal U21"]  # sorted by name
    r = await client.get(f"{API}/clubs?page=2&page_size=2", headers=h)
    assert [c["name"] for c in r.json()["items"]] == ["Benfica B"]

    assert (await client.get(f"{API}/clubs?q=ar", headers=h)).json()["total"] == 1
    assert (await client.get(f"{API}/clubs?country=england", headers=h)).json()["total"] == 1
    # LIKE wildcards are treated literally
    assert (await client.get(f"{API}/clubs?q=%25", headers=h)).json()["total"] == 0
    assert (await client.get(f"{API}/clubs?page_size=1000", headers=h)).status_code == 422


async def test_role_permissions_for_clubs(client):
    owner_t, org = await setup_org(client)
    scout_t = await add_role_member(client, org, "scout@x.com", "scout")
    admin_t = await add_role_member(client, org, "admin@x.com", "club_admin")
    rm_t = await add_role_member(client, org, "rm@x.com", "recruitment_manager")

    assert (
        await client.post(f"{API}/clubs", json=CLUB, headers=hdr(admin_t, org))
    ).status_code == 201
    cid = (await client.get(f"{API}/clubs", headers=hdr(owner_t, org))).json()["items"][0]["id"]
    for t in (scout_t, rm_t):  # can read, cannot write
        assert (await client.get(f"{API}/clubs/{cid}", headers=hdr(t, org))).status_code == 200
        assert (
            await client.post(f"{API}/clubs", json={"name": "Z"}, headers=hdr(t, org))
        ).status_code == 403
        assert (
            await client.patch(f"{API}/clubs/{cid}", json={"city": "x"}, headers=hdr(t, org))
        ).status_code == 403
        assert (await client.delete(f"{API}/clubs/{cid}", headers=hdr(t, org))).status_code == 403


async def test_clubs_require_org_context_and_auth(client):
    token, org = await setup_org(client)
    assert (await client.get(f"{API}/clubs")).status_code == 401
    assert (
        await client.get(f"{API}/clubs", headers={"Authorization": f"Bearer {token}"})
    ).status_code == 403


async def test_reference_clubs_visible_but_read_only_for_tenants(client):
    await make_user("root@x.com", platform_role="super_admin")
    root = await login(client, "root@x.com")
    r = await client.post(
        f"{API}/platform/clubs",
        json={"name": "Real Madrid", "country": "Spain"},
        headers={"Authorization": f"Bearer {root}"},
    )
    assert r.status_code == 201 and r.json()["is_reference"] is True
    ref_id = r.json()["id"]

    token, org = await setup_org(client)
    h = hdr(token, org)
    assert (await client.get(f"{API}/clubs", headers=h)).json()["total"] == 0  # not in "mine"
    listed = (await client.get(f"{API}/clubs?scope=reference&q=real", headers=h)).json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == ref_id
    assert (await client.get(f"{API}/clubs/{ref_id}", headers=h)).status_code == 200
    # tenants cannot edit or archive global clubs
    assert (
        await client.patch(f"{API}/clubs/{ref_id}", json={"city": "x"}, headers=h)
    ).status_code == 404
    assert (await client.delete(f"{API}/clubs/{ref_id}", headers=h)).status_code == 404
    # nor create them through the platform endpoint
    assert (
        await client.post(
            f"{API}/platform/clubs",
            json={"name": "Fake"},
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 403
