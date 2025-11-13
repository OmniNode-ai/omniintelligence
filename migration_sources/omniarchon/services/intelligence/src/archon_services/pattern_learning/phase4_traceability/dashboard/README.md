

# Phase 4 Analytics Dashboard

Interactive visualization dashboard for pattern learning analytics with lineage tracking, usage metrics, feedback analysis, and real-time monitoring.

## Overview

The Phase 4 Analytics Dashboard provides comprehensive visualization and monitoring capabilities for the pattern learning system, including:

- **Lineage Graph Visualization**: Interactive force-directed graphs showing pattern evolution
- **Usage Analytics**: Time-series charts, heatmaps, and performance distributions
- **Feedback Analysis**: Sentiment analysis, improvement tracking, and quality ratings
- **Real-time Metrics**: Live streaming of pattern execution and feedback metrics

## Architecture

```
dashboard/
├── __init__.py                    # Package exports
├── app.py                         # Main FastAPI application
├── visualizations/
│   ├── __init__.py
│   ├── lineage_graph.py          # Lineage graph visualizations
│   ├── usage_charts.py           # Usage analytics charts
│   ├── feedback_view.py          # Feedback analysis views
│   └── realtime_metrics.py       # Real-time metrics streaming
└── README.md                      # This file
```

## Installation

### Dependencies

```bash
# Core visualization dependencies
pip install plotly networkx pandas

# FastAPI for dashboard server
pip install fastapi uvicorn

# Optional: Image export (requires kaleido)
pip install kaleido
```

### Quick Start

```python
from phase4_traceability.dashboard import DashboardApp

# Create dashboard application
app = DashboardApp(output_dir="./exports")

# Run FastAPI server
import uvicorn
uvicorn.run(app.app, host="0.0.0.0", port=8000)
```

## Usage Guide

### 1. Lineage Graph Visualization

Visualize pattern evolution lineage with interactive force-directed graphs.

```python
from phase4_traceability.dashboard.visualizations.lineage_graph import LineageGraphVisualizer
from phase4_traceability.models.model_lineage_graph import ModelLineageGraph

# Initialize visualizer
viz = LineageGraphVisualizer(layout_algorithm="spring")

# Load lineage graph (from database in production)
lineage_graph = ModelLineageGraph()
# ... populate graph with nodes and edges

# Create interactive visualization
fig = viz.create_interactive_graph(
    lineage_graph,
    focus_pattern_id=pattern_id,  # Optional: focus on specific pattern
    max_depth=3,                  # Optional: limit traversal depth
    title="API Debug Pattern Evolution"
)

# Display in browser
fig.show()

# Export to file
viz.export_graph(fig, "lineage_graph.html", format="html")
viz.export_graph(fig, "lineage_graph.png", format="png", width=1200, height=800)
```

**Lineage Graph Features**:
- **Color-coded nodes**: Green (active), Gray (deprecated), Blue (merged), Light gray (archived)
- **Edge types**: Derived from, Merged with, Replaced by, Split into, Inspired by
- **Node size**: Proportional to usage count
- **Hover information**: Pattern details, version, usage, success rate
- **Interactive**: Zoom, pan, and click for details

### 2. Usage Analytics Charts

Analyze pattern usage trends and performance metrics.

```python
from phase4_traceability.dashboard.visualizations.usage_charts import UsageAnalyticsCharts
from phase4_traceability.models.model_pattern_metrics import (
    ModelPatternUsageMetrics,
    ModelPatternPerformanceMetrics,
)

# Initialize charts
viz = UsageAnalyticsCharts()

# Load metrics (from database in production)
usage_metrics = [...]  # List of ModelPatternUsageMetrics
performance_metrics = [...]  # List of ModelPatternPerformanceMetrics

# Usage trend over time
fig_trend = viz.create_usage_trend_chart(
    usage_metrics,
    title="Pattern Usage Trends (Last 30 Days)"
)
fig_trend.show()

# Success rate heatmap
fig_heatmap = viz.create_success_rate_heatmap(
    usage_metrics,
    title="Success Rate Heatmap"
)
fig_heatmap.show()

# Performance distribution
fig_perf = viz.create_performance_histogram(
    performance_metrics,
    title="Execution Time Distribution"
)
fig_perf.show()

# Top patterns
fig_top = viz.create_top_patterns_chart(
    usage_metrics,
    top_n=10,
    metric="execution_count",
    title="Top 10 Most Used Patterns"
)
fig_top.show()

# Multi-metric dashboard
fig_dashboard = viz.create_multi_metric_dashboard(
    usage_metrics,
    performance_metrics,
    title="Pattern Analytics Dashboard"
)
fig_dashboard.show()
```

