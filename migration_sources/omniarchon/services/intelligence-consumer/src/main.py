"""
Intelligence consumer service main entry point.

Orchestrates Kafka consumer, intelligence service client, error handling,
and health checks with graceful shutdown.
"""

import asyncio
import os
import signal
import sys
import time
import traceback
from typing import Any, Dict, Optional

# Add python lib to path for config validator
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
import structlog

from python.lib.config_validator import validate_required_env_vars

from .config import get_config
from .consumer import EnrichmentConsumer
from .enrichment import IntelligenceServiceClient
from .error_handler import ErrorClassifier, ErrorHandler

# Manifest Intelligence Handler
from .handlers.manifest_intelligence_handler import ManifestIntelligenceHandler
from .health import run_health_server

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class IntelligenceConsumerService:
    """Main service orchestrator for intelligence consumer."""

    def __init__(self):
        """Initialize consumer service."""
        self.config = get_config()

        # Core components
        self.intelligence_client: Optional[IntelligenceServiceClient] = None
        self.error_handler: Optional[ErrorHandler] = None
        self.consumer: Optional[EnrichmentConsumer] = None
        self.health_server = None
        self.manifest_intelligence_handler: Optional[ManifestIntelligenceHandler] = None

        # Shutdown flag
        self.shutdown_event = asyncio.Event()

        # Invalid event metrics
        self.invalid_events_skipped = 0
        self.invalid_events_by_reason: Dict[str, int] = {}

        # Bind instance_id to logger for all logs from this service
        self.logger = logger.bind(
            component="consumer_service", instance_id=self.config.instance_id
        )

    async def start(self) -> None:
        """Start all service components."""
        # Validate environment variables before any initialization
        validate_required_env_vars()

        self.logger.info(
            "starting_consumer_service",
            kafka_servers=self.config.kafka_bootstrap_servers,
            enrichment_topic=self.config.enrichment_topic,
        )

        try:
            # Start intelligence client (HTTP)
            self.intelligence_client = IntelligenceServiceClient()
            await self.intelligence_client.start()

            # Initialize manifest intelligence handler
            self.manifest_intelligence_handler = ManifestIntelligenceHandler(
                # Uses environment variables for postgres_url, qdrant_url, ollama_base_url, openai_api_key
            )

            # Create error handler (needed for health endpoint metrics)
            self.error_handler = ErrorHandler(dlq_publisher=self._publish_to_dlq)

            # Create consumer instance (Kafka); startup is retried asynchronously
            self.consumer = EnrichmentConsumer(
                message_processor=self._process_message,
                error_handler=self._handle_processing_error,
            )

            # Start health check server early so liveness becomes available even if Kafka is down
            self.health_server = await run_health_server(
                consumer_health_check=self._check_consumer_health,
                intelligence_health_check=self.intelligence_client.health_check,
                get_consumer_lag=self._get_consumer_lag_safe,
                get_error_stats=self.error_handler.get_stats,
                circuit_state_check=lambda: self.intelligence_client.circuit_state,
                get_invalid_event_stats=self._get_invalid_event_stats,
            )

            # Attempt consumer startup with retry in the background
            asyncio.create_task(self._start_consumer_with_retry())

            self.logger.info("consumer_service_started")

        except Exception as e:
            self.logger.error(
                "service_start_failed", error=str(e), error_type=type(e).__name__
            )
            raise

    async def stop(self) -> None:
        """Stop all service components gracefully."""
        self.logger.info("stopping_consumer_service")

        # Stop consumer (waits for in-flight processing)
        if self.consumer:
            await self.consumer.stop()

        # Stop intelligence client
        if self.intelligence_client:
            await self.intelligence_client.stop()

        # Stop health server
        if self.health_server:
            await self.health_server.stop()

        self.logger.info("consumer_service_stopped")

    async def run(self) -> None:
        """Run consumer service main loop."""
        try:
            # Wait for consumer to be started (with timeout to avoid hanging forever)
            wait_timeout = 300  # 5 minutes max wait for consumer startup
            wait_start = time.time()
            while (not self.consumer or not self.consumer.running) and (
                time.time() - wait_start
            ) < wait_timeout:
                await asyncio.sleep(1)

            if not self.consumer or not self.consumer.running:
                raise RuntimeError(f"Consumer failed to start within {wait_timeout}s")

            self.logger.info("consumer_ready_starting_consume_loop")

            # Start consume loop
            consume_task = asyncio.create_task(self.consumer.consume_loop())

            # Wait for shutdown signal
            await self.shutdown_event.wait()

            self.logger.info("shutdown_signal_received")

            # Cancel consume loop
            consume_task.cancel()

            try:
                await asyncio.wait_for(
                    consume_task, timeout=self.config.shutdown_timeout
                )
            except asyncio.TimeoutError:
                self.logger.warning(
                    "consume_loop_shutdown_timeout",
                    timeout=self.config.shutdown_timeout,
                )
            except asyncio.CancelledError:
                pass

        except Exception as e:
            self.logger.error(
                "service_run_error", error=str(e), error_type=type(e).__name__
            )
            raise

    def _is_valid_event_schema(
        self, event_data: Dict[str, Any], topic: str
    ) -> tuple[bool, str]:
        """
        Validate event has required structure before processing.

        Args:
            event_data: Event data to validate
            topic: Kafka topic name for context

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check basic structure
        if not isinstance(event_data, dict):
            return False, "Event is not a dictionary"

        payload = event_data.get("payload", {})
        if not isinstance(payload, dict):
            return False, "Missing or invalid payload"

        event_type = event_data.get("event_type", "")
        metadata = event_data.get("metadata", {})
        event_type_from_metadata = metadata.get("event_type", "")

        # Detect if this is a manifest intelligence event
        is_manifest_intelligence = (
            "manifest.requested" in topic
            or "manifest_intelligence_requested" in event_type.lower()
            or "manifest_intelligence_requested" in event_type_from_metadata.lower()
        )

        # Manifest intelligence events have different validation rules
        if is_manifest_intelligence:
            # Manifest intelligence events only need options in payload (can be empty)
            # They don't require file fields - they generate system-wide intelligence
            return True, ""

        # Detect if this is a code-analysis event
        is_code_analysis = (
            "code-analysis-requested" in topic
            or "code_analysis_requested" in event_type.lower()
            or "code_analysis_requested" in event_type_from_metadata.lower()
        )

        if is_code_analysis:
            # For code-analysis events: check for proper structure
            # INVALID OLD SCHEMA: has source_path instead of file_path
            if payload.get("source_path") and not payload.get("file_path"):
                # Allow this for backward compatibility, but log it
                # The _process_code_analysis_event handler uses source_path
                pass

            # Validate required fields (either source_path or file_path)
            has_path = bool(payload.get("file_path") or payload.get("source_path"))
            has_content = bool(payload.get("content"))

            # Check operation type - these operations don't require content
            # Try both direct payload.operation_type and payload.options.operation_type
            operation_type = (
                payload.get("operation_type")
                or payload.get("options", {}).get("operation_type")
                or ""
            )
            content_optional_operations = [
                "INFRASTRUCTURE_SCAN",
                "MODEL_SCAN",
                "MODEL_DISCOVERY",
                "SCHEMA_SCAN",
                "SCHEMA_DISCOVERY",
                "DEBUG_INTELLIGENCE_QUERY",
                "PATTERN_EXTRACTION",
            ]
            is_content_optional = operation_type in content_optional_operations

            # For standard operations, both path and content are required
            # For content-optional operations (discovery/infrastructure scans), all fields are optional
            if not is_content_optional:
                # Standard operations require both path and content
                if not has_path:
                    return (
                        False,
                        "Code-analysis event missing required fields: file_path/source_path",
                    )
                if not has_content:
                    return (
                        False,
                        f"Code-analysis event missing required fields: content (operation_type={operation_type})",
                    )

        else:
            # For enrichment events: must have EITHER (file_path + content + project_name) OR (files array)
            has_individual = all(
                [
                    payload.get("file_path"),
                    payload.get("content"),
                    payload.get("project_name"),
                ]
            )
            has_batch = (
                isinstance(payload.get("files"), list)
                and len(payload.get("files", [])) > 0
            )

            if not (has_individual or has_batch):
                payload_keys = list(payload.keys())

                # Check if this looks like old code-analysis schema in wrong topic
                if payload.get("source_path") and not payload.get("file_path"):
                    return False, (
                        f"Old code-analysis schema detected in enrichment topic "
                        f"(has source_path, missing file_path/project_name). "
                        f"Payload keys: {payload_keys}"
                    )

                return False, (
                    f"Enrichment event missing required fields. "
                    f"Need either (file_path + content + project_name) or (files array). "
                    f"Found keys: {payload_keys}"
                )

        return True, ""

    async def _process_message(self, event_data: Dict[str, Any], topic: str) -> None:
        """
        Route message to appropriate handler based on topic or event type.

        Args:
            event_data: Event data from Kafka
            topic: Kafka topic the message came from
        """
        correlation_id = event_data.get("correlation_id", "unknown")

        # Validate event schema FIRST
        is_valid, error_msg = self._is_valid_event_schema(event_data, topic)

        if not is_valid:
            # Track invalid event metrics
            self.invalid_events_skipped += 1
            reason_key = error_msg[:100]  # Truncate for grouping
            self.invalid_events_by_reason[reason_key] = (
                self.invalid_events_by_reason.get(reason_key, 0) + 1
            )

            # Log and SKIP invalid event (commit offset to move past it)
            self.logger.warning(
                "invalid_event_schema_skipped",
                correlation_id=correlation_id,
                topic=topic,
                error=error_msg,
                payload_keys=list(event_data.get("payload", {}).keys()),
                event_type=event_data.get("event_type", "unknown"),
                total_skipped=self.invalid_events_skipped,
            )

            # Alert if too many invalid events
            if self.invalid_events_skipped % 100 == 0:
                self.logger.error(
                    "high_invalid_event_count_alert",
                    total_invalid_events_skipped=self.invalid_events_skipped,
                    breakdown_by_reason=dict(
                        sorted(
                            self.invalid_events_by_reason.items(),
                            key=lambda x: x[1],
                            reverse=True,
                        )
                    ),
                )

            # Don't raise exception - just return to commit offset and skip
            return

        # Continue with normal processing
        event_type = event_data.get("event_type", "")
        metadata = event_data.get("metadata", {})
        event_type_from_metadata = metadata.get("event_type", "")

        # Check if this is a manifest intelligence event
        if (
            "manifest.requested" in topic
            or "manifest_intelligence_requested" in event_type.lower()
            or "manifest_intelligence_requested" in event_type_from_metadata.lower()
        ):
            await self._process_manifest_intelligence_event(event_data)
        # Check if this is a code-analysis event
        elif (
            "code-analysis-requested" in topic
            or "code_analysis_requested" in event_type.lower()
            or "code_analysis_requested" in event_type_from_metadata.lower()
        ):
            await self._process_code_analysis_event(event_data)
        else:
            # Default to enrichment event handling
            await self._process_enrichment_event(event_data)

    async def _process_enrichment_event(self, event_data: Dict[str, Any]) -> None:
        """
        Process enrichment event (supports both batch and individual file events).

        Args:
            event_data: Enrichment event from Kafka

        Raises:
            Exception: If processing fails
        """
        # Start timing
        start_time = time.time()

        correlation_id = event_data.get("correlation_id", "unknown")
        payload = event_data.get("payload", {})

        # Check if this is a batch event (contains 'files' array)
        files_array = payload.get("files")

        if files_array is not None:
            # Batch event processing
            await self._process_batch_event(
                event_data, correlation_id, payload, files_array, start_time
            )
        else:
            # Individual file event processing (backward compatibility)
            await self._process_individual_file_event(
                event_data, correlation_id, payload, start_time
            )

    async def _process_batch_event(
        self,
        event_data: Dict[str, Any],
        correlation_id: str,
        payload: Dict[str, Any],
        files_array: list,
        start_time: float,
    ) -> None:
        """
        Process batch enrichment event with multiple files.

        Args:
            event_data: Original event data
            correlation_id: Event correlation ID
            payload: Event payload
            files_array: Array of file objects to process
            start_time: Processing start time

        Raises:
            Exception: If all files fail processing
        """
        project_name = payload.get("project_name")
        project_path = payload.get("project_path")

        log = self.logger.bind(
            correlation_id=correlation_id,
            project_name=project_name,
            batch_size=len(files_array),
        )

        log.info(
            "batch_enrichment_event_processing_started",
            event_type=event_data.get("event_type"),
            project_path=project_path,
            total_files=len(files_array),
            include_tests=payload.get("include_tests", True),
            force_reindex=payload.get("force_reindex", False),
        )

        # Validate batch payload
        if not project_name:
            validation_error = f"Missing required field: project_name={project_name}"
            log.error("batch_payload_validation_failed", error=validation_error)
            raise ValueError(validation_error)

        if not files_array or not isinstance(files_array, list):
            validation_error = f"Invalid or empty files array: {type(files_array)}"
            log.error("batch_payload_validation_failed", error=validation_error)
            raise ValueError(validation_error)

        # Check operation type - these operations don't need content
        # Try both direct payload.operation_type and payload.options.operation_type
        operation_type = (
            payload.get("operation_type")
            or payload.get("options", {}).get("operation_type")
            or ""
        )
        content_optional_operations = [
            "INFRASTRUCTURE_SCAN",
            "MODEL_SCAN",
            "MODEL_DISCOVERY",
            "SCHEMA_SCAN",
            "SCHEMA_DISCOVERY",
            "DEBUG_INTELLIGENCE_QUERY",
            "PATTERN_EXTRACTION",
        ]
        is_infrastructure_scan = operation_type in content_optional_operations

        # Process files concurrently
        successes = 0
        failures = 0
        file_results = []

        # Create tasks for concurrent processing
        async def process_single_file(
            file_obj: Dict[str, Any], index: int
        ) -> Dict[str, Any]:
            """Process a single file from the batch."""
            file_path = file_obj.get("file_path") or file_obj.get("relative_path")
            content = file_obj.get("content")

            file_log = self.logger.bind(
                correlation_id=correlation_id,
                file_path=file_path,
                project_name=project_name,
                batch_index=index,
            )

            # Only require content for code analysis (not infrastructure scans)
            if not is_infrastructure_scan:
                if not file_path or not content:
                    file_log.warning(
                        "batch_file_skipped_invalid_data",
                        has_file_path=bool(file_path),
                        has_content=bool(content),
                    )
                    return {
                        "file_path": file_path,
                        "success": False,
                        "error": "Missing file_path or content",
                        "processing_time_ms": 0,
                    }
            else:
                # Infrastructure scans only need file_path
                if not file_path:
                    file_log.warning(
                        "batch_file_skipped_invalid_data",
                        has_file_path=bool(file_path),
                        operation_type=operation_type,
                    )
                    return {
                        "file_path": file_path,
                        "success": False,
                        "error": "Missing file_path",
                        "processing_time_ms": 0,
                    }

            try:
                file_start_time = time.time()

                # Extract content hash from file object (provided by upstream)
                content_hash = file_obj.get("content_hash") or file_obj.get("checksum")

                file_log.info(
                    "batch_file_processing_started",
                    content_length=len(content) if content else 0,
                    has_content_hash=bool(content_hash),
                    content_hash=(
                        content_hash[:16] + "..."
                        if content_hash and len(content_hash) > 16
                        else content_hash
                    ),
                )

                # Warn if hash is missing from Kafka event
                if not content_hash:
                    file_log.warning(
                        "⚠️  [HASH_MISSING_FROM_KAFKA] No content hash in Kafka event payload",
                        file_path=file_path,
                        payload_keys=list(file_obj.keys()),
                    )

                intelligence_data = await self.intelligence_client.process_document(
                    file_path=file_path,
                    content=content,
                    project_name=project_name,
                    correlation_id=f"{correlation_id}-file-{index}",
                )

                file_elapsed_ms = int((time.time() - file_start_time) * 1000)

                file_log.info(
                    "batch_file_processing_succeeded",
                    processing_time_ms=file_elapsed_ms,
                    entities_extracted=len(intelligence_data.get("entities", [])),
                    patterns_detected=len(intelligence_data.get("patterns", [])),
                    quality_score=intelligence_data.get("quality_score"),
                )

                # Publish individual completion event
                await self.consumer.publish_completion_event(
                    correlation_id=f"{correlation_id}-file-{index}",
                    file_path=file_path,
                    success=True,
                    intelligence_data=intelligence_data,
                )

                return {
                    "file_path": file_path,
                    "success": True,
                    "processing_time_ms": file_elapsed_ms,
                    "entities": len(intelligence_data.get("entities", [])),
                    "patterns": len(intelligence_data.get("patterns", [])),
                }

            except Exception as e:
                file_elapsed_ms = int((time.time() - file_start_time) * 1000)

                file_log.error(
                    "batch_file_processing_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    processing_time_ms=file_elapsed_ms,
                )

                # Publish individual failure event
                await self.consumer.publish_completion_event(
                    correlation_id=f"{correlation_id}-file-{index}",
                    file_path=file_path,
                    success=False,
                    error_message=str(e),
                )

                return {
                    "file_path": file_path,
                    "success": False,
                    "error": str(e),
                    "processing_time_ms": file_elapsed_ms,
                }

        # Process all files concurrently
        tasks = [
            process_single_file(file_obj, idx)
            for idx, file_obj in enumerate(files_array)
        ]

        file_results = await asyncio.gather(*tasks, return_exceptions=False)

        # Calculate batch statistics
        successes = sum(1 for r in file_results if r.get("success"))
        failures = len(file_results) - successes
        total_elapsed_ms = int((time.time() - start_time) * 1000)
        avg_file_time_ms = (
            int(
                sum(r.get("processing_time_ms", 0) for r in file_results)
                / len(file_results)
            )
            if file_results
            else 0
        )
        total_entities = sum(
            r.get("entities", 0) for r in file_results if r.get("success")
        )
        total_patterns = sum(
            r.get("patterns", 0) for r in file_results if r.get("success")
        )

        # Log batch completion
        log.info(
            "batch_enrichment_event_completed",
            total_files=len(files_array),
            successes=successes,
            failures=failures,
            success_rate=f"{(successes/len(files_array)*100):.1f}%",
            total_processing_time_ms=total_elapsed_ms,
            avg_file_processing_time_ms=avg_file_time_ms,
            total_entities_extracted=total_entities,
            total_patterns_detected=total_patterns,
        )

        # Log performance metric
        log.info(
            "performance_metric",
            operation="batch_enrichment_event_processing",
            duration_ms=total_elapsed_ms,
            file_count=len(files_array),
            successes=successes,
            failures=failures,
            throughput_files_per_sec=(
                round(len(files_array) / (total_elapsed_ms / 1000), 2)
                if total_elapsed_ms > 0
                else 0
            ),
        )

        # If all files failed, raise exception
        if successes == 0:
            error_msg = f"Batch processing failed: all {len(files_array)} files failed"
            log.error("batch_processing_complete_failure", error=error_msg)
            raise Exception(error_msg)

        # If partial failure, log warning but don't raise
        if failures > 0:
            log.warning(
                "batch_processing_partial_failure",
                successes=successes,
                failures=failures,
                failed_files=[
                    r["file_path"] for r in file_results if not r.get("success")
                ],
            )

    async def _process_individual_file_event(
        self,
        event_data: Dict[str, Any],
        correlation_id: str,
        payload: Dict[str, Any],
        start_time: float,
    ) -> None:
        """
        Process individual file enrichment event (backward compatibility).

        Args:
            event_data: Original event data
            correlation_id: Event correlation ID
            payload: Event payload
            start_time: Processing start time

        Raises:
            Exception: If processing fails
        """
        file_path = payload.get("file_path")
        content = payload.get("content")
        project_name = payload.get("project_name")

        log = self.logger.bind(
            correlation_id=correlation_id,
            file_path=file_path,
            project_name=project_name,
        )

        # Enhanced processing start logging
        log.info(
            "enrichment_event_processing_started",
            event_type=event_data.get("event_type"),
            has_content=bool(content),
            content_length=len(content) if content else 0,
            payload_keys=list(payload.keys()),
        )

        # Check operation type - these operations don't need content
        # Try both direct payload.operation_type and payload.options.operation_type
        operation_type = (
            payload.get("operation_type")
            or payload.get("options", {}).get("operation_type")
            or ""
        )
        content_optional_operations = [
            "INFRASTRUCTURE_SCAN",
            "MODEL_SCAN",
            "MODEL_DISCOVERY",
            "SCHEMA_SCAN",
            "SCHEMA_DISCOVERY",
            "DEBUG_INTELLIGENCE_QUERY",
            "PATTERN_EXTRACTION",
        ]
        is_infrastructure_scan = operation_type in content_optional_operations

        # Validate payload
        # For content-optional operations, all fields are optional (discovery operations)
        # For standard operations, require file_path, content, and project_name
        if is_infrastructure_scan:
            # Infrastructure/discovery operations: no required fields
            # These are repository scanning operations that discover files
            log.info(
                "content_optional_operation_detected",
                operation_type=operation_type,
                has_file_path=bool(file_path),
                has_project_name=bool(project_name),
            )
        else:
            # Standard enrichment operations require all three fields
            required_fields = [file_path, content, project_name]
            field_names = ["file_path", "content", "project_name"]

            if not all(required_fields):
                validation_error = (
                    f"Missing required fields for {operation_type or 'standard'} operation: "
                    + ", ".join(
                        [
                            f"{name}={'present' if val else 'missing'}"
                            for name, val in zip(field_names, required_fields)
                        ]
                    )
                )
                log.error(
                    "payload_validation_failed",
                    missing_fields=[
                        field
                        for field, value in zip(field_names, required_fields)
                        if not value
                    ],
                    operation_type=operation_type,
                    error=validation_error,
                )
            raise ValueError(validation_error)

        # Process through intelligence service
        try:
            # Log intelligence service call start
            intelligence_start_time = time.time()
            log.info(
                "calling_intelligence_service",
                file_path=file_path,
                content_length=len(content) if content else 0,
            )

            intelligence_data = await self.intelligence_client.process_document(
                file_path=file_path,
                content=content,
                project_name=project_name,
                correlation_id=correlation_id,
            )

            intelligence_elapsed_ms = int(
                (time.time() - intelligence_start_time) * 1000
            )

            # Log intelligence service response
            log.info(
                "intelligence_service_responded",
                processing_time_ms=intelligence_elapsed_ms,
                has_entities=bool(intelligence_data.get("entities")),
                entity_count=len(intelligence_data.get("entities", [])),
                has_patterns=bool(intelligence_data.get("patterns")),
                pattern_count=len(intelligence_data.get("patterns", [])),
                quality_score=intelligence_data.get("quality_score"),
            )

            # Publish completion event
            await self.consumer.publish_completion_event(
                correlation_id=correlation_id,
                file_path=file_path,
                success=True,
                intelligence_data=intelligence_data,
            )

            # Calculate total processing time
            total_elapsed_ms = int((time.time() - start_time) * 1000)

            # Enhanced success logging
            log.info(
                "enrichment_event_completed_successfully",
                total_processing_time_ms=total_elapsed_ms,
                intelligence_processing_time_ms=intelligence_elapsed_ms,
                overhead_ms=total_elapsed_ms - intelligence_elapsed_ms,
                entities_extracted=len(intelligence_data.get("entities", [])),
                patterns_detected=len(intelligence_data.get("patterns", [])),
            )

            # Log performance metric
            log.info(
                "performance_metric",
                operation="enrichment_event_processing",
                duration_ms=total_elapsed_ms,
                content_length=len(content) if content else 0,
                processing_rate_chars_per_sec=(
                    int(len(content) / (total_elapsed_ms / 1000))
                    if content and total_elapsed_ms > 0
                    else 0
                ),
            )

        except Exception as e:
            # Calculate processing time for failed attempts
            total_elapsed_ms = int((time.time() - start_time) * 1000)

            # Enhanced error logging with full context and stack trace
            log.error(
                "enrichment_processing_failed",
                error=str(e),
                error_type=type(e).__name__,
                processing_time_ms=total_elapsed_ms,
                content_length=len(content) if content else 0,
                file_path=file_path,
                project_name=project_name,
                stack_trace=traceback.format_exc(),
            )

            # Check if error is retryable
            if ErrorClassifier.should_skip_retry(e):
                log.warning(
                    "error_non_retryable_routing_to_dlq",
                    error_category="non_retryable",
                    will_retry=False,
                )

                # Route directly to DLQ
                await self._publish_to_dlq(
                    original_event=event_data,
                    error=e,
                    retry_count=0,
                    error_details={
                        "reason": "non_retryable_error",
                        "processing_time_ms": total_elapsed_ms,
                        "error_classification": "non_retryable",
                    },
                )

                # Publish completion event with failure
                await self.consumer.publish_completion_event(
                    correlation_id=correlation_id,
                    file_path=file_path,
                    success=False,
                    error_message=str(e),
                )
            else:
                log.warning(
                    "error_retryable_will_reprocess",
                    error_category="retryable",
                    will_retry=True,
                )
                # Re-raise for retry handling
                raise

    async def _process_code_analysis_event(self, event_data: Dict[str, Any]) -> None:
        """
        Process code-analysis event.

        Args:
            event_data: Code-analysis event from Kafka

        Raises:
            Exception: If processing fails
        """
        # Start timing
        start_time = time.time()

        correlation_id = event_data.get("correlation_id", "unknown")
        payload = event_data.get("payload", {})
        source_path = payload.get("source_path", "")
        content = payload.get("content", "")
        language = payload.get("language", "python")

        # Try both payload.operation_type and payload.options.operation_type
        operation_type = (
            payload.get("operation_type")
            or payload.get("options", {}).get("operation_type")
            or "QUALITY_ASSESSMENT"
        )

        # Check if this is a content-optional operation
        content_optional_operations = [
            "INFRASTRUCTURE_SCAN",
            "MODEL_SCAN",
            "MODEL_DISCOVERY",
            "SCHEMA_SCAN",
            "SCHEMA_DISCOVERY",
            "DEBUG_INTELLIGENCE_QUERY",
            "PATTERN_EXTRACTION",
        ]
        is_content_optional = operation_type in content_optional_operations

        log = self.logger.bind(
            correlation_id=correlation_id,
            source_path=source_path,
            language=language,
            operation_type=operation_type,
        )

        # Enhanced processing start logging
        log.info(
            "code_analysis_event_processing_started",
            event_type=event_data.get("event_type"),
            has_content=bool(content),
            content_length=len(content) if content else 0,
            language=language,
            operation_type=operation_type,
            is_content_optional=is_content_optional,
        )

        # Validate required fields (content is optional for certain operations)
        if is_content_optional:
            # For content-optional operations (discovery/infrastructure scans), ALL fields are optional
            # These are repository-wide scans that may not have specific file paths
            log.info(
                "content_optional_operation_detected",
                operation_type=operation_type,
                has_source_path=bool(source_path),
                has_content=bool(content),
            )

            # For content-optional operations with no source_path or content,
            # return early with success (infrastructure scans don't need code analysis)
            if not source_path or not content:
                log.info(
                    "content_optional_operation_skipping_code_analysis",
                    operation_type=operation_type,
                    reason="Infrastructure scan operations don't require code analysis",
                )

                # Publish completion event without analysis
                await self.consumer.publish_code_analysis_completion(
                    correlation_id=correlation_id,
                    source_path=source_path or "infrastructure_scan",
                    success=True,
                    analysis_result={
                        "operation_type": operation_type,
                        "status": "completed",
                        "message": "Infrastructure scan completed successfully",
                    },
                )

                # Calculate total processing time
                total_elapsed_ms = int((time.time() - start_time) * 1000)

                log.info(
                    "content_optional_operation_completed_successfully",
                    operation_type=operation_type,
                    total_processing_time_ms=total_elapsed_ms,
                )
                return
        else:
            # For standard operations, both source_path and content are required
            if not source_path or not content:
                validation_error = (
                    f"Missing required fields: source_path={source_path}, "
                    f"content={'present' if content else 'missing'}"
                )
                log.error(
                    "payload_validation_failed",
                    missing_fields=[
                        field
                        for field, value in [
                            ("source_path", source_path),
                            ("content", content),
                        ]
                        if not value
                    ],
                    error=validation_error,
                )
                raise ValueError(validation_error)

        # Route to intelligence service /assess/code endpoint
        try:
            # Log intelligence service call start
            analysis_start_time = time.time()
            log.info(
                "calling_code_assessment_service",
                source_path=source_path,
                content_length=len(content) if content else 0,
                language=language,
            )

            analysis_result = await self.intelligence_client.assess_code(
                source_path=source_path,
                content=content,
                language=language,
                correlation_id=correlation_id,
            )

            analysis_elapsed_ms = int((time.time() - analysis_start_time) * 1000)

            # Log intelligence service response
            log.info(
                "code_assessment_service_responded",
                processing_time_ms=analysis_elapsed_ms,
                quality_score=analysis_result.get("quality_score"),
                has_issues=bool(analysis_result.get("issues")),
                issue_count=len(analysis_result.get("issues", [])),
                has_recommendations=bool(analysis_result.get("recommendations")),
            )

            # Publish completion event (code-analysis-completed topic)
            await self.consumer.publish_code_analysis_completion(
                correlation_id=correlation_id,
                source_path=source_path,
                success=True,
                analysis_result=analysis_result,
            )

            # Calculate total processing time
            total_elapsed_ms = int((time.time() - start_time) * 1000)

            # Enhanced success logging
            log.info(
                "code_analysis_event_completed_successfully",
                total_processing_time_ms=total_elapsed_ms,
                analysis_processing_time_ms=analysis_elapsed_ms,
                overhead_ms=total_elapsed_ms - analysis_elapsed_ms,
                quality_score=analysis_result.get("quality_score"),
                issues_found=len(analysis_result.get("issues", [])),
            )

            # Log performance metric
            log.info(
                "performance_metric",
                operation="code_analysis_event_processing",
                duration_ms=total_elapsed_ms,
                content_length=len(content) if content else 0,
                language=language,
            )

        except Exception as e:
            # Calculate processing time for failed attempts
            total_elapsed_ms = int((time.time() - start_time) * 1000)

            # Enhanced error logging with full context and stack trace
            log.error(
                "code_analysis_processing_failed",
                error=str(e),
                error_type=type(e).__name__,
                processing_time_ms=total_elapsed_ms,
                content_length=len(content) if content else 0,
                source_path=source_path,
                language=language,
                stack_trace=traceback.format_exc(),
            )

            # Publish failure event
            await self.consumer.publish_code_analysis_failure(
                correlation_id=correlation_id,
                source_path=source_path,
                error=str(e),
            )

            # Re-raise for retry handling
            raise

    async def _process_manifest_intelligence_event(
        self, event_data: Dict[str, Any]
    ) -> None:
        """
        Process manifest intelligence event.

        Args:
            event_data: Manifest intelligence event from Kafka

        Raises:
            Exception: If processing fails
        """
        # Start timing
        start_time = time.time()

        correlation_id = event_data.get("correlation_id", "unknown")
        payload = event_data.get("payload", {})
        options = payload.get("options", {})

        log = self.logger.bind(
            correlation_id=correlation_id,
            operation_type="manifest_intelligence",
        )

        log.info(
            "manifest_intelligence_event_processing_started",
            event_type=event_data.get("event_type"),
            has_options=bool(options),
            options_keys=list(options.keys()) if options else [],
        )

        # Check if handler is initialized
        if not self.manifest_intelligence_handler:
            error_msg = "ManifestIntelligenceHandler not initialized"
            log.error("manifest_handler_not_initialized", error=error_msg)
            await self.consumer.publish_manifest_failure(
                correlation_id=correlation_id,
                error=error_msg,
            )
            raise RuntimeError(error_msg)

        try:
            # Process through manifest intelligence handler
            manifest_start_time = time.time()
            log.info(
                "calling_manifest_intelligence_handler",
                correlation_id=correlation_id,
                options=options,
            )

            manifest_result = await self.manifest_intelligence_handler.execute(
                correlation_id=correlation_id,
                options=options,
            )

            manifest_elapsed_ms = int((time.time() - manifest_start_time) * 1000)

            log.info(
                "manifest_intelligence_handler_responded",
                processing_time_ms=manifest_elapsed_ms,
                has_manifest_data=bool(manifest_result.get("manifest_data")),
                has_partial_results=bool(manifest_result.get("partial_results")),
            )

            # Publish completion event
            await self.consumer.publish_manifest_completion(
                correlation_id=correlation_id,
                success=manifest_result.get("success", True),
                manifest_data=manifest_result.get("manifest_data"),
                partial_results=manifest_result.get("partial_results"),
            )

            # Calculate total processing time
            total_elapsed_ms = int((time.time() - start_time) * 1000)

            log.info(
                "manifest_intelligence_event_completed_successfully",
                total_processing_time_ms=total_elapsed_ms,
                manifest_processing_time_ms=manifest_elapsed_ms,
                overhead_ms=total_elapsed_ms - manifest_elapsed_ms,
            )

        except Exception as e:
            # Calculate processing time for failed attempts
            total_elapsed_ms = int((time.time() - start_time) * 1000)

            log.error(
                "manifest_intelligence_processing_failed",
                error=str(e),
                error_type=type(e).__name__,
                processing_time_ms=total_elapsed_ms,
                stack_trace=traceback.format_exc(),
            )

            # Publish failure event with partial results if available
            partial_results = getattr(e, "partial_results", None)
            await self.consumer.publish_manifest_failure(
                correlation_id=correlation_id,
                error=str(e),
                partial_results=partial_results,
            )

            # Re-raise for retry handling
            raise

    async def _handle_processing_error(
        self, error: Exception, event_data: Dict[str, Any]
    ) -> None:
        """
        Handle processing error with retry logic.

        Args:
            error: Exception that occurred
            event_data: Original event data
        """
        try:
            await self.error_handler.handle_error(
                error=error,
                event_data=event_data,
                processor=self._process_enrichment_event,
            )
        except Exception as retry_error:
            # Error handler will have already logged and routed to DLQ
            self.logger.error(
                "error_handling_failed",
                correlation_id=event_data.get("correlation_id"),
                error=str(retry_error),
            )

    async def _publish_to_dlq(
        self,
        original_event: Dict[str, Any],
        error: Exception,
        retry_count: int,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Publish event to DLQ.

        Args:
            original_event: Original enrichment event
            error: Exception that caused failure
            retry_count: Number of retry attempts
            error_details: Additional error context
        """
        await self.consumer.publish_dlq_event(
            original_event=original_event,
            error=error,
            retry_count=retry_count,
            error_details=error_details,
        )

    async def _check_consumer_health(self) -> bool:
        """Check if consumer is healthy."""
        return self.consumer is not None and self.consumer.running

    async def _get_consumer_lag_safe(self) -> Dict[str, int]:
        """Get consumer lag; returns empty when consumer is not yet started."""
        if not self.consumer:
            return {}
        return await self.consumer.get_consumer_lag()

    def _get_invalid_event_stats(self) -> Dict[str, Any]:
        """Get statistics about invalid events that were skipped."""
        return {
            "total_skipped": self.invalid_events_skipped,
            "by_reason": dict(
                sorted(
                    self.invalid_events_by_reason.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )
            ),
        }

    async def _start_consumer_with_retry(self) -> None:
        """Start Kafka consumer with exponential backoff until successful."""
        backoff_seconds = max(1, int(self.config.retry_backoff_base))
        backoff_max = max(backoff_seconds, int(self.config.retry_backoff_max))
        while True:
            try:
                await self.consumer.start()
                self.logger.info("consumer_started_with_retry")
                return
            except Exception as e:
                self.logger.error(
                    "consumer_start_retry_scheduled",
                    error=str(e),
                    next_retry_seconds=backoff_seconds,
                )
                await asyncio.sleep(backoff_seconds)
                backoff_seconds = min(
                    backoff_seconds * int(self.config.retry_backoff_base), backoff_max
                )

    def handle_shutdown_signal(self, sig: signal.Signals) -> None:
        """
        Handle shutdown signals.

        Args:
            sig: Signal received
        """
        self.logger.info("shutdown_signal_received", signal=sig.name)
        self.shutdown_event.set()


async def main() -> None:
    """Main entry point."""
    import logging

    config = get_config()

    # Configure Python's standard logging first (required for structlog.stdlib.LoggerFactory)
    logging.basicConfig(
        format="%(message)s",
        level=logging.DEBUG if config.log_level.upper() == "DEBUG" else logging.INFO,
        stream=sys.stderr,
    )

    # Configure structured logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            (
                structlog.processors.JSONRenderer()
                if config.log_format == "json"
                else structlog.dev.ConsoleRenderer()
            ),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    service = IntelligenceConsumerService()

    # Setup signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: service.handle_shutdown_signal(s))

    try:
        # Start service
        await service.start()

        # Run main loop
        await service.run()

    except Exception as e:
        logger.error("service_error", error=str(e), error_type=type(e).__name__)
        sys.exit(1)

    finally:
        # Cleanup
        await service.stop()


def run() -> None:
    """Run service entry point."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt_received")
    except Exception as e:
        logger.error("fatal_error", error=str(e), error_type=type(e).__name__)
        sys.exit(1)


if __name__ == "__main__":
    run()
