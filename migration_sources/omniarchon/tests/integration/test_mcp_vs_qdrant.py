#!/usr/bin/env python3
"""
Test MCP service queries vs direct Qdrant search to identify routing issues.

Since we confirmed Qdrant has 3,888 indexed documents and search works,
this test will identify if the issue is in the MCP routing layer.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict

import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MCPQdrantComparisonTest:
    """Compare MCP service results with direct Qdrant results"""

    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        mcp_url: str = "http://localhost:8051",
        search_service_url: str = "http://localhost:8055",
    ):
        self.qdrant_url = qdrant_url.rstrip("/")
        self.mcp_url = mcp_url.rstrip("/")
        self.search_service_url = search_service_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def test_direct_qdrant_search(
        self, query: str = "authentication", limit: int = 5
    ) -> Dict[str, Any]:
        """Test direct Qdrant search with a real query"""
        logger.info(f"🎯 Testing direct Qdrant search for '{query}'...")

        try:
            # Create a dummy embedding vector for testing
            # In a real scenario, we'd generate this from the query using OpenAI
            dummy_vector = [0.1] * 1536

            payload = {
                "vector": dummy_vector,
                "limit": limit,
                "with_payload": True,
                "with_vectors": False,
            }

            response = await self.client.post(
                f"{self.qdrant_url}/collections/archon_vectors/points/search",
                json=payload,
            )

            if response.status_code == 200:
                data = response.json()
                results = data.get("result", [])

                logger.info(f"✅ Direct Qdrant: {len(results)} results")
                for i, result in enumerate(results[:3]):
                    score = result.get("score", 0)
                    payload = result.get("payload", {})
                    title = payload.get("title", "Untitled")[:60]
                    entity_type = payload.get("entity_type", "unknown")
                    logger.info(
                        f"  {i+1}. {title}... (type: {entity_type}, score: {score:.4f})"
                    )

                return {
                    "success": True,
                    "query": query,
                    "results_count": len(results),
                    "results": results[:5],
                    "source": "direct_qdrant",
                }
            else:
                logger.error(f"❌ Direct Qdrant search failed: {response.status_code}")
                return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"❌ Direct Qdrant search error: {e}")
            return {"success": False, "error": str(e)}

    async def test_search_service(
        self, query: str = "authentication", limit: int = 5
    ) -> Dict[str, Any]:
        """Test the search service API"""
        logger.info(f"🌐 Testing search service for '{query}'...")

        try:
            payload = {
                "query": query,
                "mode": "hybrid",
                "limit": limit,
                "include_content": True,
            }

            response = await self.client.post(
                f"{self.search_service_url}/search", json=payload
            )

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                total_results = data.get("total_results", 0)

                logger.info(
                    f"✅ Search service: {total_results} total results, {len(results)} returned"
                )
                for i, result in enumerate(results[:3]):
                    title = result.get("title", "Untitled")[:60]
                    score = result.get("relevance_score", 0)
                    entity_type = result.get("entity_type", "unknown")
                    logger.info(
                        f"  {i+1}. {title}... (type: {entity_type}, score: {score:.4f})"
                    )

                return {
                    "success": True,
                    "query": query,
                    "results_count": len(results),
                    "total_results": total_results,
                    "results": results[:5],
                    "source": "search_service",
                }
            else:
                logger.error(
                    f"❌ Search service failed: {response.status_code} - {response.text}"
                )
                return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"❌ Search service error: {e}")
            return {"success": False, "error": str(e)}

    async def test_mcp_rag_query(
        self, query: str = "authentication", limit: int = 5
    ) -> Dict[str, Any]:
        """Test MCP RAG query"""
        logger.info(f"🔧 Testing MCP RAG query for '{query}'...")

        try:
            payload = {
                "method": "perform_rag_query",
                "params": {"query": query, "match_count": limit, "context": "general"},
            }

            response = await self.client.post(f"{self.mcp_url}/mcp/call", json=payload)

            if response.status_code == 200:
                data = response.json()

                # Extract results from the orchestrated response
                results_count = 0
                results = []

                if "content" in data and isinstance(data["content"], dict):
                    content = data["content"]

                    # Check orchestrated format
                    if "results" in content and isinstance(content["results"], dict):
                        all_results = content["results"]

                        # Combine all service results
                        for service_name, service_data in all_results.items():
                            if (
                                isinstance(service_data, dict)
                                and "results" in service_data
                            ):
                                service_results = service_data["results"]
                                results.extend(
                                    service_results[:2]
                                )  # Take first 2 from each service
                                results_count += len(service_results)
                                logger.info(
                                    f"  - {service_name}: {len(service_results)} results"
                                )

                        logger.info(
                            f"✅ MCP RAG (orchestrated): {results_count} total results, {len(results)} shown"
                        )
                    else:
                        # Legacy format
                        results = content.get("results", [])
                        results_count = len(results)
                        logger.info(f"✅ MCP RAG (legacy): {results_count} results")

                    # Show sample results
                    for i, result in enumerate(results[:3]):
                        title = result.get("title", "Untitled")[:60]
                        score = result.get("relevance_score", result.get("score", 0))
                        entity_type = result.get("entity_type", "unknown")
                        logger.info(
                            f"  {i+1}. {title}... (type: {entity_type}, score: {score:.4f})"
                        )

                return {
                    "success": True,
                    "query": query,
                    "results_count": results_count,
                    "results": results[:5],
                    "source": "mcp_rag_query",
                    "raw_response": data,
                }
            else:
                logger.error(
                    f"❌ MCP RAG query failed: {response.status_code} - {response.text}"
                )
                return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"❌ MCP RAG query error: {e}")
            return {"success": False, "error": str(e)}

    async def test_mcp_advanced_vector_search(
        self, query: str = "authentication", limit: int = 5
    ) -> Dict[str, Any]:
        """Test MCP advanced vector search specifically"""
        logger.info(f"🎯 Testing MCP advanced vector search for '{query}'...")

        try:
            payload = {
                "method": "advanced_vector_search",
                "params": {
                    "query": query,
                    "limit": limit,
                    "threshold": 0.0,
                    "include_content": True,
                },
            }

            response = await self.client.post(f"{self.mcp_url}/mcp/call", json=payload)

            if response.status_code == 200:
                data = response.json()

                # Extract results from the orchestrated response
                results_count = 0
                results = []

                if "content" in data and isinstance(data["content"], dict):
                    content = data["content"]

                    # Check orchestrated format
                    if "results" in content and isinstance(content["results"], dict):
                        vector_results = content["results"].get("vector_search", {})
                        if "results" in vector_results:
                            results = vector_results["results"]
                            results_count = len(results)
                            logger.info(
                                f"✅ MCP vector search: {results_count} results"
                            )

                    # Show sample results
                    for i, result in enumerate(results[:3]):
                        title = result.get("title", "Untitled")[:60]
                        score = result.get("relevance_score", result.get("score", 0))
                        entity_type = result.get("entity_type", "unknown")
                        logger.info(
                            f"  {i+1}. {title}... (type: {entity_type}, score: {score:.4f})"
                        )

                return {
                    "success": True,
                    "query": query,
                    "results_count": results_count,
                    "results": results[:5],
                    "source": "mcp_vector_search",
                }
            else:
                logger.error(
                    f"❌ MCP vector search failed: {response.status_code} - {response.text}"
                )
                return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"❌ MCP vector search error: {e}")
            return {"success": False, "error": str(e)}

    async def run_comparison_test(
        self, query: str = "authentication API tokens"
    ) -> Dict[str, Any]:
        """Run comprehensive comparison test"""
        logger.info("\n🚀 Starting MCP vs Qdrant comparison test")
        logger.info(f"📝 Query: '{query}'")
        logger.info(f"🕐 Time: {datetime.now().isoformat()}")

        results = {"query": query, "timestamp": datetime.now().isoformat(), "tests": {}}

        # Test all endpoints
        logger.info("\n" + "=" * 80)
        results["tests"]["direct_qdrant"] = await self.test_direct_qdrant_search(query)

        logger.info("\n" + "=" * 80)
        results["tests"]["search_service"] = await self.test_search_service(query)

        logger.info("\n" + "=" * 80)
        results["tests"]["mcp_rag_query"] = await self.test_mcp_rag_query(query)

        logger.info("\n" + "=" * 80)
        results["tests"]["mcp_vector_search"] = (
            await self.test_mcp_advanced_vector_search(query)
        )

        # Analysis
        logger.info("\n" + "=" * 80)
        analysis = self._analyze_comparison(results)
        results["analysis"] = analysis

        return results

    def _analyze_comparison(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze comparison results to identify the routing issue"""
        logger.info("📊 ANALYZING COMPARISON RESULTS...")

        analysis = {
            "qdrant_working": False,
            "search_service_working": False,
            "mcp_rag_working": False,
            "mcp_vector_working": False,
            "issue_identified": False,
            "root_cause": "unknown",
            "recommendations": [],
        }

        tests = results.get("tests", {})

        # Check each service
        qdrant_test = tests.get("direct_qdrant", {})
        analysis["qdrant_working"] = (
            qdrant_test.get("success", False)
            and qdrant_test.get("results_count", 0) > 0
        )

        search_test = tests.get("search_service", {})
        analysis["search_service_working"] = (
            search_test.get("success", False)
            and search_test.get("results_count", 0) > 0
        )

        mcp_rag_test = tests.get("mcp_rag_query", {})
        analysis["mcp_rag_working"] = (
            mcp_rag_test.get("success", False)
            and mcp_rag_test.get("results_count", 0) > 0
        )

        mcp_vector_test = tests.get("mcp_vector_search", {})
        analysis["mcp_vector_working"] = (
            mcp_vector_test.get("success", False)
            and mcp_vector_test.get("results_count", 0) > 0
        )

        # Determine root cause
        if analysis["qdrant_working"]:
            if not analysis["search_service_working"]:
                analysis["root_cause"] = "search_service_issue"
                analysis["recommendations"].extend(
                    [
                        "🔧 Search service (port 8055) is not properly querying Qdrant",
                        "📝 Check search service Qdrant adapter configuration",
                        "🔍 Verify search service can connect to Qdrant at localhost:6333",
                    ]
                )
            elif not analysis["mcp_rag_working"] and not analysis["mcp_vector_working"]:
                analysis["root_cause"] = "mcp_routing_issue"
                analysis["recommendations"].extend(
                    [
                        "🔧 MCP service (port 8051) is not properly routing to search service or Qdrant",
                        "📝 Check MCP orchestration configuration",
                        "🔍 Verify MCP service can connect to search service at localhost:8055",
                    ]
                )
            elif analysis["mcp_rag_working"] and not analysis["mcp_vector_working"]:
                analysis["root_cause"] = "mcp_vector_routing_issue"
                analysis["recommendations"].extend(
                    [
                        "🔧 MCP vector search routing specifically is broken",
                        "📝 Check advanced_vector_search MCP function implementation",
                    ]
                )
            else:
                analysis["root_cause"] = "query_or_embedding_issue"
                analysis["recommendations"].extend(
                    [
                        "🔧 Issue may be with query processing or embedding generation",
                        "📝 Check if OpenAI API key is configured for embeddings",
                    ]
                )
        else:
            analysis["root_cause"] = "qdrant_search_issue"
            analysis["recommendations"].extend(
                [
                    "🔧 Qdrant search functionality has issues despite having documents",
                    "📝 Check Qdrant search endpoint configuration",
                ]
            )

        analysis["issue_identified"] = analysis["root_cause"] != "unknown"

        # Print summary
        logger.info("\n📋 COMPARISON SUMMARY:")
        logger.info(f"  - Direct Qdrant working: {analysis['qdrant_working']}")
        logger.info(f"  - Search service working: {analysis['search_service_working']}")
        logger.info(f"  - MCP RAG working: {analysis['mcp_rag_working']}")
        logger.info(f"  - MCP vector working: {analysis['mcp_vector_working']}")
        logger.info(f"  - Root cause: {analysis['root_cause']}")

        if analysis["recommendations"]:
            logger.info("\n💡 RECOMMENDATIONS:")
            for rec in analysis["recommendations"]:
                logger.info(f"  {rec}")

        return analysis

    async def close(self):
        """Clean up resources"""
        await self.client.aclose()


async def main():
    """Main test function"""
    tester = MCPQdrantComparisonTest()

    try:
        results = await tester.run_comparison_test()

        # Save results
        output_file = (
            f"mcp_qdrant_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)

        logger.info(f"\n💾 Results saved to: {output_file}")

        # Print final verdict
        analysis = results.get("analysis", {})
        root_cause = analysis.get("root_cause", "unknown")

        if root_cause == "search_service_issue":
            logger.info(
                "\n🎯 VERDICT: Search service is not properly connecting to Qdrant"
            )
        elif root_cause == "mcp_routing_issue":
            logger.info(
                "\n🎯 VERDICT: MCP service routing to search service/Qdrant is broken"
            )
        elif root_cause == "mcp_vector_routing_issue":
            logger.info(
                "\n🎯 VERDICT: MCP vector search routing specifically is broken"
            )
        elif root_cause == "query_or_embedding_issue":
            logger.info("\n🎯 VERDICT: Query processing or embedding generation issue")
        else:
            logger.info("\n🤔 VERDICT: Root cause needs further investigation")

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return 1
    finally:
        await tester.close()

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(main()))
