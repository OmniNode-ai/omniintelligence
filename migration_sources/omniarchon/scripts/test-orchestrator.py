#!/usr/bin/env python3
"""
Archon MCP Integration Test Orchestrator

A unified test runner and orchestration system that provides comprehensive
control over the integration test suite with advanced features like:
- Multi-environment testing
- Parallel test execution
- Result aggregation and analysis
- Resource management
- Failure recovery
- Performance optimization
"""

import asyncio
import json
import logging
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click
import psutil

import docker

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
RESULTS_DIR = PROJECT_ROOT / "test-results"
CONFIG_DIR = PROJECT_ROOT / "tests" / "integration" / "config"

# Logging setup
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class TestSuite:
    """Configuration for a test suite"""

    name: str
    description: str
    test_paths: List[str]
    markers: List[str] = field(default_factory=list)
    timeout_seconds: int = 1800
    parallel_workers: int = 2
    required_services: List[str] = field(default_factory=list)
    performance_thresholds: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Environment:
    """Test environment configuration"""

    name: str
    description: str
    compose_file: str
    env_file: Optional[str] = None
    service_ports: Dict[str, int] = field(default_factory=dict)
    resource_requirements: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestExecution:
    """Results from a test execution"""

    suite_name: str
    environment: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "running"
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    duration_seconds: float = 0.0
    coverage_percent: float = 0.0
    artifacts_path: Optional[Path] = None
    error_message: Optional[str] = None
    performance_metrics: Dict[str, Any] = field(default_factory=dict)


class ResourceMonitor:
    """Monitor system resources during test execution"""

    def __init__(self):
        self.monitoring = False
        self.metrics = []

    def start_monitoring(self, interval_seconds: float = 5.0):
        """Start resource monitoring"""
        self.monitoring = True
        self.metrics = []

        async def monitor():
            while self.monitoring:
                try:
                    cpu_percent = psutil.cpu_percent(interval=1)
                    memory = psutil.virtual_memory()
                    disk = psutil.disk_usage("/")

                    metric = {
                        "timestamp": datetime.now().isoformat(),
                        "cpu_percent": cpu_percent,
                        "memory_percent": memory.percent,
                        "memory_available_gb": memory.available / (1024**3),
                        "disk_free_gb": disk.free / (1024**3),
                        "disk_percent": (disk.used / disk.total) * 100,
                    }

                    self.metrics.append(metric)
                    await asyncio.sleep(interval_seconds)

                except Exception as e:
                    logger.warning(f"Resource monitoring error: {e}")
                    await asyncio.sleep(interval_seconds)

        asyncio.create_task(monitor())

    def stop_monitoring(self) -> Dict[str, Any]:
        """Stop monitoring and return aggregated metrics"""
        self.monitoring = False

        if not self.metrics:
            return {}

        # Calculate aggregated metrics
        cpu_values = [m["cpu_percent"] for m in self.metrics]
        memory_values = [m["memory_percent"] for m in self.metrics]

        return {
            "duration_minutes": len(self.metrics) * 5.0 / 60.0,
            "cpu_avg": sum(cpu_values) / len(cpu_values),
            "cpu_max": max(cpu_values),
            "memory_avg": sum(memory_values) / len(memory_values),
            "memory_max": max(memory_values),
            "samples_collected": len(self.metrics),
            "detailed_metrics": self.metrics,
        }


