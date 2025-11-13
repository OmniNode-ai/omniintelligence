"""
Tree Stamping Bridge - Core Integration Service

Orchestrates the complete pipeline for file location intelligence:
1. Intelligence Generation (Bridge) → Semantic analysis + quality scoring (inline content from Kafka)
2. Metadata Stamping (Stamping) → Metadata enrichment
3. Vector Indexing (Qdrant) → Semantic search
4. Graph Indexing (Memgraph) → Relationship mapping
5. Cache Warming (Valkey) → Fast lookups

ONEX Pattern: Orchestrator Node (Coordinates multiple services)
Performance Target: <5 minutes for 1000 files
Phase 0 (Filesystem Discovery) removed - inline content provided via Kafka messages
"""

import asyncio
import hashlib
import logging
import time
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

import httpx
from neo4j import AsyncGraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    PointStruct,
    Range,
    VectorParams,
)

# Initialize logger first
logger = logging.getLogger(__name__)

import os

# Import clients (absolute imports from project root)
import sys

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from python.src.mcp_server.clients.metadata_stamping_client import (
        MetadataStampingClient,
    )
    from python.src.server.services.llm_provider_service import (
        get_embedding_model,
        get_llm_client,
    )
except ImportError as e:
    # Fallback: Clients will be initialized via HTTP directly
    MetadataStampingClient = None  # type: ignore
    get_llm_client = None  # type: ignore
    get_embedding_model = None  # type: ignore
    logger.warning(
        f"Client imports failed - will use direct HTTP calls as fallback: {e}"
    )

# Import timeout configuration
from src.config.timeout_config import get_cache_timeout, get_http_timeout

# Import constants
from src.constants.memgraph_labels import MemgraphLabels

# Import models
from src.models.file_location import (
    FileMatch,
    FileSearchResult,
    ProjectIndexResult,
    ProjectIndexStatus,
)

# Import local services
# (Phase 0 removed - no local services needed)

# ==============================================================================
# Exceptions
# ==============================================================================


class TreeStampingBridgeError(Exception):
    """Base exception for TreeStampingBridge errors."""

    pass


class TreeDiscoveryError(TreeStampingBridgeError):
    """Raised when tree discovery fails."""

    pass


class IntelligenceGenerationError(TreeStampingBridgeError):
    """Raised when intelligence generation fails."""

    pass


class StampingError(TreeStampingBridgeError):
    """Raised when stamping fails."""

    pass


class IndexingError(TreeStampingBridgeError):
    """Raised when indexing fails."""

    pass


# ==============================================================================
# TreeStampingBridge - Main Integration Service
# ==============================================================================


