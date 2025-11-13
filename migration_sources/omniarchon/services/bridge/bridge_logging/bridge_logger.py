"""
Comprehensive Logging for Bridge Service

Enhanced logging for PostgreSQL-Memgraph Bridge Service including sync operations,
entity mapping, database operations, and performance monitoring.
"""

import json
import logging
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Context variables for request tracking
_bridge_request_id: ContextVar[Optional[str]] = ContextVar(
    "bridge_request_id", default=None
)
_bridge_correlation_id: ContextVar[Optional[str]] = ContextVar(
    "bridge_correlation_id", default=None
)


class BridgeLogger:
    """
    Comprehensive logger for Bridge service operations.

    Provides structured logging with correlation tracking, performance monitoring,
    and detailed sync operation logging.
    """

    def __init__(self, component_name: str = "bridge_service"):
        self.component_name = component_name
        self.logger = logging.getLogger(f"bridge.{component_name}")
        self.operation_timers: Dict[str, float] = {}

    def generate_request_id(self) -> str:
        """Generate a unique request ID."""
        return f"bridge_req_{uuid.uuid4().hex[:12]}_{int(time.time())}"

    def generate_correlation_id(self) -> str:
        """Generate a unique correlation ID."""
        return f"bridge_corr_{uuid.uuid4().hex[:8]}_{int(time.time())}"

    def get_current_context(self) -> Dict[str, Any]:
        """Get current request context information."""
        return {
            "request_id": _bridge_request_id.get(),
            "correlation_id": _bridge_correlation_id.get(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": self.component_name,
        }

    def set_request_context(
        self, request_id: Optional[str] = None, correlation_id: Optional[str] = None
    ):
        """Set request context for correlation tracking."""
        if request_id:
            _bridge_request_id.set(request_id)
        if correlation_id:
            _bridge_correlation_id.set(correlation_id)

    def log_sync_operation_start(
        self, operation_type: str, operation_details: Dict[str, Any]
    ) -> str:
        """Log start of sync operation."""
        request_id = self.generate_request_id()
        correlation_id = self.generate_correlation_id()

        self.set_request_context(request_id, correlation_id)
        self.operation_timers[request_id] = time.time()

        log_data = {
            **self.get_current_context(),
            "event_type": "sync_operation_start",
            "operation_type": operation_type,
            "operation_details": operation_details,
        }

        self.logger.info(
            f"🔄 Sync Operation Start | type={operation_type} | request_id={request_id}"
        )
        self._log_structured("INFO", "sync_operation_start", log_data)

        return request_id

    def log_sync_operation_complete(
        self,
        operation_type: str,
        results: Dict[str, Any],
        request_id: Optional[str] = None,
    ):
        """Log successful sync operation completion."""
        current_request_id = request_id or _bridge_request_id.get()

        duration_ms = 0
        if current_request_id and current_request_id in self.operation_timers:
            duration_ms = (
                time.time() - self.operation_timers[current_request_id]
            ) * 1000
            del self.operation_timers[current_request_id]

        log_data = {
            **self.get_current_context(),
            "event_type": "sync_operation_complete",
            "operation_type": operation_type,
            "duration_ms": round(duration_ms, 2),
            "results": results,
        }

        self.logger.info(
            f"✅ Sync Operation Complete | type={operation_type} | duration={duration_ms:.2f}ms | entities={results.get('entities_processed', 0)}"
        )
        self._log_structured("INFO", "sync_operation_complete", log_data)

    def log_sync_operation_error(
        self, operation_type: str, error: Exception, request_id: Optional[str] = None
    ):
        """Log sync operation error."""
        current_request_id = request_id or _bridge_request_id.get()

        duration_ms = 0
        if current_request_id and current_request_id in self.operation_timers:
            duration_ms = (
                time.time() - self.operation_timers[current_request_id]
            ) * 1000
            del self.operation_timers[current_request_id]

        log_data = {
            **self.get_current_context(),
            "event_type": "sync_operation_error",
            "operation_type": operation_type,
            "duration_ms": round(duration_ms, 2),
            "error": {"type": type(error).__name__, "message": str(error)},
        }

        self.logger.error(
            f"❌ Sync Operation Error | type={operation_type} | error={str(error)} | duration={duration_ms:.2f}ms"
        )
        self._log_structured("ERROR", "sync_operation_error", log_data)

    def log_entity_mapping(
        self, entity_type: str, entity_id: str, mapping_results: Dict[str, Any]
    ):
        """Log entity mapping operations."""
        log_data = {
            **self.get_current_context(),
            "event_type": "entity_mapping",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "mapping_results": mapping_results,
        }

        entities_created = mapping_results.get("entities_created", 0)
        relationships_created = mapping_results.get("relationships_created", 0)

        self.logger.info(
            f"🔗 Entity Mapping | type={entity_type} | id={entity_id} | entities={entities_created} | relationships={relationships_created}"
        )
        self._log_structured("INFO", "entity_mapping", log_data)

    def log_database_operation(
        self,
        database: str,
        operation: str,
        table: str,
        success: bool,
        affected_rows: Optional[int] = None,
        duration_ms: Optional[float] = None,
        error: Optional[Exception] = None,
    ):
        """Log database operations."""
        log_data = {
            **self.get_current_context(),
            "event_type": "database_operation",
            "database": database,
            "operation": operation,
            "table": table,
            "success": success,
            "affected_rows": affected_rows,
            "duration_ms": duration_ms,
        }

        if error:
            log_data["error"] = {"type": type(error).__name__, "message": str(error)}

        status_emoji = "✅" if success else "❌"
        message = f"{status_emoji} DB Operation | db={database} | op={operation} | table={table} | success={success}"
        if affected_rows is not None:
            message += f" | rows={affected_rows}"
        if duration_ms is not None:
            message += f" | duration={duration_ms:.2f}ms"

        if success:
            self.logger.info(message)
            self._log_structured("INFO", "database_operation", log_data)
        else:
            self.logger.error(message)
            self._log_structured("ERROR", "database_operation", log_data)

    def log_intelligence_service_call(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        response_status: int,
        response_time_ms: float,
        success: bool,
        error: Optional[str] = None,
    ):
        """Log calls to intelligence service."""
        log_data = {
            **self.get_current_context(),
            "event_type": "intelligence_service_call",
            "endpoint": endpoint,
            "payload_summary": {
                "document_id": payload.get("document_id"),
                "content_length": len(str(payload.get("content", ""))),
            },
            "response_status": response_status,
            "response_time_ms": response_time_ms,
            "success": success,
            "error": error,
        }

        status_emoji = "✅" if success else "❌"
        self.logger.info(
            f"{status_emoji} Intelligence Service | endpoint={endpoint} | status={response_status} | duration={response_time_ms:.2f}ms"
        )

        if success:
            self._log_structured("INFO", "intelligence_service_call", log_data)
        else:
            self._log_structured("ERROR", "intelligence_service_call", log_data)

    def log_realtime_document_processing(
        self,
        document_id: str,
        project_id: str,
        processing_steps: List[str],
        success: bool,
        duration_ms: float,
        entities_extracted: int = 0,
    ):
        """Log real-time document processing through the pipeline."""
        log_data = {
            **self.get_current_context(),
            "event_type": "realtime_document_processing",
            "document_id": document_id,
            "project_id": project_id,
            "processing_steps": processing_steps,
            "success": success,
            "duration_ms": duration_ms,
            "entities_extracted": entities_extracted,
        }

        status_emoji = "✅" if success else "❌"
        self.logger.info(
            f"{status_emoji} [INDEXING PIPELINE] Document Processing | doc_id={document_id} | entities={entities_extracted} | duration={duration_ms:.2f}ms"
        )

        if success:
            self._log_structured("INFO", "realtime_document_processing", log_data)
        else:
            self._log_structured("ERROR", "realtime_document_processing", log_data)

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

        if status == "healthy":
            self.logger.info(
                f"💚 Health Check | status=healthy | memgraph={memgraph_connected} | intelligence={intelligence_connected}"
            )
            self._log_structured("INFO", "health_check", log_data)
        elif status == "degraded":
            self.logger.warning(
                f"🟡 Health Check | status=degraded | memgraph={memgraph_connected} | intelligence={intelligence_connected}"
            )
            self._log_structured("WARNING", "health_check", log_data)
        else:
            self.logger.error(
                f"🔴 Health Check | status=unhealthy | memgraph={memgraph_connected} | intelligence={intelligence_connected}"
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
        }.get(status, "ℹ️")
        self.logger.info(
            f"{status_emoji} Bridge Startup | phase={phase} | status={status}"
        )

        level = "ERROR" if status == "error" else "INFO"
        self._log_structured(level, "startup_phase", log_data)

    def log_webhook_processing(
        self,
        webhook_type: str,
        payload_summary: Dict[str, Any],
        processing_result: Dict[str, Any],
    ):
        """Log webhook processing results."""
        log_data = {
            **self.get_current_context(),
            "event_type": "webhook_processing",
            "webhook_type": webhook_type,
            "payload_summary": payload_summary,
            "processing_result": processing_result,
        }

        success = processing_result.get("success", False)
        status_emoji = "✅" if success else "❌"

        self.logger.info(
            f"{status_emoji} Webhook Processing | type={webhook_type} | success={success}"
        )

        level = "INFO" if success else "ERROR"
        self._log_structured(level, "webhook_processing", log_data)

    def log_performance_metrics(self, operation: str, metrics: Dict[str, Any]):
        """Log performance metrics for bridge operations."""
        log_data = {
            **self.get_current_context(),
            "event_type": "performance_metrics",
            "operation": operation,
            "metrics": metrics,
        }

        self.logger.info(f"📊 Performance Metrics | operation={operation}")
        self._log_structured("INFO", "performance_metrics", log_data)

    def _log_structured(self, level: str, event: str, data: Dict[str, Any]):
        """Log structured entry in JSON format."""
        structured_entry = {
            "level": level,
            "event": event,
            "data": data,
            "service": "bridge",
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
bridge_logger = BridgeLogger()


def bridge_operation_logging(operation_name: str):
    """
    Decorator for automatic bridge operation logging.

    Usage:
        @bridge_operation_logging("full_sync")
        async def perform_full_sync():
            # Operation implementation
            pass
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Start logging
            request_id = bridge_logger.log_sync_operation_start(
                operation_name,
                {
                    "function": f"{func.__module__}.{func.__name__}",
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys()),
                },
            )

            try:
                # Execute the operation
                result = await func(*args, **kwargs)

                # Log success
                bridge_logger.log_sync_operation_complete(
                    operation_name,
                    {"result_type": type(result).__name__, "success": True},
                    request_id,
                )

                return result

            except Exception as e:
                # Log error
                bridge_logger.log_sync_operation_error(operation_name, e, request_id)
                raise

        return wrapper

    return decorator


# Export key components
__all__ = ["BridgeLogger", "bridge_logger", "bridge_operation_logging"]
