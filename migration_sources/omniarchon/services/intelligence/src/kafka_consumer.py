"""
Kafka Consumer for Intelligence Service

Consumes codegen events from Kafka and routes them to appropriate handlers.
Implements async event processing with error handling and graceful shutdown.

Created: 2025-10-15
Purpose: Wire event handlers to Kafka consumer for end-to-end event flow
"""

import asyncio
import json
import logging
import os

# Add project root to path for correlation ID utilities
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from confluent_kafka import Consumer, KafkaError, Message
from prometheus_client import Counter, Gauge, Histogram
from src.archon_services.langextract.codegen_langextract_service import (
    CodegenLangExtractService,
)
from src.archon_services.pattern_learning.codegen_pattern_service import (
    CodegenPatternService,
)

# Service imports
from src.archon_services.quality.codegen_quality_service import CodegenQualityService
from src.archon_services.quality.comprehensive_onex_scorer import (
    ComprehensiveONEXScorer,
)

# Event publisher for DLQ
from src.events.kafka_publisher import KafkaEventPublisher

# Phase 3: Advanced Analytics handlers
from src.handlers.autonomous_learning_handler import AutonomousLearningHandler

# Phase 4: Bridge & Utility handlers
from src.handlers.bridge_intelligence_handler import BridgeIntelligenceHandler
from src.handlers.codegen_analysis_handler import CodegenAnalysisHandler
from src.handlers.codegen_mixin_handler import CodegenMixinHandler
from src.handlers.codegen_pattern_handler import CodegenPatternHandler

# Handler imports
from src.handlers.codegen_validation_handler import CodegenValidationHandler
from src.handlers.custom_quality_rules_handler import CustomQualityRulesHandler
from src.handlers.document_indexing_handler import DocumentIndexingHandler
from src.handlers.document_processing_handler import DocumentProcessingHandler
from src.handlers.entity_extraction_handler import EntityExtractionHandler

# Phase 2: Document & Pattern handlers
from src.handlers.freshness_handler import FreshnessHandler
from src.handlers.intelligence_adapter_handler import IntelligenceAdapterHandler
from src.handlers.pattern_analytics_handler import PatternAnalyticsHandler
from src.handlers.pattern_learning_handler import PatternLearningHandler
from src.handlers.pattern_traceability_handler import PatternTraceabilityHandler
from src.handlers.performance_analytics_handler import PerformanceAnalyticsHandler
from src.handlers.performance_handler import PerformanceHandler

# Phase 1: Core Intelligence handlers
from src.handlers.quality_assessment_handler import QualityAssessmentHandler
from src.handlers.quality_trends_handler import QualityTrendsHandler
from src.handlers.repository_crawler_handler import RepositoryCrawlerHandler
from src.handlers.search_handler import SearchHandler
from src.handlers.system_utilities_handler import SystemUtilitiesHandler

# Phase 5: Tree + Stamping handlers
from src.handlers.tree_stamping_handler import TreeStampingHandler

# Centralized configuration
from config import settings

project_root = Path(__file__).resolve().parents[3]  # Go up to project root
sys.path.insert(0, str(project_root))

# Import correlation ID utilities for pipeline traceability
try:
    from scripts.lib.correlation_id import (
        extract_correlation_id,
        is_debug_mode,
        log_debug_payload,
        log_pipeline_event,
    )
except ImportError:
    logger.warning("Could not import correlation_id utilities, using fallback logging")

    # Fallback implementations
    def extract_correlation_id(event_data, default=None):
        return event_data.get("correlation_id", default or "unknown")

    def log_pipeline_event(logger_inst, level, **kwargs):
        logger_inst.log(level, str(kwargs))

    def log_debug_payload(logger_inst, corr_id, stage, payload):
        pass

    def is_debug_mode():
        return os.getenv("PIPELINE_DEBUG", "false").lower() == "true"


logger = logging.getLogger(__name__)

# Prometheus metrics for event processing failures
event_processing_failures = Counter(
    "kafka_event_processing_failures_total",
    "Total event processing failures",
    ["event_type", "error_type"],
)

event_processing_total = Counter(
    "kafka_event_processing_total", "Total events processed", ["event_type", "status"]
)

event_processing_duration = Histogram(
    "kafka_event_processing_duration_seconds",
    "Event processing duration",
    ["event_type"],
)

dlq_routed_total = Counter(
    "kafka_dlq_routed_total",
    "Total messages routed to DLQ",
    ["original_topic", "error_type"],
)

consumer_in_flight_events = Gauge(
    "kafka_consumer_in_flight_events", "Current number of events being processed"
)

consumer_backpressure_wait_seconds = Histogram(
    "kafka_consumer_backpressure_wait_seconds",
    "Time spent waiting for backpressure relief",
)


