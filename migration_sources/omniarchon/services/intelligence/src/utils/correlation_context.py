"""
Correlation ID Context Manager for Distributed Tracing

Provides a context manager that automatically attaches correlation IDs to all logs
within a scope, enabling distributed tracing across service boundaries.

Usage:
    from utils.correlation_context import correlation_context
    from uuid import uuid4

    # Automatic correlation ID generation
    async with correlation_context():
        logger.info("This log includes correlation_id automatically")

    # Explicit correlation ID (e.g., from HTTP header)
    correlation_id = uuid4()
    async with correlation_context(correlation_id):
        logger.info("This log includes the specified correlation_id")

    # Access current correlation ID
    from utils.correlation_context import get_correlation_id
    current_id = get_correlation_id()
"""

import logging
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from typing import Optional
from uuid import UUID, uuid4

# Context variable to store correlation ID per async task
_correlation_id_var: ContextVar[Optional[UUID]] = ContextVar(
    "correlation_id", default=None
)


def get_correlation_id() -> Optional[UUID]:
    """
    Get the current correlation ID from context.

    Returns:
        Current correlation ID if set, None otherwise
    """
    return _correlation_id_var.get()


def set_correlation_id(correlation_id: Optional[UUID]) -> None:
    """
    Set the correlation ID in context.

    Args:
        correlation_id: Correlation ID to set (or None to clear)
    """
    _correlation_id_var.set(correlation_id)


@asynccontextmanager
async def correlation_context(correlation_id: Optional[UUID] = None):
    """
    Async context manager for correlation ID propagation.

    Automatically sets and clears correlation ID in the context.
    If no correlation_id is provided, generates a new UUID.

    Args:
        correlation_id: Optional correlation ID. If None, generates new UUID.

    Yields:
        The correlation ID being used

    Example:
        async with correlation_context() as corr_id:
            logger.info(f"Processing | correlation_id={corr_id}")
            # All logs in this scope automatically include correlation_id
    """
    # Generate correlation ID if not provided
    if correlation_id is None:
        correlation_id = uuid4()

    # Store previous value to restore later
    previous_id = _correlation_id_var.get()

    try:
        # Set correlation ID in context
        _correlation_id_var.set(correlation_id)

        # Install logging filter to add correlation_id to all log records
        filter_instance = CorrelationIdFilter()
        logging.root.addFilter(filter_instance)

        yield correlation_id

    finally:
        # Remove logging filter
        logging.root.removeFilter(filter_instance)

        # Restore previous correlation ID
        _correlation_id_var.set(previous_id)


@contextmanager
def correlation_context_sync(correlation_id: Optional[UUID] = None):
    """
    Synchronous context manager for correlation ID propagation.

    Use this for synchronous code. For async code, use correlation_context().

    Args:
        correlation_id: Optional correlation ID. If None, generates new UUID.

    Yields:
        The correlation ID being used

    Example:
        with correlation_context_sync() as corr_id:
            logger.info(f"Processing | correlation_id={corr_id}")
    """
    # Generate correlation ID if not provided
    if correlation_id is None:
        correlation_id = uuid4()

    # Store previous value to restore later
    previous_id = _correlation_id_var.get()

    try:
        # Set correlation ID in context
        _correlation_id_var.set(correlation_id)

        # Install logging filter to add correlation_id to all log records
        filter_instance = CorrelationIdFilter()
        logging.root.addFilter(filter_instance)

        yield correlation_id

    finally:
        # Remove logging filter
        logging.root.removeFilter(filter_instance)

        # Restore previous correlation ID
        _correlation_id_var.set(previous_id)


class CorrelationIdFilter(logging.Filter):
    """
    Logging filter that adds correlation_id to log records.

    This filter automatically adds the current correlation ID from context
    to all log records, making it available in log formatters.

    Usage:
        # Add to logger
        logger.addFilter(CorrelationIdFilter())

        # Use in format string
        logging.basicConfig(
            format='%(levelname)s | %(name)s | correlation_id=%(correlation_id)s | %(message)s'
        )
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add correlation_id to log record.

        Args:
            record: Log record to modify

        Returns:
            Always True (never filters out records)
        """
        correlation_id = _correlation_id_var.get()

        # Add correlation_id to record (as string for easy formatting)
        if correlation_id:
            record.correlation_id = str(correlation_id)
        else:
            record.correlation_id = "none"

        return True


class CorrelationIdFormatter(logging.Formatter):
    """
    Custom log formatter that includes correlation_id.

    This formatter automatically includes correlation_id in log output
    with a consistent format.

    Usage:
        handler = logging.StreamHandler()
        handler.setFormatter(CorrelationIdFormatter(
            fmt='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
        ))
        logger.addHandler(handler)
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with correlation_id.

        Args:
            record: Log record to format

        Returns:
            Formatted log string with correlation_id
        """
        # Ensure correlation_id is present
        if not hasattr(record, "correlation_id"):
            correlation_id = _correlation_id_var.get()
            record.correlation_id = str(correlation_id) if correlation_id else "none"

        return super().format(record)


# Convenience function for FastAPI dependency injection
def get_correlation_id_dependency() -> Optional[UUID]:
    """
    FastAPI dependency for getting correlation_id from context.

    Can be used as a FastAPI dependency to inject correlation_id
    into route handlers.

    Usage:
        from fastapi import Depends

        @router.get("/endpoint")
        async def endpoint(
            correlation_id: UUID = Depends(get_correlation_id_dependency)
        ):
            logger.info(f"Handling request | correlation_id={correlation_id}")
    """
    return get_correlation_id()


# Example usage demonstration
if __name__ == "__main__":
    import asyncio

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | correlation_id=%(correlation_id)s | %(message)s",
    )

    logger = logging.getLogger(__name__)

    async def demo():
        """Demonstrate correlation context usage"""
        # Example 1: Auto-generated correlation ID
        async with correlation_context() as corr_id:
            logger.info(f"Starting operation with auto-generated ID: {corr_id}")
            logger.info("Processing step 1")
            logger.info("Processing step 2")

        # Example 2: Explicit correlation ID (e.g., from HTTP header)
        explicit_id = uuid4()
        async with correlation_context(explicit_id) as corr_id:
            logger.info(f"Starting operation with explicit ID: {corr_id}")
            logger.info("Processing with provided correlation_id")

        # Example 3: Nested contexts
        async with correlation_context() as outer_id:
            logger.info(f"Outer context: {outer_id}")

            async with correlation_context() as inner_id:
                logger.info(f"Inner context: {inner_id}")

            logger.info(f"Back to outer context: {get_correlation_id()}")

    asyncio.run(demo())
