"""
Rate limiting middleware using Redis.
"""

import json
import time
from typing import Callable

import redis.asyncio as redis
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.errors import RateLimitExceededError
from app.core.logging import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using sliding window algorithm.
    """

    def __init__(self, app, redis_url: str = None):
        super().__init__(app)
        self.redis_url = redis_url or settings.REDIS_URL
        self._redis: redis.Redis | None = None

    async def get_redis(self) -> redis.Redis:
        """Get Redis connection (lazy initialization)."""
        if self._redis is None:
            self._redis = redis.from_url(
                self.redis_url,
                decode_responses=True,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
            )
        return self._redis

    async def is_rate_limited(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        """
        Check if request is rate limited using sliding window.
        
        Args:
            key: Unique identifier for the rate limit
            limit: Number of requests allowed
            window: Time window in seconds
            
        Returns:
            Tuple of (is_limited, remaining_requests)
        """
        redis_client = await self.get_redis()
        
        now = int(time.time())
        pipeline = redis_client.pipeline()
        
        # Remove old entries
        pipeline.zremrangebyscore(key, 0, now - window)
        
        # Count current requests
        pipeline.zcard(key)
        
        # Add current request
        pipeline.zadd(key, {str(now): now})
        
        # Set expiration
        pipeline.expire(key, window)
        
        results = await pipeline.execute()
        current_requests = results[1]
        
        is_limited = current_requests >= limit
        remaining = max(0, limit - current_requests - 1)
        
        return is_limited, remaining

    def get_rate_limit_key(self, request: Request) -> str:
        """Generate rate limit key based on request context."""
        # Use tenant ID if available, otherwise fall back to IP
        if hasattr(request.state, "tenant_id") and request.state.tenant_id:
            return f"rate_limit:tenant:{request.state.tenant_id}"
        else:
            client_ip = request.client.host if request.client else "unknown"
            return f"rate_limit:ip:{client_ip}"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        
        # Skip rate limiting for certain paths
        skip_paths = {"/health", "/docs", "/redoc", "/openapi.json"}
        if request.url.path in skip_paths:
            return await call_next(request)

        try:
            # Check rate limit
            key = self.get_rate_limit_key(request)
            is_limited, remaining = await self.is_rate_limited(
                key,
                settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
                60  # 1 minute window
            )
            
            if is_limited:
                logger.warning(
                    "Rate limit exceeded",
                    key=key,
                    limit=settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
                )
                
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "details": {
                            "limit": settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
                            "window": "1 minute",
                            "retry_after": 60,
                        },
                    },
                    headers={
                        "X-RateLimit-Limit": str(settings.RATE_LIMIT_REQUESTS_PER_MINUTE),
                        "X-RateLimit-Remaining": str(remaining),
                        "X-RateLimit-Reset": str(int(time.time()) + 60),
                        "Retry-After": "60",
                    },
                )

            # Process request
            response = await call_next(request)
            
            # Add rate limit headers to successful responses
            response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_REQUESTS_PER_MINUTE)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)
            
            return response
            
        except Exception as e:
            # If Redis is down, don't block requests but log the error
            logger.error("Rate limiting error", error=str(e))
            return await call_next(request)

