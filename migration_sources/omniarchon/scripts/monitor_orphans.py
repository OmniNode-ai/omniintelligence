#!/usr/bin/env python3
"""
Orphan Metrics Collection System
=================================

Real-time monitoring of orphaned FILE nodes in Memgraph.
Tracks orphan count, growth rate, and historical trends.

Orphan Definition:
  A FILE node that is not connected to a PROJECT node via CONTAINS relationships.
  Excludes module imports (e.g., 'pathlib.Path') which don't have filesystem paths.

Features:
  - Collect orphan count every 5 minutes
  - Track orphan count over time (time series)
  - Calculate orphan growth rate (orphans/hour)
  - Store metrics in JSON file for historical analysis
  - Export metrics to Prometheus format (optional)
  - Provide detailed orphan information (file paths, projects)

Usage:
    # Run once (collect current metrics)
    python3 scripts/monitor_orphans.py

    # Continuous monitoring (every 5 minutes)
    python3 scripts/monitor_orphans.py --continuous

    # Custom interval (every 2 minutes)
    python3 scripts/monitor_orphans.py --continuous --interval 120

    # Export Prometheus metrics
    python3 scripts/monitor_orphans.py --prometheus

    # Detailed output with orphan file paths
    python3 scripts/monitor_orphans.py --verbose
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class OrphanMetrics:
    """Metrics for orphaned FILE nodes."""

    timestamp: str
    orphan_count: int
    total_files: int
    orphan_percentage: float
    project_nodes: int
    directory_nodes: int
    contains_relationships: int
    orphan_files: List[Dict[str, str]] = field(default_factory=list)
    growth_rate_per_hour: Optional[float] = None


@dataclass
class OrphanTrend:
    """Historical trend analysis."""

    current_orphan_count: int
    previous_orphan_count: Optional[int]
    change: Optional[int]
    growth_rate_per_hour: Optional[float]
    trend_direction: str  # "increasing", "decreasing", "stable"


class OrphanMetricsCollector:
    """Collects and stores orphan metrics."""

    def __init__(self, metrics_file: Optional[Path] = None):
        self.metrics_file = (
            metrics_file
            or Path(__file__).parent.parent / "logs" / "orphan_metrics.json"
        )
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
        self.memgraph_uri = os.getenv("MEMGRAPH_URI", "bolt://localhost:7687")
        self.running = False

    def collect_orphan_metrics(self, verbose: bool = False) -> OrphanMetrics:
        """Collect current orphan metrics from Memgraph."""
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

                # Get orphaned FILE nodes (files not connected via CONTAINS to PROJECT)
                # Exclude module imports (they don't have filesystem paths)
                orphan_query = """
                    MATCH (f:FILE)
                    WHERE f.entity_id STARTS WITH 'archon://' OR f.path CONTAINS '/'
                    OPTIONAL MATCH orphan_path = (f)<-[:CONTAINS*]-(:PROJECT)
                    WITH f, orphan_path
                    WHERE orphan_path IS NULL
                    RETURN count(f) as count
                """
                orphan_count = session.run(orphan_query).single()["count"]

                # Get total FILE count for context (source files only, not module imports)
                total_files = session.run(
                    """
                    MATCH (f:FILE)
                    WHERE f.entity_id STARTS WITH 'archon://' OR f.path CONTAINS '/'
                    RETURN count(f) as count
                    """
                ).single()["count"]

                # Get orphan file details if verbose
                orphan_files = []
                if verbose and orphan_count > 0:
                    orphan_details_query = """
                        MATCH (f:FILE)
                        WHERE f.entity_id STARTS WITH 'archon://' OR f.path CONTAINS '/'
                        OPTIONAL MATCH orphan_path = (f)<-[:CONTAINS*]-(:PROJECT)
                        WITH f, orphan_path
                        WHERE orphan_path IS NULL
                        RETURN f.path as path, f.entity_id as entity_id,
                               f.project_name as project_name
                        LIMIT 100
                    """
                    result = session.run(orphan_details_query)
                    for record in result:
                        orphan_files.append(
                            {
                                "path": record["path"],
                                "entity_id": record["entity_id"],
                                "project_name": record["project_name"] or "NULL",
                            }
                        )

            driver.close()

            orphan_percentage = (
                (orphan_count / total_files * 100) if total_files > 0 else 0
            )

            metrics = OrphanMetrics(
                timestamp=datetime.utcnow().isoformat(),
                orphan_count=orphan_count,
                total_files=total_files,
                orphan_percentage=round(orphan_percentage, 2),
                project_nodes=project_count,
                directory_nodes=directory_count,
                contains_relationships=contains_count,
                orphan_files=orphan_files,
            )

            # Calculate growth rate if historical data exists
            historical_metrics = self.load_historical_metrics()
            if historical_metrics:
                metrics.growth_rate_per_hour = self._calculate_growth_rate(
                    metrics, historical_metrics
                )

            logger.info(
                f"Orphan metrics collected: {orphan_count} orphans "
                f"({orphan_percentage:.1f}% of {total_files} files)"
            )

            return metrics

        except Exception as e:
            logger.error(f"Failed to collect orphan metrics: {e}")
            raise

    def _calculate_growth_rate(
        self, current: OrphanMetrics, historical: List[Dict]
    ) -> Optional[float]:
        """Calculate orphan growth rate (orphans per hour)."""
        if not historical:
            return None

        # Find most recent historical metric
        latest = historical[-1]
        latest_timestamp = datetime.fromisoformat(latest["timestamp"])
        current_timestamp = datetime.fromisoformat(current.timestamp)

        time_diff_hours = (current_timestamp - latest_timestamp).total_seconds() / 3600
        if time_diff_hours == 0:
            return None

        orphan_diff = current.orphan_count - latest["orphan_count"]
        growth_rate = orphan_diff / time_diff_hours

        return round(growth_rate, 2)

    def load_historical_metrics(self) -> List[Dict]:
        """Load historical metrics from JSON file."""
        if not self.metrics_file.exists():
            return []

        try:
            with open(self.metrics_file, "r") as f:
                data = json.load(f)
                return data.get("metrics", [])
        except Exception as e:
            logger.warning(f"Failed to load historical metrics: {e}")
            return []

    def save_metrics(self, metrics: OrphanMetrics):
        """Save metrics to JSON file."""
        historical = self.load_historical_metrics()

        # Add new metrics
        historical.append(asdict(metrics))

        # Keep only last 30 days (assuming 5-minute intervals = 288 per day)
        max_entries = 288 * 30
        if len(historical) > max_entries:
            historical = historical[-max_entries:]

        # Save to file
        data = {
            "last_updated": datetime.utcnow().isoformat(),
            "total_entries": len(historical),
            "metrics": historical,
        }

        with open(self.metrics_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Metrics saved to {self.metrics_file}")

    def get_trend_analysis(self) -> OrphanTrend:
        """Analyze orphan count trend."""
        historical = self.load_historical_metrics()

        if not historical:
            return OrphanTrend(
                current_orphan_count=0,
                previous_orphan_count=None,
                change=None,
                growth_rate_per_hour=None,
                trend_direction="unknown",
            )

        current = historical[-1]
        current_count = current["orphan_count"]

        # Get previous count (if available)
        previous_count = historical[-2]["orphan_count"] if len(historical) > 1 else None

        # Calculate change
        change = None
        trend_direction = "stable"
        if previous_count is not None:
            change = current_count - previous_count
            if change > 0:
                trend_direction = "increasing"
            elif change < 0:
                trend_direction = "decreasing"

        # Get growth rate
        growth_rate = current.get("growth_rate_per_hour")

        return OrphanTrend(
            current_orphan_count=current_count,
            previous_orphan_count=previous_count,
            change=change,
            growth_rate_per_hour=growth_rate,
            trend_direction=trend_direction,
        )

    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format."""
        try:
            metrics = self.collect_orphan_metrics()

            prometheus_output = f"""# HELP orphan_file_count Number of orphaned FILE nodes in Memgraph
# TYPE orphan_file_count gauge
orphan_file_count {metrics.orphan_count}

# HELP orphan_file_percentage Percentage of orphaned files
# TYPE orphan_file_percentage gauge
orphan_file_percentage {metrics.orphan_percentage}

# HELP total_file_count Total number of FILE nodes in Memgraph
# TYPE total_file_count gauge
total_file_count {metrics.total_files}

# HELP project_node_count Number of PROJECT nodes
# TYPE project_node_count gauge
project_node_count {metrics.project_nodes}

# HELP directory_node_count Number of DIRECTORY nodes
# TYPE directory_node_count gauge
directory_node_count {metrics.directory_nodes}

# HELP contains_relationship_count Number of CONTAINS relationships
# TYPE contains_relationship_count gauge
contains_relationship_count {metrics.contains_relationships}
"""

            if metrics.growth_rate_per_hour is not None:
                prometheus_output += f"""
# HELP orphan_growth_rate_per_hour Orphan growth rate (orphans per hour)
# TYPE orphan_growth_rate_per_hour gauge
orphan_growth_rate_per_hour {metrics.growth_rate_per_hour}
"""

            return prometheus_output

        except Exception as e:
            logger.error(f"Failed to export Prometheus metrics: {e}")
            return ""

    def continuous_monitoring(self, interval_seconds: int = 300):
        """Run continuous monitoring with specified interval."""
        self.running = True

        # Handle graceful shutdown
        def signal_handler(signum, frame):
            logger.info("Received shutdown signal, stopping monitoring...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        logger.info(
            f"Starting continuous orphan monitoring (interval: {interval_seconds}s)"
        )

        while self.running:
            try:
                metrics = self.collect_orphan_metrics()
                self.save_metrics(metrics)

                # Display trend
                trend = self.get_trend_analysis()
                logger.info(
                    f"Trend: {trend.trend_direction.upper()} | "
                    f"Current: {trend.current_orphan_count} | "
                    f"Change: {trend.change or 'N/A'} | "
                    f"Growth Rate: {trend.growth_rate_per_hour or 'N/A'}/hour"
                )

                # Sleep until next collection
                time.sleep(interval_seconds)

            except Exception as e:
                logger.error(f"Error during monitoring: {e}")
                time.sleep(60)  # Wait 1 minute before retrying

        logger.info("Monitoring stopped")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Orphan Metrics Collection System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--continuous", action="store_true", help="Run continuous monitoring"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Monitoring interval in seconds (default: 300 = 5 minutes)",
    )
    parser.add_argument(
        "--prometheus", action="store_true", help="Export Prometheus metrics"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Include detailed orphan file information",
    )
    parser.add_argument(
        "--metrics-file",
        type=Path,
        help="Path to metrics JSON file (default: logs/orphan_metrics.json)",
    )

    args = parser.parse_args()

    collector = OrphanMetricsCollector(metrics_file=args.metrics_file)

    try:
        if args.prometheus:
            # Export Prometheus metrics
            prometheus_output = collector.export_prometheus_metrics()
            print(prometheus_output)
        elif args.continuous:
            # Run continuous monitoring
            collector.continuous_monitoring(interval_seconds=args.interval)
        else:
            # Single collection
            metrics = collector.collect_orphan_metrics(verbose=args.verbose)
            collector.save_metrics(metrics)

            # Display metrics
            print("\n" + "=" * 70)
            print("ORPHAN METRICS")
            print("=" * 70)
            print(f"Timestamp:       {metrics.timestamp}")
            print(f"Orphan Count:    {metrics.orphan_count:,}")
            print(f"Total Files:     {metrics.total_files:,}")
            print(f"Orphan %:        {metrics.orphan_percentage:.2f}%")
            print(f"PROJECT Nodes:   {metrics.project_nodes}")
            print(f"DIRECTORY Nodes: {metrics.directory_nodes}")
            print(f"CONTAINS Rels:   {metrics.contains_relationships}")

            if metrics.growth_rate_per_hour is not None:
                print(
                    f"Growth Rate:     {metrics.growth_rate_per_hour:+.2f} orphans/hour"
                )

            # Display trend
            trend = collector.get_trend_analysis()
            if trend.change is not None:
                print(f"\nTrend:           {trend.trend_direction.upper()}")
                print(f"Change:          {trend.change:+d} orphans")

            # Display orphan details if verbose
            if args.verbose and metrics.orphan_files:
                print(f"\nOrphaned Files (showing first {len(metrics.orphan_files)}):")
                for orphan in metrics.orphan_files:
                    print(f"  - {orphan['path']} (project: {orphan['project_name']})")

            print("=" * 70)
            print(f"\nMetrics saved to: {collector.metrics_file}")

            # Exit with appropriate code
            if metrics.orphan_count > 0:
                sys.exit(1)  # Non-zero exit if orphans exist
            else:
                sys.exit(0)

    except KeyboardInterrupt:
        logger.info("Monitoring interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
