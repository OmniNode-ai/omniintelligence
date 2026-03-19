# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Tests for bootstrap promotion path (cold-start candidates with zero injections).

Reference: OMN-5500 - Relax CANDIDATE -> PROVISIONAL gate for bootstrap cold-start.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from omniintelligence.nodes.node_pattern_promotion_effect.handlers.handler_auto_promote import (
    PatternMetricsRow,
    meets_candidate_to_provisional_criteria,
)


def _make_pattern(**overrides: object) -> PatternMetricsRow:
    """Build a PatternMetricsRow with sensible defaults for bootstrap testing."""
    defaults: dict[str, object] = {
        "id": uuid4(),
        "pattern_signature": "test_pattern",
        "status": "candidate",
        "evidence_tier": "unmeasured",
        "injection_count_rolling_20": 0,
        "success_count_rolling_20": 0,
        "failure_count_rolling_20": 0,
        "failure_streak": 0,
        "confidence": 0.85,
        "recurrence_count": 3,
        "distinct_days_seen": 2,
    }
    defaults.update(overrides)
    return defaults  # type: ignore[return-value]


@pytest.mark.unit
def test_bootstrap_candidate_meets_criteria_with_zero_injections() -> None:
    """High-confidence candidates with zero injection history should be promotable via bootstrap path."""
    pattern = _make_pattern(confidence=0.85, recurrence_count=3, distinct_days_seen=2)
    assert meets_candidate_to_provisional_criteria(pattern) is True


@pytest.mark.unit
def test_bootstrap_candidate_rejected_low_confidence() -> None:
    """Low-confidence candidates should NOT be promotable via bootstrap.

    Isolates confidence check: recurrence and distinct_days are at threshold
    so this test only fails if confidence < BOOTSTRAP_MIN_CONFIDENCE.
    """
    pattern = _make_pattern(confidence=0.6, recurrence_count=2, distinct_days_seen=2)
    assert meets_candidate_to_provisional_criteria(pattern) is False


@pytest.mark.unit
def test_bootstrap_candidate_rejected_low_recurrence() -> None:
    """Candidates with high confidence but low recurrence should NOT be promotable via bootstrap."""
    pattern = _make_pattern(confidence=0.9, recurrence_count=1, distinct_days_seen=2)
    assert meets_candidate_to_provisional_criteria(pattern) is False


@pytest.mark.unit
def test_bootstrap_candidate_rejected_low_distinct_days() -> None:
    """Candidates with high confidence but only seen on 1 day should NOT be promotable via bootstrap."""
    pattern = _make_pattern(confidence=0.9, recurrence_count=3, distinct_days_seen=1)
    assert meets_candidate_to_provisional_criteria(pattern) is False


@pytest.mark.unit
def test_normal_path_still_works_with_injection_history() -> None:
    """Patterns with injection history should still promote via normal metric-based path."""
    pattern = _make_pattern(
        confidence=0.7,
        recurrence_count=1,
        distinct_days_seen=1,
        evidence_tier="observed",
        injection_count_rolling_20=5,
        success_count_rolling_20=4,
        failure_count_rolling_20=1,
        failure_streak=0,
    )
    assert meets_candidate_to_provisional_criteria(pattern) is True


@pytest.mark.unit
def test_normal_path_rejected_low_success_rate() -> None:
    """Patterns with injection history but low success rate should be rejected."""
    pattern = _make_pattern(
        confidence=0.7,
        evidence_tier="observed",
        injection_count_rolling_20=5,
        success_count_rolling_20=1,
        failure_count_rolling_20=4,
        failure_streak=0,
    )
    assert meets_candidate_to_provisional_criteria(pattern) is False


@pytest.mark.unit
def test_bootstrap_boundary_at_exact_threshold() -> None:
    """Patterns at exact bootstrap thresholds should be promotable."""
    pattern = _make_pattern(confidence=0.8, recurrence_count=2, distinct_days_seen=2)
    assert meets_candidate_to_provisional_criteria(pattern) is True


@pytest.mark.unit
def test_bootstrap_boundary_just_below_confidence() -> None:
    """Patterns just below confidence threshold should be rejected."""
    pattern = _make_pattern(confidence=0.79, recurrence_count=2, distinct_days_seen=2)
    assert meets_candidate_to_provisional_criteria(pattern) is False
