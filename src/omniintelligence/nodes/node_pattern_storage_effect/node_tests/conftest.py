# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Shared fixtures for pattern_storage_effect node tests.

Provides mock implementations of ProtocolPatternStore and
ProtocolPatternStateManager for unit testing governance invariants
without requiring a real database connection.

Reference:
    - OMN-1668: Pattern storage effect acceptance criteria
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any  # any-ok: test fixture factories use **kwargs: Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

if TYPE_CHECKING:
    pass

from omniintelligence.nodes.node_pattern_storage_effect.models import (
    ModelPatternStorageInput,
    PatternStorageGovernance,
)

# Import shared fixtures from canonical location
from omniintelligence.testing import (
    MockPatternStateManager,
    MockPatternStore,
    create_low_confidence_input_dict,
    create_valid_pattern_input,
)

# =============================================================================
# Re-export shared classes for backwards compatibility
# =============================================================================

# These are re-exported so existing tests can continue to import from here
__all__ = [
    "MockPatternStateManager",
    "MockPatternStore",
    "correlation_id",
    "create_low_confidence_input",
    "create_valid_input",
    "high_confidence_input",
    "minimum_confidence_input",
    "mock_conn",
    "mock_pattern_store",
    "mock_state_manager",
    "sample_pattern_id",
    "valid_input",
]


# =============================================================================
# Factory Function Aliases
# =============================================================================


def create_valid_input(
    **kwargs: Any,
) -> ModelPatternStorageInput:
    """Create a valid ModelPatternStorageInput for testing.

    This is an alias for create_valid_pattern_input with default actor/source_run_id
    suitable for unit tests.

    Args:
        **kwargs: Arguments passed to create_valid_pattern_input.

    Returns:
        A valid ModelPatternStorageInput instance.
    """
    # Set unit-test specific defaults if not provided
    kwargs.setdefault("actor", "test_actor")
    kwargs.setdefault("source_run_id", "test_run_001")
    kwargs.setdefault("learning_context", "unit_test")
    return create_valid_pattern_input(**kwargs)


def create_low_confidence_input(
    confidence: float = 0.3,
    **kwargs: Any,
) -> dict[str, Any]:
    """Create input dict with low confidence for validation bypass testing.

    This is an alias for create_low_confidence_input_dict.

    Args:
        confidence: Low confidence value (< 0.5).
        **kwargs: Additional fields to override.

    Returns:
        Dict representation of input with low confidence.
    """
    return create_low_confidence_input_dict(confidence=confidence, **kwargs)


# =============================================================================
# Pytest Fixtures
# =============================================================================


@pytest.fixture
def mock_pattern_store() -> MockPatternStore:
    """Provide a fresh mock pattern store for each test."""
    return MockPatternStore()


@pytest.fixture
def mock_state_manager() -> MockPatternStateManager:
    """Provide a fresh mock state manager for each test."""
    return MockPatternStateManager()


@pytest.fixture
def valid_input() -> ModelPatternStorageInput:
    """Provide a valid pattern storage input for testing."""
    return create_valid_input()


@pytest.fixture
def minimum_confidence_input() -> ModelPatternStorageInput:
    """Provide input at exactly the minimum confidence threshold."""
    return create_valid_input(confidence=PatternStorageGovernance.MIN_CONFIDENCE)


@pytest.fixture
def high_confidence_input() -> ModelPatternStorageInput:
    """Provide input with high confidence score."""
    return create_valid_input(confidence=0.95)


@pytest.fixture
def sample_pattern_id() -> UUID:
    """Provide a sample pattern UUID for testing."""
    return uuid4()


@pytest.fixture
def correlation_id() -> UUID:
    """Provide a correlation ID for distributed tracing tests."""
    return uuid4()


@pytest.fixture
def mock_conn() -> MagicMock:
    """Provide a mock database connection for testing.

    Returns a MagicMock configured with common AsyncConnection methods.
    This enables testing handlers without a real database connection
    while maintaining realistic async behavior.

    The mock includes:
    - execute: AsyncMock for query execution
    - cursor: MagicMock for cursor operations

    Note: This is intentionally minimal - add methods as needed
    for specific test scenarios.
    """
    mock = MagicMock()
    mock.execute = AsyncMock()
    mock.cursor = MagicMock()
    mock.cursor.return_value.__aenter__ = AsyncMock()
    mock.cursor.return_value.__aexit__ = AsyncMock()
    return mock
