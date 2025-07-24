"""Tests for configuration."""

import pytest
from app.core.config import Settings


def test_default_settings():
    """Test default settings values."""
    settings = Settings()
    
    # Test defaults
    assert settings.app_name == "media-gen-microservice"
    assert settings.app_env in ["development", "staging", "production"]
    assert settings.debug is not None
    assert settings.log_level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    
    
def test_settings_environment():
    """Test settings environment values."""
    settings = Settings()
    assert hasattr(settings, 'database_url')
    assert hasattr(settings, 'redis_url')
    assert hasattr(settings, 'storage_type')
    

def test_settings_attributes():
    """Test settings has required attributes."""
    settings = Settings()
    required_attrs = ['database_url', 'redis_url', 'storage_type', 'secret_key']
    for attr in required_attrs:
        assert hasattr(settings, attr) 