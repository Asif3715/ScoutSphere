import pytest

from app.core.config import get_settings
from tests.conftest import PASSWORD, bearer, hdr, login, make_user
from tests.helpers import API, add_role_member, dob_for_age, make_club, make_player, setup_org
from tests.test_player_photos import image_bytes

ME = f"{API}/me/player"
CLAIMS = f"{API}/player-claims"


@pytest.fixture(autouse=True)
def media_root(tmp_path):
    settings = get_settings()
    old = settings.media_root
    settings.media_root = str(tmp_path)
    yield tmp_path
    settings.media_root = old


async def player_user(client, email="ana@x.com", name="Ana Player"):
    user = await make_user(email, account_type="player")
    return bearer(await login(client, email)), user


async def world(client, *, age=22, name="Ana Costa"):
    """An organization with one player record, a player account and an admin."""
    owner_t, org = await setup_org(client)
    player = await make_player(client, owner_t, org["id"], name, age)
    admin_t = await add_role_member(client, org, "admin@x.com", "club_admin")
    scout_t = await add_role_member(client, org, "scout@x.com", "scout")
    h, _ = await player_user(client)
    return org, player, owner_t, hdr(admin_t, org["id"]), hdr(scout_t, org["id"]), h


async def search(client, h, name, dob):
    return await client.get(f"{ME}/search", params={"name": name, "date_of_birth": dob}, headers=h)


async def claim(client, h, player, dob=None, **kw):
    return await client.post(
        f"{ME}/claims",
        json={"player_id": player["id"], "date_of_birth": dob or player["date_of_birth"], **kw},
        headers=h,
    )


async def approved(client, admin_h, ph, player, org=None):
    c = await claim(client, ph, player, message="That's me")
    assert c.status_code == 201, c.text
    r = await client.post(
        f"{CLAIMS}/{c.json()['id']}/decision", json={"decision": "approved"}, headers=admin_h
    )
    assert r.status_code == 200, r.text
    return c.json()["id"]


# ---- finding your profile ---------------------------------------------------------------
async def test_search_needs_name_and_matching_birth_date(client):
    org, player, _, admin_h, _, h = await world(client)
    dob = player["date_of_birth"]
    found = await search(client, h, "ana", dob)
    assert found.status_code == 200
    [hit] = found.json()
    assert hit["player_id"] == player["id"] and hit["reviewed_by"] == org["name"]
    assert "date_of_birth" not in hit  # nothing identifying beyond what they already told us
    assert (await search(client, h, "ana", dob_for_age(30))).json() == []
    assert (await search(client, h, "zzz", dob)).json() == []
    assert (await client.get(f"{ME}/search", params={"name": "a"}, headers=h)).status_code == 422


async def test_only_player_accounts_can_search_or_claim(client):
    org, player, owner_t, admin_h, scout_h, _ = await world(client)
    assert (await search(client, scout_h, "ana", player["date_of_birth"])).status_code == 403
    assert (await claim(client, scout_h, player)).status_code == 403
    assert (await client.get(ME)).status_code == 401


async def test_profile_is_missing_until_a_claim_is_approved(client):
    org, player, _, admin_h, _, h = await world(client)
    none = await client.get(ME, headers=h)
    assert none.status_code == 404 and none.json()["error"]["code"] == "no_profile"


# ---- claiming ---------------------------------------------------------------------------
async def test_claim_rules(client):
    org, player, _, admin_h, _, h = await world(client)
    bad = await claim(client, h, player, dob=dob_for_age(40))
    assert bad.status_code == 404  # wrong birth date looks exactly like "no such player"
    unknown = await client.post(
        f"{ME}/claims",
        json={
            "player_id": "00000000-0000-0000-0000-000000000000",
            "date_of_birth": player["date_of_birth"],
        },
        headers=h,
    )
    assert unknown.status_code == 404
    first = await claim(client, h, player, message="Hi, it's me")
    assert first.status_code == 201 and first.json()["status"] == "pending"
    again = await claim(client, h, player)
    assert again.status_code == 409 and again.json()["error"]["code"] == "claim_pending"
    mine = (await client.get(f"{ME}/claims", headers=h)).json()
    assert [c["status"] for c in mine] == ["pending"]


