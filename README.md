# Media Generation Microservice

A production-grade asynchronous microservice for AI-powered media generation using the Replicate API. Built with FastAPI, Celery, and modern Python best practices.

## 🚀 Features

- **Asynchronous Processing**: Non-blocking API with background job processing using Celery
- **Scalable Architecture**: Horizontally scalable workers and API instances
- **Retry Logic**: Automatic retries with exponential backoff for failed jobs
- **Multiple Storage Options**: Support for S3-compatible storage (MinIO/AWS S3) and local filesystem
- **Production Ready**: Docker support, health checks, monitoring, and comprehensive error handling
- **Type Safety**: Full type hints with Pydantic models and SQLModel ORM
- **API Documentation**: Auto-generated OpenAPI/Swagger documentation
- **Database Migrations**: Version-controlled database schema with Alembic
- **Structured Logging**: JSON-formatted logs with request tracking
- **Monitoring**: Prometheus metrics and Celery Flower dashboard
- **Comprehensive Test Suite**: 146+ tests with 78%+ code coverage, including unit, integration, and API tests
- **Developer Documentation**: Detailed API examples and testing guides

## 📋 Table of Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Documentation](#documentation)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
- [Monitoring](#monitoring)
- [Contributing](#contributing)

## 🏗️ Architecture

### System Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  FastAPI    │────▶│   Celery    │
└─────────────┘     └─────────────┘     └─────────────┘
                           │                     │
                           ▼                     ▼
                    ┌─────────────┐     ┌─────────────┐
                    │  PostgreSQL │     │ Replicate   │
                    └─────────────┘     │    API      │
                           │            └─────────────┘
                           ▼                     │
                    ┌─────────────┐              ▼
                    │Redis/Celery │     ┌─────────────┐
                    └─────────────┘     │  S3/MinIO   │
                                       └─────────────┘
```

### Key Components

1. **API Layer (FastAPI)**
   - Handles HTTP requests
   - Validates input data
   - Enqueues jobs to Celery
   - Returns job status

2. **Task Queue (Celery + Redis)**
   - Processes media generation jobs asynchronously
   - Implements retry logic
   - Handles job lifecycle

3. **Database (PostgreSQL)**
   - Stores job metadata
   - Tracks job status
   - Maintains media records

4. **Storage (S3/MinIO/Local)**
   - Stores generated media files
   - Provides public URLs for access

5. **External API (Replicate)**
   - Performs actual AI media generation
   - Supports various models

### Project Structure

```
media-gen-microservice/
├── app/
│   ├── api/               # API endpoints
│   │   └── v1/
│   │       └── endpoints/
│   ├── core/              # Core configuration
│   │   ├── config.py      # Settings management
│   │   └── logging.py     # Logging setup
│   ├── db/                # Database connection
│   ├── models/            # SQLModel models
│   ├── schemas/           # Pydantic schemas
│   ├── services/          # Business logic
│   │   ├── job_service.py
│   │   ├── storage_service.py
│   │   └── replicate_service.py
│   ├── workers/           # Celery tasks
│   │   ├── celery_app.py
│   │   └── tasks.py
│   └── main.py            # FastAPI application
├── alembic/               # Database migrations
├── tests/                 # Test suite
├── infrastructure/        # Deployment configs
├── docker-compose.yml     # Development stack
├── Dockerfile             # API container
├── Dockerfile.worker      # Worker container
└── requirements.txt       # Python dependencies
```

## 🔧 Prerequisites

- Python 3.11+
- Docker and Docker Compose
- PostgreSQL (or use Docker)
- Redis (or use Docker)
- S3-compatible storage (or use MinIO in Docker)

## 🚀 Quick Start

### Using Docker Compose (Recommended)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd media-gen-microservice
   ```

2. **Copy environment variables**
   ```bash
   cp env.example .env
   # Edit .env with your configuration
   ```

3. **Start the services**
   ```bash
   docker compose up -d
   ```

4. **Run database migrations**
   ```bash
   docker compose exec api alembic upgrade head
   ```

5. **Access the services**
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - MinIO Console: http://localhost:9001 (minioadmin/minioadmin)
   - Flower (Celery): http://localhost:5555

### Local Development Setup

1. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp env.example .env
   # Edit .env with your configuration
   ```

4. **Start infrastructure services**
   ```bash
   docker compose up -d postgres redis minio
   ```

5. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

6. **Start the API server**
   ```bash
   uvicorn app.main:app --reload
   ```

7. **Start Celery worker**
   ```bash
   celery -A app.workers.celery_app worker --loglevel=info
   ```

8. **Start Celery beat (optional, for periodic tasks)**
   ```bash
   celery -A app.workers.celery_app beat --loglevel=info
   ```

## ⚙️ Configuration

### Environment Variables

Key configuration options in `.env`:

```env
# Application
APP_ENV=development
DEBUG=true
SECRET_KEY=your-secret-key

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Replicate API
REPLICATE_API_TOKEN=your-replicate-token
REPLICATE_MODEL=stability-ai/sdxl:model-version

# Storage
STORAGE_TYPE=s3  # or 'local'
S3_ENDPOINT_URL=http://localhost:9000  # MinIO
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
S3_BUCKET_NAME=media-generation
```

## 📡 API Reference

### Create Media Generation Job

```http
POST /api/v1/jobs/generate
Content-Type: application/json

{
  "prompt": "A beautiful sunset over mountains",
  "parameters": {
    "width": 1024,
    "height": 1024,
    "num_inference_steps": 50,
    "guidance_scale": 7.5
  }
}
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "created_at": "2024-01-01T00:00:00Z",
  "status_url": "/api/v1/jobs/status/550e8400-e29b-41d4-a716-446655440000",
  "estimated_completion_time": 300
}
```

### Check Job Status

```http
GET /api/v1/jobs/status/{job_id}
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "prompt": "A beautiful sunset over mountains",
  "created_at": "2024-01-01T00:00:00Z",
  "completed_at": "2024-01-01T00:05:00Z",
  "media": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440000",
      "url": "https://storage.example.com/media/generated.png",
      "type": "image",
      "width": 1024,
      "height": 1024
    }
  ]
}
```

### List Jobs

```http
GET /api/v1/jobs?page=1&per_page=20&status=completed
```

### Get Media

```http
GET /api/v1/media/{media_id}
```

### Health Check

```http
GET /api/v1/health
```

## 📚 Documentation

### Available Documentation

- **[API Examples](docs/API_EXAMPLES.md)**: Comprehensive API usage examples with curl, Python, and JavaScript
- **[Testing Guide](docs/TESTING.md)**: Detailed testing documentation, fixtures, and best practices
- **[OpenAPI/Swagger](http://localhost:8000/docs)**: Interactive API documentation (when running locally)
- **[ReDoc](http://localhost:8000/redoc)**: Alternative API documentation interface

### Quick Links

- **API Examples**: Full request/response examples for all endpoints
- **Webhook Integration**: Examples for implementing webhook handlers
- **Error Handling**: Common error scenarios and handling strategies
- **Rate Limiting**: Guidelines for API usage limits
- **Best Practices**: Recommended patterns for production use

## 🔧 Development

### Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/media-gen-microservice.git
   cd media-gen-microservice
   ```

