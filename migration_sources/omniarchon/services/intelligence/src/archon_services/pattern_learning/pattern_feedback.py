"""
Pattern Feedback Service

Tracks validation outcomes for patterns and adjusts confidence scores based on
historical success rates. Implements feedback loop for autonomous pattern learning.

Created: 2025-10-15 (MVP Phase 5A)
Purpose: Track pattern validation outcomes and provide confidence-based recommendations
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ValidationOutcome(str, Enum):
    """Validation outcome types for pattern application."""

    SUCCESS = "success"  # Validation passed with high quality (≥0.9)
    PARTIAL_SUCCESS = "partial_success"  # Validation passed but lower quality
    FAILURE = "failure"  # Validation failed
    ERROR = "error"  # Error during validation


@dataclass
class PatternFeedback:
    """
    Feedback on pattern application outcome.

    Tracks validation results and quality metrics for each pattern usage.
    """

    pattern_id: str
    correlation_id: str
    outcome: ValidationOutcome
    quality_score: float
    compliance_score: float
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/serialization."""
        return {
            "pattern_id": self.pattern_id,
            "correlation_id": self.correlation_id,
            "outcome": self.outcome.value,
            "quality_score": self.quality_score,
            "compliance_score": self.compliance_score,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context,
            "issues": self.issues,
        }


