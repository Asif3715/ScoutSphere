import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.schemas.base import RequestModel

# Passwords are never trimmed: a password with leading/trailing spaces must stay as typed.
NewPassword = Annotated[
    str, StringConstraints(strip_whitespace=False, min_length=10, max_length=128)
]
LoginPassword = Annotated[
    str, StringConstraints(strip_whitespace=False, min_length=1, max_length=128)
]


class RegisterRequest(RequestModel):
    email: EmailStr
    password: NewPassword
    full_name: str = Field(min_length=1, max_length=200)
    # Platform staff roles can never be self-assigned.
    account_type: Literal["standard", "player", "agent"] = "standard"


class LoginRequest(RequestModel):
    email: EmailStr
    password: LoginPassword


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    account_type: str
    platform_role: str | None
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserOut


class MembershipOut(BaseModel):
    organization_id: uuid.UUID
    organization_name: str
    role: str
    permissions: list[str]


class MeResponse(BaseModel):
    user: UserOut
    memberships: list[MembershipOut]
