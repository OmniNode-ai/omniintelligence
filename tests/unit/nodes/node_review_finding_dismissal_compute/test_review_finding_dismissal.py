# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""A refuted blocking finding is cleared by a recorded dismissal a second voter confirms (OMN-20910)."""

from __future__ import annotations

import pytest

from omniintelligence.models.review.model_review_finding_dismissal_record import (
    EnumReviewDismissalOutcome,
    EnumReviewDismissalRefusal,
)
from omniintelligence.nodes.node_review_finding_dismissal_compute.handlers.handler_review_finding_dismissal import (
    HandlerReviewFindingDismissal,
    apply_dismissals,
    build_judge_prompt,
    diff_excerpt,
    parse_dismissal_comments,
    parse_judge_reply,
    plan_dismissals,
)
from omniintelligence.nodes.node_review_finding_dismissal_compute.models import (
    ModelDismissalComment,
    ModelDismissalJudgement,
    ModelDismissalVoter,
    ModelFindingDismissal,
    ModelReviewDismissalRequest,
)
from omniintelligence.review_pairing.models import EnumFindingSeverity
from omniintelligence.review_pairing.models_external_review import (
    EnumQuorumVerdict,
    ModelQuorumFinding,
    ModelReviewQuorumSummary,
)
from omniintelligence.review_pairing.quorum import quorum_finding_key

HEAD = "a" * 40
NEW_HEAD = "b" * 40
EVIDENCE = (
    "The handler returns a structured error on line 40; the test "
    "test_refused_on_missing_field covers the path the finding says is unhandled."
)


def _finding(
    path: str = "src/x/handler.py",
    line: int = 40,
    models: tuple[str, ...] = ("lab-voter", "sonnet-gateway"),
) -> ModelQuorumFinding:
    rule = "category:error_handling"
    return ModelQuorumFinding(
        file_path=path,
        line_start=line,
        severity=EnumFindingSeverity.ERROR,
        rule=rule,
        message="the missing-field path raises instead of returning an error",
        agreeing_models=models,
        agreement_count=len(models),
        blocking=True,
        finding_key=quorum_finding_key(path, rule, EnumFindingSeverity.ERROR, line),
    )


VOTERS = (
    ModelDismissalVoter(voter_id="lab-voter", identity="lab#qwen"),
    ModelDismissalVoter(voter_id="sonnet-gateway", identity="anthropic#sonnet"),
)


def _dismissal(
    key: str, *, head: str = HEAD, evidence: str = EVIDENCE, authorized: bool = True
) -> ModelFindingDismissal:
    return ModelFindingDismissal(
        finding_key=key,
        head_sha=head,
        evidence=evidence,
        author="pr-author",
        source="comment:1",
        authorized=authorized,
    )


def _request(
    findings: tuple[ModelQuorumFinding, ...],
    dismissals: tuple[ModelFindingDismissal, ...],
    judgements: tuple[ModelDismissalJudgement, ...] = (),
    head: str = HEAD,
) -> ModelReviewDismissalRequest:
    return ModelReviewDismissalRequest(
        head_sha=head,
        blocking_findings=findings,
        dismissals=dismissals,
        voters=VOTERS,
        judgements=judgements,
        repo="OmniNode-ai/omnimarket",
        pr=4044,
    )


def _summary(findings: tuple[ModelQuorumFinding, ...]) -> ModelReviewQuorumSummary:
    return ModelReviewQuorumSummary(
        verdict=EnumQuorumVerdict.BLOCKED,
        quorum_threshold=2,
        models_succeeded=("lab-voter", "sonnet-gateway"),
        distinct_reviewers_succeeded=("lab#qwen", "anthropic#sonnet"),
        quorum_met=True,
        blocking_count=len(findings),
        blocking_findings=findings,
    )


@pytest.mark.unit
def test_confirmed_dismissal_clears_the_block() -> None:
    finding = _finding()
    assignments, refused = plan_dismissals(
        _request((finding,), (_dismissal(finding.finding_key),))
    )
    assert refused == ()
    assert len(assignments) == 1
    judge = assignments[0].judge_voter
    # The judge is never the voter whose message the finding carries.
    assert judge != finding.agreeing_models[0]

    result = HandlerReviewFindingDismissal().handle(
        _request(
            (finding,),
            (_dismissal(finding.finding_key),),
            (
                ModelDismissalJudgement(
                    finding_key=finding.finding_key,
                    judge_voter=judge,
                    confirmed=True,
                    reason="the cited test exercises the path",
                ),
            ),
        )
    )
    assert result.cleared_keys == (finding.finding_key,)
    (record,) = result.records
    assert record.outcome is EnumReviewDismissalOutcome.CONFIRMED
    assert record.judge_voter == judge
    assert record.evidence == EVIDENCE

    summary = apply_dismissals(_summary((finding,)), result.cleared_keys)
    assert summary.verdict is EnumQuorumVerdict.PASSED
    assert summary.blocking_count == 0
    assert summary.dismissed_findings == (finding,)


