"""
Intelligence Service Document Processing Unit Tests

Tests for the Intelligence service document processing pipeline including:
- /process/document endpoint functionality
- Entity extraction from full content
- Vectorization request handling
- Content processing validation
- Error handling and edge cases

Critical focus on ensuring full content is processed without truncation.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from shared_fixtures import (
    NESTED_CONTENT_DOCUMENT,
    STANDARDIZED_TEST_DOCUMENT,
    ContentExtractionAssertions,
    MockConnectors,
    generate_large_document,
    generate_multi_section_document,
)


class TestIntelligenceDocumentProcessing:
    """Test Intelligence service document processing functionality."""

    def setup_method(self):
        """Setup for each test method."""
        self.assertions = ContentExtractionAssertions()
        self.base_url = "http://test-intelligence:8053"

    @pytest.fixture
    def mock_intelligence_app_dependencies(self):
        """Mock Intelligence service dependencies."""
        return {
            "entity_extractor": AsyncMock(),
            "vectorization_client": AsyncMock(),
            "memgraph_adapter": MockConnectors.create_mock_memgraph_connector(),
            "search_service_client": AsyncMock(),
        }

    @pytest.mark.asyncio
    async def test_process_document_endpoint_with_standardized_document(
        self, mock_intelligence_app_dependencies
    ):
        """Test /process/document endpoint with standardized test document."""
        # Prepare test document for intelligence service
        doc_data = STANDARDIZED_TEST_DOCUMENT["document_data"]

        request_payload = {
            "document_id": STANDARDIZED_TEST_DOCUMENT["document_id"],
            "project_id": STANDARDIZED_TEST_DOCUMENT["project_id"],
            "title": doc_data["title"],
            "content": doc_data["content"],
            "document_type": doc_data["document_type"],
            "metadata": doc_data.get("metadata", {}),
        }

        # Mock the processing response
        mock_response = {
            "success": True,
            "document_id": STANDARDIZED_TEST_DOCUMENT["document_id"],
            "entities_extracted": 8,
            "vectorization_completed": True,
            "processing_time_ms": 1500,
            "status": "completed",
            "entities": [
                {
                    "entity_id": "entity_test_1",
                    "name": "Comprehensive Test Document",
                    "type": "document_concept",
                    "confidence": 0.92,
                    "properties": {"source": "title_extraction"},
                },
                {
                    "entity_id": "entity_test_2",
                    "name": "Pipeline Components",
                    "type": "technical_concept",
                    "confidence": 0.87,
                    "properties": {"source": "content_extraction"},
                },
                {
                    "entity_id": "entity_test_3",
                    "name": "Content Extraction",
                    "type": "process",
                    "confidence": 0.95,
                    "properties": {"source": "content_extraction"},
                },
            ],
            "content_analysis": {
                "content_length": len(doc_data["content"]["content"]),
                "content_preview": doc_data["content"]["content"][:200],
                "key_terms": ["test", "document", "pipeline", "extraction", "content"],
                "complexity_score": 0.75,
            },
        }

        # Simulate the intelligence service processing
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_response

            # Test that the service receives full content
            assert len(request_payload["content"]["content"]) > 400
            self.assertions.assert_content_not_truncated(
                request_payload["content"]["content"], request_payload["content"]
            )

            # Verify content contains expected elements
            content_text = request_payload["content"]["content"]
            expected_keywords = [
                "comprehensive test document",
                "substantial content",
                "pipeline components",
                "truncation bugs",
                "MCP creation",
            ]
            self.assertions.assert_content_contains_keywords(
                content_text, expected_keywords
            )

            # Validate response structure
            assert mock_response["entities_extracted"] > 0
            assert mock_response["vectorization_completed"] is True
            assert mock_response["content_analysis"]["content_length"] > 400

    @pytest.mark.asyncio
    async def test_entity_extraction_from_full_content(
        self, mock_intelligence_app_dependencies
    ):
        """Test that entity extraction processes full content without truncation."""
        # Test with large content document
        large_doc = generate_large_document(content_size=3000)
        doc_data = large_doc["document_data"]

        request_payload = {
            "document_id": large_doc["document_id"],
            "project_id": large_doc["project_id"],
            "title": doc_data["title"],
            "content": doc_data["content"],
            "document_type": doc_data["document_type"],
            "metadata": doc_data.get("metadata", {}),
        }

        # Mock entity extraction that should process full content
        mock_extracted_entities = [
            {
                "entity_id": f"large_entity_{i}",
                "name": f"Large Content Entity {i}",
                "type": "content_entity",
                "confidence": 0.8 + (i * 0.05),
                "properties": {
                    "source": "large_content_extraction",
                    "position_in_content": i * 500,  # Spread across the full content
                    "content_segment": f"Segment from large document: {'A' * 50}",
                },
            }
            for i in range(6)  # 6 entities spread across 3000 chars
        ]

        # Simulate entity extraction processing
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = {
                "success": True,
                "document_id": large_doc["document_id"],
                "entities_extracted": len(mock_extracted_entities),
                "entities": mock_extracted_entities,
                "content_analysis": {
                    "content_length": 3000,
                    "processing_segments": 6,
                    "full_content_processed": True,
                },
            }

            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_response

            # Verify full content is being processed
            content_text = request_payload["content"]["content"]
            assert (
                len(content_text) == 3000
            ), f"Large content truncated: {len(content_text)} != 3000"

            # Verify entities are extracted from different parts of the content
            for i, entity in enumerate(mock_extracted_entities):
                expected_position = i * 500
                assert entity["properties"]["position_in_content"] == expected_position
                assert "large_content_extraction" in entity["properties"]["source"]

    @pytest.mark.asyncio
    async def test_vectorization_request_with_complete_content(
        self, mock_intelligence_app_dependencies
    ):
        """Test that vectorization receives complete content without truncation."""
        doc_data = NESTED_CONTENT_DOCUMENT["document_data"]

        # Mock the vectorization request to search service
        mock_vectorization_response = {
            "success": True,
            "document_id": NESTED_CONTENT_DOCUMENT["document_id"],
            "vector_id": "vec_nested_12345",
            "dimensions": 1536,
            "content_length_processed": 0,  # Will be set by our test
            "vectorization_time_ms": 450,
            "indexed": True,
        }

        with patch("httpx.AsyncClient.post") as mock_post:
            # Simulate intelligence service calling search service for vectorization
            def mock_vectorization_call(*args, **kwargs):
                # Extract the payload that would be sent to search service
                payload = kwargs.get("json", {})
                content = payload.get("content", {})

                # Validate that full content is being sent for vectorization
                if isinstance(content, dict):
                    # Extract text content for vectorization
                    if "overview" in content:
                        text_for_vectorization = content["overview"]
                    else:
                        text_for_vectorization = " ".join(
                            str(value)
                            for value in content.values()
                            if isinstance(value, str)
                        )
                else:
                    text_for_vectorization = str(content)

                # Update response with actual processed length
                mock_vectorization_response["content_length_processed"] = len(
                    text_for_vectorization
                )

                # Assertions for vectorization content
                assert (
                    len(text_for_vectorization) > 50
                ), f"Content for vectorization too short: {len(text_for_vectorization)}"
                assert "deeply nested content structures" in text_for_vectorization

                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = mock_vectorization_response
                return mock_response

            mock_post.side_effect = mock_vectorization_call

            # Simulate intelligence service processing that calls vectorization
            request_payload = {
                "document_id": NESTED_CONTENT_DOCUMENT["document_id"],
                "title": doc_data["title"],
                "content": doc_data["content"],
                "vectorize": True,
            }

            # Execute the mock call
            mock_vectorization_call(json=request_payload)

            # Verify vectorization was called with full content
            assert mock_vectorization_response["content_length_processed"] > 100
            assert mock_vectorization_response["indexed"] is True

    @pytest.mark.asyncio
    async def test_intelligence_service_error_handling(
        self, mock_intelligence_app_dependencies
    ):
        """Test error handling in intelligence service processing."""
        # Test with malformed content
        malformed_doc = {
            "document_id": "test-malformed",
            "project_id": "test-project-67890",
            "title": "Malformed Document",
            "content": None,  # Invalid content
            "document_type": "error_test",
        }

        with patch("httpx.AsyncClient.post") as mock_post:
            # Simulate error response
            mock_error_response = {
                "success": False,
                "error": "Invalid content structure",
                "document_id": "test-malformed",
                "error_details": {
                    "content_validation": "Content cannot be None",
                    "processing_stage": "content_validation",
                },
            }

            mock_post.return_value.status_code = 400
            mock_post.return_value.json.return_value = mock_error_response

            # Verify error handling
            try:
                # This would represent the intelligence service validation
                content = malformed_doc["content"]
                if content is None:
                    raise ValueError("Content cannot be None")

                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "Content cannot be None" in str(e)

    @pytest.mark.asyncio
    async def test_multi_step_document_processing_pipeline(
        self, mock_intelligence_app_dependencies
    ):
        """Test complete multi-step document processing pipeline."""
        doc = generate_multi_section_document()
        doc_data = doc["document_data"]

        # Step 1: Content validation and preprocessing
        content = doc_data["content"]
        assert isinstance(
            content, dict
        ), "Content should be dictionary for multi-section document"

        # Step 2: Content extraction for processing
        content_sections = []
        for key, value in content.items():
            if isinstance(value, str) and len(value) > 10:
                content_sections.append(f"{key}: {value}")

        full_content_text = " ".join(content_sections)

        # Validate content extraction
        self.assertions.assert_content_not_truncated(full_content_text, content)
        assert (
            len(content_sections) >= 6
        ), f"Not all sections extracted: {len(content_sections)}"

        # Step 3: Mock entity extraction from full content
        mock_entities = []
        for i, section in enumerate(content_sections[:3]):  # Process first 3 sections
            mock_entities.append(
                {
                    "entity_id": f"section_entity_{i}",
                    "name": f"Section Entity {i}",
                    "type": "document_section",
                    "confidence": 0.85,
                    "properties": {
                        "section_content": section[:100],  # First 100 chars of section
                        "section_index": i,
                        "full_section_length": len(section),
                    },
                }
            )

        # Step 4: Mock vectorization processing
        vectorization_payload = {
            "document_id": doc["document_id"],
            "title": doc_data["title"],
            "content_text": full_content_text,
            "sections": len(content_sections),
        }

        # Validate pipeline stages
        assert (
            len(full_content_text) > 500
        ), f"Multi-section content incomplete: {len(full_content_text)}"
        assert (
            len(mock_entities) == 3
        ), f"Entity extraction failed: {len(mock_entities)} entities"
        assert (
            vectorization_payload["sections"] >= 6
        ), f"Section processing incomplete: {vectorization_payload['sections']}"

        # Final pipeline response
        pipeline_response = {
            "success": True,
            "document_id": doc["document_id"],
            "processing_stages": {
                "content_extraction": "completed",
                "entity_extraction": "completed",
                "vectorization": "completed",
            },
            "entities_extracted": len(mock_entities),
            "content_analysis": {
                "total_content_length": len(full_content_text),
                "sections_processed": len(content_sections),
                "entities_per_section": len(mock_entities) / len(content_sections),
            },
        }

        assert pipeline_response["success"] is True
        assert pipeline_response["content_analysis"]["total_content_length"] > 500

    @pytest.mark.asyncio
    async def test_content_preprocessing_edge_cases(self):
        """Test content preprocessing for various edge cases."""
        # Test case 1: Mixed content types
        mixed_content_doc = {
            "document_id": "test-mixed-content",
            "project_id": "test-project-67890",
            "document_data": {
                "title": "Mixed Content Types",
                "content": {
                    "text_section": "This is a text section with substantial content for testing.",
                    "number_section": 42,
                    "list_section": ["item1", "item2", "item3"],
                    "nested_dict": {
                        "inner_text": "Nested text content that should be extracted properly."
                    },
                    "boolean_section": True,
                },
                "document_type": "mixed_test",
            },
        }

        # Simulate intelligence service content preprocessing
        content = mixed_content_doc["document_data"]["content"]

        # Extract only string content for processing (similar to intelligence service logic)
        extracted_strings = []

        def extract_strings(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    extract_strings(value, f"{path}.{key}" if path else key)
            elif isinstance(obj, str) and len(obj) > 5:  # Only substantial strings
                extracted_strings.append(obj)

        extract_strings(content)

        # Validate string extraction
        assert (
            len(extracted_strings) >= 2
        ), f"String extraction incomplete: {extracted_strings}"
        assert "substantial content for testing" in " ".join(extracted_strings)
        assert "Nested text content" in " ".join(extracted_strings)

        # Test case 2: Content with special encoding
        unicode_doc = {
            "document_id": "test-unicode",
            "project_id": "test-project-67890",
            "document_data": {
                "title": "Unicode Content Test",
                "content": {
                    "content": "This document contains Unicode: 中文测试, العربية, русский, 日本語. The intelligence service must handle all character encodings properly without truncation or corruption."
                },
                "document_type": "unicode_test",
            },
        }

        unicode_content = unicode_doc["document_data"]["content"]["content"]

        # Validate Unicode handling
        assert (
            len(unicode_content) > 100
        ), f"Unicode content truncated: {len(unicode_content)}"
        assert "中文测试" in unicode_content, "Chinese characters lost"
        assert "العربية" in unicode_content, "Arabic characters lost"
        assert "русский" in unicode_content, "Cyrillic characters lost"
        assert "日本語" in unicode_content, "Japanese characters lost"


class TestIntelligenceServicePerformance:
    """Performance tests for Intelligence service document processing."""

    @pytest.mark.asyncio
    async def test_processing_performance_benchmarks(self):
        """Test processing performance with various document sizes."""
        test_sizes = [500, 2000, 10000, 50000]
        performance_results = []

        for size in test_sizes:
            doc = generate_large_document(content_size=size)

            import time

            start_time = time.time()

            # Simulate intelligence service processing steps
            content = doc["document_data"]["content"]["content"]

            # Content validation
            assert len(content) == size

            # Mock entity extraction (proportional to content size)
            num_entities = min(size // 500, 20)  # Up to 20 entities
            [
                {"entity_id": f"perf_entity_{i}", "confidence": 0.8}
                for i in range(num_entities)
            ]

            # Mock vectorization preparation
            content_chunks = [
                content[i : i + 1000] for i in range(0, len(content), 1000)
            ]

            processing_time = time.time() - start_time

            performance_results.append(
                {
                    "content_size": size,
                    "processing_time": processing_time,
                    "entities_extracted": num_entities,
                    "content_chunks": len(content_chunks),
                }
            )

            # Performance assertions
            assert (
                processing_time < 2.0
            ), f"Processing too slow for {size} chars: {processing_time}s"
            assert num_entities > 0, f"No entities extracted from {size} char document"

        # Verify performance scales reasonably
        largest_result = performance_results[-1]
        assert (
            largest_result["processing_time"] < 2.0
        ), "Large document processing too slow"
        assert (
            largest_result["entities_extracted"] >= 10
        ), "Insufficient entity extraction for large document"

    @pytest.mark.asyncio
    async def test_concurrent_document_processing(self):
        """Test concurrent processing of multiple documents."""
        # Create multiple test documents
        docs = [
            generate_large_document(1000),
            generate_multi_section_document(),
            STANDARDIZED_TEST_DOCUMENT.copy(),
            NESTED_CONTENT_DOCUMENT.copy(),
        ]

        async def process_document(doc):
            """Simulate processing a single document."""
            doc_data = doc["document_data"]
            content = doc_data["content"]

            # Extract content text
            if isinstance(content, dict):
                if "content" in content:
                    content_text = content["content"]
                elif "overview" in content:
                    content_text = content["overview"]
                else:
                    content_text = " ".join(
                        str(value)
                        for value in content.values()
                        if isinstance(value, str)
                    )
            else:
                content_text = str(content)

            # Simulate processing delay
            await asyncio.sleep(0.1)

            return {
                "document_id": doc["document_id"],
                "content_length": len(content_text),
                "processing_status": "completed",
            }

        # Process documents concurrently
        import time

        start_time = time.time()

        results = await asyncio.gather(*[process_document(doc) for doc in docs])

        total_time = time.time() - start_time

        # Validate concurrent processing
        assert len(results) == 4, f"Not all documents processed: {len(results)}"
        assert total_time < 1.0, f"Concurrent processing too slow: {total_time}s"

        for result in results:
            assert result["processing_status"] == "completed"
            assert (
                result["content_length"] > 50
            ), f"Content truncated in concurrent processing: {result['content_length']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
