# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""A lost voter's vote may come from a signed off-CI receipt (OMN-20947).

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
quorum on their own. A voter whose endpoint was unavailable (HTTP 502/503/504,
a refused or failed connection, a failed reachability probe) is lost to the
lab exactly like one that timed out, and takes the same receipts under the
same rules; the error strings come from the real transport error classes.
"""

from __future__ import annotations

import http.server
import json
import socket
import textwrap
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from omnibase_infra.enums import EnumInfraTransportType
from omnibase_infra.errors import (
    InfraConnectionError,
    InfraRequestRejectedError,
    InfraUnavailableError,
)
from omnibase_infra.models.errors import ModelInfraErrorContext

from omniintelligence.nodes.node_review_receipt_substitute_compute.handlers.handler_review_receipt_substitute import (
    FAILURE_TIMED_OUT,
    FAILURE_UNAVAILABLE,
    handle,
    receipt_signature,
    receipts_in_body,
    render_receipt_block,
    sign_receipt,
    substitutable_failure,
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
from omniintelligence.review_pairing.served_model_resolver import (
    ServedModelResolutionError,
    resolve_served_model_id,
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

_CTX = ModelInfraErrorContext(
    transport_type=EnumInfraTransportType.HTTP,
    operation="chat_completion",
    target_name="ai-reviewer-second",
)


def _transport_error(exc: Exception) -> str:
    """The error text the review adapter records for a transport exception."""
    body = getattr(exc, "response_body", None)
    return f"{exc} :: response_body={body}" if body else str(exc)


def _server_error(status: int, body: str = "Loading model") -> str:
    return _transport_error(
        InfraUnavailableError(
            f"Server error ({status}) from ai-reviewer-second",
            context=_CTX,
            status_code=status,
            response_body=body,
        )
    )


_UNAVAILABLE_503 = _server_error(503)
_CONNECTION_REFUSED = _transport_error(
    InfraConnectionError(
        "Connection to ai-reviewer-second failed after 3 attempts: "
        "[Errno 61] Connection refused",
        context=_CTX,
    )
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
    second_reachable: bool = True,
) -> tuple[int, dict[str, object], str]:
    """One gate run over a PR: 'first' votes clean, 'second' fails.

    With ``second_reachable=False`` the reachability probe drops 'second', so
    it is never called; the calls string then also says whether 'first' was.
    """

    def _parse(_content: str, model: str, **_: object) -> ModelExternalReviewResult:
        return _ok(model) if model == "first" else _fail(model, second_error)

    out = tmp_path / "result.json"
    llm = AsyncMock(side_effect=_parse)
    with (
        patch(
            f"{_CLI}.probe_local_reachability",
            return_value={"first": True, "second": second_reachable},
        ),
        patch(f"{_CLI}.resolve_served_model_id", return_value="Model"),
        patch(f"{_CLI}.llm_async_parse_raw", llm),
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
    if not second_reachable:
        calls += f" voter_calls={llm.call_count}"
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
        assert record["failure"] == FAILURE_TIMED_OUT
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

    @pytest.mark.parametrize(
        "error",
        [
            pytest.param(
                "unparseable reply: no review JSON in 2 attempt(s)", id="unparseable"
            ),
            pytest.param(_server_error(500), id="http-500"),
            pytest.param(
                _transport_error(
                    InfraRequestRejectedError(
                        "Request rejected (400) by ai-reviewer-second",
                        context=_CTX,
                        status_code=400,
                        response_body="input is longer than max_model_len",
                    )
                ),
                id="http-400",
            ),
            pytest.param(
                _server_error(500, body="Server error (503) from ai-reviewer-second"),
                id="500-whose-body-quotes-a-503",
            ),
            pytest.param(
                "unparseable reply: [ONEX_CORE_205_SERVICE_UNAVAILABLE] Server "
                "error (503) from ai-reviewer-second",
                id="503-text-not-at-the-start",
            ),
        ],
    )
    def test_a_voter_that_answered_and_failed_is_not_substituted(
        self, tmp_path: Path, error: str
    ) -> None:
        """Only a voter lost to the lab is substituted; its own failure stays."""
        code, _, calls = _run_gate(
            tmp_path,
            [_receipt_review("codex"), _receipt_review("opus")],
            second_error=error,
        )
        assert code == 2
        assert calls == "fetch_calls=0"

    @pytest.mark.parametrize(
        "error",
        [
            pytest.param(_UNAVAILABLE_503, id="http-503"),
            pytest.param(_server_error(502), id="http-502"),
            pytest.param(_server_error(504), id="http-504"),
            pytest.param(_CONNECTION_REFUSED, id="connection-refused"),
        ],
    )
    def test_unavailable_voter_with_valid_receipts_passes(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], error: str
    ) -> None:
        """An unavailable voter takes the same receipts a timed-out one does."""
        code, document, _ = _run_gate(
            tmp_path,
            [_receipt_review("codex"), _receipt_review("opus")],
            second_error=error,
        )

        assert code == 0
        quorum = document["quorum"]
        assert isinstance(quorum, dict)
        assert quorum["verdict"] == "passed"
        records = document["substitute_votes"]
        assert isinstance(records, list)
        (record,) = records
        assert record["voter_id"] == "second"
        assert record["failure"] == FAILURE_UNAVAILABLE
        assert record["replaced_error"] == error
        assert (
            "Substitute vote: voter 'second' was unavailable" in capsys.readouterr().err
        )

    def test_unavailable_voter_without_receipt_fails(self, tmp_path: Path) -> None:
        code, document, calls = _run_gate(tmp_path, [], second_error=_UNAVAILABLE_503)
        assert code == 2
        assert document["substitute_votes"] == []
        assert calls == "fetch_calls=1"

    @pytest.mark.parametrize(
        "reviews",
        [
            pytest.param(
                [
                    _receipt_review("codex", head=_OTHER),
                    _receipt_review("opus", head=_OTHER),
                ],
                id="other-head",
            ),
            pytest.param(
                [_receipt_review("codex"), _receipt_review("opus", findings=1)],
                id="findings",
            ),
            pytest.param([_receipt_review("codex")], id="one-short"),
        ],
    )
    def test_unavailable_voter_takes_the_same_receipt_rules(
        self, tmp_path: Path, reviews: list[ModelPullRequestReviewView]
    ) -> None:
        code, document, _ = _run_gate(tmp_path, reviews, second_error=_UNAVAILABLE_503)
        assert code == 2
        assert document["substitute_votes"] == []

    def test_unavailable_voter_with_no_policy_accepts_nothing(
        self, tmp_path: Path
    ) -> None:
        code, _, calls = _run_gate(
            tmp_path,
            [_receipt_review("codex"), _receipt_review("opus")],
            overlay=_overlay(tmp_path, policy=False),
            second_error=_CONNECTION_REFUSED,
        )
        assert code == 2
        assert calls == "fetch_calls=0"

    def test_probe_unreachable_voter_with_receipts_passes(self, tmp_path: Path) -> None:
        """With a policy, the reachable voter still votes and receipts stand in."""
        code, document, calls = _run_gate(
            tmp_path,
            [_receipt_review("codex"), _receipt_review("opus")],
            second_reachable=False,
        )
        assert code == 0
        assert calls == "fetch_calls=1 voter_calls=1"
        records = document["substitute_votes"]
        assert isinstance(records, list)
        (record,) = records
        assert record["voter_id"] == "second"
        assert record["failure"] == FAILURE_UNAVAILABLE
        assert str(record["replaced_error"]).startswith("unreachable:")

    def test_probe_unreachable_voter_without_policy_calls_no_voter(
        self, tmp_path: Path
    ) -> None:
        """OMN-20910 unchanged: no policy, a required voter down, nobody is called."""
        code, document, calls = _run_gate(
            tmp_path,
            [_receipt_review("codex"), _receipt_review("opus")],
            overlay=_overlay(tmp_path, policy=False),
            second_reachable=False,
        )
        assert code == 2
        assert calls == "fetch_calls=0 voter_calls=0"
        assert document["substitute_votes"] == []

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

    @pytest.mark.parametrize(
        "first_error", [_TIMEOUT, _UNAVAILABLE_503, _CONNECTION_REFUSED]
    )
    def test_receipts_never_form_a_quorum_alone(
        self, tmp_path: Path, first_error: str
    ) -> None:
        both_timed_out = ModelMultiReviewResult(
            models_attempted=["first", "second"],
            models_failed=["first", "second"],
            results=[_fail("first", first_error), _fail("second")],
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

    def test_lost_voters_are_substituted_in_order_with_their_kind(
        self, tmp_path: Path
    ) -> None:
        three = ModelMultiReviewResult(
            models_attempted=["first", "second", "third"],
            models_succeeded=["first"],
            models_failed=["second", "third"],
            results=[
                _ok("first"),
                _fail("second", _UNAVAILABLE_503),
                _fail("third"),
            ],
        )
        decision = _decide(
            tmp_path,
            [_receipt_review("codex"), _receipt_review("opus")],
            result=three,
            per_vote=1,
        )
        assert [(r.voter_id, r.failure) for r in decision.records] == [
            ("second", FAILURE_UNAVAILABLE),
            ("third", FAILURE_TIMED_OUT),
        ]

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


@pytest.mark.unit
class TestFailureKind:
    @pytest.mark.parametrize(
        ("exc", "kind"),
        [
            pytest.param(
                InfraUnavailableError(
                    "Server error (503) from ai-reviewer-second",
                    context=_CTX,
                    status_code=503,
                    response_body="Loading model",
                ),
                FAILURE_UNAVAILABLE,
                id="503",
            ),
            pytest.param(
                InfraConnectionError(
                    "Connection to ai-reviewer-second failed after 3 attempts: "
                    "All connection attempts failed",
                    context=_CTX,
                ),
                FAILURE_UNAVAILABLE,
                id="connection",
            ),
            pytest.param(
                InfraUnavailableError(
                    "Server error (500) from ai-reviewer-second",
                    context=_CTX,
                    status_code=500,
                    response_body="Server error (503) from x",
                ),
                None,
                id="500",
            ),
        ],
    )
    async def test_the_adapter_error_for_a_transport_failure_is_classified(
        self, exc: Exception, kind: str | None
    ) -> None:
        """Through the real adapter: the error text it records is what is matched."""
        with patch.object(
            adapter_ai_reviewer, "call_model", AsyncMock(side_effect=exc)
        ):
            result = await adapter_ai_reviewer.async_parse_raw(
                "diff",
                model=next(iter(adapter_ai_reviewer.MODEL_REGISTRY)),
                review_type="pr",
            )
        assert not result.success
        assert substitutable_failure(result) == kind


class _StatusHandler(http.server.BaseHTTPRequestHandler):
    """Answers every GET with the server's configured status and body."""

    def do_GET(self) -> None:
        server = self.server
        assert isinstance(server, _StatusServer)
        if server.delay_seconds:
            time.sleep(server.delay_seconds)
        self.send_response(server.status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(server.body.encode())


class _StatusServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, status: int, body: str, delay_seconds: float) -> None:
        super().__init__(("127.0.0.1", 0), _StatusHandler)
        self.status = status
        self.body = body
        self.delay_seconds = delay_seconds


