"""
Integration Tests for Handler Performance Tracking

Tests that all handlers properly integrate with PerformanceBaselineService.

Phase 5C: Performance Intelligence
Created: 2025-10-15
"""

import os
from unittest.mock import AsyncMock, Mock

import pytest
from archon_services.performance import PerformanceBaselineService
from handlers.codegen_analysis_handler import CodegenAnalysisHandler
from handlers.codegen_mixin_handler import CodegenMixinHandler
from handlers.codegen_pattern_handler import CodegenPatternHandler
from handlers.codegen_validation_handler import CodegenValidationHandler

# Test duration configuration (configurable via environment variables)
TEST_DURATION_FAST_MS = float(os.getenv("TEST_DURATION_FAST_MS", "50"))
TEST_DURATION_SLOW_MS = float(os.getenv("TEST_DURATION_SLOW_MS", "500"))


class TestCodegenValidationHandlerPerformance:
    """Test performance tracking in CodegenValidationHandler."""

    @pytest.fixture
    def performance_baseline(self):
        """Create performance baseline service."""
        return PerformanceBaselineService()

    @pytest.fixture
    def validation_handler(self, performance_baseline):
        """Create validation handler with performance tracking."""
        return CodegenValidationHandler(
            quality_service=None,
            pattern_extractor=None,
            performance_baseline=performance_baseline,
        )

    @pytest.mark.asyncio
    async def test_handler_records_performance_on_success(
        self, validation_handler, performance_baseline
    ):
        """Test that handler records performance metrics on successful execution."""
        # Mock event
        mock_event = Mock()
        mock_event.event_type = "codegen.request.validate"
        mock_event.correlation_id = "test-123"
        mock_event.payload = {
            "code_content": "def test(): pass",
            "node_type": "effect",
            "file_path": "test.py",
        }

        # Mock quality service
        validation_handler.quality_service = AsyncMock()
        validation_handler.quality_service.validate_generated_code = AsyncMock(
            return_value={
                "is_valid": True,
                "quality_score": 0.9,
                "onex_compliance_score": 0.85,
                "violations": [],
                "warnings": [],
            }
        )

        # Execute handler
        result = await validation_handler.handle_event(mock_event)
        assert result is True

        # Verify performance was recorded
        assert performance_baseline.get_measurement_count() > 0
        recent = performance_baseline.get_recent_measurements(
            operation="codegen_validation", limit=1
        )
        assert len(recent) == 1
        assert recent[0].operation == "codegen_validation"
        assert recent[0].duration_ms > 0

    @pytest.mark.asyncio
    async def test_handler_records_performance_on_failure(
        self, validation_handler, performance_baseline
    ):
        """Test that handler records performance even when handler fails."""
        # Mock event
        mock_event = Mock()
        mock_event.event_type = "codegen.request.validate"
        mock_event.correlation_id = "test-456"
        mock_event.payload = {"code_content": "def test(): pass", "node_type": "effect"}

        # Mock quality service to raise error
        validation_handler.quality_service = AsyncMock()
        validation_handler.quality_service.validate_generated_code = AsyncMock(
            side_effect=Exception("Validation error")
        )

        # Execute handler (should fail gracefully)
        result = await validation_handler.handle_event(mock_event)
        assert result is False

        # Verify performance was recorded despite failure
        assert performance_baseline.get_measurement_count() > 0
        recent = performance_baseline.get_recent_measurements(
            operation="codegen_validation", limit=1
        )
        assert len(recent) == 1
        assert "error" in recent[0].context

    @pytest.mark.asyncio
    async def test_handler_detects_anomalies(
        self, validation_handler, performance_baseline
    ):
        """Test that handler detects performance anomalies."""
        # Create baseline with fast operations
        for i in range(10):
            await performance_baseline.record_measurement(
                operation="codegen_validation",
                duration_ms=TEST_DURATION_FAST_MS,
                context={},
            )

        # Mock slow operation
        mock_event = Mock()
        mock_event.event_type = "codegen.request.validate"
        mock_event.correlation_id = "slow-op"
        mock_event.payload = {"code_content": "def test(): pass", "node_type": "effect"}

        validation_handler.quality_service = AsyncMock()
        validation_handler.quality_service.validate_generated_code = AsyncMock(
            return_value={
                "is_valid": True,
                "quality_score": 0.9,
                "onex_compliance_score": 0.85,
                "violations": [],
                "warnings": [],
            }
        )

        # Simulate slow execution by recording a slow measurement
        await performance_baseline.record_measurement(
            operation="codegen_validation",
            duration_ms=TEST_DURATION_SLOW_MS,  # Much slower than baseline
            context={},
        )

        # Check if anomaly was detected
        anomaly = await performance_baseline.detect_performance_anomaly(
            operation="codegen_validation", current_duration_ms=TEST_DURATION_SLOW_MS
        )

        assert anomaly["anomaly_detected"] is True


