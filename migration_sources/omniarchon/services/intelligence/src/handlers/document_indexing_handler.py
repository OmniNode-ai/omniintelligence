"""
Document Indexing Event Handler

Handles DOCUMENT_INDEX_REQUESTED events and orchestrates full intelligence pipeline:
1. Metadata stamping (BLAKE3 hash, deduplication)
2. Entity extraction (AST parsing, functions, classes)
3. Vector indexing (semantic embeddings for RAG)
4. Knowledge graph (entity relationships)
5. Quality assessment (ONEX compliance scoring)

Created: 2025-10-22
Purpose: Event-driven document intelligence pipeline with multi-service orchestration
"""

import asyncio
import hashlib
import logging
import time
from typing import Any, Dict, Optional
from uuid import UUID

import httpx
from src.events.models.document_indexing_events import (
    EnumDocumentIndexEventType,
    EnumIndexingErrorCode,
    create_completed_event,
    create_failed_event,
)
from src.handlers.base_response_publisher import BaseResponsePublisher

logger = logging.getLogger(__name__)


class DocumentIndexingHandler(BaseResponsePublisher):
    """
    Handle DOCUMENT_INDEX_REQUESTED events and orchestrate full intelligence pipeline.

    This handler implements parallel service orchestration for document indexing,
    consuming indexing requests from the event bus and publishing results back.

    Event Flow:
        1. Consume DOCUMENT_INDEX_REQUESTED event
        2. Extract document parameters (path, content, language, options)
        3. Orchestrate 5 services in parallel:
           - Metadata stamping (Bridge:8057)
           - Entity extraction (LangExtract:8156)
           - Vector indexing (Qdrant:6333)
           - Knowledge graph storage (Memgraph:7687)
           - Quality assessment (Intelligence:8053)
        4. Publish DOCUMENT_INDEX_COMPLETED (success) or DOCUMENT_INDEX_FAILED (error)

    Topics:
        - Request: dev.archon-intelligence.intelligence.document-index-requested.v1
        - Completed: dev.archon-intelligence.intelligence.document-index-completed.v1
        - Failed: dev.archon-intelligence.intelligence.document-index-failed.v1

    Services:
        - Bridge (8057): BLAKE3 content hashing and metadata stamping
        - LangExtract (8156): Entity extraction and AST parsing
        - Qdrant (6333): Vector indexing for semantic search
        - Memgraph (7687): Knowledge graph entity relationships
        - Intelligence (8053): Quality assessment and ONEX compliance
    """

    # Topic constants
    REQUEST_TOPIC = "dev.archon-intelligence.intelligence.document-index-requested.v1"
    COMPLETED_TOPIC = "dev.archon-intelligence.intelligence.document-index-completed.v1"
    FAILED_TOPIC = "dev.archon-intelligence.intelligence.document-index-failed.v1"

    # Service endpoints
    BRIDGE_URL = "http://localhost:8057"
    LANGEXTRACT_URL = "http://localhost:8156"
    QDRANT_URL = "http://localhost:6333"
    MEMGRAPH_URI = "bolt://localhost:7687"
    INTELLIGENCE_URL = "http://localhost:8053"

    # Timeouts (in seconds)
    METADATA_TIMEOUT = 5.0
    ENTITY_TIMEOUT = 10.0
    VECTOR_TIMEOUT = 10.0
    KNOWLEDGE_GRAPH_TIMEOUT = 10.0
    QUALITY_TIMEOUT = 10.0

    def __init__(
        self,
        bridge_url: Optional[str] = None,
        langextract_url: Optional[str] = None,
        qdrant_url: Optional[str] = None,
        memgraph_uri: Optional[str] = None,
        intelligence_url: Optional[str] = None,
    ):
        """
        Initialize Document Indexing handler.

        Args:
            bridge_url: Optional Bridge service URL
            langextract_url: Optional LangExtract service URL
            qdrant_url: Optional Qdrant service URL
            memgraph_uri: Optional Memgraph connection URI
            intelligence_url: Optional Intelligence service URL
        """
        super().__init__()

        # Service URLs (allow override for testing)
        self.bridge_url = bridge_url or self.BRIDGE_URL
        self.langextract_url = langextract_url or self.LANGEXTRACT_URL
        self.qdrant_url = qdrant_url or self.QDRANT_URL
        self.memgraph_uri = memgraph_uri or self.MEMGRAPH_URI
        self.intelligence_url = intelligence_url or self.INTELLIGENCE_URL

        # HTTP client for service calls
        self.http_client: Optional[httpx.AsyncClient] = None

        # Metrics
        self.metrics = {
            "events_handled": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
            "indexing_successes": 0,
            "indexing_failures": 0,
            "cache_hits": 0,
            "service_failures": {
                "metadata_stamping": 0,
                "entity_extraction": 0,
                "vector_indexing": 0,
                "knowledge_graph": 0,
                "quality_assessment": 0,
            },
        }

    async def _ensure_http_client(self) -> None:
        """Ensure HTTP client is initialized."""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=30.0)

    async def _close_http_client(self) -> None:
        """Close HTTP client."""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None

    def can_handle(self, event_type: str) -> bool:
        """
        Check if this handler can process the given event type.

        Args:
            event_type: Event type string

        Returns:
            True if event type is DOCUMENT_INDEX_REQUESTED
        """
        return event_type in [
            EnumDocumentIndexEventType.DOCUMENT_INDEX_REQUESTED.value,
            "DOCUMENT_INDEX_REQUESTED",
            "intelligence.document-index-requested",
            "omninode.intelligence.event.document_index_requested.v1",  # Full event type from Kafka
        ]

    async def handle_event(self, event: Any) -> bool:
        """
        Handle DOCUMENT_INDEX_REQUESTED event.

        Extracts document parameters from event payload, orchestrates full
        intelligence pipeline across 5 services, and publishes appropriate response.

        Args:
            event: Event envelope with DOCUMENT_INDEX_REQUESTED payload

        Returns:
            True if handled successfully, False otherwise
        """
        start_time = time.perf_counter()
        correlation_id = None

        try:
            # Extract event data
            correlation_id = self._get_correlation_id(event)
            payload = self._get_payload(event)

            # Extract required fields from payload
            source_path = payload.get("source_path")
            content = payload.get("content")
            language = payload.get("language", "python")
            project_id = payload.get("project_id")
            project_name = payload.get(
                "project_name"
            )  # Extract project_name from payload
            repository_url = payload.get("repository_url")
            commit_sha = payload.get("commit_sha")
            indexing_options = payload.get("indexing_options", {})
            user_id = payload.get("user_id")

            # Validate required fields
            if not source_path:
                logger.error(
                    f"Missing source_path in DOCUMENT_INDEX_REQUESTED event {correlation_id}"
                )
                await self._publish_failed_response(
                    correlation_id=correlation_id,
                    source_path="unknown",
                    error_code=EnumIndexingErrorCode.INVALID_INPUT,
                    error_message="Missing required field: source_path",
                    retry_allowed=False,
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )
                self.metrics["events_failed"] += 1
                self.metrics["indexing_failures"] += 1
                return False

            # If content not provided, we'd need to read from source_path
            # For now, require content to be provided
            if not content:
                logger.error(
                    f"Missing content in DOCUMENT_INDEX_REQUESTED event {correlation_id}"
                )
                await self._publish_failed_response(
                    correlation_id=correlation_id,
                    source_path=source_path,
                    error_code=EnumIndexingErrorCode.INVALID_INPUT,
                    error_message="Missing required field: content",
                    retry_allowed=False,
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )
                self.metrics["events_failed"] += 1
                self.metrics["indexing_failures"] += 1
                return False

            logger.info(
                f"Processing DOCUMENT_INDEX_REQUESTED | correlation_id={correlation_id} | "
                f"source_path={source_path} | language={language} | "
                f"content_length={len(content)} | project_id={project_id} | project_name={project_name}"
            )

            # Perform document indexing with service orchestration
            indexing_result = await self._process_document_indexing(
                content=content,
                source_path=source_path,
                language=language,
                project_id=project_id,
                project_name=project_name,  # Pass project_name to indexing function
                repository_url=repository_url,
                commit_sha=commit_sha,
                indexing_options=indexing_options,
                user_id=user_id,
            )

            # Publish success response
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_completed_response(
                correlation_id=correlation_id,
                indexing_result=indexing_result,
                source_path=source_path,
                processing_time_ms=duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["indexing_successes"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms

            if indexing_result.get("cache_hit", False):
                self.metrics["cache_hits"] += 1

            logger.info(
                f"DOCUMENT_INDEX_COMPLETED published | correlation_id={correlation_id} | "
                f"document_hash={indexing_result.get('document_hash', 'N/A')[:16]}... | "
                f"entities_extracted={indexing_result.get('entities_extracted', 0)} | "
                f"processing_time_ms={duration_ms:.2f}"
            )

            return True

        except Exception as e:
            logger.error(
                f"Document indexing handler failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )

            # Publish error response
            try:
                if correlation_id:
                    payload = self._get_payload(event) if event else {}
                    source_path = payload.get("source_path", "unknown")

                    duration_ms = (time.perf_counter() - start_time) * 1000
                    await self._publish_failed_response(
                        correlation_id=correlation_id,
                        source_path=source_path,
                        error_code=EnumIndexingErrorCode.INTERNAL_ERROR,
                        error_message=f"Document indexing failed: {str(e)}",
                        retry_allowed=True,
                        processing_time_ms=duration_ms,
                        error_details={"exception_type": type(e).__name__},
                    )
            except Exception as publish_error:
                logger.error(
                    f"Failed to publish error response | correlation_id={correlation_id} | "
                    f"error={publish_error}",
                    exc_info=True,
                )

            self.metrics["events_failed"] += 1
            self.metrics["indexing_failures"] += 1
            return False

    async def _process_document_indexing(
        self,
        content: str,
        source_path: str,
        language: str,
        project_id: Optional[str],
        project_name: Optional[str],
        repository_url: Optional[str],
        commit_sha: Optional[str],
        indexing_options: Dict[str, Any],
        user_id: Optional[str],
    ) -> Dict[str, Any]:
        """
        Process document through full intelligence pipeline.

        Orchestrates 5 services with graceful degradation:
        1. Metadata stamping (required for deduplication)
        2. Entity extraction, Vector indexing, Knowledge graph, Quality (parallel, optional)

        Args:
            content: Document content to index
            source_path: Path to the document
            language: Programming language
            project_id: Optional project identifier
            repository_url: Optional repository URL
            commit_sha: Optional commit SHA
            indexing_options: Indexing configuration options
            user_id: Optional user identifier

        Returns:
            Dictionary with indexing results and service timings

        Raises:
            Exception: If critical services fail (metadata stamping)
        """
        await self._ensure_http_client()
        service_timings = {}

        # Step 1: Metadata stamping (required for deduplication)
        logger.info(f"Step 1/5: Metadata stamping | source_path={source_path}")
        metadata_start = time.perf_counter()

        try:
            metadata_result = await self._stamp_metadata(content, source_path)
            service_timings["metadata_stamping_ms"] = (
                time.perf_counter() - metadata_start
            ) * 1000

            document_hash = metadata_result.get("hash", "")
            cache_hit = metadata_result.get("dedupe_status") == "duplicate"

            # If cache hit and force_reindex not set, return early
            if cache_hit and not indexing_options.get("force_reindex", False):
                logger.info(f"Cache hit for document | hash={document_hash[:16]}...")
                return {
                    "document_hash": document_hash,
                    "entity_ids": [],
                    "vector_ids": [],
                    "quality_score": None,
                    "onex_compliance": None,
                    "entities_extracted": 0,
                    "relationships_created": 0,
                    "chunks_indexed": 0,
                    "service_timings": service_timings,
                    "cache_hit": True,
                    "reindex_required": False,
                }
        except Exception as e:
            logger.error(f"Metadata stamping failed: {e}", exc_info=True)
            self.metrics["service_failures"]["metadata_stamping"] += 1
            raise Exception(f"Metadata stamping failed: {str(e)}")

        # Step 2-5: Parallel execution of remaining services with graceful degradation
        logger.info("Steps 2-5: Parallel execution (entity, quality, vector, KG)")

        tasks = []
        task_names = []

        # Entity extraction (if not skipped)
        if not indexing_options.get("skip_entity_extraction", False):
            tasks.append(self._extract_entities(content, source_path, language))
            task_names.append("entity_extraction")

        # Quality assessment (if not skipped)
        if not indexing_options.get("skip_quality_assessment", False):
            tasks.append(self._assess_quality(content, source_path, language))
            task_names.append("quality_assessment")

        # Execute services in parallel with graceful degradation
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        entity_result = None
        quality_result = None

        for i, (result, name) in enumerate(zip(results, task_names)):
            if isinstance(result, Exception):
                logger.warning(f"Service {name} failed: {result}")
                self.metrics["service_failures"][name] += 1
                continue

            if name == "entity_extraction":
                entity_result = result
                service_timings["entity_extraction_ms"] = result.get("timing_ms", 0)
            elif name == "quality_assessment":
                quality_result = result
                service_timings["quality_assessment_ms"] = result.get("timing_ms", 0)

        # Step 3: Vector indexing (depends on entity extraction for chunking)
        vector_ids = []
        chunks_indexed = 0
        if not indexing_options.get("skip_vector_indexing", False) and entity_result:
            try:
                logger.info("Step 3: Vector indexing")
                vector_start = time.perf_counter()

                # Chunk content for vector indexing
                chunk_size = indexing_options.get("chunk_size", 1000)
                chunk_overlap = indexing_options.get("chunk_overlap", 200)
                chunks = self._chunk_content(content, chunk_size, chunk_overlap)

                vector_result = await self._index_vectors(
                    chunks=chunks,
                    source_path=source_path,
                    metadata={
                        "language": language,
                        "project_id": project_id,
                        "project_name": project_name,
                    },
                )

                vector_ids = vector_result.get("vector_ids", [])
                chunks_indexed = len(vector_ids)
                service_timings["vector_indexing_ms"] = (
                    time.perf_counter() - vector_start
                ) * 1000
            except Exception as e:
                logger.warning(f"Vector indexing failed (non-critical): {e}")
                self.metrics["service_failures"]["vector_indexing"] += 1

        # Step 4: Knowledge graph (depends on entity extraction)
        entity_ids = []
        relationships_created = 0
        if not indexing_options.get("skip_knowledge_graph", False) and entity_result:
            try:
                logger.info("Step 4: Knowledge graph indexing")
                kg_start = time.perf_counter()

                entities = entity_result.get("entities", [])
                relationships = entity_result.get("relationships", [])

                kg_result = await self._index_knowledge_graph(
                    entities=entities,
                    relationships=relationships,
                    source_path=source_path,
                    project_name=project_name,
                )

                entity_ids = kg_result.get("entity_ids", [])
                relationships_created = kg_result.get("relationships_created", 0)
                service_timings["knowledge_graph_ms"] = (
                    time.perf_counter() - kg_start
                ) * 1000
            except Exception as e:
                logger.warning(f"Knowledge graph indexing failed (non-critical): {e}")
                self.metrics["service_failures"]["knowledge_graph"] += 1

        # Aggregate results
        return {
            "document_hash": document_hash,
            "entity_ids": entity_ids,
            "vector_ids": vector_ids,
            "quality_score": (
                quality_result.get("quality_score") if quality_result else None
            ),
            "onex_compliance": (
                quality_result.get("onex_compliance") if quality_result else None
            ),
            "entities_extracted": (
                len(entity_result.get("entities", [])) if entity_result else 0
            ),
            "relationships_created": relationships_created,
            "chunks_indexed": chunks_indexed,
            "service_timings": service_timings,
            "cache_hit": False,
            "reindex_required": False,
        }

    async def _stamp_metadata(self, content: str, source_path: str) -> Dict[str, Any]:
        """
        Call Bridge service for metadata stamping.

        Args:
            content: Document content
            source_path: Document path

        Returns:
            Dictionary with hash, timestamp, dedupe_status
        """
        response = await self.http_client.post(
            f"{self.bridge_url}/api/stamp-metadata",
            json={"content": content, "source_path": source_path},
            timeout=self.METADATA_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    async def _extract_entities(
        self, content: str, source_path: str, language: str
    ) -> Dict[str, Any]:
        """
        Call LangExtract service for entity extraction.

        Args:
            content: Document content
            source_path: Document path
            language: Programming language

        Returns:
            Dictionary with entities, relationships, timing_ms
        """
        start = time.perf_counter()

        # Call correct endpoint with proper request format
        response = await self.http_client.post(
            f"{self.langextract_url}/extract/document",
            json={
                "document_path": source_path,
                "content": content,
                "extraction_options": {
                    "extract_code_patterns": True,
                    "extract_documentation_concepts": True,
                    "include_semantic_analysis": True,
                    "include_relationship_extraction": True,
                    "schema_hints": {},
                    "semantic_context": "",
                },
                "update_knowledge_graph": False,
                "emit_events": False,
            },
            timeout=self.ENTITY_TIMEOUT,
        )
        response.raise_for_status()
        langextract_response = response.json()

        # Transform LangExtract response to expected format
        # LangExtract returns: {enriched_entities, relationships, extraction_statistics}
        # We need: {entities, relationships}
        result = {
            "entities": [
                {
                    "entity_id": entity.get(
                        "entity_id", f"entity_{hash(entity.get('name', ''))}"
                    ),
                    "name": entity.get("name", ""),
                    "entity_type": entity.get("entity_type", "CONCEPT"),
                    "description": entity.get("description", ""),
                    "source_path": source_path,
                    "confidence_score": entity.get("confidence_score", 0.5),
                    "source_line_number": entity.get("line_number"),
                    "properties": entity.get("properties", {}),
                }
                for entity in langextract_response.get("enriched_entities", [])
            ],
            "relationships": langextract_response.get("relationships", []),
            "timing_ms": (time.perf_counter() - start) * 1000,
        }

        logger.info(
            f"📊 [ENTITY EXTRACT] LangExtract response | "
            f"entities={len(result['entities'])} | "
            f"relationships={len(result['relationships'])} | "
            f"path={source_path}"
        )

        return result

    async def _assess_quality(
        self, content: str, source_path: str, language: str
    ) -> Dict[str, Any]:
        """
        Call Intelligence service for quality assessment.

        Args:
            content: Document content
            source_path: Document path
            language: Programming language

        Returns:
            Dictionary with quality_score, onex_compliance, timing_ms
        """
        start = time.perf_counter()

        response = await self.http_client.post(
            f"{self.intelligence_url}/assess/code",
            json={
                "content": content,
                "source_path": source_path,
                "language": language,
            },
            timeout=self.QUALITY_TIMEOUT,
        )
        response.raise_for_status()
        result = response.json()

        result["timing_ms"] = (time.perf_counter() - start) * 1000
        return result

    async def _index_vectors(
        self, chunks: list[str], source_path: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Index document chunks in Qdrant vector database.

        Note: This is a simplified implementation. Real implementation would:
        - Generate embeddings using OpenAI or local model
        - Create collection if not exists
        - Upload points with proper IDs

        Args:
            chunks: Content chunks to index
            source_path: Document path
            metadata: Additional metadata

        Returns:
            Dictionary with vector_ids
        """
        # Placeholder implementation
        # Real implementation would call Qdrant API or use qdrant-client
        logger.info(f"Vector indexing: {len(chunks)} chunks for {source_path}")

        # Simulate vector IDs
        vector_ids = [
            f"vec-{i}-{hashlib.blake2b(chunk.encode()).hexdigest()[:16]}"
            for i, chunk in enumerate(chunks)
        ]

        return {"vector_ids": vector_ids}

    async def _index_knowledge_graph(
        self,
        entities: list[Dict[str, Any]],
        relationships: list[Dict[str, Any]],
        source_path: str,
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Index entities and relationships in Memgraph knowledge graph.

        Args:
            entities: Entities to index (from LangExtract)
            relationships: Relationships to create (from LangExtract)
            source_path: Document path
            project_name: Optional project name for File node metadata

        Returns:
            Dictionary with entity_ids, relationships_created
        """
        import os

        from src.models.entity_models import (
            EntityMetadata,
            EntityType,
            KnowledgeEntity,
            KnowledgeRelationship,
            RelationshipType,
        )
        from src.storage.memgraph_adapter import MemgraphKnowledgeAdapter

        if not entities and not relationships:
            logger.info(
                f"📊 [MEMGRAPH] No entities or relationships to index | "
                f"source_path={source_path}"
            )
            return {"entity_ids": [], "relationships_created": 0}

        # Initialize adapter
        memgraph_uri = os.getenv("MEMGRAPH_URI", "bolt://memgraph:7687")
        adapter = MemgraphKnowledgeAdapter(uri=memgraph_uri)

        try:
            await adapter.initialize()

            entity_ids = []
            relationships_created = 0

            # Convert and store entities
            if entities:
                try:
                    logger.info(
                        f"📝 [MEMGRAPH] Converting {len(entities)} entities | "
                        f"source_path={source_path}"
                    )

                    entity_objects = []
                    for e in entities:
                        # Map entity type (handle case differences)
                        entity_type_str = e.get("entity_type", "CONCEPT").upper()
                        try:
                            entity_type = EntityType(entity_type_str)
                        except ValueError:
                            logger.warning(
                                f"⚠️ [MEMGRAPH] Unknown entity type: {entity_type_str}, "
                                f"defaulting to CONCEPT"
                            )
                            entity_type = EntityType.CONCEPT

                        # Create metadata
                        metadata = EntityMetadata(
                            file_hash=e.get("file_hash"),
                            extraction_method=e.get("extraction_method", "langextract"),
                            extraction_confidence=e.get("confidence_score", 0.0),
                        )

                        # Create KnowledgeEntity
                        entity_obj = KnowledgeEntity(
                            entity_id=e.get(
                                "entity_id",
                                f"entity-{hashlib.blake2b(e.get('name', '').encode()).hexdigest()[:16]}",
                            ),
                            name=e.get("name", ""),
                            entity_type=entity_type,
                            description=e.get("description", ""),
                            source_path=source_path,
                            confidence_score=e.get("confidence_score", 0.0),
                            source_line_number=e.get("source_line_number"),
                            properties=e.get("properties", {}),
                            metadata=metadata,
                            embedding=e.get("embedding"),
                        )
                        entity_objects.append(entity_obj)

                    # Store in Memgraph
                    stored_count = await adapter.store_entities(entity_objects)
                    entity_ids = [e.entity_id for e in entity_objects]

                    logger.info(
                        f"✅ [MEMGRAPH] Stored {stored_count}/{len(entities)} entities | "
                        f"source_path={source_path} | "
                        f"entity_ids={entity_ids[:5]}"  # Log first 5
                    )

                except Exception as e:
                    logger.error(
                        f"❌ [MEMGRAPH] Failed to store entities | "
                        f"source_path={source_path} | "
                        f"error={str(e)}",
                        exc_info=True,
                    )

            # Create File node with project metadata
            try:
                from pathlib import Path

                logger.info(
                    f"📁 [MEMGRAPH] Creating File node | "
                    f"source_path={source_path} | "
                    f"project_name={project_name or 'unknown'}"
                )

                # Generate stable file ID based on path
                path_hash = hashlib.md5(source_path.encode()).hexdigest()[:12]
                file_id = f"file_{path_hash}"

                # Extract file name and path components
                path_obj = Path(source_path)
                filename = path_obj.name

                # Build file_data dict with project_name
                file_data = {
                    "entity_id": file_id,
                    "name": filename,
                    "path": source_path,
                    "relative_path": source_path,
                    "project_name": project_name
                    or "unknown",  # ← FIX: Use project_name from event
                    "language": "unknown",  # Will be enriched by other handlers
                    "entity_count": len(entities) if entities else 0,
                }

                # Create File node in Memgraph
                file_created = await adapter.create_file_node(file_data)

                if file_created:
                    logger.info(
                        f"✅ [MEMGRAPH] File node created | "
                        f"file_id={file_id} | "
                        f"name={filename} | "
                        f"project_name={project_name or 'unknown'}"
                    )
                else:
                    logger.warning(
                        f"⚠️ [MEMGRAPH] File node creation returned False | "
                        f"file_id={file_id}"
                    )

            except Exception as e:
                logger.error(
                    f"❌ [MEMGRAPH] Failed to create File node | "
                    f"source_path={source_path} | "
                    f"error={str(e)}",
                    exc_info=True,
                )

            # Convert and store relationships
            if relationships:
                try:
                    logger.info(
                        f"🔗 [MEMGRAPH] Converting {len(relationships)} relationships | "
                        f"source_path={source_path}"
                    )

                    relationship_objects = []
                    for r in relationships:
                        # Map relationship type (handle case differences)
                        rel_type_str = r.get("relationship_type", "RELATES_TO").upper()
                        try:
                            rel_type = RelationshipType(rel_type_str)
                        except ValueError:
                            logger.warning(
                                f"⚠️ [MEMGRAPH] Unknown relationship type: {rel_type_str}, "
                                f"defaulting to RELATES_TO"
                            )
                            rel_type = RelationshipType.RELATES_TO

                        # Create KnowledgeRelationship
                        rel_obj = KnowledgeRelationship(
                            relationship_id=r.get(
                                "relationship_id",
                                f"rel-{hashlib.blake2b((r.get('source_entity_id', '') + r.get('target_entity_id', '')).encode()).hexdigest()[:16]}",
                            ),
                            source_entity_id=r.get("source_entity_id", ""),
                            target_entity_id=r.get("target_entity_id", ""),
                            relationship_type=rel_type,
                            confidence_score=r.get("confidence_score", 0.0),
                            properties=r.get("properties", {}),
                        )
                        relationship_objects.append(rel_obj)

                    # Store in Memgraph
                    relationships_created = await adapter.store_relationships(
                        relationship_objects
                    )

                    logger.info(
                        f"✅ [MEMGRAPH] Created {relationships_created}/{len(relationships)} relationships | "
                        f"source_path={source_path}"
                    )

                except Exception as e:
                    logger.error(
                        f"❌ [MEMGRAPH] Failed to create relationships | "
                        f"source_path={source_path} | "
                        f"error={str(e)}",
                        exc_info=True,
                    )

            return {
                "entity_ids": entity_ids,
                "relationships_created": relationships_created,
            }

        except Exception as e:
            logger.error(
                f"❌ [MEMGRAPH] Knowledge graph indexing failed | "
                f"source_path={source_path} | "
                f"error={str(e)}",
                exc_info=True,
            )
            return {"entity_ids": [], "relationships_created": 0}

        finally:
            await adapter.close()

    def _chunk_content(self, content: str, chunk_size: int, overlap: int) -> list[str]:
        """
        Chunk content for vector indexing.

        Args:
            content: Content to chunk
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks in characters

        Returns:
            List of content chunks
        """
        chunks = []
        start = 0

        while start < len(content):
            end = start + chunk_size
            chunk = content[start:end]
            chunks.append(chunk)
            start = end - overlap

        return chunks

    async def _publish_completed_response(
        self,
        correlation_id: UUID,
        indexing_result: Dict[str, Any],
        source_path: str,
        processing_time_ms: float,
    ) -> None:
        """
        Publish DOCUMENT_INDEX_COMPLETED event.

        Args:
            correlation_id: Correlation ID from request
            indexing_result: Indexing result dictionary
            source_path: Source file path
            processing_time_ms: Processing time in milliseconds
        """
        try:
            await self._ensure_router_initialized()

            # Create completed event using helper (returns ONEX-compliant envelope)
            event_envelope = create_completed_event(
                source_path=source_path,
                document_hash=indexing_result["document_hash"],
                entity_ids=indexing_result["entity_ids"],
                vector_ids=indexing_result["vector_ids"],
                entities_extracted=indexing_result["entities_extracted"],
                relationships_created=indexing_result["relationships_created"],
                chunks_indexed=indexing_result["chunks_indexed"],
                processing_time_ms=processing_time_ms,
                correlation_id=correlation_id,
                quality_score=indexing_result.get("quality_score"),
                onex_compliance=indexing_result.get("onex_compliance"),
                service_timings=indexing_result.get("service_timings", {}),
                cache_hit=indexing_result.get("cache_hit", False),
                reindex_required=indexing_result.get("reindex_required", False),
            )

            # Publish the ONEX-compliant envelope directly
            await self._router.publish(
                topic=self.COMPLETED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.info(
                f"Published DOCUMENT_INDEX_COMPLETED | topic={self.COMPLETED_TOPIC} | "
                f"correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(f"Failed to publish completed response: {e}", exc_info=True)
            raise

    async def _publish_failed_response(
        self,
        correlation_id: UUID,
        source_path: str,
        error_code: EnumIndexingErrorCode,
        error_message: str,
        failed_service: Optional[str] = None,
        retry_allowed: bool = False,
        retry_count: int = 0,
        processing_time_ms: float = 0.0,
        partial_results: Optional[Dict[str, Any]] = None,
        error_details: Optional[Dict[str, Any]] = None,
        suggested_action: Optional[str] = None,
    ) -> None:
        """
        Publish DOCUMENT_INDEX_FAILED event.

        Args:
            correlation_id: Correlation ID from request
            source_path: Source file path that failed
            error_code: Error code enum value
            error_message: Human-readable error message
            failed_service: Optional service that failed
            retry_allowed: Whether the operation can be retried
            retry_count: Number of retries attempted
            processing_time_ms: Time taken before failure
            partial_results: Optional partial results
            error_details: Optional error context
            suggested_action: Optional suggested action
        """
        try:
            await self._ensure_router_initialized()

            # Create failed event using helper (returns ONEX-compliant envelope)
            event_envelope = create_failed_event(
                source_path=source_path,
                error_message=error_message,
                error_code=error_code,
                correlation_id=correlation_id,
                failed_service=failed_service,
                retry_allowed=retry_allowed,
                retry_count=retry_count,
                processing_time_ms=processing_time_ms,
                partial_results=partial_results,
                error_details=error_details,
                suggested_action=suggested_action,
            )

            # Publish the ONEX-compliant envelope directly
            await self._router.publish(
                topic=self.FAILED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.warning(
                f"Published DOCUMENT_INDEX_FAILED | topic={self.FAILED_TOPIC} | "
                f"correlation_id={correlation_id} | error_code={error_code.value} | "
                f"error_message={error_message}"
            )

        except Exception as e:
            logger.error(f"Failed to publish failed response: {e}", exc_info=True)
            raise

    def get_handler_name(self) -> str:
        """Get handler name for registration."""
        return "DocumentIndexingHandler"

    def get_metrics(self) -> Dict[str, Any]:
        """Get handler metrics."""
        total_events = self.metrics["events_handled"] + self.metrics["events_failed"]
        success_rate = (
            self.metrics["events_handled"] / total_events if total_events > 0 else 1.0
        )
        avg_processing_time = (
            self.metrics["total_processing_time_ms"] / self.metrics["events_handled"]
            if self.metrics["events_handled"] > 0
            else 0.0
        )
        cache_hit_rate = (
            self.metrics["cache_hits"] / self.metrics["events_handled"]
            if self.metrics["events_handled"] > 0
            else 0.0
        )

        return {
            **self.metrics,
            "success_rate": success_rate,
            "avg_processing_time_ms": avg_processing_time,
            "cache_hit_rate": cache_hit_rate,
            "handler_name": self.get_handler_name(),
        }

    async def shutdown(self) -> None:
        """Shutdown handler and cleanup resources."""
        await self._close_http_client()
        await self._shutdown_publisher()
        logger.info("Document indexing handler shutdown complete")
