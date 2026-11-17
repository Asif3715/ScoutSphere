from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.audit import AuditLog
from app.models.organization import OrganizationMember
from tests.conftest import add_member, bearer, hdr, login, make_org, make_user

API = "/api/v1"


async def new_user(client, email="founder@x.com", **kw):
    await make_user(email, **kw)
    return await login(client, email)


async def found_org(client, token, name="Alpha FC"):
    r = await client.post(f"{API}/organizations", json={"name": name}, headers=bearer(token))
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_organization_makes_creator_owner(client):
    token = await new_user(client)
    org = await found_org(client, token)
    assert org["slug"] == "alpha-fc" and org["status"] == "active"

    me = (await client.get(f"{API}/auth/me", headers=bearer(token))).json()
    assert [(m["organization_id"], m["role"]) for m in me["memberships"]] == [
        (org["id"], "club_owner")
    ]
    async with SessionLocal() as db:
        assert await db.scalar(select(AuditLog).where(AuditLog.action == "org.create"))


async def test_slug_collision_gets_suffix(client):
    token = await new_user(client)
    a = await found_org(client, token, "Same Name")
    b = await found_org(client, token, "Same Name")
    assert a["slug"] == "same-name" and b["slug"] != a["slug"]


async def test_create_organization_requires_login_and_valid_input(client):
    assert (await client.post(f"{API}/organizations", json={"name": "X Club"})).status_code == 401
    token = await new_user(client)
    r = await client.post(f"{API}/organizations", json={"name": "x"}, headers=bearer(token))
    assert r.status_code == 422


async def test_player_accounts_cannot_create_organizations(client):
    from sqlalchemy import update

    from app.models.user import User

    token = await new_user(client)
    async with SessionLocal() as db:
        await db.execute(update(User).values(account_type="player"))
        await db.commit()
    r = await client.post(f"{API}/organizations", json={"name": "Nope FC"}, headers=bearer(token))
    assert r.status_code == 403 and r.json()["error"]["code"] == "account_type_not_allowed"


async def test_get_and_update_organization_permissions(client):
    owner_t = await new_user(client)
    org = await found_org(client, owner_t)
    h = bearer(owner_t)

    r = await client.patch(
        f"{API}/organizations/{org['id']}", json={"description": "hello"}, headers=h
    )
    assert r.status_code == 200 and r.json()["description"] == "hello"

    # an admin can read but not update organization settings (ORG_UPDATE is owner only)
    admin = await make_user("admin@x.com")
    async with SessionLocal() as db:
        from app.models.organization import Organization

        real = await db.get(Organization, __import__("uuid").UUID(org["id"]))
    await add_member(admin, real, "club_admin")
    admin_t = await login(client, "admin@x.com")
    assert (
        await client.get(f"{API}/organizations/{org['id']}", headers=bearer(admin_t))
    ).status_code == 200
    r = await client.patch(
        f"{API}/organizations/{org['id']}", json={"name": "Hacked"}, headers=bearer(admin_t)
    )
    assert r.status_code == 403


async def test_cannot_read_other_organization(client):
    t1 = await new_user(client, "a@x.com")
    t2 = await new_user(client, "b@x.com")
    org1 = await found_org(client, t1, "Org One")
    await found_org(client, t2, "Org Two")
    r = await client.get(f"{API}/organizations/{org1['id']}", headers=bearer(t2))
    assert r.status_code == 403
    r = await client.patch(
        f"{API}/organizations/{org1['id']}", json={"name": "Stolen"}, headers=bearer(t2)
    )
    assert r.status_code == 403
    r = await client.get(f"{API}/organizations/{org1['id']}/dashboard", headers=bearer(t2))
    assert r.status_code == 403


async def test_dashboard_counts(client):
    token = await new_user(client)
    org = await found_org(client, token)
    h = hdr(token, org)
    await client.post(f"{API}/clubs", json={"name": "First XI"}, headers=h)
    await client.post(
        f"{API}/organizations/{org['id']}/invitations",
        json={"email": "new@x.com", "role": "scout"},
        headers=bearer(token),
    )
    r = await client.get(f"{API}/organizations/{org['id']}/dashboard", headers=bearer(token))
    body = r.json()
    assert (body["clubs"], body["members"], body["pending_invitations"]) == (1, 1, 1)


async def test_platform_admin_lists_and_suspends_organizations(client):
    owner_t = await new_user(client, "o@x.com")
    org = await found_org(client, owner_t)
    await make_user("root@x.com", platform_role="super_admin")
    root = await login(client, "root@x.com")

    r = await client.get(f"{API}/platform/organizations", headers=bearer(root))
    assert r.status_code == 200 and r.json()["total"] == 1

    r = await client.patch(
        f"{API}/platform/organizations/{org['id']}/status",
        json={"status": "suspended"},
        headers=bearer(root),
    )
    assert r.status_code == 200 and r.json()["status"] == "suspended"
    # members of a suspended organization are locked out of it
    r = await client.get(f"{API}/organizations/{org['id']}", headers=bearer(owner_t))
    assert r.status_code == 403
    me = (await client.get(f"{API}/auth/me", headers=bearer(owner_t))).json()
    assert me["memberships"] == []

    r = await client.patch(
        f"{API}/platform/organizations/{org['id']}/status",
        json={"status": "active"},
        headers=bearer(root),
    )
    assert r.status_code == 200
    assert (
        await client.get(f"{API}/organizations/{org['id']}", headers=bearer(owner_t))
    ).status_code == 200


async def test_platform_endpoints_forbidden_to_everyone_else(client):
    owner_t = await new_user(client, "o@x.com")
    org = await found_org(client, owner_t)
    await make_user("help@x.com", platform_role="platform_support")
    support = await login(client, "help@x.com")
    for token in (owner_t, support):
        assert (
            await client.get(f"{API}/platform/organizations", headers=bearer(token))
        ).status_code == 403
        r = await client.patch(
            f"{API}/platform/organizations/{org['id']}/status",
            json={"status": "suspended"},
            headers=bearer(token),
        )
        assert r.status_code == 403
    assert (await client.get(f"{API}/platform/organizations")).status_code == 401


async def test_org_membership_rows_exist_once(client):
    token = await new_user(client)
    await found_org(client, token)
    async with SessionLocal() as db:
        rows = (await db.scalars(select(OrganizationMember))).all()
        assert len(rows) == 1
    assert await make_org("Other")  # factory still works alongside the API
