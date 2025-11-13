"""
Phase 4 Dashboard - Comprehensive Tests

Tests for all dashboard visualization components.
"""

from datetime import date, timedelta
from uuid import UUID, uuid4

import plotly.graph_objects as go
import pytest

from ..dashboard.app import DashboardApp
from ..dashboard.visualizations.feedback_view import FeedbackAnalysisView
from ..dashboard.visualizations.lineage_graph import LineageGraphVisualizer
from ..dashboard.visualizations.realtime_metrics import RealtimeMetricsStreamer
from ..dashboard.visualizations.usage_charts import UsageAnalyticsCharts
from ..models.model_lineage_graph import (
    LineageRelationType,
    ModelLineageEdge,
    ModelLineageGraph,
    ModelLineageNode,
    NodeStatus,
)
from ..models.model_pattern_feedback import (
    FeedbackSentiment,
    ImprovementStatus,
    ModelPatternFeedback,
    ModelPatternImprovement,
)
from ..models.model_pattern_metrics import (
    ModelPatternPerformanceMetrics,
    ModelPatternUsageMetrics,
)


# NOTE: correlation_id support enabled for tracing
class TestLineageGraphVisualizer:
    """Tests for lineage graph visualization."""

    @pytest.fixture
    def sample_lineage_graph(self) -> ModelLineageGraph:
        """Create sample lineage graph for testing."""
        graph = ModelLineageGraph()

        # Create nodes
        pattern_v1 = UUID("550e8400-e29b-41d4-a716-446655440000")
        pattern_v2 = UUID("660e8400-e29b-41d4-a716-446655440000")
        pattern_v3 = UUID("770e8400-e29b-41d4-a716-446655440000")

        graph.add_node(
            ModelLineageNode(
                pattern_id=pattern_v1,
                pattern_name="api_debug_v1",
                version=1,
                status=NodeStatus.DEPRECATED,
                usage_count=100,
                success_rate=0.85,
            )
        )

        graph.add_node(
            ModelLineageNode(
                pattern_id=pattern_v2,
                pattern_name="api_debug_v2",
                version=2,
                status=NodeStatus.DEPRECATED,
                usage_count=150,
                success_rate=0.90,
            )
        )

        graph.add_node(
            ModelLineageNode(
                pattern_id=pattern_v3,
                pattern_name="api_debug_v3",
                version=3,
                status=NodeStatus.ACTIVE,
                usage_count=200,
                success_rate=0.95,
            )
        )

        # Create edges
        graph.add_edge(
            ModelLineageEdge(
                source_pattern_id=pattern_v1,
                target_pattern_id=pattern_v2,
                relation_type=LineageRelationType.DERIVED_FROM,
            )
        )

        graph.add_edge(
            ModelLineageEdge(
                source_pattern_id=pattern_v2,
                target_pattern_id=pattern_v3,
                relation_type=LineageRelationType.DERIVED_FROM,
            )
        )

        return graph

    def test_create_interactive_graph(self, sample_lineage_graph):
        """Test creating interactive lineage graph."""
        viz = LineageGraphVisualizer(layout_algorithm="spring")

        fig = viz.create_interactive_graph(
            sample_lineage_graph, title="Test Lineage Graph"
        )

        assert isinstance(fig, go.Figure)
        assert fig.layout.title.text == "Test Lineage Graph"
        assert len(fig.data) > 0  # Should have traces

    def test_create_lineage_summary(self, sample_lineage_graph):
        """Test creating lineage summary statistics."""
        viz = LineageGraphVisualizer()

        summary = viz.create_lineage_summary(sample_lineage_graph)

        assert summary["total_nodes"] == 3
        assert summary["total_edges"] == 2
        assert summary["active_patterns"] == 1
        assert summary["deprecated_patterns"] == 2

    def test_export_graph_html(self, sample_lineage_graph, tmp_path):
        """Test exporting graph to HTML."""
        viz = LineageGraphVisualizer()

        fig = viz.create_interactive_graph(sample_lineage_graph)
        filepath = tmp_path / "lineage_graph.html"

        viz.export_graph(fig, str(filepath), format="html")

        assert filepath.exists()
        assert filepath.stat().st_size > 0

    def test_filter_graph_by_focus(self, sample_lineage_graph):
        """Test filtering graph by focus pattern."""
        viz = LineageGraphVisualizer()

        pattern_v2 = UUID("660e8400-e29b-41d4-a716-446655440000")

        fig = viz.create_interactive_graph(
            sample_lineage_graph, focus_pattern_id=pattern_v2, title="Filtered Graph"
        )

        assert isinstance(fig, go.Figure)


