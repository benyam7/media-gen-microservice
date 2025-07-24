#!/bin/bash

# Test runner script for media-gen-microservice

# Set test environment variables
export DATABASE_URL="sqlite+aiosqlite:///:memory:"
export REDIS_URL="redis://localhost:6379/15"
export APP_ENV="development"
export STORAGE_TYPE="local"
export STORAGE_LOCAL_PATH="/tmp/test_media"
export REPLICATE_API_TOKEN=""  # Force mock mode
export SECRET_KEY="test-secret-key"

# Create test media directory
mkdir -p /tmp/test_media

# Run tests with coverage
echo "Running tests with coverage..."
pytest "$@" 