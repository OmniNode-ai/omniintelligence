# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""A finding whose own text says there is no defect is dropped and recorded (OMN-20422).

Both Hostile Reviewer voters can emit a finding that retracts itself: "No finding
here ... No defect", "Retracting this finding", a proposed fix of "No change
needed". At critical severity such a finding is in the blocking tier, so two of
them in the same place blocked omniclaude#2629, a pin bump with no defect.
Measured on 10 merged PRs (149 findings, both voters, prompt 1.2.0): 12 findings
negated themselves, 3 of them critical.

The adapter drops such a finding after parsing and records it on the result
with the reason, so the drop is visible in the emitted JSON and on stderr. A
finding that names a real defect is kept and still blocks. Every reply below is
a verbatim reply captured from the two lab voters (fixture file beside this one).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from omniintelligence.review_pairing.adapters import adapter_ai_reviewer
from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
    self_negation_reason,
    split_self_negating,
    try_parse_review_response,
)
from omniintelligence.review_pairing.models_external_review import (
    EnumQuorumVerdict,
    ModelReviewQuorumPolicy,
)
from omniintelligence.review_pairing.quorum import evaluate_quorum

_FIXTURES = json.loads(
    (Path(__file__).parent / "fixtures" / "reviewer_replies_omn20422.json").read_text(
        encoding="utf-8"
    )
)


def _reply(name: str) -> str:
    return str(_FIXTURES[name]["raw"])


def _findings(name: str) -> list[dict[str, Any]]:
    parsed = try_parse_review_response(_reply(name))
    assert parsed is not None, name
    return parsed


def _by_title(name: str, prefix: str) -> dict[str, Any]:
    matches = [f for f in _findings(name) if str(f["title"]).startswith(prefix)]
    assert len(matches) == 1, (name, prefix, [f["title"] for f in _findings(name)])
    return matches[0]


@pytest.mark.unit
class TestSelfNegationReason:
    def test_the_pin_bump_finding_that_says_no_finding_here_is_named(self) -> None:
        finding = _by_title(
            "omniclaude_2629_pin_bump_qwen3_review", "Unpinned git dependency"
        )
        assert finding["severity"] == "critical"
        reason = self_negation_reason(finding)
        assert reason is not None
        assert "no finding here" in reason.lower()

    def test_a_retracted_finding_is_named(self) -> None:
        finding = _by_title("omniclaude_2629_qwen3_review", "Test stub JSON")
        reason = self_negation_reason(finding)
        assert reason is not None
        assert "retracting this finding" in reason.lower()

    @pytest.mark.parametrize(
        "prefix",
        [
            "Race condition in _fold_credential_events",
            "Pending events file is written",
            "The SQLite adapter's _ensure_columns",
            "The fingerprint is a prefix of sha256",
        ],
    )
    def test_findings_whose_fix_is_no_change_are_named(self, prefix: str) -> None:
        finding = _by_title("omnimarket_3510_qwen3_review", prefix)
        assert self_negation_reason(finding) is not None

    @pytest.mark.parametrize(
        ("name", "prefix"),
        [
            ("omniclaude_2628_qwen3_review", "SystemExit on ImportError"),
            # The planner's half of the blocking cluster on omniclaude#2628.
            ("omniclaude_2628_local_studio_planner", "Hardcoded credential patterns"),
            # Says "which is correct" about one assertion, then names a real gap.
            ("omnimarket_3510_qwen3_review", "The _whole_event function"),
        ],
    )
    def test_a_finding_that_names_a_defect_is_not_named(
        self, name: str, prefix: str
    ) -> None:
        assert self_negation_reason(_by_title(name, prefix)) is None

    def test_a_pin_bump_finding_that_claims_a_risk_is_not_dropped_by_text(
        self,
    ) -> None:
        """The run-1 variant asserts a supply-chain risk; the text rule must not
        guess at it. The prompt's pinning rule is what answers that variant."""
        for name in (
            "omniclaude_2629_pin_bump_run1_qwen3_review",
            "omniclaude_2629_pin_bump_run1_local_studio_planner",
        ):
            for finding in _findings(name):
                if "pyproject" in str(finding.get("location")):
                    assert self_negation_reason(finding) is None, finding["title"]

    @pytest.mark.parametrize(
        "fix",
        [
            "No change needed in the handler; add a regression test instead.",
            "No action required unless profiling shows a bottleneck.",
        ],
    )
    def test_a_fix_that_goes_on_to_ask_for_a_change_is_not_named(
        self, fix: str
    ) -> None:
        finding = {
            "title": "Missing test",
            "description": "The new branch has no test.",
            "evidence": "x",
            "proposed_fix": fix,
        }
        assert self_negation_reason(finding) is None

    def test_quoted_evidence_is_not_read(self) -> None:
        """Evidence is text from the diff; a diff may contain the phrase."""
        finding = {
            "title": "Fixture asserts the wrong verdict",
            "description": "The fixture expects passed for a blocking stub.",
            "evidence": '"description": "No finding here"',
            "proposed_fix": "Expect blocked.",
        }
        assert self_negation_reason(finding) is None


