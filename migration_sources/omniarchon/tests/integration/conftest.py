#!/usr/bin/env python3
"""
Shared test fixtures and configuration for Archon Integration Tests

This module provides comprehensive fixtures for testing the MCP document indexing pipeline
with proper setup, teardown, and resource management across all test scenarios.
"""

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
import pytest
import pytest_asyncio

# Configure logging for tests
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class ServiceUrls:
    """Service URL configuration for tests"""

    main_server: str = os.getenv("ARCHON_SERVER_URL", "http://localhost:8181")
    mcp_server: str = os.getenv("MCP_SERVER_URL", "http://localhost:8051")
    intelligence: str = os.getenv("INTELLIGENCE_URL", "http://localhost:8053")
    bridge: str = os.getenv("BRIDGE_URL", "http://localhost:8054")
    search: str = os.getenv("SEARCH_URL", "http://localhost:8055")
    qdrant: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    memgraph: str = os.getenv("MEMGRAPH_URL", "http://localhost:7444")


@dataclass
class TestProject:
    """Test project data structure"""

    id: str
    title: str
    session_id: str
    created_at: datetime
    documents: List[Dict[str, Any]] = field(default_factory=list)
    cleanup_required: bool = True


@dataclass
class TestDocument:
    """Test document data structure"""

    id: str
    project_id: str
    title: str
    content: Dict[str, Any]
    tags: List[str]
    created_at: datetime
    indexed_at: Optional[datetime] = None
    rag_retrievable: bool = False


@dataclass
class TestSession:
    """Complete test session state"""

    session_id: str
    services: ServiceUrls
    projects: List[TestProject] = field(default_factory=list)
    documents: List[TestDocument] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def get_unique_identifier(self) -> str:
        """Get unique identifier for this test session"""
        return f"{self.session_id}_{int(time.time())}"


