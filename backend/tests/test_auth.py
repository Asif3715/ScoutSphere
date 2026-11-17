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
    expired = jwt.encode(
        {"sub": str(user.id), "type": "access", "iat": now - timedelta(hours=2), "exp": now - timedelta(hours=1)},
        s.jwt_secret, algorithm=s.jwt_algorithm,
    )  # fmt: skip
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

    # Replaying the rotated-out token is rejected AND burns the whole family.
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