async def test_cancel_and_resubmit(client):
    org, player, _, admin_h, _, h = await world(client)
    c = (await claim(client, h, player)).json()
    out = await client.delete(f"{ME}/claims/{c['id']}", headers=h)
    assert out.status_code == 200 and out.json()["status"] == "cancelled"
    assert (await client.delete(f"{ME}/claims/{c['id']}", headers=h)).status_code == 409
    assert (await claim(client, h, player)).status_code == 201


async def test_reviewers_are_notified_and_only_they_see_requests(client):
    org, player, owner_t, admin_h, scout_h, h = await world(client)
    await claim(client, h, player, message="It's me")
    pending = await client.get(CLAIMS, headers=admin_h)
    [c] = pending.json()
    assert c["requester_email"] == "ana@x.com" and c["player_name"] == "Ana Costa"
    assert c["message"] == "It's me" and c["status"] == "pending"
    n = (await client.get(f"{API}/notifications", headers=bearer(owner_t))).json()["items"]
    assert n[0]["type"] == "player_claim_requested" and n[0]["link_path"] == "/players/claims"
    assert (await client.get(CLAIMS, headers=scout_h)).status_code == 403  # scouts can't review
    assert (await client.get(CLAIMS, headers=h)).status_code in (400, 403)  # player: no org


async def test_another_organization_cannot_see_or_decide_a_claim(client):
    org, player, _, admin_h, _, h = await world(client)
    c = (await claim(client, h, player)).json()
    other_t, other = await setup_org(client, "other@x.com", "Other FC")
    oh = hdr(other_t, other["id"])
    assert (await client.get(CLAIMS, headers=oh)).json() == []
    r = await client.post(f"{CLAIMS}/{c['id']}/decision", json={"decision": "approved"}, headers=oh)
    assert r.status_code == 404
    assert (await client.get(ME, headers=h)).status_code == 404  # still not linked


# ---- deciding ---------------------------------------------------------------------------
async def test_approval_links_the_profile_and_notifies_the_player(client):
    org, player, _, admin_h, _, h = await world(client)
    await approved(client, admin_h, h, player)
    me = await client.get(ME, headers=h)
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["player_id"] == player["id"] and body["full_name"] == "Ana Costa"
    assert body["managed_by"] == org["name"] and body["visibility"] == "private"
    n = (await client.get(f"{API}/notifications", headers=h)).json()["items"]
    assert n[0]["type"] == "player_claim_approved" and n[0]["link_path"] == "/player"
    # the club-side record now says it has an account
    club_view = (await client.get(f"{API}/players/{player['id']}", headers=admin_h)).json()
    assert club_view["claimed"] is True
    assert (await search(client, h, "ana", player["date_of_birth"])).json() == []  # taken
    done = (await client.get(f"{CLAIMS}?status=approved", headers=admin_h)).json()
    assert done[0]["decided_by_name"] == "admin"


async def test_rejection_needs_a_reason_and_leaves_the_profile_unlinked(client):
    org, player, _, admin_h, _, h = await world(client)
    c = (await claim(client, h, player)).json()
    url = f"{CLAIMS}/{c['id']}/decision"
    no_reason = await client.post(url, json={"decision": "rejected"}, headers=admin_h)
    assert no_reason.status_code == 422
    ok = await client.post(
        url, json={"decision": "rejected", "note": "Please use your club email"}, headers=admin_h
    )
    assert ok.status_code == 200 and ok.json()["status"] == "rejected"
    assert (await client.get(ME, headers=h)).status_code == 404
    mine = (await client.get(f"{ME}/claims", headers=h)).json()
    assert mine[0]["status"] == "rejected" and "club email" in mine[0]["decision_note"]
    n = (await client.get(f"{API}/notifications", headers=h)).json()["items"]
    assert n[0]["type"] == "player_claim_rejected"
    assert (
        await client.post(url, json={"decision": "approved"}, headers=admin_h)
    ).status_code == 409


