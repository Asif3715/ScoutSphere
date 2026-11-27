from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select, update

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.audit import AuditLog
from app.models.user import User, UserSession
from tests.conftest import PASSWORD, bearer, login, make_user

REG = {"email": "new@example.com", "password": PASSWORD, "full_name": "New User"}


async def test_register_success_hashes_password(client):
    r = await client.post("/api/v1/auth/register", json=REG)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "new@example.com" and "password" not in str(body)
    async with SessionLocal() as db:
        user = await db.scalar(select(User))
        assert user.password_hash.startswith("$argon2id$")


async def test_register_duplicate_email_case_insensitive(client):
    await client.post("/api/v1/auth/register", json=REG)
    r = await client.post("/api/v1/auth/register", json={**REG, "email": "NEW@example.com"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_taken"


async def test_register_rejects_weak_password_and_bad_email(client):
    r = await client.post("/api/v1/auth/register", json={**REG, "password": "short"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    r = await client.post("/api/v1/auth/register", json={**REG, "email": "nope"})
    assert r.status_code == 422


async def test_register_cannot_self_assign_platform_role(client):
    r = await client.post("/api/v1/auth/register", json={**REG, "platform_role": "super_admin"})
    assert r.status_code == 201
    assert r.json()["platform_role"] is None
    r = await client.post(
        "/api/v1/auth/register", json={**REG, "email": "b@x.com", "account_type": "super_admin"}
    )
    assert r.status_code == 422


async def test_login_success_sets_httponly_refresh_cookie(client):
    await make_user("a@example.com")
    r = await client.post(
        "/api/v1/auth/login", json={"email": "a@example.com", "password": PASSWORD}
    )
    assert r.status_code == 200
    assert r.json()["access_token"] and r.json()["token_type"] == "bearer"
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/api/v1/auth" in cookie


async def test_login_wrong_password_and_unknown_user_same_error(client):
    await make_user("a@example.com")
    bad = await client.post(
        "/api/v1/auth/login", json={"email": "a@example.com", "password": "wrong-password"}
    )
    unknown = await client.post(
        "/api/v1/auth/login", json={"email": "zzz@example.com", "password": "wrong-password"}
    )
    assert bad.status_code == unknown.status_code == 401
    assert bad.json() == unknown.json()
    async with SessionLocal() as db:
        fails = (await db.scalars(select(AuditLog).where(AuditLog.outcome == "failure"))).all()
        assert len(fails) == 2


async def test_inactive_user_cannot_login_or_use_token(client):
    user = await make_user("a@example.com")
    token = await login(client, "a@example.com")
    async with SessionLocal() as db:
        await db.execute(update(User).where(User.id == user.id).values(is_active=False))
        await db.commit()
    assert (await client.get("/api/v1/auth/me", headers=bearer(token))).status_code == 401
    r = await client.post(
        "/api/v1/auth/login", json={"email": "a@example.com", "password": PASSWORD}
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "account_disabled"


async def test_me_requires_valid_token(client):
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    assert (await client.get("/api/v1/auth/me", headers=bearer("garbage"))).status_code == 401


async def test_me_returns_user(client):
    await make_user("a@example.com")
    token = await login(client, "a@example.com")
    r = await client.get("/api/v1/auth/me", headers=bearer(token))
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "a@example.com" and r.json()["memberships"] == []


async def test_expired_token_rejected(client):
    user = await make_user("a@example.com")
    s = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": str(user.id),
        "type": "access",
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
    }
    expired = jwt.encode(claims, s.jwt_secret, algorithm=s.jwt_algorithm)
    r = await client.get("/api/v1/auth/me", headers=bearer(expired))
    assert r.status_code == 401


async def test_forged_wrong_secret_and_alg_none_rejected(client):
    user = await make_user("a@example.com")
    s = get_settings()
    exp = datetime.now(UTC) + timedelta(hours=1)
    claims = {"sub": str(user.id), "type": "access", "exp": exp}
    forged = jwt.encode(claims, "some-other-secret-that-is-long-enough!!", algorithm="HS256")
    assert (await client.get("/api/v1/auth/me", headers=bearer(forged))).status_code == 401
    none_alg = jwt.encode(claims, key=None, algorithm="none")
    assert (await client.get("/api/v1/auth/me", headers=bearer(none_alg))).status_code == 401
    assert s.jwt_algorithm == "HS256"


async def test_refresh_token_is_not_accepted_as_access_token(client):
    await make_user("a@example.com")
    r = await client.post(
        "/api/v1/auth/login", json={"email": "a@example.com", "password": PASSWORD}
    )
    refresh_token = client.cookies.get("refresh_token", path="/api/v1/auth")
    assert (await client.get("/api/v1/auth/me", headers=bearer(refresh_token))).status_code == 401
    assert r.status_code == 200


async def test_refresh_rotates_and_old_token_is_revoked(client):
    await make_user("a@example.com")
    await client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": PASSWORD})
    old = client.cookies.get("refresh_token", path="/api/v1/auth")

    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 200 and r.json()["access_token"]
    new = client.cookies.get("refresh_token", path="/api/v1/auth")
    assert new and new != old

    # Replaying the rotated-out token LATER (outside the short concurrency grace window) is
    # rejected AND burns the whole family.
    async with SessionLocal() as db:
        await db.execute(
            update(UserSession)
            .values(revoked_at=datetime.now(UTC) - timedelta(minutes=5))
            .where(UserSession.revoked_at.is_not(None))
        )
        await db.commit()
    client.cookies.set("refresh_token", old, path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401
    client.cookies.set("refresh_token", new, path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401
    async with SessionLocal() as db:
        reuse = await db.scalar(
            select(AuditLog).where(AuditLog.action == "auth.refresh_reuse_detected")
        )
        assert reuse is not None


async def test_refresh_without_or_with_bad_cookie(client):
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401
    client.cookies.set("refresh_token", "not-a-token", path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_expired_refresh_token_rejected(client):
    await make_user("a@example.com")
    await client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": PASSWORD})
    async with SessionLocal() as db:
        await db.execute(
            update(UserSession).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await db.commit()
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_logout_revokes_refresh_token(client):
    await make_user("a@example.com")
    await client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": PASSWORD})
    saved = client.cookies.get("refresh_token", path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/logout")).status_code == 204
    client.cookies.set("refresh_token", saved, path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401
    # logout without a session is still fine (idempotent)
    client.cookies.clear()
    assert (await client.post("/api/v1/auth/logout")).status_code == 204


async def test_refresh_token_stored_hashed_only(client):
    await make_user("a@example.com")
    await client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": PASSWORD})
    raw = client.cookies.get("refresh_token", path="/api/v1/auth")
    async with SessionLocal() as db:
        sess = await db.scalar(select(UserSession))
        assert raw.split(".", 1)[1] not in sess.refresh_token_hash
        assert len(sess.refresh_token_hash) == 64


# ---- sign-in throttling -------------------------------------------------------------------
async def _attempt(client, email, password="wrong-password-1"):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


def _from_ip(ip):
    """A client whose requests arrive from `ip` (the app trusts the socket, not headers)."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    return AsyncClient(transport=ASGITransport(app=app, client=(ip, 4321)), base_url="http://test")


async def test_repeated_wrong_passwords_lock_the_account_for_a_while(client):
    await make_user("lock@example.com")
    for _ in range(5):
        assert (await _attempt(client, "lock@example.com")).status_code == 401
    r = await _attempt(client, "lock@example.com", PASSWORD)  # even the right password waits
    assert r.status_code == 429 and r.json()["error"]["code"] == "too_many_attempts"
    assert int(r.headers["retry-after"]) > 0
    assert "Try again in" in r.json()["error"]["message"]


async def test_unknown_emails_are_throttled_the_same_way(client):
    for _ in range(5):
        assert (await _attempt(client, "nobody@example.com")).status_code == 401
    assert (await _attempt(client, "nobody@example.com")).status_code == 429


async def test_email_case_does_not_bypass_the_lock(client):
    await make_user("case@example.com")
    for _ in range(5):
        await _attempt(client, "case@example.com")
    assert (await _attempt(client, "CASE@Example.com")).status_code == 429


async def test_a_successful_sign_in_resets_the_count(client):
    await make_user("reset@example.com")
    for _ in range(4):
        await _attempt(client, "reset@example.com")
    assert (await _attempt(client, "reset@example.com", PASSWORD)).status_code == 200
    for _ in range(4):
        assert (await _attempt(client, "reset@example.com")).status_code == 401


async def test_one_ip_guessing_many_accounts_is_blocked(client):
    async with _from_ip("198.51.100.9") as attacker, _from_ip("198.51.100.10") as other:
        for i in range(30):
            await _attempt(attacker, f"spray{i}@example.com")
        assert (await _attempt(attacker, "fresh@example.com")).status_code == 429
        # someone else on another address is unaffected
        assert (await _attempt(other, "fresh@example.com")).status_code == 401


async def test_forwarded_headers_cannot_dodge_the_ip_limit(client):
    async with _from_ip("198.51.100.20") as attacker:
        for i in range(30):
            await attacker.post(
                "/api/v1/auth/login",
                json={"email": f"x{i}@example.com", "password": "wrong-password-1"},
                headers={"X-Forwarded-For": f"10.0.0.{i}"},
            )
        assert (await _attempt(attacker, "y@example.com")).status_code == 429


async def test_sign_in_still_works_when_redis_is_down(client, monkeypatch):
    from redis.exceptions import ConnectionError as RedisConnectionError

    from app.services import login_throttle

    class Broken:
        async def get(self, *a):
            raise RedisConnectionError("down")

        def pipeline(self, *a, **k):
            raise RedisConnectionError("down")

        async def delete(self, *a):
            raise RedisConnectionError("down")

    monkeypatch.setattr(login_throttle, "_redis", lambda: Broken())
    await make_user("redisdown@example.com")
    assert (await _attempt(client, "redisdown@example.com")).status_code == 401
    assert (await _attempt(client, "redisdown@example.com", PASSWORD)).status_code == 200
