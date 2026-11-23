import pytest

from app.domain.recruitment import can_move
from tests.conftest import hdr
from tests.helpers import (
    API,
    REC,
    add_role_member,
    add_spell,
    approved_report,
    full_ratings,
    in_days,
    make_assignment,
    make_club,
    make_player,
    make_requirement,
    notes,
    scouting_setup,
    setup_org,
    unread,
)
from tests.helpers import (
    move as move_assignment,
)


# ---- the stage rules themselves (pure) -----------------------------------------------------
@pytest.mark.parametrize(
    ("current", "target", "allowed"),
    [
        ("discovered", "under_evaluation", True), ("discovered", "negotiation", True),  # skipping ahead
        ("negotiation", "shortlisted", True),  # stepping back to fix a mistake
        ("discovered", "signed", False), ("trial_proposed", "signed", False),
        ("negotiation", "signed", True), ("signed", "archived", False), ("signed", "discovered", False),
        ("discovered", "rejected", True), ("negotiation", "archived", True),
        ("rejected", "discovered", True), ("archived", "discovered", True),
        ("rejected", "shortlisted", False), ("archived", "negotiation", False),
        ("discovered", "discovered", False),
    ],
)  # fmt: skip
def test_stage_rules(current, target, allowed):
    assert can_move(current, target) is allowed


# ---- requirements --------------------------------------------------------------------------
async def test_create_get_and_list_requirement(client):
    s = await scouting_setup(client)
    r = await make_requirement(
        client, s, min_age=18, max_age=23, nationality="Croatia", preferred_foot="right",
        min_appearances=40, budget_min=1_000_000, budget_max=5_000_000, currency="eur",
        contract_notes="3-year deal", instructions="Good passer", priority="high",
        attributes={"passing": 7, "ball_control": 6},
    )  # fmt: skip
    assert (
        r["status"] == "draft"
        and r["currency"] == "EUR"
        and r["attributes"] == {"passing": 7, "ball_control": 6}
    )
    assert (
        r["created_by_name"] == "rm"
        and r["allowed_statuses"] == ["cancelled", "open"]
        and r["candidate_count"] == 0
    )
    got = (
        await client.get(f"{REC}/requirements/{r['id']}", headers=s.coach_h)
    ).json()  # coaches can read
    assert got["title"] == "Creative midfielder"
    listing = (await client.get(f"{REC}/requirements", headers=s.rm_h)).json()
    assert listing["total"] == 1 and listing["items"][0]["priority"] == "high"
    assert (await client.get(f"{REC}/requirements?status=open", headers=s.rm_h)).json()[
        "total"
    ] == 0
    assert (await client.get(f"{REC}/requirements?q=creative", headers=s.rm_h)).json()["total"] == 1
    assert (await client.get(f"{REC}/requirements?q=%25", headers=s.rm_h)).json()["total"] == 0


async def test_requirement_validation(client):
    s = await scouting_setup(client)
    bad = [
        {"title": "ab"}, {"title": "   "}, {"position": "QB"}, {"min_age": 30, "max_age": 20},
        {"min_age": 5}, {"max_age": 99}, {"preferred_foot": "middle"}, {"min_appearances": -1},
        {"budget_min": 10, "budget_max": 5, "currency": "EUR"}, {"budget_min": 5},  # currency missing
        {"currency": "EURO", "budget_min": 5}, {"priority": "asap"},
        {"attributes": {"teleporting": 5}}, {"attributes": {"passing": 11}}, {"attributes": {"passing": 0}},
    ]  # fmt: skip
    from tests.helpers import req_body

    for override in bad:
        r = await client.post(f"{REC}/requirements", json=req_body(**override), headers=s.rm_h)
        assert r.status_code == 422, override


