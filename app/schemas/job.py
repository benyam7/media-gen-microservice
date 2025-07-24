"""Job-related Pydantic schemas."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field, validator, ConfigDict
from app.models.job import JobStatus


class GenerationParameters(BaseModel):
    """Media generation parameters."""
    
    model_config = ConfigDict(extra="allow")
    
    # Common parameters
    width: Optional[int] = Field(
        default=1024,
        ge=128,
        le=2048,
        description="Image width in pixels"
    )
    height: Optional[int] = Field(
        default=1024,
        ge=128,
        le=2048,
        description="Image height in pixels"
    )
    num_inference_steps: Optional[int] = Field(
        default=50,
        ge=1,
        le=500,
        description="Number of denoising steps"
    )
    guidance_scale: Optional[float] = Field(
        default=7.5,
        ge=1.0,
        le=20.0,
        description="Guidance scale for generation"
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Negative prompt to avoid certain features"
    )
    seed: Optional[int] = Field(
        default=None,
        ge=0,
        le=2147483647,
        description="Random seed for reproducibility"
    )
    scheduler: Optional[str] = Field(
        default="DPMSolverMultistep",
        description="Scheduler algorithm"
    )
    num_outputs: Optional[int] = Field(
        default=1,
        ge=1,
        le=4,
        description="Number of images to generate"
    )
    
    @validator("scheduler")
    def validate_scheduler(cls, v: str) -> str:
        """Validate scheduler is supported."""
        valid_schedulers = [
            "DDIM",
            "DPMSolverMultistep",
            "HeunDiscrete",
            "KarrasDPM",
            "K_EULER_ANCESTRAL",
            "K_EULER",
            "PNDM",
        ]
        if v not in valid_schedulers:
            raise ValueError(f"Scheduler must be one of: {', '.join(valid_schedulers)}")
        return v


class JobCreate(BaseModel):
    """Request schema for creating a new job."""
    
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Text prompt for media generation"
    )
    parameters: Optional[GenerationParameters] = Field(
        default_factory=GenerationParameters,
        description="Generation parameters"
    )
    webhook_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional webhook URL for job completion notification"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata to attach to the job"
    )
    
    @validator("prompt")
    def validate_prompt(cls, v: str) -> str:
        """Clean and validate prompt."""
        v = v.strip()
        if not v:
            raise ValueError("Prompt cannot be empty")
        return v
    
    @validator("webhook_url")
    def validate_webhook_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate webhook URL format."""
        if v:
            if not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("Webhook URL must start with http:// or https://")
        return v


class JobResponse(BaseModel):
    """Response schema for job creation."""
    
    id: UUID = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    created_at: datetime = Field(..., description="Job creation timestamp")
    status_url: str = Field(..., description="URL to check job status")
    estimated_completion_time: Optional[int] = Field(
        default=None,
        description="Estimated completion time in seconds"
    )
    
    model_config = ConfigDict(from_attributes=True)


class MediaInfo(BaseModel):
    """Media information in job response."""
    
    id: UUID = Field(..., description="Media identifier")
    url: str = Field(..., description="Media access URL")
    type: str = Field(..., description="Media type")
    mime_type: Optional[str] = Field(None, description="MIME type")
    file_size_bytes: Optional[int] = Field(None, description="File size in bytes")
    width: Optional[int] = Field(None, description="Width in pixels")
    height: Optional[int] = Field(None, description="Height in pixels")
    
    model_config = ConfigDict(from_attributes=True)


class JobStatusResponse(BaseModel):
    """Response schema for job status check."""
    
    id: UUID = Field(..., description="Job identifier")
    status: JobStatus = Field(..., description="Current job status")
    prompt: str = Field(..., description="Generation prompt")
    parameters: Dict[str, Any] = Field(..., description="Generation parameters")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    started_at: Optional[datetime] = Field(None, description="Processing start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    duration_seconds: Optional[float] = Field(None, description="Processing duration")
    retry_count: int = Field(..., description="Number of retry attempts")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    media: Optional[List[MediaInfo]] = Field(
        default=None,
        description="Generated media information"
    )
    progress: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Progress percentage"
    )
    
    model_config = ConfigDict(from_attributes=True)
    
    @validator("progress", always=True)
    def calculate_progress(cls, v: Optional[float], values: dict) -> Optional[float]:
        """Calculate progress based on status."""
        status = values.get("status")
        if status == JobStatus.PENDING:
            return 0.0
        elif status == JobStatus.PROCESSING:
            return v or 50.0  # Default to 50% if not provided
        elif status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            return 100.0
        return v


class JobListResponse(BaseModel):
    """Response schema for listing jobs."""
    
    jobs: List[JobStatusResponse] = Field(..., description="List of jobs")
    total: int = Field(..., description="Total number of jobs")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Items per page")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_prev: bool = Field(..., description="Whether there are previous pages") 