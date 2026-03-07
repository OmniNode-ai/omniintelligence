# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Tests for handler_route_storage.

Tests cover:
    - Routing vectorization.completed -> Qdrant
    - Routing entity.extraction-completed -> Memgraph
    - Routing pattern.matched -> PostgreSQL
    - Unroutable event types
    - Storage failure handling
    - DLQ routing after retry exhaustion
    - DLQ publisher failure resilience
    - Correlation ID threading
    - Missing storage client

Ticket: OMN-371
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_storage_router_effect.handlers import (
    MAX_RETRIES,
    StorageClientRegistry,
    handle_route_storage,
    resolve_backend,
)
from omniintelligence.nodes.node_storage_router_effect.models import (
    EnumStorageBackend,
    EnumStorageRouteStatus,
    ModelStorageRouteInput,
)
from omniintelligence.nodes.node_storage_router_effect.node_tests.conftest import (
    FIXED_CORRELATION_ID,
    FIXED_EVENT_ID,
    MockDlqPublisher,
    MockStorageClient,
    make_input,
    make_registry,
)

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# resolve_backend tests
# =============================================================================


class TestResolveBackend:
    """Tests for the resolve_backend routing function."""

    def test_vectorization_routes_to_qdrant(self) -> None:
        assert resolve_backend("vectorization.completed") == EnumStorageBackend.QDRANT

    def test_entity_extraction_routes_to_memgraph(self) -> None:
        assert (
            resolve_backend("entity.extraction-completed")
            == EnumStorageBackend.MEMGRAPH
        )

    def test_pattern_matched_routes_to_postgresql(self) -> None:
        assert resolve_backend("pattern.matched") == EnumStorageBackend.POSTGRESQL

    def test_unknown_event_type_returns_none(self) -> None:
        assert resolve_backend("unknown.event") is None

    def test_empty_event_type_returns_none(self) -> None:
        assert resolve_backend("") is None


# =============================================================================
# handle_route_storage tests - Success paths
# =============================================================================


class TestHandleRouteStorageSuccess:
    """Tests for successful storage routing."""

    @pytest.mark.asyncio
    async def test_vectorization_stored_in_qdrant(
        self,
        mock_qdrant_client: MockStorageClient,
        sample_vectorization_input: ModelStorageRouteInput,
    ) -> None:
        registry = make_registry(qdrant=mock_qdrant_client)
        result = await handle_route_storage(
            sample_vectorization_input,
            client_registry=registry,
        )

        assert result.success is True
        assert result.output is not None
        assert result.output.status == EnumStorageRouteStatus.STORED
        assert result.output.target_backend == EnumStorageBackend.QDRANT
        assert result.output.event_id == FIXED_EVENT_ID
        assert result.output.correlation_id == FIXED_CORRELATION_ID
        assert result.output.error_message is None
        assert len(mock_qdrant_client.stored) == 1

    @pytest.mark.asyncio
    async def test_entity_extraction_stored_in_memgraph(
        self,
        mock_memgraph_client: MockStorageClient,
        sample_entity_extraction_input: ModelStorageRouteInput,
    ) -> None:
        registry = make_registry(memgraph=mock_memgraph_client)
        result = await handle_route_storage(
            sample_entity_extraction_input,
            client_registry=registry,
        )

        assert result.success is True
        assert result.output is not None
        assert result.output.status == EnumStorageRouteStatus.STORED
        assert result.output.target_backend == EnumStorageBackend.MEMGRAPH
        assert len(mock_memgraph_client.stored) == 1

    @pytest.mark.asyncio
    async def test_pattern_matched_stored_in_postgresql(
        self,
        mock_postgresql_client: MockStorageClient,
        sample_pattern_matched_input: ModelStorageRouteInput,
    ) -> None:
        registry = make_registry(postgresql=mock_postgresql_client)
        result = await handle_route_storage(
            sample_pattern_matched_input,
            client_registry=registry,
        )

        assert result.success is True
        assert result.output is not None
        assert result.output.status == EnumStorageRouteStatus.STORED
        assert result.output.target_backend == EnumStorageBackend.POSTGRESQL
        assert len(mock_postgresql_client.stored) == 1

    @pytest.mark.asyncio
    async def test_stored_payload_matches_input(
        self,
        mock_qdrant_client: MockStorageClient,
        sample_vectorization_input: ModelStorageRouteInput,
    ) -> None:
        registry = make_registry(qdrant=mock_qdrant_client)
        await handle_route_storage(
            sample_vectorization_input,
            client_registry=registry,
        )

        stored = mock_qdrant_client.stored[0]
        assert stored["event_id"] == FIXED_EVENT_ID
        assert stored["payload"] == sample_vectorization_input.payload
        assert stored["correlation_id"] == FIXED_CORRELATION_ID


# =============================================================================
# handle_route_storage tests - Error paths
# =============================================================================


