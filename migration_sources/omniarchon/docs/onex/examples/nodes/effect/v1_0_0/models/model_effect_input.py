"""Effect operation input model."""

import uuid
from datetime import datetime
from typing import Dict

from omnibase_core.core.common_types import ModelScalarValue
from pydantic import BaseModel, Field

from .enum_effect_type import EnumEffectType


class ModelEffectInput(BaseModel):
    """
    Strongly typed input model for Effect operations.

    CANONICAL PATTERN: All fields have explicit types and descriptions.
    Optional fields use Field(default=...) for clear intent.

    Fields:
        effect_type: Type of side effect operation
        operation_data: Operation-specific parameters (type-safe scalars)
        operation_id: Unique identifier for operation tracking
        transaction_enabled: Enable transaction management with rollback
        retry_enabled: Enable automatic retry on failures
        max_retries: Maximum retry attempts before giving up
        retry_delay_ms: Base delay between retries (exponential backoff)
        circuit_breaker_enabled: Enable circuit breaker for this operation
        timeout_ms: Maximum operation execution time
        metadata: Additional context for operation
        timestamp: Operation creation timestamp
    """

    effect_type: EnumEffectType = Field(
        ..., description="Type of side effect operation to perform"
    )

    operation_data: Dict[str, ModelScalarValue] = Field(
        ..., description="Operation-specific data with type-safe scalar values"
    )

    operation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique operation identifier for tracking and correlation",
    )

    transaction_enabled: bool = Field(
        default=True,
        description="Enable transaction management with automatic rollback support",
    )

    retry_enabled: bool = Field(
        default=True, description="Enable automatic retry with exponential backoff"
    )

    max_retries: int = Field(
        default=3, ge=0, le=10, description="Maximum number of retry attempts (0-10)"
    )

    retry_delay_ms: int = Field(
        default=1000,
        ge=100,
        le=60000,
        description="Base retry delay in milliseconds (exponential backoff applied)",
    )

    circuit_breaker_enabled: bool = Field(
        default=False,
        description="Enable circuit breaker pattern for external service protection",
    )

    timeout_ms: int = Field(
        default=30000,
        ge=1000,
        le=300000,
        description="Operation timeout in milliseconds (1s-5min)",
    )

    metadata: Dict[str, ModelScalarValue] = Field(
        default_factory=dict, description="Additional metadata for operation context"
    )

    timestamp: datetime = Field(
        default_factory=datetime.now, description="Operation creation timestamp"
    )

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True
        use_enum_values = False  # Keep enum objects, don't convert to strings
