# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Dispatch bridge handler for the code entity persistence stage.

Receives ``code-entities-extracted.v1`` event, upserts entities and
relationships to Postgres via ``RepositoryCodeEntity``, and runs zombie
cleanup reconciliation per Invariant section 6.

Design Decisions:
    - ``parse_status == "syntax_error"``: log and skip (don't touch DB).
    - ``parse_status == "success"``: persist entities + reconcile stale.
    - ``parse_status == "partial"``: persist entities but SKIP reconciliation
      to avoid deleting valid entities from a prior successful parse.
    - Relationship upsert requires resolving entity qualified names to UUIDs.
    - Reconciliation deletes entities and relationships that were present in
      a prior extraction but are no longer emitted (zombie cleanup).

Related:
    - OMN-5662: Wire crawl -> extract pipeline via Kafka events
    - OMN-5657: AST-based code pattern extraction system (epic)
    - OMN-5661: Create Postgres schema for code entities and relationships
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

from omniintelligence.constants import (
    TOPIC_CODE_ENTITIES_EXTRACTED_V1,
    TOPIC_CODE_ENTITIES_PERSISTED_V1,
)
from omniintelligence.utils.log_sanitizer import get_log_sanitizer

logger = logging.getLogger(__name__)


# =============================================================================
# Bridge Handler: code-entities-extracted.v1
# =============================================================================


DispatchHandler = Callable[
    [ModelEventEnvelope[object], ProtocolHandlerContext],
    Awaitable[str],
]


def create_code_persist_dispatch_handler(
    *,
    repository: Any | None = None,
    publisher: Any | None = None,
    correlation_id: UUID | None = None,
) -> DispatchHandler:
    """Create a dispatch engine handler for code-entities-extracted events.

    The handler upserts entities and relationships to Postgres and runs
    reconciliation to clean up stale entities.

    Args:
        repository: ``RepositoryCodeEntity`` instance for DB operations.
            If None, the handler will attempt to import from a registry
            at call time.
        correlation_id: Optional fixed correlation ID for tracing.

    Returns:
        Async handler function with signature (envelope, context) -> str.
    """

    async def _handle(
        envelope: ModelEventEnvelope[object],
        context: ProtocolHandlerContext,
    ) -> str:
        """Bridge handler: envelope -> upsert entities + reconcile."""
        from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entities_extracted_event import (
            ModelCodeEntitiesExtractedEvent,
        )

        ctx_correlation_id = (
            correlation_id or getattr(context, "correlation_id", None) or uuid4()
        )

        payload = envelope.payload

        if not isinstance(payload, dict):
            msg = (
                f"Unexpected payload type {type(payload).__name__} "
                f"for code-entities-extracted (correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg)

        try:
            extracted_event = ModelCodeEntitiesExtractedEvent(**payload)
        except Exception as e:
            sanitized = get_log_sanitizer().sanitize(str(e))
            msg = (
                f"Failed to parse payload as ModelCodeEntitiesExtractedEvent: "
                f"{sanitized} (correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg) from e

        # Skip entirely on syntax errors - don't touch DB
        if extracted_event.parse_status == "syntax_error":
            logger.info(
                "Skipping persistence for syntax_error file "
                "(file=%s, repo=%s, correlation_id=%s)",
                extracted_event.file_path,
                extracted_event.repo_name,
                ctx_correlation_id,
            )
            return "ok"

        if repository is None:
            msg = (
                "RepositoryCodeEntity not configured for code-persist handler "
                f"(correlation_id={ctx_correlation_id})"
            )
            logger.error(msg)
            raise RuntimeError(msg)

        logger.info(
            "Persisting entities for %s (repo=%s, entities=%d, "
            "relationships=%d, parse_status=%s, correlation_id=%s)",
            extracted_event.file_path,
            extracted_event.repo_name,
            len(extracted_event.entities),
            len(extracted_event.relationships),
            extracted_event.parse_status,
            ctx_correlation_id,
        )

        # Upsert entities
        entity_qualified_names: list[str] = []
        for entity in extracted_event.entities:
            entity_dict = entity.model_dump()
            entity_dict["file_hash"] = extracted_event.file_hash
            entity_dict["source_path"] = extracted_event.file_path
            entity_dict["source_repo"] = extracted_event.repo_name
            await repository.upsert_entity(entity_dict)
            entity_qualified_names.append(entity.qualified_name)

        # Upsert relationships (resolve qualified names to entity IDs)
        relationship_keys: list[tuple[str, str, str]] = []
        for rel in extracted_event.relationships:
            source_id = await repository.get_entity_id_by_qualified_name(
                rel.source_entity, extracted_event.repo_name
            )
            target_id = await repository.get_entity_id_by_qualified_name(
                rel.target_entity, extracted_event.repo_name
            )

            if source_id is None or target_id is None:
                logger.debug(
                    "Skipping relationship %s -> %s (%s): entity not found",
                    rel.source_entity,
                    rel.target_entity,
                    rel.relationship_type,
                )
                continue

            rel_dict: dict[str, Any] = {
                "source_entity_id": source_id,
                "target_entity_id": target_id,
                "relationship_type": rel.relationship_type,
                "trust_tier": rel.trust_tier,
                "confidence": rel.confidence,
                "evidence": rel.evidence,
                "inject_into_context": rel.inject_into_context,
                "source_repo": extracted_event.repo_name,
            }
            await repository.upsert_relationship(rel_dict)
            relationship_keys.append(
                (rel.source_entity, rel.target_entity, rel.relationship_type)
            )

        # Reconciliation: only on successful parse (Invariant section 6)
        stale_entities_deleted = 0
        stale_relationships_deleted = 0

        if extracted_event.parse_status == "success":
            stale_entities_deleted = await repository.delete_stale_entities(
                source_path=extracted_event.file_path,
                source_repo=extracted_event.repo_name,
                current_qualified_names=entity_qualified_names,
            )
            stale_relationships_deleted = (
                await repository.delete_stale_relationships_for_file(
                    source_path=extracted_event.file_path,
                    source_repo=extracted_event.repo_name,
                    current_relationship_keys=relationship_keys,
                )
            )

            if stale_entities_deleted > 0 or stale_relationships_deleted > 0:
                logger.info(
                    "Reconciliation: deleted %d stale entities, %d stale "
                    "relationships (file=%s, repo=%s, correlation_id=%s)",
                    stale_entities_deleted,
                    stale_relationships_deleted,
                    extracted_event.file_path,
                    extracted_event.repo_name,
                    ctx_correlation_id,
                )
        else:
            logger.debug(
                "Skipping reconciliation for parse_status=%s "
                "(file=%s, repo=%s, correlation_id=%s)",
                extracted_event.parse_status,
                extracted_event.file_path,
                extracted_event.repo_name,
                ctx_correlation_id,
            )

        # Emit persisted event for downstream enrichment (Part 2: OMN-5677)
        if publisher is not None and entity_qualified_names:
            from datetime import UTC, datetime

            from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entities_persisted_event import (
                ModelCodeEntitiesPersistedEvent,
            )

            # Collect entity IDs by re-querying (they were just upserted)
            entity_ids: list[str] = []
            for qn in entity_qualified_names:
                eid = await repository.get_entity_id_by_qualified_name(
                    qn, extracted_event.repo_name
                )
                if eid:
                    entity_ids.append(eid)

            if entity_ids:
                persisted_event = ModelCodeEntitiesPersistedEvent(
                    event_id=str(uuid4()),
                    crawl_id=extracted_event.crawl_id,
                    repo_name=extracted_event.repo_name,
                    file_path=extracted_event.file_path,
                    file_hash=extracted_event.file_hash,
                    entity_ids=entity_ids,
                    persisted_count=len(entity_ids),
                    timestamp=datetime.now(UTC),
                )
                try:
                    await publisher.publish(
                        TOPIC_CODE_ENTITIES_PERSISTED_V1,
                        persisted_event.model_dump(mode="json"),
                    )
                    logger.info(
                        "Emitted code-entities-persisted.v1 "
                        "(file=%s, entities=%d, correlation_id=%s)",
                        extracted_event.file_path,
                        len(entity_ids),
                        ctx_correlation_id,
                    )
                except Exception:
                    logger.warning(
                        "Failed to emit code-entities-persisted.v1 "
                        "(file=%s, correlation_id=%s) — enrichment will be deferred",
                        extracted_event.file_path,
                        ctx_correlation_id,
                        exc_info=True,
                    )

        logger.info(
            "Code persistence complete (file=%s, entities_upserted=%d, "
            "relationships_upserted=%d, correlation_id=%s)",
            extracted_event.file_path,
            len(entity_qualified_names),
            len(relationship_keys),
            ctx_correlation_id,
        )

        return "ok"

    return _handle


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "TOPIC_CODE_ENTITIES_EXTRACTED_V1",
    "create_code_persist_dispatch_handler",
]