@pytest.mark.unit
def test_rejected_dismissal_keeps_the_block() -> None:
    finding = _finding()
    other = _finding(path="src/x/other.py", line=7)
    (assignment,), _ = plan_dismissals(
        _request((finding, other), (_dismissal(finding.finding_key),))
    )
    result = HandlerReviewFindingDismissal().handle(
        _request(
            (finding, other),
            (_dismissal(finding.finding_key),),
            (
                ModelDismissalJudgement(
                    finding_key=finding.finding_key,
                    judge_voter=assignment.judge_voter,
                    confirmed=False,
                    reason="the cited test does not reach line 40",
                ),
            ),
        )
    )
    assert result.cleared_keys == ()
    assert result.records[0].outcome is EnumReviewDismissalOutcome.REJECTED
    summary = apply_dismissals(_summary((finding, other)), result.cleared_keys)
    assert summary.verdict is EnumQuorumVerdict.BLOCKED
    assert summary.blocking_count == 2


@pytest.mark.unit
def test_unjudged_dismissal_keeps_the_block() -> None:
    """A judge that could not be asked confirms nothing: fail closed."""
    finding = _finding()
    result = HandlerReviewFindingDismissal().handle(
        _request((finding,), (_dismissal(finding.finding_key),))
    )
    assert result.cleared_keys == ()
    assert result.records[0].outcome is EnumReviewDismissalOutcome.REJECTED


@pytest.mark.unit
@pytest.mark.parametrize("evidence", ["", "   \n  ", "refuted"])
def test_dismissal_without_evidence_is_refused(evidence: str) -> None:
    finding = _finding()
    request = _request(
        (finding,), (_dismissal(finding.finding_key, evidence=evidence),)
    )
    assignments, refused = plan_dismissals(request)
    assert assignments == ()
    assert refused[0].refusal is EnumReviewDismissalRefusal.NO_EVIDENCE
    result = HandlerReviewFindingDismissal().handle(request)
    assert result.cleared_keys == ()
    assert result.records[0].outcome is EnumReviewDismissalOutcome.REFUSED


@pytest.mark.unit
def test_finding_raised_again_on_a_new_head_needs_a_new_dismissal() -> None:
    finding = _finding()
    old = _dismissal(finding.finding_key, head=HEAD)
    confirm = ModelDismissalJudgement(
        finding_key=finding.finding_key,
        judge_voter="sonnet-gateway",
        confirmed=True,
        reason="ok",
    )
    # The same finding on a new head: the dismissal recorded for the old head
    # is refused even with a confirming judgement on hand.
    result = HandlerReviewFindingDismissal().handle(
        _request((finding,), (old,), (confirm,), head=NEW_HEAD)
    )
    assert result.cleared_keys == ()
    assert result.records[0].refusal is EnumReviewDismissalRefusal.STALE_HEAD
    # A dismissal recorded for the new head is put to the judge again.
    assignments, _ = plan_dismissals(
        _request(
            (finding,),
            (old, _dismissal(finding.finding_key, head=NEW_HEAD)),
            head=NEW_HEAD,
        )
    )
    assert [a.dismissal.head_sha for a in assignments] == [NEW_HEAD]


@pytest.mark.unit
def test_unknown_and_unauthorized_dismissals_are_refused() -> None:
    finding = _finding()
    _, refused = plan_dismissals(
        _request(
            (finding,),
            (
                _dismissal("hr-000000000000"),
                _dismissal(finding.finding_key, authorized=False),
            ),
        )
    )
    assert [r.refusal for r in refused] == [
        EnumReviewDismissalRefusal.UNKNOWN_FINDING,
        EnumReviewDismissalRefusal.NOT_AUTHORIZED,
    ]


