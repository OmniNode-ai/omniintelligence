# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Shared fixtures for node_storage_router_effect tests.

Provides mock implementations of ProtocolStorageClient and ProtocolDlqPublisher,
plus helpers for building test payloads.

Ticket: OMN-371
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from omniintelligence.nodes.node_storage_router_effect.handlers import (
    ProtocolDlqPublisher,
    ProtocolStorageClient,
    StorageClientRegistry,
)
from omniintelligence.nodes.node_storage_router_effect.models import (
    EnumStorageBackend,
    ModelStorageRouteInput,
)

# =============================================================================
# Fixed identifiers for deterministic tests
# =============================================================================

FIXED_CORRELATION_ID: UUID = UUID("12345678-1234-5678-1234-567812345678")
FIXED_EVENT_ID: UUID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


# =============================================================================
# Mock implementations
# =============================================================================


class MockStorageClient:
    """Mock storage client that records store calls."""

    def __init__(self) -> None:
        self.stored: list[dict[str, Any]] = []
        self.simulate_error: Exception | None = None
        assert isinstance(self, ProtocolStorageClient)

    async def store(
        self,
        *,
        event_id: UUID,
        payload: dict[str, Any],
        correlation_id: UUID | None = None,
    ) -> None:
        if self.simulate_error is not None:
            raise self.simulate_error
        self.stored.append(
            {
                "event_id": event_id,
                "payload": payload,
                "correlation_id": correlation_id,
            }
        )


class MockDlqPublisher:
    """Mock DLQ publisher that records publish calls."""

    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []
        self.simulate_error: Exception | None = None
        assert isinstance(self, ProtocolDlqPublisher)

    async def publish_to_dlq(
        self,
        *,
        event_id: UUID,
        original_event: dict[str, Any],
        error_message: str,
        retry_count: int,
        correlation_id: UUID | None = None,
    ) -> None:
        if self.simulate_error is not None:
            raise self.simulate_error
        self.published.append(
            {
                "event_id": event_id,
                "original_event": original_event,
                "error_message": error_message,
                "retry_count": retry_count,
                "correlation_id": correlation_id,
            }
        )


# =============================================================================
# Helpers
# =============================================================================


def make_input(
    *,
    event_type: str = "vectorization.completed",
    event_id: UUID | None = None,
    correlation_id: UUID | None = FIXED_CORRELATION_ID,
    payload: dict[str, Any] | None = None,
    source_node: str = "node_embedding_generation_effect",
    retry_count: int = 0,
) -> ModelStorageRouteInput:
    """Create a ModelStorageRouteInput for testing."""
    return ModelStorageRouteInput(
        event_id=event_id or uuid4(),
        event_type=event_type,
        correlation_id=correlation_id,
        payload=payload or {"vectors": [0.1, 0.2, 0.3]},
        source_node=source_node,
        produced_at=datetime.now(UTC),
        retry_count=retry_count,
    )


def make_registry(
    *,
    qdrant: MockStorageClient | None = None,
    memgraph: MockStorageClient | None = None,
    postgresql: MockStorageClient | None = None,
) -> StorageClientRegistry:
    """Create a StorageClientRegistry with mock clients."""
    clients: dict[EnumStorageBackend, ProtocolStorageClient] = {}
    if qdrant is not None:
        clients[EnumStorageBackend.QDRANT] = qdrant
    if memgraph is not None:
        clients[EnumStorageBackend.MEMGRAPH] = memgraph
    if postgresql is not None:
        clients[EnumStorageBackend.POSTGRESQL] = postgresql
    return StorageClientRegistry(clients=clients)


# =============================================================================
# Pytest fixtures
# =============================================================================


@pytest.fixture
def mock_qdrant_client() -> MockStorageClient:
    return MockStorageClient()


@pytest.fixture
def mock_memgraph_client() -> MockStorageClient:
    return MockStorageClient()


@pytest.fixture
def mock_postgresql_client() -> MockStorageClient:
    return MockStorageClient()


@pytest.fixture
def mock_dlq_publisher() -> MockDlqPublisher:
    return MockDlqPublisher()


@pytest.fixture
def full_registry(
    mock_qdrant_client: MockStorageClient,
    mock_memgraph_client: MockStorageClient,
    mock_postgresql_client: MockStorageClient,
) -> StorageClientRegistry:
    """Registry with all three storage backends registered."""
    return make_registry(
        qdrant=mock_qdrant_client,
        memgraph=mock_memgraph_client,
        postgresql=mock_postgresql_client,
    )


@pytest.fixture
def sample_vectorization_input() -> ModelStorageRouteInput:
    return make_input(
        event_type="vectorization.completed",
        event_id=FIXED_EVENT_ID,
    )


@pytest.fixture
def sample_entity_extraction_input() -> ModelStorageRouteInput:
    return make_input(
        event_type="entity.extraction-completed",
        event_id=FIXED_EVENT_ID,
        payload={"entities": [{"name": "Foo", "type": "class"}]},
        source_node="node_semantic_analysis_compute",
    )


@pytest.fixture
def sample_pattern_matched_input() -> ModelStorageRouteInput:
    return make_input(
        event_type="pattern.matched",
        event_id=FIXED_EVENT_ID,
        payload={"pattern_id": "P001", "confidence": 0.95},
        source_node="node_pattern_matching_compute",
    )
