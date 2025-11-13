"""
ModelRoutingContext for HybridEventRouter routing decisions.

This model provides context information to the HybridEventRouter for making
intelligent routing decisions between Kafka and in-memory publishers.

Created: 2025-10-14
Purpose: Enable intelligent event routing based on context and requirements
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ModelRoutingContext(BaseModel):
    """
    Context information for intelligent event routing decisions.

    Used by HybridEventRouter to determine the optimal publisher
    (Kafka vs in-memory) based on operational requirements and context.

    Attributes:
        requires_persistence: Whether the event requires durable persistence (favors Kafka)
        is_cross_service: Whether the event crosses service boundaries (favors Kafka)
        is_test_environment: Whether running in test environment (favors in-memory)
        is_local_tool: Whether the event is for local tool usage (favors in-memory)
        priority_level: Event priority level (optional, for future routing logic)
        service_name: Source service name (optional, for tracking)
    """

    requires_persistence: bool = Field(
        default=False, description="Event requires durable persistence (favors Kafka)"
    )

    is_cross_service: bool = Field(
        default=False, description="Event crosses service boundaries (favors Kafka)"
    )

    is_test_environment: bool = Field(
        default=False, description="Running in test environment (favors in-memory)"
    )

    is_local_tool: bool = Field(
        default=False, description="Event is for local tool usage (favors in-memory)"
    )

    priority_level: Optional[str] = Field(
        default=None, description="Priority level: CRITICAL, HIGH, NORMAL, LOW"
    )

    service_name: Optional[str] = Field(
        default=None, description="Source service name for tracking"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "requires_persistence": True,
                "is_cross_service": True,
                "is_test_environment": False,
                "is_local_tool": False,
                "priority_level": "HIGH",
                "service_name": "archon-intelligence",
            }
        }
    )
