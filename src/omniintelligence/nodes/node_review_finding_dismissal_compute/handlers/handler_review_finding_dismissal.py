# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Clear a refuted blocking finding by a recorded dismissal a second voter confirms (OMN-20910).

A blocked Hostile Reviewer verdict used to leave an author who refuted a
finding with evidence nothing to do but hand-accept the block. Here the author
records a dismissal per finding key, for one head, with evidence, as a pull
request comment::

    /hostile-review dismiss hr-0123456789ab
    head: <the head sha, or at least its first 7 characters>
    evidence: <why the finding does not hold; may run over several lines>

Each dismissal is then, in order:

* refused (it keeps blocking) when it names no blocking finding of this head,
  when its author is neither the pull request author nor a repository writer,
  when it names another head (a finding raised again on a new head needs a new
  dismissal), when its evidence is empty or under ``MIN_EVIDENCE_CHARS``, or
  when no second voter succeeded in this review;
* otherwise put to a second voter: a succeeded voter that did not raise the
  finding when there is one, else any succeeded voter other than the one whose
  message the finding carries. The judge's reply must be a JSON verdict
  ``confirm``; anything else, an unreadable reply or no reply at all, rejects.

Only confirmed dismissals stop blocking. Every dismissal yields one record.
The handler is pure; the caller reads the comments and makes the judge calls.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence

from omniintelligence.models.review.model_review_finding_dismissal_record import (
    EnumReviewDismissalOutcome,
    EnumReviewDismissalRefusal,
    ModelReviewFindingDismissalRecord,
)
from omniintelligence.nodes.node_review_finding_dismissal_compute.models.model_dismissal_assignment import (
    ModelDismissalAssignment,
)
from omniintelligence.nodes.node_review_finding_dismissal_compute.models.model_dismissal_comment import (
    ModelDismissalComment,
)
from omniintelligence.nodes.node_review_finding_dismissal_compute.models.model_finding_dismissal import (
    ModelFindingDismissal,
)
from omniintelligence.nodes.node_review_finding_dismissal_compute.models.model_review_dismissal_request import (
    ModelReviewDismissalRequest,
)
from omniintelligence.nodes.node_review_finding_dismissal_compute.models.model_review_dismissal_result import (
    ModelReviewDismissalResult,
)
from omniintelligence.review_pairing.models_external_review import (
    EnumQuorumVerdict,
    ModelQuorumFinding,
    ModelReviewQuorumSummary,
)

DISMISS_COMMAND = "/hostile-review dismiss"
MIN_EVIDENCE_CHARS = 20
MIN_HEAD_PREFIX = 7
WRITER_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})

_COMMAND = re.compile(
    r"^\s*/hostile-review\s+dismiss\s+(?P<key>hr-[0-9a-f]{12})\s*$", re.IGNORECASE
)
_FIELD = re.compile(r"^\s*(?P<name>head|evidence)\s*:\s?(?P<value>.*)$", re.IGNORECASE)
_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)

JUDGE_SYSTEM_PROMPT = (
    "You are the second voter on a disputed code review finding. Two reviewers "
    "raised the finding below; the pull request author dismissed it and gave "
    "evidence. Judge only whether the evidence, read against the diff excerpt, "
    "shows the finding does not hold. Confirm the dismissal only when the "
    "evidence is specific and the diff bears it out; reject it when the evidence "
    "is vague, does not address the finding, or the diff contradicts it. Reply "
    'with one JSON object and nothing else: {"verdict": "confirm" | "reject", '
    '"reason": "<one sentence>"}.'
)


def _is_bot(login: str) -> bool:
    return login.endswith("[bot]")


def parse_dismissal_comments(
    comments: Iterable[ModelDismissalComment], *, pr_author: str | None
) -> tuple[ModelFindingDismissal, ...]:
    """Every dismissal command in the comments, oldest first; bot comments are skipped."""
    dismissals: list[ModelFindingDismissal] = []
    for comment in comments:
        if _is_bot(comment.author):
            continue
        authorized = (
            pr_author is not None and comment.author == pr_author
        ) or comment.author_association.upper() in WRITER_ASSOCIATIONS
        for key, head, evidence in _parse_body(comment.body):
            dismissals.append(
                ModelFindingDismissal(
                    finding_key=key.lower(),
                    head_sha=head,
                    evidence=evidence,
                    author=comment.author,
                    source=f"comment:{comment.comment_id}",
                    authorized=authorized,
                )
            )
    return tuple(dismissals)


def _parse_body(body: str) -> list[tuple[str, str, str]]:
    """``(key, head, evidence)`` for each command block in one comment body."""
    blocks: list[tuple[str, str, str]] = []
    key: str | None = None
    head = ""
    evidence: list[str] = []
    in_evidence = False

    def close() -> None:
        if key is not None:
            blocks.append((key, head, "\n".join(evidence).strip()))

    for line in body.splitlines():
        command = _COMMAND.match(line)
        if command is not None:
            close()
            key, head, evidence, in_evidence = command.group("key"), "", [], False
            continue
        if key is None:
            continue
        field = _FIELD.match(line)
        if field is not None and not in_evidence:
            if field.group("name").lower() == "head":
                head = field.group("value").strip()
            else:
                in_evidence = True
                evidence.append(field.group("value"))
            continue
        if in_evidence:
            evidence.append(line)
    close()
    return blocks


