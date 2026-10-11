# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Off-CI review receipts that may stand in for a timed-out voter (OMN-20947).

Operator RULING 2026-10-11T01:52:39Z: while a lab review voter times out,
approved reviewers review the pull request outside CI, and CI only reads
their result. A Hostile Reviewer voter that times out casts no vote; with two
required voters that is no quorum and the gate fails closed. When the voters
overlay declares a ``substitute_votes`` policy, clean receipts from approved
off-CI reviewers can replace that one lost vote, provided the gate can verify
them without trusting any free text:

* a receipt is a JSON document in a fenced ``onex-review-receipt`` block of a
  pull request review, posted by an account the policy names for that
  reviewer;
* it is HMAC-SHA256 signed, over every field and domain-separated by the
  schema version, with the key in the environment variable the policy names;
* it is bound to the exact head commit twice: in the signed payload, and by
  the GitHub review's own ``commit_id``;
* it is no older than ``receipt_max_age_seconds``;
* its verdict is ``clean`` with zero findings. A valid receipt that records
  findings refuses substitution outright: a reviewer that found defects is
  never counted as a pass.

Only a voter whose call failed with the transport timeout is substituted --
an unreachable voter, an unparseable reply or any other failure is not. At
least one configured voter must have voted for real, each approved reviewer
stands in for at most one voter, and the quorum rule (``evaluate_quorum``) is
applied unchanged afterwards: the stand-in vote carries no findings and its
own reviewer identity, exactly like a clean vote from a distinct model.

Every function here is pure: the reviews, the key and the clock are inputs.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta

from pydantic import ValidationError

from omniintelligence.nodes.node_review_receipt_substitute_compute.models.model_pull_request_review_view import (
    ModelPullRequestReviewView,
)
from omniintelligence.nodes.node_review_receipt_substitute_compute.models.model_review_receipt import (
    RECEIPT_FENCE,
    RECEIPT_SCHEMA_VERSION,
    ModelReviewReceipt,
)
from omniintelligence.nodes.node_review_receipt_substitute_compute.models.model_substitute_decision import (
    ModelSubstituteDecision,
)
from omniintelligence.nodes.node_review_receipt_substitute_compute.models.model_substitute_vote_request import (
    ModelSubstituteVoteRequest,
)
from omniintelligence.nodes.node_review_voters_overlay_compute.models.model_substitute_vote_policy import (
    ModelSubstituteVotePolicy,
)
from omniintelligence.review_pairing.models_external_review import (
    ModelExternalReviewResult,
    ModelMultiReviewResult,
    ModelSubstituteVoteRecord,
)

TIMEOUT_ERROR_CODE = "ONEX_CORE_092_TIMEOUT_ERROR"
_FUTURE_SKEW = timedelta(seconds=300)
_BLOCK = re.compile(
    r"```" + re.escape(RECEIPT_FENCE) + r"[ \t]*\r?\n(?P<body>.*?)\r?\n```",
    re.DOTALL,
)


def _signed_payload(receipt: ModelReviewReceipt) -> bytes:
    fields = receipt.model_dump(mode="json", exclude={"signature"})
    fields["repo"] = str(fields["repo"]).lower()
    body = json.dumps(fields, sort_keys=True, separators=(",", ":"))
    return f"{RECEIPT_SCHEMA_VERSION}\n{body}".encode()


def receipt_signature(receipt: ModelReviewReceipt, key: bytes) -> str:
    """HMAC-SHA256 over every field but the signature, domain-separated."""
    return hmac.new(key, _signed_payload(receipt), hashlib.sha256).hexdigest()


def sign_receipt(
    *,
    repo: str,
    pr: int,
    head_sha: str,
    reviewer_id: str,
    findings_count: int,
    issued_at: datetime,
    key: bytes,
) -> ModelReviewReceipt:
    """Build and sign a receipt. ``verdict`` follows from ``findings_count``."""
    unsigned = ModelReviewReceipt(
        schema_version="hostile_review_receipt.v1",
        repo=repo,
        pr=pr,
        head_sha=head_sha,
        reviewer_id=reviewer_id,
        verdict="clean" if findings_count == 0 else "findings",
        findings_count=findings_count,
        issued_at=issued_at,
        signature="0" * 64,
    )
    return unsigned.model_copy(update={"signature": receipt_signature(unsigned, key)})


def render_receipt_block(receipt: ModelReviewReceipt) -> str:
    """The fenced block a reviewer posts in its pull request review body."""
    return f"```{RECEIPT_FENCE}\n{receipt.model_dump_json()}\n```"


def receipts_in_body(body: str) -> list[tuple[ModelReviewReceipt | None, str]]:
    """Every receipt block in a review body, parsed, or why it did not parse."""
    found: list[tuple[ModelReviewReceipt | None, str]] = []
    for match in _BLOCK.finditer(body or ""):
        try:
            found.append(
                (ModelReviewReceipt.model_validate_json(match.group("body")), "")
            )
        except ValidationError as exc:
            found.append((None, f"malformed receipt: {exc.error_count()} error(s)"))
    return found


def is_timeout_failure(result: ModelExternalReviewResult) -> bool:
    """True when the voter was called and its call failed by timing out."""
    return (not result.success) and TIMEOUT_ERROR_CODE in (result.error or "")


