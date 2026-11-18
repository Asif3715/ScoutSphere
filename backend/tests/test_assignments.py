from sqlalchemy import select, update

from app.db.session import SessionLocal
from app.models.assignment import Assignment
from app.services.assignments import send_deadline_reminders
from tests.conftest import hdr, login, make_user
from tests.helpers import (
    API,
    add_role_member,
    in_days,
    make_assignment,
    make_player,
    move,
    notes,
    scouting_setup,
    setup_org,
    unread,
)


async def test_create_draft_then_assign_with_history_and_notification(client):
    s = await scouting_setup(client)
    a = await make_assignment(
        client, s, assign_now=False, instructions="Focus on pressing", criteria="Work rate"
    )
    assert a["status"] == "draft" and a["target_label"] == "North United v South Rovers"
    assert [h["to_status"] for h in a["history"]] == ["draft"]
    assert await unread(client, s.scout_t) == 0  # drafts are invisible and silent
    assert (await client.get(f"{API}/assignments/{a['id']}", headers=s.scout_h)).status_code == 404

    r = await move(client, s.rm_h, a, "assigned")
    assert r.status_code == 200 and r.json()["status"] == "assigned"
    assert [h["to_status"] for h in r.json()["history"]] == ["draft", "assigned"]
    assert r.json()["history"][1]["actor_name"] == "rm"
    n = await notes(client, s.scout_t)
    assert n[0]["type"] == "assignment_assigned" and n[0]["link_path"] == f"/assignments/{a['id']}"
    assert (await client.get(f"{API}/assignments/{a['id']}", headers=s.scout_h)).status_code == 200


async def test_assign_now_in_one_step_for_each_target_type(client):
    s = await scouting_setup(client)
    for target, label in (
        ("match", "North United v South Rovers"),
        ("player", "Target Player"),
        ("competition", "Alpha League"),
    ):
        a = await make_assignment(client, s, target)
        assert (
            a["status"] == "assigned" and a["target_type"] == target and a["target_label"] == label
        )
    assert await unread(client, s.scout_t) == 3


