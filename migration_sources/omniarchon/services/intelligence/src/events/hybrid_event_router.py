"""
Hybrid Event Router for intelligent switching between Event Bus and Kafka.

This router implements the core decision logic for determining which
publisher to use based on context, configuration, and operational requirements.
"""

import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable, Dict, List, Optional, Union
from uuid import UUID, uuid4

# Import error handling from omnibase_core with fallback
try:
    from omnibase_core.errors import EnumCoreErrorCode as CoreErrorCode
    from omnibase_core.errors import OnexError
except ImportError:
    # Fallback error handling classes
    from enum import Enum

    class CoreErrorCode(str, Enum):
        """Fallback error codes when omnibase_core is not available"""

        INITIALIZATION_FAILED = "initialization_failed"
        OPERATION_FAILED = "operation_failed"
        SHUTDOWN_ERROR = "shutdown_error"

    class OnexError(Exception):
        """Fallback OnexError when omnibase_core is not available"""

        def __init__(self, message: str, error_code: Optional[CoreErrorCode] = None):
            self.error_code = error_code
            super().__init__(message)


try:
    from omnibase_core.enums.enum_health_status import EnumHealthStatus
    from omnibase_core.enums.enum_publisher_type import EnumPublisherType
except ImportError:
    # Fallback for missing enums - define minimal versions
    from enum import Enum

    class EnumHealthStatus(str, Enum):
        HEALTHY = "healthy"
        DEGRADED = "degraded"
        UNHEALTHY = "unhealthy"
        UNAVAILABLE = "unavailable"
        ERROR = "error"

    class EnumPublisherType(str, Enum):
        KAFKA = "kafka"
        MEMORY = "memory"
        HYBRID = "hybrid"


from .models.model_event import ModelEvent
from .models.model_routing_context import ModelRoutingContext


# Stub classes for publishers and models that may not exist
class ModelPublisherConfig:
    """Stub for publisher config"""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        if not hasattr(self, "publisher_type"):
            self.publisher_type = EnumPublisherType.HYBRID
        if not hasattr(self, "force_publisher"):
            self.force_publisher = None
        if not hasattr(self, "fallback_to_memory"):
            self.fallback_to_memory = True
        if not hasattr(self, "environment"):
            self.environment = "development"
        if not hasattr(self, "service_name"):
            self.service_name = "intelligence"
        if not hasattr(self, "enable_hybrid_routing"):
            self.enable_hybrid_routing = True


class ModelPublisherHealth:
    """Stub for publisher health"""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def is_healthy(self):
        return hasattr(self, "status") and self.status == EnumHealthStatus.HEALTHY


class ModelSubscription:
    """Stub for subscription"""

    def __init__(self, publisher_type="memory", **kwargs):
        self.publisher_type = publisher_type
        for key, value in kwargs.items():
            setattr(self, key, value)


class InMemoryEventPublisher:
    """Stub for in-memory publisher"""

    def __init__(self, config=None):
        self.config = config
        self.is_connected = True

    async def initialize(self):
        pass

    async def publish(self, topic, event, key=None, headers=None, partition=None):
        pass

    async def publish_batch(self, topic, events, keys=None, headers=None):
        pass

    async def subscribe(
        self, topic, handler, group_id=None, from_beginning=False, auto_commit=True
    ):
        return ModelSubscription(publisher_type="memory")

    async def subscribe_batch(
        self, topics, handler, group_id=None, batch_size=100, batch_timeout_ms=1000
    ):
        return ModelSubscription(publisher_type="memory")

    async def unsubscribe(self, subscription):
        pass

    async def health_check(self):
        return ModelPublisherHealth(
            status=EnumHealthStatus.HEALTHY,
            publisher_type="memory",
            is_connected=True,
            checked_at=datetime.now(timezone.utc),
            events_published=0,
            events_failed=0,
        )

    async def get_topics(self):
        return []

    async def get_metrics(self):
        return {}

    async def shutdown(self):
        pass


# Import real Kafka publisher
try:
    from .kafka_publisher import KafkaEventPublisher

    logger_init = logging.getLogger(__name__)
    logger_init.info("Using REAL Kafka publisher for HybridEventRouter")
except ImportError:
    # Fallback to stub if import fails
    class KafkaEventPublisher(InMemoryEventPublisher):
        """Stub for Kafka publisher (fallback)"""

        def __init__(self, config=None):
            super().__init__(config)
            self.is_connected = False

    logger_init = logging.getLogger(__name__)
    logger_init.warning("Using STUB Kafka publisher (real publisher not available)")

logger = logging.getLogger(__name__)


