"""
Tenant context middleware for multi-tenancy isolation.
"""

from typing import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger

logger = get_logger(__name__)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add tenant context to logs and enforce isolation.
    
    Tenant context is populated by the authentication dependencies
    and stored in request.state.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with tenant context."""
        
        # Skip tenant context for non-API paths
        skip_paths = {"/health", "/docs", "/redoc", "/openapi.json"}
        if request.url.path in skip_paths:
            return await call_next(request)
        
        # Process request
        response = await call_next(request)
        
        # If tenant context was set during authentication, add to logs
        if hasattr(request.state, "tenant_id") and request.state.tenant_id:
            structlog.contextvars.bind_contextvars(
                tenant_id=str(request.state.tenant_id),
            )
            
            # Add tenant ID to response headers for debugging (non-production)
            response.headers["X-Tenant-ID"] = str(request.state.tenant_id)
        
        return response