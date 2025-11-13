"""
Kafka Consumer Service Wrapper for Archon Backend

Provides singleton service wrapper around NodeArchonKafkaConsumerEffect
for integration into FastAPI backend lifecycle management.

Responsibilities:
- Initialize consumer EFFECT node with container
- Register default event handlers
- Manage consumer lifecycle (start/stop)
- Follow singleton pattern for backend integration

Author: Archon Integration Team
Version: 1.0.0
Created: 2025-10-07
"""

import logging
import os
from pathlib import Path
from typing import Any, Optional

import yaml

# Centralized configuration
try:
    from config import settings

    _DEFAULT_KAFKA_SERVERS = settings.kafka_bootstrap_servers
except ImportError:
    _DEFAULT_KAFKA_SERVERS = "omninode-bridge-redpanda:9092"

# Try to import omnibase_core dependencies
try:
    from omnibase_core.container import ModelONEXContainer as ONEXContainer
    from omnibase_core.enums.enum_log_level import EnumLogLevel as LogLevel
    from omnibase_core.logging.structured import emit_log_event_sync as emit_log_event

    OMNIBASE_AVAILABLE = True
except ImportError:
    # Stub implementations when omnibase_core not available
    class ONEXContainer:
        def __init__(self):
            self.services = {}

        def register_service(self, name: str, service: Any) -> None:
            self.services[name] = service

    class LogLevel:
        INFO = "INFO"
        WARNING = "WARNING"
        ERROR = "ERROR"
        DEBUG = "DEBUG"

    def emit_log_event(level: str, message: str, context: dict = None) -> None:
        logger = logging.getLogger(__name__)
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(f"{message} {context or {}}")

    OMNIBASE_AVAILABLE = False

try:
    from ..nodes.handlers.service_lifecycle_handler import ServiceLifecycleHandler
    from ..nodes.handlers.system_event_handler import SystemEventHandler
    from ..nodes.handlers.tool_update_handler import ToolUpdateHandler
    from ..nodes.node_archon_kafka_consumer_effect import (
        ModelConsumerConfig,
        NodeArchonKafkaConsumerEffect,
    )

    KAFKA_CONSUMER_AVAILABLE = True
except ImportError:
    # Stub implementations when Kafka consumer not available
    class ModelConsumerConfig:
        def __init__(self, **kwargs):
            import os

            self.bootstrap_servers = kwargs.get(
                "bootstrap_servers",
                os.getenv("KAFKA_BOOTSTRAP_SERVERS", _DEFAULT_KAFKA_SERVERS),
            )
            self.consumer_group = kwargs.get("consumer_group", "archon-consumer-group")
            self.topic_patterns = kwargs.get(
                "topic_patterns", ["dev.omninode_bridge.onex.evt.*.v1"]
            )
            self.auto_offset_reset = kwargs.get("auto_offset_reset", "latest")
            self.enable_auto_commit = kwargs.get("enable_auto_commit", True)
            self.max_poll_records = kwargs.get("max_poll_records", 10)
            self.session_timeout_ms = kwargs.get("session_timeout_ms", 30000)
            self.max_concurrent_events = kwargs.get("max_concurrent_events", 5)
            self.circuit_breaker_enabled = kwargs.get("circuit_breaker_enabled", True)
            self.failure_threshold = kwargs.get("failure_threshold", 5)
            self.timeout_seconds = kwargs.get("timeout_seconds", 60)

    class NodeArchonKafkaConsumerEffect:
        def __init__(self, container, config):
            self.container = container
            self.config = config

        async def start_consuming(self):
            pass

        async def stop_consuming(self):
            pass

    class ServiceLifecycleHandler:
        def get_handler_name(self) -> str:
            return "ServiceLifecycleHandler"

    class SystemEventHandler:
        def get_handler_name(self) -> str:
            return "SystemEventHandler"

    class ToolUpdateHandler:
        def get_handler_name(self) -> str:
            return "ToolUpdateHandler"

    KAFKA_CONSUMER_AVAILABLE = False


# Stub implementations for missing classes
class CodegenLangExtractService:
    def __init__(self, client):
        self.client = client


