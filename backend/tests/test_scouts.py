from tests.conftest import hdr, login, make_user
from tests.helpers import API, add_role_member, setup_org


async def scout_setup(client):
    owner_t, org = await setup_org(client)
    scout_t = await add_role_member(client, org, "scout@x.com", "scout")
    return owner_t, org, scout_t


async def member_id(client, token, org, email):
    ms = (
        await client.get(f"{API}/organizations/{org['id']}/members", headers=hdr(token, org))
    ).json()
    return next(m["user_id"] for m in ms if m["email"] == email)


PROFILE = {
    "bio": "Youth specialist", "experience_years": 8,
    "positions": ["CM", "CAM"], "age_groups": ["u19", "u21"], "regions": ["Spain", "Portugal"],
}  # fmt: skip


async def test_manager_creates_profile_for_member(client):
    owner_t, org, _ = await scout_setup(client)
    uid = await member_id(client, owner_t, org, "scout@x.com")
    r = await client.post(
        f"{API}/scouts", json={"user_id": uid, **PROFILE}, headers=hdr(owner_t, org)
    )
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["full_name"] == "scout" and s["org_role"] == "scout" and s["experience_years"] == 8
    assert s["positions"] == ["CAM", "CM"] and s["regions"] == ["Portugal", "Spain"]
    assert s["can_edit"] is True and s["is_active"] is True


async def test_scout_creates_and_edits_own_profile(client):
    owner_t, org, scout_t = await scout_setup(client)
    r = await client.post(
        f"{API}/scouts", json=PROFILE, headers=hdr(scout_t, org)
    )  # no user_id: self
    assert r.status_code == 201 and r.json()["email"] == "scout@x.com"
    sid = r.json()["id"]
    r = await client.patch(
        f"{API}/scouts/{sid}",
        json={"bio": "Updated", "positions": ["GK"]},
        headers=hdr(scout_t, org),
    )
    assert r.status_code == 200 and r.json()["bio"] == "Updated" and r.json()["positions"] == ["GK"]
    assert r.json()["age_groups"] == ["u19", "u21"]  # untouched
    # but cannot deactivate themself or create profiles for others
    assert (
        await client.patch(
            f"{API}/scouts/{sid}", json={"is_active": False}, headers=hdr(scout_t, org)
        )
    ).status_code == 403
    uid = await member_id(client, owner_t, org, "own@x.com")
    assert (
        await client.post(f"{API}/scouts", json={"user_id": uid}, headers=hdr(scout_t, org))
    ).status_code == 403


async def test_cannot_edit_someone_elses_profile(client):
    owner_t, org, scout_t = await scout_setup(client)
    other_t = await add_role_member(client, org, "scout2@x.com", "scout")
    sid = (await client.post(f"{API}/scouts", json=PROFILE, headers=hdr(scout_t, org))).json()["id"]
    r = await client.patch(f"{API}/scouts/{sid}", json={"bio": "hacked"}, headers=hdr(other_t, org))
    assert r.status_code == 403
    listing = (await client.get(f"{API}/scouts", headers=hdr(other_t, org))).json()["items"]
    assert listing[0]["can_edit"] is False
    # a manager can
    assert (
        await client.patch(f"{API}/scouts/{sid}", json={"bio": "ok"}, headers=hdr(owner_t, org))
    ).status_code == 200


