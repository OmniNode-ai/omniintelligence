#!/usr/bin/env python3
"""
Performance Monitoring Script

Real-time monitoring of system performance metrics during load testing:
- CPU usage tracking
- Memory usage tracking
- Docker container statistics
- Real-time display with updates

Part of MVP Phase 4 - Load Testing Infrastructure

Author: Archon Intelligence Team
Date: 2025-10-15
"""

import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

# Try to import docker, provide helpful error if missing
try:
    from docker.errors import DockerException

    import docker
except ImportError:
    print("Error: docker library not installed. Install with: pip install docker")
    sys.exit(1)


# ============================================================================
# Configuration
# ============================================================================


@dataclass
class MonitorConfig:
    """Performance monitor configuration."""

    # Container to monitor
    container_name: str = "archon-intelligence"

    # Monitoring interval
    interval_seconds: int = 5

    # Output settings
    output_file: Optional[str] = None
    display_mode: str = "live"  # "live" or "silent"

    # Metrics to collect
    track_cpu: bool = True
    track_memory: bool = True
    track_docker: bool = True
    track_disk: bool = False


# ============================================================================
# Metrics Models
# ============================================================================


@dataclass
class PerformanceMetrics:
    """Performance metrics snapshot."""

    timestamp: float = field(default_factory=time.time)

    # System metrics
    cpu_percent: float = 0.0
    memory_usage_mb: float = 0.0
    memory_percent: float = 0.0
    disk_io_read_mb: float = 0.0
    disk_io_write_mb: float = 0.0

    # Docker container metrics
    container_cpu_percent: float = 0.0
    container_memory_mb: float = 0.0
    container_memory_percent: float = 0.0
    container_network_rx_mb: float = 0.0
    container_network_tx_mb: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "system": {
                "cpu_percent": self.cpu_percent,
                "memory_usage_mb": self.memory_usage_mb,
                "memory_percent": self.memory_percent,
                "disk_io_read_mb": self.disk_io_read_mb,
                "disk_io_write_mb": self.disk_io_write_mb,
            },
            "container": {
                "cpu_percent": self.container_cpu_percent,
                "memory_mb": self.container_memory_mb,
                "memory_percent": self.container_memory_percent,
                "network_rx_mb": self.container_network_rx_mb,
                "network_tx_mb": self.container_network_tx_mb,
            },
        }


@dataclass
class PerformanceSummary:
    """Performance monitoring summary."""

    start_time: float
    end_time: float
    duration_seconds: float
    sample_count: int

    # CPU statistics
    cpu_mean: float
    cpu_max: float
    cpu_min: float

    # Memory statistics
    memory_mean_mb: float
    memory_max_mb: float
    memory_min_mb: float

    # Container statistics
    container_cpu_mean: float
    container_cpu_max: float
    container_memory_mean_mb: float
    container_memory_max_mb: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "monitoring_period": {
                "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
                "end_time": datetime.fromtimestamp(self.end_time).isoformat(),
                "duration_seconds": self.duration_seconds,
                "sample_count": self.sample_count,
            },
            "system_cpu": {
                "mean_percent": self.cpu_mean,
                "max_percent": self.cpu_max,
                "min_percent": self.cpu_min,
            },
            "system_memory": {
                "mean_mb": self.memory_mean_mb,
                "max_mb": self.memory_max_mb,
                "min_mb": self.memory_min_mb,
            },
            "container": {
                "cpu_mean_percent": self.container_cpu_mean,
                "cpu_max_percent": self.container_cpu_max,
                "memory_mean_mb": self.container_memory_mean_mb,
                "memory_max_mb": self.container_memory_max_mb,
            },
        }


# ============================================================================
# Performance Monitor
# ============================================================================