class ServiceManager:
    """Manage Docker services for testing"""

    def __init__(self, compose_file: Path):
        self.compose_file = compose_file
        self.docker_client = docker.from_env()
        self.project_name = f"archon-integration-{int(time.time())}"

    async def start_services(self, services: Optional[List[str]] = None) -> bool:
        """Start Docker services"""
        try:
            cmd = [
                "docker",
                "compose",
                "-f",
                str(self.compose_file),
                "-p",
                self.project_name,
                "up",
                "-d",
                "--build",
            ]

            if services:
                cmd.extend(services)

            logger.info(f"Starting services: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode != 0:
                logger.error(f"Failed to start services: {result.stderr}")
                return False

            logger.info("Services started successfully")
            return True

        except subprocess.TimeoutExpired:
            logger.error("Service startup timed out")
            return False
        except Exception as e:
            logger.error(f"Error starting services: {e}")
            return False

    async def wait_for_health(self, max_wait_seconds: int = 300) -> bool:
        """Wait for services to become healthy"""
        logger.info("Waiting for services to become healthy...")

        health_endpoints = [
            "http://localhost:18181/health",
            "http://localhost:18051/health",
            "http://localhost:18053/health",
        ]

        start_time = time.time()
        while time.time() - start_time < max_wait_seconds:
            try:
                import aiohttp

                async with aiohttp.ClientSession() as session:
                    healthy_count = 0
                    for endpoint in health_endpoints:
                        try:
                            async with session.get(endpoint, timeout=5) as response:
                                if response.status == 200:
                                    healthy_count += 1
                        except:
                            pass

                    if healthy_count == len(health_endpoints):
                        logger.info("All services are healthy")
                        return True

            except ImportError:
                # Fallback to curl if aiohttp not available
                healthy_count = 0
                for endpoint in health_endpoints:
                    try:
                        result = subprocess.run(
                            ["curl", "-sf", endpoint], capture_output=True, timeout=5
                        )
                        if result.returncode == 0:
                            healthy_count += 1
                    except:
                        pass

                if healthy_count == len(health_endpoints):
                    logger.info("All services are healthy")
                    return True

            await asyncio.sleep(10)

        logger.error("Services failed to become healthy within timeout")
        return False

    async def stop_services(self, remove_volumes: bool = True):
        """Stop and clean up services"""
        try:
            cmd = [
                "docker",
                "compose",
                "-f",
                str(self.compose_file),
                "-p",
                self.project_name,
                "down",
            ]

            if remove_volumes:
                cmd.extend(["--volumes", "--remove-orphans"])

            logger.info("Stopping services...")
            subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            logger.info("Services stopped")

        except Exception as e:
            logger.warning(f"Error stopping services: {e}")

    async def collect_logs(self, output_dir: Path):
        """Collect logs from all services"""
        try:
            output_dir.mkdir(parents=True, exist_ok=True)

            cmd = [
                "docker",
                "compose",
                "-f",
                str(self.compose_file),
                "-p",
                self.project_name,
                "logs",
                "--no-color",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                log_file = output_dir / "services.log"
                with open(log_file, "w") as f:
                    f.write(result.stdout)
                logger.info(f"Service logs saved to {log_file}")

        except Exception as e:
            logger.warning(f"Error collecting logs: {e}")


class TestRunner:
    """Execute tests with advanced features"""

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    async def run_test_suite(
        self, suite: TestSuite, environment: Environment, output_dir: Path
    ) -> TestExecution:
        """Run a test suite in the specified environment"""

        execution = TestExecution(
            suite_name=suite.name,
            environment=environment.name,
            start_time=datetime.now(),
            artifacts_path=output_dir,
        )

        logger.info(
            f"Starting test suite '{suite.name}' in environment '{environment.name}'"
        )

        try:
            # Start resource monitoring
            monitor = ResourceMonitor()
            monitor.start_monitoring()

            # Prepare test command
            cmd = await self._build_test_command(suite, environment, output_dir)

            # Execute tests
            logger.info(f"Executing: {' '.join(cmd)}")
            start_time = time.time()

            result = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=suite.timeout_seconds,
            )

            execution.duration_seconds = time.time() - start_time
            execution.end_time = datetime.now()

            # Stop resource monitoring
            execution.performance_metrics = monitor.stop_monitoring()

            # Parse results
            await self._parse_test_results(result, execution, output_dir)

            # Determine final status
            execution.status = "success" if execution.failed_tests == 0 else "failure"

            logger.info(
                f"Test suite '{suite.name}' completed: "
                f"{execution.passed_tests}/{execution.total_tests} passed "
                f"in {execution.duration_seconds:.1f}s"
            )

        except subprocess.TimeoutExpired:
            execution.status = "timeout"
            execution.error_message = (
                f"Test suite timed out after {suite.timeout_seconds}s"
            )
            execution.end_time = datetime.now()
            logger.error(execution.error_message)

        except Exception as e:
            execution.status = "error"
            execution.error_message = str(e)
            execution.end_time = datetime.now()
            logger.error(f"Test suite '{suite.name}' failed: {e}")

        return execution

    async def _build_test_command(
        self, suite: TestSuite, environment: Environment, output_dir: Path
    ) -> List[str]:
        """Build the pytest command for the test suite"""

        compose_file = PROJECT_ROOT / environment.compose_file

        cmd = [
            "docker",
            "compose",
            "-f",
            str(compose_file),
            "run",
            "--rm",
            "test-runner",
            "pytest",
        ]

        # Add test paths
        cmd.extend(suite.test_paths)

        # Add markers
        if suite.markers:
            for marker in suite.markers:
                cmd.extend(["-m", marker])

        # Add parallel execution if specified
        if suite.parallel_workers > 1:
            cmd.extend(["-n", str(suite.parallel_workers), "--dist=worksteal"])

        # Add output options
        cmd.extend(
            [
                "--tb=short",
                "--timeout",
                str(suite.timeout_seconds),
                "--junitxml",
                str(output_dir / "junit.xml"),
                "--html",
                str(output_dir / "report.html"),
                "--self-contained-html",
            ]
        )

        # Add coverage if specified
        if "coverage" in suite.markers or suite.name in ["full", "comprehensive"]:
            cmd.extend(
                [
                    "--cov=tests/integration",
                    "--cov-report=html:" + str(output_dir / "coverage"),
                    "--cov-report=xml:" + str(output_dir / "coverage.xml"),
                ]
            )

        # Add benchmarking for performance tests
        if "performance" in suite.name.lower() or "benchmark" in suite.markers:
            cmd.extend(
                [
                    "--benchmark-json",
                    str(output_dir / "benchmark.json"),
                    "--benchmark-html",
                    str(output_dir / "benchmark.html"),
                ]
            )

        return cmd

    async def _parse_test_results(
        self,
        result: subprocess.CompletedProcess,
        execution: TestExecution,
        output_dir: Path,
    ):
        """Parse test results from various sources"""

        try:
            # Parse JUnit XML if available
            junit_file = output_dir / "junit.xml"
            if junit_file.exists():
                import xml.etree.ElementTree as ET

                tree = ET.parse(junit_file)
                root = tree.getroot()

                if root.tag == "testsuites":
                    testsuite = root.find("testsuite")
                else:
                    testsuite = root

                if testsuite is not None:
                    execution.total_tests = int(testsuite.get("tests", 0))
                    execution.failed_tests = int(testsuite.get("failures", 0)) + int(
                        testsuite.get("errors", 0)
                    )
                    execution.skipped_tests = int(testsuite.get("skipped", 0))
                    execution.passed_tests = (
                        execution.total_tests
                        - execution.failed_tests
                        - execution.skipped_tests
                    )

            # Parse coverage if available
            coverage_file = output_dir / "coverage.xml"
            if coverage_file.exists():
                import xml.etree.ElementTree as ET

                try:
                    tree = ET.parse(coverage_file)
                    root = tree.getroot()
                    coverage_elem = root.find(".//coverage")
                    if coverage_elem is not None:
                        line_rate = coverage_elem.get("line-rate")
                        if line_rate:
                            execution.coverage_percent = float(line_rate) * 100
                except ET.ParseError:
                    pass

            # Parse benchmark results if available
            benchmark_file = output_dir / "benchmark.json"
            if benchmark_file.exists():
                try:
                    with open(benchmark_file, "r") as f:
                        benchmark_data = json.load(f)
                    execution.performance_metrics["benchmarks"] = benchmark_data
                except json.JSONDecodeError:
                    pass

        except Exception as e:
            logger.warning(f"Error parsing test results: {e}")


class TestOrchestrator:
    """Main orchestrator for integration tests"""

    def __init__(self):
        self.test_suites = self._load_test_suites()
        self.environments = self._load_environments()
        self.executions: List[TestExecution] = []

    def _load_test_suites(self) -> Dict[str, TestSuite]:
        """Load test suite configurations"""
        return {
            "smoke": TestSuite(
                name="smoke",
                description="Minimal smoke tests for deployment validation",
                test_paths=["tests/integration/"],
                markers=["smoke"],
                timeout_seconds=300,
                parallel_workers=1,
            ),
            "fast": TestSuite(
                name="fast",
                description="Essential tests for quick validation",
                test_paths=[
                    "tests/integration/test_happy_path.py::test_complete_pipeline_single_document",
                    "tests/integration/test_error_handling.py::TestServiceFailureScenarios::test_intelligence_service_unavailable",
                    "tests/integration/test_performance.py::TestLatencyBenchmarks::test_document_creation_latency",
                    "tests/integration/test_data_consistency.py::TestCrossServiceDataConsistency::test_document_creation_consistency",
                ],
                timeout_seconds=900,
                parallel_workers=2,
            ),
            "happy-path": TestSuite(
                name="happy-path",
                description="Happy path integration tests",
                test_paths=["tests/integration/test_happy_path.py"],
                timeout_seconds=1200,
                parallel_workers=2,
            ),
            "errors": TestSuite(
                name="errors",
                description="Error handling and resilience tests",
                test_paths=["tests/integration/test_error_handling.py"],
                timeout_seconds=1500,
                parallel_workers=2,
            ),
            "performance": TestSuite(
                name="performance",
                description="Performance benchmarks and load tests",
                test_paths=["tests/integration/test_performance.py"],
                markers=["performance"],
                timeout_seconds=2400,
                parallel_workers=1,
            ),
            "consistency": TestSuite(
                name="consistency",
                description="Data consistency validation tests",
                test_paths=["tests/integration/test_data_consistency.py"],
                timeout_seconds=1800,
                parallel_workers=2,
            ),
            "full": TestSuite(
                name="full",
                description="Complete integration test suite",
                test_paths=["tests/integration/"],
                markers=["not slow"],
                timeout_seconds=3600,
                parallel_workers=3,
            ),
            "comprehensive": TestSuite(
                name="comprehensive",
                description="All tests including slow and resource-intensive ones",
                test_paths=["tests/integration/"],
                timeout_seconds=5400,
                parallel_workers=2,
            ),
        }

    def _load_environments(self) -> Dict[str, Environment]:
        """Load environment configurations"""
        return {
            "local": Environment(
                name="local",
                description="Local development environment",
                compose_file="deployment/docker-compose.integration-tests.yml",
                service_ports={
                    "archon-server": 18181,
                    "archon-mcp": 18051,
                    "intelligence": 18053,
                },
            ),
            "ci": Environment(
                name="ci",
                description="CI/CD optimized environment",
                compose_file="deployment/docker-compose.integration-tests.yml",
                resource_requirements={"memory_gb": 4, "disk_gb": 10, "cpu_cores": 2},
            ),
        }

    async def run_single_suite(
        self, suite_name: str, environment_name: str = "local", cleanup: bool = True
    ) -> TestExecution:
        """Run a single test suite"""

        if suite_name not in self.test_suites:
            raise ValueError(f"Unknown test suite: {suite_name}")

        if environment_name not in self.environments:
            raise ValueError(f"Unknown environment: {environment_name}")

        suite = self.test_suites[suite_name]
        environment = self.environments[environment_name]

        # Prepare output directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = RESULTS_DIR / f"{suite_name}_{environment_name}_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Setup service manager
        compose_file = PROJECT_ROOT / environment.compose_file
        service_manager = ServiceManager(compose_file)

        try:
            # Start services
            if not await service_manager.start_services():
                raise RuntimeError("Failed to start services")

            # Wait for health
            if not await service_manager.wait_for_health():
                raise RuntimeError("Services failed to become healthy")

            # Run tests
            runner = TestRunner(self)
            execution = await runner.run_test_suite(suite, environment, output_dir)

            # Collect service logs
            await service_manager.collect_logs(output_dir / "logs")

            # Store execution record
            self.executions.append(execution)

            return execution

        finally:
            if cleanup:
                await service_manager.stop_services()

    async def run_multiple_suites(
        self,
        suite_names: List[str],
        environment_name: str = "local",
        parallel: bool = False,
        cleanup_each: bool = False,
    ) -> List[TestExecution]:
        """Run multiple test suites"""

        if parallel:
            return await self._run_suites_parallel(suite_names, environment_name)
        else:
            return await self._run_suites_sequential(
                suite_names, environment_name, cleanup_each
            )

    async def _run_suites_sequential(
        self, suite_names: List[str], environment_name: str, cleanup_each: bool
    ) -> List[TestExecution]:
        """Run test suites sequentially"""

        executions = []
        for suite_name in suite_names:
            try:
                execution = await self.run_single_suite(
                    suite_name, environment_name, cleanup=cleanup_each
                )
                executions.append(execution)

                # Stop on first failure if requested
                if execution.status == "failure":
                    logger.warning(
                        f"Suite {suite_name} failed, continuing with next suite"
                    )

            except Exception as e:
                logger.error(f"Failed to run suite {suite_name}: {e}")
                # Create a failed execution record
                execution = TestExecution(
                    suite_name=suite_name,
                    environment=environment_name,
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    status="error",
                    error_message=str(e),
                )
                executions.append(execution)

        return executions

    async def _run_suites_parallel(
        self, suite_names: List[str], environment_name: str
    ) -> List[TestExecution]:
        """Run test suites in parallel"""

        tasks = []
        for suite_name in suite_names:
            task = self.run_single_suite(suite_name, environment_name, cleanup=True)
            tasks.append(task)

        # Execute all tasks concurrently
        executions = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        results = []
        for i, result in enumerate(executions):
            if isinstance(result, Exception):
                execution = TestExecution(
                    suite_name=suite_names[i],
                    environment=environment_name,
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    status="error",
                    error_message=str(result),
                )
                results.append(execution)
            else:
                results.append(result)

        return results

    def generate_summary_report(
        self, executions: List[TestExecution]
    ) -> Dict[str, Any]:
        """Generate a comprehensive summary report"""

        total_suites = len(executions)
        successful_suites = len([e for e in executions if e.status == "success"])
        failed_suites = len([e for e in executions if e.status == "failure"])
        error_suites = len([e for e in executions if e.status == "error"])

        total_tests = sum(e.total_tests for e in executions)
        passed_tests = sum(e.passed_tests for e in executions)
        failed_tests = sum(e.failed_tests for e in executions)
        skipped_tests = sum(e.skipped_tests for e in executions)

        total_duration = sum(e.duration_seconds for e in executions)
        avg_coverage = (
            sum(e.coverage_percent for e in executions) / total_suites
            if total_suites > 0
            else 0
        )

        return {
            "summary": {
                "total_suites": total_suites,
                "successful_suites": successful_suites,
                "failed_suites": failed_suites,
                "error_suites": error_suites,
                "success_rate": (
                    successful_suites / total_suites * 100 if total_suites > 0 else 0
                ),
            },
            "test_results": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "skipped_tests": skipped_tests,
                "pass_rate": passed_tests / total_tests * 100 if total_tests > 0 else 0,
            },
            "performance": {
                "total_duration_seconds": total_duration,
                "average_coverage_percent": avg_coverage,
                "executions": [
                    {
                        "suite": e.suite_name,
                        "environment": e.environment,
                        "status": e.status,
                        "duration": e.duration_seconds,
                        "tests": f"{e.passed_tests}/{e.total_tests}",
                        "coverage": e.coverage_percent,
                    }
                    for e in executions
                ],
            },
            "timestamp": datetime.now().isoformat(),
            "detailed_executions": executions,
        }


