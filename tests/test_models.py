"""Tests for SQLModel models."""

import pytest
from app.models import JobStatus, MediaType


def test_job_status_enum():
    """Test JobStatus enum values."""
    assert JobStatus.PENDING == "pending"
    assert JobStatus.PROCESSING == "processing"
    assert JobStatus.COMPLETED == "completed"
    assert JobStatus.FAILED == "failed"
    assert JobStatus.CANCELLED == "cancelled"


def test_media_type_enum():
    """Test MediaType enum values."""
    assert MediaType.IMAGE == "image"
    assert MediaType.VIDEO == "video"
    assert MediaType.AUDIO == "audio"


def test_job_status_values():
    """Test all JobStatus values are accessible."""
    statuses = [JobStatus.PENDING, JobStatus.PROCESSING, JobStatus.COMPLETED, 
                JobStatus.FAILED, JobStatus.CANCELLED]
    assert len(statuses) == 5


def test_media_type_values():
    """Test all MediaType values are accessible."""
    types = [MediaType.IMAGE, MediaType.VIDEO, MediaType.AUDIO]
    assert len(types) == 3 