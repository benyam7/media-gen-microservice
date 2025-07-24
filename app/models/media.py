"""Media model for storing generated media metadata."""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel, JSON, Column
from sqlalchemy import DateTime, func


class MediaType(str, Enum):
    """Media type enumeration."""
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class Media(SQLModel, table=True):
    """Media model for storing generated media information."""
    
    __tablename__ = "media"
    
    # Primary key
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique media identifier"
    )
    
    # Media metadata
    type: MediaType = Field(
        default=MediaType.IMAGE,
        description="Type of media"
    )
    storage_path: str = Field(
        description="Storage path or S3 key",
        index=True
    )
    storage_url: Optional[str] = Field(
        default=None,
        description="Public URL for accessing the media"
    )
    
    # File information
    file_size_bytes: Optional[int] = Field(
        default=None,
        description="File size in bytes"
    )
    mime_type: Optional[str] = Field(
        default=None,
        description="MIME type of the media"
    )
    file_extension: Optional[str] = Field(
        default=None,
        description="File extension"
    )
    
    # Media properties
    width: Optional[int] = Field(
        default=None,
        description="Width in pixels (for images/videos)"
    )
    height: Optional[int] = Field(
        default=None,
        description="Height in pixels (for images/videos)"
    )
    duration_seconds: Optional[float] = Field(
        default=None,
        description="Duration in seconds (for videos/audio)"
    )
    
    # Generation metadata
    generation_model_name: Optional[str] = Field(
        default=None,
        description="Model used for generation"
    )
    generation_model_version: Optional[str] = Field(
        default=None,
        description="Model version"
    )
    generation_params: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Parameters used for generation"
    )
    
    # Storage metadata
    storage_provider: str = Field(
        default="s3",
        description="Storage provider (s3, local, etc.)"
    )
    bucket_name: Optional[str] = Field(
        default=None,
        description="S3 bucket name"
    )
    etag: Optional[str] = Field(
        default=None,
        description="ETag for S3 objects"
    )
    
    # Additional metadata
    extra_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Additional metadata"
    )
    
    # Timestamps
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False
        ),
        description="Media creation timestamp"
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Media expiration timestamp"
    )
    
    # Computed properties
    @property
    def is_expired(self) -> bool:
        """Check if media is expired."""
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False
    
    @property
    def aspect_ratio(self) -> Optional[float]:
        """Calculate aspect ratio for images/videos."""
        if self.width and self.height:
            return self.width / self.height
        return None
    
    class Config:
        """Model configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        } 