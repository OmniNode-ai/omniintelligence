# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""What the node's overlay supplies: policy, quorum size and bus binding (OMN-22175)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_review_agent_receipt_verify_compute.models.enum_agent_receipt import (
    EnumAgentReceiptVerifyTransport,
)
from omniintelligence.nodes.node_review_agent_receipt_verify_compute.models.model_agent_receipt_policy import (
    ModelAgentReceiptPolicy,
)


class ModelAgentReceiptVerifierSettings(BaseModel):
    """The injected values a caller puts into each verify request."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    transport: EnumAgentReceiptVerifyTransport
    quorum_size: int = Field(ge=2)
    policy: ModelAgentReceiptPolicy


class ModelAgentReceiptVerifierTopics(BaseModel):
    """The command topic the node reads and the decided topic it writes."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    command: str = Field(min_length=1)
    decided: str = Field(min_length=1)


__all__ = ["ModelAgentReceiptVerifierSettings", "ModelAgentReceiptVerifierTopics"]
