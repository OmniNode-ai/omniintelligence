"""
Structured Logging Utility for Correlation Processing Pipeline

Provides comprehensive structured logging for the correlation processing pipeline
to enable visibility into processing errors, data flow issues, and performance
bottlenecks throughout the entire system.

Key Features:
- Correlation ID tracking for end-to-end request tracing
- Structured log formatting with consistent metadata
- Performance timing and metrics logging
- Data transformation logging with before/after states
- Error context preservation with full stack traces
- Intelligence data flow tracking
- Processing stage identification

Usage:
    from ..utils.correlation_logging import CorrelationLogger

    logger = CorrelationLogger("service_name")

    with logger.correlation_context("unique_correlation_id"):
        logger.log_processing_start("document_analysis", {"doc_id": "123"})
        # ... processing logic ...
        logger.log_processing_complete("document_analysis", {"correlations_found": 5})
"""

import json
import logging
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from functools import wraps
from typing import Any, Optional

# Context variable for correlation ID tracking
_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def safe_json_dumps(obj: Any, max_depth: int = 10) -> str:
    """
    Safely serialize objects to JSON, handling circular references.

    Args:
        obj: Object to serialize
        max_depth: Maximum depth to prevent infinite recursion

    Returns:
        JSON string representation
    """
    seen = set()

    def _serialize(obj, current_depth=0):
        # Prevent infinite recursion
        if current_depth > max_depth:
            return f"<max_depth_reached:{type(obj).__name__}>"

        # Handle circular references
        obj_id = id(obj)
        if obj_id in seen:
            return f"<circular_reference:{type(obj).__name__}>"

        # Handle basic types that don't need tracking
        if obj is None or isinstance(obj, bool | int | float | str):
            return obj

        # Track this object
        seen.add(obj_id)

        try:
            if isinstance(obj, dict):
                result = {}
                for key, value in obj.items():
                    try:
                        # Ensure key is serializable
                        if isinstance(key, str | int | float | bool):
                            result[key] = _serialize(value, current_depth + 1)
                        else:
                            result[str(key)] = _serialize(value, current_depth + 1)
                    except Exception:
                        result[str(key)] = (
                            f"<serialization_error:{type(value).__name__}>"
                        )
                return result
            elif isinstance(obj, list | tuple):
                result = []
                for item in obj:
                    try:
                        result.append(_serialize(item, current_depth + 1))
                    except Exception:
                        result.append(f"<serialization_error:{type(item).__name__}>")
                return result
            elif hasattr(obj, "__dict__"):
                # Handle custom objects
                try:
                    return _serialize(obj.__dict__, current_depth + 1)
                except Exception:
                    return f"<object:{type(obj).__name__}>"
            else:
                # Fallback to string representation
                try:
                    return str(obj)
                except Exception:
                    return f"<unserializable:{type(obj).__name__}>"
        finally:
            # Remove from seen set when done processing
            seen.discard(obj_id)

    try:
        serialized = _serialize(obj)
        return json.dumps(serialized, default=str, ensure_ascii=False)
    except Exception as e:
        # Fallback for any remaining errors
        return json.dumps(
            {
                "serialization_error": str(e),
                "object_type": type(obj).__name__,
                "object_repr": (
                    str(obj)[:200] + "..." if len(str(obj)) > 200 else str(obj)
                ),
            }
        )