# CLI Interface
@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--log-file", type=click.Path(), help="Log to file")
def cli(verbose: bool, log_file: Optional[str]):
    """Archon MCP Integration Test Orchestrator"""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logging.getLogger().addHandler(file_handler)


@cli.command()
@click.argument("suite_name")
@click.option("--environment", "-e", default="local", help="Test environment")
@click.option("--no-cleanup", is_flag=True, help="Skip cleanup after tests")
@click.option("--output-dir", type=click.Path(), help="Custom output directory")
def run(suite_name: str, environment: str, no_cleanup: bool, output_dir: Optional[str]):
    """Run a single test suite"""

    async def _run():
        orchestrator = TestOrchestrator()

        try:
            execution = await orchestrator.run_single_suite(
                suite_name=suite_name,
                environment_name=environment,
                cleanup=not no_cleanup,
            )

            # Print summary
            print(f"\n🧪 Test Suite: {execution.suite_name}")
            print(f"🌍 Environment: {execution.environment}")
            print(f"⏱️  Duration: {execution.duration_seconds:.1f}s")
            print(
                f"📊 Results: {execution.passed_tests}/{execution.total_tests} passed"
            )
            print(f"📈 Coverage: {execution.coverage_percent:.1f}%")
            print(f"✅ Status: {execution.status}")

            if execution.artifacts_path:
                print(f"📁 Artifacts: {execution.artifacts_path}")

            if execution.status != "success":
                print(f"❌ Error: {execution.error_message}")
                sys.exit(1)

        except Exception as e:
            logger.error(f"Failed to run test suite: {e}")
            sys.exit(1)

    asyncio.run(_run())


