# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the retry-budget invariant (OMN-15066).

RED/GREEN pair against the actual defect: the hostile-reviewer CI job's OLD
35-minute ceiling failed the invariant against the live model_registry.yaml
(RED -- reproduces the bug deterministically, no live network/GPU call); the
NEW ceiling holds (GREEN -- proves the fix closes it). Both run against the
real, live-loaded registry and the real, live-installed omnibase_infra
transport's retry defaults via reflection -- not mocked constants -- so this
test breaks (loudly, in CI) the moment either drifts back out of sync.
"""

from __future__ import annotations

import pytest

from omniintelligence.review_pairing.retry_budget import (
    assert_budget_within_ceiling,
    compute_sequential_worst_case,
    resolve_live_max_retries_default,
)

pytestmark = pytest.mark.unit

_HOSTILE_REVIEWER_MODEL_KEYS = ["qwen3-review", "qwen3-review-b"]


class TestComputeSequentialWorstCase:
    def test_matches_hand_derived_formula_for_qwen3_review_b(self) -> None:
        """qwen3-review-b is registered with timeout_seconds=600.0. With the
        live max_retries default (3 -> 4 attempts) and the ModelRetryState
        default backoff (2+4+8=14s), worst case must be exactly 2414s.
        """
        [result] = compute_sequential_worst_case(["qwen3-review-b"])

        assert result.model_key == "qwen3-review-b"
        assert result.per_attempt_timeout_seconds == 600.0
        assert result.total_attempts == 1 + resolve_live_max_retries_default()
        assert result.total_attempts == 4
        assert result.backoff_seconds == 14.0
        assert result.worst_case_seconds == 4 * 600.0 + 14.0
        assert result.worst_case_seconds == 2414.0

    def test_matches_hand_derived_formula_for_qwen3_review(self) -> None:
        """qwen3-review is registered with timeout_seconds=120.0."""
        [result] = compute_sequential_worst_case(["qwen3-review"])

        assert result.per_attempt_timeout_seconds == 120.0
        assert result.worst_case_seconds == 4 * 120.0 + 14.0
        assert result.worst_case_seconds == 494.0

    def test_sequential_sum_across_both_hostile_reviewer_models(self) -> None:
        """The hostile-reviewer workflow calls both models in a single
        sequential (non-concurrent) loop -- the caller must sum, not max.
        """
        results = compute_sequential_worst_case(_HOSTILE_REVIEWER_MODEL_KEYS)

        assert [r.model_key for r in results] == _HOSTILE_REVIEWER_MODEL_KEYS
        total = sum(r.worst_case_seconds for r in results)
        assert total == 494.0 + 2414.0
        assert total == 2908.0

    def test_cli_fallback_models_are_excluded(self) -> None:
        """codex is a subprocess CLI call, not an HTTP retry loop -- it must
        not be included in the HTTP-transport retry-budget calculation.
        """
        results = compute_sequential_worst_case(["codex"])

        assert results == []

    def test_explicit_max_retries_override_is_honored(self) -> None:
        [result] = compute_sequential_worst_case(["qwen3-review-b"], max_retries=1)

        assert result.total_attempts == 2
        # Single retry: one backoff delay of 2.0s.
        assert result.backoff_seconds == 2.0
        assert result.worst_case_seconds == 2 * 600.0 + 2.0


class TestAssertBudgetWithinCeiling:
    def test_red_old_hostile_reviewer_ceiling_violates_invariant(self) -> None:
        """RED reproduction: the hostile-reviewer job's OLD timeout-minutes=35
        (2100s) is exceeded by qwen3-review-b's worst case ALONE (2414s),
        before qwen3-review's 494s or any setup overhead is even added. This
        is the exact live defect (OMN-15066, jobs 89616541439/89616551741,
        both cancelled at 35m21s).
        """
        old_job_timeout_seconds = 35 * 60

        with pytest.raises(AssertionError, match="Retry-budget invariant violated"):
            assert_budget_within_ceiling(
                _HOSTILE_REVIEWER_MODEL_KEYS,
                job_timeout_seconds=old_job_timeout_seconds,
            )

    def test_green_new_hostile_reviewer_ceiling_holds(self) -> None:
        """GREEN: the fixed ceiling (see hostile-reviewer.yml
        timeout-minutes) comfortably exceeds the sequential worst case
        (2908s) plus a realistic setup-overhead buffer.
        """
        new_job_timeout_seconds = 60 * 60  # keep in sync with hostile-reviewer.yml
        setup_overhead_seconds = 300.0

        results = assert_budget_within_ceiling(
            _HOSTILE_REVIEWER_MODEL_KEYS,
            job_timeout_seconds=new_job_timeout_seconds,
            setup_overhead_seconds=setup_overhead_seconds,
        )

        assert len(results) == 2
        total = sum(r.worst_case_seconds for r in results) + setup_overhead_seconds
        assert total < new_job_timeout_seconds

    def test_boundary_equal_is_still_a_violation(self) -> None:
        """A job timeout exactly equal to the worst case is NOT safe -- GitHub
        Actions cancellation happens at or before the wall-clock boundary, so
        the invariant must be a strict '<', and this asserts '>=' fails.
        """
        [result] = compute_sequential_worst_case(["qwen3-review-b"])

        with pytest.raises(AssertionError, match="Retry-budget invariant violated"):
            assert_budget_within_ceiling(
                ["qwen3-review-b"],
                job_timeout_seconds=result.worst_case_seconds,
            )

    def test_violation_message_includes_per_model_breakdown(self) -> None:
        with pytest.raises(AssertionError) as exc_info:
            assert_budget_within_ceiling(
                _HOSTILE_REVIEWER_MODEL_KEYS,
                job_timeout_seconds=1.0,
            )

        message = str(exc_info.value)
        assert "qwen3-review-b" in message
        assert "qwen3-review" in message
        assert "OMN-15066" in message


class TestResolveLiveMaxRetriesDefault:
    def test_returns_an_int(self) -> None:
        assert isinstance(resolve_live_max_retries_default(), int)