class CodegenQualityService:
    def __init__(self, scorer):
        self.scorer = scorer


class CodegenPatternService:
    def __init__(self, client):
        self.client = client


class CodegenValidationHandler:
    def __init__(self, quality_service):
        self.quality_service = quality_service

    def get_handler_name(self) -> str:
        return "CodegenValidationHandler"


class CodegenAnalysisHandler:
    def __init__(self, langextract_service):
        self.langextract_service = langextract_service

    def get_handler_name(self) -> str:
        return "CodegenAnalysisHandler"


class CodegenPatternHandler:
    def __init__(self, pattern_service):
        self.pattern_service = pattern_service

    def get_handler_name(self) -> str:
        return "CodegenPatternHandler"


class CodegenMixinHandler:
    def __init__(self, pattern_service):
        self.pattern_service = pattern_service

    def get_handler_name(self) -> str:
        return "CodegenMixinHandler"


class KafkaClient:
    def __init__(self, config):
        self.config = config


def get_http_client_manager():
    return None


class ComprehensiveONEXScorer:
    def __init__(self):
        pass


logger = logging.getLogger(__name__)

# Codegen intelligence handler imports (conditional for MVP Day 2)
try:
    from services.intelligence.src.handlers.codegen_analysis_handler import (
        CodegenAnalysisHandler,
    )
    from services.intelligence.src.handlers.codegen_mixin_handler import (
        CodegenMixinHandler,
    )
    from services.intelligence.src.handlers.codegen_pattern_handler import (
        CodegenPatternHandler,
    )
    from services.intelligence.src.handlers.codegen_validation_handler import (
        CodegenValidationHandler,
    )
    from services.intelligence.src.services.langextract.codegen_langextract_service import (
        CodegenLangExtractService,
    )
    from services.intelligence.src.services.pattern_learning.codegen_pattern_service import (
        CodegenPatternService,
    )
    from services.intelligence.src.services.quality.codegen_quality_service import (
        CodegenQualityService,
    )
    from services.intelligence.src.services.quality.comprehensive_onex_scorer import (
        ComprehensiveONEXScorer,
    )

    CODEGEN_HANDLERS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Codegen intelligence handlers not yet available: {e}")
    CODEGEN_HANDLERS_AVAILABLE = False


