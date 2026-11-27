from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestGuardMiddleware, SecurityHeadersMiddleware
from app.core.security import DEV_ENVIRONMENTS, assert_secure_config
from app.db.session import SessionLocal
from app.permissions.sync import sync_rbac


@asynccontextmanager
async def lifespan(_: FastAPI):
    assert_secure_config()
    async with SessionLocal() as db:
        await sync_rbac(db)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.debug)
    app = FastAPI(
        lifespan=lifespan,
        title=settings.app_name,
        version=settings.version,
        openapi_url="/api/v1/openapi.json",
    )
    app.add_middleware(RequestGuardMiddleware)
    # HSTS everywhere except a developer machine (which has no HTTPS).
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.environment not in DEV_ENVIRONMENTS)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Organization-Id"],
        expose_headers=["Retry-After"],
    )
    register_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
