"""Effect operation output model."""

from datetime import datetime
from typing import Any, Dict, List

from omnibase_core.core.common_types import ModelScalarValue
from pydantic import BaseModel, Field

from .enum_effect_type import EnumEffectType
from .enum_transaction_state import EnumTransactionState


class ModelEffectOutput(BaseModel):
    """
    Strongly typed output model for Effect operations.

    CANONICAL PATTERN: Output models capture complete operation results
    including success/failure state, timing, and audit trail.

    Fields:
        result: Operation result data (type varies by operation)
        operation_id: Matching operation identifier from input
        effect_type: Type of operation that was performed
        transaction_state: Final transaction state
        processing_time_ms: Total processing duration
        retry_count: Number of retries performed
        side_effects_applied: List of side effects created
        rollback_operations: Instructions for reversing changes
        metadata: Additional result metadata
        timestamp: Operation completion timestamp
    """

    result: Any = Field(
        ..., description="Operation result data (structure varies by operation type)"
    )

    operation_id: str = Field(
        ..., description="Operation identifier matching the input"
    )

    effect_type: EnumEffectType = Field(
        ..., description="Type of operation that was performed"
    )

    transaction_state: EnumTransactionState = Field(
        ..., description="Final state of transaction (COMMITTED, ROLLED_BACK, etc.)"
    )

    processing_time_ms: float = Field(
        ..., ge=0.0, description="Total processing time in milliseconds"
    )

    retry_count: int = Field(
        default=0, ge=0, description="Number of retry attempts made"
    )

    side_effects_applied: List[str] = Field(
        default_factory=list,
        description="List of side effects that were successfully applied",
    )

    rollback_operations: List[str] = Field(
        default_factory=list,
        description="Instructions for reversing the applied side effects",
    )

    metadata: Dict[str, ModelScalarValue] = Field(
        default_factory=dict, description="Additional result metadata and context"
    )

    timestamp: datetime = Field(
        default_factory=datetime.now, description="Operation completion timestamp"
    )

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True
        use_enum_values = False
