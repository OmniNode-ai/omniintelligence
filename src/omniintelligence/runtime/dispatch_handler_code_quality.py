# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Dispatch handler for code entity quality scoring.

Consumes ``code-entities-persisted.v1``, runs quality scoring on each entity,
and updates Postgres with the results.

Idempotency: skips entities where (file_hash, config_hash, stage_version)
matches the stored enrichment_metadata.quality tuple.

Reference: OMN-5678
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
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


def create_code_quality_dispatch_handler(
    *,
    repository: Any | None = None,
    publisher: Any | None = None,
    quality_config: dict[str, Any] | None = None,
    correlation_id: UUID | None = None,
) -> DispatchHandler:
    """Create dispatch handler for quality scoring.

    Args:
        repository: RepositoryCodeEntity instance.
        publisher: Kafka publisher for emitting scored events.
        quality_config: Contract config for quality_scoring.
        correlation_id: Optional fixed correlation ID.
    """
    config_hash = _compute_config_hash(quality_config or {})

    async def _handle(
        envelope: ModelEventEnvelope[object],
        context: ProtocolHandlerContext,
    ) -> str:
        from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_quality_score import (
            QualityScorer,
        )
        from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entities_persisted_event import (
            ModelCodeEntitiesPersistedEvent,
        )

        ctx_cid = correlation_id or getattr(context, "correlation_id", None) or uuid4()
        payload = envelope.payload

        if not isinstance(payload, dict):
            logger.warning(
                "Unexpected payload type %s for quality handler", type(payload).__name__
            )
            raise ValueError(f"Bad payload type: {type(payload).__name__}")

        try:
            persisted = ModelCodeEntitiesPersistedEvent(**payload)
        except Exception as exc:
            sanitized = get_log_sanitizer().sanitize(str(exc))
            raise ValueError(f"Failed to parse persisted event: {sanitized}") from exc

        if repository is None or quality_config is None:
            logger.error(
                "quality handler missing repository or config (cid=%s)", ctx_cid
            )
            raise RuntimeError("quality handler not configured")

        scorer = QualityScorer(quality_config)
        entities = await repository.get_entities_by_ids(persisted.entity_ids)
        scored_count = 0

        for entity in entities:
            eid = str(entity["id"])

            # Idempotency check (Invariant 8)
            meta_info = await repository.get_entity_enrichment_metadata(eid)
            if meta_info:
                existing = meta_info.get("enrichment_metadata", {}).get("quality", {})
                if (
                    existing.get("config_hash") == config_hash
                    and existing.get("stage_version") == STAGE_VERSION
                    and meta_info.get("file_hash") == persisted.file_hash
                ):
                    continue  # Skip — already scored with same inputs

            # Try to read source code for quality analysis
            source_code = _read_source_file(
                persisted.repo_name, entity.get("source_path", "")
            )

            result = scorer.score(
                source_code=source_code,
                entity_type=entity.get("entity_type", "function"),
                entity_name=entity.get("entity_name", ""),
            )

            meta_patch = json.dumps(
                {
                    "quality": {
                        "config_hash": config_hash,
                        "stage_version": STAGE_VERSION,
                        "completed_at": datetime.now(UTC).isoformat(),
                    }
                }
            )
            await repository.update_quality_score(
                entity_id=eid,
                quality_score=result.overall_score,
                quality_dimensions=json.dumps(result.dimensions),
                enrichment_meta_patch=meta_patch,
            )
            scored_count += 1

        logger.info(
            "Quality scoring complete (file=%s, scored=%d/%d, cid=%s)",
            persisted.file_path,
            scored_count,
            len(entities),
            ctx_cid,
        )

        return "ok"

    return _handle


def _read_source_file(repo_name: str, source_path: str) -> str | None:
    """Best-effort read of source file for quality analysis."""
    try:
        # Try common repo locations
        for base in [
            Path("/Volumes/PRO-G40/Code/omni_home"),
            Path("/Volumes/PRO-G40/Code/omni_worktrees"),
        ]:
            full = base / repo_name / source_path
            if full.exists():
                return full.read_text()
        return None
    except Exception:
        return None


def _compute_config_hash(config: dict[str, Any]) -> str:
    """Compute deterministic hash of quality config."""
    serialized = json.dumps(config, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


__all__ = [
    "TOPIC_CODE_ENTITIES_PERSISTED_V1",
    "create_code_quality_dispatch_handler",
]
