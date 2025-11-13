#!/usr/bin/env python3
"""
Performance Report Generator

Generates comprehensive performance reports from load test and monitoring results:
- Aggregates multiple test results
- Compares before/after optimization runs
- Generates markdown reports
- Performance trend analysis

Part of MVP Phase 4 - Load Testing Infrastructure

Author: Archon Intelligence Team
Date: 2025-10-15
"""

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# ============================================================================
# Report Models
# ============================================================================


@dataclass
class TestResult:
    """Single test result summary."""

    test_name: str
    test_type: str  # "concurrent" or "sustained"
    event_type: str
    timestamp: str
    duration_seconds: float

    # Performance metrics
    total_requests: int
    successful_requests: int
    success_rate: float
    throughput_rps: float

    # Latency metrics
    latency_p50: float
    latency_p95: float
    latency_p99: float
    latency_mean: float

    # Resource usage (if available)
    cpu_mean: Optional[float] = None
    memory_mean_mb: Optional[float] = None

    @classmethod
    def from_load_test_file(
        cls, file_path: Path, test_name: str = None
    ) -> "TestResult":
        """
        Load test result from JSON file.

        Args:
            file_path: Path to load test result JSON
            test_name: Optional test name (default: filename)

        Returns:
            TestResult instance
        """
        with open(file_path) as f:
            data = json.load(f)

        return cls(
            test_name=test_name or file_path.stem,
            test_type=data.get("test_mode", "unknown"),
            event_type=data.get("event_type", "unknown"),
            timestamp=data.get("start_time", ""),
            duration_seconds=data.get("duration_seconds", 0.0),
            total_requests=data.get("total_requests", 0),
            successful_requests=data.get("successful_requests", 0),
            success_rate=data.get("success_rate", 0.0),
            throughput_rps=data.get("requests_per_second", 0.0),
            latency_p50=data.get("latency_p50", 0.0),
            latency_p95=data.get("latency_p95", 0.0),
            latency_p99=data.get("latency_p99", 0.0),
            latency_mean=data.get("latency_mean", 0.0),
        )

    @classmethod
    def from_monitoring_file(cls, file_path: Path) -> Optional[Dict[str, float]]:
        """
        Load resource metrics from monitoring JSON file.

        Args:
            file_path: Path to monitoring result JSON

        Returns:
            Dictionary with resource metrics or None
        """
        try:
            with open(file_path) as f:
                data = json.load(f)

            summary = data.get("summary", {})
            system_cpu = summary.get("system_cpu", {})
            system_memory = summary.get("system_memory", {})

            return {
                "cpu_mean": system_cpu.get("mean_percent", 0.0),
                "memory_mean_mb": system_memory.get("mean_mb", 0.0),
            }
        except Exception as e:
            print(f"⚠️  Could not load monitoring data: {e}")
            return None


@dataclass
class ComparisonReport:
    """Before/after comparison report."""

    baseline: TestResult
    optimized: TestResult

    @property
    def throughput_improvement(self) -> float:
        """Calculate throughput improvement percentage."""
        if self.baseline.throughput_rps == 0:
            return 0.0
        return (
            (self.optimized.throughput_rps - self.baseline.throughput_rps)
            / self.baseline.throughput_rps
        ) * 100.0

    @property
    def latency_p99_improvement(self) -> float:
        """Calculate p99 latency improvement percentage (negative = better)."""
        if self.baseline.latency_p99 == 0:
            return 0.0
        return (
            (self.optimized.latency_p99 - self.baseline.latency_p99)
            / self.baseline.latency_p99
        ) * 100.0

    @property
    def success_rate_change(self) -> float:
        """Calculate success rate change (percentage points)."""
        return (self.optimized.success_rate - self.baseline.success_rate) * 100.0


# ============================================================================
# Performance Reporter
# ============================================================================


