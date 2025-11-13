"""
End-to-End Integration Tests for Codegen Pattern Handler

Tests complete flow:
1. Consume Kafka event (or simulate)
2. Handler processes pattern matching request
3. Response published via HybridEventRouter
4. Verify response reaches correct topic with correct structure

Part of MVP Day 3 - Pattern Matching Infrastructure

Marker Usage:
  pytest -m integration                   # Run all integration tests
  pytest -m pattern_handler               # Run only pattern handler tests
  pytest -m "integration and not performance"  # Integration tests, skip performance
  pytest -m error_handling                # Run only error handling tests
  pytest -m concurrent                    # Run only concurrent request tests
  pytest -m "pattern_handler and performance"  # Performance tests for pattern handler

Author: Archon Intelligence Team
Date: 2025-10-15
"""

import asyncio
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from events.models.model_event import ModelEvent
from events.models.model_routing_context import ModelRoutingContext
from handlers.codegen_pattern_handler import CodegenPatternHandler
from integration.utils.assertions import (
    assert_correlation_id_preserved,
    assert_response_structure,
    assert_topic_naming,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_pattern_request(mock_event_envelope):
    """Create sample pattern matching request event."""
    correlation_id = str(uuid4())

    payload = {
        "node_description": "Handle user authentication with JWT tokens and session management",
        "node_type": "effect",
        "limit": 5,
        "score_threshold": 0.7,
    }

    return mock_event_envelope(correlation_id, payload)


@pytest.fixture
def sample_compute_pattern_request(mock_event_envelope):
    """Create sample pattern request for compute node."""
    correlation_id = str(uuid4())

    payload = {
        "node_description": "Transform and validate API request data with schema validation",
        "node_type": "compute",
        "limit": 3,
        "score_threshold": 0.8,
    }

    return mock_event_envelope(correlation_id, payload)


@pytest.fixture
def sample_reducer_pattern_request(mock_event_envelope):
    """Create sample pattern request for reducer node."""
    correlation_id = str(uuid4())

    payload = {
        "node_description": "Aggregate metrics from multiple sources and persist to database",
        "node_type": "reducer",
        "limit": 5,
        "score_threshold": 0.75,
    }

    return mock_event_envelope(correlation_id, payload)


@pytest.fixture
def sample_error_request(mock_event_envelope):
    """Create sample request that will trigger error."""
    correlation_id = str(uuid4())

    payload = {
        "node_description": None,  # Missing description will trigger error
        "node_type": "effect",
    }

    return mock_event_envelope(correlation_id, payload)


@pytest.fixture
def mock_pattern_service():
    """Mock pattern service for testing."""
    service = AsyncMock()
    service.find_similar_nodes = AsyncMock(
        return_value=[
            {
                "node_id": "node_auth_effect_001",
                "similarity_score": 0.92,
                "description": "JWT authentication handler with refresh token support",
                "mixins_used": ["RetryMixin", "CachingMixin", "MetricsMixin"],
                "contracts": [
                    {"name": "AuthContract", "version": "1.0.0"},
                    {"name": "TokenContract", "version": "1.2.0"},
                ],
                "code_snippets": [
                    "async def authenticate(self, token: str) -> AuthResult:",
                    "async def refresh_token(self, refresh: str) -> TokenPair:",
                ],
                "metadata": {
                    "node_type": "effect",
                    "complexity": "moderate",
                    "success_rate": 0.95,
                    "usage_count": 142,
                    "last_used": "2025-10-14T10:30:00Z",
                },
            },
            {
                "node_id": "node_session_effect_002",
                "similarity_score": 0.87,
                "description": "Session management with Redis backend",
                "mixins_used": ["CachingMixin", "HealthCheckMixin"],
                "contracts": [{"name": "SessionContract", "version": "2.0.0"}],
                "code_snippets": [
                    "async def create_session(self, user_id: str) -> Session:",
                ],
                "metadata": {
                    "node_type": "effect",
                    "complexity": "low",
                    "success_rate": 0.98,
                    "usage_count": 89,
                    "last_used": "2025-10-13T15:20:00Z",
                },
            },
            {
                "node_id": "node_oauth_effect_003",
                "similarity_score": 0.81,
                "description": "OAuth2 provider integration",
                "mixins_used": ["RetryMixin", "CircuitBreakerMixin"],
                "contracts": [{"name": "OAuthContract", "version": "1.1.0"}],
                "code_snippets": [
                    "async def oauth_authorize(self, provider: str) -> AuthURL:",
                ],
                "metadata": {
                    "node_type": "effect",
                    "complexity": "high",
                    "success_rate": 0.88,
                    "usage_count": 67,
                    "last_used": "2025-10-12T09:45:00Z",
                },
            },
        ]
    )
    return service


# ============================================================================
# E2E Test Cases
# ============================================================================


@pytest.mark.integration
@pytest.mark.handler_tests
@pytest.mark.pattern_handler
class TestPatternHandlerE2E:
    """End-to-end tests for pattern handler intelligence flow."""

    @pytest.mark.asyncio
    async def test_complete_pattern_flow_success(
        self,
        sample_pattern_request,
        mock_pattern_service,
        mock_router,
    ):
        """
        Test complete pattern matching flow:
        1. Receive pattern request
        2. Process with pattern service
        3. Publish response via HybridEventRouter
        """
        # Create handler with mocked dependencies
        handler = CodegenPatternHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Handle event
        result = await handler.handle_event(sample_pattern_request)

        # Verify handler processed successfully
        assert result is True

        # Verify pattern service was called
        mock_pattern_service.find_similar_nodes.assert_called_once()
        call_args = mock_pattern_service.find_similar_nodes.call_args
        assert (
            call_args[1]["node_description"]
            == "Handle user authentication with JWT tokens and session management"
        )
        assert call_args[1]["node_type"] == "effect"
        assert call_args[1]["limit"] == 5
        assert call_args[1]["score_threshold"] == 0.7

        # Verify response was published
        mock_router.publish.assert_called_once()
        publish_call = mock_router.publish.call_args

        # Verify topic
        assert publish_call[1]["topic"] == "omninode.codegen.response.pattern.v1"

        # Verify event structure
        event = publish_call[1]["event"]
        assert isinstance(event, ModelEvent)
        assert str(event.correlation_id) == sample_pattern_request.correlation_id
        assert event.source_service == "archon-intelligence"

        # Verify payload
        payload = event.payload
        assert "similar_nodes" in payload
        assert "count" in payload
        assert "avg_similarity" in payload
        assert len(payload["similar_nodes"]) == 3
        assert payload["count"] == 3
        assert payload["avg_similarity"] > 0.8  # (0.92 + 0.87 + 0.81) / 3

        # Verify routing context
        context = publish_call[1]["context"]
        assert isinstance(context, ModelRoutingContext)
        assert context.requires_persistence is True
        assert context.is_cross_service is True

    @pytest.mark.parametrize(
        "node_type,description,score_threshold,limit,expected_node_count,mock_results_builder",
        [
            (
                "effect",
                "Handle user authentication with JWT tokens",
                0.7,
                5,
                3,
                lambda: [
                    {
                        "node_id": f"node_auth_effect_{i:03d}",
                        "similarity_score": 0.92 - (i * 0.05),
                        "description": f"Authentication pattern {i}",
                        "mixins_used": ["RetryMixin", "MetricsMixin"],
                        "contracts": [{"name": "AuthContract", "version": "1.0.0"}],
                        "code_snippets": ["async def authenticate(): pass"],
                        "metadata": {
                            "node_type": "effect",
                            "complexity": "moderate",
                            "success_rate": 0.95,
                        },
                    }
                    for i in range(3)
                ],
            ),
            (
                "compute",
                "Transform and validate API request data",
                0.8,
                3,
                2,
                lambda: [
                    {
                        "node_id": "node_validator_compute_001",
                        "similarity_score": 0.91,
                        "description": "Schema validation compute with JSON Schema",
                        "mixins_used": ["ValidationMixin", "MetricsMixin"],
                        "contracts": [
                            {"name": "ValidationContract", "version": "1.0.0"}
                        ],
                        "code_snippets": [
                            "async def validate_schema(self, data: dict) -> ValidationResult:"
                        ],
                        "metadata": {
                            "node_type": "compute",
                            "complexity": "moderate",
                            "success_rate": 0.96,
                        },
                    },
                    {
                        "node_id": "node_transformer_compute_002",
                        "similarity_score": 0.88,
                        "description": "API data transformation with Pydantic models",
                        "mixins_used": ["CachingMixin", "PerformanceTrackerMixin"],
                        "contracts": [
                            {"name": "TransformContract", "version": "2.0.0"}
                        ],
                        "code_snippets": [
                            "async def transform(self, input: APIRequest) -> APIResponse:"
                        ],
                        "metadata": {
                            "node_type": "compute",
                            "complexity": "low",
                            "success_rate": 0.99,
                        },
                    },
                ],
            ),
            (
                "reducer",
                "Aggregate metrics from multiple sources",
                0.75,
                5,
                1,
                lambda: [
                    {
                        "node_id": "node_aggregator_reducer_001",
                        "similarity_score": 0.89,
                        "description": "Metric aggregation with time-series rollup",
                        "mixins_used": [
                            "AggregationMixin",
                            "StateManagementMixin",
                            "PersistenceMixin",
                        ],
                        "contracts": [
                            {"name": "AggregationContract", "version": "1.0.0"}
                        ],
                        "code_snippets": [
                            "async def aggregate(self, metrics: List[Metric]) -> AggregateResult:"
                        ],
                        "metadata": {
                            "node_type": "reducer",
                            "complexity": "high",
                            "success_rate": 0.94,
                        },
                    }
                ],
            ),
            (
                "orchestrator",
                "Coordinate workflow execution and dependencies",
                0.7,
                5,
                2,
                lambda: [
                    {
                        "node_id": f"node_workflow_orchestrator_{i:03d}",
                        "similarity_score": 0.90 - (i * 0.03),
                        "description": f"Workflow orchestration pattern {i}",
                        "mixins_used": ["WorkflowMixin", "DependencyMixin"],
                        "contracts": [{"name": "WorkflowContract", "version": "1.0.0"}],
                        "code_snippets": ["async def coordinate(): pass"],
                        "metadata": {
                            "node_type": "orchestrator",
                            "complexity": "high",
                            "success_rate": 0.93,
                        },
                    }
                    for i in range(2)
                ],
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_pattern_matching_by_node_type(
        self,
        mock_event_envelope,
        mock_pattern_service,
        mock_router,
        node_type,
        description,
        score_threshold,
        limit,
        expected_node_count,
        mock_results_builder,
    ):
        """Test pattern matching for different node types.

        Tests that the pattern handler correctly finds similar patterns based on
        node type and description, returning appropriate matches with similarity scores.

        Parameters:
            node_type: ONEX node type (effect, compute, reducer, orchestrator)
            description: Node description to match against
            score_threshold: Minimum similarity score threshold
            limit: Maximum number of results to return
            expected_node_count: Expected number of matching nodes
            mock_results_builder: Callable that returns mock results for this node type
        """
        # Create handler
        handler = CodegenPatternHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Create request
        correlation_id = str(uuid4())
        payload = {
            "node_description": description,
            "node_type": node_type,
            "limit": limit,
            "score_threshold": score_threshold,
        }
        event = mock_event_envelope(correlation_id, payload)

        # Mock appropriate response
        mock_pattern_service.find_similar_nodes = AsyncMock(
            return_value=mock_results_builder()
        )

        # Handle event
        result = await handler.handle_event(event)
        assert result is True

        # Verify results
        call_args = mock_pattern_service.find_similar_nodes.call_args
        assert call_args[1]["node_type"] == node_type
        assert call_args[1]["limit"] == limit
        assert call_args[1]["score_threshold"] == score_threshold

        event = mock_router.publish.call_args[1]["event"]
        payload = event.payload
        assert payload["count"] == expected_node_count
        assert len(payload["similar_nodes"]) == expected_node_count

        # Verify all nodes match the expected type
        for node in payload["similar_nodes"]:
            assert node["metadata"]["node_type"] == node_type

    @pytest.mark.asyncio
    async def test_pattern_flow_with_no_matches(
        self,
        sample_pattern_request,
        mock_pattern_service,
        mock_router,
    ):
        """Test pattern matching flow when no similar patterns found."""
        # Override mock to return empty results
        mock_pattern_service.find_similar_nodes = AsyncMock(return_value=[])

        # Create handler
        handler = CodegenPatternHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Handle event
        result = await handler.handle_event(sample_pattern_request)

        # Verify handler succeeded (empty results is valid)
        assert result is True

        # Verify response published
        mock_router.publish.assert_called_once()
        event = mock_router.publish.call_args[1]["event"]
        payload = event.payload

        # Verify empty results
        assert payload["similar_nodes"] == []
        assert payload["count"] == 0
        assert payload["avg_similarity"] == 0.0

    @pytest.mark.error_handling
    @pytest.mark.asyncio
    async def test_pattern_flow_error_handling(
        self,
        sample_error_request,
        mock_pattern_service,
        mock_router,
    ):
        """Test pattern flow with error (missing node_description)."""
        # Create handler
        handler = CodegenPatternHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Handle event (should handle gracefully)
        result = await handler.handle_event(sample_error_request)

        # Verify handler returned False (error)
        assert result is False

        # Verify error response was published
        mock_router.publish.assert_called_once()
        publish_call = mock_router.publish.call_args

        # Verify error payload
        event = publish_call[1]["event"]
        payload = event.payload
        # Error is in details dict
        assert "details" in payload
        assert "error" in payload["details"]
        assert (
            "Missing node_description" in payload["details"]["error"]
            or "node_description" in payload["details"]["error"]
        )

    @pytest.mark.asyncio
    async def test_pattern_flow_router_initialization(
        self,
        sample_pattern_request,
        mock_pattern_service,
    ):
        """Test that handler initializes router if not initialized."""
        # Create handler without initialized router
        handler = CodegenPatternHandler(pattern_service=mock_pattern_service)
        handler._router = None  # Set to None to trigger initialization
        handler._router_initialized = False

        with patch(
            "handlers.base_response_publisher.HybridEventRouter"
        ) as mock_router_class:
            mock_router = AsyncMock()
            mock_router.initialize = AsyncMock()
            mock_router.publish = AsyncMock()
            mock_router_class.return_value = mock_router

            # Handle event
            result = await handler.handle_event(sample_pattern_request)

            # Verify handler processed successfully
            assert result is True

            # Verify router was initialized
            mock_router.initialize.assert_called_once()

            # Verify publish was called
            mock_router.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_pattern_flow_publish_failure_recovery(
        self,
        sample_pattern_request,
        mock_pattern_service,
        mock_router,
        caplog,
    ):
        """Test that publish failures are handled gracefully."""
        # Make router.publish fail
        mock_router.publish.side_effect = Exception("Kafka unavailable")

        # Create handler
        handler = CodegenPatternHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Handle event (should not crash)
        result = await handler.handle_event(sample_pattern_request)

        # Verify handler still succeeded (publishing is non-blocking)
        assert result is True

        # Verify error was logged
        assert any("Failed to publish" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_response_topic_naming_convention(
        self,
        sample_pattern_request,
        mock_pattern_service,
        mock_router,
    ):
        """Verify response topic follows naming convention."""
        handler = CodegenPatternHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        await handler.handle_event(sample_pattern_request)

        publish_call = mock_router.publish.call_args
        topic = publish_call[1]["topic"]

        # Use shared assertion helper
        assert_topic_naming(topic, "pattern")

    @pytest.mark.asyncio
    async def test_response_includes_correlation_id(
        self,
        sample_pattern_request,
        mock_pattern_service,
        mock_router,
    ):
        """Verify response includes correlation ID for request tracking."""
        handler = CodegenPatternHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        await handler.handle_event(sample_pattern_request)

        publish_call = mock_router.publish.call_args
        event = publish_call[1]["event"]

        # Use shared assertion helpers
        assert_correlation_id_preserved(event, sample_pattern_request.correlation_id)
        assert publish_call[1]["key"] == sample_pattern_request.correlation_id

    @pytest.mark.asyncio
    async def test_response_payload_structure(
        self,
        sample_pattern_request,
        mock_pattern_service,
        mock_router,
    ):
        """Verify response payload has required structure."""
        handler = CodegenPatternHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        await handler.handle_event(sample_pattern_request)

        publish_call = mock_router.publish.call_args
        event = publish_call[1]["event"]
        payload = event.payload

        # Use shared assertion helper for required fields and types
        assert_response_structure(
            payload,
            required_fields=["similar_nodes", "count", "avg_similarity"],
            field_types={
                "similar_nodes": list,
                "count": int,
                "avg_similarity": (int, float),
            },
        )

        # Verify similar_nodes structure (domain-specific validation)
        if payload["count"] > 0:
            node = payload["similar_nodes"][0]
            node_required_fields = [
                "node_id",
                "similarity_score",
                "description",
                "mixins_used",
                "contracts",
                "code_snippets",
                "metadata",
            ]
            for field in node_required_fields:
                assert field in node, f"Missing required node field: {field}"

    @pytest.mark.concurrent
    @pytest.mark.asyncio
    async def test_concurrent_requests_handling(
        self,
        mock_event_envelope,
        mock_pattern_service,
        mock_router,
    ):
        """Test handling multiple concurrent pattern matching requests."""
        # Create handler
        handler = CodegenPatternHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Create multiple requests with different node types
        node_types = ["effect", "compute", "reducer", "orchestrator", "effect"]
        requests = []
        for i, node_type in enumerate(node_types * 2):  # 10 requests total
            correlation_id = str(uuid4())
            payload = {
                "node_description": f"Handle operation {i} for {node_type} node",
                "node_type": node_type,
                "limit": 5,
                "score_threshold": 0.7,
            }
            requests.append(mock_event_envelope(correlation_id, payload))

        # Process concurrently
        results = await asyncio.gather(*[handler.handle_event(req) for req in requests])

        # Verify all processed successfully
        assert all(results)

        # Verify all published
        assert mock_router.publish.call_count == 10

        # Verify each has unique correlation ID
        published_correlation_ids = set()
        for call in mock_router.publish.call_args_list:
            event = call[1]["event"]
            published_correlation_ids.add(str(event.correlation_id))

        assert len(published_correlation_ids) == 10

    @pytest.mark.asyncio
    async def test_handler_metrics_tracking(
        self,
        sample_pattern_request,
        mock_pattern_service,
        mock_router,
    ):
        """Test that handler tracks metrics correctly."""
        # Create handler
        handler = CodegenPatternHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Process multiple events
        await handler.handle_event(sample_pattern_request)
        await handler.handle_event(sample_pattern_request)
        await handler.handle_event(sample_pattern_request)

        # Get metrics
        metrics = handler.get_metrics()

        # Verify metrics
        assert metrics["events_handled"] == 3
        assert metrics["events_failed"] == 0
        assert metrics["success_rate"] == 1.0
        assert metrics["avg_processing_time_ms"] > 0
        assert metrics["handler_name"] == "CodegenPatternHandler"

    @pytest.mark.asyncio
    async def test_pattern_service_exception_handling(
        self,
        sample_pattern_request,
        mock_pattern_service,
        mock_router,
    ):
        """Test handling when pattern service raises exception."""
        # Make pattern service raise exception
        mock_pattern_service.find_similar_nodes = AsyncMock(
            side_effect=Exception("Vector search unavailable")
        )

        # Create handler
        handler = CodegenPatternHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Handle event (should handle gracefully)
        result = await handler.handle_event(sample_pattern_request)

        # Verify handler returned False (error)
        assert result is False

        # Verify error response was published
        mock_router.publish.assert_called_once()
        event = mock_router.publish.call_args[1]["event"]
        payload = event.payload
        # Error is in details dict
        assert "details" in payload
        assert "error" in payload["details"]
        assert "Vector search unavailable" in payload["details"]["error"]

    @pytest.mark.asyncio
    @pytest.mark.error_handling
    async def test_handler_service_timeout(
        self,
        sample_pattern_request,
        mock_router,
    ):
        """Test handler behavior when service calls timeout."""
        # Mock service to raise timeout
        mock_service = AsyncMock()
        mock_service.find_similar_nodes = AsyncMock(
            side_effect=asyncio.TimeoutError("Service timeout")
        )

        handler = CodegenPatternHandler(pattern_service=mock_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Handle event
        result = await handler.handle_event(sample_pattern_request)

        # Verify graceful timeout handling
        assert result is False

        # Verify error response published
        mock_router.publish.assert_called_once()
        event = mock_router.publish.call_args[1]["event"]
        payload = event.payload

        assert "details" in payload
        assert "error" in payload["details"]
        assert "timeout" in payload["details"]["error"].lower()

    @pytest.mark.asyncio
    @pytest.mark.error_handling
    async def test_handler_router_initialization_timeout(
        self,
        sample_pattern_request,
        mock_pattern_service,
        caplog,
    ):
        """Test handler behavior when router initialization times out."""
        handler = CodegenPatternHandler(pattern_service=mock_pattern_service)
        handler._router_initialized = False

        with patch(
            "handlers.base_response_publisher.HybridEventRouter"
        ) as mock_router_class:
            mock_router = AsyncMock()
            mock_router.initialize = AsyncMock(
                side_effect=asyncio.TimeoutError("Router init timeout")
            )
            mock_router_class.return_value = mock_router

            # Handle event (should handle timeout gracefully)
            result = await handler.handle_event(sample_pattern_request)

            # Handler succeeds (non-blocking publish failure)
            assert result is True

            # Verify error was logged
            assert any(
                "Failed to publish" in record.message for record in caplog.records
            )

    @pytest.mark.asyncio
    @pytest.mark.error_handling
    async def test_handler_cleanup_on_exception(
        self,
        sample_pattern_request,
        mock_pattern_service,
        mock_router,
    ):
        """Ensure resources cleaned up even when exceptions occur."""
        handler = CodegenPatternHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Make service raise exception
        mock_pattern_service.find_similar_nodes = AsyncMock(
            side_effect=Exception("Service error")
        )

        # Handle event (will fail)
        result = await handler.handle_event(sample_pattern_request)
        assert result is False

        # Now cleanup handler via base class shutdown
        await handler._shutdown_publisher()

        # Verify cleanup happened
        mock_router.shutdown.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.error_handling
    async def test_handler_cleanup_with_uninitialized_resources(
        self,
    ):
        """Test cleanup when resources were never initialized."""
        from archon_services.pattern_learning import CodegenPatternService

        handler = CodegenPatternHandler(pattern_service=CodegenPatternService())
        handler._router = None
        handler._router_initialized = False

        # Cleanup should not crash
        await handler._shutdown_publisher()

        # Should complete without error

    @pytest.mark.asyncio
    @pytest.mark.error_handling
    async def test_handler_cleanup_idempotent(
        self,
        mock_pattern_service,
        mock_router,
    ):
        """Test that cleanup can be called multiple times safely."""
        handler = CodegenPatternHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Call cleanup twice
        await handler._shutdown_publisher()
        await handler._shutdown_publisher()

        # Should not raise errors
        # Cleanup methods should be callable multiple times

    @pytest.mark.asyncio
    @pytest.mark.error_handling
    async def test_handler_service_exception_with_different_errors(
        self,
        sample_pattern_request,
        mock_pattern_service,
        mock_router,
    ):
        """Test handler behavior with various service exceptions."""
        # Test with ConnectionError
        mock_pattern_service.find_similar_nodes = AsyncMock(
            side_effect=ConnectionError("Connection lost")
        )

        handler = CodegenPatternHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Handle event (connection will fail)
        result = await handler.handle_event(sample_pattern_request)

        # Verify graceful handling
        assert result is False

        # Verify error response
        mock_router.publish.assert_called_once()
        event = mock_router.publish.call_args[1]["event"]
        payload = event.payload
        assert "details" in payload
        assert "error" in payload["details"]


# ============================================================================
# Performance Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.performance
@pytest.mark.pattern_handler
@pytest.mark.asyncio
class TestPatternHandlerPerformance:
    """Performance tests for pattern handler flow."""

    async def test_pattern_flow_performance(
        self,
        sample_pattern_request,
        mock_pattern_service,
        mock_router,
    ):
        """Test that pattern flow completes within performance target."""
        import time

        handler = CodegenPatternHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Measure performance
        start = time.time()
        result = await handler.handle_event(sample_pattern_request)
        elapsed = (time.time() - start) * 1000

        # Verify success
        assert result is True

        # Performance target: <500ms for pattern matching flow
        assert elapsed < 500, f"Pattern flow took {elapsed:.2f}ms, exceeds 500ms target"

        print(f"\n✓ Pattern Flow Performance: {elapsed:.2f}ms")

    async def test_batch_pattern_throughput(
        self,
        mock_event_envelope,
        mock_pattern_service,
        mock_router,
    ):
        """Test throughput with batch pattern matching."""
        import time

        handler = CodegenPatternHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Create 20 requests
        requests = []
        for i in range(20):
            correlation_id = str(uuid4())
            payload = {
                "node_description": f"Handle authentication operation {i}",
                "node_type": "effect",
                "limit": 5,
                "score_threshold": 0.7,
            }
            requests.append(mock_event_envelope(correlation_id, payload))

        # Process concurrently
        start = time.time()
        results = await asyncio.gather(*[handler.handle_event(req) for req in requests])
        elapsed = (time.time() - start) * 1000

        # Verify all succeeded
        assert all(results)

        # Performance target: <5s for 20 requests
        assert (
            elapsed < 5000
        ), f"Batch pattern matching took {elapsed:.2f}ms, exceeds 5s"

        # Calculate throughput
        throughput = 20 / (elapsed / 1000)

        print("\n✓ Batch Pattern Matching Performance:")
        print(f"  Total time: {elapsed:.2f}ms")
        print(f"  Throughput: {throughput:.2f} req/s")

    async def test_pattern_flow_with_large_result_set(
        self,
        sample_pattern_request,
        mock_pattern_service,
        mock_router,
    ):
        """Test performance with large result set."""
        import time

        # Override mock to return 20 similar nodes
        large_result_set = []
        for i in range(20):
            large_result_set.append(
                {
                    "node_id": f"node_pattern_{i:03d}",
                    "similarity_score": 0.95 - (i * 0.01),
                    "description": f"Pattern {i} description",
                    "mixins_used": ["MetricsMixin", "CachingMixin"],
                    "contracts": [{"name": f"Contract{i}", "version": "1.0.0"}],
                    "code_snippets": [f"async def method_{i}(self): pass"],
                    "metadata": {
                        "node_type": "effect",
                        "complexity": "moderate",
                        "success_rate": 0.95,
                        "usage_count": 100,
                        "last_used": "2025-10-14T10:00:00Z",
                    },
                }
            )

        mock_pattern_service.find_similar_nodes = AsyncMock(
            return_value=large_result_set
        )

        handler = CodegenPatternHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Measure performance
        start = time.time()
        result = await handler.handle_event(sample_pattern_request)
        elapsed = (time.time() - start) * 1000

        # Verify success
        assert result is True

        # Verify large result set handled
        event = mock_router.publish.call_args[1]["event"]
        payload = event.payload
        assert payload["count"] == 20

        # Performance should still be reasonable (<1s)
        assert elapsed < 1000, f"Large result set took {elapsed:.2f}ms, exceeds 1s"

        print(f"\n✓ Large Result Set Performance: {elapsed:.2f}ms for 20 nodes")