2. **Set up Python environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp env.example .env
   # Edit .env with your configuration
   ```

4. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

5. **Start development servers**
   ```bash
   # Terminal 1: Start API server
   make run

   # Terminal 2: Start Celery worker
   make worker

   # Terminal 3: Start Celery Flower (optional)
   make flower
   ```

### Useful Make Commands

```bash
make help          # Show all available commands
make install       # Install dependencies
make run           # Run API server
make worker        # Run Celery worker
make flower        # Run Celery Flower dashboard
make migrate       # Run database migrations
make migration     # Create new migration
make shell         # Open Python shell with app context
make clean         # Clean up cache files
make format        # Format code with Black
make lint          # Run linting checks
make type-check    # Run type checking
make test          # Run all tests
make test-fast     # Run tests without slow tests
```

## 🧪 Testing

The project includes a comprehensive test suite with 146+ tests covering all major components.

### Test Coverage

- **Current Coverage**: 78.9%
- **Test Categories**: Unit tests, Integration tests, API tests, Service tests, Worker tests

### Running Tests

```bash
# Run all tests with coverage
make test

# Run tests without slow tests (faster feedback)
make test-fast

# Run tests in parallel
make test-parallel

# Run specific test categories
make test-unit        # Unit tests only
make test-integration # Integration tests only
make test-api        # API endpoint tests only
make test-service    # Service layer tests only
make test-worker     # Worker/task tests only

