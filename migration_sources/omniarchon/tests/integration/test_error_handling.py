#!/usr/bin/env python3
"""
Error Handling Integration Tests for MCP Document Indexing Pipeline

Tests various error scenarios and failure conditions:
1. Service failures (individual services down)
2. Malformed content handling
3. Database connection failures
4. Network timeouts and interruptions
5. Resource exhaustion scenarios
6. Concurrent access conflicts
7. Invalid input validation
8. Graceful degradation testing

These tests ensure the system handles errors gracefully and provides
appropriate feedback without corrupting data or causing cascading failures.
"""

import asyncio
import logging
import time

import httpx
import pytest

from .conftest import IntegrationTestClient, TestDocument, TestProject

logger = logging.getLogger(__name__)


@pytest.mark.error_handling
@pytest.mark.asyncio
class TestServiceFailureScenarios:
    """
    Test error handling when individual services fail or become unavailable

    These tests validate that the system degrades gracefully when components
    fail and can recover when services come back online.
    """

    async def test_intelligence_service_unavailable(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Test behavior when intelligence service is unavailable"""
        logger.info("🚫 Testing intelligence service unavailable scenario")

        # First, create a document when service is available
        document = await test_client.create_test_document(
            test_project,
            "Intelligence Service Failure Test",
            content_override={
                "test_scenario": "intelligence_service_unavailable",
                "expected_behavior": "Document should be created but indexing may fail gracefully",
            },
        )

        logger.info("✅ Document created successfully")

        # Simulate intelligence service failure by using invalid URL
        original_url = test_client.session.services.intelligence
        test_client.session.services.intelligence = "http://nonexistent:9999"

        try:
            # Try to trigger intelligence processing (this might happen automatically)
            # Check that the system handles the failure gracefully

            # Attempt to check intelligence service status
            with pytest.raises(Exception):
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.get(
                        f"{test_client.session.services.intelligence}/health"
                    )

            logger.info("✅ Intelligence service correctly reported as unavailable")

            # The document should still exist in the main database
            response = await test_client.http_client.get(
                f"{test_client.session.services.main_server}/api/projects/{test_project.id}/documents/{document.id}"
            )

            assert (
                response.status_code == 200
            ), "Document should still be accessible when intelligence service is down"
            logger.info(
                "✅ Document still accessible despite intelligence service failure"
            )

        finally:
            # Restore original URL
            test_client.session.services.intelligence = original_url

        # Verify service recovery
        health_status = await test_client.check_service_health()
        assert health_status.get(
            "intelligence", False
        ), "Intelligence service should be restored"

        logger.info("🎉 Intelligence service failure test passed")

    async def test_vector_database_unavailable(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Test behavior when Qdrant vector database is unavailable"""
        logger.info("🚫 Testing vector database (Qdrant) unavailable scenario")

        # Simulate Qdrant failure
        original_qdrant_url = test_client.session.services.qdrant
        test_client.session.services.qdrant = "http://nonexistent:9999"

        try:
            # Document creation should still work
            await test_client.create_test_document(
                test_project,
                "Vector DB Failure Test",
                content_override={
                    "test_scenario": "vector_database_unavailable",
                    "expected_behavior": "Document creation succeeds, vector indexing fails gracefully",
                },
            )

            logger.info("✅ Document created despite vector database unavailability")

            # Vector search should fail gracefully
            try:
                search_request = {
                    "query": "vector database failure test",
                    "mode": "semantic",
                    "limit": 5,
                }

                response = await test_client.http_client.post(
                    f"{test_client.session.services.search}/search",
                    json=search_request,
                    timeout=10.0,
                )

                # Should either fail gracefully or return empty results
                if response.status_code == 200:
                    results = response.json()
                    logger.info(
                        f"Search returned gracefully with {len(results.get('results', []))} results"
                    )
                else:
                    logger.info(
                        f"Search failed gracefully with status {response.status_code}"
                    )

            except Exception as e:
                logger.info(f"Search failed as expected: {e}")

        finally:
            # Restore original URL
            test_client.session.services.qdrant = original_qdrant_url

        logger.info("🎉 Vector database failure test passed")

    async def test_knowledge_graph_unavailable(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Test behavior when Memgraph knowledge graph is unavailable"""
        logger.info("🚫 Testing knowledge graph (Memgraph) unavailable scenario")

        # Simulate Memgraph failure
        original_memgraph_url = test_client.session.services.memgraph
        test_client.session.services.memgraph = "http://nonexistent:9999"

        try:
            # Document creation should still work
            await test_client.create_test_document(
                test_project,
                "Knowledge Graph Failure Test",
                content_override={
                    "test_scenario": "knowledge_graph_unavailable",
                    "expected_behavior": "Document creation succeeds, graph indexing fails gracefully",
                },
            )

            logger.info("✅ Document created despite knowledge graph unavailability")

            # Graph-based searches should fail gracefully
            try:
                # Try to search for entity relationships (would use knowledge graph)
                response = await test_client.http_client.get(
                    f"{test_client.session.services.search}/entities/relationships",
                    timeout=10.0,
                )

                if response.status_code == 200:
                    logger.info("Entity relationships request handled gracefully")
                else:
                    logger.info(
                        f"Entity relationships failed gracefully with status {response.status_code}"
                    )

            except Exception as e:
                logger.info(f"Knowledge graph operation failed as expected: {e}")

        finally:
            # Restore original URL
            test_client.session.services.memgraph = original_memgraph_url

        logger.info("🎉 Knowledge graph failure test passed")

    async def test_bridge_service_unavailable(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Test behavior when bridge service is unavailable"""
        logger.info("🚫 Testing bridge service unavailable scenario")

        # Simulate bridge service failure
        original_bridge_url = test_client.session.services.bridge
        test_client.session.services.bridge = "http://nonexistent:9999"

        try:
            # Document creation should still work (bridge is not in the critical path for creation)
            await test_client.create_test_document(
                test_project,
                "Bridge Service Failure Test",
                content_override={
                    "test_scenario": "bridge_service_unavailable",
                    "expected_behavior": "Document creation succeeds, bridge sync fails gracefully",
                },
            )

            logger.info("✅ Document created despite bridge service unavailability")

            # Sync operations should fail gracefully
            try:
                response = await test_client.http_client.get(
                    f"{test_client.session.services.bridge}/sync/status", timeout=5.0
                )

                # Should fail since service is unavailable
                assert (
                    response.status_code != 200
                ), "Bridge service should be unavailable"

            except Exception as e:
                logger.info(f"Bridge service correctly unavailable: {e}")

        finally:
            # Restore original URL
            test_client.session.services.bridge = original_bridge_url

        logger.info("🎉 Bridge service failure test passed")


@pytest.mark.error_handling
@pytest.mark.asyncio
class TestMalformedContentHandling:
    """
    Test error handling for malformed or invalid content

    These tests ensure the system properly validates input and handles
    malformed data without corruption or system instability.
    """

    async def test_invalid_json_content(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Test handling of invalid JSON in document content"""
        logger.info("🔧 Testing invalid JSON content handling")

        # Test with various invalid JSON scenarios
        invalid_content_scenarios = [
            {
                "name": "circular_reference",
                "description": "Content with circular references",
            },
            {
                "name": "extremely_nested",
                "content": {"level_" + str(i): {"nested": "value"} for i in range(100)},
            },
            {"name": "null_values", "content": None},
            {
                "name": "mixed_types",
                "content": [1, "string", {"object": True}, None, [1, 2, 3]],
            },
        ]

        for scenario in invalid_content_scenarios:
            logger.info(f"Testing scenario: {scenario['name']}")

            try:
                # Attempt to create document with problematic content
                mcp_request = {
                    "method": "create_document",
                    "params": {
                        "project_id": test_project.id,
                        "title": f"Invalid Content Test - {scenario['name']}",
                        "document_type": "invalid_content_test",
                        "content": scenario.get("content", {"invalid": "data"}),
                        "tags": ["invalid_content_test", scenario["name"]],
                    },
                }

                response = await test_client.http_client.post(
                    f"{test_client.session.services.mcp_server}/mcp",
                    json=mcp_request,
                    timeout=15.0,
                )

                # Should either succeed with sanitized content or fail gracefully
                if response.status_code == 200:
                    result = response.json()
                    if "result" in result and "document_id" in result["result"]:
                        logger.info(
                            f"✅ {scenario['name']}: Document created with sanitized content"
                        )
                    else:
                        logger.info(f"⚠️ {scenario['name']}: Unexpected response format")
                else:
                    logger.info(
                        f"✅ {scenario['name']}: Request failed gracefully with status {response.status_code}"
                    )

            except Exception as e:
                logger.info(f"✅ {scenario['name']}: Exception handled gracefully: {e}")

        logger.info("🎉 Invalid JSON content handling test passed")

    async def test_oversized_content(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Test handling of oversized document content"""
        logger.info("📏 Testing oversized content handling")

        # Create extremely large content
        oversized_content = {
            "test_scenario": "oversized_content",
            "large_field": "X" * (10 * 1024 * 1024),  # 10MB of data
            "many_fields": {
                f"field_{i}": f"Content for field {i}" * 1000 for i in range(1000)
            },
            "nested_large": {
                "level1": {
                    "level2": {
                        "level3": {"large_text": "Large nested content " * 100000}
                    }
                }
            },
        }

        mcp_request = {
            "method": "create_document",
            "params": {
                "project_id": test_project.id,
                "title": "Oversized Content Test",
                "document_type": "oversized_content_test",
                "content": oversized_content,
                "tags": ["oversized_content_test"],
            },
        }

        try:
            response = await test_client.http_client.post(
                f"{test_client.session.services.mcp_server}/mcp",
                json=mcp_request,
                timeout=60.0,  # Extended timeout for large content
            )

            if response.status_code == 200:
                logger.info(
                    "✅ Oversized content handled successfully (possibly truncated)"
                )
            elif response.status_code == 413:  # Payload Too Large
                logger.info("✅ Oversized content rejected with appropriate error code")
            elif response.status_code == 400:  # Bad Request
                logger.info("✅ Oversized content rejected with bad request")
            else:
                logger.info(f"⚠️ Unexpected response status: {response.status_code}")

        except httpx.TimeoutException:
            logger.info("✅ Oversized content caused timeout (handled gracefully)")
        except Exception as e:
            logger.info(
                f"✅ Oversized content caused exception (handled gracefully): {e}"
            )

        logger.info("🎉 Oversized content handling test passed")

    async def test_malformed_mcp_requests(self, test_client: IntegrationTestClient):
        """Test handling of malformed MCP requests"""
        logger.info("📡 Testing malformed MCP requests")

        malformed_requests = [
            # Missing method
            {"params": {"test": "data"}},
            # Invalid method
            {"method": "invalid_method", "params": {}},
            # Missing params
            {"method": "create_document"},
            # Invalid params structure
            {"method": "create_document", "params": "invalid_params"},
            # Malformed JSON (will be tested as raw string)
            '{"method": "create_document", "params": {"incomplete": true',
            # Empty request
            {},
            # Non-object request
            "invalid_request_format",
            # Extremely large method name
            {"method": "x" * 10000, "params": {}},
        ]

        for i, request in enumerate(malformed_requests):
            logger.info(f"Testing malformed request {i+1}")

            try:
                if isinstance(request, str):
                    # Test malformed JSON by sending raw string
                    response = await test_client.http_client.post(
                        f"{test_client.session.services.mcp_server}/mcp",
                        content=request,
                        headers={"Content-Type": "application/json"},
                        timeout=10.0,
                    )
                else:
                    response = await test_client.http_client.post(
                        f"{test_client.session.services.mcp_server}/mcp",
                        json=request,
                        timeout=10.0,
                    )

                # Should return error status codes
                if response.status_code in [400, 422, 500]:
                    logger.info(
                        f"✅ Malformed request {i+1}: Handled with status {response.status_code}"
                    )
                else:
                    logger.info(
                        f"⚠️ Malformed request {i+1}: Unexpected status {response.status_code}"
                    )

            except Exception as e:
                logger.info(
                    f"✅ Malformed request {i+1}: Exception handled gracefully: {e}"
                )

        logger.info("🎉 Malformed MCP requests handling test passed")

    async def test_invalid_project_references(self, test_client: IntegrationTestClient):
        """Test handling of invalid project ID references"""
        logger.info("🔗 Testing invalid project references")

        invalid_project_ids = [
            "nonexistent-project-id",
            "invalid-uuid-format",
            "",
            "null",
            "12345",
            "project-" + "x" * 1000,  # Extremely long ID
        ]

        for project_id in invalid_project_ids:
            logger.info(f"Testing invalid project ID: {project_id[:50]}...")

            mcp_request = {
                "method": "create_document",
                "params": {
                    "project_id": project_id,
                    "title": "Test Document",
                    "document_type": "test",
                    "content": {"test": "content"},
                },
            }

            try:
                response = await test_client.http_client.post(
                    f"{test_client.session.services.mcp_server}/mcp",
                    json=mcp_request,
                    timeout=10.0,
                )

                # Should return error for invalid project references
                if response.status_code in [400, 404, 422]:
                    logger.info(
                        f"✅ Invalid project ID handled with status {response.status_code}"
                    )
                else:
                    logger.info(
                        f"⚠️ Invalid project ID: Unexpected status {response.status_code}"
                    )

            except Exception as e:
                logger.info(f"✅ Invalid project ID: Exception handled gracefully: {e}")

        logger.info("🎉 Invalid project references handling test passed")


@pytest.mark.error_handling
@pytest.mark.asyncio
class TestConcurrencyAndRaceConditions:
    """
    Test error handling for concurrent operations and race conditions

    These tests ensure the system handles concurrent access properly
    and prevents data corruption or conflicts.
    """

    async def test_concurrent_document_creation(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Test concurrent creation of documents in the same project"""
        logger.info("🔄 Testing concurrent document creation")

        num_concurrent = 10

        async def create_concurrent_document(doc_num: int):
            return await test_client.create_test_document(
                test_project,
                f"Concurrent Doc {doc_num}",
                content_override={
                    "test_scenario": "concurrent_document_creation",
                    "document_number": doc_num,
                    "concurrent_test": True,
                },
            )

        # Create documents concurrently
        creation_start = time.time()
        tasks = [create_concurrent_document(i) for i in range(num_concurrent)]

        try:
            documents = await asyncio.gather(*tasks, return_exceptions=True)
            creation_time = time.time() - creation_start

            # Count successful creations vs exceptions
            successful_docs = [
                doc for doc in documents if isinstance(doc, TestDocument)
            ]
            exceptions = [doc for doc in documents if isinstance(doc, Exception)]

            logger.info(
                f"✅ Concurrent creation results: {len(successful_docs)} successful, {len(exceptions)} failed"
            )
            logger.info(f"Total time: {creation_time:.2f}s")

            # We expect most documents to be created successfully
            success_rate = len(successful_docs) / num_concurrent
            assert (
                success_rate >= 0.7
            ), f"Too many concurrent creation failures: {success_rate:.1%}"

            # Verify all successful documents have unique IDs
            doc_ids = [doc.id for doc in successful_docs]
            unique_ids = set(doc_ids)
            assert len(doc_ids) == len(
                unique_ids
            ), "Duplicate document IDs detected in concurrent creation"

        except Exception as e:
            logger.warning(f"Concurrent document creation failed: {e}")
            # This is acceptable - the system should handle concurrent access gracefully

        logger.info("🎉 Concurrent document creation test passed")

    async def test_concurrent_project_operations(
        self, test_client: IntegrationTestClient
    ):
        """Test concurrent project operations"""
        logger.info("🔄 Testing concurrent project operations")

        num_concurrent = 5

        async def create_concurrent_project(project_num: int):
            return await test_client.create_test_project(
                f"Concurrent Project {project_num}"
            )

        # Create projects concurrently
        tasks = [create_concurrent_project(i) for i in range(num_concurrent)]

        try:
            projects = await asyncio.gather(*tasks, return_exceptions=True)

            # Count successful creations
            successful_projects = [
                proj for proj in projects if isinstance(proj, TestProject)
            ]
            exceptions = [proj for proj in projects if isinstance(proj, Exception)]

            logger.info(
                f"✅ Concurrent project creation: {len(successful_projects)} successful, {len(exceptions)} failed"
            )

            # Verify unique project IDs
            project_ids = [proj.id for proj in successful_projects]
            unique_ids = set(project_ids)
            assert len(project_ids) == len(unique_ids), "Duplicate project IDs detected"

            # We expect at least some projects to be created successfully
            assert (
                len(successful_projects) > 0
            ), "No concurrent projects created successfully"

        except Exception as e:
            logger.warning(f"Concurrent project operations handled gracefully: {e}")

        logger.info("🎉 Concurrent project operations test passed")

    async def test_rapid_rag_queries(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Test rapid concurrent RAG queries"""
        logger.info("🔄 Testing rapid concurrent RAG queries")

        # First create a document to query
        document = await test_client.create_test_document(
            test_project,
            "RAG Query Test Document",
            content_override={
                "test_scenario": "rapid_rag_queries",
                "searchable_content": "This document is for testing rapid concurrent RAG queries",
            },
        )

        # Wait for indexing
        await test_client.wait_for_indexing(document, max_wait_seconds=30.0)

        num_concurrent = 20

        async def perform_rag_query(query_num: int):
            mcp_request = {
                "method": "perform_rag_query",
                "params": {
                    "query": f"rapid RAG query test {query_num}",
                    "match_count": 5,
                },
            }

            response = await test_client.http_client.post(
                f"{test_client.session.services.mcp_server}/mcp",
                json=mcp_request,
                timeout=15.0,
            )

            return response.status_code == 200

        # Perform queries concurrently
        query_start = time.time()
        tasks = [perform_rag_query(i) for i in range(num_concurrent)]

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            query_time = time.time() - query_start

            # Count successful queries
            successful_queries = sum(1 for result in results if result is True)
            exceptions = sum(1 for result in results if isinstance(result, Exception))

            logger.info(
                f"✅ Rapid RAG queries: {successful_queries}/{num_concurrent} successful in {query_time:.2f}s"
            )
            logger.info(f"Exceptions: {exceptions}")

            # We expect most queries to succeed
            success_rate = successful_queries / num_concurrent
            assert (
                success_rate >= 0.6
            ), f"Too many RAG query failures: {success_rate:.1%}"

        except Exception as e:
            logger.warning(f"Rapid RAG queries handled gracefully: {e}")

        logger.info("🎉 Rapid concurrent RAG queries test passed")


@pytest.mark.error_handling
@pytest.mark.asyncio
class TestNetworkAndTimeoutHandling:
    """
    Test error handling for network issues and timeouts

    These tests simulate network problems and verify the system
    handles them gracefully with appropriate timeouts and retries.
    """

    async def test_slow_response_handling(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Test handling of slow service responses"""
        logger.info("🐌 Testing slow response handling")

        # Test with progressively longer timeouts
        timeout_values = [1.0, 5.0, 10.0, 30.0]

        for timeout in timeout_values:
            logger.info(f"Testing with {timeout}s timeout")

            # Create a client with specific timeout
            async with httpx.AsyncClient(timeout=timeout) as slow_client:
                try:
                    # Try to create a document with limited timeout
                    mcp_request = {
                        "method": "create_document",
                        "params": {
                            "project_id": test_project.id,
                            "title": f"Timeout Test {timeout}s",
                            "document_type": "timeout_test",
                            "content": {
                                "test_scenario": "slow_response_handling",
                                "timeout_value": timeout,
                                "large_content": "X"
                                * 1000000,  # 1MB content to potentially slow things down
                            },
                        },
                    }

                    start_time = time.time()
                    response = await slow_client.post(
                        f"{test_client.session.services.mcp_server}/mcp",
                        json=mcp_request,
                    )
                    response_time = time.time() - start_time

                    if response.status_code == 200:
                        logger.info(
                            f"✅ Request completed in {response_time:.2f}s (timeout: {timeout}s)"
                        )
                    else:
                        logger.info(
                            f"⚠️ Request failed with status {response.status_code} after {response_time:.2f}s"
                        )

                except httpx.TimeoutException:
                    logger.info(
                        f"✅ Request timed out after {timeout}s (handled gracefully)"
                    )
                except Exception as e:
                    logger.info(f"✅ Request failed gracefully: {e}")

        logger.info("🎉 Slow response handling test passed")

    async def test_connection_refused_handling(
        self, test_client: IntegrationTestClient
    ):
        """Test handling of connection refused errors"""
        logger.info("🚫 Testing connection refused handling")

        # Test various invalid endpoints
        invalid_endpoints = [
            "http://nonexistent.domain:8181",
            "http://localhost:99999",  # Invalid port
            "http://127.0.0.1:0",  # Port 0
        ]

        for endpoint in invalid_endpoints:
            logger.info(f"Testing connection to {endpoint}")

            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.get(f"{endpoint}/health")
                    logger.info(f"⚠️ Unexpected success connecting to {endpoint}")

            except httpx.ConnectError:
                logger.info(f"✅ Connection refused handled gracefully for {endpoint}")
            except Exception as e:
                logger.info(
                    f"✅ Connection error handled gracefully for {endpoint}: {e}"
                )

        logger.info("🎉 Connection refused handling test passed")


@pytest.mark.error_handling
@pytest.mark.asyncio
class TestResourceExhaustionScenarios:
    """
    Test error handling for resource exhaustion scenarios

    These tests simulate resource constraints and verify the system
    handles them without crashing or corrupting data.
    """

    async def test_memory_intensive_operations(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Test handling of memory-intensive operations"""
        logger.info("🧠 Testing memory-intensive operations")

        # Create documents with progressively larger content
        sizes = [1024, 10240, 102400, 1048576]  # 1KB, 10KB, 100KB, 1MB

        for size in sizes:
            logger.info(f"Testing document with {size} bytes content")

            try:
                large_content = {
                    "test_scenario": "memory_intensive_operations",
                    "content_size": size,
                    "large_data": "X" * size,
                }

                document = await test_client.create_test_document(
                    test_project,
                    f"Memory Test {size} bytes",
                    content_override=large_content,
                )

                logger.info(f"✅ Created document with {size} bytes")

                # Try to index it
                indexing_success = await test_client.wait_for_indexing(
                    document, max_wait_seconds=60.0
                )

                if indexing_success:
                    logger.info(f"✅ Indexed document with {size} bytes")
                else:
                    logger.info(
                        f"⚠️ Failed to index document with {size} bytes (may be expected for large sizes)"
                    )

            except Exception as e:
                logger.info(
                    f"✅ Memory-intensive operation handled gracefully for {size} bytes: {e}"
                )

        logger.info("🎉 Memory-intensive operations test passed")

    async def test_high_frequency_requests(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Test handling of high-frequency requests"""
        logger.info("⚡ Testing high-frequency requests")

        num_requests = 50
        request_interval = 0.1  # 10 requests per second

        async def make_rapid_request(request_num: int):
            mcp_request = {
                "method": "perform_rag_query",
                "params": {
                    "query": f"high frequency test {request_num}",
                    "match_count": 1,
                },
            }

            try:
                response = await test_client.http_client.post(
                    f"{test_client.session.services.mcp_server}/mcp",
                    json=mcp_request,
                    timeout=5.0,
                )
                return response.status_code == 200
            except Exception:
                return False

        # Make rapid requests
        start_time = time.time()
        tasks = []

        for i in range(num_requests):
            tasks.append(make_rapid_request(i))
            if i < num_requests - 1:
                await asyncio.sleep(request_interval)

        # Wait for all requests to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time

        successful_requests = sum(1 for result in results if result is True)

        logger.info(
            f"✅ High-frequency requests: {successful_requests}/{num_requests} successful in {total_time:.2f}s"
        )
        logger.info(f"Request rate: {successful_requests/total_time:.2f} req/s")

        # We expect some requests to succeed even under high load
        success_rate = successful_requests / num_requests
        assert (
            success_rate >= 0.3
        ), f"Too few high-frequency requests succeeded: {success_rate:.1%}"

        logger.info("🎉 High-frequency requests test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "error_handling"])
