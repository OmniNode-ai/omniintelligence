# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for RunnerPrReview and RunnerPrecommit.

Tests cover OMN-2496 acceptance criteria:
- R1: Workflow triggers on PR open/push (tested via runner behavior)
- R2: CI check result follows enforcement mode
- R3: Pre-commit hook reuses runner code with fast rules only
"""

from __future__ import annotations

import textwrap
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from omniintelligence.review_bot.models.model_review_severity import ReviewSeverity
from omniintelligence.review_bot.runner.runner_pr_review import (
    PrReviewResult,
    RunnerPrReview,
)
from omniintelligence.review_bot.runner.runner_precommit import RunnerPrecommit
from omniintelligence.review_bot.schemas.model_review_policy import (
    ModelReviewPolicy,
    ModelReviewRule,
)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def make_policy(
    enforcement_mode: str = "observe",
    rules: list[ModelReviewRule] | None = None,
) -> ModelReviewPolicy:
    if rules is None:
        rules = [
            ModelReviewRule(
                id="no-bare-except",
                severity=ReviewSeverity.BLOCKER,
                pattern=r"except:",
                message="Bare except is dangerous",
            )
        ]
    return ModelReviewPolicy(
        version="1.0",
        enforcement_mode=enforcement_mode,
        rules=rules,
    )


DIFF_WITH_BLOCKER = textwrap.dedent("""
    diff --git a/src/handler.py b/src/handler.py
    index abc..def 100644
    --- a/src/handler.py
    +++ b/src/handler.py
    @@ -1,3 +1,5 @@
     def handle():
    +    try:
    +        pass
    +    except:
    +        pass
""")

DIFF_CLEAN = textwrap.dedent("""
    diff --git a/src/handler.py b/src/handler.py
    index abc..def 100644
    --- a/src/handler.py
    +++ b/src/handler.py
    @@ -1,1 +1,3 @@
     def handle():
    +    # Clean code
    +    pass
