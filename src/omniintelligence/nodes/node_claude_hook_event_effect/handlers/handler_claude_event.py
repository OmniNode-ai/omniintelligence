# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler for Claude Code hook event processing.

This module provides HandlerClaudeHookEvent, a handler class that processes
Claude Code hook events with explicit dependency injection via constructor.

Design Principles:
    - Dependencies injected via constructor (NO setters)
    - Kafka publisher is REQUIRED for full functionality
    - Intent classifier is OPTIONAL
    - Pure handler functions for processing logic
    - Event type routing via pattern matching

Reference:
    - OMN-1456: Unified Claude Code hook endpoint
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol, runtime_checkable
from uuid import UUID

from omniintelligence.nodes.node_claude_hook_event_effect.models import (
    EnumClaudeCodeHookEventType,
    EnumHookProcessingStatus,
    EnumKafkaEmissionStatus,
    ModelClaudeCodeHookEvent,
    ModelClaudeCodeHookEventPayload,
    ModelClaudeHookResult,
    ModelIntentResult,
)

if TYPE_CHECKING:
    from omniintelligence.nodes.node_intent_classifier_compute.models import (
        ModelIntentClassificationInput,
        ModelIntentClassificationOutput,
    )


# =============================================================================
# Protocol Definitions
# =============================================================================


@runtime_checkable
class ProtocolIntentClassifier(Protocol):
    """Protocol for intent classifier compute nodes.

    Defines the interface expected by handler functions for classifying
    user prompts. Any compute node implementing this protocol can be used
    as an intent classifier.
    """

    async def compute(
        self,
        input_data: ModelIntentClassificationInput,
    ) -> ModelIntentClassificationOutput:
        """Classify the intent of user input."""
        ...


@runtime_checkable
class ProtocolKafkaPublisher(Protocol):
    """Protocol for Kafka event publishers.

    Defines a simplified interface for publishing events to Kafka topics.
    """

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, object],
    ) -> None:
        """Publish an event to a Kafka topic."""
        ...


# =============================================================================
# Handler Class (Declarative Pattern with Constructor Injection)
# =============================================================================


class HandlerClaudeHookEvent:
    """Handler for Claude Code hook events with constructor-injected dependencies.

    This handler processes Claude Code hook events by routing them to
    appropriate sub-handlers based on event type. Dependencies are
    injected via constructor - no setters, no container lookups.

    Attributes:
        kafka_publisher: Kafka publisher for event emission (REQUIRED for full functionality).
        intent_classifier: Intent classifier compute node (OPTIONAL).
        publish_topic: Full Kafka publish topic from contract (OPTIONAL).

    Example:
        >>> handler = HandlerClaudeHookEvent(
        ...     kafka_publisher=kafka_producer,
        ...     intent_classifier=classifier,
        ...     publish_topic="onex.evt.omniintelligence.intent-classified.v1",
        ... )
        >>> result = await handler.handle(event)
    """

    def __init__(
        self,
        *,
        kafka_publisher: ProtocolKafkaPublisher,
        intent_classifier: ProtocolIntentClassifier | None = None,
        publish_topic: str | None = None,
    ) -> None:
        """Initialize handler with explicit dependencies.

        Args:
            kafka_publisher: REQUIRED Kafka publisher for event emission.
            intent_classifier: Optional intent classifier compute node.
            publish_topic: Full Kafka topic for publishing classified intents.
                Source of truth is the contract's event_bus.publish_topics.

        Raises:
            ValueError: If kafka_publisher is None.
        """
        if kafka_publisher is None:
            raise ValueError("kafka_publisher is required")

        self._kafka_publisher = kafka_publisher
        self._intent_classifier = intent_classifier
        self._publish_topic = publish_topic

    @property
    def kafka_publisher(self) -> ProtocolKafkaPublisher:
        """Get the Kafka publisher."""
        return self._kafka_publisher

    @property
    def intent_classifier(self) -> ProtocolIntentClassifier | None:
        """Get the intent classifier if configured."""
        return self._intent_classifier

    @property
    def publish_topic(self) -> str | None:
        """Get the Kafka publish topic."""
        return self._publish_topic

    async def handle(self, event: ModelClaudeCodeHookEvent) -> ModelClaudeHookResult:
        """Handle a Claude Code hook event.

        Routes the event to the appropriate handler based on event_type
        and returns the processing result.

        Args:
            event: The Claude Code hook event to process.

        Returns:
            ModelClaudeHookResult with processing outcome.
        """
        return await route_hook_event(
            event=event,
            intent_classifier=self._intent_classifier,
            kafka_producer=self._kafka_publisher,
            publish_topic=self._publish_topic,
        )


