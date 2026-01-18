"""
Node Intelligence Adapter Effect - ONEX Effect Node with Kafka Event Integration.

This Effect node provides:
- Code analysis operations via Archon intelligence services
- Kafka event subscription for CODE_ANALYSIS_REQUESTED events
- Event publishing for CODE_ANALYSIS_COMPLETED/FAILED events
- Consumer lifecycle management
- Distributed tracing and correlation tracking
- Error handling with DLQ routing

ONEX Compliance:
- Suffix-based naming: NodeIntelligenceAdapterEffect
- Effect pattern: async execute_effect() method
- Strong typing with Pydantic models
- Correlation ID preservation
- Comprehensive error handling via OnexError

Event Flow:
1. Subscribe to dev.archon-intelligence.intelligence.code-analysis-requested.v1
2. Consume events in background loop
3. Route to analyze_code() operation
4. Publish CODE_ANALYSIS_COMPLETED or CODE_ANALYSIS_FAILED events
5. Commit offsets after successful processing

Architecture Note:
    This adapter currently handles multiple operation types (quality assessment,
    pattern detection, performance analysis). A future consideration is to split
    this into smaller, focused adapters. See ARCHITECTURE.md in this directory
    for detailed analysis and implementation roadmap.

Created: 2025-10-21
Reference: EVENT_BUS_ARCHITECTURE.md, intelligence_adapter_events.py, ARCHITECTURE.md
"""

import asyncio
import logging
import os
import time
from typing import Any
from uuid import UUID, uuid4

try:
    from confluent_kafka import Consumer, KafkaError, KafkaException

    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    Consumer = None
    KafkaError = None
    KafkaException = None

from pydantic import BaseModel, Field

# Centralized configuration
try:
    from config import settings as parent_settings

    _DEFAULT_KAFKA_SERVERS = parent_settings.kafka_bootstrap_servers
except ImportError:
    # Allow fallback ONLY if explicitly enabled via environment variable
    if os.getenv("OMNIINTELLIGENCE_ALLOW_DEFAULT_KAFKA", "").lower() == "true":
        _DEFAULT_KAFKA_SERVERS = "omninode-bridge-redpanda:9092"
    else:
        raise RuntimeError(
            "Failed to import Kafka configuration. "
            "Set KAFKA_BOOTSTRAP_SERVERS environment variable or "
            "set OMNIINTELLIGENCE_ALLOW_DEFAULT_KAFKA=true to use defaults."
        )

# Canonical models
from omniintelligence.models import ModelIntelligenceInput, ModelIntelligenceOutput

# Stub implementations for removed legacy dependencies
# These provide type compatibility without the full implementation
# TODO: Implement full replacements if needed for production use


class ModelIntelligenceConfig(BaseModel):
    """Stub config - use environment variables directly."""

    service_url: str = Field(default="http://localhost:8080")
    timeout: int = Field(default=30)

    @classmethod
    def from_environment_variable(cls) -> "ModelIntelligenceConfig":
        return cls(
            service_url=os.getenv("INTELLIGENCE_SERVICE_URL", "http://localhost:8080"),
            timeout=int(os.getenv("INTELLIGENCE_TIMEOUT", "30")),
        )


class IntelligenceServiceClient:
    """Stub client - raises NotImplementedError for actual calls."""

    def __init__(self, config: ModelIntelligenceConfig):
        self.config = config

    async def analyze_code(self, *args: Any, **kwargs: Any) -> ModelIntelligenceOutput:
        raise NotImplementedError("IntelligenceServiceClient requires implementation")

    async def close(self) -> None:
        pass


class EventPublisher:
    """Stub event publisher - logs instead of publishing."""

    def __init__(self, *args: Any, **kwargs: Any):
        self._logger = logging.getLogger(__name__)

    async def publish(self, topic: str, payload: Any, **kwargs: Any) -> None:
        self._logger.info(f"[STUB] Would publish to {topic}: {type(payload).__name__}")

    async def close(self) -> None:
        pass


# Stub request models
class ModelQualityAssessmentRequest(BaseModel):
    """Stub for quality assessment requests."""

    source_path: str = ""
    content: str = ""
    options: dict[str, Any] = Field(default_factory=dict)


class ModelPatternDetectionRequest(BaseModel):
    """Stub for pattern detection requests."""

    source_path: str = ""
    content: str = ""
    patterns: list[str] = Field(default_factory=list)


class ModelPerformanceAnalysisRequest(BaseModel):
    """Stub for performance analysis requests."""

    source_path: str = ""
    content: str = ""
    metrics: list[str] = Field(default_factory=list)


# Stub enums and event models
from enum import Enum


class EnumAnalysisErrorCode(str, Enum):
    """Analysis error codes."""

    UNKNOWN = "unknown"
    TIMEOUT = "timeout"
    INVALID_INPUT = "invalid_input"
    SERVICE_ERROR = "service_error"


class EnumAnalysisOperationType(str, Enum):
    """Analysis operation types."""

    QUALITY_ASSESSMENT = "quality_assessment"
    PATTERN_DETECTION = "pattern_detection"
    PERFORMANCE_ANALYSIS = "performance_analysis"


class EnumCodeAnalysisEventType(str, Enum):
    """Code analysis event types."""

    REQUESTED = "requested"
    COMPLETED = "completed"
    FAILED = "failed"


class ModelCodeAnalysisRequestPayload(BaseModel):
    """Event payload for code analysis requests."""

    correlation_id: str = ""
    source_path: str = ""
    content: str = ""
    operation_type: str = ""


class ModelCodeAnalysisCompletedPayload(BaseModel):
    """Event payload for completed analysis."""

    correlation_id: str = ""
    result: dict[str, Any] = Field(default_factory=dict)


class ModelCodeAnalysisFailedPayload(BaseModel):
    """Event payload for failed analysis."""

    correlation_id: str = ""
    error_code: str = ""
    error_message: str = ""


class IntelligenceAdapterEventHelpers:
    """Stub helpers for event creation."""

    @staticmethod
    def create_completed_event(correlation_id: str, result: Any) -> dict[str, Any]:
        return {"correlation_id": correlation_id, "result": result}

    @staticmethod
    def create_failed_event(
        correlation_id: str, error_code: str, error_message: str
    ) -> dict[str, Any]:
        return {
            "correlation_id": correlation_id,
            "error_code": error_code,
            "error_message": error_message,
        }
from datetime import UTC

logger = logging.getLogger(__name__)


class ModelKafkaConsumerConfig(BaseModel):
    """
    Configuration for Kafka consumer.

    Attributes:
        bootstrap_servers: Kafka bootstrap servers (comma-separated)
        group_id: Consumer group ID
        topics: List of topics to subscribe to
        auto_offset_reset: Offset reset strategy (earliest, latest)
        enable_auto_commit: Enable auto-commit of offsets
        max_poll_records: Maximum records per poll
        session_timeout_ms: Session timeout in milliseconds
        max_poll_interval_ms: Max time between polls
    """

    bootstrap_servers: str = Field(
        default=_DEFAULT_KAFKA_SERVERS,
        description="Kafka bootstrap servers from centralized config",
    )

    group_id: str = Field(
        default="intelligence_adapter_consumers",
        description="Consumer group ID for load balancing",
    )

    topics: list[str] = Field(
        default_factory=lambda: [
            "dev.archon-intelligence.intelligence.code-analysis-requested.v1"
        ],
        description="Topics to subscribe to",
    )

    auto_offset_reset: str = Field(
        default="latest",
        description="Offset reset strategy (earliest, latest)",
    )

    enable_auto_commit: bool = Field(
        default=False,
        description="Enable auto-commit (False for manual control)",
    )

    max_poll_records: int = Field(
        default=10,
        description="Maximum records to fetch per poll",
    )

    session_timeout_ms: int = Field(
        default=30000,
        description="Session timeout in milliseconds",
    )

    max_poll_interval_ms: int = Field(
        default=300000,
        description="Max time between polls (5 minutes)",
    )


