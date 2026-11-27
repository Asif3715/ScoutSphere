"""Slows down password guessing. Failed sign-ins are counted in Redis per email address and
per client IP; once either reaches its limit, attempts are refused (HTTP 429) until the
window expires. A successful sign-in clears the email's counter.

Unknown emails are counted exactly like real ones, so the lockout reveals nothing about which
accounts exist. If Redis is unreachable we fail open (and log it): a cache outage must not
lock every user out of the product.
"""

import asyncio
import hashlib
import math

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.errors import AppError

log = structlog.get_logger()
_clients: dict[int, Redis] = {}


def _redis() -> Redis:
    """One client per event loop (connections cannot be shared across loops)."""
    loop = id(asyncio.get_running_loop())
    if loop not in _clients:
        if len(_clients) > 8:  # old loops (tests) are gone; drop their clients
            _clients.clear()
        _clients[loop] = Redis.from_url(get_settings().redis_url, socket_timeout=1)
    return _clients[loop]


def _keys(email: str, ip: str | None) -> list[str]:
    # hash the email so addresses are not stored in plain text in the cache
    acct = hashlib.sha256(email.strip().lower().encode()).hexdigest()[:32]
    keys = [f"login:fail:acct:{acct}"]
    if ip:
        keys.append(f"login:fail:ip:{ip}")
    return keys


def _limits() -> tuple[int, int]:
    s = get_settings()
    return s.login_max_failures_per_account, s.login_max_failures_per_ip


async def check(email: str, ip: str | None) -> None:
    """Raises 429 if this email or IP has used up its attempts."""
    acct_limit, ip_limit = _limits()
    try:
        r = _redis()
        for key, limit in zip(_keys(email, ip), (acct_limit, ip_limit), strict=False):
            count = int(await r.get(key) or 0)
            if count >= limit:
                ttl = await r.ttl(key)
                wait = max(ttl, 1)
                minutes = math.ceil(wait / 60)
                raise AppError(
                    429, "too_many_attempts",
                    f"Too many sign-in attempts. Try again in {minutes} minute"
                    f"{'' if minutes == 1 else 's'}.",
                    headers={"Retry-After": str(wait)},
                )  # fmt: skip
    except RedisError as e:
        log.warning("login_throttle.unavailable", error=str(e))


async def record_failure(email: str, ip: str | None) -> None:
    window = get_settings().login_window_minutes * 60
    try:
        r = _redis()
        for key in _keys(email, ip):
            async with r.pipeline(transaction=True) as p:
                p.incr(key)
                p.expire(key, window, nx=True)  # the window starts at the first failure
                await p.execute()
    except RedisError as e:
        log.warning("login_throttle.unavailable", error=str(e))


async def clear(email: str) -> None:
    try:
        await _redis().delete(_keys(email, None)[0])
    except RedisError as e:
        log.warning("login_throttle.unavailable", error=str(e))