# =============================================================================
# Handler Functions (Pure Logic - Backward Compatible)
# =============================================================================


async def route_hook_event(
    event: ModelClaudeCodeHookEvent,
    *,
    intent_classifier: ProtocolIntentClassifier | None = None,
    kafka_producer: ProtocolKafkaPublisher | None = None,
    publish_topic: str | None = None,
) -> ModelClaudeHookResult:
    """Route a Claude Code hook event to the appropriate handler.

    This is the main entry point for processing hook events. It routes
    based on event_type to specialized handlers.

    Args:
        event: The Claude Code hook event to process.
        intent_classifier: Optional intent classifier compute node implementing
            ProtocolIntentClassifier.
        kafka_producer: Optional Kafka producer implementing ProtocolKafkaPublisher.
        publish_topic: Full Kafka topic for publishing classified intents.
            Source of truth is the contract's event_bus.publish_topics.

    Returns:
        ModelClaudeHookResult with processing outcome.
    """
    start_time = time.perf_counter()

    try:
        # Route based on event type
        if event.event_type == EnumClaudeCodeHookEventType.USER_PROMPT_SUBMIT:
            result = await handle_user_prompt_submit(
                event=event,
                intent_classifier=intent_classifier,
                kafka_producer=kafka_producer,
                publish_topic=publish_topic,
            )
        else:
            # All other event types are no-op for now
            result = handle_no_op(event)

        # Update processing time
        processing_time_ms = (time.perf_counter() - start_time) * 1000

        # Return result with updated processing time
        return ModelClaudeHookResult(
            status=result.status,
            event_type=result.event_type,
            session_id=result.session_id,
            correlation_id=result.correlation_id,
            intent_result=result.intent_result,
            processing_time_ms=processing_time_ms,
            processed_at=datetime.now(UTC),
            error_message=result.error_message,
            metadata=result.metadata,
        )

    except Exception as e:
        processing_time_ms = (time.perf_counter() - start_time) * 1000
        return ModelClaudeHookResult(
            status=EnumHookProcessingStatus.FAILED,
            event_type=str(event.event_type),
            session_id=event.session_id,
            correlation_id=event.correlation_id,
            processing_time_ms=processing_time_ms,
            processed_at=datetime.now(UTC),
            error_message=str(e),
            metadata={"exception_type": type(e).__name__},
        )


def handle_no_op(event: ModelClaudeCodeHookEvent) -> ModelClaudeHookResult:
    """Handle event types that are not yet implemented.

    Returns success without performing any processing.

    Args:
        event: The Claude Code hook event.

    Returns:
        ModelClaudeHookResult with status=success and no intent_result.
    """
    return ModelClaudeHookResult(
        status=EnumHookProcessingStatus.SUCCESS,
        event_type=str(event.event_type),
        session_id=event.session_id,
        correlation_id=event.correlation_id,
        intent_result=None,
        processing_time_ms=0.0,
        processed_at=datetime.now(UTC),
        error_message=None,
        metadata={"handler": "no_op", "reason": "event_type not yet implemented"},
    )


def _extract_prompt_from_payload(
    payload: ModelClaudeCodeHookEventPayload,
) -> tuple[str, str]:
    """Extract the user prompt from a hook event payload.

    Args:
        payload: The hook event payload to extract from.

    Returns:
        A tuple of (prompt, extraction_source).
    """
    # Strategy 1: Try direct attribute access
    payload_class = type(payload)
    if (
        hasattr(payload_class, "model_fields")
        and "prompt" in payload_class.model_fields
    ):
        direct_value = getattr(payload, "prompt", None)
        if direct_value is not None and direct_value != "":
            return str(direct_value), "direct_attribute"

    # Strategy 2: Extract from model_extra
    if payload.model_extra:
        prompt_value = payload.model_extra.get("prompt")
        if prompt_value is not None and prompt_value != "":
            return str(prompt_value), "model_extra"

    # Strategy 3: Not found
    return "", "not_found"


