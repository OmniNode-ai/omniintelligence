#!/usr/bin/env python3
"""
Comprehensive MCP Document Indexing Integration Test Suite

Master test execution script for running comprehensive end-to-end integration tests
for the MCP document indexing pipeline. This script orchestrates all test suites
and provides unified reporting.

CRITICAL ISSUE ADDRESSED:
The MCP Document Creation → RAG Retrievability pathway is FAILING with documents
not being retrievable within the expected 30-second SLA. This test suite provides
comprehensive validation to identify and resolve this critical issue.

Test Suites Included:
1. Enhanced MCP Integration Tests (PRIMARY - addresses failing MCP→RAG pathway)
2. Service Communication Tests (validates service connectivity)
3. SLA Performance Tests (enforces 30-second SLA requirements)
4. Edge Case and Error Handling Tests
5. Vector Embedding and Qdrant Validation Tests
6. Entity Extraction and Memgraph Tests

Usage:
    # Run all tests
    poetry run python run_integration_tests.py

    # Run specific test suite
    poetry run python run_integration_tests.py --suite mcp_integration

    # Run with strict SLA enforcement
    poetry run python run_integration_tests.py --strict-sla

    # Run load testing scenarios
    poetry run python run_integration_tests.py --load-test

    # Run continuous monitoring
    poetry run python run_integration_tests.py --continuous 30

    # Generate CI/CD report
    poetry run python run_integration_tests.py --ci-cd-report

    # Quick health check only
    poetry run python run_integration_tests.py --health-check-only
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TestSuiteStatus(Enum):
    """Test suite execution status"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class TestSuiteConfig:
    """Test suite configuration"""

    name: str
    script_path: str
    description: str
    critical: bool = False
    dependencies: List[str] = None
    timeout: float = 300.0  # 5 minutes default


@dataclass
class TestSuiteResult:
    """Test suite execution result"""

    name: str
    status: TestSuiteStatus
    start_time: float
    end_time: Optional[float]
    duration: Optional[float]
    exit_code: Optional[int]
    stdout: str = ""
    stderr: str = ""
    report_file: Optional[str] = None
    error_message: Optional[str] = None


