"""Billing enforcement middleware."""

import json
from typing import Callable
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger
from app.services.billing_service import BillingService, PlanLimitExceeded
from app.core.database import SessionLocal

logger = get_logger(__name__)


class BillingEnforcementMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce billing limits on API requests."""
    
    # Routes that should check query limits
    QUERY_ROUTES = [
        "/api/v1/query/",
        "/api/v1/query/suggestions",
    ]
    
    # Routes that should check document limits
    DOCUMENT_UPLOAD_ROUTES = [
        "/api/v1/documents/upload",
    ]
    
    # Routes that should check API key limits
    API_KEY_ROUTES = [
        "/api/v1/api-keys/",
    ]
    
    def __init__(self, app, enforce_limits: bool = True):
        super().__init__(app)
        self.enforce_limits = enforce_limits
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and enforce billing limits."""
        
        if not self.enforce_limits:
            return await call_next(request)
        
        # Skip enforcement for certain routes
        if self.should_skip_enforcement(request):
            return await call_next(request)
        
        # Get tenant from request context (set by TenantContextMiddleware)
        tenant_id = getattr(request.state, "tenant_id", None)
        if not tenant_id:
            # No tenant context, let the request through
            return await call_next(request)
        
        try:
            # Check limits based on route
            await self.check_route_limits(request, tenant_id)
            
            # Process the request
            response = await call_next(request)
            
            # Record usage after successful request
            await self.record_usage(request, tenant_id, response)
            
            return response
            
        except PlanLimitExceeded as e:
            logger.warning(
                "Plan limit exceeded",
                tenant_id=str(tenant_id),
                limit_type=e.limit_type,
                current=e.current,
                limit=e.limit,
                path=request.url.path
            )
            
            return JSONResponse(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                content={
                    "error": "Plan limit exceeded",
                    "limit_type": e.limit_type,
                    "current": e.current,
                    "limit": e.limit,
                    "message": str(e),
                    "upgrade_url": "/billing/plans"
                }
            )
        except Exception as e:
            logger.error(
                "Billing middleware error",
                error=str(e),
                tenant_id=str(tenant_id) if tenant_id else None,
                path=request.url.path,
                exc_info=True
            )
            # Don't block request on billing errors
            return await call_next(request)
    
    def should_skip_enforcement(self, request: Request) -> bool:
        """Check if enforcement should be skipped for this request."""
        path = request.url.path
        
        # Skip non-API routes
        if not path.startswith("/api/"):
            return True
        
        # Skip health checks
        if "/health" in path:
            return True
        
        # Skip auth endpoints
        if "/auth/" in path:
            return True
        
        # Skip billing endpoints (to allow plan upgrades)
        if "/billing/" in path:
            return True
        
        # Skip GET requests (read-only operations)
        if request.method == "GET":
            return True
        
        return False
    
    async def check_route_limits(self, request: Request, tenant_id: str) -> None:
        """Check limits based on the route being accessed."""
        path = request.url.path
        
        # Use database session
        db = SessionLocal()
        try:
            billing_service = BillingService(db)
            
            # Check query limits
            if any(route in path for route in self.QUERY_ROUTES):
                billing_service.enforce_query_limit(tenant_id)
            
            # Check document upload limits
            elif any(route in path for route in self.DOCUMENT_UPLOAD_ROUTES):
                billing_service.enforce_document_limit(tenant_id)
                
                # Also check storage limit if file is being uploaded
                if request.method == "POST" and "multipart/form-data" in request.headers.get("content-type", ""):
                    content_length = int(request.headers.get("content-length", 0))
                    if content_length > 0:
                        storage_mb = content_length / (1024 * 1024)
                        billing_service.enforce_storage_limit(tenant_id, storage_mb)
            
            # Check API key creation limits
            elif any(route in path for route in self.API_KEY_ROUTES) and request.method == "POST":
                billing_service.enforce_api_key_limit(tenant_id)
            
        finally:
            db.close()
    
    async def record_usage(self, request: Request, tenant_id: str, response: Response) -> None:
        """Record usage after successful request."""
        # Only record usage for successful responses
        if response.status_code >= 400:
            return
        
        path = request.url.path
        
        # Use database session
        db = SessionLocal()
        try:
            billing_service = BillingService(db)
            
            # Record query usage
            if any(route in path for route in self.QUERY_ROUTES):
                # Extract cost data from response if available
                cost_data = None
                try:
                    if hasattr(response, "body"):
                        body = json.loads(response.body)
                        if "cost_breakdown" in body:
                            cost_data = body["cost_breakdown"]
                except:
                    pass
                
                billing_service.record_query_usage(tenant_id, cost_data)
            
            # Record document upload usage
            elif any(route in path for route in self.DOCUMENT_UPLOAD_ROUTES):
                content_length = int(request.headers.get("content-length", 0))
                if content_length > 0:
                    billing_service.record_document_usage(tenant_id, content_length)
                    
        except Exception as e:
            logger.error(
                "Failed to record usage",
                error=str(e),
                tenant_id=str(tenant_id),
                path=path
            )
        finally:
            db.close()