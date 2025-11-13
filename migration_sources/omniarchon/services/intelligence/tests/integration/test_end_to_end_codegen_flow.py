#!/usr/bin/env python3
"""
End-to-End Integration Tests for Codegen Intelligence Flow

Tests complete flow:
1. Consume Kafka event (or simulate)
2. Handler processes event
3. Response published via HybridEventRouter
4. Verify response reaches correct topic with correct structure

Part of MVP Day 2 - Response Publishing Infrastructure

Author: Archon Intelligence Team (Agent 4)
Date: 2025-10-14
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from events.models.model_event import ModelEvent
from events.models.model_routing_context import (
    ModelRoutingContext,
)
from handlers.codegen_validation_handler import (
    CodegenValidationHandler,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_event_envelope():
    """Create mock event envelope for testing."""

    class MockEventEnvelope:
        def __init__(self, correlation_id: str, payload: Dict[str, Any]):
            self.correlation_id = correlation_id
            self.payload = payload

    return MockEventEnvelope


@pytest.fixture
def sample_validation_request(mock_event_envelope):
    """Create sample validation request event."""
    correlation_id = str(uuid4())

    good_code = """
from omnibase.protocols import ProtocolToolBase
from omnibase.logging import emit_log_event

class ModelUserService(BaseModel):
    user_id: str
    email: str

class NodeUserEffect(NodeBase):
    def __init__(self, registry: BaseOnexRegistry):
        super().__init__(registry)
        self.container: ModelONEXContainer = registry.get_container()

    @standard_error_handling
    async def process(self):
        emit_log_event("Processing user effect")
        try:
            result = await self.execute()
        except OnexError as e:
            raise CoreErrorCode.EXECUTION_FAILED
    """

    payload = {
        "code_content": good_code,
        "node_type": "effect",
        "file_path": "src/nodes/node_user_effect.py",
        "contracts": [{"name": "UserContract", "version": "1.0.0"}],
    }

    return mock_event_envelope(correlation_id, payload)


@pytest.fixture
def sample_error_request(mock_event_envelope):
    """Create sample request that will trigger error."""
    correlation_id = str(uuid4())

    payload = {
        "code_content": None,  # Missing code will trigger error
        "node_type": "effect",
    }

    return mock_event_envelope(correlation_id, payload)


@pytest.fixture
def mock_quality_service():
    """Mock quality service for testing."""
    service = AsyncMock()
    service.validate_generated_code = AsyncMock(
        return_value={
            "is_valid": True,
            "quality_score": 0.85,
            "onex_compliance_score": 0.90,
            "violations": [],
            "warnings": [],
            "suggestions": ["Consider adding docstrings"],
            "architectural_era": "modern_onex",
            "details": {
                "validation_timestamp": datetime.now(timezone.utc).isoformat(),
                "node_type": "effect",
            },
        }
    )
    return service


@pytest.fixture
def mock_router():
    """Mock HybridEventRouter for testing."""
    router = AsyncMock()
    router.initialize = AsyncMock()
    router.publish = AsyncMock()
    router.shutdown = AsyncMock()
    return router


# ============================================================================
# E2E Test Cases
# ============================================================================


class TestCodegenFlowE2E:
    """End-to-end tests for codegen intelligence flow."""

    @pytest.mark.asyncio
    async def test_complete_validation_flow_success(
        self,
        sample_validation_request,
        mock_quality_service,
        mock_router,
    ):
        """
        Test complete validation flow:
        1. Receive validation request
        2. Process with quality service
        3. Publish response via HybridEventRouter
        """
        # Create handler with mocked dependencies
        handler = CodegenValidationHandler(quality_service=mock_quality_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Handle event
        result = await handler.handle_event(sample_validation_request)

        # Verify handler processed successfully
        assert result is True

        # Verify quality service was called
        mock_quality_service.validate_generated_code.assert_called_once()
        call_args = mock_quality_service.validate_generated_code.call_args
        assert call_args[1]["node_type"] == "effect"
        assert call_args[1]["file_path"] == "src/nodes/node_user_effect.py"

        # Verify response was published
        mock_router.publish.assert_called_once()
        publish_call = mock_router.publish.call_args

        # Verify topic
        assert publish_call[1]["topic"] == "omninode.codegen.response.validate.v1"

        # Verify event structure
        event = publish_call[1]["event"]
        assert isinstance(event, ModelEvent)
        assert str(event.correlation_id) == sample_validation_request.correlation_id
        assert event.source_service == "archon-intelligence"

        # Verify payload
        payload = event.payload
        assert payload["is_valid"] is True
        assert payload["quality_score"] == 0.85
        assert payload["onex_compliance_score"] == 0.90

        # Verify routing context
        context = publish_call[1]["context"]
        assert isinstance(context, ModelRoutingContext)
        assert context.requires_persistence is True
        assert context.is_cross_service is True

    @pytest.mark.asyncio
    async def test_validation_flow_with_low_quality_code(
        self,
        mock_event_envelope,
        mock_router,
    ):
        """Test validation flow with low-quality code that fails validation."""
        # Create request with bad code
        correlation_id = str(uuid4())
        bad_code = """
