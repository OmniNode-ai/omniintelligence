#!/usr/bin/env python3
"""
ARCHON HEALTH MONITORING SYSTEM
===============================

Real-time health monitoring and alerting for Archon services.
Provides continuous monitoring, alerting, and auto-recovery capabilities.

Usage:
    python scripts/health_monitor.py [--dashboard] [--auto-recovery] [--alert-webhook URL]
"""

import argparse
import asyncio
import logging
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import psutil

import docker

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class ServiceHealth:
    """Comprehensive health information for a service."""

    name: str
    running: bool
    healthy: bool
    response_time_ms: Optional[float]
    cpu_percent: Optional[float]
    memory_mb: Optional[float]
    disk_io: Optional[Dict[str, Any]]
    network_io: Optional[Dict[str, Any]]
    uptime_seconds: Optional[float]
    restart_count: int
    last_restart: Optional[datetime]
    error_count: int
    last_error: Optional[str]
    dependencies_healthy: bool


@dataclass
class SystemHealth:
    """Overall system health metrics."""

    timestamp: datetime
    overall_status: str  # healthy, degraded, critical, down
    services: Dict[str, ServiceHealth]
    system_metrics: Dict[str, Any]
    alerts: List[Dict[str, Any]]


class HealthMonitor:
    """Comprehensive health monitoring for Archon platform."""

    def __init__(self):
        self.docker_client = docker.from_env()
        self.project_root = Path(__file__).parent.parent
        self.monitoring_active = False
        self.service_configs = self._load_service_configs()
        self.health_history = []
        self.alert_webhook = None
        self.auto_recovery_enabled = False

    def _load_service_configs(self) -> Dict[str, Dict[str, Any]]:
        """Load service configurations for monitoring."""
        return {
            "archon-memgraph": {
                "port": 7444,
                "health_endpoint": "/",
                "critical": True,
                "dependencies": [],
            },
            "archon-qdrant": {
                "port": 6333,
                "health_endpoint": "/readyz",
                "critical": True,
                "dependencies": [],
            },
            "archon-bridge": {
                "port": 8054,
                "health_endpoint": "/health",
                "critical": True,
                "dependencies": ["archon-memgraph"],
            },
            "archon-intelligence": {
                "port": 8053,
                "health_endpoint": "/health",
                "critical": True,
                "dependencies": ["archon-memgraph", "archon-bridge"],
            },
            "archon-search": {
                "port": 8055,
                "health_endpoint": "/health",
                "critical": True,
                "dependencies": [
                    "archon-qdrant",
                    "archon-memgraph",
                    "archon-intelligence",
                    "archon-bridge",
                ],
            },
            "archon-server": {
                "port": 8181,
                "health_endpoint": "/health",
                "critical": True,
                "dependencies": ["archon-memgraph", "archon-intelligence"],
            },
            "archon-mcp": {
                "port": 8051,
                "health_endpoint": "/",
                "critical": True,
                "dependencies": ["archon-server"],
            },
            "archon-ui": {
                "port": 3737,
                "health_endpoint": "/",
                "critical": False,
                "dependencies": ["archon-server"],
            },
        }

    async def check_service_health(
        self, container_name: str, config: Dict[str, Any]
    ) -> ServiceHealth:
        """Check comprehensive health of a service."""
        try:
            container = self.docker_client.containers.get(container_name)

            # Basic container status
            running = container.status == "running"

            # Resource metrics
            cpu_percent = None
            memory_mb = None
            disk_io = None
            network_io = None
            uptime_seconds = None

            if running:
                try:
                    # Get container stats
                    stats = container.stats(stream=False)

                    # CPU usage
                    cpu_delta = (
                        stats["cpu_stats"]["cpu_usage"]["total_usage"]
                        - stats["precpu_stats"]["cpu_usage"]["total_usage"]
                    )
                    system_delta = (
                        stats["cpu_stats"]["system_cpu_usage"]
                        - stats["precpu_stats"]["system_cpu_usage"]
                    )
                    cpu_percent = (
                        (cpu_delta / system_delta)
                        * len(stats["cpu_stats"]["cpu_usage"]["percpu_usage"])
                        * 100.0
                    )

                    # Memory usage
                    memory_mb = stats["memory_stats"]["usage"] / (1024 * 1024)

                    # Disk I/O
                    disk_io = stats.get("blkio_stats", {})

                    # Network I/O
                    network_io = stats.get("networks", {})

                    # Uptime
                    created_time = datetime.fromisoformat(
                        container.attrs["Created"].replace("Z", "+00:00")
                    )
                    uptime_seconds = (
                        datetime.now().astimezone() - created_time
                    ).total_seconds()

                except Exception as e:
                    logger.warning(f"Failed to get stats for {container_name}: {e}")

            # Health check via HTTP
            healthy = False
            response_time_ms = None

            if running and "port" in config:
                try:
                    start_time = time.time()
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        response = await client.get(
                            f"http://localhost:{config['port']}{config['health_endpoint']}"
                        )
                        response_time_ms = (time.time() - start_time) * 1000
                        healthy = response.status_code < 500
                except Exception as e:
                    logger.debug(f"Health check failed for {container_name}: {e}")

            # Check dependencies
            dependencies_healthy = True
            for dep_name in config.get("dependencies", []):
                if dep_name in self.service_configs:
                    dep_health = await self.check_service_health(
                        dep_name, self.service_configs[dep_name]
                    )
                    if not dep_health.healthy:
                        dependencies_healthy = False
                        break

            # Restart count and last restart
            restart_count = container.attrs.get("RestartCount", 0)
            last_restart = None
            if restart_count > 0:
                try:
                    started_at = container.attrs["State"]["StartedAt"]
                    last_restart = datetime.fromisoformat(
                        started_at.replace("Z", "+00:00")
                    )
                except:
                    pass

            return ServiceHealth(
                name=container_name,
                running=running,
                healthy=healthy and dependencies_healthy,
                response_time_ms=response_time_ms,
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                disk_io=disk_io,
                network_io=network_io,
                uptime_seconds=uptime_seconds,
                restart_count=restart_count,
                last_restart=last_restart,
                error_count=0,  # Would need log analysis
                last_error=None,
                dependencies_healthy=dependencies_healthy,
            )

        except docker.errors.NotFound:
            return ServiceHealth(
                name=container_name,
                running=False,
                healthy=False,
                response_time_ms=None,
                cpu_percent=None,
                memory_mb=None,
                disk_io=None,
                network_io=None,
                uptime_seconds=None,
                restart_count=0,
                last_restart=None,
                error_count=0,
                last_error="Container not found",
                dependencies_healthy=False,
            )

    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get system-wide metrics."""
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory": {
                "total_mb": psutil.virtual_memory().total / (1024 * 1024),
                "available_mb": psutil.virtual_memory().available / (1024 * 1024),
                "percent": psutil.virtual_memory().percent,
            },
            "disk": {
                "total_gb": psutil.disk_usage("/").total / (1024 * 1024 * 1024),
                "free_gb": psutil.disk_usage("/").free / (1024 * 1024 * 1024),
                "percent": psutil.disk_usage("/").percent,
            },
            "network": dict(psutil.net_io_counters()._asdict()),
            "processes": len(psutil.pids()),
            "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
        }

    async def assess_overall_status(self, services: Dict[str, ServiceHealth]) -> str:
        """Assess overall system status."""
        critical_services = [
            name
            for name, config in self.service_configs.items()
            if config.get("critical", True)
        ]
        critical_unhealthy = [
            name
            for name in critical_services
            if name in services and not services[name].healthy
        ]

        if not critical_unhealthy:
            return "healthy"
        elif len(critical_unhealthy) == 1:
            return "degraded"
        elif len(critical_unhealthy) <= len(critical_services) // 2:
            return "critical"
        else:
            return "down"

    async def generate_alerts(
        self, current_health: SystemHealth, previous_health: Optional[SystemHealth]
    ) -> List[Dict[str, Any]]:
        """Generate alerts based on health changes."""
        alerts = []

        for service_name, service_health in current_health.services.items():
            config = self.service_configs.get(service_name, {})

            # Service down alert
            if not service_health.running and config.get("critical", True):
                alerts.append(
                    {
                        "level": "critical",
                        "type": "service_down",
                        "service": service_name,
                        "message": f"Critical service {service_name} is not running",
                        "timestamp": current_health.timestamp.isoformat(),
                    }
                )

            # Service unhealthy alert
            if (
                service_health.running
                and not service_health.healthy
                and config.get("critical", True)
            ):
                alerts.append(
                    {
                        "level": "warning",
                        "type": "service_unhealthy",
                        "service": service_name,
                        "message": f"Service {service_name} is running but unhealthy",
                        "timestamp": current_health.timestamp.isoformat(),
                    }
                )

            # High resource usage alerts
            if service_health.cpu_percent and service_health.cpu_percent > 90:
                alerts.append(
                    {
                        "level": "warning",
                        "type": "high_cpu",
                        "service": service_name,
                        "message": f"Service {service_name} CPU usage is high: {service_health.cpu_percent:.1f}%",
                        "timestamp": current_health.timestamp.isoformat(),
                    }
                )

            if service_health.memory_mb and service_health.memory_mb > 1024:  # > 1GB
                alerts.append(
                    {
                        "level": "warning",
                        "type": "high_memory",
                        "service": service_name,
                        "message": f"Service {service_name} memory usage is high: {service_health.memory_mb:.1f}MB",
                        "timestamp": current_health.timestamp.isoformat(),
                    }
                )

            # Response time alerts
            if (
                service_health.response_time_ms
                and service_health.response_time_ms > 5000
            ):  # > 5 seconds
                alerts.append(
                    {
                        "level": "warning",
                        "type": "slow_response",
                        "service": service_name,
                        "message": f"Service {service_name} response time is slow: {service_health.response_time_ms:.0f}ms",
                        "timestamp": current_health.timestamp.isoformat(),
                    }
                )

        # System-wide alerts
        system_metrics = current_health.system_metrics
        if system_metrics["memory"]["percent"] > 85:
            alerts.append(
                {
                    "level": "warning",
                    "type": "high_system_memory",
                    "message": f"System memory usage is high: {system_metrics['memory']['percent']:.1f}%",
                    "timestamp": current_health.timestamp.isoformat(),
                }
            )

        if system_metrics["disk"]["percent"] > 85:
            alerts.append(
                {
                    "level": "warning",
                    "type": "high_disk_usage",
                    "message": f"Disk usage is high: {system_metrics['disk']['percent']:.1f}%",
                    "timestamp": current_health.timestamp.isoformat(),
                }
            )

        return alerts

    async def send_alert_webhook(self, alerts: List[Dict[str, Any]]):
        """Send alerts to webhook if configured."""
        if not self.alert_webhook or not alerts:
            return

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                payload = {
                    "timestamp": datetime.now().isoformat(),
                    "source": "archon-health-monitor",
                    "alerts": alerts,
                }
                response = await client.post(self.alert_webhook, json=payload)
                if response.status_code == 200:
                    logger.info(f"Sent {len(alerts)} alerts to webhook")
                else:
                    logger.warning(
                        f"Failed to send alerts to webhook: {response.status_code}"
                    )
        except Exception as e:
            logger.error(f"Failed to send webhook alerts: {e}")

    async def trigger_auto_recovery(self, service_name: str):
        """Trigger auto-recovery for a failed service."""
        if not self.auto_recovery_enabled:
            return

        try:
            logger.info(f"Triggering auto-recovery for {service_name}")

            # Import and use the recovery system
            from system_recovery import ArchonSystemRecovery

            recovery_system = ArchonSystemRecovery()

            success = await recovery_system.restart_service_with_dependencies(
                service_name
            )

            if success:
                logger.info(f"Auto-recovery successful for {service_name}")
            else:
                logger.error(f"Auto-recovery failed for {service_name}")

        except Exception as e:
            logger.error(f"Auto-recovery error for {service_name}: {e}")

    async def collect_health_data(self) -> SystemHealth:
        """Collect comprehensive health data."""
        services = {}

        for container_name, config in self.service_configs.items():
            service_health = await self.check_service_health(container_name, config)
            services[container_name] = service_health

        system_metrics = await self.get_system_metrics()
        overall_status = await self.assess_overall_status(services)

        previous_health = self.health_history[-1] if self.health_history else None

        current_health = SystemHealth(
            timestamp=datetime.now(),
            overall_status=overall_status,
            services=services,
            system_metrics=system_metrics,
            alerts=[],
        )

        # Generate alerts
        alerts = await self.generate_alerts(current_health, previous_health)
        current_health.alerts = alerts

        return current_health

    def print_dashboard(self, health: SystemHealth):
        """Print real-time dashboard to console."""
        # Clear screen
        print("\033[2J\033[H", end="")

        print("=" * 80)
        print(
            f"ARCHON HEALTH DASHBOARD - {health.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        print("=" * 80)

        # Overall status
        status_colors = {
            "healthy": "\033[92m",  # Green
            "degraded": "\033[93m",  # Yellow
            "critical": "\033[91m",  # Red
            "down": "\033[95m",  # Magenta
        }
        color = status_colors.get(health.overall_status, "\033[0m")
        print(f"Overall Status: {color}{health.overall_status.upper()}\033[0m")

        # System metrics
        print("\nSystem Metrics:")
        print(f"  CPU: {health.system_metrics['cpu_percent']:.1f}%")
        print(
            f"  Memory: {health.system_metrics['memory']['percent']:.1f}% ({health.system_metrics['memory']['available_mb']:.0f}MB free)"
        )
        print(
            f"  Disk: {health.system_metrics['disk']['percent']:.1f}% ({health.system_metrics['disk']['free_gb']:.1f}GB free)"
        )

        # Services
        print("\nServices:")
        print(
            f"{'Service':<20} {'Status':<10} {'Health':<8} {'Response':<10} {'CPU':<8} {'Memory':<10} {'Uptime':<10}"
        )
        print("-" * 80)

        for service_name, service in health.services.items():
            status = "Running" if service.running else "Stopped"
            health_status = "Healthy" if service.healthy else "Unhealthy"
            response = (
                f"{service.response_time_ms:.0f}ms"
                if service.response_time_ms
                else "N/A"
            )
            cpu = f"{service.cpu_percent:.1f}%" if service.cpu_percent else "N/A"
            memory = f"{service.memory_mb:.0f}MB" if service.memory_mb else "N/A"
            uptime = (
                f"{service.uptime_seconds/3600:.1f}h"
                if service.uptime_seconds
                else "N/A"
            )

            # Color coding
            if service.healthy:
                status_color = "\033[92m"  # Green
            elif service.running:
                status_color = "\033[93m"  # Yellow
            else:
                status_color = "\033[91m"  # Red

            print(
                f"{service_name:<20} {status_color}{status:<10}\033[0m {health_status:<8} {response:<10} {cpu:<8} {memory:<10} {uptime:<10}"
            )

        # Alerts
        if health.alerts:
            print(f"\nActive Alerts ({len(health.alerts)}):")
            for alert in health.alerts:
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
            print("\nNo active alerts ✅")

        print("\n" + "=" * 80)
        print("Press Ctrl+C to stop monitoring")

    async def start_monitoring(self, dashboard: bool = False, check_interval: int = 30):
        """Start continuous health monitoring."""
        self.monitoring_active = True
        logger.info(f"Starting health monitoring (check every {check_interval}s)")

        consecutive_failures = {}

        try:
            while self.monitoring_active:
                # Collect health data
                health = await self.collect_health_data()
                self.health_history.append(health)

                # Keep only last 100 health checks
                if len(self.health_history) > 100:
                    self.health_history = self.health_history[-100:]

                # Send alerts
                if health.alerts:
                    await self.send_alert_webhook(health.alerts)

                # Auto-recovery for critical services
                for service_name, service in health.services.items():
                    config = self.service_configs.get(service_name, {})
                    if config.get("critical", True) and not service.healthy:
                        consecutive_failures[service_name] = (
                            consecutive_failures.get(service_name, 0) + 1
                        )

                        # Trigger auto-recovery after 2 consecutive failures
                        if consecutive_failures[service_name] >= 2:
                            await self.trigger_auto_recovery(service_name)
                            consecutive_failures[service_name] = (
                                0  # Reset after recovery attempt
                            )
                    else:
                        consecutive_failures[service_name] = 0

                # Display dashboard
                if dashboard:
                    self.print_dashboard(health)
                else:
                    # Log summary
                    unhealthy_services = [
                        name
                        for name, service in health.services.items()
                        if not service.healthy
                    ]
                    if unhealthy_services:
                        logger.warning(
                            f"Unhealthy services: {', '.join(unhealthy_services)}"
                        )
                    else:
                        logger.info("All services healthy ✅")

                await asyncio.sleep(check_interval)

        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        finally:
            self.monitoring_active = False

    def stop_monitoring(self):
        """Stop monitoring."""
        self.monitoring_active = False


async def main():
    """Main entry point for health monitoring."""
    parser = argparse.ArgumentParser(description="Archon Health Monitor")
    parser.add_argument(
        "--dashboard", action="store_true", help="Show real-time dashboard"
    )
    parser.add_argument(
        "--auto-recovery", action="store_true", help="Enable automatic recovery"
    )
    parser.add_argument("--alert-webhook", help="Webhook URL for alerts")
    parser.add_argument(
        "--check-interval", type=int, default=30, help="Check interval in seconds"
    )

    args = parser.parse_args()

    monitor = HealthMonitor()
    monitor.auto_recovery_enabled = args.auto_recovery
    monitor.alert_webhook = args.alert_webhook

    # Signal handling
    def signal_handler(signum, frame):
        logger.info("Received interrupt signal")
        monitor.stop_monitoring()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await monitor.start_monitoring(
            dashboard=args.dashboard, check_interval=args.check_interval
        )
    except Exception as e:
        logger.error(f"Monitoring error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
