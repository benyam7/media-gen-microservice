"""Test configuration and fixtures."""

import asyncio
import os
import tempfile
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel

from app.main import app
from app.core.config import Settings, get_settings
from app.db.database import get_session
from app.models import Job, Media, JobStatus, MediaType
from app.services.storage_service import StorageService
from app.services.replicate_service import ReplicateService
from app.services.job_service import JobService


# Test database URL - using in-memory SQLite for speed
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class TestSettings(Settings):
    """Test-specific settings."""
    
    app_env: str = "development"
    debug: bool = True
    database_url: str = TEST_DATABASE_URL
    redis_url: str = "redis://localhost:6379/15"  # Use different DB for tests
    storage_type: str = "local"
    storage_local_path: str = "/tmp/test_media"
    replicate_api_token: str = ""  # Force mock mode
    secret_key: str = "test-secret-key"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings() -> TestSettings:
    """Get test settings."""
    return TestSettings()


@pytest.fixture
async def engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    yield engine
    
    # Cleanup
    await engine.dispose()


@pytest.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
        await session.rollback()


@pytest.fixture
def override_get_session(db_session):
    """Override database session dependency."""
    async def _get_session():
        yield db_session
    
    app.dependency_overrides[get_session] = _get_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def override_get_settings(test_settings):
    """Override settings dependency."""
    app.dependency_overrides[get_settings] = lambda: test_settings
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def client(override_get_session, override_get_settings) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def mock_storage_service(test_settings, temp_dir):
    """Create mock storage service."""
    # Set temp dir as storage path
    test_settings.storage_local_path = temp_dir
    return StorageService(test_settings)


@pytest.fixture
def mock_replicate_service(test_settings):
    """Create mock Replicate service."""
    return ReplicateService(test_settings)


@pytest.fixture
def job_service(db_session):
    """Create job service."""
    return JobService(db_session)


@pytest.fixture
async def sample_job(db_session) -> Job:
    """Create a sample job for testing."""
    job = Job(
        prompt="A beautiful sunset over mountains",
        parameters={"width": 1024, "height": 1024},
        status=JobStatus.PENDING
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


@pytest.fixture
async def sample_media(db_session, temp_dir) -> Media:
    """Create a sample media record for testing."""
    media = Media(
        type=MediaType.IMAGE,
        storage_path=f"{temp_dir}/test_image.png",
        file_size_bytes=1024,
        mime_type="image/png",
        file_extension=".png",
        width=1024,
        height=1024,
        storage_provider="local"
    )
    db_session.add(media)
    await db_session.commit()
    await db_session.refresh(media)
    return media


@pytest.fixture
async def completed_job_with_media(db_session, sample_media) -> Job:
    """Create a completed job with associated media."""
    job = Job(
        prompt="A beautiful sunset over mountains",
        parameters={"width": 1024, "height": 1024},
        status=JobStatus.COMPLETED,
        media_id=sample_media.id
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


@pytest.fixture
def mock_celery_task():
    """Mock Celery task for testing."""
    mock_task = MagicMock()
    mock_task.apply_async.return_value = MagicMock(id="test-task-id")
    return mock_task


@pytest.fixture
def sample_image_data():
    """Create sample image data for testing."""
    # Create a simple 1x1 PNG image
    import base64
    # 1x1 transparent PNG
    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAGAOH2nfgAAAABJRU5ErkJggg=="
    )
    return png_data


@pytest.fixture
def mock_replicate_output():
    """Mock Replicate API output."""
    return ["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAGAOH2nfgAAAABJRU5ErkJggg=="]


# Test data fixtures
@pytest.fixture
def job_create_data():
    """Sample job creation data."""
    return {
        "prompt": "A beautiful sunset over mountains",
        "parameters": {
            "width": 1024,
            "height": 1024,
            "num_inference_steps": 4
        }
    }


@pytest.fixture
def invalid_job_create_data():
    """Invalid job creation data for testing validation."""
    return {
        "prompt": "",  # Empty prompt should fail
        "parameters": {
            "width": -1,  # Invalid width
            "height": 5000,  # Too large height
        }
    }


# Async fixtures with proper typing
@pytest_asyncio.fixture
async def async_sample_job(db_session) -> Job:
    """Async version of sample_job fixture."""
    job = Job(
        prompt="A beautiful sunset over mountains",
        parameters={"width": 1024, "height": 1024},
        status=JobStatus.PENDING
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


# Cleanup fixtures
@pytest.fixture(autouse=True)
def cleanup_temp_files(temp_dir):
    """Automatically cleanup temporary files after each test."""
    yield
    # Additional cleanup if needed
    import shutil
    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass  # Ignore cleanup errors


# Database cleanup
@pytest.fixture(autouse=True)
async def cleanup_database(db_session):
    """Cleanup database after each test."""
    yield
    # Clear all data - rollback instead of commit to avoid StaleDataError
    try:
        from sqlalchemy import text
        await db_session.execute(text("DELETE FROM jobs"))
        await db_session.execute(text("DELETE FROM media"))
        await db_session.rollback()  # Rollback instead of commit
    except Exception:
        # If cleanup fails, just rollback
        await db_session.rollback() 