async def test_creation_validation(client):
    s = await scouting_setup(client)
    base = {
        "scout_id": s.scout_id,
        "target_type": "match",
        "target_id": s.match["id"],
        "title": "Valid title",
        "deadline": in_days(2),
    }
    post = lambda body, h=None: client.post(f"{API}/assignments", json=body, headers=h or s.rm_h)  # noqa: E731
    assert (await post({**base, "title": "ab"})).status_code == 422
    assert (await post({**base, "target_type": "team"})).status_code == 422
    r = await post({**base, "deadline": in_days(-1)})
    assert r.status_code == 422 and r.json()["error"]["code"] == "deadline_in_past"
    assert (
        await post({**base, "deadline": "2030-01-01T10:00:00"})
    ).status_code == 422  # naive datetime
    r = await post({**base, "target_id": "00000000-0000-0000-0000-000000000000"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_target"
    r = await post({**base, "scout_id": "00000000-0000-0000-0000-000000000000"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_scout"
    # a target type/id mismatch is not a valid target either
    assert (await post({**base, "target_type": "player"})).status_code == 422
    assert (await post({**base, "deadline": None})).status_code == 201  # deadline is optional


async def test_cannot_target_hidden_players_or_foreign_scouts(client):
    s = await scouting_setup(client)
    other_t, other_org = await setup_org(client, "o2@x.com", "Other Org")
    hidden = await make_player(client, other_t, other_org, "Hidden Man", 22)  # private to other org
    r = await client.post(
        f"{API}/assignments",
        json={
            "scout_id": s.scout_id,
            "target_type": "player",
            "target_id": hidden["id"],
            "title": "Spy on them",
        },
        headers=s.rm_h,
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_target"
    # the other org cannot assign our scout either
    r = await client.post(
        f"{API}/assignments",
        json={
            "scout_id": s.scout_id,
            "target_type": "player",
            "target_id": hidden["id"],
            "title": "Steal scout",
        },
        headers=hdr(other_t, other_org),
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_scout"


async def test_inactive_scout_cannot_be_assigned(client):
    s = await scouting_setup(client)
    await client.patch(f"{API}/scouts/{s.scout_id}", json={"is_active": False}, headers=s.owner_h)
    r = await client.post(
        f"{API}/assignments",
        json={
            "scout_id": s.scout_id,
            "target_type": "match",
            "target_id": s.match["id"],
            "title": "Valid title",
        },
        headers=s.rm_h,
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_scout"


async def test_roles_and_visibility(client):
    s = await scouting_setup(client)
    other_scout_t = await add_role_member(client, s.org, "scout2@x.com", "scout")
    await client.post(f"{API}/scouts", json={}, headers=hdr(other_scout_t, s.org))
    a = await make_assignment(client, s)
    draft = await make_assignment(client, s, "player", assign_now=False)

    # only managers create and manage
    body = {
        "scout_id": s.scout_id,
        "target_type": "match",
        "target_id": s.match["id"],
        "title": "Valid title",
    }
    for h in (s.scout_h, s.coach_h):
        assert (await client.post(f"{API}/assignments", json=body, headers=h)).status_code == 403
    # the assigned scout sees it, the other scout and the coach do not
    assert [
        x["id"] for x in (await client.get(f"{API}/assignments", headers=s.scout_h)).json()["items"]
    ] == [a["id"]]
    for h in (hdr(other_scout_t, s.org), s.coach_h):
        assert (await client.get(f"{API}/assignments", headers=h)).json()["total"] == 0
        assert (await client.get(f"{API}/assignments/{a['id']}", headers=h)).status_code == 404
    # managers see everything including drafts
    ids = {
        x["id"] for x in (await client.get(f"{API}/assignments", headers=s.rm_h)).json()["items"]
    }
    assert ids == {a["id"], draft["id"]}
    assert (await client.get(f"{API}/assignments")).status_code == 401


async def test_filters_and_pagination(client):
    s = await scouting_setup(client)
    a1 = await make_assignment(client, s, "match")
    await make_assignment(client, s, "player")
    await make_assignment(client, s, "competition", assign_now=False)
    await move(client, s.scout_h, a1, "accepted")

    def total(q):
        return client.get(f"{API}/assignments?{q}", headers=s.rm_h)

    assert (await total("status=assigned")).json()["total"] == 1
    assert (await total("status=accepted")).json()["total"] == 1
    assert (await total("status=draft")).json()["total"] == 1
    assert (await total("target_type=player")).json()["total"] == 1
    assert (await total(f"scout_id={s.scout_id}")).json()["total"] == 3
    assert (await total("status=bogus")).status_code == 422
    seen = []
    for page in (1, 2):
        r = (await total(f"page={page}&page_size=2")).json()
        seen += [x["id"] for x in r["items"]]
        assert r["total"] == 3
    assert len(set(seen)) == 3


async def test_workflow_rules_and_who_may_move(client):
    s = await scouting_setup(client)
    a = await make_assignment(client, s)

    # a manager cannot accept on the scout's behalf; the scout cannot cancel
    r = await move(client, s.rm_h, a, "accepted")
    assert r.status_code == 403
    r = await move(client, s.scout_h, a, "cancelled")
    assert r.status_code == 403
    # steps that exist for nobody
    for bad in ("approved", "submitted", "draft", "under_review"):
        r = await move(client, s.scout_h, a, bad)
        assert r.status_code in (403, 409)
    r = await move(client, s.rm_h, a, "approved")
    assert r.status_code == 409 and r.json()["error"]["code"] == "invalid_transition"

    detail = (await client.get(f"{API}/assignments/{a['id']}", headers=s.scout_h)).json()
    assert detail["allowed_transitions"] == ["accepted"] and detail["is_mine"] is True
    assert (await client.get(f"{API}/assignments/{a['id']}", headers=s.rm_h)).json()[
        "allowed_transitions"
    ] == ["cancelled"]

    assert (await move(client, s.scout_h, a, "accepted")).status_code == 200
    assert (await move(client, s.scout_h, a, "in_progress")).status_code == 200
    # cannot submit with no reports
    r = await move(client, s.scout_h, a, "submitted")
    assert r.status_code == 409 and r.json()["error"]["code"] == "no_reports"
    # another scout cannot touch it at all
    other_t = await add_role_member(client, s.org, "scout2@x.com", "scout")
    assert (await move(client, hdr(other_t, s.org), a, "submitted")).status_code == 404


async def test_cancel_notifies_scout_and_is_terminal(client):
    s = await scouting_setup(client)
    a = await make_assignment(client, s)
    r = await move(client, s.rm_h, a, "cancelled", "No longer needed")
    assert r.status_code == 200
    assert (await notes(client, s.scout_t))[0]["type"] == "assignment_cancelled"
    for to in ("assigned", "accepted", "in_progress"):
        assert (await move(client, s.rm_h, a, to)).status_code in (403, 409)
    # cancelling a draft stays silent
    d = await make_assignment(client, s, "player", assign_now=False)
    before = await unread(client, s.scout_t)
    await move(client, s.rm_h, d, "cancelled")
    assert await unread(client, s.scout_t) == before


async def test_edit_rules(client):
    s = await scouting_setup(client)
    a = await make_assignment(client, s, assign_now=False)
    url = f"{API}/assignments/{a['id']}"
    r = await client.patch(
        url, json={"title": "New title", "instructions": "Updated"}, headers=s.rm_h
    )
    assert r.status_code == 200 and r.json()["title"] == "New title"
    assert r.json()["history"][-1]["note"].startswith("Edited")
    assert (await client.patch(url, json={"title": "x"}, headers=s.rm_h)).status_code == 422
    assert (
        await client.patch(url, json={"deadline": in_days(-2)}, headers=s.rm_h)
    ).status_code == 422
    assert (
        await client.patch(url, json={"title": "Scout cannot edit"}, headers=s.scout_h)
    ).status_code in (403, 404)

    other_t = await add_role_member(client, s.org, "scout2@x.com", "scout")
    other = (await client.post(f"{API}/scouts", json={}, headers=hdr(other_t, s.org))).json()
    assert (
        await client.patch(url, json={"scout_id": other["id"]}, headers=s.rm_h)
    ).status_code == 200  # still a draft
    await move(client, s.rm_h, a, "assigned")
    await move(client, hdr(other_t, s.org), a, "accepted")
    r = await client.patch(url, json={"scout_id": s.scout_id}, headers=s.rm_h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "scout_locked"
    await move(client, s.rm_h, a, "cancelled")
    r = await client.patch(url, json={"title": "Too late now"}, headers=s.rm_h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_editable"


async def test_isolation_between_organizations(client):
    s = await scouting_setup(client)
    a = await make_assignment(client, s)
    other_t, other_org = await setup_org(client, "o2@x.com", "Other Org")
    ho = hdr(other_t, other_org)
    assert (await client.get(f"{API}/assignments", headers=ho)).json()["total"] == 0
    assert (await client.get(f"{API}/assignments/{a['id']}", headers=ho)).status_code == 404
    assert (await move(client, ho, a, "cancelled")).status_code == 404
    assert (
        await client.patch(f"{API}/assignments/{a['id']}", json={"title": "Hijack"}, headers=ho)
    ).status_code == 404
    assert (await client.get(f"{API}/assignments", headers=hdr(other_t, s.org))).status_code == 403
    assert make_user and login  # (shared imports)


async def test_summary_and_overdue(client):
    s = await scouting_setup(client)
    a1 = await make_assignment(client, s, "match")
    await make_assignment(client, s, "player")
    await make_assignment(client, s, "competition", assign_now=False)
    await move(client, s.scout_h, a1, "accepted")
    async with SessionLocal() as db:  # make one overdue and one due soon
        rows = (
            await db.scalars(
                select(Assignment)
                .where(Assignment.status != "draft")
                .order_by(Assignment.created_at)
            )
        ).all()
        rows[0].deadline = datetime_hours(-5)
        rows[1].deadline = datetime_hours(20)
        await db.commit()

    r = (await client.get(f"{API}/assignments/summary", headers=s.rm_h)).json()
    assert r["counts"] == {"accepted": 1, "assigned": 1, "draft": 1}
    assert r["overdue"] == 1 and r["due_soon"] == 1
    mine = (await client.get(f"{API}/assignments/summary", headers=s.scout_h)).json()
    assert (
        mine["counts"] == {"accepted": 1, "assigned": 1} and mine["overdue"] == 1
    )  # no drafts for scouts

    od = (await client.get(f"{API}/assignments?overdue=true", headers=s.scout_h)).json()
    assert od["total"] == 1 and od["items"][0]["is_overdue"] is True
    assert (await client.get(f"{API}/assignments?mine=true", headers=s.rm_h)).json()[
        "total"
    ] == 0  # RM is not a scout


def datetime_hours(hours: float):
    from datetime import UTC, datetime, timedelta

    return datetime.now(UTC) + timedelta(hours=hours)


async def test_deadline_reminders_are_sent_once_and_respect_preferences(client):
    s = await scouting_setup(client)
    a = await make_assignment(client, s)
    async with SessionLocal() as db:
        await db.execute(
            update(Assignment).where(Assignment.id == a["id"]).values(deadline=datetime_hours(10))
        )
        await db.commit()
    before = await unread(client, s.scout_t)
    async with SessionLocal() as db:
        assert await send_deadline_reminders(db) == 1
    async with SessionLocal() as db:
        assert await send_deadline_reminders(db) == 0  # idempotent
    assert await unread(client, s.scout_t) == before + 1
    assert (await notes(client, s.scout_t))[0]["type"] == "assignment_deadline"

    # a changed deadline earns a fresh reminder; a user who opted out receives none
    await client.put(
        f"{API}/notifications/preferences",
        json={"preferences": {"assignment_deadline": False}},
        headers={"Authorization": f"Bearer {s.scout_t}"},
    )
    await client.patch(
        f"{API}/assignments/{a['id']}", json={"deadline": in_days(0.4)}, headers=s.rm_h
    )
    after_edit = await unread(client, s.scout_t)
    async with SessionLocal() as db:
        assert await send_deadline_reminders(db) == 1  # processed, but no notification delivered
    assert await unread(client, s.scout_t) == after_edit
    # finished assignments are never reminded
    async with SessionLocal() as db:
        await db.execute(
            update(Assignment)
            .where(Assignment.id == a["id"])
            .values(status="cancelled", reminder_sent_at=None, deadline=datetime_hours(5))
        )
        await db.commit()
        assert await send_deadline_reminders(db) == 0
