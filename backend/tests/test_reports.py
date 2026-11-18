from datetime import UTC, datetime, timedelta

from tests.conftest import hdr
from tests.helpers import (
    API,
    add_role_member,
    full_ratings,
    make_assignment,
    make_player,
    make_report,
    move,
    notes,
    report_body,
    scouting_setup,
    setup_org,
    unread,
)

R = f"{API}/scouting-reports"


async def review(client, headers, report, decision, comment=None):
    body = {"decision": decision, **({"comment": comment} if comment else {})}
    return await client.post(f"{R}/{report['id']}/review", json=body, headers=headers)


async def test_create_draft_and_read(client):
    s = await scouting_setup(client)
    r = await make_report(
        client, s, position_observed="CM", match_id=s.match["id"], club_id=s.c1["id"]
    )
    assert r["status"] == "draft" and r["current_version"] == 0 and r["ratings"] == full_ratings()
    assert r["player_name"] == "Target Player" and r["scout_name"] == "scout"
    assert r["match_label"] == "North United v South Rovers" and r["club_name"] == "North United"
    assert r["is_mine"] and r["can_edit"] and not r["can_review"] and r["versions"] == []


async def test_creation_validation(client):
    s = await scouting_setup(client)
    post = lambda **kw: client.post(R, json=report_body(s, **kw), headers=s.scout_h)  # noqa: E731
    tomorrow = (datetime.now(UTC) + timedelta(days=2)).date().isoformat()
    for bad in (
        {"observed_on": tomorrow}, {"ratings": {"passing": 0}}, {"ratings": {"passing": 11}},
        {"ratings": {"teleporting": 5}}, {"position_observed": "QB"}, {"recommendation": "maybe"},
        {"strengths": "x" * 5001}, {"observed_on": "not-a-date"},
    ):  # fmt: skip
        assert (await post(**bad)).status_code == 422, bad
    r = await post(player_id="00000000-0000-0000-0000-000000000000")
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_player"
    r = await post(match_id="00000000-0000-0000-0000-000000000000")
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_match"
    r = await post(match_id=s.match["id"], club_id=s.c1["id"])
    assert r.status_code == 201
    r = await post(club_id="00000000-0000-0000-0000-000000000000")
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_club"


