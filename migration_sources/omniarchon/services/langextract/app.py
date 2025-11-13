"""
Archon LangExtract Service - Advanced Language-Aware Data Extraction

Enhanced entity extraction and knowledge graph capabilities for sophisticated
document analysis and semantic understanding.
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Analysis and enhancement
from analysis.code_relationship_detector import CodeRelationshipDetector
from analysis.document_analyzer import DocumentAnalyzer
from analysis.relationship_mapper import RelationshipMapper
from analysis.semantic_enricher import SemanticEnricher

# Event handling
from events.extraction_event_emitter import ExtractionEventEmitter
from events.models.extraction_events import ExtractionCompletedEvent

# Core extraction engines
from extractors.language_aware_extractor import LanguageAwareExtractor
from extractors.semantic_pattern_extractor import SemanticPatternExtractor
from extractors.structured_data_extractor import StructuredDataExtractor
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from integration.event_subscriber import DocumentEventSubscriber
from integration.intelligence_client import IntelligenceServiceClient

# Models and schemas
from models.extraction_models import (
    BatchExtractionRequest,
    DocumentExtractionRequest,
    EnhancedEntity,
    EnhancedRelationship,
    ExtractionResponse,
    ExtractionStatistics,
    HealthStatus,
    SemanticAnalysisResult,
)

# Storage and integration
from storage.enhanced_memgraph_adapter import EnhancedMemgraphAdapter

# Configure logging (must be before config validator import)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config validator - optional import (may not be available in container)
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
    from python.lib.config_validator import validate_required_env_vars
except ImportError:
    logger.warning("Config validator not available - skipping env validation")
    validate_required_env_vars = lambda: None  # No-op function

# Global service components
language_extractor = None
structured_extractor = None
semantic_extractor = None
document_analyzer = None
semantic_enricher = None
relationship_mapper = None
code_relationship_detector = None
memgraph_adapter = None
intelligence_client = None
event_subscriber = None
event_emitter = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup service components"""
    global language_extractor, structured_extractor, semantic_extractor
    global document_analyzer, semantic_enricher
    global relationship_mapper, code_relationship_detector, memgraph_adapter, intelligence_client
    global event_subscriber, event_emitter

    # Validate environment variables before any initialization
    validate_required_env_vars()

    try:
        logger.info("Initializing LangExtract service components...")

        # Initialize Memgraph adapter with enhanced capabilities
        memgraph_uri = os.getenv("MEMGRAPH_URI", "bolt://localhost:7687")
        memgraph_adapter = EnhancedMemgraphAdapter(uri=memgraph_uri)
        await memgraph_adapter.initialize()

        # Initialize extraction engines
        language_extractor = LanguageAwareExtractor()
        structured_extractor = StructuredDataExtractor()
        semantic_extractor = SemanticPatternExtractor()

        # Initialize analysis components
        document_analyzer = DocumentAnalyzer()
        semantic_enricher = SemanticEnricher()
        relationship_mapper = RelationshipMapper()
        code_relationship_detector = CodeRelationshipDetector()

        # Initialize Intelligence service client
        intelligence_url = os.getenv(
            "INTELLIGENCE_SERVICE_URL", "http://localhost:8053"
        )
        intelligence_client = IntelligenceServiceClient(base_url=intelligence_url)

        # Initialize event system
        event_emitter = ExtractionEventEmitter()

        # Get service URLs from environment variables for Docker networking
        bridge_url = os.getenv("BRIDGE_SERVICE_URL", "http://archon-bridge:8054")
        intelligence_url = os.getenv(
            "INTELLIGENCE_SERVICE_URL", "http://archon-intelligence:8053"
        )

        event_subscriber = DocumentEventSubscriber(
            callback=handle_document_update_event,
            bridge_service_url=bridge_url,
            intelligence_service_url=intelligence_url,
        )
        await event_subscriber.start()

        logger.info("LangExtract service initialized successfully")
        yield

    finally:
        # Cleanup resources
        logger.info("Shutting down LangExtract service...")

        if event_subscriber:
            await event_subscriber.stop()

        if memgraph_adapter:
            await memgraph_adapter.close()

        logger.info("LangExtract service shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Archon LangExtract Service",
    description=(
        "Advanced Language-Aware Data Extraction and Knowledge Graph Enhancement"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health Check Endpoint
@app.get("/health", response_model=HealthStatus)
async def health_check():
    """Service health check with component status"""
    try:
        # Check component health
        memgraph_healthy = (
            await memgraph_adapter.health_check() if memgraph_adapter else False
        )
        intelligence_healthy = (
            await intelligence_client.health_check() if intelligence_client else False
        )

        status = (
            "healthy"
            if all(
                [
                    memgraph_healthy,
                    intelligence_healthy,
                    language_extractor is not None,
                    document_analyzer is not None,
                ]
            )
            else "degraded"
        )

        return HealthStatus(
            status=status,
            timestamp=datetime.utcnow(),
            components={
                "memgraph_adapter": "healthy" if memgraph_healthy else "unhealthy",
                "intelligence_client": (
                    "healthy" if intelligence_healthy else "unhealthy"
                ),
                "language_extractor": "healthy" if language_extractor else "unhealthy",
                "document_analyzer": "healthy" if document_analyzer else "unhealthy",
                "event_subscriber": "healthy" if event_subscriber else "unhealthy",
            },
            version="1.0.0",
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthStatus(
            status="unhealthy",
            timestamp=datetime.utcnow(),
            error=str(e),
            version="1.0.0",
        )


# Core Extraction Endpoints
@app.post("/extract/document", response_model=ExtractionResponse)
async def extract_from_document(
    request: DocumentExtractionRequest,
    background_tasks: BackgroundTasks,
) -> ExtractionResponse:
    """
    Extract entities and relationships from a single document.

    Advanced language-aware extraction with semantic enrichment.
    """
    try:
        logger.info(f"Starting document extraction for: {request.document_path}")

        # Read document content (use inline content if provided, otherwise read from file)
        content = (
            request.content
            if request.content is not None
            else await _read_document_content(request.document_path)
        )

        # Perform multi-stage extraction
        extraction_start = datetime.utcnow()

        # Stage 1: Language-aware entity extraction
        logger.info("[INTERFACE] Stage 1: Calling language_extractor.extract_entities")
        language_results = await language_extractor.extract_entities(
            content=content,
            document_path=request.document_path,
            extraction_options=request.extraction_options,
        )
        logger.info(
            f"[INTERFACE] Stage 1: language_extractor returned type: {type(language_results)}, entities: {len(language_results.entities)}"
        )

        # Stage 2: Structured data extraction
        logger.info(
            "[INTERFACE] Stage 2: Calling structured_extractor.extract_structured_data"
        )
        structured_results = await structured_extractor.extract_structured_data(
            content=content,
            document_path=request.document_path,
            schema_hints=request.extraction_options.schema_hints,
        )
        logger.info(
            f"[INTERFACE] Stage 2: structured_extractor returned type: {type(structured_results)}"
        )

        # Stage 3: Semantic pattern extraction
        logger.info(
            "[INTERFACE] Stage 3: Calling semantic_extractor.extract_semantic_patterns"
        )
        semantic_results = await semantic_extractor.extract_semantic_patterns(
            content=content,
            entities=language_results.entities,
            context=request.extraction_options.semantic_context,
        )
        logger.info(
            f"[INTERFACE] Stage 3: semantic_extractor returned type: {type(semantic_results)}"
        )
        logger.info(
            f"[INTERFACE] Stage 3: semantic_results has semantic_context: {hasattr(semantic_results, 'semantic_context')}"
        )
        logger.info(
            f"[INTERFACE] Stage 3: semantic_context type: {type(semantic_results.semantic_context)}"
        )

        # Stage 4: Document analysis and enrichment
        logger.info("[INTERFACE] Stage 4: Calling document_analyzer.analyze_document")
        analysis_result = await document_analyzer.analyze_document(
            content=content,
            entities=language_results.entities,
            document_path=request.document_path,
        )
        logger.info(
            f"[INTERFACE] Stage 4: document_analyzer returned type: {type(analysis_result)}"
        )

        # Stage 5: Relationship mapping (use code detector for Python files, NLP mapper for docs)
        is_code_file = request.document_path.endswith(
            (".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs")
        )

        if is_code_file:
            # Use AST-based code relationship detection
            logger.info(
                f"[INTERFACE] Stage 5: Using code_relationship_detector for code file | path={request.document_path}"
            )
            raw_relationships = await code_relationship_detector.detect_relationships(
                content=content,
                language=request.document_path.split(".")[-1],
                document_path=request.document_path,
            )
            logger.info(
                f"[INTERFACE] Stage 5: code_relationship_detector returned {len(raw_relationships)} relationships"
            )
        else:
            # Use NLP-based relationship mapping for documentation
            logger.info(
                f"[INTERFACE] Stage 5: Using relationship_mapper for document | path={request.document_path}"
            )
            relationship_mapping_result = await relationship_mapper.map_relationships(
                content=content,
                entities=language_results.entities,
                context=semantic_results.semantic_context,
            )
            logger.info(
                f"[INTERFACE] Stage 5: relationship_mapper returned type: {type(relationship_mapping_result)}"
            )

            # Extract relationships list from mapping result
            raw_relationships = (
                relationship_mapping_result.relationships
                if hasattr(relationship_mapping_result, "relationships")
                else []
            )
            logger.info(
                f"[INTERFACE] Stage 5: extracted relationships type: {type(raw_relationships)}, count: {len(raw_relationships)}"
            )

        # Convert Relationship objects to EnhancedRelationship objects for response model compatibility
        relationships = []
        for i, rel in enumerate(raw_relationships):
            try:
                # Extract evidence and convert to string if it's a list
                evidence = getattr(rel, "evidence", [])
                context_str = (
                    "; ".join(evidence) if isinstance(evidence, list) else str(evidence)
                )

                # Get context field if it exists, otherwise use evidence
                context_value = getattr(rel, "context", context_str)
                # Ensure context is always a string (handle list, None, empty cases)
                if isinstance(context_value, list):
                    context_value = (
                        "; ".join(str(item) for item in context_value)
                        if context_value
                        else ""
                    )
                elif context_value is None or context_value == "":
                    context_value = context_str  # Use evidence-based fallback
                else:
                    context_value = str(context_value)  # Explicit string conversion

                enhanced_rel = EnhancedRelationship(
                    relationship_id=getattr(rel, "id", f"rel_{i}"),
                    source_entity_id=getattr(rel, "source", "unknown"),
                    target_entity_id=getattr(rel, "target", "unknown"),
                    relationship_type=getattr(rel, "relationship_type", "unknown"),
                    confidence_score=getattr(rel, "confidence", 0.5),
                    strength=getattr(rel, "strength", getattr(rel, "weight", 1.0)),
                    context=context_value,
                    properties={
                        "relationship_subtype": getattr(
                            rel, "relationship_subtype", ""
                        ),
                        "bidirectional": getattr(rel, "bidirectional", False),
                        "source_position": getattr(rel, "source_position", 0),
                        "target_position": getattr(rel, "target_position", 0),
                        "evidence": evidence,  # Store original evidence list in properties
                    },
                )
                relationships.append(enhanced_rel)
            except Exception as e:
                logger.warning(f"Failed to convert relationship {i}: {e}")
                continue

        logger.info(
            f"[INTERFACE] Stage 5: converted to EnhancedRelationships, count: {len(relationships)}"
        )

        # Stage 6: Semantic enrichment
        logger.info(
            f"[INTERFACE] Stage 6: Calling semantic_enricher.enrich_entities with semantic_patterns available: {len(semantic_results.semantic_patterns)}"
        )
        enriched_entities = await semantic_enricher.enrich_entities(
            entities=language_results.entities,
            content=content,
        )
        logger.info(
            f"[INTERFACE] Stage 6: semantic_enricher returned type: {type(enriched_entities)}, count: {len(enriched_entities)}"
        )

        extraction_duration = (datetime.utcnow() - extraction_start).total_seconds()

        # Create comprehensive response
        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path_hash = hash(request.document_path) % 10000
        extraction_id = f"ext_{timestamp_str}_{path_hash:04d}"

        response = ExtractionResponse(
            extraction_id=extraction_id,
            document_path=request.document_path,
            language_results=(
                language_results.dict()
                if hasattr(language_results, "dict")
                else language_results
            ),
            structured_results=(
                structured_results.dict()
                if hasattr(structured_results, "dict")
                else structured_results
            ),
            semantic_results=(
                semantic_results.dict()
                if hasattr(semantic_results, "dict")
                else semantic_results
            ),
            analysis_result=(
                analysis_result.dict()
                if hasattr(analysis_result, "dict")
                else analysis_result
            ),
            enriched_entities=language_results.entities,  # Use original EnhancedEntity objects
            relationships=relationships,
            extraction_statistics=ExtractionStatistics(
                total_entities=len(language_results.entities),
                total_relationships=len(relationships),
                extraction_time_seconds=extraction_duration,
                confidence_score=_calculate_overall_confidence(
                    enriched_entities
                ),  # Use EntityEnrichment for confidence
            ),
            status="completed",
            timestamp=datetime.utcnow(),
        )

        # Background tasks for knowledge graph integration
        if request.update_knowledge_graph:
            background_tasks.add_task(
                _update_knowledge_graph,
                response.enriched_entities,
                response.relationships,
                request.document_path,
            )

        # Emit extraction completed event
        background_tasks.add_task(
            _emit_extraction_event,
            response,
        )

        logger.info(f"Document extraction completed in {extraction_duration: .2f}s")
        return response

    except Exception as e:
        logger.error(f"Document extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@app.post("/extract/batch", response_model=List[ExtractionResponse])
async def extract_batch_documents(
    request: BatchExtractionRequest,
    background_tasks: BackgroundTasks,
) -> List[ExtractionResponse]:
    """
    Extract entities and relationships from multiple documents in parallel.

    Optimized for high-throughput batch processing with intelligent load balancing.
    """
    try:
        logger.info(
            f"Starting batch extraction for {len(request.document_paths)} documents"
        )

        # Create individual extraction requests
        individual_requests = [
            DocumentExtractionRequest(
                document_path=path,
                extraction_options=request.extraction_options,
                update_knowledge_graph=request.update_knowledge_graph,
            )
            for path in request.document_paths
        ]

        # Process documents in parallel with concurrency limit
        semaphore = asyncio.Semaphore(request.max_concurrent_extractions)

        async def extract_single(req: DocumentExtractionRequest) -> ExtractionResponse:
            async with semaphore:
                return await extract_from_document(req, background_tasks)

        # Execute parallel extractions
        extraction_tasks = [extract_single(req) for req in individual_requests]
        results = await asyncio.gather(*extraction_tasks, return_exceptions=True)

        # Separate successful results from errors
        successful_results = []
        errors = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                errors.append(f"Document {request.document_paths[i]}: {str(result)}")
                logger.error(
                    f"Batch extraction error for {request.document_paths[i]}: {result}"
                )
            else:
                successful_results.append(result)

        # Log batch completion statistics
        success_count = len(successful_results)
        error_count = len(errors)
        logger.info(
            f"Batch extraction completed: {success_count} successful, "
            f"{error_count} errors"
        )

        if errors:
            logger.warning(f"Batch extraction errors: {errors}")

        return successful_results

    except Exception as e:
        logger.error(f"Batch extraction failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Batch extraction failed: {str(e)}"
        )


@app.post("/analyze/semantic", response_model=SemanticAnalysisResult)
async def analyze_semantic_patterns(
    content: str,
    context: Optional[str] = None,
    language: Optional[str] = None,
) -> SemanticAnalysisResult:
    """
    Perform deep semantic analysis on text content.

    Identifies semantic patterns, concepts, and relationships
    without full document extraction.
    """
    try:
        logger.info("Starting semantic pattern analysis")

        # Perform semantic analysis
        analysis_result = await semantic_extractor.analyze_semantic_content(
            content=content,
            context=context,
            language=language,
        )

        logger.info("Semantic pattern analysis completed")
        return analysis_result

    except Exception as e:
        logger.error(f"Semantic analysis failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Semantic analysis failed: {str(e)}"
        )


@app.get("/statistics")
async def get_extraction_statistics() -> Dict[str, Any]:
    """Get service statistics and performance metrics"""
    try:
        # Get knowledge graph statistics
        kg_stats = await memgraph_adapter.get_statistics() if memgraph_adapter else {}

        # Get extraction engine statistics
        extraction_stats = {
            "language_extractor": (
                await language_extractor.get_statistics() if language_extractor else {}
            ),
            "structured_extractor": (
                await structured_extractor.get_statistics()
                if structured_extractor
                else {}
            ),
            "semantic_extractor": (
                await semantic_extractor.get_statistics() if semantic_extractor else {}
            ),
        }

        # Get service performance metrics
        service_stats = {
            "uptime": _get_service_uptime(),
            "total_extractions": _get_total_extractions(),
            "average_extraction_time": _get_average_extraction_time(),
        }

        return {
            "service_statistics": service_stats,
            "extraction_statistics": extraction_stats,
            "knowledge_graph_statistics": kg_stats,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(
            status_code=500, detail=f"Statistics retrieval failed: {str(e)}"
        )


# Event Handling
async def handle_document_update_event(event: Dict[str, Any]):
    """Handle document update events from DocumentEventBus"""
    try:
        event_type = event.get("event_type")
        document_path = event.get("document_path")

        if not document_path:
            logger.warning("Received document event without document_path")
            return

        logger.info(f"Processing document event: {event_type} for {document_path}")

        # Create extraction request based on event
        extraction_request = DocumentExtractionRequest(
            document_path=document_path,
            extraction_options={
                "include_semantic_analysis": True,
                "update_knowledge_graph": True,
                "emit_events": True,
            },
        )

        # Perform extraction asynchronously
        background_tasks = BackgroundTasks()
        await extract_from_document(extraction_request, background_tasks)

        # Execute background tasks
        for task in background_tasks.tasks:
            await task.func(*task.args, **task.kwargs)

        logger.info(f"Document event processing completed for {document_path}")

    except Exception as e:
        logger.error(f"Document event handling failed: {e}")


# Helper Functions
async def _read_document_content(document_path: str) -> str:
    """Read document content from path"""
    try:
        path = Path(document_path)
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {document_path}")

        return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to read document {document_path}: {e}")
        raise


async def _update_knowledge_graph(
    entities: List[EnhancedEntity],
    relationships: List[EnhancedRelationship],
    document_path: str,
):
    """Update knowledge graph with extracted entities and relationships"""
    try:
        await memgraph_adapter.upsert_entities(entities)
        await memgraph_adapter.upsert_relationships(relationships)
        logger.info(f"Knowledge graph updated for {document_path}")
    except Exception as e:
        logger.error(f"Knowledge graph update failed for {document_path}: {e}")


async def _emit_extraction_event(response: ExtractionResponse):
    """Emit extraction completed event"""
    try:
        event = ExtractionCompletedEvent(
            extraction_id=response.extraction_id,
            document_path=response.document_path,
            entity_count=len(response.enriched_entities),
            relationship_count=len(response.relationships),
            confidence_score=response.extraction_statistics.confidence_score,
        )
        await event_emitter.emit_extraction_completed(event)
    except Exception as e:
        logger.error(f"Failed to emit extraction event: {e}")


def _calculate_overall_confidence(entities: List[Any]) -> float:
    """Calculate overall confidence score from entities"""
    if not entities:
        return 0.0

    # Handle both EnhancedEntity (confidence_score) and EntityEnrichment (confidence)
    total_confidence = sum(
        getattr(entity, "confidence_score", getattr(entity, "confidence", 0.0))
        for entity in entities
    )
    return total_confidence / len(entities)


def _get_service_uptime() -> float:
    """Get service uptime in seconds"""
    # Implementation would track service start time
    return 0.0


def _get_total_extractions() -> int:
    """Get total number of extractions performed"""
    # Implementation would track extraction counts
    return 0


def _get_average_extraction_time() -> float:
    """Get average extraction time in seconds"""
    # Implementation would track extraction performance
    return 0.0


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("LANGEXTRACT_SERVICE_PORT", "8156"))
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=True,
    )
