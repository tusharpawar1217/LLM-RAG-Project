"""
Health check endpoints.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.base import get_db

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.API_VERSION,
        "environment": settings.APP_ENV,
    }


@router.get("/health/db")
async def database_health_check(db: AsyncSession = Depends(get_db)):
    """Database connectivity health check."""
    try:
        # Simple query to test database connection
        result = await db.execute(text("SELECT 1"))
        row = result.scalar()
        
        if row == 1:
            return {
                "status": "healthy",
                "database": "connected",
                "app": settings.APP_NAME,
            }
        else:
            return {
                "status": "unhealthy",
                "database": "unexpected_result",
                "app": settings.APP_NAME,
            }
            
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "connection_failed",
            "error": str(e),
            "app": settings.APP_NAME,
        }