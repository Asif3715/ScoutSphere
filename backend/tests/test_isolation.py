"""Cross-tenant isolation: organization A must never see or touch organization B's data."""

from tests.conftest import hdr
from tests.test_clubs import add_role_member, setup_org
from tests.test_organizations import API


async def two_orgs(client):
    ta, oa = await setup_org(client, "a@x.com", "Org A")
    tb, ob = await setup_org(client, "b@x.com", "Org B")
    return ta, oa, tb, ob


async def test_clubs_are_invisible_across_organizations(client):
    ta, oa, tb, ob = await two_orgs(client)
    r = await client.post(f"{API}/clubs", json={"name": "Secret FC"}, headers=hdr(ta, oa))
    cid = r.json()["id"]

    # B, acting properly inside its own org, cannot see, edit or archive A's club
    hb = hdr(tb, ob)
    assert (await client.get(f"{API}/clubs", headers=hb)).json()["total"] == 0
    assert (await client.get(f"{API}/clubs?q=secret", headers=hb)).json()["total"] == 0
    assert (await client.get(f"{API}/clubs/{cid}", headers=hb)).status_code == 404
    assert (
        await client.patch(f"{API}/clubs/{cid}", json={"city": "x"}, headers=hb)
    ).status_code == 404
    assert (await client.delete(f"{API}/clubs/{cid}", headers=hb)).status_code == 404
    # ...and the club is untouched
    assert (await client.get(f"{API}/clubs/{cid}", headers=hdr(ta, oa))).json()[
        "name"
    ] == "Secret FC"


async def test_spoofing_the_organization_header_fails(client):
    ta, oa, tb, ob = await two_orgs(client)
    await client.post(f"{API}/clubs", json={"name": "Secret FC"}, headers=hdr(ta, oa))
    # B claims to be acting in A
    r = await client.get(f"{API}/clubs", headers=hdr(tb, oa))
    assert r.status_code == 403 and r.json()["error"]["code"] == "not_a_member"
    r = await client.post(f"{API}/clubs", json={"name": "Injected"}, headers=hdr(tb, oa))
    assert r.status_code == 403


async def test_members_and_invitations_isolated(client):
    ta, oa, tb, ob = await two_orgs(client)
    for path in ("members", "invitations", "dashboard"):
        assert (
            await client.get(f"{API}/organizations/{oa['id']}/{path}", headers=hdr(tb, ob))
        ).status_code == 403

    # member ids from org A cannot be manipulated through org B's URL
    members_a = (
        await client.get(f"{API}/organizations/{oa['id']}/members", headers=hdr(ta, oa))
    ).json()
    mid = members_a[0]["id"]
    r = await client.patch(
        f"{API}/organizations/{ob['id']}/members/{mid}", json={"role": "scout"}, headers=hdr(tb, ob)
    )
    assert r.status_code == 404
    r = await client.delete(f"{API}/organizations/{ob['id']}/members/{mid}", headers=hdr(tb, ob))
    assert r.status_code == 404
    members_a = (
        await client.get(f"{API}/organizations/{oa['id']}/members", headers=hdr(ta, oa))
    ).json()
    assert members_a[0]["role"] == "club_owner" and members_a[0]["status"] == "active"


async def test_invitation_ids_cannot_cross_organizations(client):
    ta, oa, tb, ob = await two_orgs(client)
    r = await client.post(
        f"{API}/organizations/{oa['id']}/invitations",
        json={"email": "n@x.com", "role": "scout"},
        headers=hdr(ta, oa),
    )
    inv_id = r.json()["id"]
    r = await client.delete(
        f"{API}/organizations/{ob['id']}/invitations/{inv_id}", headers=hdr(tb, ob)
    )
    assert r.status_code == 404
    pending = (
        await client.get(f"{API}/organizations/{oa['id']}/invitations", headers=hdr(ta, oa))
    ).json()
    assert len(pending) == 1


async def test_user_in_two_orgs_sees_only_active_org_data(client):
    ta, oa, tb, ob = await two_orgs(client)
    await client.post(f"{API}/clubs", json={"name": "A Club"}, headers=hdr(ta, oa))
    await client.post(f"{API}/clubs", json={"name": "B Club"}, headers=hdr(tb, ob))
    # a scout in A who also belongs to B (as scout) sees different data per active org
    shared_t = await add_role_member(client, oa, "shared@x.com", "scout")
    # add the same user to B
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models.organization import Organization
    from app.models.user import User
    from tests.conftest import add_member

    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == "shared@x.com"))
        org_b = await db.scalar(select(Organization).where(Organization.id == ob["id"]))
    await add_member(user, org_b, "scout")

    names_a = [
        c["name"]
        for c in (await client.get(f"{API}/clubs", headers=hdr(shared_t, oa))).json()["items"]
    ]
    names_b = [
        c["name"]
        for c in (await client.get(f"{API}/clubs", headers=hdr(shared_t, ob))).json()["items"]
    ]
    assert names_a == ["A Club"] and names_b == ["B Club"]
