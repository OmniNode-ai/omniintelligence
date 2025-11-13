#!/usr/bin/env python3
"""
Direct Qdrant connectivity and collection inspection test.

This script directly connects to Qdrant to check collection status,
document counts, and perform basic searches without complex dependencies.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List

import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QdrantDirectTester:
    """Direct Qdrant testing using HTTP API"""

    def __init__(self, qdrant_url: str = "http://localhost:6333"):
        self.qdrant_url = qdrant_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def check_health(self) -> Dict[str, Any]:
        """Check Qdrant service health by testing the root endpoint"""
        logger.info("🔍 Checking Qdrant service health...")

        try:
            response = await self.client.get(f"{self.qdrant_url}/")
            if response.status_code == 200:
                data = response.json()
                logger.info(
                    f"✅ Qdrant service is healthy - version {data.get('version', 'unknown')}"
                )
                return {"status": "healthy", "details": data}
            else:
                logger.error(f"❌ Qdrant health check failed: {response.status_code}")
                return {"status": "unhealthy", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            logger.error(f"❌ Failed to connect to Qdrant: {e}")
            return {"status": "unreachable", "error": str(e)}

    async def list_collections(self) -> Dict[str, Any]:
        """List all collections in Qdrant"""
        logger.info("📂 Listing Qdrant collections...")

        try:
            response = await self.client.get(f"{self.qdrant_url}/collections")
            if response.status_code == 200:
                data = response.json()
                collections = data.get("result", {}).get("collections", [])
                logger.info(f"✅ Found {len(collections)} collections:")

                for collection in collections:
                    name = collection.get("name", "unknown")
                    logger.info(f"  - {name}")

                return {"success": True, "collections": collections}
            else:
                logger.error(f"❌ Failed to list collections: {response.status_code}")
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            logger.error(f"❌ Error listing collections: {e}")
            return {"success": False, "error": str(e)}

    async def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific collection"""
        logger.info(f"📊 Getting info for collection '{collection_name}'...")

        try:
            # Get collection info
            response = await self.client.get(
                f"{self.qdrant_url}/collections/{collection_name}"
            )
            if response.status_code == 200:
                collection_info = response.json().get("result", {})

                # Get collection statistics
                stats_response = await self.client.get(
                    f"{self.qdrant_url}/collections/{collection_name}/cluster"
                )
                if stats_response.status_code == 200:
                    stats_response.json().get("result", {})

                points_count = collection_info.get("points_count", 0)
                vectors_count = collection_info.get("vectors_count", 0)
                indexed_vectors_count = collection_info.get("indexed_vectors_count", 0)

                logger.info(f"✅ Collection '{collection_name}' info:")
                logger.info(f"  - Points count: {points_count}")
                logger.info(f"  - Vectors count: {vectors_count}")
                logger.info(f"  - Indexed vectors: {indexed_vectors_count}")

                return {
                    "success": True,
                    "collection_name": collection_name,
                    "points_count": points_count,
                    "vectors_count": vectors_count,
                    "indexed_vectors_count": indexed_vectors_count,
                    "config": collection_info.get("config", {}),
                    "status": collection_info.get("status", "unknown"),
                }
            else:
                logger.error(
                    f"❌ Collection '{collection_name}' not found or error: {response.status_code}"
                )
                return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"❌ Error getting collection info: {e}")
            return {"success": False, "error": str(e)}

    async def get_sample_documents(
        self, collection_name: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get sample documents from a collection"""
        logger.info(f"📄 Getting sample documents from '{collection_name}'...")

        try:
            # Use scroll API to get sample documents
            payload = {
                "limit": limit,
                "with_payload": True,
                "with_vectors": False,  # Don't need vectors for inspection
            }

            response = await self.client.post(
                f"{self.qdrant_url}/collections/{collection_name}/points/scroll",
                json=payload,
            )

            if response.status_code == 200:
                data = response.json()
                points = data.get("result", {}).get("points", [])

                documents = []
                for point in points:
                    payload = point.get("payload", {})
                    documents.append(
                        {
                            "id": point.get("id"),
                            "title": payload.get("title", "Untitled")[:80] + "...",
                            "entity_type": payload.get("entity_type", "unknown"),
                            "source_id": payload.get("source_id", "unknown"),
                            "content_preview": payload.get("content", "")[:100] + "...",
                        }
                    )

                logger.info(f"✅ Retrieved {len(documents)} sample documents:")
                for i, doc in enumerate(documents[:5]):
                    logger.info(
                        f"  {i+1}. {doc['title']} (type: {doc['entity_type']}, source: {doc['source_id']})"
                    )

                return documents
            else:
                logger.error(
                    f"❌ Failed to get sample documents: {response.status_code}"
                )
                return []

        except Exception as e:
            logger.error(f"❌ Error getting sample documents: {e}")
            return []

    async def test_search(
        self, collection_name: str, query_text: str = "test"
    ) -> Dict[str, Any]:
        """Test search functionality using a dummy vector"""
        logger.info(
            f"🔍 Testing search in collection '{collection_name}' with query '{query_text}'..."
        )

        try:
            # Create a dummy vector for testing (1536 dimensions, all 0.1)
            dummy_vector = [0.1] * 1536

            payload = {
                "vector": dummy_vector,
                "limit": 5,
                "with_payload": True,
                "with_vectors": False,
            }

            response = await self.client.post(
                f"{self.qdrant_url}/collections/{collection_name}/points/search",
                json=payload,
            )

            if response.status_code == 200:
                data = response.json()
                results = data.get("result", [])

                logger.info(f"✅ Search returned {len(results)} results:")
                for i, result in enumerate(results[:3]):
                    score = result.get("score", 0)
                    payload = result.get("payload", {})
                    title = payload.get("title", "Untitled")[:50]
                    logger.info(f"  {i+1}. {title}... (score: {score:.4f})")

                return {
                    "success": True,
                    "results_count": len(results),
                    "results": results[:5],  # Return top 5
                }
            else:
                logger.error(f"❌ Search failed: {response.status_code}")
                return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"❌ Error during search: {e}")
            return {"success": False, "error": str(e)}

    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive Qdrant inspection test"""
        logger.info("🚀 Starting comprehensive Qdrant inspection...")

        results = {
            "timestamp": datetime.now().isoformat(),
            "qdrant_url": self.qdrant_url,
            "tests": {},
        }

        # 1. Check health
        logger.info("\n" + "=" * 60)
        health_result = await self.check_health()
        results["tests"]["health"] = health_result

        if health_result["status"] != "healthy":
            logger.error("🚨 Qdrant is not healthy, stopping tests")
            return results

        # 2. List collections
        logger.info("\n" + "=" * 60)
        collections_result = await self.list_collections()
        results["tests"]["collections"] = collections_result

        if not collections_result["success"]:
            logger.error("🚨 Cannot list collections, stopping tests")
            return results

        # 3. Inspect each collection
        logger.info("\n" + "=" * 60)
        collection_details = {}

        standard_collections = ["archon_vectors", "quality_vectors"]
        found_collections = [c["name"] for c in collections_result["collections"]]

        for collection_name in standard_collections:
            if collection_name in found_collections:
                logger.info(f"\n--- Inspecting {collection_name} ---")

                # Get collection info
                info = await self.get_collection_info(collection_name)
                collection_details[collection_name] = info

                if info["success"] and info["points_count"] > 0:
                    # Get sample documents
                    samples = await self.get_sample_documents(collection_name)
                    collection_details[collection_name]["samples"] = samples

                    # Test search
                    search_result = await self.test_search(collection_name)
                    collection_details[collection_name]["search_test"] = search_result
                else:
                    logger.warning(
                        f"⚠️ Collection '{collection_name}' is empty or inaccessible"
                    )
            else:
                logger.warning(f"⚠️ Expected collection '{collection_name}' not found")
                collection_details[collection_name] = {
                    "success": False,
                    "error": "Collection not found",
                }

        results["tests"]["collection_details"] = collection_details

        # 4. Analysis
        logger.info("\n" + "=" * 60)
        analysis = self._analyze_results(results)
        results["analysis"] = analysis

        return results

    def _analyze_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze test results and provide recommendations"""
        logger.info("📊 ANALYZING RESULTS...")

        analysis = {
            "overall_status": "unknown",
            "total_documents": 0,
            "collections_healthy": 0,
            "issues_found": [],
            "recommendations": [],
        }

        collection_details = results["tests"].get("collection_details", {})

        # Count documents and healthy collections
        for collection_name, details in collection_details.items():
            if details.get("success"):
                analysis["collections_healthy"] += 1
                points_count = details.get("points_count", 0)
                analysis["total_documents"] += points_count

                if points_count == 0:
                    analysis["issues_found"].append(
                        f"Collection '{collection_name}' is empty"
                    )
                elif not details.get("search_test", {}).get("success"):
                    analysis["issues_found"].append(
                        f"Search functionality broken in '{collection_name}'"
                    )
                else:
                    logger.info(
                        f"✅ Collection '{collection_name}': {points_count} documents, search working"
                    )
            else:
                analysis["issues_found"].append(
                    f"Collection '{collection_name}' not accessible"
                )

        # Determine overall status
        if analysis["total_documents"] == 0:
            analysis["overall_status"] = "no_documents"
            analysis["recommendations"].extend(
                [
                    "🔍 Check document indexing pipeline - no documents found in Qdrant",
                    "✅ Verify bridge service is processing documents",
                    "📊 Check intelligence service document processing",
                ]
            )
        elif analysis["issues_found"]:
            analysis["overall_status"] = "partial_issues"
            analysis["recommendations"].extend(
                [
                    "🔧 Address specific collection issues identified",
                    "📝 Check search functionality configuration",
                ]
            )
        else:
            analysis["overall_status"] = "healthy"
            analysis["recommendations"].append(
                "✅ Qdrant appears healthy - issue may be in routing/MCP layer"
            )

        # Print summary
        logger.info("\n📋 SUMMARY:")
        logger.info(f"  - Overall status: {analysis['overall_status']}")
        logger.info(f"  - Total documents: {analysis['total_documents']}")
        logger.info(f"  - Healthy collections: {analysis['collections_healthy']}")
        logger.info(f"  - Issues found: {len(analysis['issues_found'])}")

        if analysis["issues_found"]:
            logger.info("\n⚠️ ISSUES:")
            for issue in analysis["issues_found"]:
                logger.info(f"  - {issue}")

        logger.info("\n💡 RECOMMENDATIONS:")
        for rec in analysis["recommendations"]:
            logger.info(f"  - {rec}")

        return analysis

    async def close(self):
        """Clean up resources"""
        await self.client.aclose()


async def main():
    """Main test function"""
    tester = QdrantDirectTester()

    try:
        results = await tester.run_comprehensive_test()

        # Save results
        output_file = (
            f"qdrant_inspection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)

        logger.info(f"\n💾 Results saved to: {output_file}")

        # Print final verdict
        analysis = results.get("analysis", {})
        status = analysis.get("overall_status", "unknown")

        if status == "no_documents":
            logger.info(
                "\n🚨 VERDICT: No documents found in Qdrant - indexing pipeline issue"
            )
        elif status == "partial_issues":
            logger.info("\n⚠️ VERDICT: Qdrant partially working - some issues found")
        elif status == "healthy":
            logger.info(
                "\n✅ VERDICT: Qdrant is healthy - issue likely in MCP routing layer"
            )
        else:
            logger.info("\n🤔 VERDICT: Unable to determine issue - check results file")

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return 1
    finally:
        await tester.close()

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(main()))