@pytest.mark.unit
def test_judge_prefers_a_voter_that_did_not_raise_the_finding() -> None:
    finding = _finding(models=("lab-voter",))
    (assignment,), _ = plan_dismissals(
        _request((finding,), (_dismissal(finding.finding_key),))
    )
    assert assignment.judge_voter == "sonnet-gateway"
    assert assignment.judge_raised_finding is False


@pytest.mark.unit
def test_no_second_voter_is_refused() -> None:
    finding = _finding(models=("lab-voter",))
    request = ModelReviewDismissalRequest(
        head_sha=HEAD,
        blocking_findings=(finding,),
        dismissals=(_dismissal(finding.finding_key),),
        voters=(VOTERS[0],),
    )
    _, refused = plan_dismissals(request)
    assert refused[0].refusal is EnumReviewDismissalRefusal.NO_SECOND_VOTER


@pytest.mark.unit
def test_parse_dismissal_comments() -> None:
    key = "hr-0123456789ab"
    body = (
        "Refuting the reviewer.\n\n"
        f"/hostile-review dismiss {key}\n"
        f"head: {HEAD[:12]}\n"
        "evidence: the file parses with ast.parse;\n"
        "see the CI log of the test job.\n"
    )
    comments = (
        ModelDismissalComment(comment_id="1", author="pr-author", body=body),
        ModelDismissalComment(
            comment_id="2", author="drive-by", author_association="NONE", body=body
        ),
        ModelDismissalComment(
            comment_id="3",
            author="github-actions[bot]",
            author_association="NONE",
            body=body,
        ),
        ModelDismissalComment(
            comment_id="4", author="teammate", author_association="MEMBER", body=body
        ),
    )
    parsed = parse_dismissal_comments(comments, pr_author="pr-author")
    assert [(d.author, d.authorized) for d in parsed] == [
        ("pr-author", True),
        ("drive-by", False),
        ("teammate", True),
    ]
    first = parsed[0]
    assert first.finding_key == key
    assert first.head_sha == HEAD[:12]
    assert first.source == "comment:1"
    assert (
        first.evidence
        == "the file parses with ast.parse;\nsee the CI log of the test job."
    )


@pytest.mark.unit
def test_short_head_prefix_matches_the_head() -> None:
    finding = _finding()
    assignments, _ = plan_dismissals(
        _request((finding,), (_dismissal(finding.finding_key, head=HEAD[:12]),))
    )
    assert len(assignments) == 1


@pytest.mark.unit
@pytest.mark.parametrize(
    ("reply", "confirmed"),
    [
        ('{"verdict": "confirm", "reason": "the evidence holds"}', True),
        ('```json\n{"verdict": "confirm", "reason": "ok"}\n```', True),
        ('{"verdict": "reject", "reason": "no"}', False),
        ("I think the dismissal is fine", False),
        ('{"verdict": "maybe"}', False),
    ],
)
def test_parse_judge_reply_fails_closed(reply: str, confirmed: bool) -> None:
    assert parse_judge_reply(reply)[0] is confirmed


@pytest.mark.unit
def test_judge_prompt_carries_finding_evidence_and_diff() -> None:
    finding = _finding()
    (assignment,), _ = plan_dismissals(
        _request((finding,), (_dismissal(finding.finding_key),))
    )
    diff = (
        "diff --git a/src/x/other.py b/src/x/other.py\n+unrelated\n"
        "diff --git a/src/x/handler.py b/src/x/handler.py\n+    return error\n"
    )
    excerpt = diff_excerpt(diff, finding.file_path, max_chars=4000)
    assert "handler.py" in excerpt and "unrelated" not in excerpt
    system, user = build_judge_prompt(assignment, excerpt)
    assert "confirm" in system and "reject" in system
    assert finding.message in user and EVIDENCE in user and "return error" in user


@pytest.mark.unit
def test_a_superseded_dismissal_is_still_recorded() -> None:
    """Every dismissal yields a record; only the latest one per key is judged."""
    finding = _finding()
    first = _dismissal(finding.finding_key, evidence="")
    latest = _dismissal(finding.finding_key)
    assignments, refused = plan_dismissals(_request((finding,), (first, latest)))
    assert [a.dismissal for a in assignments] == [latest]
    assert [r.refusal for r in refused] == [EnumReviewDismissalRefusal.NO_EVIDENCE]
    _, refused = plan_dismissals(_request((finding,), (latest, latest)))
    assert [r.refusal for r in refused] == [EnumReviewDismissalRefusal.SUPERSEDED]
