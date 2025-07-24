"""Tests for StorageService."""

import pytest
import os
import tempfile
from unittest.mock import patch, AsyncMock, MagicMock
from uuid import uuid4

from app.services.storage_service import StorageService
from app.core.config import Settings


class TestLocalStorage:
    """Test local storage functionality."""
    
    async def test_upload_file_local(self, mock_storage_service: StorageService, sample_image_data):
        """Test uploading file to local storage."""
        file_name = "test_upload.png"
        content_type = "image/png"
        
        storage_path, public_url = await mock_storage_service.upload_file(
            file_content=sample_image_data,
            file_name=file_name,
            content_type=content_type
        )
        
        assert storage_path is not None
        assert os.path.exists(storage_path)
        assert public_url is None  # Local storage doesn't have public URLs
        
        # Verify file content
        with open(storage_path, "rb") as f:
            content = f.read()
        assert content == sample_image_data
    
    async def test_download_file_local(self, mock_storage_service: StorageService, sample_image_data, temp_dir):
        """Test downloading file from local storage."""
        # First upload a file
        file_name = "test_download.png"
        storage_path, _ = await mock_storage_service.upload_file(
            file_content=sample_image_data,
            file_name=file_name
        )
        
        # Now download it
        file_stream, content_length = await mock_storage_service.download_file(storage_path)
        
        assert content_length == len(sample_image_data)
        
        # Read the stream
        downloaded_content = b""
        async for chunk in file_stream:
            downloaded_content += chunk
        
        assert downloaded_content == sample_image_data
    
    async def test_delete_file_local(self, mock_storage_service: StorageService, sample_image_data):
        """Test deleting file from local storage."""
        # Upload file first
        file_name = "test_delete.png"
        storage_path, _ = await mock_storage_service.upload_file(
            file_content=sample_image_data,
            file_name=file_name
        )
        
        assert os.path.exists(storage_path)
        
        # Delete file
        success = await mock_storage_service.delete_file(storage_path)
        
        assert success is True
        assert not os.path.exists(storage_path)
    
    async def test_file_exists_local(self, mock_storage_service: StorageService, sample_image_data):
        """Test checking file existence in local storage."""
        # Upload file first
        file_name = "test_exists.png"
        storage_path, _ = await mock_storage_service.upload_file(
            file_content=sample_image_data,
            file_name=file_name
        )
        
        # Check existence
        exists = await mock_storage_service.file_exists(storage_path)
        assert exists is True
        
        # Check non-existent file
        fake_path = "/non/existent/file.png"
        exists = await mock_storage_service.file_exists(fake_path)
        assert exists is False
    
    async def test_upload_with_subdirectories(self, mock_storage_service: StorageService, sample_image_data):
        """Test uploading file with subdirectory structure."""
        file_name = "subdir/nested/test.png"
        
        storage_path, _ = await mock_storage_service.upload_file(
            file_content=sample_image_data,
            file_name=file_name
        )
        
        assert os.path.exists(storage_path)
        assert "subdir/nested" in storage_path
    
    async def test_download_nonexistent_file_local(self, mock_storage_service: StorageService):
        """Test downloading non-existent file from local storage."""
        with pytest.raises(FileNotFoundError):
            await mock_storage_service.download_file("/non/existent/file.png")


