"""
Tests for Pattern Metadata Enrichment

Tests the MetadataEnrichmentService and its integration with PatternAnalyticsService.
"""

import asyncio
from uuid import uuid4

import pytest
from src.api.pattern_analytics.service import PatternAnalyticsService
from src.api.pattern_learning.metadata_enrichment import (
    MetadataEnrichmentService,
    enrich_pattern_with_analytics,
)
from src.archon_services.pattern_learning.phase4_traceability.models.model_pattern_feedback import (
    EnumSentiment,
    ModelPatternFeedback,
)


@pytest.mark.asyncio
async def test_enrichment_with_no_feedback():
    """Test enrichment when no feedback data exists (fallback values)"""
    # Setup
    analytics_service = PatternAnalyticsService()
    enrichment_service = MetadataEnrichmentService(analytics_service=analytics_service)

    # Test pattern with no feedback
    pattern_id = str(uuid4())
    pattern_data = {"name": "test_pattern", "type": "architectural"}

    # Enrich
    result = await enrichment_service.enrich_pattern_with_analytics(
        pattern_id=pattern_id,
        pattern_data=pattern_data,
    )

    # Assertions
    assert result["name"] == "test_pattern"
    assert result["type"] == "architectural"
    assert result["success_rate"] == 0.5  # Default fallback
    assert result["usage_count"] == 0  # Default fallback
    assert result["avg_quality_score"] == 0.5  # Default fallback
    assert result["confidence_score"] == 0.5  # Default fallback
    assert result["enriched"] is False  # Fallback was used
    assert result["enrichment_source"] == "fallback"
    assert "enrichment_time_ms" in result
    assert result["enrichment_time_ms"] < 20  # Should be fast


@pytest.mark.asyncio
async def test_enrichment_with_feedback():
    """Test enrichment when feedback data exists"""
    # Setup
    analytics_service = PatternAnalyticsService()
    enrichment_service = MetadataEnrichmentService(analytics_service=analytics_service)

    pattern_id = uuid4()

    # Add some mock feedback to orchestrator
    for i in range(10):
        feedback = ModelPatternFeedback(
            feedback_id=uuid4(),
            pattern_id=pattern_id,
            pattern_name="test_pattern",
            execution_id=uuid4(),
            sentiment=EnumSentiment.POSITIVE if i < 8 else EnumSentiment.NEGATIVE,
            success=i < 8,  # 80% success rate
            quality_score=0.8 + (i * 0.01),  # Varying quality scores
            context={"pattern_type": "architectural"},
            implicit_signals={"execution_time_ms": 100 + i * 10},
        )
        analytics_service.orchestrator.feedback_store.append(feedback)

    # Enrich
    pattern_data = {"name": "test_pattern", "type": "architectural"}
    result = await enrichment_service.enrich_pattern_with_analytics(
        pattern_id=str(pattern_id),
        pattern_data=pattern_data,
    )

    # Assertions
    assert result["name"] == "test_pattern"
    assert result["success_rate"] == 0.8  # 8 out of 10 successful
    assert result["usage_count"] == 10
    assert 0.8 <= result["avg_quality_score"] <= 0.9  # Average of quality scores
    assert result["enriched"] is True
    assert result["enrichment_source"] == "analytics_service"
    assert "enrichment_time_ms" in result
    assert result["enrichment_time_ms"] < 20  # Should be fast


@pytest.mark.asyncio
async def test_enrichment_confidence_calculation():
    """Test confidence score calculation based on sample size"""
    analytics_service = PatternAnalyticsService()
    enrichment_service = MetadataEnrichmentService(analytics_service=analytics_service)

    pattern_id = uuid4()

    # Add 30 feedback items (full confidence threshold)
    for i in range(30):
        feedback = ModelPatternFeedback(
            feedback_id=uuid4(),
            pattern_id=pattern_id,
            pattern_name="test_pattern",
            execution_id=uuid4(),
            sentiment=EnumSentiment.POSITIVE,
            success=True,  # 100% success
            quality_score=0.9,
            context={"pattern_type": "architectural"},
            implicit_signals={"execution_time_ms": 100},
        )
        analytics_service.orchestrator.feedback_store.append(feedback)

    # Enrich
    result = await enrichment_service.enrich_pattern_with_analytics(
        pattern_id=str(pattern_id),
        pattern_data={},
    )

    # Assertions
    assert result["success_rate"] == 1.0  # 100% success
    assert result["usage_count"] == 30
    # Confidence should be high (success_rate * min(sample_size/30, 1.0))
    # = 1.0 * min(30/30, 1.0) = 1.0
    assert result["confidence_score"] == 1.0


