import asyncio
import os
import uuid

# Must be set before any `app` import so settings/engine bind to the test database.
TEST_DB = "scoutsphere_test"
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = (
    f"postgresql+asyncpg://scoutsphere:scoutsphere@localhost:5433/{TEST_DB}"
)

import psycopg2  # noqa: E402
import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi import APIRouter, Depends  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from alembic import command  # noqa: E402
from app.api.deps import require_permission  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.organization import Organization, OrganizationMember  # noqa: E402
from app.models.rbac import Role  # noqa: E402
from app.models.user import User  # noqa: E402
from app.permissions import catalog  # noqa: E402
from app.permissions.context import AuthContext  # noqa: E402
from app.permissions.sync import sync_rbac  # noqa: E402

PASSWORD = "correct-horse-battery"

# Routes that exist only in tests, to exercise the permission dependencies directly.
_test_router = APIRouter(prefix="/_test")


@_test_router.get("/org-read")
async def _org_read(ctx: AuthContext = Depends(require_permission(catalog.ORG_READ))):
    return {"org": str(ctx.organization_id), "role": ctx.org_role}


@_test_router.get("/members-manage")
async def _members(ctx: AuthContext = Depends(require_permission(catalog.MEMBERS_MANAGE))):
    return {"ok": True}


@_test_router.get("/platform-audit")
async def _audit(ctx: AuthContext = Depends(require_permission(catalog.PLATFORM_AUDIT_READ))):
    return {"ok": True}


app.include_router(_test_router)


def _admin_conn():
    conn = psycopg2.connect(
        host="localhost", port=5433, user="scoutsphere", password="scoutsphere", dbname="postgres"
    )
    conn.autocommit = True
    return conn


@pytest.fixture(scope="session", autouse=True)
def _database():
    conn = _admin_conn()
    cur = conn.cursor()
    cur.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
    cur.execute(f"CREATE DATABASE {TEST_DB}")
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")  # also proves the migrations apply from scratch

    async def _seed():
        async with SessionLocal() as db:
            await sync_rbac(db)

    asyncio.run(_seed())
    yield
    cur.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
    conn.close()


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    conn = psycopg2.connect(
        host="localhost", port=5433, user="scoutsphere", password="scoutsphere", dbname=TEST_DB
    )
    conn.autocommit = True
    conn.cursor().execute(
        "TRUNCATE audit_logs, user_sessions, organization_members, organizations, users CASCADE"
    )
    conn.close()


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ---- factories --------------------------------------------------------------------
async def make_user(email: str, *, platform_role: str | None = None, active: bool = True) -> User:
    async with SessionLocal() as db:
        user = User(
            email=email,
            password_hash=hash_password(PASSWORD),
            full_name=email.split("@")[0],
            platform_role=platform_role,
            is_active=active,
        )
        db.add(user)
        await db.commit()
        return user


async def make_org(name: str, status: str = "active") -> Organization:
    async with SessionLocal() as db:
        org = Organization(name=name, slug=f"{name.lower()}-{uuid.uuid4().hex[:6]}", status=status)
        db.add(org)
        await db.commit()
        return org


async def add_member(user: User, org: Organization, role_key: str, status: str = "active"):
    async with SessionLocal() as db:
        role = await db.scalar(select(Role).where(Role.key == role_key))
        db.add(
            OrganizationMember(
                organization_id=org.id, user_id=user.id, role_id=role.id, status=status
            )
        )
        await db.commit()


async def login(client: AsyncClient, email: str) -> str:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def bearer(token: str, org: Organization | None = None) -> dict:
    h = {"Authorization": f"Bearer {token}"}
    if org is not None:
        h["X-Organization-Id"] = str(org.id)
    return h
