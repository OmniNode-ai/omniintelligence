"""
Phase 4 Dashboard - Usage Analytics Charts

Interactive charts for pattern usage analytics.
Includes time-series, heatmaps, histograms, and trend analysis.
"""

import logging
from typing import List, Optional
from uuid import UUID, uuid4

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from src.archon_services.pattern_learning.phase4_traceability.models.model_pattern_metrics import (
    ModelPatternPerformanceMetrics,
    ModelPatternUsageMetrics,
)

logger = logging.getLogger(__name__)


# NOTE: correlation_id support enabled for tracing
class UsageAnalyticsCharts:
    """
    Usage analytics visualization charts.

    Creates interactive charts for:
    - Usage trends over time
    - Success rate heatmaps
    - Performance distributions
    - Context breakdowns
    """

    def __init__(self):
        """Initialize usage analytics charts."""
        logger.info("Initialized UsageAnalyticsCharts")

    def create_usage_trend_chart(
        self,
        metrics: List[ModelPatternUsageMetrics],
        title: str = "Pattern Usage Trends",
    ) -> go.Figure:
        """
        Create time-series chart for usage trends.

        Args:
            metrics: List of usage metrics over time
            title: Chart title

        Returns:
            Plotly Figure with usage trends
        """
        if not metrics:
            logger.warning("No metrics provided for usage trend chart")
            return self._create_empty_figure("No data available")

        # Convert to DataFrame
        df = pd.DataFrame(
            [
                {
                    "date": m.metrics_date,
                    "pattern_name": m.pattern_name,
                    "execution_count": m.execution_count,
                    "success_count": m.success_count,
                    "failure_count": m.failure_count,
                    "success_rate": m.success_rate,
                }
                for m in metrics
            ]
        )

        # Sort by date
        df = df.sort_values("date")

        # Create figure with subplots
        fig = make_subplots(
            rows=2,
            cols=1,
            subplot_titles=("Total Executions", "Success Rate"),
            vertical_spacing=0.12,
            row_heights=[0.6, 0.4],
        )

        # Group by pattern for multi-line chart
        for pattern_name in df["pattern_name"].unique():
            pattern_df = df[df["pattern_name"] == pattern_name]

            # Execution count line
            fig.add_trace(
                go.Scatter(
                    x=pattern_df["date"],
                    y=pattern_df["execution_count"],
                    mode="lines+markers",
                    name=pattern_name,
                    showlegend=True,
                ),
                row=1,
                col=1,
            )

            # Success rate line
            fig.add_trace(
                go.Scatter(
                    x=pattern_df["date"],
                    y=pattern_df["success_rate"],
                    mode="lines+markers",
                    name=pattern_name,
                    showlegend=False,
                ),
                row=2,
                col=1,
            )

        # Update layout
        fig.update_xaxes(title_text="Date", row=2, col=1)
        fig.update_yaxes(title_text="Executions", row=1, col=1)
        fig.update_yaxes(title_text="Success Rate", row=2, col=1, tickformat=".0%")

        fig.update_layout(
            title=title,
            hovermode="x unified",
            height=700,
            showlegend=True,
        )

        return fig

    def create_success_rate_heatmap(
        self,
        metrics: List[ModelPatternUsageMetrics],
        title: str = "Success Rate Heatmap",
    ) -> go.Figure:
        """
        Create heatmap showing success rates over time.

        Args:
            metrics: List of usage metrics
            title: Chart title

        Returns:
            Plotly Figure with heatmap
        """
        if not metrics:
            return self._create_empty_figure("No data available")

        # Convert to DataFrame
        df = pd.DataFrame(
            [
                {
                    "date": m.metrics_date,
                    "pattern_name": m.pattern_name,
                    "success_rate": m.success_rate,
                }
                for m in metrics
            ]
        )

        # Pivot for heatmap
        pivot_df = df.pivot(index="pattern_name", columns="date", values="success_rate")

        # Create heatmap
        fig = go.Figure(
            data=go.Heatmap(
                z=pivot_df.values,
                x=pivot_df.columns,
                y=pivot_df.index,
                colorscale="RdYlGn",
                zmid=0.75,
                zmin=0.0,
                zmax=1.0,
                text=pivot_df.values,
                texttemplate="%{text:.1%}",
                textfont={"size": 10},
                colorbar=dict(
                    title="Success Rate",
                    tickformat=".0%",
                ),
            )
        )

        fig.update_layout(
            title=title,
            xaxis_title="Date",
            yaxis_title="Pattern",
            height=max(400, len(pivot_df) * 40),
        )

        return fig

    def create_performance_histogram(
        self,
        metrics: List[ModelPatternPerformanceMetrics],
        title: str = "Performance Distribution",
    ) -> go.Figure:
        """
        Create histogram showing performance distribution.

        Args:
            metrics: List of performance metrics
            title: Chart title

        Returns:
            Plotly Figure with histogram
        """
        if not metrics:
            return self._create_empty_figure("No data available")

        # Convert to DataFrame
        df = pd.DataFrame(
            [
                {
                    "pattern_name": m.pattern_name,
                    "execution_time_ms": m.execution_time_ms,
                }
                for m in metrics
            ]
        )

        # Create histogram
        fig = px.histogram(
            df,
            x="execution_time_ms",
            color="pattern_name",
            nbins=50,
            marginal="box",
            title=title,
            labels={"execution_time_ms": "Execution Time (ms)"},
        )

        fig.update_layout(
            showlegend=True,
            height=500,
            bargap=0.1,
        )

        return fig

    def create_context_breakdown_pie(
        self,
        usage_metrics: ModelPatternUsageMetrics,
        title: Optional[str] = None,
    ) -> go.Figure:
        """
        Create pie chart showing context breakdown.

        Args:
            usage_metrics: Usage metrics with context breakdown
            title: Chart title

        Returns:
            Plotly Figure with pie chart
        """
        if not usage_metrics.context_breakdown:
            return self._create_empty_figure("No context data available")

        if title is None:
            title = f"Context Breakdown - {usage_metrics.pattern_name}"

        # Create pie chart
        fig = go.Figure(
            data=[
                go.Pie(
                    labels=list(usage_metrics.context_breakdown.keys()),
                    values=list(usage_metrics.context_breakdown.values()),
                    hole=0.3,
                )
            ]
        )

        fig.update_layout(
            title=title,
            height=400,
        )

        return fig

    def create_top_patterns_chart(
        self,
        metrics: List[ModelPatternUsageMetrics],
        top_n: int = 10,
        metric: str = "execution_count",
        title: str = "Top Patterns",
    ) -> go.Figure:
        """
        Create bar chart showing top N patterns by metric.

        Args:
            metrics: List of usage metrics
            top_n: Number of top patterns to show
            metric: Metric to sort by ("execution_count", "success_rate")
            title: Chart title

        Returns:
            Plotly Figure with bar chart
        """
        if not metrics:
            return self._create_empty_figure("No data available")

        # Aggregate by pattern
        pattern_metrics = {}
        for m in metrics:
            if m.pattern_name not in pattern_metrics:
                pattern_metrics[m.pattern_name] = {
                    "execution_count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                }

            pattern_metrics[m.pattern_name]["execution_count"] += m.execution_count
            pattern_metrics[m.pattern_name]["success_count"] += m.success_count
            pattern_metrics[m.pattern_name]["failure_count"] += m.failure_count

        # Calculate success rates
        for name, data in pattern_metrics.items():
            total = data["execution_count"]
            if total > 0:
                data["success_rate"] = data["success_count"] / total
            else:
                data["success_rate"] = 0.0

        # Convert to DataFrame and sort
        df = pd.DataFrame(
            [{"pattern_name": name, **data} for name, data in pattern_metrics.items()]
        )

        df = df.sort_values(metric, ascending=False).head(top_n)

        # Create bar chart
        fig = go.Figure()

        if metric == "execution_count":
            fig.add_trace(
                go.Bar(
                    x=df["pattern_name"],
                    y=df["execution_count"],
                    name="Total Executions",
                    marker_color="rgb(55, 83, 109)",
                )
            )
        else:
            fig.add_trace(
                go.Bar(
                    x=df["pattern_name"],
                    y=df["success_rate"],
                    name="Success Rate",
                    marker_color="rgb(26, 118, 255)",
                    text=df["success_rate"],
                    texttemplate="%{text:.1%}",
                    textposition="auto",
                )
            )

        fig.update_layout(
            title=title,
            xaxis_title="Pattern",
            yaxis_title=metric.replace("_", " ").title(),
            height=500,
            showlegend=False,
        )

        if metric == "success_rate":
            fig.update_yaxes(tickformat=".0%")

        return fig

    def create_performance_comparison(
        self,
        metrics: List[ModelPatternPerformanceMetrics],
        title: str = "Performance Comparison",
    ) -> go.Figure:
        """
        Create box plot comparing performance across patterns.

        Args:
            metrics: List of performance metrics
            title: Chart title

        Returns:
            Plotly Figure with box plot
        """
        if not metrics:
            return self._create_empty_figure("No data available")

        # Convert to DataFrame
        df = pd.DataFrame(
            [
                {
                    "pattern_name": m.pattern_name,
                    "execution_time_ms": m.execution_time_ms,
                }
                for m in metrics
            ]
        )

        # Create box plot
        fig = px.box(
            df,
            x="pattern_name",
            y="execution_time_ms",
            title=title,
            labels={
                "execution_time_ms": "Execution Time (ms)",
                "pattern_name": "Pattern",
            },
        )

        fig.update_layout(
            height=500,
            showlegend=False,
        )

        return fig

    def create_multi_metric_dashboard(
        self,
        usage_metrics: List[ModelPatternUsageMetrics],
        performance_metrics: List[ModelPatternPerformanceMetrics],
        title: str = "Pattern Analytics Dashboard",
    ) -> go.Figure:
        """
        Create comprehensive dashboard with multiple metrics.

        Args:
            usage_metrics: List of usage metrics
            performance_metrics: List of performance metrics
            title: Dashboard title

        Returns:
            Plotly Figure with multi-panel dashboard
        """
        # Create subplots
        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "Usage Trend",
                "Success Rate",
                "Performance Distribution",
                "Top Patterns",
            ),
            specs=[
                [{"type": "scatter"}, {"type": "scatter"}],
                [{"type": "histogram"}, {"type": "bar"}],
            ],
            vertical_spacing=0.12,
            horizontal_spacing=0.10,
        )

        if usage_metrics:
            # Usage trend
            df_usage = pd.DataFrame(
                [
                    {
                        "date": m.metrics_date,
                        "execution_count": m.execution_count,
                    }
                    for m in usage_metrics
                ]
            ).sort_values("date")

            fig.add_trace(
                go.Scatter(
                    x=df_usage["date"],
                    y=df_usage["execution_count"],
                    mode="lines+markers",
                    name="Executions",
                ),
                row=1,
                col=1,
            )

            # Success rate
            df_success = pd.DataFrame(
                [
                    {
                        "date": m.metrics_date,
                        "success_rate": m.success_rate,
                    }
                    for m in usage_metrics
                ]
            ).sort_values("date")

            fig.add_trace(
                go.Scatter(
                    x=df_success["date"],
                    y=df_success["success_rate"],
                    mode="lines+markers",
                    name="Success Rate",
                    line=dict(color="green"),
                ),
                row=1,
                col=2,
            )

        if performance_metrics:
            # Performance histogram
            execution_times = [m.execution_time_ms for m in performance_metrics]

            fig.add_trace(
                go.Histogram(
                    x=execution_times,
                    nbinsx=30,
                    name="Performance",
                ),
                row=2,
                col=1,
            )

            # Top patterns
            if usage_metrics:
                pattern_counts = {}
                for m in usage_metrics:
                    pattern_counts[m.pattern_name] = (
                        pattern_counts.get(m.pattern_name, 0) + m.execution_count
                    )

                top_patterns = sorted(
                    pattern_counts.items(), key=lambda x: x[1], reverse=True
                )[:5]

                fig.add_trace(
                    go.Bar(
                        x=[p[0] for p in top_patterns],
                        y=[p[1] for p in top_patterns],
                        name="Top Patterns",
                    ),
                    row=2,
                    col=2,
                )

        # Update layout
        fig.update_layout(
            title=title,
            height=800,
            showlegend=False,
        )

        return fig

    def _create_empty_figure(self, message: str) -> go.Figure:
        """Create empty figure with message."""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=16),
        )
        fig.update_layout(
            xaxis=dict(showgrid=False, showticklabels=False),
            yaxis=dict(showgrid=False, showticklabels=False),
            height=400,
        )
        return fig
