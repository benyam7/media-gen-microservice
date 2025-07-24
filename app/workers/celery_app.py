"""Celery application configuration."""

from celery import Celery
from app.core.config import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    "media_gen_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"]
)

# Celery configuration
celery_app.conf.update(
    # Task configuration
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task execution
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_time_limit=settings.replicate_timeout + 60,  # Add buffer
    task_soft_time_limit=settings.replicate_timeout,
    
    # Worker configuration
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    worker_hijack_root_logger=False,
    
    # Result backend
    result_expires=3600,  # 1 hour
    result_persistent=True,
    
    # Retry configuration
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=settings.celery_task_max_retries,
    
    # Beat schedule (for periodic tasks)
    beat_schedule={
        "cleanup-old-jobs": {
            "task": "app.workers.tasks.cleanup_old_jobs",
            "schedule": 3600.0,  # Every hour
        },
    },
)

# Task routing
celery_app.conf.task_routes = {
    "app.workers.tasks.generate_media_task": {"queue": "media_generation"},
    "app.workers.tasks.cleanup_old_jobs": {"queue": "maintenance"},
}

# Queue configuration
celery_app.conf.task_queues = {
    "media_generation": {
        "exchange": "media_generation",
        "exchange_type": "direct",
        "routing_key": "media_generation",
    },
    "maintenance": {
        "exchange": "maintenance",
        "exchange_type": "direct",
        "routing_key": "maintenance",
    },
} 