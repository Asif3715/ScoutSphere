from tests.conftest import hdr
from tests.helpers import (
    API,
    add_clubs,
    add_role_member,
    make_club,
    make_comp,
    make_season,
    platform_headers,
    ref_club,
    setup_org,
)


async def test_org_competition_season_participant_flow(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    ph = await platform_headers(client)
    ref = await ref_club(client, ph, "Reference FC")
    own = await make_club(client, token, org, "Own FC")

    comp = await make_comp(
        client, h, "Alpha Youth League", country="England", competition_type="youth_league"
    )
    assert comp["is_global"] is False and comp["editable"] is True and comp["season_count"] == 0

    season = await make_season(client, h, comp)
    await add_clubs(client, h, season, ref, own)
    detail = (await client.get(f"{API}/seasons/{season['id']}", headers=h)).json()
    assert detail["participant_count"] == 2 and detail["competition_name"] == "Alpha Youth League"
    assert sorted(p["club_name"] for p in detail["participants"]) == ["Own FC", "Reference FC"]

    r = await client.get(f"{API}/competitions/{comp['id']}", headers=h)
    assert r.json()["seasons"][0]["participant_count"] == 2 and r.json()["season_count"] == 1

    r = await client.patch(
        f"{API}/competitions/{comp['id']}",
        json={"name": "Alpha Cup", "competition_type": "cup"},
        headers=h,
    )
    assert r.status_code == 200 and r.json()["competition_type"] == "cup"
    r = await client.patch(
        f"{API}/seasons/{season['id']}", json={"end_date": "2026-06-30"}, headers=h
    )
    assert r.status_code == 200
    assert (
        await client.delete(f"{API}/seasons/{season['id']}/participants/{own['id']}", headers=h)
    ).json()["participant_count"] == 1
    assert (await client.delete(f"{API}/seasons/{season['id']}", headers=h)).status_code == 204
    assert (await client.delete(f"{API}/competitions/{comp['id']}", headers=h)).status_code == 204
    assert (await client.get(f"{API}/competitions", headers=h)).json()["total"] == 0


async def test_validation(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    for bad in ({"name": "x"}, {"name": "Ok League", "competition_type": "tournament"}):
        assert (await client.post(f"{API}/competitions", json=bad, headers=h)).status_code == 422
    comp = await make_comp(client, h)
    base = f"{API}/competitions/{comp['id']}/seasons"
    assert (
        await client.post(
            base,
            json={"name": "S", "start_date": "2026-01-01", "end_date": "2025-01-01"},
            headers=h,
        )
    ).status_code == 422
    assert (
        await client.post(
            base, json={"name": "", "start_date": "2025-01-01", "end_date": "2026-01-01"}, headers=h
        )
    ).status_code == 422
    season = await make_season(client, h, comp, "2025/26")
    r = await client.post(
        base,
        json={"name": "2025/26", "start_date": "2025-01-01", "end_date": "2026-01-01"},
        headers=h,
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "season_exists"
    r = await client.patch(
        f"{API}/seasons/{season['id']}", json={"start_date": "2030-01-01"}, headers=h
    )
    assert r.status_code == 422  # would end before it starts
    r = await client.post(f"{API}/competitions", json={"name": "alpha league"}, headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "competition_exists"


async def test_participants_rules(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    ph = await platform_headers(client)
    ref = await ref_club(client, ph, "Ref One")
    comp = await make_comp(client, h)
    season = await make_season(client, h, comp)
    await add_clubs(client, h, season, ref)
    r = await client.post(
        f"{API}/seasons/{season['id']}/participants", json={"club_id": ref["id"]}, headers=h
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_participant"
    r = await client.post(
        f"{API}/seasons/{season['id']}/participants",
        json={"club_id": "00000000-0000-0000-0000-000000000000"},
        headers=h,
    )
    assert r.status_code == 422
    assert (
        await client.delete(f"{API}/seasons/{season['id']}/participants/{ref['id']}x", headers=h)
    ).status_code == 422
    other = "00000000-0000-0000-0000-000000000000"
    assert (
        await client.delete(f"{API}/seasons/{season['id']}/participants/{other}", headers=h)
    ).status_code == 404


async def test_cannot_use_another_orgs_private_club(client):
    ta, oa = await setup_org(client, "a@x.com", "Org A")
    tb, ob = await setup_org(client, "b@x.com", "Org B")
    secret = await make_club(client, tb, ob, "B Private FC")
    comp = await make_comp(client, hdr(ta, oa))
    season = await make_season(client, hdr(ta, oa), comp)
    r = await client.post(
        f"{API}/seasons/{season['id']}/participants",
        json={"club_id": secret["id"]},
        headers=hdr(ta, oa),
    )
    assert r.status_code == 422


async def test_global_competitions_are_read_only_for_tenants(client):
    ph = await platform_headers(client)
    g = await make_comp(
        client, ph, "World League", country="Spain"
    )  # platform admin, no org header
    assert g["is_global"] is True
    gs = await make_season(client, ph, g)
    r1 = await ref_club(client, ph, "Madrid A")
    await add_clubs(client, ph, gs, r1)

    token, org = await setup_org(client)
    h = hdr(token, org)
    own = await make_club(client, token, org, "Own FC")
    listing = (await client.get(f"{API}/competitions", headers=h)).json()
    assert [c["name"] for c in listing["items"]] == ["World League"] and listing["items"][0][
        "editable"
    ] is False
    assert (await client.get(f"{API}/competitions/{g['id']}", headers=h)).status_code == 200
    assert (await client.get(f"{API}/seasons/{gs['id']}", headers=h)).json()["editable"] is False

    # tenants cannot change anything global (looks like "not found")
    assert (
        await client.patch(f"{API}/competitions/{g['id']}", json={"name": "Hijacked"}, headers=h)
    ).status_code == 404
    assert (await client.delete(f"{API}/competitions/{g['id']}", headers=h)).status_code == 404
    assert (
        await client.post(
            f"{API}/competitions/{g['id']}/seasons",
            json={"name": "x", "start_date": "2025-01-01", "end_date": "2026-01-01"},
            headers=h,
        )
    ).status_code == 404
    assert (
        await client.post(
            f"{API}/seasons/{gs['id']}/participants", json={"club_id": own["id"]}, headers=h
        )
    ).status_code == 404
    assert (await client.delete(f"{API}/seasons/{gs['id']}", headers=h)).status_code == 404

    # a global competition can never list a private club
    r = await client.post(
        f"{API}/seasons/{gs['id']}/participants", json={"club_id": own["id"]}, headers=ph
    )
    assert r.status_code == 422


async def test_platform_endpoints_need_platform_admin(client):
    token, org = await setup_org(client)
    no_org = {"Authorization": hdr(token, org)["Authorization"]}
    assert (
        await client.post(f"{API}/competitions", json={"name": "Sneaky League"}, headers=no_org)
    ).status_code == 403
    assert (await client.get(f"{API}/competitions", headers=no_org)).status_code == 403
    from tests.conftest import login, make_user

    await make_user("help@x.com", platform_role="platform_support")
    support = {"Authorization": f"Bearer {await login(client, 'help@x.com')}"}
    assert (
        await client.post(f"{API}/competitions", json={"name": "Support League"}, headers=support)
    ).status_code == 403
    assert (await client.get(f"{API}/competitions")).status_code == 401


async def test_roles_and_isolation(client):
    owner_t, org = await setup_org(client)
    scout_t = await add_role_member(client, org, "scout@x.com", "scout")
    coach_t = await add_role_member(client, org, "coach@x.com", "coach")
    admin_t = await add_role_member(client, org, "admin@x.com", "club_admin")
    comp = await make_comp(client, hdr(admin_t, org))  # admins manage
    for t in (scout_t, coach_t):  # read only
        assert (
            await client.get(f"{API}/competitions/{comp['id']}", headers=hdr(t, org))
        ).status_code == 200
        assert (
            await client.post(
                f"{API}/competitions", json={"name": "Nope League"}, headers=hdr(t, org)
            )
        ).status_code == 403
        assert (
            await client.patch(
                f"{API}/competitions/{comp['id']}", json={"country": "x"}, headers=hdr(t, org)
            )
        ).status_code == 403

    other_t, other_org = await setup_org(client, "o2@x.com", "Other Org")
    ho = hdr(other_t, other_org)
    assert (await client.get(f"{API}/competitions", headers=ho)).json()["total"] == 0
    assert (await client.get(f"{API}/competitions/{comp['id']}", headers=ho)).status_code == 404
    assert (
        await client.patch(f"{API}/competitions/{comp['id']}", json={"country": "x"}, headers=ho)
    ).status_code == 404
    assert (await client.get(f"{API}/competitions?q=%25", headers=hdr(owner_t, org))).json()[
        "total"
    ] == 0


async def test_same_name_allowed_in_different_scopes(client):
    ta, oa = await setup_org(client, "a@x.com", "Org A")
    tb, ob = await setup_org(client, "b@x.com", "Org B")
    ph = await platform_headers(client)
    await make_comp(client, ph, "Premier Test")
    await make_comp(client, hdr(ta, oa), "Premier Test")
    await make_comp(client, hdr(tb, ob), "Premier Test")
    assert (await client.get(f"{API}/competitions", headers=hdr(ta, oa))).json()[
        "total"
    ] == 2  # global + own
