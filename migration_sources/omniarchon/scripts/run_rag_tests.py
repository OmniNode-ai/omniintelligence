#!/usr/bin/env python3
"""
RAG Integration Test Runner

Safe test runner for RAG pipeline integration tests with built-in safety checks.
This script ensures proper test environment setup before running integration tests.

Usage:
    python run_rag_tests.py                    # Run all RAG integration tests
    python run_rag_tests.py --safety-only      # Run only safety/guard tests
    python run_rag_tests.py --performance      # Run performance benchmarks
    python run_rag_tests.py --cleanup          # Run test data cleanup only
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


class RAGTestRunner:
    """Safe test runner for RAG integration tests"""

    def __init__(self):
        self.project_root = Path(__file__).parent
        self.test_dir = self.project_root / "python" / "tests"

    def check_prerequisites(self) -> bool:
        """Check that prerequisites are met for running tests"""
        print("🔍 Checking test prerequisites...")

        # Check if we're in test environment
        if os.getenv("TESTING") != "true":
            print("❌ TESTING environment variable not set to 'true'")
            print("   Set TESTING=true before running integration tests")
            return False

        # Check if test database is available
        test_db_available = self.check_test_database()
        if not test_db_available:
            print("❌ Test Supabase not available")
            print("   Please start the test Supabase first:")
            print("   python test_db_manager.py start")
            return False

        # Check for required files
        required_files = [
            self.test_dir / "test_rag_integration.py",
            self.test_dir / "test_config_rag.py",
        ]

        for file_path in required_files:
            if not file_path.exists():
                print(f"❌ Required test file not found: {file_path}")
                return False

        # Check if poetry and pytest are available
        try:
            result = subprocess.run(
                ["poetry", "run", "pytest", "--version"],
                capture_output=True,
                text=True,
                cwd=self.project_root / "python",
            )
            if result.returncode != 0:
                print("❌ pytest not available in poetry environment")
                print("   Run 'poetry install' in the python/ directory")
                return False
        except Exception as e:
            print(f"❌ Error checking poetry/pytest: {e}")
            print(
                "   Make sure poetry is installed and run 'poetry install' in python/ directory"
            )
            return False

        print("✅ Prerequisites check passed")
        return True

    def check_test_database(self) -> bool:
        """Check if test Supabase is available and accessible"""
        try:
            import urllib.request

            # Check if Supabase API is accessible (401 is expected without auth)
            try:
                with urllib.request.urlopen(
                    "http://localhost:54321/rest/v1/", timeout=5
                ) as response:
                    if response.status == 200:
                        print("✅ Test Supabase is accessible on port 54321")
                        return True
                    else:
                        print(f"❌ Test Supabase returned status {response.status}")
                        return False
            except urllib.request.HTTPError as http_err:
                if http_err.code == 401:  # Unauthorized is expected - API is working
                    print("✅ Test Supabase is accessible on port 54321")
                    return True
                else:
                    print(f"❌ Test Supabase returned HTTP {http_err.code}")
                    return False

        except Exception as e:
            print(f"❌ Error checking test Supabase: {e}")
            print("   Make sure to start it with: python test_db_manager.py start")
            return False

    def run_safety_tests(self) -> bool:
        """Run safety and guard tests only"""
        print("\n🛡️ Running safety and guard tests...")

        cmd = [
            "poetry",
            "run",
            "pytest",
            "tests/test_rag_integration.py::TestRAGPipelineIntegration::test_production_safety_guards",
            "tests/test_rag_integration.py::TestRAGPipelineIntegration::test_data_cleanup_verification",
            "-v",
            "--tb=short",
        ]

        return self._run_pytest(cmd)

    def run_integration_tests(self) -> bool:
        """Run full integration tests"""
        print("\n🔬 Running RAG integration tests...")

        cmd = [
            "poetry",
            "run",
            "pytest",
            "tests/test_rag_integration.py",
            "-v",
            "--tb=short",
            "-k",
            "not performance",  # Exclude performance tests by default
        ]

        return self._run_pytest(cmd)

    def run_performance_tests(self) -> bool:
        """Run performance benchmark tests"""
        print("\n⚡ Running performance benchmark tests...")

        cmd = [
            "poetry",
            "run",
            "pytest",
            "tests/test_rag_integration.py::TestRAGPipelineIntegration::test_performance_benchmarks",
            "-v",
            "--tb=short",
            "-s",  # -s to see performance output
        ]

        return self._run_pytest(cmd)

    def run_cleanup(self) -> bool:
        """Run test data cleanup"""
        print("\n🧹 Running test data cleanup...")

        try:
            # Import and run cleanup directly
            sys.path.insert(0, str(self.project_root / "python" / "src"))
            os.chdir(self.project_root / "python")

            # Use poetry to run cleanup
            result = subprocess.run(
                [
                    "poetry",
                    "run",
                    "python",
                    "-c",
                    """
