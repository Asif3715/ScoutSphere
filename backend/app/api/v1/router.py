from fastapi import APIRouter

from app.api.v1 import (
    assignments,
    auth,
    clubs,
    competitions,
    health,
    matches,
    notifications,
    organizations,
    platform,
    players,
    reports,
    scouts,
    teams,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(clubs.router)
api_router.include_router(platform.router)
api_router.include_router(players.router)
api_router.include_router(teams.router)
api_router.include_router(scouts.router)
api_router.include_router(competitions.router)
api_router.include_router(matches.router)
api_router.include_router(notifications.router)
api_router.include_router(assignments.router)
api_router.include_router(reports.router)
