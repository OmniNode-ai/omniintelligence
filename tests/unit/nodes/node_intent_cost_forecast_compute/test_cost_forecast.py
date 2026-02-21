"""Unit tests for intent cost and latency forecasting (OMN-2490).

Tests:
    - Baseline seeding produces non-empty distributions for all 8 intent classes
    - compute_forecast returns a frozen ModelIntentCostForecast
    - update_baseline accumulates real observations and increments sample_count
    - check_escalation fires when actual tokens exceed p90
    - compute_accuracy_record captures actual vs. forecasted correctly
    - Confidence interval widens as classification confidence drops
    - Forecast is deterministic given identical baselines
    - Baseline percentiles are monotonically ordered (p50 <= p90 <= p99)

Reference: OMN-2490
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from omnibase_core.enums.intelligence.enum_intent_class import EnumIntentClass

from omniintelligence.nodes.node_intent_cost_forecast_compute.handlers import (
    check_escalation,
    compute_accuracy_record,
    compute_forecast,
    update_baseline,
)
from omniintelligence.nodes.node_intent_cost_forecast_compute.models import (
    ModelCostBaseline,
    ModelIntentCostForecast,
    ModelIntentCostForecastInput,
    build_all_seeded_baselines,
    build_seeded_baseline,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_input(
    intent_class: EnumIntentClass = EnumIntentClass.REFACTOR,
    confidence: float = 0.9,
) -> ModelIntentCostForecastInput:
    return ModelIntentCostForecastInput(
        session_id="sess-test",
        correlation_id=str(uuid4()),
        intent_class=intent_class,
        confidence=confidence,
        requested_at=datetime.now(tz=UTC),
    )


def _make_baselines(
    intent_class: EnumIntentClass = EnumIntentClass.REFACTOR,
) -> dict[EnumIntentClass, ModelCostBaseline]:
    return {intent_class: build_seeded_baseline(intent_class)}


def _now() -> datetime:
    return datetime.now(tz=UTC)


# ---------------------------------------------------------------------------
# Baseline seeding tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.baseline
class TestBaselineSeeding:
    """Tests that seeded baselines are non-empty for all intent classes."""

    def test_build_seeded_baseline_has_token_samples(self) -> None:
        """Seeded baseline has non-empty token samples."""
        baseline = build_seeded_baseline(EnumIntentClass.REFACTOR)
        assert len(baseline.token_samples) > 0

    def test_build_seeded_baseline_has_latency_samples(self) -> None:
        """Seeded baseline has non-empty latency samples."""
        baseline = build_seeded_baseline(EnumIntentClass.FEATURE)
        assert len(baseline.latency_samples_ms) > 0

    def test_build_seeded_baseline_sample_count_is_zero(self) -> None:
        """Seeded baseline sample_count is 0 (synthetic seeds are not real observations)."""
        baseline = build_seeded_baseline(EnumIntentClass.ANALYSIS)
        assert baseline.sample_count == 0

    def test_build_all_seeded_baselines_covers_all_classes(self) -> None:
        """build_all_seeded_baselines covers all 8 EnumIntentClass values."""
        baselines = build_all_seeded_baselines()
        for cls in EnumIntentClass:
            assert cls in baselines, f"Missing baseline for {cls}"

    def test_seeded_baseline_percentiles_are_monotonic(self) -> None:
        """Seeded baseline p50 <= p90 <= p99."""
        for cls in EnumIntentClass:
            baseline = build_seeded_baseline(cls)
            assert baseline.token_p50 <= baseline.token_p90, (
                f"{cls}: p50={baseline.token_p50} > p90={baseline.token_p90}"
            )
            assert baseline.token_p90 <= baseline.token_p99, (
                f"{cls}: p90={baseline.token_p90} > p99={baseline.token_p99}"
            )

    def test_seeded_baseline_latency_percentiles_are_positive(self) -> None:
        """Seeded latency p50 and p90 are > 0 for all classes."""
        for cls in EnumIntentClass:
            baseline = build_seeded_baseline(cls)
            assert baseline.latency_p50_ms > 0, f"{cls}: latency_p50 == 0"
            assert baseline.latency_p90_ms > 0, f"{cls}: latency_p90 == 0"

    def test_seeded_baseline_cost_per_p50_is_positive(self) -> None:
        """Estimated cost at p50 is positive."""
        baseline = build_seeded_baseline(EnumIntentClass.FEATURE)
        cost = baseline.estimated_cost_usd(baseline.token_p50)
        assert cost > 0.0

    def test_different_classes_have_different_baselines(self) -> None:
        """ANALYSIS and FEATURE baselines should have different p50 medians."""
        analysis = build_seeded_baseline(EnumIntentClass.ANALYSIS)
        feature = build_seeded_baseline(EnumIntentClass.FEATURE)
        assert analysis.token_p50 != feature.token_p50


# ---------------------------------------------------------------------------
# Forecast computation tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.forecast
class TestComputeForecast:
    """Tests for compute_forecast handler."""

    def test_returns_frozen_forecast(self) -> None:
        """compute_forecast returns a frozen ModelIntentCostForecast."""
        from pydantic import ValidationError

        input_data = _make_input()
        baselines = _make_baselines()
        forecast = compute_forecast(input_data, baselines, forecasted_at=_now())

        assert isinstance(forecast, ModelIntentCostForecast)
        with pytest.raises((TypeError, ValidationError)):
            forecast.session_id = "mutated"  # type: ignore[misc]

    def test_forecast_session_id_matches_input(self) -> None:
        """Forecast session_id matches the input session_id."""
        input_data = _make_input()
        baselines = _make_baselines()
        forecast = compute_forecast(input_data, baselines, forecasted_at=_now())
        assert forecast.session_id == input_data.session_id

    def test_forecast_intent_class_matches_input(self) -> None:
        """Forecast intent_class matches the input intent_class."""
        input_data = _make_input(intent_class=EnumIntentClass.BUGFIX)
        baselines = {
            EnumIntentClass.BUGFIX: build_seeded_baseline(EnumIntentClass.BUGFIX)
        }
        forecast = compute_forecast(input_data, baselines, forecasted_at=_now())
        assert forecast.intent_class == EnumIntentClass.BUGFIX

    def test_estimated_tokens_p50_positive(self) -> None:
        """Estimated tokens p50 is positive for seeded baselines."""
        input_data = _make_input()
        baselines = _make_baselines()
        forecast = compute_forecast(input_data, baselines, forecasted_at=_now())
        assert forecast.estimated_tokens_p50 > 0

    def test_token_percentiles_ordered(self) -> None:
        """Forecast p50 <= p90 <= p99."""
        input_data = _make_input()
        baselines = _make_baselines()
        forecast = compute_forecast(input_data, baselines, forecasted_at=_now())
        assert forecast.estimated_tokens_p50 <= forecast.estimated_tokens_p90
        assert forecast.estimated_tokens_p90 <= forecast.estimated_tokens_p99

    def test_cost_usd_p50_positive(self) -> None:
        """Estimated cost at p50 is positive."""
        input_data = _make_input()
        baselines = _make_baselines()
        forecast = compute_forecast(input_data, baselines, forecasted_at=_now())
        assert forecast.estimated_cost_usd_p50 > 0.0

    def test_cost_usd_p90_gte_p50(self) -> None:
        """Cost at p90 >= cost at p50."""
        input_data = _make_input()
        baselines = _make_baselines()
        forecast = compute_forecast(input_data, baselines, forecasted_at=_now())
        assert forecast.estimated_cost_usd_p90 >= forecast.estimated_cost_usd_p50

    def test_latency_p50_positive(self) -> None:
        """Estimated latency p50 is positive."""
        input_data = _make_input()
        baselines = _make_baselines()
        forecast = compute_forecast(input_data, baselines, forecasted_at=_now())
        assert forecast.estimated_latency_ms_p50 > 0

    def test_escalation_threshold_equals_p90(self) -> None:
        """Escalation threshold equals the p90 token estimate."""
        input_data = _make_input()
        baselines = _make_baselines()
        forecast = compute_forecast(input_data, baselines, forecasted_at=_now())
        assert forecast.escalation_threshold_tokens == forecast.estimated_tokens_p90

    def test_baseline_sample_count_zero_for_seeded(self) -> None:
        """Seeded baselines report sample_count=0 (no real observations yet)."""
        input_data = _make_input()
        baselines = _make_baselines()
        forecast = compute_forecast(input_data, baselines, forecasted_at=_now())
        assert forecast.baseline_sample_count == 0

    def test_missing_baseline_uses_seeded_fallback(self) -> None:
        """compute_forecast falls back to seeded baseline when class is absent."""
        input_data = _make_input(intent_class=EnumIntentClass.MIGRATION)
        baselines: dict[EnumIntentClass, ModelCostBaseline] = {}  # empty registry
        forecast = compute_forecast(input_data, baselines, forecasted_at=_now())
        # Should not raise; should produce valid forecast
        assert forecast.estimated_tokens_p50 > 0

    def test_forecast_is_deterministic_for_same_baseline(self) -> None:
        """Same input + same baseline produces identical forecasts."""
        input_data = _make_input()
        baselines = _make_baselines()
        ts = _now()
        f1 = compute_forecast(input_data, baselines, forecasted_at=ts)
        f2 = compute_forecast(input_data, baselines, forecasted_at=ts)
        assert f1.estimated_tokens_p50 == f2.estimated_tokens_p50
        assert f1.confidence_interval == f2.confidence_interval

    def test_event_type_is_literal(self) -> None:
        """Forecast event_type is 'IntentCostForecast'."""
        input_data = _make_input()
        baselines = _make_baselines()
        forecast = compute_forecast(input_data, baselines, forecasted_at=_now())
        assert forecast.event_type == "IntentCostForecast"


# ---------------------------------------------------------------------------
# Confidence interval tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.forecast
class TestConfidenceInterval:
    """Tests for confidence interval scaling with classification confidence."""

    def test_high_confidence_produces_narrow_interval(self) -> None:
        """High classification confidence (0.9) yields a narrow interval."""
        input_data = _make_input(confidence=0.9)
        baselines = _make_baselines()
        forecast = compute_forecast(input_data, baselines, forecasted_at=_now())
        assert forecast.confidence_interval < 0.2

    def test_low_confidence_produces_wide_interval(self) -> None:
        """Low classification confidence (0.3) yields a wide interval."""
        input_data = _make_input(confidence=0.3)
        baselines = _make_baselines()
        forecast = compute_forecast(input_data, baselines, forecasted_at=_now())
        assert forecast.confidence_interval > 0.4

    def test_perfect_confidence_yields_zero_interval(self) -> None:
        """Confidence=1.0 yields confidence_interval=0.0."""
        input_data = _make_input(confidence=1.0)
        baselines = _make_baselines()
        forecast = compute_forecast(input_data, baselines, forecasted_at=_now())
        assert forecast.confidence_interval == 0.0

    def test_zero_confidence_yields_max_interval(self) -> None:
        """Confidence=0.0 yields confidence_interval=0.8 (MAX_CONFIDENCE_INTERVAL)."""
        input_data = _make_input(confidence=0.0)
        baselines = _make_baselines()
        forecast = compute_forecast(input_data, baselines, forecasted_at=_now())
        assert forecast.confidence_interval == pytest.approx(0.8)

    def test_confidence_interval_monotonically_decreases(self) -> None:
        """Higher confidence => narrower interval."""
        baselines = _make_baselines()
        ts = _now()
        forecasts = [
            compute_forecast(_make_input(confidence=c), baselines, forecasted_at=ts)
            for c in [0.2, 0.5, 0.8, 1.0]
        ]
        intervals = [f.confidence_interval for f in forecasts]
        assert intervals == sorted(intervals, reverse=True), (
            f"Expected decreasing intervals: {intervals}"
        )


# ---------------------------------------------------------------------------
# Baseline update tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.baseline
class TestUpdateBaseline:
    """Tests for update_baseline handler."""

    def test_update_increments_sample_count(self) -> None:
        """update_baseline increments sample_count by 1."""
        baseline = build_seeded_baseline(EnumIntentClass.REFACTOR)
        initial_count = baseline.sample_count
        update_baseline(baseline, actual_tokens=3000, actual_latency_ms=15000.0)
        assert baseline.sample_count == initial_count + 1

    def test_update_appends_token_sample(self) -> None:
        """update_baseline appends the token count to token_samples."""
        baseline = build_seeded_baseline(EnumIntentClass.REFACTOR)
        initial_len = len(baseline.token_samples)
        update_baseline(baseline, actual_tokens=9999, actual_latency_ms=5000.0)
        assert len(baseline.token_samples) == initial_len + 1
        assert baseline.token_samples[-1] == 9999

    def test_update_appends_latency_sample(self) -> None:
        """update_baseline appends the latency observation to latency_samples_ms."""
        baseline = build_seeded_baseline(EnumIntentClass.BUGFIX)
        initial_len = len(baseline.latency_samples_ms)
        update_baseline(baseline, actual_tokens=2000, actual_latency_ms=7777.5)
        assert len(baseline.latency_samples_ms) == initial_len + 1
        assert baseline.latency_samples_ms[-1] == pytest.approx(7777.5)

    def test_multiple_updates_shift_percentiles(self) -> None:
        """After many high-token updates, p90 should rise above the original seeded value."""
        baseline = build_seeded_baseline(EnumIntentClass.ANALYSIS)
        original_p90 = baseline.token_p90
        for _ in range(20):
            update_baseline(baseline, actual_tokens=50_000, actual_latency_ms=60_000.0)
        assert baseline.token_p90 > original_p90

    def test_sample_count_accumulates_across_calls(self) -> None:
        """sample_count increases by 1 for each call to update_baseline."""
        baseline = build_seeded_baseline(EnumIntentClass.CONFIGURATION)
        for i in range(5):
            update_baseline(baseline, actual_tokens=1000 + i, actual_latency_ms=5000.0)
        assert baseline.sample_count == 5

    def test_updated_baseline_affects_subsequent_forecast(self) -> None:
        """After many high-token updates, the forecast p90 rises."""
        baseline = build_seeded_baseline(EnumIntentClass.REFACTOR)
        baselines = {EnumIntentClass.REFACTOR: baseline}

        input_data = _make_input()
        before = compute_forecast(input_data, baselines, forecasted_at=_now())

        for _ in range(30):
            update_baseline(
                baseline, actual_tokens=100_000, actual_latency_ms=120_000.0
            )

        after = compute_forecast(input_data, baselines, forecasted_at=_now())
        assert after.estimated_tokens_p90 > before.estimated_tokens_p90


# ---------------------------------------------------------------------------
# Escalation tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.forecast
class TestCheckEscalation:
    """Tests for check_escalation handler."""

    def _make_forecast_with_threshold(
        self, threshold: float
    ) -> ModelIntentCostForecast:
        return ModelIntentCostForecast(
            session_id="s",
            correlation_id=str(uuid4()),
            intent_class=EnumIntentClass.REFACTOR,
            estimated_tokens_p50=1000.0,
            estimated_tokens_p90=threshold,
            estimated_tokens_p99=threshold * 1.5,
            estimated_cost_usd_p50=0.003,
            estimated_cost_usd_p90=0.006,
            estimated_latency_ms_p50=5000.0,
            estimated_latency_ms_p90=10000.0,
            confidence_interval=0.1,
            escalation_threshold_tokens=threshold,
            baseline_sample_count=0,
            forecasted_at=datetime.now(tz=UTC),
        )

    def test_no_escalation_when_below_threshold(self) -> None:
        """No escalation when actual tokens < p90 threshold."""
        forecast = self._make_forecast_with_threshold(5000.0)
        assert check_escalation(4999, forecast) is False

    def test_no_escalation_when_exactly_at_threshold(self) -> None:
        """No escalation when actual tokens == p90 threshold (strict >)."""
        forecast = self._make_forecast_with_threshold(5000.0)
        assert check_escalation(5000, forecast) is False

    def test_escalation_fires_when_above_threshold(self) -> None:
        """Escalation fires when actual tokens > p90 threshold."""
        forecast = self._make_forecast_with_threshold(5000.0)
        assert check_escalation(5001, forecast) is True

    def test_escalation_fires_significantly_above_threshold(self) -> None:
        """Escalation fires when actual tokens far exceed the threshold."""
        forecast = self._make_forecast_with_threshold(3000.0)
        assert check_escalation(30000, forecast) is True

    def test_escalation_never_blocks_execution(self) -> None:
        """check_escalation returns a bool — it never raises or side-effects."""
        forecast = self._make_forecast_with_threshold(2000.0)
        result = check_escalation(999999, forecast)
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# Accuracy record tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.forecast
class TestComputeAccuracyRecord:
    """Tests for compute_accuracy_record handler."""

    def _make_forecast(self) -> ModelIntentCostForecast:
        input_data = _make_input()
        baselines = _make_baselines()
        return compute_forecast(input_data, baselines, forecasted_at=_now())

    def test_returns_frozen_accuracy_record(self) -> None:
        """compute_accuracy_record returns a frozen ModelForecastAccuracyRecord."""
        from pydantic import ValidationError

        from omniintelligence.nodes.node_intent_cost_forecast_compute.models import (
            ModelForecastAccuracyRecord,
        )

        forecast = self._make_forecast()
        record = compute_accuracy_record(
            session_id="sess-acc",
            correlation_id=str(uuid4()),
            intent_class=EnumIntentClass.REFACTOR,
            forecast=forecast,
            actual_tokens=4000,
            actual_cost_usd=0.012,
            recorded_at=_now(),
        )
        assert isinstance(record, ModelForecastAccuracyRecord)
        with pytest.raises((TypeError, ValidationError)):
            record.actual_tokens = 0  # type: ignore[misc]

    def test_accuracy_record_actual_tokens_stored(self) -> None:
        """Accuracy record stores actual_tokens correctly."""
        forecast = self._make_forecast()
        record = compute_accuracy_record(
            session_id="s",
            correlation_id=str(uuid4()),
            intent_class=EnumIntentClass.REFACTOR,
            forecast=forecast,
            actual_tokens=7777,
            actual_cost_usd=0.02,
            recorded_at=_now(),
        )
        assert record.actual_tokens == 7777

    def test_accuracy_record_escalation_triggered_when_exceeded(self) -> None:
        """escalation_triggered is True when actual tokens exceed p90."""
        forecast = self._make_forecast()
        # Force actual tokens above the threshold
        very_high_tokens = int(forecast.escalation_threshold_tokens) + 10000

        record = compute_accuracy_record(
            session_id="s",
            correlation_id=str(uuid4()),
            intent_class=EnumIntentClass.REFACTOR,
            forecast=forecast,
            actual_tokens=very_high_tokens,
            actual_cost_usd=0.05,
            recorded_at=_now(),
        )
        assert record.escalation_triggered is True

    def test_accuracy_record_no_escalation_when_under_threshold(self) -> None:
        """escalation_triggered is False when actual tokens are under the threshold."""
        forecast = self._make_forecast()
        low_tokens = 1  # trivially below any threshold

        record = compute_accuracy_record(
            session_id="s",
            correlation_id=str(uuid4()),
            intent_class=EnumIntentClass.REFACTOR,
            forecast=forecast,
            actual_tokens=low_tokens,
            actual_cost_usd=0.001,
            recorded_at=_now(),
        )
        assert record.escalation_triggered is False

    def test_accuracy_record_forecast_fields_preserved(self) -> None:
        """Accuracy record preserves forecast_tokens_p50 from the forecast."""
        forecast = self._make_forecast()
        record = compute_accuracy_record(
            session_id="s",
            correlation_id=str(uuid4()),
            intent_class=EnumIntentClass.REFACTOR,
            forecast=forecast,
            actual_tokens=2000,
            actual_cost_usd=0.006,
            recorded_at=_now(),
        )
        assert record.forecast_tokens_p50 == forecast.estimated_tokens_p50
        assert record.forecast_cost_usd_p50 == forecast.estimated_cost_usd_p50
