# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for AntiGamingGuardrailsCompute (OMN-2563).

Tests cover all four guardrails:
  - Goodhart's Law detection (correlated metric divergence)
  - Reward hacking detection (score up, acceptance flat)
  - Distributional shift detection (KL-divergence)
  - Diversity constraint (VETO on too few source types)
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_anti_gaming_guardrails_compute.handlers.handler_guardrails import (
    check_distributional_shift,
    check_diversity_constraint,
    check_goodhart_violation,
    check_reward_hacking,
    run_all_guardrails,
)
from omniintelligence.nodes.node_anti_gaming_guardrails_compute.models.enum_alert_type import (
    EnumAlertType,
)
from omniintelligence.nodes.node_anti_gaming_guardrails_compute.models.model_guardrail_config import (
    ModelCorrelationPair,
    ModelGuardrailConfig,
)
from omniintelligence.nodes.node_anti_gaming_guardrails_compute.models.model_guardrail_input import (
    ModelGuardrailInput,
    ModelScoreVectorSnapshot,
)

# =============================================================================
# Helpers
# =============================================================================

_CONFIG = ModelGuardrailConfig(
    objective_id="test-objective",
    correlation_pairs=(
        ModelCorrelationPair(
            metric_a="correctness", metric_b="safety", divergence_threshold=0.2
        ),
    ),
    reward_hacking_score_threshold=0.1,
    reward_hacking_acceptance_floor=0.0,
    drift_threshold=0.1,
    min_evidence_sources=2,
)

_NOW = "2026-02-24T00:00:00Z"


def _score(
    correctness: float = 0.5,
    safety: float = 0.5,
    cost: float = 0.5,
    latency: float = 0.5,
    maintainability: float = 0.5,
    human_time: float = 0.5,
) -> ModelScoreVectorSnapshot:
    return ModelScoreVectorSnapshot(
        correctness=correctness,
        safety=safety,
        cost=cost,
        latency=latency,
        maintainability=maintainability,
        human_time=human_time,
    )


# =============================================================================
# Tests: Goodhart's Law detection
# =============================================================================


@pytest.mark.unit
class TestGoodhartViolation:
    def test_no_alert_when_both_improve(self) -> None:
        alerts = check_goodhart_violation(
            run_id="r1",
            objective_id="obj-1",
            current_score=_score(correctness=0.8, safety=0.7),
            previous_score=_score(correctness=0.5, safety=0.5),
            config=_CONFIG,
            occurred_at_utc=_NOW,
        )
        assert alerts == []

    def test_no_alert_when_both_degrade(self) -> None:
        alerts = check_goodhart_violation(
            run_id="r1",
            objective_id="obj-1",
            current_score=_score(correctness=0.3, safety=0.3),
            previous_score=_score(correctness=0.5, safety=0.5),
            config=_CONFIG,
            occurred_at_utc=_NOW,
        )
        assert alerts == []

    def test_no_alert_when_divergence_below_threshold(self) -> None:
        """Divergence below threshold: no alert."""
        # correctness +0.05, safety -0.05 → divergence=0.1, threshold=0.2
        alerts = check_goodhart_violation(
            run_id="r1",
            objective_id="obj-1",
            current_score=_score(correctness=0.55, safety=0.45),
            previous_score=_score(correctness=0.5, safety=0.5),
            config=_CONFIG,
            occurred_at_utc=_NOW,
        )
        assert alerts == []

    def test_alert_fires_when_divergence_exceeds_threshold(self) -> None:
        """correctness +0.3, safety -0.2 → divergence=0.5 > threshold=0.2."""
        alerts = check_goodhart_violation(
            run_id="r2",
            objective_id="obj-1",
            current_score=_score(correctness=0.8, safety=0.3),
            previous_score=_score(correctness=0.5, safety=0.5),
            config=_CONFIG,
            occurred_at_utc=_NOW,
        )
        assert len(alerts) == 1
        assert alerts[0].alert_type == EnumAlertType.GOODHART_VIOLATION
        assert alerts[0].improving_metric == "correctness"
        assert alerts[0].degrading_metric == "safety"

    def test_no_alert_when_no_correlation_pairs(self) -> None:
        config_no_pairs = ModelGuardrailConfig(
            objective_id="test", correlation_pairs=()
        )
        alerts = check_goodhart_violation(
            run_id="r1",
            objective_id="test",
            current_score=_score(correctness=1.0, safety=0.0),
            previous_score=_score(correctness=0.0, safety=1.0),
            config=config_no_pairs,
            occurred_at_utc=_NOW,
        )
        assert alerts == []


# =============================================================================
# Tests: Reward hacking detection
# =============================================================================


