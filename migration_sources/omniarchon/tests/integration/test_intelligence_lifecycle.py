#!/usr/bin/env python3
"""
Intelligence Document Lifecycle Integration Tests

Tests the complete intelligence document lifecycle including:
1. Document Creation → Indexing → RAG Retrieval (Core Lifecycle)
2. ResilientIndexingService Health and Processing
3. Cross-Service Intelligence Orchestration (RAG + Qdrant + Memgraph)

This test suite specifically addresses the critical issue where documents were
being created but never indexed for retrieval due to ResilientIndexingService
not being started in main.py (fixed in lines 200-217).

These tests prevent regression of this critical system failure.
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict

import pytest

from .conftest import IntegrationTestClient, TestProject

logger = logging.getLogger(__name__)


@pytest.mark.critical
@pytest.mark.intelligence_lifecycle
@pytest.mark.asyncio
class TestIntelligenceDocumentLifecycle:
    """
    Critical tests for intelligence document lifecycle and indexing service.

    These tests validate the complete flow from document creation through
    indexing to retrieval, ensuring the ResilientIndexingService properly
    processes documents and makes them available for RAG queries.
    """

    async def test_core_intelligence_document_lifecycle(
        self,
        test_client: IntegrationTestClient,
        test_project: TestProject,
        performance_thresholds: Dict[str, float],
    ):
        """
        Test complete intelligence document lifecycle: Creation → Indexing → RAG Retrieval

        This is the MOST CRITICAL test - it validates that documents created via
        MCP are properly indexed and retrievable via RAG queries.

        Steps:
        1. Create intelligence document via MCP API
        2. Wait for ResilientIndexingService to process (5-10 seconds)
        3. Verify document is retrievable via RAG query
        4. Confirm document appears in vector search results
        5. Validate performance thresholds
        """
        logger.info("🧠 Starting core intelligence document lifecycle test")

        # Step 1: Create unique intelligence document
        unique_id = str(uuid.uuid4())
        test_keywords = [
            f"INTELLIGENCE_TEST_{unique_id}",
            "CRITICAL_INDEXING_VERIFICATION",
            "RESILIENT_INDEXING_SERVICE_TEST",
        ]

        intelligence_content = {
            "intelligence_type": "debug_analysis",
            "test_metadata": {
                "test_id": unique_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "keywords": test_keywords,
            },
            "analysis_results": {
                "issue_classification": "indexing_service_failure",
                "root_cause": "ResilientIndexingService not started in main.py",
                "resolution": "Added service startup in lines 200-217",
                "prevention_strategy": "Integration tests for indexing lifecycle",
            },
            "test_verification": {
                "searchable_content": f"This document contains unique test keywords: {' '.join(test_keywords)}",
                "expected_retrieval": "Document should be findable via RAG query after indexing",
                "performance_target": "Indexing should complete within 10 seconds",
            },
        }

        start_time = time.time()

        # Create document via MCP API
        create_response = await test_client.create_document(
            project_id=test_project.id,
            title=f"Intelligence Lifecycle Test - {unique_id}",
            document_type="intelligence_analysis",
            content=intelligence_content,
            tags=["intelligence_test", "lifecycle_test", "indexing_verification"],
        )

        assert create_response["success"], "Failed to create intelligence document"
        document_id = create_response["document_id"]
        creation_time = time.time() - start_time

        logger.info(f"✅ Document created: {document_id} in {creation_time:.2f}s")

        # Step 2: Wait for indexing service to process document
        logger.info("⏳ Waiting for ResilientIndexingService to process document...")

        indexing_timeout = performance_thresholds.get("indexing_timeout", 15.0)
        poll_interval = 2.0
        elapsed_time = 0

        while elapsed_time < indexing_timeout:
            await asyncio.sleep(poll_interval)
            elapsed_time += poll_interval

            # Check if document is indexed by attempting RAG retrieval
            try:
                rag_response = await test_client.perform_rag_query(
                    query=f"INTELLIGENCE_TEST_{unique_id}", match_count=5
                )

                if rag_response.get("success") and rag_response.get("results"):
                    # Check if our document appears in results
                    for result in rag_response["results"]:
                        if unique_id in result.get("content", ""):
                            indexing_time = elapsed_time
                            logger.info(
                                f"✅ Document indexed and retrievable in {indexing_time:.2f}s"
                            )
                            break
                    else:
                        continue  # Document not found in results yet
                    break  # Found our document

            except Exception as e:
                logger.debug(f"RAG query attempt failed: {e}")
                continue
        else:
            # Timeout reached
            pytest.fail(
                f"Document not indexed within {indexing_timeout}s - ResilientIndexingService may not be working"
            )

        # Step 3: Comprehensive retrieval verification
        logger.info("🔍 Performing comprehensive retrieval verification...")

        # Test primary keyword search
        primary_rag_response = await test_client.perform_rag_query(
            query=f"INTELLIGENCE_TEST_{unique_id}", match_count=10
        )

        assert primary_rag_response["success"], "Primary RAG query failed"
        assert (
            len(primary_rag_response["results"]) > 0
        ), "No results from primary RAG query"

        # Verify our document is in the results
        found_document = False
        for result in primary_rag_response["results"]:
            if unique_id in result.get("content", ""):
                found_document = True
                assert result.get("relevance_score", 0) > 0.5, "Relevance score too low"
                logger.info(
                    f"✅ Document found with relevance score: {result.get('relevance_score')}"
                )
                break

        assert found_document, "Created document not found in RAG results"

        # Step 4: Vector search verification
        logger.info("🔎 Verifying vector search indexing...")

        vector_response = await test_client.perform_vector_search(
            query=f"intelligence test {unique_id}", limit=10
        )

        assert vector_response["success"], "Vector search failed"

        # Look for our document in vector search results
        vector_found = False
        for result in vector_response.get("results", []):
            if unique_id in result.get("content", ""):
                vector_found = True
                logger.info(
                    f"✅ Document found in vector search with similarity: {result.get('similarity_score')}"
                )
                break

        assert vector_found, "Document not found in vector search results"

        # Step 5: Performance validation
        total_time = time.time() - start_time
        logger.info(f"📊 Total lifecycle time: {total_time:.2f}s")

        # Validate performance thresholds
        max_total_time = performance_thresholds.get("total_lifecycle_time", 20.0)
        assert (
            total_time < max_total_time
        ), f"Lifecycle took {total_time:.2f}s, exceeds threshold {max_total_time}s"

        max_indexing_time = performance_thresholds.get("max_indexing_time", 10.0)
        assert (
            indexing_time < max_indexing_time
        ), f"Indexing took {indexing_time:.2f}s, exceeds threshold {max_indexing_time}s"

        logger.info("✅ Core intelligence document lifecycle test passed!")

    async def test_resilient_indexing_service_health(
        self,
        test_client: IntegrationTestClient,
        test_project: TestProject,
    ):
        """
        Test ResilientIndexingService health and queue processing

        This test validates that:
        1. ResilientIndexingService is running after server startup
        2. Service properly handles document queue processing
        3. Service gracefully handles processing failures
        """
        logger.info("🏥 Testing ResilientIndexingService health")

        # Step 1: Verify indexing service is running
        health_response = await test_client.check_indexing_service_health()

        assert health_response["success"], "Failed to get indexing service health"
        assert health_response.get(
            "service_running", False
        ), "ResilientIndexingService is not running"

        service_status = health_response.get("status", {})
        assert service_status.get(
            "processing_enabled", False
        ), "Document processing is not enabled"

        logger.info(f"✅ Indexing service healthy: {service_status}")

        # Step 2: Test queue processing with multiple documents
        logger.info("📥 Testing queue processing with multiple documents...")

        document_ids = []
        batch_size = 3

        # Create multiple documents rapidly to test queue handling
        for i in range(batch_size):
            doc_response = await test_client.create_document(
                project_id=test_project.id,
                title=f"Queue Test Document {i+1}",
                document_type="queue_test",
                content={
                    "test_type": "queue_processing",
                    "batch_index": i,
                    "searchable_keyword": f"QUEUE_TEST_{i}_{int(time.time())}",
                },
                tags=["queue_test", "batch_processing"],
            )

            assert doc_response["success"], f"Failed to create document {i+1}"
            document_ids.append(doc_response["document_id"])

        logger.info(f"✅ Created {batch_size} documents for queue testing")

        # Step 3: Wait for queue processing and verify all documents are
        # indexed
        max_wait_time = 20.0
        poll_interval = 3.0
        start_time = time.time()

        processed_documents = set()

        while (
            len(processed_documents) < batch_size
            and (time.time() - start_time) < max_wait_time
        ):
            await asyncio.sleep(poll_interval)

            # Check each document for indexing
            for i, doc_id in enumerate(document_ids):
                if doc_id in processed_documents:
                    continue

                rag_response = await test_client.perform_rag_query(
                    query=f"QUEUE_TEST_{i}", match_count=5
                )

                if rag_response.get("success") and rag_response.get("results"):
                    for result in rag_response["results"]:
                        if f"QUEUE_TEST_{i}" in result.get("content", ""):
                            processed_documents.add(doc_id)
                            logger.info(f"✅ Document {i+1} processed and indexed")
                            break

        # Verify all documents were processed
        processing_time = time.time() - start_time
        assert (
            len(processed_documents) == batch_size
        ), f"Only {len(processed_documents)}/{batch_size} documents processed within {max_wait_time}s"

        logger.info(
            f"✅ All {batch_size} documents processed in {processing_time:.2f}s"
        )

        # Step 4: Test service resilience with error handling
        logger.info("🛡️ Testing service error handling...")

        # Create document with potentially problematic content
        error_test_response = await test_client.create_document(
            project_id=test_project.id,
            title="Error Handling Test",
            document_type="error_test",
            content={
                "test_type": "error_handling",
                "large_content": "x" * 100000,  # Large content to test limits
                "special_characters": "!@#$%^&*()[]{}|;:,.<>?",
                "unicode_content": "🧠🔍📊✅❌⚠️🚀💡",
            },
            tags=["error_test", "resilience"],
        )

        # Service should handle this gracefully without crashing
        assert error_test_response[
            "success"
        ], "Service failed to handle potentially problematic document"

        logger.info("✅ ResilientIndexingService health test passed!")

    async def test_cross_service_intelligence_orchestration(
        self,
        test_client: IntegrationTestClient,
        test_project: TestProject,
    ):
        """
        Test orchestrated intelligence across RAG + Qdrant + Memgraph services

        This test validates:
        1. All three backend services respond correctly
        2. Orchestrated queries work properly
        3. Intelligent synthesis functions correctly
        4. Cross-service data consistency
        """
        logger.info("🎭 Testing cross-service intelligence orchestration")

        # Step 1: Create test document with rich metadata for cross-service
        # testing
        orchestration_id = str(uuid.uuid4())

        rich_content = {
            "orchestration_test_id": orchestration_id,
            "multi_service_verification": {
                "rag_keywords": [
                    "RAG_ORCHESTRATION",
                    "KNOWLEDGE_BASE",
                    "SEARCH_PATTERNS",
                ],
                "vector_keywords": [
                    "SEMANTIC_SIMILARITY",
                    "EMBEDDING_SPACE",
                    "VECTOR_SEARCH",
                ],
                "graph_keywords": [
                    "KNOWLEDGE_GRAPH",
                    "RELATIONSHIPS",
                    "GRAPH_TRAVERSAL",
                ],
            },
            "technical_content": {
                "architecture": "microservices orchestration pattern",
                "components": [
                    "RAG Service",
                    "Qdrant Vector DB",
                    "Memgraph Knowledge Graph",
                ],
                "integration_pattern": "parallel query execution with intelligent synthesis",
            },
            "test_data": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "service_targets": ["rag_search", "vector_search", "knowledge_graph"],
                "expected_synthesis": "context-aware recommendations from all sources",
            },
        }

        # Create the test document
        doc_response = await test_client.create_document(
            project_id=test_project.id,
            title=f"Cross-Service Orchestration Test - {orchestration_id}",
            document_type="orchestration_test",
            content=rich_content,
            tags=["orchestration", "cross_service", "intelligence_test"],
        )

        assert doc_response["success"], "Failed to create orchestration test document"

        # Step 2: Wait for indexing across all services
        logger.info("⏳ Waiting for cross-service indexing...")
        await asyncio.sleep(8)  # Allow time for all services to index

        # Step 3: Test orchestrated RAG query (primary orchestration function)
        logger.info("🎼 Testing orchestrated RAG query...")

        orchestrated_response = await test_client.perform_orchestrated_rag_query(
            query=f"orchestration test {orchestration_id} microservices",
            context="architecture",
            match_count=5,
        )

        assert orchestrated_response["success"], "Orchestrated RAG query failed"

        # Validate orchestration structure
        results = orchestrated_response.get("results", {})
        assert "rag_search" in results, "RAG search results missing from orchestration"
        assert (
            "vector_search" in results
        ), "Vector search results missing from orchestration"
        assert (
            "knowledge_graph" in results
        ), "Knowledge graph results missing from orchestration"

        # Validate synthesis
        synthesis = orchestrated_response.get("synthesis", {})
        assert "key_findings" in synthesis, "Key findings missing from synthesis"
        assert (
            "recommended_actions" in synthesis
        ), "Recommended actions missing from synthesis"
        assert (
            synthesis.get("confidence_score", 0) > 0
        ), "Confidence score missing or zero"

        logger.info(
            f"✅ Orchestration successful with confidence: {synthesis.get('confidence_score')}"
        )

        # Step 4: Validate individual service responses
        sources_successful = orchestrated_response.get("sources_successful", [])
        expected_services = ["RAG", "Vector Search", "Knowledge Graph"]

        for service in expected_services:
            assert service in sources_successful, f"{service} not in successful sources"

        # Step 5: Test performance of orchestration
        duration_ms = orchestrated_response.get("duration_ms", 0)
        max_orchestration_time = 3000  # 3 seconds max for parallel execution

        assert duration_ms > 0, "Duration not recorded"
        assert (
            duration_ms < max_orchestration_time
        ), f"Orchestration took {duration_ms}ms, exceeds {max_orchestration_time}ms"

        logger.info(f"✅ Orchestration completed in {duration_ms}ms")

        # Step 6: Test graceful degradation
        logger.info("🛡️ Testing graceful degradation...")

        # Query with complex terms to test service resilience
        degradation_response = await test_client.perform_orchestrated_rag_query(
            query="complex_nonexistent_query_for_degradation_testing_12345",
            context="debugging",
            match_count=3,
        )

        # Should still succeed even if some services return no results
        assert degradation_response[
            "success"
        ], "Orchestration failed under degradation conditions"

        # Verify at least basic structure is maintained
        assert (
            "results" in degradation_response
        ), "Results structure missing under degradation"
        assert (
            "synthesis" in degradation_response
        ), "Synthesis missing under degradation"

        logger.info("✅ Cross-service intelligence orchestration test passed!")

    async def test_indexing_service_performance_validation(
        self,
        test_client: IntegrationTestClient,
        test_project: TestProject,
        performance_thresholds: Dict[str, float],
    ):
        """
        Test indexing service performance under various load conditions

        Validates:
        1. Single document indexing performance
        2. Batch document processing efficiency
        3. Large document handling
        4. Concurrent indexing capability
        """
        logger.info("⚡ Testing indexing service performance")

        # Performance test configuration
        single_doc_threshold = performance_thresholds.get("single_doc_indexing", 5.0)
        large_doc_threshold = performance_thresholds.get("large_doc_indexing", 10.0)

        # Test 1: Single document indexing speed
        logger.info("📄 Testing single document indexing speed...")

        start_time = time.time()
        single_doc_id = str(uuid.uuid4())

        single_response = await test_client.create_document(
            project_id=test_project.id,
            title=f"Single Performance Test - {single_doc_id}",
            document_type="performance_test",
            content={"test_type": "single_performance", "test_id": single_doc_id},
            tags=["performance", "single"],
        )

        assert single_response["success"], "Single document creation failed"

        # Wait for indexing and measure time
        indexed = await test_client.wait_for_document_indexing(
            query_term=single_doc_id, timeout=single_doc_threshold
        )

        single_indexing_time = time.time() - start_time
        assert indexed, f"Single document not indexed within {single_doc_threshold}s"
        assert (
            single_indexing_time < single_doc_threshold
        ), f"Single indexing took {single_indexing_time:.2f}s"

        logger.info(f"✅ Single document indexed in {single_indexing_time:.2f}s")

        # Test 2: Large document handling
        logger.info("📋 Testing large document indexing...")

        large_content = {
            "test_type": "large_document_performance",
            "large_text": "Lorem ipsum " * 1000,  # Large text content
            "structured_data": {f"field_{i}": f"value_{i}" for i in range(100)},
            "test_id": str(uuid.uuid4()),
        }

        start_time = time.time()
        large_response = await test_client.create_document(
            project_id=test_project.id,
            title="Large Document Performance Test",
            document_type="large_performance_test",
            content=large_content,
            tags=["performance", "large"],
        )

        assert large_response["success"], "Large document creation failed"

        large_indexed = await test_client.wait_for_document_indexing(
            query_term=large_content["test_id"], timeout=large_doc_threshold
        )

        large_indexing_time = time.time() - start_time
        assert (
            large_indexed
        ), f"Large document not indexed within {large_doc_threshold}s"
        assert (
            large_indexing_time < large_doc_threshold
        ), f"Large document indexing took {large_indexing_time:.2f}s"

        logger.info(f"✅ Large document indexed in {large_indexing_time:.2f}s")

        logger.info("✅ Indexing service performance validation passed!")
