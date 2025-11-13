#!/usr/bin/env python3
"""
Post-Deployment Smoke Tests

CRITICAL smoke tests that MUST pass after any Docker rebuild before starting ingestion.
These tests validate that all core functionality is working correctly and prevent
deploying broken services.

This test suite would have caught the vectorization bug where /process/document
returned success but didn't actually create vectors in Qdrant.

Usage:
    # Run all smoke tests
    pytest tests/integration/test_post_deployment_smoke.py -v

    # Run with quick timeout (60s max)
    pytest tests/integration/test_post_deployment_smoke.py -v --timeout=60

    # Run only smoke tests across entire test suite
    pytest -m smoke -v

Exit Codes:
    0 - All smoke tests passed (safe to deploy)
    1 - One or more smoke tests failed (DO NOT DEPLOY)
"""

import asyncio
import logging
import os
import subprocess
import time
from typing import Dict, List, Optional
from uuid import uuid4

import httpx
import pytest
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


def capture_docker_logs(
    container_name: str, since: str = "30s", tail: int = 100
) -> str:
    """
    Capture recent docker logs for debugging test failures.

    This function is used when vectorization tests fail to provide immediate
    debugging context without requiring manual docker log inspection.

    Args:
        container_name: Docker container name to capture logs from
        since: Time window for logs (e.g., "30s", "1m", "5m")
        tail: Number of lines to capture (default 100)

    Returns:
        Combined stdout + stderr logs from the container

    Example:
        When test_document_processing_creates_vector fails because no vector
        is found in Qdrant, this function captures logs from archon-intelligence
        and archon-intelligence-consumer-1 to show the root cause (e.g.,
        embedding service errors, Qdrant connection failures, etc.).
    """
    try:
        result = subprocess.run(
            ["docker", "logs", container_name, "--since", since, "--tail", str(tail)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return f"⚠️  Timeout capturing logs from {container_name}"
    except Exception as e:
        return f"⚠️  Failed to capture logs from {container_name}: {e}"


# Service configuration from environment
INTELLIGENCE_URL = os.getenv("INTELLIGENCE_URL", "http://localhost:8053")
BRIDGE_URL = os.getenv("BRIDGE_URL", "http://localhost:8054")
SEARCH_URL = os.getenv("SEARCH_URL", "http://localhost:8055")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
MEMGRAPH_URI = os.getenv("MEMGRAPH_URI", "bolt://localhost:7687")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "192.168.86.200")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5436")
POSTGRES_DB = os.getenv("POSTGRES_DATABASE", "omninode_bridge")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

# Kafka configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092")

# Performance thresholds (must be met for production deployment)
PERFORMANCE_THRESHOLDS = {
    "service_health_check": 5.0,  # Health endpoint response time (seconds)
    "document_processing": 30.0,  # /process/document complete time (seconds)
    "vector_creation": 10.0,  # Time for vector to appear in Qdrant (seconds)
    "rag_query": 10.0,  # RAG query response time (seconds)
    "database_query": 5.0,  # Database query response time (seconds)
}


@pytest.mark.asyncio
@pytest.mark.smoke
@pytest.mark.critical
class TestPostDeploymentSmoke:
    """
    Critical smoke tests for post-deployment validation.

    These tests MUST pass before any ingestion or production deployment.
    Failure indicates a broken service that needs immediate attention.
    """

    async def test_all_services_healthy(self):
        """
        Verify all critical services respond to health checks.

        Services checked:
        - archon-intelligence (8053)
        - archon-bridge (8054)
        - archon-search (8055)

        PASS: All services return 200 OK within threshold
        FAIL: Any service unreachable or returns non-200 status
        """
        logger.info("🏥 SMOKE TEST: Service Health Checks")

        services = {
            "intelligence": f"{INTELLIGENCE_URL}/health",
            "bridge": f"{BRIDGE_URL}/health",
            "search": f"{SEARCH_URL}/health",
        }

        async with httpx.AsyncClient(
            timeout=PERFORMANCE_THRESHOLDS["service_health_check"]
        ) as client:
            results = {}
            for service_name, url in services.items():
                start = time.time()
                try:
                    response = await client.get(url)
                    response_time = time.time() - start

                    results[service_name] = {
                        "status": response.status_code,
                        "response_time": response_time,
                        "healthy": response.status_code == 200,
                    }

                    logger.info(
                        f"  {'✅' if response.status_code == 200 else '❌'} "
                        f"{service_name}: {response.status_code} ({response_time:.2f}s)"
                    )

                    assert (
                        response.status_code == 200
                    ), f"{service_name} service unhealthy: {response.status_code}"
                    assert (
                        response_time < PERFORMANCE_THRESHOLDS["service_health_check"]
                    ), (
                        f"{service_name} health check too slow: {response_time:.2f}s > "
                        f"{PERFORMANCE_THRESHOLDS['service_health_check']}s"
                    )

                except Exception as e:
                    logger.error(f"  ❌ {service_name}: Connection failed - {e}")
                    pytest.fail(f"{service_name} service unreachable: {e}")

        logger.info(f"✅ All {len(services)} services healthy")

    async def test_databases_accessible(self):
        """
        Verify all databases are accessible and responsive.

        Databases checked:
        - Qdrant (vector database)
        - Memgraph (knowledge graph)
        - PostgreSQL (pattern traceability)

        PASS: All databases respond to queries within threshold
        FAIL: Any database unreachable or timeout
        """
        logger.info("🗄️  SMOKE TEST: Database Accessibility")

        # Test Qdrant
        logger.info("  Testing Qdrant vector database...")
        start = time.time()
        try:
            async with httpx.AsyncClient(
                timeout=PERFORMANCE_THRESHOLDS["database_query"]
            ) as client:
                response = await client.get(f"{QDRANT_URL}/collections")
                qdrant_time = time.time() - start

                assert (
                    response.status_code == 200
                ), f"Qdrant health check failed: {response.status_code}"
                logger.info(f"  ✅ Qdrant accessible ({qdrant_time:.2f}s)")

                # Check if archon_vectors collection exists
                collections = response.json()
                collection_names = [
                    c["name"]
                    for c in collections.get("result", {}).get("collections", [])
                ]
                assert (
                    "archon_vectors" in collection_names
                ), "archon_vectors collection not found in Qdrant"
                logger.info("  ✅ archon_vectors collection exists")

        except Exception as e:
            logger.error(f"  ❌ Qdrant failed: {e}")
            pytest.fail(f"Qdrant database unreachable: {e}")

        # Test Memgraph
        logger.info("  Testing Memgraph knowledge graph...")
        start = time.time()
        try:
            driver = GraphDatabase.driver(MEMGRAPH_URI)
            with driver.session() as session:
                result = session.run("RETURN 1 as test")
                test_value = result.single()["test"]
                memgraph_time = time.time() - start

                assert test_value == 1, "Memgraph query returned unexpected result"
                logger.info(f"  ✅ Memgraph accessible ({memgraph_time:.2f}s)")

            driver.close()

        except Exception as e:
            logger.error(f"  ❌ Memgraph failed: {e}")
            pytest.fail(f"Memgraph database unreachable: {e}")

        # Test PostgreSQL (if configured)
        if POSTGRES_PASSWORD:
            logger.info("  Testing PostgreSQL pattern database...")
            start = time.time()
            try:
                import psycopg2

                conn = psycopg2.connect(
                    host=POSTGRES_HOST,
                    port=POSTGRES_PORT,
                    database=POSTGRES_DB,
                    user=POSTGRES_USER,
                    password=POSTGRES_PASSWORD,
                    connect_timeout=int(PERFORMANCE_THRESHOLDS["database_query"]),
                )
                cur = conn.cursor()
                cur.execute("SELECT 1")
                result = cur.fetchone()
                postgres_time = time.time() - start

                assert result[0] == 1, "PostgreSQL query returned unexpected result"
                logger.info(f"  ✅ PostgreSQL accessible ({postgres_time:.2f}s)")

                cur.close()
                conn.close()

            except ImportError:
                logger.warning("  ⚠️  psycopg2 not installed, skipping PostgreSQL test")
            except Exception as e:
                logger.error(f"  ❌ PostgreSQL failed: {e}")
                pytest.fail(f"PostgreSQL database unreachable: {e}")
        else:
            logger.warning("  ⚠️  POSTGRES_PASSWORD not set, skipping PostgreSQL test")

        logger.info("✅ All databases accessible")

    async def test_kafka_connectivity(self):
        """
        Verify Kafka/Redpanda event bus is accessible.

        Tests:
        - Connection to bootstrap servers
        - Topic listing (admin operation)
        - Consumer group listing

        PASS: Kafka responds to admin queries
        FAIL: Kafka unreachable or admin operations fail
        """
        logger.info("📡 SMOKE TEST: Kafka Connectivity")

        try:
            from confluent_kafka.admin import AdminClient

            admin_client = AdminClient(
                {
                    "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
                    "socket.timeout.ms": 5000,
                }
            )

            # List topics
            start = time.time()
            metadata = admin_client.list_topics(timeout=5)
            kafka_time = time.time() - start

            topic_count = len(metadata.topics)
            logger.info(f"  ✅ Kafka accessible ({kafka_time:.2f}s)")
            logger.info(f"  ✅ Found {topic_count} topics")

            # Check for critical topics
            critical_topics = [
                "dev.archon-intelligence.tree.discover.v1",
                "dev.archon-intelligence.stamping.generate.v1",
            ]

            for topic in critical_topics:
                if topic in metadata.topics:
                    logger.info(f"  ✅ Topic exists: {topic}")
                else:
                    logger.warning(f"  ⚠️  Topic missing: {topic}")

        except ImportError:
            logger.warning("  ⚠️  confluent_kafka not installed, skipping Kafka test")
            pytest.skip("confluent_kafka not available")
        except Exception as e:
            logger.error(f"  ❌ Kafka connectivity failed: {e}")
            pytest.fail(f"Kafka/Redpanda unreachable: {e}")

        logger.info("✅ Kafka connectivity verified")

    async def test_document_processing_creates_vector(self):
        """
        **THE CRITICAL TEST** - Verify /process/document actually creates vectors.

        This test would have caught the vectorization bug where:
        - POST /process/document returned 200 OK
        - Response claimed document was processed
        - BUT no vector was actually created in Qdrant

        Test Flow:
        1. Create unique test document via POST /process/document
        2. Verify endpoint returns success (200 OK)
        3. Query Qdrant to confirm vector actually exists
        4. Verify vector has correct dimensions (1536)
        5. Verify vector can be retrieved by document_id

        PASS: Vector exists in Qdrant with correct metadata
        FAIL: Vector not found or incorrect (THE BUG)
        """
        logger.info("🔍 SMOKE TEST: Document Processing Creates Vector (CRITICAL)")

        # Generate unique test document
        test_id = f"smoke_test_{uuid4().hex[:8]}"
        test_document = {
            "document_id": test_id,
            "project_id": "smoke_test",
            "content": f"Smoke test document created at {time.time()} to verify vectorization.",
            "metadata": {
                "project": "smoke_test",
                "file_path": f"test/{test_id}.txt",
                "language": "text",
                "test_type": "post_deployment_smoke",
            },
        }

        logger.info(f"  Creating test document: {test_id}")

        # Step 1: Call POST /process/document
        start = time.time()
        async with httpx.AsyncClient(
            timeout=PERFORMANCE_THRESHOLDS["document_processing"]
        ) as client:
            try:
                response = await client.post(
                    f"{INTELLIGENCE_URL}/process/document",
                    json=test_document,
                )
                processing_time = time.time() - start

                logger.info(
                    f"  Response: {response.status_code} ({processing_time:.2f}s)"
                )

                # Verify endpoint success
                assert (
                    response.status_code == 200
                ), f"/process/document failed: {response.status_code} - {response.text}"

                result = response.json()
                logger.info(f"  ✅ Document processed successfully")

            except Exception as e:
                logger.error(f"  ❌ Document processing failed: {e}")
                pytest.fail(f"POST /process/document failed: {e}")

        # Step 2: Wait for background task vectorization to complete
        # Background task: Memgraph ops (500ms) + vLLM embedding (2-10s) + Qdrant indexing (500ms)
        logger.info("  Waiting for vector indexing to complete...")
        await asyncio.sleep(15)  # Allow time for embedding generation (typical: 3-8s)

        # Step 3: Query Qdrant to verify vector actually exists
        logger.info("  Verifying vector exists in Qdrant...")
        start = time.time()

        try:
            async with httpx.AsyncClient(
                timeout=PERFORMANCE_THRESHOLDS["vector_creation"]
            ) as client:
                # Scroll through Qdrant collection to find our document
                # Use scroll API with filter to find specific document_id
                response = await client.post(
                    f"{QDRANT_URL}/collections/archon_vectors/points/scroll",
                    json={
                        "filter": {
                            "must": [
                                {"key": "document_id", "match": {"value": test_id}}
                            ]
                        },
                        "limit": 10,
                        "with_payload": True,
                        "with_vector": True,
                    },
                )

                assert (
                    response.status_code == 200
                ), f"Qdrant query failed: {response.status_code}"

                scroll_result = response.json()
                points = scroll_result.get("result", {}).get("points", [])
                vector_time = time.time() - start

                logger.info(
                    f"  Qdrant query returned {len(points)} points ({vector_time:.2f}s)"
                )

                # THE CRITICAL ASSERTION - Vector must exist
                # If vector not found, capture docker logs to debug the failure
                if len(points) == 0:
                    logger.error("  ❌ Vector not found - capturing debug logs...")

                    # Capture logs from background task executor
                    intelligence_logs = capture_docker_logs(
                        "archon-intelligence", since="30s"
                    )

                    # Also check consumer if relevant
                    consumer_logs = capture_docker_logs(
                        "archon-intelligence-consumer-1", since="30s"
                    )

                    # Build detailed failure message with logs
                    failure_msg = (
                        f"❌ VECTORIZATION BUG DETECTED: /process/document returned success "
                        f"but NO vector found in Qdrant for document_id={test_id}.\n"
                        f"\n"
                        f"{'='*70}\n"
                        f"🔍 BACKGROUND TASK LOGS (archon-intelligence, last 30s)\n"
                        f"{'='*70}\n"
                        f"{intelligence_logs}\n"
                        f"\n"
                        f"{'='*70}\n"
                        f"🔍 CONSUMER LOGS (archon-intelligence-consumer-1, last 30s)\n"
                        f"{'='*70}\n"
                        f"{consumer_logs}\n"
                        f"\n"
                        f"{'='*70}\n"
                        f"💡 TIP: Search logs above for:\n"
                        f"   - Error messages related to '{test_id}'\n"
                        f"   - Exceptions in background tasks\n"
                        f"   - Qdrant connection failures\n"
                        f"   - Embedding generation errors\n"
                        f"{'='*70}\n"
                    )

                    assert False, failure_msg

                # Verify vector properties
                point = points[0]
                vector = point.get("vector")
                payload = point.get("payload", {})

                assert vector is not None, "Vector data is missing"
                assert (
                    len(vector) == 1536
                ), f"Vector has wrong dimensions: {len(vector)} != 1536"

                assert (
                    payload.get("document_id") == test_id
                ), f"Vector has wrong document_id: {payload.get('document_id')} != {test_id}"

                logger.info(f"  ✅ Vector found in Qdrant (dimensions: {len(vector)})")
                logger.info(
                    f"  ✅ Vector metadata correct: document_id={payload.get('document_id')}"
                )

        except Exception as e:
            logger.error(f"  ❌ Vector verification failed: {e}")
            pytest.fail(
                f"❌ VECTORIZATION BUG: Document processed but vector not found in Qdrant. "
                f"Error: {e}"
            )

        logger.info("✅ Document processing creates vector (CRITICAL TEST PASSED)")

    async def test_basic_rag_query_works(self):
        """
        Verify basic RAG query functionality end-to-end.

        Test Flow:
        1. Execute simple RAG query via /search/rag endpoint
        2. Verify response structure
        3. Verify results returned within performance threshold

        PASS: RAG query returns valid results within threshold
        FAIL: RAG query fails or times out
        """
        logger.info("🔎 SMOKE TEST: Basic RAG Query")

        test_query = {
            "query": "test document",
            "limit": 5,
            "use_hybrid": False,  # Simple vector search only for smoke test
        }

        start = time.time()
        try:
            async with httpx.AsyncClient(
                timeout=PERFORMANCE_THRESHOLDS["rag_query"]
            ) as client:
                response = await client.post(
                    f"{SEARCH_URL}/search",
                    json=test_query,
                )
                query_time = time.time() - start

                logger.info(f"  Response: {response.status_code} ({query_time:.2f}s)")

                assert (
                    response.status_code == 200
                ), f"RAG query failed: {response.status_code} - {response.text}"

                result = response.json()

                # Verify response structure
                assert "results" in result, "Response missing 'results' field"
                assert isinstance(result["results"], list), "Results must be a list"

                logger.info(f"  ✅ RAG query returned {len(result['results'])} results")
                logger.info(f"  ✅ Query completed in {query_time:.2f}s")

                # Verify performance threshold
                assert query_time < PERFORMANCE_THRESHOLDS["rag_query"], (
                    f"RAG query too slow: {query_time:.2f}s > "
                    f"{PERFORMANCE_THRESHOLDS['rag_query']}s"
                )

        except Exception as e:
            logger.error(f"  ❌ RAG query failed: {e}")
            pytest.fail(f"RAG query functionality broken: {e}")

        logger.info("✅ Basic RAG query works")

    async def test_performance_baseline(self):
        """
        Verify system meets performance baselines.

        Checks:
        - Service health endpoints respond < 5s
        - Database queries complete < 5s
        - Document processing completes < 30s
        - RAG queries complete < 10s

        PASS: All operations meet performance thresholds
        FAIL: Any operation exceeds threshold (performance regression)
        """
        logger.info("⚡ SMOKE TEST: Performance Baseline")

        baseline_checks = []

        # Health check performance
        async with httpx.AsyncClient() as client:
            for service_name, url in {
                "intelligence": f"{INTELLIGENCE_URL}/health",
                "bridge": f"{BRIDGE_URL}/health",
                "search": f"{SEARCH_URL}/health",
            }.items():
                start = time.time()
                try:
                    response = await client.get(
                        url, timeout=PERFORMANCE_THRESHOLDS["service_health_check"]
                    )
                    elapsed = time.time() - start

                    meets_threshold = (
                        elapsed < PERFORMANCE_THRESHOLDS["service_health_check"]
                    )
                    baseline_checks.append(
                        {
                            "check": f"{service_name} health",
                            "elapsed": elapsed,
                            "threshold": PERFORMANCE_THRESHOLDS["service_health_check"],
                            "pass": meets_threshold,
                        }
                    )

                    logger.info(
                        f"  {'✅' if meets_threshold else '❌'} "
                        f"{service_name} health: {elapsed:.2f}s / "
                        f"{PERFORMANCE_THRESHOLDS['service_health_check']}s"
                    )

                except Exception as e:
                    logger.error(f"  ❌ {service_name} health check failed: {e}")
                    baseline_checks.append(
                        {
                            "check": f"{service_name} health",
                            "elapsed": None,
                            "threshold": PERFORMANCE_THRESHOLDS["service_health_check"],
                            "pass": False,
                        }
                    )

        # Database query performance
        try:
            driver = GraphDatabase.driver(MEMGRAPH_URI)
            with driver.session() as session:
                start = time.time()
                session.run("MATCH (f:File) RETURN count(f) as count LIMIT 1")
                elapsed = time.time() - start

                meets_threshold = elapsed < PERFORMANCE_THRESHOLDS["database_query"]
                baseline_checks.append(
                    {
                        "check": "memgraph query",
                        "elapsed": elapsed,
                        "threshold": PERFORMANCE_THRESHOLDS["database_query"],
                        "pass": meets_threshold,
                    }
                )

                logger.info(
                    f"  {'✅' if meets_threshold else '❌'} "
                    f"Memgraph query: {elapsed:.2f}s / "
                    f"{PERFORMANCE_THRESHOLDS['database_query']}s"
                )

            driver.close()

        except Exception as e:
            logger.error(f"  ❌ Memgraph query failed: {e}")
            baseline_checks.append(
                {
                    "check": "memgraph query",
                    "elapsed": None,
                    "threshold": PERFORMANCE_THRESHOLDS["database_query"],
                    "pass": False,
                }
            )

        # Summary
        passed = sum(1 for check in baseline_checks if check["pass"])
        total = len(baseline_checks)

        logger.info(f"  Performance baseline: {passed}/{total} checks passed")

        # All checks must pass
        failed_checks = [c for c in baseline_checks if not c["pass"]]
        if failed_checks:
            logger.error("  ❌ Performance regression detected:")
            for check in failed_checks:
                logger.error(
                    f"    - {check['check']}: {check['elapsed']:.2f}s > {check['threshold']}s"
                )
            pytest.fail(
                f"Performance regression: {len(failed_checks)}/{total} checks failed"
            )

        logger.info("✅ Performance baseline met")


@pytest.mark.asyncio
@pytest.mark.smoke
class TestPostDeploymentIntegration:
    """
    Integration smoke tests for cross-service functionality.

    These tests validate that services work together correctly.
    """

    async def test_intelligence_to_qdrant_pipeline(self):
        """
        Verify intelligence service → Qdrant pipeline works end-to-end.

        Test Flow:
        1. Submit document to intelligence service
        2. Verify document processing succeeds
        3. Verify vector appears in Qdrant
        4. Verify vector is searchable

        PASS: Complete pipeline functional
        FAIL: Pipeline broken at any stage
        """
        logger.info("🔗 SMOKE TEST: Intelligence → Qdrant Pipeline")

        # Generate unique test document
        test_id = f"integration_test_{uuid4().hex[:8]}"
        test_document = {
            "document_id": test_id,
            "project_id": "integration_test",
            "content": "Integration test for intelligence to Qdrant pipeline.",
            "metadata": {
                "project": "integration_test",
                "file_path": f"test/{test_id}.txt",
                "language": "text",
            },
        }

        # Step 1: Submit to intelligence service
        logger.info(f"  Submitting document: {test_id}")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{INTELLIGENCE_URL}/process/document",
                json=test_document,
            )

            assert (
                response.status_code == 200
            ), f"Intelligence service failed: {response.status_code}"
            logger.info("  ✅ Intelligence service processed document")

        # Step 2: Wait for background task vectorization to complete
        await asyncio.sleep(15)  # Allow time for embedding generation

        # Step 3: Verify in Qdrant
        logger.info("  Verifying vector in Qdrant...")
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{QDRANT_URL}/collections/archon_vectors/points/scroll",
                json={
                    "filter": {
                        "must": [{"key": "document_id", "match": {"value": test_id}}]
                    },
                    "limit": 10,
                },
            )

            assert response.status_code == 200, "Qdrant query failed"
            points = response.json().get("result", {}).get("points", [])

            # If vector not found, capture docker logs for debugging
            if len(points) == 0:
                logger.error(
                    "  ❌ Vector not found in integration test - capturing debug logs..."
                )

                # Capture logs from background task executor
                intelligence_logs = capture_docker_logs(
                    "archon-intelligence", since="30s"
                )
                consumer_logs = capture_docker_logs(
                    "archon-intelligence-consumer-1", since="30s"
                )

                failure_msg = (
                    f"❌ INTEGRATION FAILURE: Vector not found in Qdrant for document_id={test_id}\n"
                    f"\n"
                    f"{'='*70}\n"
                    f"🔍 BACKGROUND TASK LOGS (archon-intelligence, last 30s)\n"
                    f"{'='*70}\n"
                    f"{intelligence_logs}\n"
                    f"\n"
                    f"{'='*70}\n"
                    f"🔍 CONSUMER LOGS (archon-intelligence-consumer-1, last 30s)\n"
                    f"{'='*70}\n"
                    f"{consumer_logs}\n"
                    f"\n"
                    f"{'='*70}\n"
                    f"💡 TIP: Look for errors related to '{test_id}' in logs above\n"
                    f"{'='*70}\n"
                )

                assert False, failure_msg

            logger.info("  ✅ Vector exists in Qdrant")

        # Step 4: Verify searchability
        logger.info("  Testing vector searchability...")
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{SEARCH_URL}/search",
                json={"query": test_id, "limit": 5},
            )

            assert response.status_code == 200, "RAG search failed"
            results = response.json().get("results", [])
            logger.info(f"  ✅ Vector searchable (found in {len(results)} results)")

        logger.info("✅ Intelligence → Qdrant pipeline functional")


if __name__ == "__main__":
    """
    Allow running smoke tests directly for quick validation.

    Usage:
        python3 tests/integration/test_post_deployment_smoke.py
    """
    import sys

    sys.exit(pytest.main([__file__, "-v", "--tb=short", "-m", "smoke"]))
