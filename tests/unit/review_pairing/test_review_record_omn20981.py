# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""cli_review records each voter's review; the receipt reviewer records its findings (OMN-20981).

* AC1 a ``cli_review`` run with two voters and one substitute vote writes three
  records holding the voters' findings (stub transport, signed receipt fixture);
* AC2 the receipt reviewer's record holds exactly as many findings as the
  receipt counts, over a clean and two findings fixtures.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from omniintelligence.nodes.node_review_receipt_issue_compute.handlers.handler_issue_receipt import (
    handle as issue_receipt,
)
from omniintelligence.nodes.node_review_receipt_issue_compute.models import (
    ModelIssuedReceipt,
    ModelIssueReceiptRequest,
)
from omniintelligence.nodes.node_review_receipt_substitute_compute.handlers.handler_review_receipt_substitute import (
    receipt_signature,
    receipts_in_body,
    render_receipt_block,
)
from omniintelligence.nodes.node_review_record_compute.handlers.handler_review_record import (
    handle as record_review_run,
)
from omniintelligence.nodes.node_review_record_compute.models import (
    ModelReviewRecorded,
    ModelReviewRecordRequest,
)
from omniintelligence.review_pairing.adapters import adapter_ai_reviewer
from omniintelligence.review_pairing.cli_review import main
from omniintelligence.review_pairing.models import (
    EnumFindingSeverity,
    ModelReviewFindingObserved,
)
from omniintelligence.review_pairing.models_external_review import (
    ModelExternalReviewResult,
    ModelSubstituteVoteRecord,
)
from omniintelligence.review_pairing.prompts.adversarial_reviewer import (
    PROMPT_VERSION,
)
from tests.unit.review_pairing.test_substitute_receipt import (
    _CLI,
    _HEAD,
    _KEY,
    _KEY_ENV,
    _PR,
    _REPO,
    _TIMEOUT,
    _overlay,
    _receipt_review,
)

_NOW = datetime(2026, 10, 19, 7, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _restore_adapter_registry() -> Iterator[None]:
    registry = dict(adapter_ai_reviewer.MODEL_REGISTRY)
    local_keys = adapter_ai_reviewer._LOCAL_MODEL_KEYS
    yield
    adapter_ai_reviewer.MODEL_REGISTRY.clear()
    adapter_ai_reviewer.MODEL_REGISTRY.update(registry)
    adapter_ai_reviewer._LOCAL_MODEL_KEYS = local_keys


@pytest.fixture(autouse=True)
def _signing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_KEY_ENV, _KEY)


def _finding(n: int) -> ModelReviewFindingObserved:
    return ModelReviewFindingObserved(
        finding_id=uuid4(),
        repo=_REPO,
        pr_id=_PR,
        rule_id=f"ai-reviewer:first:correctness-{n}",
        severity=EnumFindingSeverity.ERROR,
        file_path="src/main.py",
        line_start=10 + n,
        tool_name="ai-reviewer",
        tool_version="1.0",
        normalized_message=f"Defect number {n}",
        raw_message=f"Defect number {n}",
        commit_sha_observed=_HEAD,
        observed_at=_NOW,
    )


def _voted(
    model: str, findings: list[ModelReviewFindingObserved]
) -> ModelExternalReviewResult:
    return ModelExternalReviewResult(
        model=model,
        prompt_version=PROMPT_VERSION,
        success=True,
        findings=findings,
        result_count=len(findings),
    )


def _lost(model: str) -> ModelExternalReviewResult:
    return ModelExternalReviewResult(
        model=model, prompt_version=PROMPT_VERSION, success=False, error=_TIMEOUT
    )


def _run_gate(tmp_path: Path, findings: list[ModelReviewFindingObserved]) -> Path:
    """One gate run: 'first' votes with ``findings``, 'second' times out and two
    signed clean receipts stand in for it. Returns the --record-out path."""

    def _parse(_content: str, model: str, **_: object) -> ModelExternalReviewResult:
        return _voted(model, findings) if model == "first" else _lost(model)

    record_out = tmp_path / "records.jsonl"
    with (
        patch(
            f"{_CLI}.probe_local_reachability",
            return_value={"first": True, "second": True},
        ),
        patch(f"{_CLI}.resolve_served_model_id", return_value="Model"),
        patch(f"{_CLI}.llm_async_parse_raw", AsyncMock(side_effect=_parse)),
        patch(f"{_CLI}.subprocess.run") as gh_diff,
        patch(
            f"{_CLI}._fetch_pr_reviews",
            return_value=[_receipt_review("codex"), _receipt_review("opus")],
        ),
    ):
        gh_diff.return_value.stdout = "diff --git a/x b/x\n+change\n"
        main(
            [
                "--pr",
                str(_PR),
                "--repo",
                _REPO,
                "--head-sha",
                _HEAD,
                "--voters-overlay",
                str(_overlay(tmp_path)),
                "--output",
                str(tmp_path / "result.json"),
                "--record-out",
                str(record_out),
            ]
        )
    return record_out


