"""Replicate API integration service."""

import asyncio
from typing import List, Dict, Any, Optional
import httpx
from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ReplicateService:
    """Service for interacting with Replicate API."""
    
    def __init__(self, settings: Settings):
        """Initialize Replicate service."""
        self.settings = settings
        self.api_token = settings.replicate_api_token
        self.model = settings.replicate_model
        self.timeout = settings.replicate_timeout
        self.base_url = "https://api.replicate.com/v1"
    
    async def generate_media(
        self,
        prompt: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Generate media using Replicate API.
        
        Args:
            prompt: Text prompt for generation
            parameters: Generation parameters
            
        Returns:
            List of generated media URLs
        """
        # Use mock in development if no API token
        if self.settings.is_development and not self.api_token:
            logger.warning("Using mock Replicate service in development")
            return await self._mock_generate_media(prompt, parameters)
        
        # Prepare input
        input_data = {
            "prompt": prompt,
            **(parameters or {})
        }
        
        # Create prediction
        prediction_id = await self._create_prediction(input_data)
        
        # Wait for completion
        output = await self._wait_for_prediction(prediction_id)
        
        # Extract URLs from output
        if isinstance(output, list):
            return [str(url) for url in output]
        elif isinstance(output, str):
            return [output]
        else:
            raise ValueError(f"Unexpected output format: {type(output)}")
    
    async def _create_prediction(self, input_data: Dict[str, Any]) -> str:
        """Create a new prediction."""
        headers = {
            "Authorization": f"Token {self.api_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "version": self.model.split(":")[-1] if ":" in self.model else self.model,
            "input": input_data
        }
        
        # If model contains owner/name:version format
        if "/" in self.model and ":" in self.model:
            model_parts = self.model.split(":")
            model_name = model_parts[0]
            version = model_parts[1]
            
            # Use the models endpoint
            url = f"{self.base_url}/models/{model_name}/predictions"
            payload = {"version": version, "input": input_data}
        else:
            # Use the predictions endpoint
            url = f"{self.base_url}/predictions"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            prediction_id = data["id"]
            
            logger.info(
                "Created Replicate prediction",
                prediction_id=prediction_id,
                model=self.model
            )
            
            return prediction_id
    
    async def _wait_for_prediction(self, prediction_id: str) -> Any:
        """Wait for prediction to complete."""
        headers = {
            "Authorization": f"Token {self.api_token}"
        }
        
        url = f"{self.base_url}/predictions/{prediction_id}"
        start_time = asyncio.get_event_loop().time()
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                # Check timeout
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > self.timeout:
                    raise TimeoutError(f"Prediction timeout after {elapsed:.1f}s")
                
                # Get prediction status
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                
                data = response.json()
                status = data["status"]
                
                logger.debug(
                    "Prediction status",
                    prediction_id=prediction_id,
                    status=status,
                    elapsed=f"{elapsed:.1f}s"
                )
                
                if status == "succeeded":
                    return data["output"]
                elif status == "failed":
                    error = data.get("error", "Unknown error")
                    raise RuntimeError(f"Prediction failed: {error}")
                elif status == "canceled":
                    raise RuntimeError("Prediction was canceled")
                
                # Wait before next check
                await asyncio.sleep(2.0)
    
    async def _mock_generate_media(
        self,
        prompt: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Mock media generation for development."""
        logger.info(
            "Mock generating media",
            prompt_preview=prompt[:50] + "...",
            parameters=parameters
        )
        
        # Simulate processing time
        await asyncio.sleep(5.0)
        
        # Instead of using external URLs that may not be accessible in Docker,
        # return a data URL with a generated test image
        from PIL import Image, ImageDraw, ImageFont
        import base64
        import io
        
        # Get image dimensions from parameters
        width = parameters.get("width", 1024) if parameters else 1024
        height = parameters.get("height", 1024) if parameters else 1024
        
        # Create a simple test image
        image = Image.new("RGB", (width, height), color="lightblue")
        draw = ImageDraw.Draw(image)
        
        # Draw some basic shapes and text
        try:
            # Try to use a default font, fall back to basic if not available
            font = ImageFont.load_default()
        except:
            font = None
        
        # Draw a simple pattern
        draw.rectangle([width//4, height//4, 3*width//4, 3*height//4], 
                      outline="navy", fill="lightcyan", width=3)
        
        # Add text
        text_lines = [
            "Generated Image",
            f"Size: {width}x{height}",
            f"Prompt: {prompt[:20]}..." if len(prompt) > 20 else f"Prompt: {prompt}"
        ]
        
        y_offset = height // 3
        for line in text_lines:
            if font:
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
            else:
                # Estimate text size if no font available
                text_width = len(line) * 8
                text_height = 12
            
            x = (width - text_width) // 2
            draw.text((x, y_offset), line, fill="navy", font=font)
            y_offset += text_height + 10
        
        # Convert to bytes
        img_buffer = io.BytesIO()
        image.save(img_buffer, format="PNG")
        img_buffer.seek(0)
        
        # Create a data URL
        image_data = base64.b64encode(img_buffer.getvalue()).decode()
        data_url = f"data:image/png;base64,{image_data}"
        
        logger.info("Generated mock image with data URL", 
                   size=f"{width}x{height}", 
                   data_size=len(image_data))
        
        return [data_url]
    
    async def cancel_prediction(self, prediction_id: str) -> bool:
        """Cancel a running prediction.
        
        Args:
            prediction_id: ID of the prediction to cancel
            
        Returns:
            True if cancelled successfully
        """
        if self.settings.is_development and not self.api_token:
            return True
        
        headers = {
            "Authorization": f"Token {self.api_token}"
        }
        
        url = f"{self.base_url}/predictions/{prediction_id}/cancel"
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, headers=headers)
                response.raise_for_status()
                
                logger.info("Cancelled prediction", prediction_id=prediction_id)
                return True
                
        except Exception as e:
            logger.error(
                "Failed to cancel prediction",
                prediction_id=prediction_id,
                error=str(e)
            )
            return False 