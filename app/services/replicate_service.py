"""Replicate API integration service."""

import asyncio
import os
from typing import List, Dict, Any, Optional
import replicate
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
        
        # Set up Replicate client
        if self.api_token:
            os.environ["REPLICATE_API_TOKEN"] = self.api_token
        
        # Debug logging to see what we actually got
        logger.info(
            "ReplicateService initialized",
            has_token=bool(self.api_token),
            token_length=len(self.api_token) if self.api_token else 0,
            token_preview=self.api_token[:8] + "..." if len(self.api_token) > 8 else self.api_token,
            model=self.model,
            is_development=settings.is_development,
            app_env=settings.app_env
        )
    
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
        # Decision logic for API vs Mock
        logger.debug(
            "Making API vs Mock decision",
            api_token_provided=bool(self.api_token),
            api_token_length=len(self.api_token) if self.api_token else 0,
            is_development=self.settings.is_development,
            app_env=self.settings.app_env
        )
        
        if self.api_token:
            # Use real API if token is provided (regardless of environment)
            logger.info(
                "Using real Replicate API",
                has_token=True,
                is_development=self.settings.is_development,
                model=self.model
            )
            return await self._use_real_api(prompt, parameters)
        elif self.settings.is_development:
            # Use mock in development when no API token
            logger.warning(
                "Using mock Replicate service in development (no API token provided)",
                has_token=False,
                is_development=True
            )
            return await self._mock_generate_media(prompt, parameters)
        else:
            # Production without token is an error
            raise ValueError(
                "REPLICATE_API_TOKEN is required in production environment. "
                "Please set the REPLICATE_API_TOKEN environment variable."
            )
    
    async def _use_real_api(
        self,
        prompt: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Use the real Replicate API for media generation."""
        # Clean and validate parameters based on the model
        cleaned_parameters = self._clean_parameters_for_model(parameters or {})
        
        # Prepare input
        input_data = {
            "prompt": prompt,
            **cleaned_parameters
        }
        
        logger.info(
            "Generating media with Replicate API",
            model=self.model,
            prompt_preview=prompt[:50] + "..." if len(prompt) > 50 else prompt,
            original_parameters=parameters,
            cleaned_parameters=cleaned_parameters
        )
        
        # Run in executor since replicate.run is synchronous
        loop = asyncio.get_event_loop()
        output = await loop.run_in_executor(
            None,
            self._run_replicate_sync,
            input_data
        )
        
        # Extract URLs from output
        if isinstance(output, list):
            return [str(url) for url in output]
        elif isinstance(output, str):
            return [output]
        else:
            raise ValueError(f"Unexpected output format: {type(output)}")
    
    def _clean_parameters_for_model(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and validate parameters based on the specific model being used."""
        cleaned = {}
        
        # Handle different models
        if "flux-schnell" in self.model.lower():
            # Flux Schnell specific parameters
            
            # For Flux, only include specific supported parameters
            # Based on Replicate docs: https://replicate.com/black-forest-labs/flux-schnell
            
            # num_inference_steps: must be <= 4 for Flux Schnell
            if "num_inference_steps" in parameters:
                num_steps = parameters["num_inference_steps"]
                if num_steps and num_steps > 4:
                    logger.warning(f"Flux model requires num_inference_steps <= 4, got {num_steps}, setting to 4")
                    cleaned["num_inference_steps"] = 4
                elif num_steps and num_steps >= 1:
                    cleaned["num_inference_steps"] = num_steps
                # Don't include if None or invalid
            
            # seed: must be integer for Flux
            if "seed" in parameters and parameters["seed"] is not None:
                try:
                    cleaned["seed"] = int(parameters["seed"])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid seed value: {parameters['seed']}, skipping")
            
            # aspect_ratio: Flux supports this
            if "aspect_ratio" in parameters and parameters["aspect_ratio"]:
                cleaned["aspect_ratio"] = str(parameters["aspect_ratio"])
            
            # output_quality: Flux supports this
            if "output_quality" in parameters and parameters["output_quality"]:
                cleaned["output_quality"] = int(parameters["output_quality"])
                
            # Skip parameters that Flux doesn't support
            unsupported_for_flux = [
                "width", "height", "guidance_scale", "negative_prompt", 
                "scheduler", "num_outputs"
            ]
            for param in unsupported_for_flux:
                if param in parameters:
                    logger.debug(f"Skipping unsupported parameter for Flux: {param}")
                    
        elif "sdxl" in self.model.lower():
            # SDXL model parameters
            for key, value in parameters.items():
                if value is not None:
                    cleaned[key] = value
                    
        else:
            # Default: include all non-None parameters
            for key, value in parameters.items():
                if value is not None:
                    cleaned[key] = value
        
        logger.debug(f"Cleaned parameters for model {self.model}: {cleaned}")
        return cleaned
    
    def _run_replicate_sync(self, input_data: Dict[str, Any]) -> Any:
        """Run replicate synchronously."""
        try:
            output = replicate.run(self.model, input=input_data)
            logger.info("Replicate generation completed successfully")
            return output
        except Exception as e:
            logger.error(f"Replicate API error: {str(e)}")
            raise
    

    
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
        
        try:
            # Run in executor since replicate operations are synchronous
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._cancel_prediction_sync,
                prediction_id
            )
            
            logger.info("Cancelled prediction", prediction_id=prediction_id)
            return True
            
        except Exception as e:
            logger.error(
                "Failed to cancel prediction",
                prediction_id=prediction_id,
                error=str(e)
            )
            return False
    
    def _cancel_prediction_sync(self, prediction_id: str) -> None:
        """Cancel prediction synchronously."""
        prediction = replicate.predictions.get(prediction_id)
        prediction.cancel() 