class KafkaConsumerService:
    """
    Service wrapper for Kafka consumer EFFECT node.

    Manages consumer lifecycle and integrates with Archon backend startup/shutdown.
    Follows singleton pattern for backend integration.

    Features:
    - Automatic handler registration from contract
    - Consumer lifecycle management
    - Graceful startup/shutdown
    - Error handling and logging

    Usage:
        service = get_kafka_consumer_service()
        await service.start()
        # ... backend operations ...
        await service.stop()
    """

    def __init__(self) -> None:
        """Initialize consumer service (does not start consumer)."""
        self.consumer: Optional[NodeArchonKafkaConsumerEffect] = None
        self._is_running = False

        # Intelligence service clients (lazy initialization)
        self._http_client_manager: Optional[Any] = None
        self._langextract_client: Optional[Any] = None
        self._quality_scorer: Optional[Any] = None
        self._pattern_client: Optional[Any] = None

    async def start(self) -> None:
        """
        Start Kafka consumer with registered handlers.

        This method:
        1. Loads consumer configuration from contract YAML
        2. Creates ONEXContainer with Kafka client
        3. Initializes consumer EFFECT node
        4. Registers default handlers
        5. Starts background consumer loop

        Raises:
            Exception: If consumer fails to start (caller handles gracefully)
        """
        if self._is_running:
            logger.warning("Kafka consumer service already running")
            return

        try:
            # Step 1: Load consumer configuration from contract
            config = self._load_consumer_config()

            # Step 2: Create container with Kafka client
            container = self._create_container()

            # Step 3: Initialize consumer EFFECT node
            self.consumer = NodeArchonKafkaConsumerEffect(container, config)

            # Step 4: Register default handlers
            await self._register_default_handlers()

            # Step 5: Start consumer loop
            await self.consumer.start_consuming()

            self._is_running = True

            emit_log_event(
                LogLevel.INFO,
                "Kafka consumer service started successfully",
                {
                    "consumer_group": config.consumer_group,
                    "topic_patterns": config.topic_patterns,
                    "handlers_registered": len(self.consumer.registry.handlers),
                },
            )

        except Exception as e:
            logger.error(f"Failed to start Kafka consumer service: {e}")
            self.consumer = None
            self._is_running = False
            raise

    async def stop(self) -> None:
        """
        Stop Kafka consumer with graceful shutdown.

        This method:
        1. Stops background consumer loop
        2. Commits offsets
        3. Cleans up resources

        Does not raise exceptions - logs warnings on failure.
        """
        if not self._is_running:
            logger.info("Kafka consumer service not running, nothing to stop")
            return

        try:
            if self.consumer:
                await self.consumer.stop_consuming()

            self._is_running = False

            emit_log_event(
                LogLevel.INFO,
                "Kafka consumer service stopped successfully",
                {
                    "final_metrics": self.consumer.metrics if self.consumer else {},
                },
            )

        except Exception as e:
            logger.warning(f"Error during Kafka consumer service shutdown: {e}")
            self._is_running = False

    def _load_consumer_config(self) -> ModelConsumerConfig:
        """
        Load consumer configuration from contract YAML.

        Returns:
            ModelConsumerConfig with settings from contract

        Note:
            Falls back to defaults if contract file is missing or invalid
        """
        try:
            contract_path = (
                Path(__file__).parent.parent / "nodes" / "consumer_contract.yaml"
            )

            if not contract_path.exists():
                logger.warning(
                    f"Consumer contract not found at {contract_path}, using defaults"
                )
                return ModelConsumerConfig()

            with open(contract_path) as f:
                contract = yaml.safe_load(f)

            consumer_cfg = contract.get("consumer_config", {})

            # Map contract config to ModelConsumerConfig
            config = ModelConsumerConfig(
                bootstrap_servers=consumer_cfg.get(
                    "bootstrap_servers",
                    os.getenv("KAFKA_BOOTSTRAP_SERVERS", _DEFAULT_KAFKA_SERVERS),
                ),
                consumer_group=consumer_cfg.get(
                    "consumer_group", "archon-consumer-group"
                ),
                topic_patterns=consumer_cfg.get(
                    "topic_patterns", ["dev.omninode_bridge.onex.evt.*.v1"]
                ),
                auto_offset_reset=consumer_cfg.get("auto_offset_reset", "latest"),
                enable_auto_commit=consumer_cfg.get("enable_auto_commit", True),
                max_poll_records=consumer_cfg.get("max_poll_records", 10),
                session_timeout_ms=consumer_cfg.get("session_timeout_ms", 30000),
                max_concurrent_events=consumer_cfg.get("max_concurrent_events", 5),
                circuit_breaker_enabled=contract.get("consumer_config", {}).get(
                    "circuit_breaker_enabled", True
                ),
                failure_threshold=contract.get("consumer_config", {}).get(
                    "failure_threshold", 5
                ),
                timeout_seconds=contract.get("consumer_config", {}).get(
                    "timeout_seconds", 60
                ),
            )

            logger.info(f"Loaded consumer configuration from {contract_path}")
            return config

        except Exception as e:
            logger.warning(f"Error loading consumer contract, using defaults: {e}")
            return ModelConsumerConfig()

    def _create_container(self) -> ONEXContainer:
        """
        Create ONEXContainer with Kafka client dependency.

        Returns:
            ONEXContainer with registered Kafka client

        Note:
            This creates a minimal container for the consumer.
            In the future, this could be enhanced to share the main
            backend container if needed.
        """
        # Use the stub KafkaClient defined above

        container = ONEXContainer()

        # Create and register Kafka client
        kafka_client = KafkaClient()
        container.register_service("kafka_client", kafka_client)

        logger.info("Created ONEX container with Kafka client")
        return container

    async def _register_default_handlers(self) -> None:
        """
        Register default event handlers from contract.

        Registers:
        - ToolUpdateHandler: Handles tool update events
        - ServiceLifecycleHandler: Handles service lifecycle events
        - SystemEventHandler: Handles system-level events and alerts
        - CodegenValidationHandler: Validates generated code quality (MVP Day 1)
        - CodegenAnalysisHandler: Analyzes code semantics via LangExtract (MVP Day 2)
        - CodegenPatternHandler: Matches patterns and recommends best practices (MVP Day 2)
        - CodegenMixinHandler: Recommends ONEX mixins for code generation (MVP Day 2)

        Note:
            Codegen intelligence handlers are registered conditionally based on
            availability. If handler modules are not found, registration continues
            gracefully with existing handlers only.
        """
        if not self.consumer:
            logger.error("Cannot register handlers - consumer not initialized")
            return

        try:
            registered_handlers = []

            # Register ToolUpdateHandler
            tool_handler = ToolUpdateHandler()
            self.consumer.registry.register(tool_handler)
            registered_handlers.append(tool_handler.get_handler_name())
            logger.info("Registered ToolUpdateHandler")

            # Register ServiceLifecycleHandler
            lifecycle_handler = ServiceLifecycleHandler()
            self.consumer.registry.register(lifecycle_handler)
            registered_handlers.append(lifecycle_handler.get_handler_name())
            logger.info("Registered ServiceLifecycleHandler")

            # Register SystemEventHandler
            system_handler = SystemEventHandler()
            self.consumer.registry.register(system_handler)
            registered_handlers.append(system_handler.get_handler_name())
            logger.info("Registered SystemEventHandler")

            # ===================================================================
            # MVP Day 2: Register Codegen Intelligence Handlers (Conditional)
            # ===================================================================

            if CODEGEN_HANDLERS_AVAILABLE:
                try:
                    # Initialize intelligence service clients
                    import asyncio

                    langextract_client = await self._get_langextract_client()
                    quality_scorer = await self._get_quality_scorer()
                    pattern_client = await self._get_pattern_client()

                    # Create intelligence service wrappers
                    langextract_service = CodegenLangExtractService(langextract_client)
                    quality_service = CodegenQualityService(quality_scorer)
                    pattern_service = CodegenPatternService(pattern_client)

                    # Register CodegenValidationHandler (MVP Day 1)
                    validation_handler = CodegenValidationHandler(quality_service)
                    self.consumer.registry.register(validation_handler)
                    registered_handlers.append(validation_handler.get_handler_name())
                    logger.info("Registered CodegenValidationHandler (MVP Day 1)")

                    # Register CodegenAnalysisHandler (MVP Day 2)
                    analysis_handler = CodegenAnalysisHandler(langextract_service)
                    self.consumer.registry.register(analysis_handler)
                    registered_handlers.append(analysis_handler.get_handler_name())
                    logger.info(
                        "Registered CodegenAnalysisHandler (MVP Day 2 - Agent 1)"
                    )

                    # Register CodegenPatternHandler (MVP Day 2)
                    pattern_handler = CodegenPatternHandler(pattern_service)
                    self.consumer.registry.register(pattern_handler)
                    registered_handlers.append(pattern_handler.get_handler_name())
                    logger.info(
                        "Registered CodegenPatternHandler (MVP Day 2 - Agent 2)"
                    )

                    # Register CodegenMixinHandler (MVP Day 2)
                    mixin_handler = CodegenMixinHandler(pattern_service)
                    self.consumer.registry.register(mixin_handler)
                    registered_handlers.append(mixin_handler.get_handler_name())
                    logger.info("Registered CodegenMixinHandler (MVP Day 2 - Agent 2)")

                    logger.info(
                        "Successfully registered all 4 codegen intelligence handlers"
                    )

                except Exception as handler_error:
                    logger.error(
                        f"Failed to register codegen intelligence handlers: {handler_error}",
                        exc_info=True,
                    )
                    logger.warning(
                        "Continuing with base handlers only (tool, lifecycle, system)"
                    )

            else:
                logger.warning(
                    "Codegen intelligence handlers not available - skipping registration. "
                    "This is expected if handlers are not yet created by Agents 1-2."
                )

            emit_log_event(
                LogLevel.INFO,
                "Event handlers registered",
                {
                    "handlers": registered_handlers,
                    "total_handlers": len(registered_handlers),
                    "codegen_handlers_enabled": CODEGEN_HANDLERS_AVAILABLE,
                },
            )

        except Exception as e:
            logger.error(f"Failed to register default handlers: {e}")
            raise

    def get_status(self) -> dict:
        """
        Get current consumer service status.

        Returns:
            Dict with status information including metrics
        """
        if not self.consumer or not self._is_running:
            return {
                "status": "stopped",
                "is_running": False,
            }

        return {
            "status": self.consumer.consumer_state.value,
            "is_running": self._is_running,
            "metrics": self.consumer.metrics,
            "circuit_breaker_state": self.consumer.circuit_breaker.state.value,
            "handlers_registered": len(self.consumer.registry.handlers),
        }

    # ============================================================================
    # Intelligence Service Client Helpers (MVP Day 2)
    # ============================================================================

    async def _get_http_client_manager(self):
        """
        Get or create HTTP client manager for intelligence services.

        Returns:
            CentralizedHttpClientManager instance

        Note:
            Uses lazy initialization and caching for efficiency
        """
        if self._http_client_manager is None:
            from ..services.centralized_http_client_manager import (
                get_http_client_manager,
            )

            self._http_client_manager = await get_http_client_manager()
            logger.debug("Initialized HTTP client manager for intelligence services")

        return self._http_client_manager

    async def _get_langextract_client(self):
        """
        Get or create LangExtract HTTP client for semantic analysis.

        Returns:
            httpx.AsyncClient configured for LangExtract service

        Note:
            LangExtract service provides ML-based semantic analysis,
            entity extraction, and classification for code generation.
        """
        if self._langextract_client is None:
            import os

            from ..config.archon_config import get_archon_config

            get_archon_config()
            langextract_url = os.getenv(
                "LANGEXTRACT_SERVICE_URL", "http://archon-langextract:8156"
            )

            client_manager = await self._get_http_client_manager()
            self._langextract_client = await client_manager.get_client("langextract")

            logger.info(
                f"Initialized LangExtract client for CodegenAnalysisHandler: {langextract_url}"
            )

        return self._langextract_client

    async def _get_quality_scorer(self):
        """
        Get or create ONEX quality scorer for code validation.

        Returns:
            ComprehensiveONEXScorer instance

        Note:
            Uses official omnibase_core validators with comprehensive
            quality scoring across 6 dimensions.
        """
        if self._quality_scorer is None:
            if CODEGEN_HANDLERS_AVAILABLE:
                self._quality_scorer = ComprehensiveONEXScorer()
                logger.info(
                    "Initialized ComprehensiveONEXScorer for CodegenValidationHandler"
                )
            else:
                logger.warning(
                    "ComprehensiveONEXScorer not available - handlers not loaded"
                )
                return None

        return self._quality_scorer

    async def _get_pattern_client(self):
        """
        Get or create Pattern Learning HTTP client for pattern matching.

        Returns:
            httpx.AsyncClient configured for Pattern Learning service

        Note:
            Pattern Learning service provides hybrid pattern matching,
            semantic analysis, and mixin recommendations.
        """
        if self._pattern_client is None:
            from ..config.archon_config import get_archon_config

            config = get_archon_config()
            pattern_learning_url = config.intelligence_service.base_url

            client_manager = await self._get_http_client_manager()
            self._pattern_client = await client_manager.get_client("pattern_learning")

            logger.info(
                f"Initialized Pattern Learning client for CodegenPatternHandler: {pattern_learning_url}"
            )

        return self._pattern_client


# ============================================================================
# Singleton Pattern
# ============================================================================

_consumer_service: Optional[KafkaConsumerService] = None


def get_kafka_consumer_service() -> KafkaConsumerService:
    """
    Get singleton Kafka consumer service instance.

    Returns:
        Singleton KafkaConsumerService instance

    Usage:
        service = get_kafka_consumer_service()
        await service.start()
    """
    global _consumer_service
    if _consumer_service is None:
        _consumer_service = KafkaConsumerService()
    return _consumer_service
