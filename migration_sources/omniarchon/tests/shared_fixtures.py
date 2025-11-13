"""
Shared test fixtures and utilities for Archon document ingestion pipeline testing.

This module provides standardized test data and utilities to ensure consistency
across all unit tests and catch content extraction bugs like the 26-38 character
truncation issue.
"""

import asyncio
import uuid
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock

import pytest

# Standardized Test Document Structure
STANDARDIZED_TEST_DOCUMENT = {
    "document_id": "test-doc-12345",
    "project_id": "test-project-67890",
    "document_data": {
        "title": "Test Document for Unit Testing",
        "content": {
            "content": "This is a comprehensive test document with substantial content that should be fully extracted and processed by all pipeline components. It contains multiple sentences to verify that content extraction works properly. The content should be much longer than 26-38 characters to catch content truncation bugs. This text is specifically designed to test the complete document processing pipeline from MCP creation through Bridge service content extraction, Intelligence service processing, Search service vectorization, and final RAG retrieval. Any truncation of this content indicates a bug in the pipeline that unit tests should catch.",
            "test_type": "unit_test_validation",
            "expected_behavior": "Full content extraction and processing",
        },
        "document_type": "test",
        "metadata": {
            "test_scenario": "content_extraction_validation",
            "expected_content_length": 500,
        },
    },
}

# Alternative test documents for various scenarios
NESTED_CONTENT_DOCUMENT = {
    "document_id": "test-nested-content",
    "project_id": "test-project-67890",
    "document_data": {
        "title": "Document with Nested Content Structure",
        "content": {
            "overview": "This document tests deeply nested content structures with multiple levels of nesting that must be properly extracted.",
            "sections": {
                "introduction": "Introduction section with substantial content for testing extraction depth.",
                "methodology": "Methodology section explaining the approach used in testing content extraction logic.",
                "results": "Results section containing findings about content processing pipeline effectiveness.",
                "conclusion": "Conclusion section summarizing the importance of proper content extraction.",
            },
            "metadata": {"word_count": 250, "complexity": "high"},
        },
        "document_type": "research",
        "metadata": {
            "test_scenario": "nested_content_extraction",
            "expected_behavior": "Extract content from all nested levels",
        },
    },
}

MINIMAL_CONTENT_DOCUMENT = {
    "document_id": "test-minimal-content",
    "project_id": "test-project-67890",
    "document_data": {
        "title": "Minimal Content Document",
        "content": {
            "text": "Short content that should still be fully extracted without truncation issues."
        },
        "document_type": "note",
        "metadata": {
            "test_scenario": "minimal_content_extraction",
            "expected_content_length": 75,
        },
    },
}

EMPTY_CONTENT_DOCUMENT = {
    "document_id": "test-empty-content",
    "project_id": "test-project-67890",
    "document_data": {
        "title": "Document with Empty Content",
        "content": {},
        "document_type": "placeholder",
        "metadata": {
            "test_scenario": "empty_content_handling",
            "expected_behavior": "Handle empty content gracefully",
        },
    },
}

STRING_CONTENT_DOCUMENT = {
    "document_id": "test-string-content",
    "project_id": "test-project-67890",
    "document_data": {
        "title": "Document with Direct String Content",
        "content": "This is direct string content rather than a dictionary structure. The content extraction logic must handle both dictionary and string content types properly to ensure full content is processed without truncation.",
        "document_type": "text",
        "metadata": {
            "test_scenario": "string_content_extraction",
            "expected_content_length": 200,
        },
    },
}


class MockConnectors:
    """Mock connectors for testing."""

    @staticmethod
    def create_mock_supabase_connector():
        """Create mock Supabase connector."""
        connector = AsyncMock()
        connector.health_check.return_value = True
        connector.execute_query.return_value = {
            "success": True,
            "data": [],
            "rows_affected": 0,
            "execution_time_ms": 10,
        }
        connector.initialize.return_value = None
        connector.close.return_value = None
        return connector

    @staticmethod
    def create_mock_memgraph_connector():
        """Create mock Memgraph connector."""
        connector = AsyncMock()
        connector.health_check.return_value = True
        connector.store_entities.return_value = True
        connector.create_relationship.return_value = True
        connector.get_entity.return_value = None
        connector.delete_entity.return_value = True
        connector.initialize.return_value = None
        connector.close.return_value = None
        return connector

    @staticmethod
    def create_mock_entity_mapper():
        """Create mock entity mapper."""
        mapper = AsyncMock()
        mapper.extract_and_map_content.return_value = [
            {
                "entity_id": "extracted_entity_1",
                "name": "Test Entity 1",
                "entity_type": "concept",
                "confidence_score": 0.85,
                "properties": {"source": "content_extraction"},
            },
            {
                "entity_id": "extracted_entity_2",
                "name": "Test Entity 2",
                "entity_type": "keyword",
                "confidence_score": 0.92,
                "properties": {"source": "content_extraction"},
            },
        ]
        mapper.map_source_to_graph.return_value = []
        mapper.get_mapping_statistics.return_value = {
            "total_entities": 100,
            "successful_mappings": 95,
            "failed_mappings": 5,
        }
        return mapper


