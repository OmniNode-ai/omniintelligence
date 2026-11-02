# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input of the agent receipt verifier (OMN-22175)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_review_agent_receipt_verify_compute.models.model_agent_receipt_policy import (
    ModelAgentReceiptPolicy,
)
from omniintelligence.nodes.node_review_receipt_issue_compute.models.model_agent_review_receipt import (
    ModelAgentReviewReceipt,
)


class ModelAgentReceiptContext(BaseModel):
    """The one thing the receipt is checked against: the pull request head in hand."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    repo: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    pr: int = Field(gt=0)
    head_sha: str = Field(pattern=r"^[0-9a-f]{40}$")


class ModelAgentReceiptVerifyRequest(BaseModel):
    """The receipt, the key, the injected policy, the quorum size and the context."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    receipt: ModelAgentReviewReceipt
    key: bytes = Field(min_length=1, description="The receipt signing key.")
    policy: ModelAgentReceiptPolicy
    quorum_size: int = Field(ge=2, description="Distinct voters a receipt must carry.")
    context: ModelAgentReceiptContext


__all__ = ["ModelAgentReceiptContext", "ModelAgentReceiptVerifyRequest"]
