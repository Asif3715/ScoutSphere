import uuid
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.domain.scouting import NOTIFICATION_TYPES
from app.models.notification import Notification, NotificationPreference
from app.schemas.common import Page, PageParams
from app.schemas.notifications import NotificationOut, PreferenceOut


async def notify(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    type: str,
    title: str,
    body: str | None = None,
    link_path: str | None = None,
    organization_id: uuid.UUID | None = None,
) -> Notification | None:
    """Queues a notification in the caller's transaction (caller commits). Respects the
    recipient's preferences; returns None when they have switched this type off."""
    if type not in NOTIFICATION_TYPES:
        raise ValueError(f"unknown notification type {type}")
    if link_path is not None and not (link_path.startswith("/") and not link_path.startswith("//")):
        raise ValueError("link_path must be an in-app path")
    disabled = await db.scalar(
        select(NotificationPreference.enabled).where(
            NotificationPreference.user_id == user_id, NotificationPreference.type == type
        )
    )
    if disabled is False:
        return None
    n = Notification(
        user_id=user_id, organization_id=organization_id, type=type,
        title=title[:200], body=body[:500] if body else None, link_path=link_path,
    )  # fmt: skip
    db.add(n)
    return n


def _out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=n.id, type=n.type, title=n.title, body=n.body, link_path=n.link_path,
        organization_id=n.organization_id, read=n.read_at is not None, created_at=n.created_at,
    )  # fmt: skip


async def list_notifications(
    db: AsyncSession, user_id: uuid.UUID, page: PageParams, unread_only: bool = False
) -> Page[NotificationOut]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await db.scalars(
        stmt.order_by(Notification.seq.desc()).offset(page.offset).limit(page.page_size)
    )
    return Page(
        items=[_out(n) for n in rows], total=total, page=page.page, page_size=page.page_size
    )


async def unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    return (
        await db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id, Notification.read_at.is_(None)
            )
        )
    ) or 0


async def mark_read(db: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID) -> None:
    n = await db.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id
        )
    )
    if n is None:  # someone else's notification looks like a missing one
        raise AppError(404, "not_found", "Notification not found")
    if n.read_at is None:
        n.read_at = datetime.now(UTC)
    await db.commit()


async def mark_all_read(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    await db.commit()
    return cast(CursorResult, result).rowcount or 0


async def get_preferences(db: AsyncSession, user_id: uuid.UUID) -> list[PreferenceOut]:
    rows = await db.scalars(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    stored = {p.type: p.enabled for p in rows}
    return [PreferenceOut(type=t, enabled=stored.get(t, True)) for t in NOTIFICATION_TYPES]


async def update_preferences(
    db: AsyncSession, user_id: uuid.UUID, prefs: dict[str, bool]
) -> list[PreferenceOut]:
    unknown = set(prefs) - set(NOTIFICATION_TYPES)
    if unknown:
        raise AppError(422, "validation_error", f"Unknown notification types: {sorted(unknown)}")
    for type_, enabled in prefs.items():
        row = await db.get(NotificationPreference, (user_id, type_))
        if row is None:
            db.add(NotificationPreference(user_id=user_id, type=type_, enabled=enabled))
        else:
            row.enabled = enabled
    await db.commit()
    return await get_preferences(db, user_id)