def _determine_processing_status(
    emitted_to_kafka: bool,
    kafka_producer: ProtocolKafkaPublisher | None,
    publish_topic: str | None,
) -> EnumHookProcessingStatus:
    """Determine the overall processing status based on Kafka emission outcome.

    This helper encapsulates the status determination logic which has three
    possible outcomes based on the Kafka emission state and configuration.

    Status Logic:
    -------------
    - SUCCESS: Either Kafka emission succeeded, OR Kafka was not configured
      (no producer or no publish topic). In the latter case, we successfully
      completed everything that was configured to run.

    - PARTIAL: Kafka emission failed despite having both a producer AND topic
      configured. This indicates the handler partially succeeded
      (intent classification worked) but the downstream emission failed.

    Args:
        emitted_to_kafka: Whether the event was successfully emitted to Kafka.
        kafka_producer: The Kafka producer, or None if not configured.
        publish_topic: The full publish topic, or None if not configured.

    Returns:
        EnumHookProcessingStatus.SUCCESS if emission succeeded or was not
        configured, EnumHookProcessingStatus.PARTIAL if emission was
        configured but failed.
    """
    # If we successfully emitted, always return success
    if emitted_to_kafka:
        return EnumHookProcessingStatus.SUCCESS

    # If emission failed but Kafka was fully configured (both producer and topic),
    # mark as partial - we completed classification but failed on emission
    if kafka_producer is not None and publish_topic is not None:
        return EnumHookProcessingStatus.PARTIAL

    # Kafka was not fully configured, so we successfully completed what was asked
    return EnumHookProcessingStatus.SUCCESS


async def handle_user_prompt_submit(
    event: ModelClaudeCodeHookEvent,
    *,
    intent_classifier: ProtocolIntentClassifier | None = None,
    kafka_producer: ProtocolKafkaPublisher | None = None,
    publish_topic: str | None = None,
) -> ModelClaudeHookResult:
    """Handle UserPromptSubmit events with intent classification.

    This handler:
    1. Extracts the prompt from the payload
    2. Calls intent_classifier_compute to classify the intent
    3. Emits the classified intent to Kafka

    Args:
        event: The UserPromptSubmit hook event.
        intent_classifier: Intent classifier compute node implementing
            ProtocolIntentClassifier (optional for testing).
        kafka_producer: Kafka producer implementing ProtocolKafkaPublisher (optional).
        publish_topic: Full Kafka topic for publishing classified intents.
            Source of truth is the contract's event_bus.publish_topics.

    Returns:
        ModelClaudeHookResult with intent classification results.
    """
    metadata: dict[str, str] = {"handler": "user_prompt_submit"}

    # Extract prompt from payload
    prompt, extraction_source = _extract_prompt_from_payload(event.payload)
    metadata["prompt_extraction_source"] = extraction_source

    if not prompt:
        return ModelClaudeHookResult(
            status=EnumHookProcessingStatus.FAILED,
            event_type=str(event.event_type),
            session_id=event.session_id,
            correlation_id=event.correlation_id,
            intent_result=None,
            processing_time_ms=0.0,
            processed_at=datetime.now(UTC),
            error_message="No prompt found in payload",
            metadata=metadata,
        )

    # Step 1: Classify intent (if classifier available)
    intent_category = "unknown"
    confidence = 0.0
    keywords: list[str] = []
    secondary_intents: list[dict[str, object]] = []

    if intent_classifier is not None:
        try:
            classification_result = await _classify_intent(
                prompt=prompt,
                session_id=event.session_id,
                correlation_id=event.correlation_id,
                classifier=intent_classifier,
            )
            intent_category = classification_result.get("intent_category", "unknown")
            confidence = classification_result.get("confidence", 0.0)
            keywords = classification_result.get("keywords", [])
            secondary_intents = classification_result.get("secondary_intents", [])
            metadata["classification_source"] = "intent_classifier_compute"
        except Exception as e:
            metadata["classification_error"] = str(e)
            metadata["classification_source"] = "fallback_unknown"
    else:
        metadata["classification_source"] = "no_classifier_available"

    # Step 2: Emit to Kafka (if producer and topic available)
    # Graph storage is handled downstream by omnimemory consuming this event
    emitted_to_kafka = False
    if kafka_producer is not None and publish_topic is not None:
        try:
            await _emit_intent_to_kafka(
                session_id=event.session_id,
                intent_category=intent_category,
                confidence=confidence,
                keywords=keywords,
                correlation_id=event.correlation_id,
                producer=kafka_producer,
                topic=publish_topic,
            )
            emitted_to_kafka = True
            metadata["kafka_emission"] = EnumKafkaEmissionStatus.SUCCESS.value
            metadata["kafka_topic"] = publish_topic
        except Exception as e:
            metadata["kafka_emission_error"] = str(e)
            metadata["kafka_emission"] = EnumKafkaEmissionStatus.FAILED.value
    elif kafka_producer is None:
        metadata["kafka_emission"] = EnumKafkaEmissionStatus.NO_PRODUCER.value
    else:
        metadata["kafka_emission"] = EnumKafkaEmissionStatus.NO_TOPIC.value

    # Build intent result
    intent_result = ModelIntentResult(
        intent_category=intent_category,
        confidence=confidence,
        keywords=keywords,
        secondary_intents=secondary_intents,
        emitted_to_kafka=emitted_to_kafka,
    )

    # Determine overall status using helper for clarity
    status = _determine_processing_status(
        emitted_to_kafka=emitted_to_kafka,
        kafka_producer=kafka_producer,
        publish_topic=publish_topic,
    )

    return ModelClaudeHookResult(
        status=status,
        event_type=str(event.event_type),
        session_id=event.session_id,
        correlation_id=event.correlation_id,
        intent_result=intent_result,
        processing_time_ms=0.0,
        processed_at=datetime.now(UTC),
        error_message=None,
        metadata=metadata,
    )


