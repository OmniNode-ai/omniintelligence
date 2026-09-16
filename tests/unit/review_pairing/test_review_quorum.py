# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for multi-model quorum aggregation of adversarial review findings.

A finding blocks only when at least ``min_agreeing_models`` DISTINCT
successful models raise a matching fingerprint. A finding raised by one
model is a warning: reported, never dropped, never blocking. Fewer than
the threshold's worth of successful models is not a verdict at all --
the CLI fails closed on it.

Every zero asserted here has a positive control beside it: the
single-model "not blocking" assertions are paired with a two-model
assertion over the same fixture that DOES block, so a quorum evaluator
that simply never blocks fails the suite.

Reference: OMN-18479
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from omniintelligence.review_pairing.cli_review import main
from omniintelligence.review_pairing.model_registry_loader import (
    ModelRegistryLoadError,
    load_registry,
)
from omniintelligence.review_pairing.models import (
    EnumFindingSeverity,
    ModelReviewFindingObserved,
)
from omniintelligence.review_pairing.models_external_review import (
    EnumQuorumVerdict,
    ModelExternalReviewResult,
    ModelMultiReviewResult,
    ModelReviewQuorumPolicy,
)
from omniintelligence.review_pairing.prompts.adversarial_reviewer import (
    PROMPT_VERSION,
)
from omniintelligence.review_pairing.quorum import evaluate_quorum

_DEFAULT_POLICY = ModelReviewQuorumPolicy()


def _finding(
    model: str,
    *,
    file_path: str = "src/app.py:120",
    category: str = "security",
    severity: EnumFindingSeverity = EnumFindingSeverity.ERROR,
    line_start: int = 1,
    message: str = "unvalidated input reaches the query builder",
) -> ModelReviewFindingObserved:
    """Build a finding shaped exactly like ``adapter_ai_reviewer`` emits one.

    That adapter writes ``rule_id = f"ai-reviewer:{model_key}:{category}"``
    and ``line_start = 1`` for every LLM finding, putting the real location
    in ``file_path``. The fixture mirrors that, so a fingerprint that keys
    on the raw ``rule_id`` can never agree across models and fails here.
    """
    return ModelReviewFindingObserved(
        finding_id=uuid4(),
        repo="OmniNode-ai/omniclaude",
        pr_id=2202,
        rule_id=f"ai-reviewer:{model}:{category}",
        severity=severity,
        file_path=file_path,
        line_start=line_start,
        line_end=None,
        tool_name=f"ai-reviewer:{model}",
        tool_version=PROMPT_VERSION,
        normalized_message=message,
        raw_message=message,
        commit_sha_observed="3e7cb51",
        observed_at=datetime(2026, 9, 16, 19, 0, tzinfo=UTC),
    )


def _model_result(
    model: str,
    findings: list[ModelReviewFindingObserved],
    *,
    success: bool = True,
) -> ModelExternalReviewResult:
    return ModelExternalReviewResult(
        model=model,
        prompt_version=PROMPT_VERSION,
        success=success,
        error=None if success else "endpoint unreachable",
        findings=findings if success else [],
        result_count=len(findings) if success else 0,
    )


def _multi(*results: ModelExternalReviewResult) -> ModelMultiReviewResult:
    return ModelMultiReviewResult(
        models_attempted=[r.model for r in results],
        models_succeeded=[r.model for r in results if r.success],
        models_failed=[r.model for r in results if not r.success],
        results=list(results),
        total_findings=sum(r.result_count for r in results if r.success),
    )


