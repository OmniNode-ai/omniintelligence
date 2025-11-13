#!/usr/bin/env python3
"""
ARCHON INGESTION PIPELINE MONITORING
====================================

Real-time monitoring of the event-driven ingestion pipeline.
Tracks Kafka topics, Qdrant vector growth, processing metrics, and service health.

Configuration:
    Uses centralized config from config/settings.py
    Override with environment variables (INTELLIGENCE_SERVICE_PORT, etc.)

Usage:
    python scripts/monitor_ingestion_pipeline.py [--dashboard] [--duration SECONDS] [--json OUTPUT]

Architecture:
    Event Bus: Redpanda at 192.168.86.200:29092 (external) / omninode-bridge-redpanda:9092 (internal)
    Topics:
      - dev.archon-intelligence.tree.discover.v1 - Tree discovery events
      - dev.archon-intelligence.tree.index-project-completed.v1 - Successful indexing
      - dev.archon-intelligence.tree.index-project-failed.v1 - Failed indexing
      - dev.archon-intelligence.stamping.generate.v1 - Intelligence generation
    Storage: Qdrant (vectors), Memgraph (knowledge graph), PostgreSQL (traceability)
    Services: archon-intelligence (8053), archon-bridge (8054), archon-search (8055)

Author: Archon Intelligence Team
Date: 2025-10-29
"""

import argparse
import asyncio
import json
import logging
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

# Add parent directory to path for config imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import centralized configuration
from config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class AlertThresholds:
    """Configurable alert thresholds for monitoring."""

    # Kafka thresholds
    consumer_lag_warning: int = 100
    consumer_lag_critical: int = 500
    message_processing_slow_ms: int = 2000
    message_processing_critical_ms: int = 5000

    # Qdrant thresholds
    vector_growth_stagnant_minutes: int = 30
    vector_growth_decreasing_alert: bool = True

    # Success rate thresholds
    success_rate_warning: float = 0.80  # 80%
    success_rate_critical: float = 0.50  # 50%

    # Service health
    service_response_warning_ms: int = 2000
    service_response_critical_ms: int = 5000


@dataclass
class MonitorConfig:
    """Ingestion pipeline monitor configuration."""

    # Monitoring settings
    check_interval_seconds: int = 10
    duration_seconds: Optional[int] = None
    dashboard_mode: bool = False
    json_output_path: Optional[str] = None

    # Service URLs (from centralized config)
    intelligence_url: str = field(
        default_factory=lambda: f"http://localhost:{settings.intelligence_service_port}"
    )
    bridge_url: str = field(
        default_factory=lambda: f"http://localhost:{settings.bridge_service_port}"
    )
    search_url: str = field(
        default_factory=lambda: f"http://localhost:{settings.search_service_port}"
    )
    qdrant_url: str = field(default_factory=lambda: settings.qdrant_url)

    # Kafka settings
    kafka_container: str = "omninode-bridge-redpanda"
    kafka_topics: List[str] = field(
        default_factory=lambda: [
            "dev.archon-intelligence.tree.discover.v1",
            "dev.archon-intelligence.tree.index-project-completed.v1",
            "dev.archon-intelligence.tree.index-project-failed.v1",
            "dev.archon-intelligence.stamping.generate.v1",
        ]
    )
    consumer_group: str = "archon-intelligence-consumers"

    # Alert settings
    alert_thresholds: AlertThresholds = field(default_factory=AlertThresholds)
    alert_webhook: Optional[str] = None


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class KafkaTopicMetrics:
    """Kafka topic metrics snapshot."""

    topic_name: str
    partition_count: int
    message_count: int
    latest_offset: int
    consumer_lag: int
    messages_per_second: float


@dataclass
class QdrantMetrics:
    """Qdrant vector database metrics."""

    timestamp: float
    vectors_count: int
    indexed_vectors_count: int
    collection_status: str
    points_count: int
    segments_count: int


@dataclass
class ProcessingMetrics:
    """Event processing metrics."""

    timestamp: float
    events_processed: int
    events_successful: int
    events_failed: int
    success_rate: float
    average_latency_ms: float
    throughput_per_second: float


