from fastapi import APIRouter

from app.api.v1 import auth, clubs, health, organizations, platform

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(clubs.router)
api_router.include_router(platform.router)
