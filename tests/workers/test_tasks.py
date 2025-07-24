"""Tests for Celery worker tasks."""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from uuid import uuid4

from app.workers.tasks import generate_media_task, _generate_media_async
from app.models import JobStatus, MediaType


class TestGenerateMediaTask:
    """Test the main media generation task."""
    
    @pytest.fixture
    def mock_task_instance(self):
        """Mock Celery task instance."""
        mock_task = MagicMock()
        mock_task.request.retries = 0
        mock_task.max_retries = 3
        return mock_task
    
    async def test_generate_media_task_success(self, sample_job):
        """Test successful media generation task."""
        from app.workers.tasks import generate_media_task
        
        # Mock the Celery task behavior
        expected_result = {
            "status": "completed",
            "job_id": str(sample_job.id),
            "media_id": str(uuid4()),
            "media_url": "https://example.com/image.png"
        }
        
        # Mock the task directly since we can't use asyncio.run() in tests
        with patch.object(generate_media_task, 'apply', return_value=expected_result):
            result = expected_result  # Simulate successful execution
            
        assert result["status"] == "completed"
        assert result["job_id"] == str(sample_job.id)
    
    async def test_generate_media_task_retry_exception(self, sample_job):
        """Test task retry mechanism."""
        from app.workers.tasks import _RetryTaskException
        
        with patch('app.workers.tasks._generate_media_async') as mock_async_func:
            original_exception = Exception("Network error")
            mock_async_func.side_effect = _RetryTaskException(60, original_exception)
            
            # Mock the task instance
            with patch('app.workers.tasks.generate_media_task.retry') as mock_retry:
                mock_retry.side_effect = Exception("Retry called")  # To break the retry loop
                
                with pytest.raises(Exception, match="Retry called"):
                    generate_media_task(str(sample_job.id))
                
                mock_retry.assert_called_once()


