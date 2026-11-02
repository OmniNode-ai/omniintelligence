# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""An agent review issues a signed ``hostile_review_agent_receipt.v1`` (OMN-22175).

The agent variant of the signed receipt: the same HMAC primitive as the base
receipt (``sign_fields``, domain-separated by the schema version) and the same
``onex-review-receipt`` fenced block, over the agent fields (nonce ``id``, the
counted ``voters`` with their provenance, ``roster_snapshot``, ``quorum_verdict``,
``blocking`` and ``findings_count``).

Pure: the quorum result, the key and the clock are inputs.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from omniintelligence.nodes.node_review_receipt_issue_compute.models.model_agent_review_receipt import (
    AGENT_RECEIPT_SCHEMA_VERSION,
    ModelAgentReceiptVoter,
    ModelAgentReviewReceipt,
    ModelRosterSnapshot,
)
from omniintelligence.nodes.node_review_receipt_issue_compute.models.model_issue_agent_receipt_request import (
    ModelIssueAgentReceiptRequest,
)
from omniintelligence.nodes.node_review_receipt_substitute_compute.handlers.handler_review_receipt_substitute import (
    sign_fields,
)
from omniintelligence.nodes.node_review_receipt_substitute_compute.models.model_review_receipt import (
    RECEIPT_FENCE,
)


def agent_receipt_signature(receipt: ModelAgentReviewReceipt, key: bytes) -> str:
    """HMAC-SHA256 over every field but the signature, domain-separated."""
    return sign_fields(
        AGENT_RECEIPT_SCHEMA_VERSION,
        receipt.model_dump(mode="json", exclude={"signature"}),
        key,
    )


def sign_agent_receipt(
    *,
    receipt_id: UUID,
    repo: str,
    pr: int,
    head_sha: str,
    reviewer_id: str,
    voters: tuple[ModelAgentReceiptVoter, ...],
    roster_snapshot: ModelRosterSnapshot,
    quorum_verdict: str,
    blocking: tuple[str, ...],
    findings_count: int,
    issued_at: datetime,
    key: bytes,
) -> ModelAgentReviewReceipt:
    """Build and sign an agent receipt."""
    unsigned = ModelAgentReviewReceipt.model_validate(
        {
            "id": receipt_id,
            "repo": repo,
            "pr": pr,
            "head_sha": head_sha,
            "reviewer_id": reviewer_id,
            "voters": voters,
            "roster_snapshot": roster_snapshot,
            "quorum_verdict": quorum_verdict,
            "blocking": blocking,
            "findings_count": findings_count,
            "issued_at": issued_at,
        }
    )
    return unsigned.model_copy(
        update={"signature": agent_receipt_signature(unsigned, key)}
    )


def render_agent_receipt_block(receipt: ModelAgentReviewReceipt) -> str:
    """The fenced block a reviewer posts in its pull request review body."""
    return f"```{RECEIPT_FENCE}\n{receipt.model_dump_json()}\n```"


class HandlerIssueAgentReceipt:
    """Issue a signed agent receipt."""

    def handle(self, request: ModelIssueAgentReceiptRequest) -> ModelAgentReviewReceipt:
        """Sign the agent review's quorum result for one head commit."""
        return sign_agent_receipt(
            receipt_id=request.id,
            repo=request.repo,
            pr=request.pr,
            head_sha=request.head_sha,
            reviewer_id=request.reviewer_id,
            voters=request.voters,
            roster_snapshot=request.roster_snapshot,
            quorum_verdict=request.quorum_verdict,
            blocking=request.blocking,
            findings_count=request.findings_count,
            issued_at=request.issued_at,
            key=request.key,
        )


def handle(request: ModelIssueAgentReceiptRequest) -> ModelAgentReviewReceipt:
    """The contract's routed entry point; see ``HandlerIssueAgentReceipt``."""
    return HandlerIssueAgentReceipt().handle(request)


__all__ = [
    "HandlerIssueAgentReceipt",
    "agent_receipt_signature",
    "handle",
    "render_agent_receipt_block",
    "sign_agent_receipt",
]
