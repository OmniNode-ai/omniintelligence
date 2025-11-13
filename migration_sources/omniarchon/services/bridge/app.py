"""
PostgreSQL-Memgraph Bridge Service for Archon

Bidirectional synchronization between Supabase PostgreSQL and Memgraph knowledge graph.
Maps relational data to graph entities and relationships.
"""

import asyncio
import logging
import os

# Import timeout configuration
import sys
from contextlib import asynccontextmanager

# Add python lib to path for config validator
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from datetime import datetime
from typing import Any, Dict

import httpx
from connectors.memgraph_connector import MemgraphConnector
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from http_client_config import HTTPClientConfig, close_all_shared_clients
from models.bridge_models import (
    BridgeHealthStatus,
    DatabaseQueryRequest,
    DatabaseQueryResponse,
    EntityMappingRequest,
    RealtimeDocumentSyncRequest,
    SyncRequest,
    SyncResponse,
)
from models.external_api_models import (
    IntelligenceDocumentProcessingResponse,
    validate_intelligence_response,
)
from producers.kafka_producer_manager import KafkaProducerManager
from pydantic import ValidationError

from python.lib.config_validator import validate_required_env_vars

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from config import get_http_timeout

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import comprehensive bridge logging
from bridge_logging.bridge_logger import bridge_logger

# Global service components
memgraph_connector = None
kafka_producer = None