# ---------------------------------------------------------------------------
# Quorum evaluation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestQuorumEvaluation:
    def test_single_model_finding_is_a_warning_not_a_block(self) -> None:
        """One model raising a critical finding must not block (AC1)."""
        summary = evaluate_quorum(
            _multi(
                _model_result("deepseek-r1", [_finding("deepseek-r1")]),
                _model_result("qwen3-review-b", []),
            ),
            _DEFAULT_POLICY,
        )
        assert summary.verdict is EnumQuorumVerdict.PASSED
        assert summary.blocking_count == 0
        assert summary.warning_count == 1
        assert summary.warning_findings[0].agreement_count == 1
        assert summary.warning_findings[0].agreeing_models == ("deepseek-r1",)

    def test_two_models_agreeing_block(self) -> None:
        """Positive control for the zero above: the same finding, twice, blocks (AC1/AC4)."""
        summary = evaluate_quorum(
            _multi(
                _model_result("deepseek-r1", [_finding("deepseek-r1")]),
                _model_result("qwen3-review-b", [_finding("qwen3-review-b")]),
            ),
            _DEFAULT_POLICY,
        )
        assert summary.verdict is EnumQuorumVerdict.BLOCKED
        assert summary.blocking_count == 1
        assert summary.warning_count == 0
        assert summary.blocking_findings[0].agreement_count == 2
        assert summary.blocking_findings[0].agreeing_models == (
            "deepseek-r1",
            "qwen3-review-b",
        )

    def test_two_models_disagreeing_produce_two_warnings(self) -> None:
        """Same fixture, different file: two warnings, no block (AC4)."""
        summary = evaluate_quorum(
            _multi(
                _model_result(
                    "deepseek-r1", [_finding("deepseek-r1", file_path="src/app.py:120")]
                ),
                _model_result(
                    "qwen3-review-b",
                    [_finding("qwen3-review-b", file_path="src/other.py:44")],
                ),
            ),
            _DEFAULT_POLICY,
        )
        assert summary.verdict is EnumQuorumVerdict.PASSED
        assert summary.blocking_count == 0
        assert summary.warning_count == 2

    def test_one_model_raising_the_same_finding_twice_is_not_a_quorum(self) -> None:
        """Agreement counts DISTINCT models, never repeated findings from one."""
        summary = evaluate_quorum(
            _multi(
                _model_result(
                    "deepseek-r1",
                    [_finding("deepseek-r1"), _finding("deepseek-r1")],
                ),
                _model_result("qwen3-review-b", []),
            ),
            _DEFAULT_POLICY,
        )
        assert summary.blocking_count == 0
        assert summary.warning_findings[0].agreement_count == 1

    def test_line_proximity_within_radius_agrees(self) -> None:
        summary = evaluate_quorum(
            _multi(
                _model_result(
                    "deepseek-r1", [_finding("deepseek-r1", file_path="src/app.py:120")]
                ),
                _model_result(
                    "qwen3-review-b",
                    [_finding("qwen3-review-b", file_path="src/app.py:122")],
                ),
            ),
            _DEFAULT_POLICY,
        )
        assert summary.verdict is EnumQuorumVerdict.BLOCKED

    def test_line_proximity_beyond_radius_does_not_agree(self) -> None:
        summary = evaluate_quorum(
            _multi(
                _model_result(
                    "deepseek-r1", [_finding("deepseek-r1", file_path="src/app.py:120")]
                ),
                _model_result(
                    "qwen3-review-b",
                    [_finding("qwen3-review-b", file_path="src/app.py:400")],
                ),
            ),
            _DEFAULT_POLICY,
        )
        assert summary.verdict is EnumQuorumVerdict.PASSED
        assert summary.warning_count == 2

    def test_model_key_inside_rule_id_does_not_prevent_agreement(self) -> None:
        """``ai-reviewer:{model}:{category}`` must be normalised to its category."""
        summary = evaluate_quorum(
            _multi(
                _model_result("deepseek-r1", [_finding("deepseek-r1")]),
                _model_result("glm-review", [_finding("glm-review")]),
            ),
            _DEFAULT_POLICY,
        )
        assert summary.verdict is EnumQuorumVerdict.BLOCKED

    def test_differing_categories_do_not_agree(self) -> None:
        summary = evaluate_quorum(
            _multi(
                _model_result(
                    "deepseek-r1", [_finding("deepseek-r1", category="security")]
                ),
                _model_result(
                    "qwen3-review-b", [_finding("qwen3-review-b", category="style")]
                ),
            ),
            _DEFAULT_POLICY,
        )
        assert summary.verdict is EnumQuorumVerdict.PASSED

    def test_non_blocking_severity_never_blocks_even_with_agreement(self) -> None:
        summary = evaluate_quorum(
            _multi(
                _model_result(
                    "deepseek-r1",
                    [_finding("deepseek-r1", severity=EnumFindingSeverity.WARNING)],
                ),
                _model_result(
                    "qwen3-review-b",
                    [_finding("qwen3-review-b", severity=EnumFindingSeverity.WARNING)],
                ),
            ),
            _DEFAULT_POLICY,
        )
        assert summary.verdict is EnumQuorumVerdict.PASSED
        assert summary.blocking_count == 0
        assert summary.warning_count == 1
        assert summary.warning_findings[0].agreement_count == 2

    def test_failed_model_findings_are_not_counted(self) -> None:
        """A failed model cannot supply half of a quorum."""
        summary = evaluate_quorum(
            _multi(
                _model_result("deepseek-r1", [_finding("deepseek-r1")]),
                _model_result("qwen3-review-b", [], success=False),
            ),
            _DEFAULT_POLICY,
        )
        assert summary.verdict is EnumQuorumVerdict.DEGRADED_QUORUM
        assert summary.quorum_met is False

    def test_one_succeeded_model_is_degraded_quorum(self) -> None:
        summary = evaluate_quorum(
            _multi(_model_result("deepseek-r1", [])), _DEFAULT_POLICY
        )
        assert summary.verdict is EnumQuorumVerdict.DEGRADED_QUORUM
        assert summary.quorum_met is False
        assert summary.blocking_count == 0

    def test_zero_succeeded_models_is_no_models(self) -> None:
        summary = evaluate_quorum(
            _multi(_model_result("deepseek-r1", [], success=False)), _DEFAULT_POLICY
        )
        assert summary.verdict is EnumQuorumVerdict.NO_MODELS

    def test_raised_threshold_is_honoured(self) -> None:
        """A caller may RAISE the threshold; two agreeing models then fall short."""
        summary = evaluate_quorum(
            _multi(
                _model_result("deepseek-r1", [_finding("deepseek-r1")]),
                _model_result("qwen3-review-b", [_finding("qwen3-review-b")]),
            ),
            ModelReviewQuorumPolicy(min_agreeing_models=3),
        )
        assert summary.verdict is EnumQuorumVerdict.DEGRADED_QUORUM