**Available Charts**:
- `create_usage_trend_chart()`: Time-series of executions and success rates
- `create_success_rate_heatmap()`: Heatmap of success rates over time
- `create_performance_histogram()`: Distribution of execution times
- `create_context_breakdown_pie()`: Pie chart of usage by context
- `create_top_patterns_chart()`: Bar chart of top N patterns
- `create_performance_comparison()`: Box plot comparing pattern performance
- `create_multi_metric_dashboard()`: Comprehensive multi-panel dashboard

### 3. Feedback Analysis

Visualize feedback sentiment, improvements, and quality ratings.

```python
from phase4_traceability.dashboard.visualizations.feedback_view import FeedbackAnalysisView
from phase4_traceability.models.model_pattern_feedback import (
    ModelPatternFeedback,
    ModelPatternImprovement,
)

# Initialize feedback view
viz = FeedbackAnalysisView()

# Load feedback data
feedbacks = [...]  # List of ModelPatternFeedback
improvements = [...]  # List of ModelPatternImprovement

# Sentiment distribution
fig_sentiment = viz.create_sentiment_distribution(
    feedbacks,
    title="Feedback Sentiment Distribution"
)
fig_sentiment.show()

# Feedback timeline
fig_timeline = viz.create_feedback_timeline(
    feedbacks,
    title="Quality Ratings Over Time"
)
fig_timeline.show()

# Improvement pipeline
fig_pipeline = viz.create_improvement_pipeline(
    improvements,
    title="Improvement Pipeline Status"
)
fig_pipeline.show()

# Priority breakdown
fig_priority = viz.create_improvement_priority_breakdown(
    improvements,
    title="Improvements by Priority Level"
)
fig_priority.show()

# Comprehensive feedback dashboard
fig_dashboard = viz.create_feedback_dashboard(
    feedbacks,
    improvements,
    title="Feedback Analysis Dashboard"
)
fig_dashboard.show()
```

**Feedback Visualizations**:
- `create_sentiment_distribution()`: Pie chart of positive/neutral/negative feedback
- `create_feedback_timeline()`: Scatter plot of quality ratings over time
- `create_improvement_pipeline()`: Funnel chart of improvement stages
- `create_improvement_priority_breakdown()`: Bar chart by priority level
- `create_improvement_type_breakdown()`: Pie chart by improvement type
- `create_feedback_summary_table()`: Table of recent feedback
- `create_improvement_summary_table()`: Table of improvement suggestions
- `create_feedback_dashboard()`: Multi-panel comprehensive dashboard

### 4. Real-time Metrics

Stream live pattern execution and feedback metrics.

```python
from phase4_traceability.dashboard.visualizations.realtime_metrics import (
    get_realtime_streamer,
    RealtimeMetric,
)

# Get singleton streamer
streamer = get_realtime_streamer()

# Publish metrics (from pattern execution hooks)
await streamer.publish_metric(RealtimeMetric(
    metric_type="execution",
    pattern_id=pattern_id,
    pattern_name="api_debug_pattern",
    value=1,
    metadata={
        "success": True,
        "execution_time_ms": 450
    }
))

# Stream metrics (async generator)
async for metric in streamer.stream_metrics(pattern_id=pattern_id):
    print(f"Received: {metric.metric_type} - {metric.value}")

# Get metrics summary
summary = await streamer.get_metrics_summary()
print(f"Active patterns: {summary.active_patterns}")
print(f"Total executions today: {summary.total_executions_today}")
print(f"Average success rate: {summary.avg_success_rate:.1%}")
```

**Real-time Features**:
- WebSocket-compatible streaming
- Server-Sent Events (SSE) support
- Metric buffering with configurable size
- Pattern-specific filtering
- Type-based filtering
- Heartbeat metrics for connection health

### 5. Complete Dashboard Application

Use the FastAPI dashboard for full-featured analytics.

```python
from phase4_traceability.dashboard.app import create_dashboard_app

# Create dashboard application
dashboard = create_dashboard_app()

# Generate full dashboard
dashboard_data = dashboard.generate_full_dashboard(
    lineage_graph=lineage_graph,
    usage_metrics=usage_metrics,
    performance_metrics=performance_metrics,
    feedbacks=feedbacks,
    improvements=improvements,
    title="Pattern Learning Analytics"
)

# Export to HTML
export_path = dashboard.export_dashboard_html(
    dashboard_data,
    filepath=Path("dashboard.html")
)

# Run FastAPI server
import uvicorn
uvicorn.run(dashboard.app, host="0.0.0.0", port=8000)
```