""")

DIFF_EMPTY = ""


# ---------------------------------------------------------------------------
# RunnerPrReview tests
# ---------------------------------------------------------------------------


class TestRunnerPrReviewObserveMode:
    """R2: OBSERVE mode always passes CI."""

    def setup_method(self) -> None:
        self.runner = RunnerPrReview()

    def test_observe_passes_with_blockers(self) -> None:
        policy = make_policy(enforcement_mode="observe")
        result = self.runner.run(DIFF_WITH_BLOCKER, policy)
        assert result.ci_passed is True
        assert result.enforcement_mode == "observe"

    def test_observe_passes_clean(self) -> None:
        policy = make_policy(enforcement_mode="observe")
        result = self.runner.run(DIFF_CLEAN, policy)
        assert result.ci_passed is True

    def test_observe_logs_findings_in_summary(self) -> None:
        policy = make_policy(enforcement_mode="observe")
        result = self.runner.run(DIFF_WITH_BLOCKER, policy)
        assert "BLOCKER" in result.summary or "no-bare-except" in result.summary


class TestRunnerPrReviewWarnMode:
    """R2: WARN mode always passes CI."""

    def setup_method(self) -> None:
        self.runner = RunnerPrReview()

    def test_warn_passes_with_blockers(self) -> None:
        policy = make_policy(enforcement_mode="warn")
        result = self.runner.run(DIFF_WITH_BLOCKER, policy)
        assert result.ci_passed is True
        assert result.enforcement_mode == "warn"

    def test_warn_passes_clean(self) -> None:
        policy = make_policy(enforcement_mode="warn")
        result = self.runner.run(DIFF_CLEAN, policy)
        assert result.ci_passed is True


class TestRunnerPrReviewBlockMode:
    """R2: BLOCK mode fails if any BLOCKER findings present."""

    def setup_method(self) -> None:
        self.runner = RunnerPrReview()

    def test_block_fails_with_blockers(self) -> None:
        policy = make_policy(enforcement_mode="block")
        result = self.runner.run(DIFF_WITH_BLOCKER, policy)
        assert result.ci_passed is False

    def test_block_passes_clean(self) -> None:
        policy = make_policy(enforcement_mode="block")
        result = self.runner.run(DIFF_CLEAN, policy)
        assert result.ci_passed is True

    def test_block_passes_with_warnings_only(self) -> None:
        policy = make_policy(
            enforcement_mode="block",
            rules=[
                ModelReviewRule(
                    id="no-print",
                    severity=ReviewSeverity.WARNING,
                    pattern=r"print\(",
                    message="No print",
                )
            ],
        )
        diff = textwrap.dedent("""
            diff --git a/src/x.py b/src/x.py
            index abc..def 100644
            --- a/src/x.py
            +++ b/src/x.py
            @@ -1 +1,2 @@
             x = 1
            +print("debug")
        """)
        result = self.runner.run(diff, policy)
        # Warnings don't block
        assert result.ci_passed is True

    def test_block_fails_summarizes_blockers(self) -> None:
        policy = make_policy(enforcement_mode="block")
        result = self.runner.run(DIFF_WITH_BLOCKER, policy)
        assert "FAILED" in result.summary or "BLOCKER" in result.summary


class TestRunnerPrReviewFindings:
    def setup_method(self) -> None:
        self.runner = RunnerPrReview()

    def test_empty_diff_no_findings(self) -> None:
        policy = make_policy()
        result = self.runner.run(DIFF_EMPTY, policy)
        assert result.findings == []
        assert result.score.score == 100

    def test_clean_diff_no_findings(self) -> None:
        policy = make_policy()
        result = self.runner.run(DIFF_CLEAN, policy)
        assert result.findings == []

    def test_blocker_diff_has_findings(self) -> None:
        policy = make_policy()
        result = self.runner.run(DIFF_WITH_BLOCKER, policy)
        assert len(result.findings) > 0
        assert any(f.severity == ReviewSeverity.BLOCKER for f in result.findings)

    def test_finding_has_file_path(self) -> None:
        policy = make_policy()
        result = self.runner.run(DIFF_WITH_BLOCKER, policy)
        for finding in result.findings:
            assert finding.file_path != ""

    def test_finding_has_line_number(self) -> None:
        policy = make_policy()
        result = self.runner.run(DIFF_WITH_BLOCKER, policy)
        assert any(f.line_number is not None for f in result.findings)

    def test_score_derived_from_findings(self) -> None:
        policy = make_policy()
        result = self.runner.run(DIFF_WITH_BLOCKER, policy)
        # Blockers cap score at 50
        assert result.score.score <= 50

    def test_multiple_rules_applied(self) -> None:
        policy = make_policy(
            rules=[
                ModelReviewRule(
                    id="no-bare-except",
                    severity=ReviewSeverity.BLOCKER,
                    pattern=r"except:",
                    message="Bare except",
                ),
                ModelReviewRule(
                    id="no-eval",
                    severity=ReviewSeverity.BLOCKER,
                    pattern=r"\beval\s*\(",
                    message="No eval",
                ),
            ]
        )
        diff = textwrap.dedent("""
            diff --git a/src/x.py b/src/x.py
            index abc..def 100644
            --- a/src/x.py
            +++ b/src/x.py
            @@ -1 +1,3 @@
             x = 1
            +except:
            +eval("bad")
        """)
        result = self.runner.run(diff, policy)
        rule_ids = {f.rule_id for f in result.findings}
        assert "no-bare-except" in rule_ids
        assert "no-eval" in rule_ids


class TestRunnerPrReviewExemptions:
    def setup_method(self) -> None:
        self.runner = RunnerPrReview()

    def test_exempted_path_skipped(self) -> None:
        from omniintelligence.review_bot.schemas.model_review_policy import (
            ModelReviewExemption,
        )

        future = (date.today() + timedelta(days=365)).isoformat()
        policy = ModelReviewPolicy(
            version="1.0",
            rules=[
                ModelReviewRule(
                    id="no-bare-except",
                    severity=ReviewSeverity.BLOCKER,
                    pattern=r"except:",
                    message="Bare except",
                )
            ],
            exemptions=[
                ModelReviewExemption(
                    rule="no-bare-except",
                    path="tests/",
                    expires=future,
                    reason="Legacy tests",
                )
            ],
        )
        diff = textwrap.dedent("""
            diff --git a/tests/test_handler.py b/tests/test_handler.py
            index abc..def 100644
            --- a/tests/test_handler.py
            +++ b/tests/test_handler.py
            @@ -1 +1,3 @@
             x = 1
            +try:
            +    pass
            +except:
            +    pass
        """)
        result = self.runner.run(diff, policy)
        # Exempt path should produce no findings
        exempt_findings = [
            f for f in result.findings if f.file_path.startswith("tests/")
        ]
        assert exempt_findings == []


class TestRunnerPrReviewSlowRules:
    def setup_method(self) -> None:
        self.runner = RunnerPrReview()

    def test_slow_rules_included_when_slow_true(self) -> None:
        policy = make_policy(
            rules=[
                ModelReviewRule(
                    id="slow-rule",
                    severity=ReviewSeverity.WARNING,
                    pattern=r"print\(",
                    message="No print",
                    slow=True,
                )
            ]
        )
        diff = textwrap.dedent("""
            diff --git a/src/x.py b/src/x.py
            index abc..def 100644
            --- a/src/x.py
            +++ b/src/x.py
            @@ -1 +1,2 @@
             x = 1
            +print("debug")
        """)
        result = self.runner.run(diff, policy, slow=True)
        assert any(f.rule_id == "slow-rule" for f in result.findings)

    def test_slow_rules_excluded_when_slow_false(self) -> None:
        policy = make_policy(
            rules=[
                ModelReviewRule(
                    id="slow-rule",
                    severity=ReviewSeverity.WARNING,
                    pattern=r"print\(",
                    message="No print",
                    slow=True,
                )
            ]
        )
        diff = textwrap.dedent("""
            diff --git a/src/x.py b/src/x.py
            index abc..def 100644
            --- a/src/x.py
            +++ b/src/x.py
            @@ -1 +1,2 @@
             x = 1
            +print("debug")
        """)
        result = self.runner.run(diff, policy, slow=False)
        # Slow rule should be skipped
        assert not any(f.rule_id == "slow-rule" for f in result.findings)


class TestRunnerPrReviewLoadPolicy:
    def test_load_policy_missing_file(self, tmp_path: object) -> None:
        runner = RunnerPrReview()
        result = runner.load_policy("/nonexistent/review_policy.yaml")
        assert result is None

    def test_load_policy_valid_file(self, tmp_path: object) -> None:

        policy_content = textwrap.dedent("""
            version: "1.0"
            rules:
              - id: no-bare-except
                severity: BLOCKER
                pattern: "except:"
                message: "Bare except"
        """)
        assert isinstance(tmp_path, type(tmp_path))  # tmp_path is pathlib.Path
        policy_file = tmp_path / "review_policy.yaml"  # type: ignore[operator]
        policy_file.write_text(policy_content)

        runner = RunnerPrReview()
        policy = runner.load_policy(str(policy_file))
        assert policy is not None
        assert policy.version == "1.0"


# ---------------------------------------------------------------------------
# RunnerPrecommit tests
# ---------------------------------------------------------------------------


class TestRunnerPrecommit:
    """R3: Pre-commit reuses runner code with fast rules only."""

    def test_precommit_skips_slow_rules(self) -> None:
        """Pre-commit uses slow=False, skipping slow rules."""
        from unittest.mock import patch

        runner = RunnerPrecommit()

        with (
            patch.object(RunnerPrReview, "run") as mock_run,
            patch.object(RunnerPrReview, "load_policy") as mock_load,
        ):
            mock_load.return_value = make_policy()
            mock_run.return_value = PrReviewResult(
                findings=[],
                score=MagicMock(score=100),
                enforcement_mode="observe",
                ci_passed=True,
                summary="No findings",
            )

            runner.run_with_diff("some diff", policy_path="review_policy.yaml")

            # Verify slow=False was passed
            call_kwargs = mock_run.call_args
            assert call_kwargs.kwargs.get("slow") is False

    def test_precommit_exits_0_on_pass(self) -> None:
        runner = RunnerPrecommit()
        policy = make_policy(enforcement_mode="block")

        with patch.object(RunnerPrReview, "load_policy", return_value=policy):
            exit_code = runner.run_with_diff(DIFF_CLEAN)
            assert exit_code == 0

    def test_precommit_exits_1_on_blocker_block_mode(self) -> None:
        runner = RunnerPrecommit()
        policy = make_policy(enforcement_mode="block")

        with patch.object(RunnerPrReview, "load_policy", return_value=policy):
            exit_code = runner.run_with_diff(DIFF_WITH_BLOCKER)
            assert exit_code == 1

    def test_precommit_exits_0_on_blocker_observe_mode(self) -> None:
        runner = RunnerPrecommit()
        policy = make_policy(enforcement_mode="observe")

        with patch.object(RunnerPrReview, "load_policy", return_value=policy):
            exit_code = runner.run_with_diff(DIFF_WITH_BLOCKER)
            assert exit_code == 0

    def test_precommit_exits_0_on_blocker_warn_mode(self) -> None:
        runner = RunnerPrecommit()
        policy = make_policy(enforcement_mode="warn")

        with patch.object(RunnerPrReview, "load_policy", return_value=policy):
            exit_code = runner.run_with_diff(DIFF_WITH_BLOCKER)
            assert exit_code == 0

    def test_precommit_exits_0_no_policy(self) -> None:
        runner = RunnerPrecommit()

        with patch.object(RunnerPrReview, "load_policy", return_value=None):
            exit_code = runner.run_with_diff(DIFF_WITH_BLOCKER)
            assert exit_code == 0

    def test_precommit_exits_0_empty_diff(self) -> None:
        runner = RunnerPrecommit()
        policy = make_policy(enforcement_mode="block")

        with patch.object(RunnerPrReview, "load_policy", return_value=policy):
            exit_code = runner.run_with_diff("")
            assert exit_code == 0