class IntegrationTestOrchestrator:
    """
    Master orchestrator for comprehensive MCP document indexing integration tests
    """

    def __init__(
        self,
        strict_sla: bool = False,
        load_test: bool = False,
        verbose: bool = False,
        parallel: bool = False,
    ):
        self.strict_sla = strict_sla
        self.load_test = load_test
        self.verbose = verbose
        self.parallel = parallel
        self.test_session_id = (
            f"integration_test_{uuid.uuid4().hex[:8]}_{int(time.time())}"
        )

        # Test suite configurations
        self.test_suites = {
            "health_check": TestSuiteConfig(
                name="health_check",
                script_path="test_real_time_indexing_pipeline.py",
                description="Service Health Check and Basic Connectivity",
                critical=True,
                timeout=60.0,
            ),
            "mcp_integration": TestSuiteConfig(
                name="mcp_integration",
                script_path="tests/enhanced_mcp_integration_tests.py",
                description="Enhanced MCP Document Creation → RAG Retrievability (PRIMARY FOCUS)",
                critical=True,
                dependencies=["health_check"],
                timeout=600.0,  # 10 minutes
            ),
            "service_communication": TestSuiteConfig(
                name="service_communication",
                script_path="tests/service_communication_tests.py",
                description="Service Communication and Bridge Sync Validation",
                critical=True,
                dependencies=["health_check"],
                timeout=300.0,
            ),
            "sla_performance": TestSuiteConfig(
                name="sla_performance",
                script_path="tests/sla_performance_tests.py",
                description="Strict 30-Second SLA Validation and Performance Benchmarks",
                critical=True,
                dependencies=["mcp_integration"],
                timeout=900.0,  # 15 minutes
            ),
            "vector_indexing": TestSuiteConfig(
                name="vector_indexing",
                script_path="tests/vector_indexing_tests.py",
                description="Vector Embedding and Qdrant Indexing Validation",
                critical=False,
                dependencies=["service_communication"],
                timeout=300.0,
            ),
            "entity_extraction": TestSuiteConfig(
                name="entity_extraction",
                script_path="tests/entity_extraction_tests.py",
                description="Entity Extraction and Memgraph Storage Validation",
                critical=False,
                dependencies=["service_communication"],
                timeout=300.0,
            ),
            "edge_cases": TestSuiteConfig(
                name="edge_cases",
                script_path="tests/edge_case_tests.py",
                description="Edge Cases and Error Handling Validation",
                critical=False,
                dependencies=["mcp_integration"],
                timeout=300.0,
            ),
        }

        self.suite_results = {}
        self.overall_start_time = None
        self.overall_end_time = None

        if verbose:
            logger.setLevel(logging.DEBUG)

    async def run_comprehensive_tests(
        self,
        selected_suites: Optional[List[str]] = None,
        continuous_minutes: int = 0,
        health_check_only: bool = False,
    ) -> Dict[str, Any]:
        """Run comprehensive integration test suite"""

        print("🚀 COMPREHENSIVE MCP DOCUMENT INDEXING INTEGRATION TESTS")
        print("=" * 80)
        print(f"Session ID: {self.test_session_id}")
        print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        print(f"Strict SLA Mode: {'ENABLED' if self.strict_sla else 'DISABLED'}")
        print(f"Load Testing: {'ENABLED' if self.load_test else 'DISABLED'}")
        print(f"Parallel Execution: {'ENABLED' if self.parallel else 'DISABLED'}")
        print(
            f"Continuous Mode: {f'{continuous_minutes} minutes' if continuous_minutes > 0 else 'DISABLED'}"
        )
        print("=" * 80)

        print("\n🎯 CRITICAL ISSUE BEING ADDRESSED:")
        print("MCP Document Creation → RAG Retrievability pathway is FAILING")
        print("Documents created via MCP are not retrievable within 30-second SLA")
        print("This test suite provides comprehensive validation to resolve this issue")

        self.overall_start_time = time.time()

        try:
            # Determine which test suites to run
            if health_check_only:
                suites_to_run = ["health_check"]
            elif selected_suites:
                suites_to_run = selected_suites
            else:
                suites_to_run = list(self.test_suites.keys())

            print(f"\n📋 Test Suites to Execute: {', '.join(suites_to_run)}")

            # Validate service availability first
            await self._validate_service_availability()

            # Execute test suites
            if self.parallel and len(suites_to_run) > 1:
                await self._run_test_suites_parallel(suites_to_run)
            else:
                await self._run_test_suites_sequential(suites_to_run)

            # Run continuous monitoring if requested
            if continuous_minutes > 0:
                await self._run_continuous_monitoring(continuous_minutes)

        except Exception as e:
            logger.error(f"Integration test orchestration failed: {e}")
            self._record_suite_result(
                "orchestration",
                TestSuiteStatus.FAILED,
                time.time(),
                error_message=str(e),
            )

        finally:
            self.overall_end_time = time.time()
            return await self._generate_comprehensive_report()

    async def _validate_service_availability(self):
        """Validate that all required services are available"""
        print("\n🔍 Validating Service Availability...")

        services = {
            "Main Server": "http://localhost:8181/health",
            "MCP Server": "http://localhost:8051/mcp",
            "Intelligence Service": "http://localhost:8053/health",
            "Bridge Service": "http://localhost:8054/health",
            "Search Service": "http://localhost:8055/health",
            "Qdrant": "http://localhost:6333/readyz",
            "Memgraph": "http://localhost:7444/",
        }

        import httpx

        unavailable_services = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for service_name, url in services.items():
                try:
                    if "mcp" in url:
                        # Special handling for MCP
                        response = await client.post(
                            url, json={"method": "session_info", "params": {}}
                        )
                    else:
                        response = await client.get(url)

                    if response.status_code == 200:
                        print(f"  ✅ {service_name}: Available")
                    else:
                        print(
                            f"  ❌ {service_name}: Unavailable (HTTP {response.status_code})"
                        )
                        unavailable_services.append(service_name)

                except Exception as e:
                    print(f"  ❌ {service_name}: Unavailable ({e})")
                    unavailable_services.append(service_name)

        if unavailable_services:
            print(
                f"\n⚠️  WARNING: {len(unavailable_services)} services unavailable: {', '.join(unavailable_services)}"
            )
            print("Some tests may fail due to service unavailability")
        else:
            print("\n✅ All services are available and ready for testing")

    async def _run_test_suites_sequential(self, suites_to_run: List[str]):
        """Run test suites sequentially with dependency resolution"""
        print("\n🔄 Running Test Suites Sequentially...")

        # Resolve dependencies and create execution order
        execution_order = self._resolve_dependencies(suites_to_run)

        for suite_name in execution_order:
            if suite_name not in self.test_suites:
                logger.warning(f"Unknown test suite: {suite_name}")
                continue

            suite_config = self.test_suites[suite_name]
            print(f"\n📋 Executing: {suite_config.description}")

            start_time = time.time()
            self._record_suite_result(suite_name, TestSuiteStatus.RUNNING, start_time)

            try:
                result = await self._execute_test_suite(suite_config)
                end_time = time.time()

                self._record_suite_result(
                    suite_name,
                    (
                        TestSuiteStatus.COMPLETED
                        if result["exit_code"] == 0
                        else TestSuiteStatus.FAILED
                    ),
                    start_time,
                    end_time,
                    result["exit_code"],
                    result["stdout"],
                    result["stderr"],
                    result.get("report_file"),
                )

                if result["exit_code"] == 0:
                    print(
                        f"  ✅ {suite_name}: COMPLETED ({end_time - start_time:.1f}s)"
                    )
                else:
                    print(f"  ❌ {suite_name}: FAILED ({end_time - start_time:.1f}s)")

                    # Handle critical test failures
                    if suite_config.critical:
                        print(f"  🚨 CRITICAL TEST FAILED: {suite_name}")
                        if self.strict_sla:
                            print(
                                "  ⏹️  Stopping execution due to critical failure in strict mode"
                            )
                            break

            except Exception as e:
                end_time = time.time()
                self._record_suite_result(
                    suite_name,
                    TestSuiteStatus.FAILED,
                    start_time,
                    end_time,
                    None,
                    "",
                    str(e),
                    error_message=str(e),
                )
                print(f"  ❌ {suite_name}: EXCEPTION - {e}")

    async def _run_test_suites_parallel(self, suites_to_run: List[str]):
        """Run test suites in parallel where possible"""
        print("\n⚡ Running Test Suites in Parallel...")

        # Group suites by dependency level
        dependency_groups = self._group_by_dependencies(suites_to_run)

        for group_level, suite_group in enumerate(dependency_groups):
            if not suite_group:
                continue

            print(f"\n📋 Parallel Group {group_level + 1}: {', '.join(suite_group)}")

            # Execute all suites in this group concurrently
            tasks = []
            for suite_name in suite_group:
                if suite_name in self.test_suites:
                    suite_config = self.test_suites[suite_name]
                    tasks.append(
                        self._execute_test_suite_async(suite_name, suite_config)
                    )

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_test_suite_async(
        self, suite_name: str, suite_config: TestSuiteConfig
    ):
        """Execute a single test suite asynchronously"""
        start_time = time.time()
        self._record_suite_result(suite_name, TestSuiteStatus.RUNNING, start_time)

        try:
            result = await self._execute_test_suite(suite_config)
            end_time = time.time()

            self._record_suite_result(
                suite_name,
                (
                    TestSuiteStatus.COMPLETED
                    if result["exit_code"] == 0
                    else TestSuiteStatus.FAILED
                ),
                start_time,
                end_time,
                result["exit_code"],
                result["stdout"],
                result["stderr"],
                result.get("report_file"),
            )

            print(
                f"  {'✅' if result['exit_code'] == 0 else '❌'} {suite_name}: "
                f"{'COMPLETED' if result['exit_code'] == 0 else 'FAILED'} ({end_time - start_time:.1f}s)"
            )

        except Exception as e:
            end_time = time.time()
            self._record_suite_result(
                suite_name,
                TestSuiteStatus.FAILED,
                start_time,
                end_time,
                None,
                "",
                str(e),
                error_message=str(e),
            )
            print(f"  ❌ {suite_name}: EXCEPTION - {e}")

    async def _execute_test_suite(
        self, suite_config: TestSuiteConfig
    ) -> Dict[str, Any]:
        """Execute a single test suite"""
        script_path = suite_config.script_path

        # Build command arguments
        cmd = [sys.executable, script_path]

        if self.strict_sla:
            cmd.append("--strict-sla")
        if self.load_test:
            cmd.append("--load-test")
        if self.verbose:
            cmd.append("--verbose")

        try:
            # Execute the test script
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.getcwd(),
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=suite_config.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise Exception(f"Test suite timed out after {suite_config.timeout}s")

            # Decode output
            stdout_text = stdout.decode("utf-8") if stdout else ""
            stderr_text = stderr.decode("utf-8") if stderr else ""

            # Look for report files
            report_file = self._find_report_file(suite_config.name, stdout_text)

            return {
                "exit_code": process.returncode,
                "stdout": stdout_text,
                "stderr": stderr_text,
                "report_file": report_file,
            }

        except Exception as e:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "report_file": None,
            }

    def _find_report_file(self, suite_name: str, stdout: str) -> Optional[str]:
        """Find report file mentioned in stdout"""
        import re

        # Look for report file patterns in stdout
        patterns = [
            r"report saved to:\s*([^\s\n]+)",
            r"Report file:\s*([^\s\n]+)",
            r"Detailed report:\s*([^\s\n]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, stdout, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _resolve_dependencies(self, suites_to_run: List[str]) -> List[str]:
        """Resolve test suite dependencies and return execution order"""
        execution_order = []
        processed = set()

        def add_suite(suite_name: str):
            if suite_name in processed or suite_name not in self.test_suites:
                return

            suite_config = self.test_suites[suite_name]

            # Add dependencies first
            if suite_config.dependencies:
                for dependency in suite_config.dependencies:
                    if dependency in suites_to_run:
                        add_suite(dependency)

            if suite_name not in processed:
                execution_order.append(suite_name)
                processed.add(suite_name)

        for suite_name in suites_to_run:
            add_suite(suite_name)

        return execution_order

    def _group_by_dependencies(self, suites_to_run: List[str]) -> List[List[str]]:
        """Group test suites by dependency level for parallel execution"""
        dependency_groups = []
        remaining_suites = set(suites_to_run)
        processed = set()

        while remaining_suites:
            current_group = []

            for suite_name in list(remaining_suites):
                suite_config = self.test_suites.get(suite_name)
                if not suite_config:
                    continue

                # Check if all dependencies are satisfied
                can_run = True
                if suite_config.dependencies:
                    for dependency in suite_config.dependencies:
                        if dependency in suites_to_run and dependency not in processed:
                            can_run = False
                            break

                if can_run:
                    current_group.append(suite_name)

            if current_group:
                dependency_groups.append(current_group)
                for suite_name in current_group:
                    remaining_suites.remove(suite_name)
                    processed.add(suite_name)
            else:
                # Circular dependency or missing dependency - add remaining suites
                dependency_groups.append(list(remaining_suites))
                break

        return dependency_groups

    def _record_suite_result(
        self,
        suite_name: str,
        status: TestSuiteStatus,
        start_time: float,
        end_time: Optional[float] = None,
        exit_code: Optional[int] = None,
        stdout: str = "",
        stderr: str = "",
        report_file: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        """Record test suite result"""
        result = TestSuiteResult(
            name=suite_name,
            status=status,
            start_time=start_time,
            end_time=end_time,
            duration=end_time - start_time if end_time else None,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            report_file=report_file,
            error_message=error_message,
        )
        self.suite_results[suite_name] = result

    async def _run_continuous_monitoring(self, minutes: int):
        """Run continuous monitoring for specified duration"""
        print(f"\n🔄 Running Continuous Monitoring for {minutes} minutes...")

        start_time = time.time()
        end_time = start_time + (minutes * 60)

        iteration = 1
        while time.time() < end_time:
            remaining_time = end_time - time.time()
            print(
                f"\n🔄 Continuous Monitoring - Iteration {iteration} ({remaining_time/60:.1f} minutes remaining)"
            )

            # Run critical tests only in continuous mode
            critical_suites = [
                name for name, config in self.test_suites.items() if config.critical
            ]
            await self._run_test_suites_sequential(critical_suites)

            # Wait before next iteration (minimum 5 minutes between runs)
            wait_time = min(300, remaining_time)  # 5 minutes or remaining time
            if wait_time > 60:  # Only wait if more than 1 minute remaining
                print(
                    f"  ⏳ Waiting {wait_time/60:.1f} minutes before next iteration..."
                )
                await asyncio.sleep(wait_time)

            iteration += 1

        print(f"\n✅ Continuous monitoring completed after {minutes} minutes")

    async def _generate_comprehensive_report(self) -> Dict[str, Any]:
        """Generate comprehensive test execution report"""
        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE INTEGRATION TEST REPORT")
        print("=" * 80)

        total_duration = (
            self.overall_end_time - self.overall_start_time
            if self.overall_end_time
            else 0
        )

        # Calculate summary statistics
        total_suites = len(self.suite_results)
        completed_suites = sum(
            1
            for r in self.suite_results.values()
            if r.status == TestSuiteStatus.COMPLETED
        )
        failed_suites = sum(
            1 for r in self.suite_results.values() if r.status == TestSuiteStatus.FAILED
        )
        critical_failures = sum(
            1
            for name, result in self.suite_results.items()
            if result.status == TestSuiteStatus.FAILED
            and self.test_suites.get(name, {}).critical
        )

        success_rate = (
            (completed_suites / total_suites * 100) if total_suites > 0 else 0
        )

        print(f"Session ID: {self.test_session_id}")
        print(f"Total Execution Time: {total_duration:.2f}s")
        print(f"Total Test Suites: {total_suites}")
        print(f"✅ Completed: {completed_suites}")
        print(f"❌ Failed: {failed_suites}")
        print(f"Success Rate: {success_rate:.1f}%")

        # Critical Test Results
        print("\n🎯 Critical Test Results:")
        critical_suites = {
            name: config for name, config in self.test_suites.items() if config.critical
        }

        for suite_name, suite_config in critical_suites.items():
            result = self.suite_results.get(suite_name)
            if result:
                status_symbol = (
                    "✅" if result.status == TestSuiteStatus.COMPLETED else "❌"
                )
                duration_text = f"({result.duration:.1f}s)" if result.duration else ""
                print(
                    f"  {status_symbol} {suite_config.description}: {result.status.value} {duration_text}"
                )

        # MCP → RAG Retrievability Assessment
        print("\n🚨 MCP → RAG RETRIEVABILITY ASSESSMENT:")
        mcp_result = self.suite_results.get("mcp_integration")
        if mcp_result:
            if mcp_result.status == TestSuiteStatus.COMPLETED:
                print("  🎉 PRIMARY ISSUE RESOLVED: MCP → RAG pathway is working!")
                print("  ✅ Documents created via MCP are retrievable within SLA")
            else:
                print("  ❌ PRIMARY ISSUE PERSISTS: MCP → RAG pathway still failing")
                print("  ⚠️  Documents created via MCP are NOT retrievable within SLA")
        else:
            print("  ⚠️  MCP integration test was not executed")

        # SLA Compliance Assessment
        print("\n⏱️  SLA Compliance Assessment:")
        sla_result = self.suite_results.get("sla_performance")
        if sla_result:
            if sla_result.status == TestSuiteStatus.COMPLETED:
                print("  ✅ 30-Second SLA: COMPLIANCE VERIFIED")
            else:
                print("  ❌ 30-Second SLA: COMPLIANCE FAILED")
        else:
            print("  ⚠️  SLA performance test was not executed")

        # Service Communication Assessment
        print("\n🌐 Service Communication Assessment:")
        comm_result = self.suite_results.get("service_communication")
        if comm_result:
            if comm_result.status == TestSuiteStatus.COMPLETED:
                print("  ✅ Service Communication: ALL PATHWAYS FUNCTIONAL")
            else:
                print("  ❌ Service Communication: PATHWAY FAILURES DETECTED")
        else:
            print("  ⚠️  Service communication test was not executed")

        # Overall Assessment
        print("\n🎯 Overall Assessment:")
        if critical_failures == 0 and success_rate >= 95:
            print(
                "🎉 EXCELLENT: All critical tests passed! System is fully functional."
            )
            print("   MCP document indexing pipeline is working correctly.")
        elif critical_failures == 0:
            print(
                "✅ GOOD: All critical tests passed with minor issues in non-critical tests."
            )
        elif critical_failures <= 1:
            print(
                "⚠️  CONCERNING: Some critical test failures detected. System needs attention."
            )
            print("   MCP → RAG pathway may still have issues.")
        else:
            print(
                "❌ CRITICAL: Multiple critical test failures. System requires immediate fixes."
            )
            print("   MCP → RAG pathway is likely still broken.")

        # Report Files
        print("\n📄 Individual Test Reports:")
        for suite_name, result in self.suite_results.items():
            if result.report_file:
                print(f"  📊 {suite_name}: {result.report_file}")

        print("=" * 80)

        # Generate unified report
        unified_report = {
            "session_id": self.test_session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_summary": {
                "total_duration": total_duration,
                "total_suites": total_suites,
                "completed_suites": completed_suites,
                "failed_suites": failed_suites,
                "critical_failures": critical_failures,
                "success_rate": success_rate,
            },
            "test_suite_results": {
                name: {
                    "status": result.status.value,
                    "duration": result.duration,
                    "exit_code": result.exit_code,
                    "report_file": result.report_file,
                    "error_message": result.error_message,
                }
                for name, result in self.suite_results.items()
            },
            "critical_assessment": {
                "mcp_rag_pathway": (
                    "RESOLVED"
                    if mcp_result and mcp_result.status == TestSuiteStatus.COMPLETED
                    else "FAILED"
                ),
                "sla_compliance": (
                    "MET"
                    if sla_result and sla_result.status == TestSuiteStatus.COMPLETED
                    else "FAILED"
                ),
                "service_communication": (
                    "FUNCTIONAL"
                    if comm_result and comm_result.status == TestSuiteStatus.COMPLETED
                    else "FAILED"
                ),
            },
            "configuration": {
                "strict_sla": self.strict_sla,
                "load_test": self.load_test,
                "parallel": self.parallel,
                "verbose": self.verbose,
            },
        }

        # Save unified report
        report_filename = f"integration_test_report_{self.test_session_id}.json"
        with open(report_filename, "w") as f:
            json.dump(unified_report, f, indent=2, default=str)

        print(f"\n📄 Unified test report saved to: {report_filename}")

        return unified_report


async def main():
    """Main test orchestration function"""
    parser = argparse.ArgumentParser(
        description="Comprehensive MCP Document Indexing Integration Test Suite"
    )

    # Test execution options
    parser.add_argument(
        "--suite",
        choices=[
            "health_check",
            "mcp_integration",
            "service_communication",
            "sla_performance",
            "vector_indexing",
            "entity_extraction",
            "edge_cases",
        ],
        help="Run specific test suite only",
    )
    parser.add_argument("--suites", nargs="+", help="Run multiple specific test suites")
    parser.add_argument(
        "--health-check-only", action="store_true", help="Run health check only"
    )

    # Test configuration options
    parser.add_argument(
        "--strict-sla", action="store_true", help="Enable strict SLA enforcement"
    )
    parser.add_argument(
        "--load-test", action="store_true", help="Run load testing scenarios"
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run test suites in parallel where possible",
    )
    parser.add_argument(
        "--continuous", type=int, default=0, help="Run continuous testing for N minutes"
    )

    # Output options
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "--ci-cd-report", action="store_true", help="Generate CI/CD compatible report"
    )

    args = parser.parse_args()

    # Determine which suites to run
    selected_suites = None
    if args.suite:
        selected_suites = [args.suite]
    elif args.suites:
        selected_suites = args.suites

    orchestrator = IntegrationTestOrchestrator(
        strict_sla=args.strict_sla,
        load_test=args.load_test,
        verbose=args.verbose,
        parallel=args.parallel,
    )

    try:
        report = await orchestrator.run_comprehensive_tests(
            selected_suites=selected_suites,
            continuous_minutes=args.continuous,
            health_check_only=args.health_check_only,
        )

        # Generate CI/CD report if requested
        if args.ci_cd_report:
            ci_cd_report = {
                "test_status": (
                    "PASS"
                    if report["execution_summary"]["critical_failures"] == 0
                    else "FAIL"
                ),
                "success_rate": report["execution_summary"]["success_rate"],
                "critical_assessment": report["critical_assessment"],
                "execution_time": report["execution_summary"]["total_duration"],
                "timestamp": report["timestamp"],
            }

            with open(f"ci_cd_report_{orchestrator.test_session_id}.json", "w") as f:
                json.dump(ci_cd_report, f, indent=2)

        # Exit with appropriate code
        critical_failures = report["execution_summary"]["critical_failures"]
        exit(1 if critical_failures > 0 else 0)

    except KeyboardInterrupt:
        print("\n⏹️  Integration tests interrupted by user")
        exit(130)
    except Exception as e:
        print(f"\n💥 Integration test orchestration failed: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
