# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for pattern demotion handler pure functions and async handler.

Tests cover:
    - Pure functions: calculate_success_rate, get_demotion_reason,
      is_cooldown_active, build_effective_thresholds, build_gate_snapshot,
      validate_threshold_overrides
    - Async handler: check_and_demote_patterns with mock repository
    - Async handler: demote_pattern with mock producer
    - Edge cases: empty patterns, no producer, dry run

Related:
    - OMN-2222 GAP 11: NodePatternDemotionEffect has zero unit tests
    - OMN-1681: Auto-demote logic for patterns
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from omniintelligence.nodes.node_pattern_demotion_effect.handlers.handler_demotion import (
    DEFAULT_COOLDOWN_HOURS,
    MAX_SUCCESS_RATE_FOR_DEMOTION,
    MIN_FAILURE_STREAK_FOR_DEMOTION,
    MIN_INJECTION_COUNT_FOR_DEMOTION,
    DemotionPatternRecord,
    build_effective_thresholds,
    build_gate_snapshot,
    calculate_hours_since_promotion,
    calculate_success_rate,
    check_and_demote_patterns,
    demote_pattern,
    get_demotion_reason,
    is_cooldown_active,
    validate_threshold_overrides,
)
from omniintelligence.nodes.node_pattern_demotion_effect.models import (
    ModelDemotionCheckRequest,
    ModelDemotionCheckResult,
    ModelDemotionGateSnapshot,
    ModelDemotionResult,
    ModelEffectiveThresholds,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def default_request() -> ModelDemotionCheckRequest:
    """Default demotion check request with default thresholds."""
    return ModelDemotionCheckRequest(
        dry_run=False,
        correlation_id=UUID("12345678-1234-1234-1234-123456789abc"),
    )


@pytest.fixture
def dry_run_request() -> ModelDemotionCheckRequest:
    """Dry-run demotion check request."""
    return ModelDemotionCheckRequest(
        dry_run=True,
        correlation_id=UUID("12345678-1234-1234-1234-123456789abc"),
    )


@pytest.fixture
def default_thresholds() -> ModelEffectiveThresholds:
    """Default effective thresholds (no overrides)."""
    return ModelEffectiveThresholds(
        max_success_rate=MAX_SUCCESS_RATE_FOR_DEMOTION,
        min_failure_streak=MIN_FAILURE_STREAK_FOR_DEMOTION,
        min_injection_count=MIN_INJECTION_COUNT_FOR_DEMOTION,
        cooldown_hours=DEFAULT_COOLDOWN_HOURS,
        overrides_applied=False,
    )


@pytest.fixture
def healthy_pattern() -> DemotionPatternRecord:
    """Pattern that does NOT meet any demotion criteria."""
    return DemotionPatternRecord(
        id=uuid4(),
        pattern_signature="healthy_pattern_sig",
        injection_count_rolling_20=20,
        success_count_rolling_20=18,
        failure_count_rolling_20=2,
        failure_streak=0,
        promoted_at=datetime.now(UTC) - timedelta(hours=48),
        is_disabled=False,
    )


@pytest.fixture
def low_success_pattern() -> DemotionPatternRecord:
    """Pattern with low success rate (below 40% threshold)."""
    return DemotionPatternRecord(
        id=uuid4(),
        pattern_signature="low_success_sig",
        injection_count_rolling_20=15,
        success_count_rolling_20=3,
        failure_count_rolling_20=12,
        failure_streak=2,
        promoted_at=datetime.now(UTC) - timedelta(hours=48),
        is_disabled=False,
    )


@pytest.fixture
def failure_streak_pattern() -> DemotionPatternRecord:
    """Pattern with high failure streak (>= 5)."""
    return DemotionPatternRecord(
        id=uuid4(),
        pattern_signature="streak_sig",
        injection_count_rolling_20=8,
        success_count_rolling_20=3,
        failure_count_rolling_20=5,
        failure_streak=6,
        promoted_at=datetime.now(UTC) - timedelta(hours=48),
        is_disabled=False,
    )


@pytest.fixture
def disabled_pattern() -> DemotionPatternRecord:
    """Manually disabled pattern."""
    return DemotionPatternRecord(
        id=uuid4(),
        pattern_signature="disabled_sig",
        injection_count_rolling_20=5,
        success_count_rolling_20=4,
        failure_count_rolling_20=1,
        failure_streak=0,
        promoted_at=datetime.now(UTC) - timedelta(hours=1),  # Within cooldown
        is_disabled=True,
    )


@pytest.fixture
def cooldown_pattern() -> DemotionPatternRecord:
    """Pattern still within cooldown period."""
    return DemotionPatternRecord(
        id=uuid4(),
        pattern_signature="cooldown_sig",
        injection_count_rolling_20=15,
        success_count_rolling_20=3,
        failure_count_rolling_20=12,
        failure_streak=2,
        promoted_at=datetime.now(UTC) - timedelta(hours=2),  # Only 2 hours ago
        is_disabled=False,
    )


@pytest.fixture
def mock_repository() -> AsyncMock:
    """Mock ProtocolPatternRepository."""
    repo = AsyncMock()
    repo.fetch = AsyncMock(return_value=[])
    repo.execute = AsyncMock(return_value="UPDATE 0")
    return repo


@pytest.fixture
def mock_producer() -> AsyncMock:
    """Mock ProtocolKafkaPublisher."""
    producer = AsyncMock()
    producer.publish = AsyncMock()
    return producer


# =============================================================================
# Tests: calculate_success_rate (pure function)
# =============================================================================


@pytest.mark.unit
class TestCalculateSuccessRate:
    """Tests for calculate_success_rate pure function."""

    def test_normal_rate(self) -> None:
        """Normal success rate calculation."""
        pattern = DemotionPatternRecord(
            id=uuid4(),
            pattern_signature="test",
            success_count_rolling_20=8,
            failure_count_rolling_20=2,
        )
        assert calculate_success_rate(pattern) == pytest.approx(0.8)

    def test_zero_total(self) -> None:
        """Returns 0.0 when no outcomes recorded."""
        pattern = DemotionPatternRecord(
            id=uuid4(),
            pattern_signature="test",
            success_count_rolling_20=0,
            failure_count_rolling_20=0,
        )
        assert calculate_success_rate(pattern) == 0.0

    def test_none_values(self) -> None:
        """Handles None values (defaults to 0)."""
        pattern = DemotionPatternRecord(
            id=uuid4(),
            pattern_signature="test",
            success_count_rolling_20=None,
            failure_count_rolling_20=None,
        )
        assert calculate_success_rate(pattern) == 0.0

    def test_all_success(self) -> None:
        """100% success rate."""
        pattern = DemotionPatternRecord(
            id=uuid4(),
            pattern_signature="test",
            success_count_rolling_20=10,
            failure_count_rolling_20=0,
        )
        assert calculate_success_rate(pattern) == 1.0

    def test_all_failure(self) -> None:
        """0% success rate."""
        pattern = DemotionPatternRecord(
            id=uuid4(),
            pattern_signature="test",
            success_count_rolling_20=0,
            failure_count_rolling_20=10,
        )
        assert calculate_success_rate(pattern) == 0.0


# =============================================================================
# Tests: get_demotion_reason (pure function)
# =============================================================================


@pytest.mark.unit
class TestGetDemotionReason:
    """Tests for get_demotion_reason pure function."""

    def test_healthy_pattern_returns_none(
        self,
        healthy_pattern: DemotionPatternRecord,
        default_thresholds: ModelEffectiveThresholds,
    ) -> None:
        """Healthy pattern should not be demoted."""
        reason = get_demotion_reason(healthy_pattern, default_thresholds)
        assert reason is None

    def test_manual_disable_returns_reason(
        self,
        disabled_pattern: DemotionPatternRecord,
        default_thresholds: ModelEffectiveThresholds,
    ) -> None:
        """Manually disabled pattern returns manual_disable reason."""
        reason = get_demotion_reason(disabled_pattern, default_thresholds)
        assert reason == "manual_disable"

    def test_failure_streak_returns_reason(
        self,
        failure_streak_pattern: DemotionPatternRecord,
        default_thresholds: ModelEffectiveThresholds,
    ) -> None:
        """Pattern with high failure streak triggers demotion."""
        reason = get_demotion_reason(failure_streak_pattern, default_thresholds)
        assert reason is not None
        assert "failure_streak" in reason

    def test_low_success_rate_returns_reason(
        self,
        low_success_pattern: DemotionPatternRecord,
        default_thresholds: ModelEffectiveThresholds,
    ) -> None:
        """Pattern with low success rate triggers demotion."""
        reason = get_demotion_reason(low_success_pattern, default_thresholds)
        assert reason is not None
        assert "low_success_rate" in reason

    def test_insufficient_data_returns_none(
        self,
        default_thresholds: ModelEffectiveThresholds,
    ) -> None:
        """Pattern with too few injections is not demoted (insufficient data)."""
        pattern = DemotionPatternRecord(
            id=uuid4(),
            pattern_signature="test",
            injection_count_rolling_20=3,  # Below min_injection_count (10)
            success_count_rolling_20=0,
            failure_count_rolling_20=3,
            failure_streak=3,
            is_disabled=False,
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        # Failure streak of 3 is below threshold of 5
        # Low success rate won't trigger because injection_count < 10
        assert reason is None


# =============================================================================
# Tests: is_cooldown_active (pure function)
# =============================================================================


@pytest.mark.unit
class TestIsCooldownActive:
    """Tests for is_cooldown_active pure function."""

    def test_cooldown_active(self, cooldown_pattern: DemotionPatternRecord) -> None:
        """Pattern promoted 2 hours ago should have active cooldown (default 24h)."""
        assert is_cooldown_active(cooldown_pattern, DEFAULT_COOLDOWN_HOURS) is True

    def test_cooldown_elapsed(self, healthy_pattern: DemotionPatternRecord) -> None:
        """Pattern promoted 48 hours ago should have elapsed cooldown."""
        assert is_cooldown_active(healthy_pattern, DEFAULT_COOLDOWN_HOURS) is False

    def test_no_promoted_at(self) -> None:
        """Pattern without promoted_at should not have active cooldown."""
        pattern = DemotionPatternRecord(
            id=uuid4(),
            pattern_signature="test",
            promoted_at=None,
        )
        assert is_cooldown_active(pattern, DEFAULT_COOLDOWN_HOURS) is False

    def test_zero_cooldown(self, cooldown_pattern: DemotionPatternRecord) -> None:
        """Zero cooldown hours should never have active cooldown."""
        assert is_cooldown_active(cooldown_pattern, 0) is False


# =============================================================================
# Tests: build_effective_thresholds (pure function)
# =============================================================================


@pytest.mark.unit
class TestBuildEffectiveThresholds:
    """Tests for build_effective_thresholds pure function."""

    def test_default_thresholds_no_overrides(
        self, default_request: ModelDemotionCheckRequest
    ) -> None:
        """Default request produces thresholds with overrides_applied=False."""
        thresholds = build_effective_thresholds(default_request)
        assert thresholds.overrides_applied is False
        assert thresholds.max_success_rate == MAX_SUCCESS_RATE_FOR_DEMOTION
        assert thresholds.min_failure_streak == MIN_FAILURE_STREAK_FOR_DEMOTION

    def test_custom_thresholds_with_overrides(self) -> None:
        """Custom thresholds produce overrides_applied=True."""
        request = ModelDemotionCheckRequest(
            max_success_rate=0.3,
            allow_threshold_override=True,
        )
        thresholds = build_effective_thresholds(request)
        assert thresholds.overrides_applied is True
        assert thresholds.max_success_rate == 0.3


# =============================================================================
# Tests: validate_threshold_overrides (pure function)
# =============================================================================


@pytest.mark.unit
class TestValidateThresholdOverrides:
    """Tests for validate_threshold_overrides pure function."""

    def test_default_thresholds_pass(
        self, default_request: ModelDemotionCheckRequest
    ) -> None:
        """Default thresholds pass validation."""
        validate_threshold_overrides(default_request)  # Should not raise

    def test_override_without_flag_raises(self) -> None:
        """Non-default thresholds without allow_threshold_override raises."""
        request = ModelDemotionCheckRequest(
            max_success_rate=0.3,
            allow_threshold_override=False,
        )
        with pytest.raises(ValueError, match="allow_threshold_override"):
            validate_threshold_overrides(request)

    def test_override_with_flag_passes(self) -> None:
        """Non-default thresholds with allow_threshold_override=True passes."""
        request = ModelDemotionCheckRequest(
            max_success_rate=0.3,
            allow_threshold_override=True,
        )
        validate_threshold_overrides(request)  # Should not raise


# =============================================================================
# Tests: build_gate_snapshot (pure function)
# =============================================================================


@pytest.mark.unit
class TestBuildGateSnapshot:
    """Tests for build_gate_snapshot pure function."""

    def test_builds_snapshot_from_pattern(
        self, healthy_pattern: DemotionPatternRecord
    ) -> None:
        """Gate snapshot captures pattern metrics correctly."""
        snapshot = build_gate_snapshot(healthy_pattern)
        assert isinstance(snapshot, ModelDemotionGateSnapshot)
        assert snapshot.failure_streak == 0
        assert snapshot.disabled is False
        assert snapshot.injection_count_rolling_20 == 20

    def test_snapshot_with_none_values(self) -> None:
        """Gate snapshot handles None values in pattern record."""
        pattern = DemotionPatternRecord(
            id=uuid4(),
            pattern_signature="test",
            injection_count_rolling_20=None,
            failure_streak=None,
        )
        snapshot = build_gate_snapshot(pattern)
        assert snapshot.injection_count_rolling_20 == 0
        assert snapshot.failure_streak == 0


# =============================================================================
# Tests: calculate_hours_since_promotion (pure function)
# =============================================================================


@pytest.mark.unit
class TestCalculateHoursSincePromotion:
    """Tests for calculate_hours_since_promotion pure function."""

    def test_returns_none_for_none(self) -> None:
        """Returns None when promoted_at is None."""
        assert calculate_hours_since_promotion(None) is None

    def test_returns_positive_for_past(self) -> None:
        """Returns positive hours for past promotion."""
        promoted_at = datetime.now(UTC) - timedelta(hours=5)
        hours = calculate_hours_since_promotion(promoted_at)
        assert hours is not None
        assert hours >= 4.9

    def test_handles_naive_datetime(self) -> None:
        """Naive datetime handling is tested as a defensive measure.

        Production code should always use timezone-aware datetimes, but the
        handler gracefully handles naive datetimes by treating them as UTC.
        This prevents crashes if a naive datetime reaches the handler from
        an upstream caller that omits timezone info.
        """
        promoted_at = datetime.now() - timedelta(hours=2)
        hours = calculate_hours_since_promotion(promoted_at)
        assert hours is not None
        assert hours >= 1.9


# =============================================================================
# Tests: check_and_demote_patterns (async handler)
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestCheckAndDemotePatterns:
    """Tests for check_and_demote_patterns async handler."""

    async def test_no_validated_patterns_returns_zero(
        self,
        mock_repository: AsyncMock,
        default_request: ModelDemotionCheckRequest,
    ) -> None:
        """Returns empty result when no validated patterns exist."""
        mock_repository.fetch.return_value = []

        result = await check_and_demote_patterns(
            repository=mock_repository,
            producer=None,
            request=default_request,
        )

        assert isinstance(result, ModelDemotionCheckResult)
        assert result.patterns_checked == 0
        assert result.patterns_eligible == 0
        assert len(result.patterns_demoted) == 0

    async def test_dry_run_does_not_mutate(
        self,
        mock_repository: AsyncMock,
        mock_producer: AsyncMock,
        low_success_pattern: DemotionPatternRecord,
    ) -> None:
        """Dry run identifies demotable patterns without mutating."""
        mock_repository.fetch.return_value = [low_success_pattern]

        request = ModelDemotionCheckRequest(
            dry_run=True,
            correlation_id=uuid4(),
        )

        result = await check_and_demote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            request=request,
        )

        assert result.dry_run is True
        assert result.patterns_checked == 1
        # Producer should not have been called in dry run
        mock_producer.publish.assert_not_called()

    async def test_healthy_pattern_not_demoted(
        self,
        mock_repository: AsyncMock,
        healthy_pattern: DemotionPatternRecord,
        default_request: ModelDemotionCheckRequest,
    ) -> None:
        """Healthy pattern is not eligible for demotion."""
        mock_repository.fetch.return_value = [healthy_pattern]

        result = await check_and_demote_patterns(
            repository=mock_repository,
            producer=None,
            request=default_request,
        )

        assert result.patterns_checked == 1
        assert result.patterns_eligible == 0

    async def test_cooldown_skips_demotion(
        self,
        mock_repository: AsyncMock,
        cooldown_pattern: DemotionPatternRecord,
        default_request: ModelDemotionCheckRequest,
    ) -> None:
        """Pattern within cooldown period is skipped."""
        mock_repository.fetch.return_value = [cooldown_pattern]

        result = await check_and_demote_patterns(
            repository=mock_repository,
            producer=None,
            request=default_request,
        )

        assert result.patterns_skipped_cooldown >= 1

    async def test_disabled_pattern_bypasses_cooldown(
        self,
        mock_repository: AsyncMock,
        mock_producer: AsyncMock,
        disabled_pattern: DemotionPatternRecord,
        default_request: ModelDemotionCheckRequest,
    ) -> None:
        """Manually disabled pattern bypasses cooldown period."""
        mock_repository.fetch.return_value = [disabled_pattern]

        result = await check_and_demote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            request=default_request,
        )

        # Disabled pattern should be eligible despite cooldown
        assert result.patterns_eligible >= 1
        assert result.patterns_skipped_cooldown == 0

    async def test_invalid_threshold_override_raises(
        self,
        mock_repository: AsyncMock,
    ) -> None:
        """Invalid threshold overrides raise ValueError."""
        request = ModelDemotionCheckRequest(
            max_success_rate=0.3,
            allow_threshold_override=False,
        )

        with pytest.raises(ValueError, match="allow_threshold_override"):
            await check_and_demote_patterns(
                repository=mock_repository,
                producer=None,
                request=request,
            )


