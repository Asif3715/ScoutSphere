from datetime import date

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.audit import AuditLog
from tests.conftest import hdr
from tests.helpers import API, add_role_member, dob_for_age, make_player, player_body, setup_org


async def test_create_and_get_player(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    body = player_body(
        height_cm=181, weight_kg=75, preferred_foot="right",
        secondary_positions=["CAM", "CDM"], biography="Box-to-box.",
    )  # fmt: skip
    r = await client.post(f"{API}/players", json=body, headers=h)
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["age"] == 22 and p["is_minor"] is False and p["is_owner"] is True
    assert p["visibility"] == "private"  # private by default
    assert p["secondary_positions"] == ["CAM", "CDM"]

    got = (await client.get(f"{API}/players/{p['id']}", headers=h)).json()
    assert got["full_name"] == "Luka Novak" and got["biography"] == "Box-to-box."
    async with SessionLocal() as db:
        assert await db.scalar(select(AuditLog).where(AuditLog.action == "player.create"))


async def test_validation(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    bad = [
        {"full_name": "A"},
        {"date_of_birth": "2999-01-01"},
        {"date_of_birth": dob_for_age(5)},
        {"date_of_birth": dob_for_age(80)},
        {"height_cm": 50},
        {"weight_kg": 500},
        {"preferred_foot": "middle"},
        {"primary_position": "QB"},
        {"secondary_positions": ["CM"], "primary_position": "CM"},
        {"secondary_positions": ["XX"]},
        {"profile_picture_url": "javascript:alert(1)"},
        {"profile_picture_url": "data:text/html,hi"},
        {"visibility": "everyone"},
    ]
    for override in bad:
        r = await client.post(f"{API}/players", json={**player_body(), **override}, headers=h)
        assert r.status_code == 422, override


async def test_only_writers_can_create_and_scouts_can_read(client):
    owner_t, org = await setup_org(client)
    scout_t = await add_role_member(client, org, "scout@x.com", "scout")
    rm_t = await add_role_member(client, org, "rm@x.com", "recruitment_manager")
    coach_t = await add_role_member(client, org, "coach@x.com", "coach")

    assert (
        await client.post(f"{API}/players", json=player_body(), headers=hdr(rm_t, org))
    ).status_code == 201
    for t in (scout_t, coach_t):
        r = await client.post(
            f"{API}/players", json=player_body("Other Person"), headers=hdr(t, org)
        )
        assert r.status_code == 403
        assert (await client.get(f"{API}/players", headers=hdr(t, org))).status_code == 200
    assert (await client.get(f"{API}/players")).status_code == 401


async def test_update_player_and_positions(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    p = await make_player(client, token, org, secondary_positions=["CAM"])
    url = f"{API}/players/{p['id']}"

    r = await client.patch(
        url, json={"height_cm": 185, "secondary_positions": ["LW", "RW", "LW"]}, headers=h
    )
    assert r.status_code == 200
    assert r.json()["height_cm"] == 185 and r.json()["secondary_positions"] == ["LW", "RW"]
    assert r.json()["full_name"] == "Luka Novak"  # untouched

    # promoting a secondary to primary removes it from secondaries
    r = await client.patch(url, json={"primary_position": "LW"}, headers=h)
    assert r.json()["primary_position"] == "LW" and r.json()["secondary_positions"] == ["RW"]

    assert (await client.patch(url, json={"full_name": None}, headers=h)).status_code == 422
    assert (await client.patch(url, json={"height_cm": 10}, headers=h)).status_code == 422


async def test_minor_rules(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    minor = await client.post(
        f"{API}/players", json=player_body("Young Talent", 16, visibility="public"), headers=h
    )
    assert minor.status_code == 422 and minor.json()["error"]["code"] == "minor_cannot_be_public"

    p = await make_player(client, token, org, "Young Talent", 16)
    assert p["is_minor"] is True
    r = await client.patch(f"{API}/players/{p['id']}", json={"visibility": "public"}, headers=h)
    assert r.status_code == 422
    assert (
        await client.patch(f"{API}/players/{p['id']}", json={"visibility": "network"}, headers=h)
    ).status_code == 200
    # an adult can be public
    adult = await make_player(client, token, org, "Adult Pro", 25, visibility="public")
    assert adult["visibility"] == "public"


async def test_visibility_change_is_audited(client):
    token, org = await setup_org(client)
    p = await make_player(client, token, org)
    await client.patch(
        f"{API}/players/{p['id']}", json={"visibility": "network"}, headers=hdr(token, org)
    )
    async with SessionLocal() as db:
        row = await db.scalar(select(AuditLog).where(AuditLog.action == "player.set_visibility"))
        assert row.metadata_ == {"from": "private", "to": "network"}


async def test_archive_player(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    p = await make_player(client, token, org)
    assert (await client.delete(f"{API}/players/{p['id']}", headers=h)).status_code == 204
    assert (await client.get(f"{API}/players/{p['id']}", headers=h)).status_code == 404
    assert (await client.get(f"{API}/players", headers=h)).json()["total"] == 0


async def test_duplicate_detection_warns_then_allows_override(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    first = await make_player(client, token, org, "Cristiano Silva", 24)

    body = player_body("Cristiano Silva", 24)
    r = await client.post(f"{API}/players", json=body, headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "possible_duplicate"
    cands = r.json()["error"]["details"]
    assert cands[0]["id"] == first["id"] and cands[0]["similarity"] == 1.0

    # near-miss spelling with the same date of birth is caught too
    near = await client.post(
        f"{API}/players", json={**body, "full_name": "Cristiano Silvas"}, headers=h
    )
    assert near.status_code == 409

    # an identical name still warns even if the birth date differs (could be a typo)
    other = await client.post(f"{API}/players", json=player_body("Cristiano Silva", 31), headers=h)
    assert other.status_code == 409
    # different person entirely: fine
    assert (
        await client.post(f"{API}/players", json=player_body("Mateo Fernandez", 24), headers=h)
    ).status_code == 201

    # explicit confirmation creates it
    ok = await client.post(f"{API}/players", json={**body, "allow_duplicate": True}, headers=h)
    assert ok.status_code == 201 and ok.json()["id"] != first["id"]
    async with SessionLocal() as db:
        flagged = await db.scalars(select(AuditLog).where(AuditLog.action == "player.create"))
        assert any((a.metadata_ or {}).get("duplicate_override") for a in flagged)


async def test_duplicate_detection_never_leaks_other_organizations_private_players(client):
    ta, oa = await setup_org(client, "a@x.com", "Org A")
    tb, ob = await setup_org(client, "b@x.com", "Org B")
    await make_player(client, ta, oa, "Secret Prospect", 17)  # private to A

    r = await client.post(
        f"{API}/players", json=player_body("Secret Prospect", 17), headers=hdr(tb, ob)
    )
    assert r.status_code == 201  # B is not warned: it cannot know the player exists

    # but a network-visible player is detected
    await make_player(client, ta, oa, "Open Prospect", 20, visibility="network")
    r = await client.post(
        f"{API}/players", json=player_body("Open Prospect", 20), headers=hdr(tb, ob)
    )
    assert r.status_code == 409


async def test_today_helper_sanity():
    assert date.fromisoformat(dob_for_age(20)) < date.today()