class IntelligenceKafkaConsumer:
    """
    Kafka consumer for intelligence service codegen events.

    Subscribes to codegen request topics and routes events to registered handlers.
    Provides async event processing with error handling and graceful shutdown.

    Features:
    - Handler registry pattern for dynamic handler registration
    - Async event processing with asyncio
    - Backpressure control with configurable max in-flight events
    - Graceful shutdown with offset commit
    - Error handling and retry logic
    - Metrics tracking (events processed, errors, latency, backpressure)
    - Health checking

    Backpressure:
    - Uses asyncio.Semaphore to limit concurrent event processing
    - Configurable via max_in_flight parameter (default: 100)
    - Prevents memory exhaustion under high load
    - Tracks backpressure metrics (wait time, frequency, percentage)

    Usage:
        from config import settings
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", settings.kafka_bootstrap_servers),
            topics=["omninode.codegen.request.validate.v1"],
            max_in_flight=100
        )
        await consumer.initialize()
        await consumer.start()
    """

    def __init__(
        self,
        bootstrap_servers: str,
        topics: List[str],
        consumer_group: str = "archon-intelligence",
        auto_offset_reset: str = "earliest",
        enable_auto_commit: bool = True,
        max_poll_records: int = 500,
        session_timeout_ms: int = 30000,
        max_in_flight: int = 100,
    ):
        """
        Initialize Kafka consumer.

        Args:
            bootstrap_servers: Kafka bootstrap servers (comma-separated)
            topics: List of topics to subscribe to
            consumer_group: Consumer group ID
            auto_offset_reset: Auto offset reset strategy (earliest, latest)
            enable_auto_commit: Enable automatic offset commits
            max_poll_records: Maximum records per poll
            session_timeout_ms: Session timeout in milliseconds
            max_in_flight: Maximum concurrent events being processed (backpressure)
        """
        self.bootstrap_servers = bootstrap_servers
        self.topics = topics
        self.consumer_group = consumer_group
        self.auto_offset_reset = auto_offset_reset
        self.enable_auto_commit = enable_auto_commit
        self.max_poll_records = max_poll_records
        self.session_timeout_ms = session_timeout_ms
        self.max_in_flight = max_in_flight

        # Consumer and state
        self.consumer: Optional[Consumer] = None
        self.handlers: List[Any] = []
        self.running = False
        self._consumer_task: Optional[asyncio.Task] = None

        # DLQ publisher (initialized lazily)
        self._dlq_publisher: Optional[KafkaEventPublisher] = None

        # Backpressure control
        self._semaphore = asyncio.Semaphore(max_in_flight)
        self._current_in_flight = 0
        self._in_flight_lock = asyncio.Lock()

        # Metrics
        self.metrics = {
            "events_processed": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
            "last_event_timestamp": None,
            "consumer_started_at": None,
            # Backpressure metrics
            "max_in_flight_reached": 0,
            "total_backpressure_wait_time_ms": 0.0,
            "current_in_flight": 0,
            "max_concurrent_events": 0,
            # DLQ metrics
            "dlq_routed": 0,
        }

    async def initialize(self) -> None:
        """
        Initialize consumer and register handlers.

        Creates Kafka consumer with configuration, initializes service clients,
        and registers event handlers.

        Raises:
            RuntimeError: If initialization fails
        """
        try:
            logger.info(
                f"Initializing Kafka consumer for intelligence service | "
                f"bootstrap_servers={self.bootstrap_servers} | topics={self.topics} | "
                f"consumer_group={self.consumer_group}"
            )

            # Create Kafka consumer
            consumer_config = {
                "bootstrap.servers": self.bootstrap_servers,
                "group.id": self.consumer_group,
                "auto.offset.reset": self.auto_offset_reset,
                "enable.auto.commit": self.enable_auto_commit,
                "session.timeout.ms": self.session_timeout_ms,
                # Performance tuning
                "fetch.min.bytes": 1,
                "fetch.wait.max.ms": 500,
                # Error handling
                "api.version.request": True,
                "log.connection.close": False,
            }

            self.consumer = Consumer(consumer_config)

            # Subscribe to topics
            self.consumer.subscribe(self.topics)
            logger.info(f"Subscribed to topics: {self.topics}")

            # Initialize DLQ publisher
            self._dlq_publisher = KafkaEventPublisher()
            await self._dlq_publisher.initialize()
            logger.info("DLQ publisher initialized")

            # Initialize service clients (lazy initialization for httpx clients)
            await self._initialize_service_clients()

            # Register handlers
            await self._register_handlers()

            logger.info(
                f"Kafka consumer initialized successfully | handlers_registered={len(self.handlers)}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize Kafka consumer: {e}", exc_info=True)
            raise RuntimeError(f"Failed to initialize Kafka consumer: {str(e)}") from e

    async def _initialize_service_clients(self) -> None:
        """
        Initialize intelligence service clients.

        Creates instances of:
        - ComprehensiveONEXScorer for quality validation
        - CodegenLangExtractService for semantic analysis
        - CodegenPatternService for pattern matching

        Note: Service clients are initialized here to avoid circular imports
        and ensure proper async initialization.
        """
        try:
            # Initialize quality scorer (no async required)
            self.quality_scorer = ComprehensiveONEXScorer()
            logger.debug("Initialized ComprehensiveONEXScorer")

            # Initialize service wrappers
            # Note: LangExtract service uses httpx client internally
            # which is initialized lazily on first request
            self.langextract_service = CodegenLangExtractService(
                langextract_client=None
            )
            # Pattern service uses direct Qdrant and Ollama connections
            self.pattern_service = CodegenPatternService()

            logger.debug("Initialized service clients for handlers")

        except Exception as e:
            logger.error(f"Failed to initialize service clients: {e}", exc_info=True)
            raise

    async def _register_handlers(self) -> None:
        """
        Register event handlers with consumer.

        Creates and registers:
        - CodegenValidationHandler: Validates generated code quality
        - CodegenAnalysisHandler: Analyzes code semantics via LangExtract
        - CodegenPatternHandler: Matches patterns and recommends best practices
        - CodegenMixinHandler: Recommends ONEX mixins for code generation

        Handlers are stored in self.handlers list and routed based on event type.
        """
        try:
            # Create quality service wrapper for validation handler
            quality_service = CodegenQualityService(quality_scorer=self.quality_scorer)

            # Register validation handler (MVP Day 1)
            validation_handler = CodegenValidationHandler(quality_service)
            self.handlers.append(validation_handler)
            logger.info(f"Registered {validation_handler.get_handler_name()}")

            # Register analysis handler (MVP Day 2)
            analysis_handler = CodegenAnalysisHandler(self.langextract_service)
            self.handlers.append(analysis_handler)
            logger.info(f"Registered {analysis_handler.get_handler_name()}")

            # Register pattern handler (MVP Day 2)
            pattern_handler = CodegenPatternHandler(self.pattern_service)
            self.handlers.append(pattern_handler)
            logger.info(f"Registered {pattern_handler.get_handler_name()}")

            # Register mixin handler (MVP Day 2)
            mixin_handler = CodegenMixinHandler(self.pattern_service)
            self.handlers.append(mixin_handler)
            logger.info(f"Registered {mixin_handler.get_handler_name()}")

            # Register Intelligence Adapter handler (2025-10-21)
            intelligence_adapter_handler = IntelligenceAdapterHandler(
                quality_scorer=self.quality_scorer
            )
            self.handlers.append(intelligence_adapter_handler)
            logger.info("Registered IntelligenceAdapterHandler")

            # Register Document Indexing handler (2025-10-22)
            document_indexing_handler = DocumentIndexingHandler()
            self.handlers.append(document_indexing_handler)
            logger.info("Registered DocumentIndexingHandler")

            # Register Repository Crawler handler (2025-10-22)
            repository_crawler_handler = RepositoryCrawlerHandler()
            self.handlers.append(repository_crawler_handler)
            logger.info("Registered RepositoryCrawlerHandler")

            # Register Search handler (2025-10-22)
            search_handler = SearchHandler()
            self.handlers.append(search_handler)
            logger.info("Registered SearchHandler")

            # ========== Phase 1: Core Intelligence Handlers ==========
            # Quality Assessment handler (Phase 1 - 2025-10-22)
            quality_assessment_handler = QualityAssessmentHandler()
            self.handlers.append(quality_assessment_handler)
            logger.info("Registered QualityAssessmentHandler")

            # Entity Extraction handler (Phase 1 - 2025-10-22)
            entity_extraction_handler = EntityExtractionHandler()
            self.handlers.append(entity_extraction_handler)
            logger.info("Registered EntityExtractionHandler")

            # Performance handler (Phase 1 - 2025-10-22)
            performance_handler = PerformanceHandler()
            self.handlers.append(performance_handler)
            logger.info("Registered PerformanceHandler")

            # ========== Phase 2: Document & Pattern Handlers ==========
            # Freshness handler (Phase 2 - 2025-10-22)
            freshness_handler = FreshnessHandler()
            self.handlers.append(freshness_handler)
            logger.info("Registered FreshnessHandler")

            # Pattern Learning handler (Phase 2 - 2025-10-22)
            pattern_learning_handler = PatternLearningHandler()
            self.handlers.append(pattern_learning_handler)
            logger.info("Registered PatternLearningHandler")

            # Pattern Traceability handler (Phase 2 - 2025-10-22)
            pattern_traceability_handler = PatternTraceabilityHandler()
            self.handlers.append(pattern_traceability_handler)
            logger.info("Registered PatternTraceabilityHandler")

            # ========== Phase 3: Advanced Analytics Handlers ==========
            # Autonomous Learning handler (Phase 3 - 2025-10-22)
            autonomous_learning_handler = AutonomousLearningHandler()
            self.handlers.append(autonomous_learning_handler)
            logger.info("Registered AutonomousLearningHandler")

            # Pattern Analytics handler (Phase 3 - 2025-10-22)
            pattern_analytics_handler = PatternAnalyticsHandler()
            self.handlers.append(pattern_analytics_handler)
            logger.info("Registered PatternAnalyticsHandler")

            # Custom Quality Rules handler (Phase 3 - 2025-10-22)
            custom_quality_rules_handler = CustomQualityRulesHandler()
            self.handlers.append(custom_quality_rules_handler)
            logger.info("Registered CustomQualityRulesHandler")

            # Quality Trends handler (Phase 3 - 2025-10-22)
            quality_trends_handler = QualityTrendsHandler()
            self.handlers.append(quality_trends_handler)
            logger.info("Registered QualityTrendsHandler")

            # Performance Analytics handler (Phase 3 - 2025-10-22)
            performance_analytics_handler = PerformanceAnalyticsHandler()
            self.handlers.append(performance_analytics_handler)
            logger.info("Registered PerformanceAnalyticsHandler")

            # ========== Phase 4: Bridge & Utility Handlers ==========
            # Bridge Intelligence handler (Phase 4 - 2025-10-22)
            bridge_intelligence_handler = BridgeIntelligenceHandler()
            self.handlers.append(bridge_intelligence_handler)
            logger.info("Registered BridgeIntelligenceHandler")

            # Document Processing handler (Phase 4 - 2025-10-22)
            document_processing_handler = DocumentProcessingHandler()
            self.handlers.append(document_processing_handler)
            logger.info("Registered DocumentProcessingHandler")

            # System Utilities handler (Phase 4 - 2025-10-22)
            system_utilities_handler = SystemUtilitiesHandler()
            self.handlers.append(system_utilities_handler)
            logger.info("Registered SystemUtilitiesHandler")

            # ========== Phase 5: Tree + Stamping Handler ==========
            # Tree Stamping handler (Phase 5 - Event-driven file location intelligence)
            tree_stamping_handler = TreeStampingHandler()
            self.handlers.append(tree_stamping_handler)
            logger.info(
                "✅ Registered TreeStampingHandler for tree discovery and stamping events"
            )

            logger.info(f"All {len(self.handlers)} handlers registered successfully")

        except Exception as e:
            logger.error(f"Failed to register handlers: {e}", exc_info=True)
            raise

    async def start(self) -> None:
        """
        Start consuming events.

        Starts background consumer loop that polls Kafka for messages
        and dispatches them to appropriate handlers.

        Runs until stop() is called or an unrecoverable error occurs.
        """
        if self.running:
            logger.warning("Consumer already running")
            return

        if not self.consumer:
            raise RuntimeError("Consumer not initialized. Call initialize() first.")

        self.running = True
        self.metrics["consumer_started_at"] = time.time()

        logger.info("Starting Kafka consumer loop")

        # Create background task for consumer loop
        self._consumer_task = asyncio.create_task(self._consumer_loop())

    async def stop(self) -> None:
        """
        Stop consumer gracefully.

        Stops consumer loop, commits offsets, and closes consumer connection.
        Waits for current event processing to complete before shutting down.
        """
        if not self.running:
            logger.info("Consumer not running, nothing to stop")
            return

        logger.info("Stopping Kafka consumer gracefully")
        self.running = False

        # Wait for consumer task to finish
        if self._consumer_task and not self._consumer_task.done():
            try:
                await asyncio.wait_for(self._consumer_task, timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning(
                    "Consumer task did not finish within timeout, cancelling"
                )
                self._consumer_task.cancel()
                try:
                    await self._consumer_task
                except asyncio.CancelledError:
                    pass

        # Close consumer
        if self.consumer:
            try:
                # Commit offsets if auto-commit is disabled
                # This ensures no message reprocessing on restart
                if not self.enable_auto_commit:
                    logger.info("Committing final offsets before shutdown")
                    self.consumer.commit(asynchronous=False)
                    logger.info("Offsets committed successfully")

                self.consumer.close()
                logger.info("Kafka consumer closed successfully")
            except Exception as e:
                logger.error(f"Error closing Kafka consumer: {e}")

        # Shutdown handlers
        await self._shutdown_handlers()

        # Shutdown DLQ publisher
        if self._dlq_publisher:
            try:
                await self._dlq_publisher.shutdown()
                logger.info("DLQ publisher shutdown complete")
            except Exception as e:
                logger.error(f"Error shutting down DLQ publisher: {e}")

        logger.info("Kafka consumer stopped")

    async def _consumer_loop(self) -> None:
        """
        Main consumer loop.

        Polls Kafka for messages and dispatches them to handlers.
        Runs until self.running is set to False.

        Error Handling:
        - KafkaException: Logs error and continues (recoverable errors)
        - Exception: Logs error and continues (non-Kafka errors)
        - Unrecoverable errors: Stop consumer loop

        Note: Uses asyncio.to_thread() to prevent blocking the event loop
        with synchronous consumer.poll() calls.
        """
        logger.info("Consumer loop started")

        # DEBUG: Log consumer state
        logger.info(
            f"[DEBUG] Consumer loop - running={self.running}, consumer={self.consumer is not None}"
        )

        try:
            poll_count = 0
            while self.running:
                poll_count += 1

                # DEBUG: Log every 10 polls to show loop is active
                if poll_count % 10 == 0:
                    logger.info(
                        f"[DEBUG] Consumer loop active - poll_count={poll_count}, running={self.running}"
                    )

                # Poll for messages (blocking with 1 second timeout)
                # Run in thread executor to avoid blocking asyncio event loop
                logger.debug(f"[DEBUG] About to poll (count={poll_count})...")
                msg: Optional[Message] = await asyncio.to_thread(
                    self.consumer.poll, 1.0
                )
                logger.debug(
                    f"[DEBUG] Poll complete - msg={'None' if msg is None else 'Message'}"
                )

                if msg is None:
                    # No message received (timeout)
                    logger.debug(
                        f"[DEBUG] Poll timeout (no message) - count={poll_count}"
                    )
                    continue

                logger.info(
                    f"[DEBUG] Message received! partition={msg.partition() if not msg.error() else 'N/A'}, offset={msg.offset() if not msg.error() else 'N/A'}"
                )

                if msg.error():
                    # Handle Kafka errors
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        # End of partition, continue polling
                        logger.debug(
                            f"Reached end of partition: {msg.topic()}[{msg.partition()}]"
                        )
                        continue
                    else:
                        # Other Kafka error
                        logger.error(f"Kafka error: {msg.error()}")
                        # Check if error is unrecoverable
                        if msg.error().fatal():
                            logger.error("Fatal Kafka error, stopping consumer")
                            self.running = False
                            break
                        continue

                # Process message
                logger.info(f"[DEBUG] About to process message from {msg.topic()}")
                try:
                    await self._process_message(msg)
                except Exception as e:
                    logger.error(
                        f"Error processing message from {msg.topic()}: {e}",
                        exc_info=True,
                    )
                    self.metrics["events_failed"] += 1
                    # Route failed message to DLQ
                    await self._route_to_dlq(msg, str(e))

                # Small yield to allow other tasks to run
                await asyncio.sleep(0)

        except asyncio.CancelledError:
            logger.info("Consumer loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Consumer loop error: {e}", exc_info=True)
            self.running = False
        finally:
            logger.info("Consumer loop stopped")

    async def _process_message(self, msg: Message) -> None:
        """
        Process a single Kafka message with backpressure control.

        Deserializes message, extracts event data, routes to appropriate handler,
        and tracks metrics. Uses semaphore to limit concurrent processing and
        prevent memory exhaustion under high load.

        Args:
            msg: Kafka message to process

        Raises:
            Exception: If message processing fails
        """
        # Track backpressure wait time
        backpressure_start = time.perf_counter()

        # Acquire semaphore (blocks if max_in_flight reached)
        async with self._semaphore:
            backpressure_wait_ms = (time.perf_counter() - backpressure_start) * 1000

            # Update backpressure metrics
            if backpressure_wait_ms > 1.0:  # Only track if we actually waited
                backpressure_wait_seconds = backpressure_wait_ms / 1000.0
                self.metrics["total_backpressure_wait_time_ms"] += backpressure_wait_ms
                self.metrics["max_in_flight_reached"] += 1

                # Record Prometheus metric for backpressure wait time
                consumer_backpressure_wait_seconds.observe(backpressure_wait_seconds)

                logger.debug(
                    f"Backpressure applied: waited {backpressure_wait_ms:.2f}ms "
                    f"to acquire processing slot"
                )

            # Track current in-flight count
            async with self._in_flight_lock:
                self._current_in_flight += 1
                self.metrics["current_in_flight"] = self._current_in_flight
                if self._current_in_flight > self.metrics["max_concurrent_events"]:
                    self.metrics["max_concurrent_events"] = self._current_in_flight

                # Update Prometheus gauge for in-flight events
                consumer_in_flight_events.set(self._current_in_flight)

            try:
                await self._process_message_internal(msg)
            finally:
                # Decrement in-flight count
                async with self._in_flight_lock:
                    self._current_in_flight -= 1
                    self.metrics["current_in_flight"] = self._current_in_flight

                    # Update Prometheus gauge for in-flight events
                    consumer_in_flight_events.set(self._current_in_flight)

    async def _process_message_internal(self, msg: Message) -> None:
        """
        Internal message processing logic.

        Separated from _process_message to allow semaphore wrapping
        without duplicating error handling logic.

        Args:
            msg: Kafka message to process

        Raises:
            Exception: If message processing fails
        """
        start_time = time.perf_counter()

        try:
            # Deserialize message
            message_value = msg.value()
            if not message_value:
                logger.warning(f"Empty message received from {msg.topic()}")
                return

            event_data = json.loads(message_value.decode("utf-8"))

            # Extract event type
            event_type = self._extract_event_type(event_data, msg.topic())

            if not event_type:
                logger.warning(
                    f"Could not determine event type for message from {msg.topic()}"
                )
                return

            # Extract correlation ID and log event received
            correlation_id = extract_correlation_id(event_data, default="unknown")

            # Log event received with pipeline traceability
            log_pipeline_event(
                logger,
                logging.INFO,
                stage="consumer",
                action="event_received",
                correlation_id=correlation_id,
                result="in_progress",
                event_type=event_type,
                topic=msg.topic(),
                partition=msg.partition(),
                offset=msg.offset(),
            )

            # In debug mode, log full event payload
            if is_debug_mode():
                log_debug_payload(logger, correlation_id, "consumer", event_data)

            # Route to appropriate handler
            log_pipeline_event(
                logger,
                logging.DEBUG,
                stage="consumer",
                action="routing_event",
                correlation_id=correlation_id,
                result="in_progress",
                event_type=event_type,
                handlers_available=len(self.handlers),
            )
            handled = await self._route_to_handler(
                event_type, event_data, correlation_id
            )

            # Update metrics
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            elapsed_seconds = elapsed_ms / 1000.0
            self.metrics["last_event_timestamp"] = time.time()

            if handled:
                # Handler succeeded
                self.metrics["events_processed"] += 1
                self.metrics["total_processing_time_ms"] += elapsed_ms

                # Record Prometheus metrics for successful processing
                event_processing_total.labels(
                    event_type=event_type, status="success"
                ).inc()
                event_processing_duration.labels(event_type=event_type).observe(
                    elapsed_seconds
                )

                logger.info(
                    f"✅ Event processed successfully",
                    extra={
                        "event_type": event_type,
                        "correlation_id": correlation_id,
                        "duration_ms": round(elapsed_ms, 2),
                        "status": "success",
                    },
                )
            else:
                # Handler failed or no handler found
                logger.warning(
                    f"❌ Event not handled successfully",
                    extra={
                        "event_type": event_type,
                        "correlation_id": correlation_id,
                        "duration_ms": round(elapsed_ms, 2),
                        "status": "failed",
                        "reason": "handler_failure_or_not_found",
                    },
                )
                self.metrics["events_failed"] += 1

                # Record Prometheus metrics for failure
                event_processing_failures.labels(
                    event_type=event_type, error_type="handler_failure"
                ).inc()
                event_processing_total.labels(
                    event_type=event_type, status="failed"
                ).inc()

            # Commit offset on success when auto-commit is disabled
            if handled and not self.enable_auto_commit and self.consumer:
                try:
                    # Asynchronous commit for throughput
                    self.consumer.commit(message=msg, asynchronous=True)
                except Exception as commit_err:
                    logger.warning(f"⚠️  Offset commit failed: {commit_err}")

        except json.JSONDecodeError as e:
            # Extract event type for metrics (may be None if deserialization failed early)
            event_type = "unknown"
            try:
                event_type = self._extract_event_type(
                    json.loads(msg.value().decode("utf-8")), msg.topic()
                )
            except:
                pass

            logger.error(f"Failed to deserialize message: {e}")
            self.metrics["events_failed"] += 1

            # Record Prometheus metrics for deserialization failure
            event_processing_failures.labels(
                event_type=event_type, error_type="deserialization_error"
            ).inc()
            event_processing_total.labels(event_type=event_type, status="failed").inc()

            # Route to DLQ to prevent data loss
            await self._route_to_dlq(msg, f"Deserialization error: {e}")
            return
        except Exception as e:
            # Extract event type for metrics
            event_type = "unknown"
            try:
                event_data = json.loads(msg.value().decode("utf-8"))
                event_type = (
                    self._extract_event_type(event_data, msg.topic()) or "unknown"
                )
            except:
                pass

            logger.error(f"Error processing message: {e}", exc_info=True)
            self.metrics["events_failed"] += 1

            # Categorize error type for better alerting
            error_type = type(e).__name__
            event_processing_failures.labels(
                event_type=event_type, error_type=error_type
            ).inc()
            event_processing_total.labels(event_type=event_type, status="failed").inc()

            # Route to DLQ to prevent data loss
            await self._route_to_dlq(msg, str(e))
            return

    def _extract_event_type(
        self, event_data: Dict[str, Any], topic: str
    ) -> Optional[str]:
        """
        Extract event type from event data or infer from topic.

        Args:
            event_data: Deserialized event data
            topic: Kafka topic name

        Returns:
            Event type string (e.g., "codegen.request.validate", "tree.index-project")
        """
        # Try to get event_type from event data
        if "event_type" in event_data:
            return event_data["event_type"]

        # Infer event type from topic name
        topic_parts = topic.split(".")

        # Handle codegen topics: omninode.codegen.request.{type}.v1
        if len(topic_parts) >= 4 and topic_parts[1] == "codegen":
            operation = topic_parts[2]  # request or response
            event_type = topic_parts[3]  # validate, analyze, pattern, mixin
            return f"codegen.{operation}.{event_type}"

        # Handle archon-intelligence topics: dev.archon-intelligence.{domain}.{action}.v1
        # Examples:
        #   dev.archon-intelligence.tree.index-project-requested.v1 -> tree.index-project
        #   dev.archon-intelligence.quality.assess-code-requested.v1 -> quality.assess-code
        if len(topic_parts) >= 4 and topic_parts[1] == "archon-intelligence":
            domain = topic_parts[2]  # tree, quality, entity, etc.
            action = (
                topic_parts[3]
                .replace("-requested", "")
                .replace("-completed", "")
                .replace("-failed", "")
            )
            return f"{domain}.{action}"

        return None

    async def _route_to_handler(
        self, event_type: str, event_data: Dict[str, Any], correlation_id: str
    ) -> bool:
        """
        Route event to appropriate handler based on event type.

        Args:
            event_type: Event type string
            event_data: Event data dictionary
            correlation_id: Correlation ID for tracing

        Returns:
            True if event was handled, False if no handler found
        """
        for handler in self.handlers:
            if handler.can_handle(event_type):
                try:
                    # Log routing to handler with pipeline traceability
                    log_pipeline_event(
                        logger,
                        logging.INFO,
                        stage="consumer",
                        action="handler_invoked",
                        correlation_id=correlation_id,
                        result="in_progress",
                        event_type=event_type,
                        handler=handler.get_handler_name(),
                    )

                    # Call handler's handle_event method
                    handler_start_time = time.perf_counter()
                    success = await handler.handle_event(event_data)
                    handler_duration_ms = (
                        time.perf_counter() - handler_start_time
                    ) * 1000

                    if not success:
                        # Log handler failure with pipeline traceability
                        log_pipeline_event(
                            logger,
                            logging.WARNING,
                            stage="consumer",
                            action="handler_failed",
                            correlation_id=correlation_id,
                            result="failed",
                            event_type=event_type,
                            handler=handler.get_handler_name(),
                            duration_ms=handler_duration_ms,
                        )
                    else:
                        # Log handler success with pipeline traceability
                        log_pipeline_event(
                            logger,
                            logging.INFO,
                            stage="consumer",
                            action="handler_completed",
                            correlation_id=correlation_id,
                            result="success",
                            event_type=event_type,
                            handler=handler.get_handler_name(),
                            duration_ms=handler_duration_ms,
                        )

                    return success

                except Exception as e:
                    # Log handler exception with pipeline traceability
                    log_pipeline_event(
                        logger,
                        logging.ERROR,
                        stage="consumer",
                        action="handler_exception",
                        correlation_id=correlation_id,
                        result="failed",
                        event_type=event_type,
                        handler=handler.get_handler_name(),
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    # Don't re-raise - log error and return False to allow processing to continue
                    return False

        # No handler found for this event type
        log_pipeline_event(
            logger,
            logging.WARNING,
            stage="consumer",
            action="no_handler_found",
            correlation_id=correlation_id,
            result="skipped",
            event_type=event_type,
            handlers_checked=len(self.handlers),
        )
        return False

    async def _route_to_dlq(self, message: Message, error: str) -> None:
        """
        Route failed message to Dead Letter Queue.

        Publishes to <original_topic>.dlq with error context.

        Args:
            message: Kafka message that failed processing
            error: Error description
        """
        try:
            self.metrics["dlq_routed"] += 1

            # Categorize error type for Prometheus metrics
            error_type = "unknown"
            if "deserialization" in error.lower() or "json" in error.lower():
                error_type = "deserialization_error"
            elif "timeout" in error.lower():
                error_type = "timeout_error"
            elif "handler" in error.lower():
                error_type = "handler_error"
            elif "validation" in error.lower():
                error_type = "validation_error"
            else:
                # Try to extract error class name from error string
                if "Error" in error:
                    error_type = (
                        error.split(":")[0].strip()
                        if ":" in error
                        else "processing_error"
                    )

            # Record Prometheus metric for DLQ routing
            dlq_routed_total.labels(
                original_topic=message.topic(), error_type=error_type
            ).inc()

            # Log the DLQ routing
            logger.warning(
                f"Routing message to DLQ | "
                f"topic={message.topic()} | "
                f"partition={message.partition()} | "
                f"offset={message.offset()} | "
                f"error={error} | "
                f"error_type={error_type}"
            )

            # Actually publish to DLQ topic if publisher available
            if self._dlq_publisher:
                dlq_topic = f"{message.topic()}.dlq"

                # Decode message value safely
                try:
                    original_value = message.value().decode("utf-8")
                except Exception as decode_err:
                    original_value = f"<binary data, size={len(message.value())} bytes>"
                    logger.warning(f"Could not decode message value: {decode_err}")

                dlq_payload = {
                    "original_topic": message.topic(),
                    "original_partition": message.partition(),
                    "original_offset": message.offset(),
                    "original_timestamp": (
                        message.timestamp()[1] if message.timestamp()[0] != -1 else None
                    ),
                    "original_value": original_value,
                    "error": error,
                    "error_type": error_type,
                    "error_timestamp": datetime.now(timezone.utc).isoformat(),
                    "consumer_group": self.consumer_group,
                }

                await self._dlq_publisher.publish(
                    topic=dlq_topic,
                    event=dlq_payload,
                    key=message.key().decode("utf-8") if message.key() else None,
                )
                logger.info(f"Published failed message to DLQ topic: {dlq_topic}")
            else:
                logger.warning(
                    "DLQ publisher not available, message not published to DLQ"
                )

        except Exception as e:
            logger.error(f"Failed to route message to DLQ: {e}", exc_info=True)

    async def _shutdown_handlers(self) -> None:
        """
        Shutdown all registered handlers.

        Calls _shutdown_publisher() on handlers that support it
        (handlers extending BaseResponsePublisher).
        """
        logger.info("Shutting down handlers")

        for handler in self.handlers:
            try:
                if hasattr(handler, "_shutdown_publisher"):
                    await handler._shutdown_publisher()
                    logger.debug(f"Shutdown handler: {handler.get_handler_name()}")
            except Exception as e:
                logger.error(
                    f"Error shutting down handler {handler.get_handler_name()}: {e}"
                )

        logger.info("All handlers shutdown complete")

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get consumer metrics including backpressure statistics.

        Returns:
            Dictionary with metrics including:
            - events_processed: Total events processed successfully
            - events_failed: Total events that failed processing
            - total_processing_time_ms: Cumulative processing time
            - avg_processing_time_ms: Average processing time per event
            - events_per_second: Processing rate
            - uptime_seconds: Consumer uptime
            - last_event_timestamp: Timestamp of last processed event
            - current_in_flight: Current number of events being processed
            - max_concurrent_events: Maximum concurrent events observed
            - max_in_flight_reached: Times backpressure was applied
            - total_backpressure_wait_time_ms: Total time spent waiting for processing slots
            - avg_backpressure_wait_ms: Average wait time when backpressure applied
            - backpressure_percentage: Percentage of events that experienced backpressure
            - max_in_flight_limit: Configured maximum in-flight events
        """
        total_events = self.metrics["events_processed"] + self.metrics["events_failed"]
        avg_processing_time = (
            self.metrics["total_processing_time_ms"] / self.metrics["events_processed"]
            if self.metrics["events_processed"] > 0
            else 0.0
        )

        uptime_seconds = (
            time.time() - self.metrics.get("consumer_started_at")
            if self.metrics.get("consumer_started_at")
            else 0
        )

        events_per_second = (
            self.metrics["events_processed"] / uptime_seconds
            if uptime_seconds > 0
            else 0.0
        )

        # Backpressure metrics
        avg_backpressure_wait_ms = (
            self.metrics["total_backpressure_wait_time_ms"]
            / self.metrics["max_in_flight_reached"]
            if self.metrics["max_in_flight_reached"] > 0
            else 0.0
        )

        backpressure_percentage = (
            (self.metrics["max_in_flight_reached"] / total_events * 100)
            if total_events > 0
            else 0.0
        )

        return {
            **self.metrics,
            "total_events": total_events,
            "avg_processing_time_ms": avg_processing_time,
            "events_per_second": events_per_second,
            "uptime_seconds": uptime_seconds,
            "handlers_registered": len(self.handlers),
            "is_running": self.running,
            # Backpressure-specific metrics
            "avg_backpressure_wait_ms": avg_backpressure_wait_ms,
            "backpressure_percentage": backpressure_percentage,
            "max_in_flight_limit": self.max_in_flight,
        }

    def get_health(self) -> Dict[str, Any]:
        """
        Get consumer health status.

        Returns:
            Dictionary with health status including:
            - status: healthy, degraded, or unhealthy
            - is_running: Whether consumer is running
            - handlers_count: Number of registered handlers
            - recent_events: Events processed in last 60 seconds
            - error_rate: Percentage of failed events
        """
        # Calculate recent event processing
        recent_threshold = 60  # seconds
        last_ts = self.metrics.get("last_event_timestamp")
        is_recent = bool(last_ts and (time.time() - last_ts) < recent_threshold)

        # Calculate error rate
        total_events = self.metrics["events_processed"] + self.metrics["events_failed"]
        error_rate = (
            (self.metrics["events_failed"] / total_events * 100)
            if total_events > 0
            else 0.0
        )

        # Determine health status
        if not self.running:
            status = "unhealthy"
        elif error_rate > 50:
            status = "degraded"
        elif not is_recent and total_events > 0:
            status = "degraded"  # No recent events but has processed before
        else:
            status = "healthy"

        return {
            "status": status,
            "is_running": self.running,
            "handlers_count": len(self.handlers),
            "total_events": total_events,
            "events_failed": self.metrics["events_failed"],
            "error_rate_percent": round(error_rate, 2),
            "has_recent_activity": is_recent,
            "uptime_seconds": (
                time.time() - self.metrics.get("consumer_started_at")
                if self.metrics.get("consumer_started_at")
                else 0
            ),
        }


# ============================================================================
# Factory Functions
# ============================================================================


def create_intelligence_kafka_consumer() -> IntelligenceKafkaConsumer:
    """
    Create Kafka consumer from environment variables.

    Reads configuration from:
    - KAFKA_BOOTSTRAP_SERVERS (default: omninode-bridge-redpanda:9092)
    - KAFKA_CONSUMER_GROUP (default: archon-intelligence)
    - KAFKA_AUTO_OFFSET_RESET (default: earliest)
    - KAFKA_ENABLE_AUTO_COMMIT (default: true)
    - KAFKA_MAX_POLL_RECORDS (default: 500)
    - KAFKA_SESSION_TIMEOUT_MS (default: 30000)
    - KAFKA_MAX_IN_FLIGHT (default: 100) - Backpressure control
    - KAFKA_CODEGEN_*_REQUEST (topic names)

    Returns:
        Configured IntelligenceKafkaConsumer instance

    Usage:
        consumer = create_intelligence_kafka_consumer()
        await consumer.initialize()
        await consumer.start()
    """
    # Read configuration from centralized config module
    bootstrap_servers = os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS", settings.kafka_bootstrap_servers
    )
    consumer_group = os.getenv("KAFKA_CONSUMER_GROUP", "archon-intelligence")
    auto_offset_reset = os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest")
    enable_auto_commit = os.getenv("KAFKA_ENABLE_AUTO_COMMIT", "true").lower() == "true"
    max_poll_records = int(os.getenv("KAFKA_MAX_POLL_RECORDS", "500"))
    session_timeout_ms = int(os.getenv("KAFKA_SESSION_TIMEOUT_MS", "30000"))
    max_in_flight = int(os.getenv("KAFKA_MAX_IN_FLIGHT", "100"))

    # Read topic names from environment (with defaults)
    topics = [
        os.getenv(
            "KAFKA_CODEGEN_VALIDATE_REQUEST", "omninode.codegen.request.validate.v1"
        ),
        os.getenv(
            "KAFKA_CODEGEN_ANALYZE_REQUEST", "omninode.codegen.request.analyze.v1"
        ),
        os.getenv(
            "KAFKA_CODEGEN_PATTERN_REQUEST", "omninode.codegen.request.pattern.v1"
        ),
        os.getenv("KAFKA_CODEGEN_MIXIN_REQUEST", "omninode.codegen.request.mixin.v1"),
        # Intelligence Adapter topic (2025-10-21)
        os.getenv(
            "KAFKA_INTELLIGENCE_ANALYSIS_REQUEST",
            "dev.archon-intelligence.intelligence.code-analysis-requested.v1",
        ),
        # New event handler topics (2025-10-22)
        os.getenv(
            "KAFKA_DOCUMENT_INDEX_REQUEST",
            "dev.archon-intelligence.intelligence.document-index-requested.v1",
        ),
        os.getenv(
            "KAFKA_REPOSITORY_SCAN_REQUEST",
            "dev.archon-intelligence.intelligence.repository-scan-requested.v1",
        ),
        os.getenv(
            "KAFKA_SEARCH_REQUEST",
            "dev.archon-intelligence.intelligence.search-requested.v1",
        ),
        # Phase 1 - Core Intelligence Events (2025-10-22)
        # Quality Assessment (3 operations)
        os.getenv(
            "KAFKA_ASSESS_CODE_REQUEST",
            "dev.archon-intelligence.quality.assess-code-requested.v1",
        ),
        os.getenv(
            "KAFKA_ASSESS_DOCUMENT_REQUEST",
            "dev.archon-intelligence.quality.assess-document-requested.v1",
        ),
        os.getenv(
            "KAFKA_COMPLIANCE_CHECK_REQUEST",
            "dev.archon-intelligence.quality.compliance-check-requested.v1",
        ),
        # Entity Extraction (4 operations)
        os.getenv(
            "KAFKA_EXTRACT_CODE_REQUEST",
            "dev.archon-intelligence.entity.extract-code-requested.v1",
        ),
        os.getenv(
            "KAFKA_EXTRACT_DOCUMENT_REQUEST",
            "dev.archon-intelligence.entity.extract-document-requested.v1",
        ),
        os.getenv(
            "KAFKA_SEARCH_ENTITIES_REQUEST",
            "dev.archon-intelligence.entity.search-requested.v1",
        ),
        os.getenv(
            "KAFKA_GET_RELATIONSHIPS_REQUEST",
            "dev.archon-intelligence.entity.relationships-requested.v1",
        ),
        # Performance (5 operations)
        os.getenv(
            "KAFKA_PERF_BASELINE_REQUEST",
            "dev.archon-intelligence.performance.baseline-requested.v1",
        ),
        os.getenv(
            "KAFKA_PERF_OPPORTUNITIES_REQUEST",
            "dev.archon-intelligence.performance.opportunities-requested.v1",
        ),
        os.getenv(
            "KAFKA_PERF_OPTIMIZE_REQUEST",
            "dev.archon-intelligence.performance.optimize-requested.v1",
        ),
        os.getenv(
            "KAFKA_PERF_REPORT_REQUEST",
            "dev.archon-intelligence.performance.report-requested.v1",
        ),
        os.getenv(
            "KAFKA_PERF_TRENDS_REQUEST",
            "dev.archon-intelligence.performance.trends-requested.v1",
        ),
        # Phase 2 - Document & Pattern Events (2025-10-22)
        # Freshness (9 operations)
        os.getenv(
            "KAFKA_FRESHNESS_ANALYZE_REQUEST",
            "dev.archon-intelligence.freshness.analyze-requested.v1",
        ),
        os.getenv(
            "KAFKA_FRESHNESS_STALE_REQUEST",
            "dev.archon-intelligence.freshness.stale-requested.v1",
        ),
        os.getenv(
            "KAFKA_FRESHNESS_REFRESH_REQUEST",
            "dev.archon-intelligence.freshness.refresh-requested.v1",
        ),
        os.getenv(
            "KAFKA_FRESHNESS_STATS_REQUEST",
            "dev.archon-intelligence.freshness.stats-requested.v1",
        ),
        os.getenv(
            "KAFKA_FRESHNESS_DOCUMENT_REQUEST",
            "dev.archon-intelligence.freshness.document-requested.v1",
        ),
        os.getenv(
            "KAFKA_FRESHNESS_CLEANUP_REQUEST",
            "dev.archon-intelligence.freshness.cleanup-requested.v1",
        ),
        os.getenv(
            "KAFKA_FRESHNESS_DOC_UPDATE_REQUEST",
            "dev.archon-intelligence.freshness.document-update-requested.v1",
        ),
        os.getenv(
            "KAFKA_FRESHNESS_EVENT_STATS_REQUEST",
            "dev.archon-intelligence.freshness.event-stats-requested.v1",
        ),
        os.getenv(
            "KAFKA_FRESHNESS_ANALYSES_REQUEST",
            "dev.archon-intelligence.freshness.analyses-requested.v1",
        ),
        # Pattern Learning (7 operations)
        os.getenv(
            "KAFKA_PATTERN_MATCH_REQUEST",
            "dev.archon-intelligence.pattern-learning.match-requested.v1",
        ),
        os.getenv(
            "KAFKA_PATTERN_HYBRID_SCORE_REQUEST",
            "dev.archon-intelligence.pattern-learning.hybrid-score-requested.v1",
        ),
        os.getenv(
            "KAFKA_PATTERN_SEMANTIC_REQUEST",
            "dev.archon-intelligence.pattern-learning.semantic-analyze-requested.v1",
        ),
        os.getenv(
            "KAFKA_PATTERN_METRICS_REQUEST",
            "dev.archon-intelligence.pattern-learning.metrics-requested.v1",
        ),
        os.getenv(
            "KAFKA_PATTERN_CACHE_STATS_REQUEST",
            "dev.archon-intelligence.pattern-learning.cache-stats-requested.v1",
        ),
        os.getenv(
            "KAFKA_PATTERN_CACHE_CLEAR_REQUEST",
            "dev.archon-intelligence.pattern-learning.cache-clear-requested.v1",
        ),
        os.getenv(
            "KAFKA_PATTERN_HEALTH_REQUEST",
            "dev.archon-intelligence.pattern-learning.health-requested.v1",
        ),
        # Pattern Traceability (11 operations)
        os.getenv(
            "KAFKA_TRACE_TRACK_REQUEST",
            "dev.archon-intelligence.traceability.track-requested.v1",
        ),
        os.getenv(
            "KAFKA_TRACE_TRACK_BATCH_REQUEST",
            "dev.archon-intelligence.traceability.track-batch-requested.v1",
        ),
        os.getenv(
            "KAFKA_TRACE_LINEAGE_REQUEST",
            "dev.archon-intelligence.traceability.lineage-requested.v1",
        ),
        os.getenv(
            "KAFKA_TRACE_EVOLUTION_REQUEST",
            "dev.archon-intelligence.traceability.evolution-requested.v1",
        ),
        os.getenv(
            "KAFKA_TRACE_EXEC_LOGS_REQUEST",
            "dev.archon-intelligence.traceability.execution-logs-requested.v1",
        ),
        os.getenv(
            "KAFKA_TRACE_EXEC_SUMMARY_REQUEST",
            "dev.archon-intelligence.traceability.execution-summary-requested.v1",
        ),
        os.getenv(
            "KAFKA_TRACE_ANALYTICS_REQUEST",
            "dev.archon-intelligence.traceability.analytics-requested.v1",
        ),
        os.getenv(
            "KAFKA_TRACE_ANALYTICS_COMPUTE_REQUEST",
            "dev.archon-intelligence.traceability.analytics-compute-requested.v1",
        ),
        os.getenv(
            "KAFKA_TRACE_FEEDBACK_ANALYZE_REQUEST",
            "dev.archon-intelligence.traceability.feedback-analyze-requested.v1",
        ),
        os.getenv(
            "KAFKA_TRACE_FEEDBACK_APPLY_REQUEST",
            "dev.archon-intelligence.traceability.feedback-apply-requested.v1",
        ),
        os.getenv(
            "KAFKA_TRACE_HEALTH_REQUEST",
            "dev.archon-intelligence.traceability.health-requested.v1",
        ),
        # Phase 3 - Advanced Analytics Events (2025-10-22)
        # Autonomous Learning (7 operations)
        os.getenv(
            "KAFKA_AUTO_PATTERNS_INGEST_REQUEST",
            "dev.archon-intelligence.autonomous.patterns-ingest-requested.v1",
        ),
        os.getenv(
            "KAFKA_AUTO_PATTERNS_SUCCESS_REQUEST",
            "dev.archon-intelligence.autonomous.patterns-success-requested.v1",
        ),
        os.getenv(
            "KAFKA_AUTO_PREDICT_AGENT_REQUEST",
            "dev.archon-intelligence.autonomous.predict-agent-requested.v1",
        ),
        os.getenv(
            "KAFKA_AUTO_PREDICT_TIME_REQUEST",
            "dev.archon-intelligence.autonomous.predict-time-requested.v1",
        ),
        os.getenv(
            "KAFKA_AUTO_SAFETY_SCORE_REQUEST",
            "dev.archon-intelligence.autonomous.safety-score-requested.v1",
        ),
        os.getenv(
            "KAFKA_AUTO_STATS_REQUEST",
            "dev.archon-intelligence.autonomous.stats-requested.v1",
        ),
        os.getenv(
            "KAFKA_AUTO_HEALTH_REQUEST",
            "dev.archon-intelligence.autonomous.health-requested.v1",
        ),
        # Pattern Analytics (5 operations)
        os.getenv(
            "KAFKA_PA_SUCCESS_RATES_REQUEST",
            "dev.archon-intelligence.pattern-analytics.success-rates-requested.v1",
        ),
        os.getenv(
            "KAFKA_PA_TOP_PATTERNS_REQUEST",
            "dev.archon-intelligence.pattern-analytics.top-patterns-requested.v1",
        ),
        os.getenv(
            "KAFKA_PA_EMERGING_REQUEST",
            "dev.archon-intelligence.pattern-analytics.emerging-requested.v1",
        ),
        os.getenv(
            "KAFKA_PA_HISTORY_REQUEST",
            "dev.archon-intelligence.pattern-analytics.history-requested.v1",
        ),
        os.getenv(
            "KAFKA_PA_HEALTH_REQUEST",
            "dev.archon-intelligence.pattern-analytics.health-requested.v1",
        ),
        # Custom Quality Rules (8 operations)
        os.getenv(
            "KAFKA_CQR_EVALUATE_REQUEST",
            "dev.archon-intelligence.custom-rules.evaluate-requested.v1",
        ),
        os.getenv(
            "KAFKA_CQR_GET_RULES_REQUEST",
            "dev.archon-intelligence.custom-rules.get-rules-requested.v1",
        ),
        os.getenv(
            "KAFKA_CQR_LOAD_CONFIG_REQUEST",
            "dev.archon-intelligence.custom-rules.load-config-requested.v1",
        ),
        os.getenv(
            "KAFKA_CQR_REGISTER_REQUEST",
            "dev.archon-intelligence.custom-rules.register-requested.v1",
        ),
        os.getenv(
            "KAFKA_CQR_ENABLE_REQUEST",
            "dev.archon-intelligence.custom-rules.enable-requested.v1",
        ),
        os.getenv(
            "KAFKA_CQR_DISABLE_REQUEST",
            "dev.archon-intelligence.custom-rules.disable-requested.v1",
        ),
        os.getenv(
            "KAFKA_CQR_CLEAR_REQUEST",
            "dev.archon-intelligence.custom-rules.clear-requested.v1",
        ),
        os.getenv(
            "KAFKA_CQR_HEALTH_REQUEST",
            "dev.archon-intelligence.custom-rules.health-requested.v1",
        ),
        # Quality Trends (7 operations)
        os.getenv(
            "KAFKA_QT_SNAPSHOT_REQUEST",
            "dev.archon-intelligence.quality-trends.snapshot-requested.v1",
        ),
        os.getenv(
            "KAFKA_QT_PROJECT_TREND_REQUEST",
            "dev.archon-intelligence.quality-trends.project-trend-requested.v1",
        ),
        os.getenv(
            "KAFKA_QT_FILE_TREND_REQUEST",
            "dev.archon-intelligence.quality-trends.file-trend-requested.v1",
        ),
        os.getenv(
            "KAFKA_QT_FILE_HISTORY_REQUEST",
            "dev.archon-intelligence.quality-trends.file-history-requested.v1",
        ),
        os.getenv(
            "KAFKA_QT_DETECT_REGRESSION_REQUEST",
            "dev.archon-intelligence.quality-trends.detect-regression-requested.v1",
        ),
        os.getenv(
            "KAFKA_QT_STATS_REQUEST",
            "dev.archon-intelligence.quality-trends.stats-requested.v1",
        ),
        os.getenv(
            "KAFKA_QT_CLEAR_REQUEST",
            "dev.archon-intelligence.quality-trends.clear-requested.v1",
        ),
        # Performance Analytics (6 operations)
        os.getenv(
            "KAFKA_PERF_ANAL_BASELINES_REQUEST",
            "dev.archon-intelligence.perf-analytics.baselines-requested.v1",
        ),
        os.getenv(
            "KAFKA_PERF_ANAL_METRICS_REQUEST",
            "dev.archon-intelligence.perf-analytics.metrics-requested.v1",
        ),
        os.getenv(
            "KAFKA_PERF_ANAL_OPPORTUNITIES_REQUEST",
            "dev.archon-intelligence.perf-analytics.opportunities-requested.v1",
        ),
        os.getenv(
            "KAFKA_PERF_ANAL_ANOMALY_CHECK_REQUEST",
            "dev.archon-intelligence.perf-analytics.anomaly-check-requested.v1",
        ),
        os.getenv(
            "KAFKA_PERF_ANAL_TRENDS_REQUEST",
            "dev.archon-intelligence.perf-analytics.trends-requested.v1",
        ),
        os.getenv(
            "KAFKA_PERF_ANAL_HEALTH_REQUEST",
            "dev.archon-intelligence.perf-analytics.health-requested.v1",
        ),
        # Phase 4 - Bridge & Utility Events (2025-10-22)
        # Bridge Intelligence (3 operations)
        os.getenv(
            "KAFKA_BRIDGE_GENERATE_INTELLIGENCE_REQUEST",
            "dev.archon-intelligence.bridge.generate-intelligence-requested.v1",
        ),
        os.getenv(
            "KAFKA_BRIDGE_HEALTH_REQUEST",
            "dev.archon-intelligence.bridge.bridge-health-requested.v1",
        ),
        os.getenv(
            "KAFKA_BRIDGE_CAPABILITIES_REQUEST",
            "dev.archon-intelligence.bridge.capabilities-requested.v1",
        ),
        # Document Processing (2 operations)
        os.getenv(
            "KAFKA_PROCESS_DOCUMENT_REQUEST",
            "dev.archon-intelligence.document.process-document-requested.v1",
        ),
        os.getenv(
            "KAFKA_BATCH_INDEX_REQUEST",
            "dev.archon-intelligence.document.batch-index-requested.v1",
        ),
        # System Utilities (3 operations)
        os.getenv(
            "KAFKA_METRICS_REQUEST",
            "dev.archon-intelligence.system.metrics-requested.v1",
        ),
        os.getenv(
            "KAFKA_KAFKA_HEALTH_REQUEST",
            "dev.archon-intelligence.system.kafka-health-requested.v1",
        ),
        os.getenv(
            "KAFKA_KAFKA_METRICS_REQUEST",
            "dev.archon-intelligence.system.kafka-metrics-requested.v1",
        ),
        # Phase 5 - Tree + Stamping Events (2025-10-26)
        # Tree Stamping (3 operations)
        os.getenv(
            "KAFKA_TREE_INDEX_PROJECT_REQUEST",
            "dev.archon-intelligence.tree.index-project-requested.v1",
        ),
        os.getenv(
            "KAFKA_TREE_SEARCH_FILES_REQUEST",
            "dev.archon-intelligence.tree.search-files-requested.v1",
        ),
        os.getenv(
            "KAFKA_TREE_GET_STATUS_REQUEST",
            "dev.archon-intelligence.tree.get-status-requested.v1",
        ),
    ]

    logger.info(
        f"Creating Kafka consumer with config: bootstrap_servers={bootstrap_servers} | "
        f"consumer_group={consumer_group} | topics={topics} | "
        f"max_in_flight={max_in_flight}"
    )

    return IntelligenceKafkaConsumer(
        bootstrap_servers=bootstrap_servers,
        topics=topics,
        consumer_group=consumer_group,
        auto_offset_reset=auto_offset_reset,
        enable_auto_commit=enable_auto_commit,
        max_poll_records=max_poll_records,
        session_timeout_ms=session_timeout_ms,
        max_in_flight=max_in_flight,
    )


# ============================================================================
# Singleton Pattern
# ============================================================================

_consumer_instance: Optional[IntelligenceKafkaConsumer] = None


def get_kafka_consumer() -> IntelligenceKafkaConsumer:
    """
    Get singleton Kafka consumer instance.

    Creates consumer on first call using environment configuration.
    Subsequent calls return the same instance.

    Returns:
        Singleton IntelligenceKafkaConsumer instance

    Usage:
        consumer = get_kafka_consumer()
        await consumer.initialize()
        await consumer.start()
    """
    global _consumer_instance

    if _consumer_instance is None:
        _consumer_instance = create_intelligence_kafka_consumer()

    return _consumer_instance
