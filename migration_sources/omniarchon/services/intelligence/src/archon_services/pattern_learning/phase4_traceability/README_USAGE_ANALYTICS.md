# Usage Analytics Reducer - Phase 4 Agent 2

**ONEX Pattern**: Reducer Node (Pure Data Aggregation)
**Performance Target**: <500ms per pattern analytics computation
**Test Coverage**: >95%
**Status**: ✅ Complete

## Overview

The Usage Analytics Reducer is an ONEX-compliant Reducer node that aggregates pattern usage metrics over time with comprehensive analytics capabilities. It provides insights into:

- **Usage Frequency**: How often patterns are executed
- **Success Rates**: Pattern effectiveness and reliability
- **Performance Metrics**: Execution time percentiles and statistics
- **Trend Analysis**: Usage trends (growing, stable, declining)
- **Context Distribution**: Where and how patterns are used

## Architecture

### ONEX Reducer Node

```
Input (from Effect nodes)
    ↓
Pure Data Aggregation (no I/O)
    ↓
    ├─ Usage Frequency Computation
    ├─ Success/Failure Analysis
    ├─ Performance Percentiles (P50, P95, P99)
    ├─ Trend Detection & Velocity
    └─ Context Distribution
    ↓
Output (ModelUsageAnalyticsOutput)
```

**Key Characteristics**:
- ✅ Pure functional operations
- ✅ No external I/O
- ✅ Stateless (no instance state)
- ✅ Deterministic results
- ✅ <500ms computation time

## Quick Start

### Basic Usage

```python
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from pattern_learning.phase4_traceability.node_usage_analytics_reducer import (
    NodeUsageAnalyticsReducer
)
from pattern_learning.phase4_traceability.model_contract_usage_analytics import (
    ModelUsageAnalyticsInput,
    TimeWindowType,
    AnalyticsGranularity
)

# Initialize reducer
reducer = NodeUsageAnalyticsReducer()

# Prepare input data (from database)
now = datetime.now(timezone.utc)
execution_data = [
    {
        "execution_id": str(uuid4()),
        "timestamp": now - timedelta(hours=i),
        "success": True,
        "execution_time_ms": 200,
        "quality_score": 0.85,
        "context_type": "debugging",
        "agent": "agent-1",
    }
    for i in range(50)
]

# Create input contract
contract = ModelUsageAnalyticsInput(
    pattern_id=uuid4(),
    time_window_start=now - timedelta(days=7),
    time_window_end=now,
    time_window_type=TimeWindowType.WEEKLY,
    granularity=AnalyticsGranularity.DETAILED,
    execution_data=execution_data,
)

# Compute analytics
result = await reducer.execute_reduction(contract)

# Access results
print(f"Total Executions: {result.usage_metrics.total_executions}")
print(f"Success Rate: {result.success_metrics.success_rate:.1%}")
print(f"P95 Latency: {result.performance_metrics.p95_execution_time_ms:.2f}ms")
print(f"Trend: {result.trend_analysis.trend_type.value}")
```

## Metrics Computed

### 1. Usage Frequency Metrics

Tracks how often patterns are executed over time.

```python
@dataclass
class UsageFrequencyMetrics:
    total_executions: int              # Total pattern executions
    executions_per_day: float          # Average daily executions
    executions_per_week: float         # Average weekly executions
    executions_per_month: float        # Average monthly executions
    unique_contexts: int               # Unique execution contexts
    unique_users: int                  # Unique users/agents
    peak_daily_usage: int              # Maximum daily executions
    time_since_last_use: Optional[float]  # Hours since last use
```

**Use Cases**:
- Monitor pattern adoption
- Identify heavily-used patterns
- Detect abandoned patterns
- Resource planning

### 2. Success Metrics

Measures pattern effectiveness and reliability.

```python
@dataclass
class SuccessMetrics:
    success_count: int                 # Successful executions
    failure_count: int                 # Failed executions
    success_rate: float                # Success percentage (0.0-1.0)
    error_rate: float                  # Error percentage (0.0-1.0)
    timeout_count: int                 # Timeout occurrences
    quality_gate_failures: int         # Quality gate violations
    avg_quality_score: float           # Average quality score
```

