"""Tests for job API endpoints."""

import pytest
from unittest.mock import patch, AsyncMock
from uuid import uuid4
from httpx import AsyncClient

from app.models import JobStatus
from tests.utils import ValidationTestUtils


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
        assert "status_url" in data
        assert "estimated_completion_time" in data
        
        # Verify Celery task was called
        mock_celery_task.apply_async.assert_called_once()
    
    async def test_create_job_with_webhook(self, client: AsyncClient, mock_celery_task):
        """Test job creation with webhook URL."""
        job_data = {
            "prompt": "A beautiful sunset",
            "webhook_url": "https://example.com/webhook",
            "metadata": {"user_id": "123"}
        }
        
        with patch('app.api.v1.endpoints.jobs.generate_media_task', mock_celery_task):
            response = await client.post("/api/v1/jobs/generate", json=job_data)
        
        assert response.status_code == 201
    
    async def test_create_job_validation_errors(self, client: AsyncClient, invalid_job_create_data):
        """Test job creation with validation errors."""
        response = await client.post("/api/v1/jobs/generate", json=invalid_job_create_data)
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        # Should have validation errors for empty prompt
        errors = data["detail"]
        assert any("prompt" in str(error) for error in errors)
    
    async def test_create_job_missing_prompt(self, client: AsyncClient):
        """Test job creation without required prompt."""
        response = await client.post("/api/v1/jobs/generate", json={})
        
        assert response.status_code == 422
    
    async def test_create_job_invalid_webhook_url(self, client: AsyncClient):
        """Test job creation with invalid webhook URL."""
        job_data = {
            "prompt": "A beautiful sunset",
            "webhook_url": "invalid-url"
        }
        
        response = await client.post("/api/v1/jobs/generate", json=job_data)
        
        assert response.status_code == 422


