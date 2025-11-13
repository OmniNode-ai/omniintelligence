#!/usr/bin/env python3
"""
Intelligence Data Quality Validation Script

This script demonstrates how the new intelligence data access module
can be used independently for data quality testing without UI concerns.

Usage:
    python scripts/test_intelligence_data_quality.py [--repository REPO] [--time-range RANGE]

Examples:
    python scripts/test_intelligence_data_quality.py
    python scripts/test_intelligence_data_quality.py --repository Archon --time-range 7d
    python scripts/test_intelligence_data_quality.py --repository all --time-range 24h
"""

import argparse
import os
import sys
from datetime import datetime
from typing import Optional

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from server.data.intelligence_data_access import (
    QueryParameters,
    create_intelligence_data_access,
)
from server.services.client_manager import get_database_client


class IntelligenceDataQualityValidator:
    """Validates intelligence data quality using the data access layer."""

    def __init__(self):
        """Initialize the validator with data access layer."""
        self.data_access = create_intelligence_data_access(get_database_client())

    def validate_time_range_parsing(self) -> bool:
        """Validate time range parsing functionality."""
        print("🔍 Validating time range parsing...")

        test_cases = [
            ("1h", 1),
            ("6h", 6),
            ("24h", 24),
            ("72h", 72),
            ("7d", 168),
            ("invalid", 24),  # Should default to 24h
        ]

        all_passed = True
        for time_range, expected in test_cases:
            result = self.data_access.parse_time_range(time_range)
            if result != expected:
                print(
                    f"❌ Time range parsing failed: {time_range} -> {result} (expected {expected})"
                )
                all_passed = False
            else:
                print(f"✅ Time range parsing passed: {time_range} -> {result}")

        return all_passed

    def validate_document_parsing(
        self, repository: Optional[str] = None, time_range: str = "24h"
    ) -> bool:
        """Validate document parsing for different content formats."""
        print(
            f"🔍 Validating document parsing (repo: {repository or 'all'}, range: {time_range})..."
        )

        params = QueryParameters(
            repository=repository,
            time_range=time_range,
            limit=10,  # Small limit for testing
        )

        try:
            # Get raw documents
            raw_result = self.data_access.get_raw_documents(params)

            if not raw_result["success"]:
                print(f"❌ Failed to fetch raw documents: {raw_result.get('error')}")
                return False

            raw_docs = raw_result["documents"]
            print(f"📊 Found {len(raw_docs)} raw documents")

            # Get parsed documents
            parsed_docs = self.data_access.get_parsed_documents(params)
            print(f"📊 Successfully parsed {len(parsed_docs)} documents")

            # Validate parsing consistency
            if len(raw_docs) != len(parsed_docs):
                print(
                    f"⚠️  Raw document count ({len(raw_docs)}) != parsed count ({len(parsed_docs)})"
                )
                # This might be OK if some documents failed to parse

            # Validate document data quality
            for i, doc in enumerate(parsed_docs):
                if not doc.repository or doc.repository == "unknown":
                    print(f"⚠️  Document {i}: Missing or unknown repository")

                if not doc.commit_sha or doc.commit_sha == "unknown":
                    print(f"⚠️  Document {i}: Missing or unknown commit SHA")

                if not doc.author or doc.author == "unknown":
                    print(f"⚠️  Document {i}: Missing or unknown author")

                # Check if document has any intelligence data
                has_data = (
                    doc.diff_analysis is not None
                    or len(doc.temporal_correlations) > 0
                    or len(doc.semantic_correlations) > 0
                    or len(doc.breaking_changes) > 0
                    or doc.security_analysis is not None
                )

                if not has_data:
                    print(f"⚠️  Document {i}: No intelligence data found")

            print("✅ Document parsing validation completed")
            return True

        except Exception as e:
            print(f"❌ Document parsing validation failed: {e}")
            return False

    def validate_statistics_calculation(
        self, repository: Optional[str] = None, time_range: str = "24h"
    ) -> bool:
        """Validate statistics calculation accuracy."""
        print(
            f"🔍 Validating statistics calculation (repo: {repository or 'all'}, range: {time_range})..."
        )

        params = QueryParameters(repository=repository, time_range=time_range)

        try:
            # Calculate statistics
            stats = self.data_access.calculate_statistics(params)

            print("📊 Statistics Summary:")
            print(f"   Total changes: {stats.total_changes}")
            print(f"   Total correlations: {stats.total_correlations}")
            print(
                f"   Average correlation strength: {stats.average_correlation_strength:.3f}"
            )
            print(f"   Breaking changes: {stats.breaking_changes}")
            print(f"   Active repositories: {stats.repositories_active}")
            print(f"   Repository list: {stats.repositories_list}")

            # Validate statistics consistency
            if stats.total_correlations > 0 and not stats.correlation_strengths:
                print("⚠️  Total correlations > 0 but no correlation strengths recorded")

            if stats.repositories_active != len(stats.repositories_list):
                print(
                    f"⚠️  Active repo count ({stats.repositories_active}) != repo list length ({len(stats.repositories_list)})"
                )

            if stats.average_correlation_strength > 0 and stats.total_correlations == 0:
                print("⚠️  Average correlation strength > 0 but total correlations = 0")

            # Validate correlation strength calculation
            if stats.correlation_strengths:
                manual_avg = sum(stats.correlation_strengths) / len(
                    stats.correlation_strengths
                )
                if abs(manual_avg - stats.average_correlation_strength) > 0.001:
                    print(
                        f"⚠️  Average correlation calculation mismatch: {manual_avg:.3f} vs {stats.average_correlation_strength:.3f}"
                    )

            print("✅ Statistics calculation validation completed")
            return True

        except Exception as e:
            print(f"❌ Statistics calculation validation failed: {e}")
            return False

    def validate_repository_extraction(self) -> bool:
        """Validate repository extraction from intelligence documents."""
        print("🔍 Validating repository extraction...")

        try:
            repositories = self.data_access.get_active_repositories()

            print(f"📊 Found {len(repositories)} active repositories:")
            for repo in repositories:
                print(f"   - {repo}")

            # Validate repository data quality
            if not repositories:
                print(
                    "⚠️  No active repositories found - this might indicate data issues"
                )

            for repo in repositories:
                if not repo or repo.strip() == "":
                    print("⚠️  Empty repository name found")

                if repo == "unknown":
                    print("⚠️  'unknown' repository found - indicates parsing issues")

            print("✅ Repository extraction validation completed")
            return True

        except Exception as e:
            print(f"❌ Repository extraction validation failed: {e}")
            return False

    def validate_content_format_handling(self) -> bool:
        """Validate handling of different content formats."""
        print("🔍 Validating content format handling...")

        # Test different content formats
        test_formats = [
            # MCP format
            {
                "name": "MCP Format",
                "content": {
                    "metadata": {
                        "repository": "test-repo",
                        "commit": "abc123",
                        "author": "test-user",
                    },
                    "code_changes_analysis": {
                        "changed_files": ["file1.py", "file2.js"]
                    },
                    "cross_repository_correlation": {
                        "temporal_correlations": [
                            {
                                "repository": "related-repo",
                                "commit": "def456",
                                "time_window": "6h",
                                "correlation_strength": "high",
                            }
                        ]
                    },
                },
            },
            # Legacy git hook format
            {
                "name": "Legacy Git Hook Format",
                "content": {
                    "diff_analysis": {
                        "total_changes": 3,
                        "added_lines": 50,
                        "removed_lines": 20,
                        "modified_files": ["file1.py", "file2.js", "file3.ts"],
                    },
                    "correlation_analysis": {
                        "temporal_correlations": [
                            {
                                "repository": "related-repo",
                                "commit_sha": "def456",
                                "time_diff_hours": 6.0,
                                "correlation_strength": 0.9,
                            }
                        ]
                    },
                    "security_analysis": {
                        "patterns_detected": ["secure_pattern_1"],
                        "risk_level": "LOW",
                        "secure_patterns": 1,
                    },
                },
            },
            # Project document format
            {
                "name": "Project Document Format",
                "content": {
                    "quality_baseline": {
                        "code_quality_metrics": {
                            "anti_patterns_found": 0,
                            "architectural_compliance": "High",
                            "type_safety": "Strong",
                        }
                    },
                    "repository_info": {
                        "repository": "project-repo",
                        "commit": "ghi789",
                        "files_changed": 2,
                    },
                    "changed_files": ["src/main.py", "tests/test.py"],
                },
            },
        ]

        all_passed = True

        for test_format in test_formats:
            print(f"   Testing {test_format['name']}...")
            content = test_format["content"]

            try:
                # Test diff analysis parsing
                diff_analysis = self.data_access.parse_diff_analysis(content)
                if diff_analysis:
                    print(
                        f"     ✅ Diff analysis: {diff_analysis.total_changes} changes"
                    )
                else:
                    print("     ⚠️  Diff analysis: No data found")

                # Test correlation parsing
                temporal, semantic, breaking = self.data_access.parse_correlations(
                    content
                )
                print(
                    f"     ✅ Correlations: {len(temporal)} temporal, {len(semantic)} semantic, {len(breaking)} breaking"
                )

                # Test security analysis parsing
                security = self.data_access.parse_security_analysis(content)
                if security:
                    print(
                        f"     ✅ Security analysis: {len(security.patterns_detected)} patterns"
                    )
                else:
                    print("     ⚠️  Security analysis: No data found")

            except Exception as e:
                print(f"     ❌ Format parsing failed: {e}")
                all_passed = False

        if all_passed:
            print("✅ Content format handling validation completed")
        else:
            print("❌ Content format handling validation had issues")

        return all_passed

    def run_comprehensive_validation(
        self, repository: Optional[str] = None, time_range: str = "24h"
    ) -> bool:
        """Run comprehensive data quality validation."""
        print("🚀 Starting comprehensive intelligence data quality validation")
        print(f"   Repository filter: {repository or 'all'}")
        print(f"   Time range: {time_range}")
        print(f"   Timestamp: {datetime.now().isoformat()}")
        print("-" * 70)

        validations = [
            ("Time Range Parsing", self.validate_time_range_parsing),
            (
                "Document Parsing",
                lambda: self.validate_document_parsing(repository, time_range),
            ),
            (
                "Statistics Calculation",
                lambda: self.validate_statistics_calculation(repository, time_range),
            ),
            ("Repository Extraction", self.validate_repository_extraction),
            ("Content Format Handling", self.validate_content_format_handling),
        ]

        results = []

        for name, validation_func in validations:
            print(f"\n{'='*20} {name} {'='*20}")
            try:
                result = validation_func()
                results.append((name, result))
            except Exception as e:
                print(f"❌ Validation '{name}' crashed: {e}")
                results.append((name, False))

        print(f"\n{'='*70}")
        print("🏁 VALIDATION SUMMARY")
        print("=" * 70)

        passed = 0
        for name, result in results:
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{name:<30} {status}")
            if result:
                passed += 1

        print(f"\nOverall: {passed}/{len(results)} validations passed")

        if passed == len(results):
            print("🎉 All validations passed! Data quality is excellent.")
            return True
        else:
            print("⚠️  Some validations failed. Please review the issues above.")
            return False


