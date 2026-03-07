"""Retry decorators for LLM calls with exponential backoff.

V4.3: Robust error handling for external API calls.
"""

from __future__ import annotations

import asyncio
import logging
from functools import wraps
from typing import Callable, TypeVar, Any, Optional
from time import sleep

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 10.0,
        exponential_base: float = 2.0,
        retryable_exceptions: tuple = (Exception,),
        on_retry: Optional[Callable[[Exception, int], None]] = None
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retryable_exceptions = retryable_exceptions
        self.on_retry = on_retry


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay with exponential backoff and jitter."""
    import random
    delay = min(
        config.base_delay * (config.exponential_base ** attempt),
        config.max_delay
    )
    # Add jitter (±10%) to avoid thundering herd
    jitter = delay * 0.1 * (2 * random.random() - 1)
    return delay + jitter


def retry_async(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    retryable_exceptions: tuple = (Exception,),
    on_failure_return: Any = None
):
    """Decorator for async functions with retry logic.
    
    Args:
        max_attempts: Maximum number of attempts
        base_delay: Initial delay between retries
        max_delay: Maximum delay cap
        retryable_exceptions: Tuple of exceptions to catch
        on_failure_return: Value to return if all retries fail
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            config = RetryConfig(
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
                retryable_exceptions=retryable_exceptions
            )
            
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts - 1:
                        delay = calculate_delay(attempt, config)
                        logger.warning(
                            f"[Retry] {func.__name__} failed (attempt {attempt + 1}/{max_attempts}): {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"[Retry] {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
            
            # All retries exhausted
            if on_failure_return is not None:
                logger.warning(f"[Retry] Returning fallback value after failures")
                return on_failure_return
            
            # Re-raise the last exception
            raise last_exception
        
        return wrapper
    return decorator


def retry_sync(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    retryable_exceptions: tuple = (Exception,),
    on_failure_return: Any = None
):
    """Decorator for sync functions with retry logic."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            config = RetryConfig(
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
                retryable_exceptions=retryable_exceptions
            )
            
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts - 1:
                        delay = calculate_delay(attempt, config)
                        logger.warning(
                            f"[Retry] {func.__name__} failed (attempt {attempt + 1}/{max_attempts}): {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        sleep(delay)
                    else:
                        logger.error(
                            f"[Retry] {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
            
            if on_failure_return is not None:
                return on_failure_return
            
            raise last_exception
        
        return wrapper
    return decorator


# Pre-configured decorators for common use cases

llm_retry = retry_async(
    max_attempts=3,
    base_delay=1.0,
    retryable_exceptions=(
        ConnectionError,
        TimeoutError,
        Exception  # Can be made more specific
    ),
    on_failure_return=None
)

media_retry = retry_async(
    max_attempts=2,
    base_delay=2.0,
    max_delay=30.0,
    retryable_exceptions=(ConnectionError, TimeoutError)
)

db_retry = retry_async(
    max_attempts=3,
    base_delay=0.5,
    retryable_exceptions=(ConnectionError,)
)