class PerformanceReporter:
    """
    Generate comprehensive performance reports.

    Aggregates multiple test results and generates markdown reports.
    """

    def __init__(self):
        """Initialize performance reporter."""
        self.test_results: List[TestResult] = []

    def add_test_result(
        self, load_test_file: Path, monitoring_file: Optional[Path] = None
    ) -> None:
        """
        Add test result from files.

        Args:
            load_test_file: Path to load test JSON
            monitoring_file: Optional path to monitoring JSON
        """
        result = TestResult.from_load_test_file(load_test_file)

        # Add resource metrics if available
        if monitoring_file and monitoring_file.exists():
            metrics = TestResult.from_monitoring_file(monitoring_file)
            if metrics:
                result.cpu_mean = metrics.get("cpu_mean")
                result.memory_mean_mb = metrics.get("memory_mean_mb")

        self.test_results.append(result)
        print(f"✅ Added test result: {result.test_name}")

    def generate_markdown_report(
        self,
        output_file: Path,
        title: str = "Performance Test Report",
        include_comparison: bool = False,
    ) -> None:
        """
        Generate markdown report.

        Args:
            output_file: Output markdown file path
            title: Report title
            include_comparison: Whether to include before/after comparison
        """
        if not self.test_results:
            print("⚠️  No test results to report")
            return

        lines = []

        # Header
        lines.append(f"# {title}\n")
        lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"**Total Tests**: {len(self.test_results)}\n")
        lines.append("\n---\n")

        # Test Results Summary Table
        lines.append("## Test Results Summary\n")
        lines.append(
            "| Test | Type | Events | Duration | Total Req | Success Rate | "
            "Throughput | p50 | p95 | p99 |\n"
        )
        lines.append(
            "|------|------|--------|----------|-----------|--------------|"
            "------------|-----|-----|-----|\n"
        )

        for result in self.test_results:
            lines.append(
                f"| {result.test_name} "
                f"| {result.test_type} "
                f"| {result.event_type} "
                f"| {result.duration_seconds:.0f}s "
                f"| {result.total_requests} "
                f"| {result.success_rate:.1%} "
                f"| {result.throughput_rps:.1f} req/s "
                f"| {result.latency_p50:.1f}ms "
                f"| {result.latency_p95:.1f}ms "
                f"| {result.latency_p99:.1f}ms |\n"
            )

        lines.append("\n---\n")

        # Detailed Results
        lines.append("## Detailed Results\n")

        for result in self.test_results:
            lines.append(f"### {result.test_name}\n")
            lines.append(f"**Type**: {result.test_type}  \n")
            lines.append(f"**Event Type**: {result.event_type}  \n")
            lines.append(f"**Timestamp**: {result.timestamp}  \n")
            lines.append(f"**Duration**: {result.duration_seconds:.1f}s  \n")
            lines.append("\n")

            lines.append("#### Performance Metrics\n")
            lines.append(f"- **Total Requests**: {result.total_requests}\n")
            lines.append(f"- **Successful**: {result.successful_requests}\n")
            lines.append(f"- **Success Rate**: {result.success_rate:.2%}\n")
            lines.append(f"- **Throughput**: {result.throughput_rps:.2f} req/s\n")
            lines.append("\n")

            lines.append("#### Latency Distribution\n")
            lines.append(f"- **p50 (median)**: {result.latency_p50:.2f}ms\n")
            lines.append(f"- **p95**: {result.latency_p95:.2f}ms\n")
            lines.append(f"- **p99**: {result.latency_p99:.2f}ms\n")
            lines.append(f"- **Mean**: {result.latency_mean:.2f}ms\n")
            lines.append("\n")

            if result.cpu_mean is not None:
                lines.append("#### Resource Usage\n")
                lines.append(f"- **CPU (mean)**: {result.cpu_mean:.1f}%\n")
                lines.append(f"- **Memory (mean)**: {result.memory_mean_mb:.1f}MB\n")
                lines.append("\n")

            # Compliance Check
            lines.append("#### Compliance\n")
            success_pass = result.success_rate >= 0.95
            latency_pass = result.latency_p99 < 1000.0
            lines.append(
                f"- **Success Rate ≥ 95%**: {'✅ PASS' if success_pass else '❌ FAIL'}\n"
            )
            lines.append(
                f"- **p99 Latency < 1000ms**: {'✅ PASS' if latency_pass else '❌ FAIL'}\n"
            )
            lines.append("\n")

            lines.append("---\n\n")

        # Comparison (if 2 results and comparison enabled)
        if include_comparison and len(self.test_results) == 2:
            lines.append("## Before/After Comparison\n")
            comparison = ComparisonReport(
                baseline=self.test_results[0], optimized=self.test_results[1]
            )

            lines.append(f"**Baseline**: {comparison.baseline.test_name}  \n")
            lines.append(f"**Optimized**: {comparison.optimized.test_name}  \n")
            lines.append("\n")

            lines.append("### Improvements\n")
            lines.append(
                f"- **Throughput**: {comparison.throughput_improvement:+.1f}%\n"
            )
            lines.append(
                f"- **p99 Latency**: {comparison.latency_p99_improvement:+.1f}% "
                f"({'✅ improved' if comparison.latency_p99_improvement < 0 else '⚠️ degraded'})\n"
            )
            lines.append(
                f"- **Success Rate**: {comparison.success_rate_change:+.1f} percentage points\n"
            )
            lines.append("\n")

            lines.append("### Metrics Comparison\n")
            lines.append("| Metric | Baseline | Optimized | Change |\n")
            lines.append("|--------|----------|-----------|--------|\n")
            lines.append(
                f"| Throughput (req/s) | {comparison.baseline.throughput_rps:.1f} "
                f"| {comparison.optimized.throughput_rps:.1f} "
                f"| {comparison.throughput_improvement:+.1f}% |\n"
            )
            lines.append(
                f"| p99 Latency (ms) | {comparison.baseline.latency_p99:.1f} "
                f"| {comparison.optimized.latency_p99:.1f} "
                f"| {comparison.latency_p99_improvement:+.1f}% |\n"
            )
            lines.append(
                f"| Success Rate | {comparison.baseline.success_rate:.2%} "
                f"| {comparison.optimized.success_rate:.2%} "
                f"| {comparison.success_rate_change:+.1f}pp |\n"
            )
            lines.append("\n")

        # Write to file
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            f.writelines(lines)

        print(f"\n📄 Report generated: {output_file}")

    def print_summary(self) -> None:
        """Print test results summary to console."""
        if not self.test_results:
            print("⚠️  No test results to display")
            return

        print("\n" + "=" * 80)
        print("📊 PERFORMANCE TEST SUMMARY")
        print("=" * 80)

        for i, result in enumerate(self.test_results, 1):
            print(f"\n{i}. {result.test_name}")
            print(f"   Type: {result.test_type} | Event: {result.event_type}")
            print(
                f"   Requests: {result.total_requests} | "
                f"Success: {result.success_rate:.1%} | "
                f"Throughput: {result.throughput_rps:.1f} req/s"
            )
            print(
                f"   Latency: p50={result.latency_p50:.1f}ms "
                f"p95={result.latency_p95:.1f}ms "
                f"p99={result.latency_p99:.1f}ms"
            )

            # Compliance
            success_pass = result.success_rate >= 0.95
            latency_pass = result.latency_p99 < 1000.0
            status = "✅" if (success_pass and latency_pass) else "⚠️"
            print(f"   Compliance: {status}")

        print("\n" + "=" * 80)


