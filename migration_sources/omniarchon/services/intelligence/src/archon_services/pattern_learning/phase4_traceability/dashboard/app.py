"""
Phase 4 Dashboard - Main Application

FastAPI-based dashboard application for pattern analytics.
Provides API endpoints and HTML export capabilities.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from src.archon_services.pattern_learning.phase4_traceability.dashboard.visualizations.feedback_view import (
    FeedbackAnalysisView,
)
from src.archon_services.pattern_learning.phase4_traceability.dashboard.visualizations.lineage_graph import (
    LineageGraphVisualizer,
)
from src.archon_services.pattern_learning.phase4_traceability.dashboard.visualizations.realtime_metrics import (
    get_realtime_streamer,
)
from src.archon_services.pattern_learning.phase4_traceability.dashboard.visualizations.usage_charts import (
    UsageAnalyticsCharts,
)
from src.archon_services.pattern_learning.phase4_traceability.models.model_lineage_graph import (
    ModelLineageGraph,
)
from src.archon_services.pattern_learning.phase4_traceability.models.model_pattern_feedback import (
    ModelPatternFeedback,
    ModelPatternImprovement,
)
from src.archon_services.pattern_learning.phase4_traceability.models.model_pattern_metrics import (
    ModelPatternPerformanceMetrics,
    ModelPatternUsageMetrics,
)

logger = logging.getLogger(__name__)


class DashboardExportRequest(BaseModel):
    """Request for dashboard export."""

    export_format: str = "html"  # html, pdf, png, svg
    include_sections: List[str] = ["lineage", "usage", "feedback", "metrics"]
    time_window_days: int = 30
    title: str = "Pattern Analytics Dashboard"


class DashboardApp:
    """
    Main dashboard application.

    Provides:
    - API endpoints for dashboard data
    - Interactive visualizations
    - Export capabilities (HTML, PDF, PNG)
    - Real-time metrics streaming
    """

    def __init__(
        self,
        output_dir: Path = Path("./dashboard_exports"),
    ):
        """
        Initialize dashboard application.

        Args:
            output_dir: Directory for exported files
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize visualizers
        self.lineage_viz = LineageGraphVisualizer(layout_algorithm="spring")
        self.usage_viz = UsageAnalyticsCharts()
        self.feedback_viz = FeedbackAnalysisView()
        self.realtime_streamer = get_realtime_streamer()

        # Initialize FastAPI app
        self.app = FastAPI(
            title="Pattern Analytics Dashboard",
            description="Interactive analytics dashboard for pattern learning system",
            version="1.0.0",
        )

        self._register_routes()

        logger.info(f"Initialized DashboardApp (output_dir={output_dir})")

    def _register_routes(self) -> None:
        """Register FastAPI routes."""

        @self.app.get("/", response_class=HTMLResponse)
        async def root():
            """Dashboard home page."""
            return self._generate_dashboard_html()

        @self.app.get("/api/lineage/{pattern_id}")
        async def get_lineage_graph(pattern_id: UUID):
            """Get lineage graph for pattern."""
            # This would query the database in production
            raise HTTPException(
                status_code=501, detail="Not implemented - connect to database"
            )

        @self.app.get("/api/usage")
        async def get_usage_metrics(
            time_window_days: int = Query(default=30, ge=1, le=365),
            pattern_id: Optional[UUID] = None,
        ):
            """Get usage metrics."""
            raise HTTPException(
                status_code=501, detail="Not implemented - connect to database"
            )

        @self.app.get("/api/feedback")
        async def get_feedback_data(
            time_window_days: int = Query(default=30, ge=1, le=365),
            pattern_id: Optional[UUID] = None,
        ):
            """Get feedback data."""
            raise HTTPException(
                status_code=501, detail="Not implemented - connect to database"
            )

        @self.app.get("/api/metrics/realtime")
        async def stream_realtime_metrics(pattern_id: Optional[UUID] = None):
            """Stream real-time metrics via SSE."""
            return StreamingResponse(
                self.realtime_streamer.stream_metrics_sse(pattern_id=pattern_id),
                media_type="text/event-stream",
            )

        @self.app.get("/api/metrics/summary")
        async def get_metrics_summary():
            """Get real-time metrics summary."""
            summary = await self.realtime_streamer.get_metrics_summary()
            return summary

        @self.app.post("/api/export")
        async def export_dashboard(request: DashboardExportRequest):
            """Export dashboard to file."""
            filepath = await self._export_dashboard(request)
            return {"filepath": str(filepath), "format": request.export_format}

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "timestamp": datetime.now().isoformat()}

    def generate_full_dashboard(
        self,
        lineage_graph: ModelLineageGraph,
        usage_metrics: List[ModelPatternUsageMetrics],
        performance_metrics: List[ModelPatternPerformanceMetrics],
        feedbacks: List[ModelPatternFeedback],
        improvements: List[ModelPatternImprovement],
        title: str = "Pattern Analytics Dashboard",
    ) -> Dict[str, Any]:
        """
        Generate complete dashboard with all visualizations.

        Args:
            lineage_graph: Pattern lineage graph
            usage_metrics: Usage metrics
            performance_metrics: Performance metrics
            feedbacks: Pattern feedbacks
            improvements: Pattern improvements
            title: Dashboard title

        Returns:
            Dictionary with all generated figures
        """
        logger.info("Generating full dashboard")

        dashboard = {
            "title": title,
            "generated_at": datetime.now().isoformat(),
            "lineage": {},
            "usage": {},
            "feedback": {},
        }

        # Lineage visualizations
        if lineage_graph:
            dashboard["lineage"]["graph"] = self.lineage_viz.create_interactive_graph(
                lineage_graph,
                title="Pattern Lineage Graph",
            )
            dashboard["lineage"]["summary"] = self.lineage_viz.create_lineage_summary(
                lineage_graph
            )

        # Usage visualizations
        if usage_metrics:
            dashboard["usage"]["trend"] = self.usage_viz.create_usage_trend_chart(
                usage_metrics,
                title="Usage Trends",
            )
            dashboard["usage"]["heatmap"] = self.usage_viz.create_success_rate_heatmap(
                usage_metrics,
                title="Success Rate Heatmap",
            )
            dashboard["usage"]["top_patterns"] = (
                self.usage_viz.create_top_patterns_chart(
                    usage_metrics,
                    top_n=10,
                    title="Top 10 Patterns",
                )
            )

        if performance_metrics:
            dashboard["usage"]["performance"] = (
                self.usage_viz.create_performance_histogram(
                    performance_metrics,
                    title="Performance Distribution",
                )
            )

        # Feedback visualizations
        if feedbacks:
            dashboard["feedback"]["sentiment"] = (
                self.feedback_viz.create_sentiment_distribution(
                    feedbacks,
                    title="Feedback Sentiment",
                )
            )
            dashboard["feedback"]["timeline"] = (
                self.feedback_viz.create_feedback_timeline(
                    feedbacks,
                    title="Feedback Timeline",
                )
            )
            dashboard["feedback"]["table"] = (
                self.feedback_viz.create_feedback_summary_table(
                    feedbacks,
                    max_rows=20,
                )
            )

        if improvements:
            dashboard["feedback"]["pipeline"] = (
                self.feedback_viz.create_improvement_pipeline(
                    improvements,
                    title="Improvement Pipeline",
                )
            )
            dashboard["feedback"]["priority"] = (
                self.feedback_viz.create_improvement_priority_breakdown(
                    improvements,
                    title="Improvements by Priority",
                )
            )
            dashboard["feedback"]["improvements_table"] = (
                self.feedback_viz.create_improvement_summary_table(
                    improvements,
                    max_rows=20,
                )
            )

        logger.info(f"Generated dashboard with {len(dashboard)} sections")
        return dashboard

    def export_dashboard_html(
        self,
        dashboard: Dict[str, Any],
        filepath: Path,
    ) -> Path:
        """
        Export dashboard to HTML file.

        Args:
            dashboard: Dashboard data from generate_full_dashboard
            filepath: Output file path

        Returns:
            Path to exported file
        """
        logger.info(f"Exporting dashboard to HTML: {filepath}")

        html_parts = [
            f"<html><head><title>{dashboard['title']}</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            "h1 { color: #2c3e50; }",
            "h2 { color: #34495e; margin-top: 30px; }",
            ".section { margin-bottom: 40px; }",
            ".timestamp { color: #7f8c8d; font-size: 0.9em; }",
            "</style>",
            "<script src='https://cdn.plot.ly/plotly-latest.min.js'></script>",
            "</head><body>",
            f"<h1>{dashboard['title']}</h1>",
            f"<p class='timestamp'>Generated: {dashboard['generated_at']}</p>",
        ]

        # Add lineage section
        if "lineage" in dashboard:
            html_parts.append("<div class='section'><h2>Pattern Lineage</h2>")
            if "graph" in dashboard["lineage"]:
                html_parts.append(
                    dashboard["lineage"]["graph"].to_html(
                        include_plotlyjs=False, div_id="lineage_graph"
                    )
                )
            if "summary" in dashboard["lineage"]:
                summary = dashboard["lineage"]["summary"]
                html_parts.append(f"<p>Total Patterns: {summary['total_nodes']}</p>")
                html_parts.append(
                    f"<p>Total Relationships: {summary['total_edges']}</p>"
                )
                html_parts.append(
                    f"<p>Active Patterns: {summary['active_patterns']}</p>"
                )
            html_parts.append("</div>")

        # Add usage section
        if "usage" in dashboard:
            html_parts.append("<div class='section'><h2>Usage Analytics</h2>")
            for viz_name, viz in dashboard["usage"].items():
                if hasattr(viz, "to_html"):
                    html_parts.append(
                        viz.to_html(include_plotlyjs=False, div_id=f"usage_{viz_name}")
                    )
            html_parts.append("</div>")

        # Add feedback section
        if "feedback" in dashboard:
            html_parts.append("<div class='section'><h2>Feedback Analysis</h2>")
            for viz_name, viz in dashboard["feedback"].items():
                if hasattr(viz, "to_html"):
                    html_parts.append(
                        viz.to_html(
                            include_plotlyjs=False, div_id=f"feedback_{viz_name}"
                        )
                    )
            html_parts.append("</div>")

        html_parts.append("</body></html>")

        # Write to file
        filepath.write_text("\n".join(html_parts))

        logger.info(f"Exported dashboard to {filepath}")
        return filepath

    async def _export_dashboard(
        self, request: DashboardExportRequest, correlation_id: Optional[UUID] = None
    ) -> Path:
        """
        Export dashboard based on request.

        Args:
            request: Export request

        Returns:
            Path to exported file
        """
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dashboard_{timestamp}.{request.export_format}"
        self.output_dir / filename

        # This would query database and generate dashboard in production
        # For now, return placeholder
        raise HTTPException(
            status_code=501, detail="Export not implemented - connect to database"
        )

    def _generate_dashboard_html(self) -> str:
        """Generate dashboard home page HTML."""
        return """
        <html>
        <head>
            <title>Pattern Analytics Dashboard</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 40px;
                    background-color: #f5f5f5;
                }
                .container {
                    max-width: 800px;
                    margin: 0 auto;
                    background-color: white;
                    padding: 40px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }
                h1 { color: #2c3e50; }
                .endpoints {
                    margin-top: 30px;
                }
                .endpoint {
                    padding: 10px;
                    margin: 10px 0;
                    background-color: #ecf0f1;
                    border-radius: 4px;
                }
                code {
                    background-color: #34495e;
                    color: white;
                    padding: 2px 6px;
                    border-radius: 3px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Pattern Analytics Dashboard</h1>
                <p>Interactive analytics for pattern learning system.</p>

                <div class="endpoints">
                    <h2>Available Endpoints</h2>

                    <div class="endpoint">
                        <strong>GET</strong> <code>/api/lineage/{pattern_id}</code>
                        <p>Get lineage graph for pattern</p>
                    </div>

                    <div class="endpoint">
                        <strong>GET</strong> <code>/api/usage</code>
                        <p>Get usage metrics</p>
                    </div>

                    <div class="endpoint">
                        <strong>GET</strong> <code>/api/feedback</code>
                        <p>Get feedback data</p>
                    </div>

                    <div class="endpoint">
                        <strong>GET</strong> <code>/api/metrics/realtime</code>
                        <p>Stream real-time metrics (SSE)</p>
                    </div>

                    <div class="endpoint">
                        <strong>GET</strong> <code>/api/metrics/summary</code>
                        <p>Get real-time metrics summary</p>
                    </div>

                    <div class="endpoint">
                        <strong>POST</strong> <code>/api/export</code>
                        <p>Export dashboard to file</p>
                    </div>

                    <div class="endpoint">
                        <strong>GET</strong> <code>/docs</code>
                        <p>API documentation (Swagger UI)</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """


def create_dashboard_app() -> DashboardApp:
    """
    Create and configure dashboard application.

    Returns:
        Configured DashboardApp instance
    """
    return DashboardApp()
