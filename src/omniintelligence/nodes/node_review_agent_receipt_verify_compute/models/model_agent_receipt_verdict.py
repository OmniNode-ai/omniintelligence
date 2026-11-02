# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output of the agent receipt verifier (OMN-22175)."""

from __future__ import annotations

from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from omniintelligence.nodes.node_review_agent_receipt_verify_compute.models.enum_agent_receipt import (
    EnumAgentReceiptDecision,
    EnumAgentReceiptRefusal,
)


class ModelAgentReceiptVerdict(BaseModel):
    """``accepted`` with the voter identities, or ``refused`` with one typed reason."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    decision: EnumAgentReceiptDecision
    reason: EnumAgentReceiptRefusal | None = None
    detail: str = ""
    voter_identities: tuple[str, ...] = ()
    receipt_id: UUID | None = None

    @model_validator(mode="after")
    def _validate_verdict(self) -> Self:
        if self.decision is EnumAgentReceiptDecision.ACCEPTED:
            if self.reason is not None or not self.voter_identities:
                raise ValueError("accepted carries voter identities and no reason")
        elif self.reason is None or not self.detail or self.voter_identities:
            raise ValueError("refused carries a reason and a detail, and no voters")
        return self


__all__ = ["ModelAgentReceiptVerdict"]
