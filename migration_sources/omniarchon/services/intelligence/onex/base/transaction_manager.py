"""
Lightweight Transaction Manager for ONEX Effect Nodes

Provides transaction context management for effect operations with logging
and error handling support.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class TransactionContext:
    """Represents a single transaction context."""

    def __init__(self, transaction_id: Optional[UUID] = None):
        self.transaction_id = transaction_id or uuid4()
        self.start_time = datetime.now(timezone.utc)
        self.end_time: Optional[datetime] = None
        self.success: bool = False
        self.error: Optional[Exception] = None

    @property
    def duration_ms(self) -> float:
        """Calculate transaction duration in milliseconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return (datetime.now(timezone.utc) - self.start_time).total_seconds() * 1000


class LightweightTransactionManager:
    """
    Lightweight transaction manager for ONEX effect nodes.

    Provides:
    - Transaction ID tracking for correlation
    - Performance monitoring
    - Error context capture
    - Structured logging
    """

    def __init__(self):
        self.current_context: Optional[TransactionContext] = None

    @asynccontextmanager
    async def begin(self, transaction_id: Optional[UUID] = None):
        """
        Begin a new transaction context.

        Args:
            transaction_id: Optional transaction ID for correlation

        Yields:
            TransactionContext: The active transaction context
        """
        context = TransactionContext(transaction_id)
        self.current_context = context

        logger.info(
            "Transaction started",
            extra={
                "transaction_id": str(context.transaction_id),
                "timestamp": context.start_time.isoformat(),
            },
        )

        try:
            yield context
            context.success = True
            logger.info(
                "Transaction completed successfully",
                extra={
                    "transaction_id": str(context.transaction_id),
                    "duration_ms": context.duration_ms,
                },
            )
        except Exception as e:
            context.success = False
            context.error = e
            logger.error(
                f"Transaction failed: {str(e)}",
                extra={
                    "transaction_id": str(context.transaction_id),
                    "duration_ms": context.duration_ms,
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise
        finally:
            context.end_time = datetime.now(timezone.utc)
            self.current_context = None
