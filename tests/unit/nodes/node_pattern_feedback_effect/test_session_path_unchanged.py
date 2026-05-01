# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Regression coverage for the existing session outcome path."""

from __future__ import annotations

from uuid import UUID

import pytest

from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
    record_session_outcome,
)
from omniintelligence.nodes.node_pattern_feedback_effect.models import (
    EnumOutcomeRecordingStatus,
)
from tests.unit.nodes.node_pattern_feedback_effect.test_handler_session_outcome import (
    InjectionState,
    MockPatternRepository,
    PatternState,
)

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_session_outcome_path_matches_baseline() -> None:
    """The dispatch handler does not change session outcome behavior."""
    session_id = UUID("12345678-1234-5678-1234-567812345678")
    pattern_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    injection_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    repo = MockPatternRepository()
    repo.add_pattern(
        PatternState(
            id=pattern_id,
            injection_count_rolling_20=5,
            success_count_rolling_20=3,
            failure_count_rolling_20=2,
            failure_streak=2,
            quality_score=0.6,
        )
    )
    repo.add_injection(
        InjectionState(
            injection_id=injection_id,
            session_id=session_id,
            pattern_ids=[pattern_id],
        )
    )

    result = await record_session_outcome(
        session_id=session_id,
        success=True,
        repository=repo,
    )

    assert result.model_dump(exclude={"recorded_at"}) == {
        "status": EnumOutcomeRecordingStatus.SUCCESS,
        "session_id": session_id,
        "injections_updated": 1,
        "patterns_updated": 1,
        "pattern_ids": [pattern_id],
        "effectiveness_scores": {pattern_id: 4 / 6},
        "attribution_binding_failed": False,
        "error_message": None,
    }
    updated = repo.patterns[pattern_id]
    assert updated.injection_count_rolling_20 == 6
    assert updated.success_count_rolling_20 == 4
    assert updated.failure_count_rolling_20 == 2
    assert updated.failure_streak == 0
