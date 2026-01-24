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
from typing import Any
from uuid import UUID

from omniintelligence.nodes.claude_hook_event_effect.models import (
    EnumClaudeHookEventType,
    EnumHookProcessingStatus,
    ModelClaudeHookEvent,
    ModelClaudeHookResult,
    ModelIntentResult,
)


async def route_hook_event(
    event: ModelClaudeHookEvent,
    *,
    intent_classifier: Any | None = None,
    kafka_producer: Any | None = None,
    topic_env_prefix: str = "dev",
) -> ModelClaudeHookResult:
    """Route a Claude Code hook event to the appropriate handler.

    This is the main entry point for processing hook events. It routes
    based on event_type to specialized handlers.

    Args:
        event: The Claude Code hook event to process.
        intent_classifier: Optional intent classifier compute node.
        kafka_producer: Optional Kafka producer for event emission.
        topic_env_prefix: Environment prefix for Kafka topic (e.g., "dev", "prod").

    Returns:
        ModelClaudeHookResult with processing outcome.
    """
    start_time = time.perf_counter()

    try:
        # Route based on event type
        if event.event_type == EnumClaudeHookEventType.USER_PROMPT_SUBMIT:
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


def handle_no_op(event: ModelClaudeHookEvent) -> ModelClaudeHookResult:
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


async def handle_user_prompt_submit(
    event: ModelClaudeHookEvent,
    *,
    intent_classifier: Any | None = None,
    kafka_producer: Any | None = None,
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
        intent_classifier: Intent classifier compute node (optional for testing).
        kafka_producer: Kafka producer for event emission (optional).
        topic_env_prefix: Environment prefix for Kafka topic (e.g., "dev", "prod").

    Returns:
        ModelClaudeHookResult with intent classification results.
    """
    metadata: dict[str, Any] = {"handler": "user_prompt_submit"}

    # Extract prompt from payload
    # Core model uses ModelClaudeCodeHookEventPayload with extra="allow"
    # Extra fields (like "prompt") are stored in model_extra
    prompt = event.payload.model_extra.get("prompt", "") if event.payload.model_extra else ""
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
    classifier: Any,
) -> dict[str, Any]:
    """Call the intent classifier compute node.

    Args:
        prompt: The user prompt to classify.
        session_id: Session ID for context.
        correlation_id: Correlation ID for tracing.
        classifier: The intent classifier compute node.

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
    producer: Any,
    *,
    topic_env_prefix: str = "dev",
) -> None:
    """Emit the classified intent to Kafka.

    Args:
        session_id: Session ID.
        intent_category: Classified intent category.
        confidence: Classification confidence.
        correlation_id: Correlation ID for tracing.
        producer: Kafka producer instance.
        topic_env_prefix: Environment prefix for Kafka topic (e.g., "dev", "prod").
    """
    # Build topic name with environment prefix
    topic = f"{topic_env_prefix}.omniintelligence.intent.classified.v1"

    # Build event payload
    event_payload = {
        "event_type": "INTENT_CLASSIFIED",
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
    "handle_no_op",
    "handle_user_prompt_submit",
    "route_hook_event",
]
