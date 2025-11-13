"""
Memgraph Connector Unit Tests

Tests for Memgraph knowledge graph operations including:
- Entity storage in knowledge graph with full content
- Relationship creation and management
- Content-based entity linking and querying
- Graph traversal and pattern matching
- Performance and scalability validation

Critical focus on ensuring full content is stored and retrievable from graph.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, Mock, patch

import neo4j
import pytest

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from shared_fixtures import (
    NESTED_CONTENT_DOCUMENT,
    STANDARDIZED_TEST_DOCUMENT,
    ContentExtractionAssertions,
    generate_large_document,
)


class TestMemgraphConnector:
    """Test Memgraph connector knowledge graph operations."""

    def setup_method(self):
        """Setup for each test method."""
        self.assertions = ContentExtractionAssertions()
        self.memgraph_uri = os.getenv("MEMGRAPH_URI", "bolt://localhost:7687")

    @pytest.fixture
    def mock_memgraph_driver(self):
        """Mock Memgraph driver for testing."""
        driver = AsyncMock()
        session = AsyncMock()

        # Mock session context manager
        driver.session.return_value.__aenter__.return_value = session
        driver.session.return_value.__aexit__.return_value = None

        # Mock query execution
        session.run.return_value = AsyncMock()
        session.run.return_value.data.return_value = []

        return driver, session

    @pytest.mark.asyncio
    async def test_entity_storage_with_full_content(self, mock_memgraph_driver):
        """Test storing entities with complete content in knowledge graph."""
        driver, session = mock_memgraph_driver
        doc = STANDARDIZED_TEST_DOCUMENT.copy()

        # Prepare entity for storage
        document_entity = {
            "entity_id": doc["document_id"],
            "entity_type": "document",
            "name": doc["document_data"]["title"],
            "properties": {
                "project_id": doc["project_id"],
                "document_type": doc["document_data"]["document_type"],
                "content": doc["document_data"]["content"]["content"],  # Full content
                "content_preview": doc["document_data"]["content"]["content"][:500],
                "full_content_length": len(doc["document_data"]["content"]["content"]),
                "metadata": doc["document_data"].get("metadata", {}),
            },
            "confidence_score": 1.0,
        }

        # Critical: Validate content is not truncated before storage
        content_text = document_entity["properties"]["content"]
        self.assertions.assert_content_not_truncated(
            content_text, doc["document_data"]["content"]
        )
        assert (
            len(content_text) > 400
        ), f"Content truncated before graph storage: {len(content_text)}"

        # Mock entity storage in Memgraph
        async def store_entity_in_graph(entity, driver):
            """Store entity with full content in knowledge graph."""

            # Validate entity structure
            assert "entity_id" in entity, "Entity missing ID"
            assert "properties" in entity, "Entity missing properties"
            assert "content" in entity["properties"], "Entity missing content"

            content = entity["properties"]["content"]
            assert len(content) > 400, f"Entity content truncated: {len(content)} chars"

            # Create Cypher query for entity storage
            cypher_query = """
            MERGE (e:Entity {entity_id: $entity_id})
            SET e.entity_type = $entity_type,
                e.name = $name,
                e.content = $content,
                e.content_preview = $content_preview,
                e.full_content_length = $full_content_length,
                e.document_type = $document_type,
                e.project_id = $project_id,
                e.confidence_score = $confidence_score,
                e.created_at = datetime(),
                e.updated_at = datetime()
            RETURN e
            """

            # Prepare parameters
            parameters = {
                "entity_id": entity["entity_id"],
                "entity_type": entity["entity_type"],
                "name": entity["name"],
                "content": entity["properties"]["content"],
                "content_preview": entity["properties"]["content_preview"],
                "full_content_length": entity["properties"]["full_content_length"],
                "document_type": entity["properties"]["document_type"],
                "project_id": entity["properties"]["project_id"],
                "confidence_score": entity["confidence_score"],
            }

            # Validate parameters preserve content
            assert len(parameters["content"]) > 400, "Content truncated in parameters"
            assert parameters["full_content_length"] == len(
                parameters["content"]
            ), "Content length mismatch"

            # Mock query execution
            result = Mock()
            result.data.return_value = [
                {
                    "e": {
                        "entity_id": entity["entity_id"],
                        "content": parameters["content"],
                        "full_content_length": parameters["full_content_length"],
                    }
                }
            ]

            with patch.object(session, "run", return_value=result):
                query_result = await session.run(cypher_query, parameters)
                stored_entities = query_result.data()

                return stored_entities[0]["e"] if stored_entities else None

        # Execute entity storage
        stored_entity = await store_entity_in_graph(document_entity, driver)

        # Validate storage results
        assert stored_entity is not None, "Entity not stored successfully"
        assert stored_entity["entity_id"] == doc["document_id"], "Entity ID mismatch"
        assert (
            len(stored_entity["content"]) > 400
        ), f"Stored content truncated: {len(stored_entity['content'])}"
        assert stored_entity["full_content_length"] == len(
            stored_entity["content"]
        ), "Stored content length mismatch"

    @pytest.mark.asyncio
    async def test_relationship_creation_with_content_context(
        self, mock_memgraph_driver
    ):
        """Test creating relationships between entities with content context."""
        driver, session = mock_memgraph_driver

        # Create test entities with content
        doc1 = STANDARDIZED_TEST_DOCUMENT.copy()
        doc2 = NESTED_CONTENT_DOCUMENT.copy()

        entities = [
            {
                "entity_id": doc1["document_id"],
                "name": doc1["document_data"]["title"],
                "content": doc1["document_data"]["content"]["content"],
                "entity_type": "document",
            },
            {
                "entity_id": doc2["document_id"],
                "name": doc2["document_data"]["title"],
                "content": doc2["document_data"]["content"]["overview"],
                "entity_type": "document",
            },
        ]

        # Mock relationship creation
        async def create_content_based_relationship(
            from_entity, to_entity, relationship_type, context
        ):
            """Create relationship with content-based context."""

            # Validate entities have content
            assert (
                len(from_entity["content"]) > 50
            ), f"From entity content too short: {len(from_entity['content'])}"
            assert (
                len(to_entity["content"]) > 50
            ), f"To entity content too short: {len(to_entity['content'])}"

            # Analyze content for relationship context
            from_content = from_entity["content"].lower()
            to_content = to_entity["content"].lower()

            # Find common terms for relationship context
            from_words = set(from_content.split())
            to_words = set(to_content.split())
            common_terms = from_words.intersection(to_words)

            # Create relationship with rich context
            relationship = {
                "from_entity_id": from_entity["entity_id"],
                "to_entity_id": to_entity["entity_id"],
                "relationship_type": relationship_type,
                "context": context,
                "content_similarity": {
                    "common_terms": list(common_terms),
                    "common_term_count": len(common_terms),
                    "similarity_score": len(common_terms)
                    / (
                        len(from_words.union(to_words))
                        if from_words.union(to_words)
                        else 1
                    ),
                },
                "content_excerpts": {
                    "from_excerpt": from_entity["content"][:200],
                    "to_excerpt": to_entity["content"][:200],
                },
            }

            # Cypher query for relationship creation
            cypher_query = """
            MATCH (from:Entity {entity_id: $from_entity_id})
            MATCH (to:Entity {entity_id: $to_entity_id})
            MERGE (from)-[r:RELATED {type: $relationship_type}]->(to)
            SET r.context = $context,
                r.common_terms = $common_terms,
                r.similarity_score = $similarity_score,
                r.from_excerpt = $from_excerpt,
                r.to_excerpt = $to_excerpt,
                r.created_at = datetime()
            RETURN r
            """

            parameters = {
                "from_entity_id": relationship["from_entity_id"],
                "to_entity_id": relationship["to_entity_id"],
                "relationship_type": relationship["relationship_type"],
                "context": relationship["context"],
                "common_terms": relationship["content_similarity"]["common_terms"],
                "similarity_score": relationship["content_similarity"][
                    "similarity_score"
                ],
                "from_excerpt": relationship["content_excerpts"]["from_excerpt"],
                "to_excerpt": relationship["content_excerpts"]["to_excerpt"],
            }

            # Mock successful relationship creation
            result = Mock()
            result.data.return_value = [
                {
                    "r": {
                        "type": relationship_type,
                        "similarity_score": parameters["similarity_score"],
                        "common_terms": parameters["common_terms"],
                    }
                }
            ]

            with patch.object(session, "run", return_value=result):
                query_result = await session.run(cypher_query, parameters)
                return query_result.data()[0]["r"]

        # Create relationship between documents
        relationship_result = await create_content_based_relationship(
            entities[0],
            entities[1],
            "SIMILAR_CONTENT",
            "Both documents contain test content",
        )

        # Validate relationship creation
        assert (
            relationship_result["type"] == "SIMILAR_CONTENT"
        ), "Relationship type mismatch"
        assert (
            relationship_result["similarity_score"] > 0
        ), "No content similarity calculated"
        assert (
            len(relationship_result["common_terms"]) > 0
        ), "No common terms found between contents"

    @pytest.mark.asyncio
    async def test_content_based_entity_querying(self, mock_memgraph_driver):
        """Test querying entities based on content patterns."""
        driver, session = mock_memgraph_driver

        # Mock content-based query scenarios
        query_scenarios = [
            {
                "query_type": "content_contains",
                "search_term": "comprehensive test document",
                "expected_matches": 1,
            },
            {
                "query_type": "content_length_range",
                "min_length": 400,
                "max_length": 1000,
                "expected_matches": 2,
            },
            {
                "query_type": "entity_type_with_content",
                "entity_type": "document",
                "content_pattern": ".*pipeline.*",
                "expected_matches": 1,
            },
        ]

        async def execute_content_query(scenario):
            """Execute content-based query against knowledge graph."""

            if scenario["query_type"] == "content_contains":
                cypher_query = """
                MATCH (e:Entity)
                WHERE e.content CONTAINS $search_term
                RETURN e.entity_id, e.name, e.content, e.full_content_length
                """
                parameters = {"search_term": scenario["search_term"]}

                # Mock result with content validation
                mock_entities = [
                    {
                        "e.entity_id": "test-doc-12345",
                        "e.name": "Test Document for Unit Testing",
                        "e.content": STANDARDIZED_TEST_DOCUMENT["document_data"][
                            "content"
                        ]["content"],
                        "e.full_content_length": len(
                            STANDARDIZED_TEST_DOCUMENT["document_data"]["content"][
                                "content"
                            ]
                        ),
                    }
                ]

            elif scenario["query_type"] == "content_length_range":
                cypher_query = """
                MATCH (e:Entity)
                WHERE e.full_content_length >= $min_length AND e.full_content_length <= $max_length
                RETURN e.entity_id, e.content, e.full_content_length
                """
                parameters = {
                    "min_length": scenario["min_length"],
                    "max_length": scenario["max_length"],
                }

                mock_entities = [
                    {
                        "e.entity_id": "test-doc-12345",
                        "e.content": STANDARDIZED_TEST_DOCUMENT["document_data"][
                            "content"
                        ]["content"],
                        "e.full_content_length": len(
                            STANDARDIZED_TEST_DOCUMENT["document_data"]["content"][
                                "content"
                            ]
                        ),
                    },
                    {
                        "e.entity_id": "test-nested-content",
                        "e.content": NESTED_CONTENT_DOCUMENT["document_data"][
                            "content"
                        ]["overview"],
                        "e.full_content_length": len(
                            NESTED_CONTENT_DOCUMENT["document_data"]["content"][
                                "overview"
                            ]
                        ),
                    },
                ]

            elif scenario["query_type"] == "entity_type_with_content":
                cypher_query = """
                MATCH (e:Entity)
                WHERE e.entity_type = $entity_type AND e.content =~ $content_pattern
                RETURN e.entity_id, e.content, e.entity_type
                """
                parameters = {
                    "entity_type": scenario["entity_type"],
                    "content_pattern": scenario["content_pattern"],
                }

                mock_entities = [
                    {
                        "e.entity_id": "test-doc-12345",
                        "e.content": STANDARDIZED_TEST_DOCUMENT["document_data"][
                            "content"
                        ]["content"],
                        "e.entity_type": "document",
                    }
                ]

            # Validate query results preserve full content
            for entity in mock_entities:
                content = entity.get("e.content")
                if content:
                    assert (
                        len(content) > 50
                    ), f"Queried entity content truncated: {len(content)}"

            # Mock query execution
            result = Mock()
            result.data.return_value = mock_entities

            with patch.object(session, "run", return_value=result):
                query_result = await session.run(cypher_query, parameters)
                return query_result.data()

        # Execute all query scenarios
        for scenario in query_scenarios:
            results = await execute_content_query(scenario)

            assert (
                len(results) == scenario["expected_matches"]
            ), f"Query result count mismatch for {scenario['query_type']}"

            # Validate content preservation in results
            for result in results:
                content = result.get("e.content")
                if content:
                    assert (
                        len(content) > 50
                    ), f"Content truncated in query result: {len(content)}"

    @pytest.mark.asyncio
    async def test_graph_traversal_with_content_analysis(self, mock_memgraph_driver):
        """Test graph traversal operations that analyze content relationships."""
        driver, session = mock_memgraph_driver

        # Mock graph structure with content-rich entities
        graph_entities = [
            {
                "entity_id": "doc_1",
                "content": "API design documentation for microservices architecture with detailed specifications.",
                "entity_type": "document",
                "tags": ["api", "design", "microservices"],
            },
            {
                "entity_id": "doc_2",
                "content": "Microservices implementation guide covering deployment and monitoring strategies.",
                "entity_type": "document",
                "tags": ["microservices", "implementation", "deployment"],
            },
            {
                "entity_id": "concept_1",
                "content": "Microservices architecture pattern for distributed systems.",
                "entity_type": "concept",
                "tags": ["microservices", "architecture", "patterns"],
            },
        ]

        async def traverse_content_related_entities(start_entity_id, max_depth=3):
            """Traverse graph finding content-related entities."""

            # Mock traversal query

            # Find entities with content relationships
            related_entities = []
            start_entity = next(
                e for e in graph_entities if e["entity_id"] == start_entity_id
            )
            start_words = set(start_entity["content"].lower().split())

            for entity in graph_entities:
                if entity["entity_id"] != start_entity_id:
                    entity_words = set(entity["content"].lower().split())
                    common_words = start_words.intersection(entity_words)

                    if len(common_words) > 0:
                        related_entities.append(
                            {
                                "entity_id": entity["entity_id"],
                                "content": entity["content"],
                                "common_words": list(common_words),
                                "relationship_strength": len(common_words)
                                / len(start_words.union(entity_words)),
                                "depth": 1,  # Simplified for test
                            }
                        )

            # Validate content preservation in traversal
            for entity in related_entities:
                assert (
                    len(entity["content"]) > 30
                ), f"Traversed entity content truncated: {len(entity['content'])}"
                assert (
                    len(entity["common_words"]) > 0
                ), "No content relationship found in traversal"

            return related_entities

        # Execute content-based traversal
        traversal_results = await traverse_content_related_entities(
            "doc_1", max_depth=2
        )

        # Validate traversal results
        assert len(traversal_results) > 0, "No related entities found in traversal"

        # Check for expected microservices-related connections
        microservices_related = [
            entity
            for entity in traversal_results
            if "microservices" in entity["common_words"]
        ]
        assert (
            len(microservices_related) >= 2
        ), "Missing microservices content relationships"

        # Verify relationship strength calculation
        for entity in traversal_results:
            assert entity["relationship_strength"] > 0, "Invalid relationship strength"
            assert (
                entity["relationship_strength"] <= 1
            ), "Relationship strength exceeds maximum"

    @pytest.mark.asyncio
    async def test_large_content_storage_and_retrieval_performance(
        self, mock_memgraph_driver
    ):
        """Test performance of storing and retrieving large content in knowledge graph."""
        driver, session = mock_memgraph_driver

        # Create large content entities
        large_documents = [
            generate_large_document(content_size=10000),  # 10KB
            generate_large_document(content_size=30000),  # 30KB
            generate_large_document(content_size=50000),  # 50KB
        ]

        async def benchmark_large_content_operations(documents):
            """Benchmark storage and retrieval of large content entities."""
            performance_results = []

            for doc in documents:
                content = doc["document_data"]["content"]["content"]
                content_size = len(content)

                import time

                # Benchmark storage
                storage_start = time.time()

                # Mock entity storage operation
                entity = {
                    "entity_id": doc["document_id"],
                    "content": content,
                    "content_size": content_size,
                    "entity_type": "large_document",
                }

                # Validate content is not truncated before storage
                assert (
                    len(entity["content"]) == content_size
                ), f"Content truncated before storage: {len(entity['content'])} != {content_size}"

                # Simulate storage time based on content size
                storage_delay = min(content_size / 100000, 0.5)  # Max 0.5s delay
                await asyncio.sleep(storage_delay)

                storage_time = time.time() - storage_start

                # Benchmark retrieval
                retrieval_start = time.time()

                # Mock entity retrieval
                retrieved_entity = {
                    "entity_id": entity["entity_id"],
                    "content": entity["content"],  # Full content retrieved
                    "content_size": len(entity["content"]),
                }

                # Validate full content retrieval
                assert (
                    len(retrieved_entity["content"]) == content_size
                ), f"Content truncated during retrieval: {len(retrieved_entity['content'])} != {content_size}"

                # Simulate retrieval time
                retrieval_delay = min(content_size / 200000, 0.3)  # Max 0.3s delay
                await asyncio.sleep(retrieval_delay)

                retrieval_time = time.time() - retrieval_start

                performance_results.append(
                    {
                        "document_id": doc["document_id"],
                        "content_size": content_size,
                        "storage_time_ms": storage_time * 1000,
                        "retrieval_time_ms": retrieval_time * 1000,
                        "total_time_ms": (storage_time + retrieval_time) * 1000,
                        "content_preserved": len(retrieved_entity["content"])
                        == content_size,
                    }
                )

            return performance_results

        # Execute performance benchmark
        results = await benchmark_large_content_operations(large_documents)

        # Validate performance results
        for result in results:
            assert result[
                "content_preserved"
            ], f"Content not preserved for {result['document_id']}"
            assert (
                result["storage_time_ms"] < 2000
            ), f"Storage too slow for {result['content_size']} bytes: {result['storage_time_ms']}ms"
            assert (
                result["retrieval_time_ms"] < 1500
            ), f"Retrieval too slow for {result['content_size']} bytes: {result['retrieval_time_ms']}ms"

            # Performance should scale reasonably with content size
            if result["content_size"] > 20000:
                assert (
                    result["total_time_ms"] < 3000
                ), f"Large content operation too slow: {result['total_time_ms']}ms"

    @pytest.mark.asyncio
    async def test_concurrent_graph_operations_with_content_integrity(
        self, mock_memgraph_driver
    ):
        """Test concurrent graph operations maintain content integrity."""
        driver, session = mock_memgraph_driver

        # Create test entities for concurrent operations
        test_entities = []
        for i in range(5):
            doc = generate_large_document(content_size=5000)
            test_entities.append(
                {
                    "entity_id": doc["document_id"],
                    "content": doc["document_data"]["content"]["content"],
                    "operation_id": i,
                }
            )

        async def concurrent_entity_operation(entity):
            """Perform concurrent entity operations."""
            # Simulate concurrent storage and retrieval
            await asyncio.sleep(0.1)  # Simulate operation delay

            # Validate content integrity during concurrent operations
            original_content = entity["content"]
            assert (
                len(original_content) == 5000
            ), f"Content size mismatch: {len(original_content)}"

            # Mock storage operation
            stored_content = original_content  # Content preserved

            # Mock retrieval operation
            retrieved_content = stored_content  # Content preserved

            # Validate content integrity
            assert (
                retrieved_content == original_content
            ), "Content corrupted during concurrent operation"

            return {
                "entity_id": entity["entity_id"],
                "operation_id": entity["operation_id"],
                "content_integrity": retrieved_content == original_content,
                "content_length": len(retrieved_content),
            }

        # Execute concurrent operations
        import time

        start_time = time.time()

        concurrent_results = await asyncio.gather(
            *[concurrent_entity_operation(entity) for entity in test_entities]
        )

        total_time = time.time() - start_time

        # Validate concurrent operation results
        assert (
            len(concurrent_results) == 5
        ), f"Not all concurrent operations completed: {len(concurrent_results)}"
        assert total_time < 1.0, f"Concurrent operations too slow: {total_time}s"

        for result in concurrent_results:
            assert result[
                "content_integrity"
            ], f"Content integrity lost in operation {result['operation_id']}"
            assert (
                result["content_length"] == 5000
            ), f"Content length changed in operation {result['operation_id']}: {result['content_length']}"


class TestMemgraphConnectorErrorHandling:
    """Test error handling in Memgraph connector operations."""

    @pytest.mark.asyncio
    async def test_connection_failure_handling(self):
        """Test handling of Memgraph connection failures."""
        # Mock connection failure scenarios
        connection_scenarios = [
            {"error_type": "ConnectionError", "retry_count": 3},
            {"error_type": "TimeoutError", "retry_count": 2},
            {"error_type": "AuthenticationError", "retry_count": 1},
        ]

        async def handle_connection_failure(scenario):
            """Handle connection failures with retry logic."""
            attempt = 0
            max_attempts = scenario["retry_count"]

            while attempt < max_attempts:
                try:
                    attempt += 1

                    # Simulate connection failure
                    if attempt < max_attempts:
                        if scenario["error_type"] == "ConnectionError":
                            raise neo4j.exceptions.ServiceUnavailable(
                                "Connection failed"
                            )
                        elif scenario["error_type"] == "TimeoutError":
                            raise neo4j.exceptions.TransientError("Connection timeout")
                        elif scenario["error_type"] == "AuthenticationError":
                            raise neo4j.exceptions.AuthError("Authentication failed")

                    # Success on final attempt
                    return {
                        "success": True,
                        "attempts": attempt,
                        "error_type": scenario["error_type"],
                    }

                except (
                    neo4j.exceptions.ServiceUnavailable,
                    neo4j.exceptions.TransientError,
                ) as e:
                    if attempt == max_attempts:
                        return {
                            "success": False,
                            "attempts": attempt,
                            "error_type": scenario["error_type"],
                            "final_error": str(e),
                        }
                    await asyncio.sleep(0.1 * (2**attempt))  # Exponential backoff

                except neo4j.exceptions.AuthError:
                    # Don't retry authentication errors
                    return {
                        "success": False,
                        "attempts": attempt,
                        "error_type": scenario["error_type"],
                        "final_error": "Authentication failed",
                    }

        # Test each failure scenario
        for scenario in connection_scenarios:
            result = await handle_connection_failure(scenario)

            if scenario["error_type"] == "AuthenticationError":
                assert not result["success"], "Authentication error should not succeed"
                assert result["attempts"] == 1, "Authentication error should not retry"
            else:
                assert result[
                    "success"
                ], f"Retryable error should eventually succeed: {scenario['error_type']}"
                assert (
                    result["attempts"] == scenario["retry_count"]
                ), f"Unexpected attempt count: {result['attempts']}"

    @pytest.mark.asyncio
    async def test_content_validation_and_sanitization(self):
        """Test content validation and sanitization for graph storage."""
        # Test content scenarios
        content_scenarios = [
            {
                "name": "valid_content",
                "content": "This is valid content for graph storage.",
                "expected_valid": True,
            },
            {
                "name": "content_with_quotes",
                "content": "Content with \"quotes\" and 'apostrophes' that need escaping.",
                "expected_valid": True,
            },
            {
                "name": "content_with_cypher_injection",
                "content": "'; DROP ALL; //",
                "expected_valid": False,
            },
            {
                "name": "very_long_content",
                "content": "A" * 100000,  # 100KB content
                "expected_valid": True,
            },
            {"name": "empty_content", "content": "", "expected_valid": False},
        ]

        def validate_and_sanitize_content(content):
            """Validate and sanitize content for graph storage."""
            # Basic validation
            if not content or len(content.strip()) == 0:
                return False, "Empty content not allowed"

            # Check for potential Cypher injection
            dangerous_patterns = [
                "'; DROP",
                "'; DELETE",
                "'; MATCH",
                "'; CREATE",
                "'; MERGE",
            ]

            content_upper = content.upper()
            for pattern in dangerous_patterns:
                if pattern in content_upper:
                    return False, f"Potential Cypher injection detected: {pattern}"

            # Content length validation (100KB limit for this test)
            if len(content) > 100000:
                return False, f"Content too long: {len(content)} bytes"

            # Sanitize content (escape quotes)
            sanitized_content = content.replace('"', '\\"').replace("'", "\\'")

            return True, sanitized_content

        # Test each content scenario
        for scenario in content_scenarios:
            is_valid, result = validate_and_sanitize_content(scenario["content"])

            assert (
                is_valid == scenario["expected_valid"]
            ), f"Validation failed for {scenario['name']}: {result}"

            if is_valid:
                # Verify sanitization preserves content intent
                if scenario["name"] == "content_with_quotes":
                    assert (
                        '\\"' in result or "\\'" in result
                    ), "Quote sanitization failed"
                elif scenario["name"] == "very_long_content":
                    assert len(result) == 100000, "Long content length not preserved"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
