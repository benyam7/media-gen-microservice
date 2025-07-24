"""Job service for managing media generation jobs."""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models import Job, JobStatus
from app.core.logging import get_logger

logger = get_logger(__name__)


class JobService:
    """Service for managing job lifecycle operations."""
    
    def __init__(self, db: AsyncSession):
        """Initialize job service with database session."""
        self.db = db
    
    async def create_job(
        self,
        prompt: str,
        parameters: Optional[Dict[str, Any]] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_metadata: Optional[Dict[str, Any]] = None
    ) -> Job:
        """Create a new job in the database.
        
        Args:
            prompt: Text prompt for generation
            parameters: Generation parameters
            client_ip: Client IP address
            user_agent: Client user agent
            request_metadata: Additional request metadata
            
        Returns:
            Created job instance
        """
        job = Job(
            prompt=prompt,
            parameters=parameters or {},
            client_ip=client_ip,
            user_agent=user_agent,
            request_metadata=request_metadata,
            status=JobStatus.PENDING
        )
        
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        
        logger.info(
            "Job created",
            job_id=str(job.id),
            prompt_preview=prompt[:50] + "..." if len(prompt) > 50 else prompt
        )
        
        return job
    
    async def get_job(self, job_id: UUID) -> Optional[Job]:
        """Get a job by ID.
        
        Args:
            job_id: Job UUID
            
        Returns:
            Job instance or None if not found
        """
        stmt = select(Job).where(Job.id == job_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def update_job_status(
        self,
        job_id: UUID,
        status: JobStatus,
        error_message: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None
    ) -> Optional[Job]:
        """Update job status with proper state transitions.
        
        Args:
            job_id: Job UUID
            status: New status
            error_message: Error message if failed
            error_details: Detailed error information
            
        Returns:
            Updated job instance or None if not found
        """
        job = await self.get_job(job_id)
        if not job:
            logger.error("Job not found for status update", job_id=str(job_id))
            return None
        
        # Validate state transition
        if job.is_terminal:
            logger.warning(
                "Attempted to update terminal job",
                job_id=str(job_id),
                current_status=job.status,
                new_status=status
            )
            return job
        
        # Update status
        job.status = status
        
        # Set timestamps based on status
        if status == JobStatus.PROCESSING and not job.started_at:
            job.started_at = datetime.utcnow()
        elif status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            job.completed_at = datetime.utcnow()
        
        # Set error information if failed
        if status == JobStatus.FAILED:
            job.error_message = error_message
            job.error_details = error_details
        
        await self.db.commit()
        await self.db.refresh(job)
        
        logger.info(
            "Job status updated",
            job_id=str(job_id),
            status=status,
            duration=job.duration_seconds
        )
        
        return job
    
    async def mark_job_processing(self, job_id: UUID) -> Optional[Job]:
        """Mark a job as processing.
        
        Args:
            job_id: Job UUID
            
        Returns:
            Updated job instance
        """
        return await self.update_job_status(job_id, JobStatus.PROCESSING)
    
    async def mark_job_completed(
        self,
        job_id: UUID,
        media_id: UUID
    ) -> Optional[Job]:
        """Mark a job as completed with generated media.
        
        Args:
            job_id: Job UUID
            media_id: Generated media UUID
            
        Returns:
            Updated job instance
        """
        job = await self.get_job(job_id)
        if not job:
            return None
        
        job.status = JobStatus.COMPLETED
        job.media_id = media_id
        job.completed_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(job)
        
        logger.info(
            "Job completed successfully",
            job_id=str(job_id),
            media_id=str(media_id),
            duration=job.duration_seconds
        )
        
        return job
    
    async def mark_job_failed(
        self,
        job_id: UUID,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None
    ) -> Optional[Job]:
        """Mark a job as failed with error information.
        
        Args:
            job_id: Job UUID
            error_message: Human-readable error message
            error_details: Detailed error information
            
        Returns:
            Updated job instance
        """
        return await self.update_job_status(
            job_id,
            JobStatus.FAILED,
            error_message,
            error_details
        )
    
    async def increment_retry_count(self, job_id: UUID) -> Optional[Job]:
        """Increment job retry count and update status.
        
        Args:
            job_id: Job UUID
            
        Returns:
            Updated job instance
        """
        job = await self.get_job(job_id)
        if not job:
            return None
        
        job.retry_count += 1
        job.status = JobStatus.RETRYING
        
        await self.db.commit()
        await self.db.refresh(job)
        
        logger.info(
            "Job retry count incremented",
            job_id=str(job_id),
            retry_count=job.retry_count,
            max_retries=job.max_retries
        )
        
        return job
    
    async def should_retry(self, job_id: UUID) -> bool:
        """Check if a job should be retried.
        
        Args:
            job_id: Job UUID
            
        Returns:
            True if job should be retried
        """
        job = await self.get_job(job_id)
        if not job:
            return False
        
        return job.can_retry
    
    async def cleanup_old_jobs(self, days: int = 30) -> int:
        """Clean up old completed jobs.
        
        Args:
            days: Number of days to keep jobs
            
        Returns:
            Number of jobs deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Find old completed jobs
        stmt = select(Job).where(
            Job.status.in_([JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]),
            Job.completed_at < cutoff_date
        )
        result = await self.db.execute(stmt)
        old_jobs = result.scalars().all()
        
        count = len(old_jobs)
        
        # Delete old jobs
        for job in old_jobs:
            await self.db.delete(job)
        
        await self.db.commit()
        
        if count > 0:
            logger.info(f"Cleaned up {count} old jobs")
        
        return count 