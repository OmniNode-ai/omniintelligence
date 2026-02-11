# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for handler_attribution_binder (L1 Attribution Bridge).

Tests cover:
- Evidence tier computation (UNMEASURED -> OBSERVED -> MEASURED -> VERIFIED)
- run_id = None path (tier updates to OBSERVED, no attribution JSON)
- run_id present + success path (tier updates to MEASURED)
- Monotonic enforcement (current MEASURED + new OBSERVED does not downgrade)
- Atomicity (attribution insert + evidence_tier update in same transaction)
- Pattern not found handling

Reference: OMN-2133
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest
from omnibase_core.enums.pattern_learning import EnumEvidenceTier

from omniintelligence.nodes.node_pattern_feedback_effect.handlers.handler_attribution_binder import (
    ProtocolPatternRepository,
    compute_evidence_tier,
    handle_attribution_binding,
)

pytestmark = pytest.mark.unit


# =============================================================================
# Mock Infrastructure
# =============================================================================


class MockRecord(dict):
    """Dict subclass mimicking asyncpg.Record with attribute access."""

    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


@dataclass
class PatternState:
    """In-memory pattern row state."""

    id: UUID
    evidence_tier: str = "unmeasured"


@dataclass
class AttributionRecord:
    """In-memory attribution record."""

    id: UUID
    pattern_id: UUID
    session_id: UUID
    run_id: UUID | None
    evidence_tier: str
    measured_attribution_json: str | None
    correlation_id: UUID | None


class MockPatternRepository:
    """Mock repository for attribution binder tests."""

    def __init__(self) -> None:
        self.patterns: dict[UUID, PatternState] = {}
        self.attributions: list[AttributionRecord] = []
        self.injection_run_ids: dict[UUID, UUID | None] = {}  # session_id -> run_id
        self.queries_executed: list[str] = []
        self._next_attribution_id: UUID = uuid4()

    async def fetch(self, query: str, *args: Any) -> list[Mapping[str, Any]]:
        self.queries_executed.append(query.strip()[:80])
        return []

    async def fetchrow(self, query: str, *args: Any) -> Mapping[str, Any] | None:
        self.queries_executed.append(query.strip()[:80])

        if "evidence_tier" in query and "learned_patterns" in query and "FROM" in query:
            # SQL_GET_PATTERN_EVIDENCE_TIER
            pattern_id = args[0] if args else None
            if pattern_id in self.patterns:
                p = self.patterns[pattern_id]
                return MockRecord(id=p.id, evidence_tier=p.evidence_tier)
            return None

        if "run_id" in query and "pattern_injections" in query:
            # SQL_GET_SESSION_RUN_ID
            session_id = args[0] if args else None
            run_id = self.injection_run_ids.get(session_id)
            if run_id is not None:
                return MockRecord(run_id=run_id)
            return None

        if "pattern_measured_attributions" in query and "INSERT" in query:
            # SQL_INSERT_ATTRIBUTION
            attr_id = self._next_attribution_id
            self._next_attribution_id = uuid4()
            record = AttributionRecord(
                id=attr_id,
                pattern_id=args[0],
                session_id=args[1],
                run_id=args[2],
                evidence_tier=args[3],
                measured_attribution_json=args[4],
                correlation_id=args[5],
            )
            self.attributions.append(record)
            return MockRecord(id=attr_id)

        if "COUNT" in query and "pattern_measured_attributions" in query:
            pattern_id = args[0] if args else None
            count = sum(1 for a in self.attributions if a.pattern_id == pattern_id)
            return MockRecord(count=count)

        if "run_result" in query and "pattern_measured_attributions" in query:
            return None

        return None

    async def execute(self, query: str, *args: Any) -> str:
        self.queries_executed.append(query.strip()[:80])

        if "UPDATE learned_patterns" in query and "evidence_tier" in query:
            # SQL_UPDATE_EVIDENCE_TIER_MONOTONIC
            pattern_id = args[0]
            new_tier = args[1]
            if pattern_id in self.patterns:
                current = self.patterns[pattern_id].evidence_tier
                current_weight = _tier_weight(current)
                new_weight = _tier_weight(new_tier)
                if new_weight > current_weight:
                    self.patterns[pattern_id].evidence_tier = new_tier
                    return "UPDATE 1"
            return "UPDATE 0"

        return "UPDATE 0"


