# Testing Documentation

This document provides comprehensive information about testing the Media Generation Microservice.

## Table of Contents

- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Test Configuration](#test-configuration)
- [Writing Tests](#writing-tests)
- [Test Coverage](#test-coverage)
- [Continuous Integration](#continuous-integration)
- [Performance Testing](#performance-testing)
- [Troubleshooting](#troubleshooting)

## Test Structure

The test suite is organized into several categories:

```
tests/
├── conftest.py              # Test configuration and fixtures
├── utils.py                 # Test utilities and helpers
├── test_health.py           # Basic health tests
├── test_integration.py      # Integration tests
├── api/                     # API endpoint tests
│   ├── test_jobs.py        # Job management tests
│   └── test_media.py       # Media handling tests
├── services/                # Service layer tests
│   ├── test_job_service.py     # Job service tests
│   ├── test_storage_service.py # Storage service tests
│   └── test_replicate_service.py # Replicate service tests
└── workers/                 # Worker and task tests
    └── test_tasks.py       # Celery task tests
```

### Test Categories

#### Unit Tests (`@pytest.mark.unit`)
- Test individual functions and methods in isolation
- Fast execution (<1 second per test)
- Mock all external dependencies

#### Integration Tests (`@pytest.mark.integration`)
- Test interactions between components
- Use real database but mock external APIs
- Moderate execution time (1-10 seconds)

#### API Tests (`@pytest.mark.api`)
- Test HTTP endpoints end-to-end
- Use test client with real request/response cycle
- Include validation and error handling

#### Service Tests (`@pytest.mark.service`)
- Test business logic in service layer
- Mock database and external dependencies
- Focus on business rules and workflows

#### Worker Tests (`@pytest.mark.worker`)
- Test Celery tasks and async operations
- Mock external APIs and storage
- Test retry logic and error handling

## Running Tests

### Basic Test Execution

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/api/test_jobs.py

# Run specific test class
pytest tests/api/test_jobs.py::TestJobCreation

# Run specific test method
pytest tests/api/test_jobs.py::TestJobCreation::test_create_job_success
```

### Running by Test Category

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run API tests
pytest -m api

# Run service tests
pytest -m service

# Run worker tests
pytest -m worker

# Exclude slow tests
pytest -m "not slow"
```

### Parallel Execution

```bash
# Run tests in parallel (requires pytest-xdist)
pytest -n auto

# Run with specific number of workers
pytest -n 4
```

### Test Coverage

```bash
# Run tests with coverage
pytest --cov=app

# Generate HTML coverage report
pytest --cov=app --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Development Testing

```bash
# Run tests and stop on first failure
pytest -x

# Run tests that failed in last run
pytest --lf

# Run tests that failed or changed files
pytest --ff

# Run tests in loop (for development)
pytest --looponfail
```

## Test Configuration

### pytest.ini Configuration

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --strict-markers
    --tb=short
    --disable-warnings
    --cov=app
    --cov-report=html:htmlcov
    --cov-report=term-missing
    --cov-fail-under=80
    --durations=10
asyncio_mode = auto
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    unit: marks tests as unit tests
    api: marks tests as API tests
    worker: marks tests as worker/task tests
    service: marks tests as service layer tests
```

### Environment Variables for Testing

```bash
# Test database (uses SQLite in-memory by default)
TEST_DATABASE_URL=sqlite+aiosqlite:///:memory:

# Test Redis (separate DB from development)
TEST_REDIS_URL=redis://localhost:6379/15

# Force mock mode for external APIs
REPLICATE_API_TOKEN=""
STORAGE_TYPE=local
```

### Test Settings

Tests use a separate `TestSettings` class that overrides production settings:

```python
class TestSettings(Settings):
    app_env: str = "testing"
    debug: bool = True
    database_url: str = "sqlite+aiosqlite:///:memory:"
    redis_url: str = "redis://localhost:6379/15"
    storage_type: str = "local"
    replicate_api_token: str = ""  # Force mock mode
    secret_key: str = "test-secret-key"
```

## Writing Tests

### Test Fixtures

The test suite provides comprehensive fixtures in `conftest.py`:

```python
# Database fixtures
@pytest.fixture
async def db_session() -> AsyncSession:
    """Database session for tests."""

@pytest.fixture
async def sample_job(db_session) -> Job:
    """Sample job for testing."""

@pytest.fixture  
async def sample_media(db_session) -> Media:
    """Sample media record for testing."""

# Service fixtures
@pytest.fixture
def job_service(db_session) -> JobService:
    """Job service instance."""

@pytest.fixture
def mock_storage_service(test_settings, temp_dir) -> StorageService:
    """Mock storage service."""

# Client fixtures
@pytest.fixture
async def client() -> AsyncClient:
    """HTTP test client."""

# Data fixtures
@pytest.fixture
def job_create_data() -> Dict[str, Any]:
    """Sample job creation data."""

@pytest.fixture
def sample_image_data() -> bytes:
    """Sample image data for testing."""
```

### Writing API Tests

```python
class TestJobCreation:
    """Test job creation endpoint."""
    
    async def test_create_job_success(self, client: AsyncClient, job_create_data, mock_celery_task):
        """Test successful job creation."""
        with patch('app.api.v1.endpoints.jobs.generate_media_task', mock_celery_task):
            response = await client.post("/api/v1/jobs/generate", json=job_create_data)
        
        assert response.status_code == 201
        data = response.json()
        
        # Check response structure
        assert "id" in data
        assert data["status"] == "pending"
        assert "created_at" in data
        
        # Verify Celery task was called
        mock_celery_task.apply_async.assert_called_once()
```

### Writing Service Tests

```python
class TestJobService:
    """Test job service functionality."""
    
    async def test_create_job(self, job_service: JobService):
        """Test job creation."""
        job = await job_service.create_job(
            prompt="Test prompt",
            parameters={"width": 1024, "height": 1024}
        )
        
        assert job.id is not None
        assert job.prompt == "Test prompt"
        assert job.status == JobStatus.PENDING
```

### Writing Worker Tests

```python
class TestMediaGeneration:
    """Test media generation task."""
    
    async def test_generate_media_success(self, sample_job):
        """Test successful media generation."""
        with patch('app.workers.tasks.ReplicateService') as mock_replicate:
            mock_replicate.return_value.generate_media.return_value = ["http://example.com/image.png"]
            
            result = await generate_media_task(str(sample_job.id))
            
            assert result["status"] == "completed"
```

### Test Utilities

Use the provided test utilities for common operations:

```python
from tests.utils import (
    TestDataFactory, 
    ImageTestUtils, 
    APITestUtils,
    DatabaseTestUtils
)

# Create test data
job_data = TestDataFactory.create_job_data(
    prompt="Test prompt",
    parameters=TestDataFactory.create_flux_parameters()
)

# Create test images
test_image = ImageTestUtils.create_test_image(1024, 1024, "blue")
data_url = ImageTestUtils.create_data_url()

# Validate API responses
APITestUtils.assert_job_response_structure(response_data)
APITestUtils.assert_pagination_structure(list_response)

# Database operations
test_job = await DatabaseTestUtils.create_test_job(db_session)
test_media = await DatabaseTestUtils.create_test_media(db_session, "/path/to/file")
```

### Mocking External Dependencies

```python
# Mock Replicate API
with patch('app.services.replicate_service.replicate.run') as mock_run:
    mock_run.return_value = ["https://example.com/image.png"]
    # Your test code here

# Mock storage operations
with patch('app.services.storage_service.aioboto3.Session') as mock_session:
    mock_s3_client = AsyncMock()
    mock_session.return_value.client.return_value.__aenter__.return_value = mock_s3_client
    # Your test code here

# Mock Celery tasks
with patch('app.api.v1.endpoints.jobs.generate_media_task') as mock_task:
    mock_task.apply_async.return_value.id = "test-task-id"
    # Your test code here
```

## Test Coverage

### Coverage Requirements

The project maintains a minimum test coverage of 80%. Coverage is measured across:

- Line coverage: Percentage of code lines executed
- Branch coverage: Percentage of conditional branches tested
- Function coverage: Percentage of functions called

### Viewing Coverage Reports

```bash
# Generate coverage report
pytest --cov=app --cov-report=html

# View in browser
open htmlcov/index.html

# Terminal report
pytest --cov=app --cov-report=term-missing
```

### Excluded from Coverage

Some files are excluded from coverage requirements:

- Migration files (`alembic/versions/*.py`)
- Configuration files (`app/core/config.py`)
- Test files themselves
- Development scripts

## Continuous Integration

### GitHub Actions Workflow

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        pytest --cov=app --cov-report=xml
      env:
        DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/test_db
        REDIS_URL: redis://localhost:6379/15
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: tests
        name: tests
        entry: pytest
        language: system
        types: [python]
        pass_filenames: false
        always_run: true
      
      - id: test-coverage
        name: test-coverage
        entry: pytest --cov=app --cov-fail-under=80
        language: system
        types: [python]
        pass_filenames: false
        always_run: true
```

## Performance Testing

### Load Testing with pytest-benchmark

```python
import pytest

def test_job_creation_performance(benchmark, client, job_create_data):
    """Benchmark job creation endpoint."""
    
    def create_job():
        return client.post("/api/v1/jobs/generate", json=job_create_data)
    
    result = benchmark(create_job)
    assert result.status_code == 201

# Run performance tests
pytest --benchmark-only
```

### Stress Testing

```python
import asyncio
import pytest

@pytest.mark.slow
async def test_concurrent_job_creation(client):
    """Test handling of concurrent job requests."""
    
    async def create_job(i):
        return await client.post("/api/v1/jobs/generate", json={
            "prompt": f"Test job {i}",
            "parameters": {"width": 512, "height": 512}
        })
    
    # Create 50 concurrent jobs
    tasks = [create_job(i) for i in range(50)]
    responses = await asyncio.gather(*tasks)
    
    # All should succeed
    for response in responses:
        assert response.status_code == 201
```

## Troubleshooting

### Common Test Failures

#### Database Connection Issues

```bash
# Error: database connection failed
# Solution: Ensure PostgreSQL is running
docker compose up -d postgres

# Or use in-memory SQLite (default for tests)
export TEST_DATABASE_URL="sqlite+aiosqlite:///:memory:"
```

#### Redis Connection Issues

```bash
# Error: Redis connection refused
# Solution: Start Redis or use fake Redis
docker compose up -d redis

# Or use fakeredis for testing
pip install fakeredis
```

#### Import Errors

```bash
# Error: ModuleNotFoundError
# Solution: Install in development mode
pip install -e .

# Or add to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

#### Async Test Issues

```bash
# Error: RuntimeError: no running event loop
# Solution: Use pytest-asyncio fixtures
@pytest.mark.asyncio
async def test_async_function():
    # Your async test code
```

### Debugging Test Failures

```bash
# Run with detailed output
pytest -vvv

# Run with Python debugger
pytest --pdb

# Run with custom markers for debugging
pytest -m "debug"

# Show local variables in tracebacks
pytest --tb=long

# Run single test with maximum verbosity
pytest -vvv tests/api/test_jobs.py::test_create_job_success
```

### Test Data Cleanup

```bash
# Clear test database
docker compose exec postgres psql -U postgres -d test_db -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# Clear Redis test data
docker compose exec redis redis-cli -n 15 FLUSHDB

# Clean temporary files
find /tmp -name "test_*" -delete
```

### Memory and Performance Issues

```bash
# Run tests with memory profiling
pytest --profile

# Limit parallel workers if running out of memory
pytest -n 2  # Instead of -n auto

# Run subset of tests for quick feedback
pytest tests/api/ -k "not slow"
```

## Best Practices

### Test Naming

- Use descriptive test names that explain what is being tested
- Follow pattern: `test_{what}_{condition}_{expected_result}`
- Examples: `test_create_job_with_valid_data_returns_201`

### Test Organization

- Group related tests in classes
- Use meaningful class names: `TestJobCreation`, `TestErrorHandling`
- Keep tests focused and testing one thing at a time

### Fixtures and Data

- Use fixtures for common test data
- Prefer factory patterns over fixed data
- Clean up resources in fixture teardown

### Mocking

- Mock external dependencies (APIs, file systems, networks)
- Don't mock the code under test
- Use appropriate mock types (Mock, MagicMock, AsyncMock)

### Assertions

- Use specific assertions (`assert x == 5` vs `assert x`)
- Include helpful error messages
- Test both positive and negative cases

### Test Independence

- Tests should not depend on other tests
- Use fresh data for each test
- Clean up state after each test 