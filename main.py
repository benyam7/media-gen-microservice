"""Entry point for running the application directly."""

import uvicorn
from app.main import app
from app.core.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development,
        workers=1 if settings.is_development else settings.api_workers,
        log_level=settings.log_level.lower(),
        access_log=True,
        use_colors=settings.is_development
    )