async def _classify_intent(
    prompt: str,
    session_id: str,
    correlation_id: UUID,
    classifier: ProtocolIntentClassifier,
) -> dict[str, object]:
    """Call the intent classifier compute node.

    Args:
        prompt: The user prompt to classify.
        session_id: Session ID for context.
        correlation_id: Correlation ID for tracing.
        classifier: Intent classifier.

    Returns:
        Dict with intent_category, confidence, keywords, and secondary_intents.
    """
    from omniintelligence.nodes.node_intent_classifier_compute.models import (
        ModelIntentClassificationInput,
    )

    input_data = ModelIntentClassificationInput(
        content=prompt,
        correlation_id=correlation_id,
        context={
            "session_id": session_id,
            "source_system": "claude_hook_event_effect",
        },
    )

    result = await classifier.compute(input_data)

    return {
        "intent_category": result.intent_category,
        "confidence": result.confidence,
        "keywords": list(result.keywords) if result.keywords else [],
        "secondary_intents": [
            {
                "intent_category": si.get("intent_category", "unknown"),
                "confidence": si.get("confidence", 0.0),
                "keywords": list(si.get("keywords", [])),
            }
            for si in (result.secondary_intents or [])
        ],
    }


async def _emit_intent_to_kafka(
    session_id: str,
    intent_category: str,
    confidence: float,
    keywords: list[str],
    correlation_id: UUID,
    producer: ProtocolKafkaPublisher,
    *,
    topic: str,
) -> None:
    """Emit the classified intent to Kafka.

    Args:
        session_id: Session ID.
        intent_category: Classified intent category.
        confidence: Classification confidence.
        keywords: Keywords extracted from intent classification.
        correlation_id: Correlation ID for tracing.
        producer: Kafka producer implementing ProtocolKafkaPublisher.
        topic: Full Kafka topic name for intent classification events.
            Source of truth is the contract's event_bus.publish_topics.
    """
    event_payload = {
        "event_type": "IntentClassified",
        "session_id": session_id,
        "correlation_id": str(correlation_id),
        "intent_category": intent_category,
        "confidence": confidence,
        "keywords": keywords,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    await producer.publish(
        topic=topic,
        key=session_id,
        value=event_payload,
    )


__all__ = [
    "HandlerClaudeHookEvent",
    "ProtocolIntentClassifier",
    "ProtocolKafkaPublisher",
    "handle_no_op",
    "handle_user_prompt_submit",
    "route_hook_event",
]