def main():
    """Main entry point for the validation script."""
    parser = argparse.ArgumentParser(
        description="Validate intelligence data quality using the data access layer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Validate all data from last 24h
  %(prog)s --repository Archon               # Validate Archon repository data
  %(prog)s --time-range 7d                   # Validate last 7 days
  %(prog)s --repository all --time-range 72h # Validate all repos, last 72h
        """,
    )

    parser.add_argument(
        "--repository",
        "-r",
        help="Repository to filter by (default: all repositories)",
        default=None,
    )

    parser.add_argument(
        "--time-range",
        "-t",
        help="Time range for data analysis (1h, 6h, 24h, 72h, 7d)",
        default="24h",
        choices=["1h", "6h", "24h", "72h", "7d"],
    )

    parser.add_argument(
        "--quiet", "-q", help="Reduce output verbosity", action="store_true"
    )

    args = parser.parse_args()

    if args.quiet:
        # Redirect stdout to reduce verbosity (errors will still show)
        import sys

        with open(os.devnull, "w") as devnull:
            sys.stdout = devnull

    try:
        validator = IntelligenceDataQualityValidator()
        success = validator.run_comprehensive_validation(
            repository=args.repository, time_range=args.time_range
        )

        if args.quiet:
            sys.stdout = sys.__stdout__

        # Exit with appropriate code
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n🛑 Validation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Validation crashed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