class PatternFeedbackService:
    """
    Track and analyze pattern application outcomes.

    Provides confidence scoring based on historical success rates and sample sizes.
    Minimum of 5 samples required for high confidence scoring.
    """

    def __init__(self):
        """Initialize feedback service with empty tracking data."""
        self.feedback_history: List[PatternFeedback] = []
        self.pattern_success_rates: Dict[str, float] = {}
        self.pattern_sample_counts: Dict[str, int] = {}

        logger.info("PatternFeedbackService initialized")

    async def record_feedback(
        self, pattern_id: str, correlation_id: str, validation_result: Dict[str, Any]
    ) -> None:
        """
        Record feedback from validation result.

        Args:
            pattern_id: ID of pattern that was applied
            correlation_id: Correlation ID for tracing
            validation_result: Validation result dictionary containing:
                - is_valid: bool
                - quality_score: float
                - onex_compliance_score: float
                - violations: List[str]
                - node_type: str (optional)
        """
        try:
            outcome = self._determine_outcome(validation_result)

            feedback = PatternFeedback(
                pattern_id=pattern_id,
                correlation_id=correlation_id,
                outcome=outcome,
                quality_score=validation_result.get("quality_score", 0.0),
                compliance_score=validation_result.get("onex_compliance_score", 0.0),
                timestamp=datetime.now(timezone.utc),
                context={
                    "node_type": validation_result.get("node_type"),
                    "is_valid": validation_result.get("is_valid", False),
                },
                issues=validation_result.get("violations", []),
            )

            self.feedback_history.append(feedback)
            await self._update_success_rates(pattern_id, outcome)

            logger.info(
                f"Recorded feedback for pattern {pattern_id}: "
                f"outcome={outcome.value}, quality={feedback.quality_score:.2f}, "
                f"compliance={feedback.compliance_score:.2f}"
            )

        except Exception as e:
            logger.error(
                f"Failed to record feedback for pattern {pattern_id}: {e}",
                exc_info=True,
            )

    def _determine_outcome(
        self, validation_result: Dict[str, Any]
    ) -> ValidationOutcome:
        """
        Determine outcome classification from validation result.

        Args:
            validation_result: Validation result dictionary

        Returns:
            ValidationOutcome enum value
        """
        # Check if validation passed
        if not validation_result.get("is_valid", False):
            return ValidationOutcome.FAILURE

        # Check quality score for success level
        quality = validation_result.get("quality_score", 0.0)

        if quality >= 0.9:
            return ValidationOutcome.SUCCESS
        else:
            return ValidationOutcome.PARTIAL_SUCCESS

    async def _update_success_rates(
        self, pattern_id: str, outcome: ValidationOutcome
    ) -> None:
        """
        Update success rate statistics for pattern.

        Args:
            pattern_id: Pattern identifier
            outcome: Outcome of this validation
        """
        try:
            # Get all feedback for this pattern
            pattern_feedbacks = [
                f for f in self.feedback_history if f.pattern_id == pattern_id
            ]

            if not pattern_feedbacks:
                return

            # Count successes (both SUCCESS and PARTIAL_SUCCESS)
            successes = sum(
                1
                for f in pattern_feedbacks
                if f.outcome
                in [ValidationOutcome.SUCCESS, ValidationOutcome.PARTIAL_SUCCESS]
            )

            # Calculate success rate
            total = len(pattern_feedbacks)
            success_rate = successes / total if total > 0 else 0.0

            # Update tracking
            self.pattern_success_rates[pattern_id] = success_rate
            self.pattern_sample_counts[pattern_id] = total

            logger.debug(
                f"Updated success rate for {pattern_id}: "
                f"{success_rate:.2%} ({successes}/{total})"
            )

        except Exception as e:
            logger.error(f"Failed to update success rates for {pattern_id}: {e}")

    async def get_pattern_confidence(self, pattern_id: str) -> float:
        """
        Get confidence score for pattern based on feedback history.

        Confidence is adjusted by sample size - minimum 5 samples required
        for full confidence. Score is: success_rate * sample_factor

        Args:
            pattern_id: Pattern identifier

        Returns:
            Confidence score (0.0-1.0)
        """
        # Get success rate (default to 0.5 if unknown)
        success_rate = self.pattern_success_rates.get(pattern_id, 0.5)

        # Get sample size
        sample_size = self.pattern_sample_counts.get(pattern_id, 0)

        # Calculate sample factor (minimum 5 samples for high confidence)
        # This creates a penalty for patterns with few samples
        sample_factor = min(sample_size / 5.0, 1.0)

        # Final confidence = success_rate * sample_factor
        confidence = success_rate * sample_factor

        return confidence

    async def get_recommended_patterns(
        self, node_type: Optional[str] = None, min_confidence: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Get recommended patterns with high confidence scores.

        Args:
            node_type: Optional filter by node type
            min_confidence: Minimum confidence threshold (default 0.7)

        Returns:
            List of pattern recommendations sorted by confidence, each containing:
            - pattern_id: str
            - success_rate: float
            - confidence: float
            - sample_size: int
            - avg_quality_score: float
            - avg_compliance_score: float
        """
        recommendations = []

        for pattern_id, success_rate in self.pattern_success_rates.items():
            # Get confidence score
            confidence = await self.get_pattern_confidence(pattern_id)

            # Filter by minimum confidence
            if confidence < min_confidence:
                continue

            # Get pattern feedback for this pattern
            pattern_feedbacks = [
                f for f in self.feedback_history if f.pattern_id == pattern_id
            ]

            # Filter by node type if specified
            if node_type:
                pattern_feedbacks = [
                    f
                    for f in pattern_feedbacks
                    if f.context.get("node_type") == node_type
                ]

            if not pattern_feedbacks:
                continue

            # Calculate average quality and compliance scores
            avg_quality = sum(f.quality_score for f in pattern_feedbacks) / len(
                pattern_feedbacks
            )
            avg_compliance = sum(f.compliance_score for f in pattern_feedbacks) / len(
                pattern_feedbacks
            )

            recommendations.append(
                {
                    "pattern_id": pattern_id,
                    "success_rate": success_rate,
                    "confidence": confidence,
                    "sample_size": len(pattern_feedbacks),
                    "avg_quality_score": avg_quality,
                    "avg_compliance_score": avg_compliance,
                }
            )

        # Sort by confidence (highest first)
        recommendations.sort(key=lambda x: x["confidence"], reverse=True)

        logger.info(
            f"Generated {len(recommendations)} pattern recommendations "
            f"(min_confidence={min_confidence:.2f}, node_type={node_type})"
        )

        return recommendations

    def get_pattern_stats(self, pattern_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed statistics for a specific pattern.

        Args:
            pattern_id: Pattern identifier

        Returns:
            Statistics dictionary or None if pattern not found
        """
        pattern_feedbacks = [
            f for f in self.feedback_history if f.pattern_id == pattern_id
        ]

        if not pattern_feedbacks:
            return None

        # Count outcomes
        outcome_counts = {
            ValidationOutcome.SUCCESS: 0,
            ValidationOutcome.PARTIAL_SUCCESS: 0,
            ValidationOutcome.FAILURE: 0,
            ValidationOutcome.ERROR: 0,
        }

        for feedback in pattern_feedbacks:
            outcome_counts[feedback.outcome] += 1

        # Calculate averages
        avg_quality = sum(f.quality_score for f in pattern_feedbacks) / len(
            pattern_feedbacks
        )
        avg_compliance = sum(f.compliance_score for f in pattern_feedbacks) / len(
            pattern_feedbacks
        )

        return {
            "pattern_id": pattern_id,
            "total_samples": len(pattern_feedbacks),
            "success_rate": self.pattern_success_rates.get(pattern_id, 0.0),
            "confidence": self.pattern_success_rates.get(pattern_id, 0.5)
            * min(len(pattern_feedbacks) / 5.0, 1.0),
            "outcome_counts": {k.value: v for k, v in outcome_counts.items()},
            "avg_quality_score": avg_quality,
            "avg_compliance_score": avg_compliance,
            "first_seen": min(f.timestamp for f in pattern_feedbacks).isoformat(),
            "last_seen": max(f.timestamp for f in pattern_feedbacks).isoformat(),
        }

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get overall feedback service metrics.

        Returns:
            Metrics dictionary with service statistics
        """
        total_feedback = len(self.feedback_history)
        total_patterns = len(self.pattern_success_rates)

        # Calculate outcome distribution
        outcome_counts = {outcome.value: 0 for outcome in ValidationOutcome}
        for feedback in self.feedback_history:
            outcome_counts[feedback.outcome.value] += 1

        # Calculate average confidence across all patterns
        if self.pattern_success_rates:
            confidences = [
                self.pattern_success_rates[pid]
                * min(self.pattern_sample_counts.get(pid, 0) / 5.0, 1.0)
                for pid in self.pattern_success_rates
            ]
            avg_confidence = sum(confidences) / len(confidences)
        else:
            avg_confidence = 0.0

        # Find high confidence patterns (≥0.8)
        high_confidence_patterns = sum(
            1
            for pid in self.pattern_success_rates
            if (
                self.pattern_success_rates[pid]
                * min(self.pattern_sample_counts.get(pid, 0) / 5.0, 1.0)
            )
            >= 0.8
        )

        return {
            "total_feedback_count": total_feedback,
            "total_patterns_tracked": total_patterns,
            "outcome_distribution": outcome_counts,
            "avg_confidence": avg_confidence,
            "high_confidence_patterns": high_confidence_patterns,
        }
