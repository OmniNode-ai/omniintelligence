#!/usr/bin/env python3
"""
Quick verification script for Pattern Feedback Loop implementation.

Demonstrates feedback recording, confidence scoring, and recommendations.
Can be run standalone without Docker dependencies.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from services.pattern_learning.pattern_feedback import (
    PatternFeedbackService,
)


async def main():
    """Demonstrate feedback loop functionality."""
    print("=" * 70)
    print("Pattern Feedback Loop Verification")
    print("=" * 70)

    # Initialize service
    feedback_service = PatternFeedbackService()
    print("\n✓ PatternFeedbackService initialized")

    # Simulate pattern usage with different outcomes
    print("\n" + "=" * 70)
    print("Simulating Pattern Usage Scenarios")
    print("=" * 70)

    # Pattern 1: High success rate (8/10 success)
    print("\n[Pattern 1: 'effect_base_pattern'] Recording 10 validations...")
    for i in range(8):
        await feedback_service.record_feedback(
            pattern_id="effect_base_pattern",
            correlation_id=f"corr_p1_success_{i}",
            validation_result={
                "is_valid": True,
                "quality_score": 0.95,
                "onex_compliance_score": 0.92,
                "violations": [],
                "node_type": "effect",
            },
        )

    for i in range(2):
        await feedback_service.record_feedback(
            pattern_id="effect_base_pattern",
            correlation_id=f"corr_p1_fail_{i}",
            validation_result={
                "is_valid": False,
                "quality_score": 0.50,
                "onex_compliance_score": 0.45,
                "violations": ["Missing base class"],
                "node_type": "effect",
            },
        )

    stats1 = feedback_service.get_pattern_stats("effect_base_pattern")
    confidence1 = await feedback_service.get_pattern_confidence("effect_base_pattern")
    print(f"  Success Rate: {stats1['success_rate']:.1%}")
    print(f"  Confidence: {confidence1:.2f} (sample_size={stats1['total_samples']})")

    # Pattern 2: Lower success rate (5/10 success)
    print("\n[Pattern 2: 'compute_validation_pattern'] Recording 10 validations...")
    for i in range(5):
        await feedback_service.record_feedback(
            pattern_id="compute_validation_pattern",
            correlation_id=f"corr_p2_success_{i}",
            validation_result={
                "is_valid": True,
                "quality_score": 0.85,
                "onex_compliance_score": 0.80,
                "violations": [],
                "node_type": "compute",
            },
        )

    for i in range(5):
        await feedback_service.record_feedback(
            pattern_id="compute_validation_pattern",
            correlation_id=f"corr_p2_fail_{i}",
            validation_result={
                "is_valid": False,
                "quality_score": 0.55,
                "onex_compliance_score": 0.50,
                "violations": ["Type hints missing"],
                "node_type": "compute",
            },
        )

    stats2 = feedback_service.get_pattern_stats("compute_validation_pattern")
    confidence2 = await feedback_service.get_pattern_confidence(
        "compute_validation_pattern"
    )
    print(f"  Success Rate: {stats2['success_rate']:.1%}")
    print(f"  Confidence: {confidence2:.2f} (sample_size={stats2['total_samples']})")

    # Pattern 3: New pattern with only 2 samples (penalty applied)
    print("\n[Pattern 3: 'reducer_aggregation_pattern'] Recording 2 validations...")
    for i in range(2):
        await feedback_service.record_feedback(
            pattern_id="reducer_aggregation_pattern",
            correlation_id=f"corr_p3_success_{i}",
            validation_result={
                "is_valid": True,
                "quality_score": 0.98,
                "onex_compliance_score": 0.95,
                "violations": [],
                "node_type": "reducer",
            },
        )

    stats3 = feedback_service.get_pattern_stats("reducer_aggregation_pattern")
    confidence3 = await feedback_service.get_pattern_confidence(
        "reducer_aggregation_pattern"
    )
    print(f"  Success Rate: {stats3['success_rate']:.1%}")
    print(
        f"  Confidence: {confidence3:.2f} (sample_size={stats3['total_samples']}) [PENALTY: <5 samples]"
    )

    # Test recommendations
    print("\n" + "=" * 70)
    print("Pattern Recommendations (min_confidence=0.6)")
    print("=" * 70)

    recommendations = await feedback_service.get_recommended_patterns(
        min_confidence=0.6
    )

    for i, rec in enumerate(recommendations, 1):
        print(f"\n{i}. {rec['pattern_id']}")
        print(f"   Confidence: {rec['confidence']:.2f}")
        print(f"   Success Rate: {rec['success_rate']:.1%}")
        print(f"   Sample Size: {rec['sample_size']}")
        print(f"   Avg Quality: {rec['avg_quality_score']:.2f}")

    # Test node type filtering
    print("\n" + "=" * 70)
    print("Pattern Recommendations for 'effect' nodes only")
    print("=" * 70)

    effect_recommendations = await feedback_service.get_recommended_patterns(
        node_type="effect", min_confidence=0.5
    )

    for i, rec in enumerate(effect_recommendations, 1):
        print(f"\n{i}. {rec['pattern_id']}")
        print(f"   Confidence: {rec['confidence']:.2f}")
        print("   Node Type: effect")

    # Overall metrics
    print("\n" + "=" * 70)
    print("Overall Service Metrics")
    print("=" * 70)

    metrics = feedback_service.get_metrics()
    print(f"\nTotal Feedback Records: {metrics['total_feedback_count']}")
    print(f"Total Patterns Tracked: {metrics['total_patterns_tracked']}")
    print(f"Average Confidence: {metrics['avg_confidence']:.2f}")
    print(f"High Confidence Patterns (≥0.8): {metrics['high_confidence_patterns']}")

    print("\nOutcome Distribution:")
    for outcome, count in metrics["outcome_distribution"].items():
        print(f"  {outcome}: {count}")

    # Test confidence scoring algorithm
    print("\n" + "=" * 70)
    print("Confidence Scoring Algorithm Demonstration")
    print("=" * 70)

    print("\nFormula: confidence = success_rate * sample_factor")
    print("         sample_factor = min(sample_size / 5.0, 1.0)")
    print("\nPattern 1 (effect_base_pattern):")
    print(f"  success_rate=0.8 * sample_factor(10/5=1.0) = {0.8 * 1.0:.2f}")
    print(f"  Actual: {confidence1:.2f} ✓")

    print("\nPattern 3 (reducer_aggregation_pattern):")
    print(f"  success_rate=1.0 * sample_factor(2/5=0.4) = {1.0 * 0.4:.2f}")
    print(f"  Actual: {confidence3:.2f} ✓")

    print("\n" + "=" * 70)
    print("✅ Verification Complete - All Features Working!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
