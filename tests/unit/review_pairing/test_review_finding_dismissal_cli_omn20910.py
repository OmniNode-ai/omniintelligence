# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""cli_review clears a blocking finding only on a dismissal a second voter confirms (OMN-20910).

Two stub voters agree on one error finding, so the quorum blocks. The pull
request's comments carry the author's dismissal of that finding for the head;
the judge call is stubbed. A confirming judge passes the gate, a rejecting one
keeps it blocked, and every dismissal is recorded in the result and posted.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from omniintelligence.review_pairing.adapters import adapter_ai_reviewer
from omniintelligence.review_pairing.cli_review import main
from omniintelligence.review_pairing.models import (
    EnumFindingSeverity,
    ModelReviewFindingObserved,
)
from omniintelligence.review_pairing.models_external_review import (
    ModelExternalReviewResult,
)
from omniintelligence.review_pairing.prompts.adversarial_reviewer import (
    PROMPT_VERSION,
)
from tests.unit.review_pairing.test_substitute_receipt import (
    _CLI,
    _HEAD,
    _PR,
    _REPO,
    _overlay,
)

_NOW = datetime(2026, 10, 19, 13, 0, tzinfo=UTC)
_EVIDENCE = (
    "The file parses: ast.parse accepts it at this head, and the test job "
    "imports it without error."
)


@pytest.fixture(autouse=True)
def _restore_adapter_registry() -> Iterator[None]:
    registry = dict(adapter_ai_reviewer.MODEL_REGISTRY)
    local_keys = adapter_ai_reviewer._LOCAL_MODEL_KEYS
    yield
    adapter_ai_reviewer.MODEL_REGISTRY.clear()
    adapter_ai_reviewer.MODEL_REGISTRY.update(registry)
    adapter_ai_reviewer._LOCAL_MODEL_KEYS = local_keys


def _finding(model: str) -> ModelReviewFindingObserved:
    return ModelReviewFindingObserved(
        finding_id=uuid4(),
        repo=_REPO,
        pr_id=_PR,
        rule_id=f"ai-reviewer:{model}:correctness",
        severity=EnumFindingSeverity.ERROR,
        file_path="src/main.py:12",
        line_start=1,
        tool_name="ai-reviewer",
        tool_version="1.0",
        normalized_message="src/main.py is not valid Python",
        raw_message="src/main.py is not valid Python",
        commit_sha_observed=_HEAD,
        observed_at=_NOW,
    )


def _parse(_content: str, model: str, **_: object) -> ModelExternalReviewResult:
    return ModelExternalReviewResult(
        model=model,
        prompt_version=PROMPT_VERSION,
        success=True,
        findings=[_finding(model)],
        result_count=1,
    )


def _run(
    tmp_path: Path,
    *,
    judge_reply: str,
    dismissal_head: str = _HEAD,
    evidence: str = _EVIDENCE,
    first_pass_keys: list[str] | None = None,
) -> tuple[int, dict[str, Any], list[list[str]]]:
    """Run the gate once; return (exit code, result document, gh argvs run)."""
    key = (first_pass_keys or [None])[0]
    comments = tmp_path / "comments.json"
    body = (
        f"/hostile-review dismiss {key}\nhead: {dismissal_head}\nevidence: {evidence}\n"
        if key
        else "no dismissal"
    )
    comments.write_text(
        json.dumps(
            [
                {
                    "id": 7,
                    "user": {"login": "pr-author"},
                    "author_association": "CONTRIBUTOR",
                    "body": body,
                }
            ]
        ),
        encoding="utf-8",
    )
    calls: list[list[str]] = []

    def _gh(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout="diff --git a/src/main.py b/src/main.py\n+x = 1\n",
            stderr="",
        )

    out = tmp_path / "result.json"
    with (
        patch(
            f"{_CLI}.probe_local_reachability",
            return_value={"first": True, "second": True},
        ),
        patch(f"{_CLI}.resolve_served_model_id", return_value="Model"),
        patch(f"{_CLI}.llm_async_parse_raw", AsyncMock(side_effect=_parse)),
        patch(f"{_CLI}.subprocess.run", side_effect=_gh),
        patch(f"{_CLI}.call_model", AsyncMock(return_value=judge_reply)) as judge,
    ):
        code = main(
            [
                "--pr",
                str(_PR),
                "--repo",
                _REPO,
                "--head-sha",
                _HEAD,
                "--voters-overlay",
                str(_overlay(tmp_path, policy=False)),
                "--output",
                str(out),
                "--dismissal-comments-file",
                str(comments),
                "--pr-author",
                "pr-author",
                "--dismissal-record-out",
                str(tmp_path / "dismissals.jsonl"),
            ]
        )
    document = json.loads(out.read_text(encoding="utf-8"))
    document["_judge_calls"] = judge.await_count
    return code, document, calls


def _blocking_key(tmp_path: Path) -> str:
    _, document, _ = _run(tmp_path, judge_reply="")
    assert document["quorum"]["verdict"] == "blocked"
    (finding,) = document["quorum"]["blocking_findings"]
    return str(finding["finding_key"])


@pytest.mark.unit
class TestCliDismissal:
    def test_confirmed_dismissal_passes_the_gate(self, tmp_path: Path) -> None:
        key = _blocking_key(tmp_path)
        code, document, calls = _run(
            tmp_path,
            judge_reply='{"verdict": "confirm", "reason": "it parses"}',
            first_pass_keys=[key],
        )
        assert code == 0
        quorum = document["quorum"]
        assert quorum["verdict"] == "passed"
        assert quorum["blocking_count"] == 0
        assert [f["finding_key"] for f in quorum["dismissed_findings"]] == [key]
        (record,) = document["dismissals"]
        assert record["outcome"] == "confirmed"
        assert record["judge_voter"] in {"first", "second"}
        assert record["source"] == "comment:7"
        # Written to the PR, and as the event payload.
        posted = [c for c in calls if c[:3] == ["gh", "pr", "comment"]]
        assert len(posted) == 1
        lines = (tmp_path / "dismissals.jsonl").read_text(encoding="utf-8").splitlines()
        assert json.loads(lines[0])["finding_key"] == key

    def test_rejected_dismissal_keeps_the_block(self, tmp_path: Path) -> None:
        key = _blocking_key(tmp_path)
        _, document, _ = _run(
            tmp_path,
            judge_reply='{"verdict": "reject", "reason": "the diff shows a syntax error"}',
            first_pass_keys=[key],
        )
        assert document["quorum"]["verdict"] == "blocked"
        assert document["dismissals"][0]["outcome"] == "rejected"

    def test_dismissal_without_evidence_is_refused_without_a_judge(
        self, tmp_path: Path
    ) -> None:
        key = _blocking_key(tmp_path)
        _, document, _ = _run(
            tmp_path,
            judge_reply='{"verdict": "confirm", "reason": "x"}',
            first_pass_keys=[key],
            evidence="",
        )
        assert document["quorum"]["verdict"] == "blocked"
        record = document["dismissals"][0]
        assert (record["outcome"], record["refusal"]) == ("refused", "no_evidence")
        assert document["_judge_calls"] == 0

    def test_dismissal_for_an_earlier_head_does_not_clear(self, tmp_path: Path) -> None:
        key = _blocking_key(tmp_path)
        _, document, _ = _run(
            tmp_path,
            judge_reply='{"verdict": "confirm", "reason": "x"}',
            first_pass_keys=[key],
            dismissal_head="c" * 40,
        )
        assert document["quorum"]["verdict"] == "blocked"
        assert document["dismissals"][0]["refusal"] == "stale_head"
        assert document["_judge_calls"] == 0
