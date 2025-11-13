"""
Intelligence Events API Models

Pydantic models for event stream responses.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class EventData(BaseModel):
    """Base event data model"""

    id: UUID = Field(description="Unique event identifier")
    type: Literal["agent_action", "routing_decision", "error"] = Field(
        description="Event type classification"
    )
    timestamp: datetime = Field(description="Event occurrence timestamp")
    correlation_id: UUID = Field(description="Correlation ID linking related events")
    agent_name: str = Field(description="Agent name associated with event")
    data: Dict[str, Any] = Field(
        default_factory=dict, description="Event-specific data"
    )


class AgentActionEvent(EventData):
    """Agent action event model"""

    type: Literal["agent_action"] = "agent_action"
    action_type: str = Field(
        description="Action type: tool_call, decision, error, success"
    )
    action_name: str = Field(description="Specific action name")
    duration_ms: Optional[int] = Field(
        None, description="Action duration in milliseconds"
    )


class RoutingDecisionEvent(EventData):
    """Routing decision event model"""

    type: Literal["routing_decision"] = "routing_decision"
    agent_selected: str = Field(description="Selected agent")
    confidence_score: float = Field(description="Routing confidence score (0.0-1.0)")
    routing_strategy: str = Field(description="Strategy used for routing")
    decision_duration_ms: Optional[int] = Field(
        None, description="Decision duration in milliseconds"
    )


class ErrorEvent(EventData):
    """Error event model"""

    type: Literal["error"] = "error"
    error_type: str = Field(description="Error classification")
    error_message: str = Field(description="Error description")


class EventsStreamResponse(BaseModel):
    """Events stream response model"""

    events: List[EventData] = Field(
        description="List of events ordered by timestamp descending"
    )
    total: int = Field(description="Total number of events in response")
    time_range: Dict[str, datetime] = Field(
        description="Time range of events (start_time, end_time)"
    )
    event_counts: Dict[str, int] = Field(description="Count of events by type")


class EventsStreamFilters(BaseModel):
    """Query filters for event stream"""

    limit: int = Field(
        default=100, ge=1, le=1000, description="Maximum number of events to return"
    )
    event_type: Optional[Literal["agent_action", "routing_decision", "error"]] = Field(
        None, description="Filter by event type"
    )
    agent_name: Optional[str] = Field(None, description="Filter by agent name")
    correlation_id: Optional[UUID] = Field(None, description="Filter by correlation ID")
    hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Time window in hours (default: 24h, max: 7 days)",
    )
