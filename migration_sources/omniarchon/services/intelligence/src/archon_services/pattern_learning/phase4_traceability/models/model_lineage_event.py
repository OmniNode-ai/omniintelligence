#!/usr/bin/env python3
"""
Lineage Event Model - ONEX Compliant

Represents events in pattern lineage history for complete audit trail
and temporal analysis of pattern evolution.

Part of Track 3 Phase 4 - Pattern Traceability & Continuous Learning.

Author: Archon Intelligence Team
Date: 2025-10-02
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

# ============================================================================
# Enums
# ============================================================================


class EnumLineageEventType(str, Enum):
    """Type of event in pattern lineage history."""

    # Creation events
    PATTERN_CREATED = "pattern_created"  # New pattern created
    VERSION_CREATED = "version_created"  # New version of pattern created

    # Modification events
    PATTERN_MODIFIED = "pattern_modified"  # Pattern data modified
    METADATA_UPDATED = "metadata_updated"  # Metadata updated
    TAGS_UPDATED = "tags_updated"  # Tags updated

    # Lifecycle events
    PATTERN_ACTIVATED = "pattern_activated"  # Pattern activated
    PATTERN_DEPRECATED = "pattern_deprecated"  # Pattern deprecated
    PATTERN_ARCHIVED = "pattern_archived"  # Pattern archived
    PATTERN_MERGED = "pattern_merged"  # Pattern merged with another

    # Relationship events
    PARENT_ADDED = "parent_added"  # Parent relationship added
    CHILD_ADDED = "child_added"  # Child relationship added
    RELATIONSHIP_REMOVED = "relationship_removed"  # Relationship removed

    # Usage events
    PATTERN_APPLIED = "pattern_applied"  # Pattern applied/executed
    EXECUTION_SUCCEEDED = "execution_succeeded"  # Execution succeeded
    EXECUTION_FAILED = "execution_failed"  # Execution failed

    # Quality events
    QUALITY_ASSESSED = "quality_assessed"  # Quality assessment performed
    PERFORMANCE_MEASURED = "performance_measured"  # Performance measured
    FEEDBACK_RECEIVED = "feedback_received"  # User feedback received

    # Improvement events
    IMPROVEMENT_PROPOSED = "improvement_proposed"  # Improvement proposed
    IMPROVEMENT_VALIDATED = "improvement_validated"  # Improvement validated
    IMPROVEMENT_APPLIED = "improvement_applied"  # Improvement applied
    IMPROVEMENT_REJECTED = "improvement_rejected"  # Improvement rejected


class EnumEventSeverity(str, Enum):
    """Severity level of lineage event."""

    DEBUG = "debug"  # Debug-level event
    INFO = "info"  # Informational event
    WARNING = "warning"  # Warning event
    ERROR = "error"  # Error event
    CRITICAL = "critical"  # Critical event


class EnumEventActor(str, Enum):
    """Actor type that triggered the event."""

    SYSTEM = "system"  # System-triggered event
    USER = "user"  # User-triggered event
    AGENT = "agent"  # AI agent-triggered event
    AUTOMATION = "automation"  # Automation-triggered event


# ============================================================================
# Lineage Event Model
# ============================================================================


class ModelLineageEvent(BaseModel):
    """
    Event in pattern lineage history.

    Captures all significant events in pattern lifecycle for complete
    audit trail, temporal analysis, and debugging.

    Architecture:
        - PostgreSQL: Event log storage with JSONB payload
        - Time-series DB: Temporal analysis and event aggregation
        - Event stream: Real-time event processing
    """

    # Primary identification
    event_id: UUID = Field(default_factory=uuid4, description="Unique event identifier")

    # Event classification
    event_type: EnumLineageEventType = Field(..., description="Type of event")

    event_severity: EnumEventSeverity = Field(
        default=EnumEventSeverity.INFO, description="Severity level of event"
    )

    # Pattern reference
    pattern_id: UUID = Field(..., description="Pattern ID this event relates to")

    node_id: Optional[UUID] = Field(
        default=None,
        description="Lineage node ID (if event relates to specific version)",
    )

    # Temporal information
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When event occurred (UTC)",
    )

    # Actor information
    actor_type: EnumEventActor = Field(
        default=EnumEventActor.SYSTEM, description="Type of actor that triggered event"
    )

    actor_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="ID of actor (user ID, agent name, system component)",
    )

    # Event context
    correlation_id: UUID = Field(
        default_factory=uuid4, description="Correlation ID for linking related events"
    )

    session_id: Optional[UUID] = Field(
        default=None, description="Session ID if event occurred during user session"
    )

    execution_id: Optional[UUID] = Field(
        default=None, description="Execution ID from Track 2 intelligence hooks"
    )

    # Event details
    event_data: Dict[str, Any] = Field(
        default_factory=dict, description="Event-specific data and payload"
    )

    # Changes tracking
    changes: Optional[Dict[str, Any]] = Field(
        default=None, description="Before/after changes for modification events"
    )

    previous_state: Optional[Dict[str, Any]] = Field(
        default=None, description="Previous state before event"
    )

    new_state: Optional[Dict[str, Any]] = Field(
        default=None, description="New state after event"
    )

    # Error information (for error events)
    error_message: Optional[str] = Field(
        default=None, description="Error message if event relates to error"
    )

    error_details: Optional[Dict[str, Any]] = Field(
        default=None, description="Detailed error information"
    )

    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional event metadata"
    )

    tags: list[str] = Field(
        default_factory=list, description="Tags for categorization and filtering"
    )

    # Source information
    source_system: str = Field(
        default="pattern_learning_engine",
        description="System component that generated event",
    )

    source_version: Optional[str] = Field(
        default=None, description="Version of source system"
    )

    model_config = ConfigDict(
        json_encoders={UUID: str, datetime: lambda v: v.isoformat()},
        json_schema_extra={
            "example": {
                "event_id": "770e8400-e29b-41d4-a716-446655440003",
                "event_type": "pattern_applied",
                "event_severity": "info",
                "pattern_id": "660e8400-e29b-41d4-a716-446655440001",
                "node_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2025-10-02T14:30:00Z",
                "actor_type": "agent",
                "actor_id": "agent-debug-intelligence",
                "correlation_id": "880e8400-e29b-41d4-a716-446655440004",
                "session_id": "990e8400-e29b-41d4-a716-446655440005",
                "execution_id": "aa0e8400-e29b-41d4-a716-446655440006",
                "event_data": {
                    "context": "api_development",
                    "execution_time_ms": 450.5,
                    "success": True,
                },
                "changes": None,
                "previous_state": None,
                "new_state": None,
                "error_message": None,
                "error_details": None,
                "metadata": {"source_file": "pattern_executor.py", "source_line": 142},
                "tags": ["execution", "api_development"],
                "source_system": "pattern_learning_engine",
                "source_version": "1.0.0",
            }
        },
    )

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def is_error_event(self) -> bool:
        """Check if this is an error event."""
        return self.event_severity in {
            EnumEventSeverity.ERROR,
            EnumEventSeverity.CRITICAL,
        }

    def is_lifecycle_event(self) -> bool:
        """Check if this is a lifecycle event."""
        lifecycle_types = {
            EnumLineageEventType.PATTERN_CREATED,
            EnumLineageEventType.PATTERN_ACTIVATED,
            EnumLineageEventType.PATTERN_DEPRECATED,
            EnumLineageEventType.PATTERN_ARCHIVED,
            EnumLineageEventType.PATTERN_MERGED,
        }
        return self.event_type in lifecycle_types

    def is_usage_event(self) -> bool:
        """Check if this is a usage event."""
        usage_types = {
            EnumLineageEventType.PATTERN_APPLIED,
            EnumLineageEventType.EXECUTION_SUCCEEDED,
            EnumLineageEventType.EXECUTION_FAILED,
        }
        return self.event_type in usage_types

    def is_modification_event(self) -> bool:
        """Check if this is a modification event."""
        modification_types = {
            EnumLineageEventType.PATTERN_MODIFIED,
            EnumLineageEventType.METADATA_UPDATED,
            EnumLineageEventType.TAGS_UPDATED,
        }
        return self.event_type in modification_types

    def has_changes(self) -> bool:
        """Check if event includes change tracking."""
        return self.changes is not None or (
            self.previous_state is not None and self.new_state is not None
        )

    def get_duration_since_event_ms(self) -> float:
        """
        Get milliseconds since event occurred.

        Returns:
            Duration in milliseconds
        """
        now = datetime.now(timezone.utc)
        delta = now - self.timestamp
        return delta.total_seconds() * 1000

    def to_audit_log_entry(self) -> Dict[str, Any]:
        """
        Convert to audit log entry format.

        Returns:
            Dictionary suitable for audit logging
        """
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type.value,
            "severity": self.event_severity.value,
            "pattern_id": str(self.pattern_id),
            "timestamp": self.timestamp.isoformat(),
            "actor": {"type": self.actor_type.value, "id": self.actor_id},
            "correlation_id": str(self.correlation_id),
            "has_error": self.is_error_event(),
            "error_message": self.error_message,
            "tags": self.tags,
        }

    def to_time_series_entry(self) -> Dict[str, Any]:
        """
        Convert to time-series database entry format.

        Returns:
            Dictionary suitable for time-series storage
        """
        return {
            "timestamp": int(self.timestamp.timestamp()),
            "event_type": self.event_type.value,
            "pattern_id": str(self.pattern_id),
            "severity": self.event_severity.value,
            "actor_type": self.actor_type.value,
            "has_error": self.is_error_event(),
            "tags": self.tags,
            "metadata": {
                "correlation_id": str(self.correlation_id),
                "session_id": str(self.session_id) if self.session_id else None,
                "execution_id": str(self.execution_id) if self.execution_id else None,
            },
        }

    @classmethod
    def create_pattern_created_event(
        cls,
        pattern_id: UUID,
        node_id: UUID,
        actor_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ModelLineageEvent":
        """
        Create a pattern created event.

        Args:
            pattern_id: Pattern ID
            node_id: Node ID
            actor_id: Actor ID
            metadata: Optional metadata

        Returns:
            New pattern created event
        """
        return cls(
            event_type=EnumLineageEventType.PATTERN_CREATED,
            event_severity=EnumEventSeverity.INFO,
            pattern_id=pattern_id,
            node_id=node_id,
            actor_type=EnumEventActor.SYSTEM,
            actor_id=actor_id,
            metadata=metadata or {},
        )

    @classmethod
    def create_execution_event(
        cls,
        pattern_id: UUID,
        node_id: UUID,
        execution_id: UUID,
        success: bool,
        actor_id: str,
        execution_time_ms: float,
        error_message: Optional[str] = None,
    ) -> "ModelLineageEvent":
        """
        Create an execution event.

        Args:
            pattern_id: Pattern ID
            node_id: Node ID
            execution_id: Execution ID
            success: Whether execution succeeded
            actor_id: Actor ID
            execution_time_ms: Execution time
            error_message: Optional error message

        Returns:
            New execution event
        """
        event_type = (
            EnumLineageEventType.EXECUTION_SUCCEEDED
            if success
            else EnumLineageEventType.EXECUTION_FAILED
        )
        severity = EnumEventSeverity.INFO if success else EnumEventSeverity.ERROR

        return cls(
            event_type=event_type,
            event_severity=severity,
            pattern_id=pattern_id,
            node_id=node_id,
            execution_id=execution_id,
            actor_type=EnumEventActor.AGENT,
            actor_id=actor_id,
            event_data={"execution_time_ms": execution_time_ms, "success": success},
            error_message=error_message if not success else None,
        )

    @classmethod
    def create_deprecation_event(
        cls,
        pattern_id: UUID,
        node_id: UUID,
        actor_id: str,
        reason: str,
        replaced_by_node_id: Optional[UUID] = None,
    ) -> "ModelLineageEvent":
        """
        Create a pattern deprecation event.

        Args:
            pattern_id: Pattern ID
            node_id: Node ID
            actor_id: Actor ID
            reason: Deprecation reason
            replaced_by_node_id: Optional replacement node ID

        Returns:
            New deprecation event
        """
        return cls(
            event_type=EnumLineageEventType.PATTERN_DEPRECATED,
            event_severity=EnumEventSeverity.WARNING,
            pattern_id=pattern_id,
            node_id=node_id,
            actor_type=EnumEventActor.SYSTEM,
            actor_id=actor_id,
            event_data={
                "reason": reason,
                "replaced_by_node_id": (
                    str(replaced_by_node_id) if replaced_by_node_id else None
                ),
            },
        )