# =============================================================================
# Tests: demote_pattern (async handler)
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestDemotePattern:
    """Tests for demote_pattern async handler."""

    async def test_no_producer_returns_kafka_unavailable(
        self,
        mock_repository: AsyncMock,
        low_success_pattern: DemotionPatternRecord,
        default_thresholds: ModelEffectiveThresholds,
    ) -> None:
        """Returns kafka_producer_unavailable when producer is None."""
        result = await demote_pattern(
            repository=mock_repository,
            producer=None,
            pattern_id=low_success_pattern["id"],
            pattern_data=low_success_pattern,
            reason="low_success_rate: 20.0%",
            thresholds=default_thresholds,
            correlation_id=uuid4(),
        )

        assert isinstance(result, ModelDemotionResult)
        assert result.reason == "kafka_producer_unavailable"
        assert result.deprecated_at is None

    async def test_with_producer_emits_lifecycle_event(
        self,
        mock_repository: AsyncMock,
        mock_producer: AsyncMock,
        low_success_pattern: DemotionPatternRecord,
        default_thresholds: ModelEffectiveThresholds,
    ) -> None:
        """With producer, emits lifecycle event and sets deprecated_at."""
        result = await demote_pattern(
            repository=mock_repository,
            producer=mock_producer,
            pattern_id=low_success_pattern["id"],
            pattern_data=low_success_pattern,
            reason="low_success_rate: 20.0%",
            thresholds=default_thresholds,
            correlation_id=uuid4(),
        )

        assert isinstance(result, ModelDemotionResult)
        assert result.deprecated_at is not None
        assert result.reason == "low_success_rate: 20.0%"
        mock_producer.publish.assert_called_once()

    async def test_kafka_failure_returns_publish_failed(
        self,
        mock_repository: AsyncMock,
        mock_producer: AsyncMock,
        low_success_pattern: DemotionPatternRecord,
        default_thresholds: ModelEffectiveThresholds,
    ) -> None:
        """Kafka publish failure returns kafka_publish_failed reason."""
        mock_producer.publish.side_effect = ConnectionError("Kafka down")

        result = await demote_pattern(
            repository=mock_repository,
            producer=mock_producer,
            pattern_id=low_success_pattern["id"],
            pattern_data=low_success_pattern,
            reason="low_success_rate: 20.0%",
            thresholds=default_thresholds,
            correlation_id=uuid4(),
        )

        assert result.deprecated_at is None
        assert "kafka_publish_failed" in result.reason

    async def test_manual_disable_sets_admin_actor(
        self,
        mock_repository: AsyncMock,
        mock_producer: AsyncMock,
        disabled_pattern: DemotionPatternRecord,
        default_thresholds: ModelEffectiveThresholds,
    ) -> None:
        """Manual disable demotion uses admin actor type."""
        result = await demote_pattern(
            repository=mock_repository,
            producer=mock_producer,
            pattern_id=disabled_pattern["id"],
            pattern_data=disabled_pattern,
            reason="manual_disable",
            thresholds=default_thresholds,
            correlation_id=uuid4(),
        )

        assert result.deprecated_at is not None
        # Verify the publish call contained admin actor_type
        call_args = mock_producer.publish.call_args
        assert call_args is not None
        value = call_args.kwargs.get("value") or call_args[1].get("value")
        assert value["actor_type"] == "admin"
