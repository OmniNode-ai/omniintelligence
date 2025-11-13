"""
Comprehensive Logging for Search Service

Enhanced logging for Search Service including query processing, vector search,
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
_search_request_id: ContextVar[Optional[str]] = ContextVar(
    "search_request_id", default=None
)
_search_correlation_id: ContextVar[Optional[str]] = ContextVar(
    "search_correlation_id", default=None
)
_pipeline_correlation_id: ContextVar[Optional[str]] = ContextVar(
    "pipeline_correlation_id", default=None
)


class SearchLogger:
    """
    Comprehensive logger for Search service operations.

    Provides structured logging with correlation tracking, performance monitoring,
    and detailed query processing, vectorization, and Qdrant operation logging.
    """

    def __init__(self, component_name: str = "search_service"):
        self.component_name = component_name
        self.logger = logging.getLogger(f"search.{component_name}")
        self.operation_timers: Dict[str, float] = {}

    def generate_request_id(self) -> str:
        """Generate a unique request ID."""
        return f"search_req_{uuid.uuid4().hex[:12]}_{int(time.time())}"

    def generate_correlation_id(self) -> str:
        """Generate a unique correlation ID."""
        return f"search_corr_{uuid.uuid4().hex[:8]}_{int(time.time())}"

    def inherit_pipeline_correlation(self, pipeline_correlation_id: str):
        """Inherit correlation ID from document processing pipeline."""
        _pipeline_correlation_id.set(pipeline_correlation_id)

    def get_current_context(self) -> Dict[str, Any]:
        """Get current request context information."""
        return {
            "request_id": _search_request_id.get(),
            "correlation_id": _search_correlation_id.get(),
            "pipeline_correlation_id": _pipeline_correlation_id.get(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": self.component_name,
            "service": "search",
        }

    def set_request_context(
        self,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        pipeline_correlation_id: Optional[str] = None,
    ):
        """Set request context for correlation tracking."""
        if request_id:
            _search_request_id.set(request_id)
        if correlation_id:
            _search_correlation_id.set(correlation_id)
        if pipeline_correlation_id:
            _pipeline_correlation_id.set(pipeline_correlation_id)

    def log_search_query_start(
        self, query: str, search_mode: str, search_params: Dict[str, Any]
    ) -> str:
        """Log start of search query operation."""
        request_id = self.generate_request_id()
        correlation_id = self.generate_correlation_id()

        self.set_request_context(request_id, correlation_id)
        self.operation_timers[request_id] = time.time()

        log_data = {
            **self.get_current_context(),
            "event_type": "search_query_start",
            "query": (
                query[:100] + "..." if len(query) > 100 else query
            ),  # Truncate long queries
            "search_mode": search_mode,
            "search_params": search_params,
        }

        self.logger.info(
            f"🔍 Search Query Start | mode={search_mode} | query_length={len(query)} | request_id={request_id}"
        )
        self._log_structured("INFO", "search_query_start", log_data)

        return request_id

    def log_search_query_complete(
        self,
        query: str,
        search_mode: str,
        results_count: int,
        search_components: Dict[str, Any],
        request_id: Optional[str] = None,
    ):
        """Log successful search query completion."""
        current_request_id = request_id or _search_request_id.get()

        duration_ms = 0
        if current_request_id and current_request_id in self.operation_timers:
            duration_ms = (
                time.time() - self.operation_timers[current_request_id]
            ) * 1000
            del self.operation_timers[current_request_id]

        log_data = {
            **self.get_current_context(),
            "event_type": "search_query_complete",
            "query": query[:100] + "..." if len(query) > 100 else query,
            "search_mode": search_mode,
            "duration_ms": round(duration_ms, 2),
            "results_count": results_count,
            "search_components": search_components,
        }

        self.logger.info(
            f"✅ Search Query Complete | mode={search_mode} | results={results_count} | duration={duration_ms:.2f}ms"
        )
        self._log_structured("INFO", "search_query_complete", log_data)

    def log_search_query_error(
        self,
        query: str,
        search_mode: str,
        error: Exception,
        error_stage: str,
        request_id: Optional[str] = None,
    ):
        """Log search query error."""
        current_request_id = request_id or _search_request_id.get()

        duration_ms = 0
        if current_request_id and current_request_id in self.operation_timers:
            duration_ms = (
                time.time() - self.operation_timers[current_request_id]
            ) * 1000
            del self.operation_timers[current_request_id]

        log_data = {
            **self.get_current_context(),
            "event_type": "search_query_error",
            "query": query[:100] + "..." if len(query) > 100 else query,
            "search_mode": search_mode,
            "error_stage": error_stage,
            "duration_ms": round(duration_ms, 2),
            "error": {"type": type(error).__name__, "message": str(error)},
        }

        self.logger.error(
            f"❌ Search Query Error | mode={search_mode} | stage={error_stage} | error={str(error)} | duration={duration_ms:.2f}ms"
        )
        self._log_structured("ERROR", "search_query_error", log_data)

    def log_vector_search_operation(
        self,
        query: str,
        collection_name: str,
        vector_results_count: int,
        similarity_threshold: float,
        search_duration_ms: float,
        success: bool,
    ):
        """Log vector search operations against Qdrant."""
        log_data = {
            **self.get_current_context(),
            "event_type": "vector_search_operation",
            "query": query[:100] + "..." if len(query) > 100 else query,
            "collection_name": collection_name,
            "vector_results_count": vector_results_count,
            "similarity_threshold": similarity_threshold,
            "search_duration_ms": search_duration_ms,
            "success": success,
        }

        status_emoji = "✅" if success else "❌"
        self.logger.info(
            f"{status_emoji} Vector Search | collection={collection_name} | results={vector_results_count} | threshold={similarity_threshold} | duration={search_duration_ms:.2f}ms"
        )

        if success:
            self._log_structured("INFO", "vector_search_operation", log_data)
        else:
            self._log_structured("ERROR", "vector_search_operation", log_data)

    def log_qdrant_operation(
        self,
        operation_type: str,
        collection_name: str,
        points_affected: int,
        success: bool,
        duration_ms: float,
        error: Optional[Exception] = None,
    ):
        """Log Qdrant database operations."""
        log_data = {
            **self.get_current_context(),
            "event_type": "qdrant_operation",
            "operation_type": operation_type,
            "collection_name": collection_name,
            "points_affected": points_affected,
            "success": success,
            "duration_ms": duration_ms,
        }

        if error:
            log_data["error"] = {"type": type(error).__name__, "message": str(error)}

        status_emoji = "✅" if success else "❌"
        message = f"{status_emoji} Qdrant Operation | op={operation_type} | collection={collection_name} | points={points_affected} | duration={duration_ms:.2f}ms"

        if success:
            self.logger.info(message)
            self._log_structured("INFO", "qdrant_operation", log_data)
        else:
            self.logger.error(message)
            self._log_structured("ERROR", "qdrant_operation", log_data)

    def log_document_vectorization(
        self,
        document_id: str,
        vector_id: str,
        content_length: int,
        embedding_dimensions: int,
        collection_name: str,
        success: bool,
        duration_ms: float,
    ):
        """Log document vectorization and storage operations."""
        log_data = {
            **self.get_current_context(),
            "event_type": "document_vectorization",
            "document_id": document_id,
            "vector_id": vector_id,
            "content_length": content_length,
            "embedding_dimensions": embedding_dimensions,
            "collection_name": collection_name,
            "success": success,
            "duration_ms": duration_ms,
        }

        status_emoji = "✅" if success else "❌"
        self.logger.info(
            f"{status_emoji} [INDEXING PIPELINE] Document Vectorization | doc_id={document_id} | vector_id={vector_id} | dims={embedding_dimensions} | duration={duration_ms:.2f}ms"
        )

        if success:
            self._log_structured("INFO", "document_vectorization", log_data)
        else:
            self._log_structured("ERROR", "document_vectorization", log_data)

    def log_hybrid_search_orchestration(
        self,
        query: str,
        search_components: List[str],
        component_results: Dict[str, int],
        final_results_count: int,
        orchestration_duration_ms: float,
    ):
        """Log hybrid search orchestration across multiple search methods."""
        log_data = {
            **self.get_current_context(),
            "event_type": "hybrid_search_orchestration",
            "query": query[:100] + "..." if len(query) > 100 else query,
            "search_components": search_components,
            "component_results": component_results,
            "final_results_count": final_results_count,
            "orchestration_duration_ms": orchestration_duration_ms,
        }

        self.logger.info(
            f"🔗 Hybrid Search Orchestration | components={len(search_components)} | final_results={final_results_count} | duration={orchestration_duration_ms:.2f}ms"
        )
        self._log_structured("INFO", "hybrid_search_orchestration", log_data)

    def log_memgraph_graph_search(
        self,
        query: str,
        relationship_types: List[str],
        max_depth: int,
        graph_results_count: int,
        search_duration_ms: float,
        success: bool,
    ):
        """Log graph search operations against Memgraph."""
        log_data = {
            **self.get_current_context(),
            "event_type": "memgraph_graph_search",
            "query": query[:100] + "..." if len(query) > 100 else query,
            "relationship_types": relationship_types,
            "max_depth": max_depth,
            "graph_results_count": graph_results_count,
            "search_duration_ms": search_duration_ms,
            "success": success,
        }

        status_emoji = "✅" if success else "❌"
        self.logger.info(
            f"{status_emoji} Graph Search | relationships={len(relationship_types)} | depth={max_depth} | results={graph_results_count} | duration={search_duration_ms:.2f}ms"
        )

        if success:
            self._log_structured("INFO", "memgraph_graph_search", log_data)
        else:
            self._log_structured("ERROR", "memgraph_graph_search", log_data)

    def log_search_result_ranking(
        self,
        query: str,
        raw_results_count: int,
        ranked_results_count: int,
        ranking_algorithm: str,
        ranking_duration_ms: float,
    ):
        """Log search result ranking and scoring operations."""
        log_data = {
            **self.get_current_context(),
            "event_type": "search_result_ranking",
            "query": query[:100] + "..." if len(query) > 100 else query,
            "raw_results_count": raw_results_count,
            "ranked_results_count": ranked_results_count,
            "ranking_algorithm": ranking_algorithm,
            "ranking_duration_ms": ranking_duration_ms,
        }

        self.logger.info(
            f"📊 Search Result Ranking | algorithm={ranking_algorithm} | raw={raw_results_count} | ranked={ranked_results_count} | duration={ranking_duration_ms:.2f}ms"
        )
        self._log_structured("INFO", "search_result_ranking", log_data)

    def log_health_check(self, health_status: Dict[str, Any]):
        """Log health check results."""
        log_data = {
            **self.get_current_context(),
            "event_type": "health_check",
            "health_status": health_status,
        }

        status = health_status.get("status", "unknown")
        memgraph_connected = health_status.get("memgraph_connected", False)
        intelligence_connected = health_status.get("intelligence_connected", False)
        bridge_connected = health_status.get("bridge_connected", False)
        embedding_service_connected = health_status.get(
            "embedding_service_connected", False
        )
        vector_index_ready = health_status.get("vector_index_ready", False)

        if status == "healthy":
            self.logger.info(
                f"💚 Health Check | status=healthy | memgraph={memgraph_connected} | intelligence={intelligence_connected} | bridge={bridge_connected} | embedding={embedding_service_connected} | vector_index={vector_index_ready}"
            )
            self._log_structured("INFO", "health_check", log_data)
        elif status == "degraded":
            self.logger.warning(
                f"🟡 Health Check | status=degraded | memgraph={memgraph_connected} | intelligence={intelligence_connected} | bridge={bridge_connected} | embedding={embedding_service_connected} | vector_index={vector_index_ready}"
            )
            self._log_structured("WARNING", "health_check", log_data)
        else:
            self.logger.error(
                f"🔴 Health Check | status=unhealthy | memgraph={memgraph_connected} | intelligence={intelligence_connected} | bridge={bridge_connected} | embedding={embedding_service_connected} | vector_index={vector_index_ready}"
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
            f"{status_emoji} Search Startup | phase={phase} | status={status}"
        )

        level = (
            "ERROR"
            if status == "error"
            else "WARNING" if status == "warning" else "INFO"
        )
        self._log_structured(level, "startup_phase", log_data)

    def log_performance_metrics(self, operation: str, metrics: Dict[str, Any]):
        """Log performance metrics for search operations."""
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
            "service": "search",
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
search_logger = SearchLogger()


def search_operation_logging(operation_name: str):
    """
    Decorator for automatic search operation logging.

    Usage:
        @search_operation_logging("hybrid_search")
        async def perform_search():
            # Operation implementation
            pass
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Start logging
            request_id = search_logger.generate_request_id()
            correlation_id = search_logger.generate_correlation_id()
            search_logger.set_request_context(request_id, correlation_id)

            start_time = time.time()
            search_logger.operation_timers[request_id] = start_time

            try:
                # Execute the operation
                result = await func(*args, **kwargs)

                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000

                # Log success
                search_logger.logger.info(
                    f"✅ Operation Complete | {operation_name} | duration={duration_ms:.2f}ms"
                )

                return result

            except Exception as e:
                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000

                # Log error
                search_logger.logger.error(
                    f"❌ Operation Error | {operation_name} | error={str(e)} | duration={duration_ms:.2f}ms"
                )
                raise
            finally:
                # Clean up timer
                if request_id in search_logger.operation_timers:
                    del search_logger.operation_timers[request_id]

        return wrapper

    return decorator


# Export key components
__all__ = ["SearchLogger", "search_logger", "search_operation_logging"]