async def test_requirement_permissions_and_isolation(client):
    s = await scouting_setup(client)
    r = await make_requirement(client, s)
    from tests.helpers import req_body

    for h in (s.scout_h, s.coach_h):  # scouts and coaches cannot create
        assert (
            await client.post(f"{REC}/requirements", json=req_body(), headers=h)
        ).status_code == 403
    assert (
        await client.get(f"{REC}/requirements", headers=s.scout_h)
    ).status_code == 403  # scouts: no recruitment access
    assert (
        await client.patch(
            f"{REC}/requirements/{r['id']}", json={"priority": "low"}, headers=s.coach_h
        )
    ).status_code == 403
    assert (await client.get(f"{REC}/requirements")).status_code == 401

    other_t, other_org = await setup_org(client, "o2@x.com", "Other Org")
    ho = hdr(other_t, other_org)
    assert (await client.get(f"{REC}/requirements", headers=ho)).json()["total"] == 0
    assert (await client.get(f"{REC}/requirements/{r['id']}", headers=ho)).status_code == 404
    assert (
        await client.patch(f"{REC}/requirements/{r['id']}", json={"priority": "low"}, headers=ho)
    ).status_code == 404
    assert (
        await client.get(f"{REC}/requirements/{r['id']}/matches", headers=ho)
    ).status_code == 404
    assert (await client.get(f"{REC}/requirements", headers=hdr(other_t, s.org))).status_code == 403


async def test_requirement_status_flow_and_editing_rules(client):
    s = await scouting_setup(client)
    r = await make_requirement(client, s)
    url = f"{REC}/requirements/{r['id']}"
    assert (
        await client.patch(url, json={"status": "fulfilled"}, headers=s.rm_h)
    ).status_code == 409  # draft -> fulfilled
    assert (await client.patch(url, json={"status": "open"}, headers=s.rm_h)).json()[
        "status"
    ] == "open"
    out = await client.patch(
        url,
        json={"priority": "urgent", "attributes": {"speed": 8}, "title": "Pacy midfielder"},
        headers=s.rm_h,
    )
    assert (
        out.json()["attributes"] == {"speed": 8} and out.json()["priority"] == "urgent"
    )  # replaced, not merged
    assert (await client.patch(url, json={"status": "on_hold"}, headers=s.rm_h)).status_code == 200
    assert (await client.patch(url, json={"status": "open"}, headers=s.rm_h)).status_code == 200
    assert (
        await client.patch(url, json={"status": "fulfilled"}, headers=s.rm_h)
    ).status_code == 200
    r2 = await client.patch(url, json={"title": "Too late now"}, headers=s.rm_h)
    assert r2.status_code == 409 and r2.json()["error"]["code"] == "not_editable"
    for bad in ({"title": None}, {"min_age": 40, "max_age": 20}):
        fresh = await make_requirement(client, s, title="Another one")
        assert (
            await client.patch(f"{REC}/requirements/{fresh['id']}", json=bad, headers=s.rm_h)
        ).status_code == 422


# ---- discovery -----------------------------------------------------------------------------
async def build_pool(client, s):
    """Players with different strengths; returns {name: id}."""
    club = await make_club(client, s.owner_t, s.org, "Pool Club")
    own, ids = s.owner_t, {}

    async def mk(name, age=22, **kw):
        kw.setdefault("nationality", "Croatia")
        kw.setdefault("preferred_foot", "right")
        kw.setdefault("primary_position", "CM")
        p = await make_player(client, own, s.org, name, age, **kw)
        ids[name] = p["id"]
        return p

    for name in (
        "Match One",
        "Weak Passer",
        "Too Old",
        "Wrong Country",
        "No Appearances",
        "Secondary CM",
        "Draft Only",
    ):
        kw = {}
        if name == "Too Old":
            kw["age"] = 31
        if name == "Wrong Country":
            kw["nationality"] = "Spain"
        if name == "Secondary CM":
            kw.update(primary_position="CAM", secondary_positions=["CM"])
        await mk(name, **kw)
    await mk("Striker Guy", primary_position="ST")
    for name in (
        "Match One",
        "Weak Passer",
        "Too Old",
        "Wrong Country",
        "Secondary CM",
        "Draft Only",
        "Striker Guy",
    ):
        await add_spell(
            client, s, ids[name], club["id"], appearances=80
        )  # "No Appearances" gets none

    await approved_report(client, s, ids["Match One"], {"passing": 9, "speed": 6, "agility": 7})
    await approved_report(
        client, s, ids["Match One"], {"passing": 5, "speed": 6, "agility": 6}
    )  # average passing = 7
    await approved_report(client, s, ids["Weak Passer"], {"passing": 6, "speed": 6, "agility": 6})
    for name in ("Too Old", "Wrong Country", "No Appearances", "Secondary CM"):
        await approved_report(client, s, ids[name], {"passing": 8, "speed": 6, "agility": 6})
    # a submitted-but-not-approved report must not count
    r = await client.post(
        f"{API}/scouting-reports",
        json={
            "player_id": ids["Draft Only"],
            "observed_on": "2026-11-01",
            "recommendation": "recommend",
            "general_observations": "x",
            "ratings": {"passing": 10, "speed": 7, "agility": 7},
        },
        headers=s.scout_h,
    )
    await client.post(f"{API}/scouting-reports/{r.json()['id']}/submit", headers=s.scout_h)
    return ids


