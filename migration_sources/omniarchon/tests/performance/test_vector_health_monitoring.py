#!/usr/bin/env python3
"""
Vector Health Monitoring System Integration Test

This script tests the complete vector health monitoring system including:
- API endpoints functionality
- Metrics collection
- Alert generation
- Dashboard data retrieval
"""

import asyncio
import logging
import sys
import time
from typing import Any, Dict

import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API Configuration
BASE_URL = "http://localhost:8181"
VECTOR_HEALTH_BASE = f"{BASE_URL}/api/vector-health"


class VectorHealthTestSuite:
    """Comprehensive test suite for vector health monitoring"""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.vector_health_url = f"{base_url}/api/vector-health"
        self.client = httpx.AsyncClient(timeout=30.0)
        self.test_results: Dict[str, Any] = {}

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

    async def test_server_health(self) -> bool:
        """Test if the server is running"""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            if response.status_code == 200:
                logger.info("✅ Server is running and healthy")
                return True
            else:
                logger.error(f"❌ Server health check failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Could not connect to server: {e}")
            return False

    async def test_vector_health_status(self) -> bool:
        """Test vector health status endpoint"""
        try:
            response = await self.client.get(f"{self.vector_health_url}/status")

            if response.status_code == 200:
                data = response.json()

                if data.get("success"):
                    logger.info("✅ Vector health status endpoint working")
                    logger.info(f"   Status: {data['data']['overall_status']}")
                    logger.info(
                        f"   Monitoring Active: {data['data']['monitoring_active']}"
                    )
                    self.test_results["status_endpoint"] = data
                    return True
                else:
                    logger.error(
                        "❌ Vector health status endpoint returned unsuccessful response"
                    )
                    return False
            else:
                logger.error(
                    f"❌ Vector health status endpoint failed: {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"❌ Vector health status test failed: {e}")
            return False

    async def test_dashboard_data(self) -> bool:
        """Test dashboard data endpoint"""
        try:
            response = await self.client.get(f"{self.vector_health_url}/dashboard")

            if response.status_code == 200:
                data = response.json()

                if data.get("success"):
                    dashboard_data = data["data"]
                    logger.info("✅ Dashboard data endpoint working")
                    logger.info(
                        f"   Monitoring Status: {dashboard_data.get('monitoring_status')}"
                    )
                    logger.info(
                        f"   Collections: {list(dashboard_data.get('collections', {}).keys())}"
                    )
                    logger.info(
                        f"   Active Alerts: {len(dashboard_data.get('alerts', []))}"
                    )

                    # Validate dashboard data structure
                    required_fields = [
                        "collections",
                        "balance",
                        "routing",
                        "alerts",
                        "thresholds",
                    ]
                    missing_fields = [
                        field
                        for field in required_fields
                        if field not in dashboard_data
                    ]

                    if missing_fields:
                        logger.warning(f"⚠️  Missing dashboard fields: {missing_fields}")
                    else:
                        logger.info("✅ Dashboard data structure is complete")

                    self.test_results["dashboard_data"] = dashboard_data
                    return True
                else:
                    logger.error(
                        "❌ Dashboard data endpoint returned unsuccessful response"
                    )
                    return False
            else:
                logger.error(
                    f"❌ Dashboard data endpoint failed: {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"❌ Dashboard data test failed: {e}")
            return False

    async def test_collection_metrics(self) -> bool:
        """Test collection metrics endpoint"""
        try:
            response = await self.client.get(
                f"{self.vector_health_url}/collections?hours=1"
            )

            if response.status_code == 200:
                data = response.json()

                if data.get("success"):
                    metrics = data["data"]["metrics"]
                    logger.info("✅ Collection metrics endpoint working")
                    logger.info(f"   Total Metrics: {len(metrics)}")

                    if metrics:
                        sample_metric = metrics[0]
                        logger.info(
                            f"   Sample Collection: {sample_metric.get('collection_name')}"
                        )
                        logger.info(
                            f"   Sample Vectors: {sample_metric.get('total_vectors')}"
                        )
                        logger.info(
                            f"   Sample Search Time: {sample_metric.get('avg_search_time_ms')}ms"
                        )

                    self.test_results["collection_metrics"] = metrics
                    return True
                else:
                    logger.error(
                        "❌ Collection metrics endpoint returned unsuccessful response"
                    )
                    return False
            else:
                logger.error(
                    f"❌ Collection metrics endpoint failed: {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"❌ Collection metrics test failed: {e}")
            return False

    async def test_balance_metrics(self) -> bool:
        """Test balance metrics endpoint"""
        try:
            response = await self.client.get(
                f"{self.vector_health_url}/balance?hours=1"
            )

            if response.status_code == 200:
                data = response.json()

                if data.get("success"):
                    balance_metrics = data["data"]["balance_metrics"]
                    logger.info("✅ Balance metrics endpoint working")
                    logger.info(f"   Total Balance Records: {len(balance_metrics)}")
                    logger.info(
                        f"   Balance Trend: {data['data'].get('balance_trend')}"
                    )

                    if balance_metrics:
                        latest_balance = balance_metrics[-1]
                        logger.info(
                            f"   Latest Balance Ratio: {latest_balance.get('size_balance_ratio')}"
                        )
                        logger.info(
                            f"   Balance Status: {latest_balance.get('balance_status')}"
                        )

                    self.test_results["balance_metrics"] = balance_metrics
                    return True
                else:
                    logger.error(
                        "❌ Balance metrics endpoint returned unsuccessful response"
                    )
                    return False
            else:
                logger.error(
                    f"❌ Balance metrics endpoint failed: {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"❌ Balance metrics test failed: {e}")
            return False

    async def test_routing_metrics(self) -> bool:
        """Test routing metrics endpoint"""
        try:
            response = await self.client.get(
                f"{self.vector_health_url}/routing?hours=1"
            )

            if response.status_code == 200:
                data = response.json()

                if data.get("success"):
                    routing_metrics = data["data"]["routing_metrics"]
                    summary = data["data"]["summary"]
                    logger.info("✅ Routing metrics endpoint working")
                    logger.info(f"   Total Routing Records: {len(routing_metrics)}")
                    logger.info(f"   Total Decisions: {summary.get('total_decisions')}")
                    logger.info(
                        f"   Average Accuracy: {summary.get('average_accuracy')}"
                    )

                    self.test_results["routing_metrics"] = routing_metrics
                    return True
                else:
                    logger.error(
                        "❌ Routing metrics endpoint returned unsuccessful response"
                    )
                    return False
            else:
                logger.error(
                    f"❌ Routing metrics endpoint failed: {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"❌ Routing metrics test failed: {e}")
            return False

    async def test_alerts_endpoint(self) -> bool:
        """Test alerts endpoint"""
        try:
            response = await self.client.get(f"{self.vector_health_url}/alerts")

            if response.status_code == 200:
                data = response.json()

                if data.get("success"):
                    alerts = data["data"]["alerts"]
                    alert_counts = data["data"]["alert_counts"]
                    logger.info("✅ Alerts endpoint working")
                    logger.info(f"   Total Alerts: {len(alerts)}")
                    logger.info(f"   Critical: {alert_counts.get('critical')}")
                    logger.info(f"   Warning: {alert_counts.get('warning')}")
                    logger.info(f"   Degraded: {alert_counts.get('degraded')}")

                    self.test_results["alerts"] = alerts
                    return True
                else:
                    logger.error("❌ Alerts endpoint returned unsuccessful response")
                    return False
            else:
                logger.error(f"❌ Alerts endpoint failed: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"❌ Alerts test failed: {e}")
            return False

    async def test_thresholds_endpoint(self) -> bool:
        """Test thresholds endpoint"""
        try:
            response = await self.client.get(f"{self.vector_health_url}/thresholds")

            if response.status_code == 200:
                data = response.json()

                if data.get("success"):
                    thresholds = data["data"]["alert_thresholds"]
                    config = data["data"]["monitoring_config"]
                    logger.info("✅ Thresholds endpoint working")
                    logger.info(f"   Threshold Count: {len(thresholds)}")
                    logger.info(f"   Main Collection: {config.get('main_collection')}")
                    logger.info(
                        f"   Quality Collection: {config.get('quality_collection')}"
                    )
                    logger.info(
                        f"   Monitoring Interval: {config.get('monitoring_interval')}s"
                    )

                    self.test_results["thresholds"] = thresholds
                    return True
                else:
                    logger.error(
                        "❌ Thresholds endpoint returned unsuccessful response"
                    )
                    return False
            else:
                logger.error(f"❌ Thresholds endpoint failed: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"❌ Thresholds test failed: {e}")
            return False

    async def test_monitoring_control(self) -> bool:
        """Test monitoring start/stop controls"""
        try:
            # Test start monitoring
            start_response = await self.client.post(
                f"{self.vector_health_url}/monitoring/start"
            )

            if start_response.status_code == 200:
                start_data = start_response.json()
                if start_data.get("success"):
                    logger.info("✅ Monitoring start endpoint working")
                else:
                    logger.warning("⚠️  Monitoring start returned unsuccessful response")
            else:
                logger.warning(
                    f"⚠️  Monitoring start failed: {start_response.status_code}"
                )

            # Wait a moment
            await asyncio.sleep(1)

            # Test stop monitoring
            stop_response = await self.client.post(
                f"{self.vector_health_url}/monitoring/stop"
            )

            if stop_response.status_code == 200:
                stop_data = stop_response.json()
                if stop_data.get("success"):
                    logger.info("✅ Monitoring stop endpoint working")
                    return True
                else:
                    logger.warning("⚠️  Monitoring stop returned unsuccessful response")
                    return False
            else:
                logger.warning(
                    f"⚠️  Monitoring stop failed: {stop_response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"❌ Monitoring control test failed: {e}")
            return False

    async def test_record_routing_decision(self) -> bool:
        """Test recording routing decisions"""
        try:
            test_data = {
                "decision": "main",
                "routing_time_ms": 25.5,
                "document_type": "test_document",
                "quality_score": 0.85,
            }

            response = await self.client.post(
                f"{self.vector_health_url}/routing/record", params=test_data
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    logger.info("✅ Routing decision recording working")
                    logger.info(f"   Recorded Decision: {data['data']['decision']}")
                    logger.info(f"   Routing Time: {data['data']['routing_time_ms']}ms")
                    return True
                else:
                    logger.error(
                        "❌ Routing decision recording returned unsuccessful response"
                    )
                    return False
            else:
                logger.error(
                    f"❌ Routing decision recording failed: {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"❌ Routing decision recording test failed: {e}")
            return False

    async def test_record_search_performance(self) -> bool:
        """Test recording search performance"""
        try:
            test_data = {
                "search_time_ms": 45.2,
                "collection": "archon_vectors",
                "query_type": "similarity_search",
                "result_count": 10,
            }

            response = await self.client.post(
                f"{self.vector_health_url}/performance/record", params=test_data
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    logger.info("✅ Search performance recording working")
                    logger.info(
                        f"   Recorded Search Time: {data['data']['search_time_ms']}ms"
                    )
                    logger.info(f"   Collection: {data['data']['collection']}")
                    return True
                else:
                    logger.error(
                        "❌ Search performance recording returned unsuccessful response"
                    )
                    return False
            else:
                logger.error(
                    f"❌ Search performance recording failed: {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"❌ Search performance recording test failed: {e}")
            return False

    async def run_all_tests(self) -> Dict[str, bool]:
        """Run all vector health monitoring tests"""
        logger.info("🚀 Starting Vector Health Monitoring Test Suite")
        logger.info("=" * 60)

        tests = [
            ("Server Health", self.test_server_health),
            ("Vector Health Status", self.test_vector_health_status),
            ("Dashboard Data", self.test_dashboard_data),
            ("Collection Metrics", self.test_collection_metrics),
            ("Balance Metrics", self.test_balance_metrics),
            ("Routing Metrics", self.test_routing_metrics),
            ("Alerts Endpoint", self.test_alerts_endpoint),
            ("Thresholds Endpoint", self.test_thresholds_endpoint),
            ("Monitoring Control", self.test_monitoring_control),
            ("Record Routing Decision", self.test_record_routing_decision),
            ("Record Search Performance", self.test_record_search_performance),
        ]

        results = {}
        passed = 0
        total = len(tests)

        for test_name, test_func in tests:
            logger.info(f"\n📋 Running test: {test_name}")
            try:
                result = await test_func()
                results[test_name] = result
                if result:
                    passed += 1
            except Exception as e:
                logger.error(f"❌ Test {test_name} failed with exception: {e}")
                results[test_name] = False

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("📊 TEST SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Passed: {passed}/{total} tests")
        logger.info(f"Success Rate: {(passed/total)*100:.1f}%")

        if passed == total:
            logger.info(
                "🎉 All tests passed! Vector health monitoring system is working correctly."
            )
        elif passed >= total * 0.8:
            logger.info("⚠️  Most tests passed. Some minor issues detected.")
        else:
            logger.info(
                "❌ Multiple test failures. Vector health monitoring system needs attention."
            )

        # Detailed results
        logger.info("\nDetailed Results:")
        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"  {test_name}: {status}")

        return results

    def generate_test_report(self, results: Dict[str, bool]) -> str:
        """Generate a comprehensive test report"""
        report = []
        report.append("# Vector Health Monitoring Test Report")
        report.append(f"**Test Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"**Server URL:** {self.base_url}")
        report.append("")

        # Summary
        passed = sum(results.values())
        total = len(results)
        success_rate = (passed / total) * 100

        report.append("## Summary")
        report.append(f"- **Total Tests:** {total}")
        report.append(f"- **Passed:** {passed}")
        report.append(f"- **Failed:** {total - passed}")
        report.append(f"- **Success Rate:** {success_rate:.1f}%")
        report.append("")

        # Test Results
        report.append("## Test Results")
        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            report.append(f"- **{test_name}:** {status}")

        report.append("")

        # Collected Data Sample
        if self.test_results:
            report.append("## Sample Data Collected")
            if "dashboard_data" in self.test_results:
                dashboard = self.test_results["dashboard_data"]
                report.append(
                    f"- **Monitoring Status:** {dashboard.get('monitoring_status')}"
                )
                report.append(
                    f"- **Collections Monitored:** {len(dashboard.get('collections', {}))}"
                )
                report.append(
                    f"- **Active Alerts:** {len(dashboard.get('alerts', []))}"
                )

        report.append("")
        report.append("## Recommendations")

        if success_rate == 100:
            report.append(
                "✅ All systems operational. Vector health monitoring is working correctly."
            )
        elif success_rate >= 80:
            report.append(
                "⚠️ System mostly operational with minor issues. Review failed tests."
            )
        else:
            report.append(
                "❌ System has significant issues. Immediate attention required."
            )

        return "\n".join(report)


async def main():
    """Main test execution function"""
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = BASE_URL

    test_suite = VectorHealthTestSuite(base_url)

    try:
        # Run all tests
        results = await test_suite.run_all_tests()

        # Generate and save test report
        report = test_suite.generate_test_report(results)

        # Save report to file
        report_filename = f"vector_health_test_report_{int(time.time())}.md"
        with open(report_filename, "w") as f:
            f.write(report)

        logger.info(f"\n📄 Test report saved to: {report_filename}")

        # Exit with appropriate code
        passed = sum(results.values())
        total = len(results)

        if passed == total:
            sys.exit(0)  # All tests passed
        else:
            sys.exit(1)  # Some tests failed

    finally:
        await test_suite.close()


if __name__ == "__main__":
    asyncio.run(main())
