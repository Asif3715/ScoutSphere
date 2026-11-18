"""Regression tests for bugs found during manual QA."""

import asyncio
import json
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update

from app.db.session import SessionLocal
from app.main import app
from app.models.organization import OrganizationMember
from app.models.user import UserSession
from tests.conftest import PASSWORD, bearer, hdr, login, make_user
from tests.helpers import (
    API,
    make_assignment,
    make_club,
    make_match,
    scouting_setup,
    setup_org,
)
from tests.test_organizations import new_user


# ---- NUL characters and oversized input -------------------------------------------------
async def test_nul_characters_in_bodies_are_rejected_with_422(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    cases = [
        ("POST", f"{API}/clubs", {"name": "bad\x00name"}, h),
        ("POST", f"{API}/players", {"full_name": "Bad\x00Name", "date_of_birth": "2000-01-01"}, h),
        ("POST", f"{API}/organizations", {"name": "ab\x00cd"}, h),
        (
            "POST",
            f"{API}/auth/register",
            {"email": "nul@example.com", "password": PASSWORD, "full_name": "a\x00b"},
            {},
        ),
        ("PATCH", f"{API}/organizations/{org['id']}", {"description": "x\x00y"}, h),
    ]
    for method, url, body, headers in cases:
        r = await client.request(method, url, json=body, headers=headers)
        assert r.status_code == 422, (url, r.status_code)
        assert r.json()["error"]["code"] == "invalid_characters"


async def test_literal_backslash_u0000_text_is_not_mistaken_for_a_nul(client):
    token, org = await setup_org(client)
    # the characters backslash,u,0,0,0,0 typed by a user are legitimate text
    r = await client.post(f"{API}/clubs", json={"name": "Club \\u0000 FC"}, headers=hdr(token, org))
    assert r.status_code == 201 and r.json()["name"] == "Club \\u0000 FC"


async def test_nul_in_query_string_and_path_are_rejected(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    assert (await client.get(f"{API}/clubs?q=%00", headers=h)).status_code == 422
    assert (await client.get(f"{API}/players?q=a%00b", headers=h)).status_code == 422
    assert (await client.get(f"{API}/organizations/%00", headers=bearer(token))).status_code == 422


async def test_denied_request_to_odd_path_does_not_crash_the_audit_log(client):
    token, org = await setup_org(client)
    r = await client.get(f"{API}/platform/organizations/%00", headers=bearer(token))
    assert r.status_code < 500


async def test_huge_page_numbers_are_a_validation_error_not_a_crash(client):
    token, org = await setup_org(client)
    h = hdr(token, org)
    for path in (
        "clubs",
        "players",
        "scouts",
        "competitions",
        "matches",
        "assignments",
        "scouting-reports",
    ):
        r = await client.get(f"{API}/{path}?page=99999999999999999999", headers=h)
        assert r.status_code == 422, path
    assert (
        await client.get(f"{API}/notifications?page=9223372036854775808", headers=bearer(token))
    ).status_code == 422
    assert (
        await client.get(f"{API}/clubs?page=1000000&page_size=100", headers=h)
    ).status_code == 200


async def test_oversized_bodies_are_rejected(client):
    token, org = await setup_org(client)
    r = await client.post(
        f"{API}/clubs",
        content=json.dumps({"name": "x" * 2_000_000}),
        headers={**hdr(token, org), "content-type": "application/json"},
    )
    assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"
    ok = await client.post(
        f"{API}/clubs",
        json={"name": "Normal Club", "description": "d" * 3000},
        headers=hdr(token, org),
    )
    assert ok.status_code == 201


async def test_database_data_errors_become_422_not_500(client):
    """Backstop: even if a bad value slips past the guard, the client gets a 4xx."""
    from sqlalchemy.exc import DBAPIError

    from app.core.errors import register_error_handlers  # noqa: F401 (handler registered on app)

    class Boom(Exception):
        def __str__(self):
            return 'invalid byte sequence for encoding "UTF8": 0x00'

    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/_qa/db-error")
    async def _raise():
        raise DBAPIError("SELECT 1", {}, Boom())

    @router.get("/_qa/crash")
    async def _crash():
        raise RuntimeError("kaboom")

    app.include_router(router)
    quiet = AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    )
    async with quiet as c:
        r = await c.get("/_qa/db-error")
        assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_input"
        r = await c.get("/_qa/crash")
        assert (
            r.status_code == 500 and r.json()["error"]["code"] == "internal_error"
        )  # JSON, no details leaked
        assert "kaboom" not in r.text


async def test_security_headers_present(client):
    r = await client.get(f"{API}/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["cache-control"] == "no-store"


# ---- whitespace-only values -------------------------------------------------------------
async def test_blank_names_are_rejected_and_padding_is_trimmed(client):
    s = await scouting_setup(client)
    h = s.owner_h
    club = await make_club(client, s.owner_t, s.org, "Spare Club")
    blanks = [
        (f"{API}/clubs", {"name": "   "}, h),
        (f"{API}/players", {"full_name": "   ", "date_of_birth": "2000-01-01"}, h),
        (f"{API}/competitions", {"name": "   "}, h),
        (f"{API}/teams", {"club_id": club["id"], "name": "   "}, h),
    ]
    for url, body, headers in blanks:
        r = await client.post(url, json=body, headers=headers)
        assert r.status_code == 422, (url, r.status_code)
    r = await client.post(f"{API}/organizations", json={"name": "  "}, headers=bearer(s.owner_t))
    assert r.status_code == 422
    r = await client.post(
        f"{API}/assignments",
        json={
            "scout_id": s.scout_id,
            "target_type": "match",
            "target_id": s.match["id"],
            "title": "      ",
        },
        headers=s.rm_h,
    )
    assert r.status_code == 422
    r = await client.patch(f"{API}/clubs/{club['id']}", json={"name": "   "}, headers=h)
    assert r.status_code == 422

    ok = await client.post(f"{API}/clubs", json={"name": "   Padded Name   "}, headers=h)
    assert ok.status_code == 201 and ok.json()["name"] == "Padded Name"
    inv = await client.post(
        f"{API}/organizations/{s.org['id']}/invitations",
        json={"email": " Padded@Example.com ", "role": "scout"},
        headers=h,
    )
    assert (
        inv.status_code == 201 and inv.json()["email"] == "Padded@example.com"
    )  # trimmed; domain normalized


async def test_passwords_are_never_trimmed(client):
    spaced = "  keep my spaces  "
    r = await client.post(
        f"{API}/auth/register",
        json={"email": "spaces@example.com", "password": spaced, "full_name": "  Spacey  "},
    )
    assert r.status_code == 201 and r.json()["full_name"] == "Spacey"
    assert (
        await client.post(
            f"{API}/auth/login", json={"email": "spaces@example.com", "password": spaced}
        )
    ).status_code == 200
    assert (
        await client.post(
            f"{API}/auth/login", json={"email": "spaces@example.com", "password": spaced.strip()}
        )
    ).status_code == 401


# ---- concurrency -------------------------------------------------------------------------
async def test_concurrent_organizations_with_the_same_name_all_succeed(client):
    tokens = [await new_user(client, f"racer{i}@x.com") for i in range(6)]
    results = await asyncio.gather(
        *[
            client.post(f"{API}/organizations", json={"name": "Racing Org"}, headers=bearer(t))
            for t in tokens
        ]
    )
    assert [r.status_code for r in results] == [201] * 6
    slugs = {r.json()["slug"] for r in results}
    assert len(slugs) == 6 and "racing-org" in slugs


async def test_concurrent_invitation_accepts_do_not_crash_or_duplicate(client):
    owner_t, org = await setup_org(client)
    from tests.test_members_invitations import token_of

    await make_user("joiner@x.com")
    joiner = await login(client, "joiner@x.com")
    inv = await client.post(
        f"{API}/organizations/{org['id']}/invitations",
        json={"email": "joiner@x.com", "role": "coach"},
        headers=hdr(owner_t, org),
    )
    raw = token_of(inv.json())
    results = await asyncio.gather(
        *[
            client.post(f"{API}/invitations/accept", json={"token": raw}, headers=bearer(joiner))
            for _ in range(6)
        ]
    )
    codes = sorted(r.status_code for r in results)
    assert codes.count(200) == 1 and all(c < 500 for c in codes), codes
    async with SessionLocal() as db:
        count = len(
            (
                await db.scalars(
                    select(OrganizationMember).where(
                        OrganizationMember.organization_id == org["id"]
                    )
                )
            ).all()
        )
    assert count == 2  # the owner and the joiner, exactly once


async def test_deleting_a_match_that_other_records_use_is_a_conflict(client):
    s = await scouting_setup(client)
    spare = await make_match(
        client, s.owner_h, s.season, s.c1, s.c2, kickoff_at="2027-03-01T15:00:00Z"
    )
    assert (
        await client.delete(f"{API}/matches/{spare['id']}", headers=s.owner_h)
    ).status_code == 204  # unused: fine

    used = await make_match(
        client, s.owner_h, s.season, s.c1, s.c2, kickoff_at="2027-04-01T15:00:00Z"
    )
    body = {
        "scout_id": s.scout_id,
        "target_type": "match",
        "target_id": used["id"],
        "title": "Points at it",
    }
    assert (await client.post(f"{API}/assignments", json=body, headers=s.rm_h)).status_code == 201
    r = await client.delete(f"{API}/matches/{used['id']}", headers=s.owner_h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "match_in_use"
    assert (
        await client.get(f"{API}/matches/{used['id']}", headers=s.owner_h)
    ).status_code == 200  # still there
    assert make_assignment  # (shared import)


# ---- refresh token race (two browser tabs) -----------------------------------------------
async def _login_cookie(email="tabs@x.com") -> tuple[str, str]:
    await make_user(email)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
        return email, c.cookies.get("refresh_token", path="/api/v1/auth")


def _cookie_from(response) -> str | None:
    for header in response.headers.get_list("set-cookie"):
        if header.startswith("refresh_token="):
            value = header.split(";", 1)[0].split("=", 1)[1]
            return None if value in ("", '""') else value
    return None


async def _refresh(cookie: str):
    """One browser tab refreshing: returns (response, the new refresh cookie or None)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(f"{API}/auth/refresh", headers={"cookie": f"refresh_token={cookie}"})
        return r, _cookie_from(r)


async def test_two_tabs_refreshing_at_once_both_stay_signed_in(client):
    _, cookie = await _login_cookie()
    (r1, c1), (r2, c2) = await asyncio.gather(_refresh(cookie), _refresh(cookie))
    assert r1.status_code == 200 and r2.status_code == 200  # no tab is logged out
    # and both of the new tokens keep working afterwards
    assert (await _refresh(c1))[0].status_code == 200
    assert (await _refresh(c2))[0].status_code == 200


async def test_late_replay_of_a_rotated_token_still_kills_the_login(client):
    _, cookie = await _login_cookie("late@x.com")
    r, new_cookie = await _refresh(cookie)
    assert r.status_code == 200
    async with SessionLocal() as db:  # pretend 5 minutes have passed
        await db.execute(
            update(UserSession)
            .values(revoked_at=datetime.now(UTC) - timedelta(minutes=5))
            .where(UserSession.revoked_at.is_not(None))
        )
        await db.commit()
    assert (await _refresh(cookie))[0].status_code == 401  # replay of the old token: theft assumed
    assert (await _refresh(new_cookie))[0].status_code == 401  # the whole family is revoked


async def test_logged_out_tokens_cannot_be_revived_inside_the_grace_window(client):
    await make_user("out@x.com")
    r = await client.post(f"{API}/auth/login", json={"email": "out@x.com", "password": PASSWORD})
    cookie = client.cookies.get("refresh_token", path="/api/v1/auth")
    assert (await client.post(f"{API}/auth/logout")).status_code == 204  # revokes just now
    assert (await _refresh(cookie))[0].status_code == 401  # within seconds, but the login is dead
    assert r.status_code == 200
