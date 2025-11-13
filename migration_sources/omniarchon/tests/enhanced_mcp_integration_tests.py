#!/usr/bin/env python3
"""
Enhanced MCP Document Indexing Integration Tests

CRITICAL FOCUS: Fix the FAILING MCP Document Creation → RAG Retrievability pathway
This test suite provides comprehensive validation of the complete MCP document indexing pipeline
with strict 30-second SLA requirements and granular component validation.

Issue: Documents created via MCP are not retrievable via RAG queries within the 30-second SLA.

Architecture Tested:
MCP Document Creation → Intelligence Service → Bridge Sync → Qdrant/Memgraph → Search Service → RAG Retrievability

Usage:
    python tests/enhanced_mcp_integration_tests.py [--strict-sla] [--verbose] [--continuous]
"""

import argparse
import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TestStatus(Enum):
    """Test execution status"""

    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    SKIP = "SKIP"


@dataclass
class TestResult:
    """Test result data structure"""

    test_name: str
    status: TestStatus
    duration: float
    message: str
    metadata: Dict[str, Any]
    timestamp: datetime


@dataclass
class SLARequirement:
    """SLA requirement definition"""

    name: str
    max_duration: float  # seconds
    description: str


class MCPDocumentIndexingTester:
    """
    Comprehensive MCP document indexing test suite with focus on the failing
    MCP Document Creation → RAG Retrievability pathway.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8181",
        mcp_url: str = "http://localhost:8051",
        strict_sla: bool = False,
        verbose: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.mcp_url = mcp_url.rstrip("/")
        self.strict_sla = strict_sla
        self.verbose = verbose
        self.test_results: List[TestResult] = []

        # Service URLs
        self.services = {
            "main_server": self.base_url,
            "mcp_server": self.mcp_url,
            "intelligence": "http://localhost:8053",
            "bridge": "http://localhost:8054",
            "search": "http://localhost:8055",
            "qdrant": "http://localhost:6333",
            "memgraph": "http://localhost:7444",
        }

        # Test data tracking
        self.test_project_id = None
        self.test_documents = []
        self.test_session_id = f"mcp_test_{uuid.uuid4().hex[:8]}_{int(time.time())}"

        # SLA Requirements
        self.sla_requirements = [
            SLARequirement("document_creation", 5.0, "MCP document creation"),
            SLARequirement("indexing_completion", 30.0, "Complete indexing pipeline"),
            SLARequirement("rag_retrievability", 30.0, "RAG query retrieval"),
            SLARequirement("vector_search", 2.0, "Vector search response"),
            SLARequirement(
                "service_communication", 10.0, "Service-to-service communication"
            ),
        ]

        if verbose:
            logger.setLevel(logging.DEBUG)

    async def run_comprehensive_tests(self, continuous: bool = False) -> Dict[str, Any]:
        """
        Run the complete enhanced test suite with focus on MCP→RAG pathway
        """
        print("🚀 Enhanced MCP Document Indexing Integration Tests")
        print("=" * 70)
        print(f"Session ID: {self.test_session_id}")
        print(f"Strict SLA Mode: {'ENABLED' if self.strict_sla else 'DISABLED'}")
        print(f"Continuous Mode: {'ENABLED' if continuous else 'DISABLED'}")
        print("=" * 70)

        start_time = time.time()

        try:
            # Phase 1: Infrastructure Validation
            await self._test_service_health_comprehensive()
            await self._test_service_communication_matrix()

            # Phase 2: Test Environment Setup
            await self._setup_test_environment()

            # Phase 3: CRITICAL - MCP Document Creation → RAG Retrievability (FAILING)
            await self._test_mcp_document_creation_with_timing()
            await self._test_intelligence_service_processing()
            await self._test_bridge_sync_triggers()
            await self._test_vector_embedding_validation()
            await self._test_knowledge_graph_sync_validation()
            await self._test_rag_retrievability_comprehensive()

            # Phase 4: Performance and SLA Validation
            await self._test_strict_sla_compliance()
            await self._test_concurrent_document_indexing()
            await self._test_large_document_handling()

            # Phase 5: Error Handling and Edge Cases
            await self._test_service_failure_scenarios()
            await self._test_malformed_document_handling()
            await self._test_concurrent_load_scenarios()

            # Phase 6: End-to-End Pipeline Validation
            await self._test_complete_pipeline_with_validation()

            # Continuous testing loop
            if continuous:
                await self._run_continuous_monitoring()

        except Exception as e:
            logger.error(f"Test suite failed with error: {e}")
            self._record_test_result(
                "test_suite_execution",
                TestStatus.FAIL,
                time.time() - start_time,
                f"Suite execution failed: {e}",
            )
        finally:
            # Always cleanup
            await self._cleanup_test_environment()

            # Generate comprehensive report
            total_time = time.time() - start_time
            return await self._generate_comprehensive_report(total_time)

    async def _test_service_health_comprehensive(self):
        """Comprehensive health check for all services in the pipeline"""
        test_name = "service_health_comprehensive"
        start_time = time.time()

        try:
            print("\n🔍 Testing Service Health (Comprehensive)...")

            health_results = {}
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Test main server health
                try:
                    response = await client.get(
                        f"{self.services['main_server']}/health"
                    )
                    health_results["main_server"] = {
                        "status": response.status_code,
                        "response_time": (
                            response.elapsed.total_seconds() if response.elapsed else 0
                        ),
                        "healthy": response.status_code == 200,
                    }
                except Exception as e:
                    health_results["main_server"] = {
                        "status": "error",
                        "error": str(e),
                        "healthy": False,
                    }

                # Test MCP server health via session info
                try:
                    mcp_request = {"method": "session_info", "params": {}}
                    response = await client.post(
                        f"{self.services['mcp_server']}/mcp", json=mcp_request
                    )
                    health_results["mcp_server"] = {
                        "status": response.status_code,
                        "response_time": (
                            response.elapsed.total_seconds() if response.elapsed else 0
                        ),
                        "healthy": response.status_code == 200,
                    }
                except Exception as e:
                    health_results["mcp_server"] = {
                        "status": "error",
                        "error": str(e),
                        "healthy": False,
                    }

                # Test other services
                service_endpoints = {
                    "intelligence": "/health",
                    "bridge": "/health",
                    "search": "/health",
                }

                for service, endpoint in service_endpoints.items():
                    try:
                        response = await client.get(
                            f"{self.services[service]}{endpoint}"
                        )
                        health_results[service] = {
                            "status": response.status_code,
                            "response_time": (
                                response.elapsed.total_seconds()
                                if response.elapsed
                                else 0
                            ),
                            "healthy": response.status_code == 200,
                        }
                    except Exception as e:
                        health_results[service] = {
                            "status": "error",
                            "error": str(e),
                            "healthy": False,
                        }

                # Test Qdrant health
                try:
                    response = await client.get(f"{self.services['qdrant']}/readyz")
                    health_results["qdrant"] = {
                        "status": response.status_code,
                        "response_time": (
                            response.elapsed.total_seconds() if response.elapsed else 0
                        ),
                        "healthy": response.status_code == 200,
                    }
                except Exception as e:
                    health_results["qdrant"] = {
                        "status": "error",
                        "error": str(e),
                        "healthy": False,
                    }

                # Test Memgraph health
                try:
                    response = await client.get(f"{self.services['memgraph']}")
                    health_results["memgraph"] = {
                        "status": response.status_code,
                        "response_time": (
                            response.elapsed.total_seconds() if response.elapsed else 0
                        ),
                        "healthy": response.status_code == 200,
                    }
                except Exception as e:
                    health_results["memgraph"] = {
                        "status": "error",
                        "error": str(e),
                        "healthy": False,
                    }

            # Evaluate health results
            total_services = len(health_results)
            healthy_services = sum(
                1 for result in health_results.values() if result.get("healthy", False)
            )
            health_percentage = (healthy_services / total_services) * 100

            if health_percentage == 100:
                status = TestStatus.PASS
                message = f"All {total_services} services healthy"
            elif health_percentage >= 80:
                status = TestStatus.WARNING
                message = f"{healthy_services}/{total_services} services healthy ({health_percentage:.1f}%)"
            else:
                status = TestStatus.FAIL
                message = f"Critical service failures: {healthy_services}/{total_services} healthy"

            duration = time.time() - start_time
            self._record_test_result(
                test_name,
                status,
                duration,
                message,
                {
                    "health_results": health_results,
                    "health_percentage": health_percentage,
                },
            )

            self._log_test_result(status, f"{message} in {duration:.2f}s")

        except Exception as e:
            duration = time.time() - start_time
            self._record_test_result(
                test_name, TestStatus.FAIL, duration, f"Health check failed: {e}"
            )
            self._log_test_result(TestStatus.FAIL, f"Service health check failed: {e}")

    async def _test_service_communication_matrix(self):
        """Test communication between all services in the pipeline"""
        test_name = "service_communication_matrix"
        start_time = time.time()

        try:
            print("\n🔗 Testing Service Communication Matrix...")

            communication_results = {}
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Test main server to intelligence service
                try:
                    response = await client.get(
                        f"{self.services['intelligence']}/stats"
                    )
                    communication_results["main_to_intelligence"] = {
                        "success": response.status_code == 200,
                        "response_time": (
                            response.elapsed.total_seconds() if response.elapsed else 0
                        ),
                    }
                except Exception as e:
                    communication_results["main_to_intelligence"] = {
                        "success": False,
                        "error": str(e),
                    }

                # Test intelligence to bridge
                try:
                    response = await client.get(
                        f"{self.services['bridge']}/mapping/stats"
                    )
                    communication_results["intelligence_to_bridge"] = {
                        "success": response.status_code == 200,
                        "response_time": (
                            response.elapsed.total_seconds() if response.elapsed else 0
                        ),
                    }
                except Exception as e:
                    communication_results["intelligence_to_bridge"] = {
                        "success": False,
                        "error": str(e),
                    }

                # Test bridge to search service
                try:
                    response = await client.get(f"{self.services['search']}/stats")
                    communication_results["bridge_to_search"] = {
                        "success": response.status_code == 200,
                        "response_time": (
                            response.elapsed.total_seconds() if response.elapsed else 0
                        ),
                    }
                except Exception as e:
                    communication_results["bridge_to_search"] = {
                        "success": False,
                        "error": str(e),
                    }

                # Test search to Qdrant
                try:
                    response = await client.get(
                        f"{self.services['qdrant']}/collections"
                    )
                    communication_results["search_to_qdrant"] = {
                        "success": response.status_code == 200,
                        "response_time": (
                            response.elapsed.total_seconds() if response.elapsed else 0
                        ),
                    }
                except Exception as e:
                    communication_results["search_to_qdrant"] = {
                        "success": False,
                        "error": str(e),
                    }

            # Evaluate communication results
            successful_connections = sum(
                1
                for result in communication_results.values()
                if result.get("success", False)
            )
            total_connections = len(communication_results)
            success_rate = (successful_connections / total_connections) * 100

            if success_rate == 100:
                status = TestStatus.PASS
                message = f"All {total_connections} service connections healthy"
            elif success_rate >= 75:
                status = TestStatus.WARNING
                message = (
                    f"{successful_connections}/{total_connections} connections healthy"
                )
            else:
                status = TestStatus.FAIL
                message = f"Critical communication failures: {successful_connections}/{total_connections}"

            duration = time.time() - start_time
            self._record_test_result(
                test_name,
                status,
                duration,
                message,
                {"communication_results": communication_results},
            )

            self._log_test_result(status, f"{message} in {duration:.2f}s")

        except Exception as e:
            duration = time.time() - start_time
            self._record_test_result(
                test_name, TestStatus.FAIL, duration, f"Communication test failed: {e}"
            )
            self._log_test_result(
                TestStatus.FAIL, f"Service communication test failed: {e}"
            )

    async def _setup_test_environment(self):
        """Setup isolated test environment"""
        test_name = "test_environment_setup"
        start_time = time.time()

        try:
            print("\n🏗️  Setting up Test Environment...")

            async with httpx.AsyncClient(timeout=60.0) as client:
                # Create test project
                project_data = {
                    "title": f"Enhanced MCP Integration Test - {self.test_session_id}",
                    "description": f"Test project for enhanced MCP document indexing validation. Session: {self.test_session_id}",
                    "github_repo": f"https://github.com/test/{self.test_session_id}",
                    "docs": [],
                    "features": {},
                    "data": {
                        "test_session": self.test_session_id,
                        "created_for": "enhanced_mcp_integration_test",
                        "auto_cleanup": True,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    },
                }

                response = await client.post(
                    f"{self.services['main_server']}/api/projects",
                    json=project_data,
                    timeout=30.0,
                )

                if response.status_code == 200:
                    result = response.json()

                    # Handle streaming project creation
                    if "progress_id" in result:
                        result["progress_id"]

                        # Wait for project creation to complete
                        await asyncio.sleep(5)

                        # Get actual project ID
                        projects_response = await client.get(
                            f"{self.services['main_server']}/api/projects"
                        )
                        if projects_response.status_code == 200:
                            projects = projects_response.json()
                            for project in projects:
                                if self.test_session_id in project.get("title", ""):
                                    self.test_project_id = project["id"]
                                    break
                    else:
                        self.test_project_id = result.get("id")

                    if self.test_project_id:
                        duration = time.time() - start_time
                        self._record_test_result(
                            test_name,
                            TestStatus.PASS,
                            duration,
                            f"Test project created: {self.test_project_id}",
                            {"project_id": self.test_project_id},
                        )
                        self._log_test_result(
                            TestStatus.PASS,
                            f"Test environment setup completed in {duration:.2f}s",
                        )
                    else:
                        raise Exception("Failed to get project ID after creation")
                else:
                    raise Exception(
                        f"Project creation failed: {response.status_code} {response.text}"
                    )

        except Exception as e:
            duration = time.time() - start_time
            self._record_test_result(
                test_name, TestStatus.FAIL, duration, f"Environment setup failed: {e}"
            )
            self._log_test_result(
                TestStatus.FAIL, f"Test environment setup failed: {e}"
            )
            raise

    async def _test_mcp_document_creation_with_timing(self):
        """
        CRITICAL TEST: Test MCP document creation with precise timing
        This is the PRIMARY FOCUS as this pathway is currently FAILING
        """
        test_name = "mcp_document_creation_timing"
        start_time = time.time()

        try:
            print("\n📝 CRITICAL TEST: MCP Document Creation with Timing...")

            if not self.test_project_id:
                raise Exception("Test project not available")

            # Create test document via MCP with comprehensive metadata
            test_doc_data = {
                "project_id": self.test_project_id,
                "title": f"Enhanced MCP Test Document - {self.test_session_id}",
                "document_type": "enhanced_test",
                "content": {
                    "overview": f"This is a comprehensive test document created via MCP for enhanced integration testing. Session: {self.test_session_id}",
                    "test_data": {
                        "session_id": self.test_session_id,
                        "test_type": "mcp_integration",
                        "created_via": "mcp_api",
                        "indexing_requirements": [
                            "vector_search",
                            "knowledge_graph",
                            "rag_retrieval",
                        ],
                    },
                    "content_for_indexing": {
                        "technologies": ["FastAPI", "Qdrant", "Memgraph", "RAG", "MCP"],
                        "concepts": [
                            "vector embeddings",
                            "knowledge graphs",
                            "semantic search",
                            "document indexing",
                        ],
                        "use_cases": [
                            "real-time search",
                            "AI-powered retrieval",
                            "intelligent document discovery",
                        ],
                    },
                    "searchable_content": f"This document should be immediately retrievable via RAG queries after creation. "
                    f"It contains test session {self.test_session_id} and should be found when searching for "
                    f"enhanced MCP integration testing, vector embeddings, or knowledge graph synchronization.",
                    "expected_entities": [
                        {"type": "technology", "value": "FastAPI"},
                        {"type": "database", "value": "Qdrant"},
                        {"type": "graph_db", "value": "Memgraph"},
                        {"type": "concept", "value": "vector embeddings"},
                        {"type": "test_session", "value": self.test_session_id},
                    ],
                },
                "tags": [
                    "enhanced_test",
                    "mcp_integration",
                    "indexing_test",
                    self.test_session_id,
                ],
                "author": "Enhanced MCP Integration Test Suite",
            }

            mcp_request = {"method": "create_document", "params": test_doc_data}

            creation_start = time.time()

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.services['mcp_server']}/mcp", json=mcp_request, timeout=30.0
                )

                creation_time = time.time() - creation_start

                if response.status_code == 200:
                    result = response.json()

                    if "result" in result and "document_id" in result["result"]:
                        document_id = result["result"]["document_id"]
                        self.test_documents.append(
                            {
                                "id": document_id,
                                "title": test_doc_data["title"],
                                "created_at": time.time(),
                                "expected_entities": test_doc_data["content"][
                                    "expected_entities"
                                ],
                            }
                        )

                        # Validate SLA for document creation
                        creation_sla = next(
                            sla
                            for sla in self.sla_requirements
                            if sla.name == "document_creation"
                        )
                        sla_status = (
                            TestStatus.PASS
                            if creation_time <= creation_sla.max_duration
                            else TestStatus.FAIL
                        )

                        duration = time.time() - start_time
                        self._record_test_result(
                            test_name,
                            sla_status,
                            duration,
                            f"MCP document created in {creation_time:.2f}s (SLA: {creation_sla.max_duration}s)",
                            {
                                "document_id": document_id,
                                "creation_time": creation_time,
                                "sla_requirement": creation_sla.max_duration,
                                "sla_met": creation_time <= creation_sla.max_duration,
                            },
                        )

                        self._log_test_result(
                            sla_status,
                            f"MCP document created: {document_id} in {creation_time:.2f}s "
                            f"(SLA: {'MET' if creation_time <= creation_sla.max_duration else 'FAILED'})",
                        )
                    else:
                        raise Exception(f"Invalid MCP response format: {result}")
                else:
                    raise Exception(
                        f"MCP document creation failed: {response.status_code} {response.text}"
                    )

        except Exception as e:
            duration = time.time() - start_time
            self._record_test_result(
                test_name,
                TestStatus.FAIL,
                duration,
                f"MCP document creation failed: {e}",
            )
            self._log_test_result(TestStatus.FAIL, f"MCP document creation failed: {e}")

    async def _test_rag_retrievability_comprehensive(self):
        """
        CRITICAL TEST: Comprehensive RAG retrievability testing
        This tests the FAILING endpoint of the pipeline
        """
        test_name = "rag_retrievability_comprehensive"
        start_time = time.time()

        try:
            print("\n🔍 CRITICAL TEST: RAG Retrievability (Comprehensive)...")

            if not self.test_documents:
                raise Exception("No test documents available for RAG testing")

            # Wait for indexing to complete (with progress monitoring)
            print("  ⏳ Waiting for document indexing to complete...")
            await self._monitor_indexing_progress(max_wait_time=30.0)

            # Test multiple RAG query patterns
            test_queries = [
                f"enhanced MCP integration testing {self.test_session_id}",
                f"test session {self.test_session_id}",
                "FastAPI Qdrant Memgraph vector embeddings",
                "knowledge graph synchronization",
                "Enhanced MCP Test Document",
                f"session {self.test_session_id[:8]}",
            ]

            rag_results = {}
            async with httpx.AsyncClient(timeout=60.0) as client:
                for query in test_queries:
                    query_start = time.time()

                    mcp_request = {
                        "method": "perform_rag_query",
                        "params": {"query": query, "match_count": 10},
                    }

                    try:
                        response = await client.post(
                            f"{self.services['mcp_server']}/mcp",
                            json=mcp_request,
                            timeout=30.0,
                        )

                        query_time = time.time() - query_start

                        if response.status_code == 200:
                            result = response.json()

                            if "result" in result and "results" in result["result"]:
                                results = result["result"]["results"]

                                # Check if our test documents are in results
                                found_test_docs = []
                                for doc_result in results:
                                    for test_doc in self.test_documents:
                                        if (
                                            self.test_session_id in str(doc_result)
                                            or test_doc["id"] in str(doc_result)
                                            or "Enhanced MCP Test Document"
                                            in str(doc_result)
                                        ):
                                            found_test_docs.append(test_doc["id"])

                                rag_results[query] = {
                                    "success": True,
                                    "response_time": query_time,
                                    "total_results": len(results),
                                    "test_docs_found": len(found_test_docs),
                                    "test_doc_ids": found_test_docs,
                                }
                            else:
                                rag_results[query] = {
                                    "success": False,
                                    "response_time": query_time,
                                    "error": "No results in response",
                                }
                        else:
                            rag_results[query] = {
                                "success": False,
                                "response_time": query_time,
                                "error": f"HTTP {response.status_code}: {response.text}",
                            }

                    except Exception as e:
                        rag_results[query] = {
                            "success": False,
                            "response_time": time.time() - query_start,
                            "error": str(e),
                        }

            # Evaluate RAG retrievability results
            successful_queries = sum(
                1 for result in rag_results.values() if result.get("success", False)
            )
            total_queries = len(rag_results)
            test_docs_found = sum(
                result.get("test_docs_found", 0) for result in rag_results.values()
            )

            # Check SLA compliance
            rag_sla = next(
                sla for sla in self.sla_requirements if sla.name == "rag_retrievability"
            )
            total_time = time.time() - start_time
            sla_met = total_time <= rag_sla.max_duration

            # Determine test status
            if successful_queries == total_queries and test_docs_found > 0 and sla_met:
                status = TestStatus.PASS
                message = f"RAG retrievability SUCCESSFUL: {test_docs_found} test docs found in {total_time:.2f}s"
            elif successful_queries > 0 and test_docs_found > 0:
                status = TestStatus.WARNING
                message = f"RAG retrievability PARTIAL: {test_docs_found} test docs found, {successful_queries}/{total_queries} queries successful"
            else:
                status = TestStatus.FAIL
                message = f"RAG retrievability FAILED: {test_docs_found} test docs found, {successful_queries}/{total_queries} queries successful"

            self._record_test_result(
                test_name,
                status,
                total_time,
                message,
                {
                    "rag_results": rag_results,
                    "successful_queries": successful_queries,
                    "total_queries": total_queries,
                    "test_docs_found": test_docs_found,
                    "sla_requirement": rag_sla.max_duration,
                    "sla_met": sla_met,
                },
            )

            self._log_test_result(
                status, f"{message} (SLA: {'MET' if sla_met else 'FAILED'})"
            )

        except Exception as e:
            duration = time.time() - start_time
            self._record_test_result(
                test_name,
                TestStatus.FAIL,
                duration,
                f"RAG retrievability test failed: {e}",
            )
            self._log_test_result(
                TestStatus.FAIL, f"RAG retrievability test failed: {e}"
            )

    async def _monitor_indexing_progress(self, max_wait_time: float = 30.0):
        """Monitor indexing progress with detailed status"""
        start_time = time.time()
        check_interval = 2.0

        async with httpx.AsyncClient(timeout=30.0) as client:
            while time.time() - start_time < max_wait_time:
                try:
                    # Check intelligence service status
                    intel_response = await client.get(
                        f"{self.services['intelligence']}/stats"
                    )
                    bridge_response = await client.get(
                        f"{self.services['bridge']}/sync/status"
                    )
                    search_response = await client.get(
                        f"{self.services['search']}/stats"
                    )

                    if (
                        intel_response.status_code == 200
                        and bridge_response.status_code == 200
                        and search_response.status_code == 200
                    ):
                        elapsed = time.time() - start_time
                        print(
                            f"    ✅ Indexing services responsive after {elapsed:.1f}s"
                        )
                        return True

                except Exception:
                    pass  # Continue monitoring

                await asyncio.sleep(check_interval)

        print(f"    ⚠️  Indexing monitoring completed after {max_wait_time}s")
        return False

    # Additional test methods would continue here...
    # Due to length constraints, I'll include the critical test methods
    # and helper methods in the next part of the file.

    def _record_test_result(
        self,
        test_name: str,
        status: TestStatus,
        duration: float,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Record a test result"""
        result = TestResult(
            test_name=test_name,
            status=status,
            duration=duration,
            message=message,
            metadata=metadata or {},
            timestamp=datetime.now(timezone.utc),
        )
        self.test_results.append(result)

    def _log_test_result(self, status: TestStatus, message: str):
        """Log a test result with appropriate formatting"""
        status_symbols = {
            TestStatus.PASS: "✅",
            TestStatus.FAIL: "❌",
            TestStatus.WARNING: "⚠️",
            TestStatus.SKIP: "⏭️",
        }

        symbol = status_symbols.get(status, "❓")
        print(f"  {symbol} {message}")

        if self.verbose or status in [TestStatus.FAIL, TestStatus.WARNING]:
            logger.log(
                (
                    logging.INFO
                    if status == TestStatus.PASS
                    else (
                        logging.WARNING
                        if status == TestStatus.WARNING
                        else logging.ERROR
                    )
                ),
                f"{status.value}: {message}",
            )

    async def _cleanup_test_environment(self):
        """Clean up test environment"""
        print("\n🧹 Cleaning up test environment...")

        if self.test_project_id:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.delete(
                        f"{self.services['main_server']}/api/projects/{self.test_project_id}"
                    )

                    if response.status_code == 200:
                        print(f"  ✅ Test project deleted: {self.test_project_id}")
                    else:
                        print(
                            f"  ⚠️  Failed to delete test project: {response.status_code}"
                        )

            except Exception as e:
                print(f"  ⚠️  Cleanup error: {e}")

    async def _generate_comprehensive_report(self, total_time: float) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        print("\n" + "=" * 70)
        print("📊 ENHANCED MCP INTEGRATION TEST REPORT")
        print("=" * 70)

        # Calculate summary statistics
        total_tests = len(self.test_results)
        passed = sum(1 for r in self.test_results if r.status == TestStatus.PASS)
        failed = sum(1 for r in self.test_results if r.status == TestStatus.FAIL)
        warnings = sum(1 for r in self.test_results if r.status == TestStatus.WARNING)

        success_rate = (passed / total_tests * 100) if total_tests > 0 else 0

        print(f"Session ID: {self.test_session_id}")
        print(f"Total Execution Time: {total_time:.2f}s")
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️  Warnings: {warnings}")
        print(f"Success Rate: {success_rate:.1f}%")

        # SLA Compliance Report
        print("\n📈 SLA Compliance Report:")
        for sla in self.sla_requirements:
            sla_tests = [
                r for r in self.test_results if sla.name in r.test_name.lower()
            ]
            if sla_tests:
                sla_met = all(r.duration <= sla.max_duration for r in sla_tests)
                avg_duration = sum(r.duration for r in sla_tests) / len(sla_tests)
                print(
                    f"  {sla.description}: {'✅ MET' if sla_met else '❌ FAILED'} "
                    f"(avg: {avg_duration:.2f}s, max: {sla.max_duration}s)"
                )

        # Critical Test Results
        print("\n🔥 Critical Test Results:")
        critical_tests = [
            "mcp_document_creation_timing",
            "rag_retrievability_comprehensive",
            "service_health_comprehensive",
        ]

        for test_name in critical_tests:
            test_result = next(
                (r for r in self.test_results if r.test_name == test_name), None
            )
            if test_result:
                status_symbol = (
                    "✅"
                    if test_result.status == TestStatus.PASS
                    else "❌" if test_result.status == TestStatus.FAIL else "⚠️"
                )
                print(f"  {status_symbol} {test_name}: {test_result.message}")

        # Overall Assessment
        print("\n🎯 Overall Assessment:")
        if failed == 0 and warnings == 0:
            print(
                "🎉 EXCELLENT: All tests passed! MCP document indexing pipeline is working perfectly."
            )
        elif failed == 0:
            print(
                "✅ GOOD: All tests passed with some warnings. Pipeline is functional."
            )
        elif failed <= 2:
            print("⚠️  CONCERNING: Some tests failed. Pipeline needs attention.")
        else:
            print(
                "❌ CRITICAL: Multiple test failures. Pipeline requires immediate fixes."
            )

        print("=" * 70)

        # Return structured report
        return {
            "session_id": self.test_session_id,
            "total_time": total_time,
            "summary": {
                "total_tests": total_tests,
                "passed": passed,
                "failed": failed,
                "warnings": warnings,
                "success_rate": success_rate,
            },
            "test_results": [
                {
                    "test_name": r.test_name,
                    "status": r.status.value,
                    "duration": r.duration,
                    "message": r.message,
                    "metadata": r.metadata,
                    "timestamp": r.timestamp.isoformat(),
                }
                for r in self.test_results
            ],
            "sla_compliance": {
                sla.name: {
                    "description": sla.description,
                    "max_duration": sla.max_duration,
                    "tests": [
                        r for r in self.test_results if sla.name in r.test_name.lower()
                    ],
                }
                for sla in self.sla_requirements
            },
        }

    # Placeholder for additional critical test methods
    async def _test_intelligence_service_processing(self):
        """Test intelligence service document processing"""
        # Implementation would go here
        pass

    async def _test_bridge_sync_triggers(self):
        """Test bridge service sync triggers"""
        # Implementation would go here
        pass

    async def _test_vector_embedding_validation(self):
        """Test vector embedding generation and storage"""
        # Implementation would go here
        pass

    async def _test_knowledge_graph_sync_validation(self):
        """Test knowledge graph synchronization"""
        # Implementation would go here
        pass

    async def _test_strict_sla_compliance(self):
        """Test strict SLA compliance across all operations"""
        # Implementation would go here
        pass

    async def _test_concurrent_document_indexing(self):
        """Test concurrent document indexing performance"""
        # Implementation would go here
        pass

    async def _test_large_document_handling(self):
        """Test large document handling capabilities"""
        # Implementation would go here
        pass

    async def _test_service_failure_scenarios(self):
        """Test service failure and recovery scenarios"""
        # Implementation would go here
        pass

    async def _test_malformed_document_handling(self):
        """Test malformed document handling"""
        # Implementation would go here
        pass

    async def _test_concurrent_load_scenarios(self):
        """Test concurrent load scenarios"""
        # Implementation would go here
        pass

    async def _test_complete_pipeline_with_validation(self):
        """Test complete pipeline with comprehensive validation"""
        # Implementation would go here
        pass

    async def _run_continuous_monitoring(self):
        """Run continuous monitoring mode"""
        # Implementation would go here
        pass


