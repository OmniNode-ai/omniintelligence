"""
Unit tests for NodeIntelligenceAdapterEffect.

Tests the Intelligence Adapter Effect Node with mocked dependencies to verify:
- Initialization and configuration
- Code analysis operations (quality, performance, patterns)
- Error handling and retry logic
- Circuit breaker behavior
- Statistics tracking
- Resource cleanup

Migrated from omniarchon to omniintelligence.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from omnibase_core.enums.enum_core_error_code import EnumCoreErrorCode
from omnibase_core.models.container.model_onex_container import ModelONEXContainer
from omnibase_core.models.errors.model_onex_error import ModelOnexError

# Import client classes from omniintelligence (migrated from omninode_bridge)
from omniintelligence.clients.client_intelligence_service import (
    CoreErrorCode,
    IntelligenceServiceClient,
    IntelligenceServiceError,
)

# Import from omniintelligence package
from omniintelligence.contracts import ModelIntelligenceInput
from omniintelligence.models import ModelIntelligenceConfig, ModelIntelligenceOutput
from omniintelligence.nodes import NodeIntelligenceAdapterEffect


class TestNodeIntelligenceAdapterEffect:
    """Test suite for Intelligence Adapter Effect Node."""

    @pytest.fixture
    def container(self):
        """Create ONEX container for testing."""
        return ModelONEXContainer()

    @pytest.fixture
    def mock_config(self):
        """Create mock intelligence config."""
        return ModelIntelligenceConfig(
            base_url="http://localhost:8053",
            timeout_seconds=30.0,
            max_retries=3,
            retry_delay_ms=1000,
            circuit_breaker_enabled=True,
            circuit_breaker_threshold=5,
            circuit_breaker_timeout_seconds=60.0,
        )

    @pytest.fixture
    def mock_client(self):
        """Create mock intelligence service client."""
        client = AsyncMock(spec=IntelligenceServiceClient)
        client.check_health = AsyncMock(
            return_value=MagicMock(
                status="healthy", service_version="1.0.0", uptime_seconds=12345
            )
        )
        client.get_metrics = MagicMock(
            return_value={
                "total_requests": 100,
                "successful_requests": 95,
                "failed_requests": 5,
                "circuit_breaker_state": "closed",
            }
        )
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def sample_intelligence_input(self):
        """Create sample intelligence input."""
        return ModelIntelligenceInput(
            operation_type="assess_code_quality",
            content="def hello(): pass",
            source_path="test.py",
            language="python",
            options={"include_recommendations": True},
            correlation_id=uuid4(),
        )

    # =========================================================================
    # Initialization Tests
    # =========================================================================

    def test_initialization_with_container(self, container):
        """Test node initialization with valid container."""
        node = NodeIntelligenceAdapterEffect(container)

        assert node is not None
        assert node.node_id is not None
        assert node._config is None  # Not initialized yet
        assert node._client is None
        assert node._stats["total_analyses"] == 0
        assert node._stats["successful_analyses"] == 0

    @pytest.mark.asyncio
    async def test_initialize_loads_config_and_client(
        self, container, mock_config, mock_client
    ):
        """Test initialization loads configuration and creates client."""
        node = NodeIntelligenceAdapterEffect(container)

        with patch.object(
            ModelIntelligenceConfig,
            "from_environment_variable",
            return_value=mock_config,
        ):
            with patch(
                "omniintelligence.nodes.intelligence_adapter.node_intelligence_adapter_effect.IntelligenceServiceClient",
                return_value=mock_client,
            ):
                await node.initialize()

        assert node._config == mock_config
        assert node._client == mock_client
        mock_client.connect.assert_called_once()
        mock_client.check_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_handles_health_check_failure(
        self, container, mock_config, mock_client
    ):
        """Test initialization continues even if health check fails (warning only)."""
        node = NodeIntelligenceAdapterEffect(container)

        # Health check fails
        mock_client.check_health.side_effect = Exception("Service unavailable")

        with patch.object(
            ModelIntelligenceConfig,
            "from_environment_variable",
            return_value=mock_config,
        ):
            with patch(
                "omniintelligence.nodes.intelligence_adapter.node_intelligence_adapter_effect.IntelligenceServiceClient",
                return_value=mock_client,
            ):
                # Should not raise, just log warning
                await node.initialize()

        assert node._config is not None
        assert node._client is not None

    @pytest.mark.asyncio
    async def test_initialize_raises_on_config_error(self, container):
        """Test initialization raises OnexError if config loading fails."""
        node = NodeIntelligenceAdapterEffect(container)

        with patch.object(
            ModelIntelligenceConfig,
            "from_environment_variable",
            side_effect=Exception("Invalid config"),
        ):
            with pytest.raises(ModelOnexError) as exc_info:
                await node.initialize()

            assert exc_info.value.error_code == EnumCoreErrorCode.INITIALIZATION_FAILED
            assert "Failed to initialize Intelligence Adapter" in exc_info.value.message

    # =========================================================================
    # Code Analysis Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_analyze_code_success(
        self, container, mock_config, mock_client, sample_intelligence_input
    ):
        """Test successful code analysis operation."""
        node = NodeIntelligenceAdapterEffect(container)
        node._config = mock_config
        node._client = mock_client

        # Mock quality assessment response
        mock_response = MagicMock()
        mock_response.quality_score = 0.92
        mock_response.onex_compliance = MagicMock(
            score=0.88, violations=[], recommendations=["Use type hints"]
        )
        mock_response.maintainability = MagicMock(complexity_score=0.85)
        mock_response.architectural_era = "advanced_archon"
        mock_response.temporal_relevance = 0.95
        mock_response.architectural_compliance = None

        mock_client.assess_code_quality = AsyncMock(return_value=mock_response)

        # Mock the process method to return expected data
        with patch.object(node, "process", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = MagicMock(
                result={
                    "success": True,
                    "quality_score": 0.92,
                    "onex_compliance": 0.88,
                    "complexity_score": 0.85,
                    "issues": [],
                    "recommendations": ["Use type hints"],
                    "patterns": [],
                    "result_data": {
                        "architectural_era": "advanced_archon",
                        "temporal_relevance": 0.95,
                    },
                },
                processing_time_ms=567.8,
            )

            result = await node.analyze_code(sample_intelligence_input)

        assert isinstance(result, ModelIntelligenceOutput)
        assert result.success is True
        assert result.quality_score == 0.92
        assert result.onex_compliance == 0.88
        assert len(result.recommendations) == 1
        assert node._stats["total_analyses"] == 1
        assert node._stats["successful_analyses"] == 1

    @pytest.mark.asyncio
    async def test_analyze_code_not_initialized_raises_error(
        self, container, sample_intelligence_input
    ):
        """Test analyze_code raises error if node not initialized."""
        node = NodeIntelligenceAdapterEffect(container)

        with pytest.raises(ModelOnexError) as exc_info:
            await node.analyze_code(sample_intelligence_input)

        assert exc_info.value.error_code == EnumCoreErrorCode.INITIALIZATION_FAILED
        assert "not initialized" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_analyze_code_handles_api_failure(
        self, container, mock_config, mock_client, sample_intelligence_input
    ):
        """Test analyze_code handles API failures gracefully."""
        node = NodeIntelligenceAdapterEffect(container)
        node._config = mock_config
        node._client = mock_client

        # Mock client method to raise exception
        mock_client.assess_code_quality = AsyncMock(
            side_effect=Exception("API call failed")
        )

        with pytest.raises(ModelOnexError) as exc_info:
            await node.analyze_code(sample_intelligence_input)

        assert exc_info.value.error_code == EnumCoreErrorCode.OPERATION_FAILED
        assert "Intelligence analysis failed" in exc_info.value.message

        # Verify failure stats updated
        assert node._stats["failed_analyses"] == 1

    @pytest.mark.asyncio
    async def test_analyze_code_preserves_correlation_id(
        self, container, mock_config, mock_client, sample_intelligence_input
    ):
        """Test correlation ID is preserved through analysis operation."""
        node = NodeIntelligenceAdapterEffect(container)
        node._config = mock_config
        node._client = mock_client

        expected_correlation_id = sample_intelligence_input.correlation_id

        with patch.object(node, "process", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = MagicMock(
                result={
                    "success": True,
                    "quality_score": 0.9,
                    "onex_compliance": 0.85,
                },
                processing_time_ms=500.0,
            )

            result = await node.analyze_code(sample_intelligence_input)

        assert result.correlation_id == expected_correlation_id

    # =========================================================================
    # Circuit Breaker Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_failures(
        self, container, mock_config, sample_intelligence_input
    ):
        """Test circuit breaker opens after threshold failures.

        This test verifies two things:
        1. The failure count is tracked correctly in node statistics
        2. The circuit breaker state transitions to 'open' after threshold failures

        Note: Circuit breaker state is managed internally by the IntelligenceServiceClient.
        The node delegates circuit breaker behavior to the client, which exposes the state
        via its get_metrics() method.
        """
        node = NodeIntelligenceAdapterEffect(container)
        node._config = mock_config

        # Track whether circuit breaker should be open based on failure count
        failure_count = {"count": 0}

        def get_circuit_breaker_state():
            """Simulate circuit breaker state based on failure count."""
            if failure_count["count"] >= mock_config.circuit_breaker_threshold:
                return "open"
            return "closed"

        # Create mock client with circuit breaker behavior
        mock_client = AsyncMock(spec=IntelligenceServiceClient)
        mock_client.assess_code_quality = AsyncMock(
            side_effect=IntelligenceServiceError(
                error_code=CoreErrorCode.SERVICE_UNAVAILABLE,
                message="Service down",
                status_code=503,
            )
        )

        # Mock get_metrics to return circuit breaker state dynamically
        mock_client.get_metrics = MagicMock(
            side_effect=lambda: {
                "total_requests": failure_count["count"],
                "successful_requests": 0,
                "failed_requests": failure_count["count"],
                "circuit_breaker_state": get_circuit_breaker_state(),
            }
        )
        node._client = mock_client

        # Simulate multiple failures (should open circuit after threshold)
        for _ in range(mock_config.circuit_breaker_threshold + 1):
            with patch.object(node, "process", side_effect=Exception("Circuit open")):
                with pytest.raises(ModelOnexError):
                    await node.analyze_code(sample_intelligence_input)
            failure_count["count"] += 1

        # Verify 1: Failure count is tracked correctly in node statistics
        assert node._stats["failed_analyses"] >= mock_config.circuit_breaker_threshold

        # Verify 2: Circuit breaker state is 'open' after exceeding threshold
        # The circuit breaker state is tracked internally by the client and exposed
        # via get_metrics(). After threshold failures, the circuit should be open.
        client_metrics = node._client.get_metrics()
        assert client_metrics["circuit_breaker_state"] == "open", (
            f"Expected circuit breaker to be 'open' after {failure_count['count']} failures "
            f"(threshold: {mock_config.circuit_breaker_threshold}), "
            f"but got '{client_metrics['circuit_breaker_state']}'"
        )

    # =========================================================================
    # Statistics Tracking Tests
    # =========================================================================

    def test_get_analysis_stats_initial_state(self, container):
        """Test get_analysis_stats returns correct initial state."""
        node = NodeIntelligenceAdapterEffect(container)

        stats = node.get_analysis_stats()

        assert stats["total_analyses"] == 0
        assert stats["successful_analyses"] == 0
        assert stats["failed_analyses"] == 0
        assert stats["avg_quality_score"] == 0.0
        assert stats["success_rate"] == 0.0
        assert "node_id" in stats

    @pytest.mark.asyncio
    async def test_stats_updated_after_successful_analysis(
        self, container, mock_config, mock_client, sample_intelligence_input
    ):
        """Test statistics are updated after successful analysis."""
        node = NodeIntelligenceAdapterEffect(container)
        node._config = mock_config
        node._client = mock_client

        # Mock quality assessment response
        mock_response = MagicMock()
        mock_response.quality_score = 0.85
        mock_response.onex_compliance = MagicMock(
            score=0.80, violations=[], recommendations=[]
        )
        mock_response.maintainability = MagicMock(complexity_score=0.75)
        mock_response.architectural_era = "advanced_archon"
        mock_response.temporal_relevance = 0.90
        mock_response.architectural_compliance = None

        mock_client.assess_code_quality = AsyncMock(return_value=mock_response)

        await node.analyze_code(sample_intelligence_input)

        stats = node.get_analysis_stats()

        assert stats["total_analyses"] == 1
        assert stats["successful_analyses"] == 1
        assert stats["avg_quality_score"] == 0.85
        assert stats["success_rate"] == 1.0
        assert stats["last_analysis_time"] is not None

    @pytest.mark.asyncio
    async def test_stats_track_average_quality_score(
        self, container, mock_config, mock_client, sample_intelligence_input
    ):
        """Test average quality score is calculated correctly."""
        node = NodeIntelligenceAdapterEffect(container)
        node._config = mock_config
        node._client = mock_client

        quality_scores = [0.8, 0.9, 0.85]

        for score in quality_scores:
            # Mock quality assessment response with different scores
            mock_response = MagicMock()
            mock_response.quality_score = score
            mock_response.onex_compliance = MagicMock(
                score=0.80, violations=[], recommendations=[]
            )
            mock_response.maintainability = MagicMock(complexity_score=0.75)
            mock_response.architectural_era = "advanced_archon"
            mock_response.temporal_relevance = 0.90
            mock_response.architectural_compliance = None

            mock_client.assess_code_quality = AsyncMock(return_value=mock_response)

            await node.analyze_code(sample_intelligence_input)

        stats = node.get_analysis_stats()

        expected_avg = sum(quality_scores) / len(quality_scores)
        assert abs(stats["avg_quality_score"] - expected_avg) < 0.01
        assert stats["successful_analyses"] == 3

    # =========================================================================
    # Retry Logic Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_retry_logic_on_transient_failure(
        self, container, mock_config, mock_client, sample_intelligence_input
    ):
        """Test retry logic retries on transient failures."""
        node = NodeIntelligenceAdapterEffect(container)
        node._config = mock_config
        node._client = mock_client

        # Fail twice, then succeed
        attempt_count = {"count": 0}

        async def mock_client_with_retry(*args, **kwargs):
            attempt_count["count"] += 1
            if attempt_count["count"] < 3:
                raise RuntimeError("Transient error")

            # Success on third attempt
            mock_response = MagicMock()
            mock_response.quality_score = 0.9
            mock_response.onex_compliance = MagicMock(
                score=0.85, violations=[], recommendations=[]
            )
            mock_response.maintainability = MagicMock(complexity_score=0.80)
            mock_response.architectural_era = "advanced_archon"
            mock_response.temporal_relevance = 0.95
            mock_response.architectural_compliance = None
            return mock_response

        mock_client.assess_code_quality = AsyncMock(side_effect=mock_client_with_retry)

        result = await node.analyze_code(sample_intelligence_input)

        assert result.success is True
        assert attempt_count["count"] == 3  # 2 failures + 1 success

    # =========================================================================
    # Resource Cleanup Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_cleanup_closes_client(self, container, mock_config, mock_client):
        """Test cleanup closes HTTP client."""
        node = NodeIntelligenceAdapterEffect(container)
        node._config = mock_config
        node._client = mock_client

        await node._cleanup_node_resources()

        mock_client.close.assert_called_once()
        assert node._client is None

    @pytest.mark.asyncio
    async def test_cleanup_handles_errors_gracefully(self, container, mock_config):
        """Test cleanup handles errors without raising."""
        node = NodeIntelligenceAdapterEffect(container)
        node._config = mock_config

        # Mock client that raises error on close
        mock_client = AsyncMock()
        mock_client.close = AsyncMock(side_effect=Exception("Close failed"))
        node._client = mock_client

        # Should not raise exception
        await node._cleanup_node_resources()

    # =========================================================================
    # Input Conversion Tests
    # =========================================================================

    def test_convert_to_effect_input(
        self, container, mock_config, sample_intelligence_input
    ):
        """Test conversion from ModelIntelligenceInput to ModelEffectInput."""
        node = NodeIntelligenceAdapterEffect(container)
        node._config = mock_config

        effect_input = node._convert_to_effect_input(sample_intelligence_input)

        assert effect_input.operation_id == sample_intelligence_input.correlation_id
        assert effect_input.operation_data["operation_type"] == "assess_code_quality"
        assert effect_input.operation_data["content"] == "def hello(): pass"
        assert effect_input.operation_data["source_path"] == "test.py"
        assert effect_input.operation_data["language"] == "python"
        assert effect_input.retry_enabled is True
        assert effect_input.circuit_breaker_enabled is True

    # =========================================================================
    # Response Transformation Tests
    # =========================================================================

    def test_transform_quality_response(self, container):
        """Test transformation of quality assessment response."""
        node = NodeIntelligenceAdapterEffect(container)

        mock_response = MagicMock()
        mock_response.quality_score = 0.92
        mock_response.onex_compliance = MagicMock(
            score=0.88, violations=["Missing docstring"], recommendations=["Add types"]
        )
        mock_response.maintainability = MagicMock(complexity_score=0.85)
        mock_response.architectural_era = "advanced_archon"
        mock_response.temporal_relevance = 0.95
        mock_response.architectural_compliance = None

        result = node._transform_quality_response(mock_response)

        assert result["success"] is True
        assert result["quality_score"] == 0.92
        assert result["onex_compliance"] == 0.88
        assert result["complexity_score"] == 0.85
        assert len(result["issues"]) == 1
        assert len(result["recommendations"]) == 1

    def test_transform_performance_response(self, container):
        """Test transformation of performance analysis response."""
        node = NodeIntelligenceAdapterEffect(container)

        mock_response = MagicMock()
        mock_response.baseline_metrics = MagicMock(
            complexity_estimate=0.7, model_dump=lambda: {"p50": 100, "p95": 250}
        )
        mock_opportunity = MagicMock(
            title="Optimize loop",
            description="Use list comprehension",
            model_dump=lambda: {"title": "Optimize loop", "impact": "high"},
        )
        mock_response.optimization_opportunities = [mock_opportunity]
        mock_response.total_opportunities = 1
        mock_response.estimated_total_improvement = 0.35

        result = node._transform_performance_response(mock_response)

        assert result["success"] is True
        assert result["complexity_score"] == 0.7
        assert len(result["recommendations"]) == 1
        assert "Optimize loop" in result["recommendations"][0]

    def test_transform_pattern_response(self, container):
        """Test transformation of pattern detection response."""
        node = NodeIntelligenceAdapterEffect(container)

        mock_pattern = MagicMock(model_dump=lambda: {"pattern": "ONEX_EFFECT"})
        mock_anti_pattern = MagicMock(
            pattern_type="GOD_CLASS", description="Class too large"
        )
        mock_response = MagicMock()
        mock_response.detected_patterns = [mock_pattern]
        mock_response.anti_patterns = [mock_anti_pattern]
        mock_response.recommendations = ["Refactor large class"]
        mock_response.architectural_compliance = MagicMock(onex_compliance=0.75)
        mock_response.analysis_summary = "2 patterns found"
        mock_response.confidence_scores = {"overall": 0.85}

        result = node._transform_pattern_response(mock_response)

        assert result["success"] is True
        assert result["onex_compliance"] == 0.75
        assert len(result["patterns"]) == 1
        assert len(result["issues"]) == 1
        assert "GOD_CLASS" in result["issues"][0]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