def _head_matches(dismissal_head: str, head_sha: str) -> bool:
    head = dismissal_head.strip().lower()
    return len(head) >= MIN_HEAD_PREFIX and head_sha.lower().startswith(head)


def _record(
    request: ModelReviewDismissalRequest,
    dismissal: ModelFindingDismissal,
    finding: ModelQuorumFinding | None,
    outcome: EnumReviewDismissalOutcome,
    *,
    refusal: EnumReviewDismissalRefusal | None = None,
    judge_voter: str | None = None,
    judge_raised_finding: bool = False,
    judge_reason: str = "",
) -> ModelReviewFindingDismissalRecord:
    return ModelReviewFindingDismissalRecord(
        finding_key=dismissal.finding_key,
        head_sha=request.head_sha,
        dismissal_head_sha=dismissal.head_sha,
        author=dismissal.author,
        source=dismissal.source,
        evidence=dismissal.evidence,
        outcome=outcome,
        refusal=refusal,
        judge_voter=judge_voter,
        judge_raised_finding=judge_raised_finding,
        judge_reason=judge_reason,
        file_path=finding.file_path if finding is not None else "",
        line_start=finding.line_start if finding is not None else 0,
        severity=finding.severity.value if finding is not None else "",
        rule=finding.rule if finding is not None else "",
        repo=request.repo,
        pr=request.pr,
        correlation_id=request.correlation_id,
    )


def _choose_judge(
    finding: ModelQuorumFinding, request: ModelReviewDismissalRequest
) -> tuple[str, bool] | None:
    """``(judge voter, judge raised the finding)``, or None when no second voter exists."""
    raisers = set(finding.agreeing_models)
    for voter in request.voters:
        if voter.voter_id not in raisers:
            return voter.voter_id, False
    first_raiser = finding.agreeing_models[0] if finding.agreeing_models else None
    for voter in request.voters:
        if voter.voter_id != first_raiser:
            return voter.voter_id, True
    return None


def _latest_per_key(
    dismissals: Sequence[ModelFindingDismissal], head_sha: str
) -> list[ModelFindingDismissal]:
    """Keep, per finding key, the latest authorized dismissal for this head.

    Dismissals for other heads, unauthorized ones and superseded ones are kept
    as they are so each still gets a record; only an authorized dismissal for
    this head supersedes an earlier one of the same key.
    """
    latest: dict[str, int] = {}
    for index, dismissal in enumerate(dismissals):
        if dismissal.authorized and _head_matches(dismissal.head_sha, head_sha):
            latest[dismissal.finding_key] = index
    kept: list[ModelFindingDismissal] = []
    for index, dismissal in enumerate(dismissals):
        current = dismissal.authorized and _head_matches(dismissal.head_sha, head_sha)
        if current and latest[dismissal.finding_key] != index:
            continue
        kept.append(dismissal)
    return kept


def plan_dismissals(
    request: ModelReviewDismissalRequest,
) -> tuple[
    tuple[ModelDismissalAssignment, ...], tuple[ModelReviewFindingDismissalRecord, ...]
]:
    """Split the dismissals into those put to a judge and those refused outright."""
    findings = {f.finding_key: f for f in request.blocking_findings if f.finding_key}
    assignments: list[ModelDismissalAssignment] = []
    refused: list[ModelReviewFindingDismissalRecord] = []
    for dismissal in _latest_per_key(request.dismissals, request.head_sha):
        finding = findings.get(dismissal.finding_key)
        refusal: EnumReviewDismissalRefusal | None = None
        judge: tuple[str, bool] | None = None
        if finding is None:
            refusal = EnumReviewDismissalRefusal.UNKNOWN_FINDING
        elif not dismissal.authorized:
            refusal = EnumReviewDismissalRefusal.NOT_AUTHORIZED
        elif not _head_matches(dismissal.head_sha, request.head_sha):
            refusal = EnumReviewDismissalRefusal.STALE_HEAD
        elif len(dismissal.evidence.strip()) < MIN_EVIDENCE_CHARS:
            refusal = EnumReviewDismissalRefusal.NO_EVIDENCE
        else:
            judge = _choose_judge(finding, request)
            if judge is None:
                refusal = EnumReviewDismissalRefusal.NO_SECOND_VOTER
        if refusal is not None or judge is None or finding is None:
            refused.append(
                _record(
                    request,
                    dismissal,
                    finding,
                    EnumReviewDismissalOutcome.REFUSED,
                    refusal=refusal,
                )
            )
            continue
        assignments.append(
            ModelDismissalAssignment(
                finding=finding,
                dismissal=dismissal,
                judge_voter=judge[0],
                judge_raised_finding=judge[1],
            )
        )
    return tuple(assignments), tuple(refused)