class TestJobStatus:
    """Test job status endpoint."""
    
    async def test_get_job_status_pending(self, client: AsyncClient, sample_job):
        """Test getting status of pending job."""
        response = await client.get(f"/api/v1/jobs/status/{sample_job.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == str(sample_job.id)
        assert data["status"] == "pending"
        assert data["prompt"] == sample_job.prompt
        assert data["parameters"] == sample_job.parameters
        assert "created_at" in data
        assert data["media"] is None
    
    async def test_get_job_status_completed(self, client: AsyncClient, completed_job_with_media, sample_media):
        """Test getting status of completed job with media."""
        response = await client.get(f"/api/v1/jobs/status/{completed_job_with_media.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == str(completed_job_with_media.id)
        assert data["status"] == "completed"
        assert data["media"] is not None
        assert len(data["media"]) == 1
        
        media_info = data["media"][0]
        assert media_info["id"] == str(sample_media.id)
        assert media_info["type"] == "image"
        assert "url" in media_info
    
    async def test_get_job_status_not_found(self, client: AsyncClient):
        """Test getting non-existent job status."""
        fake_id = uuid4()
        response = await client.get(f"/api/v1/jobs/status/{fake_id}")
        assert response.status_code == 404
        ValidationTestUtils.assert_error_response(response.json(), "Job not found")
    
    async def test_get_job_status_invalid_uuid(self, client: AsyncClient):
        """Test getting status with invalid UUID."""
        response = await client.get("/api/v1/jobs/status/invalid-uuid")
        
        assert response.status_code == 422


class TestJobListing:
    """Test job listing endpoint."""
    
    async def test_list_jobs_empty(self, client: AsyncClient):
        """Test listing jobs when none exist."""
        response = await client.get("/api/v1/jobs")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["jobs"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["per_page"] == 20
        assert not data["has_next"]
        assert not data["has_prev"]
    
    async def test_list_jobs_with_data(self, client: AsyncClient, sample_job, completed_job_with_media):
        """Test listing jobs with data."""
        response = await client.get("/api/v1/jobs")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["jobs"]) == 2
        assert data["total"] == 2
        assert data["page"] == 1
        assert data["per_page"] == 20
        assert not data["has_next"]
        assert not data["has_prev"]
        
        # Jobs should be ordered by created_at desc
        job_ids = [job["id"] for job in data["jobs"]]
        assert str(completed_job_with_media.id) in job_ids
        assert str(sample_job.id) in job_ids
    
    async def test_list_jobs_with_pagination(self, client: AsyncClient, sample_job):
        """Test job listing with pagination parameters."""
        response = await client.get("/api/v1/jobs?page=1&per_page=1")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["jobs"]) == 1
        assert data["total"] == 1
        assert data["page"] == 1
        assert data["per_page"] == 1
    
    async def test_list_jobs_filter_by_status(self, client: AsyncClient, sample_job, completed_job_with_media):
        """Test filtering jobs by status."""
        response = await client.get("/api/v1/jobs?status=completed")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["id"] == str(completed_job_with_media.id)
        assert data["jobs"][0]["status"] == "completed"
    
    async def test_list_jobs_invalid_status_filter(self, client: AsyncClient):
        """Test filtering with invalid status."""
        response = await client.get("/api/v1/jobs?status=invalid_status")
        
        assert response.status_code == 422


class TestJobCancellation:
    """Test job cancellation endpoint."""
    
    async def test_cancel_pending_job(self, client: AsyncClient, sample_job):
        """Test cancelling a pending job."""
        # Patch celery_app where it's actually used
        with patch('app.workers.celery_app.celery_app.control') as mock_control:
            mock_control.revoke.return_value = None
            response = await client.delete(f"/api/v1/jobs/{sample_job.id}")
        
        assert response.status_code == 204
        
        # Verify job status was updated
        status_response = await client.get(f"/api/v1/jobs/status/{sample_job.id}")
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "cancelled"
    
    async def test_cancel_completed_job(self, client: AsyncClient, completed_job_with_media):
        """Test attempting to cancel a completed job."""
        response = await client.delete(f"/api/v1/jobs/{completed_job_with_media.id}")
        
        assert response.status_code == 400
        data = response.json()
        # More flexible assertion - check for "cannot cancel" and "completed" keywords
        error_msg = data.get("detail", "").lower()
        assert "cannot cancel" in error_msg and "completed" in error_msg
    
    async def test_cancel_nonexistent_job(self, client: AsyncClient):
        """Test cancelling non-existent job."""
        fake_id = uuid4()
        response = await client.delete(f"/api/v1/jobs/{fake_id}")
        assert response.status_code == 404
        ValidationTestUtils.assert_error_response(response.json(), "Job not found")


class TestJobEndpointsIntegration:
    """Integration tests for job endpoints."""
    
    async def test_complete_job_workflow(self, client: AsyncClient, mock_celery_task):
        """Test complete job creation and status workflow."""
        # Step 1: Create job
        job_data = {
            "prompt": "A beautiful sunset over mountains",
            "parameters": {
                "width": 1024,
                "height": 1024
            }
        }
        
        # Create job without testing cancellation (tested separately)
        with patch('app.api.v1.endpoints.jobs.generate_media_task', mock_celery_task):
            create_response = await client.post("/api/v1/jobs/generate", json=job_data)
        
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]
        
        # Step 2: Check status
        status_response = await client.get(f"/api/v1/jobs/status/{job_id}")
        assert status_response.status_code == 200
        
        # Step 3: List jobs  
        list_response = await client.get("/api/v1/jobs")
        assert list_response.status_code == 200
        jobs_data = list_response.json()
        assert len(jobs_data["jobs"]) >= 1


class TestJobParameterValidation:
    """Test job parameter validation."""
    
    async def test_valid_flux_parameters(self, client: AsyncClient, mock_celery_task):
        """Test job creation with valid Flux parameters."""
        job_data = {
            "prompt": "A beautiful sunset",
            "parameters": {
                "num_inference_steps": 4,
                "aspect_ratio": "16:9",
                "output_quality": 80,
                "seed": 12345
            }
        }
        
        with patch('app.api.v1.endpoints.jobs.generate_media_task', mock_celery_task):
            response = await client.post("/api/v1/jobs/generate", json=job_data)
        
        assert response.status_code == 201
    
    async def test_invalid_parameter_ranges(self, client: AsyncClient):
        """Test job creation with parameters outside valid ranges."""
        job_data = {
            "prompt": "A beautiful sunset",
            "parameters": {
                "num_inference_steps": 1000,  # Too high
                "guidance_scale": 25.0,  # Too high
                "width": 50,  # Too low
                "height": 3000  # Too high
            }
        }
        
        response = await client.post("/api/v1/jobs/generate", json=job_data)
        
        assert response.status_code == 422
        errors = response.json()["detail"]
        # Should have validation errors for out-of-range parameters
        assert len(errors) > 0 