"""
Stability Monitoring Service for Archon

Real-time monitoring and alerting for system stability issues including
resource exhaustion, connection pool health, and service degradation.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import psutil

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ServiceState(Enum):
    """Service health states"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    RECOVERING = "recovering"


@dataclass
class ResourceMetrics:
    """Resource usage metrics snapshot"""

    timestamp: datetime
    memory_usage_percent: float
    cpu_usage_percent: float
    open_files_count: int
    network_connections_count: int
    active_tasks_count: int
    disk_usage_percent: float
    available_memory_mb: float
    load_average: float


@dataclass
class ServiceHealthMetric:
    """Service health metrics"""

    service_name: str
    timestamp: datetime
    state: ServiceState
    response_time_ms: float
    error_rate: float
    consecutive_failures: int
    last_success: Optional[datetime]
    custom_metrics: dict[str, Any]


@dataclass
class StabilityAlert:
    """Stability alert data"""

    alert_id: str
    timestamp: datetime
    severity: AlertSeverity
    service: str
    metric: str
    current_value: float
    threshold: float
    message: str
    correlation_id: Optional[str] = None


class CircuitBreakerState:
    """Circuit breaker state management"""

    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def record_success(self):
        """Record successful operation"""
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"
            self.failure_count = 0

    def record_failure(self):
        """Record failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

    def can_attempt(self) -> bool:
        """Check if operation can be attempted"""
        if self.state == "CLOSED":
            return True
        elif self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout_seconds:
                self.state = "HALF_OPEN"
                return True
            return False
        else:  # HALF_OPEN
            return True


class StabilityMonitoringService:
    """
    Comprehensive stability monitoring service.

    Monitors:
    - Resource usage (memory, CPU, file descriptors, connections)
    - Service health and response times
    - Connection pool utilization
    - Background task health
    - Circuit breaker states
    """

    def __init__(
        self,
        monitoring_interval: int = 10,
        alert_callback: Optional[Callable] = None,
        resource_thresholds: Optional[dict[str, float]] = None,
    ):
        self.monitoring_interval = monitoring_interval
        self.alert_callback = alert_callback
        self.is_monitoring = False
        self.monitoring_task: Optional[asyncio.Task] = None

        # Default resource thresholds
        self.thresholds = resource_thresholds or {
            "memory_usage_percent": 85.0,
            "cpu_usage_percent": 80.0,
            "open_files_count": 1000,
            "network_connections_count": 500,
            "active_tasks_count": 100,
            "disk_usage_percent": 90.0,
            "load_average": 4.0,
        }

        # State tracking
        self.resource_history: list[ResourceMetrics] = []
        self.service_health: dict[str, ServiceHealthMetric] = {}
        self.circuit_breakers: dict[str, CircuitBreakerState] = {}
        self.active_alerts: dict[str, StabilityAlert] = {}

        # Alert counters
        self.alert_counter = 0

    async def start_monitoring(self):
        """Start the monitoring loop"""
        if self.is_monitoring:
            logger.warning("Stability monitoring already running")
            return

        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Stability monitoring service started")

    async def stop_monitoring(self):
        """Stop the monitoring loop"""
        if not self.is_monitoring:
            return

        self.is_monitoring = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info("Stability monitoring service stopped")

    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_monitoring:
            try:
                # Collect resource metrics
                metrics = await self._collect_resource_metrics()
                self.resource_history.append(metrics)

                # Keep only last 100 metrics (~17 minutes at 10s intervals)
                if len(self.resource_history) > 100:
                    self.resource_history = self.resource_history[-100:]

                # Check for alert conditions
                await self._check_resource_alerts(metrics)

                # Check service health
                await self._check_service_health()

                # Update circuit breaker states
                await self._update_circuit_breakers()

                # Clean up resolved alerts
                await self._cleanup_resolved_alerts()

            except Exception as e:
                logger.error(f"Error in stability monitoring loop: {e}")

            await asyncio.sleep(self.monitoring_interval)

    async def _collect_resource_metrics(self) -> ResourceMetrics:
        """Collect current resource usage metrics"""
        try:
            # Get memory info
            memory = psutil.virtual_memory()

            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Get process info
            process = psutil.Process()
            open_files = len(process.open_files())

            # Get network connections
            connections = len(psutil.net_connections())

            # Get active asyncio tasks
            active_tasks = len(asyncio.all_tasks())

            # Get disk usage
            disk = psutil.disk_usage("/")
            disk_percent = (disk.used / disk.total) * 100

            # Get load average (Unix-like systems)
            try:
                load_avg = psutil.getloadavg()[0]  # 1-minute load average
            except (AttributeError, OSError):
                load_avg = 0.0  # Windows doesn't have load average

            return ResourceMetrics(
                timestamp=datetime.utcnow(),
                memory_usage_percent=memory.percent,
                cpu_usage_percent=cpu_percent,
                open_files_count=open_files,
                network_connections_count=connections,
                active_tasks_count=active_tasks,
                disk_usage_percent=disk_percent,
                available_memory_mb=memory.available / 1024 / 1024,
                load_average=load_avg,
            )

        except Exception as e:
            logger.error(f"Failed to collect resource metrics: {e}")
            # Return empty metrics on error
            return ResourceMetrics(
                timestamp=datetime.utcnow(),
                memory_usage_percent=0.0,
                cpu_usage_percent=0.0,
                open_files_count=0,
                network_connections_count=0,
                active_tasks_count=0,
                disk_usage_percent=0.0,
                available_memory_mb=0.0,
                load_average=0.0,
            )

    async def _check_resource_alerts(self, metrics: ResourceMetrics):
        """Check resource metrics against thresholds and generate alerts"""
        checks = [
            ("memory_usage_percent", metrics.memory_usage_percent, AlertSeverity.HIGH),
            ("cpu_usage_percent", metrics.cpu_usage_percent, AlertSeverity.MEDIUM),
            ("open_files_count", metrics.open_files_count, AlertSeverity.CRITICAL),
            (
                "network_connections_count",
                metrics.network_connections_count,
                AlertSeverity.HIGH,
            ),
            ("active_tasks_count", metrics.active_tasks_count, AlertSeverity.MEDIUM),
            ("disk_usage_percent", metrics.disk_usage_percent, AlertSeverity.HIGH),
            ("load_average", metrics.load_average, AlertSeverity.MEDIUM),
        ]

        for metric_name, current_value, severity in checks:
            threshold = self.thresholds.get(metric_name, float("inf"))

            if current_value > threshold:
                alert_id = f"resource_{metric_name}_{int(time.time())}"

                # Avoid duplicate alerts
                existing_alert = next(
                    (
                        alert
                        for alert in self.active_alerts.values()
                        if alert.metric == metric_name and alert.service == "system"
                    ),
                    None,
                )

                if not existing_alert:
                    alert = StabilityAlert(
                        alert_id=alert_id,
                        timestamp=datetime.utcnow(),
                        severity=severity,
                        service="system",
                        metric=metric_name,
                        current_value=current_value,
                        threshold=threshold,
                        message=f"{metric_name} exceeded threshold: {current_value:.2f} > {threshold:.2f}",
                    )

                    self.active_alerts[alert_id] = alert
                    await self._send_alert(alert)

    async def _check_service_health(self):
        """Check health of registered services"""
        # This would integrate with service discovery to check health endpoints
        # For now, we'll focus on basic connection health

        services_to_check = [
            "archon-search:8055",
            "archon-bridge:8054",
            "archon-intelligence:8053",
            "qdrant:6333",
            "memgraph:7687",
        ]

        for service in services_to_check:
            try:
                health_metric = await self._check_individual_service_health(service)
                self.service_health[service] = health_metric

                # Generate alerts for unhealthy services
                if health_metric.state in [
                    ServiceState.UNHEALTHY,
                    ServiceState.DEGRADED,
                ]:
                    await self._generate_service_alert(health_metric)

            except Exception as e:
                logger.error(f"Failed to check health for service {service}: {e}")

    async def _check_individual_service_health(
        self, service: str
    ) -> ServiceHealthMetric:
        """Check health of individual service"""
        import httpx

        service_name, port = service.split(":")
        health_url = f"http://{service}/health"

        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(health_url)
                response_time = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    state = ServiceState.HEALTHY
                    error_rate = 0.0
                    consecutive_failures = 0
                    last_success = datetime.utcnow()
                else:
                    state = ServiceState.DEGRADED
                    error_rate = 1.0
                    consecutive_failures = 1
                    last_success = None

        except Exception:
            response_time = (time.time() - start_time) * 1000
            state = ServiceState.UNHEALTHY
            error_rate = 1.0
            consecutive_failures = 1
            last_success = None

        return ServiceHealthMetric(
            service_name=service,
            timestamp=datetime.utcnow(),
            state=state,
            response_time_ms=response_time,
            error_rate=error_rate,
            consecutive_failures=consecutive_failures,
            last_success=last_success,
            custom_metrics={},
        )

    async def _generate_service_alert(self, health_metric: ServiceHealthMetric):
        """Generate alert for unhealthy service"""
        alert_id = f"service_{health_metric.service_name}_{int(time.time())}"

        # Check if we already have an active alert for this service
        existing_alert = next(
            (
                alert
                for alert in self.active_alerts.values()
                if alert.service == health_metric.service_name
                and "health" in alert.metric
            ),
            None,
        )

        if not existing_alert:
            severity = (
                AlertSeverity.CRITICAL
                if health_metric.state == ServiceState.UNHEALTHY
                else AlertSeverity.HIGH
            )

            alert = StabilityAlert(
                alert_id=alert_id,
                timestamp=datetime.utcnow(),
                severity=severity,
                service=health_metric.service_name,
                metric="service_health",
                current_value=float(health_metric.error_rate),
                threshold=0.0,
                message=f"Service {health_metric.service_name} is {health_metric.state.value} (response time: {health_metric.response_time_ms:.2f}ms)",
            )

            self.active_alerts[alert_id] = alert
            await self._send_alert(alert)

    async def _update_circuit_breakers(self):
        """Update circuit breaker states based on service health"""
        for service_name, health_metric in self.service_health.items():
            if service_name not in self.circuit_breakers:
                self.circuit_breakers[service_name] = CircuitBreakerState()

            breaker = self.circuit_breakers[service_name]

            if health_metric.state == ServiceState.HEALTHY:
                breaker.record_success()
            elif health_metric.state in [ServiceState.DEGRADED, ServiceState.UNHEALTHY]:
                breaker.record_failure()

    async def _cleanup_resolved_alerts(self):
        """Clean up alerts that have been resolved"""
        current_time = datetime.utcnow()
        alerts_to_remove = []

        for alert_id, alert in self.active_alerts.items():
            # Remove alerts older than 1 hour
            if (current_time - alert.timestamp).total_seconds() > 3600:
                alerts_to_remove.append(alert_id)
                continue

            # Check if resource alerts are resolved
            if alert.service == "system":
                latest_metrics = (
                    self.resource_history[-1] if self.resource_history else None
                )
                if latest_metrics:
                    current_value = getattr(latest_metrics, alert.metric, 0)
                    if current_value <= alert.threshold:
                        alerts_to_remove.append(alert_id)
                        logger.info(f"Resource alert resolved: {alert.metric}")

            # Check if service alerts are resolved
            elif alert.metric == "service_health":
                service_health = self.service_health.get(alert.service)
                if service_health and service_health.state == ServiceState.HEALTHY:
                    alerts_to_remove.append(alert_id)
                    logger.info(f"Service health alert resolved: {alert.service}")

        for alert_id in alerts_to_remove:
            del self.active_alerts[alert_id]

    async def _send_alert(self, alert: StabilityAlert):
        """Send alert through configured channels"""
        logger.warning(
            f"STABILITY ALERT [{alert.severity.value.upper()}]: {alert.message}"
        )

        if self.alert_callback:
            try:
                await self.alert_callback(alert)
            except Exception as e:
                logger.error(f"Failed to send alert callback: {e}")

    def get_circuit_breaker(self, service_name: str) -> CircuitBreakerState:
        """Get circuit breaker for service"""
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreakerState()
        return self.circuit_breakers[service_name]

    def get_current_metrics(self) -> Optional[ResourceMetrics]:
        """Get latest resource metrics"""
        return self.resource_history[-1] if self.resource_history else None

    def get_service_health_summary(self) -> dict[str, ServiceState]:
        """Get summary of all service health states"""
        return {
            service: health.state for service, health in self.service_health.items()
        }

    def get_active_alerts_summary(self) -> list[dict[str, Any]]:
        """Get summary of active alerts"""
        return [
            {
                "id": alert.alert_id,
                "severity": alert.severity.value,
                "service": alert.service,
                "metric": alert.metric,
                "message": alert.message,
                "timestamp": alert.timestamp.isoformat(),
            }
            for alert in self.active_alerts.values()
        ]


# Global instance
_stability_monitor: Optional[StabilityMonitoringService] = None


def get_stability_monitor() -> StabilityMonitoringService:
    """Get or create global stability monitoring service"""
    global _stability_monitor
    if _stability_monitor is None:
        _stability_monitor = StabilityMonitoringService()
    return _stability_monitor


async def cleanup_stability_monitor():
    """Cleanup global stability monitoring service"""
    global _stability_monitor
    if _stability_monitor:
        await _stability_monitor.stop_monitoring()
        _stability_monitor = None
