"""
FastAPI Backend for Archon Knowledge Engine

This is the main entry point for the Archon backend API.
It uses a modular approach with separate API modules for different functionality.

Modules:
- settings_api: Settings and credentials management
- knowledge_api: Knowledge base, crawling, and RAG operations
- projects_api: Project and task management with streaming
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from server.api_routes.agent_chat_api import router as agent_chat_router
from server.api_routes.bug_report_api import router as bug_report_router
from server.api_routes.correlation_api import router as correlation_router
from server.api_routes.coverage_api import router as coverage_router
from server.api_routes.intelligence_api import router as intelligence_router
from server.api_routes.internal_api import router as internal_router
from server.api_routes.knowledge_api import router as knowledge_router

# REMOVED: MCP API router - MCP support has been removed
# from server.api_routes.mcp_api import router as mcp_router
from server.api_routes.monitoring_api import router as monitoring_router
from server.api_routes.projects_api import router as projects_router

# Import modular API routers
from server.api_routes.settings_api import router as settings_router
from server.api_routes.tests_api import router as tests_router
from server.api_routes.vector_health_api import router as vector_health_router

# Import Logfire configuration
from server.config.logfire_config import api_logger, setup_logfire

# Import enhanced server logging
from server.middleware.main_server_logging import main_server_logger

# Import production monitoring middleware
from server.middleware.metrics_middleware import PrometheusMetricsMiddleware

# Import service authentication middleware
from server.middleware.service_auth_middleware import ServiceAuthMiddleware
from server.services.background_task_manager import cleanup_task_manager
from server.services.container_health_monitor import (
    start_health_monitoring,
    stop_health_monitoring,
)
from server.services.crawler_manager import cleanup_crawler, initialize_crawler

# Import utilities and core classes
from server.services.credential_service import initialize_credentials

# Import lifecycle event publishing
# NOTE: ONEX EFFECT node integration commented out until dependencies are available in container
# from omnibase_core.core.onex_container import ONEXContainer
# from omninode_bridge.services.kafka_client import KafkaClient
# from .nodes.node_archon_lifecycle_effect import (
#     NodeArchonLifecycleEffect,
#     ModelLifecycleEventInput,
#     EnumLifecycleEventType,
# )
from server.services.lifecycle_events import get_lifecycle_publisher
from server.services.vector_collection_health_monitor import (
    start_vector_monitoring,
    stop_vector_monitoring,
)

# Import Socket.IO integration
from server.socketio_app import create_socketio_app

# Import custom JSON encoder
from server.utils.json_encoder import CustomJSONEncoder, safe_json_response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Socket.IO handlers are registered via socketio_app


# Import Kafka consumer EFFECT node
# from .services.kafka_consumer_service import get_kafka_consumer_service
# TODO: Re-enable once omnibase_core circular import is resolved


# Import missing dependencies that the modular APIs need
try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig
except ImportError:
    # These are optional dependencies for full functionality
    AsyncWebCrawler = None
    BrowserConfig = None

# Logger will be initialized after credentials are loaded
logger = logging.getLogger(__name__)

# Set up logging configuration to reduce noise

# Override uvicorn's access log format to be less verbose
uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.setLevel(
    logging.WARNING
)  # Only log warnings and errors, not every request

# CrawlingContext has been replaced by CrawlerManager in services/crawler_manager.py

# Global flag to track if initialization is complete
_initialization_complete = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown tasks."""
    global _initialization_complete
    _initialization_complete = False

    # Startup - Initialize comprehensive logging
    main_server_logger.log_startup_sequence_start()
    logger.info("🚀 Starting Archon backend...")

    try:
        # Validate configuration FIRST - check for anon vs service key
        # DEGRADED MODE: Config validation is optional (Supabase deprecated)
        main_server_logger.log_startup_phase("config_validation", "progress")
        try:
            from .config.config import get_config

            get_config()  # This will raise ConfigurationError if anon key detected
            main_server_logger.log_configuration_validation(
                {"valid": True, "database_type": "supabase"}
            )
            main_server_logger.log_startup_phase("config_validation", "success")
        except Exception as e:
            main_server_logger.log_startup_phase(
                "config_validation", "warning", details={"error": str(e)}
            )
            logger.warning(
                f"⚠️  Configuration validation skipped (Supabase deprecated): {e!s}"
            )
            logger.warning(
                "Server will use environment variables for configuration. "
                "Supabase database is optional."
            )

        # Initialize credentials from database FIRST - foundation for everything else
        # DEGRADED MODE: Credential service is optional (Supabase deprecated)
        main_server_logger.log_startup_phase("credentials", "progress")
        try:
            await initialize_credentials()
            main_server_logger.log_startup_phase("credentials", "success")
            logger.info("✅ Credentials initialized from database")
        except Exception as e:
            main_server_logger.log_startup_phase("credentials", "warning", error=e)
            logger.warning(
                f"⚠️  Credential service unavailable (continuing in degraded mode): {e!s}"
            )
            logger.warning(
                "Server will start without credential database. "
                "Use environment variables for configuration."
            )

        # Now that credentials are loaded, we can properly initialize logging
        # This must happen AFTER credentials so LOGFIRE_ENABLED is set from database
        main_server_logger.log_startup_phase("logfire_setup", "progress")
        setup_logfire(service_name="archon-backend")
        main_server_logger.log_startup_phase("logfire_setup", "success")

        # Now we can safely use the logger
        logger.info("✅ Credentials initialized")
        api_logger.info("🔥 Logfire initialized for backend")

        # Initialize lifecycle event publisher
        try:
            main_server_logger.log_startup_phase("lifecycle_events", "progress")
            lifecycle_publisher = get_lifecycle_publisher()
            await lifecycle_publisher.initialize()
            app.state.lifecycle_publisher = lifecycle_publisher
            main_server_logger.log_service_initialization("lifecycle_events", "success")
            main_server_logger.log_startup_phase("lifecycle_events", "success")
            api_logger.info("✅ Lifecycle event publisher initialized")
        except Exception as e:
            main_server_logger.log_service_initialization(
                "lifecycle_events", "warning", error=e
            )
            main_server_logger.log_startup_phase("lifecycle_events", "warning", error=e)
            api_logger.warning(
                f"Lifecycle event publisher initialization failed (continuing without): {e!s}"
            )
            # Store None to indicate publisher unavailable
            app.state.lifecycle_publisher = None

        # Initialize Consul service discovery
        try:
            main_server_logger.log_startup_phase("consul_service", "progress")
            from .services.consul_service import get_consul_service

            consul_service = get_consul_service()
            app.state.consul_service = consul_service

            # Register archon-server with Consul
            if consul_service.enabled:
                server_port = int(os.getenv("ARCHON_SERVER_PORT", "8181"))
                consul_service.register_service(
                    service_id="archon-server",
                    service_name="archon-server",
                    port=server_port,
                    address="localhost",
                    tags=["archon", "api", "server"],
                    meta={
                        "version": "1.0.0",
                        "capabilities": "mcp,knowledge,projects,intelligence",
                    },
                    health_check_url=f"http://localhost:{server_port}/health",
                    health_check_interval="10s",
                    health_check_timeout="5s",
                )

                # Register other Archon services
                intelligence_port = int(os.getenv("INTELLIGENCE_SERVICE_PORT", "8053"))
                consul_service.register_service(
                    service_id="archon-intelligence",
                    service_name="archon-intelligence",
                    port=intelligence_port,
                    address="localhost",
                    tags=["archon", "intelligence", "backend"],
                    meta={
                        "version": "1.0.0",
                        "capabilities": "quality,performance,freshness,pattern-learning",
                    },
                    health_check_url=f"http://localhost:{intelligence_port}/health",
                )

                bridge_port = int(os.getenv("BRIDGE_SERVICE_PORT", "8054"))
                consul_service.register_service(
                    service_id="archon-bridge",
                    service_name="archon-bridge",
                    port=bridge_port,
                    address="localhost",
                    tags=["archon", "bridge", "backend"],
                    meta={
                        "version": "1.0.0",
                        "capabilities": "event-translation,metadata-stamping",
                    },
                    health_check_url=f"http://localhost:{bridge_port}/health",
                )

                search_port = int(os.getenv("SEARCH_SERVICE_PORT", "8055"))
                consul_service.register_service(
                    service_id="archon-search",
                    service_name="archon-search",
                    port=search_port,
                    address="localhost",
                    tags=["archon", "search", "backend"],
                    meta={
                        "version": "1.0.0",
                        "capabilities": "rag,vector-search,code-examples",
                    },
                    health_check_url=f"http://localhost:{search_port}/health",
                )

            main_server_logger.log_service_initialization("consul_service", "success")
            main_server_logger.log_startup_phase("consul_service", "success")
            api_logger.info("✅ Consul service discovery initialized")
        except Exception as e:
            main_server_logger.log_service_initialization(
                "consul_service", "warning", error=e
            )
            main_server_logger.log_startup_phase("consul_service", "warning", error=e)
            api_logger.warning(
                f"Consul service discovery initialization failed (continuing without): {e!s}"
            )
            # Store None to indicate Consul unavailable
            app.state.consul_service = None

        # Initialize crawling context
        try:
            main_server_logger.log_startup_phase("crawler_initialization", "progress")
            await initialize_crawler()
            main_server_logger.log_service_initialization("crawler_manager", "success")
            main_server_logger.log_startup_phase("crawler_initialization", "success")
        except Exception as e:
            main_server_logger.log_service_initialization(
                "crawler_manager", "warning", error=e
            )
            main_server_logger.log_startup_phase("crawler_initialization", "warning")
            api_logger.warning(f"Could not fully initialize crawling context: {e!s}")

        # Make crawling context available to modules
        # Crawler is now managed by CrawlerManager

        # Initialize Socket.IO services
        try:
            main_server_logger.log_startup_phase("socketio_services", "progress")
            # Import API modules to register their Socket.IO handlers
            main_server_logger.log_service_initialization(
                "socketio_handlers", "success"
            )
            main_server_logger.log_startup_phase("socketio_services", "success")
            api_logger.info("✅ Socket.IO handlers imported from API modules")
        except Exception as e:
            main_server_logger.log_service_initialization(
                "socketio_handlers", "warning", error=e
            )
            main_server_logger.log_startup_phase("socketio_services", "warning")
            api_logger.warning(f"Could not initialize Socket.IO services: {e}")

        # Initialize prompt service
        try:
            main_server_logger.log_startup_phase("prompt_service", "progress")
            from .services.prompt_service import prompt_service

            await prompt_service.load_prompts()
            main_server_logger.log_service_initialization("prompt_service", "success")
            main_server_logger.log_startup_phase("prompt_service", "success")
            api_logger.info("✅ Prompt service initialized")
        except Exception as e:
            main_server_logger.log_service_initialization(
                "prompt_service", "warning", error=e
            )
            main_server_logger.log_startup_phase("prompt_service", "warning")
            api_logger.warning(f"Could not initialize prompt service: {e}")

        # Set the main event loop for background tasks
        try:
            main_server_logger.log_startup_phase("background_tasks", "progress")
            from .services.background_task_manager import get_task_manager

            task_manager = get_task_manager()
            current_loop = asyncio.get_running_loop()
            task_manager.set_main_loop(current_loop)
            main_server_logger.log_service_initialization(
                "background_task_manager", "success"
            )
            main_server_logger.log_startup_phase("background_tasks", "success")
            api_logger.info("✅ Main event loop set for background tasks")
        except Exception as e:
            main_server_logger.log_service_initialization(
                "background_task_manager", "warning", error=e
            )
            main_server_logger.log_startup_phase("background_tasks", "warning")
            api_logger.warning(f"Could not set main event loop: {e}")

        # MCP Client functionality removed from architecture
        # Agents now use MCP tools directly

        # Initialize resilient indexing service for document processing
        try:
            main_server_logger.log_startup_phase("indexing_service", "progress")
            from .services.indexing.resilient_indexing_service import (
                get_indexing_service,
            )

            indexing_service = get_indexing_service()
            # Start background processing in a separate task
            asyncio.create_task(indexing_service.start_processing())

            main_server_logger.log_service_initialization(
                "resilient_indexing_service", "success"
            )
            main_server_logger.log_startup_phase("indexing_service", "success")
            api_logger.info("✅ Resilient indexing service started")
        except Exception as e:
            main_server_logger.log_service_initialization(
                "resilient_indexing_service", "warning", error=e
            )
            main_server_logger.log_startup_phase("indexing_service", "warning")
            api_logger.warning(f"Could not start indexing service: {e}")

        # Initialize vector collection health monitoring
        try:
            main_server_logger.log_startup_phase("vector_monitoring", "progress")
            await start_vector_monitoring()
            main_server_logger.log_service_initialization(
                "vector_health_monitor", "success"
            )
            main_server_logger.log_startup_phase("vector_monitoring", "success")
            api_logger.info("✅ Vector collection health monitoring started")
        except Exception as e:
            # Log the error but don't fail startup - vector monitoring is optional
            main_server_logger.log_service_initialization(
                "vector_health_monitor", "warning", error=e
            )
            main_server_logger.log_startup_phase("vector_monitoring", "warning")
            api_logger.warning(
                f"Could not start vector collection health monitoring "
                f"(continuing without): {e}"
            )

        # Start container health monitoring with Slack alerts
        try:
            main_server_logger.log_startup_phase(
                "container_health_monitoring", "progress"
            )
            # Start monitoring in background task
            asyncio.create_task(start_health_monitoring())
            main_server_logger.log_service_initialization(
                "container_health_monitor", "success"
            )
            main_server_logger.log_startup_phase(
                "container_health_monitoring", "success"
            )
            api_logger.info("🏥 Container health monitoring started")
        except Exception as e:
            main_server_logger.log_service_initialization(
                "container_health_monitor", "warning", error=e
            )
            main_server_logger.log_startup_phase(
                "container_health_monitoring", "warning", error=e
            )
            api_logger.warning(
                f"Could not start container health monitoring "
                f"(continuing without): {e}"
            )

        # Initialize Kafka consumer for bidirectional OmniNode integration
        # TODO: Re-enable Kafka consumer once omnibase_core circular import is resolved
        main_server_logger.log_startup_phase(
            "kafka_consumer",
            "skipped",
            {"reason": "omnibase_core circular import issue"},
        )
        app.state.kafka_consumer_service = None
        api_logger.info(
            "⚠️  Kafka consumer skipped - omnibase_core circular import issue"
        )

        # Mark initialization as complete
        _initialization_complete = True

        # Publish service lifecycle started event
        if (
            hasattr(app.state, "lifecycle_publisher")
            and app.state.lifecycle_publisher is not None
        ):
            try:
                await app.state.lifecycle_publisher.publish(
                    event_type="service_lifecycle_started",
                    payload={
                        "service_id": "archon-backend",
                        "node_type": "fastapi_server",
                        "domain": "archon",
                        "capabilities": [
                            "mcp",
                            "knowledge",
                            "projects",
                            "intelligence",
                            "crawler",
                            "indexing",
                            "vector_monitoring",
                        ],
                    },
                )
                api_logger.info("📡 Service lifecycle started event published")
            except Exception as e:
                api_logger.warning(f"Failed to publish startup event: {e!s}")

        main_server_logger.log_startup_sequence_complete(success=True)
        api_logger.info("🎉 Archon backend started successfully!")

    except Exception as e:
        main_server_logger.log_startup_sequence_complete(success=False)
        api_logger.error(f"❌ Failed to start backend: {e!s}")
        raise

    yield

    # Shutdown
    _initialization_complete = False
    main_server_logger.log_shutdown_phase("initialization", "start")
    api_logger.info("🛑 Shutting down Archon backend...")

    try:
        # MCP Client cleanup not needed

        # Cleanup crawling context
        try:
            main_server_logger.log_shutdown_phase("crawler_cleanup", "progress")
            await cleanup_crawler()
            main_server_logger.log_shutdown_phase("crawler_cleanup", "success")
        except Exception as e:
            main_server_logger.log_shutdown_phase("crawler_cleanup", "warning", error=e)
            api_logger.warning("Could not cleanup crawling context", error=str(e))

        # Cleanup background task manager
        try:
            main_server_logger.log_shutdown_phase("task_manager_cleanup", "progress")
            await cleanup_task_manager()
            main_server_logger.log_shutdown_phase("task_manager_cleanup", "success")
            api_logger.info("Background task manager cleaned up")
        except Exception as e:
            main_server_logger.log_shutdown_phase(
                "task_manager_cleanup", "warning", error=e
            )
            api_logger.warning(
                "Could not cleanup background task manager", error=str(e)
            )

        # Cleanup vector collection health monitoring
        try:
            main_server_logger.log_shutdown_phase(
                "vector_monitoring_cleanup", "progress"
            )
            await stop_vector_monitoring()
            main_server_logger.log_shutdown_phase(
                "vector_monitoring_cleanup", "success"
            )
            api_logger.info("Vector collection health monitoring stopped")
        except Exception as e:
            # Log cleanup failure but don't fail shutdown
            main_server_logger.log_shutdown_phase(
                "vector_monitoring_cleanup", "warning", error=e
            )
            api_logger.warning(
                f"Could not cleanup vector collection health monitoring: {e}"
            )

        # Cleanup container health monitoring
        try:
            main_server_logger.log_shutdown_phase(
                "container_health_monitoring_cleanup", "progress"
            )
            await stop_health_monitoring()
            main_server_logger.log_shutdown_phase(
                "container_health_monitoring_cleanup", "success"
            )
            api_logger.info("Container health monitoring stopped")
        except Exception as e:
            # Log cleanup failure but don't fail shutdown
            main_server_logger.log_shutdown_phase(
                "container_health_monitoring_cleanup", "warning", error=e
            )
            api_logger.warning(f"Could not cleanup container health monitoring: {e}")

        # Cleanup indexing service
        try:
            main_server_logger.log_shutdown_phase(
                "indexing_service_cleanup", "progress"
            )
            from .services.indexing.resilient_indexing_service import (
                get_indexing_service,
            )

            indexing_service = get_indexing_service()
            await indexing_service.stop_processing()
            main_server_logger.log_shutdown_phase("indexing_service_cleanup", "success")
            api_logger.info("Indexing service stopped")
        except Exception as e:
            main_server_logger.log_shutdown_phase(
                "indexing_service_cleanup", "warning", error=e
            )
            api_logger.warning(f"Could not stop indexing service: {e}")

        # Shutdown Kafka consumer service
        if (
            hasattr(app.state, "kafka_consumer_service")
            and app.state.kafka_consumer_service is not None
        ):
            try:
                main_server_logger.log_shutdown_phase(
                    "kafka_consumer_cleanup", "progress"
                )
                await app.state.kafka_consumer_service.stop()
                main_server_logger.log_shutdown_phase(
                    "kafka_consumer_cleanup", "success"
                )
                api_logger.info(
                    "Kafka consumer service stopped - bidirectional integration shutdown complete"
                )
            except Exception as e:
                main_server_logger.log_shutdown_phase(
                    "kafka_consumer_cleanup", "warning", error=e
                )
                api_logger.warning(f"Kafka consumer service shutdown failed: {e!s}")

        # Cleanup Consul service registrations
        if (
            hasattr(app.state, "consul_service")
            and app.state.consul_service is not None
        ):
            try:
                main_server_logger.log_shutdown_phase(
                    "consul_service_cleanup", "progress"
                )
                await app.state.consul_service.cleanup()
                main_server_logger.log_shutdown_phase(
                    "consul_service_cleanup", "success"
                )
                api_logger.info("Consul service discovery cleanup complete")
            except Exception as e:
                main_server_logger.log_shutdown_phase(
                    "consul_service_cleanup", "warning", error=e
                )
                api_logger.warning(f"Consul service discovery cleanup failed: {e!s}")

        # Shutdown lifecycle event publisher
        if (
            hasattr(app.state, "lifecycle_publisher")
            and app.state.lifecycle_publisher is not None
        ):
            try:
                main_server_logger.log_shutdown_phase(
                    "lifecycle_events_cleanup", "progress"
                )

                # Publish shutdown event first
                await app.state.lifecycle_publisher.publish(
                    event_type="service_lifecycle_stopped",
                    payload={
                        "service_id": "archon-backend",
                        "final_status": "clean_shutdown",
                    },
                )
                api_logger.info("📡 Service lifecycle stopped event published")

                # Then shutdown publisher
                await app.state.lifecycle_publisher.shutdown()
                main_server_logger.log_shutdown_phase(
                    "lifecycle_events_cleanup", "success"
                )
                api_logger.info("Lifecycle event publisher shutdown complete")
            except Exception as e:
                main_server_logger.log_shutdown_phase(
                    "lifecycle_events_cleanup", "warning", error=e
                )
                api_logger.warning(f"Lifecycle event publisher shutdown failed: {e!s}")

        main_server_logger.log_shutdown_phase("initialization", "success")
        api_logger.info("✅ Cleanup completed")

    except Exception as e:
        main_server_logger.log_shutdown_phase("initialization", "error", error=e)
        api_logger.error(f"❌ Error during shutdown: {e!s}")