class TreeStampingBridge:
    """
    Integration service that orchestrates the complete file location intelligence pipeline.

    Architecture:
    - Intelligence Generation: MetadataStampingClient.generate_intelligence() (uses inline content from Kafka)
    - Stamping: MetadataStampingClient.batch_stamp()
    - Indexing: Parallel Qdrant (vectors) + Memgraph (graph)
    - Caching: Valkey for fast lookups

    Performance:
    - Batch processing: 100 files at a time
    - Parallel execution: asyncio.gather for concurrent operations
    - Target: <5 minutes for 1000 files
    - Search (cold): <2s, Search (warm): <500ms

    Phase 0 Note:
    - Filesystem-based discovery removed - all content provided inline via Kafka messages
    - Use bulk_ingest_repository.py for Kafka-based file ingestion

    Usage:
        bridge = TreeStampingBridge()
        result = await bridge.index_project(
            project_path="/path/to/project",
            project_name="my-project",
            files=[{"relative_path": "...", "content": "..."}]  # Required
        )
    """

    def __init__(
        self,
        intelligence_url: str = None,
        stamping_url: str = None,
        qdrant_url: str = None,
        memgraph_uri: str = None,
        valkey_url: str = None,
        batch_size: int = 100,
    ):
        """
        Initialize TreeStampingBridge with service URLs.

        Args:
            intelligence_url: Archon Intelligence service URL
            stamping_url: Metadata Stamping service URL
            qdrant_url: Qdrant vector database URL
            memgraph_uri: Memgraph graph database URI
            valkey_url: Valkey cache URL
            batch_size: Batch processing size (default: 100)
        """
        # Read URLs from environment variables with fallback to defaults
        self.intelligence_url = intelligence_url or os.getenv(
            "INTELLIGENCE_SERVICE_URL", "http://archon-intelligence:8053"
        )
        self.stamping_url = stamping_url or os.getenv(
            "METADATA_STAMPING_SERVICE_URL",
            "http://omninode-bridge-metadata-stamping:8057",
        )
        self.qdrant_url = qdrant_url or os.getenv(
            "QDRANT_URL", "http://archon-qdrant:6333"
        )
        self.memgraph_uri = memgraph_uri or os.getenv(
            "MEMGRAPH_URI", "bolt://archon-memgraph:7687"
        )
        self.valkey_url = valkey_url or os.getenv(
            "VALKEY_URL", "redis://archon-valkey:6379/0"
        )
        self.batch_size = batch_size

        # Initialize clients (lazy initialization in context managers)
        self.stamping_client: Optional[MetadataStampingClient] = None
        self.use_http_fallback: bool = False  # Flag for HTTP fallback mode
        self.qdrant_client: Optional[QdrantClient] = None
        self.memgraph_driver = None  # Neo4j AsyncGraphDatabase driver
        self.valkey_client = None  # Redis client
        self.httpx_client: Optional[httpx.AsyncClient] = None

        # Embedding configuration (populated during initialization)
        # Read from environment to respect configured model
        self.embedding_model: Optional[str] = os.getenv("EMBEDDING_MODEL")
        self.embedding_dimensions: int = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))

        # Configure concurrency limits from environment variables
        self._intelligence_concurrency_limit = int(
            os.getenv("INTELLIGENCE_CONCURRENCY_LIMIT", "10")
        )
        self._qdrant_concurrency_limit = int(
            os.getenv("QDRANT_CONCURRENCY_LIMIT", "20")
        )
        self._embedding_concurrency_limit = int(
            os.getenv("EMBEDDING_CONCURRENCY_LIMIT", "100")
        )

        # Initialize semaphores for rate limiting external service calls
        # Intelligence generation: limit concurrent external API calls (prevents overwhelming stamping service)
        # Qdrant indexing: limit concurrent database operations (prevents overwhelming vector DB)
        # Embedding generation: limit concurrent OpenAI API calls (prevents rate limiting)
        self._intelligence_semaphore = asyncio.Semaphore(
            self._intelligence_concurrency_limit
        )
        self._qdrant_semaphore = asyncio.Semaphore(self._qdrant_concurrency_limit)
        self._embedding_semaphore = asyncio.Semaphore(self._embedding_concurrency_limit)

        # Metrics
        self.metrics = {
            "total_projects_indexed": 0,
            "total_files_indexed": 0,
            "total_search_queries": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_duration_ms": 0.0,
            "embeddings_generated": 0,
            "embeddings_fallback": 0,
        }

        logger.info(
            f"TreeStampingBridge initialized: stamping={self.stamping_url}, "
            f"qdrant={self.qdrant_url}, batch_size={batch_size}, "
            f"concurrency_limits=(intelligence={self._intelligence_concurrency_limit}, "
            f"qdrant={self._qdrant_concurrency_limit}, "
            f"embeddings={self._embedding_concurrency_limit})"
        )

    # ==========================================================================
    # Public API Methods
    # ==========================================================================

    async def index_project(
        self,
        project_path: str,
        project_name: str,
        files: Optional[List[Dict[str, Any]]] = None,
        include_tests: bool = True,
        force_reindex: bool = False,
    ) -> ProjectIndexResult:
        """
        Index entire project with full intelligence pipeline.

        Pipeline stages:
        1. Tree Discovery → enumerate all files (or use provided inline content)
        2. Intelligence Generation → batch process files for metadata
        3. Metadata Stamping → enrich files with intelligence
        4. Vector Indexing → index in Qdrant for semantic search
        5. Graph Indexing → index in Memgraph for relationships
        6. Cache Warming → pre-warm cache with common queries

        Args:
            project_path: Absolute path to project directory
            project_name: Unique project identifier
            files: Optional list of file dicts with inline content (skips filesystem discovery)
                   Format: [{"relative_path": str, "content": str}, ...]
            include_tests: Whether to include test files
            force_reindex: Force reindexing even if already indexed

        Returns:
            ProjectIndexResult with indexing statistics

        Raises:
            TreeDiscoveryError: If tree generation fails
            IntelligenceGenerationError: If intelligence generation fails
            StampingError: If stamping fails
            IndexingError: If indexing fails
        """
        start_time = time.perf_counter()
        errors: List[str] = []
        warnings: List[str] = []

        logger.info(
            f"🚀 Starting project indexing pipeline",
            extra={
                "project_name": project_name,
                "project_path": project_path,
                "include_tests": include_tests,
                "force_reindex": force_reindex,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

        try:
            # Initialize clients
            await self._initialize_clients()

            # Check if already indexed
            if not force_reindex:
                status = await self.get_indexing_status(project_name=project_name)
                if status and status[0].indexed:
                    logger.info(
                        f"⏭️  Project {project_name} already indexed. Skipping.",
                        extra={"project_name": project_name, "already_indexed": True},
                    )
                    warnings.append(
                        "Project already indexed. Use force_reindex=True to reindex."
                    )
                    return ProjectIndexResult(
                        success=False,
                        project_name=project_name,
                        duration_ms=int((time.perf_counter() - start_time) * 1000),
                        warnings=warnings,
                    )

            # Stage 1: Validate inline content provided (Phase 0 removed)
            logger.info("🔍 Stage 1/6: Validating inline content")
            if not files:
                error_msg = (
                    "files parameter is required. Phase 0 (filesystem-based indexing) "
                    "has been removed. Use bulk_ingest_repository.py which provides "
                    "inline content in Kafka messages."
                )
                logger.error(error_msg)
                raise TreeDiscoveryError(error_msg)

            # Use provided files with inline content
            file_paths = [f["relative_path"] for f in files]
            files_discovered = len(files)
            logger.info(
                f"✅ Stage 1/6 Complete: Using {files_discovered} provided files (inline content)",
                extra={
                    "stage": 1,
                    "files_discovered": files_discovered,
                    "project_name": project_name,
                },
            )

            # Stage 2: Generate intelligence (batch)
            stage2_start = time.perf_counter()
            logger.info(
                f"🧠 Stage 2/6: Generating intelligence for {len(file_paths)} files (batch size: {self.batch_size})",
                extra={
                    "stage": 2,
                    "total_files": len(file_paths),
                    "batch_size": self.batch_size,
                    "project_name": project_name,
                },
            )
            intelligence_results = await self._generate_intelligence_batch(
                file_paths, provided_files=files
            )
            stage2_duration_ms = (time.perf_counter() - stage2_start) * 1000
            logger.info(
                f"✅ Stage 2/6 Complete: Generated intelligence for {len(intelligence_results)} files",
                extra={
                    "stage": 2,
                    "files_processed": len(intelligence_results),
                    "duration_ms": round(stage2_duration_ms, 2),
                    "project_name": project_name,
                },
            )

            # Stage 3: Stamp files with intelligence
            stage3_start = time.perf_counter()
            logger.info(
                f"📝 Stage 3/6: Stamping {len(intelligence_results)} files with metadata",
                extra={
                    "stage": 3,
                    "file_count": len(intelligence_results),
                    "project_name": project_name,
                },
            )
            stamp_result = await self._stamp_files_batch(
                project_name, project_path, intelligence_results
            )
            stage3_duration_ms = (time.perf_counter() - stage3_start) * 1000
            logger.info(
                f"✅ Stage 3/6 Complete: Stamped {stamp_result.get('successful_stamps', 0)} files",
                extra={
                    "stage": 3,
                    "successful_stamps": stamp_result.get("successful_stamps", 0),
                    "failed_stamps": stamp_result.get("failed_stamps", 0),
                    "duration_ms": round(stage3_duration_ms, 2),
                    "project_name": project_name,
                },
            )

            # Stage 4 & 5: Index in storage (parallel)
            stage45_start = time.perf_counter()
            logger.info(
                "💾 Stage 4-5/6: Indexing in Qdrant + Memgraph (parallel)",
                extra={
                    "stage": 4,
                    "file_count": len(intelligence_results),
                    "project_name": project_name,
                },
            )
            index_result = await self._index_in_storage(
                project_name, project_path, intelligence_results
            )
            stage45_duration_ms = (time.perf_counter() - stage45_start) * 1000
            logger.info(
                f"✅ Stage 4-5/6 Complete: Indexed {index_result.get('vector_indexed', 0)} vectors, {index_result.get('graph_indexed', 0)} graph nodes",
                extra={
                    "stage": 4,
                    "vector_indexed": index_result.get("vector_indexed", 0),
                    "graph_indexed": index_result.get("graph_indexed", 0),
                    "duration_ms": round(stage45_duration_ms, 2),
                    "project_name": project_name,
                },
            )

            # Stage 6: Warm cache
            stage6_start = time.perf_counter()
            logger.info(
                "🔥 Stage 6/6: Warming cache with common queries",
                extra={"stage": 6, "project_name": project_name},
            )
            try:
                await self._warm_cache(project_name, intelligence_results)
                cache_warmed = True
                stage6_duration_ms = (time.perf_counter() - stage6_start) * 1000
                logger.info(
                    f"✅ Stage 6/6 Complete: Cache warmed successfully",
                    extra={
                        "stage": 6,
                        "cache_warmed": True,
                        "duration_ms": round(stage6_duration_ms, 2),
                        "project_name": project_name,
                    },
                )
            except (OSError, ConnectionError, TimeoutError) as e:
                logger.warning(f"⚠️  Cache warming failed (connection/timeout): {e}")
                warnings.append(f"Cache warming failed: {e}")
                cache_warmed = False
            except Exception as e:
                logger.warning(
                    f"⚠️  Cache warming failed (unexpected error): {e}", exc_info=True
                )
                warnings.append(f"Cache warming failed: {e}")
                cache_warmed = False

            # Finalize
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            self.metrics["total_projects_indexed"] += 1
            self.metrics["total_files_indexed"] += len(intelligence_results)
            self.metrics["total_duration_ms"] += duration_ms

            logger.info(
                f"✅ Project indexing complete: {project_name}",
                extra={
                    "project_name": project_name,
                    "files_indexed": len(intelligence_results),
                    "total_duration_ms": duration_ms,
                    "stage2_duration_ms": round(stage2_duration_ms, 2),
                    "stage3_duration_ms": round(stage3_duration_ms, 2),
                    "stage45_duration_ms": round(stage45_duration_ms, 2),
                    "files_per_second": (
                        round(len(intelligence_results) / (duration_ms / 1000), 2)
                        if duration_ms > 0
                        else 0
                    ),
                },
            )

            return ProjectIndexResult(
                success=True,
                project_name=project_name,
                files_discovered=files_discovered,
                files_indexed=len(intelligence_results),
                vector_indexed=index_result.get("vector_indexed", 0),
                graph_indexed=index_result.get("graph_indexed", 0),
                cache_warmed=cache_warmed,
                duration_ms=duration_ms,
                errors=errors,
                warnings=warnings,
            )

        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"Project indexing failed: {e}", exc_info=True)
            errors.append(str(e))

            return ProjectIndexResult(
                success=False,
                project_name=project_name,
                duration_ms=duration_ms,
                errors=errors,
                warnings=warnings,
            )
        finally:
            await self._cleanup_clients()

    async def search_files(
        self,
        query: str,
        projects: Optional[List[str]] = None,
        min_quality_score: float = 0.0,
        limit: int = 10,
    ) -> FileSearchResult:
        """
        Search for files across projects using semantic + quality ranking.

        Search strategy:
        1. Check cache (Valkey) → fast lookup
        2. If miss: Query Qdrant (vector similarity)
        3. Filter by quality score
        4. Rank by composite score (semantic + quality + compliance)
        5. Cache result (TTL: 5 minutes)

        Args:
            query: Natural language search query
            projects: Optional list of project filters
            min_quality_score: Minimum quality threshold (0.0-1.0)
            limit: Maximum results to return

        Returns:
            FileSearchResult with ranked matches

        Performance:
        - Target (cold): <2s
        - Target (warm): <500ms
        """
        start_time = time.perf_counter()

        logger.info(
            f"Searching files: query='{query}', projects={projects}, "
            f"min_quality_score={min_quality_score}, limit={limit}"
        )

        try:
            # Initialize clients
            await self._initialize_clients()

            # Stage 1: Check cache
            cache_key = self._get_cache_key(query, projects, min_quality_score, limit)
            cached_result = await self._get_from_cache(cache_key)

            if cached_result:
                query_time_ms = int((time.perf_counter() - start_time) * 1000)
                self.metrics["cache_hits"] += 1
                logger.info(f"✅ Cache hit: {query_time_ms}ms")

                cached_result["cache_hit"] = True
                cached_result["query_time_ms"] = query_time_ms
                return FileSearchResult(**cached_result)

            # Stage 2: Query Qdrant (cache miss)
            self.metrics["cache_misses"] += 1
            logger.info("Cache miss - querying Qdrant...")

            results = await self._search_in_qdrant(
                query=query,
                projects=projects,
                min_quality_score=min_quality_score,
                limit=limit,
            )

            # Stage 3: Cache result
            query_time_ms = int((time.perf_counter() - start_time) * 1000)

            search_result = FileSearchResult(
                success=True,
                results=results,
                query_time_ms=query_time_ms,
                cache_hit=False,
                total_results=len(results),
            )

            # Cache with configurable TTL (uses default from config)
            await self._set_in_cache(cache_key, search_result.model_dump())

            self.metrics["total_search_queries"] += 1

            logger.info(
                f"✅ Search complete: {len(results)} results in {query_time_ms}ms"
            )

            return search_result

        except Exception as e:
            query_time_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"Search failed: {e}", exc_info=True)

            return FileSearchResult(
                success=False,
                results=[],
                query_time_ms=query_time_ms,
                cache_hit=False,
                total_results=0,
                error=str(e),
            )
        finally:
            await self._cleanup_clients()

    async def get_indexing_status(
        self, project_name: Optional[str] = None
    ) -> List[ProjectIndexStatus]:
        """
        Get indexing status for projects.

        Data sources:
        - Valkey cache (1 hour TTL)
        - Fallback: Query Qdrant for indexed files

        Args:
            project_name: Optional filter for specific project

        Returns:
            List of ProjectIndexStatus (all projects if name=None)
        """
        logger.info(f"Getting indexing status: project_name={project_name}")

        try:
            # Initialize clients
            await self._initialize_clients()

            # Check cache first
            if project_name:
                cache_key = f"file_location:project:{project_name}:status"
                cached_status = await self._get_from_cache(cache_key)

                if cached_status:
                    logger.info(f"✅ Status from cache: {project_name}")
                    return [ProjectIndexStatus(**cached_status)]

            # Fallback: Query Qdrant
            if self.qdrant_client:
                try:
                    # Get all points from archon_vectors collection
                    collection_info = self.qdrant_client.get_collection(
                        "archon_vectors"
                    )

                    # Extract project names and file counts
                    # (Simplified - in production, query points with filters)
                    projects: Dict[str, Dict] = {}

                    # For now, return placeholder data
                    if project_name:
                        status = ProjectIndexStatus(
                            project_name=project_name,
                            indexed=collection_info.points_count > 0,
                            file_count=0,  # Would query actual count
                            status=(
                                "indexed"
                                if collection_info.points_count > 0
                                else "unknown"
                            ),
                        )
                        return [status]
                    else:
                        return []

                except (ConnectionError, TimeoutError) as e:
                    logger.warning(f"Qdrant query failed (connection/timeout): {e}")
                    return []
                except Exception as e:
                    logger.warning(
                        f"Qdrant query failed (unexpected error): {e}", exc_info=True
                    )
                    return []

            return []

        except Exception as e:
            logger.error(f"Status check failed: {e}", exc_info=True)
            return []
        finally:
            await self._cleanup_clients()

    # ==========================================================================
    # Private Module Methods
    # ==========================================================================

    # Phase 0 method (_discover_tree) removed - filesystem-based discovery deprecated
    # Use inline content provided via Kafka messages instead

    async def _generate_intelligence_http(
        self,
        file_path: str,
        provided_content: Optional[str] = None,
        provided_language: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate intelligence for a file using archon-intelligence service.

        Calls /api/bridge/generate-intelligence endpoint which provides:
        - Semantic analysis (concepts, themes, domains, patterns)
        - ONEX compliance and quality assessment
        - Pattern tracking and analytics

        Args:
            file_path: Path to file to process
            provided_content: Optional inline file content (skips filesystem read)
            provided_language: Optional language detected from file extension

        Returns:
            Intelligence result dictionary or None if failed

        Response format:
            {
                "success": bool,
                "metadata": OmniNodeToolMetadata (quality_metrics, classification, etc.),
                "processing_metadata": {
                    "processing_time_ms": int,
                    "file_size_bytes": int,
                    "timestamp": str
                },
                "intelligence_sources": ["langextract", "quality_scorer", "pattern_tracking"],
                "recommendations": ["..."]
            }
        """
        # Entry logging
        logger.info(
            f"ENTER _generate_intelligence_http: file_path={file_path}, "
            f"has_content={provided_content is not None}, language={provided_language}"
        )

        if not self.httpx_client:
            timeout = httpx.Timeout(
                connect=get_http_timeout("connect"),
                read=get_http_timeout("intelligence"),
                write=get_http_timeout("default"),
                pool=get_http_timeout("default"),
            )
            self.httpx_client = httpx.AsyncClient(timeout=timeout)

        try:
            # Validate inline content provided (Phase 0 removed)
            if not provided_content:
                error_msg = (
                    f"No inline content provided for {file_path}. "
                    "Phase 0 (filesystem-based) has been removed. "
                    "Ensure files parameter includes content for all files."
                )
                logger.error(error_msg)
                return None

            # Use inline content
            content = provided_content
            size_bytes = len(content.encode("utf-8"))
            logger.debug(f"Using inline content for {file_path} ({size_bytes} bytes)")
            # Call archon-intelligence service for intelligence generation
            # Endpoint: POST /api/bridge/generate-intelligence
            request_body = {
                "file_path": file_path,
                "include_semantic": True,
                "include_compliance": True,
                "include_patterns": True,
                "min_confidence": 0.7,
            }

            # Include inline content if provided (skips filesystem read on intelligence service)
            if provided_content:
                request_body["content"] = content

            # CRITICAL: Propagate language to intelligence service
            if provided_language:
                request_body["language"] = provided_language
                logger.debug(
                    f"🔤 Propagating language to intelligence: {provided_language}"
                )

            response = await self.httpx_client.post(
                f"{self.intelligence_url}/api/bridge/generate-intelligence",
                json=request_body,
            )
            response.raise_for_status()
            result = response.json()

            # Validate response format
            if not result.get("success"):
                error_msg = result.get("error", "Unknown error")
                logger.error(
                    f"❌ Intelligence generation FAILED: {error_msg}",
                    extra={"file_path": file_path, "error": error_msg},
                )
                return None

            # Extract metadata for indexing
            # Response structure: {success, metadata, processing_metadata, intelligence_sources, recommendations}
            metadata = result.get("metadata", {})
            quality_metrics = metadata.get("quality_metrics", {})
            processing_metadata = result.get("processing_metadata", {})

            # Build intelligence result in expected format for downstream processing
            intelligence_result = {
                "success": True,
                "file_path": file_path,
                "metadata": {
                    # Quality and compliance metrics
                    "quality_score": quality_metrics.get("quality_score", 0.0),
                    "onex_compliance": quality_metrics.get("onex_compliance", 0.0),
                    "complexity_score": quality_metrics.get("complexity_score", 0.0),
                    "maintainability_score": quality_metrics.get(
                        "maintainability_score", 0.0
                    ),
                    "documentation_score": quality_metrics.get(
                        "documentation_score", 0.0
                    ),
                    "temporal_relevance": quality_metrics.get(
                        "temporal_relevance", 0.0
                    ),
                    # Classification
                    "maturity": metadata.get("classification", {}).get(
                        "maturity", "unknown"
                    ),
                    "trust_score": metadata.get("classification", {}).get(
                        "trust_score", 0
                    ),
                    # Semantic analysis (from intelligence sources)
                    "concepts": metadata.get("semantic_analysis", {}).get(
                        "concepts", []
                    ),
                    "themes": metadata.get("semantic_analysis", {}).get("themes", []),
                    "domains": metadata.get("semantic_analysis", {}).get("domains", []),
                    "patterns": metadata.get("semantic_analysis", {}).get(
                        "patterns", []
                    ),
                    # ONEX metadata
                    "onex_type": metadata.get("onex_type", "unknown"),
                    "protocols_supported": metadata.get("protocols_supported", []),
                    # Language field (preserve from upstream detection)
                    "language": provided_language or "unknown",
                    # Additional metadata
                    "summary": metadata.get("description", ""),
                    "intelligence_sources": result.get("intelligence_sources", []),
                    "recommendations": result.get("recommendations", []),
                },
                "processing_metadata": processing_metadata,
            }

            logger.debug(
                f"✅ Intelligence generated for {file_path}: "
                f"quality={quality_metrics.get('quality_score', 0):.2f}, "
                f"onex={quality_metrics.get('onex_compliance', 0):.2f}, "
                f"sources={len(result.get('intelligence_sources', []))}, "
                f"language={provided_language or 'unknown'}"
            )

            # Success exit logging
            logger.info(
                f"EXIT _generate_intelligence_http: SUCCESS - file_path={file_path}, "
                f"quality_score={quality_metrics.get('quality_score', 0):.2f}, "
                f"sources={len(result.get('intelligence_sources', []))}"
            )
            return intelligence_result

        except httpx.HTTPStatusError as e:
            logger.error(
                f"EXIT _generate_intelligence_http: ERROR - {type(e).__name__}: "
                f"file_path={file_path}, status={e.response.status_code}",
                exc_info=True,
            )
            if e.response.status_code >= 500:
                logger.error(f"Server error response: {e.response.text}")
            return None
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.error(
                f"EXIT _generate_intelligence_http: ERROR - {type(e).__name__}: "
                f"file_path={file_path}, error={str(e)}",
                exc_info=True,
            )
            return None
        except Exception as e:
            logger.error(
                f"EXIT _generate_intelligence_http: ERROR - {type(e).__name__}: "
                f"file_path={file_path}, error={str(e)}",
                exc_info=True,
            )
            return None

    def _extract_files_from_tree(self, tree_response: Dict[str, Any]) -> List[str]:
        """
        Extract file paths from tree response with comprehensive validation.

        Args:
            tree_response: Tree discovery response dictionary

        Returns:
            List of validated absolute file paths

        Raises:
            ValueError: If tree_response is invalid or missing required fields
        """
        # Validate input structure
        if not isinstance(tree_response, dict):
            raise ValueError(
                f"tree_response must be dict, got {type(tree_response).__name__}"
            )

        if "files" not in tree_response:
            raise ValueError("tree_response missing required 'files' field")

        files = tree_response.get("files", [])

        if not isinstance(files, list):
            raise ValueError(
                f"tree_response['files'] must be list, got {type(files).__name__}"
            )

        # Extract and validate file paths
        file_paths = []
        for idx, file_entry in enumerate(files):
            # Validate entry structure
            if not isinstance(file_entry, dict):
                logger.warning(
                    f"Skipping invalid file entry at index {idx}: not a dict (got {type(file_entry).__name__})"
                )
                continue

            # Extract path with validation
            path = file_entry.get("path") or file_entry.get("file_path")
            if not path:
                logger.warning(
                    f"Skipping file entry at index {idx}: missing 'path' or 'file_path' field"
                )
                continue

            if not isinstance(path, str):
                logger.warning(
                    f"Skipping file entry at index {idx}: path is not string (got {type(path).__name__})"
                )
                continue

            # Validate path format (must be absolute)
            if not path.startswith("/"):
                logger.warning(
                    f"Skipping file entry at index {idx}: path must be absolute, got '{path}'"
                )
                continue

            # Check for path traversal attempts
            if ".." in path:
                logger.warning(
                    f"Skipping file entry at index {idx}: path contains '..' traversal: '{path}'"
                )
                continue

            # Additional validation: ensure path is not just "/"
            if path == "/":
                logger.warning(
                    f"Skipping file entry at index {idx}: path cannot be root '/'"
                )
                continue

            file_paths.append(path)

        logger.info(
            f"Extracted {len(file_paths)} valid file paths from {len(files)} entries"
        )

        return file_paths

    async def _generate_intelligence_with_semaphore(
        self,
        file_path: str,
        provided_content: Optional[str] = None,
        provided_language: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate intelligence for a single file with rate limiting.

        Uses semaphore to limit concurrent external API calls, preventing
        overwhelming of the metadata stamping service.

        Args:
            file_path: Path to file to process
            provided_content: Optional inline file content
            provided_language: Optional language detected from file extension

        Returns:
            Intelligence result dictionary or None if failed
        """
        async with self._intelligence_semaphore:
            try:
                # Use HTTP fallback if MCP client not available
                if self.use_http_fallback or not self.stamping_client:
                    return await self._generate_intelligence_http(
                        file_path,
                        provided_content=provided_content,
                        provided_language=provided_language,
                    )

                # Use MCP client
                result = await self.stamping_client.generate_intelligence(
                    file_path=file_path,
                    include_semantic=True,
                    include_compliance=True,
                    include_patterns=True,
                )
                return result
            except (httpx.HTTPError, httpx.TimeoutException, asyncio.TimeoutError) as e:
                logger.warning(
                    f"Intelligence generation failed for {file_path} (network error): {e}"
                )
                return None
            except Exception as e:
                logger.warning(
                    f"Intelligence generation failed for {file_path} (unexpected error): {e}",
                    exc_info=True,
                )
                return None

    async def _generate_intelligence_batch(
        self,
        file_paths: List[str],
        provided_files: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate intelligence for batch of files (parallel processing).

        Args:
            file_paths: List of file paths to process
            provided_files: Optional list of file dicts with inline content

        Returns:
            List of intelligence results

        Raises:
            IntelligenceGenerationError: If batch processing fails
        """
        # Entry logging
        logger.info(
            f"ENTER _generate_intelligence_batch: file_count={len(file_paths)}, "
            f"has_inline_content={provided_files is not None}, "
            f"batch_size={self.batch_size}"
        )

        try:
            if not self.stamping_client and not self.use_http_fallback:
                raise IntelligenceGenerationError("Stamping client not initialized")

            results = []

            # Create lookup dict for inline content
            content_lookup = {}
            if provided_files:
                content_lookup = {
                    f["relative_path"]: f.get("content")
                    for f in provided_files
                    if f.get("content")
                }
                language_lookup = {
                    f["relative_path"]: f.get("language", "unknown")
                    for f in provided_files
                }
                logger.debug(
                    f"Created content lookup with {len(content_lookup)} entries, "
                    f"language lookup with {len(language_lookup)} entries"
                )

            # Process in batches of batch_size
            for i in range(0, len(file_paths), self.batch_size):
                batch = file_paths[i : i + self.batch_size]

                logger.info(
                    f"Processing intelligence batch {i // self.batch_size + 1} "
                    f"({len(batch)} files)..."
                )

                # Parallel intelligence generation with rate limiting
                tasks = [
                    self._generate_intelligence_with_semaphore(
                        file_path,
                        provided_content=content_lookup.get(file_path),
                        provided_language=language_lookup.get(file_path, "unknown"),
                    )
                    for file_path in batch
                ]

                batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                # Filter out errors and None results
                for file_path, result in zip(batch, batch_results):
                    if isinstance(result, Exception):
                        logger.warning(
                            f"Intelligence generation failed for {file_path}: {result}"
                        )
                        continue

                    if result is None:
                        continue

                    if result.get("success"):
                        result["file_path"] = file_path
                        results.append(result)

            # Success exit logging
            logger.info(
                f"EXIT _generate_intelligence_batch: SUCCESS - processed {len(results)} files "
                f"from {len(file_paths)} total files"
            )
            return results

        except Exception as e:
            logger.error(
                f"EXIT _generate_intelligence_batch: ERROR - {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            raise IntelligenceGenerationError(f"Failed to generate intelligence: {e}")

    async def _stamp_files_batch(
        self,
        project_name: str,
        project_path: str,
        intelligence_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Stamp files with intelligence metadata (batch of batch_size).

        Args:
            project_name: Project name
            project_path: Project root path
            intelligence_results: Intelligence results from generation

        Returns:
            Dictionary with stamp statistics

        Raises:
            StampingError: If batch stamping fails
        """
        # Entry logging
        logger.info(
            f"ENTER _stamp_files_batch: project_name={project_name}, "
            f"file_count={len(intelligence_results)}, "
            f"use_http_fallback={self.use_http_fallback}"
        )

        try:
            # Skip stamping if HTTP fallback is active (intelligence already captured in Stage 2)
            if self.use_http_fallback or not self.stamping_client:
                logger.info(
                    f"Skipping metadata stamping for {len(intelligence_results)} files "
                    "(using HTTP fallback - intelligence already included in Stage 2)"
                )
                return {
                    "success": True,
                    "successful_stamps": 0,
                    "failed_stamps": 0,
                    "skipped": len(intelligence_results),
                    "reason": "http_fallback_active",
                }

            # Verify stamping_client is valid (type safety check)
            if isinstance(self.stamping_client, str):
                logger.error(
                    f"BUG DETECTED: stamping_client is a string ('{self.stamping_client}') "
                    "instead of client instance. This should never happen!"
                )
                raise StampingError(
                    f"Invalid stamping_client type: {type(self.stamping_client)}. "
                    "Expected MetadataStampingClient instance."
                )

            stamps = []

            for intel_result in intelligence_results:
                file_path = intel_result.get("file_path", "")
                relative_path = file_path.replace(project_path, "").lstrip("/")

                # Generate file hash (simplified - should read file content)
                file_hash = hashlib.blake2b(
                    file_path.encode(), digest_size=16
                ).hexdigest()

                # Build stamp metadata
                metadata = {
                    "absolute_path": file_path,
                    "relative_path": relative_path,
                    "project_name": project_name,
                    "project_root": project_path,
                    "file_hash": file_hash,
                    **intel_result.get("metadata", {}),
                }

                stamps.append({"file_hash": file_hash, "metadata": metadata})

            # Batch stamp (safe to call - type checked above)
            result = await self.stamping_client.batch_stamp(
                stamps=stamps, overwrite=True, batch_size=self.batch_size
            )

            logger.info(
                f"Stamped {result.successful_stamps} files "
                f"({result.failed_stamps} failed)"
            )

            # Success exit logging
            logger.info(
                f"EXIT _stamp_files_batch: SUCCESS - successful={result.successful_stamps}, "
                f"failed={result.failed_stamps}"
            )

            return {
                "success": result.success,
                "successful_stamps": result.successful_stamps,
                "failed_stamps": result.failed_stamps,
            }

        except Exception as e:
            logger.error(
                f"EXIT _stamp_files_batch: ERROR - {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            raise StampingError(f"Failed to stamp files: {e}")

    async def _index_in_storage(
        self,
        project_name: str,
        project_path: str,
        intelligence_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Index files in Qdrant + Memgraph (parallel).

        Args:
            project_name: Project name
            project_path: Project root path
            intelligence_results: Intelligence results

        Returns:
            Dictionary with indexing statistics

        Raises:
            IndexingError: If indexing fails
        """
        try:
            # Parallel indexing
            vector_task = self._index_in_qdrant_batch(
                project_name, project_path, intelligence_results
            )
            graph_task = self._index_in_memgraph_batch(
                project_name, project_path, intelligence_results
            )

            vector_result, graph_result = await asyncio.gather(
                vector_task, graph_task, return_exceptions=True
            )

            vector_count = 0 if isinstance(vector_result, Exception) else vector_result
            graph_count = 0 if isinstance(graph_result, Exception) else graph_result

            if isinstance(vector_result, Exception):
                logger.error(f"Qdrant indexing failed: {vector_result}")

            if isinstance(graph_result, Exception):
                logger.error(f"Memgraph indexing failed: {graph_result}")

            return {
                "vector_indexed": vector_count,
                "graph_indexed": graph_count,
            }

        except Exception as e:
            logger.error(f"Storage indexing failed: {e}", exc_info=True)
            raise IndexingError(f"Failed to index in storage: {e}")

    async def _index_in_qdrant_batch(
        self,
        project_name: str,
        project_path: str,
        intelligence_results: List[Dict[str, Any]],
    ) -> int:
        """
        Index files in Qdrant vector database.

        Args:
            project_name: Project name
            project_path: Project root path
            intelligence_results: Intelligence results

        Returns:
            Number of vectors indexed
        """
        # Entry logging
        logger.info(
            f"ENTER _index_in_qdrant_batch: project_name={project_name}, "
            f"file_count={len(intelligence_results)}, "
            f"embedding_dimensions={self.embedding_dimensions}"
        )

        try:
            if not self.qdrant_client:
                raise IndexingError("Qdrant client not initialized")

            # Ensure collection exists
            try:
                self.qdrant_client.get_collection("archon_vectors")
            except Exception:
                # Create collection with dynamic dimensions based on embedding model
                self.qdrant_client.create_collection(
                    collection_name="archon_vectors",
                    vectors_config=VectorParams(
                        size=self.embedding_dimensions, distance=Distance.COSINE
                    ),
                )
                logger.info(
                    f"Created Qdrant collection: archon_vectors "
                    f"({self.embedding_dimensions} dimensions)"
                )

            # Prepare points
            points = []
            failed_indexing = 0
            for idx, intel_result in enumerate(intelligence_results):
                file_path = intel_result.get("file_path", "")
                relative_path = file_path.replace(project_path, "").lstrip("/")

                # Generate embedding from file path + metadata
                metadata = intel_result.get("metadata", {})

                # VALIDATION: Check for empty metadata (indicates intelligence generation failure)
                if not metadata or not any(metadata.values()):
                    logger.error(
                        f"❌ EMPTY METADATA for {file_path} - Intelligence generation failed. "
                        f"SKIPPING Qdrant indexing. Check archon-intelligence service health.",
                        extra={
                            "file_path": file_path,
                            "intel_result": intel_result,
                            "correlation_id": intel_result.get("correlation_id"),
                        },
                    )
                    failed_indexing += 1
                    continue

                embedding_text = "\n".join(
                    [
                        f"Path: {file_path}",
                        f"Summary: {metadata.get('summary', 'N/A')}",
                        f"Concepts: {', '.join(metadata.get('concepts', [])[:10])}",
                        f"Themes: {', '.join(metadata.get('themes', [])[:10])}",
                        f"ONEX Type: {metadata.get('onex_type', 'unknown')}",
                    ]
                )

                logger.debug(
                    f"Generating embedding for {file_path} | text_length={len(embedding_text)}"
                )
                vector = await self._generate_embedding(embedding_text)

                # VALIDATION: Reject zero-valued vectors (indicates embedding generation failure)
                if not vector or all(v == 0.0 for v in vector):
                    logger.error(
                        f"❌ ZERO VECTOR DETECTED for {file_path} - SKIPPING storage. "
                        f"This indicates embedding generation failed. Check Ollama service."
                    )
                    # Skip this file instead of storing broken vector
                    continue

                logger.debug(
                    f"✅ Valid non-zero embedding generated for {file_path} | "
                    f"dimensions={len(vector)} | first_5={vector[:5]}"
                )

                # Extract content hash if available (BLAKE3 from upstream)
                content_hash = metadata.get("content_hash") or metadata.get("checksum")

                payload = {
                    "absolute_path": file_path,
                    "relative_path": relative_path,
                    "project_name": project_name,
                    "project_root": project_path,
                    "quality_score": metadata.get("quality_score", 0.0),
                    "onex_compliance": metadata.get("onex_compliance", 0.0),
                    "onex_type": metadata.get("onex_type"),
                    "concepts": metadata.get("concepts", []),
                    "themes": metadata.get("themes", []),
                    "content_hash": content_hash,  # BLAKE3 hash for deduplication
                    "indexed_at": datetime.now(UTC).isoformat(),
                }

                # Log hash information
                if content_hash:
                    logger.debug(
                        f"Indexing file in Qdrant with hash: {file_path} "
                        f"(hash={content_hash[:16] if len(content_hash) > 16 else content_hash}...)"
                    )
                else:
                    logger.warning(f"No content hash available for file: {file_path}")

                # Generate stable 64-bit int ID from file path (deterministic)
                id_int = int(
                    hashlib.blake2b(file_path.encode(), digest_size=8).hexdigest(), 16
                )

                # VALIDATION: Detect low quality payloads (data quality issue, not failure)
                payload_quality_issues = []
                if payload.get("quality_score", 0.0) == 0.0:
                    payload_quality_issues.append("quality_score=0.0")
                if not payload.get("concepts"):
                    payload_quality_issues.append("no concepts")
                if not payload.get("themes"):
                    payload_quality_issues.append("no themes")

                if payload_quality_issues:
                    logger.warning(
                        f"⚠️  Low quality payload for {file_path}: {', '.join(payload_quality_issues)}. "
                        f"Vector will be indexed but search quality may be poor.",
                        extra={
                            "file_path": file_path,
                            "issues": payload_quality_issues,
                        },
                    )

                points.append(PointStruct(id=id_int, vector=vector, payload=payload))

            # Batch upsert (offloaded to thread to avoid blocking event loop)
            await asyncio.to_thread(
                self.qdrant_client.upsert,
                collection_name="archon_vectors",
                points=points,
                wait=True,
            )

            if failed_indexing > 0:
                logger.warning(
                    f"Indexed {len(points)} vectors in Qdrant ({failed_indexing} files skipped due to empty metadata)"
                )
            else:
                logger.info(f"Indexed {len(points)} vectors in Qdrant")

            # Success exit logging
            logger.info(
                f"EXIT _index_in_qdrant_batch: SUCCESS - vectors_indexed={len(points)}, "
                f"failed={failed_indexing}"
            )
            return len(points)

        except Exception as e:
            logger.error(
                f"EXIT _index_in_qdrant_batch: ERROR - {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            raise

    async def _index_in_memgraph_batch(
        self,
        project_name: str,
        project_path: str,
        intelligence_results: List[Dict[str, Any]],
    ) -> int:
        """
        Index files in Memgraph knowledge graph.

        Creates File, Project, and Concept nodes with BELONGS_TO and HAS_CONCEPT relationships.

        Args:
            project_name: Project name
            project_path: Project root path
            intelligence_results: Intelligence results with metadata

        Returns:
            Number of files successfully indexed
        """
        # Entry logging
        logger.info(
            f"ENTER _index_in_memgraph_batch: project_name={project_name}, "
            f"file_count={len(intelligence_results)}, "
            f"has_driver={self.memgraph_driver is not None}"
        )

        if not self.memgraph_driver:
            logger.warning("Memgraph driver not available - skipping graph indexing")
            return 0

        try:
            # Build Cypher query for batch insert
            query = f"""
            UNWIND $files AS file
            MERGE (f:{MemgraphLabels.FILE} {{path: file.path}})
            SET f.project_name = file.project_name,
                f.relative_path = file.relative_path,
                f.quality_score = file.quality_score,
                f.onex_compliance = file.onex_compliance,
                f.onex_type = file.onex_type,
                f.content_hash = file.content_hash,
                f.indexed_at = datetime()

            // Create project relationship
            MERGE (p:{MemgraphLabels.PROJECT} {{name: file.project_name}})
            MERGE (f)-[:BELONGS_TO]->(p)

            // Index concepts as relationships
            FOREACH (concept IN file.concepts |
                MERGE (c:{MemgraphLabels.CONCEPT} {{name: concept}})
                MERGE (f)-[:HAS_CONCEPT]->(c)
            )

            // Index themes as relationships
            FOREACH (theme IN file.themes |
                MERGE (t:{MemgraphLabels.THEME} {{name: theme}})
                MERGE (f)-[:HAS_THEME]->(t)
            )
            """

            # Prepare batch data
            files_data = []
            for intel_result in intelligence_results:
                file_path = intel_result.get("file_path", "")
                relative_path = file_path.replace(project_path, "").lstrip("/")
                metadata = intel_result.get("metadata", {})

                # Extract content hash if available
                content_hash = metadata.get("content_hash") or metadata.get("checksum")

                # Extract language from metadata or file extension
                language = metadata.get("language", "unknown")
                if language == "unknown":
                    # Try to map from file extension
                    file_ext = os.path.splitext(file_path)[1].lstrip(".")
                    if file_ext:
                        # Import the mapping function from app.py
                        from services.intelligence.app import _map_extension_to_language

                        language = _map_extension_to_language(file_ext)

                file_data = {
                    "path": file_path,
                    "relative_path": relative_path,
                    "project_name": project_name,
                    "language": language,  # Add language field
                    "quality_score": metadata.get("quality_score", 0.0),
                    "onex_compliance": metadata.get("onex_compliance", 0.0),
                    "onex_type": metadata.get("onex_type", "unknown"),
                    "content_hash": content_hash,  # BLAKE3 hash for deduplication
                    "concepts": metadata.get("concepts", [])[:10],  # Limit to top 10
                    "themes": metadata.get("themes", [])[:10],  # Limit to top 10
                }

                # Log hash information
                if content_hash:
                    logger.debug(
                        f"Indexing file in Memgraph with hash: {file_path} "
                        f"(hash={content_hash[:16] if len(content_hash) > 16 else content_hash}...)"
                    )
                else:
                    logger.warning(
                        f"No content hash available for file in Memgraph: {file_path}"
                    )

                files_data.append(file_data)

            # Execute query in batches to avoid overwhelming Memgraph
            indexed_count = 0
            batch_size = min(50, self.batch_size)  # Smaller batches for graph DB

            for i in range(0, len(files_data), batch_size):
                batch = files_data[i : i + batch_size]
                batch_num = i // batch_size + 1

                try:
                    async with self.memgraph_driver.session() as session:
                        result = await session.run(query, {"files": batch})
                        await result.consume()

                    indexed_count += len(batch)
                    logger.debug(
                        f"Indexed {len(batch)} files in Memgraph "
                        f"(batch {batch_num}/{(len(files_data) + batch_size - 1) // batch_size})"
                    )

                except Exception as e:
                    logger.warning(f"Memgraph batch {batch_num} indexing failed: {e}")
                    # Continue with other batches even if one fails

            # Success exit logging
            logger.info(
                f"EXIT _index_in_memgraph_batch: SUCCESS - indexed={indexed_count}/{len(files_data)} files"
            )
            return indexed_count

        except Exception as e:
            logger.error(
                f"EXIT _index_in_memgraph_batch: ERROR - {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            return 0  # Return 0 instead of raising to allow graceful degradation

    async def _warm_cache(
        self, project_name: str, intelligence_results: List[Dict[str, Any]]
    ) -> None:
        """
        Pre-warm cache with common queries.

        Args:
            project_name: Project name
            intelligence_results: Intelligence results
        """
        try:
            # Extract common concepts
            all_concepts = set()
            for result in intelligence_results:
                metadata = result.get("metadata", {})
                concepts = metadata.get("concepts", [])
                all_concepts.update(concepts[:5])  # Top 5 concepts

            # Generate common queries
            common_queries = [
                f"{concept} in {project_name}" for concept in list(all_concepts)[:10]
            ]

            # Execute searches to warm cache
            logger.info(f"Warming cache with {len(common_queries)} common queries...")

            for query in common_queries:
                try:
                    await self.search_files(query, projects=[project_name], limit=5)
                except Exception as e:
                    logger.warning(f"Cache warming query failed: {query} - {e}")

            logger.info("✅ Cache warming complete")

        except Exception as e:
            logger.warning(f"Cache warming failed: {e}")

    async def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using configured provider (Ollama/OpenAI/Google) with rate limiting.

        Uses the configured embedding model (e.g., nomic-embed-text for Ollama, text-embedding-3-small for OpenAI)
        with semaphore rate limiting to prevent overwhelming the API. Falls back to zero vector if unavailable.

        Args:
            text: Text to embed (file path + metadata, truncated to 8000 chars)

        Returns:
            Embedding vector with dimensions matching the configured model
            (768 for nomic-embed-text, 1024 for mxbai-embed-large, 1536 for text-embedding-3-small)

        Performance:
        - Rate limited: max 100 concurrent calls
        - Fallback: zero vector if API unavailable
        - Truncation: 8000 chars to avoid token limits

        Metrics:
        - Increments embeddings_generated on success
        - Increments embeddings_fallback on failure or unavailable client
        """
        # Truncate text to avoid token limits (8000 chars ~= 2000 tokens)
        truncated_text = text[:8000] if len(text) > 8000 else text

        # Entry logging (debug level to avoid noise)
        logger.debug(
            f"ENTER _generate_embedding: text_length={len(truncated_text)}, "
            f"model={self.embedding_model}, dimensions={self.embedding_dimensions}"
        )

        # Try primary LLM provider service first (if available)
        if self.embedding_model and get_llm_client is not None:
            async with self._embedding_semaphore:
                try:
                    logger.debug(
                        f"Attempting embedding generation with LLM provider service"
                    )
                    # Use the unified LLM provider service (supports Ollama, OpenAI, Google)
                    async with get_llm_client(use_embedding_provider=True) as client:
                        # For OpenAI text-embedding-3-* models, include dimensions parameter
                        if "text-embedding-3-" in self.embedding_model:
                            response = await client.embeddings.create(
                                model=self.embedding_model,
                                input=truncated_text,
                                dimensions=self.embedding_dimensions,
                            )
                        else:
                            # Other models (Ollama, Google) don't support dimensions parameter
                            response = await client.embeddings.create(
                                model=self.embedding_model, input=truncated_text
                            )

                        embedding = response.data[0].embedding
                        self.metrics["embeddings_generated"] += 1
                        logger.debug(
                            f"EXIT _generate_embedding: SUCCESS - model={self.embedding_model}, "
                            f"dimensions={len(embedding)}"
                        )
                        return embedding

                except Exception as e:
                    logger.warning(
                        f"⚠️  LLM provider service embedding failed: {e}. "
                        f"Trying direct Ollama HTTP fallback..."
                    )

        # Fallback to direct embedding service HTTP client (more reliable, uses environment variables)
        try:
            embedding_model_url = os.getenv(
                "EMBEDDING_MODEL_URL", "http://192.168.86.201:8002"
            )
            embedding_model = self.embedding_model or os.getenv(
                "EMBEDDING_MODEL", "nomic-embed-text"
            )

            logger.info(
                f"🔄 Using direct embedding service HTTP client | url={embedding_model_url} | "
                f"model={embedding_model}"
            )

            async with self._embedding_semaphore:
                if not self.httpx_client:
                    self.httpx_client = httpx.AsyncClient(timeout=30.0)

                # Call embedding service API directly
                request_payload = {"model": embedding_model, "prompt": truncated_text}

                logger.debug(
                    f"Sending embedding request | url={embedding_model_url}/api/embeddings | "
                    f"model={embedding_model} | text_length={len(truncated_text)}"
                )

                response = await self.httpx_client.post(
                    f"{embedding_model_url}/api/embeddings",
                    json=request_payload,
                    timeout=30.0,
                )
                response.raise_for_status()

                result = response.json()
                embedding = result.get("embedding", [])

                if not embedding or all(v == 0.0 for v in embedding):
                    raise ValueError("Ollama returned empty or zero-valued embedding")

                self.metrics["embeddings_generated"] += 1

                # Update dimensions if different
                if len(embedding) != self.embedding_dimensions:
                    logger.warning(
                        f"Embedding dimensions mismatch: expected {self.embedding_dimensions}, "
                        f"got {len(embedding)}. Updating dimensions."
                    )
                    self.embedding_dimensions = len(embedding)

                logger.debug(
                    f"EXIT _generate_embedding: SUCCESS - model={ollama_model}, "
                    f"dimensions={len(embedding)}"
                )
                return embedding

        except httpx.HTTPStatusError as e:
            logger.error(
                f"EXIT _generate_embedding: ERROR - HTTPStatusError: status={e.response.status_code}",
                exc_info=True,
            )
        except Exception as e:
            logger.error(
                f"EXIT _generate_embedding: ERROR - {type(e).__name__}: {str(e)}",
                exc_info=True,
            )

        # Ultimate fallback: return zero vector (with warning)
        logger.error(
            f"EXIT _generate_embedding: FALLBACK - Using zero vector. "
            f"THIS WILL BREAK SEMANTIC SEARCH! Check embedding service at {os.getenv('EMBEDDING_MODEL_URL', 'http://192.168.86.201:8002')}"
        )
        self.metrics["embeddings_fallback"] += 1
        return [0.0] * self.embedding_dimensions

    async def _search_in_qdrant(
        self,
        query: str,
        projects: Optional[List[str]] = None,
        min_quality_score: float = 0.0,
        limit: int = 10,
    ) -> List[FileMatch]:
        """
        Search files in Qdrant using vector similarity.

        Args:
            query: Search query
            projects: Optional project filters
            min_quality_score: Minimum quality threshold
            limit: Maximum results

        Returns:
            List of FileMatch results
        """
        try:
            if not self.qdrant_client:
                raise IndexingError("Qdrant client not initialized")

            # Generate query embedding from search query
            # Include project filter context for better semantic matching
            project_context = f" in projects: {', '.join(projects)}" if projects else ""
            query_text = f"Search: {query}{project_context}"
            query_vector = await self._generate_embedding(query_text)

            # Build filter using proper Qdrant models
            q_filter = None
            must = []
            if projects:
                must.append(
                    FieldCondition(key="project_name", match=MatchAny(any=projects))
                )
            if min_quality_score > 0.0:
                must.append(
                    FieldCondition(
                        key="quality_score", range=Range(gte=min_quality_score)
                    )
                )
            if must:
                q_filter = Filter(must=must)

            # Search (wrap in asyncio.to_thread to avoid blocking event loop)
            search_results = await asyncio.to_thread(
                self.qdrant_client.search,
                collection_name="archon_vectors",
                query_vector=query_vector,
                query_filter=q_filter,
                limit=limit,
            )

            # Convert to FileMatch
            matches = []
            for result in search_results:
                payload = result.payload

                match = FileMatch(
                    file_path=payload["absolute_path"],
                    relative_path=payload["relative_path"],
                    project_name=payload["project_name"],
                    confidence=result.score,
                    quality_score=payload.get("quality_score", 0.0),
                    onex_type=payload.get("onex_type"),
                    concepts=payload.get("concepts", []),
                    themes=payload.get("themes", []),
                    why=f"Semantic match with score {result.score:.2f}",
                )
                matches.append(match)

            return matches

        except Exception as e:
            logger.error(f"Qdrant search failed: {e}", exc_info=True)
            return []

    # ==========================================================================
    # Cache Helper Methods
    # ==========================================================================

    def _get_cache_key(
        self,
        query: str,
        projects: Optional[List[str]],
        min_quality_score: float,
        limit: int,
    ) -> str:
        """Generate cache key for search query."""
        key_parts = [
            query,
            str(sorted(projects)) if projects else "all",
            str(min_quality_score),
            str(limit),
        ]
        key_string = ":".join(key_parts)
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()
        return f"file_location:query:{key_hash}"

    async def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get value from Valkey cache."""
        try:
            if not self.valkey_client:
                return None

            value = await self.valkey_client.get(key)
            if value:
                import json

                return json.loads(value)
            return None

        except (OSError, ConnectionError, TimeoutError) as e:
            logger.warning(f"Cache get failed (connection/timeout): {e}")
            return None
        except Exception as e:
            logger.warning(f"Cache get failed (unexpected error): {e}", exc_info=True)
            return None

    async def _set_in_cache(
        self, key: str, value: Dict[str, Any], ttl: Optional[int] = None
    ) -> None:
        """
        Set value in Valkey cache with configurable TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (default: from config)
        """
        try:
            if not self.valkey_client:
                return

            import json

            # Use config-based TTL if not specified
            if ttl is None:
                ttl = int(get_cache_timeout("search_results"))

            await self.valkey_client.setex(key, ttl, json.dumps(value))

        except (OSError, ConnectionError, TimeoutError) as e:
            logger.warning(f"Cache set failed (connection/timeout): {e}")
        except Exception as e:
            logger.warning(f"Cache set failed (unexpected error): {e}", exc_info=True)

    # ==========================================================================
    # Client Lifecycle Management
    # ==========================================================================

    async def _initialize_clients(self) -> None:
        """Initialize all service clients."""
        logger.info("ENTER _initialize_clients")

        try:
            # Phase 0 removed - FileDiscoveryService no longer used (inline content provided via Kafka)

            # MetadataStamping client (use HTTP fallback if MCP client not available)
            if not self.stamping_client and not self.use_http_fallback:
                if MetadataStampingClient is not None:
                    try:
                        self.stamping_client = MetadataStampingClient(
                            base_url=self.stamping_url,
                            intelligence_url=self.intelligence_url,
                        )
                        await self.stamping_client.connect()
                        logger.debug("MetadataStamping MCP client initialized")
                    except Exception as e:
                        logger.warning(
                            f"MetadataStamping client initialization failed: {e}. "
                            "Using HTTP fallback"
                        )
                        self.stamping_client = None
                        self.use_http_fallback = True
                else:
                    logger.info(
                        "MetadataStampingClient not available - using HTTP fallback"
                    )
                    # Mark as using HTTP fallback (will use httpx_client)
                    self.stamping_client = None
                    self.use_http_fallback = True

            # Qdrant client
            if not self.qdrant_client:
                self.qdrant_client = QdrantClient(url=self.qdrant_url)
                logger.debug("Qdrant client initialized")

            # Memgraph driver (Neo4j AsyncGraphDatabase)
            if not self.memgraph_driver:
                try:
                    self.memgraph_driver = AsyncGraphDatabase.driver(
                        self.memgraph_uri,
                        auth=None,  # Memgraph typically runs without auth in Docker
                    )
                    # Test connection
                    async with self.memgraph_driver.session() as session:
                        await session.run("RETURN 1")
                    logger.debug("Memgraph driver initialized")
                except Exception as e:
                    logger.warning(f"Memgraph driver initialization failed: {e}")
                    self.memgraph_driver = None

            # Valkey client (Redis)
            if not self.valkey_client:
                try:
                    import redis.asyncio as redis

                    self.valkey_client = redis.from_url(
                        self.valkey_url, encoding="utf-8", decode_responses=True
                    )
                    logger.debug("Valkey client initialized")
                except Exception as e:
                    logger.warning(f"Valkey client initialization failed: {e}")
                    self.valkey_client = None

            # HTTP client
            if not self.httpx_client:
                timeout = get_http_timeout("external")
                self.httpx_client = httpx.AsyncClient(timeout=timeout)
                logger.debug("HTTP client initialized")

            # Initialize embedding model and dimensions using LLM provider service
            if not self.embedding_model:
                try:
                    if get_embedding_model is None:
                        logger.warning(
                            "⚠️  LLM provider service not available - using environment configuration. "
                            "Check imports and dependencies."
                        )
                        # Keep environment-configured values
                        if self.embedding_model is None:
                            self.embedding_model = os.getenv("EMBEDDING_MODEL")
                        # embedding_dimensions already read from env in __init__
                    else:
                        # Get configured embedding model from LLM provider
                        detected_model = await get_embedding_model()

                        # Only override if we got a valid model and it differs from env
                        if detected_model:
                            self.embedding_model = detected_model

                        # Always trust EMBEDDING_DIMENSIONS from environment
                        # This ensures user configuration is respected
                        env_dimensions = os.getenv("EMBEDDING_DIMENSIONS")
                        if env_dimensions:
                            self.embedding_dimensions = int(env_dimensions)
                            logger.info(
                                f"✅ Embedding configuration from environment: "
                                f"model={self.embedding_model} | dimensions={self.embedding_dimensions}"
                            )
                        else:
                            logger.warning(
                                f"EMBEDDING_DIMENSIONS not set in environment, using default: {self.embedding_dimensions}"
                            )

                        logger.info(
                            f"✅ Embedding model initialized: {self.embedding_model} "
                            f"({self.embedding_dimensions} dimensions) - semantic search enabled"
                        )
                except Exception as e:
                    logger.error(
                        f"Failed to initialize embedding model: {e}", exc_info=True
                    )
                    # Keep environment-configured values as fallback
                    if self.embedding_model is None:
                        self.embedding_model = os.getenv("EMBEDDING_MODEL")
                    # embedding_dimensions already read from env in __init__

            logger.info(f"EXIT _initialize_clients: SUCCESS - all clients initialized")

        except Exception as e:
            logger.error(
                f"EXIT _initialize_clients: ERROR - {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            raise

    async def _cleanup_clients(self) -> None:
        """Cleanup all service clients."""
        logger.info("ENTER _cleanup_clients")

        try:
            # Phase 0 removed - FileDiscoveryService no longer used

            # Only cleanup stamping_client if it's a real client (not using HTTP fallback)
            if self.stamping_client and not self.use_http_fallback:
                try:
                    await self.stamping_client.close()
                except Exception as e:
                    logger.warning(f"Stamping client cleanup warning: {e}")
                self.stamping_client = None

            if self.memgraph_driver:
                try:
                    await self.memgraph_driver.close()
                except Exception as e:
                    logger.warning(f"Memgraph driver cleanup warning: {e}")
                self.memgraph_driver = None

            if self.valkey_client:
                try:
                    await self.valkey_client.aclose()
                except AttributeError:
                    # Older redis versions use close() instead of aclose()
                    self.valkey_client.close()
                self.valkey_client = None

            if self.httpx_client:
                await self.httpx_client.aclose()
                self.httpx_client = None

            # Qdrant client doesn't need cleanup

            logger.info("EXIT _cleanup_clients: SUCCESS - all clients cleaned up")

        except Exception as e:
            logger.error(
                f"EXIT _cleanup_clients: ERROR - {type(e).__name__}: {str(e)}",
                exc_info=True,
            )

    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive bridge metrics."""
        total_embeddings = (
            self.metrics["embeddings_generated"] + self.metrics["embeddings_fallback"]
        )
        return {
            **self.metrics,
            "cache_hit_rate": (
                self.metrics["cache_hits"]
                / (self.metrics["cache_hits"] + self.metrics["cache_misses"])
                if (self.metrics["cache_hits"] + self.metrics["cache_misses"]) > 0
                else 0.0
            ),
            "embedding_success_rate": (
                self.metrics["embeddings_generated"] / total_embeddings
                if total_embeddings > 0
                else 0.0
            ),
        }
