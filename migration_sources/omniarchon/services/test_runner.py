#!/usr/bin/env python3
"""
Comprehensive test runner for Archon services.

This script runs all unit and integration tests for the bridge, intelligence,
and search services, providing detailed reporting and debugging capabilities.

Usage:
    python test_runner.py [options]

Options:
    --unit-only         Run only unit tests
    --integration-only  Run only integration tests
    --service SERVICE   Run tests for specific service (bridge, intelligence, search)
    --coverage          Generate coverage reports
    --verbose          Enable verbose output
    --debug            Enable debug mode with detailed logging
    --parallel         Run tests in parallel (faster but less detailed output)
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict


class ArchonTestRunner:
    """Comprehensive test runner for Archon services."""

    def __init__(self, args):
        self.args = args
        self.services = ["bridge", "intelligence", "search"]
        self.base_dir = Path(__file__).parent
        self.results = {}
        self.start_time = time.time()

    def run(self):
        """Run all selected tests."""
        print("🧪 Archon Services Test Suite")
        print("=" * 50)

        # Validate services are available
        if self.args.service and self.args.service not in self.services:
            print(f"❌ Invalid service: {self.args.service}")
            print(f"Available services: {', '.join(self.services)}")
            return 1

        services_to_test = [self.args.service] if self.args.service else self.services

        # Run tests for each service
        overall_success = True
        for service in services_to_test:
            print(f"\n🔧 Testing {service.title()} Service")
            print("-" * 30)

            service_success = self._run_service_tests(service)
            overall_success &= service_success

            if service_success:
                print(f"✅ {service.title()} service tests passed")
            else:
                print(f"❌ {service.title()} service tests failed")

        # Print summary
        self._print_summary()

        return 0 if overall_success else 1

    def _run_service_tests(self, service: str) -> bool:
        """Run tests for a specific service."""
        service_dir = self.base_dir / service
        test_results = {"unit": None, "integration": None}

        # Check if service directory exists
        if not service_dir.exists():
            print(f"⚠️  Service directory not found: {service_dir}")
            return False

        # Run unit tests
        if not self.args.integration_only:
            print(f"🔬 Running unit tests for {service}...")
            unit_result = self._run_pytest(
                service_dir / "tests" / "unit", f"{service}_unit", markers=None
            )
            test_results["unit"] = unit_result

        # Run integration tests
        if not self.args.unit_only:
            print(f"🔗 Running integration tests for {service}...")
            integration_result = self._run_pytest(
                service_dir / "tests" / "integration",
                f"{service}_integration",
                markers="integration",
            )
            test_results["integration"] = integration_result

        # Store results
        self.results[service] = test_results

        # Determine overall success for this service
        success = True
        if test_results["unit"] and not test_results["unit"]["success"]:
            success = False
        if test_results["integration"] and not test_results["integration"]["success"]:
            success = False

        return success

    def _run_pytest(
        self, test_dir: Path, test_name: str, markers: str = None
    ) -> Dict[str, Any]:
        """Run pytest on a specific directory."""
        if not test_dir.exists():
            print(f"⚠️  Test directory not found: {test_dir}")
            return {"success": False, "reason": "directory_not_found"}

        # Check if there are any test files
        test_files = list(test_dir.glob("test_*.py"))
        if not test_files:
            print(f"⚠️  No test files found in: {test_dir}")
            return {"success": False, "reason": "no_test_files"}

        # Build pytest command
        cmd = ["python", "-m", "pytest"]

        # Add test directory
        cmd.append(str(test_dir))

        # Add markers if specified
        if markers:
            cmd.extend(["-m", markers])

        # Add verbosity
        if self.args.verbose or self.args.debug:
            cmd.append("-v")

        # Add coverage if requested
        if self.args.coverage:
            cmd.extend(
                [
                    "--cov=" + str(test_dir.parent.parent),
                    "--cov-report=term-missing",
                    "--cov-report=html:" + str(test_dir.parent.parent / "htmlcov"),
                ]
            )

        # Add parallel execution if requested
        if self.args.parallel:
            cmd.extend(["-n", "auto"])

        # Add JSON report for processing
        report_file = test_dir / f"report_{test_name}.json"
        cmd.extend(["--json-report", "--json-report-file=" + str(report_file)])

        # Run the command
        print(f"   Running: {' '.join(cmd[-3:])}")

        try:
            result = subprocess.run(
                cmd,
                cwd=test_dir.parent.parent,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            # Parse results
            success = result.returncode == 0

            # Try to read JSON report
            test_data = {}
            if report_file.exists():
                try:
                    with open(report_file, "r") as f:
                        test_data = json.load(f)
                except Exception as e:
                    print(f"⚠️  Could not parse test report: {e}")

            # Print basic output
            if success:
                test_count = test_data.get("summary", {}).get("total", 0)
                duration = test_data.get("duration", 0)
                print(f"   ✅ {test_count} tests passed in {duration:.2f}s")
            else:
                print(f"   ❌ Tests failed (exit code: {result.returncode})")
                if self.args.debug:
                    print("STDOUT:", result.stdout)
                    print("STDERR:", result.stderr)

            return {
                "success": success,
                "exit_code": result.returncode,
                "test_data": test_data,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

        except subprocess.TimeoutExpired:
            print("   ⏰ Tests timed out after 5 minutes")
            return {"success": False, "reason": "timeout"}

        except Exception as e:
            print(f"   ❌ Error running tests: {e}")
            return {"success": False, "reason": str(e)}

    def _print_summary(self):
        """Print test execution summary."""
        duration = time.time() - self.start_time

        print("\n" + "=" * 50)
        print("📊 Test Summary")
        print("=" * 50)

        total_tests = 0
        total_passed = 0
        total_failed = 0

        for service, results in self.results.items():
            print(f"\n{service.title()} Service:")

            for test_type, result in results.items():
                if result is None:
                    continue

                status = "✅ PASS" if result["success"] else "❌ FAIL"
                test_count = 0
                passed = 0
                failed = 0

                if "test_data" in result and result["test_data"]:
                    summary = result["test_data"].get("summary", {})
                    test_count = summary.get("total", 0)
                    passed = summary.get("passed", 0)
                    failed = summary.get("failed", 0)

                print(f"  {test_type.title()}: {status} ({passed}/{test_count} passed)")

                total_tests += test_count
                total_passed += passed
                total_failed += failed

        print("\nOverall Results:")
        print(f"  Total Tests: {total_tests}")
        print(f"  Passed: {total_passed}")
        print(f"  Failed: {total_failed}")
        print(f"  Duration: {duration:.2f}s")

        if total_failed == 0:
            print("\n🎉 All tests passed!")
        else:
            print(f"\n💥 {total_failed} tests failed")

        # Coverage summary
        if self.args.coverage:
            print("\n📈 Coverage reports generated in htmlcov/ directories")

    def _check_dependencies(self) -> bool:
        """Check if required dependencies are available."""
        required_packages = ["pytest", "pytest-asyncio", "httpx"]

        if self.args.coverage:
            required_packages.extend(["pytest-cov"])

        if self.args.parallel:
            required_packages.extend(["pytest-xdist"])

        missing = []
        for package in required_packages:
            try:
                __import__(package.replace("-", "_"))
            except ImportError:
                missing.append(package)

        if missing:
            print(f"❌ Missing required packages: {', '.join(missing)}")
            print(f"Install with: pip install {' '.join(missing)}")
            return False

        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Archon Services Test Runner")

    parser.add_argument("--unit-only", action="store_true", help="Run only unit tests")
    parser.add_argument(
        "--integration-only", action="store_true", help="Run only integration tests"
    )
    parser.add_argument(
        "--service",
        choices=["bridge", "intelligence", "search"],
        help="Run tests for specific service only",
    )
    parser.add_argument(
        "--coverage", action="store_true", help="Generate coverage reports"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug mode with detailed logging"
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run tests in parallel (requires pytest-xdist)",
    )

    args = parser.parse_args()

    # Validate arguments
    if args.unit_only and args.integration_only:
        print("❌ Cannot specify both --unit-only and --integration-only")
        return 1

    # Create and run test suite
    runner = ArchonTestRunner(args)

    # Check dependencies
    if not runner._check_dependencies():
        return 1

    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
