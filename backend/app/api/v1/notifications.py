import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import Page, PageParams
from app.schemas.notifications import (
    NotificationOut,
    PreferenceOut,
    PreferencesUpdate,
    UnreadCount,
)
from app.services import notifications

router = APIRouter(prefix="/notifications", tags=["notifications"])
# Notifications belong to the user, not an organization, so only authentication is needed.


@router.get("", response_model=Page[NotificationOut])
async def list_notifications(
    unread: bool = False,
    page: PageParams = Depends(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await notifications.list_notifications(db, user.id, page, unread)


@router.get("/unread-count", response_model=UnreadCount)
async def unread_count(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return UnreadCount(unread=await notifications.unread_count(db, user.id))


@router.post("/read-all", status_code=204)
async def read_all(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await notifications.mark_all_read(db, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/preferences", response_model=list[PreferenceOut])
async def get_preferences(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await notifications.get_preferences(db, user.id)


@router.put("/preferences", response_model=list[PreferenceOut])
async def put_preferences(
    body: PreferencesUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await notifications.update_preferences(db, user.id, body.preferences)


@router.post("/{notification_id}/read", status_code=204)
async def read_one(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await notifications.mark_read(db, user.id, notification_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
