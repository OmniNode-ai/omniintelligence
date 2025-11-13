"""
Integration Tests for Pattern Feedback Service

Tests feedback loop functionality including validation outcome tracking,
success rate calculation, and confidence scoring.

Created: 2025-10-15 (MVP Phase 5A)
"""

from datetime import datetime, timezone

import pytest

from .pattern_feedback import (
    PatternFeedback,
    PatternFeedbackService,
    ValidationOutcome,
)


class TestPatternFeedbackService:
    """Test suite for PatternFeedbackService."""

    @pytest.fixture
    def feedback_service(self):
        """Create fresh feedback service for each test."""
        return PatternFeedbackService()

    @pytest.mark.asyncio
    async def test_record_feedback_success(self, feedback_service):
        """Test recording successful validation feedback."""
        validation_result = {
            "is_valid": True,
            "quality_score": 0.95,
            "onex_compliance_score": 0.92,
            "violations": [],
            "node_type": "effect",
        }

        await feedback_service.record_feedback(
            pattern_id="pattern_123",
            correlation_id="corr_001",
            validation_result=validation_result,
        )

        # Check feedback was recorded
        assert len(feedback_service.feedback_history) == 1
        feedback = feedback_service.feedback_history[0]

        assert feedback.pattern_id == "pattern_123"
        assert feedback.correlation_id == "corr_001"
        assert feedback.outcome == ValidationOutcome.SUCCESS
        assert feedback.quality_score == 0.95
        assert feedback.compliance_score == 0.92
        assert feedback.context["node_type"] == "effect"

    @pytest.mark.asyncio
    async def test_record_feedback_partial_success(self, feedback_service):
        """Test recording partial success (quality < 0.9)."""
        validation_result = {
            "is_valid": True,
            "quality_score": 0.75,
            "onex_compliance_score": 0.80,
            "violations": [],
            "node_type": "compute",
        }

        await feedback_service.record_feedback(
            pattern_id="pattern_456",
            correlation_id="corr_002",
            validation_result=validation_result,
        )

        feedback = feedback_service.feedback_history[0]
        assert feedback.outcome == ValidationOutcome.PARTIAL_SUCCESS

    @pytest.mark.asyncio
    async def test_record_feedback_failure(self, feedback_service):
        """Test recording validation failure."""
        validation_result = {
            "is_valid": False,
            "quality_score": 0.45,
            "onex_compliance_score": 0.50,
            "violations": ["Missing base class", "No type hints"],
            "node_type": "effect",
        }

        await feedback_service.record_feedback(
            pattern_id="pattern_789",
            correlation_id="corr_003",
            validation_result=validation_result,
        )

        feedback = feedback_service.feedback_history[0]
        assert feedback.outcome == ValidationOutcome.FAILURE
        assert len(feedback.issues) == 2
        assert "Missing base class" in feedback.issues

    @pytest.mark.asyncio
    async def test_success_rate_calculation(self, feedback_service):
        """Test success rate calculation with mixed outcomes."""
        pattern_id = "pattern_test"

        # Record 7 successes and 3 failures
        for i in range(7):
            await feedback_service.record_feedback(
                pattern_id=pattern_id,
                correlation_id=f"corr_success_{i}",
                validation_result={
                    "is_valid": True,
                    "quality_score": 0.95,
                    "onex_compliance_score": 0.90,
                },
            )

        for i in range(3):
            await feedback_service.record_feedback(
                pattern_id=pattern_id,
                correlation_id=f"corr_fail_{i}",
                validation_result={
                    "is_valid": False,
                    "quality_score": 0.50,
                    "onex_compliance_score": 0.45,
                },
            )

        # Check success rate (7/10 = 0.7)
        success_rate = feedback_service.pattern_success_rates.get(pattern_id)
        assert success_rate == 0.7
        assert feedback_service.pattern_sample_counts.get(pattern_id) == 10

    @pytest.mark.asyncio
    async def test_confidence_scoring_with_sufficient_samples(self, feedback_service):
        """Test confidence scoring with sufficient samples (≥5)."""
        pattern_id = "pattern_confident"

        # Record 10 successful validations
        for i in range(10):
            await feedback_service.record_feedback(
                pattern_id=pattern_id,
                correlation_id=f"corr_{i}",
                validation_result={
                    "is_valid": True,
                    "quality_score": 0.90,
                    "onex_compliance_score": 0.88,
                },
            )

        confidence = await feedback_service.get_pattern_confidence(pattern_id)

        # With 10 samples and 100% success rate:
        # confidence = success_rate (1.0) * sample_factor (1.0) = 1.0
        assert confidence == 1.0

    @pytest.mark.asyncio
    async def test_confidence_scoring_with_insufficient_samples(self, feedback_service):
        """Test confidence penalty with insufficient samples (<5)."""
        pattern_id = "pattern_new"

        # Record only 2 successful validations
        for i in range(2):
            await feedback_service.record_feedback(
                pattern_id=pattern_id,
                correlation_id=f"corr_{i}",
                validation_result={
                    "is_valid": True,
                    "quality_score": 0.95,
                    "onex_compliance_score": 0.92,
                },
            )

        confidence = await feedback_service.get_pattern_confidence(pattern_id)

        # With 2 samples and 100% success rate:
        # confidence = success_rate (1.0) * sample_factor (2/5 = 0.4) = 0.4
        assert confidence == 0.4

    @pytest.mark.asyncio
    async def test_confidence_scoring_unknown_pattern(self, feedback_service):
        """Test confidence for unknown pattern (no feedback)."""
        confidence = await feedback_service.get_pattern_confidence("unknown_pattern")

        # Unknown patterns get default 0.5 success rate with 0 samples
        # confidence = 0.5 * (0/5) = 0.0
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_recommended_patterns(self, feedback_service):
        """Test getting recommended patterns with confidence threshold."""
        # Create patterns with different confidence levels
        patterns = [
            ("pattern_high", 10, 0.95),  # 10 samples, 95% success
            ("pattern_medium", 8, 0.80),  # 8 samples, 80% success
            (
                "pattern_low",
                3,
                0.90,
            ),  # 3 samples, 90% success (low confidence due to samples)
            ("pattern_fail", 10, 0.50),  # 10 samples, 50% success
        ]

        for pattern_id, num_samples, quality in patterns:
            for i in range(num_samples):
                is_success = i < int(
                    num_samples * quality / 0.95
                )  # Approximate success rate
                await feedback_service.record_feedback(
                    pattern_id=pattern_id,
                    correlation_id=f"{pattern_id}_corr_{i}",
                    validation_result={
                        "is_valid": is_success,
                        "quality_score": quality if is_success else 0.50,
                        "onex_compliance_score": 0.88,
                        "node_type": "effect",
                    },
                )

        # Get recommendations with min_confidence=0.7
        recommendations = await feedback_service.get_recommended_patterns(
            min_confidence=0.7
        )

        # Should only include high confidence patterns
        assert len(recommendations) > 0

        # All recommendations should meet threshold
        for rec in recommendations:
            assert rec["confidence"] >= 0.7

        # Should be sorted by confidence (descending)
        confidences = [r["confidence"] for r in recommendations]
        assert confidences == sorted(confidences, reverse=True)

    @pytest.mark.asyncio
    async def test_recommended_patterns_by_node_type(self, feedback_service):
        """Test filtering recommendations by node type."""
        # Create patterns for different node types
        for node_type in ["effect", "compute", "reducer"]:
            for i in range(5):
                await feedback_service.record_feedback(
                    pattern_id=f"pattern_{node_type}",
                    correlation_id=f"corr_{node_type}_{i}",
                    validation_result={
                        "is_valid": True,
                        "quality_score": 0.90,
                        "onex_compliance_score": 0.88,
                        "node_type": node_type,
                    },
                )

        # Get recommendations for effect nodes only
        recommendations = await feedback_service.get_recommended_patterns(
            node_type="effect",
            min_confidence=0.5,
        )

        # Should only include effect node patterns
        for rec in recommendations:
            pattern_feedbacks = [
                f
                for f in feedback_service.feedback_history
                if f.pattern_id == rec["pattern_id"]
            ]
            assert all(
                f.context.get("node_type") == "effect" for f in pattern_feedbacks
            )

    @pytest.mark.asyncio
    async def test_pattern_stats(self, feedback_service):
        """Test getting detailed pattern statistics."""
        pattern_id = "pattern_stats"

        # Record mixed outcomes
        outcomes_data = [
            (ValidationOutcome.SUCCESS, 0.95),
            (ValidationOutcome.SUCCESS, 0.92),
            (ValidationOutcome.PARTIAL_SUCCESS, 0.85),
            (ValidationOutcome.PARTIAL_SUCCESS, 0.80),
            (ValidationOutcome.FAILURE, 0.50),
        ]

        for i, (outcome_type, quality) in enumerate(outcomes_data):
            is_valid = outcome_type != ValidationOutcome.FAILURE
            await feedback_service.record_feedback(
                pattern_id=pattern_id,
                correlation_id=f"corr_{i}",
                validation_result={
                    "is_valid": is_valid,
                    "quality_score": quality,
                    "onex_compliance_score": 0.88,
                },
            )

        stats = feedback_service.get_pattern_stats(pattern_id)

        assert stats is not None
        assert stats["pattern_id"] == pattern_id
        assert stats["total_samples"] == 5
        assert stats["success_rate"] == 0.8  # 4 successes out of 5
        assert stats["outcome_counts"]["success"] == 2
        assert stats["outcome_counts"]["partial_success"] == 2
        assert stats["outcome_counts"]["failure"] == 1
        assert 0.8 <= stats["avg_quality_score"] <= 0.9
        assert stats["first_seen"] is not None
        assert stats["last_seen"] is not None

    @pytest.mark.asyncio
    async def test_pattern_stats_unknown_pattern(self, feedback_service):
        """Test getting stats for unknown pattern returns None."""
        stats = feedback_service.get_pattern_stats("unknown_pattern")
        assert stats is None

    def test_get_metrics(self, feedback_service):
        """Test getting overall service metrics."""
        metrics = feedback_service.get_metrics()

        assert "total_feedback_count" in metrics
        assert "total_patterns_tracked" in metrics
        assert "outcome_distribution" in metrics
        assert "avg_confidence" in metrics
        assert "high_confidence_patterns" in metrics

        # Initially empty
        assert metrics["total_feedback_count"] == 0
        assert metrics["total_patterns_tracked"] == 0

    @pytest.mark.asyncio
    async def test_metrics_after_feedback(self, feedback_service):
        """Test metrics after recording feedback."""
        # Record some feedback
        for i in range(5):
            await feedback_service.record_feedback(
                pattern_id=f"pattern_{i % 2}",  # 2 different patterns
                correlation_id=f"corr_{i}",
                validation_result={
                    "is_valid": True,
                    "quality_score": 0.90,
                    "onex_compliance_score": 0.88,
                },
            )

        metrics = feedback_service.get_metrics()

        assert metrics["total_feedback_count"] == 5
        assert metrics["total_patterns_tracked"] == 2
        assert metrics["outcome_distribution"]["success"] == 5

    def test_pattern_feedback_to_dict(self):
        """Test PatternFeedback serialization."""
        feedback = PatternFeedback(
            pattern_id="test_pattern",
            correlation_id="test_corr",
            outcome=ValidationOutcome.SUCCESS,
            quality_score=0.95,
            compliance_score=0.92,
            timestamp=datetime.now(timezone.utc),
            context={"node_type": "effect"},
            issues=[],
        )

        feedback_dict = feedback.to_dict()

        assert feedback_dict["pattern_id"] == "test_pattern"
        assert feedback_dict["correlation_id"] == "test_corr"
        assert feedback_dict["outcome"] == "success"
        assert feedback_dict["quality_score"] == 0.95
        assert feedback_dict["compliance_score"] == 0.92
        assert "timestamp" in feedback_dict
        assert feedback_dict["context"]["node_type"] == "effect"
        assert feedback_dict["issues"] == []