class IntegrationTestClient:
    """
    Comprehensive test client for Archon integration testing

    Provides high-level methods for testing the complete MCP document indexing pipeline
    with proper error handling, timing, and validation.
    """

    def __init__(self, session: TestSession):
        self.session = session
        self.http_client = httpx.AsyncClient(timeout=60.0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http_client.aclose()

    async def check_service_health(self) -> Dict[str, bool]:
        """Check health of all services"""
        logger.info("Checking service health...")

        health_results = {}

        # Main server health
        try:
            response = await self.http_client.get(
                f"{self.session.services.main_server}/health"
            )
            health_results["main_server"] = response.status_code == 200
        except Exception as e:
            logger.warning(f"Main server health check failed: {e}")
            health_results["main_server"] = False

        # MCP server health (via session info)
        try:
            mcp_request = {
                "jsonrpc": "2.0",
                "id": "health-check",
                "method": "session_info",
                "params": {},
            }
            response = await self.http_client.post(
                f"{self.session.services.mcp_server}/mcp",
                json=mcp_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )
            health_results["mcp_server"] = response.status_code == 200
        except Exception as e:
            logger.warning(f"MCP server health check failed: {e}")
            health_results["mcp_server"] = False

        # Other services
        services = [
            ("intelligence", "/health"),
            ("bridge", "/health"),
            ("search", "/health"),
        ]

        for service_name, endpoint in services:
            try:
                service_url = getattr(self.session.services, service_name)
                response = await self.http_client.get(f"{service_url}{endpoint}")
                health_results[service_name] = response.status_code == 200
            except Exception as e:
                logger.warning(f"{service_name} health check failed: {e}")
                health_results[service_name] = False

        # Qdrant health
        try:
            response = await self.http_client.get(
                f"{self.session.services.qdrant}/readyz"
            )
            health_results["qdrant"] = response.status_code == 200
        except Exception as e:
            logger.warning(f"Qdrant health check failed: {e}")
            health_results["qdrant"] = False

        # Memgraph health
        try:
            response = await self.http_client.get(f"{self.session.services.memgraph}")
            health_results["memgraph"] = response.status_code == 200
        except Exception as e:
            logger.warning(f"Memgraph health check failed: {e}")
            health_results["memgraph"] = False

        healthy_count = sum(health_results.values())
        total_count = len(health_results)
        logger.info(
            f"Service health check: {healthy_count}/{total_count} services healthy"
        )

        return health_results

    async def create_test_project(
        self, project_title: Optional[str] = None
    ) -> TestProject:
        """Create a test project for integration testing"""
        unique_id = self.session.get_unique_identifier()

        project_data = {
            "title": project_title or f"Integration Test Project {unique_id}",
            "description": f"Integration test project for session {self.session.session_id}",
            "github_repo": f"https://github.com/integration-test/{unique_id}",
            "data": {
                "test_session": self.session.session_id,
                "test_type": "integration",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "auto_cleanup": True,
            },
        }

        logger.info(f"Creating test project: {project_data['title']}")

        response = await self.http_client.post(
            f"{self.session.services.main_server}/api/projects",
            json=project_data,
            timeout=30.0,
        )

        if response.status_code != 200:
            raise Exception(
                f"Failed to create test project: {response.status_code} {response.text}"
            )

        result = response.json()

        # Handle streaming project creation
        project_id = None
        if "progress_id" in result:
            # Wait for project creation to complete
            await asyncio.sleep(5)
            projects_response = await self.http_client.get(
                f"{self.session.services.main_server}/api/projects"
            )
            if projects_response.status_code == 200:
                projects = projects_response.json()
                for project in projects:
                    if unique_id in project.get("title", ""):
                        project_id = project["id"]
                        break
        else:
            project_id = result.get("id")

        if not project_id:
            raise Exception("Failed to get project ID after creation")

        test_project = TestProject(
            id=project_id,
            title=project_data["title"],
            session_id=self.session.session_id,
            created_at=datetime.now(timezone.utc),
        )

        self.session.projects.append(test_project)
        logger.info(f"Test project created successfully: {project_id}")

        return test_project

    async def create_test_document(
        self,
        project: TestProject,
        document_title: Optional[str] = None,
        content_override: Optional[Dict[str, Any]] = None,
    ) -> TestDocument:
        """Create a test document via MCP API"""
        unique_id = self.session.get_unique_identifier()

        default_content = {
            "overview": f"Integration test document created for session {self.session.session_id}",
            "test_metadata": {
                "session_id": self.session.session_id,
                "project_id": project.id,
                "unique_identifier": unique_id,
                "test_type": "integration_document",
                "created_for": "mcp_pipeline_testing",
            },
            "searchable_content": f"This document should be retrievable via RAG queries. "
            f"Session identifier: {self.session.session_id}. "
            f"Unique identifier: {unique_id}. "
            f"Integration testing keywords: MCP, document indexing, "
            f"vector embeddings, knowledge graphs, semantic search.",
            "expected_entities": [
                {"type": "session", "value": self.session.session_id},
                {"type": "test_id", "value": unique_id},
                {"type": "technology", "value": "MCP"},
                {"type": "process", "value": "document indexing"},
            ],
        }

        if content_override:
            default_content.update(content_override)

        document_data = {
            "project_id": project.id,
            "title": document_title or f"Test Document {unique_id}",
            "document_type": "integration_test",
            "content": default_content,
            "tags": ["integration_test", "mcp_pipeline", self.session.session_id],
            "author": "Integration Test Suite",
        }

        mcp_request = {
            "jsonrpc": "2.0",
            "id": f"create-doc-{int(time.time())}",
            "method": "create_document",
            "params": document_data,
        }

        logger.info(f"Creating test document via MCP: {document_data['title']}")

        response = await self.http_client.post(
            f"{self.session.services.mcp_server}/mcp",
            json=mcp_request,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            timeout=30.0,
        )

        if response.status_code != 200:
            raise Exception(
                f"MCP document creation failed: {response.status_code} {response.text}"
            )

        result = response.json()

        if "result" not in result or "document_id" not in result["result"]:
            raise Exception(f"Invalid MCP response format: {result}")

        document_id = result["result"]["document_id"]

        test_document = TestDocument(
            id=document_id,
            project_id=project.id,
            title=document_data["title"],
            content=document_data["content"],
            tags=document_data["tags"],
            created_at=datetime.now(timezone.utc),
        )

        self.session.documents.append(test_document)
        project.documents.append(test_document.__dict__)

        logger.info(f"Test document created successfully: {document_id}")

        return test_document

    async def wait_for_indexing(
        self, document: TestDocument, max_wait_seconds: float = 30.0
    ) -> bool:
        """Wait for document to be indexed and available in the search pipeline"""
        logger.info(f"Waiting for document indexing: {document.id}")

        start_time = time.time()
        check_interval = 2.0

        while time.time() - start_time < max_wait_seconds:
            try:
                # Check if document is available in search results
                search_request = {
                    "query": f"session {self.session.session_id} {document.id}",
                    "mode": "semantic",
                    "limit": 10,
                    "include_content": True,
                }

                response = await self.http_client.post(
                    f"{self.session.services.search}/search",
                    json=search_request,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    results = response.json()

                    # Check if our document appears in results
                    for result in results.get("results", []):
                        if (
                            document.id in str(result)
                            or self.session.session_id in str(result)
                            or document.title in str(result)
                        ):
                            elapsed = time.time() - start_time
                            document.indexed_at = datetime.now(timezone.utc)
                            logger.info(
                                f"Document indexed successfully after {elapsed:.1f}s"
                            )
                            return True

            except Exception as e:
                logger.warning(f"Error checking indexing status: {e}")

            await asyncio.sleep(check_interval)

        elapsed = time.time() - start_time
        logger.warning(f"Document indexing timeout after {elapsed:.1f}s")
        return False

    async def test_rag_retrievability(self, document: TestDocument) -> bool:
        """Test if document is retrievable via RAG queries"""
        logger.info(f"Testing RAG retrievability for document: {document.id}")

        test_queries = [
            f"session {self.session.session_id}",
            f"document {document.id}",
            f"{document.title}",
            f"integration test {self.session.session_id}",
            "MCP document indexing vector embeddings",
        ]

        for query in test_queries:
            try:
                mcp_request = {
                    "jsonrpc": "2.0",
                    "id": f"rag-query-{int(time.time())}",
                    "method": "perform_rag_query",
                    "params": {"query": query, "match_count": 10},
                }

                response = await self.http_client.post(
                    f"{self.session.services.mcp_server}/mcp",
                    json=mcp_request,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream",
                    },
                    timeout=10.0,
                )

                if response.status_code == 200:
                    result = response.json()

                    if "result" in result and "results" in result["result"]:
                        results = result["result"]["results"]

                        # Check if our document is in results
                        for doc_result in results:
                            if (
                                document.id in str(doc_result)
                                or self.session.session_id in str(doc_result)
                                or document.title in str(doc_result)
                            ):
                                document.rag_retrievable = True
                                logger.info(f"Document found via RAG query: '{query}'")
                                return True

            except Exception as e:
                logger.warning(f"RAG query failed for '{query}': {e}")

        logger.warning(f"Document not retrievable via RAG queries: {document.id}")
        return False

    async def cleanup_test_data(self):
        """Clean up all test data created during the session"""
        logger.info(f"Cleaning up test data for session: {self.session.session_id}")

        # Clean up projects (and their documents)
        for project in self.session.projects:
            if project.cleanup_required:
                try:
                    response = await self.http_client.delete(
                        f"{self.session.services.main_server}/api/projects/{project.id}"
                    )

                    if response.status_code == 200:
                        logger.info(f"Test project cleaned up: {project.id}")
                    else:
                        logger.warning(
                            f"Failed to cleanup project {project.id}: {response.status_code}"
                        )

                except Exception as e:
                    logger.warning(f"Error cleaning up project {project.id}: {e}")

        logger.info("Test data cleanup completed")

    # Intelligence Lifecycle Testing Methods

    async def create_document(
        self,
        project_id: str,
        title: str,
        document_type: str,
        content: Dict[str, Any],
        tags: List[str] = None,
    ) -> Dict[str, Any]:
        """Create document via MCP API"""
        mcp_request = {
            "jsonrpc": "2.0",
            "id": f"create-document-{int(time.time())}",
            "method": "create_document",
            "params": {
                "project_id": project_id,
                "title": title,
                "document_type": document_type,
                "content": content,
                "tags": tags or [],
            },
        }

        response = await self.http_client.post(
            f"{self.session.services.mcp_server}/mcp",
            json=mcp_request,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            timeout=30.0,
        )

        if response.status_code != 200:
            raise Exception(
                f"Document creation failed: {response.status_code} {response.text}"
            )

        return response.json()

    async def perform_rag_query(
        self, query: str, match_count: int = 5, context: str = "general"
    ) -> Dict[str, Any]:
        """Perform RAG query via MCP API"""
        mcp_request = {
            "jsonrpc": "2.0",
            "id": "rag-query",
            "method": "perform_rag_query",
            "params": {"query": query, "match_count": match_count, "context": context},
        }

        response = await self.http_client.post(
            f"{self.session.services.mcp_server}/mcp",
            json=mcp_request,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            timeout=30.0,
        )

        if response.status_code != 200:
            raise Exception(f"RAG query failed: {response.status_code} {response.text}")

        return response.json()

    async def perform_vector_search(
        self, query: str, limit: int = 10
    ) -> Dict[str, Any]:
        """Perform vector search"""
        search_payload = {"query": query, "limit": limit}

        response = await self.http_client.post(
            f"{self.session.services.search}/api/vector_search",
            json=search_payload,
            timeout=15.0,
        )

        if response.status_code != 200:
            raise Exception(
                f"Vector search failed: {response.status_code} {response.text}"
            )

        return response.json()

    async def perform_orchestrated_rag_query(
        self, query: str, context: str = "general", match_count: int = 5
    ) -> Dict[str, Any]:
        """Perform orchestrated RAG query across all services via MCP API"""
        mcp_request = {
            "jsonrpc": "2.0",
            "id": "orchestrated-rag-query",
            "method": "perform_rag_query",
            "params": {"query": query, "context": context, "match_count": match_count},
        }

        response = await self.http_client.post(
            f"{self.session.services.mcp_server}/mcp",
            json=mcp_request,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            timeout=30.0,
        )

        if response.status_code != 200:
            raise Exception(
                f"Orchestrated RAG query failed: {response.status_code} {response.text}"
            )

        return response.json()

    async def check_indexing_service_health(self) -> Dict[str, Any]:
        """Check indexing service health"""
        try:
            response = await self.http_client.get(
                f"{self.session.services.main_server}/api/indexing/health", timeout=10.0
            )

            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "success": False,
                    "error": f"Health check failed: {response.status_code}",
                    "service_running": False,
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Health check error: {str(e)}",
                "service_running": False,
            }

    async def wait_for_document_indexing(
        self, query_term: str, timeout: float = 10.0
    ) -> bool:
        """Wait for document to be indexed and retrievable via RAG"""
        start_time = time.time()
        poll_interval = 1.0

        while (time.time() - start_time) < timeout:
            try:
                rag_response = await self.perform_rag_query(query_term, match_count=5)

                if rag_response.get("success") and rag_response.get("results"):
                    for result in rag_response["results"]:
                        if query_term in result.get("content", ""):
                            return True

            except Exception as e:
                logger.debug(f"RAG query attempt failed: {e}")

            await asyncio.sleep(poll_interval)

        return False


