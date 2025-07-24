"""Tests for media API endpoints."""

import pytest
from unittest.mock import patch, AsyncMock
from uuid import uuid4
import tempfile
import os
from httpx import AsyncClient

from app.models import MediaType, Media
from tests.utils import ValidationTestUtils


class TestMediaInfo:
    """Test media info endpoint."""
    
    async def test_get_media_info_success(self, client: AsyncClient, sample_media):
        """Test successful media info retrieval."""
        response = await client.get(f"/api/v1/media/{sample_media.id}/info")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == str(sample_media.id)
        assert data["type"] == "image"
        assert data["storage_path"] == sample_media.storage_path
        assert data["file_size_bytes"] == sample_media.file_size_bytes
        assert data["mime_type"] == sample_media.mime_type
        assert data["width"] == sample_media.width
        assert data["height"] == sample_media.height
    
    async def test_get_media_info_not_found(self, client: AsyncClient):
        """Test getting info for non-existent media."""
        fake_id = uuid4()
        response = await client.get(f"/api/v1/media/{fake_id}/info")
        assert response.status_code == 404
        ValidationTestUtils.assert_error_response(response.json(), "Media not found")
    
    async def test_get_media_info_invalid_uuid(self, client: AsyncClient):
        """Test media info with invalid UUID."""
        response = await client.get("/api/v1/media/invalid-uuid/info")
        
        assert response.status_code == 422


