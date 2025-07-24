"""API v1 router aggregation."""

from fastapi import APIRouter
from app.api.v1.endpoints import health, jobs, media

api_router = APIRouter(prefix="/api/v1")

# Include routers
api_router.include_router(health.router, tags=["health"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(media.router, prefix="/media", tags=["media"]) 