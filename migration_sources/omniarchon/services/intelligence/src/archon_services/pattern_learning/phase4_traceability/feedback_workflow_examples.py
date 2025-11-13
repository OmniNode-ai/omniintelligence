"""
Feedback Loop Workflow Examples

Demonstrates usage of NodeFeedbackLoopOrchestrator for pattern improvement.

Author: Archon Intelligence Team
Date: 2025-10-02
Track: Track 3 Phase 4
"""

import asyncio
from uuid import uuid4

from src.archon_services.pattern_learning.phase4_traceability.node_feedback_loop_orchestrator import (
    ModelFeedbackLoopInput,
    NodeFeedbackLoopOrchestrator,
)

# ============================================================================
# Example 1: Basic Feedback Loop Execution
# ============================================================================


async def example_basic_feedback_loop():
    """
    Example: Basic feedback loop execution for pattern improvement.

    Demonstrates:
    - Creating input contract
    - Executing feedback loop
    - Interpreting results
    """
    print("\n" + "=" * 70)
    print("Example 1: Basic Feedback Loop Execution")
    print("=" * 70 + "\n")

    # Initialize orchestrator
    orchestrator = NodeFeedbackLoopOrchestrator()

    # Create input contract
    contract = ModelFeedbackLoopInput(
        operation="analyze_and_improve",
        pattern_id="pattern_api_debug_v1",
        feedback_type="performance",
        time_window_days=7,
        auto_apply_threshold=0.95,
        min_sample_size=30,
        significance_level=0.05,
        enable_ab_testing=True,
        correlation_id=uuid4(),
    )

    # Execute feedback loop
    print(f"Executing feedback loop for pattern: {contract.pattern_id}")
    print(f"Time window: {contract.time_window_days} days")
    print(f"Auto-apply threshold: {contract.auto_apply_threshold}")
    print()

    result = await orchestrator.execute_orchestration(contract)

    # Display results
    if result.success:
        print("✓ Feedback loop completed successfully\n")

        data = result.data
        print(f"Feedback collected: {data['feedback_collected']}")
        print(f"Executions analyzed: {data['executions_analyzed']}")
        print(f"Improvements identified: {data['improvements_identified']}")
        print(f"Improvements validated: {data['improvements_validated']}")
        print(f"Improvements applied: {data['improvements_applied']}")
        print(f"Improvements rejected: {data['improvements_rejected']}")
        print()

        if data["improvements_applied"] > 0:
            print(f"Performance improvement: {data['performance_delta']:.1%}")
            print(f"Confidence score: {data['confidence_score']:.2%}")

            if data.get("statistically_significant"):
                print(f"P-value: {data['p_value']:.4f} (significant!)")
            print()

            print("Baseline metrics:")
            for key, value in data["baseline_metrics"].items():
                print(f"  {key}: {value:.2f}")
            print()

            print("Improved metrics:")
            for key, value in data["improved_metrics"].items():
                print(f"  {key}: {value:.2f}")
            print()

        # Display workflow stages
        print("Workflow stages:")
        for stage, status in data["workflow_stages"].items():
            print(f"  {stage}: {status}")
        print()

        # Next review
        if data.get("next_review_date"):
            print(f"Next review scheduled: {data['next_review_date']}")

    else:
        print(f"✗ Feedback loop failed: {result.error}")

    print()


# ============================================================================
# Example 2: Quality-Focused Improvement
# ============================================================================


async def example_quality_improvement():
    """
    Example: Quality-focused pattern improvement.

    Demonstrates:
    - Targeting specific feedback types
    - Quality metrics analysis
    - Multi-dimensional improvement
    """
    print("\n" + "=" * 70)
    print("Example 2: Quality-Focused Improvement")
    print("=" * 70 + "\n")

    orchestrator = NodeFeedbackLoopOrchestrator()

    contract = ModelFeedbackLoopInput(
        operation="analyze_and_improve",
        pattern_id="pattern_code_generator_v1",
        feedback_type="quality",  # Focus on quality
        time_window_days=14,  # Longer window for quality analysis
        auto_apply_threshold=0.90,  # Slightly lower threshold
        min_sample_size=50,  # Larger sample for quality
        enable_ab_testing=True,
    )

    print(f"Analyzing quality for pattern: {contract.pattern_id}")
    print(f"Feedback type: {contract.feedback_type}")
    print(f"Sample size: {contract.min_sample_size}")
    print()

    result = await orchestrator.execute_orchestration(contract)

    if result.success:
        data = result.data

        print("✓ Quality analysis completed\n")
        print(f"Quality improvements identified: {data['improvements_identified']}")

        # Display improvement opportunities
        if data.get("improvement_opportunities"):
            print("\nImprovement opportunities:")
            for i, opp in enumerate(data["improvement_opportunities"], 1):
                print(f"  {i}. {opp['description']}")
                print(f"     Type: {opp['type']}")
                print(
                    f"     Expected improvement: {opp.get('expected_improvement', 'N/A')}"
                )
            print()


