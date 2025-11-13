#!/usr/bin/env python3
"""
Ingestion Pipeline Monitoring System

Real-time monitoring for Archon's event-driven ingestion pipeline.
Tracks Kafka topics, Qdrant vectors, service health, and processing latency.

Architecture:
- Event Bus: Redpanda (config.kafka_helper: 192.168.86.200:29092 for host, omninode-bridge-redpanda:9092 for Docker)
- Topics:
  - dev.archon-intelligence.tree.discover.v1 - Tree discovery events
  - dev.archon-intelligence.tree.index-project-completed.v1 - Successful indexing
  - dev.archon-intelligence.tree.index-project-failed.v1 - Failed indexing
  - dev.archon-intelligence.stamping.generate.v1 - Intelligence generation
- Storage: Qdrant (vectors), Memgraph (knowledge graph), PostgreSQL (traceability)
- Services: archon-intelligence (8053), archon-bridge (8054), archon-search (8055)

Usage:
    # Real-time dashboard
    python scripts/monitor_ingestion_pipeline.py --dashboard

    # Monitor for specific duration
    python scripts/monitor_ingestion_pipeline.py --dashboard --duration 300

    # Export to JSON
    python scripts/monitor_ingestion_pipeline.py --duration 60 --json metrics.json

    # Custom check interval
    python scripts/monitor_ingestion_pipeline.py --dashboard --interval 5

    # With alerting
    python scripts/monitor_ingestion_pipeline.py --dashboard --alert-webhook https://hooks.slack.com/...

Examples:
    python scripts/monitor_ingestion_pipeline.py --dashboard --duration 300 --interval 10
    python scripts/monitor_ingestion_pipeline.py --json pipeline_metrics.json --duration 120
    python scripts/monitor_ingestion_pipeline.py --dashboard --consumer-lag-warning 50 --consumer-lag-critical 200
"""

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

# Add src and root directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
# Add project root to path for config imports
project_root = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, project_root)

# Import centralized configuration
from config.kafka_helper import KAFKA_HOST_SERVERS

# Parse default Kafka host and port from centralized config
_kafka_host, _kafka_port = KAFKA_HOST_SERVERS.split(":")
DEFAULT_REDPANDA_HOST = _kafka_host
DEFAULT_REDPANDA_PORT = int(_kafka_port)


@dataclass
class ServiceHealth:
    """Service health status"""

    name: str
    url: str
    healthy: bool
    response_time_ms: Optional[float] = None
    error: Optional[str] = None


@dataclass
class TopicMetrics:
    """Kafka topic metrics"""

    name: str
    message_count: int
    consumer_lag: int
    partitions: int
    replicas: int


@dataclass
class VectorMetrics:
    """Qdrant vector collection metrics"""

    collection: str
    points_count: int
    indexed_vectors: int
    timestamp: str


@dataclass
class PipelineMetrics:
    """Overall pipeline metrics"""

    timestamp: str
    services: List[ServiceHealth]
    topics: List[TopicMetrics]
    vectors: VectorMetrics
    success_rate: float
    avg_latency_ms: Optional[float] = None
    alerts: List[str] = None