class CorrelationLogger:
    """
    Structured logger for correlation processing pipeline.

    Provides consistent logging format, correlation ID tracking, and specialized
    logging methods for different aspects of correlation processing.
    """

    def __init__(self, component_name: str, logger_name: Optional[str] = None):
        """
        Initialize correlation logger.

        Args:
            component_name: Name of the component using this logger
            logger_name: Custom logger name (defaults to component_name)
        """
        self.component_name = component_name
        self.logger = logging.getLogger(logger_name or component_name)
        self.processing_timers: dict[str, float] = {}

    @contextmanager
    def correlation_context(self, correlation_id: Optional[str] = None):
        """
        Context manager for correlation ID tracking.

        Args:
            correlation_id: Correlation ID (generates one if None)
        """
        if correlation_id is None:
            correlation_id = self.generate_correlation_id()

        token = _correlation_id.set(correlation_id)
        try:
            self.log_info(
                "correlation_context_start",
                {"correlation_id": correlation_id, "component": self.component_name},
            )
            yield correlation_id
        finally:
            _correlation_id.reset(token)

    def generate_correlation_id(self) -> str:
        """Generate a unique correlation ID."""
        return f"corr_{uuid.uuid4().hex[:8]}_{int(time.time())}"

    def get_correlation_id(self) -> Optional[str]:
        """Get the current correlation ID."""
        return _correlation_id.get()

    def _create_log_entry(
        self,
        level: str,
        event: str,
        data: dict[str, Any],
        error: Optional[Exception] = None,
    ) -> dict[str, Any]:
        """Create a structured log entry."""
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": level,
            "component": self.component_name,
            "event": event,
            "correlation_id": self.get_correlation_id(),
            "data": data,
        }

        if error:
            entry["error"] = {
                "type": type(error).__name__,
                "message": str(error),
                "stack_trace": self._get_stack_trace(error),
            }

        return entry

    def _get_stack_trace(self, error: Exception) -> str:
        """Get formatted stack trace from exception."""
        import traceback

        return "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )

    def _log_structured(
        self,
        level: str,
        event: str,
        data: dict[str, Any],
        error: Optional[Exception] = None,
    ):
        """Log structured entry."""
        entry = self._create_log_entry(level, event, data, error)
        log_message = f"[{self.component_name}] {event}: {safe_json_dumps(entry)}"

        if level == "DEBUG":
            self.logger.debug(log_message)
        elif level == "INFO":
            self.logger.info(log_message)
        elif level == "WARNING":
            self.logger.warning(log_message)
        elif level == "ERROR":
            self.logger.error(log_message)
        elif level == "CRITICAL":
            self.logger.critical(log_message)

    # Standard logging methods
    def log_debug(self, event: str, data: dict[str, Any]):
        """Log debug information."""
        self._log_structured("DEBUG", event, data)

    def log_info(self, event: str, data: dict[str, Any]):
        """Log informational message."""
        self._log_structured("INFO", event, data)

    def log_warning(self, event: str, data: dict[str, Any]):
        """Log warning message."""
        self._log_structured("WARNING", event, data)

    def log_error(
        self, event: str, data: dict[str, Any], error: Optional[Exception] = None
    ):
        """Log error message."""
        self._log_structured("ERROR", event, data, error)

    def log_critical(
        self, event: str, data: dict[str, Any], error: Optional[Exception] = None
    ):
        """Log critical error message."""
        self._log_structured("CRITICAL", event, data, error)

    # Specialized logging methods for correlation processing
    def log_api_request(
        self,
        endpoint: str,
        parameters: dict[str, Any],
        request_id: Optional[str] = None,
    ):
        """Log API request start."""
        self.log_info(
            "api_request_start",
            {
                "endpoint": endpoint,
                "parameters": parameters,
                "request_id": request_id,
                "correlation_start": True,
            },
        )

    def log_api_response(
        self,
        endpoint: str,
        status_code: int,
        response_data: dict[str, Any],
        duration_ms: float,
        request_id: Optional[str] = None,
    ):
        """Log API response."""
        self.log_info(
            "api_response",
            {
                "endpoint": endpoint,
                "status_code": status_code,
                "response_size": len(str(response_data)),
                "duration_ms": duration_ms,
                "request_id": request_id,
                "success": status_code < 400,
            },
        )

    def log_processing_start(self, process_name: str, context: dict[str, Any]):
        """Log processing start with context."""
        self.processing_timers[process_name] = time.time()
        self.log_info(
            "processing_start",
            {
                "process": process_name,
                "context": context,
                "start_time": self.processing_timers[process_name],
            },
        )

    def log_processing_complete(self, process_name: str, results: dict[str, Any]):
        """Log processing completion with results."""
        start_time = self.processing_timers.get(process_name)
        duration = time.time() - start_time if start_time else None

        self.log_info(
            "processing_complete",
            {
                "process": process_name,
                "results": results,
                "duration_seconds": duration,
                "success": True,
            },
        )

        if process_name in self.processing_timers:
            del self.processing_timers[process_name]

    def log_processing_error(
        self, process_name: str, error: Exception, context: dict[str, Any]
    ):
        """Log processing error with full context."""
        start_time = self.processing_timers.get(process_name)
        duration = time.time() - start_time if start_time else None

        self.log_error(
            "processing_error",
            {
                "process": process_name,
                "context": context,
                "duration_seconds": duration,
                "success": False,
            },
            error,
        )

        if process_name in self.processing_timers:
            del self.processing_timers[process_name]

    def log_data_transformation(
        self,
        operation: str,
        input_data: Any,
        output_data: Any,
        metadata: Optional[dict[str, Any]] = None,
    ):
        """Log data transformation with before/after states."""
        self.log_debug(
            "data_transformation",
            {
                "operation": operation,
                "input_type": type(input_data).__name__,
                "input_size": len(str(input_data)) if input_data else 0,
                "output_type": type(output_data).__name__,
                "output_size": len(str(output_data)) if output_data else 0,
                "metadata": metadata or {},
            },
        )

    def log_document_analysis(
        self,
        document_id: str,
        repository: str,
        analysis_type: str,
        rich_data_available: bool,
        analysis_results: dict[str, Any],
    ):
        """Log document analysis results."""
        self.log_info(
            "document_analysis",
            {
                "document_id": document_id,
                "repository": repository,
                "analysis_type": analysis_type,
                "rich_data_available": rich_data_available,
                "results": analysis_results,
            },
        )

    def log_correlation_generation(
        self,
        source_doc: str,
        target_doc: str,
        correlation_type: str,
        strength: float,
        factors: list[str],
    ):
        """Log correlation generation details."""
        self.log_info(
            "correlation_generation",
            {
                "source_document": source_doc,
                "target_document": target_doc,
                "correlation_type": correlation_type,
                "strength": strength,
                "factors": factors,
                "correlation_created": True,
            },
        )

    def log_rich_intelligence_usage(
        self,
        document_id: str,
        technologies: list[str],
        architecture_patterns: list[str],
        usage_successful: bool,
    ):
        """Log rich intelligence data usage."""
        self.log_info(
            "rich_intelligence_usage",
            {
                "document_id": document_id,
                "technologies_count": len(technologies),
                "technologies": technologies[:5],  # Limit for readability
                "architecture_patterns_count": len(architecture_patterns),
                "architecture_patterns": architecture_patterns[:5],
                "usage_successful": usage_successful,
                "data_source": "rich_intelligence",
            },
        )

    def log_fallback_to_basic_analysis(
        self, document_id: str, reason: str, context: dict[str, Any]
    ):
        """Log fallback to basic analysis."""
        self.log_warning(
            "fallback_to_basic_analysis",
            {
                "document_id": document_id,
                "fallback_reason": reason,
                "context": context,
                "analysis_degraded": True,
            },
        )

    def log_batch_processing_status(
        self,
        batch_id: str,
        total_documents: int,
        processed: int,
        failed: int,
        remaining: int,
    ):
        """Log batch processing status."""
        self.log_info(
            "batch_processing_status",
            {
                "batch_id": batch_id,
                "total_documents": total_documents,
                "processed": processed,
                "failed": failed,
                "remaining": remaining,
                "completion_percentage": (
                    (processed + failed) / total_documents * 100
                    if total_documents > 0
                    else 0
                ),
            },
        )

    def log_database_operation(
        self,
        operation: str,
        table: str,
        document_id: str,
        success: bool,
        affected_rows: Optional[int] = None,
    ):
        """Log database operations."""
        self.log_info(
            "database_operation",
            {
                "operation": operation,
                "table": table,
                "document_id": document_id,
                "success": success,
                "affected_rows": affected_rows,
            },
        )

    def log_performance_metrics(
        self,
        operation: str,
        duration_seconds: float,
        memory_usage_mb: Optional[float] = None,
        additional_metrics: Optional[dict[str, Any]] = None,
    ):
        """Log performance metrics."""
        self.log_info(
            "performance_metrics",
            {
                "operation": operation,
                "duration_seconds": duration_seconds,
                "memory_usage_mb": memory_usage_mb,
                "additional_metrics": additional_metrics or {},
            },
        )