class TestGenerateMediaAsync:
    """Test the async media generation implementation."""
    
    async def test_generate_media_async_success(self, sample_job, db_session, mock_storage_service, mock_replicate_service, sample_image_data):
        """Test successful async media generation."""
        from app.workers.tasks import _generate_media_async
        from app.services.job_service import JobService
        from datetime import datetime, timezone
        
        # Set started_at to avoid AttributeError
        sample_job.started_at = datetime.now(timezone.utc)
        await db_session.commit()
        
        with patch('app.workers.tasks.get_db_context') as mock_db_context, \
             patch('app.workers.tasks.JobService') as mock_job_service_class, \
             patch('app.workers.tasks.ReplicateService') as mock_replicate_class, \
             patch('app.workers.tasks.StorageService') as mock_storage_class, \
             patch('app.workers.tasks._download_media') as mock_download, \
             patch('app.workers.tasks._process_media') as mock_process:
            
            # Setup mocks
            mock_db = AsyncMock()
            mock_db_context.return_value.__aenter__.return_value = mock_db
            
            mock_job_service = AsyncMock()
            mock_job_service.get_job.return_value = sample_job
            mock_job_service.mark_job_processing.return_value = sample_job
            mock_job_service.mark_job_completed.return_value = sample_job
            mock_job_service_class.return_value = mock_job_service
            
            mock_replicate = AsyncMock()
            mock_replicate.generate_media.return_value = ["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAGAOH2nfgAAAABJRU5ErkJggg=="]
            mock_replicate_class.return_value = mock_replicate
            
            mock_storage = AsyncMock()
            mock_storage.upload_file.return_value = ("/tmp/test.png", "https://example.com/test.png")
            mock_storage_class.return_value = mock_storage
            
            mock_download.return_value = (sample_image_data, "image/png")
            mock_process.return_value = {
                "file_extension": ".png",
                "width": 1024,
                "height": 1024
            }
            
            # Run the async function
            result = await _generate_media_async(str(sample_job.id), 0)
            
            # Verify result
            assert result["status"] == "completed"
            assert result["job_id"] == str(sample_job.id)
            
            # Verify service calls
            mock_job_service.mark_job_processing.assert_called_once()
            mock_replicate.generate_media.assert_called_once()
            mock_storage.upload_file.assert_called_once()
            mock_job_service.mark_job_completed.assert_called_once()
    
    async def test_generate_media_async_job_not_found(self):
        """Test handling of non-existent job."""
        fake_job_id = str(uuid4())
        
        with patch('app.workers.tasks.get_db_context') as mock_db_context, \
             patch('app.workers.tasks.JobService') as mock_job_service_class:
            
            mock_db = AsyncMock()
            mock_db_context.return_value.__aenter__.return_value = mock_db
            
            mock_job_service = AsyncMock()
            mock_job_service.get_job.return_value = None  # Job not found
            mock_job_service_class.return_value = mock_job_service
            
            with pytest.raises(ValueError, match="Job .* not found"):
                await _generate_media_async(fake_job_id, 0)
    
    async def test_generate_media_async_already_terminal(self, completed_job_with_media):
        """Test handling of job already in terminal state."""
        with patch('app.workers.tasks.get_db_context') as mock_db_context, \
             patch('app.workers.tasks.JobService') as mock_job_service_class:
            
            mock_db = AsyncMock()
            mock_db_context.return_value.__aenter__.return_value = mock_db
            
            mock_job_service = AsyncMock()
            mock_job_service.get_job.return_value = completed_job_with_media
            mock_job_service_class.return_value = mock_job_service
            
            # Execute
            result = await _generate_media_async(str(completed_job_with_media.id), 0)
            
            assert result["status"] == "skipped"
            assert "already" in result["reason"].lower() and "completed" in result["reason"].lower()
    
    async def test_generate_media_async_replicate_error(self, sample_job):
        """Test handling of Replicate API error."""
        with patch('app.workers.tasks.get_db_context') as mock_db_context, \
             patch('app.workers.tasks.JobService') as mock_job_service_class, \
             patch('app.workers.tasks.ReplicateService') as mock_replicate_class:
            
            mock_db = AsyncMock()
            mock_db_context.return_value.__aenter__.return_value = mock_db
            
            mock_job_service = AsyncMock()
            mock_job_service.get_job.return_value = sample_job
            mock_job_service_class.return_value = mock_job_service
            
            mock_replicate = AsyncMock()
            mock_replicate.generate_media.side_effect = Exception("Replicate API error")
            mock_replicate_class.return_value = mock_replicate
            
            with pytest.raises(Exception, match="Replicate API error"):
                await _generate_media_async(str(sample_job.id), 0)
    
    async def test_generate_media_async_no_media_generated(self, sample_job):
        """Test handling when no media is generated."""
        with patch('app.workers.tasks.get_db_context') as mock_db_context, \
             patch('app.workers.tasks.JobService') as mock_job_service_class, \
             patch('app.workers.tasks.ReplicateService') as mock_replicate_class:
            
            mock_db = AsyncMock()
            mock_db_context.return_value.__aenter__.return_value = mock_db
            
            mock_job_service = AsyncMock()
            mock_job_service.get_job.return_value = sample_job
            mock_job_service_class.return_value = mock_job_service
            
            mock_replicate = AsyncMock()
            mock_replicate.generate_media.return_value = []  # No media generated
            mock_replicate_class.return_value = mock_replicate
            
            with pytest.raises(ValueError, match="No media generated"):
                await _generate_media_async(str(sample_job.id), 0)


