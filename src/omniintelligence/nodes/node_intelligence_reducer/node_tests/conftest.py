# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Shared fixtures for intelligence_reducer node tests.

Provides fixtures for creating ModelReducerInputPatternLifecycle inputs
with various configurations for testing pattern lifecycle FSM transitions.

Reference:
    - OMN-1805: Pattern lifecycle state machine implementation
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from omniintelligence.enums import EnumPatternLifecycleStatus
from omniintelligence.nodes.node_intelligence_reducer.models.model_pattern_lifecycle_reducer_input import (
    ModelPatternLifecycleReducerInput,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_reducer_input import (
    ModelReducerInputPatternLifecycle,
)


# =============================================================================
# Pytest Fixtures - IDs
# =============================================================================


@pytest.fixture
def sample_pattern_id() -> str:
    """Fixed pattern ID for deterministic tests.

    Returns as string since ModelPatternLifecycleReducerInput expects string.
    """
    return "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


@pytest.fixture
def sample_pattern_id_uuid() -> UUID:
    """Fixed pattern ID as UUID for intent verification."""
    return UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def sample_request_id() -> UUID:
    """Fixed request ID for idempotency tests."""
    return UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest.fixture
def sample_correlation_id() -> UUID:
    """Fixed correlation ID for tracing tests."""
    return UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def sample_transition_at() -> datetime:
    """Fixed timestamp for transition tests."""
    return datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)


# =============================================================================
# Pytest Fixtures - Input Builders
# =============================================================================


@pytest.fixture
def make_reducer_input():
    """Factory fixture for creating ModelReducerInputPatternLifecycle instances.

    Returns a callable that creates input models with customizable fields.

    Example:
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="provisional",
            trigger="validation_passed",
        )
    """

    def _make_input(
        *,
        pattern_id: str = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        from_status: str | EnumPatternLifecycleStatus = "candidate",
        to_status: str | EnumPatternLifecycleStatus = "provisional",
        trigger: str = "validation_passed",
        actor_type: str = "handler",
        actor: str = "test_actor",
        reason: str | None = "Test reason",
        gate_snapshot: dict | None = None,
        request_id: UUID | None = None,
        correlation_id: UUID | None = None,
    ) -> ModelReducerInputPatternLifecycle:
        """Create a reducer input with specified parameters.

        Args:
            pattern_id: Pattern UUID as string.
            from_status: Source lifecycle status (enum or lowercase string).
            to_status: Target lifecycle status (enum or lowercase string).
            trigger: FSM trigger name.
            actor_type: One of "system", "admin", "handler".
            actor: Actor identifier.
            reason: Human-readable reason for transition.
            gate_snapshot: Optional gate values at decision time.
            request_id: Idempotency key (defaults to fixed UUID).
            correlation_id: Tracing ID (defaults to fixed UUID).

        Returns:
            ModelReducerInputPatternLifecycle ready for handler testing.

        Note:
            If strings are passed, they must be lowercase to match enum values.
            Use EnumPatternLifecycleStatus.CANDIDATE etc. for explicit enums.
        """
        # Convert strings to enums if needed (must be lowercase)
        if isinstance(from_status, str):
            from_status = EnumPatternLifecycleStatus(from_status.lower())
        if isinstance(to_status, str):
            to_status = EnumPatternLifecycleStatus(to_status.lower())

        return ModelReducerInputPatternLifecycle(
            fsm_type="PATTERN_LIFECYCLE",
            entity_id=pattern_id,
            action=trigger,
            payload=ModelPatternLifecycleReducerInput(
                pattern_id=pattern_id,
                from_status=from_status,
                to_status=to_status,
                trigger=trigger,
                actor_type=actor_type,
                actor=actor,
                reason=reason,
                gate_snapshot=gate_snapshot,
            ),
            correlation_id=correlation_id
            or UUID("12345678-1234-5678-1234-567812345678"),
            request_id=request_id or UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        )

    return _make_input
