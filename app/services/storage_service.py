"""Storage service for managing media files."""

import io
import os
from pathlib import Path
from typing import Optional, Tuple, BinaryIO, AsyncIterator
from uuid import UUID
import aiofiles
import aioboto3
from botocore.exceptions import ClientError
from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class StorageService:
    """Service for managing file storage in S3 or local filesystem."""
    
    def __init__(self, settings: Settings):
        """Initialize storage service with configuration."""
        self.settings = settings
        self.storage_type = settings.storage_type
        
        if self.storage_type == "local":
            # Ensure local storage directory exists
            self.local_path = Path(settings.storage_local_path)
            self.local_path.mkdir(parents=True, exist_ok=True)
    
    async def upload_file(
        self,
        file_content: bytes,
        file_name: str,
        content_type: Optional[str] = None,
        bucket_name: Optional[str] = None
    ) -> Tuple[str, Optional[str]]:
        """Upload a file to storage.
        
        Args:
            file_content: File content as bytes
            file_name: Name/key for the file
            content_type: MIME type of the file
            bucket_name: S3 bucket name (for S3 storage)
            
        Returns:
            Tuple of (storage_path, public_url)
        """
        if self.storage_type == "s3":
            return await self._upload_to_s3(
                file_content,
                file_name,
                content_type,
                bucket_name or self.settings.s3_bucket_name
            )
        else:
            return await self._upload_to_local(file_content, file_name)
    
    async def download_file(
        self,
        file_path: str,
        bucket_name: Optional[str] = None
    ) -> Tuple[AsyncIterator[bytes], Optional[int]]:
        """Download a file from storage.
        
        Args:
            file_path: Path/key of the file
            bucket_name: S3 bucket name (for S3 storage)
            
        Returns:
            Tuple of (file_stream, content_length)
        """
        if self.storage_type == "s3":
            return await self._download_from_s3(
                file_path,
                bucket_name or self.settings.s3_bucket_name
            )
        else:
            return await self._download_from_local(file_path)
    
    async def delete_file(
        self,
        file_path: str,
        bucket_name: Optional[str] = None
    ) -> bool:
        """Delete a file from storage.
        
        Args:
            file_path: Path/key of the file
            bucket_name: S3 bucket name (for S3 storage)
            
        Returns:
            True if successful
        """
        if self.storage_type == "s3":
            return await self._delete_from_s3(
                file_path,
                bucket_name or self.settings.s3_bucket_name
            )
        else:
            return await self._delete_from_local(file_path)
    
    async def file_exists(
        self,
        file_path: str,
        bucket_name: Optional[str] = None
    ) -> bool:
        """Check if a file exists in storage.
        
        Args:
            file_path: Path/key of the file
            bucket_name: S3 bucket name (for S3 storage)
            
        Returns:
            True if file exists
        """
        if self.storage_type == "s3":
            return await self._exists_in_s3(
                file_path,
                bucket_name or self.settings.s3_bucket_name
            )
        else:
            return await self._exists_in_local(file_path)
    
    # S3 Storage Methods
    
    async def _upload_to_s3(
        self,
        file_content: bytes,
        key: str,
        content_type: Optional[str],
        bucket_name: str
    ) -> Tuple[str, Optional[str]]:
        """Upload file to S3."""
        session = aioboto3.Session()
        
        async with session.client(
            "s3",
            endpoint_url=self.settings.s3_endpoint_url,
            aws_access_key_id=self.settings.s3_access_key_id,
            aws_secret_access_key=self.settings.s3_secret_access_key,
            region_name=self.settings.s3_region,
            use_ssl=self.settings.s3_use_ssl
        ) as s3_client:
            try:
                # Upload file
                extra_args = {}
                if content_type:
                    extra_args["ContentType"] = content_type
                
                await s3_client.put_object(
                    Bucket=bucket_name,
                    Key=key,
                    Body=file_content,
                    **extra_args
                )
                
                # Generate public URL if bucket is public
                public_url = None
                if self.settings.s3_endpoint_url:
                    # MinIO or custom S3
                    public_url = f"{self.settings.s3_endpoint_url}/{bucket_name}/{key}"
                else:
                    # AWS S3
                    public_url = f"https://{bucket_name}.s3.{self.settings.s3_region}.amazonaws.com/{key}"
                
                logger.info(
                    "File uploaded to S3",
                    bucket=bucket_name,
                    key=key,
                    size=len(file_content)
                )
                
                return key, public_url
                
            except ClientError as e:
                logger.error(
                    "Failed to upload to S3",
                    error=str(e),
                    bucket=bucket_name,
                    key=key
                )
                raise
    
    async def _download_from_s3(
        self,
        key: str,
        bucket_name: str
    ) -> Tuple[AsyncIterator[bytes], Optional[int]]:
        """Download file from S3."""
        session = aioboto3.Session()
        
        async with session.client(
            "s3",
            endpoint_url=self.settings.s3_endpoint_url,
            aws_access_key_id=self.settings.s3_access_key_id,
            aws_secret_access_key=self.settings.s3_secret_access_key,
            region_name=self.settings.s3_region,
            use_ssl=self.settings.s3_use_ssl
        ) as s3_client:
            try:
                # Get object
                response = await s3_client.get_object(
                    Bucket=bucket_name,
                    Key=key
                )
                
                content_length = response.get("ContentLength")
                
                # Create async iterator for streaming
                async def stream_content():
                    async for chunk in response["Body"]:
                        yield chunk
                
                return stream_content(), content_length
                
            except ClientError as e:
                if e.response["Error"]["Code"] == "NoSuchKey":
                    raise FileNotFoundError(f"File not found: {key}")
                logger.error(
                    "Failed to download from S3",
                    error=str(e),
                    bucket=bucket_name,
                    key=key
                )
                raise
    
    async def _delete_from_s3(
        self,
        key: str,
        bucket_name: str
    ) -> bool:
        """Delete file from S3."""
        session = aioboto3.Session()
        
        async with session.client(
            "s3",
            endpoint_url=self.settings.s3_endpoint_url,
            aws_access_key_id=self.settings.s3_access_key_id,
            aws_secret_access_key=self.settings.s3_secret_access_key,
            region_name=self.settings.s3_region,
            use_ssl=self.settings.s3_use_ssl
        ) as s3_client:
            try:
                await s3_client.delete_object(
                    Bucket=bucket_name,
                    Key=key
                )
                logger.info("File deleted from S3", bucket=bucket_name, key=key)
                return True
                
            except ClientError as e:
                logger.error(
                    "Failed to delete from S3",
                    error=str(e),
                    bucket=bucket_name,
                    key=key
                )
                return False
    
    async def _exists_in_s3(
        self,
        key: str,
        bucket_name: str
    ) -> bool:
        """Check if file exists in S3."""
        session = aioboto3.Session()
        
        async with session.client(
            "s3",
            endpoint_url=self.settings.s3_endpoint_url,
            aws_access_key_id=self.settings.s3_access_key_id,
            aws_secret_access_key=self.settings.s3_secret_access_key,
            region_name=self.settings.s3_region,
            use_ssl=self.settings.s3_use_ssl
        ) as s3_client:
            try:
                await s3_client.head_object(
                    Bucket=bucket_name,
                    Key=key
                )
                return True
                
            except ClientError as e:
                if e.response["Error"]["Code"] == "404":
                    return False
                raise
    
    # Local Storage Methods
    
    async def _upload_to_local(
        self,
        file_content: bytes,
        file_name: str
    ) -> Tuple[str, Optional[str]]:
        """Upload file to local filesystem."""
        file_path = self.local_path / file_name
        
        # Create subdirectories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_content)
        
        logger.info(
            "File uploaded to local storage",
            path=str(file_path),
            size=len(file_content)
        )
        
        return str(file_path), None
    
    async def _download_from_local(
        self,
        file_path: str
    ) -> Tuple[AsyncIterator[bytes], Optional[int]]:
        """Download file from local filesystem."""
        # Handle both absolute and relative paths
        if os.path.isabs(file_path):
            full_path = Path(file_path)
        else:
            full_path = self.local_path / file_path
        
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_size = full_path.stat().st_size
        
        async def stream_content():
            async with aiofiles.open(full_path, "rb") as f:
                chunk_size = 8192
                while True:
                    chunk = await f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        
        return stream_content(), file_size
    
    async def _delete_from_local(self, file_path: str) -> bool:
        """Delete file from local filesystem."""
        # Handle both absolute and relative paths
        if os.path.isabs(file_path):
            full_path = Path(file_path)
        else:
            full_path = self.local_path / file_path
        
        try:
            if full_path.exists():
                full_path.unlink()
                logger.info("File deleted from local storage", path=str(full_path))
                return True
            return False
        except Exception as e:
            logger.error(
                "Failed to delete from local storage",
                error=str(e),
                path=str(full_path)
            )
            return False
    
    async def _exists_in_local(self, file_path: str) -> bool:
        """Check if file exists in local filesystem."""
        # Handle both absolute and relative paths
        if os.path.isabs(file_path):
            full_path = Path(file_path)
        else:
            full_path = self.local_path / file_path
        
        return full_path.exists() 