"""Tests for JobService."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4, UUID

from app.services.job_service import JobService
from app.models import Job, JobStatus
from app.models.job import JobStatus


class TestJobCreation:
    """Test job creation functionality."""
    
    async def test_create_job_basic(self, job_service: JobService):
        """Test basic job creation."""
        prompt = "A beautiful sunset over mountains"
        parameters = {"width": 1024, "height": 1024}
        
        job = await job_service.create_job(
            prompt=prompt,
            parameters=parameters
        )
        
        assert job.id is not None
        assert job.prompt == prompt
        assert job.parameters == parameters
        assert job.status == JobStatus.PENDING
        assert job.retry_count == 0
        assert job.created_at is not None
        assert job.updated_at is not None
    
    async def test_create_job_with_metadata(self, job_service: JobService):
        """Test job creation with client metadata."""
        job = await job_service.create_job(
            prompt="Test prompt",
            parameters={"test": "value"},
            client_ip="192.168.1.1",
            user_agent="Test Agent",
            request_metadata={"webhook_url": "https://example.com/webhook"}
        )
        
        assert job.client_ip == "192.168.1.1"
        assert job.user_agent == "Test Agent"
        assert job.request_metadata == {"webhook_url": "https://example.com/webhook"}
    
    async def test_create_job_with_empty_parameters(self, job_service: JobService):
        """Test job creation with empty parameters."""
        job = await job_service.create_job(
            prompt="Test prompt",
            parameters=None
        )
        
        assert job.parameters == {}


class TestJobRetrieval:
    """Test job retrieval functionality."""
    
    async def test_get_job_exists(self, job_service: JobService, sample_job: Job):
        """Test retrieving existing job."""
        retrieved_job = await job_service.get_job(sample_job.id)
        
        assert retrieved_job is not None
        assert retrieved_job.id == sample_job.id
        assert retrieved_job.prompt == sample_job.prompt
        assert retrieved_job.status == sample_job.status
    
    async def test_get_job_not_exists(self, job_service: JobService):
        """Test retrieving non-existent job."""
        fake_id = uuid4()
        retrieved_job = await job_service.get_job(fake_id)
        
        assert retrieved_job is None


class TestJobStatusUpdates:
    """Test job status update functionality."""
    
    async def test_mark_job_processing(self, job_service: JobService, sample_job: Job):
        """Test marking job as processing."""
        updated_job = await job_service.mark_job_processing(sample_job.id)
        
        assert updated_job is not None
        assert updated_job.status == JobStatus.PROCESSING
        assert updated_job.started_at is not None
        assert updated_job.started_at >= sample_job.created_at
    
    async def test_mark_job_completed(self, job_service: JobService, sample_job: Job, sample_media):
        """Test marking job as completed."""
        # First mark as processing
        await job_service.mark_job_processing(sample_job.id)
        
        # Then mark as completed
        updated_job = await job_service.mark_job_completed(sample_job.id, sample_media.id)
        
        assert updated_job is not None
        assert updated_job.status == JobStatus.COMPLETED
        assert updated_job.completed_at is not None
        assert updated_job.media_id == sample_media.id
        assert updated_job.duration_seconds is not None
        assert updated_job.duration_seconds > 0
    
    async def test_mark_job_failed(self, job_service: JobService, sample_job: Job):
        """Test marking job as failed."""
        error_message = "Test error message"
        error_details = {"error_code": "TEST_ERROR", "details": "Test details"}
        
        updated_job = await job_service.mark_job_failed(
            sample_job.id,
            error_message,
            error_details
        )
        
        assert updated_job is not None
        assert updated_job.status == JobStatus.FAILED
        assert updated_job.error_message == error_message
        assert updated_job.error_details == error_details
        assert updated_job.completed_at is not None
    
    async def test_update_job_status_terminal_state_protection(self, job_service: JobService, completed_job_with_media: Job):
        """Test that completed jobs cannot be updated."""
        # Try to update already completed job
        updated_job = await job_service.update_job_status(
            completed_job_with_media.id,
            JobStatus.PROCESSING
        )
        
        # Should return None or the job unchanged
        if updated_job:
            assert updated_job.status == JobStatus.COMPLETED  # Status should not change
    
    async def test_update_nonexistent_job(self, job_service: JobService):
        """Test updating non-existent job."""
        fake_id = uuid4()
        updated_job = await job_service.update_job_status(fake_id, JobStatus.PROCESSING)
        
        assert updated_job is None


class TestJobRetryLogic:
    """Test job retry functionality."""
    
    async def test_increment_retry_count(self, job_service: JobService, sample_job: Job):
        """Test incrementing retry count."""
        original_count = sample_job.retry_count
        
        updated_job = await job_service.increment_retry_count(sample_job.id)
        
        assert updated_job is not None
        assert updated_job.retry_count == original_count + 1
    
    async def test_should_retry_within_limit(self, job_service: JobService, sample_job: Job):
        """Test retry decision within limit."""
        # Set job as failed with retry count below limit
        sample_job.status = JobStatus.FAILED
        sample_job.retry_count = 1
        sample_job.max_retries = 3
        
        should_retry = await job_service.should_retry(sample_job.id)
        
        assert should_retry is True
    
    async def test_should_retry_at_limit(self, job_service: JobService, sample_job: Job):
        """Test retry decision at limit."""
        # Set job as failed with retry count at limit
        sample_job.status = JobStatus.FAILED
        sample_job.retry_count = 3
        sample_job.max_retries = 3
        
        should_retry = await job_service.should_retry(sample_job.id)
        
        assert should_retry is False
    
    async def test_should_retry_completed_job(self, job_service: JobService, completed_job_with_media: Job):
        """Test retry decision for completed job."""
        should_retry = await job_service.should_retry(completed_job_with_media.id)
        
        assert should_retry is False
    
    async def test_should_retry_nonexistent_job(self, job_service: JobService):
        """Test retry decision for non-existent job."""
        fake_id = uuid4()
        should_retry = await job_service.should_retry(fake_id)
        
        assert should_retry is False


class TestJobCleanup:
    """Test job cleanup functionality."""
    
    async def test_cleanup_old_jobs(self, job_service: JobService, db_session):
        """Test cleaning up old jobs."""
        # Create old completed job
        old_job = Job(
            prompt="Old job",
            parameters={},
            status=JobStatus.COMPLETED,
            created_at=datetime.utcnow() - timedelta(days=40),
            completed_at=datetime.utcnow() - timedelta(days=40)
        )
        
        # Create recent job
        recent_job = Job(
            prompt="Recent job",
            parameters={},
            status=JobStatus.COMPLETED,
            created_at=datetime.utcnow() - timedelta(days=10),
            completed_at=datetime.utcnow() - timedelta(days=10)
        )
        
        db_session.add(old_job)
        db_session.add(recent_job)
        await db_session.commit()
        
        # Cleanup jobs older than 30 days
        cleanup_count = await job_service.cleanup_old_jobs(days=30)
        
        assert cleanup_count == 1
        
        # Verify old job is deleted
        retrieved_old = await job_service.get_job(old_job.id)
        assert retrieved_old is None
        
        # Verify recent job still exists
        retrieved_recent = await job_service.get_job(recent_job.id)
        assert retrieved_recent is not None


class TestJobBusinessLogic:
    """Test job business logic and computed properties."""
    
    async def test_job_duration_calculation(self, job_service: JobService, sample_job: Job):
        """Test job duration calculation."""
        # Mark as processing
        await job_service.mark_job_processing(sample_job.id)
        
        # Wait a bit and mark as completed
        import asyncio
        await asyncio.sleep(0.1)
        
        completed_job = await job_service.mark_job_completed(sample_job.id, uuid4())
        
        assert completed_job.duration_seconds is not None
        assert completed_job.duration_seconds > 0
        assert completed_job.duration_seconds < 1  # Should be very short
    
    async def test_job_terminal_state_detection(self, job_service: JobService):
        """Test terminal state detection."""
        # Create jobs in different states
        pending_job = await job_service.create_job("Pending job", {})
        
        processing_job = await job_service.create_job("Processing job", {})
        await job_service.mark_job_processing(processing_job.id)
        
        completed_job = await job_service.create_job("Completed job", {})
        await job_service.mark_job_processing(completed_job.id)
        await job_service.mark_job_completed(completed_job.id, uuid4())
        
        failed_job = await job_service.create_job("Failed job", {})
        await job_service.mark_job_failed(failed_job.id, "Test error")
        
        # Test terminal state detection
        assert not pending_job.is_terminal
        assert not processing_job.is_terminal
        assert completed_job.is_terminal
        assert failed_job.is_terminal
    
    async def test_job_can_retry_logic(self, job_service: JobService):
        """Test job retry capability logic."""
        from app.models import Job
        
        # Create a job object not tracked by the database session
        job_data = {
            "id": uuid4(),
            "prompt": "Retry test job",
            "status": JobStatus.FAILED,
            "retry_count": 1,
            "max_retries": 3,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        job = Job(**job_data)
        
        # Test within retry limit
        assert job.can_retry is True
        
        # Test exceed retry limit
        job.retry_count = 3
        assert job.can_retry is False
        
        # Test completed job cannot retry
        job.status = JobStatus.COMPLETED
        job.retry_count = 0
        assert job.can_retry is False


class TestJobServiceErrorHandling:
    """Test error handling in job service."""
    
    async def test_update_job_with_invalid_status_transition(self, job_service: JobService, sample_job: Job):
        """Test invalid status transitions are handled gracefully."""
        # Mark job as completed first
        await job_service.mark_job_processing(sample_job.id)
        await job_service.mark_job_completed(sample_job.id, uuid4())
        
        # Try to mark as processing again (invalid transition)
        result = await job_service.mark_job_processing(sample_job.id)
        
        # Should handle gracefully
        assert result is not None  # Job still exists
        # Status should remain completed
        updated_job = await job_service.get_job(sample_job.id)
        assert updated_job.status == JobStatus.COMPLETED
    
    async def test_concurrent_job_updates(self, job_service: JobService, sample_job):
        """Test handling concurrent updates to same job."""
        # SQLite has limitations with concurrent operations
        # In production with PostgreSQL, this would test true concurrency
        # For now, we'll test sequential updates to verify the logic
        
        # Update job status sequentially
        job = await job_service.mark_job_processing(sample_job.id)
        assert job.status == JobStatus.PROCESSING
        
        # Try to update again - should succeed since we're not enforcing strict state transitions
        job = await job_service.mark_job_completed(sample_job.id, uuid4())
        assert job.status == JobStatus.COMPLETED 