**Dashboard Endpoints**:

```bash
# Home page
GET http://localhost:8000/

# Lineage graph for specific pattern
GET http://localhost:8000/api/lineage/{pattern_id}

# Usage metrics
GET http://localhost:8000/api/usage?time_window_days=30

# Feedback data
GET http://localhost:8000/api/feedback?time_window_days=30

# Real-time metrics stream (SSE)
GET http://localhost:8000/api/metrics/realtime

# Metrics summary
GET http://localhost:8000/api/metrics/summary

# Export dashboard
POST http://localhost:8000/api/export
{
  "export_format": "html",
  "include_sections": ["lineage", "usage", "feedback", "metrics"],
  "time_window_days": 30,
  "title": "Pattern Analytics Dashboard"
}

# Health check
GET http://localhost:8000/health

# API documentation
GET http://localhost:8000/docs
```

## Examples

### Example 1: Daily Usage Report

Generate daily usage report with charts:

```python
from datetime import date, timedelta

# Get yesterday's metrics
yesterday = date.today() - timedelta(days=1)
metrics = db.query(ModelPatternUsageMetrics).filter(
    ModelPatternUsageMetrics.metrics_date == yesterday
).all()

# Create charts
viz = UsageAnalyticsCharts()

# Usage trend
fig_trend = viz.create_usage_trend_chart(metrics)
fig_trend.write_html("daily_usage.html")

# Top patterns
fig_top = viz.create_top_patterns_chart(metrics, top_n=10)
fig_top.write_html("top_patterns.html")

print(f"Generated daily report: {yesterday}")
```

### Example 2: Pattern Evolution Analysis

Analyze pattern evolution with lineage graph:

```python
# Load lineage graph for pattern
lineage_graph = load_lineage_graph(pattern_id)

# Create visualizer
viz = LineageGraphVisualizer(layout_algorithm="hierarchical")

# Generate lineage visualization
fig = viz.create_interactive_graph(
    lineage_graph,
    focus_pattern_id=pattern_id,
    max_depth=5,
    title=f"Evolution of {pattern_name}"
)

# Get summary statistics
summary = viz.create_lineage_summary(lineage_graph)
print(f"Total patterns in lineage: {summary['total_nodes']}")
print(f"Evolution relationships: {summary['total_edges']}")
print(f"Active versions: {summary['active_patterns']}")

# Export
fig.write_html("pattern_evolution.html")
```

### Example 3: Feedback-Driven Improvements

Track improvements from feedback:

```python
# Get recent feedback
recent_feedback = db.query(ModelPatternFeedback).filter(
    ModelPatternFeedback.created_at >= datetime.now() - timedelta(days=7)
).all()

# Get pending improvements
pending_improvements = db.query(ModelPatternImprovement).filter(
    ModelPatternImprovement.status == ImprovementStatus.PROPOSED
).all()

# Create visualizations
viz = FeedbackAnalysisView()

# Sentiment analysis
fig_sentiment = viz.create_sentiment_distribution(recent_feedback)
fig_sentiment.show()

# Improvement pipeline
fig_pipeline = viz.create_improvement_pipeline(pending_improvements)
fig_pipeline.show()

# Generate report
report = {
    "positive_feedback": len([f for f in recent_feedback if f.sentiment == FeedbackSentiment.POSITIVE]),
    "pending_improvements": len(pending_improvements),
    "high_priority": len([i for i in pending_improvements if i.priority == "high"]),
}

print(f"Feedback Report: {report}")
```

### Example 4: Real-time Monitoring

Monitor pattern executions in real-time:

```python
import asyncio

async def monitor_patterns():
    streamer = get_realtime_streamer()

    print("Monitoring pattern executions...")

    async for metric in streamer.stream_metrics(metric_types=["execution"]):
        if metric.metric_type == "execution":
            success = metric.metadata.get("success", False)
            exec_time = metric.metadata.get("execution_time_ms", 0)

            status = "✓" if success else "✗"
            print(f"{status} {metric.pattern_name}: {exec_time}ms")

        elif metric.metric_type == "heartbeat":
            print(".", end="", flush=True)

# Run monitor
asyncio.run(monitor_patterns())
```

