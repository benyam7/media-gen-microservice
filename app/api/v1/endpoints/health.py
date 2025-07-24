"""Health check endpoint."""

from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
from app.core.config import get_settings
from app.db.database import get_session, check_db_connection
from app.schemas.common import HealthResponse
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint to verify service status."""
    settings = get_settings()
    services = {}
    
    # Check database connection
    try:
        db_healthy = await check_db_connection()
        services["database"] = db_healthy
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        services["database"] = False
    
    # Check Redis connection
    try:
        redis_client = redis.from_url(settings.redis_url)
        await redis_client.ping()
        services["redis"] = True
        await redis_client.close()
    except Exception as e:
        logger.error("Redis health check failed", error=str(e))
        services["redis"] = False
    
    # Overall status
    all_healthy = all(services.values())
    
    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        version="1.0.0",
        environment=settings.app_env,
        services=services,
        timestamp=datetime.utcnow().isoformat()
    )


@router.get("/health/live")
async def liveness_check() -> dict:
    """Kubernetes liveness probe endpoint."""
    return {"status": "alive"}


@router.get("/health/ready", response_model=HealthResponse)
async def readiness_check() -> HealthResponse:
    """Kubernetes readiness probe endpoint."""
    return await health_check() 