class TestMediaFile:
    """Test media file serving endpoint."""
    
    async def test_get_media_file_local_storage(self, client: AsyncClient, db_session, temp_dir, sample_image_data):
        """Test serving media from local storage."""
        # Create media file
        file_path = os.path.join(temp_dir, "test_image.png")
        with open(file_path, "wb") as f:
            f.write(sample_image_data)
        
        # Create media record
        media = Media(
            type=MediaType.IMAGE,
            storage_path=file_path,
            storage_provider="local",
            file_size_bytes=len(sample_image_data),
            mime_type="image/png"
        )
        db_session.add(media)
        await db_session.commit()
        
        response = await client.get(f"/api/v1/media/{media.id}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        # Content-length might not be set in streaming responses
        assert response.content == sample_image_data
    
    async def test_get_media_file_s3_redirect(self, client: AsyncClient, db_session, temp_dir):
        """Test redirect for S3-stored media with public URL."""
        # Create media with S3 storage and public URL
        
        media = Media(
            type=MediaType.IMAGE,
            storage_path="generated/test.png",
            storage_url="https://s3.example.com/bucket/test.png",
            storage_provider="s3",
            file_size_bytes=1024,
            mime_type="image/png",
            file_extension=".png",
            width=1024,
            height=1024
        )
        
        db_session.add(media)
        await db_session.commit()
        await db_session.refresh(media)
        
        response = await client.get(f"/api/v1/media/{media.id}", follow_redirects=False)
        
        assert response.status_code == 302
        assert response.headers["location"] == media.storage_url
    
    async def test_get_media_file_not_found(self, client: AsyncClient):
        """Test getting non-existent media file."""
        fake_id = uuid4()
        response = await client.get(f"/api/v1/media/{fake_id}")
        assert response.status_code == 404
        ValidationTestUtils.assert_error_response(response.json(), "Media not found")
    
    async def test_get_media_file_storage_not_found(self, client: AsyncClient, db_session):
        """Test getting media file when storage file is missing."""
        # Create media record without actual file
        media = Media(
            type=MediaType.IMAGE,
            storage_path="/non/existent/path.png",
            storage_provider="local",
            file_size_bytes=1024,
            mime_type="image/png"
        )
        db_session.add(media)
        await db_session.commit()
        
        response = await client.get(f"/api/v1/media/{media.id}")
        assert response.status_code == 404
        ValidationTestUtils.assert_error_response(response.json(), "not found in storage")
    
    async def test_get_expired_media(self, client: AsyncClient, db_session, temp_dir):
        """Test serving expired media."""
        from datetime import datetime, timedelta
        
        # Create expired media
        media = Media(
            type=MediaType.IMAGE,
            storage_path=f"{temp_dir}/expired.png",
            storage_provider="local",
            file_size_bytes=1024,
            mime_type="image/png",
            expires_at=datetime.utcnow() - timedelta(hours=1)  # Expired 1 hour ago
        )
        
        db_session.add(media)
        await db_session.commit()
        await db_session.refresh(media)
        
        response = await client.get(f"/api/v1/media/{media.id}")
        
        assert response.status_code == 410
        data = response.json()
        assert data["detail"] == "Media has expired"


class TestMediaDeletion:
    """Test media deletion endpoint."""
    
    async def test_delete_media_success(self, client: AsyncClient, sample_media, temp_dir, sample_image_data):
        """Test successful media deletion."""
        # Create actual file
        file_path = os.path.join(temp_dir, "test_delete.png")
        with open(file_path, "wb") as f:
            f.write(sample_image_data)
        
        sample_media.storage_path = file_path
        
        response = await client.delete(f"/api/v1/media/{sample_media.id}")
        
        assert response.status_code == 204
        
        # Verify media record is deleted
        info_response = await client.get(f"/api/v1/media/{sample_media.id}/info")
        assert info_response.status_code == 404
        
        # Verify file is deleted
        assert not os.path.exists(file_path)
    
    async def test_delete_media_not_found(self, client: AsyncClient):
        """Test deleting non-existent media."""
        fake_id = uuid4()
        response = await client.delete(f"/api/v1/media/{fake_id}")
        assert response.status_code == 404
        ValidationTestUtils.assert_error_response(response.json(), "Media not found")
    
    async def test_delete_media_storage_error(self, client: AsyncClient, sample_media):
        """Test media deletion when storage deletion fails."""
        # Mock storage service to raise exception
        with patch('app.api.v1.endpoints.media.StorageService') as mock_storage_class:
            mock_storage = mock_storage_class.return_value
            mock_storage.delete_file.side_effect = Exception("Storage error")
            
            response = await client.delete(f"/api/v1/media/{sample_media.id}")
        
        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Failed to delete media"


class TestMediaEndpointsIntegration:
    """Integration tests for media endpoints."""
    
    async def test_media_workflow(self, client: AsyncClient, db_session, temp_dir, sample_image_data):
        """Test complete media workflow: create, get info, serve, delete."""
        from app.models import Media
        
        # Create media with file
        file_path = os.path.join(temp_dir, "workflow_test.png")
        with open(file_path, "wb") as f:
            f.write(sample_image_data)
        
        media = Media(
            type=MediaType.IMAGE,
            storage_path=file_path,
            storage_provider="local",
            file_size_bytes=len(sample_image_data),
            mime_type="image/png",
            file_extension=".png",
            width=1024,
            height=1024
        )
        
        db_session.add(media)
        await db_session.commit()
        await db_session.refresh(media)
        
        # Get media info
        info_response = await client.get(f"/api/v1/media/{media.id}/info")
        assert info_response.status_code == 200
        
        # Serve media file
        file_response = await client.get(f"/api/v1/media/{media.id}")
        assert file_response.status_code == 200
        assert file_response.content == sample_image_data
        
        # Delete media
        delete_response = await client.delete(f"/api/v1/media/{media.id}")
        assert delete_response.status_code == 204
        
        # Verify deletion
        final_info_response = await client.get(f"/api/v1/media/{media.id}/info")
        assert final_info_response.status_code == 404


class TestMediaCaching:
    """Test media caching headers."""
    
    async def test_media_cache_headers(self, client: AsyncClient, sample_media, temp_dir, sample_image_data):
        """Test that appropriate cache headers are set."""
        # Create actual file
        file_path = os.path.join(temp_dir, "cache_test.png")
        with open(file_path, "wb") as f:
            f.write(sample_image_data)
        
        sample_media.storage_path = file_path
        
        response = await client.get(f"/api/v1/media/{sample_media.id}")
        
        assert response.status_code == 200
        assert "cache-control" in response.headers
        assert "public" in response.headers["cache-control"]
        assert "max-age" in response.headers["cache-control"]


class TestMediaContentTypes:
    """Test various media content types."""
    
    async def test_different_image_formats(self, client: AsyncClient, db_session, temp_dir):
        """Test serving different image formats."""
        from app.models import Media
        
        formats = [
            ("image/jpeg", ".jpg"),
            ("image/png", ".png"),
            ("image/webp", ".webp")
        ]
        
        for mime_type, extension in formats:
            # Create a simple file
            file_path = os.path.join(temp_dir, f"test{extension}")
            with open(file_path, "wb") as f:
                f.write(b"fake image data")
            
            media = Media(
                type=MediaType.IMAGE,
                storage_path=file_path,
                storage_provider="local",
                file_size_bytes=15,
                mime_type=mime_type,
                file_extension=extension
            )
            
            db_session.add(media)
            await db_session.commit()
            await db_session.refresh(media)
            
            response = await client.get(f"/api/v1/media/{media.id}")
            
            assert response.status_code == 200
            assert response.headers["content-type"] == mime_type
            
            # Cleanup
            await db_session.delete(media)
            await db_session.commit() 