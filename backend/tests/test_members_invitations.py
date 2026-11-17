from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select, update

from app.db.session import SessionLocal
from app.models.invitation import Invitation
from tests.conftest import hdr, login, make_user
from tests.test_clubs import add_role_member, setup_org
from tests.test_organizations import API


def token_of(invite: dict) -> str:
    return parse_qs(urlparse(invite["accept_url"]).query)["token"][0]


async def invite(client, owner_t, org, email, role="scout"):
    return await client.post(
        f"{API}/organizations/{org['id']}/invitations",
        json={"email": email, "role": role},
        headers=hdr(owner_t, org),
    )


async def members(client, token, org):
    return (
        await client.get(f"{API}/organizations/{org['id']}/members", headers=hdr(token, org))
    ).json()


async def accept(client, token, raw):
    return await client.post(
        f"{API}/invitations/accept",
        json={"token": raw},
        headers={"Authorization": f"Bearer {token}"},
    )


# ---- invitations --------------------------------------------------------------------
async def test_invite_and_accept_flow(client):
    owner_t, org = await setup_org(client)
    r = await invite(client, owner_t, org, "Scout@X.com", "scout")
    assert r.status_code == 201, r.text
    inv = r.json()
    assert inv["status"] == "pending" and inv["accept_url"]

    # the raw token is never stored
    raw = token_of(inv)
    async with SessionLocal() as db:
        row = await db.scalar(select(Invitation))
        assert raw not in row.token_hash and len(row.token_hash) == 64

    preview = await client.post(f"{API}/invitations/preview", json={"token": raw})
    assert preview.status_code == 200 and preview.json()["organization_name"] == "Alpha FC"

    await make_user("scout@x.com")  # email match is case-insensitive
    scout_t = await login(client, "scout@x.com")
    r = await accept(client, scout_t, raw)
    assert r.status_code == 200 and r.json()["id"] == org["id"]

    roles = {m["email"]: m["role"] for m in await members(client, owner_t, org)}
    assert roles["scout@x.com"] == "scout"
    me = (await client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {scout_t}"})).json()
    assert me["memberships"][0]["role"] == "scout"
    # one-time use
    assert (await accept(client, scout_t, raw)).status_code == 400


async def test_accept_requires_matching_email(client):
    owner_t, org = await setup_org(client)
    raw = token_of((await invite(client, owner_t, org, "right@x.com")).json())
    await make_user("wrong@x.com")
    wrong_t = await login(client, "wrong@x.com")
    r = await accept(client, wrong_t, raw)
    assert r.status_code == 403 and r.json()["error"]["code"] == "email_mismatch"
    assert (await client.post(f"{API}/invitations/accept", json={"token": raw})).status_code == 401


async def test_bad_expired_and_revoked_tokens_are_indistinguishable(client):
    owner_t, org = await setup_org(client)
    await make_user("s@x.com")
    s_t = await login(client, "s@x.com")

    inv = (await invite(client, owner_t, org, "s@x.com")).json()
    raw = token_of(inv)
    bogus = await accept(client, s_t, "not-a-real-token-value")
    assert bogus.status_code == 400 and bogus.json()["error"]["code"] == "invalid_invitation"

    async with SessionLocal() as db:
        await db.execute(
            update(Invitation).values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await db.commit()
    expired = await accept(client, s_t, raw)
    assert expired.json() == bogus.json()
    assert (await client.post(f"{API}/invitations/preview", json={"token": raw})).status_code == 400

    # expired invitations can be re-issued
    again = await invite(client, owner_t, org, "s@x.com")
    assert again.status_code == 201
    raw2 = token_of(again.json())
    await client.delete(
        f"{API}/organizations/{org['id']}/invitations/{again.json()['id']}",
        headers=hdr(owner_t, org),
    )
    assert (await accept(client, s_t, raw2)).json() == bogus.json()  # revoked


async def test_invitation_rules(client):
    owner_t, org = await setup_org(client)
    assert (await invite(client, owner_t, org, "n@x.com")).status_code == 201
    r = await invite(client, owner_t, org, "n@x.com")
    assert r.status_code == 409 and r.json()["error"]["code"] == "invitation_exists"
    r = await invite(client, owner_t, org, "own@x.com")  # the owner themself
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_member"
    assert (await invite(client, owner_t, org, "q@x.com", "nonsense")).status_code == 422
    assert (
        await invite(client, owner_t, org, "q@x.com", "super_admin")
    ).status_code == 422  # platform role
    assert (await invite(client, owner_t, org, "not-an-email")).status_code == 422


async def test_only_owner_can_invite_owner_and_scouts_cannot_invite(client):
    owner_t, org = await setup_org(client)
    admin_t = await add_role_member(client, org, "admin@x.com", "club_admin")
    scout_t = await add_role_member(client, org, "scout@x.com", "scout")
    assert (await invite(client, admin_t, org, "a@x.com", "scout")).status_code == 201
    r = await invite(client, admin_t, org, "b@x.com", "club_owner")
    assert r.status_code == 403 and r.json()["error"]["code"] == "owner_required"
    assert (await invite(client, owner_t, org, "b@x.com", "club_owner")).status_code == 201
    assert (await invite(client, scout_t, org, "c@x.com", "scout")).status_code == 403
    assert (
        await client.get(f"{API}/organizations/{org['id']}/invitations", headers=hdr(scout_t, org))
    ).status_code == 403


async def test_removed_member_can_be_reinvited(client):
    owner_t, org = await setup_org(client)
    await add_role_member(client, org, "s@x.com", "scout")
    mid = next(m["id"] for m in await members(client, owner_t, org) if m["email"] == "s@x.com")
    await client.delete(f"{API}/organizations/{org['id']}/members/{mid}", headers=hdr(owner_t, org))
    raw = token_of((await invite(client, owner_t, org, "s@x.com", "coach")).json())
    s_t = await login(client, "s@x.com")
    assert (await accept(client, s_t, raw)).status_code == 200
    roles = {m["email"]: m["role"] for m in await members(client, owner_t, org)}
    assert roles["s@x.com"] == "coach"


async def test_suspended_org_invitation_unusable(client):
    owner_t, org = await setup_org(client)
    raw = token_of((await invite(client, owner_t, org, "s@x.com")).json())
    await make_user("root@x.com", platform_role="super_admin")
    root = await login(client, "root@x.com")
    await client.patch(
        f"{API}/platform/organizations/{org['id']}/status",
        json={"status": "suspended"},
        headers={"Authorization": f"Bearer {root}"},
    )
    await make_user("s@x.com")
    s_t = await login(client, "s@x.com")
    assert (await accept(client, s_t, raw)).status_code == 400


# ---- members ------------------------------------------------------------------------
async def test_list_members_visible_to_roles_with_members_read(client):
    owner_t, org = await setup_org(client)
    rm_t = await add_role_member(client, org, "rm@x.com", "recruitment_manager")
    scout_t = await add_role_member(client, org, "scout@x.com", "scout")
    assert len(await members(client, rm_t, org)) == 3
    r = await client.get(f"{API}/organizations/{org['id']}/members", headers=hdr(scout_t, org))
    assert r.status_code == 403


async def test_change_role_and_remove(client):
    owner_t, org = await setup_org(client)
    await add_role_member(client, org, "s@x.com", "scout")
    mid = next(m["id"] for m in await members(client, owner_t, org) if m["email"] == "s@x.com")
    h = hdr(owner_t, org)
    url = f"{API}/organizations/{org['id']}/members/{mid}"

    assert (await client.patch(url, json={"role": "coach"}, headers=h)).status_code == 204
    assert next(m["role"] for m in await members(client, owner_t, org) if m["id"] == mid) == "coach"
    assert (await client.patch(url, json={"role": "bogus"}, headers=h)).status_code == 422
    assert (await client.patch(url, json={"role": "super_admin"}, headers=h)).status_code == 422

    assert (await client.delete(url, headers=h)).status_code == 204
    assert all(m["id"] != mid for m in await members(client, owner_t, org))
    # removed member loses access immediately
    s_t = await login(client, "s@x.com")
    assert (await client.get(f"{API}/clubs", headers=hdr(s_t, org))).status_code == 403


async def test_owner_protection_rules(client):
    owner_t, org = await setup_org(client)
    admin_t = await add_role_member(client, org, "admin@x.com", "club_admin")
    ms = await members(client, owner_t, org)
    owner_mid = next(m["id"] for m in ms if m["role"] == "club_owner")
    admin_mid = next(m["id"] for m in ms if m["email"] == "admin@x.com")
    base = f"{API}/organizations/{org['id']}/members"

    # an admin cannot touch the owner, nor promote anyone (or themself) to owner
    assert (
        await client.patch(f"{base}/{owner_mid}", json={"role": "scout"}, headers=hdr(admin_t, org))
    ).status_code == 403
    assert (
        await client.delete(f"{base}/{owner_mid}", headers=hdr(admin_t, org))
    ).status_code == 403
    r = await client.patch(
        f"{base}/{admin_mid}", json={"role": "club_owner"}, headers=hdr(admin_t, org)
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "owner_required"

    # the last owner cannot be demoted or removed, even by themself
    for call in (
        client.patch(f"{base}/{owner_mid}", json={"role": "club_admin"}, headers=hdr(owner_t, org)),
        client.delete(f"{base}/{owner_mid}", headers=hdr(owner_t, org)),
    ):
        r = await call
        assert r.status_code == 409 and r.json()["error"]["code"] == "last_owner"

    # with a second owner, the first may step down
    assert (
        await client.patch(
            f"{base}/{admin_mid}", json={"role": "club_owner"}, headers=hdr(owner_t, org)
        )
    ).status_code == 204
    assert (
        await client.patch(
            f"{base}/{owner_mid}", json={"role": "club_admin"}, headers=hdr(owner_t, org)
        )
    ).status_code == 204


async def test_unknown_member_id_is_404(client):
    owner_t, org = await setup_org(client)
    url = f"{API}/organizations/{org['id']}/members/00000000-0000-0000-0000-000000000000"
    assert (
        await client.patch(url, json={"role": "scout"}, headers=hdr(owner_t, org))
    ).status_code == 404
    assert (await client.delete(url, headers=hdr(owner_t, org))).status_code == 404
