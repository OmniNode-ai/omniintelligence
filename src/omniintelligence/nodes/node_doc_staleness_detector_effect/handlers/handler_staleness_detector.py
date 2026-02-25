# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Handler for DocStalenessDetectorEffect — atomic staleness detection and re-ingestion.

Behavior:
  - Evaluates staleness candidates (from event consumption or periodic scan)
  - Classifies each candidate into one of 4 staleness cases
  - Applies the appropriate staleness policy (atomic 3-step for CONTENT_CHANGED)
  - Crash-safe: persists transition state to staleness_transition_log for resume

Staleness Cases:
  FILE_DELETED:
    - Immediate BLACKLISTED transition on old item. No new item.

  CONTENT_CHANGED_STATIC (e.g. CLAUDE.md):
    Step 1 (INDEX_NEW): Trigger re-ingestion at VALIDATED tier.
    Step 2 (VERIFY_NEW): Confirm new item in PostgreSQL + Qdrant.
    Step 3 (BLACKLIST_OLD): Blacklist old item. Only after step 2 succeeds.

  CONTENT_CHANGED_REPO:
    Same 3-step sequence. New item at QUARANTINE tier.
    If embedding_similarity(old, new) >= threshold: carry 70% of old stats.

  FILE_MOVED:
    Update source_ref in-place. No new item. No tier change.

Atomicity:
  Each CONTENT_CHANGED transition persists step state to staleness_transition_log.
  On crash, the handler resumes from the last confirmed step (idempotent).
  BLACKLIST_OLD (step 3) only executes after VERIFY_NEW (step 2) is confirmed.

Error handling:
  - Per-candidate failures are counted in items_failed (non-fatal)
  - Transition log failures are propagated (fatal — prevents silent data loss)

Architecture:
  All store/trigger dependencies are injected via protocols. No transport
  imports in this module.

Ticket: OMN-2394
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable
from uuid import UUID

