"""Jobs endpoints for media generation."""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.config import get_settings, Settings
from app.db.database import get_session
from app.models import Job, Media
from app.models.job import JobStatus
from app.schemas.job import (
    JobCreate,
    JobResponse,
    JobStatusResponse,
    JobListResponse,
    MediaInfo
)
from app.schemas.common import PaginationParams
from app.services.job_service import JobService
from app.workers.tasks import generate_media_task
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/generate", response_model=JobResponse, status_code=201)
async def create_job(
    job_data: JobCreate,
    request: Request,
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings)
) -> JobResponse:
    """Create a new media generation job.
    
    This endpoint accepts a prompt and generation parameters, creates a job,
    and enqueues it for asynchronous processing.
    """
    # Create job service
    job_service = JobService(db)
    
    # Extract request metadata
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    try:
        # Create job in database
        job = await job_service.create_job(
            prompt=job_data.prompt,
            parameters=job_data.parameters.model_dump() if job_data.parameters else {},
            client_ip=client_ip,
            user_agent=user_agent,
            request_metadata={
                "webhook_url": job_data.webhook_url,
                "custom_metadata": job_data.metadata
            } if (job_data.webhook_url or job_data.metadata) else None
        )
        
        # Enqueue job for processing
        task = generate_media_task.apply_async(
            args=[str(job.id)],
            task_id=str(job.id)
        )
        
        # Update job with Celery task ID
        job.celery_task_id = task.id
        await db.commit()
        
        # Build status URL
        status_url = str(request.url_for("get_job_status", job_id=job.id))
        
        return JobResponse(
            id=job.id,
            status=job.status,
            created_at=job.created_at,
            status_url=status_url,
            estimated_completion_time=settings.replicate_timeout
        )
        
    except Exception as e:
        logger.error("Failed to create job", error=str(e), prompt=job_data.prompt)
        raise HTTPException(
            status_code=500,
            detail="Failed to create job. Please try again."
        )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings)
) -> JobStatusResponse:
    """Get the status of a specific job.
    
    Returns detailed information about the job including its current status,
    any errors, and generated media if completed.
    """
    # Query job with media
    stmt = select(Job).where(Job.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get media if job is completed
    media_list = []
    if job.media_id:
        media_stmt = select(Media).where(Media.id == job.media_id)
        media_result = await db.execute(media_stmt)
        media = media_result.scalar_one_or_none()
        
        if media:
            media_list.append(
                MediaInfo(
                    id=media.id,
                    url=media.storage_url or f"{settings.api_host}/media/{media.id}",
                    type=media.type.value,
                    mime_type=media.mime_type,
                    file_size_bytes=media.file_size_bytes,
                    width=media.width,
                    height=media.height
                )
            )
    
    return JobStatusResponse(
        id=job.id,
        status=job.status,
        prompt=job.prompt,
        parameters=job.parameters,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_seconds=job.duration_seconds,
        retry_count=job.retry_count,
        error_message=job.error_message,
        media=media_list if media_list else None
    )


@router.get("", response_model=JobListResponse)
async def list_jobs(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[JobStatus] = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_session)
) -> JobListResponse:
    """List jobs with pagination and optional filtering.
    
    Returns a paginated list of jobs, optionally filtered by status.
    """
    # Build base query
    query = select(Job)
    count_query = select(func.count(Job.id))
    
    # Apply filters
    if status:
        query = query.where(Job.status == status)
        count_query = count_query.where(Job.status == status)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.order_by(Job.created_at.desc()).offset(offset).limit(per_page)
    
    # Execute query
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    # Convert to response format
    job_responses = []
    for job in jobs:
        # Get media if available
        media_list = []
        if job.media_id:
            media_stmt = select(Media).where(Media.id == job.media_id)
            media_result = await db.execute(media_stmt)
            media = media_result.scalar_one_or_none()
            
            if media:
                media_list.append(
                    MediaInfo(
                        id=media.id,
                        url=media.storage_url or f"/api/v1/media/{media.id}",
                        type=media.type.value,
                        mime_type=media.mime_type,
                        file_size_bytes=media.file_size_bytes,
                        width=media.width,
                        height=media.height
                    )
                )
        
        job_responses.append(
            JobStatusResponse(
                id=job.id,
                status=job.status,
                prompt=job.prompt,
                parameters=job.parameters,
                created_at=job.created_at,
                updated_at=job.updated_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                duration_seconds=job.duration_seconds,
                retry_count=job.retry_count,
                error_message=job.error_message,
                media=media_list if media_list else None
            )
        )
    
    # Calculate pagination info
    total_pages = (total + per_page - 1) // per_page
    has_next = page < total_pages
    has_prev = page > 1
    
    return JobListResponse(
        jobs=job_responses,
        total=total,
        page=page,
        per_page=per_page,
        has_next=has_next,
        has_prev=has_prev
    )


@router.delete("/{job_id}", status_code=204)
async def cancel_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_session)
) -> None:
    """Cancel a pending or processing job.
    
    Only jobs that are not in a terminal state can be cancelled.
    """
    # Get job
    stmt = select(Job).where(Job.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.is_terminal:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job in {job.status} state"
        )
    
    # Update job status
    job.status = JobStatus.CANCELLED
    await db.commit()
    
    # Revoke Celery task if it exists
    if job.celery_task_id:
        try:
            from app.workers.celery_app import celery_app
            celery_app.control.revoke(job.celery_task_id, terminate=True)
        except Exception as e:
            logger.error("Failed to revoke Celery task", error=str(e), task_id=job.celery_task_id) 