# Global pooled HTTP client for service-to-service communication
# Phase 1 Performance: Shared connection pool across all endpoints
pooled_http_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup bridge service components"""
    global memgraph_connector, pooled_http_client, kafka_producer

    # Validate environment variables before any initialization
    validate_required_env_vars()

    # Log startup sequence start
    bridge_logger.log_startup_phase("initialization", "start")

    # Log HTTP client configuration
    HTTPClientConfig.log_config()

    try:
        # Initialize Memgraph connector
        bridge_logger.log_startup_phase("memgraph_connector", "progress")
        memgraph_uri = os.getenv("MEMGRAPH_URI", "bolt://memgraph:7687")
        memgraph_connector = MemgraphConnector(memgraph_uri)
        await memgraph_connector.initialize()
        bridge_logger.log_startup_phase(
            "memgraph_connector", "success", {"memgraph_uri": memgraph_uri}
        )

        # Initialize intelligence service connection
        bridge_logger.log_startup_phase("intelligence_service", "progress")
        intelligence_url = os.getenv(
            "INTELLIGENCE_SERVICE_URL", "http://archon-intelligence:8053"
        )

        # Initialize pooled HTTP client for intelligence service calls
        # Phase 1 Performance: Single shared pool for all health checks and service calls
        pooled_http_client = HTTPClientConfig.create_pooled_client(
            base_url=intelligence_url
        )

        # Initialize Kafka producer for async enrichment
        bridge_logger.log_startup_phase("kafka_producer", "progress")
        kafka_producer = KafkaProducerManager()
        await kafka_producer.start()
        app.state.kafka_producer = kafka_producer
        bridge_logger.log_startup_phase(
            "kafka_producer", "success", {"enabled": kafka_producer.enabled}
        )

        bridge_logger.log_startup_phase("initialization", "success")
        logger.info("Bridge service initialized successfully")
        yield

    except Exception as e:
        bridge_logger.log_startup_phase("initialization", "error", {"error": str(e)})
        logger.error(f"Failed to initialize bridge service: {e}")
        raise
    finally:
        # Cleanup
        bridge_logger.log_startup_phase("cleanup", "progress")
        if kafka_producer:
            await kafka_producer.stop()
            logger.info("Stopped Kafka producer")
        if memgraph_connector:
            await memgraph_connector.close()
        if pooled_http_client:
            await pooled_http_client.aclose()
            logger.info("Closed pooled HTTP client")
        # Close any remaining shared clients
        await close_all_shared_clients()
        bridge_logger.log_startup_phase("cleanup", "success")
        logger.info("Bridge service shutdown complete")


# FastAPI application
app = FastAPI(
    title="Archon Bridge Service",
    description="PostgreSQL-Memgraph bridge for knowledge graph synchronization",
    version="1.0.0",
    lifespan=lifespan,
)


# CORS Configuration (environment-based for production security)
def get_cors_origins() -> list[str]:
    """
    Get CORS allowed origins from environment with production validation.

    Returns:
        List of allowed origins. Defaults to localhost for development.
    """
    # Check both CORS_ALLOWED_ORIGINS and ALLOWED_ORIGINS (for backward compatibility)
    origins_env = os.getenv("CORS_ALLOWED_ORIGINS") or os.getenv("ALLOWED_ORIGINS")
    environment = os.getenv("ENVIRONMENT", "development")

    # Development defaults (localhost variants)
    dev_origins = [
        "http://localhost:3737",
        "http://localhost:8181",
        "http://127.0.0.1:3737",
        "http://127.0.0.1:8181",
    ]

    if not origins_env:
        if environment == "production":
            logger.warning(
                "⚠️  SECURITY WARNING: CORS_ALLOWED_ORIGINS not set in production! "
                "Using restrictive defaults. Set CORS_ALLOWED_ORIGINS environment variable."
            )
            return dev_origins  # Fail-safe: use localhost only
        else:
            logger.info("CORS: Using development defaults (localhost)")
            return dev_origins

    # Wildcard check for production
    if origins_env == "*":
        if environment == "production":
            logger.error(
                "❌ SECURITY ERROR: Wildcard CORS (*) is NOT allowed in production! "
                "Set CORS_ALLOWED_ORIGINS to specific domains. Using restrictive defaults."
            )
            return dev_origins  # Fail-safe: reject wildcard in production
        else:
            logger.warning("CORS: Using wildcard (*) - development only")
            return ["*"]

    # Parse comma-separated origins
    origins = [origin.strip() for origin in origins_env.split(",")]
    logger.info(f"CORS: Configured {len(origins)} allowed origins for {environment}")

    return origins


cors_origins = get_cors_origins()

# CORS middleware with environment-based configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=BridgeHealthStatus)
async def health_check():
    """Bridge service health check endpoint"""
    try:
        # Test Memgraph connectivity
        memgraph_status = (
            await memgraph_connector.health_check() if memgraph_connector else False
        )

        # Test Intelligence service connectivity using pooled HTTP client
        # Phase 1 Performance: Reuses connection pool instead of creating new client
        intelligence_status = True
        try:
            if pooled_http_client:
                response = await pooled_http_client.get(
                    "/health", timeout=get_http_timeout("health")
                )
                intelligence_status = response.status_code == 200
            else:
                intelligence_status = False
        except Exception as e:
            logger.debug(f"Intelligence service health check failed: {e}")
            intelligence_status = False

        # Determine overall status
        # Core required services: Memgraph (graph), Intelligence (analysis)
        core_services_healthy = memgraph_status and intelligence_status
        status = "healthy" if core_services_healthy else "degraded"

        return BridgeHealthStatus(
            status=status,
            memgraph_connected=memgraph_status,
            intelligence_connected=intelligence_status,
            service_version="1.0.0",
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return BridgeHealthStatus(
            status="unhealthy",
            memgraph_connected=False,
            intelligence_connected=False,
            service_version="1.0.0",
            error=str(e),
        )


@app.get("/health/producer")
async def producer_health_check():
    """Kafka producer health check endpoint"""
    try:
        if not kafka_producer:
            return {
                "status": "not_initialized",
                "message": "Kafka producer not initialized",
            }

        health = await kafka_producer.health_check()
        return {
            "status": "healthy" if health["producer_running"] else "degraded",
            **health,
        }

    except Exception as e:
        logger.error(f"Producer health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }


@app.post("/sync/full", response_model=SyncResponse)
async def full_sync(background_tasks: BackgroundTasks) -> SyncResponse:
    """Perform full bidirectional sync between PostgreSQL and Memgraph"""
    try:
        if not sync_service:
            raise HTTPException(status_code=503, detail="Sync service not initialized")

        # Start full sync in background
        background_tasks.add_task(sync_service.full_sync)

        return SyncResponse(
            sync_id="full_sync_" + str(int(asyncio.get_event_loop().time())),
            status="started",
            message="Full sync initiated in background",
        )

    except Exception as e:
        logger.error(f"Full sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sync/incremental", response_model=SyncResponse)
async def incremental_sync(
    request: SyncRequest, background_tasks: BackgroundTasks
) -> SyncResponse:
    """Perform incremental sync for specific entities/timeframe"""
    try:
        if not sync_service:
            raise HTTPException(status_code=503, detail="Sync service not initialized")

        # Start incremental sync in background
        background_tasks.add_task(
            sync_service.incremental_sync,
            entity_types=request.entity_types,
            since_timestamp=request.since_timestamp,
            source_ids=request.source_ids,
        )

        return SyncResponse(
            sync_id=f"incremental_sync_{request.entity_types}_{int(asyncio.get_event_loop().time())}",
            status="started",
            message=f"Incremental sync initiated for {request.entity_types}",
        )

    except Exception as e:
        logger.error(f"Incremental sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mapping/create")
async def create_entity_mapping(request: EntityMappingRequest) -> Dict[str, Any]:
    """Create mapping for specific Supabase entity to graph entities"""
    try:
        if not entity_mapper:
            raise HTTPException(status_code=503, detail="Entity mapper not initialized")

        # Map the entity based on type
        if request.entity_type == "source":
            mapped_entities = await entity_mapper.map_source_to_graph(
                request.entity_id, include_content=request.include_content
            )
        elif request.entity_type == "project":
            mapped_entities = await entity_mapper.map_project_to_graph(
                request.entity_id, include_tasks=request.include_relationships
            )
        elif request.entity_type == "page":
            mapped_entities = await entity_mapper.map_crawled_page_to_graph(
                request.entity_id, extract_entities=request.include_content
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported entity type: {request.entity_type}",
            )

        return {
            "success": True,
            "entity_type": request.entity_type,
            "entity_id": request.entity_id,
            "mapped_entities": len(mapped_entities),
            "entities": [entity.entity_id for entity in mapped_entities],
        }

    except Exception as e:
        logger.error(f"Entity mapping failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sync/status")
async def get_sync_status() -> Dict[str, Any]:
    """Get current sync status and statistics"""
    try:
        if not sync_service:
            raise HTTPException(status_code=503, detail="Sync service not initialized")

        status = await sync_service.get_sync_status()
        return status

    except Exception as e:
        logger.error(f"Failed to get sync status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/mapping/stats")
async def get_mapping_statistics() -> Dict[str, Any]:
    """Get entity mapping statistics"""
    try:
        if not entity_mapper:
            raise HTTPException(status_code=503, detail="Entity mapper not initialized")

        stats = await entity_mapper.get_mapping_statistics()
        return stats

    except Exception as e:
        logger.error(f"Failed to get mapping statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/intelligence/extract")
async def extract_and_map_content(
    content: str, source_path: str, content_type: str = "document"
) -> Dict[str, Any]:
    """Extract entities from content and map to graph"""
    try:
        if not entity_mapper:
            raise HTTPException(status_code=503, detail="Entity mapper not initialized")

        # Use intelligence service to extract entities
        entities = await entity_mapper.extract_and_map_content(
            content=content, source_path=source_path, content_type=content_type
        )

        return {
            "success": True,
            "entities_extracted": len(entities),
            "entities": [
                {
                    "entity_id": entity.entity_id,
                    "name": entity.name,
                    "type": entity.entity_type.value,
                    "confidence": entity.confidence_score,
                }
                for entity in entities
            ],
        }

    except Exception as e:
        logger.error(f"Content extraction and mapping failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sync/realtime-document")
async def realtime_document_sync(
    request: RealtimeDocumentSyncRequest, background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Handle real-time document synchronization triggered by database events.

    This endpoint is called by database triggers or webhook systems when
    documents are created or updated, ensuring immediate knowledge graph sync.
    """
    try:
        if not entity_mapper or not sync_service:
            raise HTTPException(status_code=503, detail="Sync services not initialized")

        document_id = request.document_id
        project_id = request.project_id

        # Extract title for logging from document data
        actual_document = request.document_data
        document_title = actual_document.get("title", "untitled")

        logger.info(
            f"🔄 [INDEXING PIPELINE] Processing real-time document sync | document_id={document_id} | "
            f"project_id={project_id} | title='{document_title[:50]}' | source={request.source}"
        )

        # Queue background sync task - convert request to dict for compatibility
        document_data_dict = {
            "document_id": request.document_id,
            "project_id": request.project_id,
            "document_data": request.document_data,
            "source": request.source,
            "trigger_type": request.trigger_type,
        }

        background_tasks.add_task(
            _process_document_sync_background,
            document_data_dict,
            entity_mapper,
            sync_service,
        )

        return {
            "success": True,
            "document_id": document_id,
            "project_id": project_id,
            "status": "sync_queued",
            "message": "Document sync queued for processing",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Real-time document sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _process_document_sync_background(document_data: Dict[str, Any]):
    """
    Background task to process document synchronization to knowledge graph.
    """
    try:
        document_id = document_data.get("document_id")
        project_id = document_data.get("project_id")

        # Extract actual document data from nested structure (MCP sends document_data.document_data)
        actual_document = document_data.get("document_data", {})
        title = actual_document.get("title", "")
        content = actual_document.get("content", {})
        document_type = actual_document.get("document_type", "document")
        metadata = actual_document.get("metadata", {})

        # DEBUG: Log the actual content structure to understand the issue
        logger.info(
            f"🔍 [DEBUG] Content structure: {type(content)}, keys: {list(content.keys()) if isinstance(content, dict) else 'N/A'}"
        )
        logger.info(f"🔍 [DEBUG] Content preview: {str(content)[:200]}...")

        # Convert content to text for processing using recursive extraction
        def extract_all_text(obj, excluded_keys=None):
            """Recursively extract all text content from nested structures."""
            if excluded_keys is None:
                excluded_keys = {
                    "tags",
                    "importance",
                    "file_path",
                    "repository",
                    "document_type",
                    "summary",
                }

            if isinstance(obj, dict):
                text_parts = []
                for key, value in obj.items():
                    if key.lower() not in excluded_keys:
                        text_parts.append(extract_all_text(value, excluded_keys))
                return " ".join(text_parts)
            elif isinstance(obj, list):
                return " ".join(extract_all_text(item, excluded_keys) for item in obj)
            else:
                return str(obj)

        if isinstance(content, dict):
            content_text = extract_all_text(content)
        else:
            content_text = str(content)

        # Create full text content
        full_text = f"{title}\n\n{content_text}".strip()

        # Create source path identifier
        source_path = f"archon://projects/{project_id}/documents/{document_id}"

        logger.info(
            f"🧠 [INDEXING PIPELINE] Syncing document to knowledge graph | document_id={document_id} | content_length={len(full_text)}"
        )

        # 3-way intelligence enrichment bypass logic
        # Path 1: Skip enrichment entirely (SKIP_INTELLIGENCE_ENRICHMENT=true)
        # Path 2: Async enrichment via Kafka (ENABLE_ASYNC_ENRICHMENT=true)
        # Path 3: Synchronous enrichment blocking (legacy, both flags false)

        skip_intelligence = (
            os.getenv("SKIP_INTELLIGENCE_ENRICHMENT", "false").lower() == "true"
        )
        enable_async_enrichment = (
            os.getenv("ENABLE_ASYNC_ENRICHMENT", "false").lower() == "true"
        )

        if skip_intelligence:
            # Path 1: Skip enrichment entirely
            logger.info(
                f"⚡ [INDEXING PIPELINE] Skipping intelligence enrichment (SKIP_INTELLIGENCE_ENRICHMENT=true) | document_id={document_id}"
            )
            entities = []

        elif enable_async_enrichment:
            # Path 2: Async enrichment via Kafka
            logger.info(
                f"📤 [INDEXING PIPELINE] Queueing async intelligence enrichment | document_id={document_id}"
            )

            # Extract necessary data for enrichment event
            import hashlib
            import uuid

            # Calculate content hash (BLAKE3 if available, else SHA256)
            try:
                import blake3

                content_hash = blake3.blake3(content_text.encode("utf-8")).hexdigest()
            except ImportError:
                content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()

            # Extract file path and language from content
            file_path = (
                content.get("file_path", source_path)
                if isinstance(content, dict)
                else source_path
            )
            language = (
                content.get("language", "unknown")
                if isinstance(content, dict)
                else "unknown"
            )

            # Generate correlation ID
            correlation_id = str(uuid.uuid4()).upper()

            # Publish enrichment request to Kafka
            if kafka_producer:
                await kafka_producer.publish_enrichment_request(
                    document_id=document_id,
                    project_name=project_id,
                    content_hash=content_hash,
                    file_path=file_path,
                    content=content_text,
                    document_type=document_type,
                    language=language,
                    metadata={
                        **metadata,
                        "sync_source": "bridge_service",
                        "processing_timestamp": datetime.utcnow().isoformat(),
                    },
                    correlation_id=correlation_id,
                )
                logger.info(
                    f"✅ [INDEXING PIPELINE] Async enrichment queued | document_id={document_id} | correlation_id={correlation_id}"
                )
            else:
                logger.warning(
                    f"⚠️ [INDEXING PIPELINE] Kafka producer not initialized, skipping async enrichment | document_id={document_id}"
                )

            # Continue with empty entities list (enrichment will happen async)
            entities = []

        else:
            # Path 3: Synchronous enrichment (legacy blocking behavior)
            logger.info(
                f"📊 [INDEXING PIPELINE] Calling intelligence service for document processing (sync) | document_id={document_id}"
            )
            try:
                # Call /process/document endpoint using pooled HTTP client
                # Phase 1 Performance: Reuses connection pool for document processing
                if not pooled_http_client:
                    raise Exception("Pooled HTTP client not initialized")

                response = await pooled_http_client.post(
                    "/process/document",
                    json={
                        "document_id": document_id,
                        "project_id": project_id,
                        "title": title,
                        "content": content,  # Use original structured content
                        "document_type": document_type,
                        "metadata": {
                            **metadata,
                            "sync_source": "bridge_service",
                            "processing_timestamp": datetime.utcnow().isoformat(),
                        },
                    },
                )

                if response.status_code == 200:
                    # SECURITY: Validate response structure before processing
                    try:
                        raw_result = response.json()
                        validated_response = validate_intelligence_response(
                            raw_result, "/process/document"
                        )

                        if not isinstance(
                            validated_response, IntelligenceDocumentProcessingResponse
                        ):
                            logger.error(
                                f"❌ [INDEXING PIPELINE] Unexpected response type from /process/document: {type(validated_response)}"
                            )
                            raise Exception(
                                f"Invalid response type from intelligence service: {type(validated_response)}"
                            )

                        entities_count = validated_response.entities_extracted
                        logger.info(
                            f"✅ [INDEXING PIPELINE] Intelligence service completed | document_id={document_id} | entities_extracted={entities_count} | status={validated_response.status}"
                        )

                        # For compatibility, create a simple entities list for the rest of the function
                        entities = [
                            {"entity_id": f"entity_{i}", "confidence_score": 0.8}
                            for i in range(entities_count)
                        ]

                    except ValidationError as ve:
                        logger.error(
                            f"❌ [INDEXING PIPELINE] Response validation failed | document_id={document_id} | error={ve}"
                        )
                        logger.debug(
                            f"Invalid response data: {raw_result if 'raw_result' in locals() else 'N/A'}"
                        )
                        raise Exception(
                            f"Intelligence service returned invalid response: {ve}"
                        ) from ve

                else:
                    logger.error(
                        f"❌ [INDEXING PIPELINE] Intelligence service failed | document_id={document_id} | status={response.status_code} | error={response.text}"
                    )
                    raise Exception(
                        f"Intelligence service returned {response.status_code}: {response.text}"
                    )

            except ValidationError as ve:
                logger.error(
                    f"❌ [INDEXING PIPELINE] Validation error | document_id={document_id} | error={str(ve)}"
                )
                raise
            except httpx.TimeoutException as te:
                logger.error(
                    f"❌ [INDEXING PIPELINE] Timeout calling intelligence service | document_id={document_id} | error={str(te)}"
                )
                raise
            except httpx.RequestError as re:
                logger.error(
                    f"❌ [INDEXING PIPELINE] Network error calling intelligence service | document_id={document_id} | error={str(re)}"
                )
                raise
            except Exception as e:
                logger.error(
                    f"❌ [INDEXING PIPELINE] Intelligence service failed | document_id={document_id} | error={str(e)}"
                )
                raise

        # Create document entity in knowledge graph
        document_entity = {
            "entity_id": document_id,
            "entity_type": "document",
            "name": title,
            "properties": {
                "project_id": project_id,
                "document_type": document_type,
                "content_preview": full_text[:500],  # First 500 chars
                "source_path": source_path,
                "metadata": metadata,
            },
            "confidence_score": 1.0,  # High confidence for document entities
        }

        # Store document entity and extracted entities
        if memgraph_connector:
            await memgraph_connector.store_entities([document_entity] + entities)

            # Create relationships between document and extracted entities
            logger.info(
                f"🔗 [INDEXING PIPELINE] Creating relationships | document_id={document_id} | entity_count={len(entities)}"
            )
            for i, entity in enumerate(entities):
                entity_id = entity.get("entity_id")
                confidence_score = entity.get("confidence_score", 0.0)

                if not entity_id:
                    logger.warning(
                        f"⚠️ [INDEXING PIPELINE] Entity missing entity_id | document_id={document_id} | entity_index={i} | entity_keys={list(entity.keys()) if isinstance(entity, dict) else 'not_dict'}"
                    )
                    continue

                logger.debug(
                    f"🔗 [INDEXING PIPELINE] Creating relationship | document_id={document_id} | entity_id={entity_id} | confidence={confidence_score}"
                )
                await memgraph_connector.create_relationship(
                    from_entity_id=document_id,
                    to_entity_id=entity_id,
                    relationship_type="CONTAINS_ENTITY",
                    properties={
                        "confidence": confidence_score,
                        "extraction_method": "intelligence_service",
                    },
                )

        logger.info(
            f"Document synced to knowledge graph | document_id={document_id} | "
            f"entities_created={len(entities) + 1}"
        )

    except Exception as e:
        logger.error(
            f"Background document sync failed | document_id={document_data.get('document_id')} | "
            f"error={str(e)}"
        )


@app.post("/webhook/document-trigger")
async def document_webhook_handler(
    payload: Dict[str, Any], background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Webhook endpoint for handling document update notifications.

    This can be called by Supabase webhooks, external systems, or
    other components to trigger real-time document processing.
    """
    try:
        # Extract document information from webhook payload
        # Support multiple payload formats

        if "record" in payload:
            # Supabase webhook format
            record = payload["record"]
            document_data = {
                "document_id": record.get("id"),
                "project_id": record.get("project_id"),
                "title": record.get("title", ""),
                "content": record.get("content", {}),
                "document_type": record.get("document_type", "document"),
                "metadata": {
                    "webhook_source": "supabase",
                    "table": payload.get("table", "unknown"),
                    "event_type": payload.get("type", "unknown"),
                },
            }
        elif "document_id" in payload:
            # Direct format
            document_data = payload
        else:
            raise HTTPException(
                status_code=400, detail="Invalid webhook payload format"
            )

        return await realtime_document_sync(document_data, background_tasks)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document webhook handler failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/events/tree-index")
async def handle_tree_index_event(
    event: Dict[str, Any], background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Handle tree discovery and indexing events from Kafka consumer.

    Tree index events contain filesystem tree discovery data, including file
    metadata, content, and project context. These events populate the knowledge
    graph with Document nodes and establish relationships.

    Event payload structure:
    {
        "project_name": "omniarchon",
        "files": [
            {
                "file_path": "/path/to/file.py",
                "relative_path": "src/file.py",
                "content": "...",
                "language": "python",
                "file_type": "py",
                "checksum": "sha256...",
                "metadata": {...}
            }
        ]
    }

    Processes files by:
    - Creating/updating Document nodes in Memgraph knowledge graph
    - Indexing file content in Qdrant vector database (via intelligence service)
    - Establishing relationships (imports, dependencies, parent directories)
    - Extracting code entities and creating semantic links

    Args:
        event: Event payload containing tree discovery and file metadata

    Returns:
        Status confirmation with files processed count
    """
    try:
        if not memgraph_connector:
            raise HTTPException(
                status_code=503, detail="Memgraph connector not initialized"
            )

        # Extract from payload (event has envelope structure)
        payload = event.get("payload", {})
        project_name = payload.get("project_name", "unknown")
        files = payload.get("files", [])
        event_type = payload.get("type", "tree_discovery")

        logger.info(
            f"🌳 [TREE INDEX] Received tree index event | project={project_name} | "
            f"file_count={len(files)} | type={event_type}"
        )

        # Process each file in the tree discovery event
        files_processed = 0
        files_failed = 0

        for file_data in files:
            try:
                # Extract file information
                file_path = file_data.get(
                    "file_path", file_data.get("relative_path", "unknown")
                )
                content = file_data.get("content", "")
                language = file_data.get("language", "unknown")
                checksum = file_data.get("checksum", "")
                metadata = file_data.get("metadata", {})

                # Create document data in format expected by realtime_document_sync
                # Use file path as document ID (hash for consistency)
                import hashlib

                document_id = hashlib.sha256(
                    f"{project_name}:{file_path}".encode()
                ).hexdigest()[:16]

                document_data = {
                    "document_id": document_id,
                    "project_id": project_name,  # Use project name as project ID
                    "document_data": {
                        "title": (
                            file_path.split("/")[-1] if "/" in file_path else file_path
                        ),
                        "content": {
                            "text": content,
                            "file_path": file_path,
                            "language": language,
                            "checksum": checksum,
                        },
                        "document_type": "file",
                        "metadata": {
                            **metadata,
                            "source": "tree_discovery",
                            "project_name": project_name,
                            "file_path": file_path,
                            "language": language,
                        },
                    },
                    "source": "tree_index",
                    "trigger_type": event_type,
                }

                # Queue document processing
                background_tasks.add_task(
                    _process_document_sync_background,
                    document_data,
                )

                files_processed += 1

                logger.debug(
                    f"🌳 [TREE INDEX] Queued file processing | file={file_path} | "
                    f"document_id={document_id}"
                )

            except Exception as e:
                files_failed += 1
                logger.error(
                    f"🌳 [TREE INDEX] Failed to process file | file={file_data.get('file_path', 'unknown')} | "
                    f"error={str(e)}"
                )

        logger.info(
            f"🌳 [TREE INDEX] Completed tree index event | project={project_name} | "
            f"processed={files_processed} | failed={files_failed}"
        )

        return {
            "status": "success",
            "event_type": "tree-index",
            "project_name": project_name,
            "files_processed": files_processed,
            "files_failed": files_failed,
            "total_files": len(files),
            "message": f"Queued {files_processed}/{len(files)} files for processing",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"🌳 [TREE INDEX] Tree index event failed | error={str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("BRIDGE_SERVICE_PORT", 8054))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True, log_level="info")
