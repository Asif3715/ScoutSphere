"""The whole scouting loop: assign, accept, report, submit, review, approve."""

from tests.conftest import hdr
from tests.helpers import (
    API,
    add_role_member,
    make_assignment,
    make_report,
    move,
    notes,
    scouting_setup,
    unread,
)

R = f"{API}/scouting-reports"


async def history(client, s, a):
    d = (await client.get(f"{API}/assignments/{a['id']}", headers=s.rm_h)).json()
    return [(h["from_status"], h["to_status"]) for h in d["history"]]


async def test_full_happy_path(client):
    s = await scouting_setup(client)
    a = await make_assignment(client, s, instructions="Watch pressing", criteria="Work rate")
    assert await unread(client, s.scout_t) == 1

    assert (await move(client, s.scout_h, a, "accepted")).status_code == 200
    assert (await notes(client, s.rm_t))[0]["type"] == "assignment_accepted"

    report = await make_report(client, s, assignment_id=a["id"])
    assert (await client.get(f"{API}/assignments/{a['id']}", headers=s.rm_h)).json()[
        "status"
    ] == "in_progress"

    # the scout cannot hand in an assignment that still has a draft report
    r = await move(client, s.scout_h, a, "submitted")
    assert r.status_code == 409 and r.json()["error"]["code"] == "reports_incomplete"
    await client.post(f"{R}/{report['id']}/submit", headers=s.scout_h)
    assert (await move(client, s.scout_h, a, "submitted")).status_code == 200
    assert (await notes(client, s.rm_t))[0]["type"] == "assignment_submitted"

    assert (await move(client, s.rm_h, a, "under_review")).status_code == 200
    # cannot approve the assignment while its report is unreviewed
    r = await move(client, s.rm_h, a, "approved")
    assert r.status_code == 409 and r.json()["error"]["code"] == "reports_not_reviewed"
    await client.post(f"{R}/{report['id']}/review", json={"decision": "approved"}, headers=s.rm_h)
    assert (await move(client, s.rm_h, a, "approved", "Great work")).status_code == 200

    assert await history(client, s, a) == [
        (None, "draft"), ("draft", "assigned"), ("assigned", "accepted"),
        ("accepted", "in_progress"), ("in_progress", "submitted"),
        ("submitted", "under_review"), ("under_review", "approved"),
    ]  # fmt: skip
    kinds = [n["type"] for n in await notes(client, s.scout_t)]
    assert (
        "assignment_approved" in kinds
        and "report_approved" in kinds
        and "assignment_assigned" in kinds
    )
    # approved is final
    for to in ("in_progress", "rejected", "cancelled"):
        assert (await move(client, s.rm_h, a, to, "x")).status_code in (403, 409)


async def test_revision_request_reopens_a_submitted_assignment(client):
    s = await scouting_setup(client)
    a = await make_assignment(client, s)
    await move(client, s.scout_h, a, "accepted")
    report = await make_report(client, s, assignment_id=a["id"])
    await client.post(f"{R}/{report['id']}/submit", headers=s.scout_h)
    await move(client, s.scout_h, a, "submitted")

    out = await client.post(
        f"{R}/{report['id']}/review",
        json={"decision": "revision_requested", "comment": "Needs more evidence"},
        headers=s.rm_h,
    )
    assert out.status_code == 200
    d = (await client.get(f"{API}/assignments/{a['id']}", headers=s.rm_h)).json()
    assert d["status"] == "in_progress" and "Needs more evidence" in d["history"][-1]["note"]
    kinds = [n["type"] for n in await notes(client, s.scout_t)]
    assert "assignment_returned" in kinds and "report_revision_requested" in kinds

    await client.patch(f"{R}/{report['id']}", json={"strengths": "Added detail"}, headers=s.scout_h)
    await client.post(f"{R}/{report['id']}/submit", headers=s.scout_h)
    assert (await move(client, s.scout_h, a, "submitted")).status_code == 200
    await client.post(f"{R}/{report['id']}/review", json={"decision": "approved"}, headers=s.rm_h)
    assert (await move(client, s.rm_h, a, "under_review")).status_code == 200
    assert (await move(client, s.rm_h, a, "approved")).status_code == 200


async def test_manager_can_return_or_reject_with_a_reason(client):
    s = await scouting_setup(client)
    a = await make_assignment(client, s)
    await move(client, s.scout_h, a, "accepted")
    report = await make_report(client, s, assignment_id=a["id"])
    await client.post(f"{R}/{report['id']}/submit", headers=s.scout_h)
    await move(client, s.scout_h, a, "submitted")
    await move(client, s.rm_h, a, "under_review")

    for to in ("rejected", "in_progress"):  # a reason is mandatory
        r = await move(client, s.rm_h, a, to)
        assert r.status_code == 422 and r.json()["error"]["code"] == "note_required"
    assert (
        await move(client, s.rm_h, a, "rejected", "Report does not cover the brief")
    ).status_code == 200
    assert (await notes(client, s.scout_t))[0]["type"] == "assignment_rejected"
    assert (await move(client, s.rm_h, a, "approved")).status_code in (403, 409)


async def test_rejected_report_plus_approved_report_still_allows_approval(client):
    s = await scouting_setup(client)
    a = await make_assignment(client, s)
    await move(client, s.scout_h, a, "accepted")
    good = await make_report(client, s, assignment_id=a["id"])
    bad = await make_report(client, s, assignment_id=a["id"])
    for r in (good, bad):
        await client.post(f"{R}/{r['id']}/submit", headers=s.scout_h)
    await move(client, s.scout_h, a, "submitted")
    await move(client, s.rm_h, a, "under_review")
    await client.post(f"{R}/{good['id']}/review", json={"decision": "approved"}, headers=s.rm_h)
    r = await move(client, s.rm_h, a, "approved")
    assert r.status_code == 409  # one report is still unreviewed
    await client.post(
        f"{R}/{bad['id']}/review",
        json={"decision": "rejected", "comment": "Duplicate"},
        headers=s.rm_h,
    )
    assert (await move(client, s.rm_h, a, "approved")).status_code == 200


async def test_standalone_reports_work_without_an_assignment(client):
    s = await scouting_setup(client)
    report = await make_report(client, s)
    assert report["assignment_id"] is None
    await client.post(f"{R}/{report['id']}/submit", headers=s.scout_h)
    out = await client.post(
        f"{R}/{report['id']}/review", json={"decision": "approved"}, headers=s.owner_h
    )
    assert out.status_code == 200
    assert (
        await client.get(f"{R}/{report['id']}", headers=s.coach_h)
    ).status_code == 200  # approved: coaches may read


async def test_cancelled_assignment_blocks_new_reports(client):
    s = await scouting_setup(client)
    a = await make_assignment(client, s)
    await move(client, s.scout_h, a, "accepted")
    await move(client, s.rm_h, a, "cancelled", "Plans changed")
    from tests.helpers import report_body

    r = await client.post(R, json=report_body(s, assignment_id=a["id"]), headers=s.scout_h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "assignment_not_open"
    assert add_role_member and hdr  # (shared imports)
