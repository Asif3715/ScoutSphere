import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.base import RequestModel


class ClubBase(RequestModel):
    name: str = Field(min_length=1, max_length=200)
    short_name: str | None = Field(default=None, max_length=50)
    country: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=4000)
    founded_year: int | None = Field(default=None, ge=1800, le=2100)
    logo_url: str | None = Field(default=None, max_length=500)
    website: str | None = Field(default=None, max_length=300)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=50)


class ClubCreate(ClubBase):
    pass


class ClubUpdate(RequestModel):
    """All fields optional; only sent fields are changed."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    short_name: str | None = Field(default=None, max_length=50)
    country: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=4000)
    founded_year: int | None = Field(default=None, ge=1800, le=2100)
    logo_url: str | None = Field(default=None, max_length=500)
    website: str | None = Field(default=None, max_length=300)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=50)


class ClubOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID | None
    is_reference: bool = False
    name: str
    short_name: str | None
    country: str | None
    city: str | None
    description: str | None
    founded_year: int | None
    logo_url: str | None
    website: str | None
    contact_email: str | None
    contact_phone: str | None
    created_at: datetime