# ============================================================================
# CLI
# ============================================================================


def main():
    """Main entry point for performance reporter CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Performance Report Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate report from single test
  python performance_report.py --test load_test_results.json --output report.md

  # Generate report from multiple tests
  python performance_report.py \\
    --test baseline.json \\
    --test optimized.json \\
    --output comparison_report.md \\
    --compare

  # Include monitoring metrics
  python performance_report.py \\
    --test load_test.json \\
    --monitoring metrics.json \\
    --output report.md

  # Generate from all JSON files in directory
  python performance_report.py --directory ./results --output summary.md
        """,
    )

    parser.add_argument(
        "--test",
        action="append",
        help="Load test result JSON file (can be specified multiple times)",
    )
    parser.add_argument("--monitoring", help="Monitoring metrics JSON file")
    parser.add_argument(
        "--directory", help="Directory containing test result JSON files"
    )
    parser.add_argument(
        "--output",
        default="performance_report.md",
        help="Output markdown file (default: performance_report.md)",
    )
    parser.add_argument(
        "--title", default="Performance Test Report", help="Report title"
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Include before/after comparison (requires 2 tests)",
    )
    parser.add_argument(
        "--print-only", action="store_true", help="Print summary only, don't save"
    )

    args = parser.parse_args()

    # Create reporter
    reporter = PerformanceReporter()

    # Load test results
    if args.directory:
        # Load all JSON files from directory
        directory = Path(args.directory)
        json_files = sorted(directory.glob("*.json"))

        for json_file in json_files:
            try:
                reporter.add_test_result(json_file)
            except Exception as e:
                print(f"⚠️  Could not load {json_file}: {e}")

    elif args.test:
        # Load specified test files
        for test_file in args.test:
            test_path = Path(test_file)
            if not test_path.exists():
                print(f"❌ Test file not found: {test_file}")
                continue

            monitoring_path = Path(args.monitoring) if args.monitoring else None
            reporter.add_test_result(test_path, monitoring_path)

    else:
        print("❌ Must specify --test or --directory")
        parser.print_help()
        return 1

    # Generate output
    if args.print_only:
        reporter.print_summary()
    else:
        output_path = Path(args.output)
        reporter.generate_markdown_report(
            output_path, title=args.title, include_comparison=args.compare
        )
        reporter.print_summary()

    return 0


if __name__ == "__main__":
    sys.exit(main())
