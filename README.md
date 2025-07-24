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

## 📋 Table of Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Reference](#api-reference)
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

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_api.py
```

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
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Style

- Use Black for formatting: `black app/`
- Use flake8 for linting: `flake8 app/`
- Use mypy for type checking: `mypy app/`

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- FastAPI for the amazing web framework
- Celery for robust task processing
- Replicate for AI model hosting
- All contributors and maintainers 