# Custom JSON response middleware to fix datetime serialization
class JSONResponseMiddleware(BaseHTTPMiddleware):
    """Middleware to ensure all JSON responses use custom datetime serialization."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Only process JSON responses
        if (
            hasattr(response, "media_type")
            and response.media_type == "application/json"
            and hasattr(response, "body")
        ):
            try:
                # Get the response body
                body = response.body
                if body:
                    # Parse and re-serialize with custom encoder
                    data = json.loads(body)
                    safe_data = safe_json_response(data)
                    new_body = json.dumps(safe_data, cls=CustomJSONEncoder)

                    # Create new response with fixed body
                    return JSONResponse(
                        content=json.loads(new_body),
                        status_code=response.status_code,
                        headers=dict(response.headers),
                    )
            except Exception:
                # If anything goes wrong, return original response
                pass

        return response


# Create FastAPI application with custom JSON encoder
app = FastAPI(
    title="Archon Knowledge Engine API",
    description=(
        "Backend API for the Archon knowledge management "
        "and project automation platform"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing WebSocket issue
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add JSON response middleware to fix datetime serialization
app.add_middleware(JSONResponseMiddleware)

# Add service authentication middleware for internal MCP tool calls
# IMPORTANT: This must be added BEFORE any session validation middleware
app.add_middleware(ServiceAuthMiddleware)

# Add production monitoring middleware
# This should be added AFTER authentication middleware but BEFORE request processing
app.add_middleware(PrometheusMetricsMiddleware, service_name="archon-server")


# Health check logging middleware (class-based for consistency)
class HealthCheckLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to suppress logging for health check endpoints."""

    async def dispatch(self, request: Request, call_next):
        # Skip logging for health check endpoints
        if request.url.path in ["/health", "/api/health"]:
            # Temporarily suppress the log
            import logging

            logger = logging.getLogger("uvicorn.access")
            old_level = logger.level
            logger.setLevel(logging.ERROR)
            response = await call_next(request)
            logger.setLevel(old_level)
            return response
        return await call_next(request)


