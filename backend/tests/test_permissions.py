from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.audit import AuditLog
from app.models.rbac import Permission, Role, RolePermission
from app.permissions import catalog
from app.permissions.sync import sync_rbac
from tests.conftest import add_member, bearer, login, make_org, make_user


async def _setup(client, email, org, role):
    user = await make_user(email)
    await add_member(user, org, role)
    return await login(client, email)


async def test_unauthenticated_rejected(client):
    r = await client.get("/_test/org-read")
    assert r.status_code == 401


async def test_no_org_header_means_no_org_permissions(client):
    org = await make_org("Alpha")
    token = await _setup(client, "s@x.com", org, "scout")
    r = await client.get("/_test/org-read", headers=bearer(token))  # no X-Organization-Id
    assert r.status_code == 403


async def test_roles_have_different_permissions(client):
    org = await make_org("Alpha")
    scout = await _setup(client, "scout@x.com", org, "scout")
    owner = await _setup(client, "owner@x.com", org, "club_owner")
    manager = await _setup(client, "rm@x.com", org, "recruitment_manager")

    assert (await client.get("/_test/org-read", headers=bearer(scout, org))).status_code == 200
    assert (
        await client.get("/_test/members-manage", headers=bearer(scout, org))
    ).status_code == 403
    assert (
        await client.get("/_test/members-manage", headers=bearer(manager, org))
    ).status_code == 403
    r = await client.get("/_test/members-manage", headers=bearer(owner, org))
    assert r.status_code == 200


async def test_denial_is_audited(client):
    org = await make_org("Alpha")
    scout = await _setup(client, "scout@x.com", org, "scout")
    await client.get("/_test/members-manage", headers=bearer(scout, org))
    async with SessionLocal() as db:
        row = await db.scalar(select(AuditLog).where(AuditLog.action == "authz.denied"))
        assert row.target_id == catalog.MEMBERS_MANAGE and row.organization_id == org.id


async def test_organization_isolation_non_member_blocked(client):
    org_a, org_b = await make_org("Alpha"), await make_org("Beta")
    token_a = await _setup(client, "a@x.com", org_a, "club_owner")
    # Owner of A claims to act in B via the header: must fail.
    r = await client.get("/_test/org-read", headers=bearer(token_a, org_b))
    assert r.status_code == 403 and r.json()["error"]["code"] == "not_a_member"


async def test_nonexistent_and_foreign_org_indistinguishable(client):
    org_a, org_b = await make_org("Alpha"), await make_org("Beta")
    token = await _setup(client, "a@x.com", org_a, "club_owner")
    foreign = await client.get("/_test/org-read", headers=bearer(token, org_b))
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-Id": "00000000-0000-0000-0000-000000000000",
    }
    missing = await client.get("/_test/org-read", headers=headers)
    assert foreign.status_code == missing.status_code == 403
    assert foreign.json() == missing.json()


async def test_user_with_different_roles_in_two_orgs(client):
    org_a, org_b = await make_org("Alpha"), await make_org("Beta")
    user = await make_user("multi@x.com")
    await add_member(user, org_a, "club_owner")
    await add_member(user, org_b, "scout")
    token = await login(client, "multi@x.com")
    assert (
        await client.get("/_test/members-manage", headers=bearer(token, org_a))
    ).status_code == 200
    assert (
        await client.get("/_test/members-manage", headers=bearer(token, org_b))
    ).status_code == 403
    r = await client.get("/api/v1/auth/me", headers=bearer(token))
    assert {m["role"] for m in r.json()["memberships"]} == {"club_owner", "scout"}


async def test_invalid_org_header(client):
    org = await make_org("Alpha")
    token = await _setup(client, "a@x.com", org, "club_owner")
    r = await client.get(
        "/_test/org-read", headers={**bearer(token), "X-Organization-Id": "not-a-uuid"}
    )
    assert r.status_code == 400


async def test_suspended_org_or_membership_blocked(client):
    org = await make_org("Alpha", status="suspended")
    token = await _setup(client, "a@x.com", org, "club_owner")
    assert (await client.get("/_test/org-read", headers=bearer(token, org))).status_code == 403

    org2 = await make_org("Beta")
    user = await make_user("b@x.com")
    await add_member(user, org2, "club_owner", status="suspended")
    token2 = await login(client, "b@x.com")
    assert (await client.get("/_test/org-read", headers=bearer(token2, org2))).status_code == 403


async def test_platform_roles_separate_from_org_data(client):
    org = await make_org("Alpha")
    admin = await make_user("root@x.com", platform_role="super_admin")
    support = await make_user("help@x.com", platform_role="platform_support")
    t_admin, t_support = await login(client, "root@x.com"), await login(client, "help@x.com")
    assert admin and support

    assert (await client.get("/_test/platform-audit", headers=bearer(t_admin))).status_code == 200
    assert (await client.get("/_test/platform-audit", headers=bearer(t_support))).status_code == 403
    # Platform roles grant NO membership: neither can enter an org they don't belong to.
    assert (await client.get("/_test/org-read", headers=bearer(t_admin, org))).status_code == 403
    assert (await client.get("/_test/org-read", headers=bearer(t_support, org))).status_code == 403


async def test_org_owner_has_no_platform_permissions(client):
    org = await make_org("Alpha")
    token = await _setup(client, "o@x.com", org, "club_owner")
    assert (
        await client.get("/_test/platform-audit", headers=bearer(token, org))
    ).status_code == 403


async def test_rbac_sync_mirrors_catalog_and_is_idempotent():
    async with SessionLocal() as db:
        await sync_rbac(db)
        await sync_rbac(db)
        roles = {r.key for r in (await db.scalars(select(Role))).all()}
        perms = {p.key for p in (await db.scalars(select(Permission))).all()}
        assert roles == set(catalog.ROLES) and perms == set(catalog.ALL_PERMISSIONS)
        expected = sum(len(set(v[2])) for v in catalog.ROLES.values())
        assert len((await db.scalars(select(RolePermission))).all()) == expected


def test_catalog_invariants():
    org_perms, platform_perms = set(catalog.ALL_ORG_PERMISSIONS), set(catalog.PLATFORM_PERMISSIONS)
    assert not org_perms & platform_perms
    for key, (_, scope, perms) in catalog.ROLES.items():
        allowed = org_perms if scope == "organization" else platform_perms
        assert set(perms) <= allowed, key
    # Support must not be able to see org-private data by default.
    assert not set(catalog.ROLES["platform_support"][2]) & org_perms
    # Scouts cannot manage members or read contracts.
    scout = set(catalog.ROLES["scout"][2])
    assert catalog.MEMBERS_MANAGE not in scout and catalog.CONTRACTS_READ not in scout
