"""
Phase 4 Traceability - Dashboard Components

Interactive visualization dashboard for pattern analytics.
Includes lineage graphs, usage charts, and feedback analysis.
"""

from uuid import UUID, uuid4

from src.archon_services.pattern_learning.phase4_traceability.dashboard.app import (
    DashboardApp,
)
from src.archon_services.pattern_learning.phase4_traceability.dashboard.visualizations.feedback_view import (
    FeedbackAnalysisView,
)
from src.archon_services.pattern_learning.phase4_traceability.dashboard.visualizations.lineage_graph import (
    LineageGraphVisualizer,
)
from src.archon_services.pattern_learning.phase4_traceability.dashboard.visualizations.realtime_metrics import (
    RealtimeMetricsStreamer,
)
from src.archon_services.pattern_learning.phase4_traceability.dashboard.visualizations.usage_charts import (
    UsageAnalyticsCharts,
)

__all__ = [
    "LineageGraphVisualizer",
    "UsageAnalyticsCharts",
    "FeedbackAnalysisView",
    "RealtimeMetricsStreamer",
    "DashboardApp",
]
