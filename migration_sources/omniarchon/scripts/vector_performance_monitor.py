#!/usr/bin/env python3
"""
Vector Routing Performance Monitor

This script establishes comprehensive performance baselines and monitoring
for the vector routing system optimization project.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List

import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VectorPerformanceMonitor:
    """Comprehensive vector routing performance monitoring and baseline establishment"""

    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        search_service_url: str = "http://localhost:8055",
        main_server_url: str = "http://localhost:8181",
    ):
        self.qdrant_url = qdrant_url.rstrip("/")
        self.search_service_url = search_service_url.rstrip("/")
        self.main_server_url = main_server_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def establish_performance_baseline(self) -> Dict[str, Any]:
        """Establish comprehensive performance baseline metrics"""
        logger.info("🚀 Establishing Vector Routing Performance Baseline")

        baseline = {
            "timestamp": datetime.now().isoformat(),
            "collection_metrics": {},
            "service_health": {},
            "performance_measurements": {},
            "routing_analysis": {},
            "recommendations": [],
        }

        # 1. Collection Balance Analysis
        baseline["collection_metrics"] = await self._analyze_collection_balance()

        # 2. Service Health Assessment
        baseline["service_health"] = await self._assess_service_health()

        # 3. Performance Measurements
        baseline["performance_measurements"] = await self._measure_performance()

        # 4. Routing Analysis
        baseline["routing_analysis"] = await self._analyze_routing_performance()

        # 5. Generate Recommendations
        baseline["recommendations"] = self._generate_recommendations(baseline)

        return baseline

    async def _analyze_collection_balance(self) -> Dict[str, Any]:
        """Analyze Qdrant collection balance and configuration"""
        logger.info("📊 Analyzing collection balance...")

        try:
            # Get cluster info
            cluster_response = await self.client.get(
                f"{self.qdrant_url}/collections/archon_vectors/cluster"
            )

            # Get collection info
            collection_response = await self.client.get(
                f"{self.qdrant_url}/collections/archon_vectors"
            )

            if (
                cluster_response.status_code == 200
                and collection_response.status_code == 200
            ):
                cluster_data = cluster_response.json()["result"]
                collection_data = collection_response.json()["result"]

                # Calculate balance metrics
                local_shards = cluster_data.get("local_shards", [])
                total_points = sum(
                    shard.get("points_count", 0) for shard in local_shards
                )

                balance_analysis = {
                    "total_vectors": total_points,
                    "shard_count": cluster_data.get("shard_count", 0),
                    "local_shards": local_shards,
                    "remote_shards": cluster_data.get("remote_shards", []),
                    "balance_ratio": self._calculate_balance_ratio(local_shards),
                    "collection_config": collection_data.get("config", {}),
                    "status": "healthy" if total_points > 0 else "empty",
                }

                logger.info(
                    f"✅ Collection analysis: {total_points} vectors across {len(local_shards)} shards"
                )
                return balance_analysis
            else:
                logger.error(
                    f"❌ Collection analysis failed: {cluster_response.status_code}"
                )
                return {"status": "failed", "error": "Collection not accessible"}

        except Exception as e:
            logger.error(f"❌ Collection analysis error: {e}")
            return {"status": "error", "error": str(e)}

    def _calculate_balance_ratio(self, shards: List[Dict]) -> float:
        """Calculate collection balance ratio"""
        if not shards or len(shards) <= 1:
            return 1.0  # Perfect imbalance if single shard

        counts = [shard.get("points_count", 0) for shard in shards]
        if not counts or sum(counts) == 0:
            return 0.0

        # Balance ratio: 1.0 = perfectly balanced, 0.0 = completely unbalanced
        avg_count = sum(counts) / len(counts)
        variance = sum((count - avg_count) ** 2 for count in counts) / len(counts)
        coefficient_of_variation = (variance**0.5) / avg_count if avg_count > 0 else 1.0

        # Convert to balance ratio (0-1, where 1 is perfectly balanced)
        return max(0.0, 1.0 - coefficient_of_variation)

    async def _assess_service_health(self) -> Dict[str, Any]:
        """Assess health of all vector routing services"""
        logger.info("🩺 Assessing service health...")

        service_health = {}

        # Test Qdrant direct
        service_health["qdrant"] = await self._test_service_health(
            f"{self.qdrant_url}/collections", "Qdrant Direct"
        )

        # Test Search Service
        service_health["search_service"] = await self._test_service_health(
            f"{self.search_service_url}/health", "Search Service"
        )

        # Test Main Server
        service_health["main_server"] = await self._test_service_health(
            f"{self.main_server_url}/health", "Main Server"
        )

        return service_health

    async def _test_service_health(self, url: str, service_name: str) -> Dict[str, Any]:
        """Test individual service health"""
        try:
            start_time = time.time()
            response = await self.client.get(url)
            end_time = time.time()

            health_status = {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "response_time_ms": round((end_time - start_time) * 1000, 2),
                "status_code": response.status_code,
                "service": service_name,
            }

            logger.info(
                f"✅ {service_name}: {health_status['status']} ({health_status['response_time_ms']}ms)"
            )
            return health_status

        except Exception as e:
            logger.error(f"❌ {service_name} health check failed: {e}")
            return {"status": "error", "error": str(e), "service": service_name}

    async def _measure_performance(self) -> Dict[str, Any]:
        """Measure current performance across all services"""
        logger.info("⚡ Measuring performance...")

        performance_tests = {
            "direct_qdrant": await self._test_direct_qdrant_performance(),
            "search_service": await self._test_search_service_performance(),
            "end_to_end": await self._test_end_to_end_performance(),
        }

        return performance_tests

    async def _test_direct_qdrant_performance(self) -> Dict[str, Any]:
        """Test direct Qdrant query performance"""
        try:
            # Create test query with dummy vector
            dummy_vector = [0.1] * 1536

            start_time = time.time()
            response = await self.client.post(
                f"{self.qdrant_url}/collections/archon_vectors/points/search",
                json={
                    "vector": dummy_vector,
                    "limit": 5,
                    "with_payload": True,
                    "with_vectors": False,
                },
            )
            end_time = time.time()

            if response.status_code == 200:
                data = response.json()
                results = data.get("result", [])
                avg_score = (
                    sum(r.get("score", 0) for r in results) / len(results)
                    if results
                    else 0
                )

                return {
                    "status": "success",
                    "response_time_ms": round((end_time - start_time) * 1000, 2),
                    "results_count": len(results),
                    "average_relevance_score": round(avg_score, 4),
                    "min_score": (
                        min(r.get("score", 0) for r in results) if results else 0
                    ),
                    "max_score": (
                        max(r.get("score", 0) for r in results) if results else 0
                    ),
                }
            else:
                return {"status": "failed", "error": f"HTTP {response.status_code}"}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _test_search_service_performance(self) -> Dict[str, Any]:
        """Test search service performance"""
        try:
            start_time = time.time()
            response = await self.client.post(
                f"{self.search_service_url}/search",
                json={
                    "query": "authentication API tokens",
                    "mode": "hybrid",
                    "limit": 5,
                    "include_content": True,
                },
            )
            end_time = time.time()

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                total_results = data.get("total_results", 0)
                avg_score = (
                    sum(r.get("relevance_score", 0) for r in results) / len(results)
                    if results
                    else 0
                )

                return {
                    "status": "success",
                    "response_time_ms": round((end_time - start_time) * 1000, 2),
                    "results_count": len(results),
                    "total_results": total_results,
                    "average_relevance_score": round(avg_score, 4),
                    "scores_in_target_range": len(
                        [r for r in results if r.get("relevance_score", 0) >= 0.7]
                    ),
                }
            else:
                return {"status": "failed", "error": f"HTTP {response.status_code}"}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _test_end_to_end_performance(self) -> Dict[str, Any]:
        """Test end-to-end performance through main server"""
        try:
            start_time = time.time()
            response = await self.client.post(
                f"{self.main_server_url}/api/rag/query",
                json={
                    "query": "authentication API tokens",
                    "match_count": 5,
                    "context": "general",
                },
            )
            end_time = time.time()

            if response.status_code == 200:
                data = response.json()
                # Extract results from orchestrated response
                results_count = 0
                if "results" in data and isinstance(data["results"], dict):
                    for service_data in data["results"].values():
                        if isinstance(service_data, dict) and "results" in service_data:
                            results_count += len(service_data["results"])

                return {
                    "status": "success",
                    "response_time_ms": round((end_time - start_time) * 1000, 2),
                    "results_count": results_count,
                    "orchestrated_services": len(data.get("results", {})),
                }
            else:
                return {"status": "failed", "error": f"HTTP {response.status_code}"}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _analyze_routing_performance(self) -> Dict[str, Any]:
        """Analyze routing performance and identify bottlenecks"""
        logger.info("🔀 Analyzing routing performance...")

        # Simulate routing analysis based on service health and performance
        routing_analysis = {
            "bottlenecks_identified": [],
            "performance_issues": [],
            "routing_efficiency": "unknown",
            "recommendations": [],
        }

        # This would be expanded with actual routing analysis
        routing_analysis["analysis_note"] = (
            "Routing analysis framework established. Detailed analysis pending MCP routing fix."
        )

        return routing_analysis

    def _generate_recommendations(self, baseline: Dict[str, Any]) -> List[str]:
        """Generate performance optimization recommendations"""
        recommendations = []

        # Collection balance recommendations
        collection_metrics = baseline.get("collection_metrics", {})
        if collection_metrics.get("shard_count", 0) == 1:
            recommendations.append(
                "🔧 Consider resharding collection to multiple shards for load distribution"
            )

        # Service health recommendations
        service_health = baseline.get("service_health", {})
        for service, health in service_health.items():
            if health.get("status") != "healthy":
                recommendations.append(f"🚨 Fix {service} service health issues")

        # Performance recommendations
        performance = baseline.get("performance_measurements", {})
        direct_qdrant = performance.get("direct_qdrant", {})
        if direct_qdrant.get("average_relevance_score", 0) < 0.7:
            recommendations.append(
                "📈 Investigate low relevance scores in direct Qdrant queries"
            )

        search_service = performance.get("search_service", {})
        if (
            search_service.get("status") == "success"
            and search_service.get("average_relevance_score", 0) >= 0.7
        ):
            recommendations.append(
                "✅ Search service performing well - use as reference for optimization"
            )

        if not recommendations:
            recommendations.append(
                "📊 Baseline established - ready for optimization implementation"
            )

        return recommendations

    async def generate_monitoring_dashboard(
        self, baseline: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate monitoring dashboard configuration"""
        logger.info("📊 Generating monitoring dashboard...")

        dashboard = {
            "metrics": {
                "response_time_targets": {
                    "direct_qdrant": "<10ms",
                    "search_service": "<100ms",
                    "end_to_end": "<1000ms",
                },
                "relevance_score_targets": {"minimum": 0.7, "target_average": 0.8},
                "collection_balance_targets": {
                    "balance_ratio": ">0.8",
                    "max_shard_deviation": "<20%",
                },
            },
            "alerts": {
                "critical": [
                    "Service health check failures",
                    "Response time >2000ms",
                    "Relevance score <0.5",
                ],
                "warning": [
                    "Response time >1000ms",
                    "Relevance score <0.7",
                    "Collection balance ratio <0.6",
                ],
            },
            "current_baseline": baseline,
            "dashboard_url": "http://localhost:3737/performance-dashboard",
        }

        return dashboard

    async def run_comprehensive_analysis(self) -> Dict[str, Any]:
        """Run comprehensive performance analysis and monitoring setup"""
        logger.info("\n🚀 Starting Comprehensive Vector Routing Performance Analysis")

        # Establish baseline
        baseline = await self.establish_performance_baseline()

        # Generate monitoring dashboard
        dashboard = await self.generate_monitoring_dashboard(baseline)

        # Create final report
        report = {
            "analysis_timestamp": datetime.now().isoformat(),
            "baseline_metrics": baseline,
            "monitoring_dashboard": dashboard,
            "success_metrics_framework": {
                "tier_1_critical": {
                    "mcp_routing_success_rate": ">99%",
                    "response_time_p95": "<1000ms",
                    "relevance_score_minimum": ">0.7",
                },
                "tier_2_performance": {
                    "collection_balance_ratio": "0.4-0.6",
                    "concurrent_query_capacity": ">100 req/sec",
                    "error_rate": "<0.1%",
                },
                "tier_3_optimization": {
                    "cache_hit_ratio": ">80%",
                    "memory_utilization": "<70%",
                    "query_latency_p99": "<2000ms",
                },
            },
            "validation_framework": {
                "pre_fix_baseline": baseline,
                "post_fix_validation_tests": [
                    "MCP routing success rate test",
                    "End-to-end performance validation",
                    "Collection balance optimization verification",
                    "Relevance score improvement validation",
                ],
            },
        }

        return report

    async def close(self):
        """Clean up resources"""
        await self.client.aclose()