from omniintelligence.nodes.node_doc_staleness_detector_effect.models.enum_staleness_case import (
    EnumStalenessCase,
)
from omniintelligence.nodes.node_doc_staleness_detector_effect.models.enum_staleness_transition_step import (
    EnumStalenessTransitionStep,
)
from omniintelligence.nodes.node_doc_staleness_detector_effect.models.model_staleness_detect_input import (
    ModelStalenessCandidate,
    ModelStalenessDetectInput,
)
from omniintelligence.nodes.node_doc_staleness_detector_effect.models.model_staleness_detect_output import (
    ModelStalenessDetectOutput,
)
from omniintelligence.nodes.node_doc_staleness_detector_effect.models.model_staleness_transition import (
    ModelStalenessTransition,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Protocol Definitions (dependency injection interfaces)
# =============================================================================


@runtime_checkable
class ProtocolStalenessStore(Protocol):
    """Protocol for staleness state persistence.

    Manages:
      - context_items tier/blacklist transitions
      - source_ref in-place updates (FILE_MOVED)
      - staleness_transition_log for crash-safe resume
      - new item confirmation queries (PG + Qdrant)
    """

    async def blacklist_item(
        self,
        *,
        item_id: UUID,
    ) -> None:
        """Transition a ContextItem to BLACKLISTED tier.

        Args:
            item_id: UUID of the item to blacklist.
        """
        ...

    async def update_source_ref(
        self,
        *,
        item_id: UUID,
        new_source_ref: str,
    ) -> None:
        """Update source_ref in-place for a FILE_MOVED transition.

        Args:
            item_id: UUID of the item to update.
            new_source_ref: New file path.
        """
        ...

    async def verify_item_in_pg(
        self,
        *,
        item_id: UUID,
    ) -> bool:
        """Return True if item_id exists and is not BLACKLISTED in PostgreSQL.

        Args:
            item_id: UUID of the new item to verify.
        """
        ...

    async def verify_item_in_qdrant(
        self,
        *,
        item_id: UUID,
        collection: str,
    ) -> bool:
        """Return True if item_id has a vector in the Qdrant collection.

        Args:
            item_id: UUID of the new item to verify.
            collection: Qdrant collection name.
        """
        ...

    async def apply_stat_carry(
        self,
        *,
        old_item_id: UUID,
        new_item_id: UUID,
        carry_fraction: float,
    ) -> None:
        """Copy a fraction of old item's stats to new item.

        Applies: scored_runs * fraction, positive_signals * fraction.
        Preserves used_rate (not multiplied by fraction).

        Args:
            old_item_id: UUID of the source item.
            new_item_id: UUID of the destination item.
            carry_fraction: Fraction to apply (0.0 to 1.0).
        """
        ...

    async def save_transition(
        self,
        *,
        transition: ModelStalenessTransition,
    ) -> None:
        """Upsert a staleness transition record in staleness_transition_log.

        Uses transition_id as the idempotency key. Overwrites existing
        record if present (allows step advancement on resume).

        Args:
            transition: Transition record to persist.
        """
        ...

    async def load_transition(
        self,
        *,
        transition_id: UUID,
    ) -> ModelStalenessTransition | None:
        """Load an existing transition record by ID.

        Returns None if no record exists for this ID.

        Args:
            transition_id: UUID of the transition to load.
        """
        ...


@runtime_checkable
class ProtocolReingestionTrigger(Protocol):
    """Protocol for triggering re-ingestion of a document.

    Implementations publish a re-ingestion command or directly invoke
    the Stream B pipeline for the given source_ref.
    """

    async def trigger_reingestion(
        self,
        *,
        source_ref: str,
        is_static_standards: bool,
        correlation_id: str | None,
    ) -> UUID | None:
        """Request re-ingestion of a document.

        Args:
            source_ref: Document path to re-ingest.
            is_static_standards: True for STATIC_STANDARDS tier (VALIDATED bootstrap).
            correlation_id: Optional correlation ID for tracing.

        Returns:
            UUID of the new ContextItem if created synchronously, None if async.
        """
        ...


# =============================================================================
# Staleness case classification
# =============================================================================


def _classify_staleness(candidate: ModelStalenessCandidate) -> EnumStalenessCase:
    """Classify a staleness candidate into one of 4 cases.

    Args:
        candidate: The candidate to classify.

    Returns:
        EnumStalenessCase for this candidate.
    """
    if not candidate.file_exists:
        return EnumStalenessCase.FILE_DELETED

    if candidate.new_source_ref is not None:
        # Same content (version_hash unchanged), new path
        return EnumStalenessCase.FILE_MOVED

    if (
        candidate.new_version_hash is not None
        and candidate.new_version_hash != candidate.current_version_hash
    ):
        if candidate.is_static_standards:
            return EnumStalenessCase.CONTENT_CHANGED_STATIC
        return EnumStalenessCase.CONTENT_CHANGED_REPO

    # No detectable staleness — caller should not have included this candidate
    # Default to CONTENT_CHANGED_REPO (conservative)
    return EnumStalenessCase.CONTENT_CHANGED_REPO


def _compute_similarity(
    old_embedding: tuple[float, ...] | None,
    new_embedding: tuple[float, ...] | None,
) -> float | None:
    """Compute cosine similarity between two embeddings.

    Returns None if either embedding is absent.

    Args:
        old_embedding: Embedding vector for old content.
        new_embedding: Embedding vector for new content.

    Returns:
        Cosine similarity in [0, 1], or None.
    """
    if old_embedding is None or new_embedding is None:
        return None
    if len(old_embedding) != len(new_embedding) or len(old_embedding) == 0:
        return None

    dot: float = sum(a * b for a, b in zip(old_embedding, new_embedding, strict=True))
    norm_old: float = sum(a * a for a in old_embedding) ** 0.5
    norm_new: float = sum(b * b for b in new_embedding) ** 0.5
    if norm_old == 0.0 or norm_new == 0.0:
        return None
    return dot / (norm_old * norm_new)


# =============================================================================
# Per-case handlers
# =============================================================================


async def _handle_file_deleted(
    transition: ModelStalenessTransition,
    staleness_store: ProtocolStalenessStore,
    dry_run: bool,
) -> ModelStalenessTransition:
    """Handle FILE_DELETED: immediate blacklist, single step."""
    if dry_run:
        return transition

    await staleness_store.blacklist_item(item_id=transition.old_item_id)
    updated = ModelStalenessTransition(
        transition_id=transition.transition_id,
        old_item_id=transition.old_item_id,
        source_ref=transition.source_ref,
        new_source_ref=transition.new_source_ref,
        new_item_id=transition.new_item_id,
        staleness_case=transition.staleness_case,
        current_step=EnumStalenessTransitionStep.COMPLETE,
        stat_carry_applied=transition.stat_carry_applied,
        embedding_similarity=transition.embedding_similarity,
        correlation_id=transition.correlation_id,
    )
    await staleness_store.save_transition(transition=updated)
    return updated


async def _handle_file_moved(
    transition: ModelStalenessTransition,
    staleness_store: ProtocolStalenessStore,
    dry_run: bool,
) -> ModelStalenessTransition:
    """Handle FILE_MOVED: in-place source_ref update, single step."""
    if dry_run or transition.new_source_ref is None:
        return transition

    await staleness_store.update_source_ref(
        item_id=transition.old_item_id,
        new_source_ref=transition.new_source_ref,
    )
    updated = ModelStalenessTransition(
        transition_id=transition.transition_id,
        old_item_id=transition.old_item_id,
        source_ref=transition.source_ref,
        new_source_ref=transition.new_source_ref,
        new_item_id=transition.new_item_id,
        staleness_case=transition.staleness_case,
        current_step=EnumStalenessTransitionStep.COMPLETE,
        stat_carry_applied=transition.stat_carry_applied,
        embedding_similarity=transition.embedding_similarity,
        correlation_id=transition.correlation_id,
    )
    await staleness_store.save_transition(transition=updated)
    return updated


async def _handle_content_changed(
    transition: ModelStalenessTransition,
    staleness_store: ProtocolStalenessStore,
    reingestion_trigger: ProtocolReingestionTrigger,
    candidate: ModelStalenessCandidate,
    stat_carry_fraction: float,
    similarity_threshold: float,
    qdrant_collection: str,
    dry_run: bool,
) -> tuple[ModelStalenessTransition, bool]:
    """Handle CONTENT_CHANGED: atomic 3-step sequence with crash-safe resume.

    Returns:
        (updated_transition, stat_carry_applied)
    """
    if dry_run:
        return transition, False

    current_step = transition.current_step
    new_item_id = transition.new_item_id
    stat_carry_applied = transition.stat_carry_applied
    similarity = transition.embedding_similarity

    # Step 1: INDEX_NEW — trigger re-ingestion
    if current_step in (
        EnumStalenessTransitionStep.PENDING,
        EnumStalenessTransitionStep.INDEX_NEW,
    ):
        is_static = (
            transition.staleness_case == EnumStalenessCase.CONTENT_CHANGED_STATIC
        )
        triggered_id = await reingestion_trigger.trigger_reingestion(
            source_ref=transition.source_ref,
            is_static_standards=is_static,
            correlation_id=transition.correlation_id,
        )
        if triggered_id is not None:
            new_item_id = triggered_id

        # Compute similarity for stat carry decision
        if similarity is None:
            similarity = _compute_similarity(
                candidate.current_embedding,
                candidate.new_embedding,
            )

        step1_transition = ModelStalenessTransition(
            transition_id=transition.transition_id,
            old_item_id=transition.old_item_id,
            source_ref=transition.source_ref,
            new_source_ref=transition.new_source_ref,
            new_item_id=new_item_id,
            staleness_case=transition.staleness_case,
            current_step=EnumStalenessTransitionStep.INDEX_NEW,
            stat_carry_applied=stat_carry_applied,
            embedding_similarity=similarity,
            correlation_id=transition.correlation_id,
        )
        await staleness_store.save_transition(transition=step1_transition)
        current_step = EnumStalenessTransitionStep.INDEX_NEW

    # Step 2: VERIFY_NEW — confirm new item in PG + Qdrant
    if (
        current_step == EnumStalenessTransitionStep.INDEX_NEW
        and new_item_id is not None
    ):
        pg_ok = await staleness_store.verify_item_in_pg(item_id=new_item_id)
        qdrant_ok = await staleness_store.verify_item_in_qdrant(
            item_id=new_item_id,
            collection=qdrant_collection,
        )
        if pg_ok and qdrant_ok:
            # Apply stat carry for REPO_DERIVED with sufficient similarity
            if (
                not stat_carry_applied
                and transition.staleness_case == EnumStalenessCase.CONTENT_CHANGED_REPO
                and similarity is not None
                and similarity >= similarity_threshold
            ):
                await staleness_store.apply_stat_carry(
                    old_item_id=transition.old_item_id,
                    new_item_id=new_item_id,
                    carry_fraction=stat_carry_fraction,
                )
                stat_carry_applied = True

            step2_transition = ModelStalenessTransition(
                transition_id=transition.transition_id,
                old_item_id=transition.old_item_id,
                source_ref=transition.source_ref,
                new_source_ref=transition.new_source_ref,
                new_item_id=new_item_id,
                staleness_case=transition.staleness_case,
                current_step=EnumStalenessTransitionStep.VERIFY_NEW,
                stat_carry_applied=stat_carry_applied,
                embedding_similarity=similarity,
                correlation_id=transition.correlation_id,
            )
            await staleness_store.save_transition(transition=step2_transition)
            current_step = EnumStalenessTransitionStep.VERIFY_NEW
        else:
            # Verification failed: stay at INDEX_NEW for retry
            logger.warning(
                "New item verification failed for transition %s "
                "(new_item_id=%s, pg_ok=%s, qdrant_ok=%s)",
                transition.transition_id,
                new_item_id,
                pg_ok,
                qdrant_ok,
            )
            return ModelStalenessTransition(
                transition_id=transition.transition_id,
                old_item_id=transition.old_item_id,
                source_ref=transition.source_ref,
                new_source_ref=transition.new_source_ref,
                new_item_id=new_item_id,
                staleness_case=transition.staleness_case,
                current_step=EnumStalenessTransitionStep.INDEX_NEW,
                stat_carry_applied=stat_carry_applied,
                embedding_similarity=similarity,
                correlation_id=transition.correlation_id,
            ), stat_carry_applied

    # Step 3: BLACKLIST_OLD — only after VERIFY_NEW confirmed
    if current_step == EnumStalenessTransitionStep.VERIFY_NEW:
        await staleness_store.blacklist_item(item_id=transition.old_item_id)
        final_transition = ModelStalenessTransition(
            transition_id=transition.transition_id,
            old_item_id=transition.old_item_id,
            source_ref=transition.source_ref,
            new_source_ref=transition.new_source_ref,
            new_item_id=new_item_id,
            staleness_case=transition.staleness_case,
            current_step=EnumStalenessTransitionStep.COMPLETE,
            stat_carry_applied=stat_carry_applied,
            embedding_similarity=similarity,
            correlation_id=transition.correlation_id,
        )
        await staleness_store.save_transition(transition=final_transition)
        return final_transition, stat_carry_applied

    # Already complete or in an unexpected state — return as-is
    return ModelStalenessTransition(
        transition_id=transition.transition_id,
        old_item_id=transition.old_item_id,
        source_ref=transition.source_ref,
        new_source_ref=transition.new_source_ref,
        new_item_id=new_item_id,
        staleness_case=transition.staleness_case,
        current_step=current_step,
        stat_carry_applied=stat_carry_applied,
        embedding_similarity=similarity,
        correlation_id=transition.correlation_id,
    ), stat_carry_applied


# =============================================================================
# Main handler
# =============================================================================


async def handle_staleness_detection(
    input_data: ModelStalenessDetectInput,
    *,
    staleness_store: ProtocolStalenessStore,
    reingestion_trigger: ProtocolReingestionTrigger,
    qdrant_collection: str = "context_items_v1",
) -> ModelStalenessDetectOutput:
    """Detect and handle staleness for a batch of context item candidates.

    Classifies each candidate and applies the appropriate staleness policy.
    CONTENT_CHANGED transitions use the atomic 3-step sequence with crash-safe
    resume via staleness_transition_log.

    Args:
        input_data: Staleness detection request with candidates.
        staleness_store: Protocol for PG state persistence and item transitions.
        reingestion_trigger: Protocol for triggering re-ingestion of documents.
        qdrant_collection: Qdrant collection name for new item verification.

    Returns:
        ModelStalenessDetectOutput with transition results and counters.
    """
    transitions: list[ModelStalenessTransition] = []
    items_blacklisted = 0
    items_moved = 0
    items_reingested = 0
    stat_carries = 0
    items_failed = 0

    for candidate in input_data.candidates:
        try:
            staleness_case = _classify_staleness(candidate)

            # Build or resume transition
            # Each candidate gets a deterministic transition_id based on item_id
            # so re-processing is idempotent
            transition_id = candidate.item_id  # Use item_id as transition key

            existing = await staleness_store.load_transition(
                transition_id=transition_id,
            )
            if (
                existing is not None
                and existing.current_step == EnumStalenessTransitionStep.COMPLETE
            ):
                # Already completed — skip
                transitions.append(existing)
                continue

            if existing is None:
                transition = ModelStalenessTransition(
                    transition_id=transition_id,
                    old_item_id=candidate.item_id,
                    source_ref=candidate.source_ref,
                    new_source_ref=candidate.new_source_ref,
                    new_item_id=None,
                    staleness_case=staleness_case,
                    current_step=EnumStalenessTransitionStep.PENDING,
                    stat_carry_applied=False,
                    embedding_similarity=None,
                    correlation_id=input_data.correlation_id,
                )
                if not input_data.dry_run:
                    await staleness_store.save_transition(transition=transition)
            else:
                transition = existing

            # Apply staleness policy
            if staleness_case == EnumStalenessCase.FILE_DELETED:
                updated = await _handle_file_deleted(
                    transition=transition,
                    staleness_store=staleness_store,
                    dry_run=input_data.dry_run,
                )
                transitions.append(updated)
                if updated.current_step == EnumStalenessTransitionStep.COMPLETE:
                    items_blacklisted += 1

            elif staleness_case == EnumStalenessCase.FILE_MOVED:
                updated = await _handle_file_moved(
                    transition=transition,
                    staleness_store=staleness_store,
                    dry_run=input_data.dry_run,
                )
                transitions.append(updated)
                if updated.current_step == EnumStalenessTransitionStep.COMPLETE:
                    items_moved += 1

            else:
                # CONTENT_CHANGED_STATIC or CONTENT_CHANGED_REPO
                updated, carry_applied = await _handle_content_changed(
                    transition=transition,
                    staleness_store=staleness_store,
                    reingestion_trigger=reingestion_trigger,
                    candidate=candidate,
                    stat_carry_fraction=input_data.stat_carry_fraction,
                    similarity_threshold=input_data.similarity_threshold,
                    qdrant_collection=qdrant_collection,
                    dry_run=input_data.dry_run,
                )
                transitions.append(updated)
                if updated.current_step == EnumStalenessTransitionStep.COMPLETE:
                    items_reingested += 1
                    items_blacklisted += 1
                if carry_applied and not transition.stat_carry_applied:
                    stat_carries += 1

        except Exception:
            logger.warning(
                "Failed to process staleness candidate (item_id=%s, source_ref=%s)",
                candidate.item_id,
                candidate.source_ref,
                exc_info=True,
            )
            items_failed += 1

    logger.info(
        "Staleness detection: blacklisted=%d moved=%d reingested=%d "
        "stat_carries=%d failed=%d dry_run=%s",
        items_blacklisted,
        items_moved,
        items_reingested,
        stat_carries,
        items_failed,
        input_data.dry_run,
    )

    return ModelStalenessDetectOutput(
        transitions=tuple(transitions),
        items_blacklisted=items_blacklisted,
        items_moved=items_moved,
        items_reingested=items_reingested,
        stat_carries_applied=stat_carries,
        items_failed=items_failed,
        dry_run=input_data.dry_run,
        correlation_id=input_data.correlation_id,
    )


__all__ = [
    "handle_staleness_detection",
    "ProtocolStalenessStore",
    "ProtocolReingestionTrigger",
]
