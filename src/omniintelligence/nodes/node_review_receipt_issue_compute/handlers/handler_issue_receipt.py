# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""An off-CI reviewer issues a signed receipt and records its findings (OMN-20981).

The receipt format is unchanged (``hostile_review_receipt.v1``): a verdict and
a findings count, signed. The findings the count stands for used to be lost;
this handler returns them as a ``ModelReviewRecorded`` beside the receipt, with
exactly ``findings_count`` findings.

Pure: the findings, the key and the clock are inputs.
"""

from __future__ import annotations

from omniintelligence.models.handler_binding import bind_contract_handler
from omniintelligence.nodes.node_review_receipt_issue_compute.models.model_issue_receipt_request import (
    ModelIssueReceiptRequest,
)
from omniintelligence.nodes.node_review_receipt_issue_compute.models.model_issued_receipt import (
    ModelIssuedReceipt,
)
from omniintelligence.nodes.node_review_receipt_substitute_compute.handlers.handler_review_receipt_substitute import (
    sign_receipt,
)
from omniintelligence.nodes.node_review_record_compute.handlers.handler_review_record import (
    review_id_for,
)
from omniintelligence.nodes.node_review_record_compute.models import (
    ModelReviewRecorded,
)


class HandlerReviewReceiptIssue:
    """Issue a signed receipt alongside the record of its findings."""

    def handle(self, request: ModelIssueReceiptRequest) -> ModelIssuedReceipt:
        """Sign a receipt counting the findings, and record those findings."""
        receipt = sign_receipt(
            repo=request.repo,
            pr=request.pr,
            head_sha=request.head_sha,
            reviewer_id=request.reviewer_id,
            findings_count=len(request.findings),
            issued_at=request.issued_at,
            key=request.key,
        )
        record = ModelReviewRecorded(
            review_id=review_id_for(
                request.invocation_id, "receipt_reviewer", request.reviewer_id
            ),
            invocation_id=request.invocation_id,
            arm=request.reviewer_id,
            arm_kind="receipt_reviewer",
            reviewer_identity="receipt:" + request.reviewer_id,
            review_type="pr",
            repo=request.repo,
            pr=request.pr,
            head_sha=request.head_sha,
            execution_status="completed",
            verdict=receipt.verdict,
            findings=request.findings,
            recorded_at=request.issued_at,
        )
        return ModelIssuedReceipt(receipt=receipt, record=record)


def handle(request: ModelIssueReceiptRequest) -> ModelIssuedReceipt:
    """The contract's routed entry point; see ``HandlerReviewReceiptIssue``."""
    return bind_contract_handler("issue_receipt", HandlerReviewReceiptIssue).handle(
        request
    )


__all__ = ["HandlerReviewReceiptIssue", "handle"]