class TestUsageAnalyticsCharts:
    """Tests for usage analytics charts."""

    @pytest.fixture
    def sample_usage_metrics(self) -> list[ModelPatternUsageMetrics]:
        """Create sample usage metrics."""
        metrics = []
        base_date = date(2025, 10, 1)

        for i in range(7):
            metrics.append(
                ModelPatternUsageMetrics(
                    pattern_id=uuid4(),
                    pattern_name="api_debug_pattern",
                    metrics_date=base_date + timedelta(days=i),
                    execution_count=40 + i * 5,
                    success_count=35 + i * 4,
                    failure_count=5 + i,
                    success_rate=(35 + i * 4) / (40 + i * 5),
                    context_breakdown={
                        "api_development": 20 + i * 2,
                        "debugging": 20 + i * 3,
                    },
                    avg_execution_time_ms=450.0 + i * 10,
                )
            )

        return metrics

    @pytest.fixture
    def sample_performance_metrics(self) -> list[ModelPatternPerformanceMetrics]:
        """Create sample performance metrics."""
        metrics = []

        for i in range(20):
            metrics.append(
                ModelPatternPerformanceMetrics(
                    pattern_id=uuid4(),
                    pattern_name="api_debug_pattern",
                    execution_time_ms=400.0 + i * 25,
                    memory_usage_mb=100.0 + i * 5,
                    cpu_usage_percent=30.0 + i * 2,
                    http_calls=3,
                    database_queries=5,
                    cache_hits=8,
                    cache_misses=2,
                    quality_score=0.90 + i * 0.005,
                )
            )

        return metrics

    def test_create_usage_trend_chart(self, sample_usage_metrics):
        """Test creating usage trend chart."""
        viz = UsageAnalyticsCharts()

        fig = viz.create_usage_trend_chart(
            sample_usage_metrics, title="Test Usage Trends"
        )

        assert isinstance(fig, go.Figure)
        assert fig.layout.title.text == "Test Usage Trends"

    def test_create_success_rate_heatmap(self, sample_usage_metrics):
        """Test creating success rate heatmap."""
        viz = UsageAnalyticsCharts()

        fig = viz.create_success_rate_heatmap(
            sample_usage_metrics, title="Test Heatmap"
        )

        assert isinstance(fig, go.Figure)
        assert fig.layout.title.text == "Test Heatmap"

    def test_create_performance_histogram(self, sample_performance_metrics):
        """Test creating performance histogram."""
        viz = UsageAnalyticsCharts()

        fig = viz.create_performance_histogram(
            sample_performance_metrics, title="Test Performance"
        )

        assert isinstance(fig, go.Figure)
        assert fig.layout.title.text == "Test Performance"

    def test_create_top_patterns_chart(self, sample_usage_metrics):
        """Test creating top patterns chart."""
        viz = UsageAnalyticsCharts()

        fig = viz.create_top_patterns_chart(
            sample_usage_metrics, top_n=5, metric="execution_count"
        )

        assert isinstance(fig, go.Figure)

    def test_create_multi_metric_dashboard(
        self, sample_usage_metrics, sample_performance_metrics
    ):
        """Test creating multi-metric dashboard."""
        viz = UsageAnalyticsCharts()

        fig = viz.create_multi_metric_dashboard(
            sample_usage_metrics, sample_performance_metrics, title="Test Dashboard"
        )

        assert isinstance(fig, go.Figure)
        assert fig.layout.title.text == "Test Dashboard"


