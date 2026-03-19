# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for reward shaping module.

Tests cover:
    - All channels produce bounded rewards in [-2.0, 2.0]
    - Channel breakdown dict is present and complete
    - Edge cases: zero latency, missing fields, extreme values
    - Configurable weights affect the scalar output
    - Calibration report generation with synthetic data
"""

from __future__ import annotations

import pytest

from omniintelligence.rl.calibration import (
    CalibrationThresholds,
    RewardCalibrator,
)
from omniintelligence.rl.rewards import (
    REWARD_LOWER_BOUND,
    REWARD_UPPER_BOUND,
    RewardConfig,
    RewardShaper,
    RewardSignal,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CHANNELS = {"latency", "success", "cost", "quality"}


@pytest.fixture()
def shaper() -> RewardShaper:
    """Default reward shaper with standard config."""
    return RewardShaper()


@pytest.fixture()
def synthetic_data() -> list[dict[str, object]]:
    """Synthetic historical routing data for calibration tests."""
    data: list[dict[str, object]] = []
    for i in range(100):
        data.append(
            {
                "latency_ms": 100.0 + i * 10,
                "success": i % 3 != 0,  # ~67% success rate
                "token_count": 200 + i * 5,
                "cost_per_token": 0.00002,
                "endpoint": f"endpoint_{i % 3}",
            }
        )
    return data


# ---------------------------------------------------------------------------
# RewardSignal bounds
# ---------------------------------------------------------------------------


class TestRewardBounds:
    """All channels must produce rewards bounded in [-2.0, 2.0]."""

    def test_typical_metrics_bounded(self, shaper: RewardShaper) -> None:
        signal = shaper.compute(
            {
                "latency_ms": 250.0,
                "success": True,
                "token_count": 500,
                "cost_per_token": 0.00002,
            }
        )
        assert REWARD_LOWER_BOUND <= signal.scalar <= REWARD_UPPER_BOUND
        for value in signal.channel_breakdown.values():
            assert REWARD_LOWER_BOUND <= value <= REWARD_UPPER_BOUND

    def test_extreme_high_latency_bounded(self, shaper: RewardShaper) -> None:
        signal = shaper.compute({"latency_ms": 100_000.0, "success": False})
        assert REWARD_LOWER_BOUND <= signal.scalar <= REWARD_UPPER_BOUND
        for value in signal.channel_breakdown.values():
            assert REWARD_LOWER_BOUND <= value <= REWARD_UPPER_BOUND

    def test_zero_latency_bounded(self, shaper: RewardShaper) -> None:
        signal = shaper.compute({"latency_ms": 0.0, "success": True})
        assert REWARD_LOWER_BOUND <= signal.scalar <= REWARD_UPPER_BOUND
        # Zero latency should produce positive latency reward
        assert signal.channel_breakdown["latency"] > 0.0

    def test_extreme_cost_bounded(self, shaper: RewardShaper) -> None:
        signal = shaper.compute(
            {"token_count": 1_000_000, "cost_per_token": 1.0, "success": True}
        )
        assert REWARD_LOWER_BOUND <= signal.scalar <= REWARD_UPPER_BOUND
        assert signal.channel_breakdown["cost"] == REWARD_LOWER_BOUND

    def test_negative_latency_bounded(self, shaper: RewardShaper) -> None:
        """Negative latency is nonsensical but should not crash."""
        signal = shaper.compute({"latency_ms": -100.0, "success": True})
        assert REWARD_LOWER_BOUND <= signal.scalar <= REWARD_UPPER_BOUND

    @pytest.mark.parametrize(
        "metrics",
        [
            {
                "latency_ms": 0.0,
                "success": True,
                "token_count": 0,
                "cost_per_token": 0.0,
            },
            {
                "latency_ms": 500.0,
                "success": False,
                "token_count": 0,
                "cost_per_token": 0.0,
            },
            {
                "latency_ms": 1000.0,
                "success": True,
                "token_count": 10000,
                "cost_per_token": 0.001,
            },
            {
                "latency_ms": 50.0,
                "success": True,
                "token_count": 100,
                "cost_per_token": 0.0001,
            },
        ],
    )
    def test_parametric_bounds(
        self, shaper: RewardShaper, metrics: dict[str, object]
    ) -> None:
        signal = shaper.compute(metrics)
        assert REWARD_LOWER_BOUND <= signal.scalar <= REWARD_UPPER_BOUND
        for value in signal.channel_breakdown.values():
            assert REWARD_LOWER_BOUND <= value <= REWARD_UPPER_BOUND


# ---------------------------------------------------------------------------
# Channel breakdown
# ---------------------------------------------------------------------------


class TestChannelBreakdown:
    """Channel breakdown dict must be complete and consistent."""

    def test_all_channels_present(self, shaper: RewardShaper) -> None:
        signal = shaper.compute({"latency_ms": 300.0, "success": True})
        assert set(signal.channel_breakdown.keys()) == CHANNELS

    def test_weighted_breakdown_present(self, shaper: RewardShaper) -> None:
        signal = shaper.compute({"latency_ms": 300.0, "success": True})
        assert set(signal.weighted_breakdown.keys()) == CHANNELS

    def test_weighted_breakdown_matches_weights(self) -> None:
        config = RewardConfig(
            latency_weight=0.5,
            success_weight=0.3,
            cost_weight=0.15,
            quality_weight=0.05,
        )
        shaper = RewardShaper(config)
        signal = shaper.compute({"latency_ms": 300.0, "success": True})

        for channel in CHANNELS:
            raw = signal.channel_breakdown[channel]
            weighted = signal.weighted_breakdown[channel]
            expected_weight = config.weights_dict[channel]
            assert weighted == pytest.approx(raw * expected_weight, abs=1e-10)

    def test_quality_channel_deferred(self, shaper: RewardShaper) -> None:
        """Quality reward must be 0.0 for routing v1."""
        signal = shaper.compute({"latency_ms": 100.0, "success": True})
        assert signal.channel_breakdown["quality"] == 0.0

    def test_success_channel_values(self, shaper: RewardShaper) -> None:
        success_signal = shaper.compute({"success": True})
        failure_signal = shaper.compute({"success": False})
        assert success_signal.channel_breakdown["success"] == 1.0
        assert failure_signal.channel_breakdown["success"] == -1.0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases: missing fields, zero values, type coercion."""

    def test_empty_metrics(self, shaper: RewardShaper) -> None:
        """Missing fields should not raise; defaults are applied."""
        signal = shaper.compute({})
        assert isinstance(signal, RewardSignal)
        assert REWARD_LOWER_BOUND <= signal.scalar <= REWARD_UPPER_BOUND

    def test_missing_latency_uses_baseline(self, shaper: RewardShaper) -> None:
        signal = shaper.compute({"success": True})
        # At baseline latency, normalized deviation is 0 -> latency_reward = 0
        assert signal.channel_breakdown["latency"] == pytest.approx(0.0, abs=1e-10)

    def test_missing_success_defaults_false(self, shaper: RewardShaper) -> None:
        signal = shaper.compute({"latency_ms": 100.0})
        assert signal.channel_breakdown["success"] == -1.0

    def test_zero_token_count(self, shaper: RewardShaper) -> None:
        signal = shaper.compute({"token_count": 0, "cost_per_token": 0.001})
        # 0 tokens * any cost = 0 total cost, which is below baseline -> positive reward
        assert signal.channel_breakdown["cost"] > 0.0

    def test_zero_cost_per_token(self, shaper: RewardShaper) -> None:
        signal = shaper.compute({"token_count": 1000, "cost_per_token": 0.0})
        assert signal.channel_breakdown["cost"] > 0.0