class NodeIntelligenceAdapterEffect:
    """
    Intelligence Adapter Effect Node with Kafka Event Integration.

    This ONEX Effect node integrates Archon's intelligence services with
    event-driven architecture via Kafka. It subscribes to code analysis
    request events, processes them via intelligence services, and publishes
    completion/failure events.

    **Core Capabilities**:
    - Code quality assessment with ONEX compliance scoring
    - Document quality analysis
    - Pattern extraction and matching
    - Architectural compliance validation
    - Kafka event subscription and publishing
    - Distributed tracing with correlation IDs

    **Event Subscription**:
    - Topic: dev.archon-intelligence.intelligence.code-analysis-requested.v1
    - Consumer Group: intelligence_adapter_consumers
    - Offset Strategy: Latest (configurable)
    - Manual offset commit after successful processing

    **Event Publishing**:
    - CODE_ANALYSIS_COMPLETED: On successful analysis
    - CODE_ANALYSIS_FAILED: On analysis failure or error
    - DLQ routing: Unrecoverable errors sent to .dlq topic

    **Lifecycle Management**:
    - initialize(): Start Kafka consumer and background loop
    - shutdown(): Stop consumer, commit offsets, cleanup
    - Graceful error handling with exponential backoff

    **Usage**:
        >>> from uuid import uuid4
        >>> from omniintelligence.models import ModelIntelligenceInput
        >>>
        >>> # Direct operation (non-event)
        >>> node = NodeIntelligenceAdapterEffect(service_url="http://localhost:8053")
        >>> await node.initialize()
        >>>
        >>> input_data = ModelIntelligenceInput(
        ...     operation_type="assess_code_quality",
        ...     correlation_id=uuid4(),
        ...     content="def hello(): pass",
        ...     source_path="test.py",
        ...     language="python"
        ... )
        >>>
        >>> output = await node.analyze_code(input_data)
        >>> assert output.success
        >>> assert 0.0 <= output.quality_score <= 1.0
        >>>
        >>> # Event-driven operation (automatic)
        >>> # Events are consumed in background loop
        >>> # Results published to Kafka automatically
        >>>
        >>> await node.shutdown()

    **Error Handling**:
    - Kafka consumer errors: Log and retry with backoff
    - Analysis errors: Publish CODE_ANALYSIS_FAILED event
    - Unrecoverable errors: Route to DLQ topic
    - Circuit breaker: Prevent cascading failures

    Attributes:
        service_url: Intelligence service base URL
        event_publisher: Kafka event publisher
        kafka_consumer: Kafka consumer instance
        consumer_config: Kafka consumer configuration
        is_running: Consumer running status
        metrics: Operation metrics (events processed, errors, etc.)
    """

    def __init__(
        self,
        container: Any,
        service_url: str = "http://archon-intelligence:8053",
        bootstrap_servers: str = _DEFAULT_KAFKA_SERVERS,
        consumer_config: ModelKafkaConsumerConfig | None = None,
    ):
        """
        Initialize Intelligence Adapter Effect Node.

        Args:
            container: ONEX container for dependency injection
            service_url: Intelligence service base URL
            bootstrap_servers: Kafka bootstrap servers
            consumer_config: Optional Kafka consumer configuration
        """
        self.container = container
        self.node_id = uuid4()
        self.service_url = service_url
        self.bootstrap_servers = bootstrap_servers
        self.consumer_config = consumer_config or ModelKafkaConsumerConfig(
            bootstrap_servers=bootstrap_servers
        )

        # ONEX-compliant attributes
        self._config: ModelIntelligenceConfig | None = None
        self._client: IntelligenceServiceClient | None = None

        # Kafka infrastructure
        self.event_publisher: EventPublisher | None = None
        self.kafka_consumer: Consumer | None = None
        self._event_consumption_task: asyncio.Task[None] | None = None

        # Lifecycle state
        self.is_running = False
        self._shutdown_event = asyncio.Event()

        # Statistics tracking (ONEX-compliant _stats attribute)
        self._stats: dict[str, Any] = {
            "total_analyses": 0,
            "successful_analyses": 0,
            "failed_analyses": 0,
            "total_quality_score": 0.0,
            "avg_quality_score": 0.0,
            "success_rate": 0.0,
            "last_analysis_time": None,
        }

        # Event metrics
        self.metrics = {
            "events_consumed": 0,
            "events_processed": 0,
            "events_failed": 0,
            "analysis_completed": 0,
            "analysis_failed": 0,
            "dlq_routed": 0,
            "total_processing_time_ms": 0.0,
            "avg_processing_time_ms": 0.0,
        }

        logger.info(
            f"NodeIntelligenceAdapterEffect initialized | "
            f"node_id={self.node_id} | "
            f"service_url={service_url} | "
            f"kafka={bootstrap_servers}"
        )

    async def initialize(self) -> None:
        """
        Initialize Intelligence Adapter Effect Node.

        This method:
        1. Loads configuration from environment
        2. Creates intelligence service client
        3. Connects to intelligence service
        4. Performs health check
        5. Initializes Kafka consumer (if available)
        6. Initializes event publisher
        7. Starts background event consumption loop

        Raises:
            ModelOnexError: If initialization fails
        """
        from omnibase_core.enums.enum_core_error_code import EnumCoreErrorCode
        from omnibase_core.models.errors.model_onex_error import ModelOnexError

        try:
            # Step 1: Load configuration from environment
            self._config = ModelIntelligenceConfig.from_environment_variable()
            logger.info(
                f"Configuration loaded | base_url={self._config.base_url} | "
                f"timeout={self._config.timeout_seconds}s"
            )

            # Step 2: Create intelligence service client
            self._client = IntelligenceServiceClient(
                base_url=self._config.base_url,
                timeout_seconds=self._config.timeout_seconds,
                max_retries=self._config.max_retries,
                circuit_breaker_enabled=self._config.circuit_breaker_enabled,
            )

            # Step 3: Connect to intelligence service
            await self._client.connect()
            logger.info("Intelligence service client connected")

            # Step 4: Perform health check (warning only if fails)
            try:
                health_response = await self._client.check_health()
                logger.info(
                    f"Intelligence service health check passed | "
                    f"status={health_response.status} | "
                    f"version={health_response.service_version}"
                )
            except (ConnectionError, TimeoutError, OSError) as health_error:
                # Network-related errors during health check are non-fatal
                logger.warning(
                    f"Health check failed (continuing anyway): {health_error}"
                )
            except Exception as health_error:
                # Intentionally broad: health check should never prevent initialization
                # This catches unexpected errors like response parsing failures
                logger.warning(
                    f"Health check failed with unexpected error (continuing anyway): {health_error}"
                )

            # Step 5-7: Initialize Kafka infrastructure (if available)
            if KAFKA_AVAILABLE:
                try:
                    await self._initialize_kafka_infrastructure()
                except (KafkaException, ConnectionError, TimeoutError) as kafka_error:
                    # Kafka-specific or network errors during initialization are non-fatal
                    logger.warning(
                        f"Kafka initialization failed (continuing without event bus): {kafka_error}"
                    )
                except RuntimeError as kafka_error:
                    # RuntimeError from our own _initialize_kafka_infrastructure
                    logger.warning(
                        f"Kafka initialization failed (continuing without event bus): {kafka_error}"
                    )
            else:
                logger.warning(
                    "Kafka not available, skipping event bus initialization. "
                    "Direct API calls only."
                )

            logger.info(
                f"NodeIntelligenceAdapterEffect initialized | "
                f"node_id={self.node_id} | "
                f"config_loaded=True | "
                f"client_connected=True | "
                f"kafka_available={KAFKA_AVAILABLE}"
            )

        except (ConnectionError, TimeoutError, OSError) as e:
            # Network-related initialization failures
            logger.error(
                f"Failed to initialize Intelligence Adapter (network error): {e}", exc_info=True
            )
            raise ModelOnexError(
                error_code=EnumCoreErrorCode.INITIALIZATION_FAILED,
                message=f"Failed to initialize Intelligence Adapter (network error): {e!s}",
            ) from e
        except ValueError as e:
            # Configuration or validation errors
            logger.error(
                f"Failed to initialize Intelligence Adapter (config error): {e}", exc_info=True
            )
            raise ModelOnexError(
                error_code=EnumCoreErrorCode.INITIALIZATION_FAILED,
                message=f"Failed to initialize Intelligence Adapter (config error): {e!s}",
            ) from e
        except Exception as e:
            # Intentionally broad: top-level catch-all to convert any unexpected error
            # to ModelOnexError for consistent error handling across the ONEX system
            logger.error(
                f"Failed to initialize Intelligence Adapter (unexpected): {e}", exc_info=True
            )
            raise ModelOnexError(
                error_code=EnumCoreErrorCode.INITIALIZATION_FAILED,
                message=f"Failed to initialize Intelligence Adapter: {e!s}",
            ) from e

    async def _initialize_kafka_infrastructure(self) -> None:
        """
        Initialize Kafka consumer and event publisher.

        This is a separate method to allow initialization to succeed even
        if Kafka is not available (for direct API usage).

        Raises:
            RuntimeError: If Kafka initialization fails
        """
        if self.is_running:
            logger.warning("Consumer already running, skipping Kafka initialization")
            return

        try:
            # Step 1: Create Kafka consumer
            consumer_conf = {
                "bootstrap.servers": self.consumer_config.bootstrap_servers,
                "group.id": self.consumer_config.group_id,
                "auto.offset.reset": self.consumer_config.auto_offset_reset,
                "enable.auto.commit": self.consumer_config.enable_auto_commit,
                "max.poll.interval.ms": self.consumer_config.max_poll_interval_ms,
                "session.timeout.ms": self.consumer_config.session_timeout_ms,
                "client.id": f"intelligence-adapter-{uuid4().hex[:8]}",
            }

            self.kafka_consumer = Consumer(consumer_conf)

            # Step 2: Subscribe to topics
            self.kafka_consumer.subscribe(self.consumer_config.topics)

            logger.info(
                f"Kafka consumer subscribed | "
                f"topics={self.consumer_config.topics} | "
                f"group_id={self.consumer_config.group_id}"
            )

            # Step 3: Initialize event publisher
            self.event_publisher = EventPublisher(
                bootstrap_servers=self.bootstrap_servers,
                service_name="archon-intelligence",
                instance_id=f"intelligence-adapter-{uuid4().hex[:8]}",
                max_retries=3,
                enable_dlq=True,
            )

            logger.info("Event publisher initialized")

            # Step 4: Start background consumption loop
            self._event_consumption_task = asyncio.create_task(
                self._consume_events_loop()
            )

            self.is_running = True

            logger.info("Kafka infrastructure initialized and consumption started")

        except KafkaException as e:
            # Kafka-specific errors (broker connection, subscription, etc.)
            logger.error(
                f"Failed to initialize Kafka infrastructure (Kafka error): {e}", exc_info=True
            )
            raise RuntimeError(f"Kafka infrastructure initialization failed: {e}") from e
        except (ConnectionError, TimeoutError) as e:
            # Network-related errors during Kafka initialization
            logger.error(
                f"Failed to initialize Kafka infrastructure (network error): {e}", exc_info=True
            )
            raise RuntimeError(f"Kafka infrastructure initialization failed: {e}") from e
        except Exception as e:
            # Intentionally broad: catch unexpected errors during Kafka setup
            # and convert to RuntimeError for consistent handling
            logger.error(
                f"Failed to initialize Kafka infrastructure (unexpected): {e}", exc_info=True
            )
            raise RuntimeError(f"Kafka infrastructure initialization failed: {e}") from e

    async def shutdown(self) -> None:
        """
        Shutdown Kafka consumer and event publisher.

        This method:
        1. Signals shutdown to background loop
        2. Waits for in-flight events to complete
        3. Commits final offsets
        4. Closes Kafka consumer
        5. Closes event publisher
        6. Cleans up node resources

        Does not raise exceptions - logs warnings on failure.
        """
        if not self.is_running:
            logger.info("Consumer not running, nothing to shutdown")
            return

        logger.info("Shutting down Intelligence Adapter Effect Node...")

        # Step 1: Signal shutdown
        self._shutdown_event.set()

        # Step 2: Wait for consumption loop to finish
        if self._event_consumption_task:
            try:
                await asyncio.wait_for(self._event_consumption_task, timeout=30.0)
            except TimeoutError:
                logger.warning("Event consumption task did not finish in 30s")
                self._event_consumption_task.cancel()

        # Step 3: Commit offsets and close consumer
        if self.kafka_consumer:
            try:
                self.kafka_consumer.commit()
                self.kafka_consumer.close()
                logger.info("Kafka consumer closed, offsets committed")
            except KafkaException as e:
                # Kafka-specific errors during cleanup
                logger.warning(f"Kafka error closing consumer: {e}")
            except Exception as e:
                # Intentionally broad: cleanup must never raise, any error is logged only
                logger.warning(f"Error closing Kafka consumer: {e}")

        # Step 4: Close event publisher
        if self.event_publisher:
            try:
                await self.event_publisher.close()
                logger.info("Event publisher closed")
            except Exception as e:
                # Intentionally broad: cleanup must never raise, any error is logged only
                logger.warning(f"Error closing event publisher: {e}")

        # Step 5: Clean up node resources
        await self._cleanup_node_resources()

        self.is_running = False

        logger.info(
            f"NodeIntelligenceAdapterEffect shutdown complete | "
            f"final_metrics={self.metrics}"
        )

    async def _cleanup_node_resources(self) -> None:
        """
        Clean up node resources (ONEX-compliant).

        This method:
        1. Closes the intelligence service client
        2. Clears client reference

        Does not raise exceptions - logs warnings on failure.
        """
        if self._client:
            try:
                await self._client.close()
                logger.info("Intelligence service client closed")
            except (ConnectionError, TimeoutError) as e:
                # Network errors during client close are expected and non-fatal
                logger.warning(f"Network error closing intelligence service client: {e}")
            except Exception as e:
                # Intentionally broad: cleanup must never raise, any error is logged only
                logger.warning(f"Error closing intelligence service client: {e}")
            finally:
                self._client = None

    async def _consume_events_loop(self) -> None:
        """
        Background event consumption loop.

        This method:
        1. Polls Kafka for new messages in batches
        2. Routes messages to appropriate handlers
        3. Commits offsets after successful processing
        4. Handles errors with retry and DLQ routing
        5. Runs until shutdown signal

        Error Handling:
        - Kafka errors: Log and continue
        - Processing errors: Publish failed event, route to DLQ
        - Unrecoverable errors: Log and skip message
        """
        logger.info("Starting event consumption loop...")

        while not self._shutdown_event.is_set():
            try:
                # Guard: Kafka consumer must be initialized
                if self.kafka_consumer is None:
                    logger.error("Kafka consumer not initialized, stopping loop")
                    break

                # Poll for messages (1 second timeout)
                msg = self.kafka_consumer.poll(timeout=1.0)

                if msg is None:
                    # No message, continue polling
                    continue

                if msg.error():
                    # Kafka error
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        # End of partition, continue
                        continue
                    else:
                        logger.error(f"Kafka consumer error: {msg.error()}")
                        continue

                # Step 1: Message received
                self.metrics["events_consumed"] += 1

                # Step 2: Deserialize and route message
                try:
                    await self._route_event_to_operation(msg)
                    self.metrics["events_processed"] += 1

                    # Step 3: Commit offset after successful processing
                    if not self.consumer_config.enable_auto_commit:
                        self.kafka_consumer.commit(asynchronous=True)

                except ValueError as e:
                    # Deserialization or validation errors
                    self.metrics["events_failed"] += 1
                    logger.error(
                        f"Failed to process event (validation error) | error={e} | "
                        f"topic={msg.topic()} | partition={msg.partition()} | "
                        f"offset={msg.offset()}",
                        exc_info=True,
                    )
                    # Pass exception directly for proper error type extraction
                    await self._route_to_dlq(msg, e)

                except Exception as e:
                    # Intentionally broad: any processing error should route to DLQ
                    # rather than crash the consumer loop
                    self.metrics["events_failed"] += 1
                    logger.error(
                        f"Failed to process event | error={e} | "
                        f"topic={msg.topic()} | partition={msg.partition()} | "
                        f"offset={msg.offset()}",
                        exc_info=True,
                    )

                    # Route to DLQ for manual inspection - pass exception for type extraction
                    await self._route_to_dlq(msg, e)

            except KafkaException as ke:
                logger.error(
                    f"Kafka exception in consumption loop: {ke}", exc_info=True
                )
                # Continue after Kafka errors
                await asyncio.sleep(1.0)

            except (ConnectionError, TimeoutError) as e:
                # Network-related errors in the consumption loop
                logger.error(
                    f"Network error in consumption loop: {e}", exc_info=True
                )
                await asyncio.sleep(1.0)

            except Exception as e:
                # Intentionally broad: event loop must never crash, any unexpected
                # error is logged and the loop continues
                logger.error(
                    f"Unexpected error in consumption loop: {e}", exc_info=True
                )
                # Continue after unexpected errors
                await asyncio.sleep(1.0)

        logger.info("Event consumption loop stopped")

    async def _route_event_to_operation(self, message: Any) -> None:
        """
        Route Kafka message to appropriate operation handler.

        This method:
        1. Deserializes Kafka message value (JSON)
        2. Extracts event envelope and payload
        3. Determines event type
        4. Routes to analyze_code() for CODE_ANALYSIS_REQUESTED
        5. Publishes completion/failure events

        Args:
            message: Kafka message from consumer

        Raises:
            Exception: If message processing fails (caller handles DLQ routing)
        """
        import json

        start_time = time.perf_counter()

        # Step 1: Deserialize message
        try:
            message_value = message.value().decode("utf-8")
            event_dict = json.loads(message_value)
        except UnicodeDecodeError as e:
            logger.error(f"Failed to decode message bytes: {e}")
            raise ValueError(f"Message decoding failed (invalid UTF-8): {e}") from e
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message JSON: {e}")
            raise ValueError(f"Message parsing failed (invalid JSON): {e}") from e
        except (AttributeError, TypeError) as e:
            # message.value() returned None or unexpected type
            logger.error(f"Invalid message format: {e}")
            raise ValueError(f"Message deserialization failed (invalid format): {e}") from e

        # Step 2: Extract event metadata
        event_type = event_dict.get("event_type", "")
        correlation_id_str = event_dict.get("correlation_id")
        event_id_str = event_dict.get("event_id")

        if not correlation_id_str:
            raise ValueError("Missing correlation_id in event envelope")

        correlation_id = UUID(correlation_id_str)
        causation_id = UUID(event_id_str) if event_id_str else None

        logger.info(
            f"Processing event | event_type={event_type} | "
            f"correlation_id={correlation_id} | "
            f"topic={message.topic()}"
        )

        # Step 3: Deserialize payload using event helper
        try:
            event_type_enum, payload = (
                IntelligenceAdapterEventHelpers.deserialize_event(event_dict)
            )
        except KeyError as e:
            # Missing required fields in event payload
            logger.error(f"Missing field in event payload: {e}")
            raise ValueError(f"Payload deserialization failed (missing field): {e}") from e
        except (TypeError, ValueError) as e:
            # Type conversion or validation errors
            logger.error(f"Invalid event payload: {e}")
            raise ValueError(f"Payload deserialization failed (validation error): {e}") from e
        except Exception as e:
            # Intentionally broad: catch any deserialization error from external helper
            # and convert to ValueError for consistent handling
            logger.error(f"Failed to deserialize event payload: {e}")
            raise ValueError(f"Payload deserialization failed: {e}") from e

        # Step 4: Route based on event type
        if event_type_enum == EnumCodeAnalysisEventType.CODE_ANALYSIS_REQUESTED.value:
            # Cast payload to expected type (deserialize_event returns BaseModel)
            if not isinstance(payload, ModelCodeAnalysisRequestPayload):
                raise ValueError(
                    f"Expected ModelCodeAnalysisRequestPayload, got {type(payload).__name__}"
                )
            await self._handle_code_analysis_requested(
                payload=payload,
                correlation_id=correlation_id,
                causation_id=causation_id,
                start_time=start_time,
            )
        else:
            logger.warning(f"Unknown event type: {event_type_enum}, skipping")

    async def _handle_code_analysis_requested(
        self,
        payload: ModelCodeAnalysisRequestPayload,
        correlation_id: UUID,
        causation_id: UUID | None,
        start_time: float,
    ) -> None:
        """
        Handle CODE_ANALYSIS_REQUESTED event.

        This method:
        1. Converts event payload to ModelIntelligenceInput
        2. Calls analyze_code() to perform analysis
        3. Publishes CODE_ANALYSIS_COMPLETED on success
        4. Publishes CODE_ANALYSIS_FAILED on error

        Args:
            payload: Request payload from event
            correlation_id: Correlation ID for tracking
            causation_id: Event ID that caused this event
            start_time: Request start time for metrics
        """
        # Initialize input_data before try block to ensure it exists in exception handlers
        input_data: ModelIntelligenceInput | None = None

        try:
            # Step 1: Convert event payload to intelligence input
            input_data = ModelIntelligenceInput(
                operation_type=self._map_operation_type(payload.operation_type),
                correlation_id=correlation_id,
                source_path=payload.source_path,
                content=payload.content,
                language=payload.language,
                options=payload.options,
                metadata={
                    "project_id": payload.project_id,
                    "user_id": payload.user_id,
                    "event_driven": True,
                },
            )

            # Step 2: Perform analysis
            output = await self.analyze_code(input_data)

            # Step 3: Calculate processing time
            processing_time_ms = (time.perf_counter() - start_time) * 1000

            # Step 4: Publish completion or failure event
            if output.success:
                await self._publish_analysis_completed_event(
                    output=output,
                    correlation_id=correlation_id,
                    causation_id=causation_id,
                    processing_time_ms=processing_time_ms,
                )
                self.metrics["analysis_completed"] += 1
            else:
                await self._publish_analysis_failed_event(
                    input_data=input_data,
                    error_message=output.error_message or "Unknown error",
                    error_code=output.error_code or "INTERNAL_ERROR",
                    correlation_id=correlation_id,
                    causation_id=causation_id,
                    processing_time_ms=processing_time_ms,
                )
                self.metrics["analysis_failed"] += 1

            # Update metrics
            self.metrics["total_processing_time_ms"] += processing_time_ms
            processed_count = (
                self.metrics["analysis_completed"] + self.metrics["analysis_failed"]
            )
            if processed_count > 0:
                self.metrics["avg_processing_time_ms"] = (
                    self.metrics["total_processing_time_ms"] / processed_count
                )

        except (ConnectionError, TimeoutError) as e:
            # Network-related errors during analysis
            logger.error(
                f"Network error handling CODE_ANALYSIS_REQUESTED | "
                f"correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_analysis_failed_event(
                input_data=input_data,
                error_message=str(e),
                error_code="SERVICE_UNAVAILABLE",
                correlation_id=correlation_id,
                causation_id=causation_id,
                processing_time_ms=processing_time_ms,
            )
            self.metrics["analysis_failed"] += 1
            raise

        except Exception as e:
            # Intentionally broad: any error during analysis must publish a failure event
            # to maintain event-driven consistency (every request gets a response)
            logger.error(
                f"Error handling CODE_ANALYSIS_REQUESTED | "
                f"correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )

            # Publish failure event
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_analysis_failed_event(
                input_data=input_data,
                error_message=str(e),
                error_code="INTERNAL_ERROR",
                correlation_id=correlation_id,
                causation_id=causation_id,
                processing_time_ms=processing_time_ms,
            )
            self.metrics["analysis_failed"] += 1

            raise

    async def _publish_analysis_completed_event(
        self,
        output: ModelIntelligenceOutput,
        correlation_id: UUID,
        causation_id: UUID | None,
        processing_time_ms: float,
    ) -> None:
        """
        Publish CODE_ANALYSIS_COMPLETED event.

        Args:
            output: Analysis output with results
            correlation_id: Correlation ID from request
            causation_id: Event ID that caused this event
            processing_time_ms: Processing time in milliseconds
        """
        try:
            # Create completion payload
            payload = ModelCodeAnalysisCompletedPayload(
                source_path=output.metadata.get("source_path", "unknown"),
                quality_score=output.quality_score or 0.0,
                onex_compliance=output.onex_compliance or 0.0,
                issues_count=len(output.issues),
                recommendations_count=len(output.recommendations),
                processing_time_ms=processing_time_ms,
                operation_type=self._map_to_event_operation_type(output.operation_type),
                complexity_score=output.complexity_score,
                maintainability_score=output.metadata.get("maintainability_score"),
                results_summary=output.result_data or {},
                cache_hit=output.metrics.cache_hit if output.metrics else False,
            )

            # Create event envelope
            event = IntelligenceAdapterEventHelpers.create_analysis_completed_event(
                payload=payload,
                correlation_id=correlation_id,
                causation_id=causation_id,
            )

            # Publish to Kafka
            topic = IntelligenceAdapterEventHelpers.get_kafka_topic(
                EnumCodeAnalysisEventType.CODE_ANALYSIS_COMPLETED
            )

            if self.event_publisher is None:
                logger.warning(
                    f"Event publisher not initialized, skipping publish | "
                    f"correlation_id={correlation_id}"
                )
                return

            await self.event_publisher.publish(
                event_type=event["event_type"],
                payload=event["payload"],
                correlation_id=correlation_id,
                causation_id=causation_id,
                topic=topic,
            )

            logger.info(
                f"Published CODE_ANALYSIS_COMPLETED | "
                f"correlation_id={correlation_id} | "
                f"quality_score={payload.quality_score:.2f} | "
                f"processing_time={processing_time_ms:.2f}ms"
            )

        except (KafkaException, ConnectionError, TimeoutError) as e:
            # Kafka or network errors during event publishing
            logger.error(
                f"Failed to publish CODE_ANALYSIS_COMPLETED (publish error) | "
                f"correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )
        except Exception as e:
            # Intentionally broad: event publishing failures should not propagate
            # up the call stack; analysis was successful, just notification failed
            logger.error(
                f"Failed to publish CODE_ANALYSIS_COMPLETED | "
                f"correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )

    async def _publish_analysis_failed_event(
        self,
        input_data: ModelIntelligenceInput | None,
        error_message: str,
        error_code: str,
        correlation_id: UUID,
        causation_id: UUID | None,
        processing_time_ms: float,
    ) -> None:
        """
        Publish CODE_ANALYSIS_FAILED event.

        Args:
            input_data: Original input data (if available)
            error_message: Human-readable error description
            error_code: Machine-readable error code
            correlation_id: Correlation ID from request
            causation_id: Event ID that caused this event
            processing_time_ms: Processing time before failure
        """
        try:
            # Map error code to enum
            try:
                error_code_enum = EnumAnalysisErrorCode(error_code)
            except ValueError:
                error_code_enum = EnumAnalysisErrorCode.INTERNAL_ERROR

            # Safely extract source_path (handles both None input_data and None source_path)
            source_path: str = "unknown"
            if input_data is not None and input_data.source_path is not None:
                source_path = input_data.source_path

            # Create failure payload
            payload = ModelCodeAnalysisFailedPayload(
                operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
                source_path=source_path,
                error_message=error_message,
                error_code=error_code_enum,
                retry_allowed=True,
                processing_time_ms=processing_time_ms,
                error_details={"error": str(error_message)},
                suggested_action="Review error details and retry with valid input",
            )

            # Create event envelope
            event = IntelligenceAdapterEventHelpers.create_analysis_failed_event(
                payload=payload,
                correlation_id=correlation_id,
                causation_id=causation_id,
            )

            # Publish to Kafka
            topic = IntelligenceAdapterEventHelpers.get_kafka_topic(
                EnumCodeAnalysisEventType.CODE_ANALYSIS_FAILED
            )

            if self.event_publisher is None:
                logger.warning(
                    f"Event publisher not initialized, skipping publish | "
                    f"correlation_id={correlation_id}"
                )
                return

            await self.event_publisher.publish(
                event_type=event["event_type"],
                payload=event["payload"],
                correlation_id=correlation_id,
                causation_id=causation_id,
                topic=topic,
            )

            logger.info(
                f"Published CODE_ANALYSIS_FAILED | "
                f"correlation_id={correlation_id} | "
                f"error_code={error_code_enum.value} | "
                f"processing_time={processing_time_ms:.2f}ms"
            )

        except (KafkaException, ConnectionError, TimeoutError) as e:
            # Kafka or network errors during event publishing
            logger.error(
                f"Failed to publish CODE_ANALYSIS_FAILED (publish error) | "
                f"correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )
        except Exception as e:
            # Intentionally broad: event publishing failures should not propagate;
            # the analysis already failed, we just can't notify about it
            logger.error(
                f"Failed to publish CODE_ANALYSIS_FAILED | "
                f"correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )

    async def _route_to_dlq(
        self, message: Any, error: str | Exception, error_type: str | None = None
    ) -> None:
        """
        Route failed message to Dead Letter Queue.

        This method publishes failed messages to a DLQ topic for manual inspection
        and potential reprocessing. The DLQ topic is the original topic with a `.dlq`
        suffix (e.g., `dev.archon-intelligence.intelligence.code-analysis-requested.v1.dlq`).

        The DLQ payload includes:
        - Original message content (decoded if possible)
        - Error details and stack trace
        - Original message metadata (topic, partition, offset, timestamp)
        - Processing context (node_id, consumer_group, attempt time)

        Args:
            message: Original Kafka message that failed processing
            error: Error description or exception explaining why processing failed
            error_type: Optional explicit error type name. If not provided, will be
                        extracted from exception type or default to "ProcessingError".

        Note:
            If event_publisher is not initialized, the method logs a warning
            and only updates metrics. This allows graceful degradation when
            Kafka infrastructure is unavailable.
        """
        import json
        import traceback
        from datetime import datetime

        original_topic = message.topic()
        dlq_topic = f"{original_topic}.dlq"

        try:
            # Decode original message content
            try:
                original_content = message.value().decode("utf-8")
                try:
                    # Try to parse as JSON for structured storage
                    original_payload = json.loads(original_content)
                except json.JSONDecodeError:
                    original_payload = {"raw_content": original_content}
            except UnicodeDecodeError as decode_error:
                # Message content is not valid UTF-8, store as hex
                original_payload = {
                    "raw_bytes": message.value().hex() if message.value() else None,
                    "decode_error": str(decode_error),
                }
            except (AttributeError, TypeError) as decode_error:
                # message.value() returned None or unexpected type
                original_payload = {
                    "raw_bytes": None,
                    "decode_error": str(decode_error),
                }

            # Extract message timestamp if available
            message_timestamp = None
            if hasattr(message, "timestamp") and message.timestamp():
                ts_type, ts_value = message.timestamp()
                if ts_value:
                    message_timestamp = datetime.fromtimestamp(
                        ts_value / 1000, tz=UTC
                    ).isoformat()

            # Determine error type: use explicit type, extract from exception, or default
            resolved_error_type = error_type or (
                type(error).__name__ if isinstance(error, Exception) else "ProcessingError"
            )
            error_message = str(error)

            # Build DLQ payload with full context
            dlq_payload = {
                "original_message": original_payload,
                "error": {
                    "message": error_message,
                    "traceback": traceback.format_exc(),
                    "error_type": resolved_error_type,
                },
                "original_metadata": {
                    "topic": original_topic,
                    "partition": message.partition(),
                    "offset": message.offset(),
                    "timestamp": message_timestamp,
                    "key": message.key().decode("utf-8") if message.key() else None,
                },
                "processing_context": {
                    "node_id": str(self.node_id),
                    "consumer_group": self.consumer_config.group_id,
                    "routed_at": datetime.now(UTC).isoformat(),
                    "service_url": self.service_url,
                },
            }

            # Check if event_publisher is available
            if self.event_publisher is None:
                logger.warning(
                    f"Event publisher not initialized, cannot route to DLQ | "
                    f"topic={original_topic} | partition={message.partition()} | "
                    f"offset={message.offset()} | error={error}"
                )
                self.metrics["dlq_routed"] += 1
                return

            # Publish to DLQ topic
            # Extract correlation_id from original message if available
            correlation_id = None
            if isinstance(original_payload, dict):
                correlation_id_str = original_payload.get("correlation_id")
                if correlation_id_str:
                    try:
                        correlation_id = UUID(correlation_id_str)
                    except (ValueError, TypeError):
                        correlation_id = uuid4()
                else:
                    correlation_id = uuid4()
            else:
                correlation_id = uuid4()

            await self.event_publisher.publish(
                event_type="CODE_ANALYSIS_DLQ",
                payload=dlq_payload,
                correlation_id=correlation_id,
                topic=dlq_topic,
            )

            self.metrics["dlq_routed"] += 1

            logger.warning(
                f"Routed message to DLQ | "
                f"dlq_topic={dlq_topic} | "
                f"original_topic={original_topic} | "
                f"partition={message.partition()} | "
                f"offset={message.offset()} | "
                f"correlation_id={correlation_id} | "
                f"error={error}"
            )

        except (KafkaException, ConnectionError, TimeoutError) as e:
            # Kafka or network errors during DLQ routing
            self.metrics["dlq_routed"] += 1  # Still count the attempt
            logger.error(
                f"Failed to route message to DLQ (network/Kafka error) | "
                f"dlq_topic={dlq_topic} | "
                f"original_topic={original_topic} | "
                f"partition={message.partition()} | "
                f"offset={message.offset()} | "
                f"routing_error={e}",
                exc_info=True,
            )
        except Exception as e:
            # Intentionally broad: DLQ routing must never raise and must never
            # block the main processing loop. Any error is logged but swallowed.
            self.metrics["dlq_routed"] += 1  # Still count the attempt
            logger.error(
                f"Failed to route message to DLQ | "
                f"dlq_topic={dlq_topic} | "
                f"original_topic={original_topic} | "
                f"partition={message.partition()} | "
                f"offset={message.offset()} | "
                f"routing_error={e}",
                exc_info=True,
            )

    # =========================================================================
    # ONEX Effect Pattern Methods
    # =========================================================================

    async def process(self, operation_data: dict[str, Any]) -> Any:
        """
        Process operation (ONEX Effect pattern method).

        This is a generic Effect pattern method that can be mocked in tests
        to test higher-level workflows without actually calling the intelligence service.

        Args:
            operation_data: Dictionary containing operation details

        Returns:
            Result object with operation outcome

        Note: This is primarily for testing and ONEX pattern compliance.
        Production code should use analyze_code() directly.
        """
        # This is a stub method for ONEX Effect pattern compliance
        # Tests can mock this method to test higher-level logic
        # In production, code calls analyze_code() directly
        from types import SimpleNamespace

        return SimpleNamespace(
            result=operation_data,
            processing_time_ms=0.0,
        )

    # =========================================================================
    # Core Analysis Operation (Extended from Agent 1's work)
    # =========================================================================

    async def analyze_code(
        self, input_data: ModelIntelligenceInput
    ) -> ModelIntelligenceOutput:
        """
        Analyze code using Archon intelligence services.

        This method routes intelligence operations to appropriate backend services:
        - Quality Assessment: /assess/code endpoint
        - Document Quality: /assess/document endpoint
        - Pattern Extraction: /patterns/extract endpoint
        - Compliance Checking: /compliance/check endpoint

        Args:
            input_data: Intelligence operation input with correlation tracking

        Returns:
            ModelIntelligenceOutput with analysis results

        Raises:
            ModelOnexError: If node not initialized or analysis fails
        """
        from datetime import datetime

        from omnibase_core.enums.enum_core_error_code import EnumCoreErrorCode
        from omnibase_core.models.errors.model_onex_error import ModelOnexError

        # Check initialization
        if self._config is None or self._client is None:
            raise ModelOnexError(
                error_code=EnumCoreErrorCode.INITIALIZATION_FAILED,
                message="Intelligence Adapter Effect Node not initialized. Call initialize() first.",
            )

        # Type-safe increment of total_analyses
        total = self._stats.get("total_analyses", 0)
        self._stats["total_analyses"] = (int(total) if total is not None else 0) + 1

        # Retry logic configuration
        max_retries = self._config.max_retries if self._config else 3
        retry_count = 0
        last_error = None

        # Extract content and source_path with safe defaults
        content: str = input_data.content or ""
        source_path: str = input_data.source_path or "unknown"

        while retry_count <= max_retries:
            try:
                logger.info(
                    f"Analyzing code | operation={input_data.operation_type} | "
                    f"correlation_id={input_data.correlation_id} | "
                    f"attempt={retry_count + 1}/{max_retries + 1}"
                )

                # Track processing time
                operation_start = time.perf_counter()

                # Route to appropriate backend service based on operation type
                if input_data.operation_type in [
                    "assess_code_quality",
                    "check_architectural_compliance",
                ]:
                    # Quality assessment endpoint
                    quality_request = ModelQualityAssessmentRequest(
                        content=content,
                        source_path=source_path,
                        language=input_data.language,
                        include_recommendations=True,
                        min_quality_threshold=(
                            input_data.options.get("min_quality_threshold", 0.7)
                            if input_data.options
                            else 0.7
                        ),
                    )
                    quality_response = await self._client.assess_code_quality(
                        quality_request
                    )
                    result_data = self._transform_quality_response(quality_response)

                elif input_data.operation_type == "analyze_performance":
                    # Performance baseline endpoint
                    perf_request = ModelPerformanceAnalysisRequest(
                        operation_name=source_path,
                        code_content=content,
                        context=input_data.options,
                        include_opportunities=True,
                        target_percentile=(
                            input_data.options.get("target_percentile", 95)
                            if input_data.options
                            else 95
                        ),
                    )
                    perf_response = await self._client.analyze_performance(perf_request)
                    result_data = self._transform_performance_response(perf_response)

                elif input_data.operation_type == "get_quality_patterns":
                    # Pattern detection endpoint
                    pattern_request = ModelPatternDetectionRequest(
                        content=content,
                        source_path=source_path,
                        pattern_categories=(
                            input_data.options.get("pattern_categories")
                            if input_data.options
                            else None
                        ),
                        min_confidence=(
                            input_data.options.get("min_confidence", 0.7)
                            if input_data.options
                            else 0.7
                        ),
                        include_recommendations=True,
                    )
                    pattern_response = await self._client.detect_patterns(pattern_request)
                    result_data = self._transform_pattern_response(pattern_response)

                else:
                    # Default to quality assessment for unknown operation types
                    logger.warning(
                        f"Unknown operation type '{input_data.operation_type}', "
                        f"defaulting to quality assessment"
                    )
                    default_request = ModelQualityAssessmentRequest(
                        content=content,
                        source_path=source_path,
                        language=input_data.language,
                        include_recommendations=True,
                        min_quality_threshold=0.7,
                    )
                    default_response = await self._client.assess_code_quality(
                        default_request
                    )
                    result_data = self._transform_quality_response(default_response)

                # Calculate actual processing time
                processing_time_ms = int((time.perf_counter() - operation_start) * 1000)

                # Success - clear error and break out of retry loop
                last_error = None
                break

            except (ConnectionError, TimeoutError, OSError) as process_error:
                # Transient network errors - these are retryable
                last_error = process_error
                retry_count += 1

                if retry_count <= max_retries:
                    retry_delay = (
                        self._config.retry_delay_ms / 1000 if self._config else 1.0
                    )
                    logger.warning(
                        f"Process failed with transient error (attempt {retry_count}/{max_retries + 1}), "
                        f"retrying in {retry_delay}s: {process_error}"
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(
                        f"Process failed after {retry_count} attempts (network error): {process_error}"
                    )
                    break

            except ValueError as process_error:
                # Validation errors - not retryable, fail immediately
                last_error = process_error
                logger.error(
                    f"Process failed with validation error (not retrying): {process_error}"
                )
                break

            except Exception as process_error:
                # Intentionally broad: catch any unexpected error for the retry loop.
                # Unknown errors are treated as potentially transient and retried.
                last_error = process_error
                retry_count += 1

                if retry_count <= max_retries:
                    retry_delay = (
                        self._config.retry_delay_ms / 1000 if self._config else 1.0
                    )
                    logger.warning(
                        f"Process failed (attempt {retry_count}/{max_retries + 1}), "
                        f"retrying in {retry_delay}s: {process_error}"
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(
                        f"Process failed after {retry_count} attempts: {process_error}"
                    )
                    break

        # Check if we exhausted retries
        if last_error is not None:
            # Track failure (type-safe)
            failed = self._stats.get("failed_analyses", 0)
            self._stats["failed_analyses"] = (int(failed) if failed is not None else 0) + 1

            # Update success rate (type-safe)
            total_analyses = self._stats.get("total_analyses", 0)
            if total_analyses and int(total_analyses) > 0:
                successful = self._stats.get("successful_analyses", 0)
                self._stats["success_rate"] = (
                    float(successful or 0) / float(total_analyses)
                )

            logger.error(
                f"Intelligence analysis failed | "
                f"operation={input_data.operation_type} | "
                f"correlation_id={input_data.correlation_id} | "
                f"error={last_error}",
                exc_info=True,
            )

            raise ModelOnexError(
                error_code=EnumCoreErrorCode.OPERATION_FAILED,
                message=f"Intelligence analysis failed: {last_error!s}",
            ) from last_error

        # Build output from process result
        output = ModelIntelligenceOutput(
            success=result_data.get("success", True),
            operation_type=input_data.operation_type,
            correlation_id=input_data.correlation_id,
            processing_time_ms=processing_time_ms,
            quality_score=result_data.get("quality_score", 0.0),
            onex_compliance=result_data.get("onex_compliance", 0.0),
            complexity_score=result_data.get("complexity_score"),
            issues=result_data.get("issues", []),
            recommendations=result_data.get("recommendations", []),
            patterns=result_data.get("patterns"),
            result_data=result_data.get("result_data"),
            metadata={
                "source_path": input_data.source_path,
            },
        )

        # Update statistics for successful analysis (type-safe)
        if output.success:
            successful = self._stats.get("successful_analyses", 0)
            self._stats["successful_analyses"] = (
                int(successful) if successful is not None else 0
            ) + 1
            if output.quality_score is not None:
                total_quality = self._stats.get("total_quality_score", 0.0)
                new_total_quality = (
                    float(total_quality) if total_quality is not None else 0.0
                ) + output.quality_score
                self._stats["total_quality_score"] = new_total_quality
                successful_count = self._stats.get("successful_analyses", 1)
                self._stats["avg_quality_score"] = new_total_quality / float(
                    successful_count if successful_count else 1
                )
        else:
            failed = self._stats.get("failed_analyses", 0)
            self._stats["failed_analyses"] = (
                int(failed) if failed is not None else 0
            ) + 1

        # Update success rate (type-safe)
        total_analyses = self._stats.get("total_analyses", 0)
        if total_analyses and int(total_analyses) > 0:
            successful = self._stats.get("successful_analyses", 0)
            self._stats["success_rate"] = (
                float(successful or 0) / float(total_analyses)
            )

        # Update last analysis time
        self._stats["last_analysis_time"] = datetime.now(UTC).isoformat()

        return output

    # =========================================================================
    # Transformation Methods (ONEX-compliant)
    # =========================================================================

    def _convert_to_effect_input(self, input_data: ModelIntelligenceInput) -> Any:
        """
        Convert ModelIntelligenceInput to Effect input format.

        This is a utility method for ONEX Effect pattern compliance, converting
        intelligence input to a generic effect operation format.

        Args:
            input_data: Intelligence operation input

        Returns:
            Object with effect input structure:
            - operation_id: Correlation ID for tracking
            - operation_data: Input data and metadata
            - retry_enabled: Whether retries are enabled
            - circuit_breaker_enabled: Whether circuit breaker is active
        """
        from types import SimpleNamespace

        return SimpleNamespace(
            operation_id=input_data.correlation_id,
            operation_data={
                "operation_type": input_data.operation_type,
                "content": input_data.content,
                "source_path": input_data.source_path,
                "language": input_data.language,
                "options": input_data.options or {},
                "metadata": input_data.metadata or {},
            },
            retry_enabled=self._config.max_retries > 0 if self._config else True,
            circuit_breaker_enabled=(
                self._config.circuit_breaker_enabled if self._config else True
            ),
        )

    def _transform_quality_response(self, response: Any) -> dict[str, Any]:
        """
        Transform quality assessment response to standard format.

        Args:
            response: Quality assessment response from intelligence service

        Returns:
            Dictionary with standardized quality data:
            - success: Operation success status
            - quality_score: Overall quality score (0.0-1.0)
            - onex_compliance: ONEX compliance score (0.0-1.0)
            - complexity_score: Complexity score
            - issues: List of identified issues
            - recommendations: List of recommendations
            - patterns: Detected patterns
            - result_data: Additional result metadata
        """
        issues = []
        recommendations = []

        # Extract issues from violations
        if hasattr(response, "onex_compliance") and response.onex_compliance:
            if hasattr(response.onex_compliance, "violations"):
                issues.extend(response.onex_compliance.violations)
            if hasattr(response.onex_compliance, "recommendations"):
                recommendations.extend(response.onex_compliance.recommendations)

        return {
            "success": True,
            "quality_score": response.quality_score,
            "onex_compliance": (
                response.onex_compliance.score
                if hasattr(response, "onex_compliance") and response.onex_compliance
                else 0.0
            ),
            "complexity_score": (
                response.maintainability.complexity_score
                if hasattr(response, "maintainability") and response.maintainability
                else 0.0
            ),
            "issues": issues,
            "recommendations": recommendations,
            "patterns": [],
            "result_data": {
                "architectural_era": (
                    response.architectural_era
                    if hasattr(response, "architectural_era")
                    else None
                ),
                "temporal_relevance": (
                    response.temporal_relevance
                    if hasattr(response, "temporal_relevance")
                    else None
                ),
            },
        }

    def _transform_performance_response(self, response: Any) -> dict[str, Any]:
        """
        Transform performance analysis response to standard format.

        Args:
            response: Performance analysis response from intelligence service

        Returns:
            Dictionary with standardized performance data:
            - success: Operation success status
            - complexity_score: Complexity estimate
            - recommendations: Performance improvement recommendations
            - result_data: Additional performance metrics
        """
        recommendations = []

        # Extract optimization opportunities
        if hasattr(response, "optimization_opportunities"):
            for opportunity in response.optimization_opportunities:
                if hasattr(opportunity, "title") and hasattr(
                    opportunity, "description"
                ):
                    recommendations.append(
                        f"{opportunity.title}: {opportunity.description}"
                    )

        complexity_score = 0.0
        if (
            hasattr(response, "baseline_metrics")
            and response.baseline_metrics
            and hasattr(response.baseline_metrics, "complexity_estimate")
        ):
            complexity_score = response.baseline_metrics.complexity_estimate

        return {
            "success": True,
            "complexity_score": complexity_score,
            "recommendations": recommendations,
            "result_data": {
                "baseline_metrics": (
                    response.baseline_metrics.model_dump()
                    if hasattr(response, "baseline_metrics")
                    and response.baseline_metrics
                    else {}
                ),
                "optimization_opportunities": (
                    [
                        opportunity.model_dump()
                        for opportunity in response.optimization_opportunities
                    ]
                    if hasattr(response, "optimization_opportunities")
                    else []
                ),
                "total_opportunities": (
                    response.total_opportunities
                    if hasattr(response, "total_opportunities")
                    else 0
                ),
                "estimated_improvement": (
                    response.estimated_total_improvement
                    if hasattr(response, "estimated_total_improvement")
                    else 0.0
                ),
            },
        }

    def _transform_pattern_response(self, response: Any) -> dict[str, Any]:
        """
        Transform pattern detection response to standard format.

        Args:
            response: Pattern detection response from intelligence service

        Returns:
            Dictionary with standardized pattern data:
            - success: Operation success status
            - onex_compliance: ONEX compliance score
            - patterns: Detected patterns
            - issues: Anti-patterns and issues
            - recommendations: Pattern-based recommendations
            - result_data: Additional pattern metadata
        """
        patterns = []
        issues = []
        recommendations = []

        # Extract detected patterns
        if hasattr(response, "detected_patterns"):
            patterns = [pattern.model_dump() for pattern in response.detected_patterns]

        # Extract anti-patterns as issues
        if hasattr(response, "anti_patterns"):
            for anti_pattern in response.anti_patterns:
                if hasattr(anti_pattern, "pattern_type") and hasattr(
                    anti_pattern, "description"
                ):
                    issues.append(
                        f"{anti_pattern.pattern_type}: {anti_pattern.description}"
                    )

        # Extract recommendations
        if hasattr(response, "recommendations"):
            recommendations = list(response.recommendations)

        # Extract ONEX compliance
        onex_compliance = 0.0
        if (
            hasattr(response, "architectural_compliance")
            and response.architectural_compliance
            and hasattr(response.architectural_compliance, "onex_compliance")
        ):
            onex_compliance = response.architectural_compliance.onex_compliance

        return {
            "success": True,
            "onex_compliance": onex_compliance,
            "patterns": patterns,
            "issues": issues,
            "recommendations": recommendations,
            "result_data": {
                "analysis_summary": (
                    response.analysis_summary
                    if hasattr(response, "analysis_summary")
                    else ""
                ),
                "confidence_scores": (
                    response.confidence_scores
                    if hasattr(response, "confidence_scores")
                    else {}
                ),
            },
        }

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _map_operation_type(self, event_op_type: EnumAnalysisOperationType) -> str:
        """
        Map event operation type to intelligence operation type.

        Args:
            event_op_type: Event operation type enum

        Returns:
            Intelligence operation type string
        """
        mapping = {
            EnumAnalysisOperationType.QUALITY_ASSESSMENT: "assess_code_quality",
            EnumAnalysisOperationType.ONEX_COMPLIANCE: "check_architectural_compliance",
            EnumAnalysisOperationType.PATTERN_EXTRACTION: "get_quality_patterns",
            EnumAnalysisOperationType.ARCHITECTURAL_COMPLIANCE: "check_architectural_compliance",
            EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS: "assess_code_quality",
        }
        return mapping.get(event_op_type, "assess_code_quality")

    def _map_to_event_operation_type(
        self, operation_type: str
    ) -> EnumAnalysisOperationType:
        """
        Map intelligence operation type to event operation type.

        Args:
            operation_type: Intelligence operation type string

        Returns:
            Event operation type enum
        """
        mapping = {
            "assess_code_quality": EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
            "check_architectural_compliance": EnumAnalysisOperationType.ARCHITECTURAL_COMPLIANCE,
            "get_quality_patterns": EnumAnalysisOperationType.PATTERN_EXTRACTION,
        }
        return mapping.get(
            operation_type, EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS
        )

    def get_analysis_stats(self) -> dict[str, Any]:
        """
        Get current analysis statistics (ONEX-compliant).

        Returns:
            Dictionary with analysis statistics including:
            - node_id: Unique node identifier
            - total_analyses: Total analysis operations
            - successful_analyses: Successfully completed analyses
            - failed_analyses: Failed analysis operations
            - avg_quality_score: Average quality score across analyses
            - success_rate: Success rate (0.0 to 1.0)
            - last_analysis_time: Timestamp of last analysis
        """
        return {
            "node_id": str(self.node_id),
            **self._stats,
        }

    def get_metrics(self) -> dict[str, Any]:
        """
        Get current operation metrics.

        Returns:
            Dictionary with metrics including:
            - events_consumed: Total events consumed from Kafka
            - events_processed: Successfully processed events
            - events_failed: Failed event processing
            - analysis_completed: Successful analyses
            - analysis_failed: Failed analyses
            - dlq_routed: Messages routed to DLQ
            - avg_processing_time_ms: Average processing time
        """
        return {
            **self.metrics,
            "is_running": self.is_running,
            "consumer_group": self.consumer_config.group_id,
            "topics_subscribed": self.consumer_config.topics,
        }
