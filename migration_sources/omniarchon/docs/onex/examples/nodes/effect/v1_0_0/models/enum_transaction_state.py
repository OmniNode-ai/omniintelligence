"""Transaction state enum."""

from enum import Enum


class EnumTransactionState(Enum):
    """
    Transaction state tracking for side effect operations.

    State machine: PENDING → ACTIVE → (COMMITTED | ROLLED_BACK | FAILED)
    """

    PENDING = "pending"
    ACTIVE = "active"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"
