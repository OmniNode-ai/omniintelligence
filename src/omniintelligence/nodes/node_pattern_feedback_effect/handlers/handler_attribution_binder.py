# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler for binding session outcomes to measurement data (L1 Attribution Bridge).

This module is the L1 Attribution Bridge from OMN-2133. It joins session outcomes
to pipeline measurement runs via ``run_id`` and computes evidence tiers for patterns.

Schema Decisions (locked in epic OMN-2043):
    - SD-2: ``run_id`` on pattern_injections is the canonical join key.
    - SD-3: ``apply_transition()`` reads ``learned_patterns.evidence_tier`` directly.
    - SD-4: ``evidence_tier`` is denormalized on ``learned_patterns``.
            This handler is the SOLE WRITER. Monotonic (only increases).

Evidence Tier Computation:
    - ``run_id`` is NULL: tier = OBSERVED (anecdotal evidence from workflow)
    - ``run_id`` present + run result = success: tier = MEASURED
    - ``run_id`` present + run result = failure/partial: tier = OBSERVED
    - Independent validation (future): tier = VERIFIED

Monotonic Guarantee:
    Evidence tiers ONLY increase. If current tier is MEASURED and new computation
    yields OBSERVED, the tier is NOT downgraded. This is enforced by comparing
    numeric weights: ``GREATEST(current_weight, new_weight)``.

Atomicity:
    The attribution record insert AND evidence_tier column update happen in the
    SAME transaction (via the same ``conn`` parameter). The caller controls the
    transaction boundary.

Kafka Event Emission:
    After a successful commit, an optional Kafka event is emitted. Kafka failures
    do NOT fail the attribution operation (ONEX invariant).

Design Principles:
    - Pure handler function with injected dependencies (protocols)
    - Monotonic tier updates enforced in SQL
    - No direct imports of concrete database or Kafka implementations
    - asyncpg-style positional parameters ($1, $2, etc.)

Reference:
    - OMN-2133: L1+L2 Attribution binder, auto-promote handler, transition guards
    - OMN-2043: Pattern Learning L1+L2 epic
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any, Protocol, TypedDict, runtime_checkable
from uuid import UUID

from omnibase_core.enums.pattern_learning import EnumEvidenceTier

logger = logging.getLogger(__name__)


# =============================================================================
# Tier Weight Mapping (for SQL monotonic comparison)
# =============================================================================

_TIER_WEIGHT_MAP: dict[str, int] = {
    tier.value: tier.get_numeric_value() for tier in EnumEvidenceTier
}
"""Maps evidence tier string values to numeric weights for SQL CASE expressions."""


# =============================================================================
# Protocol Definitions
# =============================================================================


@runtime_checkable
class ProtocolPatternRepository(Protocol):
    """Protocol for pattern data access operations.

    Mirrors asyncpg.Connection semantics for database operations.
    """

    async def fetch(self, query: str, *args: Any) -> list[Mapping[str, Any]]:
        """Execute a query and return all results."""
        ...

    async def fetchrow(self, query: str, *args: Any) -> Mapping[str, Any] | None:
        """Execute a query and return first row, or None."""
        ...

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a query and return the status string."""
        ...


@runtime_checkable
class ProtocolKafkaPublisher(Protocol):
    """Protocol for Kafka event publishers."""

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, Any],
    ) -> None:
        """Publish an event to a Kafka topic."""
        ...


# =============================================================================
# SQL Queries
# =============================================================================

# Fetch the current evidence_tier for a pattern
SQL_GET_PATTERN_EVIDENCE_TIER = """
SELECT id, evidence_tier
FROM learned_patterns
WHERE id = $1
"""

# Update evidence_tier with monotonic guarantee using numeric weight comparison.
# The CASE expression maps tier strings to weights and only updates if
# the new weight is strictly greater than the current weight.
SQL_UPDATE_EVIDENCE_TIER_MONOTONIC = """
UPDATE learned_patterns
SET evidence_tier = $2,
    updated_at = NOW()
WHERE id = $1
  AND (
    CASE evidence_tier
        WHEN 'unmeasured' THEN 0
        WHEN 'observed' THEN 10
        WHEN 'measured' THEN 20
        WHEN 'verified' THEN 30
        ELSE 0
    END
  ) < (
    CASE $2
        WHEN 'unmeasured' THEN 0
        WHEN 'observed' THEN 10
        WHEN 'measured' THEN 20
        WHEN 'verified' THEN 30
        ELSE 0
    END
  )