class PerformanceMonitor:
    """
    Real-time performance monitoring.

    Tracks system and Docker container metrics with live display.
    """

    def __init__(self, config: MonitorConfig):
        """
        Initialize performance monitor.

        Args:
            config: Monitor configuration
        """
        self.config = config
        self.metrics_history: List[PerformanceMetrics] = []
        self.docker_client: Optional[docker.DockerClient] = None
        self.running = False

        # Initialize Docker client if tracking Docker
        if config.track_docker:
            try:
                self.docker_client = docker.from_env()
                print("🐳 Docker client connected")
            except DockerException as e:
                print(f"⚠️  Docker not available: {e}")
                print("   Continuing without Docker metrics")
                self.config.track_docker = False

    def start(self, duration_seconds: Optional[int] = None) -> None:
        """
        Start monitoring.

        Args:
            duration_seconds: Optional monitoring duration (None = indefinite)
        """
        print("📊 Performance Monitor Starting")
        print(f"   Container: {self.config.container_name}")
        print(f"   Interval: {self.config.interval_seconds}s")
        if duration_seconds:
            print(f"   Duration: {duration_seconds}s")
        print()

        self.running = True
        start_time = time.time()
        end_time = start_time + duration_seconds if duration_seconds else None

        try:
            while self.running:
                # Check duration
                if end_time and time.time() >= end_time:
                    break

                # Collect metrics
                metrics = self._collect_metrics()
                self.metrics_history.append(metrics)

                # Display metrics
                if self.config.display_mode == "live":
                    self._display_metrics(metrics)

                # Wait for next interval
                time.sleep(self.config.interval_seconds)

        except KeyboardInterrupt:
            print("\n⚠️  Monitoring interrupted by user")
        finally:
            self.running = False
            self._generate_summary()

    def _collect_metrics(self) -> PerformanceMetrics:
        """
        Collect current performance metrics.

        Returns:
            Performance metrics snapshot
        """
        metrics = PerformanceMetrics()

        # System CPU
        if self.config.track_cpu:
            metrics.cpu_percent = psutil.cpu_percent(interval=0.1)

        # System memory
        if self.config.track_memory:
            mem = psutil.virtual_memory()
            metrics.memory_usage_mb = mem.used / (1024 * 1024)
            metrics.memory_percent = mem.percent

        # Disk I/O
        if self.config.track_disk:
            disk_io = psutil.disk_io_counters()
            if disk_io:
                metrics.disk_io_read_mb = disk_io.read_bytes / (1024 * 1024)
                metrics.disk_io_write_mb = disk_io.write_bytes / (1024 * 1024)

        # Docker container metrics
        if self.config.track_docker and self.docker_client:
            try:
                container = self.docker_client.containers.get(
                    self.config.container_name
                )
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
                num_cpus = len(stats["cpu_stats"]["cpu_usage"].get("percpu_usage", [1]))

                if system_delta > 0:
                    metrics.container_cpu_percent = (
                        (cpu_delta / system_delta) * num_cpus * 100.0
                    )

                # Memory usage
                memory_usage = stats["memory_stats"].get("usage", 0)
                memory_limit = stats["memory_stats"].get("limit", 1)
                metrics.container_memory_mb = memory_usage / (1024 * 1024)
                metrics.container_memory_percent = (memory_usage / memory_limit) * 100.0

                # Network I/O
                networks = stats.get("networks", {})
                total_rx = sum(net.get("rx_bytes", 0) for net in networks.values())
                total_tx = sum(net.get("tx_bytes", 0) for net in networks.values())
                metrics.container_network_rx_mb = total_rx / (1024 * 1024)
                metrics.container_network_tx_mb = total_tx / (1024 * 1024)

            except Exception:
                # Container might not be running
                pass

        return metrics

    def _display_metrics(self, metrics: PerformanceMetrics) -> None:
        """
        Display metrics to console.

        Args:
            metrics: Metrics to display
        """
        # Clear screen (optional - comment out if annoying)
        # print("\033[2J\033[H", end="")

        timestamp = datetime.fromtimestamp(metrics.timestamp).strftime("%H:%M:%S")

        print(f"\r[{timestamp}] ", end="")
        print(f"CPU: {metrics.cpu_percent:5.1f}% | ", end="")
        print(
            f"MEM: {metrics.memory_usage_mb:7.1f}MB ({metrics.memory_percent:4.1f}%) | ",
            end="",
        )

        if self.config.track_docker:
            print(f"Container CPU: {metrics.container_cpu_percent:5.1f}% | ", end="")
            print(f"Container MEM: {metrics.container_memory_mb:7.1f}MB", end="")

        # Force flush
        sys.stdout.flush()

    def _generate_summary(self) -> PerformanceSummary:
        """
        Generate performance summary from collected metrics.

        Returns:
            Performance summary
        """
        if not self.metrics_history:
            print("⚠️  No metrics collected")
            return None

        print("\n\n" + "=" * 70)
        print("📊 PERFORMANCE MONITORING SUMMARY")
        print("=" * 70)

        # Calculate statistics
        cpu_values = [m.cpu_percent for m in self.metrics_history]
        memory_values = [m.memory_usage_mb for m in self.metrics_history]
        container_cpu_values = [m.container_cpu_percent for m in self.metrics_history]
        container_memory_values = [m.container_memory_mb for m in self.metrics_history]

        summary = PerformanceSummary(
            start_time=self.metrics_history[0].timestamp,
            end_time=self.metrics_history[-1].timestamp,
            duration_seconds=self.metrics_history[-1].timestamp
            - self.metrics_history[0].timestamp,
            sample_count=len(self.metrics_history),
            cpu_mean=sum(cpu_values) / len(cpu_values),
            cpu_max=max(cpu_values),
            cpu_min=min(cpu_values),
            memory_mean_mb=sum(memory_values) / len(memory_values),
            memory_max_mb=max(memory_values),
            memory_min_mb=min(memory_values),
            container_cpu_mean=sum(container_cpu_values) / len(container_cpu_values),
            container_cpu_max=max(container_cpu_values),
            container_memory_mean_mb=sum(container_memory_values)
            / len(container_memory_values),
            container_memory_max_mb=max(container_memory_values),
        )

        # Print summary
        print("\n⏱️  Monitoring Period:")
        print(f"   Duration: {summary.duration_seconds:.1f}s")
        print(f"   Samples: {summary.sample_count}")

        print("\n💻 System CPU:")
        print(f"   Mean: {summary.cpu_mean:.1f}%")
        print(f"   Max:  {summary.cpu_max:.1f}%")
        print(f"   Min:  {summary.cpu_min:.1f}%")

        print("\n🧠 System Memory:")
        print(f"   Mean: {summary.memory_mean_mb:.1f} MB")
        print(f"   Max:  {summary.memory_max_mb:.1f} MB")
        print(f"   Min:  {summary.memory_min_mb:.1f} MB")

        if self.config.track_docker:
            print(f"\n🐳 Container ({self.config.container_name}):")
            print(f"   CPU Mean: {summary.container_cpu_mean:.1f}%")
            print(f"   CPU Max:  {summary.container_cpu_max:.1f}%")
            print(f"   MEM Mean: {summary.container_memory_mean_mb:.1f} MB")
            print(f"   MEM Max:  {summary.container_memory_max_mb:.1f} MB")

        print("\n" + "=" * 70)

        # Save to file if configured
        if self.config.output_file:
            self._save_results(summary)

        return summary

    def _save_results(self, summary: PerformanceSummary) -> None:
        """
        Save monitoring results to JSON file.

        Args:
            summary: Performance summary
        """
        output_path = Path(self.config.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "summary": summary.to_dict(),
            "metrics_history": [m.to_dict() for m in self.metrics_history],
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        print(f"\n💾 Results saved to: {output_path}")


# ============================================================================
# CLI
# ============================================================================


def main():
    """Main entry point for performance monitoring CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Real-time Performance Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor archon-intelligence container indefinitely
  python monitor_performance.py

  # Monitor for 300 seconds
  python monitor_performance.py --duration 300

  # Monitor different container
  python monitor_performance.py --container archon-mcp --duration 60

  # Save results to file
  python monitor_performance.py --duration 300 --output metrics.json

  # Silent mode (no live display)
  python monitor_performance.py --duration 60 --silent --output metrics.json
        """,
    )

    parser.add_argument(
        "--container",
        default="archon-intelligence",
        help="Container name to monitor (default: archon-intelligence)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Monitoring interval in seconds (default: 5)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        help="Monitoring duration in seconds (default: indefinite)",
    )
    parser.add_argument("--output", help="Output JSON file path")
    parser.add_argument("--silent", action="store_true", help="Suppress live display")
    parser.add_argument(
        "--no-docker", action="store_true", help="Skip Docker container metrics"
    )

    args = parser.parse_args()

    # Create configuration
    config = MonitorConfig(
        container_name=args.container,
        interval_seconds=args.interval,
        output_file=args.output,
        display_mode="silent" if args.silent else "live",
        track_docker=not args.no_docker,
    )

    # Create and start monitor
    monitor = PerformanceMonitor(config)

    try:
        monitor.start(duration_seconds=args.duration)
        return 0
    except KeyboardInterrupt:
        print("\n⚠️  Monitoring interrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Monitoring failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
