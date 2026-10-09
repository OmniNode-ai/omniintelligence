# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""A gated review runs with the reviewed repository's standing rules or not at all.

OMN-20784, task T17 of the process-holes plan. One test group per acceptance
criterion; the group's name is the ``-k`` falsifier on the ticket.

The rules used by the fixtures are generic placeholders. A real rules file is the
reviewed repository's private overlay and is never shipped here.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from omniintelligence.handlers.handler_review_standing_rules import handle
from omniintelligence.models.review.model_review_standing_rules import (
    ModelReviewStandingRules,
)
from omniintelligence.models.review.model_standing_rules_request import (
    ModelStandingRulesRequest,
)
from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
    async_parse_raw,
    build_review_prompt,
    parse_raw,
)
from omniintelligence.review_pairing.cli_review import main
from omniintelligence.review_pairing.models import EnumFindingSeverity
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

_CLI = "omniintelligence.review_pairing.cli_review"
_ADAPTER = "omniintelligence.review_pairing.adapters.adapter_ai_reviewer"

_MANDATORY_ID = "no-deployment-facts-in-shipped-config"
_OPTIONAL_ID = "prefer-small-diffs"

_RULES_YAML = f"""\
schema_version: 1
version: "2026-10-09.1"
rules:
  - id: {_MANDATORY_ID}
    mandatory: true
    text: Shipped configuration names no host, lane or endpoint of a private deployment.
  - id: {_OPTIONAL_ID}
    mandatory: false
    text: A change touches one concern.
"""

_RULES_WITHOUT_MANDATORY_YAML = f"""\
schema_version: 1
version: "2026-10-09.2"
rules:
  - id: {_OPTIONAL_ID}
    mandatory: false
    text: A change touches one concern.
"""

_RULES_DEMOTED_YAML = _RULES_YAML.replace("mandatory: true", "mandatory: false")
_RULES_REWORDED_YAML = _RULES_YAML.replace(
    "names no host", "should avoid naming a host"
)
_RULES_EXTENDED_YAML = (
    _RULES_YAML
    + """\
  - id: tests-accompany-code
    mandatory: false
    text: A behaviour change carries a test.
"""
)


def _success(model: str, findings: list | None = None) -> ModelExternalReviewResult:
    return ModelExternalReviewResult(
        model=model,
        prompt_version=PROMPT_VERSION,
        success=True,
        findings=findings or [],
        result_count=len(findings or []),
    )


def _two_models() -> tuple[str, str]:
    return ("deepseek-r1", "qwen3-coder")


def _run_cli(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, str, AsyncMock]:
    """Run ``main`` with the model layer mocked; return (exit, stdout, llm mock)."""
    with (
        patch(
            f"{_CLI}.select_models_with_fallback",
            return_value=(list(_two_models()), []),
        ),
        patch(
            f"{_CLI}.llm_async_parse_raw",
            new_callable=AsyncMock,
            side_effect=lambda *_a, model, **_k: _success(model),
        ) as llm,
    ):
        code = main(argv)
    return code, capsys.readouterr().out, llm


