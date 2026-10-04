#!/usr/bin/env python3
"""
ARQ worker startup script.
Run document ingestion and other background tasks.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.workers.ingestion import WorkerSettings

logger = get_logger(__name__)


async def main():
    """Main worker function."""
    # Setup logging
    setup_logging(
        level=settings.LOG_LEVEL,
        format_type=settings.LOG_FORMAT,
        service_name="askdocs-worker"
    )
    
    logger.info(
        "Starting ARQ worker",
        redis_host=settings.REDIS_HOST,
        redis_port=settings.REDIS_PORT,
        max_jobs=WorkerSettings.max_jobs,
        queue_name=WorkerSettings.queue_name,
    )
    
    try:
        from arq import run_worker
        
        # Run the worker with our settings
        await run_worker(WorkerSettings)
        
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"Worker crashed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

