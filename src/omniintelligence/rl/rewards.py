# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Reward shaping module for RL-based routing optimization.

Maps platform metrics (latency, success, cost, quality) to scalar rewards
with configurable channel weights. Each channel produces a bounded reward
in [-2.0, 2.0], and the combined scalar is the weighted sum clipped to
the same range.

Reward Channels:
    latency_reward:  -normalize(latency_ms, baseline)
    success_reward:  +1.0 if success, -1.0 if failure
    cost_reward:     -normalize(token_count * cost_per_token)
    quality_reward:  0.0 (deferred until objective_evaluations populated)

Note on quality_reward:
    The quality channel is explicitly deferred for routing v1. It returns
    0.0 for all inputs until an objective evaluation pipeline is integrated.
    This is intentional -- premature quality scoring would introduce noise
    rather than signal into the reward function.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# -- Bounds ------------------------------------------------------------------

REWARD_LOWER_BOUND: float = -2.0
REWARD_UPPER_BOUND: float = 2.0


def _clamp(value: float) -> float:
    """Clamp *value* to [REWARD_LOWER_BOUND, REWARD_UPPER_BOUND]."""
    return max(REWARD_LOWER_BOUND, min(REWARD_UPPER_BOUND, value))


# -- Configuration -----------------------------------------------------------


class RewardConfig(BaseModel):
    """Configurable weights and normalization baselines for reward shaping.

    Attributes:
        latency_weight: Weight for the latency reward channel.
        success_weight: Weight for the success reward channel.
        cost_weight: Weight for the cost reward channel.
        quality_weight: Weight for the quality reward channel (deferred v1).
        latency_baseline_ms: Baseline latency in milliseconds used for
            normalization.  A request at exactly this latency scores 0.
        cost_baseline: Baseline cost value used for normalization.  A request
            at exactly this cost scores 0.
    """

    latency_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    success_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    cost_weight: float = Field(default=0.2, ge=0.0, le=1.0)
    quality_weight: float = Field(default=0.1, ge=0.0, le=1.0)

    latency_baseline_ms: float = Field(default=500.0, gt=0.0)
    cost_baseline: float = Field(default=0.01, gt=0.0)

    @property
    def weights_dict(self) -> dict[str, float]:
        """Return channel weights as a dictionary."""
        return {
            "latency": self.latency_weight,
            "success": self.success_weight,
            "cost": self.cost_weight,
            "quality": self.quality_weight,
        }


# -- Signal ------------------------------------------------------------------


class RewardSignal(BaseModel):
    """Result of reward computation.

    Attributes:
        scalar: Combined weighted reward, bounded in [-2.0, 2.0].
        channel_breakdown: Per-channel rewards before weighting.
        weighted_breakdown: Per-channel rewards after weighting.
    """

    scalar: float = Field(ge=REWARD_LOWER_BOUND, le=REWARD_UPPER_BOUND)
    channel_breakdown: dict[str, float]
    weighted_breakdown: dict[str, float]


# -- Shaper ------------------------------------------------------------------


class RewardShaper:
    """Maps outcome metrics to bounded scalar rewards.

    Parameters:
        config: Reward configuration with channel weights and baselines.

    Example::

        shaper = RewardShaper()
        signal = shaper.compute({
            "latency_ms": 250.0,
            "success": True,
            "token_count": 500,
            "cost_per_token": 0.00002,
        })
        assert -2.0 <= signal.scalar <= 2.0
    """

    def __init__(self, config: RewardConfig | None = None) -> None:
        self.config = config or RewardConfig()

    # -- Channel computations ------------------------------------------------

    def _latency_reward(self, latency_ms: float) -> float:
        """Compute latency reward.

        Returns negative normalized deviation from baseline.
        Lower latency is better (positive contribution when < baseline).
        """
        normalized = (
            latency_ms - self.config.latency_baseline_ms
        ) / self.config.latency_baseline_ms
        return _clamp(-normalized)

    @staticmethod
    def _success_reward(success: bool) -> float:
        """Compute success reward: +1.0 for success, -1.0 for failure."""
        return 1.0 if success else -1.0

    def _cost_reward(self, token_count: float, cost_per_token: float) -> float:
        """Compute cost reward.

        Returns negative normalized cost relative to baseline.
        Lower cost is better.
        """
        total_cost = token_count * cost_per_token
        normalized = (
            total_cost - self.config.cost_baseline
        ) / self.config.cost_baseline
        return _clamp(-normalized)

    @staticmethod
    def _quality_reward() -> float:
        """Compute quality reward.

        Deferred for routing v1 -- returns 0.0 until objective evaluation
        pipeline is integrated. See module docstring for rationale.
        """
        return 0.0

    # -- Public API ----------------------------------------------------------

    def compute(self, outcome_metrics: dict[str, object]) -> RewardSignal:
        """Map outcome metrics to a bounded scalar reward.

        Args:
            outcome_metrics: Dictionary with the following keys:
                - ``latency_ms`` (float): Request latency in milliseconds.
                    Defaults to baseline if missing.
                - ``success`` (bool): Whether the request succeeded.
                    Defaults to ``False`` if missing.
                - ``token_count`` (float): Number of tokens consumed.
                    Defaults to 0 if missing.
                - ``cost_per_token`` (float): Cost per token for the endpoint.
                    Defaults to 0 if missing.

        Returns:
            A :class:`RewardSignal` with scalar, channel breakdown, and
            weighted breakdown.
        """
        latency_ms = float(
            outcome_metrics.get("latency_ms", self.config.latency_baseline_ms)
        )
        success = bool(outcome_metrics.get("success", False))
        token_count = float(outcome_metrics.get("token_count", 0))
        cost_per_token = float(outcome_metrics.get("cost_per_token", 0))

        # Compute individual channels
        lat_r = self._latency_reward(latency_ms)
        suc_r = self._success_reward(success)
        cost_r = self._cost_reward(token_count, cost_per_token)
        qual_r = self._quality_reward()

        channel_breakdown = {
            "latency": lat_r,
            "success": suc_r,
            "cost": cost_r,
            "quality": qual_r,
        }

        # Weighted channels
        cfg = self.config
        weighted_breakdown = {
            "latency": lat_r * cfg.latency_weight,
            "success": suc_r * cfg.success_weight,
            "cost": cost_r * cfg.cost_weight,
            "quality": qual_r * cfg.quality_weight,
        }

        scalar = _clamp(sum(weighted_breakdown.values()))

        return RewardSignal(
            scalar=scalar,
            channel_breakdown=channel_breakdown,
            weighted_breakdown=weighted_breakdown,
        )
