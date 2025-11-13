#!/usr/bin/env python3
"""
Comprehensive test runner for Archon intelligence testing system.

This script replaces the old shell script approach with a structured
pytest-based testing system that provides better reporting, coverage,
and maintainability.
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


class IntelligenceTestRunner:
    """Test runner for intelligence system tests."""

    def __init__(self, verbose: bool = False, coverage: bool = True):
        """
        Initialize test runner.

        Args:
            verbose: Enable verbose output
            coverage: Enable coverage reporting
        """
        self.verbose = verbose
        self.coverage = coverage
        self.project_root = Path(__file__).parent
        self.test_results = {}

    def run_unit_tests(self, filter_pattern: Optional[str] = None) -> bool:
        """
        Run unit tests for intelligence data access layer.

        Args:
            filter_pattern: Optional pattern to filter tests

        Returns:
            True if all tests passed, False otherwise
        """
        print("🧪 Running Unit Tests")
        print("=" * 50)

        cmd = ["python", "-m", "pytest", "tests/unit/", "-m", "unit"]

        if filter_pattern:
            cmd.extend(["-k", filter_pattern])

        if self.verbose:
            cmd.append("-v")
        else:
            cmd.append("-q")

        if self.coverage:
            cmd.extend(
                [
                    "--cov=src/server/data/intelligence_data_access",
                    "--cov=src/server/services/intelligence_service",
                    "--cov=src/server/api_routes/intelligence_api",
                    "--cov-report=term-missing",
                    "--cov-report=html:htmlcov/unit",
                ]
            )

        return self._run_command(cmd, "unit_tests")

    def run_integration_tests(self, filter_pattern: Optional[str] = None) -> bool:
        """
        Run integration tests for API endpoints.

        Args:
            filter_pattern: Optional pattern to filter tests

        Returns:
            True if all tests passed, False otherwise
        """
        print("\n🔗 Running Integration Tests")
        print("=" * 50)

        cmd = ["python", "-m", "pytest", "tests/integration/", "-m", "integration"]

        if filter_pattern:
            cmd.extend(["-k", filter_pattern])

        if self.verbose:
            cmd.append("-v")
        else:
            cmd.append("-q")

        if self.coverage:
            cmd.extend(
                [
                    "--cov=src/server/api_routes/intelligence_api",
                    "--cov-report=term-missing",
                    "--cov-report=html:htmlcov/integration",
                    "--cov-append",
                ]
            )

        return self._run_command(cmd, "integration_tests")

    def run_performance_tests(
        self, filter_pattern: Optional[str] = None, include_slow: bool = False
    ) -> bool:
        """
        Run performance tests for correlation generation.

        Args:
            filter_pattern: Optional pattern to filter tests
            include_slow: Include slow-running performance tests

        Returns:
            True if all tests passed, False otherwise
        """
        print("\n⚡ Running Performance Tests")
        print("=" * 50)

        cmd = ["python", "-m", "pytest", "tests/performance/", "-m", "performance"]

        if not include_slow:
            cmd.extend(["-m", "not slow"])

        if filter_pattern:
            cmd.extend(["-k", filter_pattern])

        if self.verbose:
            cmd.append("-v")
        else:
            cmd.append("-q")

        # Add timeout for performance tests
        cmd.extend(["--timeout=300"])  # 5 minute timeout

        return self._run_command(cmd, "performance_tests")

    def run_data_validation_tests(self) -> bool:
        """
        Run comprehensive data validation tests.

        These tests validate the same functionality that was previously
        tested via the validation script.

        Returns:
            True if all tests passed, False otherwise
        """
        print("\n🔍 Running Data Validation Tests")
        print("=" * 50)

        cmd = [
            "python",
            "-m",
            "pytest",
            "tests/unit/test_intelligence_data_access_comprehensive.py::TestIntelligenceDataAccessValidation",
            "-m",
            "intelligence",
        ]

        if self.verbose:
            cmd.append("-v")
        else:
            cmd.append("-q")

        return self._run_command(cmd, "data_validation_tests")

    def run_correlation_algorithm_tests(self) -> bool:
        """
        Run correlation algorithm tests.

        Returns:
            True if all tests passed, False otherwise
        """
        print("\n🎯 Running Correlation Algorithm Tests")
        print("=" * 50)

        cmd = [
            "python",
            "-m",
            "pytest",
            "tests/unit/test_correlation_algorithms.py",
            "-m",
            "correlation",
        ]

        if self.verbose:
            cmd.append("-v")
        else:
            cmd.append("-q")

        return self._run_command(cmd, "correlation_algorithm_tests")

    def run_all_tests(self, include_slow: bool = False) -> bool:
        """
        Run complete test suite.

        Args:
            include_slow: Include slow-running tests

        Returns:
            True if all tests passed, False otherwise
        """
        print("🚀 Running Complete Intelligence Test Suite")
        print("=" * 70)

        test_suites = [
            ("Data Validation", lambda: self.run_data_validation_tests()),
            ("Unit Tests", lambda: self.run_unit_tests()),
            ("Correlation Algorithms", lambda: self.run_correlation_algorithm_tests()),
            ("Integration Tests", lambda: self.run_integration_tests()),
            (
                "Performance Tests",
                lambda: self.run_performance_tests(include_slow=include_slow),
            ),
        ]

        all_passed = True
        start_time = time.time()

        for suite_name, test_func in test_suites:
            suite_start = time.time()
            passed = test_func()
            suite_duration = time.time() - suite_start

            self.test_results[suite_name] = {
                "passed": passed,
                "duration": suite_duration,
            }

            if not passed:
                all_passed = False
                print(f"❌ {suite_name} failed")
            else:
                print(f"✅ {suite_name} passed ({suite_duration:.2f}s)")

        total_duration = time.time() - start_time

        print("\n" + "=" * 70)
        print("📊 Test Suite Summary")
        print("=" * 70)

        passed_count = sum(
            1 for result in self.test_results.values() if result["passed"]
        )
        total_count = len(self.test_results)

        print(f"Test Suites: {passed_count}/{total_count} passed")
        print(f"Total Duration: {total_duration:.2f}s")

        for suite_name, result in self.test_results.items():
            status = "✅ PASSED" if result["passed"] else "❌ FAILED"
            print(f"  {suite_name:<25} {status} ({result['duration']:.2f}s)")

        if all_passed:
            print(
                "\n🎉 All test suites passed! Intelligence system is working correctly."
            )
        else:
            print("\n⚠️  Some test suites failed. Please review the failures above.")

        return all_passed

    def run_quick_validation(self) -> bool:
        """
        Run quick validation tests (equivalent to the old validation script).

        Returns:
            True if validation passed, False otherwise
        """
        print("⚡ Running Quick Intelligence Validation")
        print("=" * 50)

        cmd = [
            "python",
            "-m",
            "pytest",
            "tests/unit/test_intelligence_data_access_comprehensive.py::TestIntelligenceDataAccessValidation::test_time_range_parsing_validation",
            "tests/unit/test_intelligence_data_access_comprehensive.py::TestIntelligenceDataAccessValidation::test_document_parsing_mcp_format",
            "tests/unit/test_intelligence_data_access_comprehensive.py::TestIntelligenceDataAccessValidation::test_document_parsing_legacy_format",
            "tests/unit/test_intelligence_data_access_comprehensive.py::TestIntelligenceDataAccessValidation::test_statistics_calculation_with_data",
            "-v",
        ]

        return self._run_command(cmd, "quick_validation")

    def _run_command(self, cmd: list[str], test_name: str) -> bool:
        """
        Run a command and capture results.

        Args:
            cmd: Command to run
            test_name: Name of the test for logging

        Returns:
            True if command succeeded, False otherwise
        """
        try:
            # Set environment for testing
            env = os.environ.copy()
            env.update(
                {
                    "PYTHONPATH": str(self.project_root / "src"),
                    "TEST_MODE": "true",
                    "TESTING": "true",
                }
            )

            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                env=env,
                capture_output=not self.verbose,
                text=True,
            )

            if result.returncode == 0:
                if not self.verbose and result.stdout:
                    # Show summary even in quiet mode
                    lines = result.stdout.strip().split("\n")
                    if lines:
                        summary_line = [
                            line
                            for line in lines
                            if "passed" in line or "failed" in line
                        ]
                        if summary_line:
                            print(f"  {summary_line[-1]}")
                return True
            else:
                print(f"❌ {test_name} failed with exit code {result.returncode}")
                if not self.verbose and result.stdout:
                    print("STDOUT:", result.stdout[-1000:])  # Last 1000 chars
                if result.stderr:
                    print("STDERR:", result.stderr[-1000:])  # Last 1000 chars
                return False

        except Exception as e:
            print(f"❌ Error running {test_name}: {e}")
            return False

    def generate_coverage_report(self) -> None:
        """Generate comprehensive coverage report."""
        if not self.coverage:
            return

        print("\n📊 Generating Coverage Report")
        print("=" * 50)

        try:
            # Generate combined coverage report
            subprocess.run(
                ["python", "-m", "coverage", "combine"],
                cwd=self.project_root,
                check=False,
            )

            subprocess.run(
                [
                    "python",
                    "-m",
                    "coverage",
                    "report",
                    "--include=src/server/data/intelligence*,src/server/services/intelligence*,src/server/api_routes/intelligence*",
                ],
                cwd=self.project_root,
                check=False,
            )

            subprocess.run(
                [
                    "python",
                    "-m",
                    "coverage",
                    "html",
                    "--include=src/server/data/intelligence*,src/server/services/intelligence*,src/server/api_routes/intelligence*",
                    "-d",
                    "htmlcov/combined",
                ],
                cwd=self.project_root,
                check=False,
            )

            print("📊 Coverage reports generated:")
            print("  - Terminal report shown above")
            print(f"  - HTML report: {self.project_root}/htmlcov/combined/index.html")

        except Exception as e:
            print(f"⚠️  Could not generate coverage report: {e}")


def main():
    """Main entry point for the test runner."""
    parser = argparse.ArgumentParser(
        description="Comprehensive test runner for Archon intelligence system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --all                    # Run all tests
  %(prog)s --quick                  # Quick validation (replaces old script)
  %(prog)s --unit                   # Run only unit tests
  %(prog)s --integration            # Run only integration tests
  %(prog)s --performance            # Run performance tests (excluding slow)
  %(prog)s --performance --slow     # Run all performance tests
  %(prog)s --data-validation        # Run data validation tests
  %(prog)s --correlation            # Run correlation algorithm tests
  %(prog)s --filter "test_parsing"  # Run tests matching pattern
  %(prog)s --all --no-coverage      # Run all tests without coverage
        """,
    )

    # Test suite selection
    parser.add_argument("--all", action="store_true", help="Run complete test suite")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick validation (equivalent to old validation script)",
    )
    parser.add_argument("--unit", action="store_true", help="Run unit tests")
    parser.add_argument(
        "--integration", action="store_true", help="Run integration tests"
    )
    parser.add_argument(
        "--performance", action="store_true", help="Run performance tests"
    )
    parser.add_argument(
        "--data-validation", action="store_true", help="Run data validation tests"
    )
    parser.add_argument(
        "--correlation", action="store_true", help="Run correlation algorithm tests"
    )

    # Test filtering and options
    parser.add_argument(
        "--filter", "-f", help="Filter tests by pattern (pytest -k option)"
    )
    parser.add_argument(
        "--slow", action="store_true", help="Include slow-running tests"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--no-coverage", action="store_true", help="Disable coverage reporting"
    )

    args = parser.parse_args()

    # Default to quick validation if no specific tests selected
    if not any(
        [
            args.all,
            args.quick,
            args.unit,
            args.integration,
            args.performance,
            args.data_validation,
            args.correlation,
        ]
    ):
        args.quick = True

    # Create test runner
    runner = IntelligenceTestRunner(verbose=args.verbose, coverage=not args.no_coverage)

    success = True

    try:
        if args.all:
            success = runner.run_all_tests(include_slow=args.slow)
        elif args.quick:
            success = runner.run_quick_validation()
        else:
            # Run individual test suites
            if args.data_validation:
                success = runner.run_data_validation_tests() and success
            if args.unit:
                success = runner.run_unit_tests(args.filter) and success
            if args.correlation:
                success = runner.run_correlation_algorithm_tests() and success
            if args.integration:
                success = runner.run_integration_tests(args.filter) and success
            if args.performance:
                success = (
                    runner.run_performance_tests(args.filter, args.slow) and success
                )

        # Generate coverage report if requested
        if not args.no_coverage and success:
            runner.generate_coverage_report()

    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Test runner crashed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