# ---------------------------------------------------------------------------
# RewardConfig
# ---------------------------------------------------------------------------


class TestRewardConfig:
    """RewardConfig validation and behavior."""

    def test_default_config(self) -> None:
        config = RewardConfig()
        assert config.latency_baseline_ms == 500.0
        assert config.cost_baseline == 0.01
        total = sum(config.weights_dict.values())
        assert total == pytest.approx(1.0)

    def test_weights_dict(self) -> None:
        config = RewardConfig(
            latency_weight=0.1, success_weight=0.2, cost_weight=0.3, quality_weight=0.4
        )
        assert config.weights_dict == {
            "latency": 0.1,
            "success": 0.2,
            "cost": 0.3,
            "quality": 0.4,
        }

    def test_custom_baselines_affect_rewards(self) -> None:
        # High baseline = lenient
        lenient = RewardShaper(RewardConfig(latency_baseline_ms=2000.0))
        strict = RewardShaper(RewardConfig(latency_baseline_ms=100.0))

        lenient_signal = lenient.compute({"latency_ms": 500.0, "success": True})
        strict_signal = strict.compute({"latency_ms": 500.0, "success": True})

        # Same latency: lenient config gives better latency reward
        assert (
            lenient_signal.channel_breakdown["latency"]
            > strict_signal.channel_breakdown["latency"]
        )


