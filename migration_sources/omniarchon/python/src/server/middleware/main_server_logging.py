"""
Enhanced Logging for Main Archon Server

Comprehensive logging enhancement for the main FastAPI server including
startup sequence monitoring, health check logging, service dependency tracking,
and performance monitoring.
"""

import time
from datetime import UTC, datetime
from typing import Any, Optional

# Import existing logging infrastructure
from server.config.logfire_config import (
    get_logger,
    is_logfire_enabled,
    safe_logfire_error,
    safe_logfire_info,
    safe_logfire_warning,
)
from server.utils.correlation_logging import CorrelationLogger


class MainServerLogger:
    """
    Enhanced logger for main Archon server operations.

    Provides comprehensive logging for startup sequences, health checks,
    service dependencies, and performance monitoring.
    """

    def __init__(self):
        self.component_name = "archon_main_server"
        self.logger = get_logger("server.main")
        self.correlation_logger = CorrelationLogger(self.component_name)
        self.startup_metrics = {}
        self.startup_start_time = None

    def log_startup_phase(
        self,
        phase: str,
        status: str,
        details: Optional[dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
    ):
        """Log server startup phase with detailed metrics."""
        log_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "component": self.component_name,
            "event_type": "startup_phase",
            "startup_phase": phase,
            "status": status,
            "details": details or {},
            "duration_ms": duration_ms,
        }

        # Choose appropriate emoji and log level
        status_emoji = {
            "start": "🚀",
            "progress": "⚙️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
        }.get(status, "ℹ️")

        message = f"{status_emoji} Server Startup | phase={phase} | status={status}"
        if duration_ms:
            message += f" | duration={duration_ms:.2f}ms"

        # Log with appropriate level
        if status == "error":
            self.logger.error(message)
            if is_logfire_enabled():
                safe_logfire_error(f"Startup phase failed: {phase}", **log_data)
        elif status == "warning":
            self.logger.warning(message)
            if is_logfire_enabled():
                safe_logfire_warning(f"Startup phase warning: {phase}", **log_data)
        else:
            self.logger.info(message)
            if is_logfire_enabled():
                safe_logfire_info(f"Startup phase: {phase}", **log_data)

        # Store metrics for overall startup summary
        if phase not in self.startup_metrics:
            self.startup_metrics[phase] = {}
        self.startup_metrics[phase][status] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "duration_ms": duration_ms,
            "details": details,
        }

    def log_startup_sequence_start(self):
        """Log the start of the server startup sequence."""
        self.startup_start_time = time.time()
        self.startup_metrics = {}

        self.log_startup_phase(
            "initialization",
            "start",
            {
                "server_type": "archon_main_server",
                "startup_timestamp": datetime.now(UTC).isoformat(),
            },
        )

    def log_startup_sequence_complete(self, success: bool = True):
        """Log completion of startup sequence with summary metrics."""
        if self.startup_start_time:
            total_startup_time = (time.time() - self.startup_start_time) * 1000
        else:
            total_startup_time = 0

        summary = {
            "total_startup_time_ms": total_startup_time,
            "total_phases": len(self.startup_metrics),
            "successful_phases": len(
                [p for p in self.startup_metrics.values() if "success" in p]
            ),
            "failed_phases": len(
                [p for p in self.startup_metrics.values() if "error" in p]
            ),
            "warning_phases": len(
                [p for p in self.startup_metrics.values() if "warning" in p]
            ),
            "startup_summary": self.startup_metrics,
        }

        if success:
            self.log_startup_phase(
                "initialization", "success", summary, total_startup_time
            )
        else:
            self.log_startup_phase(
                "initialization", "error", summary, total_startup_time
            )

        # Log performance metrics
        self.correlation_logger.log_performance_metrics(
            operation="server_startup",
            duration_seconds=total_startup_time / 1000,
            additional_metrics=summary,
        )

    def log_configuration_validation(self, config_status: dict[str, Any]):
        """Log configuration validation results."""
        log_data = {
            "event_type": "configuration_validation",
            "config_valid": config_status.get("valid", False),
            "config_details": config_status,
        }

        if config_status.get("valid", False):
            self.logger.info(
                f"✅ Configuration Validation | valid=true | database_type={config_status.get('database_type', 'unknown')}"
            )
            if is_logfire_enabled():
                safe_logfire_info("Configuration validation passed", **log_data)
        else:
            error_details = config_status.get("error", "Unknown validation error")
            self.logger.error(
                f"❌ Configuration Validation | valid=false | error={error_details}"
            )
            if is_logfire_enabled():
                safe_logfire_error("Configuration validation failed", **log_data)

    def log_service_initialization(
        self,
        service_name: str,
        status: str,
        duration_ms: Optional[float] = None,
        error: Optional[Exception] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        """Log service initialization results."""
        log_data = {
            "event_type": "service_initialization",
            "service_name": service_name,
            "status": status,
            "duration_ms": duration_ms,
            "details": details or {},
        }

        status_emoji = {"success": "✅", "warning": "⚠️", "error": "❌"}.get(status, "ℹ️")
        message = (
            f"{status_emoji} Service Init | service={service_name} | status={status}"
        )
        if duration_ms:
            message += f" | duration={duration_ms:.2f}ms"

        if status == "error" and error:
            message += f" | error={error!s}"
            log_data["error"] = {"type": type(error).__name__, "message": str(error)}
            self.logger.error(message)
            if is_logfire_enabled():
                safe_logfire_error(
                    f"Service initialization failed: {service_name}", **log_data
                )
        elif status == "warning":
            self.logger.warning(message)
            if is_logfire_enabled():
                safe_logfire_warning(
                    f"Service initialization warning: {service_name}", **log_data
                )
        else:
            self.logger.info(message)
            if is_logfire_enabled():
                safe_logfire_info(f"Service initialized: {service_name}", **log_data)

    def log_health_check_result(
        self,
        endpoint: str,
        status_code: int,
        response_time_ms: float,
        success: bool,
        response_data: Optional[dict[str, Any]] = None,
    ):
        """Log health check results for monitoring."""
        log_data = {
            "event_type": "health_check_result",
            "endpoint": endpoint,
            "status_code": status_code,
            "response_time_ms": response_time_ms,
            "success": success,
            "response_data": response_data or {},
        }

        status_emoji = "✅" if success else "❌"
        self.logger.info(
            f"{status_emoji} Health Check | endpoint={endpoint} | status={status_code} | duration={response_time_ms:.2f}ms | success={success}"
        )

        if is_logfire_enabled():
            if success:
                safe_logfire_info(f"Health check passed: {endpoint}", **log_data)
            else:
                safe_logfire_warning(f"Health check failed: {endpoint}", **log_data)

        # Use correlation logger for consistent health tracking
        self.correlation_logger.log_api_response(
            endpoint=endpoint,
            status_code=status_code,
            response_data=response_data or {},
            duration_ms=response_time_ms,
            request_id=f"health_check_{int(time.time())}",
        )

    def log_service_dependency_check(
        self,
        service_name: str,
        available: bool,
        response_time_ms: Optional[float] = None,
        error: Optional[str] = None,
    ):
        """Log service dependency availability checks."""
        log_data = {
            "event_type": "service_dependency_check",
            "service_name": service_name,
            "available": available,
            "response_time_ms": response_time_ms,
            "error": error,
        }

        status_emoji = "✅" if available else "❌"
        message = f"{status_emoji} Service Dependency | service={service_name} | available={available}"
        if response_time_ms:
            message += f" | response_time={response_time_ms:.2f}ms"
        if error and not available:
            message += f" | error={error}"

        if available:
            self.logger.info(message)
            if is_logfire_enabled():
                safe_logfire_info(
                    f"Service dependency healthy: {service_name}", **log_data
                )
        else:
            self.logger.warning(message)
            if is_logfire_enabled():
                safe_logfire_warning(
                    f"Service dependency unhealthy: {service_name}", **log_data
                )

    def log_middleware_registration(
        self, middleware_name: str, success: bool, error: Optional[Exception] = None
    ):
        """Log middleware registration results."""
        log_data = {
            "event_type": "middleware_registration",
            "middleware_name": middleware_name,
            "success": success,
        }

        if success:
            self.logger.info(f"✅ Middleware Registered | middleware={middleware_name}")
            if is_logfire_enabled():
                safe_logfire_info(
                    f"Middleware registered: {middleware_name}", **log_data
                )
        else:
            error_msg = str(error) if error else "Unknown error"
            log_data["error"] = error_msg
            self.logger.error(
                f"❌ Middleware Registration Failed | middleware={middleware_name} | error={error_msg}"
            )
            if is_logfire_enabled():
                safe_logfire_error(
                    f"Middleware registration failed: {middleware_name}", **log_data
                )

    def log_route_registration(self, router_name: str, route_count: int):
        """Log API route registration."""
        log_data = {
            "event_type": "route_registration",
            "router_name": router_name,
            "route_count": route_count,
        }

        self.logger.info(
            f"🛣️ Routes Registered | router={router_name} | routes={route_count}"
        )
        if is_logfire_enabled():
            safe_logfire_info(f"Routes registered: {router_name}", **log_data)

    def log_shutdown_phase(
        self,
        phase: str,
        status: str,
        duration_ms: Optional[float] = None,
        error: Optional[Exception] = None,
    ):
        """Log server shutdown phases."""
        log_data = {
            "event_type": "shutdown_phase",
            "shutdown_phase": phase,
            "status": status,
            "duration_ms": duration_ms,
        }

        status_emoji = {"success": "✅", "warning": "⚠️", "error": "❌"}.get(status, "ℹ️")
        message = f"{status_emoji} Server Shutdown | phase={phase} | status={status}"
        if duration_ms:
            message += f" | duration={duration_ms:.2f}ms"

        if status == "error" and error:
            message += f" | error={error!s}"
            log_data["error"] = str(error)
            self.logger.error(message)
            if is_logfire_enabled():
                safe_logfire_error(f"Shutdown phase failed: {phase}", **log_data)
        elif status == "warning":
            self.logger.warning(message)
            if is_logfire_enabled():
                safe_logfire_warning(f"Shutdown phase warning: {phase}", **log_data)
        else:
            self.logger.info(message)
            if is_logfire_enabled():
                safe_logfire_info(f"Shutdown phase: {phase}", **log_data)

    def log_performance_metrics(self, operation: str, metrics: dict[str, Any]):
        """Log performance metrics for server operations."""
        log_data = {
            "event_type": "server_performance_metrics",
            "operation": operation,
            "metrics": metrics,
        }

        self.logger.info(f"📊 Performance Metrics | operation={operation}")
        if is_logfire_enabled():
            safe_logfire_info(f"Performance metrics: {operation}", **log_data)

        # Use correlation logger for consistent performance tracking
        self.correlation_logger.log_performance_metrics(
            operation=operation,
            duration_seconds=metrics.get("duration_seconds", 0),
            memory_usage_mb=metrics.get("memory_usage_mb"),
            additional_metrics=metrics,
        )


# Global logger instance
main_server_logger = MainServerLogger()


def log_timed_operation(operation_name: str, service_name: Optional[str] = None):
    """
    Decorator for timing and logging server operations.

    Usage:
        @log_timed_operation("credential_initialization", "credentials")
        async def initialize_credentials():
            # Implementation
            pass
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                # Execute the operation
                result = await func(*args, **kwargs)

                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000

                # Log success
                if service_name:
                    main_server_logger.log_service_initialization(
                        service_name, "success", duration_ms
                    )
                else:
                    main_server_logger.log_startup_phase(
                        operation_name, "success", duration_ms=duration_ms
                    )

                return result

            except Exception as e:
                # Calculate duration for error case
                duration_ms = (time.time() - start_time) * 1000

                # Log error
                if service_name:
                    main_server_logger.log_service_initialization(
                        service_name, "error", duration_ms, e
                    )
                else:
                    main_server_logger.log_startup_phase(
                        operation_name, "error", duration_ms=duration_ms
                    )

                raise

        return wrapper

    return decorator


# Export key components
__all__ = ["MainServerLogger", "main_server_logger", "log_timed_operation"]
