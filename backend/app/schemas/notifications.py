import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.base import RequestModel


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    body: str | None
    link_path: str | None
    organization_id: uuid.UUID | None
    read: bool
    created_at: datetime


class PreferenceOut(BaseModel):
    type: str
    enabled: bool


class PreferencesUpdate(RequestModel):
    preferences: dict[str, bool]


class UnreadCount(BaseModel):
    unread: int