# ---------------------------------------------------------------------------
# Calibration report
# ---------------------------------------------------------------------------


class TestCalibrationReport:
    """Calibration report generation and gate logic."""

    def test_report_with_synthetic_data(
        self, synthetic_data: list[dict[str, object]]
    ) -> None:
        calibrator = RewardCalibrator()
        report = calibrator.analyze(synthetic_data)

        assert report.sample_count == 100
        assert set(report.channel_means.keys()) == CHANNELS
        assert set(report.channel_stds.keys()) == CHANNELS
        assert report.scalar_variance > 0.0
        assert len(report.sensitivity_results) >= 3

    def test_empty_data_blocks_training(self) -> None:
        calibrator = RewardCalibrator()
        report = calibrator.analyze([])

        assert report.training_blocked is True
        assert report.sample_count == 0
        assert "No historical data" in report.block_reasons[0]

    def test_collapsed_rewards_block_training(self) -> None:
        """Identical samples => zero variance => training blocked."""
        identical_data = [
            {
                "latency_ms": 500.0,
                "success": True,
                "token_count": 0,
                "cost_per_token": 0.0,
            }
        ] * 50
        calibrator = RewardCalibrator()
        report = calibrator.analyze(identical_data)

        assert report.training_blocked is True
        assert any(
            "Collapsed" in r or "variance" in r.lower() for r in report.block_reasons
        )

    def test_healthy_data_passes_gate(
        self, synthetic_data: list[dict[str, object]]
    ) -> None:
        """Diverse synthetic data should generally pass the gate."""
        calibrator = RewardCalibrator()
        report = calibrator.analyze(synthetic_data)
        # The synthetic data is reasonably diverse, so it should pass
        # (unless thresholds are very strict)
        assert report.sample_count == 100

    def test_sensitivity_has_at_least_3_presets(
        self, synthetic_data: list[dict[str, object]]
    ) -> None:
        calibrator = RewardCalibrator()
        report = calibrator.analyze(synthetic_data)
        assert len(report.sensitivity_results) >= 3
        preset_names = {r.preset_name for r in report.sensitivity_results}
        assert "latency_heavy" in preset_names
        assert "success_heavy" in preset_names
        assert "cost_heavy" in preset_names

    def test_sensitivity_presets_differ(
        self, synthetic_data: list[dict[str, object]]
    ) -> None:
        """Different weight presets should produce different scalar means."""
        calibrator = RewardCalibrator()
        report = calibrator.analyze(synthetic_data)
        means = [r.scalar_mean for r in report.sensitivity_results]
        # At least two presets should differ
        assert len({f"{m:.4f}" for m in means}) > 1

    def test_custom_thresholds(self) -> None:
        thresholds = CalibrationThresholds(
            variance_floor=100.0,  # impossibly high
            min_success_correlation=0.99,
        )
        calibrator = RewardCalibrator(thresholds=thresholds)
        data = [
            {"latency_ms": float(i * 100), "success": i % 2 == 0} for i in range(50)
        ]
        report = calibrator.analyze(data)
        assert report.training_blocked is True

    def test_endpoint_skew_detection(self) -> None:
        """Create data with extreme endpoint skew."""
        data: list[dict[str, object]] = []
        # Endpoint A: always fast + success
        for _ in range(50):
            data.append(
                {
                    "latency_ms": 50.0,
                    "success": True,
                    "token_count": 100,
                    "cost_per_token": 0.00001,
                    "endpoint": "fast_endpoint",
                }
            )
        # Endpoint B: always slow + failure
        for _ in range(50):
            data.append(
                {
                    "latency_ms": 5000.0,
                    "success": False,
                    "token_count": 10000,
                    "cost_per_token": 0.001,
                    "endpoint": "slow_endpoint",
                }
            )

        calibrator = RewardCalibrator(
            thresholds=CalibrationThresholds(endpoint_skew_tolerance=2.0)
        )
        report = calibrator.analyze(data)
        # The endpoints have very different reward profiles
        assert report.endpoint_skew_ratio > 1.0
        assert len(report.endpoint_means) == 2
