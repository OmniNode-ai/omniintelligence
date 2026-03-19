# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Reward calibration analysis for RL-based routing optimization.

Provides a calibration gate that must pass before any training claims are
valid.  The gate analyzes reward distributions on historical routing data
and blocks training if rewards are collapsed, severely skewed per-endpoint,
unstable, or negatively correlated with success metrics.

Calibration Checks:
    1. Scalar reward variance must exceed a floor (no collapsed rewards).
    2. Per-endpoint reward distributions must not be severely skewed.
    3. Reward instability (coefficient of variation) must be below threshold.
    4. Combined reward must be positively correlated with success rate.

Channel-Weight Sensitivity:
    The calibrator runs reward computation under multiple weight presets
    to detect fragile configurations where small weight changes cause
    large reward distribution shifts.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict

from pydantic import BaseModel, Field

from omniintelligence.rl.rewards import RewardConfig, RewardShaper

# -- Thresholds --------------------------------------------------------------


class CalibrationThresholds(BaseModel):
    """Numeric thresholds governing the calibration gate.

    Attributes:
        variance_floor: Minimum variance of the combined scalar reward.
            Below this, rewards are considered collapsed (no learning signal).
        endpoint_skew_tolerance: Maximum ratio between the highest and
            lowest endpoint mean rewards.  Above this, endpoint bias is
            too severe for fair policy learning.
        instability_ceiling: Maximum coefficient of variation (std/|mean|)
            for the scalar reward.  Above this, rewards are too noisy.
        min_success_correlation: Minimum Pearson correlation between the
            combined scalar reward and the binary success indicator.
            Below this, the reward function is not aligned with outcomes.
    """

    variance_floor: float = Field(default=0.01, gt=0.0)
    endpoint_skew_tolerance: float = Field(default=5.0, gt=1.0)
    instability_ceiling: float = Field(default=3.0, gt=0.0)
    min_success_correlation: float = Field(default=0.1, ge=-1.0, le=1.0)


# -- Report models -----------------------------------------------------------


class ChannelSensitivityResult(BaseModel):
    """Sensitivity analysis for a single weight preset.

    Attributes:
        preset_name: Human-readable name of the weight preset.
        config: The RewardConfig used for this preset.
        scalar_mean: Mean of combined scalar rewards under this preset.
        scalar_std: Standard deviation of combined scalar rewards.
        channel_means: Per-channel mean rewards.
    """

    preset_name: str
    config: RewardConfig
    scalar_mean: float
    scalar_std: float
    channel_means: dict[str, float]


class RewardCalibrationReport(BaseModel):
    """Full calibration analysis report.

    Attributes:
        sample_count: Number of historical samples analyzed.
        channel_means: Per-channel mean reward across all samples.
        channel_stds: Per-channel standard deviation.
        scalar_mean: Mean of the combined scalar reward.
        scalar_std: Standard deviation of the combined scalar reward.
        scalar_variance: Variance of the combined scalar reward.
        endpoint_means: Mean scalar reward per endpoint.
        endpoint_skew_ratio: Ratio of max to min absolute endpoint mean.
        instability_cv: Coefficient of variation of scalar rewards.
        success_correlation: Pearson correlation between scalar reward
            and binary success indicator.
        sensitivity_results: Channel-weight sensitivity analysis results
            for multiple weight presets.
        training_blocked: Whether training should be blocked.
        block_reasons: List of human-readable reasons for blocking.
    """

    sample_count: int
    channel_means: dict[str, float]
    channel_stds: dict[str, float]
    scalar_mean: float
    scalar_std: float
    scalar_variance: float
    endpoint_means: dict[str, float]
    endpoint_skew_ratio: float
    instability_cv: float
    success_correlation: float
    sensitivity_results: list[ChannelSensitivityResult]
    training_blocked: bool
    block_reasons: list[str] = Field(default_factory=list)


# -- Weight presets ----------------------------------------------------------

