# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Per-intent-class historical cost and latency baseline.

Stores p50/p90/p99 token count distributions and latency observations
used to generate cost and latency forecasts. Baselines are seeded with
synthetic values on first run to prevent cold-start empty forecasts.

Reference: OMN-2490
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean, median, quantiles

from omnibase_core.enums.intelligence.enum_intent_class import EnumIntentClass

# ---------------------------------------------------------------------------
# Synthetic seed values per intent class (tokens)
# Derived from typical Claude API usage patterns.
# ---------------------------------------------------------------------------
_SYNTHETIC_TOKEN_SEEDS: dict[EnumIntentClass, list[int]] = {
    EnumIntentClass.REFACTOR: [2200, 2800, 3500, 4100, 5000],
    EnumIntentClass.BUGFIX: [1500, 2000, 2600, 3200, 4000],
    EnumIntentClass.FEATURE: [3000, 4000, 5500, 7000, 9000],
    EnumIntentClass.ANALYSIS: [800, 1200, 1600, 2200, 3000],
    EnumIntentClass.CONFIGURATION: [600, 900, 1200, 1600, 2000],
    EnumIntentClass.DOCUMENTATION: [700, 1000, 1400, 2000, 2800],
    EnumIntentClass.MIGRATION: [2500, 3500, 5000, 7000, 9000],
    EnumIntentClass.SECURITY: [1200, 1800, 2500, 3500, 4500],
}

# Synthetic latency seeds per intent class (milliseconds wall-clock)
_SYNTHETIC_LATENCY_SEEDS: dict[EnumIntentClass, list[float]] = {
    EnumIntentClass.REFACTOR: [8000.0, 12000.0, 18000.0, 25000.0, 35000.0],
    EnumIntentClass.BUGFIX: [5000.0, 8000.0, 12000.0, 18000.0, 25000.0],
    EnumIntentClass.FEATURE: [10000.0, 15000.0, 22000.0, 32000.0, 45000.0],
    EnumIntentClass.ANALYSIS: [3000.0, 5000.0, 8000.0, 12000.0, 18000.0],
    EnumIntentClass.CONFIGURATION: [2000.0, 3500.0, 5000.0, 7000.0, 10000.0],
    EnumIntentClass.DOCUMENTATION: [2500.0, 4000.0, 6000.0, 9000.0, 13000.0],
    EnumIntentClass.MIGRATION: [12000.0, 18000.0, 28000.0, 40000.0, 55000.0],
    EnumIntentClass.SECURITY: [6000.0, 9000.0, 14000.0, 20000.0, 28000.0],
}

# Cost per 1K tokens (USD) — Claude claude-sonnet-4-6 blended input+output estimate
_COST_PER_1K_TOKENS: float = 0.003


@dataclass
class ModelCostBaseline:
    """Mutable historical baseline for a single intent class.

    Accumulates token counts and latency observations from completed sessions.
    Exposes p50/p90/p99 percentile accessors derived from the stored samples.

    Not frozen — baselines are updated after each session outcome.

    Attributes:
        intent_class: The intent class this baseline tracks.
        token_samples: Raw token count samples (input + output tokens per session).
        latency_samples_ms: Raw latency samples in milliseconds.
        sample_count: Number of real (non-synthetic) sessions observed.
    """

    intent_class: EnumIntentClass
    token_samples: list[int] = field(default_factory=list)
    latency_samples_ms: list[float] = field(default_factory=list)
    sample_count: int = 0  # real (non-synthetic) observations

    # -----------------------------------------------------------------------
    # Token percentiles
    # -----------------------------------------------------------------------

    @property
    def token_p50(self) -> float:
        """Median (p50) token count."""
        if not self.token_samples:
            return 0.0
        return float(median(self.token_samples))

    @property
    def token_p90(self) -> float:
        """90th-percentile token count."""
        if len(self.token_samples) < 2:
            return float(self.token_samples[0]) if self.token_samples else 0.0
        qs = quantiles(self.token_samples, n=10)
        return float(qs[8])  # index 8 = 90th percentile

    @property
    def token_p99(self) -> float:
        """99th-percentile token count."""
        if len(self.token_samples) < 2:
            return float(self.token_samples[0]) if self.token_samples else 0.0
        qs = quantiles(self.token_samples, n=100)
        return float(qs[98])  # index 98 = 99th percentile

    @property
    def token_mean(self) -> float:
        """Mean token count."""
        if not self.token_samples:
            return 0.0
        return mean(self.token_samples)

    # -----------------------------------------------------------------------
    # Latency percentiles
    # -----------------------------------------------------------------------

    @property
    def latency_p50_ms(self) -> float:
        """Median (p50) latency in milliseconds."""
        if not self.latency_samples_ms:
            return 0.0
        return float(median(self.latency_samples_ms))

    @property
    def latency_p90_ms(self) -> float:
        """90th-percentile latency in milliseconds."""
        if len(self.latency_samples_ms) < 2:
            return float(self.latency_samples_ms[0]) if self.latency_samples_ms else 0.0
        qs = quantiles(self.latency_samples_ms, n=10)
        return float(qs[8])

    @property
    def latency_p99_ms(self) -> float:
        """99th-percentile latency in milliseconds."""
        if len(self.latency_samples_ms) < 2:
            return float(self.latency_samples_ms[0]) if self.latency_samples_ms else 0.0
        qs = quantiles(self.latency_samples_ms, n=100)
        return float(qs[98])

    # -----------------------------------------------------------------------
    # Cost estimation
    # -----------------------------------------------------------------------

    def estimated_cost_usd(self, tokens: float) -> float:
        """Convert token count to USD cost estimate.

        Args:
            tokens: Number of tokens to price.

        Returns:
            Estimated cost in USD.
        """
        return (tokens / 1000.0) * _COST_PER_1K_TOKENS


def build_seeded_baseline(intent_class: EnumIntentClass) -> ModelCostBaseline:
    """Build a baseline pre-seeded with synthetic values for the given class.

    Prevents cold-start empty forecasts on first run. The synthetic seed values
    are representative but conservative — real observations will quickly
    dominate as sessions complete.

    Args:
        intent_class: The intent class to build a baseline for.

    Returns:
        ModelCostBaseline seeded with synthetic token and latency samples.
    """
    baseline = ModelCostBaseline(intent_class=intent_class)
    baseline.token_samples.extend(
        _SYNTHETIC_TOKEN_SEEDS.get(intent_class, [2000, 3000, 4000, 5000, 6000])
    )
    baseline.latency_samples_ms.extend(
        _SYNTHETIC_LATENCY_SEEDS.get(
            intent_class, [5000.0, 10000.0, 15000.0, 20000.0, 30000.0]
        )
    )
    # sample_count stays 0 — synthetic seeds are not real observations
    return baseline


def build_all_seeded_baselines() -> dict[EnumIntentClass, ModelCostBaseline]:
    """Build seeded baselines for all 8 intent classes.

    Returns:
        Dict mapping each EnumIntentClass to its pre-seeded baseline.
    """
    return {cls: build_seeded_baseline(cls) for cls in EnumIntentClass}


__all__ = [
    "ModelCostBaseline",
    "build_all_seeded_baselines",
    "build_seeded_baseline",
]