# Add health check logging middleware
app.add_middleware(HealthCheckLoggingMiddleware)


# Include API routers
app.include_router(settings_router)
# app.include_router(mcp_router)  # REMOVED: MCP support has been removed
# app.include_router(mcp_client_router)  # Removed - not part of new architecture
app.include_router(knowledge_router)
app.include_router(projects_router)
app.include_router(tests_router)
app.include_router(agent_chat_router)
app.include_router(internal_router)
app.include_router(coverage_router)
app.include_router(bug_report_router)
app.include_router(monitoring_router)
app.include_router(intelligence_router)
app.include_router(correlation_router)
app.include_router(vector_health_router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint returning API information."""
    return {
        "name": "Archon Knowledge Engine API",
        "version": "1.0.0",
        "description": "Backend API for knowledge management and project automation",
        "status": "healthy",
        "modules": ["settings", "mcp", "mcp-clients", "knowledge", "projects"],
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Health check endpoint that indicates true readiness including credential loading.
    """
    from datetime import datetime

    # Check if initialization is complete
    if not _initialization_complete:
        return {
            "status": "initializing",
            "service": "archon-backend",
            "timestamp": datetime.now().isoformat(),
            "message": "Backend is starting up, credentials loading...",
            "ready": False,
        }

    # Check for required database schema
    schema_status = await _check_database_schema()
    if not schema_status["valid"]:
        return {
            "status": "migration_required",
            "service": "archon-backend",
            "timestamp": datetime.now().isoformat(),
            "ready": False,
            "migration_required": True,
            "message": schema_status["message"],
            "migration_instructions": (
                "Open Supabase Dashboard → SQL Editor → "
                "Run: migration/add_source_url_display_name.sql"
            ),
            "schema_valid": False,
        }

    return {
        "status": "healthy",
        "service": "archon-backend",
        "timestamp": datetime.now().isoformat(),
        "ready": True,
        "credentials_loaded": True,
        "schema_valid": True,
    }


# API health check endpoint (alias for /health at /api/health)
@app.get("/api/health")
async def api_health_check():
    """API health check endpoint - alias for /health."""
    return await health_check()


# Prometheus metrics endpoint
@app.get("/metrics")
async def metrics_endpoint():
    """
    Prometheus metrics endpoint.

    Exposes all Prometheus metrics including:
    - HTTP request metrics (count, duration, errors)
    - System metrics (CPU, memory, disk)
    - Container health metrics (checks, alerts, status)
    - Application metrics (RAG queries, cache hits, etc.)

    Can be disabled with ENABLE_PROMETHEUS_METRICS=false
    """
    # Check if Prometheus metrics are enabled
    enable_metrics = os.getenv("ENABLE_PROMETHEUS_METRICS", "true").lower() == "true"

    if not enable_metrics:
        return JSONResponse(
            status_code=404,
            content={
                "error": "Metrics endpoint disabled (ENABLE_PROMETHEUS_METRICS=false)"
            },
        )

    # Import here to avoid startup dependency
    from .middleware.metrics_middleware import get_metrics

    return get_metrics()


@app.get("/health/consumer")
async def consumer_health_check():
    """
    Kafka consumer health check endpoint.

    Returns consumer status, metrics, and circuit breaker state.
    """
    from datetime import datetime

    # Check if consumer service is available
    if (
        not hasattr(app.state, "kafka_consumer_service")
        or app.state.kafka_consumer_service is None
    ):
        return {
            "status": "unavailable",
            "service": "kafka-consumer",
            "timestamp": datetime.now().isoformat(),
            "message": "Kafka consumer service not initialized",
            "ready": False,
        }

    # Get consumer status
    status = app.state.kafka_consumer_service.get_status()

    return {
        "status": status.get("status", "unknown"),
        "service": "kafka-consumer",
        "timestamp": datetime.now().isoformat(),
        "ready": status.get("is_running", False),
        "metrics": status.get("metrics", {}),
        "circuit_breaker_state": status.get("circuit_breaker_state", "unknown"),
        "handlers_registered": status.get("handlers_registered", 0),
    }


@app.get("/metrics/consumer")
async def consumer_metrics():
    """
    Kafka consumer metrics endpoint.

    Returns detailed consumer metrics including:
    - Event consumption counters
    - Processing time statistics
    - Circuit breaker metrics
    - Handler-specific metrics
    """
    from datetime import datetime

    # Check if consumer service is available
    if (
        not hasattr(app.state, "kafka_consumer_service")
        or app.state.kafka_consumer_service is None
    ):
        return {
            "error": "Kafka consumer service not initialized",
            "timestamp": datetime.now().isoformat(),
        }

    consumer_service = app.state.kafka_consumer_service

    # Check if consumer is running
    if not consumer_service.consumer or not consumer_service._is_running:
        return {
            "status": "not_running",
            "message": "Consumer is not running",
            "timestamp": datetime.now().isoformat(),
        }

    consumer = consumer_service.consumer

    # Gather comprehensive metrics
    metrics = {
        "timestamp": datetime.now().isoformat(),
        "consumer_state": consumer.consumer_state.value,
        # Event counters
        "events": {
            "consumed_total": consumer.metrics.get("events_consumed", 0),
            "processed_successfully": consumer.metrics.get("events_processed", 0),
            "failed": consumer.metrics.get("events_failed", 0),
            "success_rate": (
                consumer.metrics.get("events_processed", 0)
                / consumer.metrics.get("events_consumed", 1)
                if consumer.metrics.get("events_consumed", 0) > 0
                else 0.0
            ),
        },
        # Processing time
        "processing": {
            "total_time_ms": consumer.metrics.get("total_processing_time_ms", 0.0),
            "average_time_ms": consumer.metrics.get("average_processing_time_ms", 0.0),
        },
        # Circuit breaker
        "circuit_breaker": {
            "state": consumer.circuit_breaker.state.value,
            "failure_count": consumer.circuit_breaker.failure_count,
            "failure_threshold": consumer.circuit_breaker.failure_threshold,
            "trips": consumer.metrics.get("circuit_breaker_trips", 0),
        },
        # Handler metrics
        "handlers": {},
    }

    # Add per-handler metrics
    for handler_name, handler in consumer.registry.handlers.items():
        metrics["handlers"][handler_name] = {
            "events_handled": handler.metrics.get("events_handled", 0),
            "successes": handler.metrics.get("successes", 0),
            "failures": handler.metrics.get("failures", 0),
            "total_time_ms": handler.metrics.get("total_time_ms", 0.0),
            "average_time_ms": handler.metrics.get("average_time_ms", 0.0),
            "success_rate": (
                handler.metrics.get("successes", 0)
                / handler.metrics.get("events_handled", 1)
                if handler.metrics.get("events_handled", 0) > 0
                else 0.0
            ),
        }

    # Registry metrics
    metrics["registry"] = {
        "total_dispatched": consumer.registry.dispatch_metrics.get(
            "total_dispatched", 0
        ),
        "successful_dispatches": consumer.registry.dispatch_metrics.get(
            "successful_dispatches", 0
        ),
        "failed_dispatches": consumer.registry.dispatch_metrics.get(
            "failed_dispatches", 0
        ),
        "unhandled_events": consumer.registry.dispatch_metrics.get(
            "unhandled_events", 0
        ),
    }

    return metrics


# ==============================================================================
# Kafka Event Handler Endpoints
# ==============================================================================
# These endpoints receive events from the Kafka consumer and process them
# according to their event type. They serve as the integration layer between
# the Kafka event stream and the Archon backend services.


@app.post("/api/events/tool-update")
async def handle_tool_update(event: dict[str, Any]):
    """
    Handle tool update events from Kafka consumer.

    Tool update events notify of changes to available tools, tool configurations,
    or tool capabilities in the system.

    TODO: Add business logic for tool update processing:
          - Update tool registry
          - Notify affected services
          - Track version changes

    Args:
        event: Event payload containing tool update information

    Returns:
        Status confirmation with event type
    """
    event_type = event.get("type", "unknown")
    tool_name = event.get("tool_name", "unknown")

    api_logger.info(
        f"Received tool update event: {event_type} for tool '{tool_name}'",
        extra={"event": event},
    )

    # Placeholder: Add actual processing logic here
    # For now, we just log and acknowledge receipt
    return {
        "status": "received",
        "event_type": "tool-update",
        "processed_at": event.get("timestamp"),
    }


@app.post("/api/events/service-lifecycle")
async def handle_service_lifecycle(event: dict[str, Any]):
    """
    Handle service lifecycle events from Kafka consumer.

    Service lifecycle events track the operational state of services in the
    system (started, stopped, health changes, etc.).

    TODO: Add business logic for lifecycle event processing:
          - Update service registry status
          - Track service uptime/downtime
          - Trigger health monitoring actions

    Args:
        event: Event payload containing service lifecycle information

    Returns:
        Status confirmation with event type
    """
    event_type = event.get("type", "unknown")
    service_id = event.get("service_id", "unknown")

    api_logger.info(
        f"Received service lifecycle event: {event_type} for service '{service_id}'",
        extra={"event": event},
    )

    # Placeholder: Add actual processing logic here
    return {
        "status": "received",
        "event_type": "service-lifecycle",
        "processed_at": event.get("timestamp"),
    }


@app.post("/api/events/system-event")
async def handle_system_event(event: dict[str, Any]):
    """
    Handle general system events from Kafka consumer.

    System events represent important system-level occurrences that don't fit
    into more specific categories (configuration changes, alerts, etc.).

    TODO: Add business logic for system event processing:
          - Route to appropriate subsystems
          - Trigger alerts for critical events
          - Update system state tracking

    Args:
        event: Event payload containing system event information

    Returns:
        Status confirmation with event type
    """
    event_type = event.get("type", "unknown")

    api_logger.info(f"Received system event: {event_type}", extra={"event": event})

    # Placeholder: Add actual processing logic here
    return {
        "status": "received",
        "event_type": "system-event",
        "processed_at": event.get("timestamp"),
    }


@app.post("/api/events/bridge-event")
async def handle_bridge_event(event: dict[str, Any]):
    """
    Handle bridge integration events from Kafka consumer.

    Bridge events represent cross-system integration activities, such as
    metadata stamping, file processing, or OmniNode protocol communications.

    TODO: Add business logic for bridge event processing:
          - Process metadata stamping events
          - Handle file system events
          - Coordinate with Bridge service

    Args:
        event: Event payload containing bridge event information

    Returns:
        Status confirmation with event type
    """
    event_type = event.get("type", "unknown")

    api_logger.info(f"Received bridge event: {event_type}", extra={"event": event})

    # Placeholder: Add actual processing logic here
    return {
        "status": "received",
        "event_type": "bridge-event",
        "processed_at": event.get("timestamp"),
    }


@app.post("/api/events/tree-index")
async def handle_tree_index_event(event: dict[str, Any]):
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

    TODO: Phase 2 implementation:
          - Create/update Document nodes in Memgraph knowledge graph
          - Index file content in Qdrant vector database
          - Establish relationships (imports, dependencies, parent directories)
          - Extract code entities and create semantic links

    Args:
        event: Event payload containing tree discovery and file metadata

    Returns:
        Status confirmation with files processed count
    """
    project_name = event.get("project_name", "unknown")
    files = event.get("files", [])
    event_type = event.get("type", "tree_discovery")

    api_logger.info(
        f"Received tree index event for project '{project_name}' with {len(files)} files",
        extra={
            "project_name": project_name,
            "file_count": len(files),
            "event_type": event_type,
        },
    )

    # Phase 1: Log and acknowledge
    # Phase 2: Process files and populate Memgraph/Qdrant

    return {
        "status": "received",
        "event_type": "tree-index",
        "project_name": project_name,
        "files_processed": len(files),
        "processed_at": event.get("timestamp"),
    }


@app.post("/api/events/generic")
async def handle_generic_event(event: dict[str, Any]):
    """
    Handle generic/unknown events from Kafka consumer (fallback handler).

    This endpoint serves as a fallback for events that don't match any specific
    topic routing. Events arriving here should be investigated to determine if
    they need dedicated handlers.

    Args:
        event: Event payload containing generic event information

    Returns:
        Status confirmation with event type
    """
    event_type = event.get("type", "unknown")
    topic = event.get("topic", "unknown")

    api_logger.warning(
        f"Received generic/unrouted event: {event_type} from topic '{topic}' - "
        f"consider adding dedicated handler",
        extra={"event": event},
    )

    return {
        "status": "received",
        "event_type": "generic",
        "processed_at": event.get("timestamp"),
        "warning": "Event processed by generic handler - consider adding dedicated endpoint",
    }


# ==============================================================================
# Database Schema Validation
# ==============================================================================


# Cache schema check result to avoid repeated database queries
_schema_check_cache = {"valid": None, "checked_at": 0}


async def _check_database_schema():
    """
    Check if required database schema exists.

    Only for existing users who need migration.
    """
    import time

    # If we've already confirmed schema is valid, don't check again
    if _schema_check_cache["valid"] is True:
        return {"valid": True, "message": "Schema is up to date (cached)"}

    # If we recently failed, don't spam the database (wait at least 30 seconds)
    current_time = time.time()
    if (
        _schema_check_cache["valid"] is False
        and current_time - _schema_check_cache["checked_at"] < 30
    ):
        return _schema_check_cache["result"]

    try:
        from .services.client_manager import get_database_client

        client = get_database_client()

        # Try to query the new columns directly - if they exist, schema is up to date
        (
            client.table("archon_sources")
            .select("source_url, source_display_name")
            .limit(1)
            .execute()
        )

        # Cache successful result permanently
        _schema_check_cache["valid"] = True
        _schema_check_cache["checked_at"] = current_time

        return {"valid": True, "message": "Schema is up to date"}

    except Exception as e:
        error_msg = str(e).lower()

        # Log schema check error for debugging
        api_logger.debug(f"Schema check error: {type(e).__name__}: {e!s}")

        # Check for specific error types based on PostgreSQL error codes and messages

        # Check for missing columns first (more specific than table check)
        missing_source_url = "source_url" in error_msg and (
            "column" in error_msg or "does not exist" in error_msg
        )
        missing_source_display = "source_display_name" in error_msg and (
            "column" in error_msg or "does not exist" in error_msg
        )

        # Also check for PostgreSQL error code 42703 (undefined column)
        is_column_error = "42703" in error_msg or "column" in error_msg

        if (missing_source_url or missing_source_display) and is_column_error:
            result = {
                "valid": False,
                "message": (
                    "Database schema outdated - missing required columns "
                    "from recent updates"
                ),
            }
            # Cache failed result with timestamp
            _schema_check_cache["valid"] = False
            _schema_check_cache["checked_at"] = current_time
            _schema_check_cache["result"] = result
            return result

        # Check for table doesn't exist (less specific,
        # only if column check didn't match)
        # Look for relation/table errors specifically
        if ("relation" in error_msg and "does not exist" in error_msg) or (
            "table" in error_msg and "does not exist" in error_msg
        ):
            # Table doesn't exist - not a migration issue, it's a setup issue
            return {
                "valid": True,
                "message": "Table doesn't exist - handled by startup error",
            }

        # Other errors don't necessarily mean migration needed
        result = {"valid": True, "message": f"Schema check inconclusive: {e!s}"}
        # Don't cache inconclusive results - allow retry
        return result


# Export for Socket.IO


# Create Socket.IO app wrapper
# This wraps the FastAPI app with Socket.IO functionality
socket_app = create_socketio_app(app)

# Export the socket_app for uvicorn to use
# The socket_app still handles all FastAPI routes, but also adds Socket.IO support


def main():
    """Main entry point for running the server."""
    import uvicorn

    # Require ARCHON_SERVER_PORT to be set
    server_port = os.getenv("ARCHON_SERVER_PORT")
    if not server_port:
        raise ValueError(
            "ARCHON_SERVER_PORT environment variable is required. "
            "Please set it in your .env file or environment. "
            "Default value: 8181"
        )

    uvicorn.run(
        "src.server.main:socket_app",
        host="0.0.0.0",
        port=int(server_port),
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