## Performance Considerations

### Visualization Performance

- **Large graphs**: Use `focus_pattern_id` to limit visualization scope
- **Time-series data**: Downsample for >1000 data points
- **Heatmaps**: Limit to reasonable date ranges (30-90 days)
- **Export formats**: HTML is fastest, PNG/PDF require kaleido

### Real-time Streaming

- **Buffer size**: Adjust based on metric volume (default: 100)
- **Update interval**: Balance freshness vs. load (default: 5s)
- **Subscriber limits**: Monitor active WebSocket connections
- **Metric retention**: Buffer only keeps recent metrics

### Dashboard Scaling

- **Caching**: Cache generated visualizations for frequently accessed patterns
- **Lazy loading**: Load dashboard sections on demand
- **Pagination**: Paginate tables and lists
- **Background tasks**: Generate reports asynchronously

## Testing

Run comprehensive tests:

```bash
# Run all dashboard tests
pytest tests/test_dashboard.py -v

# Run specific test class
pytest tests/test_dashboard.py::TestLineageGraphVisualizer -v

# Run with coverage
pytest tests/test_dashboard.py --cov=dashboard --cov-report=html
```

## Export Formats

Supported export formats:

| Format | Use Case | Requirements |
|--------|----------|--------------|
| HTML | Interactive dashboards, sharing | None |
| PNG | Static images, reports | kaleido |
| SVG | Scalable graphics, print | kaleido |
| PDF | Reports, documentation | kaleido |

## Customization

### Custom Color Schemes

```python
# Custom node colors
LineageGraphVisualizer.STATUS_COLORS = {
    NodeStatus.ACTIVE: "#00FF00",     # Bright green
    NodeStatus.DEPRECATED: "#FF0000", # Red
    # ...
}

# Custom sentiment colors
FeedbackAnalysisView.SENTIMENT_COLORS = {
    FeedbackSentiment.POSITIVE: "#2ECC40",
    FeedbackSentiment.NEUTRAL: "#FFDC00",
    FeedbackSentiment.NEGATIVE: "#FF4136",
}
```

### Custom Layout Algorithms

```python
# Use different NetworkX layout
viz = LineageGraphVisualizer(layout_algorithm="kamada_kawai")

# Available layouts:
# - "spring": Force-directed (default)
# - "kamada_kawai": Energy minimization
# - "circular": Circular arrangement
# - "hierarchical": Tree-like hierarchy (requires graphviz)
```

## Troubleshooting

### Common Issues

**Issue**: "ModuleNotFoundError: No module named 'kaleido'"
```bash
# Install kaleido for image export
pip install kaleido
```

**Issue**: "Graph layout too dense"
```python
# Increase spacing parameter
viz = LineageGraphVisualizer(layout_algorithm="spring")
pos = nx.spring_layout(G, k=3, iterations=100)  # Increase k for more spacing
```

**Issue**: "Dashboard loads slowly"
```python
# Reduce data volume or enable caching
# Option 1: Limit time window
usage_metrics = get_usage_metrics(time_window_days=7)

# Option 2: Downsample data
usage_metrics = downsample_metrics(usage_metrics, target_points=100)
```

## Integration

### Integration with Pattern Learning System

```python
# Hook into pattern execution
from intelligence.hooks import register_hook

@register_hook("post_pattern_execution")
async def publish_execution_metric(pattern_id, success, duration_ms):
    streamer = get_realtime_streamer()
    await streamer.publish_metric(RealtimeMetric(
        metric_type="execution",
        pattern_id=pattern_id,
        value=1,
        metadata={
            "success": success,
            "execution_time_ms": duration_ms
        }
    ))
```

### Integration with FastAPI

```python
from fastapi import FastAPI
from phase4_traceability.dashboard.app import DashboardApp

app = FastAPI()
dashboard = DashboardApp()

# Mount dashboard at /dashboard
app.mount("/dashboard", dashboard.app)
```

## Contributing

When adding new visualizations:

1. Create visualization class in `visualizations/`
2. Add to `__init__.py` exports
3. Write comprehensive tests in `tests/test_dashboard.py`
4. Update this README with usage examples
5. Add integration to `app.py` if needed

## License

Part of the Archon Intelligence System.

## Support

For issues or questions:
- Check troubleshooting section above
- Review test examples in `tests/test_dashboard.py`
- See main project documentation

---

**Version**: 1.0.0
**Last Updated**: 2025-10-02
**Maintainer**: Archon Intelligence Team