def _plan(tmp_path: Path) -> Path:
    plan = tmp_path / "plan.md"
    plan.write_text("# Plan\n\nDo the thing.\n", encoding="utf-8")
    return plan


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _repo_with_base_and_pr(
    tmp_path: Path, *, base_rules: str | None, pr_rules: str | None
) -> Path:
    """A git repo whose ``base`` branch holds ``base_rules`` and ``pr`` holds ``pr_rules``.

    ``None`` means the rules file is absent on that branch. The working tree is
    left on ``pr``, as in a pull request checkout.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "base")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    if base_rules is not None:
        (repo / "rules.yaml").write_text(base_rules, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "checkout", "-q", "-b", "pr")
    if pr_rules is None:
        if base_rules is not None:
            _git(repo, "rm", "-q", "rules.yaml")
    else:
        (repo / "rules.yaml").write_text(pr_rules, encoding="utf-8")
        _git(repo, "add", "-A")
    (repo / "change.txt").write_text("a change\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "pr")
    return repo


def _gated_argv(plan: Path, repo: Path) -> list[str]:
    return [
        "--file",
        str(plan),
        "--gated",
        "--rules-file",
        "rules.yaml",
        "--rules-base-ref",
        "base",
        "--rules-head-ref",
        "pr",
        "--rules-repo-dir",
        str(repo),
    ]


# ---------------------------------------------------------------------------
# AC1: a gated review with no rules file, or an invalid one, fails before any
# model call.
# ---------------------------------------------------------------------------


class TestGatedReviewRequiresRules:
    def test_gated_review_requires_rules_file_argument(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, out, llm = _run_cli(["--file", str(_plan(tmp_path)), "--gated"], capsys)
        assert code == 1
        assert out == ""
        llm.assert_not_called()

    def test_gated_review_requires_rules_file_that_exists(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        argv = [
            "--file",
            str(_plan(tmp_path)),
            "--gated",
            "--rules-file",
            str(tmp_path / "absent.yaml"),
        ]
        code, out, llm = _run_cli(argv, capsys)
        assert code == 1
        assert out == ""
        llm.assert_not_called()

    @pytest.mark.parametrize(
        "bad_text",
        [
            pytest.param("", id="empty"),
            pytest.param("rules: [", id="not-yaml"),
            pytest.param("- just\n- a list\n", id="not-a-mapping"),
            pytest.param('schema_version: 1\nversion: "v"\nrules: []\n', id="no-rules"),
            pytest.param(
                'schema_version: 2\nversion: "v"\nrules:\n'
                "  - {id: aa, mandatory: true, text: t}\n",
                id="unknown-schema-version",
            ),
            pytest.param(
                'schema_version: 1\nversion: "v"\nrules:\n'
                "  - {id: aa, mandatory: true, text: t}\n"
                "  - {id: aa, mandatory: false, text: u}\n",
                id="duplicate-id",
            ),
            pytest.param(
                'schema_version: 1\nversion: "v"\nrules:\n'
                "  - {id: 'Bad Id', mandatory: true, text: t}\n",
                id="malformed-id",
            ),
            pytest.param(
                'schema_version: 1\nversion: "v"\nrules:\n'
                "  - {id: aa, mandatory: true, text: ''}\n",
                id="empty-text",
            ),
            pytest.param(
                'schema_version: 1\nversion: "v"\ndigest: abc\nrules:\n'
                "  - {id: aa, mandatory: true, text: t}\n",
                id="declared-digest",
            ),
        ],
    )
    def test_gated_review_requires_valid_rules(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        bad_text: str,
    ) -> None:
        rules = tmp_path / "rules.yaml"
        rules.write_text(bad_text, encoding="utf-8")
        argv = ["--file", str(_plan(tmp_path)), "--gated", "--rules-file", str(rules)]
        code, out, llm = _run_cli(argv, capsys)
        assert code == 1
        assert out == ""
        llm.assert_not_called()

    def test_gated_pull_request_review_requires_a_base_ref(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Rules for a pull request come from the base branch, never the working tree."""
        rules = tmp_path / "rules.yaml"
        rules.write_text(_RULES_YAML, encoding="utf-8")
        argv = [
            "--pr",
            "1",
            "--repo",
            "OmniNode-ai/example",
            "--gated",
            "--rules-file",
            str(rules),
        ]
        with patch(f"{_CLI}.subprocess.run") as gh:
            code, out, llm = _run_cli(argv, capsys)
        assert code == 1
        assert out == ""
        gh.assert_not_called()
        llm.assert_not_called()

    def test_gated_review_requires_rules_positive_control(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A valid rules file lets the same invocation reach the models."""
        rules = tmp_path / "rules.yaml"
        rules.write_text(_RULES_YAML, encoding="utf-8")
        argv = ["--file", str(_plan(tmp_path)), "--gated", "--rules-file", str(rules)]
        code, _out, llm = _run_cli(argv, capsys)
        assert code == 0
        assert llm.call_count == 2

    def test_gated_review_requires_rules_from_base_ref(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """No rules file on the base branch is a failure, not an empty rule set."""
        repo = _repo_with_base_and_pr(tmp_path, base_rules=None, pr_rules=_RULES_YAML)
        code, out, llm = _run_cli(_gated_argv(_plan(tmp_path), repo), capsys)
        assert code == 1
        assert out == ""
        llm.assert_not_called()

    def test_validate_rules_command(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        good = tmp_path / "good.yaml"
        good.write_text(_RULES_YAML, encoding="utf-8")
        assert main(["validate-rules", "--rules-file", str(good)]) == 0
        report = json.loads(capsys.readouterr().out)
        assert report["ok"] is True
        assert report["rule_ids"] == [_MANDATORY_ID, _OPTIONAL_ID]
        assert len(report["digest"]) == 64

        bad = tmp_path / "bad.yaml"
        bad.write_text("rules: [", encoding="utf-8")
        assert main(["validate-rules", "--rules-file", str(bad)]) == 1
        assert json.loads(capsys.readouterr().out)["ok"] is False


# ---------------------------------------------------------------------------
# AC2: every rule appears in the rendered prompt by id; the verdict record
# carries the rules digest.
# ---------------------------------------------------------------------------


def _load(text: str) -> ModelReviewStandingRules:
    result = handle(ModelStandingRulesRequest(rules_text=text))
    assert result.ok, result.errors
    assert result.rules is not None
    return result.rules


class TestStandingRulesRenderedAndDigested:
    def test_standing_rules_rendered_and_digested_in_prompt(self) -> None:
        rules = _load(_RULES_YAML)
        system_prompt, _user = build_review_prompt("a diff", standing_rules=rules)
        for rule in rules.rules:
            assert rule.id in system_prompt
            assert rule.text in system_prompt
        # The mandatory flag is rendered so the model knows which rules must block.
        mandatory_line = next(
            line for line in system_prompt.splitlines() if _MANDATORY_ID in line
        )
        assert "mandatory" in mandatory_line.lower()

    def test_prompt_without_rules_names_no_rule(self) -> None:
        system_prompt, _user = build_review_prompt("a diff")
        assert _MANDATORY_ID not in system_prompt
        assert "Standing Rules" not in system_prompt

    def test_standing_rules_rendered_and_digested_for_the_model_call(self) -> None:
        """The prompt the endpoint receives is the one with the rules in it."""
        rules = _load(_RULES_YAML)
        with patch(
            f"{_ADAPTER}.call_model", new_callable=AsyncMock, return_value="[]"
        ) as call:
            import asyncio

            asyncio.run(
                async_parse_raw(
                    "a diff",
                    model="deepseek-r1",
                    review_type="pr",
                    standing_rules=rules,
                )
            )
        system_prompt = call.call_args.args[0]
        for rule in rules.rules:
            assert rule.id in system_prompt

    def test_digest_is_stable_and_content_addressed(self) -> None:
        rules = _load(_RULES_YAML)
        assert rules.digest == _load(_RULES_YAML).digest
        assert len(rules.digest) == 64
        # Rule order in the file does not change what the rules are.
        reordered = (
            'schema_version: 1\nversion: "2026-10-09.1"\nrules:\n'
            f"  - id: {_OPTIONAL_ID}\n"
            "    mandatory: false\n"
            "    text: A change touches one concern.\n"
            f"  - id: {_MANDATORY_ID}\n"
            "    mandatory: true\n"
            "    text: Shipped configuration names no host, lane or endpoint of a "
            "private deployment.\n"
        )
        assert _load(reordered).digest == rules.digest
        # Any change to text, flag or version changes the digest.
        assert _load(_RULES_REWORDED_YAML).digest != rules.digest
        assert _load(_RULES_DEMOTED_YAML).digest != rules.digest
        assert _load(_RULES_YAML.replace("2026-10-09.1", "2026-10-09.9")).digest != (
            rules.digest
        )

    def test_standing_rules_rendered_and_digested_in_verdict_record(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rules_path = tmp_path / "rules.yaml"
        rules_path.write_text(_RULES_YAML, encoding="utf-8")
        argv = [
            "--file",
            str(_plan(tmp_path)),
            "--gated",
            "--rules-file",
            str(rules_path),
        ]
        code, out, llm = _run_cli(argv, capsys)
        assert code == 0
        verdict = json.loads(out)
        record = verdict["standing_rules"]
        expected = _load(_RULES_YAML)
        assert record["digest"] == expected.digest
        assert record["version"] == "2026-10-09.1"
        assert record["rule_ids"] == [_MANDATORY_ID, _OPTIONAL_ID]
        assert record["gated"] is True
        # Every model was handed the same rules.
        for call in llm.call_args_list:
            assert call.kwargs["standing_rules"].digest == expected.digest

    def test_ungated_review_without_rules_carries_no_record(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, out, llm = _run_cli(["--file", str(_plan(tmp_path))], capsys)
        assert code == 0
        assert json.loads(out)["standing_rules"] is None
        assert "standing_rules" not in llm.call_args_list[0].kwargs


# ---------------------------------------------------------------------------
# AC3: a recorded model response citing a rule id parses into a blocking
# finding bound to that rule.
# ---------------------------------------------------------------------------


def _recorded_response(rule_id: str | None, severity: str = "minor") -> str:
    return json.dumps(
        [
            {
                "category": "architecture",
                "severity": severity,
                "title": "Host name in shipped config",
                "description": "The diff adds a private host to packaged routing.",
                "evidence": "+  endpoint: http://host.example.invalid:8000",
                "proposed_fix": "Move the value to the deployment overlay.",
                "location": "config/routing.yaml:12",
                "standing_rule_id": rule_id,
            }
        ]
    )


class TestRuleCitedFindingBlocks:
    def test_rule_cited_finding_blocks_and_is_bound_to_the_rule(self) -> None:
        rules = _load(_RULES_YAML)
        findings = parse_raw(
            _recorded_response(_MANDATORY_ID),
            model="deepseek-r1",
            standing_rules=rules,
        )
        assert len(findings) == 1
        assert findings[0].standing_rule_id == _MANDATORY_ID
        # A violated mandatory rule is never below the blocking severity, whatever
        # severity the model attached.
        assert findings[0].severity is EnumFindingSeverity.ERROR

    def test_rule_cited_finding_blocks_in_the_quorum(self) -> None:
        rules = _load(_RULES_YAML)
        results = [
            _success(
                model,
                parse_raw(
                    _recorded_response(_MANDATORY_ID),
                    model=model,
                    standing_rules=rules,
                ),
            )
            for model in _two_models()
        ]
        policy = ModelReviewQuorumPolicy(min_agreeing_models=2, line_proximity_lines=7)
        summary = evaluate_quorum(
            ModelMultiReviewResult(
                models_attempted=list(_two_models()),
                models_succeeded=list(_two_models()),
                results=results,
            ),
            policy,
        )
        assert summary.verdict is EnumQuorumVerdict.BLOCKED
        assert summary.blocking_count == 1
        assert summary.blocking_findings[0].standing_rule_id == _MANDATORY_ID
        assert summary.blocking_findings[0].rule == f"standing:{_MANDATORY_ID}"

    def test_rule_cited_finding_blocks_through_the_model_call(self) -> None:
        """Recorded reply, real prompt path and parse path, no endpoint."""
        rules = _load(_RULES_YAML)
        import asyncio

        with patch(
            f"{_ADAPTER}.call_model",
            new_callable=AsyncMock,
            return_value=_recorded_response(_MANDATORY_ID),
        ):
            result = asyncio.run(
                async_parse_raw(
                    "a diff",
                    model="deepseek-r1",
                    review_type="pr",
                    standing_rules=rules,
                )
            )
        assert result.success
        assert result.findings[0].standing_rule_id == _MANDATORY_ID

    def test_optional_rule_binds_without_raising_severity(self) -> None:
        rules = _load(_RULES_YAML)
        findings = parse_raw(
            _recorded_response(_OPTIONAL_ID, severity="minor"),
            model="deepseek-r1",
            standing_rules=rules,
        )
        assert findings[0].standing_rule_id == _OPTIONAL_ID
        assert findings[0].severity is EnumFindingSeverity.INFO

    def test_unknown_rule_id_is_not_bound(self) -> None:
        """Positive control: a citation outside the supplied rules binds nothing."""
        rules = _load(_RULES_YAML)
        findings = parse_raw(
            _recorded_response("invented-rule"),
            model="deepseek-r1",
            standing_rules=rules,
        )
        assert findings[0].standing_rule_id is None
        assert findings[0].severity is EnumFindingSeverity.INFO

    def test_citation_without_supplied_rules_is_not_bound(self) -> None:
        findings = parse_raw(_recorded_response(_MANDATORY_ID), model="deepseek-r1")
        assert findings[0].standing_rule_id is None


# ---------------------------------------------------------------------------
# AC4: a schema-valid pull request that removes a mandatory rule fails the
# gated review, because the rules come from the base branch.
# ---------------------------------------------------------------------------


class TestPrCannotWeakenBaseRules:
    @pytest.mark.parametrize(
        ("pr_rules", "why"),
        [
            pytest.param(_RULES_WITHOUT_MANDATORY_YAML, "removed", id="rule-removed"),
            pytest.param(_RULES_DEMOTED_YAML, "demoted", id="rule-demoted"),
            pytest.param(_RULES_REWORDED_YAML, "reworded", id="rule-reworded"),
            pytest.param(None, "removed", id="file-deleted"),
        ],
    )
    def test_pr_cannot_weaken_base_rules(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        pr_rules: str | None,
        why: str,
    ) -> None:
        # The pull request's own file is schema-valid, so a reviewer that loaded
        # the file from the pull request's branch would accept it.
        if pr_rules is not None:
            assert handle(ModelStandingRulesRequest(rules_text=pr_rules)).ok
        repo = _repo_with_base_and_pr(
            tmp_path, base_rules=_RULES_YAML, pr_rules=pr_rules
        )
        code, out, llm = _run_cli(_gated_argv(_plan(tmp_path), repo), capsys)

        llm.assert_not_called()
        assert code == 0  # a verdict exists; the verdict is the failure
        verdict = json.loads(out)
        assert verdict["quorum"]["verdict"] == "blocked"
        blocking = verdict["quorum"]["blocking_findings"]
        assert [f["standing_rule_id"] for f in blocking] == [_MANDATORY_ID]
        assert why in blocking[0]["message"]
        assert verdict["standing_rules"]["violations"][0]["rule_id"] == _MANDATORY_ID
        # The record still names the BASE rules the review was bound to.
        assert verdict["standing_rules"]["digest"] == _load(_RULES_YAML).digest

    def test_pr_cannot_weaken_base_rules_review_uses_base_rules(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A pull request that only ADDS a rule is reviewed against the base rules."""
        repo = _repo_with_base_and_pr(
            tmp_path, base_rules=_RULES_YAML, pr_rules=_RULES_EXTENDED_YAML
        )
        code, out, llm = _run_cli(_gated_argv(_plan(tmp_path), repo), capsys)
        assert code == 0
        verdict = json.loads(out)
        assert verdict["quorum"]["verdict"] == "passed"
        assert verdict["standing_rules"]["digest"] == _load(_RULES_YAML).digest
        assert verdict["standing_rules"]["rule_ids"] == [_MANDATORY_ID, _OPTIONAL_ID]
        assert verdict["standing_rules"]["violations"] == []
        assert llm.call_count == 2
        for call in llm.call_args_list:
            assert "tests-accompany-code" not in {
                r.id for r in call.kwargs["standing_rules"].rules
            }

    def test_pr_cannot_weaken_base_rules_ignores_the_working_tree(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The checked-out file is the pull request's; the base ref is the authority."""
        repo = _repo_with_base_and_pr(
            tmp_path, base_rules=_RULES_YAML, pr_rules=_RULES_WITHOUT_MANDATORY_YAML
        )
        argv = [
            "--file",
            str(_plan(tmp_path)),
            "--gated",
            "--rules-file",
            "rules.yaml",
            "--rules-base-ref",
            "base",
            "--rules-repo-dir",
            str(repo),
        ]
        # No head ref named: head defaults to HEAD, the working tree's branch.
        code, out, llm = _run_cli(argv, capsys)
        llm.assert_not_called()
        assert code == 0
        assert json.loads(out)["quorum"]["verdict"] == "blocked"

    def test_pr_cannot_weaken_base_rules_unchanged_file_passes(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Positive control: the same invocation passes when the rules are untouched."""
        repo = _repo_with_base_and_pr(
            tmp_path, base_rules=_RULES_YAML, pr_rules=_RULES_YAML
        )
        code, out, llm = _run_cli(_gated_argv(_plan(tmp_path), repo), capsys)
        assert code == 0
        assert json.loads(out)["quorum"]["verdict"] == "passed"
        assert llm.call_count == 2

    def test_pr_cannot_weaken_base_rules_invalid_head_file_is_a_violation(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = _repo_with_base_and_pr(
            tmp_path, base_rules=_RULES_YAML, pr_rules="rules: ["
        )
        code, out, llm = _run_cli(_gated_argv(_plan(tmp_path), repo), capsys)
        llm.assert_not_called()
        assert code == 0
        verdict = json.loads(out)
        assert verdict["quorum"]["verdict"] == "blocked"
        assert verdict["standing_rules"]["candidate_errors"]


class TestStandingRulesHandler:
    """The pure handler behind the CLI."""

    def test_handler_returns_structured_errors_and_never_raises(self) -> None:
        for text in ("", "rules: [", None, "\x00"):
            result = handle(ModelStandingRulesRequest(rules_text=text))
            assert result.ok is False
            assert result.rules is None
            assert result.errors

    def test_handler_reports_every_weakening_of_a_mandatory_rule(self) -> None:
        for candidate, reason in (
            (_RULES_WITHOUT_MANDATORY_YAML, "removed"),
            (_RULES_DEMOTED_YAML, "demoted"),
            (_RULES_REWORDED_YAML, "reworded"),
            (None, "removed"),
        ):
            result = handle(
                ModelStandingRulesRequest(
                    rules_text=_RULES_YAML,
                    compare_candidate=True,
                    candidate_text=candidate,
                )
            )
            assert result.ok is False
            assert [(w.rule_id, w.reason) for w in result.weakened] == [
                (_MANDATORY_ID, reason)
            ]
            assert result.rules is not None

    def test_handler_accepts_a_candidate_that_only_adds_or_edits_optional_rules(
        self,
    ) -> None:
        edited = _RULES_YAML.replace("A change touches one concern.", "One concern.")
        for candidate in (_RULES_EXTENDED_YAML, edited):
            result = handle(
                ModelStandingRulesRequest(
                    rules_text=_RULES_YAML,
                    compare_candidate=True,
                    candidate_text=candidate,
                )
            )
            assert result.ok is True, result
            assert result.weakened == ()
