#!/usr/bin/env python3
"""
Intelligence Debug Tool

Comprehensive debugging utility for the Archon Intelligence system.
Provides live API testing, data comparison, correlation validation, and
ASCII dashboard visualization for debugging correlation issues.

Usage:
    python debug_intelligence.py --live-api         # Test live API
    python debug_intelligence.py --compare-data     # Compare fixture vs live
    python debug_intelligence.py --dashboard        # Show dashboard
    python debug_intelligence.py --validate         # Validate data quality
    python debug_intelligence.py --regenerate       # Trigger correlation regeneration
"""

import argparse
import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

# Import our fixtures and utilities
from fixtures.intelligence_fixtures import (
    ASCIIDashboard,
    IntelligenceDebugUtils,
    IntelligenceFixtures,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class IntelligenceDebugTool:
    """Comprehensive debugging tool for Archon Intelligence system."""

    def __init__(self, base_url: str = "http://localhost:8181"):
        self.base_url = base_url
        self.api_base = f"{base_url}/api/intelligence"
        self.client = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client:
            await self.client.aclose()

    # ========================================
    # Live API Testing
    # ========================================

    async def test_live_api(self) -> dict[str, Any]:
        """Test live API endpoints and return data."""
        print("🔍 TESTING LIVE INTELLIGENCE API")
        print("=" * 60)

        results = {}

        try:
            # Test documents endpoint
            print("📄 Testing /api/intelligence/documents...")
            response = await self.client.get(f"{self.api_base}/documents?limit=5")

            if response.status_code == 200:
                data = response.json()
                results["documents"] = data
                print(f"✅ Got {len(data.get('documents', []))} documents")
                print(f"   Total count: {data.get('total_count', 0)}")
                print(f"   Repositories: {data.get('repositories', [])}")
            else:
                print(f"❌ Documents API failed: {response.status_code}")
                results["documents_error"] = response.text

            # Test stats endpoint
            print("\n📊 Testing /api/intelligence/stats...")
            response = await self.client.get(f"{self.api_base}/stats")

            if response.status_code == 200:
                stats = response.json()
                results["stats"] = stats
                print("✅ Stats retrieved:")
                print(f"   Total changes: {stats.get('total_changes', 0)}")
                print(f"   Total correlations: {stats.get('total_correlations', 0)}")
                print(f"   Breaking changes: {stats.get('breaking_changes', 0)}")
                print(f"   Active repositories: {stats.get('repositories_active', 0)}")
            else:
                print(f"❌ Stats API failed: {response.status_code}")
                results["stats_error"] = response.text

            # Test repositories endpoint
            print("\n🏢 Testing /api/intelligence/repositories...")
            response = await self.client.get(f"{self.api_base}/repositories")

            if response.status_code == 200:
                repos = response.json()
                results["repositories"] = repos
                print(f"✅ Got {len(repos.get('repositories', []))} repositories")
                for repo in repos.get("repositories", []):
                    print(f"   - {repo}")
            else:
                print(f"❌ Repositories API failed: {response.status_code}")
                results["repositories_error"] = response.text

        except Exception as e:
            print(f"❌ API test failed with exception: {e}")
            results["exception"] = str(e)

        return results

    # ========================================
    # Data Quality Analysis
    # ========================================

    async def analyze_data_quality(
        self, api_data: dict[str, Any] = None
    ) -> dict[str, Any]:
        """Analyze the quality of live API data."""
        print("\n🔍 ANALYZING DATA QUALITY")
        print("=" * 60)

        if api_data is None:
            api_data = await self.test_live_api()

        quality_report = {
            "overall_issues": [],
            "document_analysis": [],
            "correlation_quality": {},
            "recommendations": [],
        }

        documents = api_data.get("documents", {}).get("documents", [])

        if not documents:
            quality_report["overall_issues"].append(
                "No documents found in API response"
            )
            return quality_report

        print(f"📄 Analyzing {len(documents)} documents...")

        for i, doc in enumerate(documents):
            doc_analysis = {
                "document_id": doc.get("id", f"doc-{i}"),
                "repository": doc.get("repository", "unknown"),
                "issues": [],
                "quality_score": 100,
            }

            # Check intelligence data structure
            intel_data = doc.get("intelligence_data", {})
            if not intel_data:
                doc_analysis["issues"].append("Missing intelligence_data")
                doc_analysis["quality_score"] -= 20
                continue

            # Check correlation analysis
            corr_analysis = intel_data.get("correlation_analysis", {})
            if not corr_analysis:
                doc_analysis["issues"].append("Missing correlation_analysis")
                doc_analysis["quality_score"] -= 30
            else:
                # Analyze semantic correlations
                semantic_corrs = corr_analysis.get("semantic_correlations", [])
                for j, corr in enumerate(semantic_corrs):
                    file_info = corr.get("file_information", {})

                    if file_info:
                        # Use our validation utility
                        validation_issues = (
                            IntelligenceDebugUtils.validate_file_information(file_info)
                        )
                        if validation_issues:
                            doc_analysis["issues"].extend(
                                [
                                    f"Semantic correlation {j}: {issue}"
                                    for issue in validation_issues
                                ]
                            )
                            doc_analysis["quality_score"] -= min(
                                len(validation_issues) * 5, 25
                            )
                    else:
                        doc_analysis["issues"].append(
                            f"Semantic correlation {j}: Missing file_information"
                        )
                        doc_analysis["quality_score"] -= 10

            quality_report["document_analysis"].append(doc_analysis)

        # Overall quality assessment
        if quality_report["document_analysis"]:
            avg_quality = sum(
                doc["quality_score"] for doc in quality_report["document_analysis"]
            ) / len(quality_report["document_analysis"])
            print(f"\n📊 Overall Quality Score: {avg_quality:.1f}/100")

            if avg_quality < 70:
                quality_report["recommendations"].append(
                    "Consider regenerating correlations - quality is below 70%"
                )

            if avg_quality < 50:
                quality_report["recommendations"].append(
                    "CRITICAL: Force regenerate all correlations immediately"
                )

        # Print summary
        total_issues = sum(
            len(doc["issues"]) for doc in quality_report["document_analysis"]
        )
        print(f"📋 Total Issues Found: {total_issues}")

        for doc_analysis in quality_report["document_analysis"]:
            if doc_analysis["issues"]:
                print(
                    f"\n📄 {doc_analysis['repository']} ({doc_analysis['document_id']}):"
                )
                for issue in doc_analysis["issues"]:
                    print(f"   ⚠️  {issue}")

        return quality_report

    # ========================================
    # Data Comparison
    # ========================================

    async def compare_fixture_vs_live(self) -> str:
        """Compare fixture data with live API data."""
        print("\n🔄 COMPARING FIXTURE vs LIVE DATA")
        print("=" * 60)

        # Get fixture data
        fixture_correlations = IntelligenceFixtures.get_realistic_correlations()
        print("✅ Loaded fixture correlations")

        # Get live API data
        live_data = await self.test_live_api()

        if not live_data.get("documents", {}).get("documents"):
            return "❌ No live data available for comparison"

        live_doc = live_data["documents"]["documents"][0]
        live_correlations = live_doc.get("intelligence_data", {}).get(
            "correlation_analysis", {}
        )

        if not live_correlations:
            return "❌ No correlation data in live API response"

        # Use our comparison utility
        comparison_report = IntelligenceDebugUtils.compare_expected_vs_actual(
            fixture_correlations, live_correlations
        )

        print(comparison_report)
        return comparison_report

    # ========================================
    # Dashboard Visualization
    # ========================================

    async def show_dashboard(self, use_live_data: bool = True) -> None:
        """Display ASCII dashboard with correlation data."""
        print("\n🎯 INTELLIGENCE CORRELATION DASHBOARD")
        print("=" * 80)

        if use_live_data:
            print("📡 Using LIVE API data...")
            live_data = await self.test_live_api()

            if live_data.get("documents", {}).get("documents"):
                live_doc = live_data["documents"]["documents"][0]
                correlations = live_doc.get("intelligence_data", {}).get(
                    "correlation_analysis", {}
                )

                if correlations:
                    dashboard = ASCIIDashboard.render_correlation_summary(correlations)
                    print(dashboard)
                else:
                    print("❌ No correlation data found in live API")
                    print("\n📋 Falling back to fixture data...")
                    fixture_correlations = (
                        IntelligenceFixtures.get_realistic_correlations()
                    )
                    dashboard = ASCIIDashboard.render_correlation_summary(
                        fixture_correlations
                    )
                    print(dashboard)
            else:
                print("❌ No documents found in live API")
                print("\n📋 Showing fixture data instead...")
                fixture_correlations = IntelligenceFixtures.get_realistic_correlations()
                dashboard = ASCIIDashboard.render_correlation_summary(
                    fixture_correlations
                )
                print(dashboard)
        else:
            print("📋 Using FIXTURE data...")
            fixture_correlations = IntelligenceFixtures.get_realistic_correlations()
            dashboard = ASCIIDashboard.render_correlation_summary(fixture_correlations)
            print(dashboard)

    # ========================================
    # Correlation Management
    # ========================================

    async def regenerate_correlations(self, force: bool = False) -> dict[str, Any]:
        """Trigger correlation regeneration."""
        endpoint = (
            "/force-regenerate-correlations" if force else "/generate-correlations"
        )
        action = "Force regenerating" if force else "Regenerating"

        print(f"\n🔄 {action.upper()} CORRELATIONS")
        print("=" * 60)

        try:
            print(f"🚀 Triggering {endpoint}...")
            response = await self.client.post(f"{self.api_base}{endpoint}")

            if response.status_code == 200:
                result = response.json()
                print("✅ Regeneration completed successfully!")

                if "results" in result:
                    results = result["results"]
                    print(
                        f"   📊 Processed documents: {results.get('processed_documents', 0)}"
                    )
                    print(
                        f"   🔍 Analyzed documents: {results.get('analyzed_documents', 0)}"
                    )
                    if force:
                        print(
                            f"   🗑️  Cleared documents: {results.get('cleared_documents', 0)}"
                        )

                if "improvements" in result:
                    print("\n🎯 Improvements applied:")
                    for improvement in result["improvements"]:
                        print(f"   ✨ {improvement}")

                return result
            else:
                print(f"❌ Regeneration failed: {response.status_code}")
                print(f"   Error: {response.text}")
                return {"success": False, "error": response.text}

        except Exception as e:
            print(f"❌ Exception during regeneration: {e}")
            return {"success": False, "exception": str(e)}

    # ========================================
    # Comprehensive Testing Suite
    # ========================================

    async def run_comprehensive_test(self) -> dict[str, Any]:
        """Run comprehensive intelligence system test."""
        print("🧪 COMPREHENSIVE INTELLIGENCE SYSTEM TEST")
        print("=" * 80)

        test_results = {
            "timestamp": datetime.now(UTC).isoformat(),
            "api_test": {},
            "data_quality": {},
            "comparison": "",
            "recommendations": [],
        }

        # Step 1: Test API endpoints
        print("\n1️⃣  API ENDPOINT TESTING")
        test_results["api_test"] = await self.test_live_api()

        # Step 2: Analyze data quality
        print("\n2️⃣  DATA QUALITY ANALYSIS")
        test_results["data_quality"] = await self.analyze_data_quality(
            test_results["api_test"]
        )

        # Step 3: Compare with fixtures
        print("\n3️⃣  FIXTURE COMPARISON")
        test_results["comparison"] = await self.compare_fixture_vs_live()

        # Step 4: Show dashboard
        print("\n4️⃣  DASHBOARD VISUALIZATION")
        await self.show_dashboard(use_live_data=True)

        # Step 5: Generate recommendations
        print("\n5️⃣  RECOMMENDATIONS")
        if test_results["data_quality"].get("recommendations"):
            for rec in test_results["data_quality"]["recommendations"]:
                test_results["recommendations"].append(rec)
                print(f"   💡 {rec}")

        total_issues = sum(
            len(doc["issues"])
            for doc in test_results["data_quality"].get("document_analysis", [])
        )

        if total_issues > 5:
            test_results["recommendations"].append(
                "High number of issues found - consider system maintenance"
            )

        if not test_results["api_test"].get("documents", {}).get("documents"):
            test_results["recommendations"].append(
                "No documents found - check intelligence hook deployment"
            )

        # Save results
        await self.save_test_results(test_results)

        print(f"\n✅ Comprehensive test completed - {total_issues} issues found")
        return test_results

    async def save_test_results(self, results: dict[str, Any]) -> None:
        """Save test results to file."""
        try:
            output_dir = Path(__file__).parent / "debug_output"
            output_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = output_dir / f"intelligence_debug_{timestamp}.json"

            with open(output_file, "w") as f:
                json.dump(results, f, indent=2, default=str)

            print(f"💾 Test results saved to: {output_file}")

        except Exception as e:
            print(f"⚠️  Could not save results: {e}")


async def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(description="Archon Intelligence Debug Tool")
    parser.add_argument(
        "--live-api", action="store_true", help="Test live API endpoints"
    )
    parser.add_argument(
        "--dashboard", action="store_true", help="Show correlation dashboard"
    )
    parser.add_argument(
        "--fixture-dashboard", action="store_true", help="Show fixture dashboard only"
    )
    parser.add_argument(
        "--compare-data", action="store_true", help="Compare fixture vs live data"
    )
    parser.add_argument("--validate", action="store_true", help="Validate data quality")
    parser.add_argument(
        "--regenerate", action="store_true", help="Regenerate correlations"
    )
    parser.add_argument(
        "--force-regenerate",
        action="store_true",
        help="Force regenerate all correlations",
    )
    parser.add_argument(
        "--comprehensive", action="store_true", help="Run comprehensive test suite"
    )
    parser.add_argument(
        "--base-url", default="http://localhost:8181", help="API base URL"
    )

    args = parser.parse_args()

    # If no specific action, show help
    if not any(
        [
            args.live_api,
            args.dashboard,
            args.fixture_dashboard,
            args.compare_data,
            args.validate,
            args.regenerate,
            args.force_regenerate,
            args.comprehensive,
        ]
    ):
        # Show fixture dashboard by default
        print("🎯 SHOWING FIXTURE DASHBOARD (use --help for options)")
        ASCIIDashboard.test_dashboard_display()
        return

    async with IntelligenceDebugTool(base_url=args.base_url) as tool:
        if args.comprehensive:
            await tool.run_comprehensive_test()

        elif args.live_api:
            await tool.test_live_api()

        elif args.dashboard:
            await tool.show_dashboard(use_live_data=True)

        elif args.fixture_dashboard:
            await tool.show_dashboard(use_live_data=False)

        elif args.compare_data:
            await tool.compare_fixture_vs_live()

        elif args.validate:
            live_data = await tool.test_live_api()
            await tool.analyze_data_quality(live_data)

        elif args.regenerate:
            await tool.regenerate_correlations(force=False)

        elif args.force_regenerate:
            await tool.regenerate_correlations(force=True)


if __name__ == "__main__":
    asyncio.run(main())