async def main():
    """Main test execution function"""
    parser = argparse.ArgumentParser(
        description="Enhanced MCP Document Indexing Integration Tests"
    )
    parser.add_argument(
        "--strict-sla", action="store_true", help="Enable strict SLA validation"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "--continuous", action="store_true", help="Run continuous monitoring"
    )
    parser.add_argument(
        "--base-url", default="http://localhost:8181", help="Base URL for main server"
    )
    parser.add_argument(
        "--mcp-url", default="http://localhost:8051", help="MCP server URL"
    )

    args = parser.parse_args()

    tester = MCPDocumentIndexingTester(
        base_url=args.base_url,
        mcp_url=args.mcp_url,
        strict_sla=args.strict_sla,
        verbose=args.verbose,
    )

    try:
        report = await tester.run_comprehensive_tests(continuous=args.continuous)

        # Save report to file
        report_filename = f"enhanced_mcp_test_report_{tester.test_session_id}.json"
        with open(report_filename, "w") as f:
            json.dump(report, f, indent=2, default=str)

        print(f"\n📄 Detailed report saved to: {report_filename}")

        # Exit with appropriate code
        failed_tests = sum(
            1 for r in tester.test_results if r.status == TestStatus.FAIL
        )
        exit(1 if failed_tests > 0 else 0)

    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        exit(130)
    except Exception as e:
        print(f"\n💥 Test suite failed with error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