class TestS3Storage:
    """Test S3 storage functionality."""
    
    @pytest.fixture
    def s3_settings(self, test_settings):
        """S3-specific test settings."""
        test_settings.storage_type = "s3"
        test_settings.s3_endpoint_url = "http://localhost:9000"
        test_settings.s3_access_key_id = "test_key"
        test_settings.s3_secret_access_key = "test_secret"
        test_settings.s3_bucket_name = "test-bucket"
        test_settings.s3_region = "us-east-1"
        test_settings.s3_use_ssl = False
        return test_settings
    
    @pytest.fixture
    def s3_storage_service(self, s3_settings):
        """Create S3 storage service."""
        return StorageService(s3_settings)
    
    async def test_upload_file_s3(self, s3_storage_service: StorageService, sample_image_data):
        """Test uploading file to S3."""
        with patch('aioboto3.Session') as mock_session:
            mock_s3_client = AsyncMock()
            mock_session.return_value.client.return_value.__aenter__.return_value = mock_s3_client
            
            file_name = "test_s3_upload.png"
            content_type = "image/png"
            
            storage_path, public_url = await s3_storage_service.upload_file(
                file_content=sample_image_data,
                file_name=file_name,
                content_type=content_type
            )
            
            assert storage_path == file_name
            assert public_url is not None
            assert "test-bucket" in public_url
            assert file_name in public_url
            
            # Verify S3 client was called correctly
            mock_s3_client.put_object.assert_called_once()
            call_args = mock_s3_client.put_object.call_args
            assert call_args[1]["Bucket"] == "test-bucket"
            assert call_args[1]["Key"] == file_name
            assert call_args[1]["Body"] == sample_image_data
            assert call_args[1]["ContentType"] == content_type
    
    async def test_download_file_s3(self, s3_storage_service: StorageService):
        """Test downloading file from S3."""
        with patch('aioboto3.Session') as mock_session:
            mock_s3_client = AsyncMock()
            mock_response = {
                "Body": AsyncMock(),
                "ContentLength": 1024
            }
            mock_response["Body"].__aiter__.return_value = [b"chunk1", b"chunk2"]
            mock_s3_client.get_object.return_value = mock_response
            mock_session.return_value.client.return_value.__aenter__.return_value = mock_s3_client
            
            file_path = "test_download.png"
            
            file_stream, content_length = await s3_storage_service.download_file(file_path)
            
            assert content_length == 1024
            
            # Read stream
            chunks = []
            async for chunk in file_stream:
                chunks.append(chunk)
            
            assert chunks == [b"chunk1", b"chunk2"]
            
            # Verify S3 client was called
            mock_s3_client.get_object.assert_called_once_with(
                Bucket="test-bucket",
                Key=file_path
            )
    
    async def test_delete_file_s3(self, s3_storage_service: StorageService):
        """Test deleting file from S3."""
        with patch('aioboto3.Session') as mock_session:
            mock_s3_client = AsyncMock()
            mock_session.return_value.client.return_value.__aenter__.return_value = mock_s3_client
            
            file_path = "test_delete.png"
            
            success = await s3_storage_service.delete_file(file_path)
            
            assert success is True
            
            # Verify S3 client was called
            mock_s3_client.delete_object.assert_called_once_with(
                Bucket="test-bucket",
                Key=file_path
            )
    
    async def test_file_exists_s3(self, s3_storage_service: StorageService):
        """Test checking file existence in S3."""
        with patch('aioboto3.Session') as mock_session:
            mock_s3_client = AsyncMock()
            mock_session.return_value.client.return_value.__aenter__.return_value = mock_s3_client
            
            file_path = "test_exists.png"
            
            exists = await s3_storage_service.file_exists(file_path)
            
            assert exists is True
            
            # Verify S3 client was called
            mock_s3_client.head_object.assert_called_once_with(
                Bucket="test-bucket",
                Key=file_path
            )
    
    async def test_s3_error_handling(self, s3_storage_service: StorageService, sample_image_data):
        """Test S3 error handling."""
        from botocore.exceptions import ClientError
        
        with patch('aioboto3.Session') as mock_session:
            mock_s3_client = AsyncMock()
            # Simulate S3 error
            mock_s3_client.put_object.side_effect = ClientError(
                {"Error": {"Code": "NoSuchBucket", "Message": "Bucket not found"}},
                "PutObject"
            )
            mock_session.return_value.client.return_value.__aenter__.return_value = mock_s3_client
            
            with pytest.raises(ClientError):
                await s3_storage_service.upload_file(
                    file_content=sample_image_data,
                    file_name="test.png"
                )