async def test_approving_one_claim_declines_competing_ones(client):
    org, player, _, admin_h, _, h = await world(client)
    h2, _ = await player_user(client, "ana2@x.com")
    a = (await claim(client, h, player)).json()
    b = (await claim(client, h2, player)).json()
    r = await client.post(
        f"{CLAIMS}/{a['id']}/decision", json={"decision": "approved"}, headers=admin_h
    )
    assert r.status_code == 200
    mine2 = (await client.get(f"{ME}/claims", headers=h2)).json()
    assert mine2[0]["id"] == b["id"] and mine2[0]["status"] == "rejected"
    assert (await client.get(ME, headers=h2)).status_code == 404
    # and the profile cannot be claimed again
    h3, _ = await player_user(client, "ana3@x.com")
    assert (await claim(client, h3, player)).status_code == 404


async def test_a_linked_account_cannot_claim_a_second_profile(client):
    org, player, owner_t, admin_h, _, h = await world(client)
    await approved(client, admin_h, h, player)
    other = await make_player(client, owner_t, org["id"], "Ana Costa", 22)
    r = await claim(client, h, other)
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_claimed"


# ---- editing your own profile ------------------------------------------------------------
async def test_player_edits_only_the_allowed_fields(client):
    org, player, _, admin_h, _, h = await world(client)
    await approved(client, admin_h, h, player)
    r = await client.patch(
        ME,
        json={"biography": "Left-footed playmaker.", "height_cm": 181, "preferred_foot": "left",
              "primary_position": "CAM", "secondary_positions": ["CM", "LW"]},
        headers=h,
    )  # fmt: skip
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["height_cm"] == 181 and body["secondary_positions"] == ["CM", "LW"]
    assert body["primary_position"] == "CAM" and body["biography"].startswith("Left-footed")
    # name, date of birth and unknown fields are the club's: ignored or refused
    ignored = await client.patch(ME, json={"full_name": "Someone Else"}, headers=h)
    assert (await client.get(ME, headers=h)).json()["full_name"] == "Ana Costa"
    assert ignored.status_code in (200, 422)
    assert (await client.patch(ME, json={"height_cm": 20}, headers=h)).status_code == 422
    # the club sees the player's changes
    club = (await client.get(f"{API}/players/{player['id']}", headers=admin_h)).json()
    assert club["height_cm"] == 181 and club["biography"].startswith("Left-footed")


async def test_player_controls_visibility_and_the_club_cannot_override_it(client):
    org, player, _, admin_h, _, h = await world(client)
    await approved(client, admin_h, h, player)
    res = await client.patch(ME, json={"visibility": "network"}, headers=h)
    assert res.status_code == 200 and res.json()["visibility"] == "network"
    # another organization can now find them
    other_t, other = await setup_org(client, "other@x.com", "Other FC")
    seen = await client.get(f"{API}/players/{player['id']}", headers=hdr(other_t, other["id"]))
    assert seen.status_code == 200
    # the owning club may no longer change it...
    club = await client.patch(
        f"{API}/players/{player['id']}", json={"visibility": "private"}, headers=admin_h
    )
    assert club.status_code == 409 and club.json()["error"]["code"] == "controlled_by_player"
    # ...but can still edit the rest of the record
    ok = await client.patch(
        f"{API}/players/{player['id']}", json={"nationality": "Portugal"}, headers=admin_h
    )
    assert ok.status_code == 200
    # and the player can hide again
    back = await client.patch(ME, json={"visibility": "private"}, headers=h)
    assert back.json()["visibility"] == "private"
    gone = await client.get(f"{API}/players/{player['id']}", headers=hdr(other_t, other["id"]))
    assert gone.status_code == 404
    assert (await client.patch(ME, json={"visibility": "public"}, headers=h)).status_code == 422