@pytest.mark.unit
class TestRewardHacking:
    def test_no_alert_without_acceptance_data(self) -> None:
        result = check_reward_hacking(
            run_id="r1",
            objective_id="obj-1",
            current_score=_score(correctness=0.9),
            previous_score=_score(correctness=0.5),
            human_acceptance_rate=None,
            previous_acceptance_rate=None,
            config=_CONFIG,
            occurred_at_utc=_NOW,
        )
        assert result is None

    def test_no_alert_when_correctness_improvement_below_threshold(self) -> None:
        """correctness +0.05, which is < threshold=0.1"""
        result = check_reward_hacking(
            run_id="r1",
            objective_id="obj-1",
            current_score=_score(correctness=0.55),
            previous_score=_score(correctness=0.5),
            human_acceptance_rate=0.6,
            previous_acceptance_rate=0.6,
            config=_CONFIG,
            occurred_at_utc=_NOW,
        )
        assert result is None

    def test_no_alert_when_acceptance_also_improves(self) -> None:
        """Both correctness and acceptance improved — no alert."""
        result = check_reward_hacking(
            run_id="r1",
            objective_id="obj-1",
            current_score=_score(correctness=0.8),
            previous_score=_score(correctness=0.5),
            human_acceptance_rate=0.9,
            previous_acceptance_rate=0.6,
            config=_CONFIG,
            occurred_at_utc=_NOW,
        )
        assert result is None

    def test_alert_fires_when_correctness_up_acceptance_flat(self) -> None:
        """Correctness +0.4 but acceptance flat."""
        result = check_reward_hacking(
            run_id="r2",
            objective_id="obj-1",
            current_score=_score(correctness=0.9),
            previous_score=_score(correctness=0.5),
            human_acceptance_rate=0.5,
            previous_acceptance_rate=0.5,  # no improvement
            config=_CONFIG,
            occurred_at_utc=_NOW,
        )
        assert result is not None
        assert result.alert_type == EnumAlertType.REWARD_HACKING
        assert result.score_improvement > 0

    def test_alert_fires_when_acceptance_decreases(self) -> None:
        """Correctness up, acceptance down — strong reward hacking signal."""
        result = check_reward_hacking(
            run_id="r3",
            objective_id="obj-1",
            current_score=_score(correctness=0.9),
            previous_score=_score(correctness=0.5),
            human_acceptance_rate=0.3,
            previous_acceptance_rate=0.6,
            config=_CONFIG,
            occurred_at_utc=_NOW,
        )
        assert result is not None
        assert result.acceptance_rate_delta < 0


# =============================================================================
# Tests: Distributional shift detection
# =============================================================================


@pytest.mark.unit
class TestDistributionalShift:
    def test_no_alert_without_baseline(self) -> None:
        result = check_distributional_shift(
            run_id="r1",
            objective_id="obj-1",
            current_dist={"test_result": 0.9},
            baseline_dist=None,
            config=_CONFIG,
            occurred_at_utc=_NOW,
        )
        assert result is None

    def test_no_alert_when_identical_distributions(self) -> None:
        dist = {"test_result": 0.9, "lint_result": 0.8}
        result = check_distributional_shift(
            run_id="r1",
            objective_id="obj-1",
            current_dist=dist,
            baseline_dist=dict(dist),
            config=_CONFIG,
            occurred_at_utc=_NOW,
        )
        assert result is None

    def test_no_alert_when_drift_below_threshold(self) -> None:
        """Small drift below threshold."""
        result = check_distributional_shift(
            run_id="r1",
            objective_id="obj-1",
            current_dist={"test_result": 0.85},
            baseline_dist={"test_result": 0.9},
            config=_CONFIG,
            occurred_at_utc=_NOW,
        )
        assert result is None

    def test_alert_fires_on_large_drift(self) -> None:
        """Large distributional shift triggers alert."""
        result = check_distributional_shift(
            run_id="r2",
            objective_id="obj-1",
            current_dist={"test_result": 0.1, "new_source": 0.9},
            baseline_dist={"test_result": 0.9, "lint_result": 0.9},
            config=_CONFIG,
            occurred_at_utc=_NOW,
        )
        assert result is not None
        assert result.alert_type == EnumAlertType.DISTRIBUTIONAL_SHIFT
        assert result.drift_score > _CONFIG.drift_threshold


# =============================================================================
# Tests: Diversity constraint
# =============================================================================


