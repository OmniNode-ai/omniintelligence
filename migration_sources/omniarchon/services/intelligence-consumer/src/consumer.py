"""
Kafka consumer for intelligence enrichment requests.

Handles consuming events from enrichment topic, processing them through
the intelligence service, and managing offsets for reliability.
"""

import asyncio
import json
import time
import traceback
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional

import structlog
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError

from .config import get_config

logger = structlog.get_logger(__name__)


class EnrichmentConsumer:
    """Kafka consumer for document enrichment events."""

    def __init__(
        self,
        message_processor: Callable[[Dict[str, Any], str], Awaitable[None]],
        error_handler: Optional[
            Callable[[Exception, Dict[str, Any]], Awaitable[None]]
        ] = None,
    ):
        """
        Initialize enrichment consumer.

        Args:
            message_processor: Async function to process messages (takes event_data, topic)
            error_handler: Optional async function to handle processing errors
        """
        self.config = get_config()
        self.message_processor = message_processor
        self.error_handler = error_handler
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.producer: Optional[AIOKafkaProducer] = None
        self.running = False
        self._processing_tasks = set()

        # Worker queue infrastructure for parallel processing
        self.work_queue: asyncio.Queue = asyncio.Queue(maxsize=self.config.queue_size)
        self.worker_tasks: list[asyncio.Task] = []
        self.receiver_task: Optional[asyncio.Task] = None
        self.worker_count = self.config.worker_count

        # Worker metrics for monitoring
        self._worker_metrics = {
            "messages_processed": [0] * self.worker_count,
            "total_processing_time_ms": [0] * self.worker_count,
            "worker_errors": [0] * self.worker_count,
        }
        self._last_metrics_log = time.time()

        self.logger = logger.bind(
            component="enrichment_consumer",
            consumer_group=self.config.kafka_consumer_group,
            instance_id=self.config.instance_id,
            worker_count=self.worker_count,
            queue_size=self.config.queue_size,
        )

    async def start(self) -> None:
        """Start Kafka consumer and producer."""
        try:
            # Initialize consumer with all subscribed topics
            topics = self.config.get_subscribed_topics()
            self.consumer = AIOKafkaConsumer(
                *topics,
                **self.config.get_kafka_config(),
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            )

            # Initialize producer for completion events and DLQ
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.config.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )

            await self.consumer.start()
            await self.producer.start()

            self.running = True

            self.logger.info(
                "consumer_started",
                topics=topics,
                bootstrap_servers=self.config.kafka_bootstrap_servers,
            )

        except Exception as e:
            self.logger.error(
                "consumer_start_failed", error=str(e), error_type=type(e).__name__
            )
            raise

    async def stop(self) -> None:
        """Stop Kafka consumer and producer gracefully."""
        self.logger.info("stopping_consumer")
        self.running = False

        # Stop receiver task (stops pulling new messages)
        if self.receiver_task and not self.receiver_task.done():
            self.logger.info("stopping_receiver_task")
            self.receiver_task.cancel()
            try:
                await self.receiver_task
            except asyncio.CancelledError:
                pass

        # Drain work queue (process remaining messages)
        queue_size = self.work_queue.qsize()
        if queue_size > 0:
            self.logger.info("draining_work_queue", remaining_messages=queue_size)
            # Wait for all queued messages to be processed
            await self.work_queue.join()

        # Stop all worker tasks
        if self.worker_tasks:
            self.logger.info("stopping_workers", worker_count=len(self.worker_tasks))
            for task in self.worker_tasks:
                if not task.done():
                    task.cancel()
            # Wait for all workers to finish
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)

        # Wait for any legacy in-flight processing tasks
        if self._processing_tasks:
            self.logger.info(
                "waiting_for_processing_tasks", task_count=len(self._processing_tasks)
            )
            await asyncio.gather(*self._processing_tasks, return_exceptions=True)

        # Stop consumer and producer
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()

        # Log final worker metrics
        self._log_worker_metrics(final=True)

        self.logger.info("consumer_stopped")

    async def consume_loop(self) -> None:
        """
        Main consumption loop with worker pool architecture.

        Starts a fast receiver coroutine and N worker coroutines for
        parallel message processing to optimize throughput.
        """
        if not self.consumer or not self.running:
            raise RuntimeError("Consumer not started")

        self.logger.info(
            "starting_worker_pool_consume_loop",
            worker_count=self.worker_count,
            queue_size=self.config.queue_size,
        )

        try:
            # Start fast receiver task
            self.receiver_task = asyncio.create_task(self._fast_receiver())

            # Start worker pool
            for worker_id in range(self.worker_count):
                worker_task = asyncio.create_task(self._worker(worker_id))
                self.worker_tasks.append(worker_task)

            self.logger.info(
                "worker_pool_started",
                receiver_running=not self.receiver_task.done(),
                workers_running=len([t for t in self.worker_tasks if not t.done()]),
            )

            # Monitor tasks for failures
            all_tasks = [self.receiver_task] + self.worker_tasks
            done, pending = await asyncio.wait(
                all_tasks, return_when=asyncio.FIRST_COMPLETED
            )

            # If any task completes/fails while running=True, it's an error
            if self.running:
                for task in done:
                    if task.exception():
                        self.logger.error(
                            "worker_pool_task_failed",
                            error=str(task.exception()),
                            error_type=type(task.exception()).__name__,
                        )
                        raise task.exception()

        except asyncio.CancelledError:
            self.logger.info("consume_loop_cancelled")
            raise
        except Exception as e:
            self.logger.error(
                "consume_loop_error", error=str(e), error_type=type(e).__name__
            )
            raise
        finally:
            # Ensure cleanup happens
            if self.running:
                self.running = False

    async def _fast_receiver(self) -> None:
        """
        Fast receiver coroutine that reads messages from Kafka and puts them in the work queue.

        This coroutine is optimized for high-throughput message reception with minimal
        processing overhead. It simply deserializes and queues messages for worker processing.
        """
        messages_received = 0
        last_throughput_log = time.time()

        self.logger.info("fast_receiver_started")

        try:
            async for message in self.consumer:
                if not self.running:
                    self.logger.info(
                        "fast_receiver_stopping", messages_received=messages_received
                    )
                    break

                # Put message in work queue (blocks if queue is full)
                await self.work_queue.put(message)
                messages_received += 1

                # Log throughput metrics every 10 seconds
                now = time.time()
                if now - last_throughput_log >= 10.0:
                    elapsed = now - last_throughput_log
                    throughput = messages_received / elapsed
                    self.logger.info(
                        "receiver_throughput_metric",
                        messages_received=messages_received,
                        elapsed_seconds=int(elapsed),
                        messages_per_second=int(throughput),
                        queue_size=self.work_queue.qsize(),
                    )
                    messages_received = 0
                    last_throughput_log = now

        except asyncio.CancelledError:
            self.logger.info(
                "fast_receiver_cancelled", total_received=messages_received
            )
            raise
        except Exception as e:
            self.logger.error(
                "fast_receiver_error",
                error=str(e),
                error_type=type(e).__name__,
                messages_received=messages_received,
            )
            raise

    async def _worker(self, worker_id: int) -> None:
        """
        Worker coroutine that processes messages from the work queue.

        Args:
            worker_id: Unique identifier for this worker (0 to worker_count-1)
        """
        worker_log = self.logger.bind(worker_id=worker_id)
        worker_log.info("worker_started")

        messages_processed = 0
        last_metrics_log = time.time()

        try:
            while self.running:
                try:
                    # Get message from queue with timeout to allow graceful shutdown
                    message = await asyncio.wait_for(self.work_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    # No message available, check if still running
                    continue

                try:
                    # Process message using existing logic
                    await self._process_message(message)

                    # Update worker metrics
                    messages_processed += 1
                    self._worker_metrics["messages_processed"][worker_id] += 1

                    # Log worker metrics every 30 seconds
                    now = time.time()
                    if now - last_metrics_log >= 30.0:
                        elapsed = now - last_metrics_log
                        throughput = messages_processed / elapsed if elapsed > 0 else 0
                        worker_log.info(
                            "worker_throughput_metric",
                            messages_processed=messages_processed,
                            elapsed_seconds=int(elapsed),
                            messages_per_second=round(throughput, 2),
                            total_messages=self._worker_metrics["messages_processed"][
                                worker_id
                            ],
                        )
                        messages_processed = 0
                        last_metrics_log = now

                except Exception as e:
                    # Log error but don't crash worker
                    self._worker_metrics["worker_errors"][worker_id] += 1
                    worker_log.error(
                        "worker_processing_error",
                        error=str(e),
                        error_type=type(e).__name__,
                        total_errors=self._worker_metrics["worker_errors"][worker_id],
                    )
                finally:
                    # Mark task as done in queue
                    self.work_queue.task_done()

        except asyncio.CancelledError:
            worker_log.info(
                "worker_cancelled",
                messages_processed=self._worker_metrics["messages_processed"][
                    worker_id
                ],
                errors=self._worker_metrics["worker_errors"][worker_id],
            )
            raise
        except Exception as e:
            worker_log.error(
                "worker_fatal_error",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    def _log_worker_metrics(self, final: bool = False) -> None:
        """
        Log aggregated worker metrics.

        Args:
            final: Whether this is the final metrics log (on shutdown)
        """
        total_processed = sum(self._worker_metrics["messages_processed"])
        total_errors = sum(self._worker_metrics["worker_errors"])

        # Calculate per-worker stats
        worker_stats = []
        for i in range(self.worker_count):
            worker_stats.append(
                {
                    "worker_id": i,
                    "messages_processed": self._worker_metrics["messages_processed"][i],
                    "errors": self._worker_metrics["worker_errors"][i],
                }
            )

        self.logger.info(
            "worker_pool_metrics",
            total_processed=total_processed,
            total_errors=total_errors,
            worker_count=self.worker_count,
            worker_stats=worker_stats,
            final=final,
        )

    async def _process_message(self, message) -> None:
        """
        Process a single enrichment message.

        Args:
            message: Kafka message from aiokafka
        """
        # Start timing
        start_time = time.time()

        event_data = message.value
        payload = event_data.get("payload", {})

        # Calculate message size
        message_size_bytes = len(json.dumps(event_data).encode("utf-8"))

        log = self.logger.bind(
            topic=message.topic,
            partition=message.partition,
            offset=message.offset,
            correlation_id=event_data.get("correlation_id"),
        )

        # Enhanced message reception logging
        log.info(
            "message_received",
            event_type=event_data.get("event_type"),
            file_path=payload.get("file_path"),
            project_name=payload.get("project_name"),
            message_size_bytes=message_size_bytes,
            message_timestamp=message.timestamp,
            has_content=bool(payload.get("content")),
            content_length=len(payload.get("content") or ""),
        )

        try:
            # Log enrichment start
            log.info(
                "enrichment_started",
                document_id=payload.get("document_id"),
                project_id=payload.get("project_name"),
                file_path=payload.get("file_path"),
            )

            # Process message through handler (pass topic for routing)
            await self.message_processor(event_data, message.topic)

            # Calculate processing time
            elapsed_ms = int((time.time() - start_time) * 1000)

            # Commit offset after successful processing
            await self.consumer.commit()

            # Log offset commit
            log.debug(
                "offset_committed",
                partition=message.partition,
                offset=message.offset,
            )

            # Enhanced success logging with performance metrics
            log.info(
                "enrichment_completed",
                document_id=payload.get("document_id"),
                processing_time_ms=elapsed_ms,
                status="success",
            )

            # Log performance metric
            log.info(
                "performance_metric",
                operation="message_processing",
                duration_ms=elapsed_ms,
                message_size_bytes=message_size_bytes,
                throughput_bytes_per_sec=(
                    int(message_size_bytes / (elapsed_ms / 1000))
                    if elapsed_ms > 0
                    else 0
                ),
            )

        except Exception as e:
            # Calculate processing time for failed attempts
            elapsed_ms = int((time.time() - start_time) * 1000)

            # Enhanced error logging with stack trace
            log.error(
                "enrichment_failed",
                document_id=payload.get("document_id"),
                error=str(e),
                error_type=type(e).__name__,
                processing_time_ms=elapsed_ms,
                stack_trace=traceback.format_exc(),
            )

            # Call error handler if provided
            if self.error_handler:
                try:
                    await self.error_handler(e, event_data)
                except Exception as handler_error:
                    log.error(
                        "error_handler_failed",
                        handler_error=str(handler_error),
                        handler_error_type=type(handler_error).__name__,
                        stack_trace=traceback.format_exc(),
                    )

            # Don't commit offset on failure - message will be reprocessed
            log.warning(
                "message_not_committed_due_to_error",
                will_retry=True,
                partition=message.partition,
                offset=message.offset,
            )

    async def publish_completion_event(
        self,
        correlation_id: str,
        file_path: str,
        success: bool,
        intelligence_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Publish enrichment completion event.

        Args:
            correlation_id: Correlation ID from original request
            file_path: Document file path
            success: Whether enrichment succeeded
            intelligence_data: Intelligence results (if successful)
            error_message: Error message (if failed)
        """
        if not self.producer:
            raise RuntimeError("Producer not started")

        completion_event = {
            "event_type": "enrichment_completed",
            "correlation_id": correlation_id,
            "timestamp": datetime.utcnow().isoformat(),
            "success": success,
            "payload": {
                "file_path": file_path,
                "intelligence_data": intelligence_data,
                "error_message": error_message,
            },
        }

        try:
            await self.producer.send(
                self.config.completion_topic, value=completion_event
            )

            self.logger.info(
                "completion_event_published",
                correlation_id=correlation_id,
                file_path=file_path,
                success=success,
            )

        except Exception as e:
            self.logger.error(
                "completion_event_publish_failed",
                correlation_id=correlation_id,
                error=str(e),
            )
            raise

    async def publish_dlq_event(
        self,
        original_event: Dict[str, Any],
        error: Exception,
        retry_count: int,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Publish failed event to dead letter queue.

        Args:
            original_event: Original enrichment event
            error: Exception that caused failure
            retry_count: Number of retry attempts
            error_details: Additional error context
        """
        if not self.producer:
            raise RuntimeError("Producer not started")

        dlq_event = {
            "event_type": "enrichment_failed",
            "failure_timestamp": datetime.utcnow().isoformat(),
            "failure_reason": str(error),
            "failure_type": type(error).__name__,
            "retry_count": retry_count,
            "original_event": original_event,
            "error_details": error_details or {},
        }

        try:
            await self.producer.send(self.config.dlq_topic, value=dlq_event)

            self.logger.warning(
                "dlq_event_published",
                correlation_id=original_event.get("correlation_id"),
                retry_count=retry_count,
                error_type=type(error).__name__,
            )

        except Exception as e:
            self.logger.error(
                "dlq_event_publish_failed",
                correlation_id=original_event.get("correlation_id"),
                error=str(e),
            )
            raise

    async def publish_code_analysis_completion(
        self,
        correlation_id: str,
        source_path: str,
        success: bool,
        analysis_result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Publish code-analysis completion event.

        Args:
            correlation_id: Correlation ID from original request
            source_path: Source path analyzed
            success: Whether analysis succeeded
            analysis_result: Analysis results (if successful)
            error_message: Error message (if failed)
        """
        if not self.producer:
            raise RuntimeError("Producer not started")

        completion_event = {
            "event_type": "omninode.intelligence.event.code_analysis_completed.v1",
            "correlation_id": correlation_id,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": {
                "source_path": source_path,
                "success": success,
                "analysis_result": analysis_result,
                "error_message": error_message,
            },
        }

        try:
            await self.producer.send(
                self.config.code_analysis_completed_topic, value=completion_event
            )

            self.logger.info(
                "code_analysis_completion_published",
                correlation_id=correlation_id,
                source_path=source_path,
                success=success,
            )

        except Exception as e:
            self.logger.error(
                "code_analysis_completion_publish_failed",
                correlation_id=correlation_id,
                error=str(e),
            )
            raise

    async def publish_code_analysis_failure(
        self,
        correlation_id: str,
        source_path: str,
        error: str,
    ) -> None:
        """
        Publish code-analysis failure event.

        Args:
            correlation_id: Correlation ID from original request
            source_path: Source path that failed
            error: Error message
        """
        if not self.producer:
            raise RuntimeError("Producer not started")

        failure_event = {
            "event_type": "omninode.intelligence.event.code_analysis_failed.v1",
            "correlation_id": correlation_id,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": {
                "source_path": source_path,
                "error_message": error,
                "error_code": "PROCESSING_ERROR",
            },
        }

        try:
            await self.producer.send(
                self.config.code_analysis_failed_topic, value=failure_event
            )

            self.logger.warning(
                "code_analysis_failure_published",
                correlation_id=correlation_id,
                source_path=source_path,
                error=error,
            )

        except Exception as e:
            self.logger.error(
                "code_analysis_failure_publish_failed",
                correlation_id=correlation_id,
                error=str(e),
            )
            raise

    async def publish_manifest_completion(
        self,
        correlation_id: str,
        success: bool,
        manifest_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        partial_results: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Publish manifest intelligence completion event.

        Args:
            correlation_id: Correlation ID from original request
            success: Whether manifest generation succeeded
            manifest_data: Complete manifest results (if successful)
            error_message: Error message (if failed)
            partial_results: Partial results if operation partially completed
        """
        if not self.producer:
            raise RuntimeError("Producer not started")

        completion_event = {
            "event_type": "omninode.intelligence.event.manifest_intelligence_completed.v1",
            "correlation_id": correlation_id,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": {
                "success": success,
                "manifest_data": manifest_data,
                "error_message": error_message,
                "partial_results": partial_results,
            },
        }

        try:
            await self.producer.send(
                self.config.manifest_completed_topic, value=completion_event
            )

            self.logger.info(
                "manifest_completion_published",
                correlation_id=correlation_id,
                success=success,
                has_partial_results=bool(partial_results),
            )

        except Exception as e:
            self.logger.error(
                "manifest_completion_publish_failed",
                correlation_id=correlation_id,
                error=str(e),
            )
            raise

    async def publish_manifest_failure(
        self,
        correlation_id: str,
        error: str,
        partial_results: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Publish manifest intelligence failure event.

        Args:
            correlation_id: Correlation ID from original request
            error: Error message
            partial_results: Partial results if operation partially completed
        """
        if not self.producer:
            raise RuntimeError("Producer not started")

        failure_event = {
            "event_type": "omninode.intelligence.event.manifest_intelligence_failed.v1",
            "correlation_id": correlation_id,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": {
                "error_message": error,
                "error_code": "PROCESSING_ERROR",
                "partial_results": partial_results,
            },
        }

        try:
            await self.producer.send(
                self.config.manifest_failed_topic, value=failure_event
            )

            self.logger.warning(
                "manifest_failure_published",
                correlation_id=correlation_id,
                error=error,
                has_partial_results=bool(partial_results),
            )

        except Exception as e:
            self.logger.error(
                "manifest_failure_publish_failed",
                correlation_id=correlation_id,
                error=str(e),
            )
            raise

    async def get_consumer_lag(self) -> Dict[str, int]:
        """
        Get consumer lag per partition.

        Returns:
            Dict mapping partition (topic-partition format) to lag count
        """
        if not self.consumer:
            return {}

        lag = {}

        try:
            partitions = self.consumer.assignment()

            for partition in partitions:
                try:
                    # Get committed offset (async method in aiokafka 0.12.0)
                    committed = await self.consumer.committed(partition)

                    # Get high water mark (synchronous method in aiokafka 0.12.0)
                    high_water = self.consumer.highwater(partition)

                    if committed is not None and high_water is not None:
                        # Use topic-partition format for better observability
                        partition_key = f"{partition.topic}-{partition.partition}"
                        lag[partition_key] = high_water - committed
                except Exception as partition_error:
                    self.logger.warning(
                        "partition_lag_calculation_failed",
                        partition=partition.partition,
                        topic=(
                            partition.topic
                            if hasattr(partition, "topic")
                            else "unknown"
                        ),
                        error=str(partition_error),
                    )
                    continue

            return lag

        except Exception as e:
            self.logger.error("lag_calculation_failed", error=str(e))
            return {}