def _check(
    receipt: ModelReviewReceipt,
    review: ModelPullRequestReviewView,
    request: ModelSubstituteVoteRequest,
    policy: ModelSubstituteVotePolicy,
    key: bytes,
) -> str:
    """Empty when the receipt is valid for this head; otherwise why not."""
    who = f"reviewer {receipt.reviewer_id!r}"
    reviewer = policy.reviewer(receipt.reviewer_id)
    if reviewer is None:
        return f"{who} is not an approved substitute"
    if review.author_login not in reviewer.github_logins:
        return (
            f"{who} receipt was posted by {review.author_login!r}, not an "
            "account the overlay names for it"
        )
    if review.state.upper() == "DISMISSED":
        return f"{who} receipt is on a dismissed review"
    if receipt.repo.lower() != request.repo.lower() or receipt.pr != request.pr:
        return (
            f"{who} receipt is for {receipt.repo}#{receipt.pr}, "
            f"not {request.repo}#{request.pr}"
        )
    head = request.head_sha
    if receipt.head_sha != head or review.commit_id != head:
        return (
            f"{who} receipt is bound to {receipt.head_sha[:12]} (review commit "
            f"{review.commit_id[:12]}), not head {head[:12]}"
        )
    if not hmac.compare_digest(receipt.signature, receipt_signature(receipt, key)):
        return f"{who} receipt signature does not verify"
    age = request.now - receipt.issued_at
    if age < -_FUTURE_SKEW:
        return f"{who} receipt is dated in the future"
    if age > timedelta(seconds=policy.receipt_max_age_seconds):
        return (
            f"{who} receipt is {int(age.total_seconds())}s old, over the "
            f"{policy.receipt_max_age_seconds}s limit"
        )
    return ""


def handle(request: ModelSubstituteVoteRequest) -> ModelSubstituteDecision:
    """Decide which timed-out voters valid clean receipts stand in for."""
    result = request.result
    timed_out = [r for r in result.results if is_timeout_failure(r)]
    if not timed_out:
        return ModelSubstituteDecision()
    policy = request.policy
    if policy is None:
        return ModelSubstituteDecision(
            refusals=("the overlay declares no substitute_votes policy",)
        )
    key = request.key
    if not key:
        return ModelSubstituteDecision(
            refusals=(f"the receipt signing key ({policy.signing_key_env}) is not set",)
        )
    if not any(r.success for r in result.results):
        return ModelSubstituteDecision(
            refusals=("no configured voter voted; receipts never form a quorum alone",)
        )

    refusals: list[str] = []
    clean: dict[str, str] = {}  # reviewer_id -> account that posted it
    findings: list[str] = []
    for review in request.reviews:
        for receipt, parse_error in receipts_in_body(review.body):
            if receipt is None:
                refusals.append(f"review by {review.author_login!r}: {parse_error}")
                continue
            reason = _check(receipt, review, request, policy, key)
            if reason:
                refusals.append(reason)
            elif receipt.verdict == "findings":
                findings.append(
                    f"reviewer {receipt.reviewer_id!r} recorded "
                    f"{receipt.findings_count} finding(s) at {request.head_sha[:12]}"
                )
            else:
                clean.setdefault(receipt.reviewer_id, review.author_login)

    if findings:
        return ModelSubstituteDecision(
            refusals=(*refusals, *findings, "a receipt with findings is never a pass")
        )

    available = [r.reviewer_id for r in policy.reviewers if r.reviewer_id in clean]
    records: list[ModelSubstituteVoteRecord] = []
    for voter in timed_out:
        if len(available) < policy.receipts_per_vote:
            refusals.append(
                f"voter {voter.model!r} timed out and {len(available)} unused clean "
                f"receipt(s) remain for head {request.head_sha[:12]}; "
                f"{policy.receipts_per_vote} required"
            )
            continue
        group = available[: policy.receipts_per_vote]
        available = available[policy.receipts_per_vote :]
        records.append(
            ModelSubstituteVoteRecord(
                voter_id=voter.model,
                replaced_error=voter.error or "",
                reviewer_ids=tuple(group),
                head_sha=request.head_sha,
                review_authors=tuple(clean[rid] for rid in group),
            )
        )
    return ModelSubstituteDecision(records=tuple(records), refusals=tuple(refusals))


def apply_substitutes(
    result: ModelMultiReviewResult, decision: ModelSubstituteDecision
) -> ModelMultiReviewResult:
    """Replace each substituted voter's failed result with a clean stand-in vote."""
    if not decision.records:
        return result
    by_voter = {record.voter_id: record for record in decision.records}
    results: list[ModelExternalReviewResult] = []
    for r in result.results:
        record = by_voter.get(r.model)
        if record is None:
            results.append(r)
            continue
        results.append(
            ModelExternalReviewResult(
                model=r.model,
                prompt_version=r.prompt_version,
                success=True,
                findings=[],
                result_count=0,
                reviewer_identity="receipt:" + "+".join(record.reviewer_ids),
            )
        )
    return result.model_copy(
        update={
            "results": results,
            "models_succeeded": [r.model for r in results if r.success],
            "models_failed": [r.model for r in results if not r.success],
            "substitute_votes": [*result.substitute_votes, *decision.records],
        }
    )


__all__ = [
    "TIMEOUT_ERROR_CODE",
    "apply_substitutes",
    "handle",
    "is_timeout_failure",
    "receipt_signature",
    "receipts_in_body",
    "render_receipt_block",
    "sign_receipt",
]
