import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.base import RequestModel


class OrganizationCreate(RequestModel):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class OrganizationUpdate(RequestModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class OrganizationStatusUpdate(RequestModel):
    status: Literal["active", "suspended", "deactivated"]


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    status: str
    created_at: datetime


class MemberOut(BaseModel):
    id: uuid.UUID  # membership id
    user_id: uuid.UUID
    email: str
    full_name: str
    role: str
    status: str
    joined_at: datetime


class MemberUpdate(RequestModel):
    role: str


class InvitationCreate(RequestModel):
    email: EmailStr
    role: str


class InvitationOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime
    # Only populated in local/test environments, where email delivery is stubbed.
    accept_url: str | None = None


class InvitationAccept(RequestModel):
    token: str = Field(min_length=10, max_length=200)


class InvitationPreview(BaseModel):
    organization_name: str
    email: str
    role: str


class DashboardOut(BaseModel):
    organization: OrganizationOut
    clubs: int
    members: int
    pending_invitations: int