class MockHTTPResponses:
    """Mock HTTP responses for testing external service calls."""

    @staticmethod
    def create_intelligence_success_response():
        """Create successful intelligence service response."""
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "success": True,
            "document_id": "test-doc-12345",
            "entities_extracted": 5,
            "vectorization_completed": True,
            "processing_time_ms": 1250,
            "status": "completed",
            "entities": [
                {
                    "entity_id": "entity_1",
                    "name": "Test Concept",
                    "type": "concept",
                    "confidence": 0.87,
                },
                {
                    "entity_id": "entity_2",
                    "name": "Test Process",
                    "type": "process",
                    "confidence": 0.93,
                },
            ],
        }
        return response

    @staticmethod
    def create_intelligence_failure_response():
        """Create failed intelligence service response."""
        response = Mock()
        response.status_code = 500
        response.text = "Internal server error during document processing"
        return response

    @staticmethod
    def create_search_vectorization_response():
        """Create successful search service vectorization response."""
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "success": True,
            "document_id": "test-doc-12345",
            "vector_id": "vec_12345",
            "dimensions": 1536,
            "vectorization_time_ms": 450,
            "indexed": True,
        }
        return response

    @staticmethod
    def create_rag_retrieval_response():
        """Create successful RAG retrieval response."""
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "success": True,
            "query": "test query",
            "results": [
                {
                    "document_id": "test-doc-12345",
                    "title": "Test Document for Unit Testing",
                    "content": "This is a comprehensive test document with substantial content...",
                    "score": 0.95,
                    "metadata": {
                        "document_type": "test",
                        "project_id": "test-project-67890",
                    },
                }
            ],
            "total_results": 1,
            "search_time_ms": 125,
        }
        return response


class ContentExtractionAssertions:
    """Assertion helpers for validating content extraction."""

    @staticmethod
    def assert_content_not_truncated(extracted_content: str, original_content: Any):
        """Assert that content is not truncated (specifically not 26-38 characters)."""
        assert (
            len(extracted_content) > 38
        ), f"Content appears truncated: {len(extracted_content)} chars (should be > 38)"
        assert (
            len(extracted_content) > 26
        ), f"Content appears truncated: {len(extracted_content)} chars (should be > 26)"

        # If original is string, ensure we got the full content
        if isinstance(original_content, str):
            assert (
                extracted_content.strip() in original_content
                or original_content in extracted_content.strip()
            )

    @staticmethod
    def assert_full_content_extraction(
        extracted_content: str, expected_min_length: int = 100
    ):
        """Assert that full content was extracted based on expected minimum length."""
        assert (
            len(extracted_content) >= expected_min_length
        ), f"Content extraction incomplete: {len(extracted_content)} < {expected_min_length}"
        assert (
            extracted_content.strip() != ""
        ), "Content extraction resulted in empty string"

    @staticmethod
    def assert_content_contains_keywords(extracted_content: str, keywords: List[str]):
        """Assert that extracted content contains expected keywords."""
        for keyword in keywords:
            assert (
                keyword.lower() in extracted_content.lower()
            ), f"Missing keyword '{keyword}' in extracted content"

    @staticmethod
    def assert_structured_content_flattened(
        extracted_content: str, original_dict: Dict[str, Any]
    ):
        """Assert that structured content was properly flattened."""
        if isinstance(original_dict, dict):
            for key, value in original_dict.items():
                if (
                    isinstance(value, str) and len(value) > 5
                ):  # Only check substantial string values
                    assert (
                        value in extracted_content
                    ), f"Missing content from key '{key}': {value[:50]}..."


# Pytest fixtures
@pytest.fixture
def standardized_test_document():
    """Provide the standardized test document."""
    return STANDARDIZED_TEST_DOCUMENT.copy()


@pytest.fixture
def nested_content_document():
    """Provide document with nested content structure."""
    return NESTED_CONTENT_DOCUMENT.copy()


@pytest.fixture
def minimal_content_document():
    """Provide document with minimal content."""
    return MINIMAL_CONTENT_DOCUMENT.copy()


