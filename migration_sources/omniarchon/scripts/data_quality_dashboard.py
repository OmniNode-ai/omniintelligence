#!/usr/bin/env python3
"""
Data Quality Dashboard
======================

Real-time dashboard for monitoring orphan count, tree health, and ingestion metrics.

Features:
  - Display current orphan count (real-time)
  - Show orphan count trend graph (last 24 hours)
  - Display orphan growth rate (per hour/day)
  - Show tree health metrics: PROJECT nodes, DIRECTORY nodes, CONTAINS relationships
  - Display ingestion metrics: files processed, success rate, failure rate
  - Provide orphan remediation suggestions
  - Auto-refresh dashboard (optional)

Usage:
    # Display dashboard once
    python3 scripts/data_quality_dashboard.py

    # Auto-refresh every 30 seconds
    python3 scripts/data_quality_dashboard.py --refresh 30

    # Compact view (no graphs)
    python3 scripts/data_quality_dashboard.py --compact

    # JSON output for automation
    python3 scripts/data_quality_dashboard.py --json
"""

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Suppress INFO logs for cleaner dashboard
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class TreeHealthMetrics:
    """Tree graph health metrics."""

    project_nodes: int
    directory_nodes: int
    contains_relationships: int
    orphan_count: int
    total_files: int
    orphan_percentage: float
    health_status: str  # "healthy", "degraded", "critical"


@dataclass
class IngestionMetrics:
    """Ingestion pipeline metrics."""

    total_files_processed: int
    successful_ingestions: int
    failed_ingestions: int
    success_rate: float
    last_ingestion_time: Optional[str]


@dataclass
class DashboardData:
    """Complete dashboard data."""

    timestamp: str
    tree_health: TreeHealthMetrics
    ingestion_metrics: IngestionMetrics
    orphan_trend_24h: List[Dict]
    growth_rate_per_hour: Optional[float]
    growth_rate_per_day: Optional[float]
    recommendations: List[str]


