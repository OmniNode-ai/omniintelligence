# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for enforcement feedback handler (tests/ directory mirror).

This file mirrors the co-located node_tests for the enforcement feedback handler
to ensure both test discovery paths work. The authoritative tests are co-located
in the node_tests directory; this file provides the standard tests/ path.

Reference:
    - OMN-2270: Enforcement feedback loop for pattern confidence adjustment
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

import pytest

from omniintelligence.nodes.node_enforcement_feedback_effect.handlers.handler_enforcement_feedback import (
    CONFIDENCE_ADJUSTMENT_PER_VIOLATION,
    filter_confirmed_violations,
    process_enforcement_feedback,
)
from omniintelligence.nodes.node_enforcement_feedback_effect.models import (
    EnumEnforcementFeedbackStatus,
    ModelEnforcementEvent,
    ModelPatternViolation,
)
from omniintelligence.protocols import ProtocolPatternRepository

# =============================================================================
# Minimal Mock for tests/ directory
# =============================================================================


class _MockRecord(dict[str, Any]):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"Record has no column '{name}'")


class _MockRepo:
    """Minimal mock for ProtocolPatternRepository."""

    def __init__(self) -> None:
        self.patterns: dict[UUID, dict[str, Any]] = {}

    def add_pattern(self, pid: UUID, quality_score: float = 0.5) -> None:
        self.patterns[pid] = {"id": pid, "quality_score": quality_score}

    async def fetch(self, query: str, *args: Any) -> list[Mapping[str, Any]]:
        return []

    async def fetchrow(self, query: str, *args: Any) -> Mapping[str, Any] | None:
        if args:
            p = self.patterns.get(args[0])
            if p is not None:
                return _MockRecord(p)
        return None

    async def execute(self, query: str, *args: Any) -> str:
        if "UPDATE learned_patterns" in query and len(args) >= 2:
            pid, adj = args[0], args[1]
            p = self.patterns.get(pid)
            if p is not None:
                p["quality_score"] = max(0.0, min(1.0, p["quality_score"] + adj))
                return "UPDATE 1"
            return "UPDATE 0"
        return "EXECUTE 0"


assert isinstance(_MockRepo(), ProtocolPatternRepository)


# =============================================================================
# Tests
# =============================================================================


@pytest.mark.unit
class TestFilterConfirmedViolations:
    """Tests for filter_confirmed_violations pure function."""

    def test_empty_list(self) -> None:
        assert filter_confirmed_violations([]) == []

    def test_only_confirmed(self) -> None:
        v = ModelPatternViolation(
            pattern_id=uuid4(),
            pattern_name="p",
            was_advised=True,
            was_corrected=True,
        )
        result = filter_confirmed_violations([v])
        assert len(result) == 1
        assert result[0] is v

    def test_only_unconfirmed(self) -> None:
        v = ModelPatternViolation(
            pattern_id=uuid4(),
            pattern_name="p",
            was_advised=True,
            was_corrected=False,
        )
        assert filter_confirmed_violations([v]) == []

    def test_mixed(self) -> None:
        confirmed = ModelPatternViolation(
            pattern_id=uuid4(),
            pattern_name="c",
            was_advised=True,
            was_corrected=True,
        )
        unconfirmed = ModelPatternViolation(
            pattern_id=uuid4(),
            pattern_name="u",
            was_advised=True,
            was_corrected=False,
        )
        result = filter_confirmed_violations([confirmed, unconfirmed])
        assert len(result) == 1
        assert result[0] is confirmed


@pytest.mark.unit
class TestProcessEnforcementFeedback:
    """Core handler tests in the tests/ directory."""

    @pytest.mark.asyncio
    async def test_no_violations_returns_no_violations(self) -> None:
        repo = _MockRepo()
        event = ModelEnforcementEvent(
            correlation_id=uuid4(),
            session_id=uuid4(),
            patterns_checked=5,
            violations_found=0,
        )
        result = await process_enforcement_feedback(event=event, repository=repo)
        assert result.status == EnumEnforcementFeedbackStatus.NO_VIOLATIONS

    @pytest.mark.asyncio
    async def test_confirmed_violation_adjusts_score(self) -> None:
        repo = _MockRepo()
        pid = uuid4()
        repo.add_pattern(pid, quality_score=0.8)
        event = ModelEnforcementEvent(
            correlation_id=uuid4(),
            session_id=uuid4(),
            patterns_checked=1,
            violations_found=1,
            violations=[
                ModelPatternViolation(
                    pattern_id=pid,
                    pattern_name="test",
                    was_advised=True,
                    was_corrected=True,
                ),
            ],
        )
        result = await process_enforcement_feedback(event=event, repository=repo)
        assert result.status == EnumEnforcementFeedbackStatus.SUCCESS
        assert result.eligible_violations == 1
        assert len(result.adjustments) == 1
        assert result.processing_errors == []
        assert repo.patterns[pid]["quality_score"] == pytest.approx(0.79)

    @pytest.mark.asyncio
    async def test_unconfirmed_violation_no_adjustment(self) -> None:
        repo = _MockRepo()
        pid = uuid4()
        repo.add_pattern(pid, quality_score=0.8)
        event = ModelEnforcementEvent(
            correlation_id=uuid4(),
            session_id=uuid4(),
            patterns_checked=1,
            violations_found=1,
            violations=[
                ModelPatternViolation(
                    pattern_id=pid,
                    pattern_name="test",
                    was_advised=True,
                    was_corrected=False,
                ),
            ],
        )
        result = await process_enforcement_feedback(event=event, repository=repo)
        assert result.status == EnumEnforcementFeedbackStatus.NO_ADJUSTMENTS
        assert repo.patterns[pid]["quality_score"] == 0.8

    @pytest.mark.asyncio
    async def test_adjustment_constant_value(self) -> None:
        assert CONFIDENCE_ADJUSTMENT_PER_VIOLATION == -0.01
