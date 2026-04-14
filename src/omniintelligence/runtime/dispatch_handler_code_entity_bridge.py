# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Dispatch bridge handler: code-entities-extracted → learned patterns.

Receives ``code-entities-extracted.v1`` events (parallel with the persist
handler), feeds them through NodeCodeEntityBridgeCompute to derive
learned_patterns, upserts each derived pattern into the learned_patterns
table via AdapterPatternStore.upsert_pattern, and optionally publishes
``code-entity-patterns-derived.v1``.

Design:
    - Parallel consumer of code-entities-extracted.v1 (same as embed+graph handler).
      Uses a dispatch alias to register a second route on the same canonical event.
    - Pure compute via NodeCodeEntityBridgeCompute (stateless, no I/O).
    - Effect: upserts patterns using upsert_pattern (ON CONFLICT DO NOTHING)
      for idempotency.
    - Kafka publish is optional; primary flow succeeds whether or not Kafka is up.

Ticket: OMN-7863
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope
from omnibase_core.protocols.handler.protocol_handler_context import (
    ProtocolHandlerContext,
)

from omniintelligence.constants import TOPIC_CODE_ENTITY_PATTERNS_DERIVED_V1
from omniintelligence.nodes.node_code_entity_bridge_compute.models.model_input import (
    ModelCodeEntityBridgeInput,
)
from omniintelligence.nodes.node_code_entity_bridge_compute.models.model_output import (
    ModelDerivedPattern,
)
from omniintelligence.nodes.node_code_entity_bridge_compute.node import (
    NodeCodeEntityBridgeCompute,
)
from omniintelligence.runtime.contract_topics import canonical_topic_to_dispatch_alias
from omniintelligence.topics import IntentTopic

logger = logging.getLogger(__name__)

# Dispatch alias — a distinct topic alias that lets the dispatch engine register
# a second route on code-entities-extracted.v1 without colliding with the persist
# handler's route on the canonical topic.
DISPATCH_ALIAS_CODE_ENTITY_BRIDGE = canonical_topic_to_dispatch_alias(
    IntentTopic.CODE_ENTITIES_EXTRACTED_BRIDGE
)

DispatchHandler = Callable[
    [ModelEventEnvelope[object], ProtocolHandlerContext],
    Awaitable[str],
]

_BRIDGE_NODE = NodeCodeEntityBridgeCompute()


