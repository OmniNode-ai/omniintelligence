# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler for pattern storage operations.

This module contains the handler function for persisting learned patterns
to storage with governance invariants, idempotency, and version tracking.

Key Invariants:
    - Governance: Confidence must be >= 0.5 (MIN_CONFIDENCE)
    - Uniqueness: UNIQUE(domain, signature_hash, version)
    - Current Tracking: UNIQUE(domain, signature_hash) WHERE is_current = true
    - Immutable History: Never overwrite existing patterns, create new version
    - Idempotency: Same (event_id, signature_hash) returns same result

Lineage Key:
    Patterns are uniquely identified by (domain, signature_hash) for
    deduplication and version tracking across pattern versions.

Reference:
    - OMN-1668: Pattern storage effect node implementation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from omniintelligence.nodes.pattern_storage_effect.models import (
    EnumPatternState,
    ModelPatternStorageInput,
    ModelPatternStoredEvent,
    PatternStorageGovernance,
)


# =============================================================================
# Logging Configuration
# =============================================================================

logger = logging.getLogger(__name__)


# =============================================================================
# Protocol Definitions
# =============================================================================
# These protocols define the expected interfaces for injected dependencies.
# They are defined locally to avoid coupling to specific implementations while
# providing proper type hints for static analysis.
# =============================================================================