async def main():
    """Main function to run performance baseline analysis"""
    monitor = VectorPerformanceMonitor()

    try:
        report = await monitor.run_comprehensive_analysis()

        # Save report
        output_file = f"vector_performance_baseline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w") as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"\n💾 Performance baseline report saved to: {output_file}")

        # Print summary
        baseline = report["baseline_metrics"]
        collection_metrics = baseline.get("collection_metrics", {})
        performance_measurements = baseline.get("performance_measurements", {})

        logger.info("\n📋 PERFORMANCE BASELINE SUMMARY:")
        logger.info(
            f"  - Collection vectors: {collection_metrics.get('total_vectors', 'unknown')}"
        )
        logger.info(
            f"  - Collection shards: {collection_metrics.get('shard_count', 'unknown')}"
        )
        logger.info(
            f"  - Balance ratio: {collection_metrics.get('balance_ratio', 'unknown'):.2f}"
        )

        if performance_measurements:
            for test_name, results in performance_measurements.items():
                if isinstance(results, dict) and results.get("status") == "success":
                    response_time = results.get("response_time_ms", "unknown")
                    relevance = results.get("average_relevance_score", "unknown")
                    logger.info(
                        f"  - {test_name}: {response_time}ms, relevance: {relevance}"
                    )

        recommendations = baseline.get("recommendations", [])
        if recommendations:
            logger.info("\n💡 KEY RECOMMENDATIONS:")
            for rec in recommendations[:5]:  # Show top 5
                logger.info(f"  {rec}")

        logger.info(
            "\n✅ Vector routing performance baseline established successfully!"
        )

    except Exception as e:
        logger.error(f"❌ Performance analysis failed: {e}")
        return 1
    finally:
        await monitor.close()

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(main()))
