#!/usr/bin/env python3
"""
Happy Path Integration Tests for MCP Document Indexing Pipeline

Tests the complete happy path flow:
MCP Document Creation → Intelligence Processing → Bridge Sync →
Vector Indexing (Qdrant) → Knowledge Graph Sync (Memgraph) → RAG Retrievability

These are CRITICAL tests that validate the core functionality is working correctly.
All happy path tests must pass for the system to be considered functional.
"""

import asyncio
import logging
import time
from typing import Dict

import pytest

from .conftest import IntegrationTestClient, TestProject

logger = logging.getLogger(__name__)


@pytest.mark.critical
@pytest.mark.happy_path
@pytest.mark.asyncio
class TestMCPDocumentIndexingHappyPath:
    """
    Critical happy path tests for the complete MCP document indexing pipeline.

    These tests validate that the core functionality works end-to-end without errors
    and within acceptable performance bounds.
    """

    async def test_complete_pipeline_single_document(
        self,
        test_client: IntegrationTestClient,
        test_project: TestProject,
        performance_thresholds: Dict[str, float],
    ):
        """
        Test complete pipeline with a single document (most critical test)

        This test validates the entire flow:
        1. Create document via MCP API
        2. Wait for automatic indexing
        3. Verify RAG retrievability
        4. Validate performance thresholds
        """
        logger.info("🎯 CRITICAL: Testing complete pipeline with single document")

        pipeline_start = time.time()

        # Step 1: Create test document via MCP
        logger.info("Step 1: Creating document via MCP API")
        creation_start = time.time()

        document = await test_client.create_test_document(
            test_project,
            document_title="Happy Path Test Document",
            content_override={
                "test_scenario": "complete_pipeline_single_document",
                "critical_keywords": [
                    "happy path testing",
                    "MCP document creation",
                    "automatic indexing",
                    "RAG retrievability validation",
                ],
                "expected_behavior": "This document should be created, indexed, and retrievable within 30 seconds",
            },
        )

        creation_time = time.time() - creation_start
        logger.info(f"✅ Document created in {creation_time:.2f}s")

        # Validate creation time against SLA
        assert (
            creation_time <= performance_thresholds["document_creation"]
        ), f"Document creation exceeded SLA: {creation_time:.2f}s > {performance_thresholds['document_creation']}s"

        # Step 2: Wait for automatic indexing
        logger.info("Step 2: Waiting for automatic indexing")
        indexing_start = time.time()

        indexing_success = await test_client.wait_for_indexing(
            document, max_wait_seconds=performance_thresholds["indexing_completion"]
        )

        indexing_time = time.time() - indexing_start
        logger.info(
            f"{'✅' if indexing_success else '❌'} Indexing completed in {indexing_time:.2f}s"
        )

        assert indexing_success, "Document indexing failed or timed out"
        assert (
            indexing_time <= performance_thresholds["indexing_completion"]
        ), f"Indexing exceeded SLA: {indexing_time:.2f}s > {performance_thresholds['indexing_completion']}s"

        # Step 3: Test RAG retrievability
        logger.info("Step 3: Testing RAG retrievability")
        rag_start = time.time()

        rag_success = await test_client.test_rag_retrievability(document)

        rag_time = time.time() - rag_start
        logger.info(
            f"{'✅' if rag_success else '❌'} RAG retrieval completed in {rag_time:.2f}s"
        )

        assert rag_success, "Document not retrievable via RAG queries"
        assert (
            rag_time <= performance_thresholds["rag_query"]
        ), f"RAG query exceeded SLA: {rag_time:.2f}s > {performance_thresholds['rag_query']}s"

        # Step 4: Validate complete pipeline time
        total_time = time.time() - pipeline_start
        logger.info(f"🎉 Complete pipeline time: {total_time:.2f}s")

        assert (
            total_time <= performance_thresholds["complete_pipeline"]
        ), f"Complete pipeline exceeded SLA: {total_time:.2f}s > {performance_thresholds['complete_pipeline']}s"

        # Additional validations
        assert document.indexed_at is not None, "Document indexing timestamp not set"
        assert document.rag_retrievable, "Document not marked as RAG retrievable"

        logger.info("🎉 SUCCESS: Complete pipeline test passed all validations")

    async def test_multiple_documents_sequential(
        self,
        test_client: IntegrationTestClient,
        test_project: TestProject,
        performance_thresholds: Dict[str, float],
    ):
        """
        Test pipeline with multiple documents created sequentially

        Validates that the system can handle multiple documents without
        interference or performance degradation.
        """
        logger.info("📚 Testing multiple documents sequential processing")

        num_documents = 3
        documents = []
        creation_times = []

        # Create multiple documents sequentially
        for i in range(num_documents):
            logger.info(f"Creating document {i+1}/{num_documents}")

            creation_start = time.time()
            document = await test_client.create_test_document(
                test_project,
                document_title=f"Sequential Test Document {i+1}",
                content_override={
                    "test_scenario": "multiple_documents_sequential",
                    "document_number": i + 1,
                    "total_documents": num_documents,
                    "unique_content": f"This is document number {i+1} in the sequential test",
                },
            )
            creation_time = time.time() - creation_start

            documents.append(document)
            creation_times.append(creation_time)

            # Validate each creation meets SLA
            assert (
                creation_time <= performance_thresholds["document_creation"]
            ), f"Document {i+1} creation exceeded SLA: {creation_time:.2f}s"

        logger.info(
            f"✅ Created {num_documents} documents, avg time: {sum(creation_times)/len(creation_times):.2f}s"
        )

        # Wait for all documents to be indexed
        indexing_start = time.time()
        indexed_count = 0

        for i, document in enumerate(documents):
            logger.info(f"Waiting for document {i+1} indexing...")
            indexing_success = await test_client.wait_for_indexing(
                document, max_wait_seconds=30.0
            )
            if indexing_success:
                indexed_count += 1

        indexing_time = time.time() - indexing_start
        logger.info(
            f"✅ Indexed {indexed_count}/{num_documents} documents in {indexing_time:.2f}s"
        )

        assert (
            indexed_count == num_documents
        ), f"Only {indexed_count}/{num_documents} documents indexed"

        # Test RAG retrievability for all documents
        rag_start = time.time()
        retrievable_count = 0

        for i, document in enumerate(documents):
            logger.info(f"Testing RAG retrievability for document {i+1}...")
            rag_success = await test_client.test_rag_retrievability(document)
            if rag_success:
                retrievable_count += 1

        rag_time = time.time() - rag_start
        logger.info(
            f"✅ {retrievable_count}/{num_documents} documents retrievable via RAG in {rag_time:.2f}s"
        )

        assert (
            retrievable_count == num_documents
        ), f"Only {retrievable_count}/{num_documents} documents retrievable"

        logger.info("🎉 SUCCESS: Multiple documents sequential test passed")

    async def test_large_document_processing(
        self,
        test_client: IntegrationTestClient,
        test_project: TestProject,
        performance_thresholds: Dict[str, float],
    ):
        """
        Test pipeline with a large document to validate performance with substantial content

        This test ensures the system can handle larger documents without
        significant performance degradation or failures.
        """
        logger.info("📄 Testing large document processing")

        # Generate large document content
        large_content = {
            "test_scenario": "large_document_processing",
            "overview": "This is a comprehensive large document test for the MCP indexing pipeline. "
            * 10,
            "sections": {
                f"section_{i}": f"This is section {i} content. " * 50 for i in range(20)
            },
            "detailed_content": {
                "technical_specifications": "Technical specifications section. " * 100,
                "implementation_details": "Implementation details section. " * 100,
                "performance_considerations": "Performance considerations section. "
                * 100,
                "security_requirements": "Security requirements section. " * 100,
                "testing_procedures": "Testing procedures section. " * 100,
            },
            "appendices": {
                f"appendix_{i}": f"Appendix {i} content with detailed information. "
                * 30
                for i in range(10)
            },
            "keywords_for_search": [
                "large document testing",
                "performance validation",
                "comprehensive content",
                "MCP pipeline scalability",
                "vector embedding efficiency",
                "knowledge graph performance",
            ],
            "metadata": {
                "word_count_estimate": 25000,
                "expected_processing_time": "under 30 seconds",
                "test_focus": "performance with large content",
            },
        }

        # Create large document
        creation_start = time.time()
        document = await test_client.create_test_document(
            test_project,
            document_title="Large Document Performance Test",
            content_override=large_content,
        )
        creation_time = time.time() - creation_start

        logger.info(f"✅ Large document created in {creation_time:.2f}s")

        # Allow slightly more time for large document creation
        extended_creation_threshold = performance_thresholds["document_creation"] * 2
        assert (
            creation_time <= extended_creation_threshold
        ), f"Large document creation exceeded extended SLA: {creation_time:.2f}s > {extended_creation_threshold}s"

        # Wait for indexing (may take longer for large documents)
        indexing_start = time.time()
        indexing_success = await test_client.wait_for_indexing(
            document,
            max_wait_seconds=performance_thresholds["indexing_completion"]
            * 1.5,  # 50% more time
        )
        indexing_time = time.time() - indexing_start

        logger.info(
            f"{'✅' if indexing_success else '❌'} Large document indexed in {indexing_time:.2f}s"
        )

        assert indexing_success, "Large document indexing failed"

        # Test RAG retrievability
        rag_start = time.time()
        rag_success = await test_client.test_rag_retrievability(document)
        rag_time = time.time() - rag_start

        logger.info(
            f"{'✅' if rag_success else '❌'} Large document RAG retrieval in {rag_time:.2f}s"
        )

        assert rag_success, "Large document not retrievable via RAG"

        # Total time validation (with extended threshold for large documents)
        total_time = creation_time + indexing_time + rag_time
        extended_pipeline_threshold = performance_thresholds["complete_pipeline"] * 1.5

        assert (
            total_time <= extended_pipeline_threshold
        ), f"Large document pipeline exceeded extended SLA: {total_time:.2f}s > {extended_pipeline_threshold}s"

        logger.info("🎉 SUCCESS: Large document processing test passed")

    async def test_document_with_special_characters(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """
        Test pipeline with documents containing special characters and unicode

        Validates that the system properly handles various character encodings
        and special content without corruption or failures.
        """
        logger.info("🔤 Testing document with special characters")

        special_content = {
            "test_scenario": "special_characters_processing",
            "unicode_text": "🚀 Testing Unicode: café, naïve, résumé, Москва, 北京, 東京, العربية",
            "special_symbols": "Special symbols: !@#$%^&*()_+-=[]{}|;':\",./<>?",
            "code_snippets": {
                "python": "def test_function():\n    return 'Hello, 世界!'",
                "json": '{"key": "value with spaces", "unicode": "🎉"}',
                "xml": "<root><item>Content & more</item></root>",
                "markdown": "# Header\n**Bold** and *italic* text\n- List item",
            },
            "multilingual_content": {
                "english": "This is English content for testing",
                "spanish": "Este es contenido en español para pruebas",
                "french": "Ceci est du contenu français pour les tests",
                "german": "Dies ist deutscher Inhalt für Tests",
                "japanese": "これはテスト用の日本語コンテンツです",
                "chinese": "这是用于测试的中文内容",
                "arabic": "هذا محتوى عربي للاختبار",
            },
            "mathematical_expressions": "Mathematical: α + β = γ, ∑(i=1 to n) xi, ∫f(x)dx",
            "chemical_formulas": "Chemical: H₂O, CO₂, CaCl₂, C₆H₁₂O₆",
            "edge_cases": {
                "empty_string": "",
                "null_representation": "null",
                "very_long_line": "This is a very long line that goes on and on " * 50,
                "nested_quotes": "\"He said 'Hello' to her\"",
                "backslashes": "Path\\to\\file\\with\\backslashes",
                "tabs_and_newlines": "Content\twith\ttabs\nand\nnewlines",
            },
        }

        # Create document with special characters
        document = await test_client.create_test_document(
            test_project,
            document_title="Special Characters Test Document 🔤",
            content_override=special_content,
        )

        logger.info("✅ Document with special characters created")

        # Wait for indexing
        indexing_success = await test_client.wait_for_indexing(document)
        assert indexing_success, "Special characters document indexing failed"

        logger.info("✅ Special characters document indexed")

        # Test RAG retrievability with various queries
        rag_queries = [
            "special characters",
            "unicode testing",
            "café naïve résumé",  # Accented characters
            "世界",  # Chinese characters
            "العربية",  # Arabic
            "mathematical expressions",
            "H₂O CO₂",  # Chemical formulas
        ]

        retrievable_queries = 0
        for query in rag_queries:
            try:
                mcp_request = {
                    "method": "perform_rag_query",
                    "params": {"query": query, "match_count": 5},
                }

                response = await test_client.http_client.post(
                    f"{test_client.session.services.mcp_server}/mcp",
                    json=mcp_request,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    result = response.json()
                    if "result" in result and "results" in result["result"]:
                        results = result["result"]["results"]
                        if any(document.id in str(r) for r in results):
                            retrievable_queries += 1
                            logger.info(f"✅ Document found via query: '{query}'")
                        else:
                            logger.info(f"❌ Document not found via query: '{query}'")

            except Exception as e:
                logger.warning(f"Query failed for '{query}': {e}")

        # We expect at least some queries to work
        assert (
            retrievable_queries > 0
        ), "No RAG queries successful for special characters document"

        logger.info(
            f"🎉 SUCCESS: Special characters test passed ({retrievable_queries}/{len(rag_queries)} queries successful)"
        )

    async def test_rapid_document_creation(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """
        Test rapid creation of multiple documents to validate system stability

        This test creates several documents in quick succession to ensure
        the system handles rapid requests without conflicts or failures.
        """
        logger.info("⚡ Testing rapid document creation")

        num_documents = 5
        creation_interval = 0.5  # seconds between creations

        # Create documents rapidly
        creation_tasks = []
        for i in range(num_documents):

            async def create_doc(doc_num):
                return await test_client.create_test_document(
                    test_project,
                    document_title=f"Rapid Creation Doc {doc_num}",
                    content_override={
                        "test_scenario": "rapid_document_creation",
                        "document_number": doc_num,
                        "creation_sequence": "rapid",
                        "test_content": f"Content for rapidly created document {doc_num}",
                    },
                )

            creation_tasks.append(create_doc(i + 1))

            # Small delay between starting tasks (not waiting for completion)
            if i < num_documents - 1:
                await asyncio.sleep(creation_interval)

        # Wait for all documents to be created
        documents = await asyncio.gather(*creation_tasks)

        logger.info(f"✅ Created {len(documents)} documents rapidly")

        # Verify all documents were created successfully
        assert (
            len(documents) == num_documents
        ), f"Expected {num_documents} documents, got {len(documents)}"

        # Wait for all documents to be indexed
        indexing_tasks = [
            test_client.wait_for_indexing(doc, max_wait_seconds=45.0)
            for doc in documents
        ]

        indexing_results = await asyncio.gather(*indexing_tasks)
        indexed_count = sum(indexing_results)

        logger.info(
            f"✅ {indexed_count}/{num_documents} rapidly created documents indexed"
        )

        # We expect most documents to be indexed successfully
        assert (
            indexed_count >= num_documents * 0.8
        ), f"Too many indexing failures: {indexed_count}/{num_documents} indexed"

        # Test RAG retrievability for successfully indexed documents
        rag_tasks = [
            test_client.test_rag_retrievability(doc)
            for doc, indexed in zip(documents, indexing_results)
            if indexed
        ]

        if rag_tasks:
            rag_results = await asyncio.gather(*rag_tasks)
            retrievable_count = sum(rag_results)

            logger.info(
                f"✅ {retrievable_count}/{len(rag_tasks)} rapidly created documents retrievable"
            )

            # We expect most indexed documents to be retrievable
            assert (
                retrievable_count >= len(rag_tasks) * 0.8
            ), f"Too many RAG failures: {retrievable_count}/{len(rag_tasks)} retrievable"

        logger.info("🎉 SUCCESS: Rapid document creation test passed")


@pytest.mark.smoke
@pytest.mark.happy_path
@pytest.mark.asyncio
class TestBasicSystemFunctionality:
    """
    Basic smoke tests to verify core system functionality

    These are quick tests that verify the system is operational
    and can handle basic operations.
    """

    async def test_service_health_check(self, test_client: IntegrationTestClient):
        """Verify all services are healthy and responding"""
        logger.info("🏥 Testing service health check")

        health_status = await test_client.check_service_health()

        # Log detailed health status
        for service, healthy in health_status.items():
            logger.info(
                f"{'✅' if healthy else '❌'} {service}: {'Healthy' if healthy else 'Unhealthy'}"
            )

        # Verify critical services are healthy
        critical_services = [
            "main_server",
            "mcp_server",
            "intelligence",
            "bridge",
            "search",
        ]

        for service in critical_services:
            assert health_status.get(
                service, False
            ), f"Critical service {service} is unhealthy"

        # At least 80% of all services should be healthy
        healthy_count = sum(health_status.values())
        total_count = len(health_status)
        health_percentage = (healthy_count / total_count) * 100

        assert (
            health_percentage >= 80
        ), f"System health below threshold: {health_percentage:.1f}% ({healthy_count}/{total_count})"

        logger.info(f"🎉 System health check passed: {health_percentage:.1f}% healthy")

    async def test_basic_mcp_functionality(self, test_client: IntegrationTestClient):
        """Test basic MCP server functionality"""
        logger.info("🔧 Testing basic MCP functionality")

        # Test session info
        mcp_request = {"method": "session_info", "params": {}}

        response = await test_client.http_client.post(
            f"{test_client.session.services.mcp_server}/mcp",
            json=mcp_request,
            timeout=10.0,
        )

        assert (
            response.status_code == 200
        ), f"MCP session_info failed: {response.status_code}"

        result = response.json()
        assert "result" in result, "MCP response missing result field"

        logger.info("✅ Basic MCP functionality verified")

    async def test_basic_project_operations(self, test_client: IntegrationTestClient):
        """Test basic project creation and retrieval"""
        logger.info("📁 Testing basic project operations")

        # Create a test project
        project = await test_client.create_test_project("Smoke Test Project")

        assert project.id is not None, "Project creation failed - no ID returned"
        assert "Smoke Test Project" in project.title, "Project title not set correctly"

        # Verify project exists by fetching it
        response = await test_client.http_client.get(
            f"{test_client.session.services.main_server}/api/projects/{project.id}"
        )

        assert (
            response.status_code == 200
        ), f"Project retrieval failed: {response.status_code}"

        project_data = response.json()
        assert project_data["id"] == project.id, "Retrieved project ID mismatch"

        logger.info("✅ Basic project operations verified")

    async def test_basic_document_creation(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Test basic document creation via MCP"""
        logger.info("📝 Testing basic document creation")

        document = await test_client.create_test_document(
            test_project,
            "Smoke Test Document",
            content_override={
                "test_type": "smoke_test",
                "basic_content": "Simple test content",
            },
        )

        assert document.id is not None, "Document creation failed - no ID returned"
        assert document.project_id == test_project.id, "Document project ID mismatch"
        assert (
            "Smoke Test Document" in document.title
        ), "Document title not set correctly"

        logger.info("✅ Basic document creation verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