# ============================================================================
# Example 3: Conservative Validation (Manual Review)
# ============================================================================


async def example_conservative_validation():
    """
    Example: Conservative validation requiring manual review.

    Demonstrates:
    - Disabling auto-apply
    - High confidence requirements
    - Manual approval workflow
    """
    print("\n" + "=" * 70)
    print("Example 3: Conservative Validation (Manual Review)")
    print("=" * 70 + "\n")

    orchestrator = NodeFeedbackLoopOrchestrator()

    contract = ModelFeedbackLoopInput(
        operation="analyze_and_improve",
        pattern_id="pattern_critical_system_v1",
        feedback_type="all",
        time_window_days=30,  # Long observation period
        auto_apply_threshold=0.99,  # Very high threshold (effectively manual)
        min_sample_size=100,  # Large sample for confidence
        significance_level=0.01,  # Stricter significance
        enable_ab_testing=True,
    )

    print(f"Conservative validation for: {contract.pattern_id}")
    print(
        f"Auto-apply threshold: {contract.auto_apply_threshold} (requires manual review)"
    )
    print(f"Significance level: {contract.significance_level} (stricter)")
    print()

    result = await orchestrator.execute_orchestration(contract)

    if result.success:
        data = result.data

        print("✓ Validation completed\n")

        # Show what needs manual review
        validated_count = data["improvements_validated"]
        applied_count = data["improvements_applied"]
        pending_review = validated_count - applied_count

        print(f"Improvements requiring manual review: {pending_review}")

        if data.get("validation_results"):
            print("\nValidation results for manual review:")
            for i, val_result in enumerate(data["validation_results"], 1):
                print(f"\n  Improvement {i}:")
                print(f"    P-value: {val_result.get('p_value', 'N/A')}")
                print(f"    Confidence: {val_result.get('confidence', 'N/A'):.2%}")
                print(
                    f"    Significant: {'Yes' if val_result.get('significant') else 'No'}"
                )

                # Recommendation
                if val_result.get("confidence", 0) >= 0.95:
                    print(
                        "    Recommendation: APPROVE (high confidence, statistically significant)"
                    )
                elif val_result.get("confidence", 0) >= 0.85:
                    print(
                        "    Recommendation: REVIEW (moderate confidence, needs analysis)"
                    )
                else:
                    print("    Recommendation: REJECT (low confidence)")


# ============================================================================
# Example 4: Rapid Iteration (Relaxed Validation)
# ============================================================================


async def example_rapid_iteration():
    """
    Example: Rapid iteration with relaxed validation.

    Demonstrates:
    - Lower thresholds for faster iteration
    - Shorter time windows
    - Aggressive improvement application
    """
    print("\n" + "=" * 70)
    print("Example 4: Rapid Iteration (Relaxed Validation)")
    print("=" * 70 + "\n")

    orchestrator = NodeFeedbackLoopOrchestrator()

    contract = ModelFeedbackLoopInput(
        operation="analyze_and_improve",
        pattern_id="pattern_experimental_v1",
        feedback_type="performance",
        time_window_days=3,  # Short window for rapid feedback
        auto_apply_threshold=0.85,  # Lower threshold
        min_sample_size=20,  # Smaller sample
        significance_level=0.10,  # Relaxed significance
        enable_ab_testing=True,
    )

    print(f"Rapid iteration for: {contract.pattern_id}")
    print(f"Time window: {contract.time_window_days} days (short)")
    print(f"Auto-apply threshold: {contract.auto_apply_threshold} (relaxed)")
    print()

    result = await orchestrator.execute_orchestration(contract)

    if result.success:
        data = result.data

        print("✓ Rapid iteration completed\n")
        print(f"Applied {data['improvements_applied']} improvements quickly")

        if data["improvements_applied"] > 0:
            print(
                f"\nPerformance gain: {data['performance_delta']:.1%} (fast iteration)"
            )
        else:
            print("\nNo improvements applied (insufficient confidence)")