import os
os.environ['TESTING'] = 'true'
from tests.test_rag_integration import emergency_cleanup
import asyncio
asyncio.run(emergency_cleanup())
                """,
                ],
                cwd=self.project_root / "python",
            )
            return result.returncode == 0
        except Exception as e:
            print(f"❌ Cleanup failed: {e}")
            return False

    def _run_pytest(self, cmd: list) -> bool:
        """Run pytest command and return success status"""
        try:
            # Temporarily rename conftest.py to avoid database mocking
            conftest_path = self.test_dir / "conftest.py"
            conftest_backup = self.test_dir / "conftest_backup.py"
            integration_conftest = self.test_dir / "conftest_integration.py"

            # Backup original conftest and replace with integration version
            if conftest_path.exists():
                conftest_path.rename(conftest_backup)

            if integration_conftest.exists():
                integration_conftest.rename(conftest_path)

            try:
                result = subprocess.run(
                    cmd,
                    cwd=self.project_root / "python",
                    env={
                        **os.environ,
                        "TESTING": "true",
                        "REAL_INTEGRATION_TESTS": "true",
                    },
                )
                return result.returncode == 0
            finally:
                # Restore original conftest
                if conftest_path.exists():
                    conftest_path.rename(integration_conftest)

                if conftest_backup.exists():
                    conftest_backup.rename(conftest_path)

        except Exception as e:
            print(f"❌ Test execution failed: {e}")
            return False


def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(description="RAG Integration Test Runner")
    parser.add_argument(
        "--safety-only", action="store_true", help="Run only safety and guard tests"
    )
    parser.add_argument(
        "--performance", action="store_true", help="Run performance benchmark tests"
    )
    parser.add_argument(
        "--cleanup", action="store_true", help="Run test data cleanup only"
    )
    parser.add_argument(
        "--all", action="store_true", help="Run all tests including performance"
    )

    args = parser.parse_args()

    runner = RAGTestRunner()

    # Check prerequisites first
    if not runner.check_prerequisites():
        print(
            "\n❌ Prerequisites check failed. Please fix issues before running tests."
        )
        sys.exit(1)

    success = True

    # Run requested tests
    if args.cleanup:
        success = runner.run_cleanup()
    elif args.safety_only:
        success = runner.run_safety_tests()
    elif args.performance:
        success = runner.run_performance_tests()
    elif args.all:
        print("\n🚀 Running comprehensive RAG test suite...")
        success &= runner.run_safety_tests()
        success &= runner.run_integration_tests()
        success &= runner.run_performance_tests()
    else:
        # Default: run integration tests
        success = runner.run_integration_tests()

    # Report results
    if success:
        print("\n✅ All RAG tests completed successfully!")
        print("\nNext steps:")
        print("  - Review test output above")
        print("  - Check that all test data was cleaned up")
        print("  - Run 'python run_rag_tests.py --cleanup' if needed")
    else:
        print("\n❌ Some RAG tests failed!")
        print("\nTroubleshooting:")
        print("  - Check test environment configuration")
        print("  - Verify database connectivity")
        print("  - Review error messages above")
        print("  - Run 'python run_rag_tests.py --safety-only' first")
        sys.exit(1)


if __name__ == "__main__":
    main()