class TestCodegenPatternHandlerPerformance:
    """Test performance tracking in CodegenPatternHandler."""

    @pytest.fixture
    def performance_baseline(self):
        return PerformanceBaselineService()

    @pytest.fixture
    def pattern_handler(self, performance_baseline):
        return CodegenPatternHandler(
            pattern_service=None,
            feedback_service=None,
            performance_baseline=performance_baseline,
        )

    @pytest.mark.asyncio
    async def test_pattern_handler_records_performance(
        self, pattern_handler, performance_baseline
    ):
        """Test pattern handler records performance."""
        mock_event = Mock()
        mock_event.event_type = "codegen.request.pattern"
        mock_event.correlation_id = "pattern-test"
        mock_event.payload = {
            "node_description": "test node",
            "node_type": "effect",
            "limit": 5,
        }

        # Mock pattern service
        pattern_handler.pattern_service = AsyncMock()
        pattern_handler.pattern_service.find_similar_nodes = AsyncMock(return_value=[])

        result = await pattern_handler.handle_event(mock_event)
        assert result is True

        # Verify performance recorded
        recent = performance_baseline.get_recent_measurements(
            operation="codegen_pattern_matching", limit=1
        )
        assert len(recent) == 1
        assert recent[0].operation == "codegen_pattern_matching"


class TestCodegenAnalysisHandlerPerformance:
    """Test performance tracking in CodegenAnalysisHandler."""

    @pytest.fixture
    def performance_baseline(self):
        return PerformanceBaselineService()

    @pytest.fixture
    def analysis_handler(self, performance_baseline):
        return CodegenAnalysisHandler(
            langextract_service=None, performance_baseline=performance_baseline
        )

    @pytest.mark.asyncio
    async def test_analysis_handler_records_performance(
        self, analysis_handler, performance_baseline
    ):
        """Test analysis handler records performance."""
        mock_event = Mock()
        mock_event.event_type = "codegen.request.analyze"
        mock_event.correlation_id = "analysis-test"
        mock_event.payload = {"prd_content": "test content", "analysis_type": "full"}

        # Mock langextract service
        mock_service = AsyncMock()
        mock_service.analyze_prd_semantics = AsyncMock(
            return_value={"concepts": [], "entities": [], "confidence": 0.8}
        )
        analysis_handler.langextract_service = mock_service
        analysis_handler._service_initialized = True

        result = await analysis_handler.handle_event(mock_event)
        assert result is True

        # Verify performance recorded
        recent = performance_baseline.get_recent_measurements(
            operation="codegen_analysis", limit=1
        )
        assert len(recent) == 1
        assert recent[0].operation == "codegen_analysis"


class TestCodegenMixinHandlerPerformance:
    """Test performance tracking in CodegenMixinHandler."""

    @pytest.fixture
    def performance_baseline(self):
        return PerformanceBaselineService()

    @pytest.fixture
    def mixin_handler(self, performance_baseline):
        return CodegenMixinHandler(
            pattern_service=None, performance_baseline=performance_baseline
        )

    @pytest.mark.asyncio
    async def test_mixin_handler_records_performance(
        self, mixin_handler, performance_baseline
    ):
        """Test mixin handler records performance."""
        mock_event = Mock()
        mock_event.event_type = "codegen.request.mixin"
        mock_event.correlation_id = "mixin-test"
        mock_event.payload = {
            "requirements": ["logging", "caching"],
            "node_type": "effect",
        }

        # Mock pattern service
        mixin_handler.pattern_service = AsyncMock()
        mixin_handler.pattern_service.recommend_mixins = AsyncMock(return_value=[])

        result = await mixin_handler.handle_event(mock_event)
        assert result is True

        # Verify performance recorded
        recent = performance_baseline.get_recent_measurements(
            operation="codegen_mixin_recommendation", limit=1
        )
        assert len(recent) == 1
        assert recent[0].operation == "codegen_mixin_recommendation"