async def names(client, url, headers):
    r = await client.get(url, headers=headers)
    assert r.status_code == 200, r.text
    return sorted(m["player"]["full_name"] for m in r.json()["items"]), r.json()


async def test_requirement_matching_combines_every_criterion(client):
    s = await scouting_setup(client)
    await build_pool(client, s)
    req = await make_requirement(
        client, s, min_age=18, max_age=25, nationality="Croatia", preferred_foot="right",
        min_appearances=50, attributes={"passing": 7},
    )  # fmt: skip
    got, body = await names(client, f"{REC}/requirements/{req['id']}/matches", s.rm_h)
    # "Secondary CM" is a CAM who also plays CM, so he qualifies through his secondary position
    assert got == ["Match One", "Secondary CM"], got
    for hidden in (
        "Weak Passer",
        "Too Old",
        "Wrong Country",
        "No Appearances",
        "Draft Only",
        "Striker Guy",
        "Target Player",
    ):
        assert hidden not in got, hidden
    match_one = next(m for m in body["items"] if m["player"]["full_name"] == "Match One")
    breakdown = {c["name"]: c for c in match_one["criteria"]}
    assert breakdown["Passing rating"] == {
        "name": "Passing rating",
        "required": "≥ 7",
        "actual": "7.0",
        "met": True,
    }  # (9+5)/2
    assert (
        breakdown["Career appearances"]["actual"] == "80"
        and breakdown["Nationality"]["actual"] == "Croatia"
    )
    assert all(c["met"] for c in match_one["criteria"]) and match_one["report_count"] == 2


async def test_unapproved_reports_and_other_orgs_reports_do_not_count(client):
    s = await scouting_setup(client)
    ids = await build_pool(client, s)
    req = await make_requirement(client, s, attributes={"passing": 9})
    got, _ = await names(client, f"{REC}/requirements/{req['id']}/matches", s.rm_h)
    assert "Draft Only" not in got  # a submitted (unreviewed) 10 is ignored
    # another organization's own approved ratings never leak into ours
    other_t, other_org = await setup_org(client, "o2@x.com", "Other Org")
    ho = hdr(other_t, other_org)
    shared = await make_player(
        client, s.owner_t, s.org, "Shared Star", 22, visibility="network", primary_position="CM"
    )
    # our organization approves excellent ratings on this player...
    await approved_report(client, s, shared["id"], {"passing": 10, "speed": 10, "agility": 10})
    other_req = await client.post(
        f"{REC}/requirements",
        json={"title": "Their need", "position": "CM", "attributes": {"passing": 5}},
        headers=ho,
    )
    r = await client.get(f"{REC}/requirements/{other_req.json()['id']}/matches", headers=ho)
    assert (
        r.status_code == 200 and r.json()["total"] == 0
    )  # visible player, but no ratings of theirs
    assert ids and shared


