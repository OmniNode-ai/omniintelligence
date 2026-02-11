# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for handler_auto_promote (L2 Lifecycle Controller).

Tests cover:
- Evidence tier gate: CANDIDATE->PROVISIONAL with OBSERVED -> accepted
- Evidence tier gate: PROVISIONAL->VALIDATED with MEASURED -> accepted
- Metrics gates: insufficient injection count -> skipped
- Failure streak gate: too many failures -> skipped
- Mock apply_transition integration
- Empty candidate/provisional sets

Reference: OMN-2133
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import pytest

from omniintelligence.nodes.node_pattern_promotion_effect.handlers.handler_auto_promote import (
    handle_auto_promote_check,
    meets_candidate_to_provisional_criteria,
    meets_provisional_to_validated_criteria,
)

pytestmark = pytest.mark.unit


# =============================================================================
# Mock Infrastructure
# =============================================================================


class MockRecord(dict):
    """Dict subclass mimicking asyncpg.Record."""

    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


@dataclass
class MockTransitionResult:
    """Mock result from apply_transition."""

    success: bool = True
    duplicate: bool = False
    pattern_id: UUID = field(default_factory=uuid4)
    from_status: str = "candidate"
    to_status: str = "provisional"
    transition_id: UUID | None = field(default_factory=uuid4)
    reason: str = "auto_promote_evidence_gate"
    transitioned_at: Any = None
    error_message: str | None = None


class MockPatternRepository:
    """Mock repository for auto-promote tests."""

    def __init__(self) -> None:
        self.candidate_patterns: list[dict[str, Any]] = []
        self.provisional_patterns: list[dict[str, Any]] = []
        self.queries_executed: list[str] = []

    async def fetch(self, query: str, *args: Any) -> list[Mapping[str, Any]]:
        self.queries_executed.append(query.strip()[:80])
        if "status = 'candidate'" in query:
            return [MockRecord(**p) for p in self.candidate_patterns]
        if "status = 'provisional'" in query:
            return [MockRecord(**p) for p in self.provisional_patterns]
        return []

    async def fetchrow(self, query: str, *args: Any) -> Mapping[str, Any] | None:
        self.queries_executed.append(query.strip()[:80])
        if "COUNT" in query:
            return MockRecord(count=0)
        if "run_result" in query:
            return None
        return None

    async def execute(self, query: str, *args: Any) -> str:
        self.queries_executed.append(query.strip()[:80])
        return "UPDATE 0"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def correlation_id() -> UUID:
    return uuid4()


def _make_pattern(
    status: str = "candidate",
    evidence_tier: str = "observed",
    injection_count: int = 10,
    success_count: int = 8,
    failure_count: int = 2,
    failure_streak: int = 0,
) -> dict[str, Any]:
    return {
        "id": uuid4(),
        "pattern_signature": f"test_pattern_{status}",
        "status": status,
        "evidence_tier": evidence_tier,
        "injection_count_rolling_20": injection_count,
        "success_count_rolling_20": success_count,
        "failure_count_rolling_20": failure_count,
        "failure_streak": failure_streak,
    }


# =============================================================================
# Tests: Pure Criteria Functions
# =============================================================================


class TestMeetsCandidateToProvisionalCriteria:
    """Tests for candidate -> provisional criteria evaluation."""

    def test_meets_criteria(self) -> None:
        pattern = _make_pattern(
            injection_count=5,
            success_count=4,
            failure_count=1,
            failure_streak=0,
        )
        assert meets_candidate_to_provisional_criteria(pattern) is True

    def test_insufficient_injections(self) -> None:
        pattern = _make_pattern(
            injection_count=2,
            success_count=2,
            failure_count=0,
            failure_streak=0,
        )
        assert meets_candidate_to_provisional_criteria(pattern) is False

    def test_low_success_rate(self) -> None:
        pattern = _make_pattern(
            injection_count=10,
            success_count=3,
            failure_count=7,
            failure_streak=0,
        )
        assert meets_candidate_to_provisional_criteria(pattern) is False

    def test_high_failure_streak(self) -> None:
        pattern = _make_pattern(
            injection_count=10,
            success_count=8,
            failure_count=2,
            failure_streak=3,
        )
        assert meets_candidate_to_provisional_criteria(pattern) is False

    def test_no_outcomes(self) -> None:
        pattern = _make_pattern(
            injection_count=5,
            success_count=0,
            failure_count=0,
            failure_streak=0,
        )
        assert meets_candidate_to_provisional_criteria(pattern) is False


