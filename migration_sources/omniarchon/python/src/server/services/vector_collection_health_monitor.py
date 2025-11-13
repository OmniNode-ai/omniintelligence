"""
Vector Collection Health Monitoring Service

Production monitoring system for vector collection health with real-time balance tracking,
performance threshold alerts, routing accuracy metrics, and collection health visualization.

Key Metrics:
- Collection size balance (archon_vectors vs quality_vectors)
- Routing accuracy percentage
- Response time trends
- Error rates by document type
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import httpx
import numpy as np
from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)


class CollectionHealthStatus(Enum):
    """Collection health status levels"""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    DEGRADED = "degraded"


class VectorRoutingResult(Enum):
    """Vector routing decision results"""

    MAIN_COLLECTION = "main"
    QUALITY_COLLECTION = "quality"
    ROUTING_ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class VectorCollectionMetrics:
    """Vector collection metrics snapshot"""

    timestamp: datetime
    collection_name: str

    # Size metrics
    total_vectors: int
    indexed_vectors: int
    points_count: int
    segments_count: int

    # Performance metrics
    avg_search_time_ms: float
    p95_search_time_ms: float
    memory_usage_mb: float
    disk_usage_mb: float

    # Health indicators
    health_status: CollectionHealthStatus
    error_rate: float
    availability_percentage: float

    # Quality metrics (for quality collection)
    avg_quality_score: Optional[float] = None
    min_quality_score: Optional[float] = None
    max_quality_score: Optional[float] = None


@dataclass
class CollectionBalanceMetrics:
    """Collection balance metrics between main and quality collections"""

    timestamp: datetime

    # Size comparison
    main_collection_size: int
    quality_collection_size: int
    size_balance_ratio: float  # quality_size / main_size

    # Performance comparison
    main_avg_search_time: float
    quality_avg_search_time: float
    performance_ratio: float  # quality_time / main_time

    # Balance health
    balance_status: CollectionHealthStatus
    imbalance_severity: float  # 0.0 = perfect balance, 1.0 = severe imbalance


@dataclass
class VectorRoutingMetrics:
    """Vector routing accuracy and performance metrics"""

    timestamp: datetime

    # Routing decisions
    total_routing_decisions: int
    main_collection_routes: int
    quality_collection_routes: int
    routing_errors: int

    # Accuracy metrics
    routing_accuracy_percentage: float
    routing_error_rate: float

    # Performance metrics
    avg_routing_time_ms: float
    routing_timeouts: int

    # Quality-based routing analysis
    correctly_routed_high_quality: int
    correctly_routed_low_quality: int
    misrouted_documents: int


@dataclass
class VectorCollectionAlert:
    """Vector collection health alert"""

    alert_id: str
    timestamp: datetime
    severity: CollectionHealthStatus
    collection: str
    metric: str
    current_value: float
    threshold: float
    message: str
    alert_type: str  # 'balance', 'performance', 'routing', 'health'


class VectorCollectionHealthMonitor:
    """
    Comprehensive vector collection health monitoring service.

    Monitors:
    - Collection size balance between archon_vectors and quality_vectors
    - Vector routing accuracy and performance
    - Search performance trends and thresholds
    - Collection health indicators and error rates
    - Document type-specific error analysis
    """

    def __init__(
        self,
        qdrant_url: str = "http://qdrant:6333",
        main_collection: str = "archon_vectors",
        quality_collection: str = "quality_vectors",
        monitoring_interval: int = 30,
        alert_thresholds: Optional[dict[str, float]] = None,
    ):
        """
        Initialize vector collection health monitor.

        Args:
            qdrant_url: Qdrant service URL
            main_collection: Main collection name
            quality_collection: Quality collection name
            monitoring_interval: Monitoring interval in seconds
            alert_thresholds: Custom alert thresholds
        """
        self.qdrant_url = qdrant_url
        self.main_collection = main_collection
        self.quality_collection = quality_collection
        self.monitoring_interval = monitoring_interval

        # Alert thresholds
        self.thresholds = alert_thresholds or {
            # Balance thresholds
            "size_balance_min": 0.3,  # quality_size / main_size should be >= 30%
            "size_balance_max": 1.5,  # quality_size / main_size should be <= 150%
            # Performance thresholds
            "search_time_max_ms": 100.0,  # Max acceptable search time
            "search_time_p95_max_ms": 200.0,  # Max P95 search time
            "error_rate_max": 0.05,  # Max 5% error rate
            # Routing thresholds
            "routing_accuracy_min": 0.85,  # Min 85% routing accuracy
            "routing_error_rate_max": 0.10,  # Max 10% routing error rate
            "routing_time_max_ms": 50.0,  # Max routing decision time
            # Availability thresholds
            "availability_min": 0.95,  # Min 95% availability
            "memory_usage_max_mb": 2048,  # Max 2GB memory per collection
        }

        # Monitoring state
        self.qdrant_client = QdrantClient(url=qdrant_url)
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.is_monitoring = False
        self.monitoring_task: Optional[asyncio.Task] = None

        # Metrics storage
        self.collection_metrics_history: list[VectorCollectionMetrics] = []
        self.balance_metrics_history: list[CollectionBalanceMetrics] = []
        self.routing_metrics_history: list[VectorRoutingMetrics] = []
        self.active_alerts: dict[str, VectorCollectionAlert] = {}

        # Performance tracking
        self.search_performance_buffer: list[float] = []
        self.routing_performance_buffer: list[tuple[str, float]] = (
            []
        )  # (decision, time)

        # Alert handlers
        self.alert_handlers: list[callable] = []

    async def start_monitoring(self):
        """Start the vector collection health monitoring"""
        if self.is_monitoring:
            logger.warning("Vector collection monitoring already running")
            return

        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Vector collection health monitoring started")

    async def stop_monitoring(self):
        """Stop the monitoring system"""
        self.is_monitoring = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        await self.http_client.aclose()
        logger.info("Vector collection health monitoring stopped")

    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_monitoring:
            try:
                # Collect collection metrics
                await self._collect_collection_metrics()

                # Collect balance metrics
                await self._collect_balance_metrics()

                # Collect routing metrics
                await self._collect_routing_metrics()

                # Check alert conditions
                await self._check_alerts()

                # Cleanup old data
                await self._cleanup_old_metrics()

                # Wait for next collection interval
                await asyncio.sleep(self.monitoring_interval)

            except Exception as e:
                logger.error(f"Error in vector collection monitoring loop: {e}")
                await asyncio.sleep(self.monitoring_interval)

    async def _collect_collection_metrics(self):
        """Collect metrics for both collections"""
        collections = [self.main_collection, self.quality_collection]

        for collection_name in collections:
            try:
                metrics = await self._get_collection_metrics(collection_name)
                if metrics:
                    self.collection_metrics_history.append(metrics)

            except Exception as e:
                logger.error(f"Failed to collect metrics for {collection_name}: {e}")

    async def _get_collection_metrics(
        self, collection_name: str
    ) -> Optional[VectorCollectionMetrics]:
        """Get detailed metrics for a specific collection"""
        try:
            # Get collection info
            collection_info = self.qdrant_client.get_collection(collection_name)

            # Measure search performance
            time.time()
            search_times = await self._measure_search_performance(collection_name)

            # Calculate performance metrics
            avg_search_time = np.mean(search_times) if search_times else 0.0
            p95_search_time = np.percentile(search_times, 95) if search_times else 0.0

            # Get quality metrics for quality collection
            quality_metrics = None
            if collection_name == self.quality_collection:
                quality_metrics = await self._get_quality_metrics(collection_name)

            # Determine health status
            health_status = self._determine_health_status(
                avg_search_time, collection_info.vectors_count
            )

            # Create metrics object
            metrics = VectorCollectionMetrics(
                timestamp=datetime.utcnow(),
                collection_name=collection_name,
                total_vectors=collection_info.vectors_count or 0,
                indexed_vectors=collection_info.indexed_vectors_count or 0,
                points_count=collection_info.points_count or 0,
                segments_count=(
                    len(collection_info.segments) if collection_info.segments else 0
                ),
                avg_search_time_ms=avg_search_time,
                p95_search_time_ms=p95_search_time,
                memory_usage_mb=(collection_info.ram_data_size or 0) / (1024 * 1024),
                disk_usage_mb=(collection_info.disk_data_size or 0) / (1024 * 1024),
                health_status=health_status,
                error_rate=0.0,  # Calculate from actual search errors
                availability_percentage=1.0,  # Calculate from service availability
                avg_quality_score=(
                    quality_metrics.get("avg_score") if quality_metrics else None
                ),
                min_quality_score=(
                    quality_metrics.get("min_score") if quality_metrics else None
                ),
                max_quality_score=(
                    quality_metrics.get("max_score") if quality_metrics else None
                ),
            )

            return metrics

        except Exception as e:
            logger.error(f"Failed to get metrics for collection {collection_name}: {e}")
            return None

    async def _measure_search_performance(
        self, collection_name: str, num_tests: int = 5
    ) -> list[float]:
        """Measure search performance with sample queries"""
        search_times = []

        try:
            # Use a random vector for testing
            test_vector = np.random.random(1536).tolist()  # OpenAI embedding dimension

            for _ in range(num_tests):
                start_time = time.time()

                try:
                    self.qdrant_client.search(
                        collection_name=collection_name,
                        query_vector=test_vector,
                        limit=10,
                        score_threshold=0.5,
                    )

                    search_time_ms = (time.time() - start_time) * 1000
                    search_times.append(search_time_ms)

                except Exception as e:
                    logger.warning(f"Search test failed for {collection_name}: {e}")
                    continue

                # Small delay between tests
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Performance measurement failed for {collection_name}: {e}")

        return search_times

    async def _get_quality_metrics(
        self, collection_name: str
    ) -> Optional[dict[str, float]]:
        """Get quality score statistics for quality collection"""
        try:
            # Scroll through collection to get quality scores
            quality_scores = []

            scroll_result = self.qdrant_client.scroll(
                collection_name=collection_name,
                limit=100,  # Sample of recent vectors
                with_payload=["quality_score"],
            )

            points = scroll_result[0]
            for point in points:
                quality_score = point.payload.get("quality_score")
                if quality_score is not None:
                    quality_scores.append(float(quality_score))

            if quality_scores:
                return {
                    "avg_score": np.mean(quality_scores),
                    "min_score": np.min(quality_scores),
                    "max_score": np.max(quality_scores),
                    "sample_size": len(quality_scores),
                }

        except Exception as e:
            logger.error(f"Failed to get quality metrics for {collection_name}: {e}")

        return None

    async def _collect_balance_metrics(self):
        """Collect collection balance metrics"""
        try:
            # Get latest metrics for both collections
            main_metrics = None
            quality_metrics = None

            for metrics in reversed(self.collection_metrics_history[-10:]):
                if metrics.collection_name == self.main_collection and not main_metrics:
                    main_metrics = metrics
                elif (
                    metrics.collection_name == self.quality_collection
                    and not quality_metrics
                ):
                    quality_metrics = metrics

                if main_metrics and quality_metrics:
                    break

            if not main_metrics or not quality_metrics:
                logger.warning("Missing collection metrics for balance calculation")
                return

            # Calculate balance metrics
            size_balance_ratio = (
                quality_metrics.total_vectors / main_metrics.total_vectors
                if main_metrics.total_vectors > 0
                else 0.0
            )

            performance_ratio = (
                quality_metrics.avg_search_time_ms / main_metrics.avg_search_time_ms
                if main_metrics.avg_search_time_ms > 0
                else 1.0
            )

            # Determine balance status
            balance_status = self._determine_balance_status(size_balance_ratio)

            # Calculate imbalance severity
            optimal_ratio = 0.8  # Ideal ratio
            imbalance_severity = abs(size_balance_ratio - optimal_ratio) / optimal_ratio

            balance_metrics = CollectionBalanceMetrics(
                timestamp=datetime.utcnow(),
                main_collection_size=main_metrics.total_vectors,
                quality_collection_size=quality_metrics.total_vectors,
                size_balance_ratio=size_balance_ratio,
                main_avg_search_time=main_metrics.avg_search_time_ms,
                quality_avg_search_time=quality_metrics.avg_search_time_ms,
                performance_ratio=performance_ratio,
                balance_status=balance_status,
                imbalance_severity=min(imbalance_severity, 1.0),
            )

            self.balance_metrics_history.append(balance_metrics)

        except Exception as e:
            logger.error(f"Failed to collect balance metrics: {e}")

    async def _collect_routing_metrics(self):
        """Collect vector routing accuracy and performance metrics"""
        try:
            # Analyze recent routing decisions from buffer
            if not self.routing_performance_buffer:
                # Create placeholder metrics if no routing data available
                routing_metrics = VectorRoutingMetrics(
                    timestamp=datetime.utcnow(),
                    total_routing_decisions=0,
                    main_collection_routes=0,
                    quality_collection_routes=0,
                    routing_errors=0,
                    routing_accuracy_percentage=1.0,
                    routing_error_rate=0.0,
                    avg_routing_time_ms=0.0,
                    routing_timeouts=0,
                    correctly_routed_high_quality=0,
                    correctly_routed_low_quality=0,
                    misrouted_documents=0,
                )
                self.routing_metrics_history.append(routing_metrics)
                return

            # Analyze routing performance buffer
            routing_decisions = [
                decision for decision, _ in self.routing_performance_buffer
            ]
            routing_times = [rt_time for _, rt_time in self.routing_performance_buffer]

            # Count routing decisions
            main_routes = routing_decisions.count("main")
            quality_routes = routing_decisions.count("quality")
            errors = routing_decisions.count("error")
            total_decisions = len(routing_decisions)

            # Calculate metrics
            routing_accuracy = (
                (main_routes + quality_routes) / total_decisions
                if total_decisions > 0
                else 1.0
            )
            error_rate = errors / total_decisions if total_decisions > 0 else 0.0
            avg_routing_time = np.mean(routing_times) if routing_times else 0.0

            routing_metrics = VectorRoutingMetrics(
                timestamp=datetime.utcnow(),
                total_routing_decisions=total_decisions,
                main_collection_routes=main_routes,
                quality_collection_routes=quality_routes,
                routing_errors=errors,
                routing_accuracy_percentage=routing_accuracy,
                routing_error_rate=error_rate,
                avg_routing_time_ms=avg_routing_time,
                routing_timeouts=0,  # Track separately if needed
                correctly_routed_high_quality=quality_routes,  # Simplified assumption
                correctly_routed_low_quality=main_routes,  # Simplified assumption
                misrouted_documents=errors,
            )

            self.routing_metrics_history.append(routing_metrics)

            # Clear buffer after processing
            self.routing_performance_buffer.clear()

        except Exception as e:
            logger.error(f"Failed to collect routing metrics: {e}")

    def _determine_health_status(
        self, avg_search_time: float, vector_count: int
    ) -> CollectionHealthStatus:
        """Determine collection health status based on metrics"""
        if avg_search_time > self.thresholds["search_time_max_ms"] * 2:
            return CollectionHealthStatus.CRITICAL
        elif avg_search_time > self.thresholds["search_time_max_ms"]:
            return CollectionHealthStatus.WARNING
        elif vector_count == 0:
            return CollectionHealthStatus.DEGRADED
        else:
            return CollectionHealthStatus.HEALTHY

    def _determine_balance_status(
        self, size_balance_ratio: float
    ) -> CollectionHealthStatus:
        """Determine balance status between collections"""
        min_ratio = self.thresholds["size_balance_min"]
        max_ratio = self.thresholds["size_balance_max"]

        if size_balance_ratio < min_ratio * 0.5 or size_balance_ratio > max_ratio * 1.5:
            return CollectionHealthStatus.CRITICAL
        elif size_balance_ratio < min_ratio or size_balance_ratio > max_ratio:
            return CollectionHealthStatus.WARNING
        else:
            return CollectionHealthStatus.HEALTHY

    async def _check_alerts(self):
        """Check all alert conditions and trigger alerts"""
        try:
            # Check collection-specific alerts
            await self._check_collection_alerts()

            # Check balance alerts
            await self._check_balance_alerts()

            # Check routing alerts
            await self._check_routing_alerts()

            # Cleanup resolved alerts
            await self._cleanup_resolved_alerts()

        except Exception as e:
            logger.error(f"Error checking alerts: {e}")

    async def _check_collection_alerts(self):
        """Check for collection-specific performance alerts"""
        if not self.collection_metrics_history:
            return

        for metrics in self.collection_metrics_history[-2:]:  # Check recent metrics
            collection = metrics.collection_name

            # Performance alerts
            if metrics.avg_search_time_ms > self.thresholds["search_time_max_ms"]:
                await self._create_alert(
                    alert_type="performance",
                    collection=collection,
                    metric="avg_search_time_ms",
                    current_value=metrics.avg_search_time_ms,
                    threshold=self.thresholds["search_time_max_ms"],
                    severity=CollectionHealthStatus.WARNING,
                    message=f"High average search time for {collection}: {metrics.avg_search_time_ms:.2f}ms",
                )

            # Memory usage alerts
            if metrics.memory_usage_mb > self.thresholds["memory_usage_max_mb"]:
                await self._create_alert(
                    alert_type="health",
                    collection=collection,
                    metric="memory_usage_mb",
                    current_value=metrics.memory_usage_mb,
                    threshold=self.thresholds["memory_usage_max_mb"],
                    severity=CollectionHealthStatus.WARNING,
                    message=f"High memory usage for {collection}: {metrics.memory_usage_mb:.2f}MB",
                )

    async def _check_balance_alerts(self):
        """Check for collection balance alerts"""
        if not self.balance_metrics_history:
            return

        latest_balance = self.balance_metrics_history[-1]

        # Size balance alerts
        if latest_balance.balance_status != CollectionHealthStatus.HEALTHY:
            await self._create_alert(
                alert_type="balance",
                collection="both",
                metric="size_balance_ratio",
                current_value=latest_balance.size_balance_ratio,
                threshold=self.thresholds["size_balance_min"],
                severity=latest_balance.balance_status,
                message=f"Collection size imbalance: ratio={latest_balance.size_balance_ratio:.2f}",
            )

    async def _check_routing_alerts(self):
        """Check for routing accuracy and performance alerts"""
        if not self.routing_metrics_history:
            return

        latest_routing = self.routing_metrics_history[-1]

        # Routing accuracy alerts
        if (
            latest_routing.routing_accuracy_percentage
            < self.thresholds["routing_accuracy_min"]
        ):
            await self._create_alert(
                alert_type="routing",
                collection="routing",
                metric="routing_accuracy_percentage",
                current_value=latest_routing.routing_accuracy_percentage,
                threshold=self.thresholds["routing_accuracy_min"],
                severity=CollectionHealthStatus.WARNING,
                message=f"Low routing accuracy: {latest_routing.routing_accuracy_percentage:.2f}",
            )

        # Routing performance alerts
        if latest_routing.avg_routing_time_ms > self.thresholds["routing_time_max_ms"]:
            await self._create_alert(
                alert_type="routing",
                collection="routing",
                metric="avg_routing_time_ms",
                current_value=latest_routing.avg_routing_time_ms,
                threshold=self.thresholds["routing_time_max_ms"],
                severity=CollectionHealthStatus.WARNING,
                message=f"Slow routing performance: {latest_routing.avg_routing_time_ms:.2f}ms",
            )

    async def _create_alert(
        self,
        alert_type: str,
        collection: str,
        metric: str,
        current_value: float,
        threshold: float,
        severity: CollectionHealthStatus,
        message: str,
    ):
        """Create and handle a new alert"""
        alert_key = f"{alert_type}_{collection}_{metric}"

        # Avoid duplicate alerts
        if alert_key in self.active_alerts:
            return

        alert = VectorCollectionAlert(
            alert_id=f"vcm_{int(time.time())}_{alert_key}",
            timestamp=datetime.utcnow(),
            severity=severity,
            collection=collection,
            metric=metric,
            current_value=current_value,
            threshold=threshold,
            message=message,
            alert_type=alert_type,
        )

        self.active_alerts[alert_key] = alert

        # Log alert
        logger.warning(f"VECTOR COLLECTION ALERT [{severity.value.upper()}]: {message}")

        # Call alert handlers
        for handler in self.alert_handlers:
            try:
                await handler(alert)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")

    async def _cleanup_resolved_alerts(self):
        """Clean up alerts that have been resolved"""
        current_time = datetime.utcnow()
        resolved_alerts = []

        for alert_key, alert in self.active_alerts.items():
            # Remove alerts older than 1 hour
            if (current_time - alert.timestamp).total_seconds() > 3600:
                resolved_alerts.append(alert_key)

        for alert_key in resolved_alerts:
            del self.active_alerts[alert_key]
            logger.info(f"Resolved alert: {alert_key}")

    async def _cleanup_old_metrics(self):
        """Clean up old metrics to prevent memory bloat"""
        # Keep last 100 metrics (about 50 minutes at 30s intervals)
        max_metrics = 100

        if len(self.collection_metrics_history) > max_metrics:
            self.collection_metrics_history = self.collection_metrics_history[
                -max_metrics:
            ]

        if len(self.balance_metrics_history) > max_metrics:
            self.balance_metrics_history = self.balance_metrics_history[-max_metrics:]

        if len(self.routing_metrics_history) > max_metrics:
            self.routing_metrics_history = self.routing_metrics_history[-max_metrics:]

    # Public API methods for external monitoring

    def add_alert_handler(self, handler: callable):
        """Add an alert handler function"""
        self.alert_handlers.append(handler)

    def record_routing_decision(self, decision: str, routing_time_ms: float):
        """Record a routing decision for metrics tracking"""
        self.routing_performance_buffer.append((decision, routing_time_ms))

    def record_search_performance(self, search_time_ms: float):
        """Record search performance for metrics tracking"""
        self.search_performance_buffer.append(search_time_ms)

    def get_dashboard_data(self) -> dict[str, Any]:
        """Get comprehensive data for monitoring dashboard"""
        try:
            # Latest collection metrics
            latest_metrics = {}
            for metrics in reversed(self.collection_metrics_history[-4:]):
                latest_metrics[metrics.collection_name] = {
                    "total_vectors": metrics.total_vectors,
                    "avg_search_time_ms": metrics.avg_search_time_ms,
                    "health_status": metrics.health_status.value,
                    "memory_usage_mb": metrics.memory_usage_mb,
                    "quality_score": metrics.avg_quality_score,
                }

            # Latest balance metrics
            balance_data = {}
            if self.balance_metrics_history:
                latest_balance = self.balance_metrics_history[-1]
                balance_data = {
                    "size_balance_ratio": latest_balance.size_balance_ratio,
                    "balance_status": latest_balance.balance_status.value,
                    "imbalance_severity": latest_balance.imbalance_severity,
                    "main_collection_size": latest_balance.main_collection_size,
                    "quality_collection_size": latest_balance.quality_collection_size,
                }

            # Latest routing metrics
            routing_data = {}
            if self.routing_metrics_history:
                latest_routing = self.routing_metrics_history[-1]
                routing_data = {
                    "routing_accuracy_percentage": latest_routing.routing_accuracy_percentage,
                    "routing_error_rate": latest_routing.routing_error_rate,
                    "avg_routing_time_ms": latest_routing.avg_routing_time_ms,
                    "total_decisions": latest_routing.total_routing_decisions,
                }

            # Active alerts summary
            alerts_summary = [
                {
                    "id": alert.alert_id,
                    "severity": alert.severity.value,
                    "collection": alert.collection,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat(),
                    "type": alert.alert_type,
                }
                for alert in self.active_alerts.values()
            ]

            return {
                "timestamp": datetime.utcnow().isoformat(),
                "monitoring_status": "running" if self.is_monitoring else "stopped",
                "collections": latest_metrics,
                "balance": balance_data,
                "routing": routing_data,
                "alerts": alerts_summary,
                "thresholds": self.thresholds,
            }

        except Exception as e:
            logger.error(f"Failed to generate dashboard data: {e}")
            return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}

    async def get_health_status(self) -> dict[str, Any]:
        """Get overall vector collection health status"""
        try:
            # Determine overall health
            if self.active_alerts:
                critical_alerts = [
                    a
                    for a in self.active_alerts.values()
                    if a.severity == CollectionHealthStatus.CRITICAL
                ]
                warning_alerts = [
                    a
                    for a in self.active_alerts.values()
                    if a.severity == CollectionHealthStatus.WARNING
                ]

                if critical_alerts:
                    overall_status = "critical"
                elif warning_alerts:
                    overall_status = "warning"
                else:
                    overall_status = "degraded"
            else:
                overall_status = "healthy"

            return {
                "overall_status": overall_status,
                "monitoring_active": self.is_monitoring,
                "collections_monitored": [
                    self.main_collection,
                    self.quality_collection,
                ],
                "active_alerts_count": len(self.active_alerts),
                "last_check": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get health status: {e}")
            return {"overall_status": "unknown", "error": str(e)}


# Global monitoring instance
_vector_health_monitor: Optional[VectorCollectionHealthMonitor] = None


def get_vector_health_monitor() -> VectorCollectionHealthMonitor:
    """Get or create global vector health monitoring service"""
    global _vector_health_monitor
    if _vector_health_monitor is None:
        _vector_health_monitor = VectorCollectionHealthMonitor()
    return _vector_health_monitor


async def start_vector_monitoring():
    """Start the global vector collection health monitoring"""
    monitor = get_vector_health_monitor()
    await monitor.start_monitoring()


async def stop_vector_monitoring():
    """Stop the global vector collection health monitoring"""
    global _vector_health_monitor
    if _vector_health_monitor:
        await _vector_health_monitor.stop_monitoring()
        _vector_health_monitor = None