async def test_validation_and_rules(client):
    owner_t, org, scout_t = await scout_setup(client)
    h = hdr(owner_t, org)
    uid = await member_id(client, owner_t, org, "scout@x.com")
    for bad in (
        {"experience_years": -1}, {"experience_years": 99}, {"positions": ["XX"]},
        {"age_groups": ["u99"]}, {"regions": [""]}, {"regions": ["x" * 101]},
        {"regions": [f"r{i}" for i in range(11)]},
    ):  # fmt: skip
        assert (
            await client.post(f"{API}/scouts", json={"user_id": uid, **bad}, headers=h)
        ).status_code == 422, bad
    # non-member cannot be profiled
    await make_user("stranger@x.com")
    stranger = await member_id_by_email("stranger@x.com")
    r = await client.post(f"{API}/scouts", json={"user_id": stranger}, headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "not_a_member"
    # one profile per member
    assert (await client.post(f"{API}/scouts", json={"user_id": uid}, headers=h)).status_code == 201
    assert (await client.post(f"{API}/scouts", json={"user_id": uid}, headers=h)).status_code == 409


async def member_id_by_email(email):
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models.user import User

    async with SessionLocal() as db:
        return str(await db.scalar(select(User.id).where(User.email == email)))


async def test_directory_search_filters_and_pagination(client):
    owner_t, org, _ = await scout_setup(client)
    h = hdr(owner_t, org)

    def prof(years, positions, groups, regions):
        return {
            "experience_years": years, "positions": positions,
            "age_groups": groups, "regions": regions,
        }  # fmt: skip

    people = [
        ("Ana Scout", prof(2, ["GK"], ["u15"], ["Brazil"])),
        ("Ben Scout", prof(10, ["CM"], ["u19"], ["Spain"])),
        ("Cid Scout", prof(20, ["CM", "ST"], ["senior"], ["spain"])),
    ]
    for i, (name, prof) in enumerate(people):
        email = f"s{i}@x.com"
        await add_role_member(client, org, email, "scout")
        await _rename(email, name)
        uid = await member_id(client, owner_t, org, email)
        assert (
            await client.post(f"{API}/scouts", json={"user_id": uid, **prof}, headers=h)
        ).status_code == 201

    def names(r):
        return [s["full_name"] for s in r.json()["items"]]

    assert names(await client.get(f"{API}/scouts", headers=h)) == [
        "Ana Scout",
        "Ben Scout",
        "Cid Scout",
    ]
    assert names(await client.get(f"{API}/scouts?q=ben", headers=h)) == ["Ben Scout"]
    assert names(await client.get(f"{API}/scouts?position=CM", headers=h)) == [
        "Ben Scout",
        "Cid Scout",
    ]
    assert names(await client.get(f"{API}/scouts?age_group=u15", headers=h)) == ["Ana Scout"]
    assert names(await client.get(f"{API}/scouts?region=SPAIN", headers=h)) == [
        "Ben Scout",
        "Cid Scout",
    ]
    assert names(await client.get(f"{API}/scouts?min_experience=10", headers=h)) == [
        "Ben Scout",
        "Cid Scout",
    ]
    assert names(await client.get(f"{API}/scouts?position=CM&min_experience=15", headers=h)) == [
        "Cid Scout"
    ]
    assert (await client.get(f"{API}/scouts?q=%25", headers=h)).json()["total"] == 0
    page2 = await client.get(f"{API}/scouts?page=2&page_size=2", headers=h)
    assert names(page2) == ["Cid Scout"] and page2.json()["total"] == 3
    assert (await client.get(f"{API}/scouts?position=ZZ", headers=h)).status_code == 422


async def _rename(email, name):
    from sqlalchemy import update

    from app.db.session import SessionLocal
    from app.models.user import User

    async with SessionLocal() as db:
        await db.execute(update(User).where(User.email == email).values(full_name=name))
        await db.commit()


async def test_deactivate_and_removed_members_disappear(client):
    owner_t, org, scout_t = await scout_setup(client)
    h = hdr(owner_t, org)
    sid = (await client.post(f"{API}/scouts", json=PROFILE, headers=hdr(scout_t, org))).json()["id"]
    assert (await client.get(f"{API}/scouts", headers=h)).json()["total"] == 1

    assert (
        await client.patch(f"{API}/scouts/{sid}", json={"is_active": False}, headers=h)
    ).status_code == 200
    assert (await client.get(f"{API}/scouts", headers=h)).json()["total"] == 0
    assert (await client.get(f"{API}/scouts?status=inactive", headers=h)).json()["total"] == 1
    assert (await client.get(f"{API}/scouts?status=all", headers=h)).json()["total"] == 1

    await client.patch(f"{API}/scouts/{sid}", json={"is_active": True}, headers=h)
    mid = next(
        m["id"]
        for m in (await client.get(f"{API}/organizations/{org['id']}/members", headers=h)).json()
        if m["email"] == "scout@x.com"
    )
    await client.delete(f"{API}/organizations/{org['id']}/members/{mid}", headers=h)
    assert (await client.get(f"{API}/scouts?status=all", headers=h)).json()["total"] == 0
    assert (await client.get(f"{API}/scouts/{sid}", headers=h)).status_code == 404


async def test_permissions_and_isolation(client):
    owner_t, org, scout_t = await scout_setup(client)
    coach_t = await add_role_member(client, org, "coach@x.com", "coach")
    sid = (await client.post(f"{API}/scouts", json=PROFILE, headers=hdr(scout_t, org))).json()["id"]
    # coaches have no access to the scout directory
    assert (await client.get(f"{API}/scouts", headers=hdr(coach_t, org))).status_code == 403
    assert (await client.get(f"{API}/scouts/{sid}", headers=hdr(coach_t, org))).status_code == 403
    assert (await client.get(f"{API}/scouts")).status_code == 401
    no_org = {"Authorization": hdr(owner_t, org)["Authorization"]}  # no organization selected
    assert (await client.get(f"{API}/scouts", headers=no_org)).status_code == 403

    other_t, other_org = await setup_org(client, "o2@x.com", "Other Org")
    ho = hdr(other_t, other_org)
    assert (await client.get(f"{API}/scouts", headers=ho)).json()["total"] == 0
    assert (await client.get(f"{API}/scouts/{sid}", headers=ho)).status_code == 404
    assert (
        await client.patch(f"{API}/scouts/{sid}", json={"bio": "x"}, headers=ho)
    ).status_code == 404
    assert (
        await client.get(f"{API}/scouts", headers=hdr(other_t, org))
    ).status_code == 403  # spoofed header
    assert login  # (imported for parity with other test modules)