@dataclass
class ServiceHealthMetrics:
    """Service health status."""

    service_name: str
    healthy: bool
    response_time_ms: Optional[float]
    status: str  # healthy, degraded, unhealthy


@dataclass
class PipelineSnapshot:
    """Complete pipeline state snapshot."""

    timestamp: float
    kafka_metrics: List[KafkaTopicMetrics]
    qdrant_metrics: QdrantMetrics
    processing_metrics: ProcessingMetrics
    service_health: List[ServiceHealthMetrics]
    alerts: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "kafka": [asdict(m) for m in self.kafka_metrics],
            "qdrant": asdict(self.qdrant_metrics),
            "processing": asdict(self.processing_metrics),
            "services": [asdict(s) for s in self.service_health],
            "alerts": self.alerts,
        }


# =============================================================================
# Pipeline Monitor
# =============================================================================


class IngestionPipelineMonitor:
    """
    Real-time ingestion pipeline monitoring.

    Tracks Kafka topics, Qdrant vectors, processing metrics, and service health.
    """

    def __init__(self, config: MonitorConfig):
        """
        Initialize pipeline monitor.

        Args:
            config: Monitor configuration
        """
        self.config = config
        self.monitoring_active = False
        self.history: List[PipelineSnapshot] = []
        self.previous_qdrant_metrics: Optional[QdrantMetrics] = None
        self.previous_kafka_offsets: Dict[str, int] = {}

    async def start_monitoring(self):
        """Start continuous pipeline monitoring."""
        self.monitoring_active = True
        logger.info(
            f"Starting ingestion pipeline monitoring (check every {self.config.check_interval_seconds}s)"
        )

        if self.config.dashboard_mode:
            print("=" * 80)
            print("📊 ARCHON INGESTION PIPELINE MONITOR")
            print("=" * 80)
            print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Check interval: {self.config.check_interval_seconds}s")
            if self.config.duration_seconds:
                print(f"Duration: {self.config.duration_seconds}s")
            print("\nPress Ctrl+C to stop monitoring\n")

        start_time = time.time()
        end_time = (
            start_time + self.config.duration_seconds
            if self.config.duration_seconds
            else None
        )

        try:
            while self.monitoring_active:
                # Check duration
                if end_time and time.time() >= end_time:
                    break

                # Collect metrics
                snapshot = await self._collect_pipeline_snapshot()
                self.history.append(snapshot)

                # Keep only last 100 snapshots in memory
                if len(self.history) > 100:
                    self.history = self.history[-100:]

                # Display dashboard
                if self.config.dashboard_mode:
                    self._display_dashboard(snapshot)
                else:
                    # Log summary
                    self._log_summary(snapshot)

                # Send alerts
                if snapshot.alerts:
                    await self._send_alerts(snapshot.alerts)

                await asyncio.sleep(self.config.check_interval_seconds)

        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        finally:
            self.monitoring_active = False
            await self._generate_final_report()

    async def _collect_pipeline_snapshot(self) -> PipelineSnapshot:
        """
        Collect comprehensive pipeline metrics snapshot.

        Returns:
            Complete pipeline snapshot
        """
        timestamp = time.time()

        # Collect metrics in parallel
        kafka_task = self._collect_kafka_metrics()
        qdrant_task = self._collect_qdrant_metrics()
        processing_task = self._collect_processing_metrics()
        service_task = self._collect_service_health()

        kafka_metrics, qdrant_metrics, processing_metrics, service_health = (
            await asyncio.gather(kafka_task, qdrant_task, processing_task, service_task)
        )

        # Generate alerts
        alerts = self._generate_alerts(
            kafka_metrics, qdrant_metrics, processing_metrics, service_health
        )

        return PipelineSnapshot(
            timestamp=timestamp,
            kafka_metrics=kafka_metrics,
            qdrant_metrics=qdrant_metrics,
            processing_metrics=processing_metrics,
            service_health=service_health,
            alerts=alerts,
        )

    async def _collect_kafka_metrics(self) -> List[KafkaTopicMetrics]:
        """Collect Kafka topic metrics."""
        metrics = []

        try:
            for topic in self.config.kafka_topics:
                # Get topic description
                result = subprocess.run(
                    [
                        "docker",
                        "exec",
                        self.config.kafka_container,
                        "rpk",
                        "topic",
                        "describe",
                        topic,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if result.returncode == 0:
                    # Parse output for metrics
                    partition_count = 0
                    latest_offset = 0

                    for line in result.stdout.split("\n"):
                        if "partitions" in line.lower():
                            try:
                                partition_count = int(
                                    line.split(":")[1].strip().split()[0]
                                )
                            except:
                                pass
                        if "high watermark" in line.lower() or "offset" in line.lower():
                            try:
                                # Extract offset number
                                import re

                                numbers = re.findall(r"\d+", line)
                                if numbers:
                                    latest_offset = max(latest_offset, int(numbers[-1]))
                            except:
                                pass

                    # Calculate messages per second
                    previous_offset = self.previous_kafka_offsets.get(topic, 0)
                    messages_per_second = 0.0
                    if previous_offset > 0 and len(self.history) > 0:
                        time_diff = time.time() - self.history[-1].timestamp
                        if time_diff > 0:
                            messages_per_second = (
                                latest_offset - previous_offset
                            ) / time_diff

                    self.previous_kafka_offsets[topic] = latest_offset

                    # Get consumer lag
                    consumer_lag = await self._get_consumer_lag(topic)

                    metrics.append(
                        KafkaTopicMetrics(
                            topic_name=topic,
                            partition_count=partition_count,
                            message_count=latest_offset,
                            latest_offset=latest_offset,
                            consumer_lag=consumer_lag,
                            messages_per_second=messages_per_second,
                        )
                    )

        except Exception as e:
            logger.warning(f"Failed to collect Kafka metrics: {e}")

        return metrics

    async def _get_consumer_lag(self, topic: str) -> int:
        """Get consumer lag for a specific topic."""
        try:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    self.config.kafka_container,
                    "rpk",
                    "group",
                    "describe",
                    self.config.consumer_group,
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                # Parse for lag information
                for line in result.stdout.split("\n"):
                    if topic in line and "LAG" in result.stdout:
                        import re

                        numbers = re.findall(r"\d+", line)
                        if numbers:
                            return int(numbers[-1])

        except Exception as e:
            logger.debug(f"Failed to get consumer lag for {topic}: {e}")

        return 0

    async def _collect_qdrant_metrics(self) -> QdrantMetrics:
        """Collect Qdrant vector database metrics."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.config.qdrant_url}/collections/archon_vectors"
                )

                if response.status_code == 200:
                    data = response.json()
                    result = data.get("result", {})

                    metrics = QdrantMetrics(
                        timestamp=time.time(),
                        vectors_count=result.get("vectors_count", 0),
                        indexed_vectors_count=result.get("indexed_vectors_count", 0),
                        collection_status=result.get("status", "unknown"),
                        points_count=result.get("points_count", 0),
                        segments_count=result.get("segments_count", 0),
                    )

                    self.previous_qdrant_metrics = metrics
                    return metrics

        except Exception as e:
            logger.warning(f"Failed to collect Qdrant metrics: {e}")

        # Return previous or default
        if self.previous_qdrant_metrics:
            return self.previous_qdrant_metrics

        return QdrantMetrics(
            timestamp=time.time(),
            vectors_count=0,
            indexed_vectors_count=0,
            collection_status="unknown",
            points_count=0,
            segments_count=0,
        )

    async def _collect_processing_metrics(self) -> ProcessingMetrics:
        """Collect event processing metrics."""
        # Calculate from Kafka metrics
        total_processed = 0
        successful = 0
        failed = 0

        if len(self.history) > 0:
            prev_snapshot = self.history[-1]

            # Get completed/failed counts
            for metric in prev_snapshot.kafka_metrics:
                if "completed" in metric.topic_name:
                    successful = metric.message_count
                elif "failed" in metric.topic_name:
                    failed = metric.message_count

            total_processed = successful + failed

        success_rate = successful / total_processed if total_processed > 0 else 1.0

        # Calculate throughput
        throughput = 0.0
        if len(self.history) >= 2:
            time_diff = self.history[-1].timestamp - self.history[-2].timestamp
            if time_diff > 0:
                prev_total = sum(
                    m.message_count for m in self.history[-2].kafka_metrics
                )
                current_total = sum(
                    m.message_count for m in self.history[-1].kafka_metrics
                )
                throughput = (current_total - prev_total) / time_diff

        # Average latency (placeholder - would need instrumentation)
        avg_latency = 250.0  # ms (default estimate)

        return ProcessingMetrics(
            timestamp=time.time(),
            events_processed=total_processed,
            events_successful=successful,
            events_failed=failed,
            success_rate=success_rate,
            average_latency_ms=avg_latency,
            throughput_per_second=throughput,
        )

    async def _collect_service_health(self) -> List[ServiceHealthMetrics]:
        """Collect service health status."""
        services = [
            ("archon-intelligence", self.config.intelligence_url),
            ("archon-bridge", self.config.bridge_url),
            ("archon-search", self.config.search_url),
        ]

        health_metrics = []

        for service_name, url in services:
            try:
                start_time = time.time()
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{url}/health")
                    response_time_ms = (time.time() - start_time) * 1000

                    if response.status_code == 200:
                        data = response.json()
                        status = data.get("status", "unknown")
                        healthy = status == "healthy"

                        health_metrics.append(
                            ServiceHealthMetrics(
                                service_name=service_name,
                                healthy=healthy,
                                response_time_ms=response_time_ms,
                                status=status,
                            )
                        )
                    else:
                        health_metrics.append(
                            ServiceHealthMetrics(
                                service_name=service_name,
                                healthy=False,
                                response_time_ms=response_time_ms,
                                status="unhealthy",
                            )
                        )

            except Exception as e:
                logger.debug(f"Health check failed for {service_name}: {e}")
                health_metrics.append(
                    ServiceHealthMetrics(
                        service_name=service_name,
                        healthy=False,
                        response_time_ms=None,
                        status="unreachable",
                    )
                )

        return health_metrics

    def _generate_alerts(
        self,
        kafka_metrics: List[KafkaTopicMetrics],
        qdrant_metrics: QdrantMetrics,
        processing_metrics: ProcessingMetrics,
        service_health: List[ServiceHealthMetrics],
    ) -> List[Dict[str, Any]]:
        """Generate alerts based on thresholds."""
        alerts = []
        thresholds = self.config.alert_thresholds

        # Kafka consumer lag alerts
        for metric in kafka_metrics:
            if metric.consumer_lag >= thresholds.consumer_lag_critical:
                alerts.append(
                    {
                        "level": "critical",
                        "type": "consumer_lag",
                        "topic": metric.topic_name,
                        "message": f"Critical consumer lag: {metric.consumer_lag} messages",
                        "value": metric.consumer_lag,
                        "timestamp": time.time(),
                    }
                )
            elif metric.consumer_lag >= thresholds.consumer_lag_warning:
                alerts.append(
                    {
                        "level": "warning",
                        "type": "consumer_lag",
                        "topic": metric.topic_name,
                        "message": f"High consumer lag: {metric.consumer_lag} messages",
                        "value": metric.consumer_lag,
                        "timestamp": time.time(),
                    }
                )

        # Vector growth alerts
        if self.previous_qdrant_metrics and thresholds.vector_growth_decreasing_alert:
            if (
                qdrant_metrics.vectors_count
                < self.previous_qdrant_metrics.vectors_count
            ):
                alerts.append(
                    {
                        "level": "critical",
                        "type": "vector_count_decreasing",
                        "message": f"Vector count decreased: {self.previous_qdrant_metrics.vectors_count} → {qdrant_metrics.vectors_count}",
                        "timestamp": time.time(),
                    }
                )

        # Check for stagnant growth
        if len(self.history) >= 3:
            # Check last 3 snapshots
            recent_counts = [s.qdrant_metrics.vectors_count for s in self.history[-3:]]
            if len(set(recent_counts)) == 1:  # All same
                time_stagnant = self.history[-1].timestamp - self.history[-3].timestamp
                if time_stagnant >= thresholds.vector_growth_stagnant_minutes * 60:
                    alerts.append(
                        {
                            "level": "warning",
                            "type": "vector_growth_stagnant",
                            "message": f"Vector count stagnant for {time_stagnant/60:.1f} minutes",
                            "timestamp": time.time(),
                        }
                    )

        # Success rate alerts
        if processing_metrics.success_rate < thresholds.success_rate_critical:
            alerts.append(
                {
                    "level": "critical",
                    "type": "low_success_rate",
                    "message": f"Critical success rate: {processing_metrics.success_rate:.1%}",
                    "value": processing_metrics.success_rate,
                    "timestamp": time.time(),
                }
            )
        elif processing_metrics.success_rate < thresholds.success_rate_warning:
            alerts.append(
                {
                    "level": "warning",
                    "type": "low_success_rate",
                    "message": f"Low success rate: {processing_metrics.success_rate:.1%}",
                    "value": processing_metrics.success_rate,
                    "timestamp": time.time(),
                }
            )

        # Service health alerts
        for service in service_health:
            if not service.healthy:
                alerts.append(
                    {
                        "level": "critical",
                        "type": "service_unhealthy",
                        "service": service.service_name,
                        "message": f"Service {service.service_name} is {service.status}",
                        "timestamp": time.time(),
                    }
                )
            elif (
                service.response_time_ms
                and service.response_time_ms >= thresholds.service_response_critical_ms
            ):
                alerts.append(
                    {
                        "level": "warning",
                        "type": "slow_service",
                        "service": service.service_name,
                        "message": f"Service {service.service_name} slow: {service.response_time_ms:.0f}ms",
                        "timestamp": time.time(),
                    }
                )

        return alerts

    def _display_dashboard(self, snapshot: PipelineSnapshot):
        """Display real-time dashboard."""
        # Clear screen
        print("\033[2J\033[H", end="")

        print("=" * 80)
        print(
            f"📊 INGESTION PIPELINE DASHBOARD - {datetime.fromtimestamp(snapshot.timestamp).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        print("=" * 80)

        # Qdrant metrics
        print("\n🗄️  Qdrant Vector Database:")
        print(
            f"  Vectors: {snapshot.qdrant_metrics.vectors_count:,} (indexed: {snapshot.qdrant_metrics.indexed_vectors_count:,})"
        )
        print(f"  Status: {snapshot.qdrant_metrics.collection_status}")
        print(f"  Segments: {snapshot.qdrant_metrics.segments_count}")

        # Calculate growth rate
        if self.previous_qdrant_metrics:
            growth = (
                snapshot.qdrant_metrics.vectors_count
                - self.previous_qdrant_metrics.vectors_count
            )
            if growth != 0:
                print(f"  Growth: {'+' if growth > 0 else ''}{growth} vectors")

        # Kafka topics
        print("\n📨 Kafka Topics:")
        print(f"{'Topic':<50} {'Messages':<12} {'Lag':<8} {'Rate (msg/s)':<12}")
        print("-" * 80)

        for metric in snapshot.kafka_metrics:
            topic_short = metric.topic_name.replace("dev.archon-intelligence.", "")
            lag_color = ""
            if (
                metric.consumer_lag
                >= self.config.alert_thresholds.consumer_lag_critical
            ):
                lag_color = "\033[91m"  # Red
            elif (
                metric.consumer_lag >= self.config.alert_thresholds.consumer_lag_warning
            ):
                lag_color = "\033[93m"  # Yellow
            else:
                lag_color = "\033[92m"  # Green

            print(
                f"{topic_short:<50} {metric.message_count:<12,} {lag_color}{metric.consumer_lag:<8}\033[0m {metric.messages_per_second:<12.2f}"
            )

        # Processing metrics
        print("\n⚙️  Processing Metrics:")
        success_color = "\033[92m"  # Green
        if (
            snapshot.processing_metrics.success_rate
            < self.config.alert_thresholds.success_rate_critical
        ):
            success_color = "\033[91m"  # Red
        elif (
            snapshot.processing_metrics.success_rate
            < self.config.alert_thresholds.success_rate_warning
        ):
            success_color = "\033[93m"  # Yellow

        print(f"  Total Processed: {snapshot.processing_metrics.events_processed:,}")
        print(
            f"  Success Rate: {success_color}{snapshot.processing_metrics.success_rate:.1%}\033[0m"
        )
        print(
            f"  Throughput: {snapshot.processing_metrics.throughput_per_second:.2f} events/s"
        )
        print(f"  Avg Latency: {snapshot.processing_metrics.average_latency_ms:.0f}ms")

        # Service health
        print("\n🏥 Service Health:")
        for service in snapshot.service_health:
            status_color = "\033[92m" if service.healthy else "\033[91m"
            response_time = (
                f"{service.response_time_ms:.0f}ms"
                if service.response_time_ms
                else "N/A"
            )
            print(
                f"  {service.service_name:<25} {status_color}{service.status:<12}\033[0m Response: {response_time}"
            )

        # Alerts
        if snapshot.alerts:
            print(f"\n⚠️  Active Alerts ({len(snapshot.alerts)}):")
            for alert in snapshot.alerts:
                level_colors = {
                    "critical": "\033[91m",  # Red
                    "warning": "\033[93m",  # Yellow
                    "info": "\033[94m",  # Blue
                }
                color = level_colors.get(alert.get("level", "info"), "\033[0m")
                print(
                    f"  {color}[{alert.get('level', 'INFO').upper()}]\033[0m {alert.get('message', 'No message')}"
                )
        else:
            print("\n✅ No active alerts")

        print("\n" + "=" * 80)
        print("Press Ctrl+C to stop monitoring")

    def _log_summary(self, snapshot: PipelineSnapshot):
        """Log monitoring summary."""
        logger.info(
            f"Pipeline Status: {snapshot.qdrant_metrics.vectors_count:,} vectors, "
            f"{snapshot.processing_metrics.success_rate:.1%} success rate, "
            f"{len(snapshot.alerts)} alerts"
        )

        if snapshot.alerts:
            for alert in snapshot.alerts:
                if alert.get("level") == "critical":
                    logger.error(f"ALERT: {alert.get('message')}")
                elif alert.get("level") == "warning":
                    logger.warning(f"ALERT: {alert.get('message')}")

    async def _send_alerts(self, alerts: List[Dict[str, Any]]):
        """Send alerts to webhook if configured."""
        if not self.config.alert_webhook or not alerts:
            return

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                payload = {
                    "timestamp": datetime.now().isoformat(),
                    "source": "archon-ingestion-pipeline-monitor",
                    "alerts": alerts,
                }
                response = await client.post(self.config.alert_webhook, json=payload)
                if response.status_code == 200:
                    logger.info(f"Sent {len(alerts)} alerts to webhook")
                else:
                    logger.warning(
                        f"Failed to send alerts to webhook: {response.status_code}"
                    )
        except Exception as e:
            logger.error(f"Failed to send webhook alerts: {e}")

    async def _generate_final_report(self):
        """Generate final monitoring report."""
        if not self.history:
            print("\n⚠️  No monitoring data collected")
            return

        print("\n" + "=" * 80)
        print("📊 INGESTION PIPELINE MONITORING REPORT")
        print("=" * 80)

        first_snapshot = self.history[0]
        last_snapshot = self.history[-1]

        duration = last_snapshot.timestamp - first_snapshot.timestamp

        print(
            f"\nMonitoring Period: {duration:.0f} seconds ({len(self.history)} snapshots)"
        )
        print(
            f"Start: {datetime.fromtimestamp(first_snapshot.timestamp).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        print(
            f"End: {datetime.fromtimestamp(last_snapshot.timestamp).strftime('%Y-%m-%d %H:%M:%S')}"
        )

        # Vector growth summary
        print("\n🗄️  Vector Growth:")
        vector_growth = (
            last_snapshot.qdrant_metrics.vectors_count
            - first_snapshot.qdrant_metrics.vectors_count
        )
        print(f"  Start: {first_snapshot.qdrant_metrics.vectors_count:,} vectors")
        print(f"  End: {last_snapshot.qdrant_metrics.vectors_count:,} vectors")
        print(f"  Growth: {vector_growth:,} vectors")
        if duration > 0:
            print(f"  Rate: {vector_growth / duration * 60:.1f} vectors/minute")

        # Processing summary
        print("\n⚙️  Processing Summary:")
        print(
            f"  Total Processed: {last_snapshot.processing_metrics.events_processed:,}"
        )
        print(f"  Success Rate: {last_snapshot.processing_metrics.success_rate:.1%}")
        print(
            f"  Average Throughput: {last_snapshot.processing_metrics.throughput_per_second:.2f} events/s"
        )

        # Alert summary
        total_alerts = sum(len(s.alerts) for s in self.history)
        critical_alerts = sum(
            sum(1 for a in s.alerts if a.get("level") == "critical")
            for s in self.history
        )
        warning_alerts = sum(
            sum(1 for a in s.alerts if a.get("level") == "warning")
            for s in self.history
        )

        print("\n⚠️  Alert Summary:")
        print(f"  Total Alerts: {total_alerts}")
        print(f"  Critical: {critical_alerts}")
        print(f"  Warnings: {warning_alerts}")

        print("\n" + "=" * 80)

        # Save to JSON if configured
        if self.config.json_output_path:
            await self._save_json_report()

    async def _save_json_report(self):
        """Save monitoring data to JSON file."""
        output_path = Path(self.config.json_output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "monitoring_start": datetime.fromtimestamp(
                self.history[0].timestamp
            ).isoformat(),
            "monitoring_end": datetime.fromtimestamp(
                self.history[-1].timestamp
            ).isoformat(),
            "duration_seconds": self.history[-1].timestamp - self.history[0].timestamp,
            "snapshot_count": len(self.history),
            "snapshots": [s.to_dict() for s in self.history],
            "summary": {
                "vector_growth": self.history[-1].qdrant_metrics.vectors_count
                - self.history[0].qdrant_metrics.vectors_count,
                "total_events_processed": self.history[
                    -1
                ].processing_metrics.events_processed,
                "final_success_rate": self.history[-1].processing_metrics.success_rate,
                "total_alerts": sum(len(s.alerts) for s in self.history),
            },
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        print(f"\n💾 Monitoring data saved to: {output_path}")

    def stop_monitoring(self):
        """Stop monitoring."""
        self.monitoring_active = False


# =============================================================================
# CLI
# =============================================================================


async def main():
    """Main entry point for ingestion pipeline monitoring."""
    parser = argparse.ArgumentParser(
        description="Archon Ingestion Pipeline Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor with real-time dashboard
  python scripts/monitor_ingestion_pipeline.py --dashboard

  # Monitor for 5 minutes and save JSON report
  python scripts/monitor_ingestion_pipeline.py --duration 300 --json pipeline_metrics.json

  # Monitor with custom check interval
  python scripts/monitor_ingestion_pipeline.py --dashboard --interval 5

  # Monitor with alert webhook
  python scripts/monitor_ingestion_pipeline.py --dashboard --alert-webhook https://hooks.slack.com/...
        """,
    )

    parser.add_argument(
        "--dashboard", action="store_true", help="Show real-time dashboard"
    )
    parser.add_argument(
        "--duration",
        type=int,
        help="Monitoring duration in seconds (default: indefinite)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Check interval in seconds (default: 10)",
    )
    parser.add_argument("--json", help="Save monitoring data to JSON file")
    parser.add_argument("--alert-webhook", help="Webhook URL for alerts")

    # Alert threshold overrides
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

    args = parser.parse_args()

    # Create configuration
    alert_thresholds = AlertThresholds(
        consumer_lag_warning=args.consumer_lag_warning,
        consumer_lag_critical=args.consumer_lag_critical,
    )

    config = MonitorConfig(
        check_interval_seconds=args.interval,
        duration_seconds=args.duration,
        dashboard_mode=args.dashboard,
        json_output_path=args.json,
        alert_thresholds=alert_thresholds,
        alert_webhook=args.alert_webhook,
    )

    # Create and start monitor
    monitor = IngestionPipelineMonitor(config)

    # Signal handling
    def signal_handler(signum, frame):
        logger.info("Received interrupt signal")
        monitor.stop_monitoring()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await monitor.start_monitoring()
        return 0
    except Exception as e:
        logger.error(f"Monitoring error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
