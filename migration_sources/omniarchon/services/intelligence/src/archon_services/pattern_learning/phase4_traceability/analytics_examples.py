"""
Usage Analytics Reducer - Examples

Demonstrates how to use the ONEX Usage Analytics Reducer for
pattern usage analysis and trend detection.

ONEX Pattern: Reducer node usage examples
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from src.archon_services.pattern_learning.phase4_traceability.model_contract_usage_analytics import (
    AnalyticsGranularity,
    ModelUsageAnalyticsInput,
    TimeWindowType,
)
from src.archon_services.pattern_learning.phase4_traceability.node_usage_analytics_reducer import (
    NodeUsageAnalyticsReducer,
)

# ============================================================================
# Example 1: Basic Usage Analytics
# ============================================================================


# NOTE: correlation_id support enabled for tracing
async def example_basic_analytics():
    """
    Example: Compute basic usage analytics for a pattern.

    Use Case: Track how often a debugging pattern is being used
    """
    print("Example 1: Basic Usage Analytics")
    print("=" * 60)

    # Initialize reducer
    reducer = NodeUsageAnalyticsReducer()

    # Create sample execution data (would come from database in production)
    now = datetime.now(timezone.utc)
    execution_data = []

    for i in range(50):
        execution_data.append(
            {
                "execution_id": str(uuid4()),
                "timestamp": now - timedelta(hours=48 - i),
                "success": i % 5 != 0,  # 80% success rate
                "execution_time_ms": 200 + (i % 30) * 10,
                "quality_score": 0.75 + (i % 25) * 0.01,
                "context_type": "debugging",
                "agent": f"agent-{i % 3}",
                "project": "my-project",
            }
        )

    # Create input contract
    pattern_id = uuid4()
    contract = ModelUsageAnalyticsInput(
        pattern_id=pattern_id,
        time_window_start=now - timedelta(days=2),
        time_window_end=now,
        time_window_type=TimeWindowType.DAILY,
        granularity=AnalyticsGranularity.SUMMARY,
        execution_data=execution_data,
    )

    # Compute analytics
    result = await reducer.execute_reduction(contract)

    # Display results
    print(f"Pattern ID: {result.pattern_id}")
    print(f"Total Executions: {result.usage_metrics.total_executions}")
    print(f"Executions/Day: {result.usage_metrics.executions_per_day:.2f}")
    print(f"Success Rate: {result.success_metrics.success_rate:.1%}")
    print(f"Avg Quality Score: {result.success_metrics.avg_quality_score:.2f}")
    print(f"Computation Time: {result.computation_time_ms:.2f}ms")
    print()


# ============================================================================
# Example 2: Performance Analysis
# ============================================================================


async def example_performance_analysis():
    """
    Example: Analyze pattern performance metrics.

    Use Case: Identify slow patterns that need optimization
    """
    print("Example 2: Performance Analysis")
    print("=" * 60)

    reducer = NodeUsageAnalyticsReducer()
    now = datetime.now(timezone.utc)

    # Create execution data with varying performance
    execution_data = []
    for i in range(100):
        # Simulate performance degradation over time
        base_time = 150
        degradation = (i // 10) * 50  # Increases every 10 executions

        execution_data.append(
            {
                "execution_id": str(uuid4()),
                "timestamp": now - timedelta(hours=100 - i),
                "success": True,
                "execution_time_ms": base_time + degradation + (i % 10) * 5,
                "quality_score": 0.85,
            }
        )

    contract = ModelUsageAnalyticsInput(
        pattern_id=uuid4(),
        time_window_start=now - timedelta(days=5),
        time_window_end=now,
        include_performance=True,
        execution_data=execution_data,
    )

    result = await reducer.execute_reduction(contract)

    # Display performance metrics
    perf = result.performance_metrics
    print("Performance Percentiles:")
    print(f"  P50 (Median): {perf.p50_execution_time_ms:.2f}ms")
    print(f"  P95: {perf.p95_execution_time_ms:.2f}ms")
    print(f"  P99: {perf.p99_execution_time_ms:.2f}ms")
    print(f"  Min: {perf.min_execution_time_ms:.2f}ms")
    print(f"  Max: {perf.max_execution_time_ms:.2f}ms")
    print(f"  Avg: {perf.avg_execution_time_ms:.2f}ms")
    print(f"  Std Dev: {perf.std_dev_ms:.2f}ms")
    print()

    # Performance health check
    if perf.p95_execution_time_ms > 500:
        print("⚠️  WARNING: P95 latency exceeds 500ms - optimization needed")
    else:
        print("✅ Performance is healthy")
    print()


# ============================================================================
# Example 3: Trend Detection
# ============================================================================


async def example_trend_detection():
    """
    Example: Detect usage trends over time.

    Use Case: Identify growing/declining patterns for resource planning
    """
    print("Example 3: Trend Detection")
    print("=" * 60)

    reducer = NodeUsageAnalyticsReducer()
    now = datetime.now(timezone.utc)

    # Create growing usage pattern
    execution_data = []
    for week in range(4):
        # More executions each week
        executions_per_week = 10 + week * 5

        for i in range(executions_per_week):
            execution_data.append(
                {
                    "execution_id": str(uuid4()),
                    "timestamp": now - timedelta(weeks=3 - week, days=i % 7),
                    "success": True,
                    "execution_time_ms": 200,
                    "agent": f"user-{i % 5}",
                }
            )

    contract = ModelUsageAnalyticsInput(
        pattern_id=uuid4(),
        time_window_start=now - timedelta(weeks=4),
        time_window_end=now,
        time_window_type=TimeWindowType.MONTHLY,
        include_trends=True,
        execution_data=execution_data,
    )

    result = await reducer.execute_reduction(contract)

    # Display trend analysis
    trend = result.trend_analysis
    print(f"Trend Type: {trend.trend_type.value}")
    print(f"Velocity: {trend.velocity:.2f} executions/period")
    print(f"Acceleration: {trend.acceleration:.2f}")
    print(f"Growth: {trend.growth_percentage:+.1f}%")
    print(f"Adoption Rate: {trend.adoption_rate:.2f} new users/week")
    print(f"Retention Rate: {trend.retention_rate:.1%}")
    print(f"Confidence: {trend.confidence_score:.1%}")
    print()

    # Strategic recommendations
    if trend.trend_type.value == "growing":
        print("📈 Pattern is GROWING - consider investing in optimization")
    elif trend.trend_type.value == "declining":
        print("📉 Pattern is DECLINING - investigate why usage is dropping")
    elif trend.trend_type.value == "stable":
        print("📊 Pattern is STABLE - maintain current support level")
    print()


# ============================================================================
# Example 4: Context Distribution Analysis
# ============================================================================


async def example_context_distribution():
    """
    Example: Analyze how patterns are used across different contexts.

    Use Case: Understand which teams/projects/agents use which patterns
    """
    print("Example 4: Context Distribution Analysis")
    print("=" * 60)

    reducer = NodeUsageAnalyticsReducer()
    now = datetime.now(timezone.utc)

    # Create execution data across multiple contexts
    execution_data = []
    contexts = ["debugging", "api_design", "performance", "testing"]
    agents = ["agent-frontend", "agent-backend", "agent-devops"]
    projects = ["project-alpha", "project-beta", "project-gamma"]

    for i in range(120):
        execution_data.append(
            {
                "execution_id": str(uuid4()),
                "timestamp": now - timedelta(hours=120 - i),
                "success": True,
                "execution_time_ms": 250,
                "context_type": contexts[i % len(contexts)],
                "agent": agents[i % len(agents)],
                "project": projects[i % len(projects)],
                "file_path": f"src/module_{i % 10}.py",
            }
        )

    contract = ModelUsageAnalyticsInput(
        pattern_id=uuid4(),
        time_window_start=now - timedelta(days=5),
        time_window_end=now,
        include_distribution=True,
        execution_data=execution_data,
    )

    result = await reducer.execute_reduction(contract)

    # Display context distribution
    dist = result.context_distribution
    print("Distribution by Context Type:")
    for context, count in sorted(
        dist.by_context_type.items(), key=lambda x: x[1], reverse=True
    ):
        percentage = (count / result.total_data_points) * 100
        print(f"  {context}: {count} ({percentage:.1f}%)")
    print()

    print("Distribution by Agent:")
    for agent, count in sorted(dist.by_agent.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / result.total_data_points) * 100
        print(f"  {agent}: {count} ({percentage:.1f}%)")
    print()

    print("Distribution by Project:")
    for project, count in sorted(
        dist.by_project.items(), key=lambda x: x[1], reverse=True
    ):
        percentage = (count / result.total_data_points) * 100
        print(f"  {project}: {count} ({percentage:.1f}%)")
    print()


# ============================================================================
# Example 5: Comprehensive Analytics Dashboard
# ============================================================================


async def example_comprehensive_dashboard():
    """
    Example: Generate comprehensive analytics for dashboard display.

    Use Case: Full pattern health dashboard with all metrics
    """
    print("Example 5: Comprehensive Analytics Dashboard")
    print("=" * 60)

    reducer = NodeUsageAnalyticsReducer()
    now = datetime.now(timezone.utc)

    # Create realistic execution data
    execution_data = []
    for i in range(200):
        day = i // 20  # 20 executions per day for 10 days

        execution_data.append(
            {
                "execution_id": str(uuid4()),
                "timestamp": now - timedelta(days=9 - day, hours=i % 24),
                "success": i % 8 != 0,  # 87.5% success rate
                "execution_time_ms": 180 + (i % 40) * 8,
                "quality_score": 0.78 + (i % 22) * 0.01,
                "quality_gates_passed": i % 12 != 0,
                "timeout": i % 50 == 0,
                "context_type": ["debugging", "api", "perf"][i % 3],
                "agent": f"agent-{i % 4}",
                "project": f"project-{i % 2}",
                "file_path": f"src/file_{i % 15}.py",
            }
        )

    contract = ModelUsageAnalyticsInput(
        pattern_id=uuid4(),
        time_window_start=now - timedelta(days=10),
        time_window_end=now,
        time_window_type=TimeWindowType.WEEKLY,
        granularity=AnalyticsGranularity.COMPREHENSIVE,
        include_performance=True,
        include_trends=True,
        include_distribution=True,
        execution_data=execution_data,
    )

    result = await reducer.execute_reduction(contract)

    # Generate dashboard-style output
    print("📊 PATTERN ANALYTICS DASHBOARD")
    print("=" * 60)

    # Summary metrics
    print("\n📈 USAGE SUMMARY")
    print(f"Total Executions: {result.usage_metrics.total_executions}")
    print(f"Executions/Day: {result.usage_metrics.executions_per_day:.1f}")
    print(f"Unique Contexts: {result.usage_metrics.unique_contexts}")
    print(f"Unique Users: {result.usage_metrics.unique_users}")
    print(f"Peak Daily Usage: {result.usage_metrics.peak_daily_usage}")

    # Success metrics
    print("\n✅ SUCCESS METRICS")
    print(f"Success Rate: {result.success_metrics.success_rate:.1%}")
    print(f"Error Rate: {result.success_metrics.error_rate:.1%}")
    print(f"Timeout Count: {result.success_metrics.timeout_count}")
    print(f"Quality Gate Failures: {result.success_metrics.quality_gate_failures}")
    print(f"Avg Quality Score: {result.success_metrics.avg_quality_score:.2f}")

    # Performance metrics
    print("\n⚡ PERFORMANCE METRICS")
    perf = result.performance_metrics
    print(f"P50 Latency: {perf.p50_execution_time_ms:.2f}ms")
    print(f"P95 Latency: {perf.p95_execution_time_ms:.2f}ms")
    print(f"P99 Latency: {perf.p99_execution_time_ms:.2f}ms")
    print(f"Avg Latency: {perf.avg_execution_time_ms:.2f}ms")

    # Trend analysis
    print("\n📊 TREND ANALYSIS")
    trend = result.trend_analysis
    print(f"Trend: {trend.trend_type.value.upper()}")
    print(f"Velocity: {trend.velocity:+.2f} executions/period")
    print(f"Growth: {trend.growth_percentage:+.1f}%")
    print(f"Retention: {trend.retention_rate:.1%}")
    print(f"Confidence: {trend.confidence_score:.1%}")

    # Top contexts
    print("\n🎯 TOP CONTEXTS")
    dist = result.context_distribution
    top_contexts = sorted(
        dist.by_context_type.items(), key=lambda x: x[1], reverse=True
    )[:3]
    for i, (context, count) in enumerate(top_contexts, 1):
        print(f"{i}. {context}: {count} executions")

    # Analytics quality
    print("\n🔍 ANALYTICS QUALITY")
    print(f"Data Points: {result.total_data_points}")
    print(f"Quality Score: {result.analytics_quality_score:.1%}")
    print(f"Computation Time: {result.computation_time_ms:.2f}ms")

    # Health status
    print("\n🏥 HEALTH STATUS")
    if result.success_metrics.success_rate >= 0.95:
        print("✅ Excellent - Pattern performing very well")
    elif result.success_metrics.success_rate >= 0.80:
        print("✅ Good - Pattern performing well")
    elif result.success_metrics.success_rate >= 0.60:
        print("⚠️  Warning - Success rate needs improvement")
    else:
        print("❌ Critical - Pattern has serious issues")

    print()


# ============================================================================
# Example 6: Comparative Analytics
# ============================================================================


async def example_comparative_analytics():
    """
    Example: Compare analytics across multiple patterns.

    Use Case: Identify best-performing patterns vs underperforming ones
    """
    print("Example 6: Comparative Analytics")
    print("=" * 60)

    reducer = NodeUsageAnalyticsReducer()
    now = datetime.now(timezone.utc)

    patterns = []

    # Pattern 1: High performer
    pattern1_data = [
        {
            "execution_id": str(uuid4()),
            "timestamp": now - timedelta(hours=i),
            "success": True,
            "execution_time_ms": 100 + (i % 20) * 5,
            "quality_score": 0.95,
        }
        for i in range(100)
    ]

    # Pattern 2: Average performer
    pattern2_data = [
        {
            "execution_id": str(uuid4()),
            "timestamp": now - timedelta(hours=i),
            "success": i % 5 != 0,
            "execution_time_ms": 300 + (i % 30) * 10,
            "quality_score": 0.75,
        }
        for i in range(50)
    ]

    # Pattern 3: Low performer
    pattern3_data = [
        {
            "execution_id": str(uuid4()),
            "timestamp": now - timedelta(hours=i),
            "success": i % 3 != 0,
            "execution_time_ms": 600 + (i % 50) * 15,
            "quality_score": 0.60,
        }
        for i in range(30)
    ]

    # Compute analytics for all patterns
    for pattern_name, execution_data in [
        ("HighPerformer", pattern1_data),
        ("AveragePerformer", pattern2_data),
        ("LowPerformer", pattern3_data),
    ]:
        contract = ModelUsageAnalyticsInput(
            pattern_id=uuid4(),
            time_window_start=now - timedelta(days=5),
            time_window_end=now,
            include_performance=True,
            execution_data=execution_data,
        )

        result = await reducer.execute_reduction(contract)
        patterns.append((pattern_name, result))

    # Display comparative table
    print(
        f"{'Pattern':<20} {'Usage':<10} {'Success':<10} {'P95 Latency':<15} {'Quality':<10}"
    )
    print("-" * 70)

    for name, result in patterns:
        usage = result.usage_metrics.total_executions
        success = f"{result.success_metrics.success_rate:.1%}"
        p95 = f"{result.performance_metrics.p95_execution_time_ms:.0f}ms"
        quality = f"{result.success_metrics.avg_quality_score:.2f}"

        print(f"{name:<20} {usage:<10} {success:<10} {p95:<15} {quality:<10}")

    print()

    # Recommendations
    print("📋 RECOMMENDATIONS:")
    for name, result in patterns:
        if result.success_metrics.success_rate < 0.80:
            print(
                f"⚠️  {name}: Improve success rate (currently {result.success_metrics.success_rate:.1%})"
            )
        if result.performance_metrics.p95_execution_time_ms > 500:
            print(
                f"⚠️  {name}: Optimize performance (P95 = {result.performance_metrics.p95_execution_time_ms:.0f}ms)"
            )
        if result.success_metrics.avg_quality_score < 0.70:
            print(
                f"⚠️  {name}: Improve code quality (currently {result.success_metrics.avg_quality_score:.2f})"
            )

    print()


# ============================================================================
# Example 7: Export Analytics to JSON
# ============================================================================


async def example_export_to_json():
    """
    Example: Export analytics results to JSON for external processing.

    Use Case: Integrate with monitoring systems, dashboards, APIs
    """
    print("Example 7: Export Analytics to JSON")
    print("=" * 60)

    reducer = NodeUsageAnalyticsReducer()
    now = datetime.now(timezone.utc)

    execution_data = [
        {
            "execution_id": str(uuid4()),
            "timestamp": now - timedelta(hours=i),
            "success": True,
            "execution_time_ms": 200 + (i % 25) * 8,
            "quality_score": 0.85,
        }
        for i in range(50)
    ]

    contract = ModelUsageAnalyticsInput(
        pattern_id=uuid4(),
        time_window_start=now - timedelta(days=2),
        time_window_end=now,
        include_performance=True,
        include_trends=True,
        include_distribution=True,
        execution_data=execution_data,
    )

    result = await reducer.execute_reduction(contract)

    # Convert to JSON
    analytics_json = result.to_dict()

    # Pretty print JSON
    print(json.dumps(analytics_json, indent=2, default=str))
    print()

    # Example: Save to file
    # with open("pattern_analytics.json", "w") as f:
    #     json.dump(analytics_json, f, indent=2, default=str)
    # print("Analytics exported to pattern_analytics.json")


# ============================================================================
# Main Runner
# ============================================================================


async def main():
    """Run all examples."""
    examples = [
        example_basic_analytics,
        example_performance_analysis,
        example_trend_detection,
        example_context_distribution,
        example_comprehensive_dashboard,
        example_comparative_analytics,
        example_export_to_json,
    ]

    for example_func in examples:
        await example_func()
        print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