class TestValidationOutcomeClassification:
    """Test outcome classification logic."""

    @pytest.fixture
    def feedback_service(self):
        return PatternFeedbackService()

    def test_classify_success(self, feedback_service):
        """Test SUCCESS classification (valid + quality ≥ 0.9)."""
        result = {
            "is_valid": True,
            "quality_score": 0.95,
        }
        outcome = feedback_service._determine_outcome(result)
        assert outcome == ValidationOutcome.SUCCESS

    def test_classify_partial_success(self, feedback_service):
        """Test PARTIAL_SUCCESS classification (valid + quality < 0.9)."""
        result = {
            "is_valid": True,
            "quality_score": 0.75,
        }
        outcome = feedback_service._determine_outcome(result)
        assert outcome == ValidationOutcome.PARTIAL_SUCCESS

    def test_classify_failure(self, feedback_service):
        """Test FAILURE classification (not valid)."""
        result = {
            "is_valid": False,
            "quality_score": 0.50,
        }
        outcome = feedback_service._determine_outcome(result)
        assert outcome == ValidationOutcome.FAILURE

    def test_classify_edge_case_exact_threshold(self, feedback_service):
        """Test classification at exact threshold (0.9)."""
        result = {
            "is_valid": True,
            "quality_score": 0.90,
        }
        outcome = feedback_service._determine_outcome(result)
        assert outcome == ValidationOutcome.SUCCESS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
