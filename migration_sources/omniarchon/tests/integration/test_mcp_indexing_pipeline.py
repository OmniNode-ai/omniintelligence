#!/usr/bin/env python3
"""
End-to-End Test for MCP Document Indexing Pipeline

This script tests the complete flow:
1. Create MCP document → 2. Bridge service processing → 3. Intelligence service extraction
4. Search service vectorization → 5. RAG query retrieval

Verifies documents are indexed and immediately available for RAG queries.
"""

import asyncio
import time
import uuid
from datetime import datetime
from typing import Dict

import httpx


class MCPIndexingPipelineTest:
    """End-to-end test for MCP document indexing pipeline"""

    def __init__(self):
        # Service URLs
        self.mcp_url = "http://localhost:8051"
        self.server_url = "http://localhost:8181"
        self.bridge_url = "http://localhost:8054"
        self.intelligence_url = "http://localhost:8053"
        self.search_url = "http://localhost:8055"

        # Test document data
        self.test_project_id = None
        self.test_document_id = None
        self.test_content = (
            "Test Document for MCP Indexing Pipeline\n\n"
            "This is a comprehensive test document created to verify the MCP document indexing pipeline. "
            "It contains unique content about vector embeddings, knowledge graphs, and semantic search capabilities. "
            "The document should be processed through the bridge service, intelligence service, and search service "
            "to become immediately available in RAG queries. This includes entity extraction, vectorization, "
            "and index refreshing for real-time availability."
        )

        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http_client.aclose()

    async def check_service_health(self) -> Dict[str, bool]:
        """Check health of all services in the pipeline"""
        print("🏥 Checking service health...")

        services = {
            "server": f"{self.server_url}/health",
            "bridge": f"{self.bridge_url}/health",
            "intelligence": f"{self.intelligence_url}/health",
            "search": f"{self.search_url}/health",
        }

        health_status = {}
        for service, url in services.items():
            try:
                response = await self.http_client.get(url)
                health_status[service] = response.status_code == 200
                status_icon = "✅" if health_status[service] else "❌"
                print(f"  {status_icon} {service}: {response.status_code}")
            except Exception as e:
                health_status[service] = False
                print(f"  ❌ {service}: {str(e)}")

        # Skip MCP health check as it doesn't have a standard health endpoint
        # but is accessible via the server
        health_status["mcp"] = True
        print("  ⏭️ mcp: Skipped (accessed via server)")

        return health_status

    async def create_test_project(self) -> str:
        """Create a test project for document testing"""
        print("📁 Creating test project...")

        project_data = {
            "title": f"MCP Indexing Test Project {datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "description": "Test project for verifying MCP document indexing pipeline",
            "github_repo": "https://github.com/test/mcp-indexing-test",
        }

        response = await self.http_client.post(
            f"{self.server_url}/api/projects", json=project_data
        )

        if response.status_code != 200:
            raise Exception(
                f"Failed to create project: {response.status_code} - {response.text}"
            )

        result = response.json()
        project_id = result.get("project_id")
        print(f"  ✅ Project created: {project_id}")
        return project_id

    async def create_test_document(self, project_id: str) -> str:
        """Create a test document via MCP API"""
        print("📝 Creating test document via MCP...")

        unique_identifier = str(uuid.uuid4())[:8]
        document_data = {
            "project_id": project_id,
            "title": f"Test Document {unique_identifier}",
            "document_type": "test",
            "content": {
                "text": self.test_content
                + f"\n\nUnique identifier: {unique_identifier}",
                "test_metadata": {
                    "created_for": "pipeline_testing",
                    "unique_id": unique_identifier,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            },
            "tags": ["test", "mcp", "indexing", "pipeline"],
        }

        response = await self.http_client.post(
            f"{self.server_url}/api/projects/{project_id}/documents", json=document_data
        )

        if response.status_code != 200:
            raise Exception(
                f"Failed to create document: {response.status_code} - {response.text}"
            )

        result = response.json()
        document_id = result.get("document_id")
        print(f"  ✅ Document created: {document_id}")
        return document_id

    async def wait_for_pipeline_processing(
        self, document_id: str, max_wait_seconds: int = 60
    ):
        """Wait for the document to be processed through the entire pipeline"""
        print(f"⏳ Waiting for pipeline processing (max {max_wait_seconds}s)...")

        start_time = time.time()
        while time.time() - start_time < max_wait_seconds:
            # Check if document is available in search results
            try:
                search_response = await self.http_client.post(
                    f"{self.search_url}/search",
                    json={
                        "query": f"Test Document {document_id[:8]}",
                        "mode": "semantic",
                        "limit": 5,
                        "include_content": True,
                    },
                )

                if search_response.status_code == 200:
                    search_results = search_response.json()

                    # Look for our document in the results
                    for result in search_results.get("results", []):
                        if document_id in result.get(
                            "entity_id", ""
                        ) or document_id in result.get("content", ""):
                            elapsed = time.time() - start_time
                            print(
                                f"  ✅ Document found in search results after {elapsed:.1f}s"
                            )
                            return True

                # Also check vector search specifically
                vector_response = await self.http_client.get(
                    f"{self.search_url}/search/stats"
                )

                if vector_response.status_code == 200:
                    stats = vector_response.json()
                    print(
                        f"  📊 Search stats: {stats.get('service_status', 'unknown')}"
                    )

            except Exception as e:
                print(f"  ⚠️ Search check error: {str(e)}")

            await asyncio.sleep(2)  # Wait 2 seconds before next check

        elapsed = time.time() - start_time
        print(
            f"  ⏰ Timeout after {elapsed:.1f}s - document not found in search results"
        )
        return False

    async def test_rag_query(self, document_id: str) -> bool:
        """Test that the document is retrievable via RAG query"""
        print("🔍 Testing RAG query retrieval...")

        # Test various search modes
        search_modes = ["semantic", "hybrid"]

        for mode in search_modes:
            print(f"  Testing {mode} search...")

            try:
                # Query with content from our test document
                query_terms = [
                    "MCP indexing pipeline",
                    "vector embeddings",
                    "knowledge graphs",
                ]

                for query in query_terms:
                    response = await self.http_client.post(
                        f"{self.search_url}/search",
                        json={
                            "query": query,
                            "mode": mode,
                            "limit": 10,
                            "include_content": True,
                        },
                    )

                    if response.status_code == 200:
                        results = response.json()

                        # Check if our document appears in results
                        for result in results.get("results", []):
                            content = result.get("content", "")
                            entity_id = result.get("entity_id", "")

                            if document_id in entity_id or document_id[:8] in content:
                                relevance_score = result.get("relevance_score", 0)
                                print(
                                    f"    ✅ Found document in {mode} search (query: '{query}', score: {relevance_score:.3f})"
                                )
                                return True
                    else:
                        print(f"    ❌ Search failed: {response.status_code}")

            except Exception as e:
                print(f"    ⚠️ Search error: {str(e)}")

        print("  ❌ Document not found in any RAG queries")
        return False

    async def verify_indexing_logs(self):
        """Check service logs for indexing pipeline activity"""
        print("📋 Checking indexing pipeline logs...")

        # Check logs from all services for our indexing pipeline markers
        services = ["archon-bridge", "archon-intelligence", "archon-search"]

        for service in services:
            try:
                # Get recent logs
                import subprocess

                result = subprocess.run(
                    ["docker", "compose", "logs", "--tail=50", service],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode == 0:
                    logs = result.stdout
                    pipeline_lines = [
                        line
                        for line in logs.split("\n")
                        if "[INDEXING PIPELINE]" in line
                    ]

                    if pipeline_lines:
                        print(f"  📝 {service} pipeline activity:")
                        for line in pipeline_lines[
                            -5:
                        ]:  # Show last 5 pipeline log lines
                            # Clean up the log line
                            clean_line = (
                                line.split("|", 1)[-1].strip()
                                if "|" in line
                                else line.strip()
                            )
                            print(f"    {clean_line}")
                    else:
                        print(f"  ⚠️ {service}: No pipeline activity found")
                else:
                    print(f"  ❌ {service}: Failed to get logs")

            except Exception as e:
                print(f"  ⚠️ {service}: Log check error: {str(e)}")

    async def cleanup_test_data(self):
        """Clean up test project and documents"""
        print("🧹 Cleaning up test data...")

        try:
            if self.test_document_id and self.test_project_id:
                # Delete test document
                response = await self.http_client.delete(
                    f"{self.server_url}/api/projects/{self.test_project_id}/documents/{self.test_document_id}"
                )
                if response.status_code == 200:
                    print("  ✅ Test document deleted")
                else:
                    print(f"  ⚠️ Document deletion failed: {response.status_code}")

            if self.test_project_id:
                # Delete test project
                response = await self.http_client.delete(
                    f"{self.server_url}/api/projects/{self.test_project_id}"
                )
                if response.status_code == 200:
                    print("  ✅ Test project deleted")
                else:
                    print(f"  ⚠️ Project deletion failed: {response.status_code}")

        except Exception as e:
            print(f"  ⚠️ Cleanup error: {str(e)}")

    async def run_complete_test(self) -> bool:
        """Run the complete end-to-end test"""
        print("🚀 Starting MCP Document Indexing Pipeline E2E Test")
        print("=" * 60)

        try:
            # 1. Check service health
            health_status = await self.check_service_health()
            unhealthy_services = [
                service for service, healthy in health_status.items() if not healthy
            ]

            if unhealthy_services:
                print(f"❌ Unhealthy services: {unhealthy_services}")
                print("Cannot proceed with test - services must be healthy")
                return False

            print("✅ All services healthy\n")

            # 2. Create test project
            self.test_project_id = await self.create_test_project()
            print()

            # 3. Create test document
            self.test_document_id = await self.create_test_document(
                self.test_project_id
            )
            print()

            # 4. Wait for pipeline processing
            processing_success = await self.wait_for_pipeline_processing(
                self.test_document_id
            )
            print()

            # 5. Test RAG query
            rag_success = (
                await self.test_rag_query(self.test_document_id)
                if processing_success
                else False
            )
            print()

            # 6. Check logs
            await self.verify_indexing_logs()
            print()

            # 7. Results
            print("=" * 60)
            if processing_success and rag_success:
                print(
                    "🎉 SUCCESS: MCP Document Indexing Pipeline is working correctly!"
                )
                print(
                    "✅ Documents are being indexed and immediately available in RAG queries"
                )
                return True
            else:
                print("❌ FAILURE: MCP Document Indexing Pipeline has issues")
                if not processing_success:
                    print("  • Document processing failed or timed out")
                if not rag_success:
                    print("  • Document not retrievable via RAG queries")
                return False

        except Exception as e:
            print(f"❌ Test failed with exception: {str(e)}")
            return False

        finally:
            # Always cleanup
            await self.cleanup_test_data()


async def main():
    """Main test execution function"""
    async with MCPIndexingPipelineTest() as test:
        success = await test.run_complete_test()
        exit_code = 0 if success else 1
        exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
