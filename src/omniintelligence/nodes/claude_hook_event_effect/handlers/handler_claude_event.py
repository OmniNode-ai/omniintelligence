# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler functions for Claude Code hook event routing.

This module contains pure handler functions for processing Claude Code hook
events. The handlers are designed to be side-effect-free where possible,
with external I/O delegated to adapters passed as parameters.

Design Principles:
    - Pure functions where possible
    - Side effects via injected adapters
    - Event type routing via pattern matching
    - No-op handlers return success for unimplemented event types

Reference:
    - OMN-1456: Unified Claude Code hook endpoint
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import UUID

from omniintelligence.constants import ONEX_EVT_OMNIINTELLIGENCE_INTENT_CLASSIFIED_V1
from omniintelligence.nodes.claude_hook_event_effect.models import (
    EnumClaudeCodeHookEventType,
    EnumHookProcessingStatus,
    ModelClaudeCodeHookEvent,
    ModelClaudeCodeHookEventPayload,
    ModelClaudeHookResult,
    ModelIntentResult,
)

if TYPE_CHECKING:
    from omniintelligence.nodes.intent_classifier_compute.models import (
        ModelIntentClassificationInput,
        ModelIntentClassificationOutput,
    )


# =============================================================================
# Local Protocol Definitions
# =============================================================================
# These protocols define the expected interfaces for injected dependencies.
# They are defined locally to avoid coupling to specific implementations while
# providing proper type hints for static analysis.
#
# Note: The contract.yaml references ProtocolKafkaProducer from
# omnibase_infra.protocols.protocol_kafka_producer, but this protocol doesn't
# exist yet. Once it's implemented, these local protocols can be replaced with
# imports from that module.
# =============================================================================


@runtime_checkable
class ProtocolIntentClassifier(Protocol):
    """Protocol for intent classifier compute nodes.

    Defines the interface expected by handler functions for classifying
    user prompts. Any compute node implementing this protocol can be used
    as an intent classifier.

    The protocol matches the interface of NodeIntentClassifierCompute from
    omniintelligence.nodes.intent_classifier_compute.
    """

    async def compute(
        self,
        input_data: ModelIntentClassificationInput,
    ) -> ModelIntentClassificationOutput:
        """Classify the intent of user input.

        Args:
            input_data: Classification input containing content and context.

        Returns:
            Classification output with intent category, confidence, and
            optional secondary intents.
        """
        ...


@runtime_checkable
class ProtocolKafkaPublisher(Protocol):
    """Protocol for Kafka event publishers.

    Defines a simplified interface for publishing events to Kafka topics.
    This protocol uses a dict-based value for flexibility, with serialization
    handled by the implementation.

    Note: This is a simplified interface. For production use, consider using
    ProtocolEventPublisher from omnibase_spi.protocols.event_bus which
    provides additional reliability features (retries, circuit breaker, DLQ).
    """

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, Any],
    ) -> None:
        """Publish an event to a Kafka topic.

        Args:
            topic: Target Kafka topic name.
            key: Message key for partitioning.
            value: Event payload as a dictionary (serialized by implementation).
        """
        ...


