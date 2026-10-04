"""
FastAPI application entry point.
"""

import sentry_sdk
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.api.v1 import router as api_v1_router
from app.core.config import settings
from app.core.errors import AskDocsException
from app.core.logging import get_logger
from app.core.monitoring import setup_monitoring, start_metrics_server
from app.core.cache import init_cache_system
from app.core.redis import redis_client
from app.db.base import init_db, close_db
from app.middleware.tenant_context import TenantContextMiddleware
from app.middleware.rate_limiting import RateLimitMiddleware
from app.middleware.usage_tracking import UsageTrackingMiddleware
from app.middleware.tracing import TracingMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting AskDocs application")
    
    # Initialize monitoring and cache systems
    setup_monitoring()
    init_cache_system(redis_client)
    
    # Start metrics server on different port in production
    if settings.is_production:
        start_metrics_server(port=8001)
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down AskDocs application")
    await close_db()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    
    # Initialize Sentry for error tracking
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            integrations=[
                FastApiIntegration(auto_enabling=True),
                SqlalchemyIntegration(),
            ],
        )
        logger.info("Sentry initialized")

    # Create FastAPI app
    app = FastAPI(
        title=settings.APP_NAME,
        description="Production-grade multi-tenant RAG SaaS",
        version=settings.API_VERSION,
        debug=settings.DEBUG,
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add custom middleware (order matters!)
    app.add_middleware(TracingMiddleware)
    app.add_middleware(TenantContextMiddleware)
    app.add_middleware(UsageTrackingMiddleware)
    
    if settings.RATE_LIMIT_ENABLED:
        app.add_middleware(RateLimitMiddleware)

    # Add routes
    app.include_router(
        api_v1_router,
        prefix=f"/api/{settings.API_VERSION}",
    )

    # Global exception handler
    @app.exception_handler(AskDocsException)
    async def askdocs_exception_handler(request: Request, exc: AskDocsException) -> JSONResponse:
        """Handle custom application exceptions."""
        logger.error(
            "Application error",
            error=exc.message,
            status_code=exc.status_code,
            details=exc.details,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.message,
                "details": exc.details,
                "type": exc.__class__.__name__,
            },
        )

    # Generic exception handler
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected exceptions."""
        logger.error(
            "Unexpected error",
            error=str(exc),
            path=request.url.path,
            exc_info=exc,
        )
        
        if settings.DEBUG:
            import traceback
            return JSONResponse(
                status_code=500,
                content={
                    "error": str(exc),
                    "type": exc.__class__.__name__,
                    "traceback": traceback.format_exc(),
                },
            )
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "type": "InternalServerError",
                },
            )

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "app": settings.APP_NAME,
            "version": settings.API_VERSION,
            "environment": settings.APP_ENV,
        }

    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        log_level=settings.LOG_LEVEL.lower(),
    )