async def test_discovery_respects_visibility_and_pipeline_exclusion(client):
    s = await scouting_setup(client)
    other_t, other_org = await setup_org(client, "o2@x.com", "Other Org")
    await make_player(client, other_t, other_org, "Hidden Gem", 22)  # private to another org
    await make_player(client, other_t, other_org, "Open Gem", 22, visibility="network")
    mine = await make_player(client, s.owner_t, s.org, "My Midfielder", 22)
    req = await make_requirement(client, s)  # no attribute criteria
    url = f"{REC}/requirements/{req['id']}/matches"
    got, _ = await names(client, url, s.rm_h)
    assert "Hidden Gem" not in got and {"Open Gem", "My Midfielder", "Target Player"} <= set(got)

    add = await client.post(
        f"{REC}/requirements/{req['id']}/candidates", json={"player_id": mine["id"]}, headers=s.rm_h
    )
    assert add.status_code == 201
    got, _ = await names(client, url, s.rm_h)
    assert "My Midfielder" not in got  # already in the pipeline
    got, body = await names(client, url + "?exclude_pipeline=false", s.rm_h)
    flagged = {m["player"]["full_name"]: m["in_pipeline"] for m in body["items"]}
    assert flagged["My Midfielder"] is True and flagged["Open Gem"] is False


async def test_matches_pagination_and_permissions(client):
    s = await scouting_setup(client)
    for i in range(5):
        await make_player(client, s.owner_t, s.org, f"Pager Player {i}", 22)
    req = await make_requirement(client, s)
    url = f"{REC}/requirements/{req['id']}/matches"
    seen = []
    for page in (1, 2, 3):
        r = (await client.get(f"{url}?page={page}&page_size=2", headers=s.rm_h)).json()
        seen += [m["player"]["id"] for m in r["items"]]
        assert r["total"] == 6  # five new players plus the seeded one
    assert len(set(seen)) == 6
    assert (
        await client.get(url, headers=s.coach_h)
    ).status_code == 200  # recruitment + players read
    assert (await client.get(url, headers=s.scout_h)).status_code == 403


async def test_adhoc_search_with_scout_rating_filters(client):
    s = await scouting_setup(client)
    ids = await build_pool(client, s)
    url = f"{REC}/search"
    got, _ = await names(
        client, f"{url}?position=CM&min_rating=passing:8&min_rating=agility:6", s.rm_h
    )
    assert got == ["No Appearances", "Secondary CM", "Too Old", "Wrong Country"]
    assert (await names(client, f"{url}?min_rating=passing:9", s.rm_h))[
        0
    ] == []  # Match One averages 7
    assert (await names(client, f"{url}?q=weak", s.rm_h))[0] == ["Weak Passer"]
    assert (await names(client, f"{url}?nationality=spain&position=CM", s.rm_h))[0] == [
        "Wrong Country"
    ]
    assert (await names(client, f"{url}?min_age=30", s.rm_h))[0] == ["Too Old"]
    assert (await names(client, f"{url}?min_appearances=50&position=ST", s.rm_h))[0] == [
        "Striker Guy"
    ]
    for bad in (
        "min_rating=passing",
        "min_rating=bogus:5",
        "min_rating=passing:11",
        "min_rating=passing:x",
        "min_age=40&max_age=20",
        "position=QB",
    ):
        assert (await client.get(f"{url}?{bad}", headers=s.rm_h)).status_code == 422, bad
    assert (await client.get(f"{url}?q=%00", headers=s.rm_h)).status_code == 422
    assert (await client.get(url, headers=s.scout_h)).status_code == 403
    assert ids


# ---- pipeline ------------------------------------------------------------------------------
async def pipeline(client, s):
    req = await make_requirement(client, s)
    p = await make_player(client, s.owner_t, s.org, "Pipeline Player", 21)
    r = await client.post(
        f"{REC}/requirements/{req['id']}/candidates",
        json={"player_id": p["id"], "notes": "Spotted live"},
        headers=s.rm_h,
    )
    assert r.status_code == 201, r.text
    return req, p, r.json()