class HybridEventRouter:
    """
    Intelligent event router that switches between Event Bus and Kafka.

    This router makes runtime decisions about which publisher to use
    based on context, configuration, and operational health.
    """

    def __init__(self, config: Optional[ModelPublisherConfig] = None):
        """
        Initialize the hybrid router.

        Args:
            config: Publisher configuration
        """
        self.config = config or self._default_config()

        # Publishers
        self._in_memory_publisher: Optional[InMemoryEventPublisher] = None
        self._kafka_publisher: Optional[KafkaEventPublisher] = None

        # Publisher health cache
        self._health_cache: Dict[str, ModelPublisherHealth] = {}
        self._health_cache_ttl = 30  # seconds
        self._last_health_check: Dict[str, datetime] = {}

        # Routing metrics
        self._routing_metrics = {
            "kafka_routes": 0,
            "memory_routes": 0,
            "fallback_routes": 0,
            "routing_errors": 0,
        }

        # Circuit breaker state
        self._kafka_circuit_breaker = {
            "failures": 0,
            "last_failure": None,
            "is_open": False,
            "failure_threshold": 5,
            "recovery_timeout": 60,  # seconds
        }

        self._initialized = False

    def _default_config(self) -> ModelPublisherConfig:
        """Create default configuration."""
        return ModelPublisherConfig(
            publisher_type=EnumPublisherType.HYBRID,
            environment="development",
            service_name="hybrid_router",
            enable_hybrid_routing=True,
            fallback_to_memory=True,
        )

    async def initialize(self, correlation_id: Optional[UUID] = None) -> None:
        """
        Initialize the router and both publishers.

        Args:
            correlation_id: Optional correlation ID for tracking

        Raises:
            OnexError: If initialization fails
        """
        correlation_id = correlation_id or uuid4()
        try:
            if self._initialized:
                return

            # Initialize in-memory publisher (always available)
            self._in_memory_publisher = InMemoryEventPublisher(self.config)
            await self._in_memory_publisher.initialize()

            # Initialize Kafka publisher (may fail if not available)
            try:
                self._kafka_publisher = KafkaEventPublisher(self.config)
                await self._kafka_publisher.initialize()
                logger.info(
                    "Kafka publisher initialized successfully",
                    extra={"correlation_id": str(correlation_id)},
                )
            except Exception as e:
                logger.warning(
                    f"Kafka publisher initialization failed: {e}",
                    extra={"correlation_id": str(correlation_id)},
                )
                if not self.config.fallback_to_memory:
                    raise
                # Continue with memory-only mode
                self._kafka_publisher = None

            self._initialized = True
            logger.info(
                f"HybridEventRouter initialized (Kafka: {'✓' if self._kafka_publisher else '✗'})",
                extra={"correlation_id": str(correlation_id)},
            )

        except Exception as e:
            raise OnexError(
                f"Failed to initialize HybridEventRouter: {str(e)}",
                error_code=CoreErrorCode.INITIALIZATION_FAILED,
            ) from e

    async def publish(
        self,
        topic: str,
        event: ModelEvent,
        key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        partition: Optional[int] = None,
        context: Optional[ModelRoutingContext] = None,
        correlation_id: Optional[UUID] = None,
    ) -> None:
        """
        Publish an event using intelligent routing.

        Args:
            topic: Topic name
            event: Event to publish
            key: Optional key
            headers: Optional headers
            partition: Optional partition
            context: Optional routing context
            correlation_id: Optional correlation ID for tracking

        Raises:
            OnexError: If publishing fails
        """
        correlation_id = correlation_id or uuid4()
        try:
            if not self._initialized:
                await self.initialize(correlation_id=correlation_id)

            # Determine which publisher to use
            publisher = await self._select_publisher(topic, event, context)

            # Attempt to publish
            try:
                await publisher.publish(topic, event, key, headers, partition)

                # Update routing metrics
                if publisher == self._kafka_publisher:
                    self._routing_metrics["kafka_routes"] += 1
                    self._reset_circuit_breaker()
                else:
                    self._routing_metrics["memory_routes"] += 1

            except Exception as e:
                # Handle publisher failure
                if (
                    publisher == self._kafka_publisher
                    and self.config.fallback_to_memory
                ):
                    logger.warning(
                        f"Kafka publish failed, falling back to memory: {e}",
                        extra={"correlation_id": str(correlation_id)},
                    )
                    self._trip_circuit_breaker()

                    # Retry with in-memory publisher
                    await self._in_memory_publisher.publish(topic, event, key, headers)
                    self._routing_metrics["fallback_routes"] += 1
                else:
                    raise

        except Exception as e:
            self._routing_metrics["routing_errors"] += 1
            logger.error(
                f"Failed to route event: {str(e)}",
                extra={"correlation_id": str(correlation_id)},
            )
            raise OnexError(
                f"Failed to route event: {str(e)}",
                error_code=CoreErrorCode.OPERATION_FAILED,
            ) from e

    async def publish_batch(
        self,
        topic: str,
        events: List[ModelEvent],
        keys: Optional[List[Optional[str]]] = None,
        headers: Optional[List[Optional[Dict[str, str]]]] = None,
        context: Optional[ModelRoutingContext] = None,
    ) -> None:
        """
        Publish batch with intelligent routing.

        Args:
            topic: Topic name
            events: Events to publish
            keys: Optional keys
            headers: Optional headers
            context: Optional routing context

        Raises:
            OnexError: If batch publishing fails
        """
        try:
            if not events:
                return

            # Use first event for routing decision
            publisher = await self._select_publisher(topic, events[0], context)

            try:
                await publisher.publish_batch(topic, events, keys, headers)

                # Update metrics
                if publisher == self._kafka_publisher:
                    self._routing_metrics["kafka_routes"] += len(events)
                    self._reset_circuit_breaker()
                else:
                    self._routing_metrics["memory_routes"] += len(events)

            except Exception as e:
                if (
                    publisher == self._kafka_publisher
                    and self.config.fallback_to_memory
                ):
                    logger.warning(f"Kafka batch failed, falling back to memory: {e}")
                    self._trip_circuit_breaker()

                    await self._in_memory_publisher.publish_batch(
                        topic, events, keys, headers
                    )
                    self._routing_metrics["fallback_routes"] += len(events)
                else:
                    raise

        except Exception as e:
            self._routing_metrics["routing_errors"] += 1
            raise OnexError(
                f"Failed to route batch: {str(e)}",
                error_code=CoreErrorCode.OPERATION_FAILED,
            ) from e

    async def subscribe(
        self,
        topic: str,
        handler: Callable[[ModelEvent], Awaitable[None]],
        group_id: Optional[str] = None,
        from_beginning: bool = False,
        auto_commit: bool = True,
        prefer_kafka: bool = False,
        context: Optional[ModelRoutingContext] = None,
    ) -> ModelSubscription:
        """
        Subscribe with intelligent routing.

        Args:
            topic: Topic name
            handler: Event handler
            group_id: Consumer group
            from_beginning: Start from beginning
            auto_commit: Auto-commit offsets
            prefer_kafka: Prefer Kafka if available
            context: Routing context

        Returns:
            Subscription object

        Raises:
            OnexError: If subscription fails
        """
        try:
            if not self._initialized:
                await self.initialize()

            # Determine publisher for subscription
            if (
                prefer_kafka
                and self._kafka_publisher
                and not self._is_circuit_breaker_open()
            ):
                try:
                    return await self._kafka_publisher.subscribe(
                        topic, handler, group_id, from_beginning, auto_commit
                    )
                except Exception as e:
                    logger.warning(f"Kafka subscribe failed, using memory: {e}")

            # Use in-memory publisher
            return await self._in_memory_publisher.subscribe(
                topic, handler, group_id, from_beginning, auto_commit
            )

        except Exception as e:
            raise OnexError(
                f"Failed to subscribe: {str(e)}",
                error_code=CoreErrorCode.OPERATION_FAILED,
            ) from e

    async def subscribe_batch(
        self,
        topics: List[str],
        handler: Callable[[List[ModelEvent]], Awaitable[None]],
        group_id: Optional[str] = None,
        batch_size: int = 100,
        batch_timeout_ms: int = 1000,
        prefer_kafka: bool = False,
    ) -> ModelSubscription:
        """
        Batch subscribe with routing.

        Args:
            topics: Topic names
            handler: Batch handler
            group_id: Consumer group
            batch_size: Max batch size
            batch_timeout_ms: Batch timeout
            prefer_kafka: Prefer Kafka

        Returns:
            Subscription object
        """
        try:
            if not self._initialized:
                await self.initialize()

            if (
                prefer_kafka
                and self._kafka_publisher
                and not self._is_circuit_breaker_open()
            ):
                try:
                    return await self._kafka_publisher.subscribe_batch(
                        topics, handler, group_id, batch_size, batch_timeout_ms
                    )
                except Exception as e:
                    logger.warning(f"Kafka batch subscribe failed, using memory: {e}")

            return await self._in_memory_publisher.subscribe_batch(
                topics, handler, group_id, batch_size, batch_timeout_ms
            )

        except Exception as e:
            raise OnexError(
                f"Failed to batch subscribe: {str(e)}",
                error_code=CoreErrorCode.OPERATION_FAILED,
            ) from e

    async def unsubscribe(self, subscription: ModelSubscription) -> None:
        """
        Unsubscribe from the appropriate publisher.

        Args:
            subscription: Subscription to cancel
        """
        if subscription.publisher_type == "kafka" and self._kafka_publisher:
            await self._kafka_publisher.unsubscribe(subscription)
        else:
            await self._in_memory_publisher.unsubscribe(subscription)

    async def health_check(self) -> ModelPublisherHealth:
        """
        Get aggregated health status.

        Returns:
            Combined health status
        """
        try:
            memory_health = await self._get_cached_health("memory")
            kafka_health = (
                await self._get_cached_health("kafka")
                if self._kafka_publisher
                else None
            )

            # Determine overall health
            if kafka_health and kafka_health.is_healthy():
                overall_status = EnumHealthStatus.HEALTHY
            elif memory_health.is_healthy():
                overall_status = EnumHealthStatus.DEGRADED  # Memory only
            else:
                overall_status = EnumHealthStatus.UNHEALTHY

            return ModelPublisherHealth(
                status=overall_status,
                publisher_type="hybrid",
                is_connected=memory_health.is_connected,
                checked_at=datetime.now(timezone.utc),
                events_published=(
                    memory_health.events_published
                    + (kafka_health.events_published if kafka_health else 0)
                ),
                events_failed=(
                    memory_health.events_failed
                    + (kafka_health.events_failed if kafka_health else 0)
                ),
                connection_details={
                    "memory_health": memory_health.status.value,
                    "kafka_health": (
                        kafka_health.status.value if kafka_health else "unavailable"
                    ),
                    "circuit_breaker_open": self._is_circuit_breaker_open(),
                    "routing_metrics": self._routing_metrics,
                },
            )

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return ModelPublisherHealth(
                status=EnumHealthStatus.ERROR,
                publisher_type="hybrid",
                is_connected=False,
                checked_at=datetime.now(timezone.utc),
                last_error=str(e),
            )

    async def get_topics(self) -> List[str]:
        """
        Get topics from all publishers.

        Returns:
            Combined list of topics
        """
        topics = set()

        if self._in_memory_publisher:
            memory_topics = await self._in_memory_publisher.get_topics()
            topics.update(memory_topics)

        if self._kafka_publisher and not self._is_circuit_breaker_open():
            try:
                kafka_topics = await self._kafka_publisher.get_topics()
                topics.update(kafka_topics)
            except Exception as e:
                logger.warning(f"Failed to get Kafka topics: {e}")

        return list(topics)

    async def get_metrics(self) -> Dict[str, float]:
        """
        Get combined metrics from all publishers.

        Returns:
            Aggregated metrics
        """
        metrics = self._routing_metrics.copy()

        if self._in_memory_publisher:
            memory_metrics = await self._in_memory_publisher.get_metrics()
            for key, value in memory_metrics.items():
                metrics[f"memory_{key}"] = value

        if self._kafka_publisher:
            try:
                kafka_metrics = await self._kafka_publisher.get_metrics()
                for key, value in kafka_metrics.items():
                    metrics[f"kafka_{key}"] = value
            except Exception as e:
                logger.warning(f"Failed to get Kafka metrics: {e}")

        return metrics

    async def shutdown(self) -> None:
        """
        Shutdown all publishers.

        Raises:
            OnexError: If shutdown fails
        """
        try:
            logger.info("Shutting down HybridEventRouter")

            # Shutdown publishers
            if self._in_memory_publisher:
                await self._in_memory_publisher.shutdown()

            if self._kafka_publisher:
                await self._kafka_publisher.shutdown()

            self._initialized = False
            logger.info("HybridEventRouter shutdown complete")

        except Exception as e:
            raise OnexError(
                f"Failed to shutdown: {str(e)}", error_code=CoreErrorCode.SHUTDOWN_ERROR
            ) from e

    @property
    def publisher_type(self) -> str:
        """Get publisher type."""
        return "hybrid"

    @property
    def is_connected(self) -> bool:
        """Check if at least one publisher is connected."""
        memory_connected = (
            self._in_memory_publisher and self._in_memory_publisher.is_connected
        )
        kafka_connected = self._kafka_publisher and self._kafka_publisher.is_connected
        return bool(memory_connected or kafka_connected)

    # Private helper methods

    async def _select_publisher(
        self,
        topic: str,
        event: ModelEvent,
        context: Optional[ModelRoutingContext] = None,
    ) -> Union[InMemoryEventPublisher, KafkaEventPublisher]:
        """
        Select the appropriate publisher based on routing logic.

        Args:
            topic: Topic name
            event: Event to publish
            context: Optional routing context

        Returns:
            Selected publisher
        """
        # Check for forced publisher override
        if self.config.force_publisher:
            if (
                self.config.force_publisher == EnumPublisherType.KAFKA
                and self._kafka_publisher
                and not self._is_circuit_breaker_open()
            ):
                return self._kafka_publisher
            return self._in_memory_publisher

        # Circuit breaker check
        if self._is_circuit_breaker_open():
            logger.debug("Circuit breaker open, using in-memory publisher")
            return self._in_memory_publisher

        # Context-based routing
        if context:
            if context.is_test_environment:
                return self._in_memory_publisher

            if context.requires_persistence and self._kafka_publisher:
                return self._kafka_publisher

            if context.is_cross_service and self._kafka_publisher:
                return self._kafka_publisher

            if context.is_local_tool:
                return self._in_memory_publisher

        # Event-based routing
        intelligence_topics = ["intelligence", "capture", "analysis", "metadata"]
        if any(keyword in topic.lower() for keyword in intelligence_topics):
            if self._kafka_publisher:
                return self._kafka_publisher

        # High priority events prefer Kafka for persistence
        if (
            hasattr(event, "priority")
            and event.priority in ["CRITICAL", "HIGH"]
            and self._kafka_publisher
        ):
            return self._kafka_publisher

        # Environment-based routing
        if self.config.environment == "production" and self._kafka_publisher:
            return self._kafka_publisher

        if self.config.environment in ["development", "test"]:
            return self._in_memory_publisher

        # Default fallback
        if self._kafka_publisher and not self._is_circuit_breaker_open():
            return self._kafka_publisher

        return self._in_memory_publisher

    async def _get_cached_health(self, publisher_type: str) -> ModelPublisherHealth:
        """
        Get cached health status for a publisher.

        Args:
            publisher_type: Publisher type (memory or kafka)

        Returns:
            Health status
        """
        now = datetime.now(timezone.utc)

        # Check cache
        if (
            publisher_type in self._health_cache
            and publisher_type in self._last_health_check
        ):
            cache_age = (now - self._last_health_check[publisher_type]).total_seconds()
            if cache_age < self._health_cache_ttl:
                return self._health_cache[publisher_type]

        # Refresh cache
        if publisher_type == "memory" and self._in_memory_publisher:
            health = await self._in_memory_publisher.health_check()
        elif publisher_type == "kafka" and self._kafka_publisher:
            health = await self._kafka_publisher.health_check()
        else:
            health = ModelPublisherHealth(
                status=EnumHealthStatus.UNAVAILABLE,
                publisher_type=publisher_type,
                is_connected=False,
                checked_at=now,
            )

        self._health_cache[publisher_type] = health
        self._last_health_check[publisher_type] = now

        return health

    def _is_circuit_breaker_open(self) -> bool:
        """
        Check if the Kafka circuit breaker is open.

        Returns:
            True if circuit breaker is open
        """
        if not self._kafka_circuit_breaker["is_open"]:
            return False

        # Check if recovery timeout has passed
        if self._kafka_circuit_breaker["last_failure"]:
            elapsed = (
                datetime.now(timezone.utc) - self._kafka_circuit_breaker["last_failure"]
            ).total_seconds()
            if elapsed > self._kafka_circuit_breaker["recovery_timeout"]:
                logger.info(
                    "Circuit breaker recovery timeout reached, attempting reset"
                )
                self._reset_circuit_breaker()
                return False

        return True

    def _trip_circuit_breaker(self) -> None:
        """Trip the circuit breaker due to Kafka failure."""
        self._kafka_circuit_breaker["failures"] += 1
        self._kafka_circuit_breaker["last_failure"] = datetime.now(timezone.utc)

        if (
            self._kafka_circuit_breaker["failures"]
            >= self._kafka_circuit_breaker["failure_threshold"]
        ):
            self._kafka_circuit_breaker["is_open"] = True
            logger.warning("Kafka circuit breaker tripped - using memory fallback")

    def _reset_circuit_breaker(self) -> None:
        """Reset the circuit breaker after successful operation."""
        if self._kafka_circuit_breaker["failures"] > 0:
            self._kafka_circuit_breaker["failures"] = 0
            self._kafka_circuit_breaker["is_open"] = False
            logger.info("Circuit breaker reset - Kafka operations resumed")