class TestFeedbackAnalysisView:
    """Tests for feedback analysis view."""

    @pytest.fixture
    def sample_feedbacks(self) -> list[ModelPatternFeedback]:
        """Create sample feedbacks."""
        feedbacks = []

        sentiments = [
            FeedbackSentiment.POSITIVE,
            FeedbackSentiment.NEUTRAL,
            FeedbackSentiment.NEGATIVE,
        ]

        for i in range(9):
            feedbacks.append(
                ModelPatternFeedback(
                    pattern_id=uuid4(),
                    pattern_name="api_debug_pattern",
                    sentiment=sentiments[i % 3],
                    feedback_text=f"Feedback {i}",
                    success_confirmed=i % 2 == 0,
                    quality_rating=3.0 + (i % 3),
                )
            )

        return feedbacks

    @pytest.fixture
    def sample_improvements(self) -> list[ModelPatternImprovement]:
        """Create sample improvements."""
        improvements = []

        statuses = [
            ImprovementStatus.PROPOSED,
            ImprovementStatus.VALIDATED,
            ImprovementStatus.APPLIED,
        ]
        priorities = ["low", "medium", "high", "critical"]

        for i in range(12):
            improvements.append(
                ModelPatternImprovement(
                    pattern_id=uuid4(),
                    pattern_name="api_debug_pattern",
                    status=statuses[i % 3],
                    improvement_type="performance" if i % 2 == 0 else "accuracy",
                    description=f"Improvement {i}",
                    source="user_feedback",
                    priority=priorities[i % 4],
                    impact_estimate="Medium impact",
                )
            )

        return improvements

    def test_create_sentiment_distribution(self, sample_feedbacks):
        """Test creating sentiment distribution."""
        viz = FeedbackAnalysisView()

        fig = viz.create_sentiment_distribution(
            sample_feedbacks, title="Test Sentiment"
        )

        assert isinstance(fig, go.Figure)
        assert fig.layout.title.text == "Test Sentiment"

    def test_create_feedback_timeline(self, sample_feedbacks):
        """Test creating feedback timeline."""
        viz = FeedbackAnalysisView()

        fig = viz.create_feedback_timeline(sample_feedbacks, title="Test Timeline")

        assert isinstance(fig, go.Figure)

    def test_create_improvement_pipeline(self, sample_improvements):
        """Test creating improvement pipeline."""
        viz = FeedbackAnalysisView()

        fig = viz.create_improvement_pipeline(
            sample_improvements, title="Test Pipeline"
        )

        assert isinstance(fig, go.Figure)

    def test_create_improvement_priority_breakdown(self, sample_improvements):
        """Test creating priority breakdown."""
        viz = FeedbackAnalysisView()

        fig = viz.create_improvement_priority_breakdown(
            sample_improvements, title="Test Priority"
        )

        assert isinstance(fig, go.Figure)

    def test_create_feedback_dashboard(self, sample_feedbacks, sample_improvements):
        """Test creating comprehensive feedback dashboard."""
        viz = FeedbackAnalysisView()

        fig = viz.create_feedback_dashboard(
            sample_feedbacks, sample_improvements, title="Test Feedback Dashboard"
        )

        assert isinstance(fig, go.Figure)


class TestRealtimeMetricsStreamer:
    """Tests for real-time metrics streamer."""

    @pytest.mark.asyncio
    async def test_publish_and_receive_metric(self):
        """Test publishing and receiving metrics."""
        from ..dashboard.visualizations.realtime_metrics import RealtimeMetric

        streamer = RealtimeMetricsStreamer()

        # Publish metric
        metric = RealtimeMetric(
            metric_type="execution",
            pattern_name="test_pattern",
            value=1,
        )

        await streamer.publish_metric(metric)

        # Check buffer
        recent = streamer.get_recent_metrics(count=1)
        assert len(recent) == 1
        assert recent[0].metric_type == "execution"

    @pytest.mark.asyncio
    async def test_stream_metrics(self):
        """Test streaming metrics."""
        from ..dashboard.visualizations.realtime_metrics import RealtimeMetric

        streamer = RealtimeMetricsStreamer(update_interval_seconds=1)

        # Start stream
        metric_stream = streamer.stream_metrics()

        # Publish metric
        metric = RealtimeMetric(
            metric_type="test",
            value=1,
        )
        await streamer.publish_metric(metric)

        # Receive metric
        received = await anext(metric_stream)
        assert received.metric_type in ["test", "heartbeat"]

    @pytest.mark.asyncio
    async def test_get_metrics_summary(self):
        """Test getting metrics summary."""
        streamer = RealtimeMetricsStreamer()

        summary = await streamer.get_metrics_summary()

        assert summary.active_patterns > 0
        assert summary.total_executions_today >= 0
        assert 0.0 <= summary.avg_success_rate <= 1.0