@cli.command()
@click.argument("suite_names", nargs=-1, required=True)
@click.option("--environment", "-e", default="local", help="Test environment")
@click.option("--parallel", "-p", is_flag=True, help="Run suites in parallel")
@click.option("--no-cleanup", is_flag=True, help="Skip cleanup after tests")
@click.option("--stop-on-failure", is_flag=True, help="Stop on first failure")
def run_multiple(
    suite_names: Tuple[str],
    environment: str,
    parallel: bool,
    no_cleanup: bool,
    stop_on_failure: bool,
):
    """Run multiple test suites"""

    async def _run():
        orchestrator = TestOrchestrator()

        try:
            executions = await orchestrator.run_multiple_suites(
                suite_names=list(suite_names),
                environment_name=environment,
                parallel=parallel,
                cleanup_each=not no_cleanup,
            )

            # Generate and display summary
            report = orchestrator.generate_summary_report(executions)

            print("\n📊 Test Execution Summary")
            print("═══════════════════════════")
            print(
                f"Suites: {report['summary']['successful_suites']}/{report['summary']['total_suites']} successful"
            )
            print(
                f"Tests: {report['test_results']['passed_tests']}/{report['test_results']['total_tests']} passed"
            )
            print(f"Duration: {report['performance']['total_duration_seconds']:.1f}s")
            print(f"Coverage: {report['performance']['average_coverage_percent']:.1f}%")

            print("\n📋 Suite Details:")
            for exec_info in report["performance"]["executions"]:
                status_icon = "✅" if exec_info["status"] == "success" else "❌"
                print(
                    f"  {status_icon} {exec_info['suite']}: {exec_info['tests']} ({exec_info['duration']:.1f}s)"
                )

            # Save detailed report
            report_file = (
                RESULTS_DIR / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            report_file.parent.mkdir(parents=True, exist_ok=True)
            with open(report_file, "w") as f:
                json.dump(report, f, indent=2, default=str)
            print(f"\n📄 Detailed report: {report_file}")

            # Exit with error if any suite failed
            if (
                report["summary"]["failed_suites"] > 0
                or report["summary"]["error_suites"] > 0
            ):
                sys.exit(1)

        except Exception as e:
            logger.error(f"Failed to run test suites: {e}")
            sys.exit(1)

    asyncio.run(_run())


@cli.command()
def list_suites():
    """List available test suites"""
    orchestrator = TestOrchestrator()

    print("📋 Available Test Suites:")
    print("═════════════════════════")

    for name, suite in orchestrator.test_suites.items():
        print(f"\n🧪 {name}")
        print(f"   Description: {suite.description}")
        print(f"   Timeout: {suite.timeout_seconds}s")
        print(f"   Workers: {suite.parallel_workers}")
        if suite.markers:
            print(f"   Markers: {', '.join(suite.markers)}")


@cli.command()
def list_environments():
    """List available test environments"""
    orchestrator = TestOrchestrator()

    print("🌍 Available Environments:")
    print("══════════════════════════")

    for name, env in orchestrator.environments.items():
        print(f"\n🏗️  {name}")
        print(f"   Description: {env.description}")
        print(f"   Compose file: {env.compose_file}")
        if env.service_ports:
            print(f"   Ports: {env.service_ports}")


@cli.command()
@click.option("--port", default=8080, help="Dashboard port")
@click.option("--host", default="127.0.0.1", help="Dashboard host")
def dashboard(port: int, host: str):
    """Launch the test results dashboard"""
    try:
        dashboard_script = SCRIPTS_DIR / "test-dashboard.py"
        subprocess.run(
            [
                sys.executable,
                str(dashboard_script),
                "--port",
                str(port),
                "--host",
                host,
                "--scan",
            ]
        )
    except KeyboardInterrupt:
        print("\n🛑 Dashboard stopped")
    except Exception as e:
        logger.error(f"Failed to start dashboard: {e}")
        sys.exit(1)


@cli.command()
@click.option("--days", default=30, help="Number of days to analyze")
def analyze(days: int):
    """Analyze test execution history and generate insights"""
    # This would integrate with the dashboard database to provide analysis
    print(f"🔍 Analyzing test history for the last {days} days...")
    print("📊 Analysis features coming soon!")


if __name__ == "__main__":
    cli()