@runtime_checkable
class ProtocolPatternStore(Protocol):
    """Protocol for pattern storage operations.

    Defines the interface for persisting patterns to a database or other
    storage backend. Implementations must support version tracking via
    the is_current flag for lineage management.

    Database Schema Requirements:
        - UNIQUE(domain, signature_hash, version): No duplicate versions
        - UNIQUE(domain, signature_hash) WHERE is_current = true: Only one current
        - pattern_state_transitions table: Audit trail (future)

    Implementations should handle:
        - Idempotent storage (same pattern_id + signature_hash returns existing)
        - Version management (is_current flag transitions)
        - Atomic operations (set_previous_not_current + store_pattern)
    """

    async def store_pattern(
        self,
        *,
        pattern_id: UUID,
        signature: str,
        signature_hash: str,
        domain: str,
        version: int,
        confidence: float,
        state: EnumPatternState,
        is_current: bool,
        stored_at: datetime,
        actor: str | None = None,
        source_run_id: str | None = None,
        correlation_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UUID:
        """Store a pattern in the pattern database.

        Args:
            pattern_id: Unique identifier for this pattern instance.
            signature: The pattern signature (behavioral/structural fingerprint).
            signature_hash: Hash of the signature for efficient lookup.
            domain: Domain where the pattern was learned.
            version: Version number in the pattern lineage.
            confidence: Confidence score at storage time.
            state: Initial state of the pattern.
            is_current: Whether this is the current version for the lineage.
            stored_at: Timestamp when the pattern was stored.
            actor: Identifier of the entity that stored the pattern.
            source_run_id: ID of the run that produced this pattern.
            correlation_id: Correlation ID for distributed tracing.
            metadata: Additional metadata as key-value pairs.

        Returns:
            UUID of the stored pattern (may be same as pattern_id).

        Raises:
            PatternStorageError: If storage operation fails.
        """
        ...

    async def check_exists(
        self,
        domain: str,
        signature_hash: str,
        version: int,
    ) -> bool:
        """Check if a pattern already exists for the given lineage and version.

        This is used for idempotency checking before storage.

        Args:
            domain: Domain of the pattern (part of lineage key).
            signature_hash: Hash of the signature (part of lineage key).
            version: Version number to check.

        Returns:
            True if a pattern exists for (domain, signature_hash, version).
        """
        ...

    async def check_exists_by_id(
        self,
        pattern_id: UUID,
        signature_hash: str,
    ) -> UUID | None:
        """Check if a pattern exists by idempotency key.

        The idempotency key is (pattern_id, signature_hash). If a pattern
        was previously stored with the same idempotency key, return its
        stored ID for idempotent response.

        Args:
            pattern_id: The pattern_id from the incoming event.
            signature_hash: Hash of the signature.

        Returns:
            UUID of existing pattern if found, None otherwise.
        """
        ...

    async def set_previous_not_current(
        self,
        domain: str,
        signature_hash: str,
    ) -> int:
        """Set is_current = false for all previous versions of this lineage.

        This must be called before inserting a new current version to maintain
        the invariant: UNIQUE(domain, signature_hash) WHERE is_current = true.

        Args:
            domain: Domain of the pattern (part of lineage key).
            signature_hash: Hash of the signature (part of lineage key).

        Returns:
            Number of rows updated (0 if no previous versions existed).
        """
        ...

    async def get_latest_version(
        self,
        domain: str,
        signature_hash: str,
    ) -> int | None:
        """Get the latest version number for a pattern lineage.

        Used to determine the next version number when storing a new pattern.

        Args:
            domain: Domain of the pattern (part of lineage key).
            signature_hash: Hash of the signature (part of lineage key).

        Returns:
            Latest version number, or None if no versions exist.
        """
        ...


# =============================================================================
# Governance Validation
# =============================================================================


@dataclass(frozen=True)
class GovernanceViolation:
    """Represents a single governance rule violation.

    Attributes:
        rule: Name of the violated rule.
        message: Human-readable description of the violation.
        value: The value that caused the violation.
        threshold: The threshold or expected value.
    """

    rule: str
    message: str
    value: Any = None
    threshold: Any = None


@dataclass
class GovernanceResult:
    """Result of governance validation.

    Attributes:
        valid: Whether the input passes all governance checks.
        violations: List of governance violations (empty if valid).
        checked_at: Timestamp when validation was performed.
    """

    valid: bool
    violations: list[GovernanceViolation] = field(default_factory=list)
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def validate_governance(input_data: ModelPatternStorageInput) -> GovernanceResult:
    """Validate input against governance invariants.

    Checks all governance rules that cannot be bypassed. These are hard-coded
    constants that ensure consistent quality across all pattern storage.

    Governance Rules:
        - CONFIDENCE_THRESHOLD: confidence >= 0.5 (MIN_CONFIDENCE)

    Note: The ModelPatternStorageInput already validates confidence at the
    Pydantic model level. This function provides an explicit governance
    layer that can add additional rules and return detailed violations.

    Args:
        input_data: The pattern storage input to validate.

    Returns:
        GovernanceResult with valid=True if all checks pass, or
        valid=False with list of violations if any checks fail.

    Example:
        >>> result = validate_governance(input_data)
        >>> if not result.valid:
        ...     for v in result.violations:
        ...         print(f"Violation: {v.rule} - {v.message}")
    """
    violations: list[GovernanceViolation] = []

    # Rule 1: Confidence threshold (MIN_CONFIDENCE = 0.5)
    # This is also enforced by Pydantic, but explicit governance layer
    # provides auditability and allows for additional rules
    if input_data.confidence < PatternStorageGovernance.MIN_CONFIDENCE:
        violations.append(
            GovernanceViolation(
                rule="CONFIDENCE_THRESHOLD",
                message=(
                    f"Confidence {input_data.confidence} is below minimum threshold "
                    f"{PatternStorageGovernance.MIN_CONFIDENCE}"
                ),
                value=input_data.confidence,
                threshold=PatternStorageGovernance.MIN_CONFIDENCE,
            )
        )

    # Rule 2: Signature must not be empty
    if not input_data.signature or not input_data.signature.strip():
        violations.append(
            GovernanceViolation(
                rule="SIGNATURE_REQUIRED",
                message="Pattern signature cannot be empty",
                value=input_data.signature,
                threshold="non-empty string",
            )
        )

    # Rule 3: Domain must not be empty
    if not input_data.domain or not input_data.domain.strip():
        violations.append(
            GovernanceViolation(
                rule="DOMAIN_REQUIRED",
                message="Pattern domain cannot be empty",
                value=input_data.domain,
                threshold="non-empty string",
            )
        )

    return GovernanceResult(
        valid=len(violations) == 0,
        violations=violations,
    )


# =============================================================================
# Audit Trail Support
# =============================================================================


@dataclass(frozen=True)
class PatternStateTransition:
    """Record of a pattern state transition for audit trail.

    This dataclass represents a row that would be inserted into
    the pattern_state_transitions table for governance compliance
    and debugging.

    Attributes:
        pattern_id: The pattern this transition belongs to.
        from_state: Previous state (None for initial storage).
        to_state: New state after transition.
        reason: Human-readable reason for the transition.
        actor: Entity that triggered the transition.
        correlation_id: Correlation ID for distributed tracing.
        transitioned_at: Timestamp of the transition.
        metadata: Additional context for the transition.
    """

    pattern_id: UUID
    from_state: EnumPatternState | None
    to_state: EnumPatternState
    reason: str
    actor: str | None
    correlation_id: UUID | None
    transitioned_at: datetime
    metadata: dict[str, Any] | None = None


def create_initial_storage_transition(
    pattern_id: UUID,
    state: EnumPatternState,
    actor: str | None,
    correlation_id: UUID | None,
) -> PatternStateTransition:
    """Create an audit trail record for initial pattern storage.

    Args:
        pattern_id: The pattern being stored.
        state: Initial state (typically CANDIDATE).
        actor: Entity storing the pattern.
        correlation_id: Correlation ID for tracing.

    Returns:
        PatternStateTransition record for audit trail.
    """
    return PatternStateTransition(
        pattern_id=pattern_id,
        from_state=None,  # Initial storage has no previous state
        to_state=state,
        reason="Initial pattern storage",
        actor=actor,
        correlation_id=correlation_id,
        transitioned_at=datetime.now(UTC),
        metadata={"operation": "store_pattern"},
    )


# =============================================================================
# Main Handler
# =============================================================================


@dataclass
class StorePatternResult:
    """Internal result from store pattern operation.

    Attributes:
        success: Whether the operation succeeded.
        event: The stored event if successful.
        was_idempotent: True if this was an idempotent return (already existed).
        error_message: Error message if failed.
        governance_violations: List of governance violations if rejected.
    """

    success: bool
    event: ModelPatternStoredEvent | None = None
    was_idempotent: bool = False
    error_message: str | None = None
    governance_violations: list[GovernanceViolation] | None = None


async def handle_store_pattern(
    input_data: ModelPatternStorageInput,
    *,
    pattern_store: ProtocolPatternStore | None = None,
) -> ModelPatternStoredEvent:
    """Store a learned pattern with governance enforcement.

    This handler implements the following invariants:
        1. Governance: Reject if confidence < MIN_CONFIDENCE (0.5)
        2. Idempotency: If (pattern_id, signature_hash) exists, return existing
        3. Version Management: Set previous is_current = false
        4. Storage: Insert new pattern with is_current = true
        5. Audit: Log state transition for governance trail

    The handler is designed to be idempotent - calling with the same
    (pattern_id, signature_hash) will return the same result without
    side effects.

    Args:
        input_data: The pattern to store, validated against governance rules.
        pattern_store: Optional pattern store implementing ProtocolPatternStore.
            If not provided, a mock response is returned for testing.

    Returns:
        ModelPatternStoredEvent with storage confirmation.

    Raises:
        ValueError: If governance validation fails (confidence below threshold).
        RuntimeError: If storage operation fails unexpectedly.

    Example:
        >>> from omniintelligence.nodes.pattern_storage_effect.models import (
        ...     ModelPatternStorageInput,
        ... )
        >>> input_data = ModelPatternStorageInput(
        ...     pattern_id=uuid4(),
        ...     signature="def.*return.*None",
        ...     signature_hash="abc123",
        ...     domain="code_patterns",
        ...     confidence=0.85,
        ... )
        >>> event = await handle_store_pattern(input_data, pattern_store=store)
        >>> print(f"Stored pattern {event.pattern_id} version {event.version}")
    """
    # -------------------------------------------------------------------------
    # Step 1: Validate governance invariants
    # -------------------------------------------------------------------------
    governance_result = validate_governance(input_data)

    if not governance_result.valid:
        violation_messages = "; ".join(v.message for v in governance_result.violations)
        logger.warning(
            "Pattern rejected due to governance violations",
            extra={
                "pattern_id": str(input_data.pattern_id),
                "domain": input_data.domain,
                "signature_hash": input_data.signature_hash,
                "violations": [v.rule for v in governance_result.violations],
                "correlation_id": str(input_data.correlation_id)
                if input_data.correlation_id
                else None,
            },
        )
        msg = f"Governance validation failed: {violation_messages}"
        raise ValueError(msg)

    logger.debug(
        "Governance validation passed",
        extra={
            "pattern_id": str(input_data.pattern_id),
            "confidence": input_data.confidence,
            "domain": input_data.domain,
        },
    )

    # -------------------------------------------------------------------------
    # Step 2: Handle case where no pattern_store is provided (testing mode)
    # -------------------------------------------------------------------------
    stored_at = datetime.now(UTC)

    if pattern_store is None:
        logger.info(
            "No pattern_store provided, returning mock event",
            extra={
                "pattern_id": str(input_data.pattern_id),
                "domain": input_data.domain,
            },
        )
        return ModelPatternStoredEvent(
            pattern_id=input_data.pattern_id,
            signature=input_data.signature,
            signature_hash=input_data.signature_hash,
            domain=input_data.domain,
            version=input_data.version,
            confidence=input_data.confidence,
            state=EnumPatternState.CANDIDATE,
            stored_at=stored_at,
            actor=input_data.metadata.actor,
            source_run_id=input_data.metadata.source_run_id,
            correlation_id=input_data.correlation_id,
        )

    # -------------------------------------------------------------------------
    # Step 3: Check idempotency (same event_id + signature_hash = same result)
    # -------------------------------------------------------------------------
    existing_id = await pattern_store.check_exists_by_id(
        pattern_id=input_data.pattern_id,
        signature_hash=input_data.signature_hash,
    )

    if existing_id is not None:
        logger.info(
            "Idempotent return: pattern already exists",
            extra={
                "pattern_id": str(input_data.pattern_id),
                "existing_id": str(existing_id),
                "domain": input_data.domain,
                "signature_hash": input_data.signature_hash,
                "correlation_id": str(input_data.correlation_id)
                if input_data.correlation_id
                else None,
            },
        )
        # Return event for existing pattern (idempotent behavior)
        return ModelPatternStoredEvent(
            pattern_id=existing_id,
            signature=input_data.signature,
            signature_hash=input_data.signature_hash,
            domain=input_data.domain,
            version=input_data.version,
            confidence=input_data.confidence,
            state=EnumPatternState.CANDIDATE,
            stored_at=stored_at,  # Use current time for event, not original storage time
            actor=input_data.metadata.actor,
            source_run_id=input_data.metadata.source_run_id,
            correlation_id=input_data.correlation_id,
        )

    # -------------------------------------------------------------------------
    # Step 4: Determine version number
    # -------------------------------------------------------------------------
    # If input specifies version > 1, check if it makes sense
    # Otherwise, auto-increment from latest version
    latest_version = await pattern_store.get_latest_version(
        domain=input_data.domain,
        signature_hash=input_data.signature_hash,
    )

    if latest_version is not None:
        # New version in existing lineage
        version = latest_version + 1
        logger.debug(
            "Auto-incrementing version for existing lineage",
            extra={
                "domain": input_data.domain,
                "signature_hash": input_data.signature_hash,
                "latest_version": latest_version,
                "new_version": version,
            },
        )
    else:
        # First version in new lineage
        version = 1
        logger.debug(
            "First version in new lineage",
            extra={
                "domain": input_data.domain,
                "signature_hash": input_data.signature_hash,
                "version": version,
            },
        )

    # -------------------------------------------------------------------------
    # Step 5: Set previous versions as not current
    # -------------------------------------------------------------------------
    # This maintains the invariant: UNIQUE(domain, signature_hash) WHERE is_current = true
    updated_count = await pattern_store.set_previous_not_current(
        domain=input_data.domain,
        signature_hash=input_data.signature_hash,
    )

    if updated_count > 0:
        logger.debug(
            "Set previous versions as not current",
            extra={
                "domain": input_data.domain,
                "signature_hash": input_data.signature_hash,
                "updated_count": updated_count,
            },
        )

    # -------------------------------------------------------------------------
    # Step 6: Store the new pattern with is_current = true
    # -------------------------------------------------------------------------
    initial_state = EnumPatternState.CANDIDATE

    stored_id = await pattern_store.store_pattern(
        pattern_id=input_data.pattern_id,
        signature=input_data.signature,
        signature_hash=input_data.signature_hash,
        domain=input_data.domain,
        version=version,
        confidence=input_data.confidence,
        state=initial_state,
        is_current=True,
        stored_at=stored_at,
        actor=input_data.metadata.actor,
        source_run_id=input_data.metadata.source_run_id,
        correlation_id=input_data.correlation_id,
        metadata={
            "tags": input_data.metadata.tags,
            "learning_context": input_data.metadata.learning_context,
            **input_data.metadata.additional_attributes,
        },
    )

    logger.info(
        "Pattern stored successfully",
        extra={
            "pattern_id": str(stored_id),
            "domain": input_data.domain,
            "signature_hash": input_data.signature_hash,
            "version": version,
            "confidence": input_data.confidence,
            "state": initial_state.value,
            "correlation_id": str(input_data.correlation_id)
            if input_data.correlation_id
            else None,
        },
    )

    # -------------------------------------------------------------------------
    # Step 7: Create audit trail record (for future pattern_state_transitions table)
    # -------------------------------------------------------------------------
    audit_record = create_initial_storage_transition(
        pattern_id=stored_id,
        state=initial_state,
        actor=input_data.metadata.actor,
        correlation_id=input_data.correlation_id,
    )

    # Log audit trail (actual DB insertion to pattern_state_transitions will be added later)
    logger.debug(
        "Audit trail: pattern state transition",
        extra={
            "pattern_id": str(audit_record.pattern_id),
            "from_state": audit_record.from_state,
            "to_state": audit_record.to_state.value,
            "reason": audit_record.reason,
            "actor": audit_record.actor,
            "correlation_id": str(audit_record.correlation_id)
            if audit_record.correlation_id
            else None,
        },
    )

    # -------------------------------------------------------------------------
    # Step 8: Return the stored event
    # -------------------------------------------------------------------------
    return ModelPatternStoredEvent(
        pattern_id=stored_id,
        signature=input_data.signature,
        signature_hash=input_data.signature_hash,
        domain=input_data.domain,
        version=version,
        confidence=input_data.confidence,
        state=initial_state,
        stored_at=stored_at,
        actor=input_data.metadata.actor,
        source_run_id=input_data.metadata.source_run_id,
        correlation_id=input_data.correlation_id,
    )


__all__ = [
    "GovernanceResult",
    "GovernanceViolation",
    "PatternStateTransition",
    "ProtocolPatternStore",
    "StorePatternResult",
    "create_initial_storage_transition",
    "handle_store_pattern",
    "validate_governance",
]