# Pytest Fixtures


# Session-scoped event loop required for session-scoped async fixtures
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def service_urls() -> ServiceUrls:
    """Service URLs configuration fixture"""
    return ServiceUrls()


@pytest_asyncio.fixture(scope="session")
async def test_session(service_urls: ServiceUrls) -> AsyncGenerator[TestSession, None]:
    """Create and manage test session state"""
    session_id = f"test_{uuid.uuid4().hex[:8]}_{int(time.time())}"

    session = TestSession(session_id=session_id, services=service_urls)

    logger.info(f"Starting test session: {session_id}")

    yield session

    # Cleanup is handled by individual test clients
    logger.info(f"Completed test session: {session_id}")


@pytest_asyncio.fixture
async def test_client(
    test_session: TestSession,
) -> AsyncGenerator[IntegrationTestClient, None]:
    """Create integration test client with automatic cleanup"""
    async with IntegrationTestClient(test_session) as client:
        # Verify services are healthy before running tests
        health_status = await client.check_service_health()

        unhealthy_services = [
            service for service, healthy in health_status.items() if not healthy
        ]
        if unhealthy_services:
            pytest.skip(f"Unhealthy services detected: {unhealthy_services}")

        yield client

        # Cleanup test data after each test
        await client.cleanup_test_data()


