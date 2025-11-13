#!/usr/bin/env python3
"""
Demo: Orchestrated Multi-Source Intelligence Query

Demonstrates querying multiple intelligence sources (RAG, Qdrant, Memgraph)
for comprehensive information about ONEX node development.

Configuration:
    Uses centralized config from config/settings.py
    Override with environment variables (INTELLIGENCE_SERVICE_PORT, etc.)

Example Query: "How to build an omni orchestrator node"

Usage:
    python3 scripts/demo_orchestrated_search.py
    python3 scripts/demo_orchestrated_search.py --query "how to build orchestrator node"
    python3 scripts/demo_orchestrated_search.py --json  # Output as JSON
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from neo4j import GraphDatabase

# Add parent directory to path for config imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import centralized configuration
from config import settings

# Service endpoints (from centralized config)
SEARCH_SERVICE_URL = f"http://localhost:{settings.search_service_port}"
INTELLIGENCE_SERVICE_URL = f"http://localhost:{settings.intelligence_service_port}"

# Load configuration from centralized settings
EMBEDDING_MODEL = settings.embedding_model
EMBEDDING_DIMENSIONS = settings.embedding_dimensions
EMBEDDING_MODEL_URL = os.getenv("EMBEDDING_MODEL_URL", "http://192.168.86.201:8002")


class OrchestratedSearchDemo:
    """Demo orchestrated multi-source intelligence queries"""

    def __init__(self, search_url: str, intelligence_url: str):
        self.search_url = search_url
        self.intelligence_url = intelligence_url

    async def query_all_sources(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """
        Query all intelligence sources in parallel.

        Sources:
            - RAG Search Service (hybrid search with reranking)
            - Qdrant Vector Database (semantic similarity)
            - Memgraph Knowledge Graph (relationship queries)

        Args:
            query: Natural language query
            limit: Maximum results per source

        Returns:
            Dictionary with results from all sources + metadata
        """
        start_time = time.time()

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Launch parallel queries to all sources
            tasks = [
                self._query_rag_search(client, query, limit),
                self._query_vector_search(client, query, limit),
                self._query_knowledge_graph(client, query, limit),
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

        total_time = time.time() - start_time

        # Aggregate results
        return {
            "query": query,
            "sources": {
                "rag_search": (
                    results[0]
                    if not isinstance(results[0], Exception)
                    else {"error": str(results[0])}
                ),
                "vector_search": (
                    results[1]
                    if not isinstance(results[1], Exception)
                    else {"error": str(results[1])}
                ),
                "knowledge_graph": (
                    results[2]
                    if not isinstance(results[2], Exception)
                    else {"error": str(results[2])}
                ),
            },
            "metadata": {
                "total_time_ms": round(total_time * 1000, 2),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "parallel_execution": True,
            },
        }

    async def _query_rag_search(
        self, client: httpx.AsyncClient, query: str, limit: int
    ) -> Dict[str, Any]:
        """Query RAG Search Service (hybrid search + reranking)"""
        start_time = time.time()

        try:
            response = await client.post(
                f"{self.search_url}/search",
                json={
                    "query": query,
                    "limit": limit,
                    "project_name": "omniarchon",  # Optional filter
                },
            )
            response.raise_for_status()
            data = response.json()

            elapsed = time.time() - start_time

            return {
                "status": "success",
                "results_count": data.get("total_results", 0),
                "results": data.get("results", []),
                "response_time_ms": round(elapsed * 1000, 2),
                "source": "RAG Search Service (Hybrid + Reranking)",
            }

        except Exception as e:
            elapsed = time.time() - start_time
            return {
                "status": "error",
                "error": str(e),
                "response_time_ms": round(elapsed * 1000, 2),
                "source": "RAG Search Service",
            }

    async def _query_vector_search(
        self, client: httpx.AsyncClient, query: str, limit: int
    ) -> Dict[str, Any]:
        """Query Qdrant Vector Database (direct semantic similarity)"""
        start_time = time.time()

        try:
            # Step 1: Generate embedding for query using embedding service
            # CRITICAL: Use embedding model and dimensions from environment
            embed_response = await client.post(
                f"{EMBEDDING_MODEL_URL}/api/embeddings",
                json={
                    "model": EMBEDDING_MODEL,
                    "prompt": query,
                },
                timeout=10.0,
            )
            embed_response.raise_for_status()
            embedding = embed_response.json()["embedding"]

            # Verify embedding dimensions match expected configuration
            if len(embedding) != EMBEDDING_DIMENSIONS:
                raise ValueError(
                    f"Embedding dimension mismatch: got {len(embedding)}, "
                    f"expected {EMBEDDING_DIMENSIONS}. "
                    f"Check EMBEDDING_MODEL and EMBEDDING_DIMENSIONS in .env"
                )

            # Step 2: Query Qdrant with the embedding
            qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
            search_response = await client.post(
                f"{qdrant_url}/collections/archon_vectors/points/search",
                json={
                    "vector": embedding,
                    "limit": limit,
                    "with_payload": True,
                },
                timeout=10.0,
            )
            search_response.raise_for_status()
            search_data = search_response.json()

            # Format results - FILTER OUT empty payloads (data quality issue)
            results = []
            for hit in search_data.get("result", []):
                payload = hit.get("payload", {})
                # Skip results with empty payloads (no metadata)
                if not payload or not payload.get("file_path"):
                    continue
                results.append(
                    {
                        "file_path": payload.get("file_path", "Unknown"),
                        "content": payload.get("content", ""),
                        "score": hit.get("score", 0),
                        "project": payload.get("project_name", "N/A"),
                    }
                )

            elapsed = time.time() - start_time

            return {
                "status": "success",
                "results_count": len(results),
                "results": results,
                "response_time_ms": round(elapsed * 1000, 2),
                "source": "Qdrant Vector Database",
                "embedding_model": EMBEDDING_MODEL,
                "embedding_dims": len(embedding),
                "dimension_verification": (
                    "✅ PASS" if len(embedding) == EMBEDDING_DIMENSIONS else "❌ FAIL"
                ),
            }

        except Exception as e:
            elapsed = time.time() - start_time
            return {
                "status": "error",
                "error": str(e),
                "response_time_ms": round(elapsed * 1000, 2),
                "source": "Qdrant Vector Database",
            }

    async def _query_knowledge_graph(
        self, client: httpx.AsyncClient, query: str, limit: int
    ) -> Dict[str, Any]:
        """Query Memgraph Knowledge Graph (relationship queries) via Bolt protocol"""
        start_time = time.time()

        try:
            # Extract key search terms from query
            search_terms = query.lower().split()
            if not search_terms:
                return {
                    "status": "error",
                    "error": "Empty query provided",
                    "response_time_ms": 0,
                    "source": "Memgraph Knowledge Graph",
                }

            # Get Memgraph connection URI from environment
            # Note: Script runs on host, use localhost (not Docker container name)
            memgraph_uri = os.getenv("MEMGRAPH_URI", "bolt://localhost:7687")

            # Build Cypher query to search for documents matching query terms
            # Search in content and return documents with their relationships
            search_term = search_terms[0]  # Use first term for primary search

            cypher_query = """
            MATCH (d:Document)
            WHERE toLower(d.content) CONTAINS $search_term
               OR toLower(d.file_path) CONTAINS $search_term
            OPTIONAL MATCH (d)-[r]-(related)
            WITH d,
                 count(DISTINCT r) as relationship_count,
                 collect(DISTINCT type(r)) as relationship_types,
                 collect(DISTINCT labels(related)) as related_labels
            RETURN d.file_path as file_path,
                   d.content as content,
                   d.project_name as project,
                   relationship_count,
                   relationship_types,
                   related_labels
            ORDER BY relationship_count DESC
            LIMIT $limit
            """

            # Execute query via Bolt protocol (synchronous, run in executor)
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                self._execute_cypher_query,
                memgraph_uri,
                cypher_query,
                {"search_term": search_term, "limit": limit},
            )

            elapsed = time.time() - start_time

            # Format results
            formatted_results = []
            for record in results:
                content = record.get("content", "")
                formatted_results.append(
                    {
                        "file_path": record.get("file_path", "Unknown"),
                        "content_preview": content[:500] if content else "",
                        "full_content_length": len(content) if content else 0,
                        "project": record.get("project", "N/A"),
                        "relationship_count": record.get("relationship_count", 0),
                        "relationship_types": record.get("relationship_types", []),
                        "related_entities": record.get("related_labels", []),
                    }
                )

            return {
                "status": "success",
                "results_count": len(formatted_results),
                "results": formatted_results,
                "response_time_ms": round(elapsed * 1000, 2),
                "source": "Memgraph Knowledge Graph (Bolt Protocol)",
                "connection": memgraph_uri,
                "search_term": search_term,
            }

        except Exception as e:
            elapsed = time.time() - start_time
            return {
                "status": "error",
                "error": str(e),
                "response_time_ms": round(elapsed * 1000, 2),
                "source": "Memgraph Knowledge Graph",
            }

    def _execute_cypher_query(
        self, uri: str, query: str, parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Execute Cypher query synchronously via Bolt protocol.

        This method is called from async context using run_in_executor.
        """
        driver = None
        try:
            driver = GraphDatabase.driver(uri)
            with driver.session() as session:
                result = session.run(query, parameters)
                # Convert records to dictionaries
                records = [dict(record) for record in result]
                return records
        finally:
            if driver:
                driver.close()

    def format_results(
        self, results: Dict[str, Any], format_type: str = "human"
    ) -> str:
        """Format results for display"""
        if format_type == "json":
            return json.dumps(results, indent=2)

        # Human-readable format
        output = []
        output.append("=" * 80)
        output.append(f"🔍 ORCHESTRATED INTELLIGENCE QUERY")
        output.append("=" * 80)
        output.append(f"\nQuery: \"{results['query']}\"")
        output.append(f"Execution Time: {results['metadata']['total_time_ms']}ms")
        output.append(f"Timestamp: {results['metadata']['timestamp']}")
        output.append(
            f"Parallel Execution: {results['metadata']['parallel_execution']}"
        )
        output.append("\n" + "-" * 80)

        # RAG Search Results
        rag = results["sources"]["rag_search"]
        output.append("\n📚 RAG SEARCH SERVICE (Hybrid + Reranking)")
        output.append("-" * 80)
        if rag.get("status") == "success":
            output.append(f"Status: ✅ Success")
            output.append(f"Results: {rag['results_count']} documents")
            output.append(f"Response Time: {rag['response_time_ms']}ms")

            if rag.get("results"):
                output.append("\nTop Results:")
                for i, result in enumerate(rag["results"][:5], 1):
                    file_path = result.get("file_path") or result.get(
                        "entity_id", "Unknown"
                    )
                    title = result.get("title", "Untitled")
                    score = result.get("relevance_score") or result.get(
                        "semantic_score", 0
                    )
                    content = result.get("content") or ""

                    output.append(f"\n  {i}. {title}")
                    output.append(f"     Path: {file_path}")
                    output.append(f"     Score: {score:.4f}")
                    output.append(f"     Preview: {content[:300]}...")
        else:
            output.append(f"Status: ❌ Error - {rag.get('error')}")

        # Vector Search Results
        vector = results["sources"]["vector_search"]
        output.append("\n\n🔢 QDRANT VECTOR DATABASE (Semantic Similarity)")
        output.append("-" * 80)
        if vector.get("status") == "success":
            output.append(f"Status: ✅ Success")
            output.append(f"Results: {vector['results_count']} documents")
            output.append(f"Response Time: {vector['response_time_ms']}ms")
            if vector.get("embedding_model"):
                output.append(f"Embedding Model: {vector['embedding_model']}")
            if vector.get("embedding_dims"):
                output.append(f"Embedding Dimensions: {vector['embedding_dims']}")
            if vector.get("dimension_verification"):
                output.append(f"Dimension Check: {vector['dimension_verification']}")

            if vector.get("results"):
                output.append("\nTop Results:")
                for i, result in enumerate(vector["results"][:5], 1):
                    file_path = result.get("file_path", "Unknown")
                    score = result.get("score", 0)
                    content = result.get("content", "")

                    output.append(f"\n  {i}. {file_path}")
                    output.append(f"     Score: {score:.4f}")
                    if content:
                        output.append(f"     Preview: {content[:300]}...")
                    else:
                        output.append(f"     Preview: (No content in payload)")
        else:
            output.append(f"Status: ❌ Error - {vector.get('error')}")

        # Knowledge Graph Results
        kg = results["sources"]["knowledge_graph"]
        output.append("\n\n🕸️  MEMGRAPH KNOWLEDGE GRAPH (Relationships)")
        output.append("-" * 80)
        if kg.get("status") == "success":
            output.append(f"Status: ✅ Success")
            output.append(
                f"Results: {kg['results_count']} documents with relationships"
            )
            output.append(f"Response Time: {kg['response_time_ms']}ms")
            if kg.get("connection"):
                output.append(f"Connection: {kg['connection']}")
            if kg.get("search_term"):
                output.append(f"Search Term: '{kg['search_term']}'")

            if kg.get("results"):
                output.append("\nTop Results (ordered by relationship count):")
                for i, result in enumerate(kg["results"][:5], 1):
                    file_path = result.get("file_path", "Unknown")
                    rel_count = result.get("relationship_count", 0)
                    rel_types = result.get("relationship_types", [])
                    related_entities = result.get("related_entities", [])
                    content_preview = result.get("content_preview", "")

                    output.append(f"\n  {i}. {file_path}")
                    output.append(f"     Relationships: {rel_count}")
                    if rel_types:
                        output.append(
                            f"     Relationship Types: {', '.join(rel_types)}"
                        )
                    if related_entities:
                        # Flatten nested lists and get unique entity types
                        flat_entities = [
                            item
                            for sublist in related_entities
                            for item in (
                                sublist if isinstance(sublist, list) else [sublist]
                            )
                        ]
                        unique_entities = list(set(flat_entities))
                        if unique_entities:
                            output.append(
                                f"     Related Entities: {', '.join(unique_entities)}"
                            )
                    if content_preview:
                        output.append(f"     Preview: {content_preview[:200]}...")
            elif kg["results_count"] == 0:
                output.append("\nNo documents found matching the search term.")
        else:
            output.append(f"Status: ❌ Error - {kg.get('error')}")

        output.append("\n" + "=" * 80)
        output.append("✅ ORCHESTRATED QUERY COMPLETE")
        output.append("=" * 80)

        return "\n".join(output)


async def main():
    parser = argparse.ArgumentParser(
        description="Demo: Orchestrated Multi-Source Intelligence Query"
    )
    parser.add_argument(
        "--query",
        "-q",
        default="how to build an omni orchestrator node",
        help="Query string",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=10,
        help="Maximum results per source",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--search-url",
        default=SEARCH_SERVICE_URL,
        help="Search service URL",
    )
    parser.add_argument(
        "--intelligence-url",
        default=INTELLIGENCE_SERVICE_URL,
        help="Intelligence service URL",
    )

    args = parser.parse_args()

    # Create demo instance
    demo = OrchestratedSearchDemo(
        search_url=args.search_url,
        intelligence_url=args.intelligence_url,
    )

    print("🚀 Starting orchestrated intelligence query...\n")

    # Execute query
    results = await demo.query_all_sources(args.query, args.limit)

    # Format and display results
    output_format = "json" if args.json else "human"
    print(demo.format_results(results, output_format))


if __name__ == "__main__":
    asyncio.run(main())
