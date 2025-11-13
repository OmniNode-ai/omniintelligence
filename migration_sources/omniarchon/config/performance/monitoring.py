"""
Performance Monitoring and Alerting System

Provides comprehensive monitoring of system performance, resource usage,
and health metrics with alerting capabilities.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import httpx
import psutil

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class PerformanceMetric:
    """Performance metric data point"""

    name: str
    value: float
    unit: str
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class AlertRule:
    """Alert rule configuration"""

    name: str
    metric_name: str
    condition: str  # 'gt', 'lt', 'eq', 'gte', 'lte'
    threshold: float
    severity: AlertSeverity
    duration_seconds: float = 60.0  # How long condition must persist
    cooldown_seconds: float = 300.0  # Cooldown between alerts
    last_triggered: Optional[float] = None
    active: bool = True


@dataclass
class Alert:
    """Alert notification"""

    rule_name: str
    severity: AlertSeverity
    message: str
    timestamp: float
    metric_value: float
    threshold: float


class SystemResourceMonitor:
    """Monitor system resources (CPU, memory, disk, network)"""

    def __init__(self):
        self.process = psutil.Process()

    def get_cpu_metrics(self) -> Dict[str, float]:
        """Get CPU usage metrics"""
        return {
            "cpu_percent_system": psutil.cpu_percent(interval=1),
            "cpu_percent_process": self.process.cpu_percent(),
            "cpu_count": psutil.cpu_count(),
            "load_average_1m": (
                psutil.getloadavg()[0] if hasattr(psutil, "getloadavg") else 0.0
            ),
            "load_average_5m": (
                psutil.getloadavg()[1] if hasattr(psutil, "getloadavg") else 0.0
            ),
            "load_average_15m": (
                psutil.getloadavg()[2] if hasattr(psutil, "getloadavg") else 0.0
            ),
        }

    def get_memory_metrics(self) -> Dict[str, float]:
        """Get memory usage metrics"""
        system_memory = psutil.virtual_memory()
        process_memory = self.process.memory_info()

        return {
            "memory_percent_system": system_memory.percent,
            "memory_available_gb": system_memory.available / (1024**3),
            "memory_used_gb": system_memory.used / (1024**3),
            "memory_total_gb": system_memory.total / (1024**3),
            "memory_process_rss_mb": process_memory.rss / (1024**2),
            "memory_process_vms_mb": process_memory.vms / (1024**2),
        }

    def get_disk_metrics(self) -> Dict[str, float]:
        """Get disk usage metrics"""
        disk_usage = psutil.disk_usage("/")
        disk_io = psutil.disk_io_counters()

        metrics = {
            "disk_percent_used": (disk_usage.used / disk_usage.total) * 100,
            "disk_free_gb": disk_usage.free / (1024**3),
            "disk_used_gb": disk_usage.used / (1024**3),
            "disk_total_gb": disk_usage.total / (1024**3),
        }

        if disk_io:
            metrics.update(
                {
                    "disk_read_bytes_per_sec": disk_io.read_bytes,
                    "disk_write_bytes_per_sec": disk_io.write_bytes,
                    "disk_read_count": disk_io.read_count,
                    "disk_write_count": disk_io.write_count,
                }
            )

        return metrics

    def get_network_metrics(self) -> Dict[str, float]:
        """Get network I/O metrics"""
        network_io = psutil.net_io_counters()

        return {
            "network_bytes_sent": network_io.bytes_sent,
            "network_bytes_recv": network_io.bytes_recv,
            "network_packets_sent": network_io.packets_sent,
            "network_packets_recv": network_io.packets_recv,
            "network_errors_in": network_io.errin,
            "network_errors_out": network_io.errout,
            "network_drops_in": network_io.dropin,
            "network_drops_out": network_io.dropout,
        }


class ServiceHealthMonitor:
    """Monitor health of Archon services"""

    def __init__(self):
        self.service_urls = {
            "archon-server": "http://archon-server:8181/health",
            "archon-mcp": "http://archon-mcp:8051/health",
            "archon-intelligence": "http://archon-intelligence:8053/health",
            "archon-bridge": "http://archon-bridge:8054/health",
            "archon-search": "http://archon-search:8055/health",
            "archon-langextract": "http://archon-langextract:8156/health",
            "qdrant": "http://qdrant:6333/readyz",
            "memgraph": "http://memgraph:7444/",
        }

    async def check_service_health(self, service_name: str, url: str) -> Dict[str, Any]:
        """Check health of a single service"""
        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                response_time_ms = (time.time() - start_time) * 1000

                is_healthy = 200 <= response.status_code < 300

                result = {
                    "service": service_name,
                    "healthy": is_healthy,
                    "status_code": response.status_code,
                    "response_time_ms": response_time_ms,
                    "timestamp": time.time(),
                }

                try:
                    response_data = response.json()
                    result["details"] = response_data
                except:
                    result["details"] = {"response": response.text[:200]}

                return result

        except Exception as e:
            return {
                "service": service_name,
                "healthy": False,
                "status_code": 0,
                "response_time_ms": (time.time() - start_time) * 1000,
                "timestamp": time.time(),
                "error": str(e),
            }

    async def check_all_services(self) -> Dict[str, Any]:
        """Check health of all services"""
        tasks = [
            self.check_service_health(service, url)
            for service, url in self.service_urls.items()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        service_health = {}
        healthy_count = 0
        total_count = len(results)

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Service health check failed: {result}")
                continue

            service_health[result["service"]] = result
            if result["healthy"]:
                healthy_count += 1

        return {
            "services": service_health,
            "summary": {
                "healthy_services": healthy_count,
                "total_services": total_count,
                "overall_health": (
                    healthy_count / total_count if total_count > 0 else 0.0
                ),
                "timestamp": time.time(),
            },
        }


class MetricsCollector:
    """Collect and store performance metrics"""

    def __init__(self, retention_hours: int = 24):
        self.retention_hours = retention_hours
        self.metrics: List[PerformanceMetric] = []
        self.system_monitor = SystemResourceMonitor()
        self.service_monitor = ServiceHealthMonitor()

    def add_metric(
        self, name: str, value: float, unit: str, labels: Dict[str, str] = None
    ):
        """Add a metric data point"""
        metric = PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            timestamp=time.time(),
            labels=labels or {},
        )
        self.metrics.append(metric)
        self._cleanup_old_metrics()

    def _cleanup_old_metrics(self):
        """Remove metrics older than retention period"""
        cutoff_time = time.time() - (self.retention_hours * 3600)
        self.metrics = [m for m in self.metrics if m.timestamp > cutoff_time]

    async def collect_system_metrics(self):
        """Collect system resource metrics"""
        time.time()

        # CPU metrics
        cpu_metrics = self.system_monitor.get_cpu_metrics()
        for name, value in cpu_metrics.items():
            self.add_metric(name, value, "percent" if "percent" in name else "count")

        # Memory metrics
        memory_metrics = self.system_monitor.get_memory_metrics()
        for name, value in memory_metrics.items():
            unit = "percent" if "percent" in name else ("gb" if "gb" in name else "mb")
            self.add_metric(name, value, unit)

        # Disk metrics
        disk_metrics = self.system_monitor.get_disk_metrics()
        for name, value in disk_metrics.items():
            unit = (
                "percent" if "percent" in name else ("gb" if "gb" in name else "bytes")
            )
            self.add_metric(name, value, unit)

        # Network metrics
        network_metrics = self.system_monitor.get_network_metrics()
        for name, value in network_metrics.items():
            unit = "bytes" if "bytes" in name else "count"
            self.add_metric(name, value, unit)

    async def collect_service_metrics(self):
        """Collect service health metrics"""
        health_data = await self.service_monitor.check_all_services()

        # Overall health
        self.add_metric(
            "services_overall_health", health_data["summary"]["overall_health"], "ratio"
        )

        # Individual service metrics
        for service_name, service_data in health_data["services"].items():
            labels = {"service": service_name}

            self.add_metric(
                "service_healthy",
                1.0 if service_data["healthy"] else 0.0,
                "boolean",
                labels,
            )

            self.add_metric(
                "service_response_time",
                service_data["response_time_ms"],
                "milliseconds",
                labels,
            )

    def get_metrics(
        self, name_pattern: str = None, hours: int = 1
    ) -> List[PerformanceMetric]:
        """Get metrics matching pattern within time window"""
        cutoff_time = time.time() - (hours * 3600)

        filtered_metrics = [m for m in self.metrics if m.timestamp > cutoff_time]

        if name_pattern:
            filtered_metrics = [m for m in filtered_metrics if name_pattern in m.name]

        return filtered_metrics

    def get_metric_summary(self, name: str, hours: int = 1) -> Dict[str, float]:
        """Get summary statistics for a metric"""
        metrics = self.get_metrics(name, hours)

        if not metrics:
            return {"count": 0}

        values = [m.value for m in metrics]
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "current": values[-1] if values else 0.0,
            "timestamp": time.time(),
        }


class AlertManager:
    """Manage alert rules and notifications"""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.alert_rules: List[AlertRule] = []
        self.active_alerts: List[Alert] = []
        self.alert_handlers: List[Callable[[Alert], None]] = []

    def add_alert_rule(self, rule: AlertRule):
        """Add an alert rule"""
        self.alert_rules.append(rule)
        logger.info(f"Added alert rule: {rule.name}")

    def add_alert_handler(self, handler: Callable[[Alert], None]):
        """Add an alert handler function"""
        self.alert_handlers.append(handler)

    def setup_default_rules(self):
        """Setup default alert rules for common issues"""
        default_rules = [
            AlertRule(
                name="High CPU Usage",
                metric_name="cpu_percent_system",
                condition="gt",
                threshold=80.0,
                severity=AlertSeverity.WARNING,
                duration_seconds=120.0,
            ),
            AlertRule(
                name="Critical CPU Usage",
                metric_name="cpu_percent_system",
                condition="gt",
                threshold=95.0,
                severity=AlertSeverity.CRITICAL,
                duration_seconds=60.0,
            ),
            AlertRule(
                name="High Memory Usage",
                metric_name="memory_percent_system",
                condition="gt",
                threshold=85.0,
                severity=AlertSeverity.WARNING,
                duration_seconds=180.0,
            ),
            AlertRule(
                name="Critical Memory Usage",
                metric_name="memory_percent_system",
                condition="gt",
                threshold=95.0,
                severity=AlertSeverity.CRITICAL,
                duration_seconds=60.0,
            ),
            AlertRule(
                name="Low Disk Space",
                metric_name="disk_percent_used",
                condition="gt",
                threshold=85.0,
                severity=AlertSeverity.WARNING,
                duration_seconds=300.0,
            ),
            AlertRule(
                name="Critical Disk Space",
                metric_name="disk_percent_used",
                condition="gt",
                threshold=95.0,
                severity=AlertSeverity.CRITICAL,
                duration_seconds=60.0,
            ),
            AlertRule(
                name="Service Health Degraded",
                metric_name="services_overall_health",
                condition="lt",
                threshold=0.8,
                severity=AlertSeverity.WARNING,
                duration_seconds=120.0,
            ),
            AlertRule(
                name="Service Health Critical",
                metric_name="services_overall_health",
                condition="lt",
                threshold=0.5,
                severity=AlertSeverity.CRITICAL,
                duration_seconds=60.0,
            ),
        ]

        for rule in default_rules:
            self.add_alert_rule(rule)

    async def check_alerts(self):
        """Check all alert rules and trigger alerts if needed"""
        current_time = time.time()

        for rule in self.alert_rules:
            if not rule.active:
                continue

            # Check cooldown
            if (
                rule.last_triggered
                and current_time - rule.last_triggered < rule.cooldown_seconds
            ):
                continue

            # Get recent metrics for this rule
            metrics = self.metrics_collector.get_metrics(rule.metric_name, hours=0.1)

            if not metrics:
                continue

            # Check if condition has been met for the required duration
            violation_start = None
            for metric in reversed(metrics):
                condition_met = self._evaluate_condition(
                    metric.value, rule.condition, rule.threshold
                )

                if condition_met:
                    if violation_start is None:
                        violation_start = metric.timestamp
                else:
                    violation_start = None
                    break

            # If condition has been met for required duration, trigger alert
            if (
                violation_start
                and current_time - violation_start >= rule.duration_seconds
            ):
                latest_metric = metrics[-1]
                alert = Alert(
                    rule_name=rule.name,
                    severity=rule.severity,
                    message=f"{rule.name}: {rule.metric_name} is {latest_metric.value:.2f} (threshold: {rule.threshold})",
                    timestamp=current_time,
                    metric_value=latest_metric.value,
                    threshold=rule.threshold,
                )

                await self._trigger_alert(alert)
                rule.last_triggered = current_time

    def _evaluate_condition(
        self, value: float, condition: str, threshold: float
    ) -> bool:
        """Evaluate alert condition"""
        if condition == "gt":
            return value > threshold
        elif condition == "gte":
            return value >= threshold
        elif condition == "lt":
            return value < threshold
        elif condition == "lte":
            return value <= threshold
        elif condition == "eq":
            return abs(value - threshold) < 0.001
        else:
            return False

    async def _trigger_alert(self, alert: Alert):
        """Trigger an alert notification"""
        self.active_alerts.append(alert)

        # Keep only last 100 alerts
        if len(self.active_alerts) > 100:
            self.active_alerts = self.active_alerts[-100:]

        logger.warning(f"ALERT [{alert.severity.value.upper()}]: {alert.message}")

        # Call all alert handlers
        for handler in self.alert_handlers:
            try:
                (
                    await asyncio.create_task(handler(alert))
                    if asyncio.iscoroutinefunction(handler)
                    else handler(alert)
                )
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")


class PerformanceMonitor:
    """Main performance monitoring system"""

    def __init__(self, collection_interval: int = 30):
        self.collection_interval = collection_interval
        self.metrics_collector = MetricsCollector()
        self.alert_manager = AlertManager(self.metrics_collector)
        self._monitoring_task = None
        self._running = False

    async def start(self):
        """Start the monitoring system"""
        if self._running:
            return

        self._running = True
        self.alert_manager.setup_default_rules()
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Performance monitoring started")

    async def stop(self):
        """Stop the monitoring system"""
        self._running = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Performance monitoring stopped")

    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self._running:
            try:
                # Collect metrics
                await self.metrics_collector.collect_system_metrics()
                await self.metrics_collector.collect_service_metrics()

                # Check alerts
                await self.alert_manager.check_alerts()

                # Wait for next collection
                await asyncio.sleep(self.collection_interval)

            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(self.collection_interval)

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get data for monitoring dashboard"""
        current_time = time.time()

        # System metrics summary
        system_metrics = {
            "cpu": self.metrics_collector.get_metric_summary("cpu_percent_system"),
            "memory": self.metrics_collector.get_metric_summary(
                "memory_percent_system"
            ),
            "disk": self.metrics_collector.get_metric_summary("disk_percent_used"),
            "services": self.metrics_collector.get_metric_summary(
                "services_overall_health"
            ),
        }

        # Recent alerts
        recent_alerts = [
            {
                "rule_name": alert.rule_name,
                "severity": alert.severity.value,
                "message": alert.message,
                "timestamp": alert.timestamp,
                "age_minutes": (current_time - alert.timestamp) / 60,
            }
            for alert in self.active_alerts[-10:]
        ]

        # Alert rules status
        alert_rules_status = [
            {
                "name": rule.name,
                "metric": rule.metric_name,
                "threshold": rule.threshold,
                "severity": rule.severity.value,
                "active": rule.active,
                "last_triggered": rule.last_triggered,
            }
            for rule in self.alert_manager.alert_rules
        ]

        return {
            "timestamp": current_time,
            "system_metrics": system_metrics,
            "recent_alerts": recent_alerts,
            "alert_rules": alert_rules_status,
            "monitoring_status": "running" if self._running else "stopped",
        }


# Global monitoring instance
performance_monitor = PerformanceMonitor()


async def start_monitoring():
    """Start the global performance monitoring"""
    await performance_monitor.start()


async def stop_monitoring():
    """Stop the global performance monitoring"""
    await performance_monitor.stop()


def get_monitoring_data() -> Dict[str, Any]:
    """Get current monitoring data"""
    return performance_monitor.get_dashboard_data()