@pytest_asyncio.fixture
async def test_project(test_client: IntegrationTestClient) -> TestProject:
    """Create a test project for individual tests"""
    return await test_client.create_test_project()


@pytest_asyncio.fixture
async def test_document(
    test_client: IntegrationTestClient, test_project: TestProject
) -> TestDocument:
    """Create a test document for individual tests"""
    return await test_client.create_test_document(test_project)


# Performance testing fixtures


@pytest.fixture
def performance_thresholds() -> Dict[str, float]:
    """Performance threshold configuration"""
    return {
        "document_creation": 5.0,  # seconds
        "indexing_completion": 30.0,  # seconds
        "rag_query": 2.0,  # seconds
        "vector_search": 1.0,  # seconds
        "complete_pipeline": 30.0,  # seconds
        # Intelligence lifecycle specific thresholds
        "indexing_timeout": 15.0,  # seconds
        "total_lifecycle_time": 20.0,  # seconds
        "max_indexing_time": 10.0,  # seconds
        "single_doc_indexing": 5.0,  # seconds
        "batch_indexing": 15.0,  # seconds
        "large_doc_indexing": 10.0,  # seconds
    }


# Test data generators


@pytest.fixture
def sample_document_content() -> Dict[str, Any]:
    """Generate sample document content for testing"""
    return {
        "title": "Sample Integration Test Document",
        "overview": "This is a comprehensive test document for integration testing",
        "sections": {
            "introduction": "Introduction to the test document",
            "main_content": "Main content with various keywords for testing search functionality",
            "conclusion": "Conclusion of the test document",
        },
        "metadata": {
            "author": "Integration Test Suite",
            "category": "testing",
            "tags": ["integration", "test", "mcp", "indexing"],
        },
        "searchable_keywords": [
            "integration testing",
            "document indexing",
            "vector embeddings",
            "semantic search",
            "knowledge graphs",
            "MCP protocol",
            "RAG queries",
        ],
    }


