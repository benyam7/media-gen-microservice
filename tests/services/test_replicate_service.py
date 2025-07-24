"""Tests for ReplicateService."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import asyncio

from app.services.replicate_service import ReplicateService
from app.core.config import Settings


class TestReplicateServiceInitialization:
    """Test Replicate service initialization."""
    
    def test_init_with_api_token(self):
        """Test initialization with API token."""
        settings = Settings(
            replicate_api_token="test-token-123",
            replicate_model="black-forest-labs/flux-schnell",
            replicate_timeout=300
        )
        
        service = ReplicateService(settings)
        
        assert service.api_token == "test-token-123"
        assert service.model == "black-forest-labs/flux-schnell"
        assert service.timeout == 300
    
    def test_init_without_api_token(self):
        """Test initialization without API token."""
        settings = Settings(
            replicate_api_token="",
            app_env="development"
        )
        
        service = ReplicateService(settings)
        
        assert service.api_token == ""


class TestMockMode:
    """Test mock mode functionality."""
    
    @pytest.fixture
    def mock_service(self):
        """Create service in mock mode."""
        settings = Settings(
            replicate_api_token="",  # No token = mock mode
            app_env="development"
        )
        return ReplicateService(settings)
    
    async def test_mock_generate_media_basic(self, mock_service: ReplicateService):
        """Test basic mock media generation."""
        prompt = "A beautiful sunset over mountains"
        
        urls = await mock_service.generate_media(prompt)
        
        assert len(urls) == 1
        assert urls[0].startswith("data:image/png;base64,")
    
    async def test_mock_generate_media_with_parameters(self, mock_service: ReplicateService):
        """Test mock generation with parameters."""
        prompt = "A beautiful landscape"
        parameters = {
            "width": 512,
            "height": 768,
            "num_inference_steps": 4
        }
        
        urls = await mock_service.generate_media(prompt, parameters)
        
        assert len(urls) == 1
        assert urls[0].startswith("data:image/png;base64,")
    
    async def test_mock_timing(self, mock_service):
        """Test that mock service simulates delay."""
        import time
        
        start = time.time()
        result = await mock_service.generate_media("Test prompt")
        duration = time.time() - start
        
        assert len(result) > 0
        assert 4 < duration < 7  # Allow more variance for slower systems
    
    async def test_mock_cancel_prediction(self, mock_service: ReplicateService):
        """Test mock prediction cancellation."""
        result = await mock_service.cancel_prediction("fake-prediction-id")
        assert result is True


class TestRealAPIMode:
    """Test real API mode functionality."""
    
    @pytest.fixture
    def api_service(self):
        """Create service with API token."""
        settings = Settings(
            replicate_api_token="test-api-token-123",
            replicate_model="black-forest-labs/flux-schnell",
            app_env="production"
        )
        return ReplicateService(settings)
    
    async def test_real_api_generate_media(self, api_service: ReplicateService):
        """Test real API media generation."""
        with patch('replicate.run') as mock_replicate_run:
            mock_replicate_run.return_value = ["https://example.com/generated-image.png"]
            
            prompt = "A beautiful sunset"
            parameters = {"num_inference_steps": 4}
            
            urls = await api_service.generate_media(prompt, parameters)
            
            assert urls == ["https://example.com/generated-image.png"]
            
            # Verify replicate.run was called correctly
            mock_replicate_run.assert_called_once()
            call_args = mock_replicate_run.call_args
            assert call_args[0][0] == "black-forest-labs/flux-schnell"  # model
            assert call_args[1]["input"]["prompt"] == prompt
    
    async def test_real_api_with_parameter_cleaning(self, api_service: ReplicateService):
        """Test parameter cleaning for specific models."""
        with patch('replicate.run') as mock_replicate_run:
            mock_replicate_run.return_value = ["https://example.com/image.png"]
            
            # Test Flux-specific parameter cleaning
            parameters = {
                "num_inference_steps": 10,  # Should be capped at 4 for Flux
                "width": 1024,  # Should be removed for Flux
                "height": 1024,  # Should be removed for Flux
                "aspect_ratio": "16:9",  # Should be kept for Flux
                "seed": 12345  # Should be kept
            }
            
            await api_service.generate_media("Test prompt", parameters)
            
            # Check the cleaned parameters passed to replicate
            call_args = mock_replicate_run.call_args
            input_params = call_args[1]["input"]
            
            # For Flux, num_inference_steps should be capped at 4
            assert input_params.get("num_inference_steps") == 4
            # Width/height should be removed for Flux
            assert "width" not in input_params
            assert "height" not in input_params
            # Flux-specific params should be kept
            assert input_params.get("aspect_ratio") == "16:9"
            assert input_params.get("seed") == 12345
    
    async def test_real_api_error_handling(self, api_service: ReplicateService):
        """Test error handling in real API mode."""
        with patch('replicate.run') as mock_replicate_run:
            mock_replicate_run.side_effect = Exception("API Error")
            
            with pytest.raises(Exception, match="API Error"):
                await api_service.generate_media("Test prompt")
    
    async def test_real_api_string_output(self, api_service: ReplicateService):
        """Test handling of string output from API."""
        with patch('replicate.run') as mock_replicate_run:
            mock_replicate_run.return_value = "https://single-image.png"
            
            urls = await api_service.generate_media("Test prompt")
            
            assert urls == ["https://single-image.png"]
    
    async def test_real_api_unexpected_output_format(self, api_service: ReplicateService):
        """Test handling of unexpected output format."""
        with patch('replicate.run') as mock_replicate_run:
            mock_replicate_run.return_value = {"unexpected": "format"}
            
            with pytest.raises(ValueError, match="Unexpected output format"):
                await api_service.generate_media("Test prompt")


class TestParameterCleaning:
    """Test parameter cleaning for different models."""
    
    @pytest.fixture
    def flux_service(self):
        """Service configured for Flux model."""
        settings = Settings(
            replicate_api_token="test-token",
            replicate_model="black-forest-labs/flux-schnell"
        )
        return ReplicateService(settings)
    
    @pytest.fixture
    def sdxl_service(self):
        """Service configured for SDXL model."""
        settings = Settings(
            replicate_api_token="test-token",
            replicate_model="stability-ai/sdxl:model-version"
        )
        return ReplicateService(settings)
    
    def test_flux_parameter_cleaning(self, flux_service: ReplicateService):
        """Test parameter cleaning for Flux models."""
        parameters = {
            "num_inference_steps": 10,  # Should be capped at 4
            "width": 1024,  # Should be removed
            "height": 1024,  # Should be removed
            "guidance_scale": 7.5,  # Should be removed
            "aspect_ratio": "16:9",  # Should be kept
            "output_quality": 80,  # Should be kept
            "seed": 12345,  # Should be kept
            "negative_prompt": "bad quality"  # Should be removed
        }
        
        cleaned = flux_service._clean_parameters_for_model(parameters)
        
        assert cleaned["num_inference_steps"] == 4
        assert "width" not in cleaned
        assert "height" not in cleaned
        assert "guidance_scale" not in cleaned
        assert cleaned["aspect_ratio"] == "16:9"
        assert cleaned["output_quality"] == 80
        assert cleaned["seed"] == 12345
        assert "negative_prompt" not in cleaned
    
    def test_sdxl_parameter_cleaning(self, sdxl_service: ReplicateService):
        """Test parameter cleaning for SDXL models."""
        parameters = {
            "num_inference_steps": 50,
            "width": 1024,
            "height": 1024,
            "guidance_scale": 7.5,
            "negative_prompt": "bad quality",
            "seed": 12345
        }
        
        cleaned = sdxl_service._clean_parameters_for_model(parameters)
        
        # SDXL should keep most parameters
        assert cleaned["num_inference_steps"] == 50
        assert cleaned["width"] == 1024
        assert cleaned["height"] == 1024
        assert cleaned["guidance_scale"] == 7.5
        assert cleaned["negative_prompt"] == "bad quality"
        assert cleaned["seed"] == 12345
    
    def test_invalid_seed_handling(self, flux_service: ReplicateService):
        """Test handling of invalid seed values."""
        parameters = {
            "seed": "invalid_seed"  # Should be filtered out
        }
        
        cleaned = flux_service._clean_parameters_for_model(parameters)
        
        assert "seed" not in cleaned
    
    def test_none_parameter_filtering(self, flux_service: ReplicateService):
        """Test filtering of None parameters."""
        parameters = {
            "num_inference_steps": None,
            "seed": None,
            "aspect_ratio": "16:9",
            "output_quality": None
        }
        
        cleaned = flux_service._clean_parameters_for_model(parameters)
        
        # Only non-None parameters should be included
        assert "num_inference_steps" not in cleaned
        assert "seed" not in cleaned
        assert cleaned["aspect_ratio"] == "16:9"
        assert "output_quality" not in cleaned


class TestModeDecision:
    """Test API vs Mock mode decision logic."""
    
    async def test_production_without_token_raises_error(self):
        """Test that production mode requires API token."""
        from app.services.replicate_service import ReplicateService
        from app.core.config import Settings
        
        # In production mode, service should raise error when trying to generate
        settings = Settings(
            app_env="production",
            replicate_api_token="dummy-token",  # Settings validates this at init
            database_url="postgresql://test",
            redis_url="redis://test",
            storage_type="local",
            storage_local_path="/tmp"
        )
        
        # Clear token after validation
        settings.replicate_api_token = ""
        service = ReplicateService(settings)
        
        # Should raise error when trying to generate without token in production
        with pytest.raises(ValueError, match="REPLICATE_API_TOKEN is required"):
            await service.generate_media("Test prompt")
    
    async def test_development_without_token_uses_mock(self):
        """Test that development without token uses mock."""
        settings = Settings(
            replicate_api_token="",
            app_env="development"
        )
        service = ReplicateService(settings)
        
        # Should not raise error and return mock data
        urls = await service.generate_media("Test prompt")
        assert len(urls) == 1
        assert urls[0].startswith("data:image/png;base64,")
    
    async def test_development_with_token_uses_api(self):
        """Test that development with token uses real API."""
        settings = Settings(
            replicate_api_token="test-token",
            app_env="development"
        )
        service = ReplicateService(settings)
        
        with patch('replicate.run') as mock_replicate_run:
            mock_replicate_run.return_value = ["https://api-result.png"]
            
            urls = await service.generate_media("Test prompt")
            
            assert urls == ["https://api-result.png"]
            mock_replicate_run.assert_called_once()


class TestCancellation:
    """Test prediction cancellation functionality."""
    
    async def test_cancel_prediction_real_api(self):
        """Test cancelling prediction with real API."""
        settings = Settings(
            replicate_api_token="test-token",
            app_env="production"
        )
        service = ReplicateService(settings)
        
        with patch('replicate.predictions.get') as mock_get:
            mock_prediction = MagicMock()
            mock_get.return_value = mock_prediction
            
            result = await service.cancel_prediction("prediction-123")
            
            assert result is True
            mock_get.assert_called_once_with("prediction-123")
            mock_prediction.cancel.assert_called_once()
    
    async def test_cancel_prediction_error_handling(self):
        """Test error handling in prediction cancellation."""
        settings = Settings(
            replicate_api_token="test-token",
            app_env="production"
        )
        service = ReplicateService(settings)
        
        with patch('replicate.predictions.get') as mock_get:
            mock_get.side_effect = Exception("Prediction not found")
            
            result = await service.cancel_prediction("invalid-prediction")
            
            assert result is False


class TestAsyncExecution:
    """Test async execution of synchronous Replicate API."""
    
    async def test_sync_to_async_conversion(self):
        """Test that sync replicate.run is properly converted to async."""
        settings = Settings(
            replicate_api_token="test-token",
            replicate_model="test-model"
        )
        service = ReplicateService(settings)
        
        with patch('replicate.run') as mock_replicate_run:
            # Simulate slow sync operation
            def slow_operation(*args, **kwargs):
                import time
                time.sleep(0.1)  # Simulate network delay
                return ["result.png"]
            
            mock_replicate_run.side_effect = slow_operation
            
            # Should not block the event loop
            start_time = asyncio.get_event_loop().time()
            urls = await service.generate_media("Test prompt")
            end_time = asyncio.get_event_loop().time()
            
            assert urls == ["result.png"]
            # Should take roughly the sleep time
            assert 0.08 < (end_time - start_time) < 0.5 