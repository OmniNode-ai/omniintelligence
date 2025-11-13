"""Transaction management with rollback support."""

import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from omnibase_core.core.core_structured_logging import (
    emit_log_event_sync as emit_log_event,
)
from omnibase_core.enums.enum_log_level import EnumLogLevel as LogLevel

from ..models.enum_transaction_state import EnumTransactionState


class Transaction:
    """
    Transaction manager for side effect operations with rollback support.

    CANONICAL PATTERN: Every side effect operation can register a rollback
    function. If the transaction fails, all rollback operations are executed
    in reverse order (LIFO - Last In, First Out).

    Usage:
        transaction = Transaction("op-123")
        transaction.add_operation(
            "create_file",
            {"path": "/tmp/test.txt"},
            rollback_func=lambda: os.remove("/tmp/test.txt")
        )
        await transaction.commit()  # Success
        # or
        await transaction.rollback()  # Failure - executes rollback_func

    Attributes:
        transaction_id: Unique identifier for this transaction
        state: Current transaction state (PENDING, ACTIVE, etc.)
        operations: List of operations performed in this transaction
        rollback_operations: Stack of rollback functions (LIFO order)
        started_at: Transaction start timestamp
        committed_at: Transaction commit timestamp (None if not committed)
    """

    def __init__(self, transaction_id: str):
        """
        Initialize a new transaction.

        Args:
            transaction_id: Unique identifier for transaction tracking
        """
        self.transaction_id = transaction_id
        self.state = EnumTransactionState.PENDING
        self.operations: List[Dict[str, Any]] = []
        self.rollback_operations: List[Callable[..., Any]] = []
        self.started_at = datetime.now()
        self.committed_at: Optional[datetime] = None

    def add_operation(
        self,
        operation_name: str,
        operation_data: Dict[str, Any],
        rollback_func: Optional[Callable[..., Any]] = None,
    ) -> None:
        """
        Add an operation to the transaction with optional rollback function.

        CANONICAL PATTERN: Every destructive operation should provide a rollback
        function. Idempotent operations may skip rollback.

        Args:
            operation_name: Descriptive name for the operation
            operation_data: Operation parameters and context
            rollback_func: Optional function to reverse the operation

        Example:
            transaction.add_operation(
                "insert_user",
                {"user_id": 123, "name": "John"},
                rollback_func=lambda: delete_user(123)
            )
        """
        self.operations.append(
            {
                "name": operation_name,
                "data": operation_data,
                "timestamp": datetime.now(),
            }
        )

        if rollback_func:
            self.rollback_operations.append(rollback_func)

    async def commit(self) -> None:
        """
        Commit the transaction - marks it as successfully completed.

        CANONICAL PATTERN: Call commit() only after ALL operations succeed.
        Once committed, rollback operations are cleared (no longer needed).
        """
        self.state = EnumTransactionState.COMMITTED
        self.committed_at = datetime.now()
        # Clear rollback operations - no longer needed after successful commit
        self.rollback_operations.clear()

    async def rollback(self) -> None:
        """
        Rollback the transaction - execute all rollback operations in reverse order.

        CANONICAL PATTERN: Rollback operations are executed in LIFO order
        (Last In, First Out) to properly reverse the sequence of changes.
        Each rollback operation is wrapped in try/except to prevent cascading failures.
        """
        self.state = EnumTransactionState.ROLLED_BACK

        # Execute rollback operations in reverse order (LIFO)
        for rollback_func in reversed(self.rollback_operations):
            try:
                if asyncio.iscoroutinefunction(rollback_func):
                    await rollback_func()
                else:
                    rollback_func()
            except Exception as e:
                # Log rollback failure but continue with remaining rollbacks
                emit_log_event(
                    LogLevel.ERROR,
                    f"Rollback operation failed: {str(e)}",
                    {
                        "transaction_id": self.transaction_id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
