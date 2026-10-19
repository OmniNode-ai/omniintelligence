# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""One typed review record per voter and per substitute vote (OMN-20981).

``cli_review`` used to write ``hostile-review-result.json`` into the runner
workspace and the workflow discarded it, so finding content survived only as
pull request threads. This handler turns the same run into records that can be
written out and published:

* one record per voter result, in result order, so a voter that was lost to
  the lab is recorded as the failed run it was;
* one record per substitute vote, naming the voter it replaced and the
  approved reviewers whose clean receipts stood in.

Every function here is pure: the clock and the invocation id are inputs.
"""

from __future__ import annotations

from uuid import NAMESPACE_URL, UUID, uuid5

from omniintelligence.nodes.node_review_record_compute.models import (
    ModelReviewRecordBatch,
    ModelReviewRecorded,
    ModelReviewRecordRequest,
)
from omniintelligence.review_pairing.models_external_review import (
    ModelExternalReviewResult,
    ModelSubstituteVoteRecord,
)


def review_id_for(invocation_id: UUID, arm_kind: str, arm: str) -> UUID:
    """The record's id: the same arm of the same invocation always gets the same id."""
    return uuid5(NAMESPACE_URL, f"review-recorded:{invocation_id}:{arm_kind}:{arm}")


def _voter_record(
    request: ModelReviewRecordRequest, result: ModelExternalReviewResult
) -> ModelReviewRecorded:
    failed = not result.success
    findings = () if failed else tuple(result.findings)
    return ModelReviewRecorded(
        review_id=review_id_for(request.invocation_id, "voter", result.model),
        invocation_id=request.invocation_id,
        arm=result.model,
        arm_kind="voter",
        reviewer_identity=result.reviewer_identity,
        prompt_version=result.prompt_version,
        review_type=request.review_type,
        repo=request.repo,
        pr=request.pr,
        head_sha=request.head_sha,
        execution_status="failed" if failed else "completed",
        verdict="failed" if failed else ("findings" if findings else "clean"),
        failure_reason=(result.error or "unknown failure") if failed else None,
        findings=findings,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        recorded_at=request.recorded_at,
    )


def _substitute_record(
    request: ModelReviewRecordRequest, vote: ModelSubstituteVoteRecord
) -> ModelReviewRecorded:
    arm = "+".join(vote.reviewer_ids)
    return ModelReviewRecorded(
        review_id=review_id_for(request.invocation_id, "substitute", vote.voter_id),
        invocation_id=request.invocation_id,
        arm=arm,
        arm_kind="substitute",
        reviewer_identity="receipt:" + arm,
        review_type=request.review_type,
        repo=request.repo,
        pr=request.pr,
        head_sha=vote.head_sha,
        execution_status="completed",
        verdict="clean",
        substitute_for=vote.voter_id,
        substitute_reviewer_ids=vote.reviewer_ids,
        substitute_review_authors=vote.review_authors,
        recorded_at=request.recorded_at,
    )


class HandlerReviewRecord:
    """Build typed records for each voter and substitute vote."""

    def handle(self, request: ModelReviewRecordRequest) -> ModelReviewRecordBatch:
        """Record each voter's review and each substitute vote of one run."""
        return ModelReviewRecordBatch(
            records=(
                *(_voter_record(request, r) for r in request.results),
                *(_substitute_record(request, v) for v in request.substitute_votes),
            )
        )


def handle(request: ModelReviewRecordRequest) -> ModelReviewRecordBatch:
    """The contract's routed entry point; see ``HandlerReviewRecord``."""
    return HandlerReviewRecord().handle(request)


__all__ = ["HandlerReviewRecord", "handle", "review_id_for"]
