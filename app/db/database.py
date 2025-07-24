"""Database connection and session management."""

import asyncio
from typing import AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, text
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global engine instance
_engine: AsyncEngine | None = None
_async_session_maker: async_sessionmaker | None = None
_current_loop_id: int | None = None


def get_engine() -> AsyncEngine:
    """Get or create the async database engine."""
    global _engine, _current_loop_id
    
    # Check if we're in a different event loop
    try:
        current_loop = asyncio.get_running_loop()
        current_loop_id = id(current_loop)
    except RuntimeError:
        current_loop_id = None
    
    # Reset connections if we're in a different event loop
    if _current_loop_id != current_loop_id:
        if _engine is not None:
            # Don't await here as we might not be in an async context
            logger.info("Resetting database engine for new event loop")
        _engine = None
        _current_loop_id = current_loop_id
    
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug and settings.is_development,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout=settings.database_pool_timeout,
            pool_recycle=settings.database_pool_recycle,
            pool_pre_ping=True,
            future=True,
        )
        logger.info("Database engine created", url=settings.database_url)
    return _engine


def get_session_maker() -> async_sessionmaker:
    """Get or create the async session maker."""
    global _async_session_maker
    if _async_session_maker is None:
        engine = get_engine()
        _async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        logger.info("Session maker created")
    return _async_session_maker


async def reset_db_connections() -> None:
    """Reset database connections for a new event loop.
    
    This is useful for Celery tasks that run in new event loops.
    """
    global _engine, _async_session_maker, _current_loop_id
    
    if _engine:
        try:
            await _engine.dispose()
            logger.info("Previous database engine disposed")
        except Exception as e:
            logger.warning("Error disposing previous engine", error=str(e))
    
    _engine = None
    _async_session_maker = None
    _current_loop_id = None
    logger.info("Database connections reset for new event loop")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session.
    
    This is the main dependency for FastAPI endpoints.
    
    Yields:
        AsyncSession: Database session
    """
    async_session_maker = get_session_maker()
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session as a context manager.
    
    Useful for non-FastAPI contexts like background tasks.
    
    Yields:
        AsyncSession: Database session
    """
    async_session_maker = get_session_maker()
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize the database by creating all tables."""
    engine = get_engine()
    async with engine.begin() as conn:
        # Import all models to ensure they're registered
        from app.models import Job, Media  # noqa: F401
        
        await conn.run_sync(SQLModel.metadata.create_all)
        logger.info("Database tables created")


async def close_db() -> None:
    """Close the database engine."""
    global _engine, _async_session_maker
    if _engine:
        await _engine.dispose()
        _engine = None
        _async_session_maker = None
        logger.info("Database engine closed")


async def check_db_connection() -> bool:
    """Check if the database connection is working.
    
    Returns:
        bool: True if connection is successful
    """
    try:
        async with get_db_context() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error("Database connection check failed", error=str(e))
        return False 