def diff_excerpt(diff: str, path: str, *, max_chars: int) -> str:
    """The diff sections of ``path`` (case-insensitive), cut at ``max_chars``."""
    wanted = path.strip().lower().lstrip("./")
    sections: list[str] = []
    current: list[str] = []
    keep = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            if keep and current:
                sections.append("\n".join(current))
            current = [line]
            keep = line.lower().endswith(f" b/{wanted}")
            continue
        current.append(line)
    if keep and current:
        sections.append("\n".join(current))
    return "\n".join(sections)[:max_chars]


def build_judge_prompt(
    assignment: ModelDismissalAssignment, excerpt: str
) -> tuple[str, str]:
    """The judge's system and user prompts for one dismissal."""
    finding = assignment.finding
    user = (
        "## Finding\n"
        f"key: {finding.finding_key}\n"
        f"location: {finding.file_path}:{finding.line_start}\n"
        f"severity: {finding.severity.value}\n"
        f"rule: {finding.rule}\n"
        f"message: {finding.message}\n\n"
        "## Author's evidence for dismissing it\n"
        f"{assignment.dismissal.evidence}\n\n"
        "## Diff excerpt of the file at this head\n"
        f"{excerpt or '(no diff section for this file)'}\n"
    )
    return JUDGE_SYSTEM_PROMPT, user


def parse_judge_reply(reply: str) -> tuple[bool, str]:
    """``(confirmed, reason)``; anything but a JSON ``confirm`` verdict rejects."""
    match = _JSON_OBJECT.search(reply or "")
    if match is None:
        return False, "judge reply carried no JSON verdict"
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return False, "judge reply was not valid JSON"
    if not isinstance(data, dict):
        return False, "judge reply was not a JSON object"
    verdict = str(data.get("verdict", "")).strip().lower()
    reason = str(data.get("reason", "")).strip()
    if verdict == "confirm":
        return True, reason
    if verdict == "reject":
        return False, reason
    return False, f"judge verdict {verdict!r} is neither confirm nor reject"


def apply_dismissals(
    summary: ModelReviewQuorumSummary, cleared_keys: Sequence[str]
) -> ModelReviewQuorumSummary:
    """Move the cleared blocking findings to ``dismissed_findings`` and re-derive the verdict."""
    cleared = set(cleared_keys)
    if not cleared:
        return summary
    kept = tuple(f for f in summary.blocking_findings if f.finding_key not in cleared)
    dismissed = tuple(f for f in summary.blocking_findings if f.finding_key in cleared)
    verdict = summary.verdict
    if verdict is EnumQuorumVerdict.BLOCKED and not kept:
        verdict = EnumQuorumVerdict.PASSED
    return summary.model_copy(
        update={
            "verdict": verdict,
            "blocking_findings": kept,
            "blocking_count": len(kept),
            "dismissed_findings": summary.dismissed_findings + dismissed,
        }
    )


class HandlerReviewFindingDismissal:
    """Resolve recorded dismissals against the second voters' judgements."""

    def handle(
        self, request: ModelReviewDismissalRequest
    ) -> ModelReviewDismissalResult:
        """One record per dismissal; a dismissal clears only on a confirming judgement."""
        assignments, refused = plan_dismissals(request)
        judgements = {(j.finding_key, j.judge_voter): j for j in request.judgements}
        records = list(refused)
        cleared: list[str] = []
        for assignment in assignments:
            key = assignment.finding.finding_key
            judgement = judgements.get((key, assignment.judge_voter))
            confirmed = judgement is not None and judgement.confirmed
            if judgement is None:
                reason = f"no judgement from {assignment.judge_voter}"
            else:
                reason = judgement.reason
            records.append(
                _record(
                    request,
                    assignment.dismissal,
                    assignment.finding,
                    EnumReviewDismissalOutcome.CONFIRMED
                    if confirmed
                    else EnumReviewDismissalOutcome.REJECTED,
                    judge_voter=assignment.judge_voter,
                    judge_raised_finding=assignment.judge_raised_finding,
                    judge_reason=reason,
                )
            )
            if confirmed and key not in cleared:
                cleared.append(key)
        return ModelReviewDismissalResult(
            records=tuple(records),
            cleared_keys=tuple(cleared),
            assignments=assignments,
        )


def handle(request: ModelReviewDismissalRequest) -> ModelReviewDismissalResult:
    """The contract's routed entry point for resolving finding dismissals."""
    return HandlerReviewFindingDismissal().handle(request)


__all__ = [
    "DISMISS_COMMAND",
    "MIN_EVIDENCE_CHARS",
    "HandlerReviewFindingDismissal",
    "apply_dismissals",
    "build_judge_prompt",
    "diff_excerpt",
    "handle",
    "parse_dismissal_comments",
    "parse_judge_reply",
    "plan_dismissals",
]