async def test_add_candidate_rules(client):
    s = await scouting_setup(client)
    req, p, cand = await pipeline(client, s)
    assert (
        cand["stage"] == "discovered"
        and cand["player_name"] == "Pipeline Player"
        and cand["notes"] == "Spotted live"
    )
    r = await client.post(
        f"{REC}/requirements/{req['id']}/candidates", json={"player_id": p["id"]}, headers=s.rm_h
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_candidate"
    other_t, other_org = await setup_org(client, "o2@x.com", "Other Org")
    hidden = await make_player(client, other_t, other_org, "Hidden", 22)
    r = await client.post(
        f"{REC}/requirements/{req['id']}/candidates",
        json={"player_id": hidden["id"]},
        headers=s.rm_h,
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_player"
    assert (
        await client.post(
            f"{REC}/requirements/{req['id']}/candidates",
            json={"player_id": p["id"]},
            headers=s.coach_h,
        )
    ).status_code == 403
    detail = (await client.get(f"{REC}/candidates/{cand['id']}", headers=s.rm_h)).json()
    assert [(h["from_stage"], h["to_stage"]) for h in detail["history"]] == [(None, "discovered")]


async def test_bulk_add_reports_added_and_skipped(client):
    s = await scouting_setup(client)
    req = await make_requirement(client, s)
    ps = [await make_player(client, s.owner_t, s.org, f"Bulk Player {i}", 22) for i in range(3)]
    ids = [p["id"] for p in ps]
    first = await client.post(
        f"{REC}/requirements/{req['id']}/candidates/bulk",
        json={"player_ids": ids[:2]},
        headers=s.rm_h,
    )
    assert first.status_code == 201 and (first.json()["added"], first.json()["skipped"]) == (2, 0)
    second = await client.post(
        f"{REC}/requirements/{req['id']}/candidates/bulk",
        json={"player_ids": ids + ids[:1]},
        headers=s.rm_h,
    )
    assert (second.json()["added"], second.json()["skipped"]) == (
        1,
        2,
    )  # a repeated id in the request counts once
    assert (await client.get(f"{REC}/requirements/{req['id']}", headers=s.rm_h)).json()[
        "pipeline_counts"
    ] == {"discovered": 3}
    for bad in ([], ids * 10):
        assert (
            await client.post(
                f"{REC}/requirements/{req['id']}/candidates/bulk",
                json={"player_ids": bad},
                headers=s.rm_h,
            )
        ).status_code == 422


async def test_stage_moves_history_and_notifications(client):
    s = await scouting_setup(client)
    req, p, cand = await pipeline(client, s)
    url = f"{REC}/candidates/{cand['id']}/stage"

    def move(to, note=None, h=None):
        return client.post(
            url, json={"to": to, **({"note": note} if note else {})}, headers=h or s.owner_h
        )

    assert (await move("discovered")).json()["error"]["code"] == "same_stage"
    for illegal in ("signed",):
        r = await move(illegal)
        assert r.status_code == 409 and r.json()["error"]["code"] == "invalid_transition"
    assert (await move("bogus")).status_code == 422
    assert (await move("under_evaluation", "Looks promising")).status_code == 200
    assert (await move("negotiation")).status_code == 200  # may skip ahead
    assert (await move("shortlisted", "Step back")).status_code == 200  # and back
    assert (await move("negotiation")).status_code == 200
    out = await move("signed", "Deal done")
    assert (
        out.status_code == 200
        and out.json()["stage"] == "signed"
        and out.json()["allowed_stages"] == []
    )
    r = await move("archived")
    assert r.status_code == 409  # signed is final
    history = [(h["from_stage"], h["to_stage"]) for h in out.json()["history"]]
    assert history == [
        (None, "discovered"), ("discovered", "under_evaluation"), ("under_evaluation", "negotiation"),
        ("negotiation", "shortlisted"), ("shortlisted", "negotiation"), ("negotiation", "signed"),
    ]  # fmt: skip
    assert (
        out.json()["history"][1]["note"] == "Looks promising"
        and out.json()["history"][1]["actor_name"] == "own"
    )
    # the requirement's creator (rm) was told about each move made by someone else (the owner)
    types = [n["type"] for n in await notes(client, s.rm_t)]
    assert types.count("recruitment_status_updated") == 5
    # ...but moves made by the creator themself are silent
    c2 = (
        await client.post(
            f"{REC}/requirements/{req['id']}/candidates",
            json={
                "player_id": (await make_player(client, s.owner_t, s.org, "Second One", 22))["id"]
            },
            headers=s.rm_h,
        )
    ).json()
    before = await unread(client, s.rm_t)
    await client.post(
        f"{REC}/candidates/{c2['id']}/stage", json={"to": "under_evaluation"}, headers=s.rm_h
    )
    assert await unread(client, s.rm_t) == before


async def test_rejected_and_archived_can_only_reopen(client):
    s = await scouting_setup(client)
    req, p, cand = await pipeline(client, s)
    url = f"{REC}/candidates/{cand['id']}/stage"
    assert (
        await client.post(url, json={"to": "rejected", "note": "Not for us"}, headers=s.rm_h)
    ).status_code == 200
    r = await client.post(url, json={"to": "shortlisted"}, headers=s.rm_h)
    assert r.status_code == 409
    assert (
        await client.post(url, json={"to": "discovered", "note": "Reconsidering"}, headers=s.rm_h)
    ).status_code == 200
    assert (await client.post(url, json={"to": "archived"}, headers=s.rm_h)).status_code == 200


async def test_list_candidates_filters_and_permissions(client):
    s = await scouting_setup(client)
    req = await make_requirement(client, s)
    cands = []
    for i in range(3):
        p = await make_player(client, s.owner_t, s.org, f"Listed {i}", 22)
        cands.append(
            (
                await client.post(
                    f"{REC}/requirements/{req['id']}/candidates",
                    json={"player_id": p["id"]},
                    headers=s.rm_h,
                )
            ).json()
        )
    await client.post(
        f"{REC}/candidates/{cands[0]['id']}/stage", json={"to": "shortlisted"}, headers=s.rm_h
    )
    base = f"{REC}/requirements/{req['id']}/candidates"
    assert (await client.get(base, headers=s.coach_h)).json()["total"] == 3
    assert [
        c["player_name"]
        for c in (await client.get(base + "?stage=shortlisted", headers=s.rm_h)).json()["items"]
    ] == ["Listed 0"]
    assert (await client.get(base + "?stage=bogus", headers=s.rm_h)).status_code == 422
    assert len((await client.get(base + "?page_size=2", headers=s.rm_h)).json()["items"]) == 2
    assert (await client.get(base, headers=s.scout_h)).status_code == 403
    assert (
        await client.post(
            f"{REC}/candidates/{cands[1]['id']}/stage",
            json={"to": "shortlisted"},
            headers=s.coach_h,
        )
    ).status_code == 403


async def test_closed_requirements_freeze_the_pipeline(client):
    s = await scouting_setup(client)
    req, p, cand = await pipeline(client, s)
    await client.patch(
        f"{REC}/requirements/{req['id']}", json={"status": "cancelled"}, headers=s.rm_h
    )
    other = await make_player(client, s.owner_t, s.org, "Latecomer", 22)
    r = await client.post(
        f"{REC}/requirements/{req['id']}/candidates",
        json={"player_id": other["id"]},
        headers=s.rm_h,
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "requirement_closed"
    assert (
        await client.post(
            f"{REC}/candidates/{cand['id']}/stage", json={"to": "shortlisted"}, headers=s.rm_h
        )
    ).status_code == 409
    assert (
        await client.post(
            f"{REC}/candidates/{cand['id']}/stage", json={"to": "archived"}, headers=s.rm_h
        )
    ).status_code == 200  # tidying up is allowed


async def test_candidate_isolation(client):
    s = await scouting_setup(client)
    req, p, cand = await pipeline(client, s)
    other_t, other_org = await setup_org(client, "o2@x.com", "Other Org")
    ho = hdr(other_t, other_org)
    assert (await client.get(f"{REC}/candidates/{cand['id']}", headers=ho)).status_code == 404
    assert (
        await client.post(
            f"{REC}/candidates/{cand['id']}/stage", json={"to": "shortlisted"}, headers=ho
        )
    ).status_code == 404
    assert (
        await client.get(f"{REC}/requirements/{req['id']}/candidates", headers=ho)
    ).status_code == 404
    assert (
        await client.post(
            f"{REC}/requirements/{req['id']}/candidates", json={"player_id": p["id"]}, headers=ho
        )
    ).status_code == 404


# ---- assign a scout from the pipeline -------------------------------------------------------
async def test_assign_scout_creates_assignment_and_advances_stage(client):
    s = await scouting_setup(client)
    req, p, cand = await pipeline(client, s)
    r = await client.post(
        f"{REC}/candidates/{cand['id']}/assign-scout",
        json={
            "scout_id": s.scout_id,
            "deadline": in_days(5),
            "instructions": "Watch the next game",
        },
        headers=s.rm_h,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert (
        d["stage"] == "scout_assigned"
        and d["assignment_id"]
        and d["assignment_status"] == "assigned"
    )
    assert [h["to_stage"] for h in d["history"]] == [
        "discovered",
        "scout_assigned",
    ] and "Scout assigned" in d["history"][-1]["note"]
    asg = (await client.get(f"{API}/assignments/{d['assignment_id']}", headers=s.scout_h)).json()
    assert (
        asg["target_type"] == "player"
        and asg["target_label"] == "Pipeline Player"
        and asg["instructions"] == "Watch the next game"
    )
    assert "Pipeline Player" in asg["title"]
    assert (await notes(client, s.scout_t))[0]["type"] == "assignment_assigned"


async def test_assign_scout_rules(client):
    s = await scouting_setup(client)
    req, p, cand = await pipeline(client, s)
    url = f"{REC}/candidates/{cand['id']}/assign-scout"
    assert (
        await client.post(url, json={"scout_id": s.scout_id}, headers=s.coach_h)
    ).status_code == 403
    bad = await client.post(
        url, json={"scout_id": "00000000-0000-0000-0000-000000000000"}, headers=s.rm_h
    )
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_scout"
    assert (
        await client.post(
            url, json={"scout_id": s.scout_id, "deadline": in_days(-1)}, headers=s.rm_h
        )
    ).status_code == 422
    # a candidate that is already further along keeps its stage but still gets the assignment
    await client.post(
        f"{REC}/candidates/{cand['id']}/stage", json={"to": "negotiation"}, headers=s.rm_h
    )
    ok = await client.post(url, json={"scout_id": s.scout_id}, headers=s.rm_h)
    assert (
        ok.status_code == 200 and ok.json()["stage"] == "negotiation" and ok.json()["assignment_id"]
    )
    await client.post(
        f"{REC}/candidates/{cand['id']}/stage", json={"to": "rejected"}, headers=s.rm_h
    )
    assert (
        await client.post(url, json={"scout_id": s.scout_id}, headers=s.rm_h)
    ).status_code == 409
    assert add_role_member and add_spell  # (shared imports)


# ---- reports move candidates along the pipeline ---------------------------------------------
async def _stage(client, s, cand_id) -> dict:
    return (await client.get(f"{REC}/candidates/{cand_id}", headers=s.rm_h)).json()


async def _assigned_candidate(client, s):
    req, p, cand = await pipeline(client, s)
    d = (
        await client.post(
            f"{REC}/candidates/{cand['id']}/assign-scout",
            json={"scout_id": s.scout_id, "deadline": in_days(5)},
            headers=s.rm_h,
        )
    ).json()
    return req, p, cand, d["assignment_id"]


async def _submitted_report(client, s, player_id, assignment_id=None):
    if assignment_id:  # the scout must accept an assignment before reporting on it
        acc = await move_assignment(client, s.scout_h, {"id": assignment_id}, "accepted")
        assert acc.status_code == 200, acc.text
    body = {
        "player_id": player_id, "observed_on": "2026-01-10", "recommendation": "recommend",
        "general_observations": "Calm on the ball.", "ratings": full_ratings(),
        **({"assignment_id": assignment_id} if assignment_id else {}),
    }  # fmt: skip
    r = await client.post(f"{API}/scouting-reports", json=body, headers=s.scout_h)
    assert r.status_code == 201, r.text
    sub = await client.post(f"{API}/scouting-reports/{r.json()['id']}/submit", headers=s.scout_h)
    assert sub.status_code == 200, sub.text
    return r.json()["id"]


async def test_submitting_and_approving_a_report_moves_the_candidate(client):
    s = await scouting_setup(client)
    req, p, cand, asg = await _assigned_candidate(client, s)
    assert (await _stage(client, s, cand["id"]))["stage"] == "scout_assigned"

    rid = await _submitted_report(client, s, p["id"], asg)
    d = await _stage(client, s, cand["id"])
    assert d["stage"] == "report_submitted"
    assert "report was submitted" in d["history"][-1]["note"]

    ok = await client.post(
        f"{API}/scouting-reports/{rid}/review", json={"decision": "approved"}, headers=s.rm_h
    )
    assert ok.status_code == 200, ok.text
    d = await _stage(client, s, cand["id"])
    assert d["stage"] == "under_review" and "approved" in d["history"][-1]["note"]
    assert [h["to_stage"] for h in d["history"]][-3:] == [
        "scout_assigned", "report_submitted", "under_review",
    ]  # fmt: skip


async def test_revision_request_sends_the_candidate_back_to_the_scout(client):
    s = await scouting_setup(client)
    req, p, cand, asg = await _assigned_candidate(client, s)
    rid = await _submitted_report(client, s, p["id"], asg)
    bad = await client.post(
        f"{API}/scouting-reports/{rid}/review",
        json={"decision": "revision_requested", "comment": "Add more on defending"},
        headers=s.rm_h,
    )
    assert bad.status_code == 200, bad.text
    assert (await _stage(client, s, cand["id"]))["stage"] == "scout_assigned"


async def test_rejected_report_leaves_the_candidate_where_it_is(client):
    s = await scouting_setup(client)
    req, p, cand, asg = await _assigned_candidate(client, s)
    rid = await _submitted_report(client, s, p["id"], asg)
    await client.post(
        f"{API}/scouting-reports/{rid}/review",
        json={"decision": "rejected", "comment": "Not enough evidence"},
        headers=s.rm_h,
    )
    assert (await _stage(client, s, cand["id"]))["stage"] == "report_submitted"


async def test_reports_never_pull_a_further_along_candidate_back(client):
    s = await scouting_setup(client)
    req, p, cand, asg = await _assigned_candidate(client, s)
    moved = await client.post(
        f"{REC}/candidates/{cand['id']}/stage", json={"to": "negotiation"}, headers=s.rm_h
    )
    assert moved.status_code == 200, moved.text
    rid = await _submitted_report(client, s, p["id"], asg)
    await client.post(
        f"{API}/scouting-reports/{rid}/review", json={"decision": "approved"}, headers=s.rm_h
    )
    assert (await _stage(client, s, cand["id"]))["stage"] == "negotiation"


async def test_report_for_another_assignment_does_not_move_the_candidate(client):
    s = await scouting_setup(client)
    req, p, cand, asg = await _assigned_candidate(client, s)
    s.player = p  # make_assignment targets s.player
    other = await make_assignment(client, s, "player")  # a different job about the same player
    await _submitted_report(client, s, p["id"], other["id"])
    assert (await _stage(client, s, cand["id"]))["stage"] == "scout_assigned"


async def test_closed_requirement_candidates_are_left_alone(client):
    s = await scouting_setup(client)
    req, p, cand = await pipeline(client, s)
    assert (
        await client.post(
            f"{REC}/candidates/{cand['id']}/stage", json={"to": "rejected"}, headers=s.rm_h
        )
    ).status_code == 200
    await _submitted_report(client, s, p["id"])
    assert (await _stage(client, s, cand["id"]))["stage"] == "rejected"