def _tier_weight(tier: str) -> int:
    weights = {"unmeasured": 0, "observed": 10, "measured": 20, "verified": 30}
    return weights.get(tier, 0)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def pattern_id() -> UUID:
    return uuid4()


@pytest.fixture
def session_id() -> UUID:
    return uuid4()


@pytest.fixture
def correlation_id() -> UUID:
    return uuid4()


@pytest.fixture
def run_id() -> UUID:
    return uuid4()


@pytest.fixture
def repo(pattern_id: UUID) -> MockPatternRepository:
    repo = MockPatternRepository()
    repo.patterns[pattern_id] = PatternState(id=pattern_id, evidence_tier="unmeasured")
    return repo


# =============================================================================
# Tests: compute_evidence_tier (Pure Function)
# =============================================================================


class TestComputeEvidenceTier:
    """Tests for the pure evidence tier computation function."""

    def test_no_run_id_yields_observed(self) -> None:
        result = compute_evidence_tier(
            run_id=None,
            run_result=None,
            current_tier=EnumEvidenceTier.UNMEASURED,
        )
        assert result == EnumEvidenceTier.OBSERVED

    def test_run_id_success_yields_measured(self) -> None:
        result = compute_evidence_tier(
            run_id=uuid4(),
            run_result="success",
            current_tier=EnumEvidenceTier.UNMEASURED,
        )
        assert result == EnumEvidenceTier.MEASURED

    def test_run_id_failure_yields_observed(self) -> None:
        result = compute_evidence_tier(
            run_id=uuid4(),
            run_result="failure",
            current_tier=EnumEvidenceTier.UNMEASURED,
        )
        assert result == EnumEvidenceTier.OBSERVED

    def test_run_id_partial_yields_observed(self) -> None:
        result = compute_evidence_tier(
            run_id=uuid4(),
            run_result="partial",
            current_tier=EnumEvidenceTier.UNMEASURED,
        )
        assert result == EnumEvidenceTier.OBSERVED

    def test_monotonic_no_downgrade_measured_to_observed(self) -> None:
        """Current MEASURED + new computation yields OBSERVED -> stays MEASURED."""
        result = compute_evidence_tier(
            run_id=None,
            run_result=None,
            current_tier=EnumEvidenceTier.MEASURED,
        )
        assert result == EnumEvidenceTier.MEASURED

    def test_monotonic_no_downgrade_verified_to_measured(self) -> None:
        """Current VERIFIED + new computation yields MEASURED -> stays VERIFIED."""
        result = compute_evidence_tier(
            run_id=uuid4(),
            run_result="success",
            current_tier=EnumEvidenceTier.VERIFIED,
        )
        assert result == EnumEvidenceTier.VERIFIED

    def test_upgrade_observed_to_measured(self) -> None:
        """Current OBSERVED + successful run -> MEASURED."""
        result = compute_evidence_tier(
            run_id=uuid4(),
            run_result="success",
            current_tier=EnumEvidenceTier.OBSERVED,
        )
        assert result == EnumEvidenceTier.MEASURED

    @pytest.mark.parametrize(
        "current,expected",
        [
            (EnumEvidenceTier.UNMEASURED, EnumEvidenceTier.OBSERVED),
            (EnumEvidenceTier.OBSERVED, EnumEvidenceTier.OBSERVED),
            (EnumEvidenceTier.MEASURED, EnumEvidenceTier.MEASURED),
            (EnumEvidenceTier.VERIFIED, EnumEvidenceTier.VERIFIED),
        ],
    )
    def test_no_run_id_monotonic_across_all_tiers(
        self,
        current: EnumEvidenceTier,
        expected: EnumEvidenceTier,
    ) -> None:
        result = compute_evidence_tier(
            run_id=None,
            run_result=None,
            current_tier=current,
        )
        assert result == expected


