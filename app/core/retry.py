"""Retry utilities with exponential backoff."""

import logging
import time
from typing import Callable, TypeVar, Optional

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_with_backoff(
    func: Callable[[], T],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple = (Exception,),
    log_errors: bool = True,
) -> T:
    """Retry a function with exponential backoff.
    
    Args:
        func: Function to retry
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        backoff_factor: Multiplier for delay after each retry
        retryable_exceptions: Tuple of exceptions that should trigger retry
        log_errors: Whether to log retry attempts
    
    Returns:
        Result of func() if successful
    
    Raises:
        Last exception if all retries fail
    """
    delay = initial_delay
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return func()
        except retryable_exceptions as e:
            last_exception = e
            
            if attempt < max_retries:
                if log_errors:
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                time.sleep(delay)
                delay = min(delay * backoff_factor, max_delay)
            else:
                if log_errors:
                    logger.error(
                        f"All {max_retries + 1} attempts failed. Last error: {e}",
                        exc_info=True,
                    )
                raise
    
    # Should never reach here, but type checker needs it
    if last_exception:
        raise last_exception
    raise RuntimeError("Retry failed without exception")