# ============================================================================
# Example 5: Performance Monitoring Without Changes
# ============================================================================


async def example_monitoring_only():
    """
    Example: Monitor pattern performance without applying changes.

    Demonstrates:
    - Disabling A/B testing
    - Analysis-only mode
    - Performance tracking
    """
    print("\n" + "=" * 70)
    print("Example 5: Performance Monitoring (No Changes)")
    print("=" * 70 + "\n")

    orchestrator = NodeFeedbackLoopOrchestrator()

    contract = ModelFeedbackLoopInput(
        operation="analyze_and_improve",
        pattern_id="pattern_stable_v1",
        feedback_type="all",
        time_window_days=30,
        auto_apply_threshold=1.0,  # Never auto-apply
        enable_ab_testing=False,  # Disable testing
    )

    print(f"Monitoring pattern: {contract.pattern_id}")
    print("Mode: Analysis only (no changes)")
    print()

    result = await orchestrator.execute_orchestration(contract)

    if result.success:
        data = result.data

        print("✓ Monitoring completed\n")

        # Display metrics
        print("Performance metrics:")
        for key, value in data.get("baseline_metrics", {}).items():
            print(f"  {key}: {value:.2f}")
        print()

        # Warnings and recommendations
        if data.get("warnings"):
            print("Warnings:")
            for warning in data["warnings"]:
                print(f"  - {warning}")
            print()

        # Improvement opportunities (for information only)
        if data.get("improvement_opportunities"):
            print(
                f"Improvement opportunities identified: {len(data['improvement_opportunities'])}"
            )
            print("(Not applied - monitoring mode)")


# ============================================================================
# Example 6: Full Workflow with Multiple Patterns
# ============================================================================


async def example_batch_improvement():
    """
    Example: Batch improvement across multiple patterns.

    Demonstrates:
    - Processing multiple patterns
    - Aggregating results
    - Prioritizing improvements
    """
    print("\n" + "=" * 70)
    print("Example 6: Batch Improvement Across Patterns")
    print("=" * 70 + "\n")

    orchestrator = NodeFeedbackLoopOrchestrator()

    patterns = [
        "pattern_api_debug_v1",
        "pattern_code_generator_v1",
        "pattern_test_writer_v1",
    ]

    print(f"Processing {len(patterns)} patterns for improvement\n")

    results = []

    for pattern_id in patterns:
        print(f"Analyzing {pattern_id}...")

        contract = ModelFeedbackLoopInput(
            pattern_id=pattern_id,
            feedback_type="all",
            time_window_days=7,
            auto_apply_threshold=0.95,
        )

        result = await orchestrator.execute_orchestration(contract)
        results.append((pattern_id, result))

    # Aggregate results
    print("\n" + "=" * 70)
    print("Batch Results Summary")
    print("=" * 70 + "\n")

    total_improvements = 0
    total_performance_gain = 0.0

    for pattern_id, result in results:
        if result.success:
            data = result.data
            applied = data["improvements_applied"]
            delta = data.get("performance_delta", 0.0)

            total_improvements += applied
            total_performance_gain += delta

            print(f"✓ {pattern_id}")
            print(f"  Improvements: {applied}")
            print(f"  Performance gain: {delta:.1%}")
        else:
            print(f"✗ {pattern_id}: {result.error}")

    print()
    print(f"Total improvements applied: {total_improvements}")
    print(f"Average performance gain: {total_performance_gain / len(patterns):.1%}")


# ============================================================================
# Main Entry Point
# ============================================================================


async def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("Feedback Loop Orchestrator - Usage Examples")
    print("=" * 70)

    # Run examples
    await example_basic_feedback_loop()
    await example_quality_improvement()
    await example_conservative_validation()
    await example_rapid_iteration()
    await example_monitoring_only()
    await example_batch_improvement()

    print("\n" + "=" * 70)
    print("All examples completed!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