# =============================================================================
# Tests: handle_attribution_binding (Handler)
# =============================================================================


class TestHandleAttributionBinding:
    """Tests for the main attribution binding handler."""

    @pytest.mark.asyncio
    async def test_empty_pattern_ids_returns_zero(
        self,
        session_id: UUID,
        repo: MockPatternRepository,
    ) -> None:
        result = await handle_attribution_binding(
            session_id=session_id,
            pattern_ids=[],
            conn=repo,
        )
        assert result["patterns_processed"] == 0
        assert result["patterns_updated"] == 0
        assert result["attributions_created"] == 0
        assert result["bindings"] == []

    @pytest.mark.asyncio
    async def test_run_id_none_updates_to_observed(
        self,
        pattern_id: UUID,
        session_id: UUID,
        correlation_id: UUID,
        repo: MockPatternRepository,
    ) -> None:
        """No run_id -> tier updates to OBSERVED, no attribution JSON."""
        result = await handle_attribution_binding(
            session_id=session_id,
            pattern_ids=[pattern_id],
            conn=repo,
            correlation_id=correlation_id,
        )

        assert result["patterns_processed"] == 1
        assert result["patterns_updated"] == 1
        assert result["attributions_created"] == 1

        binding = result["bindings"][0]
        assert binding["previous_tier"] == "unmeasured"
        assert binding["computed_tier"] == "observed"
        assert binding["tier_updated"] is True
        assert binding["run_id"] is None

        # Check attribution record
        assert len(repo.attributions) == 1
        attr = repo.attributions[0]
        assert attr.pattern_id == pattern_id
        assert attr.session_id == session_id
        assert attr.run_id is None
        assert attr.evidence_tier == "observed"
        assert attr.measured_attribution_json is None  # No JSON for run_id=None

        # Check pattern state updated
        assert repo.patterns[pattern_id].evidence_tier == "observed"

    @pytest.mark.asyncio
    async def test_run_id_present_success_updates_to_measured(
        self,
        pattern_id: UUID,
        session_id: UUID,
        run_id: UUID,
        repo: MockPatternRepository,
    ) -> None:
        """run_id + success -> tier updates to MEASURED, has attribution JSON."""
        result = await handle_attribution_binding(
            session_id=session_id,
            pattern_ids=[pattern_id],
            conn=repo,
            run_id_override=run_id,
            run_result_override="success",
        )

        assert result["patterns_updated"] == 1
        binding = result["bindings"][0]
        assert binding["computed_tier"] == "measured"
        assert binding["tier_updated"] is True
        assert binding["run_id"] == run_id

        # Check attribution record has JSON
        attr = repo.attributions[0]
        assert attr.measured_attribution_json is not None
        parsed = json.loads(attr.measured_attribution_json)
        assert parsed["run_id"] == str(run_id)
        assert parsed["run_result"] == "success"

        # Check pattern state
        assert repo.patterns[pattern_id].evidence_tier == "measured"

    @pytest.mark.asyncio
    async def test_monotonic_measured_not_downgraded_by_observed(
        self,
        pattern_id: UUID,
        session_id: UUID,
        repo: MockPatternRepository,
    ) -> None:
        """Pattern at MEASURED + no run_id -> stays MEASURED (monotonic)."""
        repo.patterns[pattern_id].evidence_tier = "measured"

        result = await handle_attribution_binding(
            session_id=session_id,
            pattern_ids=[pattern_id],
            conn=repo,
        )

        binding = result["bindings"][0]
        assert binding["previous_tier"] == "measured"
        assert binding["computed_tier"] == "measured"
        assert binding["tier_updated"] is False

        # Attribution record still created (audit trail)
        assert result["attributions_created"] == 1
        # But pattern tier not changed
        assert repo.patterns[pattern_id].evidence_tier == "measured"

    @pytest.mark.asyncio
    async def test_pattern_not_found_skipped(
        self,
        session_id: UUID,
    ) -> None:
        """Missing pattern is skipped gracefully."""
        repo = MockPatternRepository()
        missing_id = uuid4()

        result = await handle_attribution_binding(
            session_id=session_id,
            pattern_ids=[missing_id],
            conn=repo,
        )

        assert result["patterns_processed"] == 1
        assert result["patterns_updated"] == 0
        assert result["attributions_created"] == 0

        binding = result["bindings"][0]
        assert binding["previous_tier"] == "unknown"
        assert binding["tier_updated"] is False

    @pytest.mark.asyncio
    async def test_multiple_patterns_independent(
        self,
        session_id: UUID,
    ) -> None:
        """Each pattern is processed independently."""
        repo = MockPatternRepository()
        p1 = uuid4()
        p2 = uuid4()
        repo.patterns[p1] = PatternState(id=p1, evidence_tier="unmeasured")
        repo.patterns[p2] = PatternState(id=p2, evidence_tier="observed")

        result = await handle_attribution_binding(
            session_id=session_id,
            pattern_ids=[p1, p2],
            conn=repo,
        )

        assert result["patterns_processed"] == 2
        # p1: unmeasured -> observed (updated)
        # p2: observed -> observed (not updated, already there)
        assert result["patterns_updated"] == 1
        assert result["attributions_created"] == 2

    @pytest.mark.asyncio
    async def test_run_id_from_session_injections(
        self,
        pattern_id: UUID,
        session_id: UUID,
        run_id: UUID,
        repo: MockPatternRepository,
    ) -> None:
        """run_id looked up from pattern_injections when not provided."""
        repo.injection_run_ids[session_id] = run_id

        result = await handle_attribution_binding(
            session_id=session_id,
            pattern_ids=[pattern_id],
            conn=repo,
        )

        binding = result["bindings"][0]
        assert binding["run_id"] == run_id
        # Without run_result_override, result is None -> OBSERVED path
        assert binding["computed_tier"] == "observed"

    @pytest.mark.asyncio
    async def test_atomicity_both_operations_use_same_conn(
        self,
        pattern_id: UUID,
        session_id: UUID,
        repo: MockPatternRepository,
    ) -> None:
        """Verify that insert attribution and update tier use same connection."""
        await handle_attribution_binding(
            session_id=session_id,
            pattern_ids=[pattern_id],
            conn=repo,
        )

        # Check that both queries were executed
        insert_queries = [q for q in repo.queries_executed if "INSERT" in q]
        update_queries = [
            q for q in repo.queries_executed if "UPDATE learned_patterns" in q
        ]
        assert len(insert_queries) == 1
        assert len(update_queries) == 1

    @pytest.mark.asyncio
    async def test_run_id_override_without_result_returns_error(
        self,
        pattern_id: UUID,
        session_id: UUID,
        repo: MockPatternRepository,
    ) -> None:
        """run_id_override without run_result_override -> structured error."""
        result = await handle_attribution_binding(
            session_id=session_id,
            pattern_ids=[pattern_id],
            conn=repo,
            run_id_override=uuid4(),
            run_result_override=None,
        )
        assert result["patterns_processed"] == 0
        assert result["error_message"] is not None
        assert "run_result_override" in result["error_message"]


# =============================================================================
# Tests: Protocol Conformance
# =============================================================================


class TestProtocolConformance:
    """Verify mock conforms to protocol."""

    def test_mock_implements_protocol(self) -> None:
        repo = MockPatternRepository()
        assert isinstance(repo, ProtocolPatternRepository)
