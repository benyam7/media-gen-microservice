.PHONY: help install run test lint format clean docker-up docker-down migrate

help:
	@echo "Available commands:"
	@echo "  make install        - Install dependencies"
	@echo "  make run            - Run the application locally"
	@echo "  make worker         - Run Celery worker"
	@echo "  make beat           - Run Celery beat scheduler"
	@echo ""
	@echo "Testing:"
	@echo "  make test           - Run all tests"
	@echo "  make test-unit      - Run unit tests only"
	@echo "  make test-integration - Run integration tests only"
	@echo "  make test-api       - Run API tests only"
	@echo "  make test-service   - Run service tests only"
	@echo "  make test-worker    - Run worker tests only"
	@echo "  make test-cov       - Run tests with coverage report"
	@echo "  make test-cov-fail  - Run tests with coverage and fail if below 80%"
	@echo "  make test-fast      - Run tests excluding slow ones"
	@echo "  make test-parallel  - Run tests in parallel"
	@echo "  make test-watch     - Run tests in watch mode"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint           - Run linting (flake8, mypy)"
	@echo "  make format         - Format code with black and isort"
	@echo "  make clean          - Clean up cache files"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up      - Start Docker services"
	@echo "  make docker-down    - Stop Docker services"
	@echo "  make docker-build   - Build Docker images"
	@echo ""
	@echo "Database:"
	@echo "  make migrate        - Run database migrations"
	@echo "  make migration      - Create new migration"

install:
	pip install -r requirements.txt

run:
	uvicorn app.main:app --reload

worker:
	celery -A app.workers.celery_app worker --loglevel=info

beat:
	celery -A app.workers.celery_app beat --loglevel=info

test:
	./scripts/test.sh

test-unit:
	./scripts/test.sh -m unit

test-integration:
	./scripts/test.sh -m integration

test-api:
	./scripts/test.sh -m api

test-service:
	./scripts/test.sh -m service

test-worker:
	./scripts/test.sh -m worker

test-cov:
	./scripts/test.sh --cov=app --cov-report=html --cov-report=term-missing

test-cov-fail:
	./scripts/test.sh --cov-fail-under=78

test-fast:
	./scripts/test.sh -m "not slow" --maxfail=1

test-parallel:
	./scripts/test.sh -n auto

test-watch:
	ptw -- -m "not slow"

lint:
	flake8 app/
	mypy app/

format:
	black app/
	isort app/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-build:
	docker compose build

migrate:
	alembic upgrade head

migration:
	@read -p "Enter migration message: " msg; \
	alembic revision --autogenerate -m "$$msg" 