class DataQualityDashboard:
    """Data quality monitoring dashboard."""

    def __init__(self):
        self.memgraph_uri = os.getenv("MEMGRAPH_URI", "bolt://localhost:7687")
        self.metrics_file = (
            Path(__file__).parent.parent / "logs" / "orphan_metrics.json"
        )

    def get_tree_health(self) -> TreeHealthMetrics:
        """Get current tree health metrics."""
        try:
            driver = GraphDatabase.driver(self.memgraph_uri)

            with driver.session() as session:
                # Get PROJECT node count
                project_count = session.run(
                    "MATCH (p:PROJECT) RETURN count(p) as count"
                ).single()["count"]

                # Get DIRECTORY node count
                directory_count = session.run(
                    "MATCH (d:DIRECTORY) RETURN count(d) as count"
                ).single()["count"]

                # Get CONTAINS relationship count
                contains_count = session.run(
                    "MATCH ()-[r:CONTAINS]->() RETURN count(r) as count"
                ).single()["count"]

                # Get orphaned FILE nodes
                orphan_count = session.run(
                    """
                    MATCH (f:FILE)
                    WHERE f.entity_id STARTS WITH 'archon://' OR f.path CONTAINS '/'
                    OPTIONAL MATCH orphan_path = (f)<-[:CONTAINS*]-(:PROJECT)
                    WITH f, orphan_path
                    WHERE orphan_path IS NULL
                    RETURN count(f) as count
                    """
                ).single()["count"]

                # Get total FILE count
                total_files = session.run(
                    """
                    MATCH (f:FILE)
                    WHERE f.entity_id STARTS WITH 'archon://' OR f.path CONTAINS '/'
                    RETURN count(f) as count
                    """
                ).single()["count"]

            driver.close()

            orphan_percentage = (
                (orphan_count / total_files * 100) if total_files > 0 else 0
            )

            # Determine health status
            if orphan_count == 0 and project_count > 0 and directory_count > 0:
                health_status = "healthy"
            elif orphan_percentage < 10:
                health_status = "degraded"
            else:
                health_status = "critical"

            return TreeHealthMetrics(
                project_nodes=project_count,
                directory_nodes=directory_count,
                contains_relationships=contains_count,
                orphan_count=orphan_count,
                total_files=total_files,
                orphan_percentage=round(orphan_percentage, 2),
                health_status=health_status,
            )

        except Exception as e:
            logger.error(f"Failed to get tree health: {e}")
            raise

    def get_ingestion_metrics(self) -> IngestionMetrics:
        """Get ingestion pipeline metrics."""
        try:
            driver = GraphDatabase.driver(self.memgraph_uri)

            with driver.session() as session:
                # Get total FILE count as proxy for successful ingestions
                total_files = session.run(
                    """
                    MATCH (f:FILE)
                    WHERE f.entity_id STARTS WITH 'archon://' OR f.path CONTAINS '/'
                    RETURN count(f) as count
                    """
                ).single()["count"]

                # Get files with missing metadata as proxy for failed ingestions
                failed_count = session.run(
                    """
                    MATCH (f:FILE)
                    WHERE (f.entity_id STARTS WITH 'archon://' OR f.path CONTAINS '/')
                      AND (f.language IS NULL OR f.project_name IS NULL)
                    RETURN count(f) as count
                    """
                ).single()["count"]

            driver.close()

            successful = total_files - failed_count
            success_rate = (successful / total_files * 100) if total_files > 0 else 0

            return IngestionMetrics(
                total_files_processed=total_files,
                successful_ingestions=successful,
                failed_ingestions=failed_count,
                success_rate=round(success_rate, 2),
                last_ingestion_time=None,  # Not tracked in current schema
            )

        except Exception as e:
            logger.error(f"Failed to get ingestion metrics: {e}")
            raise

    def get_orphan_trend_24h(self) -> List[Dict]:
        """Get orphan count trend for last 24 hours."""
        if not self.metrics_file.exists():
            return []

        try:
            with open(self.metrics_file, "r") as f:
                data = json.load(f)
                all_metrics = data.get("metrics", [])

            # Filter to last 24 hours
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            recent_metrics = []

            for metric in all_metrics:
                timestamp = datetime.fromisoformat(metric["timestamp"])
                if timestamp >= cutoff_time:
                    recent_metrics.append(
                        {
                            "timestamp": metric["timestamp"],
                            "orphan_count": metric["orphan_count"],
                            "orphan_percentage": metric["orphan_percentage"],
                        }
                    )

            return recent_metrics

        except Exception as e:
            logger.warning(f"Failed to load orphan trend: {e}")
            return []

    def calculate_growth_rates(
        self, trend_24h: List[Dict]
    ) -> tuple[Optional[float], Optional[float]]:
        """Calculate growth rates (per hour and per day)."""
        if len(trend_24h) < 2:
            return None, None

        first = trend_24h[0]
        last = trend_24h[-1]

        first_time = datetime.fromisoformat(first["timestamp"])
        last_time = datetime.fromisoformat(last["timestamp"])

        time_diff_hours = (last_time - first_time).total_seconds() / 3600
        if time_diff_hours == 0:
            return None, None

        orphan_diff = last["orphan_count"] - first["orphan_count"]

        growth_rate_per_hour = orphan_diff / time_diff_hours
        growth_rate_per_day = growth_rate_per_hour * 24

        return round(growth_rate_per_hour, 2), round(growth_rate_per_day, 2)

    def generate_recommendations(
        self, tree_health: TreeHealthMetrics, growth_rate: Optional[float]
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        # Tree health recommendations
        if tree_health.orphan_count > 0:
            recommendations.append(
                f"⚠️  {tree_health.orphan_count:,} orphaned files detected. "
                "Run tree building to reconnect files to directory structure."
            )
            recommendations.append("Action: python3 scripts/quick_fix_tree.py")

        if tree_health.project_nodes == 0:
            recommendations.append(
                "⚠️  No PROJECT nodes found. Tree graph needs initialization."
            )
            recommendations.append(
                "Action: Re-run bulk_ingest_repository.py with --project-name"
            )

        # Growth rate recommendations
        if growth_rate is not None and growth_rate > 10:
            recommendations.append(
                f"⚠️  High orphan growth rate: {growth_rate:+.2f} orphans/hour. "
                "Investigate ingestion pipeline for failures."
            )
            recommendations.append("Action: Check logs in logs/archon-* for errors")

        if growth_rate is not None and growth_rate < 0:
            recommendations.append(
                f"✅ Orphan count decreasing: {growth_rate:+.2f} orphans/hour. "
                "Tree healing is working!"
            )

        # Healthy state
        if tree_health.orphan_count == 0 and tree_health.health_status == "healthy":
            recommendations.append("✅ Data quality is excellent! No orphans detected.")

        return recommendations

    def get_dashboard_data(self) -> DashboardData:
        """Get complete dashboard data."""
        tree_health = self.get_tree_health()
        ingestion_metrics = self.get_ingestion_metrics()
        orphan_trend = self.get_orphan_trend_24h()

        growth_rate_hour, growth_rate_day = self.calculate_growth_rates(orphan_trend)

        recommendations = self.generate_recommendations(tree_health, growth_rate_hour)

        return DashboardData(
            timestamp=datetime.utcnow().isoformat(),
            tree_health=tree_health,
            ingestion_metrics=ingestion_metrics,
            orphan_trend_24h=orphan_trend,
            growth_rate_per_hour=growth_rate_hour,
            growth_rate_per_day=growth_rate_day,
            recommendations=recommendations,
        )

    def render_dashboard(self, compact: bool = False):
        """Render dashboard to console."""
        data = self.get_dashboard_data()

        print("\n" + "=" * 80)
        print("DATA QUALITY DASHBOARD")
        print("=" * 80)
        print(f"Timestamp: {data.timestamp}")
        print()

        # Tree Health Section
        print("📊 TREE HEALTH")
        print("-" * 80)
        health_icon = {"healthy": "✅", "degraded": "⚠️ ", "critical": "❌"}[
            data.tree_health.health_status
        ]
        print(
            f"Status:              {health_icon} {data.tree_health.health_status.upper()}"
        )
        print(f"Orphan Count:        {data.tree_health.orphan_count:,}")
        print(f"Orphan Percentage:   {data.tree_health.orphan_percentage:.2f}%")
        print(f"Total Files:         {data.tree_health.total_files:,}")
        print(f"PROJECT Nodes:       {data.tree_health.project_nodes}")
        print(f"DIRECTORY Nodes:     {data.tree_health.directory_nodes}")
        print(f"CONTAINS Rels:       {data.tree_health.contains_relationships}")
        print()

        # Ingestion Metrics Section
        print("📥 INGESTION METRICS")
        print("-" * 80)
        print(f"Files Processed:     {data.ingestion_metrics.total_files_processed:,}")
        print(f"Successful:          {data.ingestion_metrics.successful_ingestions:,}")
        print(f"Failed:              {data.ingestion_metrics.failed_ingestions:,}")
        print(f"Success Rate:        {data.ingestion_metrics.success_rate:.2f}%")
        print()

        # Trend Section
        print("📈 ORPHAN TRENDS (Last 24 Hours)")
        print("-" * 80)
        if data.orphan_trend_24h:
            print(f"Data Points:         {len(data.orphan_trend_24h)}")
            print(f"First Record:        {data.orphan_trend_24h[0]['timestamp']}")
            print(f"Latest Record:       {data.orphan_trend_24h[-1]['timestamp']}")

            if data.growth_rate_per_hour is not None:
                trend_icon = (
                    "📈"
                    if data.growth_rate_per_hour > 0
                    else "📉" if data.growth_rate_per_hour < 0 else "➡️ "
                )
                print(
                    f"Growth Rate (hour):  {trend_icon} {data.growth_rate_per_hour:+.2f} orphans/hour"
                )
                print(
                    f"Growth Rate (day):   {trend_icon} {data.growth_rate_per_day:+.2f} orphans/day"
                )

            # Simple ASCII graph (if not compact)
            if not compact and len(data.orphan_trend_24h) > 1:
                print("\nOrphan Count Graph (Last 24 Hours):")
                self._render_ascii_graph(data.orphan_trend_24h)
        else:
            print(
                "No historical data available. Run monitor_orphans.py to collect metrics."
            )
        print()

        # Recommendations Section
        print("💡 RECOMMENDATIONS")
        print("-" * 80)
        if data.recommendations:
            for rec in data.recommendations:
                print(f"{rec}")
        else:
            print("No recommendations at this time.")
        print()

        print("=" * 80)

    def _render_ascii_graph(
        self, trend_data: List[Dict], height: int = 10, width: int = 60
    ):
        """Render simple ASCII graph of orphan count over time."""
        if not trend_data:
            return

        # Extract orphan counts
        counts = [d["orphan_count"] for d in trend_data]
        min_count = min(counts)
        max_count = max(counts)

        # Normalize to graph height
        if max_count == min_count:
            normalized = [height // 2] * len(counts)
        else:
            normalized = [
                int((count - min_count) / (max_count - min_count) * height)
                for count in counts
            ]

        # Render graph
        for row in range(height, -1, -1):
            line = ""
            for val in normalized:
                if val >= row:
                    line += "█"
                else:
                    line += " "

            # Add Y-axis label
            if row == height:
                print(f"{max_count:6,} │{line}│")
            elif row == 0:
                print(f"{min_count:6,} │{line}│")
            else:
                print(f"       │{line}│")

        # X-axis
        print(f"       └{'─' * len(normalized)}┘")
        print(
            f"        {trend_data[0]['timestamp'][:10]} → {trend_data[-1]['timestamp'][:10]}"
        )

    def render_json(self):
        """Render dashboard data as JSON."""
        data = self.get_dashboard_data()
        output = {
            "timestamp": data.timestamp,
            "tree_health": asdict(data.tree_health),
            "ingestion_metrics": asdict(data.ingestion_metrics),
            "growth_rates": {
                "per_hour": data.growth_rate_per_hour,
                "per_day": data.growth_rate_per_day,
            },
            "orphan_trend_count": len(data.orphan_trend_24h),
            "recommendations": data.recommendations,
        }
        print(json.dumps(output, indent=2))

    def auto_refresh(self, interval: int):
        """Auto-refresh dashboard at specified interval."""
        try:
            while True:
                # Clear screen (cross-platform)
                os.system("cls" if os.name == "nt" else "clear")

                # Render dashboard
                self.render_dashboard()

                print(f"\n[Auto-refresh: {interval}s | Press Ctrl+C to stop]")

                # Wait for next refresh
                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n\nDashboard stopped.")
            sys.exit(0)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Data Quality Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--refresh",
        type=int,
        metavar="SECONDS",
        help="Auto-refresh interval in seconds",
    )
    parser.add_argument(
        "--compact", action="store_true", help="Compact view (no graphs)"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    dashboard = DataQualityDashboard()

    try:
        if args.json:
            dashboard.render_json()
        elif args.refresh:
            dashboard.auto_refresh(interval=args.refresh)
        else:
            dashboard.render_dashboard(compact=args.compact)

        # Exit with appropriate code based on tree health
        data = dashboard.get_dashboard_data()
        if data.tree_health.health_status == "healthy":
            sys.exit(0)
        elif data.tree_health.health_status == "degraded":
            sys.exit(1)
        else:  # critical
            sys.exit(2)

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