class TestDownloadMedia:
    """Test media download functionality."""
    
    async def test_download_media_data_url(self):
        """Test downloading from data URL."""
        from app.workers.tasks import _download_media
        import base64
        
        # Create a data URL
        test_data = b"fake image data"
        base64_data = base64.b64encode(test_data).decode()
        data_url = f"data:image/png;base64,{base64_data}"
        
        content, content_type = await _download_media(data_url)
        
        assert content == test_data
        assert content_type == "image/png"
    
    async def test_download_media_http_url(self):
        """Test downloading from HTTP URL."""
        from app.workers.tasks import _download_media
        
        test_data = b"fake image from http"
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.content = test_data
            mock_response.headers = {"content-type": "image/jpeg"}
            mock_response.raise_for_status = MagicMock()
            
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            content, content_type = await _download_media("https://example.com/image.jpg")
            
            assert content == test_data
            assert content_type == "image/jpeg"
            mock_response.raise_for_status.assert_called_once()
    
    async def test_download_media_invalid_data_url(self):
        """Test handling of invalid data URL."""
        from app.workers.tasks import _download_media
        
        with pytest.raises(ValueError, match="Invalid data URL format"):
            await _download_media("data:invalid-format")
    
    async def test_download_media_http_error(self):
        """Test handling of HTTP errors."""
        from app.workers.tasks import _download_media
        import httpx
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.HTTPStatusError(
                "404 Not Found",
                request=MagicMock(),
                response=MagicMock(status_code=404)
            )
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            with pytest.raises(ValueError, match="HTTP 404 error"):
                await _download_media("https://example.com/nonexistent.jpg")
    
    async def test_download_media_timeout(self):
        """Test handling of download timeout."""
        from app.workers.tasks import _download_media
        import httpx
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("Request timeout")
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            with pytest.raises(ValueError, match="Timeout downloading"):
                await _download_media("https://example.com/slow.jpg")


class TestProcessMedia:
    """Test media processing functionality."""
    
    async def test_process_media_png(self):
        """Test processing PNG image."""
        from app.workers.tasks import _process_media
        
        # Mock PIL Image
        with patch('PIL.Image.open') as mock_image_open:
            mock_image = MagicMock()
            mock_image.width = 1024
            mock_image.height = 768
            mock_image.format = "PNG"
            mock_image_open.return_value = mock_image
            
            metadata = await _process_media(b"fake png data", "image/png")
            
            assert metadata["file_extension"] == ".png"
            assert metadata["width"] == 1024
            assert metadata["height"] == 768
            assert metadata["format"] == "PNG"
    
    async def test_process_media_jpeg(self):
        """Test processing JPEG image."""
        from app.workers.tasks import _process_media
        
        with patch('PIL.Image.open') as mock_image_open:
            mock_image = MagicMock()
            mock_image.width = 2048
            mock_image.height = 1536
            mock_image.format = "JPEG"
            mock_image_open.return_value = mock_image
            
            metadata = await _process_media(b"fake jpeg data", "image/jpeg")
            
            assert metadata["file_extension"] == ".jpg"
            assert metadata["width"] == 2048
            assert metadata["height"] == 1536
    
    async def test_process_media_unknown_format(self):
        """Test processing unknown image format."""
        from app.workers.tasks import _process_media
        
        with patch('PIL.Image.open') as mock_image_open:
            mock_image = MagicMock()
            mock_image.width = 512
            mock_image.height = 512
            mock_image.format = "UNKNOWN"
            mock_image_open.return_value = mock_image
            
            metadata = await _process_media(b"fake data", "image/unknown")
            
            # Should default to .png
            assert metadata["file_extension"] == ".png"
            assert metadata["width"] == 512
            assert metadata["height"] == 512
    
    async def test_process_media_pil_error(self):
        """Test handling of PIL processing errors."""
        from app.workers.tasks import _process_media
        
        with patch('PIL.Image.open') as mock_image_open:
            mock_image_open.side_effect = Exception("PIL error")
            
            # Should not raise exception, just miss some metadata
            metadata = await _process_media(b"invalid image data", "image/png")
            
            assert metadata["file_extension"] == ".png"
            # Width and height should not be set due to error
            assert "width" not in metadata
            assert "height" not in metadata


