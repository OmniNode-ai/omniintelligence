#!/usr/bin/env python3
"""
Performance Baseline Measurement Script

Establishes performance baselines for Archon services and creates
benchmark data for monitoring and optimization validation.
"""

import asyncio
import json
import logging
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
import psutil

from config.performance.monitoring import performance_monitor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BaselineResult:
    """Baseline measurement result"""

    operation: str
    service: str
    response_time_ms: float
    throughput_ops_per_sec: float
    success_rate: float
    memory_usage_mb: float
    cpu_usage_percent: float
    timestamp: str
    sample_size: int
    metadata: Dict[str, Any]


@dataclass
class SystemBaseline:
    """System-wide baseline measurements"""

    timestamp: str
    total_memory_gb: float
    available_memory_gb: float
    cpu_count: int
    disk_space_gb: float
    service_baselines: List[BaselineResult]
    system_metrics: Dict[str, float]


class BaselineMeasurer:
    """Measures performance baselines for services and operations"""

    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.baseline_results: List[BaselineResult] = []

    async def measure_service_health_baseline(
        self, service_name: str, url: str, iterations: int = 10
    ) -> BaselineResult:
        """Measure baseline for service health check"""
        logger.info(f"Measuring health check baseline for {service_name}")

        response_times = []
        success_count = 0
        start_memory = psutil.Process().memory_info().rss / (1024 * 1024)
        start_cpu_time = psutil.Process().cpu_times()

        for i in range(iterations):
            start_time = time.time()

            try:
                response = await self.http_client.get(url)
                response_time = (time.time() - start_time) * 1000
                response_times.append(response_time)

                if 200 <= response.status_code < 300:
                    success_count += 1

            except Exception as e:
                logger.warning(f"Health check failed for {service_name}: {e}")
                response_times.append(30000)  # 30 second timeout

            # Small delay between requests
            await asyncio.sleep(0.1)

        end_memory = psutil.Process().memory_info().rss / (1024 * 1024)
        end_cpu_time = psutil.Process().cpu_times()

        # Calculate metrics
        avg_response_time = statistics.mean(response_times) if response_times else 0
        success_rate = success_count / iterations
        throughput = 1000 / avg_response_time if avg_response_time > 0 else 0
        memory_usage = end_memory - start_memory
        cpu_usage = (
            (
                (end_cpu_time.user + end_cpu_time.system)
                - (start_cpu_time.user + start_cpu_time.system)
            )
            / iterations
            * 100
        )

        result = BaselineResult(
            operation="health_check",
            service=service_name,
            response_time_ms=avg_response_time,
            throughput_ops_per_sec=throughput,
            success_rate=success_rate,
            memory_usage_mb=memory_usage,
            cpu_usage_percent=cpu_usage,
            timestamp=datetime.utcnow().isoformat(),
            sample_size=iterations,
            metadata={
                "min_response_time": min(response_times) if response_times else 0,
                "max_response_time": max(response_times) if response_times else 0,
                "p95_response_time": (
                    statistics.quantiles(response_times, n=20)[18]
                    if len(response_times) > 10
                    else 0
                ),
                "url": url,
            },
        )

        self.baseline_results.append(result)
        return result

    async def measure_api_endpoint_baseline(
        self,
        service_name: str,
        endpoint_url: str,
        method: str = "GET",
        json_data: Dict = None,
        iterations: int = 20,
    ) -> BaselineResult:
        """Measure baseline for API endpoint"""
        logger.info(
            f"Measuring API baseline for {service_name} {method} {endpoint_url}"
        )

        response_times = []
        success_count = 0
        start_memory = psutil.Process().memory_info().rss / (1024 * 1024)
        start_cpu_time = psutil.Process().cpu_times()

        for i in range(iterations):
            start_time = time.time()

            try:
                if method.upper() == "GET":
                    response = await self.http_client.get(endpoint_url)
                elif method.upper() == "POST":
                    response = await self.http_client.post(endpoint_url, json=json_data)
                else:
                    response = await self.http_client.request(
                        method, endpoint_url, json=json_data
                    )

                response_time = (time.time() - start_time) * 1000
                response_times.append(response_time)

                if 200 <= response.status_code < 300:
                    success_count += 1

            except Exception as e:
                logger.warning(f"API call failed for {service_name}: {e}")
                response_times.append(30000)

            await asyncio.sleep(0.2)  # Slight delay between API calls

        end_memory = psutil.Process().memory_info().rss / (1024 * 1024)
        end_cpu_time = psutil.Process().cpu_times()

        # Calculate metrics
        avg_response_time = statistics.mean(response_times) if response_times else 0
        success_rate = success_count / iterations
        throughput = 1000 / avg_response_time if avg_response_time > 0 else 0
        memory_usage = end_memory - start_memory
        cpu_usage = (
            (
                (end_cpu_time.user + end_cpu_time.system)
                - (start_cpu_time.user + start_cpu_time.system)
            )
            / iterations
            * 100
        )

        result = BaselineResult(
            operation=f"api_{method.lower()}",
            service=service_name,
            response_time_ms=avg_response_time,
            throughput_ops_per_sec=throughput,
            success_rate=success_rate,
            memory_usage_mb=memory_usage,
            cpu_usage_percent=cpu_usage,
            timestamp=datetime.utcnow().isoformat(),
            sample_size=iterations,
            metadata={
                "method": method,
                "endpoint": endpoint_url,
                "min_response_time": min(response_times) if response_times else 0,
                "max_response_time": max(response_times) if response_times else 0,
                "p95_response_time": (
                    statistics.quantiles(response_times, n=20)[18]
                    if len(response_times) > 10
                    else 0
                ),
                "has_payload": json_data is not None,
            },
        )

        self.baseline_results.append(result)
        return result

    async def measure_database_baseline(
        self, service_name: str, base_url: str
    ) -> List[BaselineResult]:
        """Measure database operation baselines"""
        logger.info(f"Measuring database baselines for {service_name}")

        database_results = []

        # Test database read operations
        if service_name == "archon-intelligence":
            # Entity search
            search_result = await self.measure_api_endpoint_baseline(
                service_name,
                f"{base_url}/entities/search?query=test&limit=10",
                method="GET",
                iterations=15,
            )
            database_results.append(search_result)

        elif service_name == "archon-search":
            # Vector search
            search_data = {"query": "test search", "mode": "semantic", "limit": 10}
            search_result = await self.measure_api_endpoint_baseline(
                service_name,
                f"{base_url}/search",
                method="POST",
                json_data=search_data,
                iterations=10,
            )
            database_results.append(search_result)

        elif service_name == "archon-server":
            # Project listing
            projects_result = await self.measure_api_endpoint_baseline(
                service_name, f"{base_url}/api/projects", method="GET", iterations=15
            )
            database_results.append(projects_result)

        return database_results

    async def get_system_metrics(self) -> Dict[str, float]:
        """Get current system metrics"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_gb": memory.available / (1024**3),
            "memory_total_gb": memory.total / (1024**3),
            "disk_percent": (disk.used / disk.total) * 100,
            "disk_free_gb": disk.free / (1024**3),
            "disk_total_gb": disk.total / (1024**3),
            "load_average": (
                psutil.getloadavg()[0] if hasattr(psutil, "getloadavg") else 0.0
            ),
        }

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()


async def establish_comprehensive_baseline() -> SystemBaseline:
    """Establish comprehensive baseline for the entire system"""
    logger.info("🚀 Starting comprehensive performance baseline measurement")

    measurer = BaselineMeasurer()

    # Define services to measure
    services = {
        "archon-server": os.getenv("API_SERVICE_URL", "http://localhost:8181"),
        "archon-mcp": os.getenv("ARCHON_MCP_URL", "http://localhost:8051"),
        "archon-intelligence": os.getenv(
            "INTELLIGENCE_SERVICE_URL", "http://localhost:8053"
        ),
        "archon-bridge": os.getenv("BRIDGE_SERVICE_URL", "http://localhost:8054"),
        "archon-search": os.getenv("SEARCH_SERVICE_URL", "http://localhost:8055"),
        "archon-langextract": os.getenv(
            "LANGEXTRACT_SERVICE_URL", "http://localhost:8156"
        ),
    }

    all_results = []

    try:
        # Measure health check baselines for all services
        logger.info("📊 Measuring health check baselines...")
        for service_name, base_url in services.items():
            if base_url:
                try:
                    health_url = f"{base_url}/health"
                    result = await measurer.measure_service_health_baseline(
                        service_name, health_url
                    )
                    logger.info(
                        f"✅ {service_name}: {result.response_time_ms:.1f}ms avg, {result.success_rate:.2%} success"
                    )
                except Exception as e:
                    logger.error(f"❌ Failed to measure {service_name}: {e}")

        # Measure API endpoint baselines
        logger.info("📊 Measuring API endpoint baselines...")

        # Main server API endpoints
        if services.get("archon-server"):
            server_url = services["archon-server"]
            api_endpoints = [
                ("/api/projects", "GET", None),
                ("/api/settings", "GET", None),
            ]

            for endpoint, method, data in api_endpoints:
                try:
                    result = await measurer.measure_api_endpoint_baseline(
                        "archon-server", f"{server_url}{endpoint}", method, data
                    )
                    all_results.append(result)
                except Exception as e:
                    logger.warning(f"Failed to measure {endpoint}: {e}")

        # Intelligence service endpoints
        if services.get("archon-intelligence"):
            intelligence_url = services["archon-intelligence"]
            intelligence_endpoints = [
                ("/entities/search?query=test&limit=5", "GET", None),
            ]

            for endpoint, method, data in intelligence_endpoints:
                try:
                    result = await measurer.measure_api_endpoint_baseline(
                        "archon-intelligence",
                        f"{intelligence_url}{endpoint}",
                        method,
                        data,
                    )
                    all_results.append(result)
                except Exception as e:
                    logger.warning(f"Failed to measure intelligence {endpoint}: {e}")

        # Search service endpoints
        if services.get("archon-search"):
            search_url = services["archon-search"]
            search_data = {"query": "baseline test", "mode": "semantic", "limit": 5}

            try:
                result = await measurer.measure_api_endpoint_baseline(
                    "archon-search", f"{search_url}/search", "POST", search_data
                )
                all_results.append(result)
            except Exception as e:
                logger.warning(f"Failed to measure search endpoint: {e}")

        # Get system metrics
        system_metrics = await measurer.get_system_metrics()

        # Create comprehensive baseline
        baseline = SystemBaseline(
            timestamp=datetime.utcnow().isoformat(),
            total_memory_gb=system_metrics["memory_total_gb"],
            available_memory_gb=system_metrics["memory_available_gb"],
            cpu_count=psutil.cpu_count(),
            disk_space_gb=system_metrics["disk_total_gb"],
            service_baselines=measurer.baseline_results,
            system_metrics=system_metrics,
        )

        logger.info("✅ Comprehensive baseline measurement completed")
        return baseline

    finally:
        await measurer.close()


async def save_baseline_results(baseline: SystemBaseline, output_file: str = None):
    """Save baseline results to file"""
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"performance_baseline_{timestamp}.json"

    baseline_data = asdict(baseline)

    with open(output_file, "w") as f:
        json.dump(baseline_data, f, indent=2)

    logger.info(f"📁 Baseline results saved to: {output_file}")
    return output_file


def print_baseline_summary(baseline: SystemBaseline):
    """Print a summary of baseline results"""
    print("\n" + "=" * 80)
    print("🎯 PERFORMANCE BASELINE SUMMARY")
    print("=" * 80)

    print(f"📅 Timestamp: {baseline.timestamp}")
    print(
        f"💾 System Memory: {baseline.available_memory_gb:.1f}GB / {baseline.total_memory_gb:.1f}GB available"
    )
    print(f"⚙️  CPU Cores: {baseline.cpu_count}")
    print(f"💽 Disk Space: {baseline.disk_space_gb:.1f}GB total")

    print("\n📊 System Metrics at Baseline:")
    for metric, value in baseline.system_metrics.items():
        if "percent" in metric:
            print(f"   • {metric}: {value:.1f}%")
        elif "gb" in metric:
            print(f"   • {metric}: {value:.2f}GB")
        else:
            print(f"   • {metric}: {value:.2f}")

    print("\n🔧 Service Performance Baselines:")
    print("-" * 80)

    # Group by service
    services = {}
    for result in baseline.service_baselines:
        if result.service not in services:
            services[result.service] = []
        services[result.service].append(result)

    for service_name, results in services.items():
        print(f"\n🏢 {service_name.upper()}:")
        for result in results:
            print(
                f"   • {result.operation}: {result.response_time_ms:.1f}ms avg "
                f"({result.success_rate:.1%} success, {result.throughput_ops_per_sec:.1f} ops/sec)"
            )
            if result.metadata.get("p95_response_time"):
                print(f"     P95: {result.metadata['p95_response_time']:.1f}ms")

    print("\n" + "=" * 80)
    print("🎯 PERFORMANCE TARGETS:")
    print("=" * 80)
    print("✅ Service startup time: <30 seconds")
    print("✅ API response time: <2 seconds")
    print("✅ Health check: <500ms")
    print("✅ Memory usage: <80% of allocated resources")
    print("✅ CPU usage: <70% sustained load")
    print("✅ Service availability: >99.9%")
    print("=" * 80)


async def run_baseline_comparison(baseline_file: str):
    """Run a new baseline and compare with previous results"""
    logger.info(f"📊 Running baseline comparison with {baseline_file}")

    # Load previous baseline
    with open(baseline_file, "r") as f:
        previous_data = json.load(f)

    # Run new baseline
    current_baseline = await establish_comprehensive_baseline()

    print("\n" + "=" * 80)
    print("📈 PERFORMANCE COMPARISON")
    print("=" * 80)

    # Compare service performance
    previous_services = {
        r["service"]: r
        for r in previous_data["service_baselines"]
        if r["operation"] == "health_check"
    }
    current_services = {
        r.service: r
        for r in current_baseline.service_baselines
        if r.operation == "health_check"
    }

    for service_name in set(previous_services.keys()) | set(current_services.keys()):
        prev = previous_services.get(service_name)
        curr = current_services.get(service_name)

        if prev and curr:
            change = (
                (curr.response_time_ms - prev["response_time_ms"])
                / prev["response_time_ms"]
            ) * 100
            status = "🔴" if change > 10 else "🟡" if change > 5 else "🟢"
            print(
                f"{status} {service_name}: {prev['response_time_ms']:.1f}ms → {curr.response_time_ms:.1f}ms ({change:+.1f}%)"
            )
        elif curr:
            print(f"🆕 {service_name}: {curr.response_time_ms:.1f}ms (new)")
        else:
            print(f"❌ {service_name}: offline")


async def main():
    """Main baseline measurement function"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Archon Performance Baseline Measurement"
    )
    parser.add_argument("--output", "-o", help="Output file for results")
    parser.add_argument("--compare", "-c", help="Compare with previous baseline file")
    parser.add_argument(
        "--monitor", "-m", action="store_true", help="Start continuous monitoring"
    )

    args = parser.parse_args()

    if args.compare:
        await run_baseline_comparison(args.compare)
        return

    if args.monitor:
        logger.info("🔄 Starting continuous performance monitoring...")
        await performance_monitor.start()
        try:
            while True:
                await asyncio.sleep(60)
                dashboard_data = performance_monitor.get_dashboard_data()
                logger.info(
                    f"System Health - CPU: {dashboard_data['system_metrics']['cpu']['current']:.1f}%, "
                    f"Memory: {dashboard_data['system_metrics']['memory']['current']:.1f}%, "
                    f"Services: {dashboard_data['system_metrics']['services']['current']:.1%}"
                )
        except KeyboardInterrupt:
            logger.info("Stopping monitoring...")
        finally:
            await performance_monitor.stop()
        return

    # Run baseline measurement
    baseline = await establish_comprehensive_baseline()

    # Save results
    await save_baseline_results(baseline, args.output)

    # Print summary
    print_baseline_summary(baseline)

    return baseline


if __name__ == "__main__":
    asyncio.run(main())