async def route_hook_event(
    event: ModelClaudeCodeHookEvent,
    *,
    intent_classifier: ProtocolIntentClassifier | None = None,
    kafka_producer: ProtocolKafkaPublisher | None = None,
    topic_env_prefix: str = "dev",
) -> ModelClaudeHookResult:
    """Route a Claude Code hook event to the appropriate handler.

    This is the main entry point for processing hook events. It routes
    based on event_type to specialized handlers.

    Args:
        event: The Claude Code hook event to process.
        intent_classifier: Optional intent classifier compute node implementing
            ProtocolIntentClassifier.
        kafka_producer: Optional Kafka producer implementing ProtocolKafkaPublisher.
        topic_env_prefix: Environment prefix for Kafka topic (e.g., "dev", "prod").

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
                topic_env_prefix=topic_env_prefix,
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

    Returns success without performing any processing. This allows the
    pipeline shape to be stable while handlers are incrementally added.

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

    This helper encapsulates the prompt extraction logic and documents the
    payload contract dependency. The prompt field location depends on how
    ModelClaudeCodeHookEventPayload is configured in omnibase_core.

    Payload Contract (omnibase_core.models.hooks.claude_code):
    ----------------------------------------------------------
    ModelClaudeCodeHookEventPayload uses Pydantic's extra="allow" configuration,
    which means fields not explicitly defined in the model (like "prompt") are
    stored in the model_extra dict. This is intentional to support extensible
    payloads without schema changes.

    Expected payload structure for UserPromptSubmit:
        {
            "prompt": "user's input text",
            ... other optional fields ...
        }

    Extraction Strategy:
    1. First, try direct attribute access (future-proofing if prompt becomes
       a declared field)
    2. Fall back to model_extra dict access (current behavior)
    3. Return empty string if neither source has the prompt

    Args:
        payload: The hook event payload to extract from.

    Returns:
        A tuple of (prompt, extraction_source) where:
        - prompt: The extracted prompt string, or empty string if not found
        - extraction_source: One of "direct_attribute", "model_extra", or
          "not_found" indicating how the prompt was obtained
    """
    # Strategy 1: Try direct attribute access (future-proof for schema changes)
    # If ModelClaudeCodeHookEventPayload ever adds "prompt" as a declared field,
    # this will automatically use it without code changes.
    # Note: Access model_fields on the class (not instance) per Pydantic V2.11+
    payload_class = type(payload)
    if hasattr(payload_class, "model_fields") and "prompt" in payload_class.model_fields:
        direct_value = getattr(payload, "prompt", None)
        if direct_value is not None and direct_value != "":
            return str(direct_value), "direct_attribute"

    # Strategy 2: Extract from model_extra (current behavior with extra="allow")
    if payload.model_extra:
        prompt_value = payload.model_extra.get("prompt")
        if prompt_value is not None and prompt_value != "":
            return str(prompt_value), "model_extra"

    # Strategy 3: Not found in any source
    return "", "not_found"


async def handle_user_prompt_submit(
    event: ModelClaudeCodeHookEvent,
    *,
    intent_classifier: ProtocolIntentClassifier | None = None,
    kafka_producer: ProtocolKafkaPublisher | None = None,
    topic_env_prefix: str = "dev",
) -> ModelClaudeHookResult:
    """Handle UserPromptSubmit events with intent classification.

    This handler:
    1. Extracts the prompt from the payload
    2. Calls intent_classifier_compute to classify the intent
    3. Emits the classified intent to Kafka

    Graph storage is handled downstream by omnimemory consuming the Kafka event.
    This keeps omniintelligence decoupled from omnimemory.

    Args:
        event: The UserPromptSubmit hook event.
        intent_classifier: Intent classifier compute node implementing
            ProtocolIntentClassifier (optional for testing).
        kafka_producer: Kafka producer implementing ProtocolKafkaPublisher (optional).
        topic_env_prefix: Environment prefix for Kafka topic (e.g., "dev", "prod").

    Returns:
        ModelClaudeHookResult with intent classification results.
    """
    metadata: dict[str, Any] = {"handler": "user_prompt_submit"}

    # Extract prompt from payload using robust helper
    # See _extract_prompt_from_payload docstring for payload contract details
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
    secondary_intents: list[dict[str, Any]] = []

    if intent_classifier is not None:
        try:
            # Call the intent classifier compute node
            classification_result = await _classify_intent(
                prompt=prompt,
                session_id=event.session_id,
                correlation_id=event.correlation_id,
                classifier=intent_classifier,
            )
            intent_category = classification_result.get("intent_category", "unknown")
            confidence = classification_result.get("confidence", 0.0)
            secondary_intents = classification_result.get("secondary_intents", [])
            metadata["classification_source"] = "intent_classifier_compute"
        except Exception as e:
            metadata["classification_error"] = str(e)
            metadata["classification_source"] = "fallback_unknown"
    else:
        metadata["classification_source"] = "no_classifier_available"

    # Step 2: Emit to Kafka (if producer available)
    # Graph storage is handled downstream by omnimemory consuming this event
    emitted_to_kafka = False
    if kafka_producer is not None:
        try:
            await _emit_intent_to_kafka(
                session_id=event.session_id,
                intent_category=intent_category,
                confidence=confidence,
                correlation_id=event.correlation_id,
                producer=kafka_producer,
                topic_env_prefix=topic_env_prefix,
            )
            emitted_to_kafka = True
            metadata["kafka_emission"] = "success"
        except Exception as e:
            metadata["kafka_emission_error"] = str(e)
            metadata["kafka_emission"] = "failed"
    else:
        metadata["kafka_emission"] = "no_producer_available"

    # Build intent result
    intent_result = ModelIntentResult(
        intent_category=intent_category,
        confidence=confidence,
        secondary_intents=secondary_intents,
        emitted_to_kafka=emitted_to_kafka,
    )

    # Determine overall status
    status = EnumHookProcessingStatus.SUCCESS
    if not emitted_to_kafka and kafka_producer is not None:
        status = EnumHookProcessingStatus.PARTIAL

    return ModelClaudeHookResult(
        status=status,
        event_type=str(event.event_type),
        session_id=event.session_id,
        correlation_id=event.correlation_id,
        intent_result=intent_result,
        processing_time_ms=0.0,  # Placeholder - caller creates final result with actual time
        processed_at=datetime.now(UTC),
        error_message=None,
        metadata=metadata,
    )