class TestDashboardApp:
    """Tests for main dashboard application."""

    @pytest.fixture
    def dashboard_app(self, tmp_path):
        """Create dashboard app for testing."""
        return DashboardApp(output_dir=tmp_path)

    def test_dashboard_initialization(self, dashboard_app):
        """Test dashboard app initialization."""
        assert dashboard_app.lineage_viz is not None
        assert dashboard_app.usage_viz is not None
        assert dashboard_app.feedback_viz is not None
        assert dashboard_app.app is not None

    def test_generate_full_dashboard(
        self,
        dashboard_app,
        sample_lineage_graph,
        sample_usage_metrics,
        sample_performance_metrics,
        sample_feedbacks,
        sample_improvements,
    ):
        """Test generating full dashboard."""
        dashboard = dashboard_app.generate_full_dashboard(
            lineage_graph=sample_lineage_graph,
            usage_metrics=sample_usage_metrics,
            performance_metrics=sample_performance_metrics,
            feedbacks=sample_feedbacks,
            improvements=sample_improvements,
            title="Test Dashboard",
        )

        assert "title" in dashboard
        assert "lineage" in dashboard
        assert "usage" in dashboard
        assert "feedback" in dashboard

    def test_export_dashboard_html(
        self,
        dashboard_app,
        sample_lineage_graph,
        sample_usage_metrics,
        sample_performance_metrics,
        sample_feedbacks,
        sample_improvements,
        tmp_path,
    ):
        """Test exporting dashboard to HTML."""
        dashboard = dashboard_app.generate_full_dashboard(
            lineage_graph=sample_lineage_graph,
            usage_metrics=sample_usage_metrics,
            performance_metrics=sample_performance_metrics,
            feedbacks=sample_feedbacks,
            improvements=sample_improvements,
        )

        filepath = tmp_path / "test_dashboard.html"
        result_path = dashboard_app.export_dashboard_html(dashboard, filepath)

        assert result_path.exists()
        assert result_path.stat().st_size > 0

        # Verify HTML content
        html_content = result_path.read_text()
        assert "<html>" in html_content
        assert "Pattern Lineage" in html_content


# Fixtures available to all tests
@pytest.fixture
def sample_lineage_graph() -> ModelLineageGraph:
    """Create sample lineage graph for all tests."""
    graph = ModelLineageGraph()

    pattern_v1 = uuid4()
    pattern_v2 = uuid4()

    graph.add_node(
        ModelLineageNode(
            pattern_id=pattern_v1,
            pattern_name="test_pattern_v1",
            version=1,
            status=NodeStatus.ACTIVE,
            usage_count=50,
            success_rate=0.90,
        )
    )

    graph.add_node(
        ModelLineageNode(
            pattern_id=pattern_v2,
            pattern_name="test_pattern_v2",
            version=2,
            status=NodeStatus.ACTIVE,
            usage_count=75,
            success_rate=0.95,
        )
    )

    graph.add_edge(
        ModelLineageEdge(
            source_pattern_id=pattern_v1,
            target_pattern_id=pattern_v2,
            relation_type=LineageRelationType.DERIVED_FROM,
        )
    )

    return graph


@pytest.fixture
def sample_usage_metrics() -> list[ModelPatternUsageMetrics]:
    """Create sample usage metrics for all tests."""
    return [
        ModelPatternUsageMetrics(
            pattern_id=uuid4(),
            pattern_name="test_pattern",
            metrics_date=date(2025, 10, i),
            execution_count=40 + i,
            success_count=35 + i,
            failure_count=5,
            success_rate=0.875,
            context_breakdown={"test": 40 + i},
            avg_execution_time_ms=450.0,
        )
        for i in range(1, 8)
    ]


@pytest.fixture
def sample_performance_metrics() -> list[ModelPatternPerformanceMetrics]:
    """Create sample performance metrics for all tests."""
    return [
        ModelPatternPerformanceMetrics(
            pattern_id=uuid4(),
            pattern_name="test_pattern",
            execution_time_ms=400.0 + i * 10,
            memory_usage_mb=100.0,
            cpu_usage_percent=30.0,
            http_calls=3,
            database_queries=5,
        )
        for i in range(10)
    ]


@pytest.fixture
def sample_feedbacks() -> list[ModelPatternFeedback]:
    """Create sample feedbacks for all tests."""
    return [
        ModelPatternFeedback(
            pattern_id=uuid4(),
            pattern_name="test_pattern",
            sentiment=FeedbackSentiment.POSITIVE,
            feedback_text=f"Feedback {i}",
            quality_rating=4.0,
        )
        for i in range(5)
    ]


@pytest.fixture
def sample_improvements() -> list[ModelPatternImprovement]:
    """Create sample improvements for all tests."""
    return [
        ModelPatternImprovement(
            pattern_id=uuid4(),
            pattern_name="test_pattern",
            status=ImprovementStatus.PROPOSED,
            improvement_type="performance",
            description=f"Improvement {i}",
            source="user_feedback",
            priority="medium",
        )
        for i in range(5)
    ]
