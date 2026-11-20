from tests.conftest import hdr
from tests.helpers import (
    API,
    REC,
    add_spell,
    approved_report,
    make_club,
    make_player,
    make_requirement,
    scouting_setup,
    setup_org,
)

SL = f"{REC}/shortlists"


async def trio(client, s):
    club = await make_club(client, s.owner_t, s.org, "Compare Club")
    a = await make_player(
        client,
        s.owner_t,
        s.org,
        "Alpha Mid",
        21,
        height_cm=180,
        weight_kg=72,
        secondary_positions=["CAM"],
    )
    b = await make_player(
        client, s.owner_t, s.org, "Bravo Mid", 27, preferred_foot="left", nationality="Spain"
    )
    c = await make_player(client, s.owner_t, s.org, "Charlie Mid", 19)
    await add_spell(
        client,
        s,
        a["id"],
        club["id"],
        start_date="2018-01-01",
        end_date="2020-06-30",
        appearances=50,
        goals=5,
        assists=2,
    )
    await add_spell(
        client, s, a["id"], club["id"], start_date="2020-07-01", appearances=30, goals=9, assists=7
    )
    await add_spell(client, s, b["id"], club["id"], appearances=100, goals=20, assists=30)
    await approved_report(
        client, s, a["id"], {"passing": 8, "speed": 6, "agility": 7}, "strongly_recommend"
    )
    await approved_report(client, s, a["id"], {"passing": 6, "speed": 8, "agility": 7}, "recommend")
    await approved_report(client, s, b["id"], {"passing": 7, "speed": 9, "agility": 5}, "monitor")
    return a, b, c


