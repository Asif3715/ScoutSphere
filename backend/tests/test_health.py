import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_liveness(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_readiness_reports_dependencies(client):
    """Requires the compose postgres and redis to be running."""
    r = await client.get("/api/v1/health/ready")
    assert r.status_code == 200, r.text
    assert r.json()["checks"] == {"postgres": "ok", "redis": "ok"}


async def test_openapi_available(client):
    r = await client.get("/api/v1/openapi.json")
    assert r.status_code == 200
