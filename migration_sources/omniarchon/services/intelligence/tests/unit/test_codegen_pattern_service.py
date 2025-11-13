"""
Unit tests for Codegen Pattern Service

Tests pattern matching and mixin recommendation logic.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from archon_services.pattern_learning.codegen_pattern_service import (
    CodegenPatternService,
)

# Add src directory to path for imports


class TestCodegenPatternService:
    """Test suite for Codegen Pattern Service."""

    @pytest.fixture
    def mock_vector_index(self):
        """Create mock vector index."""
        mock = AsyncMock()
        # Mock search result structure
        mock.search_similar.return_value = MagicMock(
            hits=[
                MagicMock(
                    id="node-123",
                    score=0.95,
                    payload={
                        "node_type": "effect",
                        "text": "Database writer node for PostgreSQL",
                        "description": "Writes data to PostgreSQL database",
                        "mixins": ["CachingMixin", "RetryMixin"],
                        "contracts": [{"name": "ContractEffect"}],
                        "code_examples": ["class NodeDatabaseEffect: ..."],
                        "complexity": "moderate",
                        "success_rate": 0.98,
                        "usage_count": 42,
                    },
                ),
                MagicMock(
                    id="node-456",
                    score=0.87,
                    payload={
                        "node_type": "effect",
                        "text": "API client node for external service",
                        "description": "Makes HTTP requests to external API",
                        "mixins": ["RetryMixin", "CircuitBreakerMixin"],
                        "contracts": [{"name": "ContractEffect"}],
                        "code_examples": ["class NodeApiClientEffect: ..."],
                        "complexity": "simple",
                        "success_rate": 0.95,
                        "usage_count": 28,
                    },
                ),
            ]
        )
        return mock

    @pytest.fixture
    def service(self, mock_vector_index):
        """Create pattern service instance with mocked dependencies."""
        service = CodegenPatternService()
        service.vector_index = mock_vector_index
        return service

    @pytest.mark.asyncio
    async def test_find_similar_nodes_success(self, service):
        """Test successful pattern matching."""
        result = await service.find_similar_nodes(
            node_description="Write data to database",
            node_type="effect",
            limit=5,
            score_threshold=0.7,
        )

        assert len(result) == 2
        assert result[0]["node_id"] == "node-123"
        assert result[0]["similarity_score"] == 0.95
        # Description comes from "text" field first, then "description"
        assert "Database writer node" in result[0]["description"]
        assert "CachingMixin" in result[0]["mixins_used"]
        assert result[0]["metadata"]["node_type"] == "effect"

    @pytest.mark.asyncio
    async def test_find_similar_nodes_with_limit(self, service):
        """Test pattern matching respects limit."""
        result = await service.find_similar_nodes(
            node_description="API client",
            node_type="effect",
            limit=1,
            score_threshold=0.7,
        )

        # Should return only 1 result despite 2 matches
        assert len(result) == 1
        assert result[0]["node_id"] == "node-123"

    @pytest.mark.asyncio
    async def test_find_similar_nodes_filters_by_type(self, service, mock_vector_index):
        """Test that results are filtered by node type."""
        # Mock with mixed node types
        mock_vector_index.search_similar.return_value = MagicMock(
            hits=[
                MagicMock(
                    id="node-effect",
                    score=0.95,
                    payload={"node_type": "effect", "text": "Effect node"},
                ),
                MagicMock(
                    id="node-compute",
                    score=0.90,
                    payload={"node_type": "compute", "text": "Compute node"},
                ),
            ]
        )

        result = await service.find_similar_nodes(
            node_description="Some description",
            node_type="effect",
            limit=5,
        )

        # Should only return effect nodes
        assert len(result) == 1
        assert result[0]["node_id"] == "node-effect"

    @pytest.mark.asyncio
    async def test_find_similar_nodes_empty_results(self, service, mock_vector_index):
        """Test handling of no matching patterns."""
        mock_vector_index.search_similar.return_value = MagicMock(hits=[])

        result = await service.find_similar_nodes(
            node_description="Nonexistent pattern",
            node_type="effect",
        )

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_find_similar_nodes_error_handling(self, service, mock_vector_index):
        """Test error handling in pattern matching."""
        mock_vector_index.search_similar.side_effect = Exception("Vector search failed")

        result = await service.find_similar_nodes(
            node_description="Some description",
            node_type="effect",
        )

        # Should return empty list on error
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_recommend_mixins_caching(self, service):
        """Test mixin recommendation for caching requirements."""
        result = await service.recommend_mixins(
            requirements=["needs caching", "improve performance"],
            node_type="effect",
        )

        assert len(result) > 0
        # Should recommend CachingMixin
        caching_mixin = next(
            (r for r in result if r["mixin_name"] == "CachingMixin"), None
        )
        assert caching_mixin is not None
        assert caching_mixin["confidence"] > 0.0
        assert (
            "cache" in caching_mixin["reason"].lower()
            or "caching" in caching_mixin["reason"].lower()
        )

    @pytest.mark.asyncio
    async def test_recommend_mixins_retry_logic(self, service):
        """Test mixin recommendation for retry requirements."""
        result = await service.recommend_mixins(
            requirements=["retry on failure", "resilience"],
            node_type="effect",
        )

        assert len(result) > 0
        # Should recommend RetryMixin
        retry_mixin = next((r for r in result if r["mixin_name"] == "RetryMixin"), None)
        assert retry_mixin is not None
        assert retry_mixin["confidence"] > 0.0

    @pytest.mark.asyncio
    async def test_recommend_mixins_multiple_requirements(self, service):
        """Test mixin recommendation with multiple requirements."""
        result = await service.recommend_mixins(
            requirements=["caching", "metrics", "health check"],
            node_type="effect",
        )

        # Should recommend at least 3 mixins
        assert len(result) >= 3

        # Check that recommendations are sorted by confidence
        confidences = [r["confidence"] for r in result]
        assert confidences == sorted(confidences, reverse=True)

    @pytest.mark.asyncio
    async def test_recommend_mixins_node_type_specific(self, service):
        """Test that mixin recommendations are node type specific."""
        effect_result = await service.recommend_mixins(
            requirements=["event handling and caching"],
            node_type="effect",
        )

        compute_result = await service.recommend_mixins(
            requirements=["validation and performance tracking"],
            node_type="compute",
        )

        # Effect nodes should have different available mixins than compute
        effect_names = {r["mixin_name"] for r in effect_result}
        compute_names = {r["mixin_name"] for r in compute_result}

        # Check that effect has EventBusMixin (not in compute)
        assert any("EventBus" in name for name in effect_names)
        # Check that compute has ValidationMixin (not in effect)
        assert any("Validation" in name for name in compute_names) or any(
            "Performance" in name for name in compute_names
        )

    @pytest.mark.asyncio
    async def test_recommend_mixins_empty_requirements(self, service):
        """Test mixin recommendation with no requirements."""
        result = await service.recommend_mixins(
            requirements=[],
            node_type="effect",
        )

        # Should return empty list for no requirements
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_recommend_mixins_unknown_node_type(self, service):
        """Test mixin recommendation with unknown node type."""
        result = await service.recommend_mixins(
            requirements=["some requirement"],
            node_type="unknown_type",
        )

        # Should return empty list for unknown type
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_recommend_mixins_with_config(self, service):
        """Test that mixin recommendations include configuration."""
        result = await service.recommend_mixins(
            requirements=["caching needed"],
            node_type="effect",
        )

        caching_mixin = next(
            (r for r in result if r["mixin_name"] == "CachingMixin"), None
        )
        assert caching_mixin is not None

        # Should have required config
        config = caching_mixin["required_config"]
        assert "cache_ttl_seconds" in config
        assert "cache_strategy" in config
        assert config["cache_ttl_seconds"] == 300

    @pytest.mark.asyncio
    async def test_mixin_confidence_scoring(self, service):
        """Test that mixin confidence scores are calculated correctly."""
        result = await service.recommend_mixins(
            requirements=["cache cache cache"],  # Multiple mentions
            node_type="effect",
        )

        caching_mixin = next(
            (r for r in result if r["mixin_name"] == "CachingMixin"), None
        )
        assert caching_mixin is not None

        # Confidence should be reasonable
        assert 0.0 <= caching_mixin["confidence"] <= 1.0
        assert caching_mixin["confidence"] > 0.0


@pytest.mark.asyncio
class TestCodegenPatternServicePerformance:
    """Performance tests for Codegen Pattern Service."""

    @pytest.fixture
    def service(self):
        """Create pattern service instance."""
        service = CodegenPatternService()
        # Mock vector index for performance tests
        service.vector_index = AsyncMock()
        service.vector_index.search_similar.return_value = MagicMock(hits=[])
        return service

    async def test_mixin_recommendation_performance(self, service):
        """Test that mixin recommendation completes quickly."""
        import time

        start = time.time()
        result = await service.recommend_mixins(
            requirements=["cache", "metrics", "health"],
            node_type="effect",
        )
        elapsed = time.time() - start

        assert elapsed < 0.1, "Mixin recommendation should complete in < 100ms"
        assert result is not None