def _served_model_error(
    status: int | None, *, body: str = "Service Unavailable", delay: float = 0.0
) -> str:
    """The error the review adapter records when the real /v1/models read fails.

    ``status=None`` reads from a port nothing listens on, so the connection is
    refused. Every other case runs a loopback server that answers ``status``.
    """
    if status is None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        url = f"http://127.0.0.1:{port}/v1/chat/completions"
        server = None
    else:
        server = _StatusServer(status, body, delay)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{server.server_address[1]}/v1/chat/completions"
    try:
        resolve_served_model_id(url, timeout_seconds=0.5, use_cache=False)
    except ServedModelResolutionError as exc:
        return _transport_error(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
    raise AssertionError(f"the /v1/models read of {url} did not fail")


@pytest.mark.unit
class TestServedModelReadFailure:
    """A ``served`` voter can be lost before its review call (OMN-20947).

    The gate reads GET /v1/models first; a Studio that answers 503 there, or
    refuses the connection, fails the voter with the resolver's error, not the
    transport's. Each error here comes from a real urllib read of a loopback
    server, so the text matched is the text the gate records.
    """

    @pytest.mark.parametrize(
        ("status", "delay"),
        [
            pytest.param(503, 0.0, id="models-503"),
            pytest.param(502, 0.0, id="models-502"),
            pytest.param(504, 0.0, id="models-504"),
            pytest.param(None, 0.0, id="models-connection-refused"),
            pytest.param(200, 2.0, id="models-no-answer-in-time"),
        ],
    )
    def test_an_unavailable_models_endpoint_is_an_unavailable_voter(
        self, status: int | None, delay: float
    ) -> None:
        error = _served_model_error(status, delay=delay)
        assert error.startswith("could not read the served model id from ")
        assert substitutable_failure(_fail("second", error)) == FAILURE_UNAVAILABLE

    @pytest.mark.parametrize(
        ("status", "body"),
        [
            pytest.param(500, "HTTP Error 503: ", id="models-500-quoting-503"),
            pytest.param(404, "not found", id="models-404"),
            pytest.param(401, "unauthorized", id="models-401"),
            pytest.param(200, "not json", id="models-not-json"),
            pytest.param(
                200,
                json.dumps({"data": [{"id": "a"}, {"id": "b"}]}),
                id="models-two-served",
            ),
        ],
    )
    def test_any_other_models_failure_is_not_substitutable(
        self, status: int, body: str
    ) -> None:
        error = _served_model_error(status, body=body)
        assert substitutable_failure(_fail("second", error)) is None

    @pytest.mark.parametrize(
        "status",
        [pytest.param(503, id="models-503"), pytest.param(None, id="refused")],
    )
    def test_the_gate_substitutes_clean_receipts_for_it(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        status: int | None,
    ) -> None:
        error = _served_model_error(status)
        code, document, _ = _run_gate(
            tmp_path,
            [_receipt_review("codex"), _receipt_review("opus")],
            second_error=error,
        )

        assert code == 0
        records = document["substitute_votes"]
        assert isinstance(records, list)
        (record,) = records
        assert record["failure"] == FAILURE_UNAVAILABLE
        assert record["replaced_error"] == error
        assert (
            "Substitute vote: voter 'second' was unavailable" in capsys.readouterr().err
        )

    def test_the_same_receipt_rules_hold(self, tmp_path: Path) -> None:
        """A receipt for another head is refused for this failure as well."""
        code, document, _ = _run_gate(
            tmp_path,
            [_receipt_review("codex"), _receipt_review("opus", head=_OTHER)],
            second_error=_served_model_error(503),
        )
        assert code == 2
        assert not document.get("substitute_votes")

    def test_without_receipts_the_gate_stays_red(self, tmp_path: Path) -> None:
        code, document, _ = _run_gate(
            tmp_path, [], second_error=_served_model_error(503)
        )
        assert code == 2
        assert not document.get("substitute_votes")