@pytest.mark.asyncio
async def test_batch_enrichment():
    """Test batch enrichment of multiple patterns"""
    analytics_service = PatternAnalyticsService()
    enrichment_service = MetadataEnrichmentService(analytics_service=analytics_service)

    # Create test patterns
    patterns = [{"pattern_id": str(uuid4()), "name": f"pattern_{i}"} for i in range(5)]

    # Enrich batch
    enriched = await enrichment_service.enrich_multiple_patterns(patterns)

    # Assertions
    assert len(enriched) == 5
    for pattern in enriched:
        assert "success_rate" in pattern
        assert "usage_count" in pattern
        assert "avg_quality_score" in pattern
        assert "confidence_score" in pattern
        assert "enrichment_time_ms" in pattern


@pytest.mark.asyncio
async def test_enrichment_statistics():
    """Test enrichment statistics tracking"""
    analytics_service = PatternAnalyticsService()
    enrichment_service = MetadataEnrichmentService(analytics_service=analytics_service)

    # Initially no stats
    stats = enrichment_service.get_statistics()
    assert stats["enrichment_count"] == 0
    assert stats["fallback_count"] == 0

    # Enrich some patterns (will use fallback since no feedback)
    for i in range(5):
        await enrichment_service.enrich_pattern_with_analytics(
            pattern_id=str(uuid4()),
            pattern_data={"name": f"pattern_{i}"},
        )

    # Check stats
    stats = enrichment_service.get_statistics()
    assert stats["enrichment_count"] == 5
    assert stats["fallback_count"] == 5
    assert stats["fallback_rate"] == 1.0
    assert stats["avg_enrichment_time_ms"] < 20

    # Reset stats
    enrichment_service.reset_statistics()
    stats = enrichment_service.get_statistics()
    assert stats["enrichment_count"] == 0


@pytest.mark.asyncio
async def test_convenience_function():
    """Test convenience function for direct usage"""
    pattern_id = str(uuid4())
    pattern_data = {"name": "test_pattern"}

    # Use convenience function
    result = await enrich_pattern_with_analytics(
        pattern_id=pattern_id,
        pattern_data=pattern_data,
    )

    # Assertions
    assert "success_rate" in result
    assert "usage_count" in result
    assert "enriched" in result


@pytest.mark.asyncio
async def test_enrichment_performance():
    """Test enrichment performance target (<20ms)"""
    import time

    analytics_service = PatternAnalyticsService()
    enrichment_service = MetadataEnrichmentService(analytics_service=analytics_service)

    pattern_id = str(uuid4())
    pattern_data = {"name": "test_pattern"}

    # Measure performance
    start = time.time()
    result = await enrichment_service.enrich_pattern_with_analytics(
        pattern_id=pattern_id,
        pattern_data=pattern_data,
    )
    elapsed_ms = (time.time() - start) * 1000

    # Assertions
    assert elapsed_ms < 20  # Performance target
    assert result["enrichment_time_ms"] < 20


if __name__ == "__main__":
    # Run tests manually
    print("Running metadata enrichment tests...")

    async def run_tests():
        await test_enrichment_with_no_feedback()
        print("✓ test_enrichment_with_no_feedback")

        await test_enrichment_with_feedback()
        print("✓ test_enrichment_with_feedback")

        await test_enrichment_confidence_calculation()
        print("✓ test_enrichment_confidence_calculation")

        await test_batch_enrichment()
        print("✓ test_batch_enrichment")

        await test_enrichment_statistics()
        print("✓ test_enrichment_statistics")

        await test_convenience_function()
        print("✓ test_convenience_function")

        await test_enrichment_performance()
        print("✓ test_enrichment_performance")

        print("\n✓ All tests passed!")

    asyncio.run(run_tests())