def correlation_logging(component_name: str):
    """
    Decorator for automatic correlation logging.

    Args:
        component_name: Name of the component

    Usage:
        @correlation_logging("correlation_processor")
        def process_correlations(doc_id):
            # Function automatically gets correlation context
            pass
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = CorrelationLogger(component_name)
            correlation_id = logger.generate_correlation_id()

            with logger.correlation_context(correlation_id):
                logger.log_processing_start(
                    func.__name__,
                    {
                        "function": f"{func.__module__}.{func.__name__}",
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys()),
                    },
                )

                try:
                    result = func(*args, **kwargs)
                    logger.log_processing_complete(
                        func.__name__,
                        {
                            "result_type": type(result).__name__,
                            "result_size": len(str(result)) if result else 0,
                        },
                    )
                    return result
                except Exception as e:
                    logger.log_processing_error(
                        func.__name__,
                        e,
                        {
                            "function": f"{func.__module__}.{func.__name__}",
                            "args_count": len(args),
                            "kwargs_keys": list(kwargs.keys()),
                        },
                    )
                    raise

        return wrapper

    return decorator


# Global logger instances for commonly used components
api_logger = CorrelationLogger("intelligence_api")
generator_logger = CorrelationLogger("correlation_generator")
processor_logger = CorrelationLogger("enhanced_correlation_processor")
integration_logger = CorrelationLogger("intelligence_correlation_integration")


def get_correlation_logger(component_name: str) -> CorrelationLogger:
    """
    Get or create a correlation logger for a component.

    Args:
        component_name: Name of the component

    Returns:
        CorrelationLogger instance
    """
    return CorrelationLogger(component_name)