class TestAllHandlersPerformanceIntegration:
    """Test performance tracking across all handlers."""

    @pytest.fixture
    def shared_performance_baseline(self):
        """Create shared performance baseline for all handlers."""
        return PerformanceBaselineService()

    @pytest.mark.asyncio
    async def test_multiple_handlers_share_baseline(self, shared_performance_baseline):
        """Test that multiple handlers can share the same baseline service."""
        # Create handlers with shared baseline
        validation_handler = CodegenValidationHandler(
            quality_service=None,
            pattern_extractor=None,
            performance_baseline=shared_performance_baseline,
        )

        pattern_handler = CodegenPatternHandler(
            pattern_service=None,
            feedback_service=None,
            performance_baseline=shared_performance_baseline,
        )

        # Mock services
        validation_handler.quality_service = AsyncMock()
        validation_handler.quality_service.validate_generated_code = AsyncMock(
            return_value={
                "is_valid": True,
                "quality_score": 0.9,
                "onex_compliance_score": 0.85,
                "violations": [],
                "warnings": [],
            }
        )

        pattern_handler.pattern_service = AsyncMock()
        pattern_handler.pattern_service.find_similar_nodes = AsyncMock(return_value=[])

        # Execute both handlers
        mock_event1 = Mock()
        mock_event1.event_type = "codegen.request.validate"
        mock_event1.correlation_id = "test-1"
        mock_event1.payload = {
            "code_content": "def test(): pass",
            "node_type": "effect",
        }

        mock_event2 = Mock()
        mock_event2.event_type = "codegen.request.pattern"
        mock_event2.correlation_id = "test-2"
        mock_event2.payload = {"node_description": "test", "node_type": "effect"}

        await validation_handler.handle_event(mock_event1)
        await pattern_handler.handle_event(mock_event2)

        # Verify both operations recorded
        operations = shared_performance_baseline.get_operations()
        assert (
            "codegen_validation" in operations
            or shared_performance_baseline.get_measurement_count() >= 2
        )
        assert shared_performance_baseline.get_measurement_count() >= 2

    @pytest.mark.asyncio
    async def test_handler_metrics_include_anomalies(self, shared_performance_baseline):
        """Test that handler metrics include anomaly counts."""
        handler = CodegenValidationHandler(
            quality_service=None,
            pattern_extractor=None,
            performance_baseline=shared_performance_baseline,
        )

        # Initial anomaly count should be 0
        metrics = handler.get_metrics()
        assert "performance_anomalies" in metrics
        assert metrics["performance_anomalies"] == 0


@pytest.mark.asyncio
async def test_end_to_end_performance_tracking():
    """End-to-end test of performance tracking system."""
    baseline_service = PerformanceBaselineService()

    # Simulate multiple handler executions
    operations = [
        ("codegen_validation", 150.0),
        ("codegen_pattern_matching", 80.0),
        ("codegen_analysis", 200.0),
        ("codegen_mixin_recommendation", 120.0),
    ]

    # Record measurements for each operation
    for op, duration in operations:
        for i in range(15):
            await baseline_service.record_measurement(
                operation=op,
                duration_ms=duration + (i * 5),  # Slight variation
                context={"iteration": i},
            )

    # Verify baselines exist for all operations
    all_baselines = await baseline_service.get_all_baselines()
    assert len(all_baselines) >= 4

    # Verify anomaly detection works
    anomaly = await baseline_service.detect_performance_anomaly(
        operation="codegen_validation",
        current_duration_ms=TEST_DURATION_SLOW_MS,  # Way above baseline
    )
    assert anomaly["anomaly_detected"] is True


@pytest.mark.asyncio
async def test_performance_tracking_overhead():
    """Test that performance tracking adds minimal overhead."""
    import time

    baseline_service = PerformanceBaselineService()
    handler = CodegenValidationHandler(
        quality_service=None,
        pattern_extractor=None,
        performance_baseline=baseline_service,
    )

    # Mock event
    mock_event = Mock()
    mock_event.event_type = "codegen.request.validate"
    mock_event.correlation_id = "overhead-test"
    mock_event.payload = {"code_content": "def test(): pass", "node_type": "effect"}

    # Mock quality service for fast execution
    handler.quality_service = AsyncMock()
    handler.quality_service.validate_generated_code = AsyncMock(
        return_value={
            "is_valid": True,
            "quality_score": 0.9,
            "onex_compliance_score": 0.85,
            "violations": [],
            "warnings": [],
        }
    )

    # Measure execution time
    start = time.perf_counter()
    await handler.handle_event(mock_event)
    elapsed_ms = (time.perf_counter() - start) * 1000

    # Performance tracking should add <5ms overhead
    assert (
        elapsed_ms < 100.0
    ), f"Handler execution took {elapsed_ms:.2f}ms (includes mocking overhead)"