async def test_contact_email_is_shown_to_other_clubs_only_when_open_to_offers(client):
    org, player, _, admin_h, _, h = await world(client)
    await approved(client, admin_h, h, player)
    need = await client.patch(ME, json={"open_to_offers": True}, headers=h)
    assert need.status_code == 422 and need.json()["error"]["code"] == "contact_required"
    await client.patch(
        ME, json={"visibility": "network", "contact_email": "ana@agent.com"}, headers=h
    )
    other_t, other = await setup_org(client, "other@x.com", "Other FC")
    oh = hdr(other_t, other["id"])
    url = f"{API}/players/{player['id']}"
    assert (await client.get(url, headers=oh)).json()["contact_email"] is None
    assert (await client.get(url, headers=admin_h)).json()["contact_email"] == "ana@agent.com"
    await client.patch(ME, json={"open_to_offers": True}, headers=h)
    seen = (await client.get(url, headers=oh)).json()
    assert seen["open_to_offers"] is True and seen["contact_email"] == "ana@agent.com"
    await client.patch(ME, json={"open_to_offers": False}, headers=h)
    assert (await client.get(url, headers=oh)).json()["contact_email"] is None


async def test_minors_cannot_change_who_sees_or_contacts_them(client):
    org, player, _, admin_h, _, h = await world(client, age=16)
    await approved(client, admin_h, h, player)
    for body in ({"visibility": "network"}, {"open_to_offers": True}, {"contact_email": "a@b.com"}):
        r = await client.patch(ME, json=body, headers=h)
        assert r.status_code == 403 and r.json()["error"]["code"] == "guardian_required"
    ok = await client.patch(ME, json={"biography": "Academy captain."}, headers=h)
    assert ok.status_code == 200 and ok.json()["is_minor"] is True


async def test_player_photo_upload_and_removal(client):
    org, player, _, admin_h, _, h = await world(client)
    await approved(client, admin_h, h, player)
    up = await client.put(
        f"{ME}/photo", files={"file": ("p.jpg", image_bytes(), "image/jpeg")}, headers=h
    )
    assert up.status_code == 200, up.text
    assert up.json()["has_uploaded_photo"] and up.json()["photo_url"].startswith("/api/v1/media/")
    club = (await client.get(f"{API}/players/{player['id']}", headers=admin_h)).json()
    assert club["has_uploaded_photo"] is True
    bad = await client.put(
        f"{ME}/photo", files={"file": ("p.txt", b"not an image", "text/plain")}, headers=h
    )
    assert bad.status_code == 422
    gone = await client.delete(f"{ME}/photo", headers=h)
    assert gone.status_code == 200 and gone.json()["has_uploaded_photo"] is False


async def test_career_history_is_shown_read_only(client):
    org, player, owner_t, admin_h, _, h = await world(client)
    club = await make_club(client, owner_t, org["id"], "Alpha Senior")
    spell = await client.post(
        f"{API}/players/{player['id']}/career",
        json={"club_id": club["id"], "start_date": "2024-07-01", "appearances": 30, "goals": 9},
        headers=hdr(owner_t, org["id"]),
    )
    assert spell.status_code == 201, spell.text
    await approved(client, admin_h, h, player)
    me = (await client.get(ME, headers=h)).json()
    assert me["current_club"]["club_name"] == "Alpha Senior"
    assert me["career"][0]["club_name"] == "Alpha Senior" and me["career"][0]["goals"] == 9


async def test_password_still_works_for_player_accounts(client):
    # sanity: the factory made a real, loginable account
    await make_user("p@x.com", account_type="player")
    r = await client.post(f"{API}/auth/login", json={"email": "p@x.com", "password": PASSWORD})
    assert r.status_code == 200 and r.json()["user"]["account_type"] == "player"


# ---- the club is told when a player edits their profile ---------------------------------
async def _updates(client, token):
    items = (await client.get(f"{API}/notifications", headers=bearer(token))).json()["items"]
    return [n for n in items if n["type"] == "player_profile_updated"]