from typing import Any

class myservice:  # Non-CamelCase
    def process(self, data: Any):  # Any type (forbidden)
        import os  # Direct import
        return data
        """

        payload = {
            "code_content": bad_code,
            "node_type": "effect",
        }

        event = mock_event_envelope(correlation_id, payload)

        # Create handler (use real quality service)
        from archon_services.quality import (
            CodegenQualityService,
            ComprehensiveONEXScorer,
        )

        real_quality_service = CodegenQualityService(
            quality_scorer=ComprehensiveONEXScorer()
        )
        handler = CodegenValidationHandler(quality_service=real_quality_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Handle event
        result = await handler.handle_event(event)

        # Verify handler processed successfully
        assert result is True

        # Verify response was published
        mock_router.publish.assert_called_once()
        publish_call = mock_router.publish.call_args

        # Verify payload indicates failure
        payload = publish_call[1]["event"].payload
        assert payload["is_valid"] is False
        assert payload["quality_score"] < 0.7
        assert len(payload["violations"]) > 0

    @pytest.mark.asyncio
    async def test_validation_flow_error_handling(
        self,
        sample_error_request,
        mock_quality_service,
        mock_router,
    ):
        """Test validation flow with error (missing code_content)."""
        # Create handler
        handler = CodegenValidationHandler(quality_service=mock_quality_service)
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
        assert payload["is_valid"] is False
        assert payload["quality_score"] == 0.0
        assert len(payload["violations"]) > 0
        assert "Missing code_content" in payload["violations"][0]

    @pytest.mark.asyncio
    async def test_validation_flow_router_initialization(
        self,
        sample_validation_request,
        mock_quality_service,
    ):
        """Test that handler initializes router if not initialized."""
        # Create handler without initialized router
        handler = CodegenValidationHandler(quality_service=mock_quality_service)
        handler._router_initialized = False

        with patch(
            "handlers.base_response_publisher.HybridEventRouter"
        ) as mock_router_class:
            mock_router = AsyncMock()
            mock_router.initialize = AsyncMock()
            mock_router.publish = AsyncMock()
            mock_router_class.return_value = mock_router

            # Handle event
            result = await handler.handle_event(sample_validation_request)

            # Verify handler processed successfully
            assert result is True

            # Verify router was initialized
            mock_router.initialize.assert_called_once()

            # Verify publish was called
            mock_router.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_validation_flow_publish_failure_recovery(
        self,
        sample_validation_request,
        mock_quality_service,
        mock_router,
        caplog,
    ):
        """Test that publish failures are handled gracefully."""
        # Make router.publish fail
        mock_router.publish.side_effect = Exception("Kafka unavailable")

        # Create handler
        handler = CodegenValidationHandler(quality_service=mock_quality_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Handle event (should not crash)
        result = await handler.handle_event(sample_validation_request)

        # Verify handler still succeeded (publishing is non-blocking)
        assert result is True

        # Verify error was logged
        assert any("Failed to publish" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_response_topic_naming_convention(
        self,
        sample_validation_request,
        mock_quality_service,
        mock_router,
    ):
        """Verify response topic follows naming convention."""
        handler = CodegenValidationHandler(quality_service=mock_quality_service)
        handler._router = mock_router
        handler._router_initialized = True

        await handler.handle_event(sample_validation_request)

        publish_call = mock_router.publish.call_args
        topic = publish_call[1]["topic"]

        # Verify topic naming: omninode.codegen.response.<type>.v1
        assert topic == "omninode.codegen.response.validate.v1"
        assert topic.startswith("omninode.codegen.response.")
        assert topic.endswith(".v1")

    @pytest.mark.asyncio
    async def test_response_includes_correlation_id(
        self,
        sample_validation_request,
        mock_quality_service,
        mock_router,
    ):
        """Verify response includes correlation ID for request tracking."""
        handler = CodegenValidationHandler(quality_service=mock_quality_service)
        handler._router = mock_router
        handler._router_initialized = True

        await handler.handle_event(sample_validation_request)

        publish_call = mock_router.publish.call_args
        event = publish_call[1]["event"]

        # Verify correlation ID preserved
        assert str(event.correlation_id) == sample_validation_request.correlation_id

        # Verify correlation ID used as key
        assert publish_call[1]["key"] == sample_validation_request.correlation_id

    @pytest.mark.asyncio
    async def test_response_payload_structure(
        self,
        sample_validation_request,
        mock_quality_service,
        mock_router,
    ):
        """Verify response payload has required structure."""
        handler = CodegenValidationHandler(quality_service=mock_quality_service)
        handler._router = mock_router
        handler._router_initialized = True

        await handler.handle_event(sample_validation_request)

        publish_call = mock_router.publish.call_args
        event = publish_call[1]["event"]
        payload = event.payload

        # Verify required fields
        required_fields = [
            "is_valid",
            "quality_score",
            "onex_compliance_score",
            "violations",
            "warnings",
            "suggestions",
            "architectural_era",
            "details",
        ]

        for field in required_fields:
            assert field in payload, f"Missing required field: {field}"

        # Verify types
        assert isinstance(payload["is_valid"], bool)
        assert isinstance(payload["quality_score"], (int, float))
        assert isinstance(payload["onex_compliance_score"], (int, float))
        assert isinstance(payload["violations"], list)
        assert isinstance(payload["warnings"], list)
        assert isinstance(payload["suggestions"], list)

    @pytest.mark.asyncio
    async def test_concurrent_requests_handling(
        self,
        mock_event_envelope,
        mock_quality_service,
        mock_router,
    ):
        """Test handling multiple concurrent validation requests."""
        # Create handler
        handler = CodegenValidationHandler(quality_service=mock_quality_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Create multiple requests
        requests = []
        for i in range(10):
            correlation_id = str(uuid4())
            payload = {
                "code_content": f"class Service{i}: pass",
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


# ============================================================================
# Performance Tests
# ============================================================================


@pytest.mark.asyncio
class TestCodegenFlowPerformance:
    """Performance tests for codegen flow."""

    async def test_validation_flow_performance(
        self,
        sample_validation_request,
        mock_router,
    ):
        """Test that validation flow completes within performance target."""
        import time

        from archon_services.quality import (
            CodegenQualityService,
            ComprehensiveONEXScorer,
        )

        real_quality_service = CodegenQualityService(
            quality_scorer=ComprehensiveONEXScorer()
        )
        handler = CodegenValidationHandler(quality_service=real_quality_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Measure performance
        start = time.time()
        result = await handler.handle_event(sample_validation_request)
        elapsed = (time.time() - start) * 1000

        # Verify success
        assert result is True

        # Performance target: <1000ms (1s) for full flow
        assert (
            elapsed < 1000
        ), f"Validation flow took {elapsed:.2f}ms, exceeds 1s target"

        print(f"\n✓ Validation Flow Performance: {elapsed:.2f}ms")

    async def test_batch_validation_throughput(
        self,
        mock_event_envelope,
        mock_router,
    ):
        """Test throughput with batch validation."""
        import time

        from archon_services.quality import (
            CodegenQualityService,
            ComprehensiveONEXScorer,
        )

        real_quality_service = CodegenQualityService(
            quality_scorer=ComprehensiveONEXScorer()
        )
        handler = CodegenValidationHandler(quality_service=real_quality_service)
        handler._router = mock_router
        handler._router_initialized = True

        # Create 20 requests
        requests = []
        for i in range(20):
            correlation_id = str(uuid4())
            payload = {
                "code_content": f"class Service{i}(NodeBase): pass",
                "node_type": "effect",
            }
            requests.append(mock_event_envelope(correlation_id, payload))

        # Process concurrently
        start = time.time()
        results = await asyncio.gather(*[handler.handle_event(req) for req in requests])
        elapsed = (time.time() - start) * 1000

        # Verify all succeeded
        assert all(results)

        # Performance target: <5s for 20 requests
        assert elapsed < 5000, f"Batch validation took {elapsed:.2f}ms, exceeds 5s"

        # Calculate throughput
        throughput = 20 / (elapsed / 1000)

        print("\n✓ Batch Validation Performance:")
        print(f"  Total time: {elapsed:.2f}ms")
        print(f"  Throughput: {throughput:.2f} req/s")


# ============================================================================
# Main Test Runner
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
