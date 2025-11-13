"""
End-to-End Integration Tests for Codegen Analysis Handler

Tests complete flow:
1. Consume Kafka event (or simulate)
2. Handler processes event with LangExtract service
3. Response published via HybridEventRouter
4. Verify response reaches correct topic with correct structure

Part of MVP Day 3 - Integration Testing Phase
Based on: test_end_to_end_codegen_flow.py

Marker Usage:
  pytest -m integration                   # Run all integration tests
  pytest -m analysis_handler              # Run only analysis handler tests
  pytest -m "integration and not performance"  # Integration tests, skip performance
  pytest -m error_handling                # Run only error handling tests
  pytest -m concurrent                    # Run only concurrent request tests
  pytest -m "analysis_handler and performance"  # Performance tests for analysis handler

Author: Archon Intelligence Team
Date: 2025-10-15
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from events.models.model_event import ModelEvent
from handlers import CodegenAnalysisHandler
from integration.utils.assertions import (
    assert_correlation_id_preserved,
    assert_error_response,
    assert_metrics_tracking,
    assert_publish_called_with_key,
    assert_response_structure,
    assert_routing_context,
    assert_topic_naming,
    assert_unique_correlation_ids,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_prd_analysis_request(mock_event_envelope):
    """Create sample PRD analysis request event."""
    correlation_id = str(uuid4())

    prd_content = """
    ## User Authentication Service

    ### Requirements
    The system shall provide secure user authentication via REST API endpoints.

    ### Features
    - User registration with email validation
    - JWT-based session management
    - Password reset functionality
    - OAuth2 integration for social login

    ### Technical Details
    - Store user credentials in PostgreSQL database
    - Use bcrypt for password hashing
    - Implement rate limiting for API endpoints
    - Cache session tokens in Redis

    ### API Endpoints
    - POST /api/auth/register - Create new user account
    - POST /api/auth/login - Authenticate user
    - POST /api/auth/refresh - Refresh access token
    - POST /api/auth/logout - End user session
    """

    payload = {
        "prd_content": prd_content,
        "analysis_type": "full",
        "context": "REST API authentication service",
        "min_confidence": 0.7,
    }

    return mock_event_envelope(correlation_id, payload)


@pytest.fixture
def sample_quick_analysis_request(mock_event_envelope):
    """Create sample quick analysis request event."""
    correlation_id = str(uuid4())

    prd_content = """
    Simple data transformation service that converts JSON to XML format.
    Input: JSON document
    Output: XML document
    """

    payload = {
        "prd_content": prd_content,
        "analysis_type": "quick",
        "context": "Data transformation",
        "min_confidence": 0.8,
    }

    return mock_event_envelope(correlation_id, payload)


@pytest.fixture
def sample_error_request(mock_event_envelope):
    """Create sample request that will trigger error."""
    correlation_id = str(uuid4())

    payload = {
        "prd_content": None,  # Missing prd_content will trigger error
        "analysis_type": "full",
    }

    return mock_event_envelope(correlation_id, payload)


@pytest.fixture
def mock_langextract_service():
    """Mock LangExtract service for testing."""
    service = AsyncMock()

    # Mock successful semantic analysis response
    mock_concept = MagicMock()
    mock_concept.concept = "authentication"
    mock_concept.score = 0.92
    mock_concept.context = "user authentication"

    mock_pattern = MagicMock()
    mock_pattern.pattern_type = "API_INTEGRATION"
    mock_pattern.strength = 0.85
    mock_pattern.description = "REST API integration pattern"

    mock_theme = MagicMock()
    mock_theme.theme = "security"

    mock_result = MagicMock()
    mock_result.concepts = [mock_concept]
    mock_result.patterns = [mock_pattern]
    mock_result.themes = [mock_theme]
    mock_result.domains = ["authentication", "security"]
    mock_result.processing_time_ms = 150
    mock_result.language = "en"

    service.analyze_prd_semantics = AsyncMock(
        return_value={
            "concepts": [
                {
                    "name": "authentication",
                    "confidence": 0.92,
                    "type": "concept",
                    "context": "user authentication",
                }
            ],
            "entities": [
                {"name": "User", "confidence": 0.88, "context": "user entity"},
                {"name": "Token", "confidence": 0.85, "context": "JWT token"},
            ],
            "relationships": [
                {
                    "pattern": "API_INTEGRATION",
                    "confidence": 0.85,
                    "description": "REST API integration pattern",
                }
            ],
            "domain_keywords": ["security", "authentication", "api"],
            "node_type_hints": {
                "effect": 0.45,
                "compute": 0.25,
                "reducer": 0.20,
                "orchestrator": 0.10,
            },
            "confidence": 0.87,
            "metadata": {
                "processing_time_ms": 150,
                "language": "en",
                "total_concepts": 1,
                "total_themes": 1,
                "total_domains": 2,
                "total_patterns": 1,
                "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
    )

    service.connect = AsyncMock()
    service.close = AsyncMock()

    return service


# ============================================================================
# E2E Test Cases
# ============================================================================


@pytest.mark.integration
@pytest.mark.handler_tests
@pytest.mark.analysis_handler
@pytest.mark.requires_langextract
class TestAnalysisHandlerIntegration:
    """End-to-end integration tests for CodegenAnalysisHandler."""

    @pytest.mark.asyncio
    async def test_complete_analysis_flow_success(
        self,
        sample_prd_analysis_request,
        mock_langextract_service,
        mock_router,
    ):
        """
        Test complete analysis flow:
        1. Receive PRD analysis request
        2. Process with LangExtract service
        3. Publish response via HybridEventRouter
        """
        # Create handler with mocked dependencies
        handler = CodegenAnalysisHandler(langextract_service=mock_langextract_service)
        handler._router = mock_router
        handler._router_initialized = True
        handler._service_initialized = True

        # Handle event
        result = await handler.handle_event(sample_prd_analysis_request)

        # Verify handler processed successfully
        assert result is True

        # Verify LangExtract service was called
        mock_langextract_service.analyze_prd_semantics.assert_called_once()
        call_args = mock_langextract_service.analyze_prd_semantics.call_args
        assert call_args[1]["analysis_type"] == "full"
        assert call_args[1]["min_confidence"] == 0.7
        assert "authentication" in call_args[1]["prd_content"].lower()

        # Verify response was published
        mock_router.publish.assert_called_once()
        publish_call = mock_router.publish.call_args

        # Verify topic
        assert publish_call[1]["topic"] == "omninode.codegen.response.analyze.v1"

        # Verify event structure
        event = publish_call[1]["event"]
        assert isinstance(event, ModelEvent)
        assert str(event.correlation_id) == sample_prd_analysis_request.correlation_id
        assert event.source_service == "archon-intelligence"

        # Verify payload structure
        payload = event.payload
        assert "concepts" in payload
        assert "entities" in payload
        assert "relationships" in payload
        assert "domain_keywords" in payload
        assert "node_type_hints" in payload
        assert "confidence" in payload
        assert payload["confidence"] == 0.87

        # Verify routing context
        context = publish_call[1]["context"]
        assert_routing_context(
            context, requires_persistence=True, is_cross_service=True
        )

    @pytest.mark.parametrize(
        "analysis_type,prd_content,min_confidence",
        [
            (
                "quick",
                "Simple data transformation service that converts JSON to XML format. Input: JSON document, Output: XML document",
                0.8,
            ),
            (
                "full",
                "User authentication service with JWT tokens, session management, OAuth2 integration, password reset functionality",
                0.7,
            ),
            (
                "detailed",
                "Data aggregation service that processes streaming events, aggregates metrics from multiple sources, stores in time-series database, triggers alerts",
                0.6,
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_analysis_with_different_modes(
        self,
        mock_event_envelope,
        mock_langextract_service,
        mock_router,
        analysis_type,
        prd_content,
        min_confidence,
    ):
        """Test PRD analysis with different analysis modes.

        Tests that the handler correctly processes different analysis types (quick, full, detailed)
        with appropriate confidence thresholds and PRD content patterns.

        Parameters:
            analysis_type: Analysis mode (quick, full, detailed)
            prd_content: PRD content to analyze
            min_confidence: Minimum confidence threshold for analysis
        """
        # Create handler
        handler = CodegenAnalysisHandler(langextract_service=mock_langextract_service)
        handler._router = mock_router
        handler._router_initialized = True
        handler._service_initialized = True

        # Create request
        correlation_id = str(uuid4())
        payload = {
            "prd_content": prd_content,
            "analysis_type": analysis_type,
            "context": f"{analysis_type.capitalize()} analysis test",
            "min_confidence": min_confidence,
        }
        event = mock_event_envelope(correlation_id, payload)

        # Handle event
        result = await handler.handle_event(event)

        # Verify success
        assert result is True

        # Verify analysis type was passed correctly
        call_args = mock_langextract_service.analyze_prd_semantics.call_args
        assert call_args[1]["analysis_type"] == analysis_type
        assert call_args[1]["min_confidence"] == min_confidence
        assert prd_content.split()[0].lower() in call_args[1]["prd_content"].lower()

        # Verify response published
        mock_router.publish.assert_called_once()

    @pytest.mark.error_handling
    @pytest.mark.asyncio
    async def test_analysis_error_handling_missing_prd_content(
        self,
        sample_error_request,
        mock_langextract_service,
        mock_router,
    ):
        """Test analysis flow with error (missing prd_content)."""
        # Create handler
        handler = CodegenAnalysisHandler(langextract_service=mock_langextract_service)
        handler._router = mock_router
        handler._router_initialized = True
        handler._service_initialized = True

        # Handle event (should handle gracefully)
        result = await handler.handle_event(sample_error_request)

        # Verify handler returned False (error)
        assert result is False

        # Verify LangExtract service was NOT called
        mock_langextract_service.analyze_prd_semantics.assert_not_called()

        # Verify error response was published
        mock_router.publish.assert_called_once()
        publish_call = mock_router.publish.call_args

        # Verify error payload
        event = publish_call[1]["event"]
        payload = event.payload
        # Error is in details dict
        assert_error_response(payload, "prd_content")

    @pytest.mark.asyncio
    async def test_analysis_router_initialization(
        self,
        sample_prd_analysis_request,
        mock_langextract_service,
    ):
        """Test that handler initializes router if not initialized."""
        # Create handler without initialized router
        handler = CodegenAnalysisHandler(langextract_service=mock_langextract_service)
        handler._router_initialized = False
        handler._service_initialized = True

        with patch(
            "src.handlers.base_response_publisher.HybridEventRouter"
        ) as mock_router_class:
            mock_router = AsyncMock()
            mock_router.initialize = AsyncMock()
            mock_router.publish = AsyncMock()
            mock_router_class.return_value = mock_router

            # Handle event
            result = await handler.handle_event(sample_prd_analysis_request)

            # Verify handler processed successfully
            assert result is True

            # Verify router was initialized
            mock_router.initialize.assert_called_once()

            # Verify publish was called
            mock_router.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_analysis_service_initialization(
        self,
        sample_prd_analysis_request,
        mock_router,
    ):
        """Test that handler initializes LangExtract service if not initialized."""
        # Create handler without initialized service
        handler = CodegenAnalysisHandler()
        handler._router = mock_router
        handler._router_initialized = True
        handler._service_initialized = False

        with patch(
            "src.handlers.codegen_analysis_handler.CodegenLangExtractService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service.connect = AsyncMock()
            mock_service.analyze_prd_semantics = AsyncMock(
                return_value={
                    "concepts": [],
                    "entities": [],
                    "relationships": [],
                    "domain_keywords": [],
                    "node_type_hints": {},
                    "confidence": 0.5,
                    "metadata": {},
                }
            )
            mock_service_class.return_value = mock_service

            # Handle event
            result = await handler.handle_event(sample_prd_analysis_request)

            # Verify handler processed successfully
            assert result is True

            # Verify service was connected
            mock_service.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_analysis_publish_failure_recovery(
        self,
        sample_prd_analysis_request,
        mock_langextract_service,
        mock_router,
        caplog,
    ):
        """Test that publish failures are handled gracefully."""
        # Make router.publish fail
        mock_router.publish.side_effect = Exception("Kafka unavailable")

        # Create handler
        handler = CodegenAnalysisHandler(langextract_service=mock_langextract_service)
        handler._router = mock_router
        handler._router_initialized = True
        handler._service_initialized = True

        # Handle event (should not crash)
        result = await handler.handle_event(sample_prd_analysis_request)

        # Verify handler still succeeded (publishing is non-blocking)
        assert result is True

        # Verify error was logged
        assert any("Failed to publish" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_response_topic_naming_convention(
        self,
        sample_prd_analysis_request,
        mock_langextract_service,
        mock_router,
    ):
        """Verify response topic follows naming convention."""
        handler = CodegenAnalysisHandler(langextract_service=mock_langextract_service)
        handler._router = mock_router
        handler._router_initialized = True
        handler._service_initialized = True

        await handler.handle_event(sample_prd_analysis_request)

        publish_call = mock_router.publish.call_args
        topic = publish_call[1]["topic"]

        # Verify topic naming: omninode.codegen.response.<type>.v1
        assert_topic_naming(topic, "analyze")

    @pytest.mark.asyncio
    async def test_response_includes_correlation_id(
        self,
        sample_prd_analysis_request,
        mock_langextract_service,
        mock_router,
    ):
        """Verify response includes correlation ID for request tracking."""
        handler = CodegenAnalysisHandler(langextract_service=mock_langextract_service)
        handler._router = mock_router
        handler._router_initialized = True
        handler._service_initialized = True

        await handler.handle_event(sample_prd_analysis_request)

        publish_call = mock_router.publish.call_args
        event = publish_call[1]["event"]

        # Verify correlation ID preserved
        assert_correlation_id_preserved(
            event, sample_prd_analysis_request.correlation_id
        )

        # Verify correlation ID used as key
        assert_publish_called_with_key(
            publish_call, sample_prd_analysis_request.correlation_id
        )

    @pytest.mark.asyncio
    async def test_response_payload_structure(
        self,
        sample_prd_analysis_request,
        mock_langextract_service,
        mock_router,
    ):
        """Verify response payload has required structure."""
        handler = CodegenAnalysisHandler(langextract_service=mock_langextract_service)
        handler._router = mock_router
        handler._router_initialized = True
        handler._service_initialized = True

        await handler.handle_event(sample_prd_analysis_request)

        publish_call = mock_router.publish.call_args
        event = publish_call[1]["event"]
        payload = event.payload

        # Verify required fields and types
        required_fields = [
            "concepts",
            "entities",
            "relationships",
            "domain_keywords",
            "node_type_hints",
            "confidence",
            "metadata",
        ]

        field_types = {
            "concepts": list,
            "entities": list,
            "relationships": list,
            "domain_keywords": list,
            "node_type_hints": dict,
            "confidence": (int, float),
            "metadata": dict,
        }

        assert_response_structure(payload, required_fields, field_types)

        # Verify confidence range
        assert 0.0 <= payload["confidence"] <= 1.0

        # Verify node_type_hints structure
        expected_node_types = ["effect", "compute", "reducer", "orchestrator"]
        for node_type in expected_node_types:
            if node_type in payload["node_type_hints"]:
                assert isinstance(payload["node_type_hints"][node_type], (int, float))
                assert 0.0 <= payload["node_type_hints"][node_type] <= 1.0

    @pytest.mark.concurrent
    @pytest.mark.asyncio
    async def test_concurrent_requests_handling(
        self,
        mock_event_envelope,
        mock_langextract_service,
        mock_router,
    ):
        """Test handling multiple concurrent analysis requests."""
        # Create handler
        handler = CodegenAnalysisHandler(langextract_service=mock_langextract_service)
        handler._router = mock_router
        handler._router_initialized = True
        handler._service_initialized = True

        # Create multiple requests
        requests = []
        for i in range(10):
            correlation_id = str(uuid4())
            payload = {
                "prd_content": f"Service {i}: Process data and store results.",
                "analysis_type": "quick",
            }
            requests.append(mock_event_envelope(correlation_id, payload))

        # Process concurrently
        results = await asyncio.gather(*[handler.handle_event(req) for req in requests])

        # Verify all processed successfully
        assert all(results)

        # Verify all published
        assert mock_router.publish.call_count == 10

        # Verify each has unique correlation ID
        assert_unique_correlation_ids(mock_router.publish.call_args_list, 10)

    @pytest.mark.asyncio
    async def test_handler_metrics_tracking(
        self,
        sample_prd_analysis_request,
        mock_langextract_service,
        mock_router,
    ):
        """Test that handler tracks metrics correctly."""
        # Create handler
        handler = CodegenAnalysisHandler(langextract_service=mock_langextract_service)
        handler._router = mock_router
        handler._router_initialized = True
        handler._service_initialized = True

        # Process multiple events
        await handler.handle_event(sample_prd_analysis_request)
        await handler.handle_event(sample_prd_analysis_request)

        # Get metrics
        metrics = handler.get_metrics()

        # Verify metrics using shared assertion helper
        assert_metrics_tracking(metrics, 2, 0, "CodegenAnalysisHandler")

    @pytest.mark.asyncio
    async def test_handler_cleanup(
        self,
        mock_langextract_service,
    ):
        """Test handler cleanup closes resources properly."""
        # Create handler
        handler = CodegenAnalysisHandler(langextract_service=mock_langextract_service)
        handler._service_initialized = True

        with patch(
            "src.handlers.base_response_publisher.HybridEventRouter"
        ) as mock_router_class:
            mock_router = AsyncMock()
            mock_router.initialize = AsyncMock()
            mock_router.shutdown = AsyncMock()
            mock_router_class.return_value = mock_router

            handler._router = mock_router
            handler._router_initialized = True

            # Cleanup
            await handler.cleanup()

            # Verify service was closed
            mock_langextract_service.close.assert_called_once()

            # Verify router was shutdown
            mock_router.shutdown.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.error_handling
    async def test_handler_service_timeout(
        self,
        sample_prd_analysis_request,
        mock_router,
    ):
        """Test handler behavior when service calls timeout."""
        # Mock service to raise timeout
        mock_service = AsyncMock()
        mock_service.analyze_prd_semantics = AsyncMock(
            side_effect=asyncio.TimeoutError("Service timeout")
        )
        mock_service.connect = AsyncMock()
        mock_service.close = AsyncMock()

        handler = CodegenAnalysisHandler(langextract_service=mock_service)
        handler._router = mock_router
        handler._router_initialized = True
        handler._service_initialized = True

        # Handle event
        result = await handler.handle_event(sample_prd_analysis_request)

        # Verify graceful timeout handling
        assert result is False

        # Verify error response published
        mock_router.publish.assert_called_once()
        event = mock_router.publish.call_args[1]["event"]
        payload = event.payload

        assert_error_response(payload, "timeout")

    @pytest.mark.asyncio
    @pytest.mark.error_handling
    async def test_handler_router_initialization_timeout(
        self,
        sample_prd_analysis_request,
        mock_langextract_service,
        caplog,
    ):
        """Test handler behavior when router initialization times out."""
        handler = CodegenAnalysisHandler(langextract_service=mock_langextract_service)
        handler._router_initialized = False
        handler._service_initialized = True

        with patch(
            "src.handlers.base_response_publisher.HybridEventRouter"
        ) as mock_router_class:
            mock_router = AsyncMock()
            mock_router.initialize = AsyncMock(
                side_effect=asyncio.TimeoutError("Router init timeout")
            )
            mock_router_class.return_value = mock_router

            # Handle event (should handle timeout gracefully)
            result = await handler.handle_event(sample_prd_analysis_request)

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
        sample_prd_analysis_request,
        mock_langextract_service,
        mock_router,
    ):
        """Ensure resources cleaned up even when exceptions occur."""
        handler = CodegenAnalysisHandler(langextract_service=mock_langextract_service)
        handler._router = mock_router
        handler._router_initialized = True
        handler._service_initialized = True

        # Make service raise exception
        mock_langextract_service.analyze_prd_semantics = AsyncMock(
            side_effect=Exception("Service error")
        )

        # Handle event (will fail)
        result = await handler.handle_event(sample_prd_analysis_request)
        assert result is False

        # Now cleanup handler
        await handler.cleanup()

        # Verify cleanup still happened despite error
        mock_langextract_service.close.assert_called_once()
        mock_router.shutdown.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.error_handling
    async def test_handler_cleanup_with_uninitialized_resources(
        self,
    ):
        """Test cleanup when resources were never initialized."""
        handler = CodegenAnalysisHandler()
        handler._router = None
        handler._router_initialized = False
        handler._service_initialized = False

        # Cleanup should not crash
        await handler.cleanup()

        # Should complete without error

    @pytest.mark.asyncio
    @pytest.mark.error_handling
    async def test_handler_cleanup_idempotent(
        self,
        mock_langextract_service,
        mock_router,
    ):
        """Test that cleanup can be called multiple times safely."""
        handler = CodegenAnalysisHandler(langextract_service=mock_langextract_service)
        handler._router = mock_router
        handler._router_initialized = True
        handler._service_initialized = True

        # Call cleanup twice
        await handler.cleanup()
        await handler.cleanup()

        # Should not raise errors
        # Cleanup methods should be callable multiple times

    @pytest.mark.asyncio
    @pytest.mark.error_handling
    async def test_handler_service_connection_failure(
        self,
        sample_prd_analysis_request,
        mock_router,
    ):
        """Test handler behavior when service connection fails."""
        handler = CodegenAnalysisHandler()
        handler._router = mock_router
        handler._router_initialized = True
        handler._service_initialized = False

        with patch(
            "src.handlers.codegen_analysis_handler.CodegenLangExtractService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service.connect = AsyncMock(
                side_effect=ConnectionError("Cannot connect to service")
            )
            mock_service_class.return_value = mock_service

            # Handle event (connection will fail)
            result = await handler.handle_event(sample_prd_analysis_request)

            # Verify graceful handling
            assert result is False

            # Verify error response
            mock_router.publish.assert_called_once()
            event = mock_router.publish.call_args[1]["event"]
            payload = event.payload
            assert_error_response(payload, "connect")


# ============================================================================
# Performance Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.performance
@pytest.mark.analysis_handler
@pytest.mark.requires_langextract
@pytest.mark.asyncio
class TestAnalysisHandlerPerformance:
    """Performance benchmarks for analysis handler."""

    async def test_analysis_flow_performance(
        self,
        sample_prd_analysis_request,
        mock_langextract_service,
        mock_router,
    ):
        """Test that analysis flow completes within performance target."""
        import time

        handler = CodegenAnalysisHandler(langextract_service=mock_langextract_service)
        handler._router = mock_router
        handler._router_initialized = True
        handler._service_initialized = True

        # Measure performance
        start = time.time()
        result = await handler.handle_event(sample_prd_analysis_request)
        elapsed = (time.time() - start) * 1000

        # Verify success
        assert result is True

        # Performance target: <500ms for full analysis flow
        assert (
            elapsed < 500
        ), f"Analysis flow took {elapsed:.2f}ms, exceeds 500ms target"

        print(f"\n✓ Analysis Flow Performance: {elapsed:.2f}ms")

    async def test_batch_analysis_throughput(
        self,
        mock_event_envelope,
        mock_langextract_service,
        mock_router,
    ):
        """Test throughput with batch analysis."""
        import time

        handler = CodegenAnalysisHandler(langextract_service=mock_langextract_service)
        handler._router = mock_router
        handler._router_initialized = True
        handler._service_initialized = True

        # Create 20 requests
        requests = []
        for i in range(20):
            correlation_id = str(uuid4())
            payload = {
                "prd_content": f"Service {i}: REST API for data processing with database storage.",
                "analysis_type": "quick",
            }
            requests.append(mock_event_envelope(correlation_id, payload))

        # Process concurrently
        start = time.time()
        results = await asyncio.gather(*[handler.handle_event(req) for req in requests])
        elapsed = (time.time() - start) * 1000

        # Verify all succeeded
        assert all(results)

        # Performance target: <5s for 20 requests
        assert elapsed < 5000, f"Batch analysis took {elapsed:.2f}ms, exceeds 5s"

        # Calculate throughput
        throughput = 20 / (elapsed / 1000)

        print("\n✓ Batch Analysis Performance:")
        print(f"  Total time: {elapsed:.2f}ms")
        print(f"  Throughput: {throughput:.2f} req/s")
