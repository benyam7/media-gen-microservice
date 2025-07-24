"""Application configuration module using Pydantic settings."""

from functools import lru_cache
from typing import List, Optional, Literal
from pydantic import Field, validator, AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Application Configuration
    app_name: str = Field(default="media-gen-microservice", description="Application name")
    app_env: Literal["development", "staging", "production"] = Field(
        default="development", description="Application environment"
    )
    debug: bool = Field(default=False, description="Debug mode")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level"
    )
    
    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_workers: int = Field(default=4, description="Number of API workers")
    
    # Database Configuration
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/media_gen_db",
        description="Database connection URL"
    )
    database_pool_size: int = Field(default=20, description="Database connection pool size")
    database_max_overflow: int = Field(default=40, description="Maximum overflow connections")
    database_pool_timeout: int = Field(default=30, description="Connection pool timeout")
    database_pool_recycle: int = Field(default=3600, description="Connection recycle time")
    
    # Redis Configuration
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    redis_max_connections: int = Field(default=100, description="Maximum Redis connections")
    
    # Celery Configuration
    celery_broker_url: str = Field(
        default="redis://localhost:6379/1",
        description="Celery broker URL"
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/2",
        description="Celery result backend URL"
    )
    celery_task_max_retries: int = Field(default=3, description="Maximum task retries")
    celery_retry_backoff_base: int = Field(default=2, description="Retry backoff base")
    celery_retry_backoff_max: int = Field(default=600, description="Maximum retry backoff")
    
    # Replicate API Configuration
    replicate_api_token: str = Field(
        default="",
        description="Replicate API token"
    )
    replicate_model: str = Field(
        default="stability-ai/sdxl:8c9b1b7b3b4b5e6f7d8a9c0e1f2g3h4i5j6k7l8m9n0o1p",
        description="Replicate model ID"
    )
    replicate_timeout: int = Field(default=300, description="Replicate API timeout")
    
    # Storage Configuration
    storage_type: Literal["s3", "local"] = Field(
        default="s3",
        description="Storage type"
    )
    storage_local_path: str = Field(
        default="/app/media",
        description="Local storage path"
    )
    
    # S3/MinIO Configuration
    s3_endpoint_url: Optional[str] = Field(
        default=None,
        description="S3 endpoint URL (for MinIO or custom S3)"
    )
    s3_access_key_id: str = Field(default="", description="S3 access key")
    s3_secret_access_key: str = Field(default="", description="S3 secret key")
    s3_bucket_name: str = Field(default="media-generation", description="S3 bucket name")
    s3_region: str = Field(default="us-east-1", description="S3 region")
    s3_use_ssl: bool = Field(default=True, description="Use SSL for S3")
    
    # Security Configuration
    secret_key: str = Field(
        default="",
        description="Application secret key"
    )
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="Allowed CORS origins"
    )
    
    # Monitoring Configuration
    sentry_dsn: Optional[str] = Field(default=None, description="Sentry DSN")
    prometheus_enabled: bool = Field(default=True, description="Enable Prometheus metrics")
    prometheus_port: int = Field(default=9090, description="Prometheus metrics port")
    
    @validator("secret_key")
    def validate_secret_key(cls, v: str, values: dict) -> str:
        """Validate secret key is set in production."""
        if values.get("app_env") == "production" and not v:
            raise ValueError("SECRET_KEY must be set in production")
        return v or "dev-secret-key-not-for-production"
    
    @validator("replicate_api_token")
    def validate_replicate_token(cls, v: str, values: dict) -> str:
        """Validate Replicate API token is set in production."""
        if values.get("app_env") == "production" and not v:
            raise ValueError("REPLICATE_API_TOKEN must be set in production")
        return v
    
    @validator("allowed_origins", pre=True)
    def parse_allowed_origins(cls, v):
        """Parse comma-separated allowed origins."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL for Alembic."""
        return self.database_url.replace("+asyncpg", "")
    
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.app_env == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.app_env == "development"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings() 