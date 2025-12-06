"""
Intent Model for omniintelligence.

Intent models used for communication between reducers and orchestrators.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence._legacy.enums import EnumIntentType


def _utc_now() -> datetime:
    """Get current UTC time with timezone info."""
    return datetime.now(UTC)


class ModelIntent(BaseModel):
    """
    Intent emitted by reducers to orchestrators or effect nodes.

    Intents are the primary communication mechanism in the system,
    allowing pure reducers to request actions without side effects.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "intent_type": "WORKFLOW_TRIGGER",
                "target": "intelligence_orchestrator",
                "payload": {
                    "operation_type": "DOCUMENT_INGESTION",
                    "entity_id": "doc_123",
                },
                "correlation_id": "corr_456",
            }
        }
    )

    intent_type: EnumIntentType = Field(..., description="Type of intent")
    target: str = Field(..., description="Target node for this intent")
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Intent payload"
    )
    correlation_id: str = Field(..., description="Correlation ID for tracing")
    timestamp: datetime = Field(
        default_factory=_utc_now, description="Intent creation timestamp"
    )
    metadata: dict[str, Any] | None = Field(
        default=None, description="Additional metadata"
    )


__all__ = ["ModelIntent"]
