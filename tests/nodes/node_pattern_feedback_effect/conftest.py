"""Shared fixtures for node_pattern_feedback_effect tests.

These fixtures provide mock data for testing pattern feedback effect node
which handles user feedback on pattern usefulness and quality.
"""

import uuid

import pytest


# =============================================================================
# UUID Fixtures
# =============================================================================


@pytest.fixture
def mock_session_id() -> uuid.UUID:
    """Fixed session UUID for deterministic test output."""
    return uuid.UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def mock_pattern_ids() -> list[uuid.UUID]:
    """List of 3 pattern UUIDs for testing batch operations."""
    return [
        uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
    ]


@pytest.fixture
def mock_correlation_id() -> uuid.UUID:
    """Fixed correlation UUID for tracing test execution."""
    return uuid.UUID("deadbeef-dead-beef-dead-beefdeadbeef")
