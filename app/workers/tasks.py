"""Celery tasks for media generation."""

import asyncio
import io
import time
from typing import Dict, Any, Optional
from uuid import UUID
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
import httpx
from PIL import Image
from app.workers.celery_app import celery_app
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.database import get_db_context, reset_db_connections
from app.models import JobStatus, Media, MediaType
from app.services.job_service import JobService
from app.services.storage_service import StorageService
from app.services.replicate_service import ReplicateService

logger = get_logger(__name__)


class CallbackTask(Task):
    """Base task with callbacks for better error handling."""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called on task failure."""
        job_id = args[0] if args else None
        logger.error(
            "Task failed",
            task_id=task_id,
            job_id=job_id,
            error=str(exc),
            traceback=str(einfo)
        )
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called on task retry."""
        job_id = args[0] if args else None
        logger.warning(
            "Task retrying",
            task_id=task_id,
            job_id=job_id,
            error=str(exc),
            retry_count=self.request.retries
        )
    
    def on_success(self, retval, task_id, args, kwargs):
        """Called on task success."""
        job_id = args[0] if args else None
        logger.info(
            "Task completed successfully",
            task_id=task_id,
            job_id=job_id
        )


@celery_app.task(
    base=CallbackTask,
    bind=True,
    name="app.workers.tasks.generate_media_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def generate_media_task(self, job_id: str) -> Dict[str, Any]:
    """Generate media using Replicate API.
    
    This task handles the entire media generation workflow:
    1. Update job status to processing
    2. Call Replicate API
    3. Download generated media
    4. Upload to storage
    5. Create media record
    6. Update job with result
    
    Args:
        job_id: UUID of the job to process
        
    Returns:
        Dict with task result information
    """
    # Use a single event loop for all async operations
    try:
        return asyncio.run(_generate_media_task_async(job_id, self))
    except _RetryTaskException as retry_exc:
        # Handle retry in sync context
        raise self.retry(countdown=retry_exc.countdown, exc=retry_exc.original_exc)
    except Exception as e:
        logger.error("Task failed with unexpected error", job_id=job_id, error=str(e))
        raise


async def _generate_media_task_async(job_id: str, task_instance) -> Dict[str, Any]:
    """Main async task implementation with proper error handling and retry logic."""
    settings = get_settings()
    
    # Reset database connections to ensure fresh connections for this event loop
    await reset_db_connections()
    
    try:
        # Run the media generation
        return await _generate_media_async(job_id, task_instance.request.retries)
        
    except SoftTimeLimitExceeded:
        logger.error("Task timeout exceeded", job_id=job_id)
        await _handle_job_failure(
            job_id,
            "Task timeout exceeded",
            {"timeout": settings.replicate_timeout}
        )
        raise
        
    except Exception as e:
        logger.error("Task failed with error", job_id=job_id, error=str(e))
        
        # Check if we should retry
        should_retry = await _should_retry_job(job_id)
        
        if should_retry and task_instance.request.retries < task_instance.max_retries:
            # Calculate exponential backoff
            backoff = min(
                settings.celery_retry_backoff_base ** task_instance.request.retries,
                settings.celery_retry_backoff_max
            )
            
            # Update retry count
            await _increment_retry_count(job_id)
            
            # Retry the task - we need to raise this synchronously
            # Convert the retry exception to be raised in the sync context
            raise _RetryTaskException(backoff, e)
        else:
            # Mark as permanently failed
            await _handle_job_failure(
                job_id,
                str(e),
                {
                    "retry_count": task_instance.request.retries,
                    "max_retries": task_instance.max_retries
                }
            )
            raise


class _RetryTaskException(Exception):
    """Exception to signal task should be retried."""
    def __init__(self, countdown: int, original_exc: Exception):
        self.countdown = countdown
        self.original_exc = original_exc
        super().__init__(str(original_exc))


async def _generate_media_async(job_id: str, retry_count: int) -> Dict[str, Any]:
    """Async implementation of media generation."""
    settings = get_settings()
    
    async with get_db_context() as db:
        job_service = JobService(db)
        
        # Get job
        job = await job_service.get_job(UUID(job_id))
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        # Check if job is already complete or cancelled
        if job.is_terminal:
            logger.warning(
                "Job already in terminal state",
                job_id=job_id,
                status=job.status
            )
            return {"status": "skipped", "reason": f"Job already {job.status}"}
        
        # Update job status to processing
        await job_service.mark_job_processing(job.id)
        
        try:
            # Initialize services
            replicate_service = ReplicateService(settings)
            storage_service = StorageService(settings)
            
            # Generate media using Replicate
            logger.info(
                "Calling Replicate API",
                job_id=job_id,
                prompt_preview=job.prompt[:50] + "..."
            )
            
            media_urls = await replicate_service.generate_media(
                prompt=job.prompt,
                parameters=job.parameters
            )
            
            if not media_urls:
                raise ValueError("No media generated by Replicate")
            
            # Process the first generated media
            # (extend this to handle multiple outputs if needed)
            media_url = media_urls[0]
            
            # Download media from URL
            logger.info("Downloading generated media", job_id=job_id, url=media_url)
            media_content, content_type = await _download_media(media_url)
            
            # Process and get media metadata
            media_metadata = await _process_media(media_content, content_type)
            
            # Generate storage key
            file_extension = media_metadata["file_extension"]
            storage_key = f"generated/{job.id}{file_extension}"
            
            # Upload to storage
            logger.info("Uploading media to storage", job_id=job_id, key=storage_key)
            storage_path, public_url = await storage_service.upload_file(
                file_content=media_content,
                file_name=storage_key,
                content_type=content_type
            )
            
            # Create media record
            media = Media(
                type=MediaType.IMAGE,  # Extend to support other types
                storage_path=storage_path,
                storage_url=public_url,
                file_size_bytes=len(media_content),
                mime_type=content_type,
                file_extension=file_extension,
                width=media_metadata.get("width"),
                height=media_metadata.get("height"),
                generation_model_name=settings.replicate_model.split(":")[0],
                generation_model_version=settings.replicate_model.split(":")[1] if ":" in settings.replicate_model else None,
                generation_params=job.parameters,
                storage_provider=settings.storage_type,
                bucket_name=settings.s3_bucket_name if settings.storage_type == "s3" else None
            )
            
            db.add(media)
            await db.commit()
            await db.refresh(media)
            
            # Update job with media reference
            await job_service.mark_job_completed(job.id, media.id)
            
            # Send webhook if configured
            if job.request_metadata and job.request_metadata.get("webhook_url"):
                await _send_webhook(
                    job.request_metadata["webhook_url"],
                    {
                        "job_id": str(job.id),
                        "status": "completed",
                        "media_url": public_url or f"/api/v1/media/{media.id}",
                        "media_id": str(media.id)
                    }
                )
            
            logger.info(
                "Media generation completed",
                job_id=job_id,
                media_id=str(media.id),
                duration=time.time() - job.started_at.timestamp()
            )
            
            return {
                "status": "completed",
                "job_id": str(job.id),
                "media_id": str(media.id),
                "media_url": public_url
            }
            
        except Exception as e:
            logger.error(
                "Media generation failed",
                job_id=job_id,
                error=str(e),
                retry_count=retry_count
            )
            raise


async def _download_media(url: str) -> tuple[bytes, str]:
    """Download media from URL or decode from data URL with better error handling."""
    # Handle data URLs (base64 encoded images)
    if url.startswith("data:"):
        import base64
        import re
        
        # Parse data URL: data:image/png;base64,iVBORw0KGgoAAAA...
        match = re.match(r"data:([^;]+);base64,(.+)", url)
        if not match:
            raise ValueError(f"Invalid data URL format: {url[:50]}...")
        
        content_type = match.group(1)
        base64_data = match.group(2)
        
        try:
            content = base64.b64decode(base64_data)
            logger.debug(
                "Data URL decoded successfully",
                content_type=content_type,
                size=len(content)
            )
            return content, content_type
        except Exception as e:
            raise ValueError(f"Failed to decode data URL: {e}")
    
    # Handle regular HTTP/HTTPS URLs
    timeout_config = httpx.Timeout(60.0, connect=10.0)
    
    try:
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            logger.debug("Attempting to download media", url=url)
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            
            content_type = response.headers.get("content-type", "image/png")
            logger.debug(
                "Media download successful", 
                url=url, 
                content_type=content_type,
                size=len(response.content)
            )
            return response.content, content_type
            
    except httpx.ConnectError as e:
        logger.error(
            "Network connectivity error downloading media",
            url=url,
            error=str(e)
        )
        raise ValueError(f"Failed to connect to media URL: {url}. Network error: {e}")
    except httpx.TimeoutException as e:
        logger.error(
            "Timeout downloading media",
            url=url,
            error=str(e)
        )
        raise ValueError(f"Timeout downloading media from: {url}")
    except httpx.HTTPStatusError as e:
        logger.error(
            "HTTP error downloading media",
            url=url,
            status_code=e.response.status_code,
            error=str(e)
        )
        raise ValueError(f"HTTP {e.response.status_code} error downloading media from: {url}")
    except Exception as e:
        logger.error(
            "Unexpected error downloading media",
            url=url,
            error=str(e)
        )
        raise ValueError(f"Unexpected error downloading media from: {url}: {e}")


async def _process_media(content: bytes, content_type: str) -> Dict[str, Any]:
    """Process media and extract metadata."""
    metadata = {}
    
    # Determine file extension
    if "jpeg" in content_type or "jpg" in content_type:
        metadata["file_extension"] = ".jpg"
    elif "png" in content_type:
        metadata["file_extension"] = ".png"
    elif "webp" in content_type:
        metadata["file_extension"] = ".webp"
    else:
        metadata["file_extension"] = ".png"  # Default
    
    # Extract image dimensions
    try:
        image = Image.open(io.BytesIO(content))
        metadata["width"] = image.width
        metadata["height"] = image.height
        metadata["format"] = image.format
    except Exception as e:
        logger.warning("Failed to extract image metadata", error=str(e))
    
    return metadata


async def _send_webhook(url: str, data: Dict[str, Any]) -> None:
    """Send webhook notification."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=data)
            response.raise_for_status()
            logger.info("Webhook sent successfully", url=url)
    except Exception as e:
        logger.error("Failed to send webhook", url=url, error=str(e))


async def _should_retry_job(job_id: str) -> bool:
    """Check if job should be retried."""
    try:
        async with get_db_context() as db:
            job_service = JobService(db)
            return await job_service.should_retry(UUID(job_id))
    except Exception as e:
        logger.error("Error checking retry status", job_id=job_id, error=str(e))
        # If we can't check retry status, don't retry to avoid infinite loops
        return False


async def _increment_retry_count(job_id: str) -> None:
    """Increment job retry count."""
    try:
        async with get_db_context() as db:
            job_service = JobService(db)
            await job_service.increment_retry_count(UUID(job_id))
    except Exception as e:
        logger.error("Error incrementing retry count", job_id=job_id, error=str(e))


async def _handle_job_failure(
    job_id: str,
    error_message: str,
    error_details: Optional[Dict[str, Any]] = None
) -> None:
    """Handle job failure."""
    try:
        async with get_db_context() as db:
            job_service = JobService(db)
            job = await job_service.mark_job_failed(
                UUID(job_id),
                error_message,
                error_details
            )
            
            # Send failure webhook if configured
            if job and job.request_metadata and job.request_metadata.get("webhook_url"):
                await _send_webhook(
                    job.request_metadata["webhook_url"],
                    {
                        "job_id": str(job.id),
                        "status": "failed",
                        "error": error_message,
                        "error_details": error_details
                    }
                )
    except Exception as e:
        logger.error("Error handling job failure", job_id=job_id, error=str(e))


@celery_app.task(name="app.workers.tasks.cleanup_old_jobs")
def cleanup_old_jobs() -> Dict[str, Any]:
    """Periodic task to clean up old jobs."""
    try:
        count = asyncio.run(_cleanup_old_jobs_async())
        return {"status": "success", "cleaned_up": count}
    except Exception as e:
        logger.error("Failed to cleanup old jobs", error=str(e))
        return {"status": "failed", "error": str(e)}


async def _cleanup_old_jobs_async() -> int:
    """Async implementation of job cleanup."""
    # Reset database connections for cleanup task as well
    await reset_db_connections()
    
    async with get_db_context() as db:
        job_service = JobService(db)
        return await job_service.cleanup_old_jobs(days=30) 