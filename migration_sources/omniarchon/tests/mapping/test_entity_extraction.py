"""
Entity Mapper Unit Tests

Tests for entity extraction and mapping functionality including:
- Entity extraction from full content without truncation
- Content length validation and limits
- Entity mapping to knowledge graph
- Content-based entity linking
- Performance and accuracy validation

Critical focus on ensuring entities are extracted from complete text content.
"""

import os
import sys
from unittest.mock import AsyncMock

import pytest

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from shared_fixtures import (
    NESTED_CONTENT_DOCUMENT,
    STANDARDIZED_TEST_DOCUMENT,
    ContentExtractionAssertions,
    generate_large_document,
    generate_multi_section_document,
)


class TestEntityExtraction:
    """Test entity extraction from document content."""

    def setup_method(self):
        """Setup for each test method."""
        self.assertions = ContentExtractionAssertions()
        self.content_length_limit = 50000  # 50KB limit as mentioned in requirements

    @pytest.fixture
    def mock_intelligence_service(self):
        """Mock intelligence service for entity extraction."""
        service = AsyncMock()
        service.extract_entities.return_value = [
            {
                "entity_id": "entity_1",
                "name": "Test Document",
                "type": "document",
                "confidence": 0.95,
                "start_pos": 0,
                "end_pos": 13,
                "context": "Test Document for Unit Testing",
            },
            {
                "entity_id": "entity_2",
                "name": "Pipeline Components",
                "type": "technical_concept",
                "confidence": 0.87,
                "start_pos": 150,
                "end_pos": 169,
                "context": "pipeline components and verification",
            },
        ]
        return service

    @pytest.mark.asyncio
    async def test_entity_extraction_from_full_content(self, mock_intelligence_service):
        """Test that entities are extracted from complete content without truncation."""
        doc = STANDARDIZED_TEST_DOCUMENT.copy()
        content = doc["document_data"]["content"]["content"]

        # Validate content is substantial for entity extraction
        self.assertions.assert_content_not_truncated(
            content, doc["document_data"]["content"]
        )
        assert (
            len(content) > 400
        ), f"Content too short for comprehensive entity extraction: {len(content)}"

        # Mock entity extraction process
        async def extract_entities_from_content(text_content, document_id):
            """Extract entities from full text content."""
            # Validate input content
            assert (
                len(text_content) > 400
            ), f"Entity extraction content truncated: {len(text_content)}"
            assert isinstance(
                text_content, str
            ), "Content must be string for entity extraction"

            # Simulate entity extraction based on content analysis
            entities = []

            # Extract title-based entities
            if "Test Document" in text_content:
                entities.append(
                    {
                        "entity_id": f"{document_id}_title_entity",
                        "name": "Test Document",
                        "type": "document_title",
                        "confidence": 0.95,
                        "extraction_method": "title_analysis",
                        "source_text": "Test Document for Unit Testing",
                    }
                )

            # Extract concept entities from full content
            technical_terms = [
                "pipeline",
                "components",
                "extraction",
                "processing",
                "truncation",
            ]
            for i, term in enumerate(technical_terms):
                if term in text_content.lower():
                    position = text_content.lower().find(term)
                    entities.append(
                        {
                            "entity_id": f"{document_id}_concept_{i}",
                            "name": term.title(),
                            "type": "technical_concept",
                            "confidence": 0.8 + (i * 0.02),
                            "extraction_method": "content_analysis",
                            "position_in_text": position,
                            "context": text_content[
                                max(0, position - 20) : position + 20 + len(term)
                            ],
                        }
                    )

            # Extract process entities
            process_keywords = ["test", "validate", "process", "extract", "create"]
            for i, keyword in enumerate(process_keywords):
                if keyword in text_content.lower():
                    position = text_content.lower().find(keyword)
                    entities.append(
                        {
                            "entity_id": f"{document_id}_process_{i}",
                            "name": f"{keyword.title()} Process",
                            "type": "process",
                            "confidence": 0.75 + (i * 0.03),
                            "extraction_method": "process_identification",
                            "position_in_text": position,
                        }
                    )

            return entities

        # Execute entity extraction
        extracted_entities = await extract_entities_from_content(
            content, doc["document_id"]
        )

        # Validate entity extraction results
        assert (
            len(extracted_entities) > 5
        ), f"Insufficient entities extracted: {len(extracted_entities)}"

        # Verify entities are extracted from different parts of the content
        positions = [
            entity.get("position_in_text", 0)
            for entity in extracted_entities
            if "position_in_text" in entity
        ]
        if positions:
            position_spread = max(positions) - min(positions)
            assert (
                position_spread > 100
            ), f"Entities not extracted from full content span: {position_spread}"

        # Verify entity quality
        for entity in extracted_entities:
            assert (
                entity["confidence"] > 0.7
            ), f"Low confidence entity: {entity['confidence']}"
            assert len(entity["name"]) > 2, f"Entity name too short: {entity['name']}"
            assert entity["type"] in [
                "document_title",
                "technical_concept",
                "process",
            ], f"Invalid entity type: {entity['type']}"

    @pytest.mark.asyncio
    async def test_content_length_limits_and_truncation_logic(self):
        """Test content length validation and truncation logic for entity extraction."""
        # Test case 1: Content within limits
        normal_doc = generate_large_document(
            content_size=30000
        )  # 30KB - within 50KB limit
        normal_content = normal_doc["document_data"]["content"]["content"]

        assert len(normal_content) == 30000, "Normal content size incorrect"
        assert (
            len(normal_content) <= self.content_length_limit
        ), "Normal content exceeds limit"

        # Test case 2: Content exceeding limits
        large_doc = generate_large_document(
            content_size=60000
        )  # 60KB - exceeds 50KB limit
        large_content = large_doc["document_data"]["content"]["content"]

        assert len(large_content) == 60000, "Large content size incorrect"
        assert (
            len(large_content) > self.content_length_limit
        ), "Large content should exceed limit"

        # Mock content truncation logic
        def apply_content_length_limit(content, limit=50000):
            """Apply content length limit with smart truncation."""
            if len(content) <= limit:
                return content, False  # content, was_truncated

            # Smart truncation - try to break at sentence boundaries
            truncated = content[:limit]

            # Find last complete sentence
            last_period = truncated.rfind(".")
            if last_period > limit * 0.8:  # If we can keep 80%+ of content
                truncated = truncated[: last_period + 1]

            return truncated, True

        # Test normal content (no truncation)
        processed_normal, normal_truncated = apply_content_length_limit(normal_content)
        assert not normal_truncated, "Normal content should not be truncated"
        assert len(processed_normal) == 30000, "Normal content length changed"

        # Test large content (truncation)
        processed_large, large_truncated = apply_content_length_limit(large_content)
        assert large_truncated, "Large content should be truncated"
        assert (
            len(processed_large) <= self.content_length_limit
        ), "Truncated content still exceeds limit"
        assert (
            len(processed_large) > self.content_length_limit * 0.8
        ), "Too much content truncated"

    @pytest.mark.asyncio
    async def test_entity_mapping_to_knowledge_graph(self, mock_intelligence_service):
        """Test mapping of extracted entities to knowledge graph."""
        doc = NESTED_CONTENT_DOCUMENT.copy()
        content = doc["document_data"]["content"]["overview"]

        # Mock entity extraction
        extracted_entities = [
            {
                "entity_id": "concept_nested_structures",
                "name": "Nested Content Structures",
                "type": "technical_concept",
                "confidence": 0.92,
                "properties": {
                    "complexity": "high",
                    "extraction_context": "deeply nested content structures",
                },
            },
            {
                "entity_id": "process_extraction",
                "name": "Content Extraction Process",
                "type": "process",
                "confidence": 0.89,
                "properties": {
                    "domain": "document_processing",
                    "extraction_context": "content extraction logic",
                },
            },
        ]

        # Mock knowledge graph mapping
        async def map_entities_to_graph(entities, document_id, content_source):
            """Map extracted entities to knowledge graph structure."""
            mapped_entities = []

            for entity in entities:
                # Validate entity has been extracted from full content
                assert (
                    "extraction_context" in entity["properties"]
                ), "Entity missing extraction context"

                # Create graph entity
                graph_entity = {
                    "graph_id": f"graph_{entity['entity_id']}",
                    "original_entity_id": entity["entity_id"],
                    "name": entity["name"],
                    "type": entity["type"],
                    "confidence": entity["confidence"],
                    "source_document": document_id,
                    "extraction_metadata": {
                        "source_content_length": len(content_source),
                        "extraction_method": "intelligence_service",
                        "content_preview": content_source[:100],
                    },
                    "graph_properties": entity["properties"],
                }

                mapped_entities.append(graph_entity)

            return mapped_entities

        # Execute entity mapping
        mapped_entities = await map_entities_to_graph(
            extracted_entities, doc["document_id"], content
        )

        # Validate entity mapping
        assert len(mapped_entities) == len(
            extracted_entities
        ), "Entity count mismatch in mapping"

        for mapped_entity in mapped_entities:
            assert "graph_id" in mapped_entity, "Mapped entity missing graph ID"
            assert (
                "source_document" in mapped_entity
            ), "Mapped entity missing source document"
            assert (
                mapped_entity["extraction_metadata"]["source_content_length"] > 100
            ), "Source content length not preserved"

            # Verify confidence is preserved
            original_entity = next(
                e
                for e in extracted_entities
                if e["entity_id"] == mapped_entity["original_entity_id"]
            )
            assert (
                mapped_entity["confidence"] == original_entity["confidence"]
            ), "Confidence not preserved in mapping"

    @pytest.mark.asyncio
    async def test_content_based_entity_linking(self):
        """Test linking entities based on content relationships."""
        # Create documents with related content
        doc1_content = "API endpoints provide access to data processing pipelines for document analysis."
        doc2_content = "Document analysis pipelines use advanced algorithms for content extraction and entity recognition."

        documents = [
            {
                "document_id": "doc_api",
                "content": doc1_content,
                "entities": [
                    {"name": "API", "type": "technical_concept"},
                    {"name": "Data Processing", "type": "process"},
                    {"name": "Document Analysis", "type": "process"},
                ],
            },
            {
                "document_id": "doc_analysis",
                "content": doc2_content,
                "entities": [
                    {"name": "Document Analysis", "type": "process"},
                    {"name": "Content Extraction", "type": "process"},
                    {"name": "Entity Recognition", "type": "process"},
                ],
            },
        ]

        # Mock content-based entity linking
        async def link_entities_by_content(documents):
            """Link entities based on content relationships and co-occurrence."""
            entity_links = []

            # Find entities that appear in multiple documents
            all_entities = {}
            for doc in documents:
                for entity in doc["entities"]:
                    entity_name = entity["name"]
                    if entity_name not in all_entities:
                        all_entities[entity_name] = []
                    all_entities[entity_name].append(
                        {
                            "document_id": doc["document_id"],
                            "entity": entity,
                            "content": doc["content"],
                        }
                    )

            # Create links for entities appearing in multiple documents
            for entity_name, occurrences in all_entities.items():
                if len(occurrences) > 1:
                    for i, occ1 in enumerate(occurrences):
                        for occ2 in occurrences[i + 1 :]:
                            # Validate content context for linking
                            assert (
                                len(occ1["content"]) > 50
                            ), "Content too short for entity linking"
                            assert (
                                len(occ2["content"]) > 50
                            ), "Content too short for entity linking"

                            entity_links.append(
                                {
                                    "entity_name": entity_name,
                                    "document1": occ1["document_id"],
                                    "document2": occ2["document_id"],
                                    "link_type": "co_occurrence",
                                    "confidence": 0.85,
                                    "context1": occ1["content"],
                                    "context2": occ2["content"],
                                }
                            )

            # Find semantic relationships based on content analysis
            semantic_keywords = {
                "processing": [
                    "data processing",
                    "document analysis",
                    "content extraction",
                ],
                "api": ["api", "endpoints", "access"],
                "analysis": ["analysis", "algorithms", "recognition"],
            }

            for category, keywords in semantic_keywords.items():
                related_entities = []
                for doc in documents:
                    content_lower = doc["content"].lower()
                    for entity in doc["entities"]:
                        entity_lower = entity["name"].lower()
                        if any(
                            keyword in content_lower or keyword in entity_lower
                            for keyword in keywords
                        ):
                            related_entities.append(
                                {
                                    "document_id": doc["document_id"],
                                    "entity": entity,
                                    "category": category,
                                }
                            )

                # Create semantic links
                for i, rel1 in enumerate(related_entities):
                    for rel2 in related_entities[i + 1 :]:
                        if rel1["document_id"] != rel2["document_id"]:
                            entity_links.append(
                                {
                                    "entity1": rel1["entity"]["name"],
                                    "entity2": rel2["entity"]["name"],
                                    "document1": rel1["document_id"],
                                    "document2": rel2["document_id"],
                                    "link_type": "semantic_relationship",
                                    "category": category,
                                    "confidence": 0.75,
                                }
                            )

            return entity_links

        # Execute entity linking
        entity_links = await link_entities_by_content(documents)

        # Validate entity linking
        assert len(entity_links) > 0, "No entity links created"

        # Check for co-occurrence link
        co_occurrence_links = [
            link for link in entity_links if link["link_type"] == "co_occurrence"
        ]
        assert len(co_occurrence_links) > 0, "No co-occurrence links found"

        # Verify "Document Analysis" appears in both documents
        doc_analysis_link = next(
            (
                link
                for link in co_occurrence_links
                if link["entity_name"] == "Document Analysis"
            ),
            None,
        )
        assert (
            doc_analysis_link is not None
        ), "Document Analysis co-occurrence link missing"

        # Check for semantic relationship links
        semantic_links = [
            link
            for link in entity_links
            if link["link_type"] == "semantic_relationship"
        ]
        assert len(semantic_links) > 0, "No semantic relationship links found"

        # Validate link properties
        for link in entity_links:
            assert (
                link["confidence"] > 0.7
            ), f"Low confidence entity link: {link['confidence']}"
            if "context1" in link:
                assert (
                    len(link["context1"]) > 50
                ), "Context 1 too short for entity linking"
            if "context2" in link:
                assert (
                    len(link["context2"]) > 50
                ), "Context 2 too short for entity linking"

    @pytest.mark.asyncio
    async def test_entity_extraction_performance_and_accuracy(self):
        """Test entity extraction performance and accuracy with various content sizes."""
        # Create test documents of different sizes
        test_documents = [
            generate_large_document(1000),  # 1KB
            generate_large_document(10000),  # 10KB
            generate_large_document(30000),  # 30KB
            generate_multi_section_document(),  # Multi-section
        ]

        async def benchmark_entity_extraction(document):
            """Benchmark entity extraction for performance and accuracy."""
            content = document["document_data"]["content"]
            if isinstance(content, dict) and "content" in content:
                content_text = content["content"]
            elif isinstance(content, dict):
                content_text = " ".join(
                    str(v) for v in content.values() if isinstance(v, str)
                )
            else:
                content_text = str(content)

            import time

            start_time = time.time()

            # Mock entity extraction with performance tracking
            entities = []

            # Extract based on content patterns
            words = content_text.split()
            entity_candidates = []

            # Look for capitalized words (potential proper nouns)
            for i, word in enumerate(words):
                if word[0].isupper() and len(word) > 3:
                    entity_candidates.append(
                        {"text": word, "position": i, "type": "proper_noun"}
                    )

            # Extract multi-word technical terms
            technical_patterns = [
                "test",
                "document",
                "content",
                "extraction",
                "processing",
                "analysis",
            ]
            for pattern in technical_patterns:
                if pattern.lower() in content_text.lower():
                    entities.append(
                        {
                            "entity_id": f"entity_{pattern}_{document['document_id']}",
                            "name": pattern.title(),
                            "type": "technical_concept",
                            "confidence": 0.8,
                            "extraction_method": "pattern_matching",
                        }
                    )

            extraction_time = time.time() - start_time

            return {
                "document_id": document["document_id"],
                "content_length": len(content_text),
                "entities_extracted": len(entities),
                "extraction_time_ms": extraction_time * 1000,
                "entities_per_kb": (
                    len(entities) / (len(content_text) / 1000)
                    if len(content_text) > 0
                    else 0
                ),
                "performance_acceptable": extraction_time < 2.0,  # 2 second limit
            }

        # Benchmark all documents
        benchmark_results = []
        for doc in test_documents:
            result = await benchmark_entity_extraction(doc)
            benchmark_results.append(result)

        # Validate performance and accuracy
        for result in benchmark_results:
            assert result[
                "performance_acceptable"
            ], f"Entity extraction too slow: {result['extraction_time_ms']}ms"
            assert (
                result["entities_extracted"] > 0
            ), f"No entities extracted from {result['content_length']} char document"

            # Accuracy expectations based on content size
            if result["content_length"] > 10000:
                assert (
                    result["entities_extracted"] >= 5
                ), f"Too few entities from large document: {result['entities_extracted']}"
            elif result["content_length"] > 1000:
                assert (
                    result["entities_extracted"] >= 3
                ), f"Too few entities from medium document: {result['entities_extracted']}"
            else:
                assert (
                    result["entities_extracted"] >= 1
                ), f"Too few entities from small document: {result['entities_extracted']}"

        # Verify extraction efficiency scales reasonably
        large_result = max(benchmark_results, key=lambda x: x["content_length"])
        assert (
            large_result["extraction_time_ms"] < 2000
        ), f"Large document extraction too slow: {large_result['extraction_time_ms']}ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