_WEIGHT_PRESETS: list[tuple[str, RewardConfig]] = [
    (
        "latency_heavy",
        RewardConfig(
            latency_weight=0.6, success_weight=0.2, cost_weight=0.1, quality_weight=0.1
        ),
    ),
    (
        "success_heavy",
        RewardConfig(
            latency_weight=0.1, success_weight=0.6, cost_weight=0.2, quality_weight=0.1
        ),
    ),
    (
        "cost_heavy",
        RewardConfig(
            latency_weight=0.1, success_weight=0.2, cost_weight=0.6, quality_weight=0.1
        ),
    ),
    (
        "balanced",
        RewardConfig(
            latency_weight=0.25,
            success_weight=0.25,
            cost_weight=0.25,
            quality_weight=0.25,
        ),
    ),
]


# -- Helpers -----------------------------------------------------------------


def _pearson_correlation(xs: list[float], ys: list[float]) -> float:
    """Compute Pearson correlation coefficient between two sequences.

    Returns 0.0 if either sequence has zero variance (correlation undefined).
    """
    n = len(xs)
    if n < 2:
        return 0.0

    mean_x = statistics.mean(xs)
    mean_y = statistics.mean(ys)

    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)) / n
    std_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs) / n)
    std_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys) / n)

    if std_x == 0.0 or std_y == 0.0:
        return 0.0

    return cov / (std_x * std_y)


# -- Calibrator --------------------------------------------------------------


