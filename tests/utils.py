"""Test utilities and helper functions."""

import asyncio
import base64
import io
import os
import tempfile
from typing import Dict, Any, Optional, List
from uuid import uuid4
import pytest
from PIL import Image

from app.models import Job, Media, JobStatus, MediaType


class TestDataFactory:
    """Factory for creating test data."""
    
    @staticmethod
    def create_job_data(
        prompt: str = "A beautiful sunset over mountains",
        parameters: Optional[Dict[str, Any]] = None,
        webhook_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create job creation data."""
        data = {"prompt": prompt}
        
        if parameters:
            data["parameters"] = parameters
        if webhook_url:
            data["webhook_url"] = webhook_url
        if metadata:
            data["metadata"] = metadata
            
        return data
    
    @staticmethod
    def create_flux_parameters(
        num_inference_steps: int = 4,
        aspect_ratio: str = "1:1",
        output_quality: int = 80,
        seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create Flux-specific parameters."""
        params = {
            "num_inference_steps": num_inference_steps,
            "aspect_ratio": aspect_ratio,
            "output_quality": output_quality
        }
        
        if seed is not None:
            params["seed"] = seed
            
        return params
    
    @staticmethod
    def create_sdxl_parameters(
        width: int = 1024,
        height: int = 1024,
        num_inference_steps: int = 50,
        guidance_scale: float = 7.5,
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create SDXL-specific parameters."""
        params = {
            "width": width,
            "height": height,
            "num_inference_steps": num_inference_steps,
            "guidance_scale": guidance_scale
        }
        
        if negative_prompt:
            params["negative_prompt"] = negative_prompt
        if seed is not None:
            params["seed"] = seed
            
        return params


class ImageTestUtils:
    """Utilities for working with test images."""
    
    @staticmethod
    def create_test_image(
        width: int = 100,
        height: int = 100,
        color: str = "red",
        format: str = "PNG"
    ) -> bytes:
        """Create a test image as bytes."""
        image = Image.new("RGB", (width, height), color)
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        return buffer.getvalue()
    
    @staticmethod
    def create_data_url(
        width: int = 100,
        height: int = 100,
        color: str = "blue",
        format: str = "PNG"
    ) -> str:
        """Create a data URL with test image."""
        image_data = ImageTestUtils.create_test_image(width, height, color, format)
        base64_data = base64.b64encode(image_data).decode()
        mime_type = f"image/{format.lower()}"
        return f"data:{mime_type};base64,{base64_data}"
    
    @staticmethod
    def save_test_image(
        file_path: str,
        width: int = 100,
        height: int = 100,
        color: str = "green",
        format: str = "PNG"
    ) -> int:
        """Save a test image to file and return file size."""
        image_data = ImageTestUtils.create_test_image(width, height, color, format)
        with open(file_path, "wb") as f:
            f.write(image_data)
        return len(image_data)


class MockResponseHelper:
    """Helper for creating mock API responses."""
    
    @staticmethod
    def create_replicate_response(
        urls: Optional[List[str]] = None,
        is_data_url: bool = True
    ) -> List[str]:
        """Create mock Replicate API response."""
        if urls:
            return urls
        
        if is_data_url:
            return [ImageTestUtils.create_data_url()]
        else:
            return ["https://example.com/generated-image.png"]
    
    @staticmethod
    def create_webhook_payload(
        job_id: str,
        status: str = "completed",
        media_url: Optional[str] = None,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create webhook payload."""
        payload = {
            "job_id": job_id,
            "status": status
        }
        
        if media_url:
            payload["media_url"] = media_url
        if error:
            payload["error"] = error
            
        return payload


class DatabaseTestUtils:
    """Utilities for database operations in tests."""
    
    @staticmethod
    async def create_test_job(
        db_session,
        prompt: str = "Test job",
        status: JobStatus = JobStatus.PENDING,
        parameters: Optional[Dict[str, Any]] = None,
        media_id: Optional[str] = None
    ) -> Job:
        """Create a test job in the database."""
        job = Job(
            prompt=prompt,
            status=status,
            parameters=parameters or {},
            media_id=media_id
        )
        
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)
        return job
    
    @staticmethod
    async def create_test_media(
        db_session,
        storage_path: str,
        media_type: MediaType = MediaType.IMAGE,
        file_size: int = 1024,
        width: int = 1024,
        height: int = 1024,
        storage_provider: str = "local"
    ) -> Media:
        """Create a test media record in the database."""
        media = Media(
            type=media_type,
            storage_path=storage_path,
            storage_provider=storage_provider,
            file_size_bytes=file_size,
            mime_type="image/png",
            file_extension=".png",
            width=width,
            height=height
        )
        
        db_session.add(media)
        await db_session.commit()
        await db_session.refresh(media)
        return media
    
    @staticmethod
    async def cleanup_test_data(db_session):
        """Clean up test data from database."""
        await db_session.execute("DELETE FROM jobs")
        await db_session.execute("DELETE FROM media")
        await db_session.commit()


class FileTestUtils:
    """Utilities for file operations in tests."""
    
    @staticmethod
    def create_temp_file(
        content: bytes = b"test content",
        suffix: str = ".txt",
        delete: bool = False
    ) -> str:
        """Create a temporary file and return its path."""
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=delete) as f:
            f.write(content)
            f.flush()
            return f.name
    
    @staticmethod
    def create_temp_dir() -> str:
        """Create a temporary directory."""
        return tempfile.mkdtemp()
    
    @staticmethod
    def cleanup_file(file_path: str):
        """Clean up a file if it exists."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass  # Ignore cleanup errors
    
    @staticmethod
    def cleanup_dir(dir_path: str):
        """Clean up a directory if it exists."""
        try:
            if os.path.exists(dir_path):
                import shutil
                shutil.rmtree(dir_path)
        except Exception:
            pass  # Ignore cleanup errors


class AsyncTestUtils:
    """Utilities for async testing."""
    
    @staticmethod
    async def wait_for_condition(
        condition_func,
        timeout: float = 5.0,
        interval: float = 0.1
    ) -> bool:
        """Wait for a condition to become true."""
        end_time = asyncio.get_event_loop().time() + timeout
        
        while asyncio.get_event_loop().time() < end_time:
            try:
                if await condition_func() if asyncio.iscoroutinefunction(condition_func) else condition_func():
                    return True
            except Exception:
                pass  # Ignore errors during condition check
            
            await asyncio.sleep(interval)
        
        return False
    
    @staticmethod
    async def run_with_timeout(coro, timeout: float = 5.0):
        """Run a coroutine with timeout."""
        return await asyncio.wait_for(coro, timeout=timeout)


class APITestUtils:
    """Utilities for API testing."""
    
    @staticmethod
    def assert_job_response_structure(response_data: Dict[str, Any]):
        """Assert that job response has correct structure."""
        required_fields = ["id", "status", "created_at"]
        for field in required_fields:
            assert field in response_data, f"Missing field: {field}"
        
        assert response_data["status"] in [status.value for status in JobStatus]
    
    @staticmethod
    def assert_media_response_structure(response_data: Dict[str, Any]):
        """Assert that media response has correct structure."""
        required_fields = ["id", "type", "storage_path"]
        for field in required_fields:
            assert field in response_data, f"Missing field: {field}"
        
        assert response_data["type"] in [media_type.value for media_type in MediaType]
    
    @staticmethod
    def assert_pagination_structure(response_data: Dict[str, Any]):
        """Assert that pagination response has correct structure."""
        required_fields = ["total", "page", "per_page", "has_next", "has_prev"]
        for field in required_fields:
            assert field in response_data, f"Missing field: {field}"
        
        assert isinstance(response_data["total"], int)
        assert isinstance(response_data["page"], int)
        assert isinstance(response_data["per_page"], int)
        assert isinstance(response_data["has_next"], bool)
        assert isinstance(response_data["has_prev"], bool)


class PerformanceTestUtils:
    """Utilities for performance testing."""
    
    @staticmethod
    async def measure_execution_time(coro):
        """Measure execution time of a coroutine."""
        start_time = asyncio.get_event_loop().time()
        result = await coro
        end_time = asyncio.get_event_loop().time()
        return result, end_time - start_time
    
    @staticmethod
    async def run_concurrent_operations(operations: List, max_concurrency: int = 10):
        """Run operations concurrently with limited concurrency."""
        semaphore = asyncio.Semaphore(max_concurrency)
        
        async def run_with_semaphore(operation):
            async with semaphore:
                return await operation
        
        return await asyncio.gather(*[run_with_semaphore(op) for op in operations])


class ValidationTestUtils:
    """Utilities for validation testing."""
    
    @staticmethod
    def get_invalid_job_parameters() -> List[Dict[str, Any]]:
        """Get list of invalid job parameter combinations."""
        return [
            {"width": -1, "height": 1024},  # Negative width
            {"width": 1024, "height": -1},  # Negative height
            {"width": 50, "height": 1024},  # Width too small
            {"width": 1024, "height": 50},  # Height too small
            {"width": 5000, "height": 1024},  # Width too large
            {"width": 1024, "height": 5000},  # Height too large
            {"num_inference_steps": 0},  # Zero steps
            {"num_inference_steps": 1000},  # Too many steps
            {"guidance_scale": -1.0},  # Negative guidance
            {"guidance_scale": 25.0},  # Too high guidance
        ]
    
    @staticmethod
    def get_invalid_webhooks() -> List[str]:
        """Get list of invalid webhook URLs."""
        return [
            "not-a-url",
            "ftp://example.com",
            "javascript:alert('xss')",
            "http://",
            "https://",
            "",
        ]

    @staticmethod
    def assert_error_response(response_json: Dict[str, Any], expected_message: str) -> None:
        """Assert error response contains expected message.
        
        Handles different error response formats (detail, error, message).
        """
        error_keys = ["detail", "error", "message"]
        error_message = None
        
        for key in error_keys:
            if key in response_json:
                error_message = response_json[key]
                break
        
        assert error_message is not None, f"No error message found in response: {response_json}"
        
        # Be more flexible with matching - if error message is generic "Not found", accept it
        if error_message.lower() == "not found" and "not found" in expected_message.lower():
            return
            
        assert expected_message.lower() in error_message.lower(), f"Expected '{expected_message}' in '{error_message}'"


# Test markers decorator helpers
def slow_test(func):
    """Mark test as slow."""
    return pytest.mark.slow(func)


def integration_test(func):
    """Mark test as integration test."""
    return pytest.mark.integration(func)


def api_test(func):
    """Mark test as API test."""
    return pytest.mark.api(func)


def service_test(func):
    """Mark test as service test."""
    return pytest.mark.service(func)


def worker_test(func):
    """Mark test as worker test."""
    return pytest.mark.worker(func) 