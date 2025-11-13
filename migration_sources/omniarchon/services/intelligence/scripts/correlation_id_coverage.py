#!/usr/bin/env python3
"""
Correlation ID Coverage Tracking Script

Analyzes correlation_id propagation coverage across the intelligence service codebase.
Generates detailed reports by file type and priority level.

Usage:
    python scripts/correlation_id_coverage.py [--verbose] [--json]
"""

import argparse
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set


class CorrelationIDCoverageTracker:
    """Track and report on correlation_id coverage across the codebase."""

    def __init__(self, src_dir: str = "src"):
        self.src_dir = Path(src_dir)
        self.all_files: Set[str] = set()
        self.files_with_corr: Set[str] = set()
        self.missing_files: Set[str] = set()
        self.categories: Dict[str, List[str]] = defaultdict(list)

    def scan_files(self) -> None:
        """Scan all Python files in the source directory."""
        # Get all Python files
        result = subprocess.run(
            ["find", str(self.src_dir), "-name", "*.py"],
            capture_output=True,
            text=True,
        )
        self.all_files = set(
            line.strip() for line in result.stdout.strip().split("\n") if line
        )

        # Get files with correlation_id
        result = subprocess.run(
            ["grep", "-rl", "correlation_id", str(self.src_dir)],
            capture_output=True,
            text=True,
        )
        self.files_with_corr = set(
            line.strip()
            for line in result.stdout.strip().split("\n")
            if line and line.endswith(".py")
        )

        # Calculate missing files
        self.missing_files = self.all_files - self.files_with_corr

    def categorize_files(self) -> None:
        """Categorize files by type and priority."""
        priority_keywords = {
            "event_handlers": ["event", "handler"],
            "api_routes": ["route", "api", "endpoint"],
            "services": ["service"],
            "models": ["model", "schema"],
            "utils": ["util", "helper"],
            "config": ["config", "settings"],
            "middleware": ["middleware"],
            "background_tasks": ["task", "worker", "job"],
        }

        for file in self.missing_files:
            file_lower = file.lower()
            categorized = False

            for category, keywords in priority_keywords.items():
                if any(keyword in file_lower for keyword in keywords):
                    self.categories[category].append(file)
                    categorized = True
                    break

            if not categorized:
                self.categories["other"].append(file)

    def get_priority_level(self, category: str) -> int:
        """Get priority level for a category (1=highest, 5=lowest)."""
        priority_map = {
            "event_handlers": 1,
            "api_routes": 1,
            "background_tasks": 1,
            "services": 2,
            "middleware": 2,
            "config": 3,
            "models": 3,
            "utils": 4,
            "other": 5,
        }
        return priority_map.get(category, 5)

    def calculate_stats(self) -> Dict:
        """Calculate coverage statistics."""
        total = len(self.all_files)
        with_corr = len(self.files_with_corr)
        without_corr = len(self.missing_files)
        current_percent = (with_corr / total * 100) if total > 0 else 0

        # Target is 80% (200/251 files, but we have 253 files)
        target_count = int(total * 0.80)
        target_percent = 80.0
        needed = max(0, target_count - with_corr)

        return {
            "total_files": total,
            "files_with_correlation_id": with_corr,
            "files_without_correlation_id": without_corr,
            "current_coverage_percent": round(current_percent, 1),
            "target_count": target_count,
            "target_percent": target_percent,
            "files_needed_for_target": needed,
        }

    def generate_report(self, verbose: bool = False) -> str:
        """Generate human-readable coverage report."""
        stats = self.calculate_stats()

        report = []
        report.append("=" * 80)
        report.append("CORRELATION ID COVERAGE REPORT")
        report.append("=" * 80)
        report.append("")
        report.append("OVERALL STATISTICS:")
        report.append(f"  Total Python files: {stats['total_files']}")
        report.append(
            f"  Files with correlation_id: {stats['files_with_correlation_id']}"
        )
        report.append(
            f"  Files without correlation_id: {stats['files_without_correlation_id']}"
        )
        report.append(f"  Current coverage: {stats['current_coverage_percent']}%")
        report.append("")
        report.append(
            f"TARGET: {stats['target_count']}/{stats['total_files']} files ({stats['target_percent']}%)"
        )
        report.append(f"FILES NEEDED: {stats['files_needed_for_target']}")
        report.append("")

        # Breakdown by category (sorted by priority)
        report.append("BREAKDOWN BY CATEGORY (Priority Order):")
        sorted_categories = sorted(
            self.categories.items(), key=lambda x: (self.get_priority_level(x[0]), x[0])
        )

        for category, files in sorted_categories:
            if files:
                priority = self.get_priority_level(category)
                priority_label = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "MINIMAL"][
                    priority - 1
                ]
                report.append(f"  [{priority_label}] {category}: {len(files)} files")

                if verbose:
                    for file in sorted(files)[:10]:  # Show first 10 files
                        report.append(f"    - {file}")
                    if len(files) > 10:
                        report.append(f"    ... and {len(files) - 10} more")
                    report.append("")

        report.append("=" * 80)
        return "\n".join(report)

    def generate_json_report(self) -> Dict:
        """Generate JSON coverage report."""
        stats = self.calculate_stats()

        # Organize categories by priority
        categorized_files = {}
        for category, files in self.categories.items():
            categorized_files[category] = {
                "count": len(files),
                "priority": self.get_priority_level(category),
                "files": sorted(files),
            }

        return {
            "statistics": stats,
            "categories": categorized_files,
            "files_with_correlation_id": sorted(self.files_with_corr),
            "files_without_correlation_id": sorted(self.missing_files),
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Track correlation_id coverage across the codebase"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed file lists"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output report in JSON format"
    )
    parser.add_argument(
        "--src-dir", default="src", help="Source directory to scan (default: src)"
    )

    args = parser.parse_args()

    # Create tracker and scan files
    tracker = CorrelationIDCoverageTracker(src_dir=args.src_dir)
    tracker.scan_files()
    tracker.categorize_files()

    # Generate and output report
    if args.json:
        report = tracker.generate_json_report()
        print(json.dumps(report, indent=2))
    else:
        report = tracker.generate_report(verbose=args.verbose)
        print(report)


if __name__ == "__main__":
    main()