class TestStorageServiceInitialization:
    """Test storage service initialization."""
    
    def test_local_storage_initialization(self, temp_dir):
        """Test local storage service initialization."""
        settings = Settings(
            storage_type="local",
            storage_local_path=temp_dir
        )
        
        service = StorageService(settings)
        
        assert service.storage_type == "local"
        assert service.local_path.exists()
    
    def test_s3_storage_initialization(self):
        """Test S3 storage service initialization."""
        settings = Settings(
            storage_type="s3",
            s3_endpoint_url="http://localhost:9000",
            s3_access_key_id="test_key",
            s3_secret_access_key="test_secret",
            s3_bucket_name="test-bucket"
        )
        
        service = StorageService(settings)
        
        assert service.storage_type == "s3"


class TestStorageServiceEdgeCases:
    """Test edge cases and error conditions."""
    
    async def test_empty_file_upload(self, mock_storage_service: StorageService):
        """Test uploading empty file."""
        empty_content = b""
        file_name = "empty_file.txt"
        
        storage_path, public_url = await mock_storage_service.upload_file(
            file_content=empty_content,
            file_name=file_name
        )
        
        assert os.path.exists(storage_path)
        
        # Verify file is empty
        with open(storage_path, "rb") as f:
            content = f.read()
        assert content == empty_content
    
    async def test_large_file_simulation(self, mock_storage_service: StorageService):
        """Test handling of larger files."""
        # Create a larger content (1MB)
        large_content = b"x" * (1024 * 1024)
        file_name = "large_file.bin"
        
        storage_path, _ = await mock_storage_service.upload_file(
            file_content=large_content,
            file_name=file_name
        )
        
        assert os.path.exists(storage_path)
        
        # Verify download works for large files
        file_stream, content_length = await mock_storage_service.download_file(storage_path)
        
        assert content_length == len(large_content)
        
        # Read in chunks
        downloaded_content = b""
        async for chunk in file_stream:
            downloaded_content += chunk
        
        assert len(downloaded_content) == len(large_content)
    
    async def test_unicode_filename_handling(self, mock_storage_service: StorageService, sample_image_data):
        """Test handling of Unicode filenames."""
        unicode_filename = "tëst_ümläuts_你好.png"
        
        storage_path, _ = await mock_storage_service.upload_file(
            file_content=sample_image_data,
            file_name=unicode_filename
        )
        
        assert os.path.exists(storage_path)
        
        # Should be able to download using the same path
        file_stream, content_length = await mock_storage_service.download_file(storage_path)
        assert content_length == len(sample_image_data)
    
    async def test_special_characters_in_path(self, mock_storage_service: StorageService, sample_image_data):
        """Test handling of special characters in file paths."""
        special_filename = "test file with spaces & symbols!@#.png"
        
        storage_path, _ = await mock_storage_service.upload_file(
            file_content=sample_image_data,
            file_name=special_filename
        )
        
        assert os.path.exists(storage_path)
    
    async def test_delete_nonexistent_file(self, mock_storage_service: StorageService):
        """Test deleting non-existent file."""
        fake_path = "/completely/fake/path.png"
        
        # Should return False but not raise exception
        success = await mock_storage_service.delete_file(fake_path)
        assert success is False
    
    async def test_concurrent_file_operations(self, mock_storage_service: StorageService, sample_image_data):
        """Test concurrent file operations."""
        import asyncio
        
        async def upload_file(index):
            return await mock_storage_service.upload_file(
                file_content=sample_image_data,
                file_name=f"concurrent_test_{index}.png"
            )
        
        # Run multiple uploads concurrently
        results = await asyncio.gather(*[upload_file(i) for i in range(5)])
        
        # All should succeed
        assert len(results) == 5
        for storage_path, public_url in results:
            assert os.path.exists(storage_path) 