@pytest.mark.unit
class TestDiversityConstraint:
    def test_no_violation_with_sufficient_sources(self) -> None:
        result = check_diversity_constraint(
            run_id="r1",
            objective_id="obj-1",
            evidence_sources=("test_result", "lint_result"),
            config=_CONFIG,
            occurred_at_utc=_NOW,
        )
        assert result is None

    def test_no_violation_with_exactly_min_sources(self) -> None:
        result = check_diversity_constraint(
            run_id="r1",
            objective_id="obj-1",
            evidence_sources=("test_result", "lint_result"),  # exactly 2
            config=_CONFIG,
            occurred_at_utc=_NOW,
        )
        assert result is None

    def test_violation_with_single_source(self) -> None:
        result = check_diversity_constraint(
            run_id="r2",
            objective_id="obj-1",
            evidence_sources=("test_result",),  # only 1, need 2
            config=_CONFIG,
            occurred_at_utc=_NOW,
        )
        assert result is not None
        assert result.alert_type == EnumAlertType.DIVERSITY_CONSTRAINT_VIOLATION
        assert result.required_min_sources == 2

    def test_violation_with_empty_sources(self) -> None:
        result = check_diversity_constraint(
            run_id="r3",
            objective_id="obj-1",
            evidence_sources=(),
            config=_CONFIG,
            occurred_at_utc=_NOW,
        )
        assert result is not None

    def test_duplicate_sources_counted_once(self) -> None:
        """Duplicate source types count as one distinct type."""
        result = check_diversity_constraint(
            run_id="r4",
            objective_id="obj-1",
            evidence_sources=("test_result", "test_result"),  # duplicates = 1 distinct
            config=_CONFIG,
            occurred_at_utc=_NOW,
        )
        assert result is not None  # Only 1 distinct source, need 2


# =============================================================================
# Tests: run_all_guardrails integration
# =============================================================================


@pytest.mark.unit
class TestRunAllGuardrails:
    def test_clean_run_no_alerts(self) -> None:
        """All-clean run: no previous score, sufficient sources, no shift."""
        inp = ModelGuardrailInput(
            run_id="r1",
            current_score=_score(),
            previous_score=None,
            evidence_sources=("test_result", "lint_result"),
            config=_CONFIG,
        )
        output = run_all_guardrails(inp)
        assert output.alerts == ()
        assert output.diversity_violation is None
        assert not output.should_veto

    def test_diversity_violation_causes_veto(self) -> None:
        inp = ModelGuardrailInput(
            run_id="r2",
            current_score=_score(),
            previous_score=None,
            evidence_sources=("test_result",),  # only 1 source
            config=_CONFIG,
        )
        output = run_all_guardrails(inp)
        assert output.should_veto is True
        assert output.diversity_violation is not None

    def test_goodhart_alert_does_not_veto(self) -> None:
        """Goodhart alert is non-blocking."""
        inp = ModelGuardrailInput(
            run_id="r3",
            current_score=_score(correctness=0.9, safety=0.2),
            previous_score=_score(correctness=0.5, safety=0.5),
            evidence_sources=("test_result", "lint_result"),
            config=_CONFIG,
        )
        output = run_all_guardrails(inp)
        assert not output.should_veto
        assert output.alert_count >= 1

    def test_reward_hacking_alert_does_not_veto(self) -> None:
        """Reward hacking alert is non-blocking."""
        inp = ModelGuardrailInput(
            run_id="r4",
            current_score=_score(correctness=0.9),
            previous_score=_score(correctness=0.5),
            evidence_sources=("test_result", "lint_result"),
            human_acceptance_rate=0.5,
            previous_acceptance_rate=0.5,
            config=_CONFIG,
        )
        output = run_all_guardrails(inp)
        assert not output.should_veto
        assert output.alert_count >= 1

    def test_multiple_alerts_accumulated(self) -> None:
        """Multiple alerts can fire simultaneously."""
        config_low_threshold = ModelGuardrailConfig(
            objective_id="test-obj",
            correlation_pairs=(
                ModelCorrelationPair(
                    metric_a="correctness", metric_b="safety", divergence_threshold=0.05
                ),
            ),
            reward_hacking_score_threshold=0.05,
            reward_hacking_acceptance_floor=0.0,
            drift_threshold=0.001,
            min_evidence_sources=2,
        )
        inp = ModelGuardrailInput(
            run_id="r5",
            current_score=_score(correctness=0.9, safety=0.2),
            previous_score=_score(correctness=0.5, safety=0.5),
            evidence_sources=("test_result", "lint_result"),
            human_acceptance_rate=0.5,
            previous_acceptance_rate=0.5,
            baseline_source_distribution={"test_result": 0.5, "lint_result": 0.5},
            current_source_distribution={"test_result": 0.9, "coverage_report": 0.9},
            config=config_low_threshold,
        )
        output = run_all_guardrails(inp)
        assert output.alert_count >= 2  # At least goodhart + reward hacking
        assert not output.should_veto  # Still passes diversity (2 sources)

    @pytest.mark.parametrize(
        "sources,should_veto",
        [
            (("test_result",), True),
            (("test_result", "lint_result"), False),
            (("test_result", "lint_result", "coverage_report"), False),
        ],
    )
    def test_diversity_parametric(
        self, sources: tuple[str, ...], should_veto: bool
    ) -> None:
        inp = ModelGuardrailInput(
            run_id=f"r-{len(sources)}",
            current_score=_score(),
            evidence_sources=sources,
            config=_CONFIG,
        )
        output = run_all_guardrails(inp)
        assert output.should_veto is should_veto