@pytest.fixture
def empty_content_document():
    """Provide document with empty content."""
    return EMPTY_CONTENT_DOCUMENT.copy()


@pytest.fixture
def string_content_document():
    """Provide document with string content."""
    return STRING_CONTENT_DOCUMENT.copy()


@pytest.fixture
def mock_supabase_connector():
    """Provide mock Supabase connector."""
    return MockConnectors.create_mock_supabase_connector()


@pytest.fixture
def mock_memgraph_connector():
    """Provide mock Memgraph connector."""
    return MockConnectors.create_mock_memgraph_connector()


@pytest.fixture
def mock_entity_mapper():
    """Provide mock entity mapper."""
    return MockConnectors.create_mock_entity_mapper()


@pytest.fixture
def mock_intelligence_success():
    """Provide successful intelligence service response."""
    return MockHTTPResponses.create_intelligence_success_response()


@pytest.fixture
def mock_intelligence_failure():
    """Provide failed intelligence service response."""
    return MockHTTPResponses.create_intelligence_failure_response()


@pytest.fixture
def mock_search_response():
    """Provide successful search service response."""
    return MockHTTPResponses.create_search_vectorization_response()


@pytest.fixture
def mock_rag_response():
    """Provide successful RAG service response."""
    return MockHTTPResponses.create_rag_retrieval_response()


@pytest.fixture
def content_assertions():
    """Provide content extraction assertion helpers."""
    return ContentExtractionAssertions()


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Test data generators
def generate_large_document(content_size: int = 2000) -> Dict[str, Any]:
    """Generate a document with large content for stress testing."""
    large_content = "A" * content_size
    return {
        "document_id": f"test-large-{uuid.uuid4()}",
        "project_id": "test-project-67890",
        "document_data": {
            "title": f"Large Document ({content_size} chars)",
            "content": {
                "content": large_content,
                "size_info": f"Generated content of {content_size} characters",
            },
            "document_type": "stress_test",
            "metadata": {
                "test_scenario": "large_content_extraction",
                "expected_content_length": content_size,
            },
        },
    }


def generate_multi_section_document() -> Dict[str, Any]:
    """Generate document with multiple content sections."""
    return {
        "document_id": f"test-multi-{uuid.uuid4()}",
        "project_id": "test-project-67890",
        "document_data": {
            "title": "Multi-Section Document",
            "content": {
                "abstract": "This document contains multiple sections that must all be extracted properly during content processing.",
                "introduction": "The introduction section provides background information about the testing methodology.",
                "methodology": "The methodology section describes the systematic approach used for testing content extraction.",
                "results": "The results section presents findings from the content extraction validation tests.",
                "discussion": "The discussion section analyzes the implications of the test results for pipeline reliability.",
                "conclusion": "The conclusion section summarizes the key findings and recommendations for improvement.",
                "references": "References section lists sources and related documentation for further reading.",
            },
            "document_type": "article",
            "metadata": {
                "test_scenario": "multi_section_extraction",
                "sections_count": 7,
                "expected_content_length": 800,
            },
        },
    }


# Environment setup helpers
def setup_test_environment():
    """Setup test environment with required configurations."""
    import os

    os.environ.setdefault("INTELLIGENCE_SERVICE_URL", "http://test-intelligence:8053")
    os.environ.setdefault("SEARCH_SERVICE_URL", "http://test-search:8055")
    os.environ.setdefault("MEMGRAPH_URI", "bolt://localhost:7687")
    os.environ.setdefault("LOG_LEVEL", "DEBUG")


def cleanup_test_environment():
    """Cleanup test environment."""
    import os

    test_env_vars = [
        "INTELLIGENCE_SERVICE_URL",
        "SEARCH_SERVICE_URL",
        "MEMGRAPH_URI",
        "TEST_MODE",
    ]
    for var in test_env_vars:
        os.environ.pop(var, None)


if __name__ == "__main__":
    # Validate test document structure
    print("Validating standardized test document...")
    doc = STANDARDIZED_TEST_DOCUMENT
    content = doc["document_data"]["content"]["content"]
    print(f"Content length: {len(content)} characters")
    print(f"Content preview: {content[:100]}...")

    # Validate all test documents
    all_docs = [
        STANDARDIZED_TEST_DOCUMENT,
        NESTED_CONTENT_DOCUMENT,
        MINIMAL_CONTENT_DOCUMENT,
        STRING_CONTENT_DOCUMENT,
    ]

    print(f"\nValidated {len(all_docs)} test documents")
    for doc in all_docs:
        scenario = (
            doc["document_data"].get("metadata", {}).get("test_scenario", "unknown")
        )
        print(f"- {scenario}: {doc['document_id']}")
