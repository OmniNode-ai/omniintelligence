# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler functions for enforcement feedback processing.

This module implements the enforcement feedback loop: when omniclaude's
PostToolUse hook detects pattern violations, it emits an enforcement event.
This handler consumes those events and applies conservative confidence
adjustments to violated patterns.

Conservative Adjustment Policy:
-------------------------------
A violation only counts toward confidence adjustment when ALL conditions
are met:
    1. The violation was detected (violation exists in the event)
    2. The agent was **advised** about the violation (was_advised=True)
    3. The agent subsequently **corrected** the violation (was_corrected=True)

When all conditions are met, the pattern's quality_score is decremented by
CONFIDENCE_ADJUSTMENT_PER_VIOLATION (-0.01). This is intentionally conservative
to prevent rapid erosion of pattern confidence from noisy enforcement data.

The quality_score is clamped to [0.0, 1.0] after adjustment.

Why require correction confirmation?
    If an agent was advised of a violation but did NOT correct it, we cannot
    confirm the violation was real. The advisory might have been a false
    positive, or the agent might have intentionally kept the code as-is.
    Only when the agent both receives advice AND acts on it can we be
    confident the violation was genuine.

SQL Pattern:
    Uses a single UPDATE with GREATEST(..., 0.0) clamping to ensure
    quality_score never goes below 0.0. Each confirmed violation applies
    CONFIDENCE_ADJUSTMENT_PER_VIOLATION independently.

Reference:
    - OMN-2270: Enforcement feedback loop for pattern confidence adjustment
    - OMN-2263: PostToolUse pattern enforcement hook (producer)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from omniintelligence.nodes.node_enforcement_feedback_effect.models import (
    EnumEnforcementFeedbackStatus,
    ModelConfidenceAdjustment,
    ModelEnforcementEvent,
    ModelEnforcementFeedbackResult,
    ModelPatternViolation,
)
from omniintelligence.protocols import ProtocolPatternRepository
from omniintelligence.utils.log_sanitizer import get_log_sanitizer
from omniintelligence.utils.pg_status import parse_pg_status_count

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

CONFIDENCE_ADJUSTMENT_PER_VIOLATION: float = -0.01
"""Amount to subtract from quality_score per confirmed violation.

This value is intentionally conservative:
    - Small enough that a single false positive is negligible
    - Large enough that persistent violations accumulate meaningfully
    - At -0.01 per violation, it takes 50 confirmed violations to drop
      a perfect score (1.0) to a failing threshold (0.5)

The adjustment is ALWAYS negative (quality decreases on violations).
"""

QUALITY_SCORE_FLOOR: float = 0.0
"""Minimum quality_score after adjustment.

Quality scores are clamped to [0.0, 1.0]. The GREATEST(..., 0.0) in SQL
ensures we never store negative values.
"""


# =============================================================================
# SQL Queries
# =============================================================================

# Adjust quality_score for a single pattern by a given delta.
# Uses GREATEST to clamp at 0.0 (never negative).
# Uses LEAST to clamp at 1.0 (never exceeds maximum).
# Parameters: $1 = pattern_id, $2 = adjustment (negative float)
SQL_ADJUST_QUALITY_SCORE = """
UPDATE learned_patterns
SET
    quality_score = LEAST(GREATEST(quality_score + $2, 0.0), 1.0),
    updated_at = NOW()
WHERE id = $1
"""

# =============================================================================
# Handler Functions
# =============================================================================


def _filter_confirmed_violations(
    violations: list[ModelPatternViolation],
) -> list[ModelPatternViolation]:
    """Filter violations to only those meeting the confirmation criteria.

    A violation is "confirmed" when:
        1. was_advised is True (agent was told about the violation)
        2. was_corrected is True (agent subsequently fixed it)

    This two-condition requirement prevents false positives from eroding
    pattern confidence. See module docstring for full rationale.

    Args:
        violations: All violations from the enforcement event.

    Returns:
        Only violations where both was_advised AND was_corrected are True.
    """
    return [v for v in violations if v.was_advised and v.was_corrected]


