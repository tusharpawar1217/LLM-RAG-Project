"""
Usage tracking middleware for billing and analytics.
"""

from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger

logger = get_logger(__name__)


class UsageTrackingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track API usage for billing purposes.
    
    This will be fully implemented in Module 9: Billing.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with usage tracking."""
        
        # Skip tracking for non-billable endpoints
        skip_paths = {"/health", "/docs", "/redoc", "/openapi.json"}
        if request.url.path in skip_paths:
            return await call_next(request)
        
        # TODO: Track usage events
        # This will be implemented when we add billing
        
        response = await call_next(request)
        return response