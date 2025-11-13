#!/usr/bin/env python3
"""
Test script to verify MCP document indexing and compare direct Qdrant queries vs RAG search results.

This script will help identify if MCP documents are properly indexed in Qdrant
but not appearing in RAG search results due to routing issues.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, List

# Add paths for imports
sys.path.append("/Volumes/PRO-G40/Code/Archon/services/search")
sys.path.append("/Volumes/PRO-G40/Code/Archon/python/src")

try:
    from services.search.engines.qdrant_adapter import QdrantAdapter
    from services.search.engines.vector_search import VectorSearchEngine
    from services.search.models.search_models import EntityType, SearchRequest
except ImportError as e:
    # Skip tests if imports fail - pytest will handle this gracefully
    import pytest

    pytest.skip(
        f"Import error: {e}. Please ensure you're running this from the Archon root directory",
        allow_module_level=True,
    )

import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SearchComparisonTest:
    """Test class to compare direct Qdrant queries vs RAG search results"""

    def __init__(self):
        self.qdrant_adapter = QdrantAdapter(
            qdrant_url="http://localhost:6333",
            collection_name="archon_vectors",
            quality_collection="quality_vectors",
        )
        self.vector_search = VectorSearchEngine()
        self.search_service_url = "http://localhost:8055"
        self.mcp_service_url = "http://localhost:8051"

    async def initialize(self):
        """Initialize all services"""
        try:
            await self.qdrant_adapter.initialize()
            await self.vector_search.initialize()
            logger.info("✅ Services initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize services: {e}")
            raise

    async def check_qdrant_collections(self) -> Dict[str, Any]:
        """Check what's actually stored in Qdrant collections"""
        logger.info("\n🔍 Checking Qdrant collection contents...")

        results = {}

        for collection_name in ["archon_vectors", "quality_vectors"]:
            try:
                stats = await self.qdrant_adapter.get_collection_stats(collection_name)
                logger.info(f"📊 Collection '{collection_name}' stats:")
                logger.info(f"  - Points count: {stats.get('points_count', 0)}")
                logger.info(f"  - Vectors count: {stats.get('vectors_count', 0)}")
                logger.info(
                    f"  - Indexed vectors: {stats.get('indexed_vectors_count', 0)}"
                )

                results[collection_name] = stats

                # Get a few sample documents to see what's indexed
                sample_docs = await self._get_sample_documents(collection_name)
                results[f"{collection_name}_samples"] = sample_docs

                logger.info(f"📄 Sample documents in '{collection_name}':")
                for i, doc in enumerate(sample_docs[:3]):
                    title = doc.get("title", "Untitled")[:50]
                    entity_type = doc.get("entity_type", "unknown")
                    source_id = doc.get("source_id", "unknown")
                    logger.info(
                        f"  {i+1}. {title}... (type: {entity_type}, source: {source_id})"
                    )

            except Exception as e:
                logger.error(f"❌ Failed to check collection {collection_name}: {e}")
                results[collection_name] = {"error": str(e)}

        return results

    async def _get_sample_documents(
        self, collection_name: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get sample documents from a Qdrant collection"""
        try:
            scroll_result = self.qdrant_adapter.client.scroll(
                collection_name=collection_name,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )

            documents = []
            if (
                scroll_result and scroll_result[0]
            ):  # scroll_result is (points, next_page_offset)
                for point in scroll_result[0]:
                    documents.append(point.payload)

            return documents
        except Exception as e:
            logger.error(f"Failed to get sample documents from {collection_name}: {e}")
            return []

    async def test_direct_qdrant_search(
        self, query: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Test direct Qdrant vector similarity search"""
        logger.info(f"\n🎯 Testing direct Qdrant search for: '{query}'")

        try:
            # Generate embedding for query
            query_vector = await self.vector_search.generate_embedding(query)
            if query_vector is None:
                logger.error("❌ Failed to generate embedding for query")
                return []

            # Create search request
            request = SearchRequest(
                query=query,
                max_semantic_results=limit,
                semantic_threshold=0.0,  # Low threshold to get more results
                entity_types=[],
                source_ids=[],
                include_content=True,
            )

            # Search in main collection
            main_results = await self.qdrant_adapter.similarity_search(
                query_vector, request, "archon_vectors"
            )

            # Search in quality collection
            quality_results = await self.qdrant_adapter.similarity_search(
                query_vector, request, "quality_vectors"
            )

            logger.info("✅ Direct Qdrant search results:")
            logger.info(f"  - Main collection: {len(main_results)} results")
            logger.info(f"  - Quality collection: {len(quality_results)} results")

            # Log top results
            for i, result in enumerate(main_results[:3]):
                logger.info(
                    f"  {i+1}. {result.title[:50]}... (score: {result.relevance_score:.3f})"
                )

            return [
                {
                    "collection": "archon_vectors",
                    "results": [
                        {
                            "entity_id": r.entity_id,
                            "title": r.title,
                            "score": r.relevance_score,
                            "entity_type": r.entity_type,
                            "source_id": r.source_id,
                        }
                        for r in main_results
                    ],
                },
                {
                    "collection": "quality_vectors",
                    "results": [
                        {
                            "entity_id": r.entity_id,
                            "title": r.title,
                            "score": r.relevance_score,
                            "entity_type": r.entity_type,
                            "source_id": r.source_id,
                        }
                        for r in quality_results
                    ],
                },
            ]

        except Exception as e:
            logger.error(f"❌ Direct Qdrant search failed: {e}")
            return []

    async def test_search_service_api(
        self, query: str, limit: int = 5
    ) -> Dict[str, Any]:
        """Test the search service API directly"""
        logger.info(f"\n🌐 Testing search service API for: '{query}'")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.search_service_url}/search",
                    json={
                        "query": query,
                        "mode": "hybrid",
                        "limit": limit,
                        "include_content": True,
                    },
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.info("✅ Search service API results:")
                    logger.info(f"  - Status: {result.get('success', False)}")
                    logger.info(f"  - Total results: {result.get('total_results', 0)}")

                    results = result.get("results", [])
                    for i, res in enumerate(results[:3]):
                        title = res.get("title", "Untitled")[:50]
                        score = res.get("relevance_score", 0)
                        logger.info(f"  {i+1}. {title}... (score: {score:.3f})")

                    return result
                else:
                    logger.error(
                        f"❌ Search service API error: {response.status_code} - {response.text}"
                    )
                    return {"error": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"❌ Search service API test failed: {e}")
            return {"error": str(e)}

    async def test_mcp_rag_query(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Test MCP RAG query endpoint"""
        logger.info(f"\n🔧 Testing MCP RAG query for: '{query}'")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.mcp_service_url}/mcp/call",
                    json={
                        "method": "perform_rag_query",
                        "params": {
                            "query": query,
                            "match_count": limit,
                            "context": "general",
                        },
                    },
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.info("✅ MCP RAG query results:")

                    # Check if this is the orchestrated response format
                    if "content" in result and isinstance(result["content"], dict):
                        content = result["content"]
                        if "results" in content:
                            # This is orchestrated search results
                            rag_results = content.get("results", {}).get(
                                "rag_search", {}
                            )
                            vector_results = content.get("results", {}).get(
                                "vector_search", {}
                            )

                            logger.info(
                                f"  - RAG search results: {len(rag_results.get('results', []))}"
                            )
                            logger.info(
                                f"  - Vector search results: {len(vector_results.get('results', []))}"
                            )

                            # Log sample results
                            for source, source_data in content.get(
                                "results", {}
                            ).items():
                                if (
                                    isinstance(source_data, dict)
                                    and "results" in source_data
                                ):
                                    results = source_data["results"]
                                    logger.info(f"  {source}: {len(results)} results")
                                    for i, res in enumerate(results[:2]):
                                        title = res.get("title", "Untitled")[:50]
                                        logger.info(f"    {i+1}. {title}...")
                        else:
                            # Legacy format
                            results = content.get("results", [])
                            logger.info(f"  - Results: {len(results)}")
                            for i, res in enumerate(results[:3]):
                                title = res.get("title", "Untitled")[:50]
                                logger.info(f"    {i+1}. {title}...")

                    return result
                else:
                    logger.error(
                        f"❌ MCP RAG query error: {response.status_code} - {response.text}"
                    )
                    return {"error": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"❌ MCP RAG query test failed: {e}")
            return {"error": str(e)}

    async def run_comprehensive_test(
        self, query: str = "MCP document creation authentication"
    ) -> Dict[str, Any]:
        """Run comprehensive comparison test"""
        logger.info("\n🚀 Starting comprehensive search comparison test")
        logger.info(f"📝 Test query: '{query}'")
        logger.info(f"🕐 Test time: {datetime.now().isoformat()}")

        test_results = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "results": {},
        }

        try:
            # 1. Check Qdrant collections
            logger.info("\n" + "=" * 60)
            collection_stats = await self.check_qdrant_collections()
            test_results["results"]["qdrant_collections"] = collection_stats

            # 2. Test direct Qdrant search
            logger.info("\n" + "=" * 60)
            qdrant_results = await self.test_direct_qdrant_search(query)
            test_results["results"]["direct_qdrant"] = qdrant_results

            # 3. Test search service API
            logger.info("\n" + "=" * 60)
            search_api_results = await self.test_search_service_api(query)
            test_results["results"]["search_service_api"] = search_api_results

            # 4. Test MCP RAG query
            logger.info("\n" + "=" * 60)
            mcp_rag_results = await self.test_mcp_rag_query(query)
            test_results["results"]["mcp_rag_query"] = mcp_rag_results

            # 5. Analysis and comparison
            logger.info("\n" + "=" * 60)
            analysis = self._analyze_results(test_results)
            test_results["analysis"] = analysis

            return test_results

        except Exception as e:
            logger.error(f"❌ Comprehensive test failed: {e}")
            test_results["error"] = str(e)
            return test_results

    def _analyze_results(self, test_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze and compare the different search results"""
        logger.info("\n📊 ANALYSIS: Comparing search results...")

        analysis = {
            "qdrant_indexed_documents": 0,
            "direct_qdrant_results": 0,
            "search_api_results": 0,
            "mcp_rag_results": 0,
            "hypothesis_confirmed": False,
            "key_findings": [],
            "recommendations": [],
        }

        results = test_results.get("results", {})

        # Check if documents are indexed in Qdrant
        qdrant_collections = results.get("qdrant_collections", {})
        total_docs = 0
        for collection in ["archon_vectors", "quality_vectors"]:
            if collection in qdrant_collections:
                points = qdrant_collections[collection].get("points_count", 0)
                total_docs += points
                logger.info(f"📚 {collection}: {points} documents indexed")

        analysis["qdrant_indexed_documents"] = total_docs

        # Count direct Qdrant results
        direct_qdrant = results.get("direct_qdrant", [])
        direct_count = 0
        for collection_result in direct_qdrant:
            direct_count += len(collection_result.get("results", []))
        analysis["direct_qdrant_results"] = direct_count
        logger.info(f"🎯 Direct Qdrant search: {direct_count} results")

        # Count search API results
        search_api = results.get("search_service_api", {})
        api_count = (
            search_api.get("total_results", 0) if not search_api.get("error") else 0
        )
        analysis["search_api_results"] = api_count
        logger.info(f"🌐 Search service API: {api_count} results")

        # Count MCP RAG results
        mcp_rag = results.get("mcp_rag_query", {})
        mcp_count = 0
        if not mcp_rag.get("error") and "content" in mcp_rag:
            content = mcp_rag["content"]
            if "results" in content and isinstance(content["results"], dict):
                # Orchestrated format
                for source_data in content["results"].values():
                    if isinstance(source_data, dict) and "results" in source_data:
                        mcp_count += len(source_data["results"])
            elif "results" in content and isinstance(content["results"], list):
                # Legacy format
                mcp_count = len(content["results"])

        analysis["mcp_rag_results"] = mcp_count
        logger.info(f"🔧 MCP RAG query: {mcp_count} results")

        # Determine if hypothesis is confirmed
        if total_docs > 0 and direct_count > 0 and mcp_count == 0:
            analysis["hypothesis_confirmed"] = True
            analysis["key_findings"].append(
                "✅ HYPOTHESIS CONFIRMED: Documents are indexed in Qdrant but not returned by MCP RAG"
            )
        elif total_docs > 0 and direct_count > 0 and mcp_count > 0:
            analysis["hypothesis_confirmed"] = False
            analysis["key_findings"].append(
                "❓ Documents are indexed and MCP RAG is working - issue may be elsewhere"
            )
        elif total_docs == 0:
            analysis["hypothesis_confirmed"] = False
            analysis["key_findings"].append(
                "❌ No documents found in Qdrant collections - indexing issue"
            )
        else:
            analysis["hypothesis_confirmed"] = False
            analysis["key_findings"].append(
                "❓ Mixed results - requires further investigation"
            )

        # Generate recommendations
        if analysis["hypothesis_confirmed"]:
            analysis["recommendations"].extend(
                [
                    "🔧 Fix MCP service routing to query Qdrant collections directly",
                    "📝 Update service_client.py call_existing_rag() method",
                    "✅ Verify search orchestration routes to correct backends",
                ]
            )
        elif total_docs == 0:
            analysis["recommendations"].extend(
                [
                    "🔍 Check document indexing pipeline",
                    "✅ Verify bridge service is processing documents",
                    "📊 Check intelligence service document processing",
                ]
            )
        else:
            analysis["recommendations"].extend(
                [
                    "🔍 Investigate MCP service configuration",
                    "📊 Check service orchestration routing logic",
                    "✅ Verify all services are properly connected",
                ]
            )

        # Print summary
        logger.info("\n📋 SUMMARY:")
        for finding in analysis["key_findings"]:
            logger.info(f"  {finding}")

        logger.info("\n💡 RECOMMENDATIONS:")
        for rec in analysis["recommendations"]:
            logger.info(f"  {rec}")

        return analysis

    async def close(self):
        """Clean up resources"""
        try:
            await self.qdrant_adapter.close()
            await self.vector_search.close()
            logger.info("✅ Resources cleaned up")
        except Exception as e:
            logger.error(f"❌ Failed to clean up resources: {e}")


async def main():
    """Main test function"""
    test = SearchComparisonTest()

    try:
        await test.initialize()

        # Run the comprehensive test
        results = await test.run_comprehensive_test()

        # Save results to file
        output_file = (
            f"search_comparison_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)

        logger.info(f"\n💾 Test results saved to: {output_file}")

        # Print final verdict
        analysis = results.get("analysis", {})
        if analysis.get("hypothesis_confirmed"):
            logger.info(
                "\n🎯 VERDICT: Search routing issue confirmed - documents exist but MCP RAG doesn't find them"
            )
        else:
            logger.info("\n🤔 VERDICT: Issue requires further investigation")

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return 1
    finally:
        await test.close()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