async def test_only_scouts_with_a_profile_can_write(client):
    s = await scouting_setup(client)
    assert (
        await client.post(R, json=report_body(s), headers=s.rm_h)
    ).status_code == 403  # no reports:write
    assert (await client.post(R, json=report_body(s), headers=s.coach_h)).status_code == 403
    # the owner may write, but needs a scout profile first
    r = await client.post(R, json=report_body(s), headers=s.owner_h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "scout_profile_required"
    assert (await client.post(R, json=report_body(s))).status_code == 401


async def test_edit_ratings_merge_and_remove(client):
    s = await scouting_setup(client)
    r = await make_report(client, s)
    url = f"{R}/{r['id']}"
    out = await client.patch(
        url,
        json={"ratings": {"passing": 10, "crossing": 5, "speed": None}, "strengths": "Updated"},
        headers=s.scout_h,
    )
    assert out.status_code == 200
    assert out.json()["ratings"] == {
        "passing": 10,
        "ball_control": 7,
        "dribbling": 6,
        "positioning": 8,
        "crossing": 5,
    }
    assert (
        out.json()["strengths"] == "Updated"
        and out.json()["general_observations"] == "Calm on the ball."
    )
    for bad in ({"ratings": {"passing": 11}}, {"ratings": {"bogus": 3}}, {"observed_on": None}):
        assert (await client.patch(url, json=bad, headers=s.scout_h)).status_code == 422


async def test_submit_requires_a_complete_report_and_snapshots_version_one(client):
    s = await scouting_setup(client)
    thin = await make_report(
        client, s, ratings={"passing": 7}, recommendation=None, general_observations=None
    )
    r = await client.post(f"{R}/{thin['id']}/submit", headers=s.scout_h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "incomplete_report"
    assert len(r.json()["error"]["details"]) == 3

    full = await make_report(client, s)
    r = await client.post(f"{R}/{full['id']}/submit", headers=s.scout_h)
    assert (
        r.status_code == 200
        and r.json()["status"] == "submitted"
        and r.json()["current_version"] == 1
    )
    assert r.json()["can_edit"] is False and [v["version"] for v in r.json()["versions"]] == [1]
    snap = (await client.get(f"{R}/{full['id']}/versions/1", headers=s.scout_h)).json()
    assert snap["ratings"] == full_ratings() and snap["recommendation"] == "recommend"
    assert (await client.get(f"{R}/{full['id']}/versions/9", headers=s.scout_h)).status_code == 404
    # submitted reports are frozen
    assert (
        await client.patch(f"{R}/{full['id']}", json={"strengths": "x"}, headers=s.scout_h)
    ).status_code == 409
    assert (await client.post(f"{R}/{full['id']}/submit", headers=s.scout_h)).status_code == 409
    assert (await client.delete(f"{R}/{full['id']}", headers=s.scout_h)).status_code == 409


async def test_delete_only_unsubmitted_drafts(client):
    s = await scouting_setup(client)
    r = await make_report(client, s)
    assert (await client.delete(f"{R}/{r['id']}", headers=s.scout_h)).status_code == 204
    assert (await client.get(f"{R}/{r['id']}", headers=s.scout_h)).status_code == 404


async def test_review_decisions_and_notifications(client):
    s = await scouting_setup(client)
    r = await make_report(client, s)
    await client.post(f"{R}/{r['id']}/submit", headers=s.scout_h)
    # reviewers were notified; the author was not
    assert (await notes(client, s.rm_t))[0]["type"] == "report_submitted"
    assert (await notes(client, s.owner_t))[0]["type"] == "report_submitted"
    assert await unread(client, s.scout_t) == 0

    assert (
        await review(client, s.scout_h, r, "approved")
    ).status_code == 403  # scouts cannot review
    assert (await review(client, s.coach_h, r, "approved")).status_code == 403
    out = await review(client, s.rm_h, r, "revision_requested")
    assert out.status_code == 422 and out.json()["error"]["code"] == "comment_required"
    assert (await review(client, s.rm_h, r, "rejected")).status_code == 422
    assert (await review(client, s.rm_h, r, "maybe", "x")).status_code == 422

    out = await review(client, s.rm_h, r, "revision_requested", "Add more detail on pressing")
    assert out.status_code == 200 and out.json()["status"] == "revision_requested"
    assert (
        out.json()["reviews"][0]["comment"] == "Add more detail on pressing"
        and out.json()["reviews"][0]["reviewer_name"] == "rm"
    )
    n = (await notes(client, s.scout_t))[0]
    assert n["type"] == "report_revision_requested" and n["link_path"] == f"/reports/{r['id']}"
    assert (
        await review(client, s.rm_h, r, "approved")
    ).status_code == 409  # not submitted any more


async def test_revision_cycle_creates_version_two(client):
    s = await scouting_setup(client)
    r = await make_report(client, s)
    await client.post(f"{R}/{r['id']}/submit", headers=s.scout_h)
    await review(client, s.rm_h, r, "revision_requested", "Rating for passing looks high")
    edit = await client.patch(
        f"{R}/{r['id']}",
        json={"ratings": {"passing": 6}, "general_observations": "Revised view."},
        headers=s.scout_h,
    )
    assert edit.status_code == 200 and edit.json()["can_edit"] is True
    out = await client.post(f"{R}/{r['id']}/submit", headers=s.scout_h)
    assert out.json()["current_version"] == 2 and out.json()["status"] == "submitted"
    v1 = (await client.get(f"{R}/{r['id']}/versions/1", headers=s.scout_h)).json()
    v2 = (await client.get(f"{R}/{r['id']}/versions/2", headers=s.scout_h)).json()
    assert v1["ratings"]["passing"] == 8 and v2["ratings"]["passing"] == 6  # history preserved
    assert (
        v1["general_observations"] == "Calm on the ball."
        and v2["general_observations"] == "Revised view."
    )
    approved = await review(client, s.rm_h, r, "approved")
    assert approved.json()["status"] == "approved"
    assert [rv["version"] for rv in approved.json()["reviews"]] == [1, 2]
    assert (
        await client.patch(f"{R}/{r['id']}", json={"strengths": "x"}, headers=s.scout_h)
    ).status_code == 409


async def test_rejected_reports_are_final(client):
    s = await scouting_setup(client)
    r = await make_report(client, s)
    await client.post(f"{R}/{r['id']}/submit", headers=s.scout_h)
    assert (await review(client, s.rm_h, r, "rejected", "Not enough evidence")).json()[
        "status"
    ] == "rejected"
    assert (await notes(client, s.scout_t))[0]["type"] == "report_rejected"
    assert (
        await client.patch(f"{R}/{r['id']}", json={"strengths": "x"}, headers=s.scout_h)
    ).status_code == 409


async def test_cannot_review_own_report(client):
    s = await scouting_setup(client)
    await client.post(f"{API}/scouts", json={}, headers=s.owner_h)  # the owner becomes a scout too
    r = await make_report(client, s, headers=s.owner_h)
    await client.post(f"{R}/{r['id']}/submit", headers=s.owner_h)
    out = await review(client, s.owner_h, r, "approved")
    assert out.status_code == 403 and out.json()["error"]["code"] == "cannot_review_own"
    assert (await review(client, s.rm_h, r, "approved")).status_code == 200  # someone else can


async def test_visibility_matrix(client):
    s = await scouting_setup(client)
    scout2_t = await add_role_member(client, s.org, "scout2@x.com", "scout")
    await client.post(f"{API}/scouts", json={}, headers=hdr(scout2_t, s.org))
    h2 = hdr(scout2_t, s.org)
    draft = await make_report(client, s)
    sub = await make_report(client, s)
    await client.post(f"{R}/{sub['id']}/submit", headers=s.scout_h)
    appr = await make_report(client, s)
    await client.post(f"{R}/{appr['id']}/submit", headers=s.scout_h)
    await review(client, s.rm_h, appr, "approved")

    async def ids(h):
        return {x["id"] for x in (await client.get(R, headers=h)).json()["items"]}

    everything = {draft["id"], sub["id"], appr["id"]}
    assert await ids(s.scout_h) == everything  # authors see their own
    assert (
        await ids(s.rm_h) == everything and await ids(s.owner_h) == everything
    )  # reviewers see all
    assert await ids(h2) == {appr["id"]}  # colleagues and coaches only see approved reports
    assert await ids(s.coach_h) == {appr["id"]}
    for h in (h2, s.coach_h):
        assert (await client.get(f"{R}/{draft['id']}", headers=h)).status_code == 404
        assert (await client.get(f"{R}/{sub['id']}/versions/1", headers=h)).status_code == 404
        assert (await client.get(f"{R}/{appr['id']}", headers=h)).status_code == 200
        assert (
            await client.patch(f"{R}/{draft['id']}", json={"strengths": "x"}, headers=h)
        ).status_code in (403, 404)
    assert (await client.get(f"{R}?mine=true", headers=s.scout_h)).json()["total"] == 3
    assert (await client.get(f"{R}?mine=true", headers=h2)).json()["total"] == 0


async def test_filters_and_pagination(client):
    s = await scouting_setup(client)
    other = await make_player(client, s.owner_t, s.org, "Second Player", 23)
    a = await make_report(client, s)
    b = await make_report(client, s, player_id=other["id"], recommendation="monitor")
    await client.post(f"{R}/{a['id']}/submit", headers=s.scout_h)

    def q(params):
        return client.get(f"{R}?{params}", headers=s.rm_h)

    assert (await q(f"player_id={other['id']}")).json()["total"] == 1
    assert (await q("status=submitted")).json()["items"][0]["id"] == a["id"]
    assert (await q("recommendation=monitor")).json()["items"][0]["id"] == b["id"]
    assert (await q(f"scout_id={s.scout_id}")).json()["total"] == 2
    assert (await q("status=bogus")).status_code == 422
    assert (await q("page=1&page_size=1")).json()["total"] == 2


async def test_isolation_between_organizations(client):
    s = await scouting_setup(client)
    r = await make_report(client, s)
    await client.post(f"{R}/{r['id']}/submit", headers=s.scout_h)
    other_t, other_org = await setup_org(client, "o2@x.com", "Other Org")
    ho = hdr(other_t, other_org)
    assert (await client.get(R, headers=ho)).json()["total"] == 0
    assert (await client.get(f"{R}/{r['id']}", headers=ho)).status_code == 404
    assert (await review(client, ho, r, "approved")).status_code == 404
    assert (await client.get(R, headers=hdr(other_t, s.org))).status_code == 403


# ---- assignment linkage --------------------------------------------------------------
async def test_report_must_match_its_assignment(client):
    s = await scouting_setup(client)
    other_player = await make_player(client, s.owner_t, s.org, "Other Player", 21)
    pa = await make_assignment(client, s, "player")
    r = await client.post(R, json=report_body(s, assignment_id=pa["id"]), headers=s.scout_h)
    assert (
        r.status_code == 409 and r.json()["error"]["code"] == "assignment_not_open"
    )  # not accepted yet
    await move(client, s.scout_h, pa, "accepted")
    r = await client.post(
        R,
        json=report_body(s, assignment_id=pa["id"], player_id=other_player["id"]),
        headers=s.scout_h,
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "assignment_mismatch"
    ok = await client.post(R, json=report_body(s, assignment_id=pa["id"]), headers=s.scout_h)
    assert ok.status_code == 201 and ok.json()["assignment_title"] == "Watch the player"
    # starting the report moved the assignment to in_progress, with history
    detail = (await client.get(f"{API}/assignments/{pa['id']}", headers=s.rm_h)).json()
    assert detail["status"] == "in_progress" and detail["history"][-1]["note"] == "Started a report"
    assert detail["reports"][0]["player_name"] == "Target Player" and detail["report_count"] == 1

    ma = await make_assignment(client, s, "match")
    await move(client, s.scout_h, ma, "accepted")
    r = await client.post(R, json=report_body(s, assignment_id=ma["id"]), headers=s.scout_h)
    assert (
        r.status_code == 201 and r.json()["match_id"] == s.match["id"]
    )  # filled from the assignment

    # someone else's assignment cannot be used
    scout2_t = await add_role_member(client, s.org, "scout2@x.com", "scout")
    await client.post(f"{API}/scouts", json={}, headers=hdr(scout2_t, s.org))
    r = await client.post(
        R, json=report_body(s, assignment_id=ma["id"]), headers=hdr(scout2_t, s.org)
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_assignment"