class IngestionPipelineMonitor:
    """Monitors the Archon ingestion pipeline end-to-end"""

    def __init__(
        self,
        redpanda_host: str = DEFAULT_REDPANDA_HOST,
        redpanda_port: int = DEFAULT_REDPANDA_PORT,
        qdrant_url: str = "http://localhost:6333",
        intelligence_url: str = "http://localhost:8053",
        bridge_url: str = "http://localhost:8054",
        search_url: str = "http://localhost:8055",
        consumer_lag_warning: int = 100,
        consumer_lag_critical: int = 500,
        alert_webhook: Optional[str] = None,
    ):
        """Initialize the monitor with service endpoints and thresholds"""
        self.redpanda_host = redpanda_host
        self.redpanda_port = redpanda_port
        self.qdrant_url = qdrant_url
        self.intelligence_url = intelligence_url
        self.bridge_url = bridge_url
        self.search_url = search_url
        self.consumer_lag_warning = consumer_lag_warning
        self.consumer_lag_critical = consumer_lag_critical
        self.alert_webhook = alert_webhook

        # Topics to monitor
        self.topics = [
            "dev.archon-intelligence.tree.discover.v1",
            "dev.archon-intelligence.tree.index-project-completed.v1",
            "dev.archon-intelligence.tree.index-project-failed.v1",
            "dev.archon-intelligence.stamping.generate.v1",
        ]

        # Historical data for trend analysis
        self.history: List[PipelineMetrics] = []

    def check_service_health(self, name: str, url: str) -> ServiceHealth:
        """Check health of a service endpoint"""
        try:
            start = time.time()
            response = requests.get(f"{url}/health", timeout=5)
            response_time = (time.time() - start) * 1000

            healthy = response.status_code == 200
            return ServiceHealth(
                name=name,
                url=url,
                healthy=healthy,
                response_time_ms=round(response_time, 2),
            )
        except Exception as e:
            return ServiceHealth(
                name=name,
                url=url,
                healthy=False,
                error=str(e),
            )

    def get_topic_metrics(self, topic: str) -> Optional[TopicMetrics]:
        """Get metrics for a Kafka topic using rpk CLI"""
        try:
            # Use docker exec to run rpk commands
            cmd = [
                "docker",
                "exec",
                "omninode-bridge-redpanda",
                "rpk",
                "topic",
                "describe",
                topic,
                "--format",
                "json",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                return None

            data = json.loads(result.stdout)

            # Extract metrics from rpk output
            partitions = len(data.get("partitions", []))
            replicas = data.get("partitions", [{}])[0].get("replicas", [])
            replicas_count = len(replicas) if replicas else 0

            # Get message count from partition high watermarks
            message_count = sum(
                p.get("high_watermark", 0) for p in data.get("partitions", [])
            )

            # Get consumer lag
            consumer_lag = self._get_consumer_lag(topic)

            return TopicMetrics(
                name=topic,
                message_count=message_count,
                consumer_lag=consumer_lag,
                partitions=partitions,
                replicas=replicas_count,
            )
        except Exception as e:
            print(f"Error getting topic metrics for {topic}: {e}", file=sys.stderr)
            return None

    def _get_consumer_lag(self, topic: str) -> int:
        """Get consumer lag for a topic"""
        try:
            cmd = [
                "docker",
                "exec",
                "omninode-bridge-redpanda",
                "rpk",
                "group",
                "describe",
                "archon-kafka-consumer",
                "--format",
                "json",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                return 0

            data = json.loads(result.stdout)

            # Sum lag across all partitions for this topic
            total_lag = 0
            for member in data.get("members", []):
                for partition in member.get("partitions", []):
                    if partition.get("topic") == topic:
                        total_lag += partition.get("lag", 0)

            return total_lag
        except Exception:
            return 0

    def get_qdrant_metrics(self) -> Optional[VectorMetrics]:
        """Get Qdrant vector collection metrics"""
        try:
            response = requests.get(
                f"{self.qdrant_url}/collections/archon",
                timeout=5,
            )

            if response.status_code != 200:
                return None

            data = response.json()
            result = data.get("result", {})

            return VectorMetrics(
                collection="archon",
                points_count=result.get("points_count", 0),
                indexed_vectors=result.get("indexed_vectors_count", 0),
                timestamp=datetime.now().isoformat(),
            )
        except Exception as e:
            print(f"Error getting Qdrant metrics: {e}", file=sys.stderr)
            return None

    def calculate_success_rate(self, topics: List[TopicMetrics]) -> float:
        """Calculate success rate from completed vs failed topics"""
        completed = 0
        failed = 0

        for topic in topics:
            if "completed" in topic.name:
                completed = topic.message_count
            elif "failed" in topic.name:
                failed = topic.message_count

        total = completed + failed
        if total == 0:
            return 100.0

        return round((completed / total) * 100, 2)

    def generate_alerts(self, metrics: PipelineMetrics) -> List[str]:
        """Generate alerts based on metrics and thresholds"""
        alerts = []

        # Check service health
        unhealthy_services = [s for s in metrics.services if not s.healthy]
        if unhealthy_services:
            alerts.append(
                f"⚠️  {len(unhealthy_services)} service(s) unhealthy: {', '.join(s.name for s in unhealthy_services)}"
            )

        # Check consumer lag
        for topic in metrics.topics:
            if topic.consumer_lag >= self.consumer_lag_critical:
                alerts.append(
                    f"🚨 CRITICAL: Topic {topic.name} has lag of {topic.consumer_lag} (threshold: {self.consumer_lag_critical})"
                )
            elif topic.consumer_lag >= self.consumer_lag_warning:
                alerts.append(
                    f"⚠️  WARNING: Topic {topic.name} has lag of {topic.consumer_lag} (threshold: {self.consumer_lag_warning})"
                )

        # Check success rate
        if metrics.success_rate < 90.0:
            alerts.append(
                f"⚠️  Low success rate: {metrics.success_rate}% (threshold: 90%)"
            )

        # Check vector growth
        if len(self.history) > 0:
            prev_vectors = self.history[-1].vectors.points_count
            curr_vectors = metrics.vectors.points_count
            if curr_vectors <= prev_vectors:
                alerts.append(
                    f"⚠️  No vector growth detected: {prev_vectors} → {curr_vectors}"
                )

        return alerts

    def send_alert(self, alerts: List[str]):
        """Send alerts to webhook (e.g., Slack)"""
        if not self.alert_webhook or not alerts:
            return

        try:
            payload = {
                "text": "🚨 Archon Ingestion Pipeline Alerts",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "\n".join(alerts),
                        },
                    }
                ],
            }

            response = requests.post(
                self.alert_webhook,
                json=payload,
                timeout=5,
            )

            if response.status_code != 200:
                print(f"Failed to send alert: {response.status_code}", file=sys.stderr)
        except Exception as e:
            print(f"Error sending alert: {e}", file=sys.stderr)

    def collect_metrics(self) -> PipelineMetrics:
        """Collect all metrics for current state"""
        # Check service health
        services = [
            self.check_service_health("archon-intelligence", self.intelligence_url),
            self.check_service_health("archon-bridge", self.bridge_url),
            self.check_service_health("archon-search", self.search_url),
        ]

        # Get topic metrics
        topic_metrics = []
        for topic in self.topics:
            metrics = self.get_topic_metrics(topic)
            if metrics:
                topic_metrics.append(metrics)

        # Get vector metrics
        vector_metrics = self.get_qdrant_metrics()
        if not vector_metrics:
            vector_metrics = VectorMetrics(
                collection="archon",
                points_count=0,
                indexed_vectors=0,
                timestamp=datetime.now().isoformat(),
            )

        # Calculate success rate
        success_rate = self.calculate_success_rate(topic_metrics)

        # Create pipeline metrics
        metrics = PipelineMetrics(
            timestamp=datetime.now().isoformat(),
            services=services,
            topics=topic_metrics,
            vectors=vector_metrics,
            success_rate=success_rate,
            alerts=[],
        )

        # Generate alerts
        metrics.alerts = self.generate_alerts(metrics)

        # Send alerts if configured
        if metrics.alerts:
            self.send_alert(metrics.alerts)

        return metrics

    def display_dashboard(self, metrics: PipelineMetrics):
        """Display real-time dashboard in terminal"""
        # Clear screen
        os.system("clear" if os.name != "nt" else "cls")

        print("╔════════════════════════════════════════════════════════════════╗")
        print("║       Archon Ingestion Pipeline Monitor                       ║")
        print("╠════════════════════════════════════════════════════════════════╣")
        print(f"║  Timestamp: {metrics.timestamp:<45} ║")
        print("╚════════════════════════════════════════════════════════════════╝")
        print()

        # Service Health
        print("📊 SERVICE HEALTH")
        print("─" * 70)
        for service in metrics.services:
            status = "✅ HEALTHY" if service.healthy else "❌ UNHEALTHY"
            response_time = (
                f"{service.response_time_ms}ms" if service.response_time_ms else "N/A"
            )
            print(f"  {service.name:20} {status:15} Response: {response_time}")
            if service.error:
                print(f"    Error: {service.error}")
        print()

        # Topic Metrics
        print("📨 KAFKA TOPIC METRICS")
        print("─" * 70)
        for topic in metrics.topics:
            short_name = topic.name.split(".")[-1]
            print(f"  {short_name:30}")
            print(f"    Messages: {topic.message_count:>10}")
            print(f"    Consumer Lag: {topic.consumer_lag:>6}")
            print(
                f"    Partitions: {topic.partitions:>3}   Replicas: {topic.replicas:>2}"
            )
        print()

        # Vector Metrics
        print("🔢 QDRANT VECTOR METRICS")
        print("─" * 70)
        print(f"  Collection: {metrics.vectors.collection}")
        print(f"  Points Count: {metrics.vectors.points_count:,}")
        print(f"  Indexed Vectors: {metrics.vectors.indexed_vectors:,}")
        print()

        # Success Rate
        print("📈 PIPELINE PERFORMANCE")
        print("─" * 70)
        print(f"  Success Rate: {metrics.success_rate:.2f}%")
        if metrics.avg_latency_ms:
            print(f"  Avg Latency: {metrics.avg_latency_ms:.2f}ms")

        # Vector growth trend
        if len(self.history) > 1:
            prev_vectors = self.history[-2].vectors.points_count
            curr_vectors = metrics.vectors.points_count
            growth = curr_vectors - prev_vectors
            print(f"  Vector Growth: +{growth:,} points")
        print()

        # Alerts
        if metrics.alerts:
            print("🚨 ALERTS")
            print("─" * 70)
            for alert in metrics.alerts:
                print(f"  {alert}")
            print()

        print(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("Press Ctrl+C to stop monitoring")

    def run_dashboard(self, duration: Optional[int] = None, interval: int = 10):
        """Run the dashboard in real-time mode"""
        start_time = time.time()

        try:
            while True:
                # Collect metrics
                metrics = self.collect_metrics()
                self.history.append(metrics)

                # Display dashboard
                self.display_dashboard(metrics)

                # Check duration
                if duration and (time.time() - start_time) >= duration:
                    print("\n✅ Monitoring duration completed")
                    break

                # Wait for next interval
                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n\n✅ Monitoring stopped by user")

    def export_to_json(self, duration: int, interval: int, output_file: str):
        """Collect metrics and export to JSON file"""
        print(f"📊 Collecting metrics for {duration} seconds...")
        start_time = time.time()

        try:
            while (time.time() - start_time) < duration:
                metrics = self.collect_metrics()
                self.history.append(metrics)

                # Show progress
                elapsed = int(time.time() - start_time)
                remaining = duration - elapsed
                print(
                    f"\rCollected {len(self.history)} snapshots... {remaining}s remaining",
                    end="",
                )

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n\n⚠️  Collection interrupted by user")

        # Export to JSON
        print(f"\n\n💾 Exporting to {output_file}...")
        data = {
            "monitoring_session": {
                "start_time": self.history[0].timestamp if self.history else None,
                "end_time": self.history[-1].timestamp if self.history else None,
                "duration_seconds": duration,
                "interval_seconds": interval,
                "snapshots_collected": len(self.history),
            },
            "metrics": [asdict(m) for m in self.history],
        }

        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)

        print(f"✅ Exported {len(self.history)} snapshots to {output_file}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Monitor Archon ingestion pipeline in real-time",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --dashboard
  %(prog)s --dashboard --duration 300 --interval 10
  %(prog)s --json metrics.json --duration 120
  %(prog)s --dashboard --consumer-lag-warning 50 --consumer-lag-critical 200
        """,
    )

    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Show real-time dashboard",
    )

    parser.add_argument(
        "--duration",
        type=int,
        help="Monitoring duration in seconds (optional, runs indefinitely if not set)",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Check interval in seconds (default: 10)",
    )

    parser.add_argument(
        "--json",
        type=str,
        help="Save monitoring data to JSON file",
    )

    parser.add_argument(
        "--alert-webhook",
        type=str,
        help="Webhook URL for alerts (e.g., Slack webhook)",
    )

    parser.add_argument(
        "--consumer-lag-warning",
        type=int,
        default=100,
        help="Consumer lag warning threshold (default: 100)",
    )

    parser.add_argument(
        "--consumer-lag-critical",
        type=int,
        default=500,
        help="Consumer lag critical threshold (default: 500)",
    )

    parser.add_argument(
        "--redpanda-host",
        type=str,
        default="192.168.86.200",
        help="Redpanda host (default: 192.168.86.200)",
    )

    parser.add_argument(
        "--redpanda-port",
        type=int,
        default=DEFAULT_REDPANDA_PORT,
        help=f"Redpanda port (default: {DEFAULT_REDPANDA_PORT} from config.kafka_helper)",
    )

    parser.add_argument(
        "--qdrant-url",
        type=str,
        default="http://localhost:6333",
        help="Qdrant URL (default: http://localhost:6333)",
    )

    parser.add_argument(
        "--intelligence-url",
        type=str,
        default="http://localhost:8053",
        help="Intelligence service URL (default: http://localhost:8053)",
    )

    parser.add_argument(
        "--bridge-url",
        type=str,
        default="http://localhost:8054",
        help="Bridge service URL (default: http://localhost:8054)",
    )

    parser.add_argument(
        "--search-url",
        type=str,
        default="http://localhost:8055",
        help="Search service URL (default: http://localhost:8055)",
    )

    args = parser.parse_args()

    # Create monitor
    monitor = IngestionPipelineMonitor(
        redpanda_host=args.redpanda_host,
        redpanda_port=args.redpanda_port,
        qdrant_url=args.qdrant_url,
        intelligence_url=args.intelligence_url,
        bridge_url=args.bridge_url,
        search_url=args.search_url,
        consumer_lag_warning=args.consumer_lag_warning,
        consumer_lag_critical=args.consumer_lag_critical,
        alert_webhook=args.alert_webhook,
    )

    # Run monitoring
    if args.dashboard:
        monitor.run_dashboard(duration=args.duration, interval=args.interval)
    elif args.json:
        if not args.duration:
            print(
                "❌ Error: --duration is required when using --json",
                file=sys.stderr,
            )
            sys.exit(1)
        monitor.export_to_json(args.duration, args.interval, args.json)
    else:
        # Default: collect metrics once and display
        metrics = monitor.collect_metrics()
        monitor.display_dashboard(metrics)


if __name__ == "__main__":
    main()
