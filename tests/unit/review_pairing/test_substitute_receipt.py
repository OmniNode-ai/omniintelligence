# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""A timed-out voter's vote may come from a signed off-CI receipt (OMN-20947).

Operator RULING 2026-10-11T01:52:39Z: while a lab review voter times out, an
approved off-CI reviewer reviews the pull request and the gate reads the
result. These tests run the real gate (``cli_review.main`` with a voters
overlay) with the model calls and the GitHub review read faked, and hold:

* AC1 a timeout plus a valid clean receipt for the head passes (exit 0);
* AC2 a timeout without a receipt is still no verdict (exit 2);
* AC3 a receipt for another head commit is refused (exit 2);
* AC4 a receipt that records findings is refused (exit 2);
* AC5 an overlay with no substitute policy accepts nothing (exit 2);
plus the checks a receipt must pass one by one: signature, poster, age,
reviewer, dismissed review, failure kind, and that receipts never form a
quorum on their own.
"""

from __future__ import annotations

import json
import textwrap
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from omniintelligence.nodes.node_review_receipt_substitute_compute.handlers.handler_review_receipt_substitute import (
    handle,
    receipt_signature,
    receipts_in_body,
    render_receipt_block,
    sign_receipt,
)
from omniintelligence.nodes.node_review_receipt_substitute_compute.models import (
    ModelPullRequestReviewView,
    ModelSubstituteDecision,
    ModelSubstituteVoteRequest,
)
from omniintelligence.review_pairing.adapters import adapter_ai_reviewer
from omniintelligence.review_pairing.cli_review import main
from omniintelligence.review_pairing.model_registry_loader import load_review_voters
from omniintelligence.review_pairing.models_external_review import (
    ModelExternalReviewResult,
    ModelMultiReviewResult,
)
from omniintelligence.review_pairing.prompts.adversarial_reviewer import (
    PROMPT_VERSION,
)

_CLI = "omniintelligence.review_pairing.cli_review"
_REPO = "Example-org/example-repo"
_PR = 42
_HEAD = "a" * 40
_OTHER = "b" * 40
_KEY = "test-signing-key"
_KEY_ENV = "REVIEW_RECEIPT_TEST_KEY"
_TIMEOUT = (
    "[ONEX_CORE_092_TIMEOUT_ERROR] Request to ai-reviewer-second timed out "
    "after 300.0s (2 attempts)"
)

_VOTERS = textwrap.dedent(
    """\
    schema_version: "review_voters_overlay.v1"
    voters:
      - voter_id: first
        endpoint_url: "http://voter-a.example:8000/v1/chat/completions"
        required: true
        timeout_seconds: 120
      - voter_id: second
        endpoint_url: "http://voter-b.example:8130/v1/chat/completions"
        required: true
        timeout_seconds: 300
    """
)

_POLICY = textwrap.dedent(
    f"""\
    substitute_votes:
      reviewers:
        - reviewer_id: codex
          github_logins: ["review-bot"]
        - reviewer_id: opus
          github_logins: ["review-bot"]
      receipts_per_vote: {{per_vote}}
      receipt_max_age_seconds: 3600
      signing_key_env: {_KEY_ENV}
    """
)


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


def _overlay(tmp_path: Path, *, policy: bool = True, per_vote: int = 2) -> Path:
    text = _VOTERS + (_POLICY.format(per_vote=per_vote) if policy else "")
    path = tmp_path / "voters.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def _receipt_review(
    reviewer: str,
    *,
    head: str = _HEAD,
    commit: str | None = None,
    findings: int = 0,
    author: str = "review-bot",
    key: str = _KEY,
    issued_at: datetime | None = None,
    state: str = "COMMENTED",
    pr: int = _PR,
) -> ModelPullRequestReviewView:
    receipt = sign_receipt(
        repo=_REPO,
        pr=pr,
        head_sha=head,
        reviewer_id=reviewer,
        findings_count=findings,
        issued_at=issued_at or datetime.now(tz=UTC) - timedelta(minutes=5),
        key=key.encode(),
    )
    return ModelPullRequestReviewView(
        author_login=author,
        commit_id=commit if commit is not None else head,
        state=state,
        body=f"Off-CI review.\n\n{render_receipt_block(receipt)}\n",
    )


def _ok(model: str) -> ModelExternalReviewResult:
    return ModelExternalReviewResult(
        model=model, prompt_version=PROMPT_VERSION, success=True, findings=[]
    )


def _fail(model: str, error: str = _TIMEOUT) -> ModelExternalReviewResult:
    return ModelExternalReviewResult(
        model=model, prompt_version=PROMPT_VERSION, success=False, error=error
    )


def _run_gate(
    tmp_path: Path,
    reviews: list[ModelPullRequestReviewView],
    *,
    overlay: Path | None = None,
    second_error: str = _TIMEOUT,
    head: str = _HEAD,
) -> tuple[int, dict[str, object], str]:
    """One gate run over a PR: 'first' votes clean, 'second' fails."""

    def _parse(_content: str, model: str, **_: object) -> ModelExternalReviewResult:
        return _ok(model) if model == "first" else _fail(model, second_error)

    out = tmp_path / "result.json"
    with (
        patch(
            f"{_CLI}.probe_local_reachability",
            return_value={"first": True, "second": True},
        ),
        patch(f"{_CLI}.resolve_served_model_id", return_value="Model"),
        patch(f"{_CLI}.llm_async_parse_raw", AsyncMock(side_effect=_parse)),
        patch(f"{_CLI}.subprocess.run") as gh_diff,
        patch(f"{_CLI}._fetch_pr_reviews", return_value=reviews) as fetch,
    ):
        gh_diff.return_value.stdout = "diff --git a/x b/x\n+change\n"
        code = main(
            [
                "--pr",
                str(_PR),
                "--repo",
                _REPO,
                "--head-sha",
                head,
                "--voters-overlay",
                str(overlay or _overlay(tmp_path)),
                "--output",
                str(out),
            ]
        )
    document = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    calls = f"fetch_calls={fetch.call_count}"
    return code, document, calls


@pytest.mark.unit
class TestGate:
    def test_timeout_with_valid_receipt_passes(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """AC1: the substituted vote completes the quorum; the verdict passes."""
        code, document, _ = _run_gate(
            tmp_path, [_receipt_review("codex"), _receipt_review("opus")]
        )

        assert code == 0
        quorum = document["quorum"]
        assert isinstance(quorum, dict)
        assert quorum["verdict"] == "passed"
        assert quorum["distinct_reviewers_succeeded"][-1] == "receipt:codex+opus"
        records = document["substitute_votes"]
        assert isinstance(records, list)
        (record,) = records
        assert record["voter_id"] == "second"
        assert record["head_sha"] == _HEAD
        assert "TIMEOUT_ERROR" in record["replaced_error"]
        assert "Substitute vote: voter 'second' timed out" in capsys.readouterr().err

    def test_timeout_without_receipt_fails_as_today(self, tmp_path: Path) -> None:
        """AC2: no receipt, no vote: exit 2, no substitute recorded."""
        code, document, _ = _run_gate(tmp_path, [])

        assert code == 2
        assert document["substitute_votes"] == []
        assert document["models_failed"] == ["second"]

    def test_receipt_for_other_sha_fails(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """AC3: receipts signed for another head never count for this one."""
        reviews = [
            _receipt_review("codex", head=_OTHER),
            _receipt_review("opus", head=_OTHER),
        ]
        code, document, _ = _run_gate(tmp_path, reviews)

        assert code == 2
        assert document["substitute_votes"] == []
        assert "not head aaaaaaaaaaaa" in capsys.readouterr().err

    def test_receipt_on_other_review_commit_fails(self, tmp_path: Path) -> None:
        """A receipt for this sha on a review of another commit is refused too."""
        reviews = [
            _receipt_review("codex", commit=_OTHER),
            _receipt_review("opus", commit=_OTHER),
        ]
        assert _run_gate(tmp_path, reviews)[0] == 2

    def test_findings_receipt_fails(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """AC4: one reviewer with findings refuses substitution outright."""
        reviews = [_receipt_review("codex"), _receipt_review("opus", findings=2)]
        code, document, _ = _run_gate(tmp_path, reviews)

        assert code == 2
        assert document["substitute_votes"] == []
        assert "recorded 2 finding(s)" in capsys.readouterr().err

    def test_no_policy_refuses_every_receipt(self, tmp_path: Path) -> None:
        """AC5: an overlay with no substitute_votes behaves exactly as before."""
        overlay = _overlay(tmp_path, policy=False)
        code, document, calls = _run_gate(
            tmp_path,
            [_receipt_review("codex"), _receipt_review("opus")],
            overlay=overlay,
        )

        assert code == 2
        assert document["substitute_votes"] == []
        assert calls == "fetch_calls=0"

    def test_unreachable_or_unparseable_voter_is_not_substituted(
        self, tmp_path: Path
    ) -> None:
        """Only a timeout is substituted; any other failure stays a failure."""
        code, _, calls = _run_gate(
            tmp_path,
            [_receipt_review("codex"), _receipt_review("opus")],
            second_error="unparseable reply: no review JSON in 2 attempt(s)",
        )
        assert code == 2
        assert calls == "fetch_calls=0"

    def test_one_receipt_is_short_of_two_per_vote(self, tmp_path: Path) -> None:
        assert _run_gate(tmp_path, [_receipt_review("codex")])[0] == 2

    def test_one_receipt_suffices_when_the_overlay_says_one(
        self, tmp_path: Path
    ) -> None:
        overlay = _overlay(tmp_path, per_vote=1)
        code, _, _ = _run_gate(tmp_path, [_receipt_review("opus")], overlay=overlay)
        assert code == 0

    def test_missing_signing_key_accepts_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(_KEY_ENV)
        reviews = [_receipt_review("codex"), _receipt_review("opus")]
        assert _run_gate(tmp_path, reviews)[0] == 2


def _timeout_result() -> ModelMultiReviewResult:
    return ModelMultiReviewResult(
        models_attempted=["first", "second"],
        models_succeeded=["first"],
        models_failed=["second"],
        results=[_ok("first"), _fail("second")],
    )


def _decide(
    tmp_path: Path,
    reviews: list[ModelPullRequestReviewView],
    *,
    result: ModelMultiReviewResult | None = None,
    per_vote: int = 2,
) -> ModelSubstituteDecision:
    roster = load_review_voters(_overlay(tmp_path, per_vote=per_vote))
    return handle(
        ModelSubstituteVoteRequest(
            result=result or _timeout_result(),
            policy=roster.substitute_votes,
            reviews=tuple(reviews),
            repo=_REPO,
            pr=_PR,
            head_sha=_HEAD,
            key=_KEY.encode(),
            now=datetime.now(tz=UTC),
        )
    )


@pytest.mark.unit
class TestReceiptChecks:
    @pytest.mark.parametrize(
        ("review", "reason"),
        [
            (_receipt_review("opus", key="another-key"), "signature does not verify"),
            (_receipt_review("opus", author="someone-else"), "not an account"),
            (
                _receipt_review(
                    "opus", issued_at=datetime.now(tz=UTC) - timedelta(hours=2)
                ),
                "over the 3600s limit",
            ),
            (
                _receipt_review(
                    "opus", issued_at=datetime.now(tz=UTC) + timedelta(hours=1)
                ),
                "dated in the future",
            ),
            (_receipt_review("gemini"), "not an approved substitute"),
            (_receipt_review("opus", state="DISMISSED"), "dismissed review"),
            (_receipt_review("opus", pr=7), "not Example-org/example-repo#42"),
        ],
    )
    def test_invalid_receipt_is_refused_with_its_reason(
        self, tmp_path: Path, review: ModelPullRequestReviewView, reason: str
    ) -> None:
        decision = _decide(tmp_path, [_receipt_review("codex"), review])
        assert decision.records == ()
        assert any(reason in refusal for refusal in decision.refusals)

    def test_tampered_receipt_fails_its_signature(self, tmp_path: Path) -> None:
        review = _receipt_review("opus", findings=3)
        tampered = review.model_copy(
            update={
                "body": review.body.replace('"findings"', '"clean"').replace(
                    '"findings_count":3', '"findings_count":0'
                )
            }
        )
        decision = _decide(tmp_path, [_receipt_review("codex"), tampered])
        assert decision.records == ()
        assert any("signature does not verify" in r for r in decision.refusals)

    def test_receipts_never_form_a_quorum_alone(self, tmp_path: Path) -> None:
        both_timed_out = ModelMultiReviewResult(
            models_attempted=["first", "second"],
            models_failed=["first", "second"],
            results=[_fail("first"), _fail("second")],
        )
        decision = _decide(
            tmp_path,
            [_receipt_review("codex"), _receipt_review("opus")],
            result=both_timed_out,
            per_vote=1,
        )
        assert decision.records == ()
        assert any("never form a quorum alone" in r for r in decision.refusals)

    def test_a_reviewer_stands_in_for_one_voter_only(self, tmp_path: Path) -> None:
        three = ModelMultiReviewResult(
            models_attempted=["first", "second", "third"],
            models_succeeded=["first"],
            models_failed=["second", "third"],
            results=[_ok("first"), _fail("second"), _fail("third")],
        )
        decision = _decide(
            tmp_path, [_receipt_review("codex")], result=three, per_vote=1
        )
        assert [r.voter_id for r in decision.records] == ["second"]
        assert any("'third' timed out" in r for r in decision.refusals)

    def test_malformed_block_is_reported_not_trusted(self, tmp_path: Path) -> None:
        junk = ModelPullRequestReviewView(
            author_login="review-bot",
            commit_id=_HEAD,
            state="COMMENTED",
            body='```onex-review-receipt\n{"verdict": "clean"}\n```',
        )
        decision = _decide(tmp_path, [junk], per_vote=1)
        assert decision.records == ()
        assert any("malformed receipt" in r for r in decision.refusals)


@pytest.mark.unit
class TestOverlayPolicy:
    def test_policy_round_trips_through_the_node(self, tmp_path: Path) -> None:
        roster = load_review_voters(_overlay(tmp_path))
        assert roster.ok
        policy = roster.substitute_votes
        assert policy is not None
        assert [r.reviewer_id for r in policy.reviewers] == ["codex", "opus"]
        assert policy.receipts_per_vote == 2

    def test_absent_policy_is_none(self, tmp_path: Path) -> None:
        roster = load_review_voters(_overlay(tmp_path, policy=False))
        assert roster.ok
        assert roster.substitute_votes is None

    def test_reviewer_named_like_a_voter_is_refused(self, tmp_path: Path) -> None:
        path = _overlay(tmp_path)
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "reviewer_id: codex", "reviewer_id: first"
            ),
            encoding="utf-8",
        )
        roster = load_review_voters(path)
        assert not roster.ok
        assert "also voter ids" in roster.error

    def test_more_receipts_per_vote_than_reviewers_is_refused(
        self, tmp_path: Path
    ) -> None:
        roster = load_review_voters(_overlay(tmp_path, per_vote=3))
        assert not roster.ok
        assert "exceeds" in roster.error

    def test_a_rendered_receipt_parses_and_verifies(self) -> None:
        receipt = sign_receipt(
            repo=_REPO,
            pr=_PR,
            head_sha=_HEAD,
            reviewer_id="codex",
            findings_count=0,
            issued_at=datetime.now(tz=UTC),
            key=_KEY.encode(),
        )
        ((parsed, error),) = receipts_in_body(render_receipt_block(receipt))
        assert error == ""
        assert parsed == receipt
        assert parsed.signature == receipt_signature(parsed, _KEY.encode())