def create_code_entity_bridge_dispatch_handler(
    *,
    pattern_store: Any | None = None,
    kafka_publisher: Any | None = None,
    publish_topic: str | None = None,
    correlation_id: UUID | None = None,
    project_scope: str | None = None,
    domain_id: str = "code_structure",
    min_confidence: float = 0.7,
) -> DispatchHandler:
    """Create a dispatch handler for code-entities-extracted events.

    Args:
        pattern_store: AdapterPatternStore for upsert_pattern calls. When None,
            patterns are derived but not persisted (dry-run / test mode).
        kafka_publisher: Optional Kafka publisher for the derived event.
        publish_topic: Topic to publish derived-patterns events to.
        correlation_id: Optional fixed correlation ID for tracing.
        project_scope: Optional project scope filter (e.g. 'omniclaude').
        domain_id: Domain identifier applied to all derived patterns.
        min_confidence: Minimum entity confidence to derive a pattern.

    Returns:
        Async dispatch handler with signature (envelope, context) -> str.
    """

    async def _handle(
        envelope: ModelEventEnvelope[object],
        context: ProtocolHandlerContext,
    ) -> str:
        from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entities_extracted_event import (
            ModelCodeEntitiesExtractedEvent,
        )

        ctx_correlation_id = (
            correlation_id or getattr(context, "correlation_id", None) or uuid4()
        )

        payload = envelope.payload
        if not isinstance(payload, dict):
            logger.warning(
                "Unexpected payload type %s for code-entities-extracted bridge "
                "(correlation_id=%s)",
                type(payload).__name__,
                ctx_correlation_id,
            )
            return "ok"

        try:
            extracted_event = ModelCodeEntitiesExtractedEvent(**payload)
        except Exception as exc:
            logger.warning(
                "Failed to parse code-entities-extracted payload: %s "
                "(correlation_id=%s)",
                exc,
                ctx_correlation_id,
            )
            return "ok"

        if not extracted_event.entities:
            logger.debug(
                "No entities in extracted event for %s/%s, skipping "
                "(correlation_id=%s)",
                extracted_event.repo_name,
                extracted_event.file_path,
                ctx_correlation_id,
            )
            return "ok"

        if extracted_event.parse_status == "syntax_error":
            logger.debug(
                "Skipping bridge for syntax_error file %s/%s (correlation_id=%s)",
                extracted_event.repo_name,
                extracted_event.file_path,
                ctx_correlation_id,
            )
            return "ok"

        bridge_input = ModelCodeEntityBridgeInput(
            correlation_id=ctx_correlation_id,
            entities=list(extracted_event.entities),
            source_repo=extracted_event.repo_name,
            project_scope=project_scope,
            domain_id=domain_id,
            min_confidence=min_confidence,
        )

        bridge_output = _BRIDGE_NODE.compute(bridge_input)

        logger.info(
            "Bridge derived %d patterns (skipped=%d errors=%d repo=%s "
            "file=%s duration_ms=%.1f correlation_id=%s)",
            len(bridge_output.derived_patterns),
            bridge_output.skipped_count,
            bridge_output.error_count,
            extracted_event.repo_name,
            extracted_event.file_path,
            bridge_output.duration_ms,
            ctx_correlation_id,
        )

        if pattern_store is not None and bridge_output.derived_patterns:
            await _upsert_patterns(
                bridge_output.derived_patterns,
                pattern_store=pattern_store,
                correlation_id=ctx_correlation_id,
            )

        if (
            kafka_publisher is not None
            and publish_topic
            and bridge_output.derived_patterns
        ):
            try:
                event_dict = bridge_output.model_dump(mode="json")
                await kafka_publisher.publish(
                    topic=publish_topic,
                    value=event_dict,
                    key=f"{extracted_event.repo_name}:{extracted_event.file_path}",
                )
            except Exception:
                logger.exception(
                    "Failed to publish code-entity-patterns-derived event "
                    "(repo=%s file=%s correlation_id=%s)",
                    extracted_event.repo_name,
                    extracted_event.file_path,
                    ctx_correlation_id,
                )

        return "ok"

    return _handle


async def _upsert_patterns(
    patterns: list[ModelDerivedPattern],
    *,
    pattern_store: Any,
    correlation_id: UUID,
) -> None:
    """Upsert each derived pattern into the learned_patterns table.

    Uses upsert_pattern (ON CONFLICT DO NOTHING) — safe to replay the same
    code-entities-extracted event multiple times without creating duplicates.

    Matches ProtocolPatternUpsertStore.upsert_pattern signature exactly.
    """
    upserted = 0
    failed = 0

    for pattern in patterns:
        try:
            await pattern_store.upsert_pattern(
                pattern_id=pattern.pattern_id,
                signature=pattern.pattern_signature,
                signature_hash=pattern.signature_hash,
                domain_id=pattern.domain_id,
                domain_version=pattern.domain_version,
                confidence=pattern.confidence,
                version=1,
                source_session_ids=[],
            )
            upserted += 1
        except Exception:
            failed += 1
            logger.exception(
                "Failed to upsert pattern %s (correlation_id=%s)",
                pattern.pattern_id,
                correlation_id,
            )

    logger.info(
        "Pattern upsert complete: upserted=%d failed=%d (correlation_id=%s)",
        upserted,
        failed,
        correlation_id,
    )


__all__ = [
    "DISPATCH_ALIAS_CODE_ENTITY_BRIDGE",
    "TOPIC_CODE_ENTITY_PATTERNS_DERIVED_V1",
    "create_code_entity_bridge_dispatch_handler",
]