def _read(path: Path) -> list[ModelReviewRecorded]:
    return [
        ModelReviewRecorded.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


@pytest.mark.unit
class TestCliRecordOut:
    def test_two_voters_and_one_substitute_vote_write_three_records(
        self, tmp_path: Path
    ) -> None:
        """AC1: the voters' findings survive, and so does the substitute vote."""
        findings = [_finding(1), _finding(2)]
        records = _read(_run_gate(tmp_path, findings))

        assert [(r.arm, r.arm_kind, r.verdict) for r in records] == [
            ("first", "voter", "findings"),
            ("second", "voter", "failed"),
            ("codex+opus", "substitute", "clean"),
        ]
        first, second, substitute = records
        assert first.findings == tuple(findings)
        assert second.failure_reason is not None
        assert "TIMEOUT_ERROR" in second.failure_reason
        assert second.findings == ()
        assert substitute.substitute_for == "second"
        assert substitute.substitute_reviewer_ids == ("codex", "opus")
        assert substitute.head_sha == _HEAD
        assert {r.invocation_id for r in records} == {first.invocation_id}
        assert len({r.review_id for r in records}) == 3
        assert all(r.repo == _REPO and r.pr == _PR for r in records)

    def test_records_are_json_lines(self, tmp_path: Path) -> None:
        path = _run_gate(tmp_path, [_finding(1)])
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 3
        assert [json.loads(line)["schema_version"] for line in lines] == [
            "review_recorded.v1"
        ] * 3

    def test_empty_diff_writes_an_empty_record_file(self, tmp_path: Path) -> None:
        out = tmp_path / "records.jsonl"
        with patch(f"{_CLI}.subprocess.run") as gh_diff:
            gh_diff.return_value.stdout = "  \n"
            code = main(["--pr", str(_PR), "--repo", _REPO, "--record-out", str(out)])
        assert code == 0
        assert out.exists()
        assert out.read_text(encoding="utf-8") == ""


@pytest.mark.unit
class TestRecordHandler:
    def _request(self) -> ModelReviewRecordRequest:
        return ModelReviewRecordRequest(
            invocation_id=UUID(int=1),
            recorded_at=_NOW,
            review_type="pr",
            repo=_REPO,
            pr=_PR,
            head_sha=_HEAD,
            results=(_voted("a", [_finding(1)]), _voted("b", []), _lost("c")),
            substitute_votes=(
                ModelSubstituteVoteRecord(
                    voter_id="c",
                    failure="timed out",
                    replaced_error=_TIMEOUT,
                    reviewer_ids=("codex",),
                    head_sha=_HEAD,
                    review_authors=("review-bot",),
                ),
            ),
        )

    def test_one_record_per_voter_then_per_substitute(self) -> None:
        batch = record_review_run(self._request())
        assert [(r.arm, r.verdict) for r in batch.records] == [
            ("a", "findings"),
            ("b", "clean"),
            ("c", "failed"),
            ("codex", "clean"),
        ]

    def test_same_invocation_gives_the_same_ids(self) -> None:
        first = record_review_run(self._request())
        second = record_review_run(self._request())
        assert [r.review_id for r in first.records] == [
            r.review_id for r in second.records
        ]

    def test_plan_review_without_substitutes(self) -> None:
        batch = record_review_run(
            ModelReviewRecordRequest(
                invocation_id=uuid4(),
                recorded_at=_NOW,
                review_type="plan",
                results=(_voted("a", []),),
            )
        )
        (record,) = batch.records
        assert record.repo is None and record.pr is None
        assert record.verdict == "clean"

    @pytest.mark.parametrize(
        "update",
        [
            {"verdict": "clean", "execution_status": "failed"},
            {"verdict": "findings"},
            {"verdict": "failed", "execution_status": "completed"},
            {"recorded_at": datetime(2026, 10, 19, 7, 0)},
        ],
    )
    def test_inconsistent_record_is_refused(self, update: dict[str, object]) -> None:
        record = record_review_run(self._request()).records[1]
        with pytest.raises(ValidationError):
            ModelReviewRecorded.model_validate({**record.model_dump(), **update})


def _issue(findings: list[ModelReviewFindingObserved]) -> ModelIssuedReceipt:
    return issue_receipt(
        ModelIssueReceiptRequest(
            invocation_id=UUID(int=2),
            repo=_REPO,
            pr=_PR,
            head_sha=_HEAD,
            reviewer_id="codex",
            findings=tuple(findings),
            issued_at=_NOW,
            key=_KEY.encode(),
        )
    )


@pytest.mark.unit
class TestReceiptReviewerRecord:
    @pytest.mark.parametrize("count", [0, 1, 3])
    def test_record_holds_as_many_findings_as_the_receipt_counts(
        self, count: int
    ) -> None:
        """AC2: over a clean fixture and two findings fixtures."""
        findings = [_finding(n) for n in range(count)]
        issued = _issue(findings)

        assert issued.receipt.findings_count == count
        assert len(issued.record.findings) == issued.receipt.findings_count
        assert issued.record.findings == tuple(findings)
        assert issued.record.verdict == issued.receipt.verdict
        assert issued.record.arm_kind == "receipt_reviewer"

    def test_receipt_is_the_unchanged_signed_receipt(self) -> None:
        issued = _issue([_finding(1), _finding(2)])
        receipt = issued.receipt
        assert receipt.schema_version == "hostile_review_receipt.v1"
        assert receipt.verdict == "findings"
        assert receipt.signature == receipt_signature(receipt, _KEY.encode())
        ((parsed, error),) = receipts_in_body(render_receipt_block(receipt))
        assert error == "" and parsed == receipt

    def test_a_record_with_another_count_is_refused(self) -> None:
        """Positive control: the pairing check fires on a mismatch."""
        issued = _issue([_finding(1), _finding(2)])
        short = issued.record.model_copy(
            update={"findings": issued.record.findings[:1]}
        )
        with pytest.raises(ValidationError, match="the receipt counts 2"):
            ModelIssuedReceipt(receipt=issued.receipt, record=short)
