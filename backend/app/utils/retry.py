"""
Retry utilities using tenacity.
"""

import functools
from typing import Any, Callable, Type, Union

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.logging import get_logger

logger = get_logger(__name__)


def with_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    multiplier: float = 2.0,
    retry_on: Union[Type[Exception], tuple[Type[Exception], ...]] = Exception,
):
    """
    Decorator to add retry logic to functions.
    
    Args:
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time between retries (seconds)
        max_wait: Maximum wait time between retries (seconds)
        multiplier: Backoff multiplier
        retry_on: Exception types to retry on
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable) -> Callable:
        @retry(
            retry=retry_if_exception_type(retry_on),
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(
                multiplier=multiplier,
                min=min_wait,
                max=max_wait,
            ),
            reraise=True,
        )
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(
                    "Function call failed, retrying",
                    function=func.__name__,
                    error=str(e),
                )
                raise
        
        return wrapper
    
    return decorator


def with_async_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    multiplier: float = 2.0,
    retry_on: Union[Type[Exception], tuple[Type[Exception], ...]] = Exception,
):
    """
    Decorator to add retry logic to async functions.
    
    Args:
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time between retries (seconds)
        max_wait: Maximum wait time between retries (seconds)
        multiplier: Backoff multiplier
        retry_on: Exception types to retry on
        
    Returns:
        Decorated async function with retry logic
    """
    def decorator(func: Callable) -> Callable:
        @retry(
            retry=retry_if_exception_type(retry_on),
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(
                multiplier=multiplier,
                min=min_wait,
                max=max_wait,
            ),
            reraise=True,
        )
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.warning(
                    "Async function call failed, retrying",
                    function=func.__name__,
                    error=str(e),
                )
                raise
        
        return wrapper
    
    return decorator