"""

# Insert attribution record into the audit table
SQL_INSERT_ATTRIBUTION = """
INSERT INTO pattern_measured_attributions (
    pattern_id,
    session_id,
    run_id,
    evidence_tier,
    measured_attribution_json,
    correlation_id
) VALUES ($1, $2, $3, $4, $5, $6)
RETURNING id
"""

# Find the run_id for a session from pattern_injections
SQL_GET_SESSION_RUN_ID = """
SELECT run_id
FROM pattern_injections
WHERE session_id = $1
  AND run_id IS NOT NULL
ORDER BY injected_at DESC
LIMIT 1
"""


# =============================================================================
# Type Definitions
# =============================================================================


class AttributionBindingResult(TypedDict):
    """Result of a single pattern attribution binding."""

    pattern_id: UUID
    previous_tier: str
    computed_tier: str
    tier_updated: bool
    attribution_id: UUID | None
    run_id: UUID | None


class BindSessionResult(TypedDict):
    """Result of binding all patterns in a session to measurements."""

    session_id: UUID
    patterns_processed: int
    patterns_updated: int
    attributions_created: int
    bindings: list[AttributionBindingResult]


# =============================================================================
# Pure Functions
# =============================================================================


def compute_evidence_tier(
    *,
    run_id: UUID | None,
    run_result: str | None,
    current_tier: EnumEvidenceTier,
) -> EnumEvidenceTier:
    """Compute the evidence tier for a pattern based on measurement data.

    This is a PURE FUNCTION with no I/O. It determines the evidence tier
    based on whether a pipeline run exists and its result.

    Args:
        run_id: Pipeline run ID. None means no measurement data.
        run_result: Overall result of the pipeline run (success|partial|failure).
            None when run_id is None.
        current_tier: Current evidence tier on the pattern.

    Returns:
        The computed evidence tier (may be same as current if no upgrade).

    Evidence Tier Rules:
        - No run_id: OBSERVED (anecdotal evidence)
        - run_id + success: MEASURED (quantitative data)
        - run_id + partial/failure: OBSERVED (run exists but didn't succeed)
        - VERIFIED requires independent validation (not computed here)
    """
    if run_id is None:
        computed = EnumEvidenceTier.OBSERVED
    elif run_result == "success":
        computed = EnumEvidenceTier.MEASURED
    else:
        # run exists but failed or partial - still just observed
        computed = EnumEvidenceTier.OBSERVED

    # Monotonic: never downgrade
    if computed > current_tier:
        return computed
    return current_tier


def _parse_evidence_tier(raw: str | None) -> EnumEvidenceTier:
    """Parse a raw evidence tier string into the enum.

    Args:
        raw: Raw tier string from database, or None.

    Returns:
        Parsed EnumEvidenceTier. Defaults to UNMEASURED if null or unparseable.
    """
    if not raw:
        return EnumEvidenceTier.UNMEASURED
    try:
        return EnumEvidenceTier(raw)
    except ValueError:
        logger.warning(
            "Unparseable evidence_tier value, treating as UNMEASURED",
            extra={"raw_value": raw},
        )
        return EnumEvidenceTier.UNMEASURED


# =============================================================================
# Handler Functions
# =============================================================================


async def bind_injection_to_measurement(
    session_id: UUID,
    pattern_ids: list[UUID],
    *,
    conn: ProtocolPatternRepository,
    correlation_id: UUID | None = None,
    run_id_override: UUID | None = None,
    run_result_override: str | None = None,
) -> BindSessionResult:
    """Bind session outcome patterns to measurement data and update evidence tiers.

    This is the main entry point for L1 Attribution Bridge. Called after
    session outcome recording (step 6 in record_session_outcome).

    For each pattern in the session:
    1. Look up the current evidence_tier from learned_patterns
    2. Determine run_id (from override or session's pattern_injections)
    3. Compute new evidence tier
    4. If tier would increase: atomically insert attribution + update column
    5. If tier would not increase: insert attribution record only (audit trail)

    Args:
        session_id: The Claude Code session ID.
        pattern_ids: List of pattern UUIDs that were injected in this session.
        conn: Database connection (caller manages transaction boundary).
        correlation_id: Optional correlation ID for distributed tracing.
        run_id_override: Optional run_id to use instead of looking up from DB.
            Used when the caller already knows the run_id.
        run_result_override: Optional run result (success|partial|failure).
            Required when run_id_override is provided.

    Returns:
        BindSessionResult with per-pattern binding details.
    """
    if not pattern_ids:
        return BindSessionResult(
            session_id=session_id,
            patterns_processed=0,
            patterns_updated=0,
            attributions_created=0,
            bindings=[],
        )

    logger.info(
        "Binding session patterns to measurements",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "session_id": str(session_id),
            "pattern_count": len(pattern_ids),
        },
    )

    # Determine run_id for this session
    run_id = run_id_override
    run_result = run_result_override
    if run_id is None:
        run_row = await conn.fetchrow(SQL_GET_SESSION_RUN_ID, session_id)
        if run_row is not None:
            run_id = run_row["run_id"]
            # run_result must be fetched separately or passed by caller
            # For now, having a run_id without explicit result means OBSERVED
            run_result = None

    bindings: list[AttributionBindingResult] = []
    patterns_updated = 0
    attributions_created = 0

    for pattern_id in pattern_ids:
        binding = await _bind_single_pattern(
            pattern_id=pattern_id,
            session_id=session_id,
            run_id=run_id,
            run_result=run_result,
            conn=conn,
            correlation_id=correlation_id,
        )
        bindings.append(binding)
        if binding["tier_updated"]:
            patterns_updated += 1
        if binding["attribution_id"] is not None:
            attributions_created += 1

    logger.info(
        "Attribution binding complete",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "session_id": str(session_id),
            "patterns_processed": len(pattern_ids),
            "patterns_updated": patterns_updated,
            "attributions_created": attributions_created,
        },
    )

    return BindSessionResult(
        session_id=session_id,
        patterns_processed=len(pattern_ids),
        patterns_updated=patterns_updated,
        attributions_created=attributions_created,
        bindings=bindings,
    )


async def _bind_single_pattern(
    pattern_id: UUID,
    session_id: UUID,
    run_id: UUID | None,
    run_result: str | None,
    *,
    conn: ProtocolPatternRepository,
    correlation_id: UUID | None = None,
) -> AttributionBindingResult:
    """Bind a single pattern to measurement data.

    Internal function that handles one pattern's attribution binding.
    Both the attribution insert and evidence_tier update use the same
    connection (``conn``) for atomicity.

    Args:
        pattern_id: The pattern to bind.
        session_id: The session that triggered this binding.
        run_id: Pipeline run ID (nullable).
        run_result: Pipeline run overall result (nullable).
        conn: Database connection for atomic operations.
        correlation_id: Optional correlation ID.

    Returns:
        AttributionBindingResult for this pattern.
    """
    # Step 1: Get current evidence tier
    row = await conn.fetchrow(SQL_GET_PATTERN_EVIDENCE_TIER, pattern_id)
    if row is None:
        logger.warning(
            "Pattern not found during attribution binding - skipping",
            extra={
                "correlation_id": str(correlation_id) if correlation_id else None,
                "pattern_id": str(pattern_id),
                "session_id": str(session_id),
            },
        )
        return AttributionBindingResult(
            pattern_id=pattern_id,
            previous_tier="unknown",
            computed_tier="unknown",
            tier_updated=False,
            attribution_id=None,
            run_id=run_id,
        )

    current_tier = _parse_evidence_tier(row.get("evidence_tier"))

    # Step 2: Compute new tier
    computed_tier = compute_evidence_tier(
        run_id=run_id,
        run_result=run_result,
        current_tier=current_tier,
    )

    # Step 3: Build measured attribution JSON (only when run_id is present)
    attribution_json: str | None = None
    if run_id is not None:
        attribution_json = json.dumps(
            {
                "run_id": str(run_id),
                "run_result": run_result,
                "evidence_tier": computed_tier.value,
                "session_id": str(session_id),
                "pattern_id": str(pattern_id),
            }
        )

    # Step 4: Insert attribution record (always, for audit trail)
    attr_row = await conn.fetchrow(
        SQL_INSERT_ATTRIBUTION,
        pattern_id,
        session_id,
        run_id,
        computed_tier.value,
        attribution_json,
        correlation_id,
    )
    attribution_id = attr_row["id"] if attr_row else None

    # Step 5: Update evidence_tier (monotonic - only if computed > current)
    tier_updated = False
    if computed_tier > current_tier:
        update_status = await conn.execute(
            SQL_UPDATE_EVIDENCE_TIER_MONOTONIC,
            pattern_id,
            computed_tier.value,
        )
        tier_updated = "UPDATE 1" in (update_status or "")

        if tier_updated:
            logger.info(
                "Evidence tier upgraded",
                extra={
                    "correlation_id": str(correlation_id) if correlation_id else None,
                    "pattern_id": str(pattern_id),
                    "previous_tier": current_tier.value,
                    "new_tier": computed_tier.value,
                    "run_id": str(run_id) if run_id else None,
                },
            )

    return AttributionBindingResult(
        pattern_id=pattern_id,
        previous_tier=current_tier.value,
        computed_tier=computed_tier.value,
        tier_updated=tier_updated,
        attribution_id=attribution_id,
        run_id=run_id,
    )


__all__ = [
    "AttributionBindingResult",
    "BindSessionResult",
    "ProtocolKafkaPublisher",
    "ProtocolPatternRepository",
    "bind_injection_to_measurement",
    "compute_evidence_tier",
]
