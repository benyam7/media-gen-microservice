"""Job model for tracking media generation tasks."""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel, JSON, Column
from sqlalchemy import DateTime, func, text


class JobStatus(str, Enum):
    """Job status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class Job(SQLModel, table=True):
    """Job model for tracking media generation tasks."""
    
    __tablename__ = "jobs"
    
    # Primary key
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique job identifier"
    )
    
    # Job metadata
    status: JobStatus = Field(
        default=JobStatus.PENDING,
        description="Current job status"
    )
    prompt: str = Field(
        description="Text prompt for media generation",
        index=True
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Generation parameters (model settings, etc.)"
    )
    
    # Execution tracking
    retry_count: int = Field(
        default=0,
        description="Number of retry attempts"
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retries allowed"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if job failed"
    )
    error_details: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Detailed error information"
    )
    
    # Celery task tracking
    celery_task_id: Optional[str] = Field(
        default=None,
        index=True,
        description="Celery task ID for job tracking"
    )
    
    # Media result
    media_id: Optional[UUID] = Field(
        default=None,
        foreign_key="media.id",
        description="Generated media ID"
    )
    
    # Request metadata
    client_ip: Optional[str] = Field(
        default=None,
        description="Client IP address"
    )
    user_agent: Optional[str] = Field(
        default=None,
        description="Client user agent"
    )
    request_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Additional request metadata"
    )
    
    # Timestamps
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False
        ),
        description="Job creation timestamp"
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False
        ),
        description="Last update timestamp"
    )
    started_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Processing start timestamp"
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Job completion timestamp"
    )
    
    # Computed properties
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate job duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def is_terminal(self) -> bool:
        """Check if job is in a terminal state."""
        return self.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]
    
    @property
    def can_retry(self) -> bool:
        """Check if job can be retried."""
        return (
            self.status == JobStatus.FAILED and
            self.retry_count < self.max_retries
        )
    
    class Config:
        """Model configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        } 