async def test_club_staff_are_notified_when_a_player_edits_their_profile(client):
    org, player, owner_t, admin_h, scout_h, h = await world(client)
    await approved(client, admin_h, h, player)
    admin_t = admin_h["Authorization"].split()[1]
    scout_t = scout_h["Authorization"].split()[1]
    assert await _updates(client, owner_t) == []  # nothing before the player does anything

    await client.patch(ME, json={"height_cm": 181, "biography": "Playmaker."}, headers=h)
    for token in (owner_t, admin_t):
        [n] = await _updates(client, token)
        assert n["title"] == "Ana Costa updated their own profile"
        assert n["body"] == "Changed: biography, height"
        assert n["link_path"] == f"/players/{player['id']}"
    assert await _updates(client, scout_t) == []  # scouts don't manage players

    # more edits fold into the same unread notification instead of piling up
    await client.patch(ME, json={"preferred_foot": "left", "height_cm": 182}, headers=h)
    [n] = await _updates(client, owner_t)
    assert n["body"] == "Changed: biography, height, preferred foot"

    # a visibility change is called out in words
    await client.patch(ME, json={"visibility": "network"}, headers=h)
    [n] = await _updates(client, owner_t)
    assert n["body"].endswith("visibility · now visible to every organization")
    await client.patch(ME, json={"biography": "Updated."}, headers=h)
    [n] = await _updates(client, owner_t)
    assert "now visible to every organization" in n["body"]  # kept when merging


async def test_a_read_notification_is_followed_by_a_new_one(client):
    org, player, owner_t, admin_h, _, h = await world(client)
    await approved(client, admin_h, h, player)
    await client.patch(ME, json={"height_cm": 181}, headers=h)
    [first] = await _updates(client, owner_t)
    await client.post(f"{API}/notifications/{first['id']}/read", headers=bearer(owner_t))
    await client.patch(ME, json={"weight_kg": 70}, headers=h)
    assert [n["body"] for n in await _updates(client, owner_t)] == [
        "Changed: weight",
        "Changed: height",
    ]


async def test_photo_changes_and_rejected_edits_notify_correctly(client):
    org, player, owner_t, admin_h, _, h = await world(client)
    await approved(client, admin_h, h, player)
    await client.put(
        f"{ME}/photo", files={"file": ("p.jpg", image_bytes(), "image/jpeg")}, headers=h
    )
    [n] = await _updates(client, owner_t)
    assert n["body"] == "Changed: photo"
    await client.delete(f"{ME}/photo", headers=h)
    [n] = await _updates(client, owner_t)
    assert n["body"] == "Changed: photo · removed"
    # an edit that fails validation, or an empty one, tells nobody anything
    before = await _updates(client, owner_t)
    assert (await client.patch(ME, json={"height_cm": 20}, headers=h)).status_code == 422
    await client.patch(ME, json={}, headers=h)
    assert await _updates(client, owner_t) == before


async def test_staff_can_switch_these_notifications_off(client):
    org, player, owner_t, admin_h, _, h = await world(client)
    await approved(client, admin_h, h, player)
    off = await client.put(
        f"{API}/notifications/preferences",
        json={"preferences": {"player_profile_updated": False}},
        headers=bearer(owner_t),
    )
    assert off.status_code == 200
    await client.patch(ME, json={"height_cm": 181}, headers=h)
    assert await _updates(client, owner_t) == []
    assert len(await _updates(client, admin_h["Authorization"].split()[1])) == 1


# ---- squads: the player hears about it; managers are prompted when a candidate signs ------
from tests.helpers import make_team  # noqa: E402
from tests.test_recruitment import pipeline  # noqa: E402

REC = f"{API}/recruitment"


async def _squad_news(client, h):
    items = (await client.get(f"{API}/notifications", headers=h)).json()["items"]
    return [n for n in items if n["type"] in ("squad_joined", "squad_left")]


async def test_player_is_told_when_added_moved_and_released(client):
    org, player, owner_t, admin_h, _, h = await world(client)
    await approved(client, admin_h, h, player)
    club = await make_club(client, owner_t, org["id"], "Alpha Senior")
    first = await make_team(client, owner_t, org["id"], club, "First Team")
    youth = await make_team(client, owner_t, org["id"], club, "U21", "u21")
    oh = hdr(owner_t, org["id"])

    added = await client.post(
        f"{API}/teams/{first['id']}/players", json={"player_id": player["id"]}, headers=oh
    )
    assert added.status_code == 201, added.text
    [n] = await _squad_news(client, h)
    assert (
        n["type"] == "squad_joined" and n["title"] == "You have joined First Team at Alpha Senior"
    )
    assert n["link_path"] == "/player"

    member = added.json()["players"][0]["membership_id"]
    moved = await client.post(
        f"{API}/teams/{first['id']}/players/{member}/transfer",
        json={"to_team_id": youth["id"]},
        headers=oh,
    )
    assert moved.status_code == 200, moved.text
    assert (await _squad_news(client, h))[0]["title"] == "You have moved to U21 at Alpha Senior"

    new_member = moved.json()["players"][0]["membership_id"]
    rel = await client.delete(f"{API}/teams/{youth['id']}/players/{new_member}", headers=oh)
    assert rel.status_code == 200
    news = await _squad_news(client, h)
    assert (
        news[0]["type"] == "squad_left" and news[0]["title"] == "You have left U21 at Alpha Senior"
    )
    assert len(news) == 3


