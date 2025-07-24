"""Media-related Pydantic schemas."""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from app.models.media import MediaType


class MediaResponse(BaseModel):
    """Response schema for media information."""
    
    id: UUID = Field(..., description="Media identifier")
    type: MediaType = Field(..., description="Media type")
    storage_url: str = Field(..., description="Public URL for accessing the media")
    storage_path: str = Field(..., description="Storage path or S3 key")
    
    # File information
    file_size_bytes: Optional[int] = Field(None, description="File size in bytes")
    mime_type: Optional[str] = Field(None, description="MIME type")
    file_extension: Optional[str] = Field(None, description="File extension")
    
    # Media properties
    width: Optional[int] = Field(None, description="Width in pixels")
    height: Optional[int] = Field(None, description="Height in pixels")
    duration_seconds: Optional[float] = Field(None, description="Duration in seconds")
    aspect_ratio: Optional[float] = Field(None, description="Aspect ratio")
    
    # Generation metadata
    generation_model_name: Optional[str] = Field(None, description="Model used for generation")
    generation_model_version: Optional[str] = Field(None, description="Model version")
    
    # Storage metadata
    storage_provider: str = Field(..., description="Storage provider")
    bucket_name: Optional[str] = Field(None, description="S3 bucket name")
    
    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")
    is_expired: bool = Field(..., description="Whether media is expired")
    
    # Additional metadata
    extra_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    
    model_config = ConfigDict(from_attributes=True) 