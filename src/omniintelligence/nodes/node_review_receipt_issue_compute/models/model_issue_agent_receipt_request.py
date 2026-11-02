# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input of the agent receipt issuing operation (OMN-22175)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from omniintelligence.nodes.node_review_receipt_issue_compute.models.model_agent_review_receipt import (
    ModelAgentReceiptVoter,
    ModelRosterSnapshot,
)


class ModelIssueAgentReceiptRequest(BaseModel):
    """An agent review's quorum result on one head commit, and the key to sign with."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    id: UUID
    repo: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    pr: int = Field(gt=0)
    head_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    reviewer_id: str = Field(min_length=1, max_length=63)
    voters: tuple[ModelAgentReceiptVoter, ...]
    roster_snapshot: ModelRosterSnapshot
    quorum_verdict: Literal["passed", "blocked"]
    blocking: tuple[str, ...] = ()
    findings_count: int = Field(ge=0)
    issued_at: datetime = Field(description="The reviewer's clock, timezone-aware.")
    key: bytes = Field(min_length=1, description="The receipt signing key.")

    @model_validator(mode="after")
    def _validate_request(self) -> Self:
        if (self.quorum_verdict == "blocked") != bool(self.blocking):
            raise ValueError(
                "quorum_verdict is 'blocked' exactly when blocking findings are listed"
            )
        if len(self.blocking) > self.findings_count:
            raise ValueError("blocking lists more findings than findings_count counts")
        return self


__all__ = ["ModelIssueAgentReceiptRequest"]