class TestMeetsProvisionalToValidatedCriteria:
    """Tests for provisional -> validated criteria evaluation."""

    def test_meets_criteria(self) -> None:
        pattern = _make_pattern(
            injection_count=10,
            success_count=8,
            failure_count=2,
            failure_streak=0,
        )
        assert meets_provisional_to_validated_criteria(pattern) is True

    def test_insufficient_injections(self) -> None:
        pattern = _make_pattern(
            injection_count=3,
            success_count=3,
            failure_count=0,
            failure_streak=0,
        )
        # Default threshold for validated is 5
        assert meets_provisional_to_validated_criteria(pattern) is False

    def test_exact_threshold(self) -> None:
        pattern = _make_pattern(
            injection_count=5,
            success_count=4,
            failure_count=1,
            failure_streak=0,
        )
        # 4/5 = 0.8 > 0.6 threshold
        assert meets_provisional_to_validated_criteria(pattern) is True


# =============================================================================
# Tests: check_and_auto_promote Handler
# =============================================================================


class TestCheckAndAutoPromote:
    """Tests for the main auto-promote handler."""

    @pytest.mark.asyncio
    async def test_no_candidates_no_provisionals(
        self,
        correlation_id: UUID,
    ) -> None:
        """Empty candidate and provisional sets -> zero promotions."""
        repo = MockPatternRepository()

        async def mock_apply_transition(
            *_args: Any, **_kwargs: Any
        ) -> MockTransitionResult:
            raise AssertionError("Should not be called")

        result = await handle_auto_promote_check(
            repository=repo,
            apply_transition_fn=mock_apply_transition,
            idempotency_store=None,
            correlation_id=correlation_id,
        )

        assert result["candidates_checked"] == 0
        assert result["candidates_promoted"] == 0
        assert result["provisionals_checked"] == 0
        assert result["provisionals_promoted"] == 0
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_candidate_promoted_to_provisional(
        self,
        correlation_id: UUID,
    ) -> None:
        """Eligible candidate with OBSERVED evidence -> promoted to PROVISIONAL."""
        repo = MockPatternRepository()
        pattern = _make_pattern(
            status="candidate",
            evidence_tier="observed",
            injection_count=5,
            success_count=4,
            failure_count=1,
        )
        repo.candidate_patterns = [pattern]

        transition_calls: list[dict[str, Any]] = []

        async def mock_apply_transition(
            *_args: Any,
            **kwargs: Any,
        ) -> MockTransitionResult:
            transition_calls.append(kwargs)
            return MockTransitionResult(
                success=True,
                pattern_id=kwargs["pattern_id"],
                from_status="candidate",
                to_status="provisional",
            )

        result = await handle_auto_promote_check(
            repository=repo,
            apply_transition_fn=mock_apply_transition,
            idempotency_store=None,
            correlation_id=correlation_id,
        )

        assert result["candidates_checked"] == 1
        assert result["candidates_promoted"] == 1
        assert len(transition_calls) == 1
        assert transition_calls[0]["trigger"] == "auto_promote_evidence_gate"

    @pytest.mark.asyncio
    async def test_provisional_promoted_to_validated(
        self,
        correlation_id: UUID,
    ) -> None:
        """Eligible provisional with MEASURED evidence -> promoted to VALIDATED."""
        repo = MockPatternRepository()
        pattern = _make_pattern(
            status="provisional",
            evidence_tier="measured",
            injection_count=10,
            success_count=8,
            failure_count=2,
        )
        repo.provisional_patterns = [pattern]

        transition_calls: list[dict[str, Any]] = []

        async def mock_apply_transition(
            *_args: Any,
            **kwargs: Any,
        ) -> MockTransitionResult:
            transition_calls.append(kwargs)
            return MockTransitionResult(
                success=True,
                pattern_id=kwargs["pattern_id"],
                from_status="provisional",
                to_status="validated",
            )

        result = await handle_auto_promote_check(
            repository=repo,
            apply_transition_fn=mock_apply_transition,
            idempotency_store=None,
            correlation_id=correlation_id,
        )

        assert result["provisionals_checked"] == 1
        assert result["provisionals_promoted"] == 1

    @pytest.mark.asyncio
    async def test_candidate_insufficient_metrics_skipped(
        self,
        correlation_id: UUID,
    ) -> None:
        """Candidate with OBSERVED but low injection count -> not promoted."""
        repo = MockPatternRepository()
        pattern = _make_pattern(
            status="candidate",
            evidence_tier="observed",
            injection_count=1,  # Below threshold
            success_count=1,
            failure_count=0,
        )
        repo.candidate_patterns = [pattern]

        async def mock_apply_transition(
            *_args: Any,
            **_kwargs: Any,
        ) -> MockTransitionResult:
            raise AssertionError("Should not be called")

        result = await handle_auto_promote_check(
            repository=repo,
            apply_transition_fn=mock_apply_transition,
            idempotency_store=None,
            correlation_id=correlation_id,
        )

        assert result["candidates_checked"] == 1
        assert result["candidates_promoted"] == 0

    @pytest.mark.asyncio
    async def test_transition_failure_isolated(
        self,
        correlation_id: UUID,
    ) -> None:
        """Failed transition doesn't block other promotions."""
        repo = MockPatternRepository()
        p1 = _make_pattern(status="candidate", evidence_tier="observed")
        p2 = _make_pattern(status="candidate", evidence_tier="observed")
        repo.candidate_patterns = [p1, p2]

        call_count = 0

        async def mock_apply_transition(
            *_args: Any,
            **kwargs: Any,
        ) -> MockTransitionResult:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("DB connection lost")
            return MockTransitionResult(
                success=True,
                pattern_id=kwargs["pattern_id"],
            )

        result = await handle_auto_promote_check(
            repository=repo,
            apply_transition_fn=mock_apply_transition,
            idempotency_store=None,
            correlation_id=correlation_id,
        )

        assert result["candidates_checked"] == 2
        assert result["candidates_promoted"] == 1
        # Both results recorded (one success, one failure)
        assert len(result["results"]) == 2

    @pytest.mark.asyncio
    async def test_both_phases_run(
        self,
        correlation_id: UUID,
    ) -> None:
        """Both candidate and provisional phases run in single call."""
        repo = MockPatternRepository()
        repo.candidate_patterns = [
            _make_pattern(status="candidate", evidence_tier="observed"),
        ]
        repo.provisional_patterns = [
            _make_pattern(status="provisional", evidence_tier="measured"),
        ]

        async def mock_apply_transition(
            *_args: Any,
            **kwargs: Any,
        ) -> MockTransitionResult:
            return MockTransitionResult(
                success=True,
                pattern_id=kwargs["pattern_id"],
            )

        result = await handle_auto_promote_check(
            repository=repo,
            apply_transition_fn=mock_apply_transition,
            idempotency_store=None,
            correlation_id=correlation_id,
        )

        assert result["candidates_promoted"] == 1
        assert result["provisionals_promoted"] == 1
        assert len(result["results"]) == 2


# =============================================================================
# Tests: Protocol Conformance
# =============================================================================


class TestProtocolConformance:
    """Verify mocks conform to protocols."""

    def test_mock_repository_implements_protocol(self) -> None:
        from omniintelligence.nodes.node_pattern_promotion_effect.handlers.handler_auto_promote import (
            ProtocolPatternRepository,
        )

        repo = MockPatternRepository()
        assert isinstance(repo, ProtocolPatternRepository)