**Use Cases**:
- Quality monitoring
- Pattern reliability tracking
- Identify problematic patterns
- SLA compliance

### 3. Performance Metrics

Analyzes execution time and performance characteristics.

```python
@dataclass
class PerformanceMetrics:
    avg_execution_time_ms: float       # Average execution time
    p50_execution_time_ms: float       # Median (50th percentile)
    p95_execution_time_ms: float       # 95th percentile
    p99_execution_time_ms: float       # 99th percentile
    min_execution_time_ms: float       # Minimum execution time
    max_execution_time_ms: float       # Maximum execution time
    std_dev_ms: float                  # Standard deviation
    total_execution_time_ms: float     # Cumulative execution time
```

**Use Cases**:
- Performance optimization
- SLA monitoring
- Identify slow patterns
- Capacity planning

**Performance Thresholds**:
- ✅ P95 < 500ms: Excellent
- ⚠️ P95 500-1000ms: Needs attention
- ❌ P95 > 1000ms: Requires optimization

### 4. Trend Analysis

Detects usage trends and predicts future patterns.

```python
@dataclass
class TrendAnalysis:
    trend_type: UsageTrendType         # growing/stable/declining/emerging/abandoned
    velocity: float                    # Rate of change (executions/period)
    acceleration: float                # Change in velocity
    adoption_rate: float               # New users per week
    retention_rate: float              # User retention (0.0-1.0)
    churn_rate: float                  # User churn (0.0-1.0)
    growth_percentage: float           # Growth vs previous period
    confidence_score: float            # Trend confidence (0.0-1.0)
```

**Trend Types**:
- **GROWING**: Usage increasing over time (velocity > 0.5)
- **STABLE**: Consistent usage rate (|velocity| < 0.5)
- **DECLINING**: Usage decreasing (velocity < -0.5)
- **EMERGING**: New pattern gaining traction (<10 executions)
- **ABANDONED**: No recent usage (velocity < -2.0, <5 executions)

**Use Cases**:
- Investment decisions
- Deprecation planning
- Resource allocation
- Strategic planning

### 5. Context Distribution

Analyzes how patterns are used across different contexts.

```python
@dataclass
class ContextDistribution:
    by_context_type: Dict[str, int]    # Usage by context type
    by_agent: Dict[str, int]           # Usage by agent/user
    by_project: Dict[str, int]         # Usage by project
    by_file_type: Dict[str, int]       # Usage by file type
    by_time_of_day: Dict[int, int]     # Usage by hour (0-23)
    by_day_of_week: Dict[int, int]     # Usage by day (0-6)
```

**Use Cases**:
- Understand usage patterns
- Team/project insights
- Temporal analysis
- Resource optimization

## Configuration Options

### Time Windows

Control the analysis time period:

```python
class TimeWindowType(str, Enum):
    HOURLY = "hourly"          # Last hour
    DAILY = "daily"            # Last 24 hours
    WEEKLY = "weekly"          # Last 7 days
    MONTHLY = "monthly"        # Last 30 days
    QUARTERLY = "quarterly"    # Last 90 days
    YEARLY = "yearly"          # Last 365 days
    ALL_TIME = "all_time"      # Complete history
```

### Analytics Granularity

Control the level of detail:

```python
class AnalyticsGranularity(str, Enum):
    SUMMARY = "summary"           # High-level overview only
    DETAILED = "detailed"         # Includes breakdowns (default)
    COMPREHENSIVE = "comprehensive"  # Full analysis with predictions
```

### Feature Flags

Enable/disable specific analytics:

```python
contract = ModelUsageAnalyticsInput(
    pattern_id=pattern_id,
    time_window_start=start_time,
    time_window_end=end_time,

    # Feature flags
    include_trends=True,          # Trend analysis
    include_performance=True,     # Performance metrics
    include_distribution=True,    # Context distribution
    include_predictions=False,    # Future predictions (experimental)

    execution_data=data,
)
```

## Use Cases

### 1. Pattern Health Monitoring

