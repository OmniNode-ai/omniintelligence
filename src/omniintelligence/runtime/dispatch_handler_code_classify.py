# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Dispatch handler for deterministic code entity classification.

Consumes ``code-entities-persisted.v1``, runs deterministic classification
on each entity, and updates Postgres with the results.

Idempotency: skips entities where (file_hash, config_hash, stage_version)
matches the stored enrichment_metadata.classify tuple.

Reference: OMN-5678
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope
from omnibase_core.protocols.handler.protocol_handler_context import (
    ProtocolHandlerContext,
)

from omniintelligence.constants import (
    TOPIC_CODE_ENTITIES_PERSISTED_V1,
)
from omniintelligence.utils.log_sanitizer import get_log_sanitizer

logger = logging.getLogger(__name__)

STAGE_VERSION = "1.0.0"

DispatchHandler = Callable[
    [ModelEventEnvelope[object], ProtocolHandlerContext],
    Awaitable[str],
]


def create_code_classify_dispatch_handler(
    *,
    repository: Any | None = None,
    publisher: Any | None = None,
    classify_config: dict[str, Any] | None = None,
    correlation_id: UUID | None = None,
) -> DispatchHandler:
    """Create dispatch handler for deterministic classification.

    Args:
        repository: RepositoryCodeEntity instance.
        publisher: Kafka publisher for emitting classified events.
        classify_config: Contract config for deterministic_classification.
        correlation_id: Optional fixed correlation ID.
    """
    config_hash = _compute_config_hash(classify_config or {})

    async def _handle(
        envelope: ModelEventEnvelope[object],
        context: ProtocolHandlerContext,
    ) -> str:
        from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_deterministic_classify import (
            DeterministicClassifier,
        )
        from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entities_persisted_event import (
            ModelCodeEntitiesPersistedEvent,
        )

        ctx_cid = correlation_id or getattr(context, "correlation_id", None) or uuid4()
        payload = envelope.payload

        if not isinstance(payload, dict):
            logger.warning(
                "Unexpected payload type %s for classify handler",
                type(payload).__name__,
            )
            raise ValueError(f"Bad payload type: {type(payload).__name__}")

        try:
            persisted = ModelCodeEntitiesPersistedEvent(**payload)
        except Exception as exc:
            sanitized = get_log_sanitizer().sanitize(str(exc))
            raise ValueError(f"Failed to parse persisted event: {sanitized}") from exc

        if repository is None or classify_config is None:
            logger.error(
                "classify handler missing repository or config (cid=%s)", ctx_cid
            )
            raise RuntimeError("classify handler not configured")

        classifier = DeterministicClassifier(classify_config)
        entities = await repository.get_entities_by_ids(persisted.entity_ids)
        classified_count = 0

        for entity in entities:
            eid = str(entity["id"])

            # Idempotency check (Invariant 8)
            meta_info = await repository.get_entity_enrichment_metadata(eid)
            if meta_info:
                existing = meta_info.get("enrichment_metadata", {}).get("classify", {})
                if (
                    existing.get("config_hash") == config_hash
                    and existing.get("stage_version") == STAGE_VERSION
                    and meta_info.get("file_hash") == persisted.file_hash
                ):
                    continue  # Skip — already classified with same inputs

            # Classify
            methods = entity.get("methods") or []
            if isinstance(methods, str):
                methods = json.loads(methods)

            result = classifier.classify(
                entity_name=entity.get("entity_name", ""),
                bases=entity.get("bases") or [],
                methods=methods,
                decorators=entity.get("decorators") or [],
                docstring=entity.get("docstring"),
            )

            meta_patch = json.dumps(
                {
                    "classify": {
                        "config_hash": config_hash,
                        "stage_version": STAGE_VERSION,
                        "completed_at": datetime.now(UTC).isoformat(),
                    }
                }
            )
            await repository.update_deterministic_classification(
                entity_id=eid,
                node_type=result.node_type,
                confidence=result.confidence,
                alternatives=json.dumps(result.alternatives),
                enrichment_meta_patch=meta_patch,
            )
            classified_count += 1

        logger.info(
            "Classification complete (file=%s, classified=%d/%d, cid=%s)",
            persisted.file_path,
            classified_count,
            len(entities),
            ctx_cid,
        )

        return "ok"

    return _handle


def _compute_config_hash(config: dict[str, Any]) -> str:
    """Compute deterministic hash of classification config."""
    serialized = json.dumps(config, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


__all__ = [
    "TOPIC_CODE_ENTITIES_PERSISTED_V1",
    "create_code_classify_dispatch_handler",
]