# ---------------------------------------------------------------------------
# Contract-declared threshold
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestQuorumPolicyContract:
    def test_policy_refuses_threshold_below_two(self) -> None:
        with pytest.raises(ValueError):
            ModelReviewQuorumPolicy(min_agreeing_models=1)

    def test_shipped_registry_declares_a_quorum_policy(self) -> None:
        contract = load_registry()
        assert contract.review_quorum.min_agreeing_models >= 2
        assert contract.review_quorum.line_proximity_lines >= 0
        assert EnumFindingSeverity.ERROR in contract.review_quorum.blocking_severities

    def test_registry_rejects_a_threshold_below_two(self, tmp_path: Path) -> None:
        path = tmp_path / "reg.yaml"
        path.write_text(
            """
default_model_key: real
local_model_keys: []
api_fallback_keys: []
review_quorum:
  min_agreeing_models: 1
models:
  real:
    env_var: LLM_REAL_URL
    default_url: "http://example.invalid"
    kind: reasoning
    timeout_seconds: 10.0
    api_model_id: real
""",
            encoding="utf-8",
        )
        with pytest.raises(ModelRegistryLoadError):
            load_registry(path)


# ---------------------------------------------------------------------------
# CLI exit-code contract
# ---------------------------------------------------------------------------


def _run_cli(
    tmp_path: Path,
    results: list[ModelExternalReviewResult],
    extra_args: list[str] | None = None,
) -> tuple[int, str]:
    plan_file = tmp_path / "plan.md"
    plan_file.write_text("# Test Plan")
    output_file = tmp_path / "out.json"
    model_keys = [r.model for r in results]
    argv = ["--file", str(plan_file), "--output", str(output_file)]
    for key in model_keys:
        argv += ["--model", key]
    argv += extra_args or []

    with (
        patch(
            "omniintelligence.review_pairing.cli_review.select_models_with_fallback",
            return_value=(model_keys, []),
        ),
        patch(
            "omniintelligence.review_pairing.cli_review.llm_async_parse_raw",
            new_callable=AsyncMock,
            side_effect=list(results),
        ),
    ):
        code = main(argv)
    return code, output_file.read_text(encoding="utf-8") if output_file.exists() else ""


@pytest.mark.unit
class TestCliQuorumExitCodes:
    def test_single_succeeded_model_exits_two_with_degraded_quorum(
        self, tmp_path: Path
    ) -> None:
        code, payload = _run_cli(
            tmp_path,
            [
                _model_result("deepseek-r1", [_finding("deepseek-r1")]),
                _model_result("qwen3-review-b", [], success=False),
            ],
        )
        assert code == 2
        assert '"verdict": "degraded_quorum"' in payload

    def test_all_models_failed_exits_one(self, tmp_path: Path) -> None:
        code, _ = _run_cli(tmp_path, [_model_result("deepseek-r1", [], success=False)])
        assert code == 1

    def test_two_agreeing_models_exit_zero_and_report_blocked(
        self, tmp_path: Path
    ) -> None:
        code, payload = _run_cli(
            tmp_path,
            [
                _model_result("deepseek-r1", [_finding("deepseek-r1")]),
                _model_result("qwen3-review-b", [_finding("qwen3-review-b")]),
            ],
        )
        assert code == 0
        assert '"verdict": "blocked"' in payload
        assert '"blocking_count": 1' in payload

    def test_two_disagreeing_models_exit_zero_and_report_passed(
        self, tmp_path: Path
    ) -> None:
        code, payload = _run_cli(
            tmp_path,
            [
                _model_result(
                    "deepseek-r1", [_finding("deepseek-r1", file_path="src/a.py:10")]
                ),
                _model_result(
                    "qwen3-review-b",
                    [_finding("qwen3-review-b", file_path="src/b.py:10")],
                ),
            ],
        )
        assert code == 0
        assert '"verdict": "passed"' in payload
        assert '"warning_count": 2' in payload

    def test_quorum_threshold_below_contract_minimum_is_refused(
        self, tmp_path: Path
    ) -> None:
        code, _ = _run_cli(
            tmp_path,
            [
                _model_result("deepseek-r1", []),
                _model_result("qwen3-review-b", []),
            ],
            extra_args=["--quorum-threshold", "1"],
        )
        assert code == 1

    def test_raised_quorum_threshold_degrades_a_two_model_run(
        self, tmp_path: Path
    ) -> None:
        code, payload = _run_cli(
            tmp_path,
            [
                _model_result("deepseek-r1", []),
                _model_result("qwen3-review-b", []),
            ],
            extra_args=["--quorum-threshold", "3"],
        )
        assert code == 2
        assert '"verdict": "degraded_quorum"' in payload