async def process_enforcement_feedback(
    event: ModelEnforcementEvent,
    *,
    repository: ProtocolPatternRepository,
) -> ModelEnforcementFeedbackResult:
    """Process an enforcement feedback event and apply confidence adjustments.

    This is the main entry point for the enforcement feedback handler. It:
    1. Validates the event contains violations
    2. Filters to only confirmed violations (advised AND corrected)
    3. Applies conservative confidence adjustments (-0.01 per confirmed violation)
    4. Returns structured result with adjustment details

    Args:
        event: The enforcement event from omniclaude's PostToolUse hook.
        repository: Database repository implementing ProtocolPatternRepository.

    Returns:
        ModelEnforcementFeedbackResult with processing status and adjustments.
    """
    logger.info(
        "Processing enforcement feedback event",
        extra={
            "correlation_id": str(event.correlation_id),
            "session_id": str(event.session_id),
            "patterns_checked": event.patterns_checked,
            "violations_found": event.violations_found,
        },
    )

    # Step 1: Check if there are any violations to process
    if event.violations_found == 0 or not event.violations:
        logger.info(
            "No violations in enforcement event - skipping",
            extra={
                "correlation_id": str(event.correlation_id),
                "session_id": str(event.session_id),
            },
        )
        return ModelEnforcementFeedbackResult(
            status=EnumEnforcementFeedbackStatus.NO_VIOLATIONS,
            correlation_id=event.correlation_id,
            session_id=event.session_id,
            patterns_checked=event.patterns_checked,
            violations_found=event.violations_found,
            confirmed_violations=0,
            adjustments=[],
            processed_at=datetime.now(UTC),
        )

    # Step 2: Filter to confirmed violations (advised AND corrected)
    confirmed = _filter_confirmed_violations(event.violations)

    if not confirmed:
        logger.info(
            "No confirmed violations (advised AND corrected) - skipping adjustments",
            extra={
                "correlation_id": str(event.correlation_id),
                "session_id": str(event.session_id),
                "total_violations": len(event.violations),
            },
        )
        return ModelEnforcementFeedbackResult(
            status=EnumEnforcementFeedbackStatus.NO_ADJUSTMENTS,
            correlation_id=event.correlation_id,
            session_id=event.session_id,
            patterns_checked=event.patterns_checked,
            violations_found=event.violations_found,
            confirmed_violations=0,
            adjustments=[],
            processed_at=datetime.now(UTC),
        )

    # Step 3: Apply confidence adjustments for each confirmed violation
    adjustments: list[ModelConfidenceAdjustment] = []

    for violation in confirmed:
        try:
            adjustment = await _apply_confidence_adjustment(
                pattern_id=violation.pattern_id,
                pattern_name=violation.pattern_name,
                repository=repository,
                correlation_id=event.correlation_id,
            )
            if adjustment is not None:
                adjustments.append(adjustment)
        except Exception as exc:
            # Per handler error policy: return structured errors, don't raise
            # for expected failures. Log and continue with remaining violations.
            sanitized_error = get_log_sanitizer().sanitize(str(exc))
            logger.error(
                "Failed to adjust confidence for pattern",
                extra={
                    "correlation_id": str(event.correlation_id),
                    "pattern_id": str(violation.pattern_id),
                    "error": sanitized_error,
                    "error_type": type(exc).__name__,
                },
                exc_info=True,
            )

    logger.info(
        "Enforcement feedback processing complete",
        extra={
            "correlation_id": str(event.correlation_id),
            "session_id": str(event.session_id),
            "confirmed_violations": len(confirmed),
            "adjustments_applied": len(adjustments),
        },
    )

    return ModelEnforcementFeedbackResult(
        status=EnumEnforcementFeedbackStatus.SUCCESS,
        correlation_id=event.correlation_id,
        session_id=event.session_id,
        patterns_checked=event.patterns_checked,
        violations_found=event.violations_found,
        confirmed_violations=len(confirmed),
        adjustments=adjustments,
        processed_at=datetime.now(UTC),
    )


async def _apply_confidence_adjustment(
    pattern_id: UUID,
    pattern_name: str,
    *,
    repository: ProtocolPatternRepository,
    correlation_id: UUID,
) -> ModelConfidenceAdjustment | None:
    """Apply a single confidence adjustment to a pattern.

    Applies the adjustment via UPDATE and checks the row count to detect
    whether the pattern exists. Returns None if the pattern was not found
    (0 rows updated).

    Args:
        pattern_id: The pattern to adjust.
        pattern_name: Human-readable name for the audit record.
        repository: Database repository.
        correlation_id: For distributed tracing.

    Returns:
        ModelConfidenceAdjustment if adjustment was applied, None if
        pattern does not exist.
    """
    # Apply the adjustment; row count of 0 means the pattern does not exist
    status = await repository.execute(
        SQL_ADJUST_QUALITY_SCORE,
        pattern_id,
        CONFIDENCE_ADJUSTMENT_PER_VIOLATION,
    )
    rows_updated = parse_pg_status_count(status)

    if rows_updated == 0:
        logger.warning(
            "Pattern not found for confidence adjustment - skipping",
            extra={
                "correlation_id": str(correlation_id),
                "pattern_id": str(pattern_id),
                "pattern_name": pattern_name,
            },
        )
        return None

    logger.debug(
        "Applied confidence adjustment",
        extra={
            "correlation_id": str(correlation_id),
            "pattern_id": str(pattern_id),
            "pattern_name": pattern_name,
            "adjustment": CONFIDENCE_ADJUSTMENT_PER_VIOLATION,
        },
    )

    return ModelConfidenceAdjustment(
        pattern_id=pattern_id,
        adjustment=CONFIDENCE_ADJUSTMENT_PER_VIOLATION,
        reason=f"Confirmed enforcement violation: pattern '{pattern_name}' "
        f"was advised and subsequently corrected",
    )


__all__ = [
    "CONFIDENCE_ADJUSTMENT_PER_VIOLATION",
    "process_enforcement_feedback",
]