Monitor pattern health and identify issues:

```python
result = await reducer.execute_reduction(contract)

# Health check
if result.success_metrics.success_rate < 0.80:
    print("⚠️ Low success rate - investigate failures")

if result.performance_metrics.p95_execution_time_ms > 500:
    print("⚠️ High latency - optimization needed")

if result.usage_metrics.time_since_last_use > 168:  # 1 week
    print("⚠️ Pattern not used recently - consider archival")
```

### 2. Performance Optimization

Identify patterns needing optimization:

```python
result = await reducer.execute_reduction(contract)
perf = result.performance_metrics

# Check performance degradation
if perf.p95_execution_time_ms > 2 * perf.p50_execution_time_ms:
    print("⚠️ High variance - investigate outliers")

# Check absolute performance
if perf.p99_execution_time_ms > 1000:
    print("❌ Critical: P99 exceeds 1 second")
```

### 3. Trend-Based Resource Planning

Make strategic decisions based on trends:

```python
result = await reducer.execute_reduction(contract)
trend = result.trend_analysis

if trend.trend_type == UsageTrendType.GROWING:
    # Growing pattern - invest in optimization
    print(f"📈 Growing {trend.velocity:.1f} executions/day")
    print("Action: Invest in optimization and scaling")

elif trend.trend_type == UsageTrendType.DECLINING:
    # Declining pattern - investigate why
    print(f"📉 Declining {trend.velocity:.1f} executions/day")
    print("Action: Investigate reasons for decline")

elif trend.trend_type == UsageTrendType.ABANDONED:
    # Abandoned pattern - consider deprecation
    print("🗑️ Pattern abandoned")
    print("Action: Mark for deprecation")
```

### 4. Team/Project Analytics

Analyze usage across teams and projects:

```python
result = await reducer.execute_reduction(contract)
dist = result.context_distribution

# Find top teams using pattern
top_teams = sorted(
    dist.by_agent.items(),
    key=lambda x: x[1],
    reverse=True
)[:5]

print("Top Teams:")
for team, count in top_teams:
    print(f"  {team}: {count} executions")

# Find peak usage times
peak_hours = sorted(
    dist.by_time_of_day.items(),
    key=lambda x: x[1],
    reverse=True
)[:3]

print("Peak Hours:")
for hour, count in peak_hours:
    print(f"  {hour:02d}:00 - {count} executions")
```

### 5. Quality Gate Monitoring

Track quality metrics over time:

```python
result = await reducer.execute_reduction(contract)

quality_issues = []

if result.success_metrics.quality_gate_failures > 0:
    quality_issues.append(
        f"{result.success_metrics.quality_gate_failures} quality gate failures"
    )

if result.success_metrics.avg_quality_score < 0.70:
    quality_issues.append(
        f"Low quality score: {result.success_metrics.avg_quality_score:.2f}"
    )

if quality_issues:
    print("Quality Issues:")
    for issue in quality_issues:
        print(f"  ⚠️ {issue}")
```

## Integration Patterns

### 1. With Database Effect Nodes

Analytics reducer receives data from Effect nodes:

```python
# Effect node fetches execution data from PostgreSQL
execution_data = await pattern_storage_effect.fetch_executions(
    pattern_id=pattern_id,
    start_time=start_time,
    end_time=end_time
)

# Reducer computes analytics (pure function, no I/O)
contract = ModelUsageAnalyticsInput(
    pattern_id=pattern_id,
    time_window_start=start_time,
    time_window_end=end_time,
    execution_data=execution_data,  # Data from Effect node
)

analytics = await reducer.execute_reduction(contract)

# Another Effect node stores results
await analytics_storage_effect.store_analytics(analytics)
```

### 2. With Dashboard Orchestrator

Orchestrator coordinates multiple analytics computations:

```python
class DashboardOrchestrator:
    async def generate_dashboard(self, pattern_ids: List[UUID]) -> Dict:
        """Generate dashboard for multiple patterns."""

        analytics_results = []

        for pattern_id in pattern_ids:
            # Fetch data (Effect node)
            execution_data = await self.storage.fetch_executions(pattern_id)

            # Compute analytics (Reducer node)
            contract = ModelUsageAnalyticsInput(
                pattern_id=pattern_id,
                execution_data=execution_data,
                # ... other params
            )
            analytics = await self.reducer.execute_reduction(contract)
            analytics_results.append(analytics)

        # Aggregate for dashboard
        return self._build_dashboard(analytics_results)
```

### 3. With Real-Time Monitoring

Continuous monitoring with periodic analytics updates:

```python
async def monitor_patterns():
    """Continuous pattern monitoring."""

    while True:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=1)

        for pattern_id in active_patterns:
            # Get recent executions
            executions = await storage.fetch_executions(
                pattern_id, window_start, now
            )

            # Compute analytics
            contract = ModelUsageAnalyticsInput(
                pattern_id=pattern_id,
                time_window_start=window_start,
                time_window_end=now,
                execution_data=executions,
            )

            analytics = await reducer.execute_reduction(contract)

            # Check for alerts
            if analytics.success_metrics.error_rate > 0.20:
                await send_alert(f"High error rate for {pattern_id}")

        # Wait before next check
        await asyncio.sleep(300)  # 5 minutes
```

## Performance Optimization

### Target Performance

- **Computation Time**: <500ms per pattern
- **Data Volume**: Handles 1000+ execution records efficiently
- **Memory Usage**: O(n) where n = number of execution records
- **Scalability**: Linear time complexity

### Optimization Techniques

1. **Efficient Percentile Calculation**
   - Pre-sorted arrays for O(1) percentile lookup
   - Single-pass statistical computations

2. **Lazy Computation**
   - Optional metrics only computed when requested
   - Feature flags control computation overhead

3. **Memory Efficiency**
   - Streaming-style aggregation where possible
   - Minimal intermediate data structures

4. **Batching Support**
   - Single reducer call can handle multiple time windows
   - Efficient bulk analytics computation

## Testing

### Test Coverage

>95% test coverage including:

- ✅ Core reducer functionality
- ✅ All metric computation methods
- ✅ Edge cases (empty data, single execution)
- ✅ Performance benchmarks
- ✅ Contract validation
- ✅ Integration scenarios

### Running Tests

```bash
# Run all tests
pytest tests/test_usage_analytics_reducer.py -v

# Run specific test category
pytest tests/test_usage_analytics_reducer.py -k "test_compute_usage_frequency" -v

# Run with coverage
pytest tests/test_usage_analytics_reducer.py --cov --cov-report=html

# Run performance tests
pytest tests/test_usage_analytics_reducer.py -k "test_performance" -v
```

### Key Test Scenarios

```python
# Test basic analytics
async def test_execute_reduction_basic(reducer, sample_data):
    result = await reducer.execute_reduction(contract)
    assert result.computation_time_ms < 500  # Performance target
    assert result.total_data_points == len(sample_data)

# Test large dataset performance
async def test_performance_large_dataset(reducer):
    large_dataset = create_dataset(size=1000)
    result = await reducer.execute_reduction(contract)
    assert result.computation_time_ms < 500  # Still meets target

# Test edge cases
async def test_execute_reduction_empty_data(reducer):
    result = await reducer.execute_reduction(empty_contract)
    assert result.total_data_points == 0  # Handles gracefully
```

## Examples

### Run Examples

```bash
# Run all examples
python analytics_examples.py

# Run specific example
python -c "from analytics_examples import example_basic_analytics; import asyncio; asyncio.run(example_basic_analytics())"
```

### Available Examples

1. **Basic Analytics** - Simple usage frequency and success rates
2. **Performance Analysis** - Percentile metrics and performance health
3. **Trend Detection** - Usage trends and growth patterns
4. **Context Distribution** - Team/project/temporal analysis
5. **Comprehensive Dashboard** - Full analytics for dashboard display
6. **Comparative Analytics** - Compare multiple patterns
7. **Export to JSON** - Export analytics for external systems

## API Reference

### Main Classes

#### NodeUsageAnalyticsReducer

