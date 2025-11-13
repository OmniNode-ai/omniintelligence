"""
ONEX Qdrant Example Usage

Demonstrates all 4 effect nodes with realistic patterns from Archon intelligence.
"""

import asyncio
import os

from services.intelligence.onex import ONEXQdrantService


async def main():
    """Run example demonstrating all ONEX Qdrant operations."""

    # Ensure environment variables are set
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        return

    print("=" * 60)
    print("ONEX Qdrant Vector Indexing - Example Usage")
    print("=" * 60)

    # Initialize service
    async with ONEXQdrantService() as service:

        # =================================================================
        # Example 1: Index Intelligence Patterns
        # =================================================================
        print("\n1. INDEXING INTELLIGENCE PATTERNS")
        print("-" * 60)

        patterns = [
            {
                "text": "User authentication with JWT tokens and refresh tokens for secure session management",
                "type": "security",
                "category": "authentication",
                "complexity": "medium",
                "source": "archon_intelligence",
            },
            {
                "text": "Database connection pooling with automatic retry logic and health checks",
                "type": "performance",
                "category": "database",
                "complexity": "low",
                "source": "archon_intelligence",
            },
            {
                "text": "Rate limiting middleware with token bucket algorithm for API protection",
                "type": "security",
                "category": "api",
                "complexity": "medium",
                "source": "archon_intelligence",
            },
            {
                "text": "Caching strategy with Redis for frequently accessed data and cache invalidation",
                "type": "performance",
                "category": "caching",
                "complexity": "medium",
                "source": "archon_intelligence",
            },
            {
                "text": "Error handling pattern with exponential backoff and circuit breaker",
                "type": "resilience",
                "category": "error_handling",
                "complexity": "high",
                "source": "archon_intelligence",
            },
        ]

        index_result = await service.index_patterns(patterns)

        print(f"✓ Indexed {index_result.indexed_count} patterns")
        print(f"  Duration: {index_result.duration_ms:.2f}ms")
        print(f"  Collection: {index_result.collection_name}")
        print(f"  Point IDs: {[str(pid)[:8] for pid in index_result.point_ids[:3]]}...")

        # Save first point ID for update example
        first_point_id = str(index_result.point_ids[0])

        # =================================================================
        # Example 2: Semantic Search
        # =================================================================
        print("\n2. SEMANTIC SIMILARITY SEARCH")
        print("-" * 60)

        queries = [
            ("security authentication", 3),
            ("performance optimization", 3),
            ("error handling resilience", 2),
        ]

        for query_text, limit in queries:
            print(f"\nQuery: '{query_text}' (limit={limit})")

            search_result = await service.search_patterns(
                query_text=query_text,
                limit=limit,
                score_threshold=0.5,
            )

            print(
                f"  Found {len(search_result.hits)} results in {search_result.search_time_ms:.2f}ms"
            )

            for i, hit in enumerate(search_result.hits, 1):
                print(f"  {i}. Score: {hit.score:.3f}")
                print(f"     Text: {hit.payload['text'][:60]}...")
                print(
                    f"     Type: {hit.payload['type']} | Category: {hit.payload['category']}"
                )

        # =================================================================
        # Example 3: Advanced Search with Filters
        # =================================================================
        print("\n3. FILTERED SEARCH")
        print("-" * 60)

        print("\nSearching for 'optimization' in 'performance' category only:")

        filtered_result = await service.search_patterns(
            query_text="optimization patterns",
            limit=5,
            score_threshold=0.5,
            filters={"must": [{"key": "type", "match": {"value": "performance"}}]},
        )

        print(
            f"  Found {len(filtered_result.hits)} results in {filtered_result.search_time_ms:.2f}ms"
        )
        for i, hit in enumerate(filtered_result.hits, 1):
            print(f"  {i}. {hit.payload['text'][:60]}... (score: {hit.score:.3f})")

        # =================================================================
        # Example 4: Update Pattern Metadata
        # =================================================================
        print("\n4. UPDATE PATTERN METADATA")
        print("-" * 60)

        print(f"Updating pattern {first_point_id[:8]}... with review metadata:")

        update_result = await service.update_pattern(
            point_id=first_point_id,
            payload={
                "text": patterns[0]["text"],  # Keep original text
                "type": patterns[0]["type"],
                "category": patterns[0]["category"],
                "complexity": patterns[0]["complexity"],
                "source": patterns[0]["source"],
                "reviewed": True,
                "review_score": 0.92,
                "reviewer": "archon_intelligence_system",
            },
        )

        print(f"✓ Update completed in {update_result.operation_time_ms:.2f}ms")
        print(f"  Status: {update_result.status}")

        # =================================================================
        # Example 5: Update with Re-embedding
        # =================================================================
        print("\n5. UPDATE WITH RE-EMBEDDING")
        print("-" * 60)

        print("Updating pattern text and regenerating embedding:")

        reembedding_result = await service.update_pattern(
            point_id=first_point_id,
            text_for_embedding="Enhanced JWT authentication with OAuth2 integration and multi-factor authentication support",
            payload={
                "type": "security",
                "category": "authentication",
                "complexity": "high",  # Complexity increased
                "source": "archon_intelligence",
                "reviewed": True,
                "review_score": 0.95,
                "last_updated": "2025-10-02",
            },
        )

        print(
            f"✓ Re-embedding completed in {reembedding_result.operation_time_ms:.2f}ms"
        )

        # =================================================================
        # Example 6: Health Check
        # =================================================================
        print("\n6. COLLECTION HEALTH CHECK")
        print("-" * 60)

        health_result = await service.health_check()

        print(f"✓ Service Status: {'OK' if health_result.service_ok else 'FAILED'}")
        print(f"  Response Time: {health_result.response_time_ms:.2f}ms")
        print(f"  Collections: {len(health_result.collections)}")

        for collection in health_result.collections:
            print(f"\n  Collection: {collection.name}")
            print(f"    Points: {collection.points_count}")
            print(f"    Vectors: {collection.vectors_count}")
            print(f"    Indexed: {collection.indexed_vectors_count}")

        # =================================================================
        # Example 7: Batch Indexing Performance
        # =================================================================
        print("\n7. BATCH INDEXING PERFORMANCE")
        print("-" * 60)

        # Generate 50 test patterns
        batch_patterns = [
            {
                "text": f"Intelligence pattern {i}: Implementing distributed tracing and monitoring for microservices architecture",
                "type": "observability",
                "category": "monitoring",
                "batch_id": i,
            }
            for i in range(50)
        ]

        batch_result = await service.index_patterns(batch_patterns)

        print(f"✓ Indexed {batch_result.indexed_count} patterns")
        print(f"  Total Duration: {batch_result.duration_ms:.2f}ms")
        print(
            f"  Per Pattern: {batch_result.duration_ms / batch_result.indexed_count:.2f}ms"
        )
        print(
            f"  Throughput: {batch_result.indexed_count / (batch_result.duration_ms / 1000):.2f} patterns/sec"
        )

        # =================================================================
        # Example 8: Search Performance with Different Parameters
        # =================================================================
        print("\n8. SEARCH PERFORMANCE TUNING")
        print("-" * 60)

        print("\nComparing different HNSW search parameters:")

        hnsw_ef_values = [64, 128, 256]
        for hnsw_ef in hnsw_ef_values:
            result = await service.search_patterns(
                query_text="distributed system patterns", limit=10, hnsw_ef=hnsw_ef
            )
            print(
                f"  hnsw_ef={hnsw_ef:3d}: {result.search_time_ms:6.2f}ms ({len(result.hits)} results)"
            )

        # =================================================================
        # Summary
        # =================================================================
        print("\n" + "=" * 60)
        print("EXAMPLE COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print("\nAll ONEX Qdrant operations demonstrated:")
        print("  ✓ Vector indexing with batch processing")
        print("  ✓ Semantic similarity search with filters")
        print("  ✓ Metadata updates without re-embedding")
        print("  ✓ Full updates with embedding regeneration")
        print("  ✓ Health monitoring and statistics")
        print("  ✓ Performance tuning with HNSW parameters")
        print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
