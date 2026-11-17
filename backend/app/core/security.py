import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

_hasher = PasswordHasher()  # Argon2id with library defaults
# Verified against when the email is unknown, so timing does not reveal account existence.
DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    """Returns (token, expires_in_seconds)."""
    s = get_settings()
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=s.access_token_minutes)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm), s.access_token_minutes * 60


def decode_access_token(token: str) -> uuid.UUID | None:
    """Returns the user id, or None for any invalid/expired/wrong-type token."""
    s = get_settings()
    try:
        payload = jwt.decode(
            token,
            s.jwt_secret,
            algorithms=[s.jwt_algorithm],  # pinned: never trust the token's own alg
            options={"require": ["exp", "sub", "type"]},
        )
        if payload.get("type") != "access":
            return None
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError):
        return None


def new_refresh_token(session_id: uuid.UUID) -> tuple[str, str]:
    """Returns (opaque token for the client, sha256 hash to store)."""
    secret = secrets.token_urlsafe(48)
    return f"{session_id}.{secret}", hash_refresh_secret(secret)


def hash_refresh_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def parse_refresh_token(token: str) -> tuple[uuid.UUID, str] | None:
    try:
        sid, secret = token.split(".", 1)
        return uuid.UUID(sid), secret
    except ValueError:
        return None


def assert_secure_config() -> None:
    s = get_settings()
    if s.environment not in {"local", "test"} and (
        s.jwt_secret.startswith("dev-only") or len(s.jwt_secret) < 32
    ):
        raise RuntimeError("JWT_SECRET must be set to a strong value outside local/test")