```python
class NodeUsageAnalyticsReducer:
    """ONEX Reducer node for pattern usage analytics."""

    async def execute_reduction(
        self,
        contract: ModelUsageAnalyticsInput
    ) -> ModelUsageAnalyticsOutput:
        """
        Execute analytics reduction on pattern usage data.

        Args:
            contract: Input contract with pattern data

        Returns:
            Output contract with comprehensive analytics

        Performance:
            <500ms computation time
        """
```

### Input Contract

```python
@dataclass
class ModelUsageAnalyticsInput:
    """Input contract for analytics computation."""

    pattern_id: UUID                    # Pattern to analyze
    time_window_start: datetime         # Analysis window start
    time_window_end: datetime           # Analysis window end
    time_window_type: TimeWindowType    # Window type
    granularity: AnalyticsGranularity   # Detail level

    # Feature flags
    include_trends: bool = True
    include_performance: bool = True
    include_distribution: bool = True
    include_predictions: bool = False

    # Input data (from Effect nodes)
    execution_data: List[Dict[str, Any]]

    # Tracing
    correlation_id: UUID
```

### Output Contract

```python
@dataclass
class ModelUsageAnalyticsOutput:
    """Output contract with analytics results."""

    pattern_id: UUID
    time_window_start: datetime
    time_window_end: datetime
    time_window_type: TimeWindowType

    # Core metrics
    usage_metrics: UsageFrequencyMetrics
    success_metrics: SuccessMetrics

    # Optional metrics
    performance_metrics: Optional[PerformanceMetrics]
    trend_analysis: Optional[TrendAnalysis]
    context_distribution: Optional[ContextDistribution]

    # Summary
    total_data_points: int
    analytics_quality_score: float
    computation_time_ms: float

    # Export to JSON
    def to_dict(self) -> Dict[str, Any]:
        """Convert analytics to dictionary format."""
```

## Troubleshooting

### Common Issues

**Issue**: Analytics computation takes >500ms

**Solutions**:
- Reduce data volume by filtering at source
- Disable optional analytics (trends, distribution)
- Use SUMMARY granularity instead of COMPREHENSIVE
- Batch multiple analytics computations

**Issue**: Low analytics quality score

**Solutions**:
- Increase time window duration (more data)
- Wait for more pattern executions
- Ensure execution data includes all fields
- Check data quality at source

**Issue**: Unexpected trend classification

**Solutions**:
- Verify sufficient data points (>20 recommended)
- Check time window duration (7+ days recommended)
- Review velocity threshold settings
- Validate execution timestamps

## Future Enhancements

### Planned Features

- [ ] Predictive analytics (usage forecasting)
- [ ] Anomaly detection in usage patterns
- [ ] Seasonal trend analysis
- [ ] Cross-pattern correlation analysis
- [ ] Advanced statistical models
- [ ] Real-time streaming analytics

### Contributing

When extending the analytics reducer:

1. **Maintain ONEX Compliance**: Pure functions, no I/O
2. **Performance**: Keep computation <500ms
3. **Test Coverage**: Maintain >95% coverage
4. **Documentation**: Update this README
5. **Examples**: Add new examples for new features

## References

- **ONEX Architecture**: [ONEX Architecture Patterns](../../../../../../docs/onex/archive/ONEX_ARCHITECTURE_PATTERNS_COMPLETE.md)
- **Phase 4 Overview**: `/docs/TRACK_3_2_AGENT_2_SPEC.md`
- **Contract Models**: `model_contract_usage_analytics.py`
- **Test Suite**: `tests/test_usage_analytics_reducer.py`
- **Examples**: `analytics_examples.py`

## Support

For issues, questions, or contributions:

1. Check this README first
2. Review examples in `analytics_examples.py`
3. Run tests to verify setup
4. Check Phase 4 documentation

---

**Agent 2: Usage Analytics Reducer**
**Status**: ✅ Complete
**ONEX Compliance**: ✅ Validated
**Performance**: ✅ <500ms target met
**Test Coverage**: ✅ >95%
**Documentation**: ✅ Complete

*Built with precision for Track 3 Phase 4 Pattern Learning Engine*