@pytest.mark.unit
class TestSplitSelfNegating:
    def test_split_keeps_order_and_records_each_drop(self) -> None:
        parsed = _findings("omnimarket_3510_qwen3_review")
        kept, dropped = split_self_negating(parsed)
        assert len(kept) + len(dropped) == len(parsed)
        assert len(dropped) == 4
        assert [f for f in parsed if f in kept] == kept
        for record in dropped:
            assert record.reason
            assert record.title
            assert record.severity in {"critical", "major", "minor", "nit"}


@pytest.mark.unit
class TestAsyncParseRawRecordsDrops:
    @pytest.mark.asyncio
    async def test_dropped_finding_is_recorded_not_counted(self) -> None:
        raw = _reply("omniclaude_2629_pin_bump_qwen3_review")
        total = len(_findings("omniclaude_2629_pin_bump_qwen3_review"))
        with patch.object(adapter_ai_reviewer, "call_model", return_value=raw):
            result = await adapter_ai_reviewer.async_parse_raw(
                "diff", model="qwen3-review", review_type="pr"
            )

        assert result.success is True
        assert result.result_count == total - 1
        assert len(result.findings) == total - 1
        assert [d.title for d in result.dropped_findings] == [
            "Unpinned git dependency in uv.lock"
        ]
        assert result.dropped_findings[0].severity == "critical"
        assert all("Unpinned" not in f.raw_message for f in result.findings)
        assert "dropped_findings" in result.model_dump_json()


@pytest.mark.unit
class TestQuorum:
    @pytest.mark.asyncio
    async def test_two_self_negating_votes_no_longer_block(self) -> None:
        """The omniclaude#2629 shape: both voters raise the same critical
        finding and both say it is not one."""
        from omniintelligence.review_pairing.cli_review import run_review

        negating = _by_title(
            "omniclaude_2629_pin_bump_qwen3_review", "Unpinned git dependency"
        )
        reply = json.dumps([negating])
        with patch.object(adapter_ai_reviewer, "call_model", return_value=reply):
            multi = await run_review(
                "diff", ["qwen3-review", "local-studio-planner"], review_type="pr"
            )

        summary = evaluate_quorum(multi, ModelReviewQuorumPolicy())
        assert summary.verdict is EnumQuorumVerdict.PASSED
        assert all(len(r.dropped_findings) == 1 for r in multi.results)

    @pytest.mark.asyncio
    async def test_a_real_defect_both_voters_raise_still_blocks(self) -> None:
        """Positive control: omniclaude#2628's agreed SystemExit finding."""
        from omniintelligence.review_pairing.cli_review import run_review

        replies = {
            "qwen3-review": _reply("omniclaude_2628_qwen3_review"),
            "local-studio-planner": _reply("omniclaude_2628_local_studio_planner"),
        }

        async def _call(
            system_prompt: str, user_prompt: str, model_key: str = ""
        ) -> str:
            return replies[model_key]

        with patch.object(adapter_ai_reviewer, "call_model", side_effect=_call):
            multi = await run_review(
                "diff", ["qwen3-review", "local-studio-planner"], review_type="pr"
            )

        summary = evaluate_quorum(multi, ModelReviewQuorumPolicy())
        assert summary.verdict is EnumQuorumVerdict.BLOCKED
        assert any(
            "SystemExit on ImportError" in b.message for b in summary.blocking_findings
        )


@pytest.mark.unit
class TestCliReportsDrops:
    def test_stderr_names_each_dropped_finding(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from omniintelligence.review_pairing.cli_review import main

        plan = tmp_path / "diff.txt"
        plan.write_text("diff", encoding="utf-8")
        raw = _reply("omniclaude_2629_pin_bump_qwen3_review")
        with (
            patch(
                "omniintelligence.review_pairing.cli_review.select_models_with_fallback",
                return_value=(["qwen3-review", "local-studio-planner"], []),
            ),
            patch.object(adapter_ai_reviewer, "call_model", return_value=raw),
        ):
            code = main(
                [
                    "--file",
                    str(plan),
                    "--model",
                    "qwen3-review",
                    "--model",
                    "local-studio-planner",
                    "--output",
                    str(tmp_path / "out.json"),
                ]
            )

        err = capsys.readouterr().err
        assert code == 0
        assert "Dropped (own text states no defect): 2" in err
        assert (
            "[dropped] qwen3-review critical Unpinned git dependency in uv.lock" in err
        )
        doc = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
        assert doc["total_dropped"] == 2
