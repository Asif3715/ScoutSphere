from tests.conftest import hdr
from tests.helpers import (
    API,
    add_clubs,
    add_role_member,
    make_comp,
    make_match,
    make_player,
    make_season,
    match_setup,
    platform_headers,
    ref_club,
    setup_org,
)


async def started_match(client, status="live"):
    token, org, h, c1, c2, comp, season = await match_setup(client)
    m = await make_match(client, h, season, c1, c2)
    body = {"status": status, "home_score": 0, "away_score": 0}
    assert (await client.patch(f"{API}/matches/{m['id']}", json=body, headers=h)).status_code == 200
    return token, org, h, c1, c2, comp, season, m


async def test_create_and_get_match(client):
    token, org, h, c1, c2, comp, season = await match_setup(client)
    m = await make_match(client, h, season, c1, c2, venue="North Park", round_label="Round 1")
    assert m["status"] == "scheduled" and m["home_score"] is None and m["editable"] is True
    assert m["home_club_name"] == "North United" and m["competition_name"] == "Alpha League"
    got = (await client.get(f"{API}/matches/{m['id']}", headers=h)).json()
    assert got["venue"] == "North Park" and got["events"] == []
    assert got["statistics"] == {"home": None, "away": None}


async def test_creation_validation_and_consistency(client):
    token, org, h, c1, c2, comp, season = await match_setup(client)
    base = {
        "season_id": season["id"],
        "home_club_id": c1["id"],
        "away_club_id": c2["id"],
        "kickoff_at": "2026-03-01T15:00:00Z",
    }
    assert (
        await client.post(f"{API}/matches", json={**base, "away_club_id": c1["id"]}, headers=h)
    ).status_code == 422
    assert (
        await client.post(
            f"{API}/matches", json={**base, "kickoff_at": "2026-03-01T15:00:00"}, headers=h
        )
    ).status_code == 422
    assert (
        await client.post(f"{API}/matches", json={**base, "kickoff_at": "soon"}, headers=h)
    ).status_code == 422
    r = await client.post(
        f"{API}/matches",
        json={**base, "season_id": "00000000-0000-0000-0000-000000000000"},
        headers=h,
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_season"

    ph = await platform_headers(client)
    stranger = await ref_club(client, ph, "Stranger FC")
    r = await client.post(
        f"{API}/matches", json={**base, "away_club_id": stranger["id"]}, headers=h
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "club_not_in_season"
    await add_clubs(client, h, season, stranger)
    assert (
        await client.post(
            f"{API}/matches", json={**base, "away_club_id": stranger["id"]}, headers=h
        )
    ).status_code == 201


async def test_status_workflow_and_scores(client):
    token, org, h, c1, c2, comp, season = await match_setup(client)
    m = await make_match(client, h, season, c1, c2)
    url = f"{API}/matches/{m['id']}"

    r = await client.patch(url, json={"status": "finished"}, headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "scores_required"
    r = await client.patch(url, json={"home_score": 1, "away_score": 0}, headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "scores_not_allowed"
    r = await client.patch(url, json={"status": "live", "home_score": 1}, headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "scores_incomplete"

    r = await client.patch(
        url, json={"status": "live", "home_score": 0, "away_score": 0}, headers=h
    )
    assert r.status_code == 200 and r.json()["status"] == "live"
    r = await client.patch(url, json={"home_score": 1}, headers=h)  # away keeps its 0
    assert (r.json()["home_score"], r.json()["away_score"]) == (1, 0)
    r = await client.patch(url, json={"status": "finished"}, headers=h)  # keeps the live score
    assert r.status_code == 200 and (r.json()["status"], r.json()["home_score"]) == ("finished", 1)
    # a final score can still be corrected, but a finished match cannot be re-opened
    assert (await client.patch(url, json={"home_score": 2}, headers=h)).json()["home_score"] == 2
    for status in ("live", "scheduled", "postponed", "cancelled"):
        r = await client.patch(url, json={"status": status}, headers=h)
        assert r.status_code == 409 and r.json()["error"]["code"] == "invalid_transition", status
    for bad in (
        {"home_score": -1},
        {"home_score": 100},
        {"status": "abandoned"},
        {"kickoff_at": None},
        {"status": None},
    ):
        assert (await client.patch(url, json=bad, headers=h)).status_code == 422, bad


async def test_postpone_cancel_and_reinstate(client):
    token, org, h, c1, c2, comp, season = await match_setup(client)
    m = await make_match(client, h, season, c1, c2)
    url = f"{API}/matches/{m['id']}"
    assert (await client.patch(url, json={"status": "postponed"}, headers=h)).status_code == 200
    r = await client.patch(
        url, json={"status": "finished", "home_score": 1, "away_score": 1}, headers=h
    )
    assert r.status_code == 409  # postponed -> finished is not allowed
    assert (
        await client.patch(
            url, json={"status": "scheduled", "kickoff_at": "2026-04-01T18:00:00Z"}, headers=h
        )
    ).status_code == 200
    # abandoning a live match clears its provisional score
    await client.patch(url, json={"status": "live", "home_score": 2, "away_score": 1}, headers=h)
    r = await client.patch(url, json={"status": "cancelled"}, headers=h)
    assert r.status_code == 200 and r.json()["home_score"] is None
    assert (
        await client.patch(url, json={"status": "scheduled"}, headers=h)
    ).status_code == 200  # reinstated


async def test_delete_only_unplayed_matches(client):
    token, org, h, c1, c2, comp, season = await match_setup(client)
    m = await make_match(client, h, season, c1, c2)
    assert (await client.delete(f"{API}/matches/{m['id']}", headers=h)).status_code == 204
    assert (await client.get(f"{API}/matches/{m['id']}", headers=h)).status_code == 404
    m2 = await make_match(client, h, season, c1, c2)
    await client.patch(
        f"{API}/matches/{m2['id']}",
        json={"status": "live", "home_score": 0, "away_score": 0},
        headers=h,
    )
    r = await client.delete(f"{API}/matches/{m2['id']}", headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "match_played"


async def test_season_and_participant_cannot_be_removed_while_in_use(client):
    token, org, h, c1, c2, comp, season = await match_setup(client)
    m = await make_match(client, h, season, c1, c2)
    r = await client.delete(f"{API}/seasons/{season['id']}", headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "season_has_matches"
    r = await client.delete(f"{API}/seasons/{season['id']}/participants/{c1['id']}", headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "participant_has_matches"
    await client.delete(f"{API}/matches/{m['id']}", headers=h)
    assert (
        await client.delete(f"{API}/seasons/{season['id']}/participants/{c1['id']}", headers=h)
    ).status_code == 200


# ---- events ---------------------------------------------------------------------------
async def test_events_lifecycle_and_validation(client):
    token, org, h, c1, c2, comp, season, m = await started_match(client)
    url = f"{API}/matches/{m['id']}/events"
    player = await make_player(client, token, org, "Goal Scorer", 24)

    r = await client.post(
        url,
        json={"event_type": "goal", "minute": 70, "club_id": c1["id"], "player_id": player["id"]},
        headers=h,
    )
    assert r.status_code == 201
    await client.post(
        url,
        json={
            "event_type": "yellow_card",
            "minute": 12,
            "club_id": c2["id"],
            "description": "Late tackle",
        },
        headers=h,
    )
    events = (await client.get(f"{API}/matches/{m['id']}", headers=h)).json()["events"]
    assert [(e["minute"], e["event_type"]) for e in events] == [
        (12, "yellow_card"),
        (70, "goal"),
    ]  # by minute
    assert events[1]["player_name"] == "Goal Scorer" and events[1]["club_name"] == "North United"

    ph = await platform_headers(client)
    stranger = await ref_club(client, ph, "Not Playing FC")
    for bad in (
        {"event_type": "goal", "minute": 5, "club_id": stranger["id"]},
        {"event_type": "goal", "minute": 151, "club_id": c1["id"]},
        {"event_type": "goal", "minute": -1, "club_id": c1["id"]},
        {"event_type": "dive", "minute": 5, "club_id": c1["id"]},
        {
            "event_type": "goal",
            "minute": 5,
            "club_id": c1["id"],
            "player_id": "00000000-0000-0000-0000-000000000000",
        },
    ):
        assert (await client.post(url, json=bad, headers=h)).status_code == 422, bad

    r = await client.delete(f"{url}/{events[0]['id']}", headers=h)
    assert r.status_code == 200 and len(r.json()["events"]) == 1
    assert (await client.delete(f"{url}/{events[0]['id']}", headers=h)).status_code == 404


async def test_events_and_stats_need_a_started_match(client):
    token, org, h, c1, c2, comp, season = await match_setup(client)
    m = await make_match(client, h, season, c1, c2)  # scheduled
    r = await client.post(
        f"{API}/matches/{m['id']}/events",
        json={"event_type": "goal", "minute": 1, "club_id": c1["id"]},
        headers=h,
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "match_not_started"
    r = await client.put(
        f"{API}/matches/{m['id']}/statistics", json={"home": {"shots": 3}}, headers=h
    )
    assert r.status_code == 409


async def test_event_cannot_reference_hidden_players(client):
    token, org, h, c1, c2, comp, season, m = await started_match(client)
    other_t, other_org = await setup_org(client, "o2@x.com", "Other Org")
    hidden = await make_player(
        client, other_t, other_org, "Hidden Man", 22
    )  # private to the other org
    r = await client.post(
        f"{API}/matches/{m['id']}/events",
        json={"event_type": "goal", "minute": 5, "club_id": c1["id"], "player_id": hidden["id"]},
        headers=h,
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_player"


# ---- statistics -----------------------------------------------------------------------
async def test_statistics_roundtrip_and_validation(client):
    token, org, h, c1, c2, comp, season, m = await started_match(client)
    url = f"{API}/matches/{m['id']}/statistics"
    home = {"possession_pct": 60, "shots": 12, "shots_on_target": 5, "corners": 6}
    r = await client.put(url, json={"home": home}, headers=h)
    assert r.status_code == 200
    assert r.json()["statistics"]["home"]["shots"] == 12 and r.json()["statistics"]["away"] is None

    r = await client.put(url, json={"away": {"possession_pct": 40, "shots": 8}}, headers=h)
    assert r.json()["statistics"]["home"]["possession_pct"] == 60  # untouched side kept
    assert r.json()["statistics"]["away"]["shots"] == 8

    # combined possession is checked against the stored side too
    r = await client.put(url, json={"away": {"possession_pct": 55}}, headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_possession"
    assert (
        await client.put(url, json={"home": {"shots": 3, "shots_on_target": 9}}, headers=h)
    ).status_code == 422
    for bad in ({"possession_pct": 101}, {"corners": -1}, {"red_cards": 12}):
        assert (await client.put(url, json={"home": bad}, headers=h)).status_code == 422

    r = await client.put(url, json={"home": None}, headers=h)  # clears one side
    assert r.json()["statistics"]["home"] is None and r.json()["statistics"]["away"]["shots"] == 8


# ---- list, filters, scopes ------------------------------------------------------------
async def test_list_filters_sorting_pagination(client):
    token, org, h, c1, c2, comp, season = await match_setup(client)
    comp2 = await make_comp(client, h, "Second Cup")
    season2 = await make_season(client, h, comp2, "2026")
    await add_clubs(client, h, season2, c1, c2)
    stamps = ["2026-01-10T12:00:00Z", "2026-02-10T12:00:00Z", "2026-03-10T12:00:00Z"]
    ms = [await make_match(client, h, season, c1, c2, kickoff_at=t) for t in stamps]
    cup = await make_match(client, h, season2, c2, c1, kickoff_at="2026-02-20T12:00:00Z")
    await client.patch(
        f"{API}/matches/{ms[0]['id']}",
        json={"status": "live", "home_score": 0, "away_score": 0},
        headers=h,
    )

    async def ids(q=""):
        r = await client.get(f"{API}/matches?{q}", headers=h)
        assert r.status_code == 200, r.text
        return [m["id"] for m in r.json()["items"]], r.json()["total"]

    assert (await ids())[0] == [ms[2]["id"], cup["id"], ms[1]["id"], ms[0]["id"]]  # newest first
    assert (await ids("sort=kickoff_asc"))[0][0] == ms[0]["id"]
    assert (await ids(f"competition_id={comp2['id']}"))[0] == [cup["id"]]
    assert (await ids(f"season_id={season['id']}"))[1] == 3
    assert (await ids(f"club_id={c1['id']}"))[1] == 4
    assert (await ids("status=live"))[0] == [ms[0]["id"]]
    assert (await ids("date_from=2026-02-10&date_to=2026-02-20"))[0] == [
        cup["id"],
        ms[1]["id"],
    ]  # inclusive days
    assert (await ids("date_from=2027-01-01"))[1] == 0
    seen = []
    for page in (1, 2):
        got, total = await ids(f"page={page}&page_size=2")
        seen += got
        assert total == 4
    assert len(set(seen)) == 4
    assert (await client.get(f"{API}/matches?status=bogus", headers=h)).status_code == 422
    assert (await client.get(f"{API}/matches?page_size=500", headers=h)).status_code == 422


async def test_roles_and_isolation(client):
    token, org, h, c1, c2, comp, season = await match_setup(client)
    m = await make_match(client, h, season, c1, c2)
    scout_t = await add_role_member(client, org, "scout@x.com", "scout")
    coach_t = await add_role_member(client, org, "coach@x.com", "coach")
    rm_t = await add_role_member(client, org, "rm@x.com", "recruitment_manager")
    for t in (scout_t, coach_t, rm_t):
        hh = hdr(t, org)
        assert (await client.get(f"{API}/matches/{m['id']}", headers=hh)).status_code == 200
        assert (
            await client.patch(f"{API}/matches/{m['id']}", json={"venue": "x"}, headers=hh)
        ).status_code == 403
        assert (await client.delete(f"{API}/matches/{m['id']}", headers=hh)).status_code == 403
        r = await client.post(
            f"{API}/matches",
            json={
                "season_id": season["id"],
                "home_club_id": c1["id"],
                "away_club_id": c2["id"],
                "kickoff_at": "2026-05-01T12:00:00Z",
            },
            headers=hh,
        )
        assert r.status_code == 403

    other_t, other_org = await setup_org(client, "o2@x.com", "Other Org")
    ho = hdr(other_t, other_org)
    assert (await client.get(f"{API}/matches", headers=ho)).json()["total"] == 0
    assert (await client.get(f"{API}/matches/{m['id']}", headers=ho)).status_code == 404
    assert (
        await client.patch(f"{API}/matches/{m['id']}", json={"venue": "x"}, headers=ho)
    ).status_code == 404
    assert (await client.delete(f"{API}/matches/{m['id']}", headers=ho)).status_code == 404
    assert (
        await client.get(f"{API}/matches", headers=hdr(other_t, org))
    ).status_code == 403  # spoofed header
    assert (await client.get(f"{API}/matches")).status_code == 401


async def test_global_matches_are_visible_but_read_only_for_tenants(client):
    ph = await platform_headers(client)
    c1, c2 = await ref_club(client, ph, "Global A"), await ref_club(client, ph, "Global B")
    gcomp = await make_comp(client, ph, "World League")
    gseason = await make_season(client, ph, gcomp)
    await add_clubs(client, ph, gseason, c1, c2)
    gm = await make_match(client, ph, gseason, c1, c2)
    assert gm["is_global"] is True

    token, org = await setup_org(client)
    h = hdr(token, org)
    listing = (await client.get(f"{API}/matches", headers=h)).json()
    assert [x["id"] for x in listing["items"]] == [gm["id"]] and listing["items"][0][
        "editable"
    ] is False
    assert (
        await client.patch(f"{API}/matches/{gm['id']}", json={"venue": "x"}, headers=h)
    ).status_code == 404
    assert (await client.delete(f"{API}/matches/{gm['id']}", headers=h)).status_code == 404
    assert (
        await client.post(
            f"{API}/matches/{gm['id']}/events",
            json={"event_type": "goal", "minute": 1, "club_id": c1["id"]},
            headers=h,
        )
    ).status_code == 404

    # an organization may schedule its own private match inside a global competition
    own = await make_match(client, h, gseason, c1, c2, kickoff_at="2026-09-01T12:00:00Z")
    assert own["is_global"] is False and own["editable"] is True
    other_t, other_org = await setup_org(client, "o2@x.com", "Other Org")
    ids = [
        x["id"]
        for x in (await client.get(f"{API}/matches", headers=hdr(other_t, other_org))).json()[
            "items"
        ]
    ]
    assert ids == [gm["id"]]  # the other org sees the global match but not this private one

    # global matches cannot reference players
    await client.patch(
        f"{API}/matches/{gm['id']}",
        json={"status": "live", "home_score": 0, "away_score": 0},
        headers=ph,
    )
    p = await make_player(client, token, org, "Some Player", 22, visibility="network")
    r = await client.post(
        f"{API}/matches/{gm['id']}/events",
        json={"event_type": "goal", "minute": 1, "club_id": c1["id"], "player_id": p["id"]},
        headers=ph,
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "player_not_allowed"
