import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    DUMMY_HASH,
    create_access_token,
    hash_password,
    hash_refresh_secret,
    new_refresh_token,
    parse_refresh_token,
    password_needs_rehash,
    verify_password,
)
from app.models.user import User, UserSession
from app.services.audit import record_audit

INVALID_CREDENTIALS = AppError(401, "invalid_credentials", "Invalid email or password")
INVALID_REFRESH = AppError(401, "invalid_refresh_token", "Invalid or expired refresh token")


@dataclass
class IssuedTokens:
    user: User
    access_token: str
    expires_in: int
    refresh_token: str


def _now() -> datetime:
    return datetime.now(UTC)


async def register_user(
    db: AsyncSession, *, email: str, password: str, full_name: str, account_type: str,
    ip: str | None = None,
) -> User:  # fmt: skip
    user = User(
        email=email.strip(),
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        account_type=account_type,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise AppError(409, "email_taken", "An account with this email already exists") from None
    await record_audit(
        db, action="auth.register", outcome="success", actor_user_id=user.id,
        target_type="user", target_id=str(user.id), ip_address=ip,
    )  # fmt: skip
    await db.commit()
    return user


async def _issue_session(
    db: AsyncSession, user: User, *, family_id: uuid.UUID | None, ua: str | None, ip: str | None
) -> IssuedTokens:
    s = get_settings()
    session_id = uuid.uuid4()
    token, token_hash = new_refresh_token(session_id)
    db.add(
        UserSession(
            id=session_id,
            user_id=user.id,
            family_id=family_id or uuid.uuid4(),
            refresh_token_hash=token_hash,
            expires_at=_now() + timedelta(days=s.refresh_token_days),
            user_agent=(ua or "")[:300] or None,
            ip_address=ip,
        )
    )
    access, expires_in = create_access_token(user.id)
    return IssuedTokens(user, access, expires_in, token)


async def login(
    db: AsyncSession, *, email: str, password: str, ua: str | None, ip: str | None
) -> IssuedTokens:
    user = await db.scalar(select(User).where(User.email == email.strip()))
    # Always run one Argon2 verification so unknown emails cost the same as wrong passwords.
    ok = verify_password(password, user.password_hash if user else DUMMY_HASH)
    if user is None or not ok:
        await record_audit(
            db, action="auth.login", outcome="failure",
            actor_user_id=user.id if user else None, ip_address=ip,
            metadata={"reason": "bad_credentials"},
        )  # fmt: skip
        await db.commit()
        raise INVALID_CREDENTIALS
    if not user.is_active:
        await record_audit(
            db, action="auth.login", outcome="denied", actor_user_id=user.id,
            ip_address=ip, metadata={"reason": "inactive"},
        )  # fmt: skip
        await db.commit()
        raise AppError(403, "account_disabled", "This account has been disabled")

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = _now()
    issued = await _issue_session(db, user, family_id=None, ua=ua, ip=ip)
    await record_audit(
        db, action="auth.login", outcome="success", actor_user_id=user.id, ip_address=ip
    )
    await db.commit()
    return issued


async def refresh(db: AsyncSession, *, token: str, ua: str | None, ip: str | None) -> IssuedTokens:
    parsed = parse_refresh_token(token)
    if parsed is None:
        raise INVALID_REFRESH
    session_id, secret = parsed
    sess = await db.get(UserSession, session_id, with_for_update=True)
    if sess is None or sess.refresh_token_hash != hash_refresh_secret(secret):
        raise INVALID_REFRESH

    if sess.revoked_at is not None:
        # A rotated-out token was presented again: assume theft, kill the whole family.
        await db.execute(
            update(UserSession)
            .where(UserSession.family_id == sess.family_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=_now())
        )
        await record_audit(
            db, action="auth.refresh_reuse_detected", outcome="denied",
            actor_user_id=sess.user_id, ip_address=ip,
        )  # fmt: skip
        await db.commit()
        raise INVALID_REFRESH

    user = await db.get(User, sess.user_id)
    if sess.expires_at <= _now() or user is None or not user.is_active:
        raise INVALID_REFRESH

    sess.revoked_at = _now()
    issued = await _issue_session(db, user, family_id=sess.family_id, ua=ua, ip=ip)
    await db.commit()
    return issued


async def logout(db: AsyncSession, *, token: str | None) -> None:
    """Revokes the whole token family. Always succeeds (idempotent, leaks nothing)."""
    parsed = parse_refresh_token(token) if token else None
    if parsed is None:
        return
    session_id, secret = parsed
    sess = await db.get(UserSession, session_id)
    if sess is None or sess.refresh_token_hash != hash_refresh_secret(secret):
        return
    await db.execute(
        update(UserSession)
        .where(UserSession.family_id == sess.family_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    await record_audit(db, action="auth.logout", outcome="success", actor_user_id=sess.user_id)
    await db.commit()