# Markers for test categorization


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line("markers", "critical: Critical path tests that must pass")
    config.addinivalue_line("markers", "happy_path: Happy path integration tests")
    config.addinivalue_line(
        "markers", "error_handling: Error handling and edge case tests"
    )
    config.addinivalue_line("markers", "performance: Performance and load tests")
    config.addinivalue_line("markers", "sla: SLA compliance tests")
    config.addinivalue_line(
        "markers", "data_consistency: Data consistency validation tests"
    )
    config.addinivalue_line("markers", "smoke: Basic smoke tests")
    config.addinivalue_line("markers", "slow: Tests that take more than 10 seconds")


# Custom test collection hooks


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test names"""
    for item in items:
        # Add markers based on test file and function names
        if "test_happy_path" in item.nodeid:
            item.add_marker(pytest.mark.happy_path)
            item.add_marker(pytest.mark.critical)

        if "test_error" in item.nodeid or "test_failure" in item.nodeid:
            item.add_marker(pytest.mark.error_handling)

        if "test_performance" in item.nodeid or "test_sla" in item.nodeid:
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)

        if "test_smoke" in item.nodeid:
            item.add_marker(pytest.mark.smoke)

        if "test_consistency" in item.nodeid:
            item.add_marker(pytest.mark.data_consistency)


# Memgraph connection fixture


@pytest.fixture(scope="module")
def memgraph_uri():
    """
    Auto-detect Docker vs host context for Memgraph connection.

    Returns:
        str: Memgraph Bolt URI appropriate for execution context

    Context Detection:
        - Docker: Uses internal hostname 'memgraph:7687'
        - Host: Uses localhost 'bolt://localhost:7687'
        - Environment override: Respects MEMGRAPH_URI if set
    """
    # Allow environment variable override
    env_uri = os.getenv("MEMGRAPH_URI")
    if env_uri:
        logger.info(f"Using Memgraph URI from environment: {env_uri}")
        return env_uri

    # Check if running inside Docker container
    in_docker = os.path.exists("/.dockerenv")

    if in_docker:
        uri = "bolt://memgraph:7687"
        logger.info(f"Detected Docker context, using internal hostname: {uri}")
    else:
        uri = "bolt://localhost:7687"
        logger.info(f"Detected host context, using localhost: {uri}")

    return uri


# Test reporting helpers


@pytest.fixture
def test_metadata(request) -> Dict[str, Any]:
    """Provide metadata about the current test"""
    return {
        "test_name": request.node.name,
        "test_file": request.node.fspath.basename,
        "test_markers": [marker.name for marker in request.node.iter_markers()],
        "start_time": datetime.now(timezone.utc),
    }