# Generate coverage report
make test-cov

# Run tests with coverage threshold check
make test-cov-fail
```

### Test Structure

```
tests/
├── conftest.py          # Shared fixtures and configuration
├── utils.py             # Test utilities and helpers
├── test_*.py           # Root level tests
├── api/                # API endpoint tests
│   ├── test_jobs.py
│   ├── test_media.py
│   └── test_health.py
├── services/           # Service layer tests
│   ├── test_job_service.py
│   ├── test_storage_service.py
│   └── test_replicate_service.py
└── workers/            # Celery worker tests
    └── test_tasks.py
```

### Test Features

- **Async Support**: Full async/await test support with pytest-asyncio
- **Fixtures**: Comprehensive fixtures for database, storage, and service mocking
- **In-Memory Database**: SQLite for fast test execution
- **Mock Services**: Mock Replicate API for testing without API calls
- **Test Markers**: Organize tests with markers (slow, unit, integration, etc.)
- **Parallel Execution**: Run tests in parallel with pytest-xdist

For detailed testing documentation, see [docs/TESTING.md](docs/TESTING.md).

## 🚢 Deployment

### Production Deployment with Docker

1. **Build production images**
   ```bash
   docker build -t media-gen-api:latest .
   docker build -t media-gen-worker:latest -f Dockerfile.worker .
   ```

2. **Use production docker compose**
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

### Kubernetes Deployment

Kubernetes manifests are provided in `infrastructure/k8s/`:

```bash
kubectl apply -f infrastructure/k8s/
```

### Environment-Specific Configurations

- **Development**: Uses mock Replicate service if no API token is provided
- **Staging**: Full functionality with test API tokens
- **Production**: Full functionality with production tokens and external services

## 📊 Monitoring

### Metrics

Prometheus metrics are exposed at `/metrics`:
- Request count and latency
- Job processing metrics
- Queue length and worker status

### Logging

Structured JSON logs are available with:
- Request ID tracking
- Error context
- Performance metrics

### Celery Monitoring

Access Flower dashboard at http://localhost:5555 for:
- Worker status
- Task history
- Queue monitoring
- Real-time statistics

## 🛠️ Maintenance

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Backup and Restore

```bash
# Backup database
docker compose exec postgres pg_dump -U postgres media_gen_db > backup.sql

# Restore database
docker compose exec -T postgres psql -U postgres media_gen_db < backup.sql
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for your changes
4. Ensure all tests pass (`make test`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Development Guidelines

- **Code Style**: Use Black for formatting (`black app/`)
- **Linting**: Use flake8 for linting (`flake8 app/`)
- **Type Checking**: Use mypy for type checking (`mypy app/`)
- **Testing**: Write tests for new features and ensure 78%+ coverage
- **Documentation**: Update documentation for API changes

### Pre-commit Checklist

- [ ] All tests pass (`make test`)
- [ ] Code is formatted (`black app/`)
- [ ] No linting errors (`flake8 app/`)
- [ ] Type hints are correct (`mypy app/`)
- [ ] Documentation is updated
- [ ] Commit messages are descriptive

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- FastAPI for the amazing web framework
- Celery for robust task processing
- Replicate for AI model hosting
- All contributors and maintainers 