"""
Comprehensive Logging for Intelligence Service

Enhanced logging for Intelligence Service including entity extraction, vectorization,
Qdrant operations, and performance monitoring with full correlation tracking.
"""

import json
import logging
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Context variables for cross-service correlation tracking
_intelligence_request_id: ContextVar[Optional[str]] = ContextVar(
    "intelligence_request_id", default=None
)
_intelligence_correlation_id: ContextVar[Optional[str]] = ContextVar(
    "intelligence_correlation_id", default=None
)
_pipeline_correlation_id: ContextVar[Optional[str]] = ContextVar(
    "pipeline_correlation_id", default=None
)


class IntelligenceLogger:
    """
    Comprehensive logger for Intelligence service operations.

    Provides structured logging with correlation tracking, performance monitoring,
    and detailed entity extraction, vectorization, and Qdrant operation logging.
    """

    def __init__(self, component_name: str = "intelligence_service"):
        self.component_name = component_name
        self.logger = logging.getLogger(f"intelligence.{component_name}")
        self.operation_timers: Dict[str, float] = {}

    def generate_request_id(self) -> str:
        """Generate a unique request ID."""
        return f"intel_req_{uuid.uuid4().hex[:12]}_{int(time.time())}"

    def generate_correlation_id(self) -> str:
        """Generate a unique correlation ID."""
        return f"intel_corr_{uuid.uuid4().hex[:8]}_{int(time.time())}"

    def inherit_pipeline_correlation(self, pipeline_correlation_id: str):
        """Inherit correlation ID from document processing pipeline."""
        _pipeline_correlation_id.set(pipeline_correlation_id)

    def get_current_context(self) -> Dict[str, Any]:
        """Get current request context information."""
        return {
            "request_id": _intelligence_request_id.get(),
            "correlation_id": _intelligence_correlation_id.get(),
            "pipeline_correlation_id": _pipeline_correlation_id.get(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": self.component_name,
            "service": "intelligence",
        }

    def set_request_context(
        self,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        pipeline_correlation_id: Optional[str] = None,
    ):
        """Set request context for correlation tracking."""
        if request_id:
            _intelligence_request_id.set(request_id)
        if correlation_id:
            _intelligence_correlation_id.set(correlation_id)
        if pipeline_correlation_id:
            _pipeline_correlation_id.set(pipeline_correlation_id)

    def log_document_processing_start(
        self,
        document_id: str,
        project_id: str,
        content_length: int,
        processing_details: Dict[str, Any],
    ) -> str:
        """Log start of document processing operation."""
        request_id = self.generate_request_id()
        correlation_id = self.generate_correlation_id()

        self.set_request_context(request_id, correlation_id)
        self.operation_timers[request_id] = time.time()

        log_data = {
            **self.get_current_context(),
            "event_type": "document_processing_start",
            "document_id": document_id,
            "project_id": project_id,
            "content_length": content_length,
            "processing_details": processing_details,
        }

        self.logger.info(
            f"🔬 [INDEXING PIPELINE] Document Processing Start | doc_id={document_id} | project_id={project_id} | content_length={content_length}"
        )
        self._log_structured("INFO", "document_processing_start", log_data)

        return request_id

    def log_document_processing_complete(
        self,
        document_id: str,
        entities_extracted: int,
        vectorization_result: Dict[str, Any],
        request_id: Optional[str] = None,
    ):
        """Log successful document processing completion."""
        current_request_id = request_id or _intelligence_request_id.get()

        duration_ms = 0
        if current_request_id and current_request_id in self.operation_timers:
            duration_ms = (
                time.time() - self.operation_timers[current_request_id]
            ) * 1000
            del self.operation_timers[current_request_id]

        log_data = {
            **self.get_current_context(),
            "event_type": "document_processing_complete",
            "document_id": document_id,
            "duration_ms": round(duration_ms, 2),
            "entities_extracted": entities_extracted,
            "vectorization_result": vectorization_result,
        }

        self.logger.info(
            f"✅ [INDEXING PIPELINE] Document Processing Complete | doc_id={document_id} | entities={entities_extracted} | duration={duration_ms:.2f}ms"
        )
        self._log_structured("INFO", "document_processing_complete", log_data)

    def log_document_processing_error(
        self,
        document_id: str,
        error: Exception,
        processing_stage: str,
        request_id: Optional[str] = None,
    ):
        """Log document processing error."""
        current_request_id = request_id or _intelligence_request_id.get()

        duration_ms = 0
        if current_request_id and current_request_id in self.operation_timers:
            duration_ms = (
                time.time() - self.operation_timers[current_request_id]
            ) * 1000
            del self.operation_timers[current_request_id]

        log_data = {
            **self.get_current_context(),
            "event_type": "document_processing_error",
            "document_id": document_id,
            "processing_stage": processing_stage,
            "duration_ms": round(duration_ms, 2),
            "error": {"type": type(error).__name__, "message": str(error)},
        }

        self.logger.error(
            f"❌ [INDEXING PIPELINE] Document Processing Error | doc_id={document_id} | stage={processing_stage} | error={str(error)} | duration={duration_ms:.2f}ms"
        )
        self._log_structured("ERROR", "document_processing_error", log_data)

    def log_entity_extraction(
        self,
        document_id: str,
        source_path: str,
        entities_found: int,
        extraction_time_ms: float,
        entity_types: List[str],
    ):
        """Log entity extraction operations."""
        log_data = {
            **self.get_current_context(),
            "event_type": "entity_extraction",
            "document_id": document_id,
            "source_path": source_path,
            "entities_found": entities_found,
            "extraction_time_ms": extraction_time_ms,
            "entity_types": entity_types,
        }

        self.logger.info(
            f"🧠 [INDEXING PIPELINE] Entity Extraction | doc_id={document_id} | entities={entities_found} | types={len(entity_types)} | duration={extraction_time_ms:.2f}ms"
        )
        self._log_structured("INFO", "entity_extraction", log_data)

    def log_memgraph_operation(
        self,
        operation_type: str,
        entity_count: int,
        success: bool,
        duration_ms: float,
        error: Optional[Exception] = None,
    ):
        """Log Memgraph knowledge graph operations."""
        log_data = {
            **self.get_current_context(),
            "event_type": "memgraph_operation",
            "operation_type": operation_type,
            "entity_count": entity_count,
            "success": success,
            "duration_ms": duration_ms,
        }

        if error:
            log_data["error"] = {"type": type(error).__name__, "message": str(error)}

        status_emoji = "✅" if success else "❌"
        message = f"{status_emoji} [INDEXING PIPELINE] Memgraph Operation | op={operation_type} | entities={entity_count} | success={success} | duration={duration_ms:.2f}ms"

        if success:
            self.logger.info(message)
            self._log_structured("INFO", "memgraph_operation", log_data)
        else:
            self.logger.error(message)
            self._log_structured("ERROR", "memgraph_operation", log_data)

    def log_search_service_call(
        self,
        endpoint: str,
        payload_summary: Dict[str, Any],
        response_status: int,
        response_time_ms: float,
        success: bool,
        result_summary: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        """Log calls to search service for vectorization."""
        log_data = {
            **self.get_current_context(),
            "event_type": "search_service_call",
            "endpoint": endpoint,
            "payload_summary": payload_summary,
            "response_status": response_status,
            "response_time_ms": response_time_ms,
            "success": success,
            "result_summary": result_summary,
            "error": error,
        }

        status_emoji = "✅" if success else "❌"
        self.logger.info(
            f"{status_emoji} [INDEXING PIPELINE] Search Service Call | endpoint={endpoint} | status={response_status} | duration={response_time_ms:.2f}ms"
        )

        if success:
            self._log_structured("INFO", "search_service_call", log_data)
        else:
            self._log_structured("ERROR", "search_service_call", log_data)

    def log_vectorization_operation(
        self,
        document_id: str,
        vector_id: str,
        content_length: int,
        embedding_dimensions: int,
        success: bool,
        duration_ms: float,
        qdrant_response: Optional[Dict[str, Any]] = None,
    ):
        """Log vectorization and Qdrant storage operations."""
        log_data = {
            **self.get_current_context(),
            "event_type": "vectorization_operation",
            "document_id": document_id,
            "vector_id": vector_id,
            "content_length": content_length,
            "embedding_dimensions": embedding_dimensions,
            "success": success,
            "duration_ms": duration_ms,
            "qdrant_response": qdrant_response,
        }

        status_emoji = "✅" if success else "❌"
        self.logger.info(
            f"{status_emoji} [INDEXING PIPELINE] Vectorization | doc_id={document_id} | vector_id={vector_id} | dims={embedding_dimensions} | duration={duration_ms:.2f}ms"
        )

        if success:
            self._log_structured("INFO", "vectorization_operation", log_data)
        else:
            self._log_structured("ERROR", "vectorization_operation", log_data)

    def log_quality_assessment(
        self,
        content_type: str,
        assessment_type: str,
        quality_score: float,
        assessment_details: Dict[str, Any],
        duration_ms: float,
    ):
        """Log quality assessment operations."""
        log_data = {
            **self.get_current_context(),
            "event_type": "quality_assessment",
            "content_type": content_type,
            "assessment_type": assessment_type,
            "quality_score": quality_score,
            "assessment_details": assessment_details,
            "duration_ms": duration_ms,
        }

        self.logger.info(
            f"📊 Quality Assessment | type={assessment_type} | score={quality_score:.3f} | duration={duration_ms:.2f}ms"
        )
        self._log_structured("INFO", "quality_assessment", log_data)

    def log_performance_baseline(
        self,
        operation_name: str,
        baseline_metrics: Dict[str, Any],
        measurement_duration_minutes: int,
    ):
        """Log performance baseline establishment."""
        log_data = {
            **self.get_current_context(),
            "event_type": "performance_baseline",
            "operation_name": operation_name,
            "baseline_metrics": baseline_metrics,
            "measurement_duration_minutes": measurement_duration_minutes,
        }

        self.logger.info(
            f"📈 Performance Baseline | operation={operation_name} | avg_response={baseline_metrics.get('average_response_time_ms', 0):.2f}ms"
        )
        self._log_structured("INFO", "performance_baseline", log_data)

    def log_freshness_analysis(
        self,
        document_path: str,
        freshness_score: float,
        is_stale: bool,
        dependencies_count: int,
        analysis_duration_ms: float,
    ):
        """Log document freshness analysis operations."""
        log_data = {
            **self.get_current_context(),
            "event_type": "freshness_analysis",
            "document_path": document_path,
            "freshness_score": freshness_score,
            "is_stale": is_stale,
            "dependencies_count": dependencies_count,
            "analysis_duration_ms": analysis_duration_ms,
        }

        staleness_emoji = "🟡" if is_stale else "💚"
        self.logger.info(
            f"{staleness_emoji} Freshness Analysis | path={document_path} | score={freshness_score:.3f} | stale={is_stale} | deps={dependencies_count}"
        )
        self._log_structured("INFO", "freshness_analysis", log_data)

    def log_health_check(self, health_status: Dict[str, Any]):
        """Log health check results."""
        log_data = {
            **self.get_current_context(),
            "event_type": "health_check",
            "health_status": health_status,
        }

        status = health_status.get("status", "unknown")
        memgraph_connected = health_status.get("memgraph_connected", False)
        embedding_service_connected = health_status.get(
            "embedding_service_connected", health_status.get("ollama_connected", False)
        )  # Backward compatible
        freshness_db_connected = health_status.get(
            "freshness_database_connected", False
        )

        if status == "healthy":
            self.logger.info(
                f"💚 Health Check | status=healthy | memgraph={memgraph_connected} | embedding_service={embedding_service_connected} | freshness_db={freshness_db_connected}"
            )
            self._log_structured("INFO", "health_check", log_data)
        elif status == "degraded":
            self.logger.warning(
                f"🟡 Health Check | status=degraded | memgraph={memgraph_connected} | embedding_service={embedding_service_connected} | freshness_db={freshness_db_connected}"
            )
            self._log_structured("WARNING", "health_check", log_data)
        else:
            self.logger.error(
                f"🔴 Health Check | status=unhealthy | memgraph={memgraph_connected} | embedding_service={embedding_service_connected} | freshness_db={freshness_db_connected}"
            )
            self._log_structured("ERROR", "health_check", log_data)

    def log_startup_phase(
        self, phase: str, status: str, details: Optional[Dict[str, Any]] = None
    ):
        """Log startup sequence phases."""
        log_data = {
            **self.get_current_context(),
            "event_type": "startup_phase",
            "phase": phase,
            "status": status,
            "details": details or {},
        }

        status_emoji = {
            "start": "🚀",
            "progress": "⚙️",
            "success": "✅",
            "error": "❌",
            "warning": "⚠️",
        }.get(status, "ℹ️")
        self.logger.info(
            f"{status_emoji} Intelligence Startup | phase={phase} | status={status}"
        )

        level = (
            "ERROR"
            if status == "error"
            else "WARNING" if status == "warning" else "INFO"
        )
        self._log_structured(level, "startup_phase", log_data)

    def log_performance_metrics(self, operation: str, metrics: Dict[str, Any]):
        """Log performance metrics for intelligence operations."""
        log_data = {
            **self.get_current_context(),
            "event_type": "performance_metrics",
            "operation": operation,
            "metrics": metrics,
        }

        self.logger.info(f"📊 Performance Metrics | operation={operation}")
        self._log_structured("INFO", "performance_metrics", log_data)

    def log_pipeline_correlation(
        self,
        document_id: str,
        pipeline_stage: str,
        upstream_correlation_id: Optional[str] = None,
        downstream_correlation_id: Optional[str] = None,
    ):
        """Log pipeline correlation for end-to-end tracking."""
        log_data = {
            **self.get_current_context(),
            "event_type": "pipeline_correlation",
            "document_id": document_id,
            "pipeline_stage": pipeline_stage,
            "upstream_correlation_id": upstream_correlation_id,
            "downstream_correlation_id": downstream_correlation_id,
        }

        self.logger.info(
            f"🔗 [PIPELINE CORRELATION] | doc_id={document_id} | stage={pipeline_stage} | upstream={upstream_correlation_id} | downstream={downstream_correlation_id}"
        )
        self._log_structured("INFO", "pipeline_correlation", log_data)

    def _log_structured(self, level: str, event: str, data: Dict[str, Any]):
        """Log structured entry in JSON format."""
        structured_entry = {
            "level": level,
            "event": event,
            "data": data,
            "service": "intelligence",
        }

        # Log as JSON for structured logging systems
        json_message = json.dumps(structured_entry, default=str)

        if level == "DEBUG":
            self.logger.debug(f"[STRUCTURED] {json_message}")
        elif level == "INFO":
            self.logger.info(f"[STRUCTURED] {json_message}")
        elif level == "WARNING":
            self.logger.warning(f"[STRUCTURED] {json_message}")
        elif level == "ERROR":
            self.logger.error(f"[STRUCTURED] {json_message}")


# Global logger instance
intelligence_logger = IntelligenceLogger()


def intelligence_operation_logging(operation_name: str):
    """
    Decorator for automatic intelligence operation logging.

    Usage:
        @intelligence_operation_logging("entity_extraction")
        async def extract_entities():
            # Operation implementation
            pass
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Start logging
            request_id = intelligence_logger.generate_request_id()
            correlation_id = intelligence_logger.generate_correlation_id()
            intelligence_logger.set_request_context(request_id, correlation_id)

            start_time = time.time()
            intelligence_logger.operation_timers[request_id] = start_time

            try:
                # Execute the operation
                result = await func(*args, **kwargs)

                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000

                # Log success
                intelligence_logger.logger.info(
                    f"✅ Operation Complete | {operation_name} | duration={duration_ms:.2f}ms"
                )

                return result

            except Exception as e:
                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000

                # Log error
                intelligence_logger.logger.error(
                    f"❌ Operation Error | {operation_name} | error={str(e)} | duration={duration_ms:.2f}ms"
                )
                raise
            finally:
                # Clean up timer
                if request_id in intelligence_logger.operation_timers:
                    del intelligence_logger.operation_timers[request_id]

        return wrapper

    return decorator


# Export key components
__all__ = [
    "IntelligenceLogger",
    "intelligence_logger",
    "intelligence_operation_logging",
]