class RewardCalibrator:
    """Analyzes reward distributions and gates training readiness.

    Parameters:
        config: Reward configuration to calibrate.
        thresholds: Numeric thresholds for the calibration gate.

    Example::

        calibrator = RewardCalibrator()
        report = calibrator.analyze(historical_outcomes)
        if report.training_blocked:
            print("Cannot train:", report.block_reasons)
    """

    def __init__(
        self,
        config: RewardConfig | None = None,
        thresholds: CalibrationThresholds | None = None,
    ) -> None:
        self.config = config or RewardConfig()
        self.thresholds = thresholds or CalibrationThresholds()

    def analyze(
        self, historical_data: list[dict[str, object]]
    ) -> RewardCalibrationReport:
        """Run full calibration analysis on historical routing data.

        Args:
            historical_data: List of outcome metric dicts.  Each dict should
                contain the keys expected by :meth:`RewardShaper.compute`
                plus an optional ``endpoint`` key for per-endpoint analysis.

        Returns:
            A :class:`RewardCalibrationReport` with distribution statistics,
            endpoint skew analysis, sensitivity results, and a go/no-go
            training gate decision.
        """
        shaper = RewardShaper(self.config)

        # Compute rewards for all samples
        scalars: list[float] = []
        channel_values: dict[str, list[float]] = defaultdict(list)
        endpoint_scalars: dict[str, list[float]] = defaultdict(list)
        success_indicators: list[float] = []

        for sample in historical_data:
            signal = shaper.compute(sample)
            scalars.append(signal.scalar)
            success_indicators.append(1.0 if sample.get("success", False) else 0.0)

            for channel, value in signal.channel_breakdown.items():
                channel_values[channel].append(value)

            endpoint = str(sample.get("endpoint", "unknown"))
            endpoint_scalars[endpoint].append(signal.scalar)

        sample_count = len(scalars)

        # -- Aggregate statistics --------------------------------------------

        if sample_count == 0:
            return RewardCalibrationReport(
                sample_count=0,
                channel_means={},
                channel_stds={},
                scalar_mean=0.0,
                scalar_std=0.0,
                scalar_variance=0.0,
                endpoint_means={},
                endpoint_skew_ratio=0.0,
                instability_cv=0.0,
                success_correlation=0.0,
                sensitivity_results=[],
                training_blocked=True,
                block_reasons=["No historical data provided"],
            )

        scalar_mean = statistics.mean(scalars)
        scalar_variance = statistics.pvariance(scalars)
        scalar_std = math.sqrt(scalar_variance)

        channel_means = {
            ch: statistics.mean(vals) for ch, vals in channel_values.items()
        }
        channel_stds = {
            ch: (statistics.pstdev(vals) if len(vals) > 1 else 0.0)
            for ch, vals in channel_values.items()
        }

        endpoint_means = {
            ep: statistics.mean(vals) for ep, vals in endpoint_scalars.items()
        }

        # Endpoint skew: ratio of max to min absolute mean
        abs_means = [abs(m) for m in endpoint_means.values() if m != 0.0]
        if len(abs_means) >= 2:
            endpoint_skew_ratio = max(abs_means) / min(abs_means)
        else:
            endpoint_skew_ratio = 1.0

        # Instability: coefficient of variation
        instability_cv = scalar_std / abs(scalar_mean) if scalar_mean != 0.0 else 0.0

        # Success correlation
        success_correlation = _pearson_correlation(scalars, success_indicators)

        # -- Sensitivity analysis --------------------------------------------

        sensitivity_results = self._run_sensitivity(historical_data)

        # -- Gate decision ---------------------------------------------------

        block_reasons: list[str] = []

        if scalar_variance < self.thresholds.variance_floor:
            block_reasons.append(
                f"Collapsed rewards: variance {scalar_variance:.6f} "
                f"< floor {self.thresholds.variance_floor}"
            )

        if endpoint_skew_ratio > self.thresholds.endpoint_skew_tolerance:
            block_reasons.append(
                f"Severe endpoint skew: ratio {endpoint_skew_ratio:.2f} "
                f"> tolerance {self.thresholds.endpoint_skew_tolerance}"
            )

        if instability_cv > self.thresholds.instability_ceiling:
            block_reasons.append(
                f"High instability: CV {instability_cv:.2f} "
                f"> ceiling {self.thresholds.instability_ceiling}"
            )

        if success_correlation < self.thresholds.min_success_correlation:
            block_reasons.append(
                f"Negative/low success correlation: {success_correlation:.4f} "
                f"< minimum {self.thresholds.min_success_correlation}"
            )

        return RewardCalibrationReport(
            sample_count=sample_count,
            channel_means=channel_means,
            channel_stds=channel_stds,
            scalar_mean=scalar_mean,
            scalar_std=scalar_std,
            scalar_variance=scalar_variance,
            endpoint_means=endpoint_means,
            endpoint_skew_ratio=endpoint_skew_ratio,
            instability_cv=instability_cv,
            success_correlation=success_correlation,
            sensitivity_results=sensitivity_results,
            training_blocked=len(block_reasons) > 0,
            block_reasons=block_reasons,
        )

    def _run_sensitivity(
        self, historical_data: list[dict[str, object]]
    ) -> list[ChannelSensitivityResult]:
        """Run reward computation under multiple weight presets."""
        results: list[ChannelSensitivityResult] = []

        for preset_name, preset_config in _WEIGHT_PRESETS:
            shaper = RewardShaper(preset_config)
            scalars: list[float] = []
            channel_accum: dict[str, list[float]] = defaultdict(list)

            for sample in historical_data:
                signal = shaper.compute(sample)
                scalars.append(signal.scalar)
                for ch, val in signal.channel_breakdown.items():
                    channel_accum[ch].append(val)

            if scalars:
                scalar_mean = statistics.mean(scalars)
                scalar_std = statistics.pstdev(scalars) if len(scalars) > 1 else 0.0
                ch_means = {
                    ch: statistics.mean(vals) for ch, vals in channel_accum.items()
                }
            else:
                scalar_mean = 0.0
                scalar_std = 0.0
                ch_means = {}

            results.append(
                ChannelSensitivityResult(
                    preset_name=preset_name,
                    config=preset_config,
                    scalar_mean=scalar_mean,
                    scalar_std=scalar_std,
                    channel_means=ch_means,
                )
            )

        return results
