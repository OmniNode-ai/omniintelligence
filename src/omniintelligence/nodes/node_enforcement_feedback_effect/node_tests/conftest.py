# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Shared fixtures for enforcement_feedback_effect node tests.

Provides mock implementations of ProtocolPatternRepository for unit testing
enforcement feedback processing without requiring real infrastructure.

Reference:
    - OMN-2270: Enforcement feedback loop for pattern confidence adjustment
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

import pytest

from omniintelligence.nodes.node_enforcement_feedback_effect.models import (
    ModelEnforcementEvent,
    ModelPatternViolation,
)
from omniintelligence.protocols import ProtocolPatternRepository

# =============================================================================
# Mock asyncpg.Record Implementation
# =============================================================================


class MockRecord(dict[str, Any]):
    """Dict-like object that mimics asyncpg.Record behavior."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"Record has no column '{name}'")


# =============================================================================
# Mock Protocol Implementations
# =============================================================================


class MockEnforcementRepository:
    """Mock implementation of ProtocolPatternRepository for testing.

    Simulates a pattern database with in-memory storage, supporting
    the specific SQL operations used by the enforcement feedback handler.

    Attributes:
        patterns: Map of pattern_id to pattern data (including quality_score).
        queries_executed: History of (query, args) tuples for verification.
        simulate_db_error: If set, raises this exception on execute.
    """

    def __init__(
        self,
        patterns: dict[UUID, dict[str, Any]] | None = None,
    ) -> None:
        self.patterns: dict[UUID, dict[str, Any]] = patterns or {}
        self.queries_executed: list[tuple[str, tuple[Any, ...]]] = []
        self.simulate_db_error: Exception | None = None

    def add_pattern(
        self,
        pattern_id: UUID,
        quality_score: float = 0.5,
        **extra: Any,
    ) -> None:
        """Add a pattern to the mock database.

        Args:
            pattern_id: Unique identifier for the pattern.
            quality_score: Current quality score (0.0 to 1.0).
            **extra: Additional pattern fields.
        """
        self.patterns[pattern_id] = {
            "id": pattern_id,
            "quality_score": quality_score,
            **extra,
        }

    async def fetch(
        self,
        query: str,
        *args: Any,
    ) -> list[Mapping[str, Any]]:
        self.queries_executed.append((query, args))
        return []

    async def fetchrow(
        self,
        query: str,
        *args: Any,
    ) -> Mapping[str, Any] | None:
        self.queries_executed.append((query, args))

        # Handle: Check pattern exists (SQL_CHECK_PATTERN_EXISTS)
        if "SELECT" in query.upper() and "learned_patterns" in query.lower():
            if args:
                pattern_id = args[0]
                pattern = self.patterns.get(pattern_id)
                if pattern is not None:
                    return MockRecord(pattern)
        return None

    async def execute(
        self,
        query: str,
        *args: Any,
    ) -> str:
        self.queries_executed.append((query, args))

        if self.simulate_db_error is not None:
            raise self.simulate_db_error

        # Handle: UPDATE quality_score
        if "UPDATE learned_patterns" in query and "quality_score" in query:
            if len(args) >= 2:
                pattern_id = args[0]
                adjustment = args[1]
                pattern = self.patterns.get(pattern_id)
                if pattern is not None:
                    old_score = pattern.get("quality_score", 0.5)
                    new_score = max(0.0, min(1.0, old_score + adjustment))
                    pattern["quality_score"] = new_score
                    return "UPDATE 1"
            return "UPDATE 0"

        return "EXECUTE 0"

    def reset(self) -> None:
        """Reset all storage for test isolation."""
        self.patterns.clear()
        self.queries_executed.clear()
        self.simulate_db_error = None


# Protocol compliance verification at import time
assert isinstance(MockEnforcementRepository(), ProtocolPatternRepository)


# =============================================================================
# Pytest Fixtures
# =============================================================================


@pytest.fixture
def mock_repository() -> MockEnforcementRepository:
    """Provide a fresh mock pattern repository for each test."""
    return MockEnforcementRepository()


@pytest.fixture
def sample_pattern_id_a() -> UUID:
    """Fixed pattern ID A for deterministic tests."""
    return UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def sample_pattern_id_b() -> UUID:
    """Fixed pattern ID B for deterministic tests."""
    return UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest.fixture
def sample_correlation_id() -> UUID:
    """Fixed correlation ID for tracing tests."""
    return UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def sample_session_id() -> UUID:
    """Fixed session ID for tests."""
    return UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


@pytest.fixture
def sample_enforcement_event_no_violations(
    sample_correlation_id: UUID,
    sample_session_id: UUID,
) -> ModelEnforcementEvent:
    """Enforcement event with no violations."""
    return ModelEnforcementEvent(
        correlation_id=sample_correlation_id,
        session_id=sample_session_id,
        patterns_checked=5,
        violations_found=0,
        violations=[],
    )


@pytest.fixture
def sample_enforcement_event_unconfirmed(
    sample_correlation_id: UUID,
    sample_session_id: UUID,
    sample_pattern_id_a: UUID,
) -> ModelEnforcementEvent:
    """Enforcement event with violations that are NOT confirmed (not corrected)."""
    return ModelEnforcementEvent(
        correlation_id=sample_correlation_id,
        session_id=sample_session_id,
        patterns_checked=5,
        violations_found=1,
        violations=[
            ModelPatternViolation(
                pattern_id=sample_pattern_id_a,
                pattern_name="test-pattern-a",
                was_advised=True,
                was_corrected=False,  # NOT corrected
            ),
        ],
    )


@pytest.fixture
def sample_enforcement_event_confirmed(
    sample_correlation_id: UUID,
    sample_session_id: UUID,
    sample_pattern_id_a: UUID,
) -> ModelEnforcementEvent:
    """Enforcement event with a single confirmed violation (advised AND corrected)."""
    return ModelEnforcementEvent(
        correlation_id=sample_correlation_id,
        session_id=sample_session_id,
        patterns_checked=5,
        violations_found=1,
        violations=[
            ModelPatternViolation(
                pattern_id=sample_pattern_id_a,
                pattern_name="test-pattern-a",
                was_advised=True,
                was_corrected=True,
            ),
        ],
    )


@pytest.fixture
def sample_enforcement_event_mixed(
    sample_correlation_id: UUID,
    sample_session_id: UUID,
    sample_pattern_id_a: UUID,
    sample_pattern_id_b: UUID,
) -> ModelEnforcementEvent:
    """Enforcement event with mixed violations (some confirmed, some not)."""
    return ModelEnforcementEvent(
        correlation_id=sample_correlation_id,
        session_id=sample_session_id,
        patterns_checked=10,
        violations_found=3,
        violations=[
            # Confirmed: advised AND corrected
            ModelPatternViolation(
                pattern_id=sample_pattern_id_a,
                pattern_name="test-pattern-a",
                was_advised=True,
                was_corrected=True,
            ),
            # NOT confirmed: advised but NOT corrected
            ModelPatternViolation(
                pattern_id=sample_pattern_id_b,
                pattern_name="test-pattern-b",
                was_advised=True,
                was_corrected=False,
            ),
            # NOT confirmed: not advised at all
            ModelPatternViolation(
                pattern_id=sample_pattern_id_b,
                pattern_name="test-pattern-b",
                was_advised=False,
                was_corrected=False,
            ),
        ],
    )