class TestHandleRouteStorageErrors:
    """Tests for error handling in storage routing."""

    @pytest.mark.asyncio
    async def test_unroutable_event_type(self) -> None:
        input_data = make_input(event_type="unknown.event.type")
        registry = make_registry()
        result = await handle_route_storage(
            input_data,
            client_registry=registry,
        )

        assert result.success is False
        assert result.output is not None
        assert result.output.status == EnumStorageRouteStatus.UNROUTABLE
        assert result.output.target_backend is None
        assert "No routing rule" in (result.output.error_message or "")

    @pytest.mark.asyncio
    async def test_missing_storage_client(self) -> None:
        """Event type has routing rule but no client registered."""
        input_data = make_input(event_type="vectorization.completed")
        registry = make_registry()  # No clients registered
        result = await handle_route_storage(
            input_data,
            client_registry=registry,
        )

        assert result.success is False
        assert result.output is not None
        assert result.output.status == EnumStorageRouteStatus.FAILED
        assert result.output.target_backend == EnumStorageBackend.QDRANT
        assert "No storage client registered" in (result.output.error_message or "")

    @pytest.mark.asyncio
    async def test_storage_failure_with_retries_remaining(self) -> None:
        client = MockStorageClient()
        client.simulate_error = ConnectionError("Connection refused")
        registry = make_registry(qdrant=client)
        input_data = make_input(
            event_type="vectorization.completed",
            retry_count=1,
        )

        result = await handle_route_storage(
            input_data,
            client_registry=registry,
        )

        assert result.success is False
        assert result.output is not None
        assert result.output.status == EnumStorageRouteStatus.FAILED
        assert result.routed_to_dlq is False
        assert "Storage failed" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_storage_failure_routes_to_dlq_after_max_retries(self) -> None:
        client = MockStorageClient()
        client.simulate_error = ConnectionError("Connection refused")
        registry = make_registry(qdrant=client)
        dlq = MockDlqPublisher()
        input_data = make_input(
            event_type="vectorization.completed",
            retry_count=MAX_RETRIES,
        )

        result = await handle_route_storage(
            input_data,
            client_registry=registry,
            dlq_publisher=dlq,
        )

        assert result.success is False
        assert result.output is not None
        assert result.output.status == EnumStorageRouteStatus.DLQ
        assert result.routed_to_dlq is True
        assert len(dlq.published) == 1
        dlq_msg = dlq.published[0]
        assert dlq_msg["event_id"] == input_data.event_id
        assert dlq_msg["retry_count"] == MAX_RETRIES

    @pytest.mark.asyncio
    async def test_dlq_routing_without_publisher(self) -> None:
        """DLQ routing succeeds (returns DLQ status) even without a publisher."""
        client = MockStorageClient()
        client.simulate_error = ConnectionError("Connection refused")
        registry = make_registry(qdrant=client)
        input_data = make_input(
            event_type="vectorization.completed",
            retry_count=MAX_RETRIES,
        )

        result = await handle_route_storage(
            input_data,
            client_registry=registry,
            dlq_publisher=None,
        )

        assert result.success is False
        assert result.output is not None
        assert result.output.status == EnumStorageRouteStatus.DLQ
        assert result.routed_to_dlq is True

    @pytest.mark.asyncio
    async def test_dlq_publisher_failure_does_not_crash(self) -> None:
        """If the DLQ publisher itself fails, the handler still returns gracefully."""
        client = MockStorageClient()
        client.simulate_error = ConnectionError("Connection refused")
        registry = make_registry(qdrant=client)
        dlq = MockDlqPublisher()
        dlq.simulate_error = RuntimeError("DLQ unavailable")
        input_data = make_input(
            event_type="vectorization.completed",
            retry_count=MAX_RETRIES,
        )

        result = await handle_route_storage(
            input_data,
            client_registry=registry,
            dlq_publisher=dlq,
        )

        # Should still return DLQ status even if publish failed
        assert result.success is False
        assert result.output is not None
        assert result.output.status == EnumStorageRouteStatus.DLQ
        assert result.routed_to_dlq is True


# =============================================================================
# handle_route_storage tests - Correlation ID
# =============================================================================


class TestCorrelationIdThreading:
    """Tests that correlation_id is properly threaded through all operations."""

    @pytest.mark.asyncio
    async def test_correlation_id_in_output(
        self,
        mock_qdrant_client: MockStorageClient,
        sample_vectorization_input: ModelStorageRouteInput,
    ) -> None:
        registry = make_registry(qdrant=mock_qdrant_client)
        result = await handle_route_storage(
            sample_vectorization_input,
            client_registry=registry,
        )

        assert result.output is not None
        assert result.output.correlation_id == FIXED_CORRELATION_ID

    @pytest.mark.asyncio
    async def test_correlation_id_passed_to_storage_client(
        self,
        mock_qdrant_client: MockStorageClient,
        sample_vectorization_input: ModelStorageRouteInput,
    ) -> None:
        registry = make_registry(qdrant=mock_qdrant_client)
        await handle_route_storage(
            sample_vectorization_input,
            client_registry=registry,
        )

        assert len(mock_qdrant_client.stored) == 1
        assert mock_qdrant_client.stored[0]["correlation_id"] == FIXED_CORRELATION_ID

    @pytest.mark.asyncio
    async def test_none_correlation_id_handled(self) -> None:
        client = MockStorageClient()
        registry = make_registry(qdrant=client)
        input_data = make_input(
            event_type="vectorization.completed",
            correlation_id=None,
        )

        result = await handle_route_storage(
            input_data,
            client_registry=registry,
        )

        assert result.success is True
        assert result.output is not None
        assert result.output.correlation_id is None
        assert client.stored[0]["correlation_id"] is None


# =============================================================================
# StorageClientRegistry tests
# =============================================================================


class TestStorageClientRegistry:
    """Tests for the StorageClientRegistry."""

    def test_get_registered_client(self) -> None:
        client = MockStorageClient()
        registry = make_registry(qdrant=client)
        assert registry.get_client(EnumStorageBackend.QDRANT) is client

    def test_get_unregistered_client_returns_none(self) -> None:
        registry = make_registry()
        assert registry.get_client(EnumStorageBackend.QDRANT) is None

    def test_registry_with_all_clients(
        self,
        full_registry: StorageClientRegistry,
    ) -> None:
        assert full_registry.get_client(EnumStorageBackend.QDRANT) is not None
        assert full_registry.get_client(EnumStorageBackend.MEMGRAPH) is not None
        assert full_registry.get_client(EnumStorageBackend.POSTGRESQL) is not None
