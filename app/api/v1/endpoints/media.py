"""Media endpoints for accessing generated files."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import get_session
from app.models import Media
from app.schemas.media import MediaResponse
from app.services.storage_service import StorageService
from app.core.config import get_settings, Settings
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/{media_id}/info", response_model=MediaResponse)
async def get_media_info(
    media_id: UUID,
    db: AsyncSession = Depends(get_session)
) -> MediaResponse:
    """Get metadata information about a media file."""
    # Query media
    stmt = select(Media).where(Media.id == media_id)
    result = await db.execute(stmt)
    media = result.scalar_one_or_none()
    
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
    
    return MediaResponse.model_validate(media)


@router.get("/{media_id}")
async def get_media_file(
    media_id: UUID,
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings)
):
    """Retrieve the actual media file.
    
    For local storage or private S3, this streams the file content.
    """
    # Query media
    stmt = select(Media).where(Media.id == media_id)
    result = await db.execute(stmt)
    media = result.scalar_one_or_none()
    
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
    
    # Check if media is expired
    if media.is_expired:
        raise HTTPException(status_code=410, detail="Media has expired")
    
    # If we have a public URL, redirect to it
    if media.storage_url and media.storage_provider == "s3":
        return RedirectResponse(url=media.storage_url, status_code=302)
    
    # Otherwise, stream the file from storage
    try:
        storage_service = StorageService(settings)
        
        # Debug logging
        logger.info(
            "Storage configuration",
            storage_type=settings.storage_type,
            storage_local_path=settings.storage_local_path,
            media_path=media.storage_path,
            media_provider=media.storage_provider
        )
        
        # Get file stream
        file_stream, content_length = await storage_service.download_file(
            media.storage_path,
            media.bucket_name
        )
        
        # Determine content type
        content_type = media.mime_type or "application/octet-stream"
        
        # Return streaming response
        return StreamingResponse(
            file_stream,
            media_type=content_type,
            headers={
                "Content-Length": str(content_length) if content_length else None,
                "Content-Disposition": f'inline; filename="{media.id}{media.file_extension or ""}"',
                "Cache-Control": "public, max-age=3600"
            }
        )
        
    except FileNotFoundError:
        logger.error("Media file not found in storage", media_id=media_id, path=media.storage_path)
        raise HTTPException(status_code=404, detail="Media file not found in storage")
    except Exception as e:
        logger.error("Failed to retrieve media file", error=str(e), media_id=media_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve media file")


@router.delete("/{media_id}", status_code=204)
async def delete_media(
    media_id: UUID,
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings)
) -> None:
    """Delete a media file and its metadata.
    
    This permanently deletes both the file from storage and the database record.
    """
    # Query media
    stmt = select(Media).where(Media.id == media_id)
    result = await db.execute(stmt)
    media = result.scalar_one_or_none()
    
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
    
    try:
        # Delete from storage
        storage_service = StorageService(settings)
        await storage_service.delete_file(
            media.storage_path,
            media.bucket_name
        )
        
        # Delete from database
        await db.delete(media)
        await db.commit()
        
        logger.info("Media deleted successfully", media_id=media_id)
        
    except Exception as e:
        logger.error("Failed to delete media", error=str(e), media_id=media_id)
        raise HTTPException(status_code=500, detail="Failed to delete media") 