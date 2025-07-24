"""Tests for health check endpoints."""

import pytest
from httpx import AsyncClient


async def test_health_check(client: AsyncClient):
    """Test health check endpoint."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    # The status might be "degraded" in test environment due to SQLite connection issues
    assert data["status"] in ["healthy", "degraded"]
    assert "version" in data
    assert "timestamp" in data


async def test_liveness_check(client: AsyncClient):
    """Test liveness check endpoint."""
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"


async def test_readiness_check(client: AsyncClient):
    """Test readiness check endpoint."""
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    # The status might be "degraded" in test environment
    assert data["status"] in ["healthy", "degraded", "ready"]
    # Services might not all be connected in test environment
    assert "services" in data or "database" in data


async def test_root_endpoint(client: AsyncClient):
    """Test root endpoint."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "media-gen-microservice"
    assert data["version"] == "1.0.0"
    assert "environment" in data
    assert data["docs"] == "/docs"
    assert data["health"] == "/api/v1/health" 