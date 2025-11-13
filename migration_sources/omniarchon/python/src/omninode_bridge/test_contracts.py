#!/usr/bin/env python3
"""
Quick test script to verify API contracts work with Intelligence Service.

This script performs a simple integration test to ensure:
1. Models serialize/deserialize correctly
2. HTTP client connects successfully
3. All three API contracts work end-to-end
"""

import asyncio
import logging
import sys

from src.omninode_bridge.clients.client_intelligence_service import (
    IntelligenceServiceClient,
)
from src.omninode_bridge.models.model_intelligence_api_contracts import (
    ModelPatternDetectionRequest,
    ModelPerformanceAnalysisRequest,
    ModelQualityAssessmentRequest,
    PatternCategory,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_health_check():
    """Test health check endpoint."""
    logger.info("=" * 60)
    logger.info("Test 1: Health Check")
    logger.info("=" * 60)

    async with IntelligenceServiceClient() as client:
        try:
            health = await client.check_health()
            logger.info(f"✓ Health check passed: {health.status}")
            logger.info(f"  Memgraph: {health.memgraph_connected}")
            logger.info(f"  Ollama: {health.ollama_connected}")
            logger.info(f"  Version: {health.service_version}")
            return True
        except Exception as e:
            logger.error(f"✗ Health check failed: {e}")
            return False


async def test_quality_assessment():
    """Test code quality assessment API."""
    logger.info("\n" + "=" * 60)
    logger.info("Test 2: Code Quality Assessment")
    logger.info("=" * 60)

    async with IntelligenceServiceClient() as client:
        try:
            request = ModelQualityAssessmentRequest(
                content="def hello():\n    pass",
                source_path="test.py",
                language="python",
            )

            response = await client.assess_code_quality(request)

            logger.info(f"✓ Quality assessment completed")
            logger.info(f"  Quality Score: {response.quality_score:.2f}")
            logger.info(f"  ONEX Compliance: {response.onex_compliance.score:.2f}")
            logger.info(f"  Architectural Era: {response.architectural_era}")
            return True

        except Exception as e:
            logger.error(f"✗ Quality assessment failed: {e}")
            return False


async def test_performance_analysis():
    """Test performance analysis API."""
    logger.info("\n" + "=" * 60)
    logger.info("Test 3: Performance Analysis")
    logger.info("=" * 60)

    async with IntelligenceServiceClient() as client:
        try:
            request = ModelPerformanceAnalysisRequest(
                operation_name="test_operation",
                code_content="def test():\n    pass",
            )

            response = await client.analyze_performance(request)

            logger.info(f"✓ Performance analysis completed")
            logger.info(f"  Operation: {response.operation_name}")
            logger.info(f"  Source: {response.source}")
            logger.info(
                f"  Average Response Time: {response.average_response_time_ms:.2f}ms"
            )
            logger.info(f"  P50: {response.p50_ms:.2f}ms")
            logger.info(f"  P95: {response.p95_ms:.2f}ms")
            logger.info(f"  P99: {response.p99_ms:.2f}ms")
            logger.info(f"  Sample Size: {response.sample_size}")
            if response.quality_score:
                logger.info(f"  Quality Score: {response.quality_score:.2f}")
            if response.message:
                logger.info(f"  Message: {response.message}")
            return True

        except Exception as e:
            logger.error(f"✗ Performance analysis failed: {e}")
            return False


async def test_pattern_detection():
    """Test pattern detection API."""
    logger.info("\n" + "=" * 60)
    logger.info("Test 4: Pattern Detection")
    logger.info("=" * 60)

    async with IntelligenceServiceClient() as client:
        try:
            request = ModelPatternDetectionRequest(
                content="def hello():\n    pass",
                source_path="test.py",
                pattern_categories=[PatternCategory.BEST_PRACTICES],
            )

            response = await client.detect_patterns(request)

            logger.info(f"✓ Pattern detection completed")
            logger.info(f"  Patterns Found: {len(response.detected_patterns)}")
            logger.info(
                f"  Overall Confidence: {response.confidence_scores.get('overall_confidence', 0.0):.2f}"
            )
            return True

        except Exception as e:
            logger.error(f"✗ Pattern detection failed: {e}")
            return False


async def test_client_metrics():
    """Test client metrics tracking."""
    logger.info("\n" + "=" * 60)
    logger.info("Test 5: Client Metrics")
    logger.info("=" * 60)

    async with IntelligenceServiceClient() as client:
        # Execute a few requests
        for i in range(3):
            try:
                request = ModelQualityAssessmentRequest(
                    content=f"def func_{i}(): pass",
                    source_path=f"test_{i}.py",
                )
                await client.assess_code_quality(request)
            except Exception as e:
                logger.warning(
                    f"Quality assessment request failed during metrics warmup: {e}"
                )

        # Get metrics
        metrics = client.get_metrics()

        logger.info(f"✓ Metrics collection working")
        logger.info(f"  Total Requests: {metrics['total_requests']}")
        logger.info(f"  Success Rate: {metrics['success_rate']:.2%}")
        logger.info(f"  Avg Duration: {metrics['avg_duration_ms']:.2f}ms")
        logger.info(f"  Circuit Breaker: {metrics['circuit_breaker_state']}")
        return True


async def run_all_tests():
    """Run all integration tests."""
    logger.info("\n" + "=" * 80)
    logger.info("API Contract Integration Tests")
    logger.info("=" * 80)

    results = []

    # Run tests
    results.append(("Health Check", await test_health_check()))
    results.append(("Quality Assessment", await test_quality_assessment()))
    results.append(("Performance Analysis", await test_performance_analysis()))
    results.append(("Pattern Detection", await test_pattern_detection()))
    results.append(("Client Metrics", await test_client_metrics()))

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("Test Summary")
    logger.info("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {test_name}")

    logger.info(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        logger.info("\n✓ All tests passed!")
        return 0
    else:
        logger.error(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
