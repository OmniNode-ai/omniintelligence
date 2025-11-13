"""
MCP Service Client for HTTP-based microservice communication

This module provides HTTP clients for the MCP service to communicate with
other services (API and Agents) instead of importing their modules directly.
"""

import os
import uuid
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import httpx
from pydantic import ValidationError
from server.config.logfire_config import mcp_logger
from server.config.service_discovery import get_agents_url, get_api_url
from server.models.search_models import EnhancedSearchRequest, EnhancedSearchResponse


def serialize_datetime_objects(obj: Any) -> Any:
    """Recursively convert datetime objects to ISO format strings for JSON serialization."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_datetime_objects(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime_objects(item) for item in obj]
    else:
        return obj


def get_search_service_url() -> str:
    """Get the search service URL for enhanced search capabilities."""
    # Check for custom search service URL first
    if custom_url := os.getenv("SEARCH_SERVICE_URL"):
        return custom_url.rstrip("/")

    # Use service discovery pattern
    if discovery_mode := os.getenv("SERVICE_DISCOVERY_MODE"):
        if discovery_mode == "docker_compose":
            search_port = os.getenv("SEARCH_SERVICE_PORT", "8055")
            return f"http://archon-search:{search_port}"

    # Default fallback
    return "http://localhost:8055"


class MCPServiceClient:
    """
    Client for MCP service to communicate with other microservices via HTTP.
    Replaces direct module imports with proper service-to-service communication.
    """

    def __init__(self):
        self.api_url = get_api_url()
        self.agents_url = get_agents_url()
        self.search_url = get_search_service_url()
        # Use environment variable for service authentication token
        self.service_auth = os.getenv("SERVICE_AUTH_TOKEN", "mcp-service-key")
        self.timeout = httpx.Timeout(
            connect=5.0,
            read=300.0,  # 5 minutes for long operations like crawling
            write=30.0,
            pool=5.0,
        )

    def _get_headers(self, request_id: str | None = None) -> dict[str, str]:
        """Get common headers for internal requests"""
        headers = {
            "X-Service-Auth": self.service_auth,
            "Content-Type": "application/json",
        }
        if request_id:
            headers["X-Request-ID"] = request_id
        else:
            headers["X-Request-ID"] = str(uuid.uuid4())
        return headers

    async def crawl_url(
        self, url: str, options: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Crawl a URL by calling the API service's knowledge-items/crawl endpoint.
        Transforms MCP's simple format to the API's KnowledgeItemRequest format.

        Args:
            url: URL to crawl
            options: Crawling options (max_depth, chunk_size, smart_crawl)

        Returns:
            Crawl response with success status and results
        """
        endpoint = urljoin(self.api_url, "/api/knowledge-items/crawl")

        # Transform to API's expected format
        request_data = {
            "url": url,
            "knowledge_type": "documentation",  # Default type
            "tags": [],
            "update_frequency": 7,  # Default to weekly
            "metadata": options or {},
        }

        mcp_logger.info(f"Calling API service to crawl {url}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint, json=request_data, headers=self._get_headers()
                )
                response.raise_for_status()
                result = response.json()

                # Transform API response to MCP expected format
                return {
                    "success": result.get("success", False),
                    "progressId": result.get("progressId"),
                    "message": result.get("message", "Crawling started"),
                    "error": (
                        None if result.get("success") else {"message": "Crawl failed"}
                    ),
                }
        except httpx.TimeoutException:
            mcp_logger.error(f"Timeout crawling {url}")
            return {
                "success": False,
                "error": {"code": "TIMEOUT", "message": "Crawl operation timed out"},
            }
        except httpx.HTTPStatusError as e:
            mcp_logger.error(f"HTTP error crawling {url}: {e.response.status_code}")
            return {
                "success": False,
                "error": {"code": "HTTP_ERROR", "message": str(e)},
            }
        except Exception as e:
            mcp_logger.error(f"Error crawling {url}: {e!s}")
            return {
                "success": False,
                "error": {"code": "CRAWL_FAILED", "message": str(e)},
            }

    async def search(
        self,
        query: str,
        source_filter: str | None = None,
        match_count: int = 5,
        use_reranking: bool = False,
    ) -> dict[str, Any]:
        """
        Perform a search by calling the API service's rag/query endpoint.
        Transforms MCP's simple format to the API's RagQueryRequest format.

        Args:
            query: Search query
            source_filter: Optional source ID to filter results
            match_count: Number of results to return
            use_reranking: Whether to rerank results (handled in Server's service layer)

        Returns:
            Search response with results
        """
        endpoint = urljoin(self.api_url, "/api/rag/query")
        request_data = {
            "query": query,
            "source": source_filter,
            "match_count": match_count,
        }

        mcp_logger.info(f"Calling API service to search: {query}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # First, get search results from API service
                response = await client.post(
                    endpoint, json=request_data, headers=self._get_headers()
                )
                response.raise_for_status()
                result = response.json()

                # Transform API response to MCP expected format
                return {
                    "success": result.get("success", True),
                    "results": result.get("results", []),
                    "reranked": False,  # Reranking should be handled by Server's service layer
                    "error": None,
                }

        except Exception as e:
            mcp_logger.error(f"Error searching: {e!s}")
            return {
                "success": False,
                "results": [],
                "error": {"code": "SEARCH_FAILED", "message": str(e)},
            }

    # Removed _rerank_results method - reranking should be handled by Server's service layer

    async def store_documents(
        self, documents: list[dict[str, Any]], generate_embeddings: bool = True
    ) -> dict[str, Any]:
        """
        Store documents by transforming them into the format expected by the API.
        Note: The regular API expects file uploads, so this is a simplified version.

        Args:
            documents: List of documents to store
            generate_embeddings: Whether to generate embeddings

        Returns:
            Storage response
        """
        # For now, return a simplified response since document upload
        # through the regular API requires multipart form data
        mcp_logger.info("Document storage through regular API not yet implemented")
        return {
            "success": True,
            "documents_stored": len(documents),
            "chunks_created": len(documents),
            "message": "Document storage should be handled by Server's service layer",
        }

    async def generate_embeddings(
        self, texts: list[str], model: str = "text-embedding-3-small"
    ) -> dict[str, Any]:
        """
        Generate embeddings - this should be handled by Server's service layer.
        MCP tools shouldn't need to directly generate embeddings.

        Args:
            texts: List of texts to embed
            model: Embedding model to use

        Returns:
            Embeddings response
        """
        mcp_logger.warning("Direct embedding generation not needed for MCP tools")
        raise NotImplementedError(
            "Embeddings should be handled by Server's service layer"
        )

    # Removed analyze_document - document analysis should be handled by Agents via MCP tools

    async def health_check(self) -> dict[str, Any]:
        """
        Check health of all dependent services.

        Returns:
            Combined health status
        """
        health_status = {"api_service": False, "agents_service": False}

        # Check API service
        api_health_url = urljoin(self.api_url, "/api/health")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                mcp_logger.info(f"Checking API service health at: {api_health_url}")
                response = await client.get(api_health_url)
                health_status["api_service"] = response.status_code == 200
                mcp_logger.info(f"API service health check: {response.status_code}")
        except Exception as e:
            health_status["api_service"] = False
            mcp_logger.warning(f"API service health check failed: {e}")

        # Check Agents service
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(urljoin(self.agents_url, "/health"))
                health_status["agents_service"] = response.status_code == 200
        except Exception:
            pass

        return health_status

    async def get_sources(self) -> dict[str, Any]:
        """
        Get available sources in the knowledge base.

        Returns:
            Sources response with list of available sources
        """
        endpoint = urljoin(self.api_url, "/api/rag/sources")

        mcp_logger.info("Calling API service to get available sources")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(endpoint, headers=self._get_headers())
                response.raise_for_status()
                result = response.json()

                # Transform API response to consistent format
                return {
                    "success": True,
                    "sources": result.get("sources", []),
                    "count": len(result.get("sources", [])),
                    "error": None,
                }

        except Exception as e:
            mcp_logger.error(f"Error getting sources: {e!s}")
            return {
                "success": False,
                "sources": [],
                "count": 0,
                "error": {"code": "GET_SOURCES_FAILED", "message": str(e)},
            }

    async def search_code_examples(
        self,
        query: str,
        source_domain: str | None = None,
        match_count: int = 5,
    ) -> dict[str, Any]:
        """
        Search for code examples in the knowledge base.

        Args:
            query: Search query
            source_domain: Optional domain filter
            match_count: Number of results to return

        Returns:
            Code examples search response
        """
        endpoint = urljoin(self.api_url, "/api/rag/code-examples")
        request_data = {"query": query, "match_count": match_count}
        if source_domain:
            request_data["source"] = source_domain

        mcp_logger.info(f"Calling API service to search code examples: {query}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint, json=request_data, headers=self._get_headers()
                )
                response.raise_for_status()
                result = response.json()

                # Transform API response to consistent format
                return {
                    "success": True,
                    "results": result.get("results", []),
                    "reranked": result.get("reranked", False),
                    "error": None,
                }

        except Exception as e:
            mcp_logger.error(f"Error searching code examples: {e!s}")
            return {
                "success": False,
                "results": [],
                "error": {"code": "SEARCH_CODE_EXAMPLES_FAILED", "message": str(e)},
            }

    # === Enhanced Search Service Integration ===

    async def enhanced_search(
        self,
        query: str,
        mode: str = "hybrid",
        entity_types: list[str] | None = None,
        source_ids: list[str] | None = None,
        limit: int = 5,
        include_content: bool = False,
        include_relationships: bool = False,
    ) -> dict[str, Any]:
        """
        Perform enhanced search using the Phase 4 search service with Pydantic validation.

        Args:
            query: Search query text
            mode: Search mode - "semantic", "structural", "relational", or "hybrid"
            entity_types: Filter by entity types (source, page, code_example, project, entity)
            source_ids: Filter by specific source IDs
            limit: Maximum number of results
            include_content: Include full content in results
            include_relationships: Include entity relationships

        Returns:
            Enhanced search response with comprehensive results
        """
        endpoint = urljoin(self.search_url, "/search")

        # Use Pydantic model for request validation
        try:
            request_model = EnhancedSearchRequest(
                query=query,
                mode=mode,
                entity_types=entity_types,
                source_ids=source_ids,
                limit=limit,
                include_content=include_content,
                include_relationships=include_relationships,
            )
            request_data = request_model.dict(exclude_none=True)
        except ValidationError as e:
            mcp_logger.error(f"Invalid search request parameters: {e}")
            return {
                "success": False,
                "results": [],
                "error": {"code": "INVALID_REQUEST", "message": str(e)},
            }

        mcp_logger.info(f"Calling enhanced search service: {query} (mode: {mode})")
        mcp_logger.debug(f"Enhanced search URL: {endpoint}")
        mcp_logger.debug(f"Request headers: {self._get_headers()}")
        mcp_logger.debug(f"Request payload: {request_data}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint, json=request_data, headers=self._get_headers()
                )
                mcp_logger.debug(f"Response status: {response.status_code}")
                mcp_logger.debug(f"Response body: {response.text[:1000]}...")
                response.raise_for_status()

                # Parse response with Pydantic model
                raw_response = response.json()
                try:
                    enhanced_response = EnhancedSearchResponse(**raw_response)
                    mcp_logger.info(
                        f"Enhanced search returned {enhanced_response.returned_results} results"
                    )

                    # Transform to MCP-compatible format using the model
                    return {
                        "success": True,
                        "query": enhanced_response.query,
                        "mode": enhanced_response.mode.value,
                        "total_results": enhanced_response.total_results,
                        "returned_results": enhanced_response.returned_results,
                        "results": [
                            serialize_datetime_objects(result.dict())
                            for result in enhanced_response.results
                        ],
                        "search_time_ms": enhanced_response.search_time_ms,
                        "semantic_search_time_ms": enhanced_response.semantic_search_time_ms,
                        "graph_search_time_ms": enhanced_response.graph_search_time_ms,
                        "relational_search_time_ms": enhanced_response.relational_search_time_ms,
                        "entity_type_counts": enhanced_response.entity_type_counts,
                        "source_counts": enhanced_response.source_counts,
                        "offset": enhanced_response.offset,
                        "limit": enhanced_response.limit,
                        "has_more": enhanced_response.has_more,
                        "error": None,
                    }

                except ValidationError as e:
                    mcp_logger.error(
                        f"Invalid response format from search service: {e}"
                    )
                    mcp_logger.error(f"Raw response: {raw_response}")
                    return {
                        "success": False,
                        "results": [],
                        "error": {
                            "code": "INVALID_RESPONSE",
                            "message": f"Response validation failed: {e!s}",
                        },
                    }

        except httpx.HTTPStatusError as e:
            mcp_logger.error(f"HTTP error in enhanced search: {e.response.status_code}")
            try:
                error_body = e.response.json()
                mcp_logger.error(f"Error response body: {error_body}")
            except Exception as json_err:
                mcp_logger.debug(f"Could not parse error response as JSON: {json_err}")
                mcp_logger.error(f"Error response text: {e.response.text}")
            return {
                "success": False,
                "results": [],
                "error": {"code": "HTTP_ERROR", "message": str(e)},
            }
        except Exception as e:
            mcp_logger.error(f"Error in enhanced search: {e!s}")
            return {
                "success": False,
                "results": [],
                "error": {"code": "ENHANCED_SEARCH_FAILED", "message": str(e)},
            }

    async def search_similar_entities(
        self,
        entity_id: str,
        limit: int = 10,
        threshold: float = 0.7,
    ) -> dict[str, Any]:
        """
        Find entities similar to a given entity using vector similarity.

        Args:
            entity_id: ID of the reference entity
            limit: Maximum similar entities to return
            threshold: Minimum similarity threshold (0.0-1.0)

        Returns:
            Similar entities response
        """
        endpoint = urljoin(self.search_url, f"/search/similar/{entity_id}")
        params = {"limit": limit, "threshold": threshold}

        mcp_logger.info(f"Finding similar entities to: {entity_id}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    endpoint, params=params, headers=self._get_headers()
                )
                response.raise_for_status()
                result = response.json()

                return {
                    "success": True,
                    "entity_id": result.get("entity_id"),
                    "similar_entities": result.get("similar_entities", []),
                    "count": result.get("count", 0),
                    "error": None,
                }

        except Exception as e:
            mcp_logger.error(f"Error finding similar entities: {e!s}")
            return {
                "success": False,
                "similar_entities": [],
                "error": {"code": "SIMILAR_SEARCH_FAILED", "message": str(e)},
            }

    async def search_entity_relationships(
        self,
        entity_id: str,
        relationship_types: list[str] | None = None,
        max_depth: int = 3,
    ) -> dict[str, Any]:
        """
        Search for entity relationships using graph traversal.

        Args:
            entity_id: Source entity ID
            relationship_types: Filter by relationship types
            max_depth: Maximum traversal depth

        Returns:
            Entity relationships response
        """
        endpoint = urljoin(self.search_url, "/search/relationships")
        request_data = {
            "entity_id": entity_id,
            "max_depth": max_depth,
            "include_paths": True,
        }

        if relationship_types:
            request_data["relationship_types"] = relationship_types

        mcp_logger.info(f"Searching relationships for entity: {entity_id}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint, json=request_data, headers=self._get_headers()
                )
                response.raise_for_status()
                result = response.json()

                return {
                    "success": True,
                    "source_entity_id": result.get("source_entity_id"),
                    "relationships": result.get("relationships", []),
                    "paths": result.get("paths", []),
                    "search_time_ms": result.get("search_time_ms"),
                    "error": None,
                }

        except Exception as e:
            mcp_logger.error(f"Error searching relationships: {e!s}")
            return {
                "success": False,
                "relationships": [],
                "error": {"code": "RELATIONSHIP_SEARCH_FAILED", "message": str(e)},
            }

    async def get_search_stats(self) -> dict[str, Any]:
        """
        Get search service statistics and performance metrics.

        Returns:
            Search service statistics
        """
        endpoint = urljoin(self.search_url, "/search/stats")

        mcp_logger.info("Getting search service statistics")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(endpoint, headers=self._get_headers())
                response.raise_for_status()
                result = response.json()

                return {
                    "success": True,
                    "service_status": result.get("service_status"),
                    "vector_index": result.get("vector_index", {}),
                    "component_health": result.get("component_health", {}),
                    "search_capabilities": result.get("search_capabilities", {}),
                    "error": None,
                }

        except Exception as e:
            mcp_logger.error(f"Error getting search stats: {e!s}")
            return {
                "success": False,
                "error": {"code": "SEARCH_STATS_FAILED", "message": str(e)},
            }

    async def get_projects(self) -> dict[str, Any]:
        """
        Get all projects from the API service.

        Returns:
            Dictionary containing success status and projects list
        """
        endpoint = urljoin(self.api_url, "/api/projects")

        mcp_logger.info("Getting all projects")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(endpoint, headers=self._get_headers())
                response.raise_for_status()
                result = response.json()

                return {
                    "success": True,
                    "projects": result,
                    "error": None,
                }

        except Exception as e:
            mcp_logger.error(f"Error getting projects: {e!s}")
            return {
                "success": False,
                "projects": [],
                "error": {"code": "GET_PROJECTS_FAILED", "message": str(e)},
            }

    async def get_project_documents(self, project_id: str) -> dict[str, Any]:
        """
        Get all documents for a specific project from the API service.

        Args:
            project_id: UUID of the project

        Returns:
            Dictionary containing success status and documents list
        """
        endpoint = urljoin(self.api_url, f"/api/projects/{project_id}/documents")

        mcp_logger.info(f"Getting documents for project {project_id}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(endpoint, headers=self._get_headers())
                response.raise_for_status()
                result = response.json()

                return {
                    "success": True,
                    "documents": result,
                    "error": None,
                }

        except Exception as e:
            mcp_logger.error(f"Error getting project documents: {e!s}")
            return {
                "success": False,
                "documents": [],
                "error": {"code": "GET_PROJECT_DOCUMENTS_FAILED", "message": str(e)},
            }


# Global client instance
_mcp_client = None


def get_mcp_service_client() -> MCPServiceClient:
    """Get or create the global MCP service client"""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPServiceClient()
    return _mcp_client