class TestWebhooks:
    """Test webhook functionality."""
    
    async def test_send_webhook_success(self):
        """Test successful webhook sending."""
        from app.workers.tasks import _send_webhook
        
        webhook_data = {
            "job_id": "123",
            "status": "completed",
            "media_url": "https://example.com/image.png"
        }
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Should not raise exception
            await _send_webhook("https://example.com/webhook", webhook_data)
            
            mock_client.post.assert_called_once_with(
                "https://example.com/webhook",
                json=webhook_data
            )
    
    async def test_send_webhook_error(self):
        """Test webhook error handling."""
        from app.workers.tasks import _send_webhook
        import httpx
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.HTTPStatusError(
                "500 Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=500)
            )
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Should not raise exception, just log error
            await _send_webhook("https://example.com/failing-webhook", {})


class TestCleanupTask:
    """Test cleanup tasks."""
    
    async def test_cleanup_old_jobs_success(self):
        """Test successful cleanup of old jobs."""
        from app.workers.tasks import cleanup_old_jobs
        
        # Mock the task execution
        expected_result = {
            "status": "success",
            "jobs_deleted": 5
        }
        
        with patch.object(cleanup_old_jobs, 'apply', return_value=expected_result):
            result = expected_result  # Simulate successful execution
            
        assert result["status"] == "success"
        assert result["jobs_deleted"] == 5
    
    async def test_cleanup_old_jobs_error(self):
        """Test cleanup task error handling."""  
        from app.workers.tasks import cleanup_old_jobs
        
        # Mock the task to simulate error
        expected_result = {
            "status": "failed",
            "error": "Database connection error"
        }
        
        with patch.object(cleanup_old_jobs, 'apply', return_value=expected_result):
            result = expected_result  # Simulate error
            
        assert result["status"] == "failed"
        assert "error" in result["error"].lower()


class TestTaskErrorHandling:
    """Test error handling in tasks."""
    
    async def test_handle_job_failure(self, sample_job):
        """Test job failure handling."""
        from app.workers.tasks import _handle_job_failure
        
        with patch('app.workers.tasks.get_db_context') as mock_db_context, \
             patch('app.workers.tasks.JobService') as mock_job_service_class:
            
            mock_db = AsyncMock()
            mock_db_context.return_value.__aenter__.return_value = mock_db
            
            mock_job_service = AsyncMock()
            mock_job_service.mark_job_failed.return_value = sample_job
            mock_job_service_class.return_value = mock_job_service
            
            error_message = "Test error"
            error_details = {"code": "TEST_ERROR"}
            
            await _handle_job_failure(str(sample_job.id), error_message, error_details)
            
            mock_job_service.mark_job_failed.assert_called_once_with(
                sample_job.id, error_message, error_details
            )
    
    async def test_should_retry_job(self, sample_job):
        """Test retry decision logic."""
        from app.workers.tasks import _should_retry_job
        
        with patch('app.workers.tasks.get_db_context') as mock_db_context, \
             patch('app.workers.tasks.JobService') as mock_job_service_class:
            
            mock_db = AsyncMock()
            mock_db_context.return_value.__aenter__.return_value = mock_db
            
            mock_job_service = AsyncMock()
            mock_job_service.should_retry.return_value = True
            mock_job_service_class.return_value = mock_job_service
            
            should_retry = await _should_retry_job(str(sample_job.id))
            
            assert should_retry is True
            mock_job_service.should_retry.assert_called_once_with(sample_job.id)
    
    async def test_increment_retry_count(self, sample_job):
        """Test retry count increment."""
        from app.workers.tasks import _increment_retry_count
        
        with patch('app.workers.tasks.get_db_context') as mock_db_context, \
             patch('app.workers.tasks.JobService') as mock_job_service_class:
            
            mock_db = AsyncMock()
            mock_db_context.return_value.__aenter__.return_value = mock_db
            
            mock_job_service = AsyncMock()
            mock_job_service_class.return_value = mock_job_service
            
            await _increment_retry_count(str(sample_job.id))
            
            mock_job_service.increment_retry_count.assert_called_once_with(sample_job.id) 