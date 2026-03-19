# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Integration test for full promotion lifecycle with bootstrap path.

Verifies: candidate with bootstrap criteria -> promotion check -> provisional status.

Reference: OMN-5503 - Integration test for full promotion lifecycle.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from omniintelligence.enums import EnumPatternLifecycleStatus
from omniintelligence.nodes.node_pattern_promotion_effect.handlers.handler_auto_promote import (
    handle_auto_promote_check,
)


@pytest.mark.integration
async def test_full_promotion_lifecycle_bootstrap_candidate() -> None:
    """End-to-end: candidate with bootstrap criteria -> promotion check -> provisional status.

    Tests the full auto-promote handler with a mock repository returning a
    bootstrap-eligible candidate (confidence >= 0.8, recurrence >= 2,
    distinct_days >= 2, zero injection history).
    """
    pattern_id = uuid4()

    # Mock repository returning a bootstrap-eligible candidate
    mock_repo = AsyncMock()
    mock_repo.fetch.side_effect = [
        # Phase 1: CANDIDATE -> PROVISIONAL query
        [
            {
                "id": pattern_id,
                "pattern_signature": "Always validate inputs at API boundaries",
                "status": "candidate",
                "evidence_tier": "unmeasured",
                "injection_count_rolling_20": 0,
                "success_count_rolling_20": 0,
                "failure_count_rolling_20": 0,
                "failure_streak": 0,
                "confidence": 0.9,
                "recurrence_count": 3,
                "distinct_days_seen": 2,
            }
        ],
        # Phase 2: PROVISIONAL -> VALIDATED query (no results)
        [],
    ]
    # fetchrow for gate snapshot enrichment
    mock_repo.fetchrow.side_effect = [
        {"count": 0},  # attribution count
        None,  # no latest run result
    ]

    # Mock apply_transition_fn
    mock_transition_result = MagicMock()
    mock_transition_result.success = True
    mock_transition_result.duplicate = False
    mock_transition_result.reason = "auto_promote_evidence_gate"

    mock_apply_transition = AsyncMock(return_value=mock_transition_result)

    # Mock Kafka producer
    mock_producer = AsyncMock()

    result = await handle_auto_promote_check(
        repository=mock_repo,
        apply_transition_fn=mock_apply_transition,
        idempotency_store=None,
        producer=mock_producer,
        correlation_id=uuid4(),
    )

    # Verify the candidate was promoted
    assert result["candidates_checked"] == 1
    assert result["candidates_promoted"] == 1
    assert result["provisionals_checked"] == 0
    assert result["provisionals_promoted"] == 0

    # Verify apply_transition was called with correct transition
    assert mock_apply_transition.called
    call_kwargs = mock_apply_transition.call_args.kwargs
    assert call_kwargs["pattern_id"] == pattern_id
    assert call_kwargs["from_status"] == EnumPatternLifecycleStatus.CANDIDATE
    assert call_kwargs["to_status"] == EnumPatternLifecycleStatus.PROVISIONAL
    assert "Bootstrap-promoted" in call_kwargs["reason"]


@pytest.mark.integration
async def test_full_promotion_lifecycle_rejects_low_confidence_bootstrap() -> None:
    """Bootstrap candidates with low confidence should not be promoted."""
    mock_repo = AsyncMock()
    mock_repo.fetch.side_effect = [
        # Phase 1: CANDIDATE -> PROVISIONAL query
        [
            {
                "id": uuid4(),
                "pattern_signature": "Low confidence pattern",
                "status": "candidate",
                "evidence_tier": "unmeasured",
                "injection_count_rolling_20": 0,
                "success_count_rolling_20": 0,
                "failure_count_rolling_20": 0,
                "failure_streak": 0,
                "confidence": 0.5,
                "recurrence_count": 1,
                "distinct_days_seen": 1,
            }
        ],
        # Phase 2: No provisionals
        [],
    ]

    mock_apply_transition = AsyncMock()
    mock_producer = AsyncMock()

    result = await handle_auto_promote_check(
        repository=mock_repo,
        apply_transition_fn=mock_apply_transition,
        idempotency_store=None,
        producer=mock_producer,
        correlation_id=uuid4(),
    )

    # Candidate should NOT be promoted (doesn't meet bootstrap criteria)
    assert result["candidates_checked"] == 1
    assert result["candidates_promoted"] == 0
    assert not mock_apply_transition.called


@pytest.mark.integration
async def test_full_promotion_lifecycle_normal_metric_path() -> None:
    """Candidates with injection history should promote via normal metric path."""
    pattern_id = uuid4()

    mock_repo = AsyncMock()
    mock_repo.fetch.side_effect = [
        # Phase 1: CANDIDATE -> PROVISIONAL
        [
            {
                "id": pattern_id,
                "pattern_signature": "Use structured logging",
                "status": "candidate",
                "evidence_tier": "observed",
                "injection_count_rolling_20": 5,
                "success_count_rolling_20": 4,
                "failure_count_rolling_20": 1,
                "failure_streak": 0,
                "confidence": 0.7,
                "recurrence_count": 1,
                "distinct_days_seen": 1,
            }
        ],
        # Phase 2: No provisionals
        [],
    ]
    mock_repo.fetchrow.side_effect = [
        {"count": 2},  # attribution count
        {"run_result": "success"},  # latest run result
    ]

    mock_transition_result = MagicMock()
    mock_transition_result.success = True
    mock_transition_result.duplicate = False
    mock_transition_result.reason = "auto_promote_evidence_gate"

    mock_apply_transition = AsyncMock(return_value=mock_transition_result)
    mock_producer = AsyncMock()

    result = await handle_auto_promote_check(
        repository=mock_repo,
        apply_transition_fn=mock_apply_transition,
        idempotency_store=None,
        producer=mock_producer,
        correlation_id=uuid4(),
    )

    assert result["candidates_checked"] == 1
    assert result["candidates_promoted"] == 1
    assert mock_apply_transition.called
    call_kwargs = mock_apply_transition.call_args.kwargs
    assert "Auto-promoted" in call_kwargs["reason"]