async def test_comparison_separates_objective_facts_from_scout_opinion(client):
    s = await scouting_setup(client)
    a, b, c = await trio(client, s)
    r = await client.post(
        f"{REC}/compare", json={"player_ids": [a["id"], b["id"], c["id"]]}, headers=s.rm_h
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert [p["player"]["full_name"] for p in body["players"]] == [
        "Alpha Mid",
        "Bravo Mid",
        "Charlie Mid",
    ]  # caller's order
    pa, pb, pc = body["players"]

    assert (
        pa["player"]["age"] == 21
        and pa["height_cm"] == 180
        and pa["secondary_positions"] == ["CAM"]
    )
    assert pb["preferred_foot"] == "left" and pb["player"]["nationality"] == "Spain"
    # objective: summed career stats and the most recent spell
    assert (
        pa["objective"]["appearances"],
        pa["objective"]["goals"],
        pa["objective"]["assists"],
    ) == (80, 14, 9)
    assert (pa["objective"]["recent_appearances"], pa["objective"]["recent_goals"]) == (30, 9)
    assert (
        pa["objective"]["recent_club"] == "Compare Club"
        and pa["objective"]["contract_status"] is None
    )
    assert (
        pc["objective"]["appearances"] is None and pc["objective"]["recent_club"] is None
    )  # no data: explicit nulls
    # scouting: averages over approved reports only, counted and explained
    assert pa["scouting"]["approved_reports"] == 2 and pa["scouting"]["ratings"] == {
        "passing": 7.0,
        "speed": 7.0,
        "agility": 7.0,
    }
    assert pa["scouting"]["recommendations"] == {"strongly_recommend": 1, "recommend": 1}
    assert pa["scouting"]["latest_recommendation"] == "recommend"
    assert pb["scouting"]["latest_recommendation"] == "monitor"
    assert pc["scouting"]["approved_reports"] == 0 and pc["scouting"]["ratings"] == {}
    # the two worlds never mix: ratings are not inside `objective`, stats not inside `scouting`
    assert "ratings" not in pa["objective"] and "goals" not in pa["scouting"]
    assert pa["suitability"] is None and body["requirement_title"] is None

    assert body["attributes"] == ["passing", "speed", "agility"]
    assert body["leaders"] == {
        "passing": [a["id"], b["id"]],
        "speed": [b["id"]],
        "agility": [a["id"]],
    }  # ties are shared
    # transparent by design: no composite score, ranking or "winner" is ever produced
    assert not any(k in body for k in ("ranking", "winner", "composite", "score"))
    assert not any("score" in p for p in body["players"])


async def test_comparison_against_a_requirement_shows_what_each_player_lacks(client):
    s = await scouting_setup(client)
    a, b, c = await trio(client, s)
    req = await make_requirement(
        client,
        s,
        min_age=18,
        max_age=24,
        nationality="Croatia",
        attributes={"passing": 7, "speed": 8},
    )
    r = await client.post(
        f"{REC}/compare",
        json={"player_ids": [a["id"], b["id"]], "requirement_id": req["id"]},
        headers=s.rm_h,
    )
    body = r.json()
    assert body["requirement_title"] == "Creative midfielder"

    def by_name(p):
        return {c["name"]: c for c in p["suitability"]}

    pa, pb = (by_name(p) for p in body["players"])
    assert pa["Age"]["met"] is True and pb["Age"]["met"] is False and pb["Age"]["actual"] == "27"
    assert pa["Nationality"]["met"] is True and pb["Nationality"]["met"] is False
    assert (
        pa["Passing rating"]["met"] is True
        and pa["Speed rating"]["met"] is False
        and pa["Speed rating"]["actual"] == "7.0"
    )
    assert pb["Speed rating"]["met"] is True and pb["Position"]["met"] is True


async def test_comparison_validation_and_visibility(client):
    s = await scouting_setup(client)
    a, b, c = await trio(client, s)

    def post(ids, **kw):
        return client.post(f"{REC}/compare", json={"player_ids": ids, **kw}, headers=s.rm_h)

    assert (await post([a["id"]])).status_code == 422
    assert (await post([a["id"], a["id"]])).status_code == 422
    six = [
        (await make_player(client, s.owner_t, s.org, f"Extra Player {i}", 22))["id"]
        for i in range(4)
    ]
    assert (await post([a["id"], b["id"], c["id"]] + six)).status_code == 422
    assert (await post([a["id"], "00000000-0000-0000-0000-000000000000"])).json()["error"][
        "code"
    ] == "invalid_player"
    assert (
        await post([a["id"], b["id"]], requirement_id="00000000-0000-0000-0000-000000000000")
    ).json()["error"]["code"] == "invalid_requirement"
    assert (
        await post([a["id"], b["id"], c["id"]] + six[:2])
    ).status_code == 200  # five is the maximum

    other_t, other_org = await setup_org(client, "o2@x.com", "Other Org")
    hidden = await make_player(client, other_t, other_org, "Hidden", 22)
    assert (await post([a["id"], hidden["id"]])).status_code == 422
    for h in (s.scout_h,):
        assert (
            await client.post(f"{REC}/compare", json={"player_ids": [a["id"], b["id"]]}, headers=h)
        ).status_code == 403
    assert (
        await client.post(
            f"{REC}/compare", json={"player_ids": [a["id"], b["id"]]}, headers=s.coach_h
        )
    ).status_code == 200
    assert (
        await client.post(f"{REC}/compare", json={"player_ids": [a["id"], b["id"]]})
    ).status_code == 401


async def test_another_organizations_ratings_never_appear(client):
    s = await scouting_setup(client)
    a, b, c = await trio(client, s)
    shared = await make_player(client, s.owner_t, s.org, "Network Mid", 22, visibility="network")
    await approved_report(client, s, shared["id"], {"passing": 9, "speed": 9, "agility": 9})
    other_t, other_org = await setup_org(client, "o2@x.com", "Other Org")
    ho = hdr(other_t, other_org)
    mine = await make_player(client, other_t, other_org, "Their Own", 22)
    r = await client.post(
        f"{REC}/compare", json={"player_ids": [shared["id"], mine["id"]]}, headers=ho
    )
    assert r.status_code == 200
    p_shared = r.json()["players"][0]
    assert (
        p_shared["scouting"]["approved_reports"] == 0 and p_shared["scouting"]["ratings"] == {}
    )  # our private evaluations stay ours
    assert r.json()["attributes"] == [] and r.json()["leaders"] == {}


async def test_compare_a_shortlist(client):
    s = await scouting_setup(client)
    a, b, c = await trio(client, s)
    sl = (await client.post(SL, json={"name": "Compare me"}, headers=s.rm_h)).json()
    assert (
        await client.get(f"{SL}/{sl['id']}/compare", headers=s.rm_h)
    ).status_code == 422  # empty
    await client.post(f"{SL}/{sl['id']}/players", json={"player_id": a["id"]}, headers=s.rm_h)
    assert (
        await client.get(f"{SL}/{sl['id']}/compare", headers=s.rm_h)
    ).status_code == 422  # only one
    await client.post(f"{SL}/{sl['id']}/players", json={"player_id": b["id"]}, headers=s.rm_h)
    r = await client.get(f"{SL}/{sl['id']}/compare", headers=s.rm_h)
    assert r.status_code == 200 and [p["player"]["full_name"] for p in r.json()["players"]] == [
        "Alpha Mid",
        "Bravo Mid",
    ]
    req = await make_requirement(client, s)
    assert (
        await client.get(f"{SL}/{sl['id']}/compare?requirement_id={req['id']}", headers=s.rm_h)
    ).json()["players"][0]["suitability"]
    # private shortlists cannot be compared by someone they are not shared with
    assert (await client.get(f"{SL}/{sl['id']}/compare", headers=s.owner_h)).status_code == 404
    assert API
