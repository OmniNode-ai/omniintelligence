"""
End-to-End Integration Tests for Mixin Recommendation Flow

Tests complete flow:
1. Consume Kafka event (or simulate)
2. Handler processes event with CodegenPatternService
3. Response published via HybridEventRouter
4. Verify response reaches correct topic with correct structure

Part of MVP Day 3 - Mixin Handler Integration Testing

Marker Usage:
  pytest -m integration                   # Run all integration tests
  pytest -m mixin_handler                 # Run only mixin handler tests
  pytest -m "integration and not performance"  # Integration tests, skip performance
  pytest -m error_handling                # Run only error handling tests
  pytest -m concurrent                    # Run only concurrent request tests
  pytest -m "mixin_handler and performance"    # Performance tests for mixin handler

Author: Archon Intelligence Team
Date: 2025-10-15
"""

import asyncio
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from events.models.model_event import ModelEvent
from events.models.model_routing_context import ModelRoutingContext
from handlers.codegen_mixin_handler import CodegenMixinHandler
from integration.utils.assertions import (
    assert_correlation_id_preserved,
    assert_response_structure,
    assert_topic_naming,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_mixin_request(mock_event_envelope):
    """Create sample mixin recommendation request event."""
    correlation_id = str(uuid4())

    payload = {
        "requirements": [
            "needs caching for performance",
            "retry logic for resilience",
            "health check monitoring",
        ],
        "node_type": "effect",
    }

    return mock_event_envelope(correlation_id, payload)


@pytest.fixture
def sample_compute_mixin_request(mock_event_envelope):
    """Create sample mixin request for compute node."""
    correlation_id = str(uuid4())

    payload = {
        "requirements": [
            "validation needed",
            "performance tracking",
            "caching for optimization",
        ],
        "node_type": "compute",
    }

    return mock_event_envelope(correlation_id, payload)


@pytest.fixture
def sample_reducer_mixin_request(mock_event_envelope):
    """Create sample mixin request for reducer node."""
    correlation_id = str(uuid4())

    payload = {
        "requirements": [
            "state management required",
            "aggregation logic",
            "persistence needed",
        ],
        "node_type": "reducer",
    }

    return mock_event_envelope(correlation_id, payload)


@pytest.fixture
def sample_orchestrator_mixin_request(mock_event_envelope):
    """Create sample mixin request for orchestrator node."""
    correlation_id = str(uuid4())

    payload = {
        "requirements": [
            "workflow coordination",
            "dependency management",
            "error handling",
        ],
        "node_type": "orchestrator",
    }

    return mock_event_envelope(correlation_id, payload)


@pytest.fixture
def sample_error_request(mock_event_envelope):
    """Create sample request that will trigger error (missing requirements)."""
    correlation_id = str(uuid4())

    payload = {
        "requirements": [],  # Empty requirements will trigger error
        "node_type": "effect",
    }

    return mock_event_envelope(correlation_id, payload)


@pytest.fixture
def mock_pattern_service():
    """Mock CodegenPatternService for testing."""
    service = AsyncMock()
    service.recommend_mixins = AsyncMock(
        return_value=[
            {
                "mixin_name": "CachingMixin",
                "confidence": 0.85,
                "reason": "CachingMixin matches requirements: needs caching for performance",
                "required_config": {
                    "cache_ttl_seconds": 300,
                    "cache_strategy": "lru",
                    "max_cache_size": 1000,
                },
            },
            {
                "mixin_name": "RetryMixin",
                "confidence": 0.75,
                "reason": "RetryMixin matches requirements: retry logic for resilience",
                "required_config": {
                    "max_retries": 3,
                    "backoff_multiplier": 2.0,
                    "initial_delay_ms": 100,
                },
            },
            {
                "mixin_name": "HealthCheckMixin",
                "confidence": 0.70,
                "reason": "HealthCheckMixin matches requirements: health check monitoring",
                "required_config": {},
            },
        ]
    )
    return service


# ============================================================================
# E2E Test Cases
# ============================================================================


@pytest.mark.integration
@pytest.mark.handler_tests
@pytest.mark.mixin_handler
class TestMixinHandlerE2E:
    """End-to-end tests for mixin recommendation flow."""

    @pytest.mark.asyncio
    async def test_complete_mixin_flow_success(
        self,
        sample_mixin_request,
        mock_pattern_service,
        mock_router,
    ):
        """
        Test complete mixin recommendation flow:
        1. Receive mixin request
        2. Process with pattern service
        3. Publish response via HybridEventRouter
        """
        # Create handler with mocked dependencies
        handler = CodegenMixinHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Handle event
        result = await handler.handle_event(sample_mixin_request)

        # Verify handler processed successfully
        assert result is True

        # Verify pattern service was called
        mock_pattern_service.recommend_mixins.assert_called_once()
        call_args = mock_pattern_service.recommend_mixins.call_args
        assert call_args[1]["node_type"] == "effect"
        assert len(call_args[1]["requirements"]) == 3

        # Verify response was published
        mock_router.publish.assert_called_once()
        publish_call = mock_router.publish.call_args

        # Verify topic
        assert publish_call[1]["topic"] == "omninode.codegen.response.mixin.v1"

        # Verify event structure
        event = publish_call[1]["event"]
        assert isinstance(event, ModelEvent)
        assert str(event.correlation_id) == sample_mixin_request.correlation_id
        assert event.source_service == "archon-intelligence"

        # Verify payload
        payload = event.payload
        assert "recommendations" in payload
        assert "count" in payload
        assert "avg_confidence" in payload
        assert payload["count"] == 3
        assert isinstance(payload["avg_confidence"], float)

        # Verify routing context
        context = publish_call[1]["context"]
        assert isinstance(context, ModelRoutingContext)
        assert context.requires_persistence is True
        assert context.is_cross_service is True

    @pytest.mark.parametrize(
        "node_type,requirements,expected_mixin_patterns",
        [
            (
                "effect",
                ["needs caching", "retry logic", "health monitoring"],
                ["Caching", "Retry", "Health"],
            ),
            (
                "compute",
                ["validation needed", "performance tracking", "caching"],
                ["Validation", "Caching", "Performance"],
            ),
            (
                "reducer",
                ["state management", "aggregation logic", "persistence"],
                ["State", "Aggregation", "Persistence"],
            ),
            (
                "orchestrator",
                ["workflow coordination", "dependency management", "error handling"],
                ["Workflow", "Dependency", "Error"],
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_mixin_recommendations_by_node_type(
        self,
        mock_event_envelope,
        mock_router,
        node_type,
        requirements,
        expected_mixin_patterns,
    ):
        """Test mixin recommendations for different node types.

        Tests that the mixin handler correctly recommends node-type-specific mixins
        based on requirements. Each node type should get mixins matching its patterns.

        Parameters:
            node_type: ONEX node type (effect, compute, reducer, orchestrator)
            requirements: List of requirement strings describing needed functionality
            expected_mixin_patterns: Patterns expected in recommended mixin names
        """
        from archon_services.pattern_learning import CodegenPatternService

        real_pattern_service = CodegenPatternService()
        handler = CodegenMixinHandler(pattern_service=real_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Create request
        correlation_id = str(uuid4())
        payload = {"requirements": requirements, "node_type": node_type}
        event = mock_event_envelope(correlation_id, payload)

        # Handle event
        result = await handler.handle_event(event)
        assert result is True

        # Verify node-type specific mixins
        publish_call = mock_router.publish.call_args
        payload = publish_call[1]["event"].payload
        recommendations = payload["recommendations"]

        mixin_names = [r["mixin_name"] for r in recommendations]
        assert any(
            any(pattern in name for pattern in expected_mixin_patterns)
            for name in mixin_names
        ), f"Expected patterns {expected_mixin_patterns} not found in {mixin_names}"

    @pytest.mark.error_handling
    @pytest.mark.asyncio
    async def test_mixin_flow_error_handling(
        self,
        sample_error_request,
        mock_pattern_service,
        mock_router,
    ):
        """Test mixin flow with error (missing requirements)."""
        # Create handler
        handler = CodegenMixinHandler(pattern_service=mock_pattern_service)
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
        assert "Missing requirements" in payload["details"]["error"]

    @pytest.mark.asyncio
    async def test_mixin_flow_router_initialization(
        self,
        sample_mixin_request,
        mock_pattern_service,
    ):
        """Test that handler initializes router if not initialized."""
        # Create handler without initialized router
        handler = CodegenMixinHandler(pattern_service=mock_pattern_service)
        handler._router_initialized = False

        with patch(
            "handlers.base_response_publisher.HybridEventRouter"
        ) as mock_router_class:
            mock_router = AsyncMock()
            mock_router.initialize = AsyncMock()
            mock_router.publish = AsyncMock()
            mock_router_class.return_value = mock_router

            # Handle event
            result = await handler.handle_event(sample_mixin_request)

            # Verify handler processed successfully
            assert result is True

            # Verify router was initialized
            mock_router.initialize.assert_called_once()

            # Verify publish was called
            mock_router.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_mixin_flow_publish_failure_recovery(
        self,
        sample_mixin_request,
        mock_pattern_service,
        mock_router,
        caplog,
    ):
        """Test that publish failures are handled gracefully."""
        # Make router.publish fail
        mock_router.publish.side_effect = Exception("Kafka unavailable")

        # Create handler
        handler = CodegenMixinHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Handle event (should not crash)
        result = await handler.handle_event(sample_mixin_request)

        # Verify handler still succeeded (publishing is non-blocking)
        assert result is True

        # Verify error was logged
        assert any("Failed to publish" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_response_topic_naming_convention(
        self,
        sample_mixin_request,
        mock_pattern_service,
        mock_router,
    ):
        """Verify response topic follows naming convention."""
        handler = CodegenMixinHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        await handler.handle_event(sample_mixin_request)

        publish_call = mock_router.publish.call_args
        topic = publish_call[1]["topic"]

        # Use shared assertion helper
        assert_topic_naming(topic, "mixin")

    @pytest.mark.asyncio
    async def test_response_includes_correlation_id(
        self,
        sample_mixin_request,
        mock_pattern_service,
        mock_router,
    ):
        """Verify response includes correlation ID for request tracking."""
        handler = CodegenMixinHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        await handler.handle_event(sample_mixin_request)

        publish_call = mock_router.publish.call_args
        event = publish_call[1]["event"]

        # Use shared assertion helpers
        assert_correlation_id_preserved(event, sample_mixin_request.correlation_id)
        assert publish_call[1]["key"] == sample_mixin_request.correlation_id

    @pytest.mark.asyncio
    async def test_response_payload_structure(
        self,
        sample_mixin_request,
        mock_pattern_service,
        mock_router,
    ):
        """Verify response payload has required structure."""
        handler = CodegenMixinHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        await handler.handle_event(sample_mixin_request)

        publish_call = mock_router.publish.call_args
        event = publish_call[1]["event"]
        payload = event.payload

        # Use shared assertion helper for required fields and types
        assert_response_structure(
            payload,
            required_fields=["recommendations", "count", "avg_confidence"],
            field_types={
                "recommendations": list,
                "count": int,
                "avg_confidence": float,
            },
        )

        # Verify each recommendation structure (domain-specific validation)
        for rec in payload["recommendations"]:
            assert "mixin_name" in rec
            assert "confidence" in rec
            assert "reason" in rec
            assert "required_config" in rec
            assert isinstance(rec["mixin_name"], str)
            assert isinstance(rec["confidence"], float)
            assert isinstance(rec["reason"], str)
            assert isinstance(rec["required_config"], dict)

    @pytest.mark.concurrent
    @pytest.mark.asyncio
    async def test_concurrent_requests_handling(
        self,
        mock_event_envelope,
        mock_pattern_service,
        mock_router,
    ):
        """Test handling multiple concurrent mixin recommendation requests."""
        # Create handler
        handler = CodegenMixinHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Create multiple requests
        requests = []
        for i in range(10):
            correlation_id = str(uuid4())
            payload = {
                "requirements": [f"requirement {i}"],
                "node_type": "effect",
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
    async def test_string_requirements_conversion(
        self,
        mock_event_envelope,
        mock_pattern_service,
        mock_router,
    ):
        """Test that single string requirement is converted to list."""
        correlation_id = str(uuid4())
        payload = {
            "requirements": "needs caching",  # Single string
            "node_type": "effect",
        }
        event = mock_event_envelope(correlation_id, payload)

        handler = CodegenMixinHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Handle event
        result = await handler.handle_event(event)

        # Verify success
        assert result is True

        # Verify pattern service received list
        call_args = mock_pattern_service.recommend_mixins.call_args
        requirements = call_args[1]["requirements"]
        assert isinstance(requirements, list)
        assert requirements == ["needs caching"]

    @pytest.mark.asyncio
    @pytest.mark.error_handling
    async def test_handler_service_timeout(
        self,
        sample_mixin_request,
        mock_router,
    ):
        """Test handler behavior when service calls timeout."""
        # Mock service to raise timeout
        mock_service = AsyncMock()
        mock_service.recommend_mixins = AsyncMock(
            side_effect=asyncio.TimeoutError("Service timeout")
        )

        handler = CodegenMixinHandler(pattern_service=mock_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Handle event
        result = await handler.handle_event(sample_mixin_request)

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
        sample_mixin_request,
        mock_pattern_service,
        caplog,
    ):
        """Test handler behavior when router initialization times out."""
        handler = CodegenMixinHandler(pattern_service=mock_pattern_service)
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
            result = await handler.handle_event(sample_mixin_request)

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
        sample_mixin_request,
        mock_pattern_service,
        mock_router,
    ):
        """Ensure resources cleaned up even when exceptions occur."""
        handler = CodegenMixinHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Make service raise exception
        mock_pattern_service.recommend_mixins = AsyncMock(
            side_effect=Exception("Service error")
        )

        # Handle event (will fail)
        result = await handler.handle_event(sample_mixin_request)
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

        handler = CodegenMixinHandler(pattern_service=CodegenPatternService())
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
        handler = CodegenMixinHandler(pattern_service=mock_pattern_service)
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
        sample_mixin_request,
        mock_pattern_service,
        mock_router,
    ):
        """Test handler behavior with various service exceptions."""
        # Test with ConnectionError
        mock_pattern_service.recommend_mixins = AsyncMock(
            side_effect=ConnectionError("Connection lost")
        )

        handler = CodegenMixinHandler(pattern_service=mock_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Handle event (connection will fail)
        result = await handler.handle_event(sample_mixin_request)

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
@pytest.mark.mixin_handler
@pytest.mark.asyncio
class TestMixinHandlerPerformance:
    """Performance tests for mixin recommendation flow."""

    async def test_mixin_flow_performance(
        self,
        sample_mixin_request,
        mock_router,
    ):
        """Test that mixin flow completes within performance target."""
        import time

        from archon_services.pattern_learning import CodegenPatternService

        real_pattern_service = CodegenPatternService()
        handler = CodegenMixinHandler(pattern_service=real_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Measure performance
        start = time.time()
        result = await handler.handle_event(sample_mixin_request)
        elapsed = (time.time() - start) * 1000

        # Verify success
        assert result is True

        # Performance target: <500ms for mixin recommendation
        assert elapsed < 500, f"Mixin flow took {elapsed:.2f}ms, exceeds 500ms target"

        print(f"\n✓ Mixin Flow Performance: {elapsed:.2f}ms")

    async def test_batch_mixin_throughput(
        self,
        mock_event_envelope,
        mock_router,
    ):
        """Test throughput with batch mixin recommendations."""
        import time

        from archon_services.pattern_learning import CodegenPatternService

        real_pattern_service = CodegenPatternService()
        handler = CodegenMixinHandler(pattern_service=real_pattern_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Create 20 requests with different node types
        requests = []
        node_types = ["effect", "compute", "reducer", "orchestrator"]
        for i in range(20):
            correlation_id = str(uuid4())
            payload = {
                "requirements": [f"requirement {i}"],
                "node_type": node_types[i % 4],
            }
            requests.append(mock_event_envelope(correlation_id, payload))

        # Process concurrently
        start = time.time()
        results = await asyncio.gather(*[handler.handle_event(req) for req in requests])
        elapsed = (time.time() - start) * 1000

        # Verify all succeeded
        assert all(results)

        # Performance target: <5s for 20 requests
        assert elapsed < 5000, f"Batch mixin took {elapsed:.2f}ms, exceeds 5s"

        # Calculate throughput
        throughput = 20 / (elapsed / 1000)

        print("\n✓ Batch Mixin Performance:")
        print(f"  Total time: {elapsed:.2f}ms")
        print(f"  Throughput: {throughput:.2f} req/s")
