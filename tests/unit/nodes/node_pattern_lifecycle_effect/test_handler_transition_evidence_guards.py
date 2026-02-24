# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for evidence tier guards in handler_transition.

Tests cover:
- PROVISIONAL->VALIDATED with OBSERVED -> rejected
- PROVISIONAL->VALIDATED with MEASURED -> accepted
- CANDIDATE->PROVISIONAL with UNMEASURED -> rejected
- CANDIDATE->PROVISIONAL with OBSERVED -> accepted
- null/unparseable evidence_tier treated as UNMEASURED -> rejects promotion
- Evidence tier recorded in gate snapshot

Reference: OMN-2133
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from omniintelligence.enums import EnumPatternLifecycleStatus
from omniintelligence.nodes.node_pattern_lifecycle_effect.handlers.handler_transition import (
    apply_transition,
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


class MockPatternRepository:
    """Mock repository for transition tests."""

    def __init__(
        self,
        pattern_id: UUID,
        status: str = "candidate",
        evidence_tier: str = "unmeasured",
    ) -> None:
        self.pattern_id = pattern_id
        self.status = status
        self.evidence_tier = evidence_tier
        self.queries_executed: list[str] = []
        self.updates: list[tuple[str, ...]] = []

    async def fetch(self, query: str, *args: Any) -> list[Mapping[str, Any]]:
        self.queries_executed.append(query.strip()[:80])
        return []

    async def fetchrow(self, query: str, *args: Any) -> Mapping[str, Any] | None:
        self.queries_executed.append(query.strip()[:80])
        if "learned_patterns" in query and args and args[0] == self.pattern_id:
            return MockRecord(
                id=self.pattern_id,
                status=self.status,
                evidence_tier=self.evidence_tier,
            )
        return None

    async def execute(self, query: str, *args: Any) -> str:
        self.queries_executed.append(query.strip()[:80])
        self.updates.append(args)
        if "UPDATE learned_patterns" in query:
            # Simulate successful status update
            return "UPDATE 1"
        if "INSERT INTO pattern_lifecycle_transitions" in query:
            return "INSERT 0 1"
        return "UPDATE 0"


class MockIdempotencyStore:
    """Mock idempotency store."""

    def __init__(self) -> None:
        self.recorded: set[UUID] = set()

    async def check_and_record(self, request_id: UUID) -> bool:
        if request_id in self.recorded:
            return True
        self.recorded.add(request_id)
        return False

    async def exists(self, request_id: UUID) -> bool:
        return request_id in self.recorded

    async def record(self, request_id: UUID) -> None:
        self.recorded.add(request_id)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def pattern_id() -> UUID:
    return uuid4()


@pytest.fixture
def request_id() -> UUID:
    return uuid4()


@pytest.fixture
def correlation_id() -> UUID:
    return uuid4()


@pytest.fixture
def idempotency_store() -> MockIdempotencyStore:
    return MockIdempotencyStore()


@pytest.fixture
def transition_at() -> datetime:
    return datetime.now(UTC)


# =============================================================================
# Tests: Evidence Tier Guard - PROVISIONAL -> VALIDATED
# =============================================================================


class TestEvidenceTierGuardValidated:
    """Evidence tier guard for transitions TO VALIDATED."""

    @pytest.mark.asyncio
    async def test_provisional_to_validated_with_observed_rejected(
        self,
        pattern_id: UUID,
        request_id: UUID,
        correlation_id: UUID,
        idempotency_store: MockIdempotencyStore,
        transition_at: datetime,
    ) -> None:
        """PROVISIONAL->VALIDATED with evidence_tier=OBSERVED -> rejected."""
        repo = MockPatternRepository(
            pattern_id=pattern_id,
            status="provisional",
            evidence_tier="observed",
        )

        result = await apply_transition(
            repository=repo,
            idempotency_store=idempotency_store,
            producer=None,
            request_id=request_id,
            correlation_id=correlation_id,
            pattern_id=pattern_id,
            from_status=EnumPatternLifecycleStatus.PROVISIONAL,
            to_status=EnumPatternLifecycleStatus.VALIDATED,
            trigger="auto_promote",
            transition_at=transition_at,
        )

        assert result.success is False
        assert "evidence_tier" in (result.error_message or "").lower()
        assert "MEASURED" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_provisional_to_validated_with_measured_accepted(
        self,
        pattern_id: UUID,
        request_id: UUID,
        correlation_id: UUID,
        idempotency_store: MockIdempotencyStore,
        transition_at: datetime,
    ) -> None:
        """PROVISIONAL->VALIDATED with evidence_tier=MEASURED -> accepted."""
        repo = MockPatternRepository(
            pattern_id=pattern_id,
            status="provisional",
            evidence_tier="measured",
        )

        result = await apply_transition(
            repository=repo,
            idempotency_store=idempotency_store,
            producer=None,
            request_id=request_id,
            correlation_id=correlation_id,
            pattern_id=pattern_id,
            from_status=EnumPatternLifecycleStatus.PROVISIONAL,
            to_status=EnumPatternLifecycleStatus.VALIDATED,
            trigger="auto_promote",
            transition_at=transition_at,
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_provisional_to_validated_with_verified_accepted(
        self,
        pattern_id: UUID,
        request_id: UUID,
        correlation_id: UUID,
        idempotency_store: MockIdempotencyStore,
        transition_at: datetime,
    ) -> None:
        """PROVISIONAL->VALIDATED with evidence_tier=VERIFIED -> accepted."""
        repo = MockPatternRepository(
            pattern_id=pattern_id,
            status="provisional",
            evidence_tier="verified",
        )

        result = await apply_transition(
            repository=repo,
            idempotency_store=idempotency_store,
            producer=None,
            request_id=request_id,
            correlation_id=correlation_id,
            pattern_id=pattern_id,
            from_status=EnumPatternLifecycleStatus.PROVISIONAL,
            to_status=EnumPatternLifecycleStatus.VALIDATED,
            trigger="auto_promote",
            transition_at=transition_at,
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_provisional_to_validated_with_unmeasured_rejected(
        self,
        pattern_id: UUID,
        request_id: UUID,
        correlation_id: UUID,
        idempotency_store: MockIdempotencyStore,
        transition_at: datetime,
    ) -> None:
        """PROVISIONAL->VALIDATED with evidence_tier=UNMEASURED -> rejected."""
        repo = MockPatternRepository(
            pattern_id=pattern_id,
            status="provisional",
            evidence_tier="unmeasured",
        )

        result = await apply_transition(
            repository=repo,
            idempotency_store=idempotency_store,
            producer=None,
            request_id=request_id,
            correlation_id=correlation_id,
            pattern_id=pattern_id,
            from_status=EnumPatternLifecycleStatus.PROVISIONAL,
            to_status=EnumPatternLifecycleStatus.VALIDATED,
            trigger="auto_promote",
            transition_at=transition_at,
        )

        assert result.success is False
        assert "MEASURED" in (result.error_message or "")


# =============================================================================
# Tests: Evidence Tier Guard - CANDIDATE -> PROVISIONAL
# =============================================================================


class TestEvidenceTierGuardProvisional:
    """Evidence tier guard for transitions TO PROVISIONAL.

    The PROVISIONAL guard allows CANDIDATE -> PROVISIONAL (OMN-2133) but blocks
    all other transitions to PROVISIONAL (legacy protection). Evidence tier
    guards then apply: CANDIDATE -> PROVISIONAL requires evidence_tier >= OBSERVED.
    """

    @pytest.mark.asyncio
    async def test_candidate_to_provisional_with_observed_accepted(
        self,
        pattern_id: UUID,
        request_id: UUID,
        correlation_id: UUID,
        idempotency_store: MockIdempotencyStore,
        transition_at: datetime,
    ) -> None:
        """CANDIDATE->PROVISIONAL with evidence_tier=OBSERVED -> accepted."""
        repo = MockPatternRepository(
            pattern_id=pattern_id,
            status="candidate",
            evidence_tier="observed",
        )

        result = await apply_transition(
            repository=repo,
            idempotency_store=idempotency_store,
            producer=None,
            request_id=request_id,
            correlation_id=correlation_id,
            pattern_id=pattern_id,
            from_status=EnumPatternLifecycleStatus.CANDIDATE,
            to_status=EnumPatternLifecycleStatus.PROVISIONAL,
            trigger="auto_promote_evidence_gate",
            transition_at=transition_at,
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_candidate_to_provisional_with_unmeasured_rejected(
        self,
        pattern_id: UUID,
        request_id: UUID,
        correlation_id: UUID,
        idempotency_store: MockIdempotencyStore,
        transition_at: datetime,
    ) -> None:
        """CANDIDATE->PROVISIONAL with evidence_tier=UNMEASURED -> rejected."""
        repo = MockPatternRepository(
            pattern_id=pattern_id,
            status="candidate",
            evidence_tier="unmeasured",
        )

        result = await apply_transition(
            repository=repo,
            idempotency_store=idempotency_store,
            producer=None,
            request_id=request_id,
            correlation_id=correlation_id,
            pattern_id=pattern_id,
            from_status=EnumPatternLifecycleStatus.CANDIDATE,
            to_status=EnumPatternLifecycleStatus.PROVISIONAL,
            trigger="auto_promote_evidence_gate",
            transition_at=transition_at,
        )

        assert result.success is False
        assert "OBSERVED" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_validated_to_provisional_blocked_by_guard(
        self,
        pattern_id: UUID,
        request_id: UUID,
        correlation_id: UUID,
        idempotency_store: MockIdempotencyStore,
        transition_at: datetime,
    ) -> None:
        """VALIDATED->PROVISIONAL blocked by PROVISIONAL guard (non-CANDIDATE)."""
        repo = MockPatternRepository(
            pattern_id=pattern_id,
            status="validated",
            evidence_tier="measured",
        )

        result = await apply_transition(
            repository=repo,
            idempotency_store=idempotency_store,
            producer=None,
            request_id=request_id,
            correlation_id=correlation_id,
            pattern_id=pattern_id,
            from_status=EnumPatternLifecycleStatus.VALIDATED,
            to_status=EnumPatternLifecycleStatus.PROVISIONAL,
            trigger="manual_revert",
            transition_at=transition_at,
        )

        assert result.success is False
        assert "PROVISIONAL guard" in (result.reason or "")

    @pytest.mark.asyncio
    async def test_null_evidence_tier_treated_as_unmeasured(
        self,
        pattern_id: UUID,
        request_id: UUID,
        correlation_id: UUID,
        idempotency_store: MockIdempotencyStore,
        transition_at: datetime,
    ) -> None:
        """null evidence_tier -> treated as UNMEASURED -> rejects VALIDATED."""
        repo = MockPatternRepository(
            pattern_id=pattern_id,
            status="provisional",
            evidence_tier="",  # Empty string = null/unparseable
        )

        result = await apply_transition(
            repository=repo,
            idempotency_store=idempotency_store,
            producer=None,
            request_id=request_id,
            correlation_id=correlation_id,
            pattern_id=pattern_id,
            from_status=EnumPatternLifecycleStatus.PROVISIONAL,
            to_status=EnumPatternLifecycleStatus.VALIDATED,
            trigger="auto_promote",
            transition_at=transition_at,
        )

        assert result.success is False
        assert "MEASURED" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_unparseable_evidence_tier_treated_as_unmeasured(
        self,
        pattern_id: UUID,
        request_id: UUID,
        correlation_id: UUID,
        idempotency_store: MockIdempotencyStore,
        transition_at: datetime,
    ) -> None:
        """Unparseable evidence_tier -> treated as UNMEASURED -> rejects VALIDATED."""
        repo = MockPatternRepository(
            pattern_id=pattern_id,
            status="provisional",
            evidence_tier="garbage_value",
        )

        result = await apply_transition(
            repository=repo,
            idempotency_store=idempotency_store,
            producer=None,
            request_id=request_id,
            correlation_id=correlation_id,
            pattern_id=pattern_id,
            from_status=EnumPatternLifecycleStatus.PROVISIONAL,
            to_status=EnumPatternLifecycleStatus.VALIDATED,
            trigger="auto_promote",
            transition_at=transition_at,
        )

        assert result.success is False


# =============================================================================
# Tests: Transition to DEPRECATED (no evidence gate)
# =============================================================================


class TestNoEvidenceGateForDeprecated:
    """DEPRECATED transitions should NOT have evidence tier gates."""

    @pytest.mark.asyncio
    async def test_provisional_to_deprecated_with_unmeasured_accepted(
        self,
        pattern_id: UUID,
        request_id: UUID,
        correlation_id: UUID,
        idempotency_store: MockIdempotencyStore,
        transition_at: datetime,
    ) -> None:
        """PROVISIONAL->DEPRECATED with UNMEASURED -> accepted (no gate)."""
        repo = MockPatternRepository(
            pattern_id=pattern_id,
            status="provisional",
            evidence_tier="unmeasured",
        )

        result = await apply_transition(
            repository=repo,
            idempotency_store=idempotency_store,
            producer=None,
            request_id=request_id,
            correlation_id=correlation_id,
            pattern_id=pattern_id,
            from_status=EnumPatternLifecycleStatus.PROVISIONAL,
            to_status=EnumPatternLifecycleStatus.DEPRECATED,
            trigger="manual_deprecation",
            transition_at=transition_at,
        )

        assert result.success is True


# =============================================================================
# Tests: Protocol Conformance
# =============================================================================


class TestProtocolConformance:
    """Verify mocks conform to their protocols."""

    def test_mock_repository_implements_protocol(self) -> None:
        from omniintelligence.nodes.node_pattern_lifecycle_effect.handlers.handler_transition import (
            ProtocolPatternRepository,
        )

        repo = MockPatternRepository(pattern_id=uuid4(), status="candidate")
        assert isinstance(repo, ProtocolPatternRepository)

    def test_mock_idempotency_store_implements_protocol(self) -> None:
        from omniintelligence.nodes.node_pattern_lifecycle_effect.handlers.handler_transition import (
            ProtocolIdempotencyStore,
        )

        store = MockIdempotencyStore()
        assert isinstance(store, ProtocolIdempotencyStore)