async def _classify_intent(
    prompt: str,
    session_id: str,
    correlation_id: UUID,
    classifier: ProtocolIntentClassifier,
) -> dict[str, Any]:
    """Call the intent classifier compute node.

    Args:
        prompt: The user prompt to classify.
        session_id: Session ID for context.
        correlation_id: Correlation ID for tracing.
        classifier: Intent classifier implementing ProtocolIntentClassifier.

    Returns:
        Dict with intent_category, confidence, and secondary_intents.
    """
    # Import here to avoid circular imports
    from omniintelligence.nodes.intent_classifier_compute.models import (
        ModelIntentClassificationInput,
    )

    # Create input for classifier
    # Note: IntentContextDict uses 'source_system' not 'source'
    input_data = ModelIntentClassificationInput(
        content=prompt,
        correlation_id=correlation_id,
        context={
            "session_id": session_id,
            "source_system": "claude_hook_event_effect",
        },
    )

    # Call classifier (assuming it has a compute method)
    result = await classifier.compute(input_data)

    return {
        "intent_category": result.intent_category,
        "confidence": result.confidence,
        "secondary_intents": [
            {
                "intent_category": si.intent_category,
                "confidence": si.confidence,
            }
            for si in (result.secondary_intents or [])
        ],
    }


async def _emit_intent_to_kafka(
    session_id: str,
    intent_category: str,
    confidence: float,
    correlation_id: UUID,
    producer: ProtocolKafkaPublisher,
    *,
    topic_env_prefix: str = "dev",
) -> None:
    """Emit the classified intent to Kafka.

    Args:
        session_id: Session ID.
        intent_category: Classified intent category.
        confidence: Classification confidence.
        correlation_id: Correlation ID for tracing.
        producer: Kafka producer implementing ProtocolKafkaPublisher.
        topic_env_prefix: Environment prefix for Kafka topic (e.g., "dev", "prod").
    """
    # Build topic name with environment prefix using ONEX naming convention
    # Constant imported from omniintelligence.constants (temporary - see OMN-1546)
    topic = f"{topic_env_prefix}.{ONEX_EVT_OMNIINTELLIGENCE_INTENT_CLASSIFIED_V1}"

    # Build event payload
    event_payload = {
        "event_type": "IntentClassified",
        "session_id": session_id,
        "correlation_id": str(correlation_id),
        "intent_category": intent_category,
        "confidence": confidence,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Publish to Kafka
    await producer.publish(
        topic=topic,
        key=session_id,
        value=event_payload,
    )


__all__ = [
    "ProtocolIntentClassifier",
    "ProtocolKafkaPublisher",
    "handle_no_op",
    "handle_user_prompt_submit",
    "route_hook_event",
]