async def test_players_without_an_account_are_not_notified_and_nothing_breaks(client):
    owner_t, org = await setup_org(client)
    player = await make_player(client, owner_t, org["id"], "No Account", 21)
    club = await make_club(client, owner_t, org["id"])
    team = await make_team(client, owner_t, org["id"], club)
    r = await client.post(
        f"{API}/teams/{team['id']}/players",
        json={"player_id": player["id"]},
        headers=hdr(owner_t, org["id"]),
    )
    assert r.status_code == 201, r.text


async def test_signing_a_candidate_prompts_club_managers_to_add_them_to_a_team(client):
    from tests.helpers import scouting_setup

    s = await scouting_setup(client)
    req, p, cand = await pipeline(client, s)
    for stage in ("negotiation", "signed"):
        r = await client.post(
            f"{REC}/candidates/{cand['id']}/stage", json={"to": stage}, headers=s.rm_h
        )
        assert r.status_code == 200, r.text
    # the recruitment manager did the signing; the owner can put players in teams
    owner = (await client.get(f"{API}/notifications", headers=bearer(s.owner_t))).json()["items"]
    [n] = [x for x in owner if x["type"] == "candidate_signed"]
    assert (
        n["title"] == "Pipeline Player has signed" and n["link_path"] == f"/recruitment/{req['id']}"
    )
    rm = (await client.get(f"{API}/notifications", headers=s.rm_h)).json()["items"]
    assert not [
        x for x in rm if x["type"] == "candidate_signed"
    ]  # no squad permission, and they did it
    detail = (await client.get(f"{REC}/candidates/{cand['id']}", headers=s.rm_h)).json()
    assert detail["stage"] == "signed" and detail["squad_team_id"] is None


async def test_no_prompt_when_the_player_is_already_in_a_team_and_candidates_show_their_team(
    client,
):
    from tests.helpers import scouting_setup

    s = await scouting_setup(client)
    req, p, cand = await pipeline(client, s)
    club = await make_club(client, s.owner_t, s.org["id"], "Alpha Senior")
    team = await make_team(client, s.owner_t, s.org["id"], club, "First Team")
    await client.post(
        f"{API}/teams/{team['id']}/players", json={"player_id": p["id"]}, headers=s.owner_h
    )
    await client.post(
        f"{REC}/candidates/{cand['id']}/stage", json={"to": "negotiation"}, headers=s.rm_h
    )
    await client.post(f"{REC}/candidates/{cand['id']}/stage", json={"to": "signed"}, headers=s.rm_h)
    owner = (await client.get(f"{API}/notifications", headers=bearer(s.owner_t))).json()["items"]
    assert not [x for x in owner if x["type"] == "candidate_signed"]
    detail = (await client.get(f"{REC}/candidates/{cand['id']}", headers=s.rm_h)).json()
    assert (
        detail["squad_team_id"] == team["id"]
        and detail["squad_team_name"] == "First Team · Alpha Senior"
    )


async def test_two_claims_sent_at_once_cannot_both_be_pending(client):
    import asyncio

    org, player, owner_t, admin_h, _, h = await world(client)
    other = await make_player(client, owner_t, org["id"], "Ana Costa", 22)
    results = await asyncio.gather(claim(client, h, player), claim(client, h, other))
    codes = sorted(r.status_code for r in results)
    assert codes == [201, 409], [r.text for r in results]
    assert [c["status"] for c in (await client.get(f"{ME}/claims", headers=h)).json()] == [
        "pending"
    ]
